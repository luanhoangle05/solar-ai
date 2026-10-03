import { beforeAll, describe, expect, it } from "vitest";
import { loadFrontendData } from "./frontend-data.server";
import { frontendDataSchema } from "../schemas/frontend-data";
import { getControlTargetRow, getSelectedModel } from "./selectors";
import { getCandidateInsight, getControlTargetZone, getDashboardSummary, getLatestAgentEvents, getRawEnergyMaximum, getZoneSummaries } from "./dashboard";
import { formatDisplayName, formatMetric, formatRecordedTime } from "./formatters";
import { actionPresentation } from "../config/actions";
import { dataStatusVariants } from "../config/status";
import type { FrontendData } from "../types/solar";

let fixture: FrontendData;
beforeAll(async () => { fixture = await loadFrontendData(); });

function unavailableRun(): FrontendData {
  const data = structuredClone(fixture);
  data.current_weather = null;
  data.optimization = null;
  data.selected_model = null;
  data.candidate_predictions = [];
  data.model_comparison = data.model_comparison.map(model => ({ ...model, status: "UNAVAILABLE", mae: null, rmse: null, r2: null }));
  data.decision = { action: "HOLD", target_angle_deg: 35, reason: "Test unavailable state" };
  data.farm_status.rows[0].action = "HOLD";
  data.agent_log = [];
  data.history = [];
  return frontendDataSchema.parse(data);
}

describe("dashboard fixture regression", () => {
  it("retains contract values and distinguishes observed state from proposed action", () => {
    const summary = getDashboardSummary(fixture);
    expect(summary.currentAngleDeg).toBe(35);
    expect(summary.recommendedAngleDeg).toBe(45);
    expect(summary.predictedKwh).toBe(6.09);
    expect(summary.energyGainKwh).toBeCloseTo(0.29);
    expect(summary.netBenefitKwhEquivalent).toBe(0.26);
    expect(summary.decisionAction).toBe("ROTATE");
    expect(summary.decisionTargetAngleDeg).toBe(45);
    expect(summary.targetRow?.angle_deg).toBe(35);
    expect(summary.weather?.temperature_c).toBe(22);
    expect(fixture.farm_status.total_panels).toBe(1000);
    expect(fixture.farm_status.rows).toHaveLength(50);
  });
  it("looks up the target row and its zone from contract IDs", () => {
    expect(getControlTargetRow(fixture)?.row_id).toBe("row-001");
    expect(getControlTargetZone(fixture)?.zone_id).toBe("zone-01");
    const changed = structuredClone(fixture);
    changed.metadata.control_target_id = "row-050";
    expect(getControlTargetZone(changed)?.zone_id).toBe("zone-04");
  });
  it("looks up the selected model without selecting a model in the UI", () => {
    expect(getSelectedModel(fixture)).toMatchObject({ model: "boosting", implementation: "xgboost", status: "MOCK" });
  });
  it("derives zone counts and highlights only the target zone", () => {
    const zones = getZoneSummaries(fixture);
    expect(zones.map(zone => zone.panelCount)).toEqual([260, 240, 260, 240]);
    expect(zones.map(zone => zone.rowCount)).toEqual([13, 12, 13, 12]);
    expect(zones.filter(zone => zone.isTarget).map(zone => zone.id)).toEqual(["zone-01"]);
    expect(Object.values(getDashboardSummary(fixture).rowStates).reduce((a, b) => a + b, 0)).toBe(50);
  });
  it("explains raw maximum separately from the backend recommendation", () => {
    expect(getRawEnergyMaximum(fixture.candidate_predictions)).toEqual({ angle_deg: 60, predicted_kwh: 6.11 });
    expect(getCandidateInsight(fixture)).toContain("60° has the highest raw predicted energy");
    expect(getCandidateInsight(fixture)).toContain("backend recommends 45°");
  });
  it("handles matching maxima and ties without making a false difference claim", () => {
    const data = structuredClone(fixture);
    data.candidate_predictions = [{ angle_deg: 30, predicted_kwh: 7 }, { angle_deg: 45, predicted_kwh: 7 }];
    expect(getCandidateInsight(data)).toContain("recommendation also reaches the highest");
  });
  it("sorts candidates for display without mutating the contract", () => {
    const data = structuredClone(fixture);
    data.candidate_predictions.reverse();
    const before = structuredClone(data);
    expect(getDashboardSummary(data).candidates[0].angle_deg).toBe(30);
    expect(data).toEqual(before);
  });
  it("limits recent events while retaining chronological order without mutation", () => {
    const data = structuredClone(fixture);
    data.agent_log.reverse();
    const before = structuredClone(data.agent_log);
    const events = getLatestAgentEvents(data, 4);
    expect(events).toHaveLength(4);
    expect(events[0].timestamp).toBe("2026-06-21T18:59:04Z");
    expect(events[3].agent).toBe("manager");
    expect(data.agent_log).toEqual(before);
  });
});

