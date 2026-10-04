import { beforeAll, describe, expect, it } from "vitest";
import { loadFrontendData } from "./frontend-data.server";
import { agentOrder, formatAgentName, getAgentEvents, getAgentPipelineSummary, getAgentsSummary, getDecisionAngleLabel, getModelDisplay, getSafetyCheckTone } from "./agents";
import { formatMetric, formatModelName } from "./formatters";
import { dataStatusVariants } from "../config/status";
import type { FrontendData, ModelMetrics } from "../types/solar";
import { modelMetricsSchema, dataAgentReportSchema, safetyResultSchema } from "../schemas/frontend-data";

let fixture: FrontendData;
beforeAll(async () => { fixture = await loadFrontendData(); });

describe("model presentation", () => {
  it("finds the supplied selected model", () => expect(getAgentsSummary(fixture).selectedModel?.implementation).toBe("xgboost"));
  it("does not choose a model when selection is null", () => {
    const data = { ...fixture, selected_model:null };
    expect(getAgentsSummary(data).selectedModel).toBeNull();
    expect(getAgentsSummary(data).models.every(model => !model.selected)).toBe(true);
  });
  it.each([["linear_regression","Linear Regression"],["random_forest","Random Forest"],["boosting","Boosting"],["lstm","LSTM"]] as const)("formats %s", (model,label) => expect(formatModelName(model)).toBe(label));
  it.each(["MOCK","VALIDATED","UNAVAILABLE"] as const)("supports %s without changing its meaning", status => {
    const model = modelMetricsSchema.parse({ ...fixture.model_comparison[0], status, ...(status === "UNAVAILABLE" ? {mae:null,rmse:null,r2:null} : {}) });
    const view = getModelDisplay(model, null);
    expect(view.status).toBe(status);
    expect(view.provenance).toBe(status === "MOCK" ? "Synthetic fixture metrics" : status === "UNAVAILABLE" ? "Metrics unavailable" : "Validated status supplied by payload");
  });
  it("uses dashes for unavailable metrics, never zero", () => {
    const model: ModelMetrics = {...fixture.model_comparison[0],status:"UNAVAILABLE",mae:null,rmse:null,r2:null};
    expect(getModelDisplay(model,null).metrics).toEqual(["—","—","—"]);
  });
  it("formats metrics to four decimals without percent conversion", () => expect([0.0875,0.090138781923,0.9935].map(formatMetric)).toEqual(["0.0875","0.0901","0.9935"]));
  it("marks only the selected key without ranking metrics", () => {
    const data = {...fixture,selected_model:"lstm" as const};
    expect(getAgentsSummary(data).models.filter(model => model.selected).map(model => model.model)).toEqual(["lstm"]);
  });
  it("preserves model collection order", () => {
    const data = {...fixture,model_comparison:[...fixture.model_comparison].reverse()};
    expect(getAgentsSummary(data).models.map(model => model.model)).toEqual(data.model_comparison.map(model => model.model));
  });
  it("preserves fixture metrics and selection", () => {
    const summary = getAgentsSummary(fixture);
    expect(summary.models).toHaveLength(4);
    expect(summary.selectedModel).toMatchObject({model:"boosting",implementation:"xgboost",status:"MOCK",r2:0.9935});
    expect(summary.selectedModel?.mae).toBeCloseTo(0.0875,8);
    expect(summary.selectedModel?.rmse).toBeCloseTo(0.0901388,6);
    summary.models.forEach((model,index) => expect(model.mae).toBeCloseTo([0.4,0.175,0.0875,0.275][index],8));
  });
});

describe("data quality", () => {
  it.each(["VALID","DEGRADED","STALE","INVALID"] as const)("preserves %s", status => {
    const report = dataAgentReportSchema.parse({...fixture.data_agent,status,issues:status === "VALID" ? [] : ["Actual issue"]});
    const summary = getAgentsSummary({...fixture,data_agent:report});
    expect(summary.dataQuality.status).toBe(status);
    expect(dataStatusVariants[status]).toBe(status === "VALID" ? "success" : status === "INVALID" ? "danger" : "warning");
  });
  it("preserves supplied issue strings", () => {
    const report = {...fixture.data_agent,issues:["Provider unavailable","Cached input"]};
    expect(getAgentsSummary({...fixture,data_agent:report}).dataQuality.issues).toEqual(report.issues);
  });
  it.each([true,false])("preserves cache use %s", used_cache => expect(getAgentsSummary({...fixture,data_agent:{...fixture.data_agent,used_cache}}).dataQuality.used_cache).toBe(used_cache));
  it("preserves unknown forecast age", () => {
    const report = dataAgentReportSchema.parse({...fixture.data_agent,status:"STALE",forecast_age_minutes:null,issues:["Unknown age"]});
    expect(getAgentsSummary({...fixture,data_agent:report}).dataQuality.forecast_age_minutes).toBeNull();
  });
  it("preserves fixture run age and source", () => expect(getAgentsSummary(fixture).dataQuality).toMatchObject({status:"VALID",source:"mock_csv",forecast_age_minutes:5,used_cache:false,issues:[]}));
});

