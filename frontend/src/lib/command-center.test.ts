import { beforeAll, describe, expect, it } from "vitest";
import { loadFrontendData } from "./frontend-data.server";
import { getCommandCenterView } from "./command-center";
import type { FrontendData } from "../types/solar";
let data: FrontendData;
beforeAll(async () => { data = await loadFrontendData(); });
const agent = (view: ReturnType<typeof getCommandCenterView>, name: string) => view.agents.find(card => card.agent === name)!;
describe("agent command center view", () => {
  it("lists the four agents in pipeline order", () => expect(getCommandCenterView(data).agents.map(card => card.agent)).toEqual(["data", "modeling", "optimization", "manager"]));
  it("marks every recorded stage completed", () => expect(getCommandCenterView(data).agents.every(card => card.status === "COMPLETED")).toBe(true));
  it("shows supplied weather inputs", () => expect(agent(getCommandCenterView(data), "data").lines[0]).toBe("Inputs: 22°C | 850 W/m² | 14 km/h | Clouds 15%"));
  it("names the selected model and horizon", () => expect(agent(getCommandCenterView(data), "modeling").lines).toEqual(["Model: Boosting", "Prediction horizon: 60 min · 7 candidate angles"]));
  it("reports the supplied optimization figures", () => expect(agent(getCommandCenterView(data), "optimization").lines).toEqual(["Evaluated 35° → 45°", "Gain +0.29 kWh vs. movement cost 0.03 kWh eq.", "Net benefit +0.26 kWh eq."]));
  it("reports safety and decision for the manager", () => expect(agent(getCommandCenterView(data), "manager").lines).toEqual(["Safety PASS", "Decision: ROTATE → 45°"]));
  it("uses the latest recorded event as the headline", () => expect(agent(getCommandCenterView(data), "optimization").headline).toBe(data.agent_log.filter(event => event.agent === "optimization").at(-1)!.result));
  it("uses the decision reason for the manager headline", () => expect(agent(getCommandCenterView(data), "manager").headline).toBe(data.decision.reason));
  it("summarises the cycle and gain", () => expect(getCommandCenterView(data)).toMatchObject({ cycle: "35° → 45°", gain: "+0.29 kWh / 60 min", action: "ROTATE" }));
  it("has no LLM reasoning when the run log holds none", () => {
    const view = getCommandCenterView(data);
    expect(view.hasReasoning).toBe(false);
    expect(view.agents.map(card => card.reasoning)).toEqual([null, null, null, null]);
  });
  it("shows an agent's recorded LLM reasoning and keeps its last tool step as the headline", () => {
    const last = data.agent_log.filter(event => event.agent === "optimization").at(-1)!;
    const explained = { ...data, agent_log: [...data.agent_log, { timestamp: "2026-06-21T19:30:00Z", agent: "optimization" as const, action: "llm_reasoning", result: "Moving is worth it." }] };
    const view = getCommandCenterView(explained);
    expect(view.hasReasoning).toBe(true);
    expect(agent(view, "optimization")).toMatchObject({ reasoning: "Moving is worth it.", headline: last.result });
    expect(agent(view, "modeling").reasoning).toBeNull();
  });
  it("does not present an unavailable LLM explanation as reasoning", () => {
    const view = getCommandCenterView({ ...data, agent_log: [...data.agent_log, { timestamp: "2026-06-21T19:30:00Z", agent: "manager" as const, action: "llm_reasoning_unavailable", result: "No LLM explanation for this stage." }] });
    expect(agent(view, "manager").reasoning).toBeNull();
  });
  it("counts degraded but usable data as collected and still shows its quality", () => {
    const view = getCommandCenterView({ ...data, data_agent: { ...data.data_agent, status: "DEGRADED", issues: ["replayed hour"] } });
    expect(agent(view, "data")).toMatchObject({ status: "COMPLETED" });
    expect(agent(view, "data").lines[1]).toBe("Data quality: DEGRADED");
  });
  it("shows invalid data as unavailable", () => expect(agent(getCommandCenterView({ ...data, data_agent: { ...data.data_agent, status: "INVALID", forecast_age_minutes: null, issues: ["unknown issue time"] } }), "data").status).toBe("UNAVAILABLE"));
  it("never claims the panel moved", () => expect(getCommandCenterView(data).execution.status).toBe("Not confirmed"));
  it("labels recorded milestones", () => expect(getCommandCenterView(data).agents.map(card => card.milestone)).toEqual(["Data collected", "Modeling complete", "Angle optimized", "Decision recorded"]));
  it("marks missing optimization unavailable without inventing a gain", () => {
    const view = getCommandCenterView({ ...data, optimization: null });
    expect(agent(view, "optimization")).toMatchObject({ status: "UNAVAILABLE", lines: ["Result unavailable"], milestone: "Optimization unavailable" });
    expect(view.gain).toBe("Unavailable");
  });
  it("marks missing input and model unavailable", () => {
    const view = getCommandCenterView({ ...data, current_weather: null, selected_model: null, candidate_predictions: [] });
    expect(agent(view, "data")).toMatchObject({ status: "UNAVAILABLE" });
    expect(agent(view, "data").lines[0]).toBe("Input unavailable");
    expect(agent(view, "modeling")).toMatchObject({ status: "UNAVAILABLE", lines: ["Model: Unavailable", "Prediction horizon: 60 min · 0 candidate angles"] });
  });
  it("flags an agent with a recorded error", () => {
    const view = getCommandCenterView({ ...data, errors: [{ agent: "modeling", code: "TOOL_ERROR", message: "failed" }] } as FrontendData);
    expect(agent(view, "modeling")).toMatchObject({ status: "ISSUE", milestone: "Issue reported" });
  });
  it("says so when an agent has no recorded activity", () => expect(agent(getCommandCenterView({ ...data, agent_log: [] }), "data").headline).toBe("No recorded agent activity for this stage."));
  it("preserves a STOW decision", () => expect(getCommandCenterView({ ...data, decision: { action: "STOW", target_angle_deg: 0, reason: "Severe wind" } })).toMatchObject({ action: "STOW", cycle: "35° → 0°" }));
});
