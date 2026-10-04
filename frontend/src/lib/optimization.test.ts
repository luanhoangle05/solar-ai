import { beforeAll, describe, expect, it } from "vitest";
import { loadFrontendData } from "./frontend-data.server";
import { frontendDataSchema } from "../schemas/frontend-data";
import { getCandidateRoles, getCurrentCandidate, getOptimizationAgentEvents, getOptimizationSummary, getRawEnergyMaxCandidates, getRecommendedCandidate } from "./optimization";
import { formatCandidateEnergy, formatKwhEquivalent, formatMovementCost } from "./formatters";
import { actionPresentation } from "../config/actions";
import { dataStatusVariants } from "../config/status";
import type { FrontendData } from "../types/solar";

let fixture: FrontendData;
beforeAll(async () => { fixture = await loadFrontendData(); });
function unavailable() {
  const data = structuredClone(fixture);
  data.optimization = null;
  data.selected_model = null;
  data.candidate_predictions = [];
  data.current_weather = null;
  data.model_comparison = data.model_comparison.map(model => ({ ...model, status: "UNAVAILABLE", mae: null, rmse: null, r2: null }));
  data.decision = { action: "HOLD", target_angle_deg: 35, reason: "Unavailable test run" };
  data.farm_status.rows[0].action = "HOLD";
  return frontendDataSchema.parse(data);
}

describe("optimization display selectors", () => {
  it("finds the current candidate", () => expect(getCurrentCandidate(fixture)).toEqual({ angle_deg: 35, predicted_kwh: 5.8 }));
  it("finds the backend recommended candidate", () => expect(getRecommendedCandidate(fixture)).toEqual({ angle_deg: 45, predicted_kwh: 6.09 }));
  it("finds a unique raw maximum", () => expect(getRawEnergyMaxCandidates(fixture.candidate_predictions)).toEqual([{ angle_deg: 60, predicted_kwh: 6.11 }]));
  it("preserves all tied raw maxima", () => {
    const points = [{ angle_deg: 30, predicted_kwh: 4 }, { angle_deg: 40, predicted_kwh: 5 }, { angle_deg: 50, predicted_kwh: 5 }];
    expect(getRawEnergyMaxCandidates(points)).toEqual(points.slice(1));
  });
  it("does not confuse the raw maximum with the recommendation", () => {
    const summary = getOptimizationSummary(fixture);
    expect(summary.recommendationIsRawMax).toBe(false);
    expect(summary.insight).toContain("backend recommends 45°");
    expect(summary.recommendedCandidate?.angle_deg).not.toBe(summary.rawMaxima[0].angle_deg);
  });
  it("recognizes matching recommendation and maximum without a false difference claim", () => {
    const data = structuredClone(fixture);
    data.candidate_predictions = data.candidate_predictions.filter(point => point.angle_deg <= 45);
    const summary = getOptimizationSummary(frontendDataSchema.parse(data));
    expect(summary.recommendationIsRawMax).toBe(true);
    expect(summary.insight).toContain("recommendation also reaches the highest");
    expect(summary.recommendedAngle).toBe(45);
  });
  it("combines all overlapping roles on one candidate", () => {
    expect(getCandidateRoles({ angle_deg: 40, predicted_kwh: 6 }, 40, 40, 6)).toEqual(["Current", "Recommended", "Raw Max"]);
  });
  it("combines recommended/raw-max roles for every matching point", () => {
    const data = structuredClone(fixture);
    data.candidate_predictions = [{ angle_deg: 35, predicted_kwh: 5.8 }, { angle_deg: 45, predicted_kwh: 6.09 }, { angle_deg: 55, predicted_kwh: 6.09 }];
    const summary = getOptimizationSummary(frontendDataSchema.parse(data));
    expect(summary.rawMaxima).toHaveLength(2);
    expect(summary.candidates[1].roles).toEqual(["Recommended", "Raw Max"]);
    expect(summary.candidates[2].roles).toEqual(["Raw Max"]);
  });
  it("preserves the actual fixture economics, scope, model and decision", () => {
    const summary = getOptimizationSummary(fixture);
    expect(summary.comparison).toMatchObject({ currentAngle:35, recommendedAngle:45, baseline:5.8, predicted:6.09, movementCost:0.03, netBenefit:0.26 });
    expect(summary.comparison?.gain).toBeCloseTo(0.29);
    expect(summary.decision).toMatchObject({ action:"ROTATE", target_angle_deg:45 });
    expect(summary.model?.model).toBe("boosting");
    expect(summary.target?.row_id).toBe("row-001");
    expect(summary.candidates).toHaveLength(7);
    expect(fixture.metadata).toMatchObject({ energy_scope:"row", prediction_horizon_minutes:60 });
  });
  it("keeps comparison values supplied by optimization, not frontend economics", () => {
    const data = structuredClone(fixture);
    data.optimization!.movement_cost_kwh_equivalent = 0.1;
    data.optimization!.net_benefit_kwh_equivalent = 0.19;
    const summary = getOptimizationSummary(frontendDataSchema.parse(data));
    expect(summary.comparison?.movementCost).toBe(0.1);
    expect(summary.comparison?.netBenefit).toBe(0.19);
  });
  it("does not mutate or reorder the loaded payload", () => {
    const data = structuredClone(fixture);
    data.candidate_predictions.reverse(); data.agent_log.reverse();
    const before = structuredClone(data);
    const summary = getOptimizationSummary(data);
    expect(summary.candidates.map(point => point.angle_deg)).toEqual([30,35,40,45,50,55,60]);
    expect(data).toEqual(before);
  });
  it("does not invent per-candidate economics", () => {
    const point = getOptimizationSummary(fixture).candidates[0];
    expect(Object.keys(point).sort()).toEqual(["angle_deg", "predicted_kwh", "roles"]);
  });
  it("supports a null optimization without fake zeros or a proposed angle as current", () => {
    const summary = getOptimizationSummary(unavailable());
    expect(summary.optimization).toBeNull(); expect(summary.comparison).toBeNull();
    expect(summary.currentAngle).toBeNull(); expect(summary.recommendedAngle).toBeNull();
    expect(summary.currentCandidate).toBeNull(); expect(summary.recommendedCandidate).toBeNull();
    expect(summary.target?.angle_deg).toBe(35);
  });
  it("supports empty candidate predictions", () => {
    const summary = getOptimizationSummary(unavailable());
    expect(summary.candidates).toEqual([]); expect(summary.rawMaxima).toEqual([]);
    expect(summary.insight).toContain("No candidate predictions");
  });
  it("does not imply optimization when only raw predictions are available", () => {
    const data = structuredClone(fixture); data.optimization = null;
    const summary = getOptimizationSummary(data);
    expect(summary.insight).toContain("optimization is unavailable");
    expect(summary.recommendedCandidate).toBeNull();
  });
  it("finds the selected model and its actual implementation", () => expect(getOptimizationSummary(fixture).model).toMatchObject({model:"boosting",implementation:"xgboost",status:"MOCK"}));
  it("supports a missing selected model", () => expect(getOptimizationSummary(unavailable()).model).toBeNull());
  it("does not select a fallback model if lookup fails", () => {
    const data = structuredClone(fixture); data.model_comparison = [];
    expect(getOptimizationSummary(data).model).toBeNull();
  });
  it("filters and orders only actual optimization/manager handoff events", () => {
    const data = structuredClone(fixture); data.agent_log.reverse();
    const events = getOptimizationAgentEvents(data);
    expect(events.map(event => event.action)).toEqual(["candidate_comparison", "recommendation", "safety"]);
    expect(events[2].result).toBe("MOCK checks passed; no controller executed");
  });
  it("handles no handoff events", () => {
    const data = structuredClone(fixture); data.agent_log = [];
    expect(getOptimizationAgentEvents(data)).toEqual([]);
  });
});

