import { beforeAll, describe, expect, it } from "vitest";
import { loadFrontendData, loadZoneRuns, resolveZoneRunPaths, resolveMockFrontendDataPath } from "./frontend-data.server";
import { getCandidateAngleRange, getPreviewAngle, getPreviewFarm, getRunForRow, getRunsPreviewFarm, getRunsPreviewRowCount, getRowSimulationView, getSimulationConditions } from "./farm-simulation";
import type { FrontendData } from "../types/solar";
let data: FrontendData;
beforeAll(async () => { data = await loadFrontendData(); });
describe("solar farm simulation view", () => {
  it("shows the supplied weather snapshot", () => expect(getSimulationConditions(data).weather?.map(item => item.value)).toEqual(["850 W/m²", "15%", "22°C", "14 km/h"]));
  it("reports missing weather as null, not zeros", () => expect(getSimulationConditions({ ...data, current_weather: null }).weather).toBeNull());
  it("shows the recorded interval and horizon", () => expect(getSimulationConditions(data)).toMatchObject({ interval: "21 Jun 2026, 19:00:00 UTC", horizon: "60 min" }));
  it("previews the manager's decided target", () => expect(getPreviewAngle(data)).toBe(45));
  it("previews a STOW at the stow angle", () => expect(getPreviewAngle({ ...data, decision: { action: "STOW", target_angle_deg: 0, reason: "Severe wind" } })).toBe(0));
  it("has no preview when the manager holds, even if another angle was recommended", () => expect(getPreviewAngle({ ...data, decision: { action: "HOLD", target_angle_deg: 35, reason: "Blocked" } })).toBeNull());
  it("draws only the control target at the recommended angle", () => {
    const preview = getPreviewFarm(data);
    expect(preview.rows.find(row => row.row_id === "row-001")?.angle_deg).toBe(45);
    expect(preview.rows.filter(row => row.row_id !== "row-001")).toEqual(data.farm_status.rows.filter(row => row.row_id !== "row-001"));
  });
  it("never changes the validated payload", () => { getPreviewFarm(data); expect(data.farm_status.rows[0].angle_deg).toBe(35); });
  it("returns the same farm when nothing can be previewed", () => expect(getPreviewFarm({ ...data, decision: { action: "HOLD", target_angle_deg: 35, reason: "Blocked" } })).toBe(data.farm_status));
  it("describes the control target with its recommendation", () => expect(getRowSimulationView(data, "row-001")).toMatchObject({ isTarget: true, zoneName: "Zone 1", position: "Row 1 of 13", currentAngle: 35, recommendedAngle: 45, gain: "+0.29 kWh", horizon: "60 min" }));
  it("restates supplied values as reasoning", () => expect(getRowSimulationView(data, "row-001")?.reasoning).toEqual([
    "45° gives the best net benefit (+0.26 kWh eq.).",
    "Energy gain +0.29 kWh against movement cost 0.03 kWh eq.",
    `Safety passed: ${data.safety.reason}`,
    `Decision ROTATE → 45°: ${data.decision.reason}`,
  ]));
  it("gives other rows no recommendation, gain or reasoning", () => {
    const other = data.farm_status.rows.find(row => row.row_id !== "row-001")!;
    expect(getRowSimulationView(data, other.row_id)).toMatchObject({ isTarget: false, recommendedAngle: null, gain: null, reasoning: [], currentAngle: other.angle_deg });
  });
  it("shows the control row's recommendation and reasoning on a row that shares its action, state and angle", () => {
    const marked = { ...data, farm_status: { ...data.farm_status, rows: data.farm_status.rows.map(row => row.row_id === "row-002" ? { ...row, action: "ROTATE" as const } : row) } };
    const view = getRowSimulationView(marked, "row-002")!;
    expect(view).toMatchObject({ isTarget: false, appliesDecision: true, recommendedAngle: 45, gain: "+0.29 kWh" });
    expect(view.reasoning[0]).toBe("Same state and angle as control row row-001, so its decision is shown here; it was not computed separately for this row.");
    expect(view.reasoning.slice(1)).toEqual(getRowSimulationView(marked, "row-001")!.reasoning);
  });
  it("shows no recommendation on a marked row in a different state", () => {
    const stowed = data.farm_status.rows.find(row => row.current_state === "STOWED")!;
    const marked = { ...data, farm_status: { ...data.farm_status, rows: data.farm_status.rows.map(row => row.row_id === stowed.row_id ? { ...row, action: "ROTATE" as const } : row) } };
    expect(getRowSimulationView(marked, stowed.row_id)).toMatchObject({ appliesDecision: false, recommendedAngle: null, reasoning: [] });
  });
  it("marks the control target as carrying the decision", () => expect(getRowSimulationView(data, "row-001")).toMatchObject({ isTarget: true, appliesDecision: true }));
  describe("several runs over one farm", () => {
    // Two runs sharing one farm: zone 1 starts at 35 and rotates to 45; zone 2 starts at 50 and holds.
    const zoneTwo = () => data.farm_status.zones[1];
    const farm = () => ({ ...data.farm_status, rows: data.farm_status.rows.map(row => row.current_state !== "READY" ? row
      : row.zone_id === zoneTwo().zone_id ? { ...row, angle_deg: 50, action: "HOLD" as const }
      : row.zone_id === "zone-01" ? { ...row, action: "ROTATE" as const } : row) });
    const first = () => ({ ...data, farm_status: farm() });
    const second = () => ({ ...data, farm_status: farm(), metadata: { ...data.metadata, control_target_id: zoneTwo().row_ids[0] },
      decision: { action: "HOLD" as const, target_angle_deg: 50, reason: "Zone two holds" },
      optimization: { ...data.optimization!, current_angle_deg: 50, recommended_angle_deg: 50 } });
    it("finds the run that decided for a row", () => {
      expect(getRunForRow([first(), second()], "row-002").metadata.control_target_id).toBe("row-001");
      expect(getRunForRow([first(), second()], zoneTwo().row_ids[1]).decision.reason).toBe("Zone two holds");
    });
    it("falls back to the first run for a row no run covers", () => {
      const stowed = data.farm_status.rows.find(row => row.current_state === "STOWED")!;
      expect(getRunForRow([first(), second()], stowed.row_id).metadata.control_target_id).toBe("row-001");
      expect(getRunForRow([first(), second()], null).metadata.control_target_id).toBe("row-001");
    });
    it("shows each zone its own run's recommendation", () => {
      const row = zoneTwo().row_ids[1];
      expect(getRowSimulationView(getRunForRow([first(), second()], row), row)).toMatchObject({ appliesDecision: true, currentAngle: 50, recommendedAngle: 50 });
      expect(getRowSimulationView(getRunForRow([first(), second()], "row-002"), "row-002")).toMatchObject({ appliesDecision: true, currentAngle: 35, recommendedAngle: 45 });
    });
    it("previews every run's rows at that run's target and leaves holding zones alone", () => {
      const preview = getRunsPreviewFarm([first(), second()]);
      expect(preview.rows.filter(row => row.zone_id === "zone-01" && row.current_state === "READY").every(row => row.angle_deg === 45)).toBe(true);
      expect(preview.rows.filter(row => row.zone_id === zoneTwo().zone_id && row.current_state === "READY").every(row => row.angle_deg === 50)).toBe(true);
    });
    it("counts the rows the previews move", () => expect(getRunsPreviewRowCount([first(), second()])).toBe(data.farm_status.rows.filter(row => row.zone_id === "zone-01" && row.current_state === "READY").length));
    it("returns the farm unchanged when no run moves anything", () => { const run = second(); expect(getRunsPreviewFarm([run])).toBe(run.farm_status); });
  });
  it("says so when the target has no optimization result", () => expect(getRowSimulationView({ ...data, optimization: null }, "row-001")).toMatchObject({ recommendedAngle: null, gain: null, reasoning: expect.arrayContaining(["No optimization result was supplied for this run."]) }));
  it("takes the tracking range from the evaluated candidate angles", () => expect(getCandidateAngleRange(data)).toEqual({ minDeg: 30, maxDeg: 60 }));
  it("offers no tracking range without candidates", () => expect(getCandidateAngleRange({ candidate_predictions: [] })).toBeNull());
  it("returns null for an unknown row", () => expect(getRowSimulationView(data, "row-999")).toBeNull());
});

describe("configured zone analysis loading", () => {
  it("uses no additional runs by default", async () => {
    expect(resolveZoneRunPaths({})).toEqual([]);
    expect(await loadZoneRuns([])).toEqual({ runs: [], error: null });
  });
  it("validates each configured file through the existing loader", async () => {
    const result = await loadZoneRuns([resolveMockFrontendDataPath()]);
    expect(result.error).toBeNull();
    expect(result.runs).toEqual([data]);
  });
  it("returns no partial runs when a configured file fails", async () => {
    const result = await loadZoneRuns([resolveMockFrontendDataPath(), "missing-zone-analysis.json"]);
    expect(result.runs).toEqual([]);
    expect(result.error).toContain("could not be read");
  });
});
