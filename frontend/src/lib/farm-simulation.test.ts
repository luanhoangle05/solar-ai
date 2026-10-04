import { beforeAll, describe, expect, it } from "vitest";
import { loadFrontendData } from "./frontend-data.server";
import { getCandidateAngleRange, getPreviewAngle, getPreviewFarm, getPreviewRowIds, getRowSimulationView, getSimulationConditions } from "./farm-simulation";
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
  it("previews only the control row when no other row shares its action", () => expect(getPreviewRowIds(data)).toEqual(["row-001"]));
  it("previews every row the payload marks with the same action, state and angle", () => {
    const marked = { ...data, farm_status: { ...data.farm_status, rows: data.farm_status.rows.map(row => row.current_state === "READY" ? { ...row, action: "ROTATE" as const } : row) } };
    const ready = data.farm_status.rows.filter(row => row.current_state === "READY").map(row => row.row_id);
    expect(getPreviewRowIds(marked)).toEqual(ready);
    const preview = getPreviewFarm(marked);
    expect(preview.rows.filter(row => row.current_state === "READY").every(row => row.angle_deg === 45)).toBe(true);
    expect(preview.rows.filter(row => row.current_state !== "READY").map(row => row.angle_deg)).toEqual(data.farm_status.rows.filter(row => row.current_state !== "READY").map(row => row.angle_deg));
  });
  it("does not preview a marked row that sits at a different angle", () => {
    const marked = { ...data, farm_status: { ...data.farm_status, rows: data.farm_status.rows.map(row => row.row_id === "row-002" ? { ...row, action: "ROTATE" as const, angle_deg: 50 } : row) } };
    expect(getPreviewRowIds(marked)).toEqual(["row-001"]);
  });
  it("previews no rows when the manager holds", () => expect(getPreviewRowIds({ ...data, decision: { action: "HOLD", target_angle_deg: 35, reason: "Blocked" } })).toEqual([]));
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
  it("says so when the target has no optimization result", () => expect(getRowSimulationView({ ...data, optimization: null }, "row-001")).toMatchObject({ recommendedAngle: null, gain: null, reasoning: expect.arrayContaining(["No optimization result was supplied for this run."]) }));
  it("takes the tracking range from the evaluated candidate angles", () => expect(getCandidateAngleRange(data)).toEqual({ minDeg: 30, maxDeg: 60 }));
  it("offers no tracking range without candidates", () => expect(getCandidateAngleRange({ candidate_predictions: [] })).toBeNull());
  it("returns null for an unknown row", () => expect(getRowSimulationView(data, "row-999")).toBeNull());
});