describe("result and status fidelity", () => {
  it.each([["ROTATE","success"],["HOLD","warning"],["STOW","danger"]] as const)("preserves %s decision and %s presentation", (action,variant) => {
    const data = action === "ROTATE" ? structuredClone(fixture) : unavailable();
    data.decision.action = action; data.farm_status.rows[0].action = action;
    if (action === "STOW") data.decision.target_angle_deg = 0;
    const summary = getOptimizationSummary(frontendDataSchema.parse(data));
    expect(summary.decision.action).toBe(action);
    expect(actionPresentation[summary.decision.action].variant).toBe(variant);
  });
  it("preserves passed safety", () => expect(getOptimizationSummary(fixture).safety.passed).toBe(true));
  it("preserves severe failure and STOW without recalculating safety", () => {
    const data = unavailable(); data.safety.passed = false; data.safety.checks[0].passed = false;
    data.decision = { action:"STOW",target_angle_deg:0,reason:"Test safety override" }; data.farm_status.rows[0].action = "STOW";
    const summary = getOptimizationSummary(frontendDataSchema.parse(data));
    expect(summary.safety.passed).toBe(false); expect(summary.decision.action).toBe("STOW");
    expect(summary.safety.checks[0].severity).toBe("SEVERE");
  });
  it.each([["VALID","success"],["DEGRADED","warning"],["STALE","warning"],["INVALID","danger"]] as const)("keeps %s data status with %s presentation", (status,variant) => {
    const data = unavailable(); data.data_agent.status = status;
    if (status !== "VALID") data.data_agent.issues = ["Test data-health issue"];
    const validated = frontendDataSchema.parse(data);
    expect(dataStatusVariants[validated.data_agent.status]).toBe(variant);
    expect(getOptimizationSummary(validated).decision.action).toBe("HOLD");
  });
});

describe("candidate and economics formatting", () => {
  it("distinguishes close predictions", () => expect([6.1,6.105,6.11].map(formatCandidateEnergy)).toEqual(["6.100 kWh","6.105 kWh","6.110 kWh"]));
  it("does not expose floating-point noise", () => expect(formatCandidateEnergy(0.29000000000000004)).toBe("0.290 kWh"));
  it("does not turn missing energy into zero", () => expect(formatCandidateEnergy(null)).toBe("Unavailable"));
  it("keeps equivalent units and signed net benefit", () => {
    expect(formatMovementCost(0.03)).toBe("0.03 kWh eq.");
    expect(formatKwhEquivalent(-0.03)).toBe("-0.03 kWh eq.");
  });
});