describe("unavailable and failure states", () => {
  it("accepts a valid run with no weather, optimization, model, candidates, events or history", () => {
    const data = unavailableRun();
    const summary = getDashboardSummary(data);
    expect(summary.weather).toBeNull();
    expect(summary.optimization).toBeNull();
    expect(summary.selectedModel).toBeNull();
    expect(summary.currentAngleDeg).toBe(35);
    expect(summary.recommendedAngleDeg).toBeNull();
    expect(summary.predictedKwh).toBeNull();
    expect(summary.energyGainKwh).toBeNull();
    expect(summary.netBenefitKwhEquivalent).toBeNull();
    expect(summary.candidates).toEqual([]);
    expect(summary.events).toEqual([]);
    expect(summary.rawMaximum).toBeNull();
    expect(data.history).toEqual([]);
    expect(getCandidateInsight(data)).toContain("No candidate predictions");
  });
  it("does not invent an observed angle when the target cannot be found", () => {
    const data = unavailableRun();
    data.metadata.control_target_id = "unknown-row";
    expect(getDashboardSummary(data).currentAngleDeg).toBeNull();
    expect(getControlTargetZone(data)).toBeNull();
  });
  it("supports a contract-valid severe safety failure with STOW", () => {
    const data = unavailableRun();
    data.safety.passed = false;
    data.safety.checks[0].passed = false;
    data.decision.action = "STOW";
    data.decision.target_angle_deg = 0;
    data.farm_status.rows[0].action = "STOW";
    const validated = frontendDataSchema.parse(data);
    expect(getDashboardSummary(validated).decisionAction).toBe("STOW");
    expect(validated.safety.checks.filter(check => !check.passed)).toHaveLength(1);
  });
  it.each([ ["ROTATE", "success"], ["HOLD", "warning"], ["STOW", "danger"] ] as const)("presents %s as %s", (action, variant) => {
    expect(actionPresentation[action].variant).toBe(variant);
    expect(actionPresentation[action].icon).toBeDefined();
  });
  it.each([ ["VALID", "success"], ["DEGRADED", "warning"], ["STALE", "warning"], ["INVALID", "danger"] ] as const)("presents data status %s as %s", (status, variant) => {
    expect(dataStatusVariants[status]).toBe(variant);
  });
});

describe("dashboard formatting", () => {
  it("preserves metric precision and unavailable values", () => {
    expect(formatMetric(0.090138781)).toBe("0.0901");
    expect(formatMetric(null)).toBe("Unavailable");
    expect(formatDisplayName("wind_safety")).toBe("Wind Safety");
  });
  it("formats recorded times in a deterministic explicit timezone", () => {
    expect(formatRecordedTime("2026-06-21T19:00:00Z", false)).toBe("19:00:00 UTC");
    expect(formatRecordedTime("2026-06-21T21:00:00+02:00", false)).toBe("19:00:00 UTC");
  });
});