describe("recorded agent evidence", () => {
  it("finds latest actual event per agent", () => {
    const stages = getAgentPipelineSummary(fixture);
    expect(stages.map(stage => stage.agent)).toEqual(agentOrder);
    for (const stage of stages) expect(stage.latest).toEqual(getAgentEvents(fixture,stage.agent).at(-1));
  });
  it("retains multiple events from an agent", () => expect(getAgentEvents(fixture,"optimization").map(event => event.action)).toEqual(["candidate_comparison","recommendation"]));
  it("handles empty activity without invented events", () => {
    const data = {...fixture,agent_log:[]};
    expect(getAgentsSummary(data).events).toEqual([]);
    expect(getAgentPipelineSummary(data).every(stage => stage.latest === null && stage.evidence === "No recorded activity")).toBe(true);
  });
  it.each(agentOrder)("labels %s", agent => expect(formatAgentName(agent)).toBe(agent[0].toUpperCase()+agent.slice(1)+" Agent"));
  it("sorts timestamps by instant including timezone offsets", () => {
    const base = fixture.agent_log[0];
    const data = {...fixture,agent_log:[{...base,timestamp:"2026-06-21T20:00:00+02:00"},{...base,timestamp:"2026-06-21T17:59:59Z"}]};
    expect(getAgentEvents(data).map(event => event.timestamp)).toEqual(["2026-06-21T17:59:59Z","2026-06-21T20:00:00+02:00"]);
  });
  it("preserves input order for equal timestamps", () => {
    const events = fixture.agent_log.slice(0,2).map(event => ({...event,timestamp:fixture.timestamp}));
    expect(getAgentEvents({...fixture,agent_log:events})).toEqual(events);
  });
  it("does not mutate payload arrays", () => {
    const data = structuredClone(fixture); data.agent_log.reverse(); const before = structuredClone(data);
    getAgentsSummary(data); expect(data).toEqual(before);
  });
  it("preserves seven fixture events and no errors", () => {
    const summary = getAgentsSummary(fixture); expect(summary.events).toHaveLength(7); expect(summary.errors).toEqual([]);
    expect(summary.pipeline.every(stage => stage.evidence === "Recorded")).toBe(true);
  });
  it("associates real errors only with their agent", () => {
    const error = {agent:"modeling" as const,code:"MODEL_ERROR",message:"Supplied failure"};
    const summary = getAgentsSummary({...fixture,errors:[error]});
    expect(summary.errors).toEqual([error]); expect(summary.pipeline[1].evidence).toBe("Issue reported");
    expect(summary.pipeline[0].evidence).toBe("Recorded");
  });
});

describe("safety and decision fidelity", () => {
  it("uses supplied overall safety", () => expect(getAgentsSummary(fixture).safety.passed).toBe(true));
  it("preserves failed safety", () => {
    const safety = safetyResultSchema.parse({...fixture.safety,passed:false,checks:fixture.safety.checks.map((check,i) => ({...check,passed:i !== 0}))});
    expect(getAgentsSummary({...fixture,safety}).safety).toEqual(safety);
  });
  it.each([["INFO","warning"],["BLOCK_ROTATE","warning"],["SEVERE","danger"]] as const)("presents failed %s severity", (severity,tone) => expect(getSafetyCheckTone({name:"Check",passed:false,severity,reason:"Supplied reason"})).toBe(tone));
  it("does not mark a passed severe-class check as failed", () => expect(getSafetyCheckTone({name:"Wind",passed:true,severity:"SEVERE",reason:"Passed"})).toBe("success"));
  it("presents ROTATE current and target", () => expect(getDecisionAngleLabel(fixture)).toBe("35° → 45°"));
  it("presents HOLD without movement arrow", () => expect(getDecisionAngleLabel({...fixture,decision:{action:"HOLD",target_angle_deg:35,reason:"Hold"}})).toBe("Target 35°"));
  it("presents supplied STOW target", () => expect(getDecisionAngleLabel({...fixture,decision:{action:"STOW",target_angle_deg:0,reason:"Stow"}})).toBe("35° → 0°"));
  it("uses observed row when optimization is absent", () => expect(getDecisionAngleLabel({...fixture,optimization:null})).toBe("35° → 45°"));
  it("does not substitute target for unknown current", () => expect(getDecisionAngleLabel({...fixture,optimization:null,farm_status:{...fixture.farm_status,rows:[]}})).toBe("Target 45°"));
  it("keeps fixture decision reason and target unchanged", () => expect(getAgentsSummary(fixture).decision).toEqual(fixture.decision));
});
