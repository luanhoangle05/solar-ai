import type { AgentName, FrontendData } from "../types/solar";
import { agentOrder, getAgentEvents } from "./agents";
import { formatAngle, formatKwhEquivalent, formatModelName, formatMovementCost, formatSignedKwh } from "./formatters";
import { getControlTargetRow } from "./selectors";

export type AgentCardStatus = "COMPLETED" | "ISSUE" | "UNAVAILABLE";
export type CommandCenterAgent = {
  agent: AgentName; title: string; role: string; status: AgentCardStatus;
  /** Shown while the recorded run is replayed; never a claim about a live process. */
  replayLabel: string;
  headline: string; lines: string[]; milestone: string;
  /** The agent's LLM-written explanation recorded in the run log, when the run produced one. */
  reasoning: string | null;
};
const LLM_REASONING_ACTION = "llm_reasoning";
/** Data the Data Agent reported as usable; anything else is shown as unavailable. */
const usableDataStatuses = ["VALID", "DEGRADED"];

const titles: Record<AgentName, string> = { data: "Data Agent", modeling: "Modeling Agent", optimization: "Optimization Agent", manager: "Manager Agent" };
const roles: Record<AgentName, string> = {
  data: "Collects and validates environmental and system data.",
  modeling: "Predicts energy output across candidate tilt angles.",
  optimization: "Finds the panel angle with the best net benefit.",
  manager: "Validates safety, constraints and the final decision.",
};
const replayLabels: Record<AgentName, string> = { data: "COLLECTING…", modeling: "PREDICTING…", optimization: "ADJUSTING ANGLE…", manager: "VALIDATING…" };
const milestones: Record<AgentName, string> = { data: "Data collected", modeling: "Modeling complete", optimization: "Angle optimized", manager: "Decision recorded" };
const unavailableMilestones: Record<AgentName, string> = { data: "Data unavailable", modeling: "Prediction unavailable", optimization: "Optimization unavailable", manager: "Decision unavailable" };
const noActivity = "No recorded agent activity for this stage.";

/** Every value below is read from the payload; nothing is recalculated or inferred beyond formatting. */
export function getCommandCenterView(data: FrontendData) {
  const weather = data.current_weather, optimization = data.optimization;
  const currentAngle = optimization?.current_angle_deg ?? getControlTargetRow(data)?.angle_deg ?? null;
  const horizon = data.metadata.prediction_horizon_minutes;
  const available: Record<AgentName, boolean> = {
    data: usableDataStatuses.includes(data.data_agent.status) && weather !== null,
    modeling: data.selected_model !== null && data.candidate_predictions.length > 0,
    optimization: optimization !== null,
    manager: true,
  };
  const lines: Record<AgentName, string[]> = {
    data: weather
      ? [`Inputs: ${weather.temperature_c}°C | ${weather.ghi_wm2} W/m² | ${weather.wind_speed_kmh} km/h | Clouds ${weather.cloud_cover_pct}%`, `Data quality: ${data.data_agent.status}`]
      : ["Input unavailable", `Data quality: ${data.data_agent.status}`],
    modeling: [`Model: ${formatModelName(data.selected_model)}`, `Prediction horizon: ${horizon} min · ${data.candidate_predictions.length} candidate angles`],
    optimization: optimization
      ? [`Evaluated ${formatAngle(optimization.current_angle_deg)} → ${formatAngle(optimization.recommended_angle_deg)}`,
        `Gain ${formatSignedKwh(optimization.energy_gain_kwh)} vs. movement cost ${formatMovementCost(optimization.movement_cost_kwh_equivalent)}`,
        `Net benefit ${formatKwhEquivalent(optimization.net_benefit_kwh_equivalent)}`]
      : ["Result unavailable"],
    manager: [`Safety ${data.safety.passed ? "PASS" : "FAIL"}`, `Decision: ${data.decision.action} → ${formatAngle(data.decision.target_angle_deg)}`],
  };
  const agents: CommandCenterAgent[] = agentOrder.map(agent => {
    const hasError = data.errors.some(error => error.agent === agent);
    const events = getAgentEvents(data, agent);
    // The headline is the agent's last recorded step; the LLM's wording of the run is shown separately.
    const latest = events.filter(event => !event.action.startsWith(LLM_REASONING_ACTION)).at(-1);
    const reasoning = events.filter(event => event.action === LLM_REASONING_ACTION).at(-1)?.result ?? null;
    const status: AgentCardStatus = hasError ? "ISSUE" : available[agent] ? "COMPLETED" : "UNAVAILABLE";
    return {
      agent, title: titles[agent], role: roles[agent], replayLabel: replayLabels[agent], status,
      // The track label follows the recorded status, so it never claims a stage the payload does not support.
      milestone: status === "COMPLETED" ? milestones[agent] : status === "ISSUE" ? "Issue reported" : unavailableMilestones[agent],
      headline: agent === "manager" ? data.decision.reason : latest?.result ?? noActivity,
      lines: lines[agent], reasoning,
    };
  });
  return {
    agents, hasReasoning: agents.some(agent => agent.reasoning !== null),
    cycle: currentAngle === null ? `Target ${formatAngle(data.decision.target_angle_deg)}` : `${formatAngle(currentAngle)} → ${formatAngle(data.decision.target_angle_deg)}`,
    action: data.decision.action,
    gain: optimization ? `${formatSignedKwh(optimization.energy_gain_kwh)} / ${horizon} min` : "Unavailable",
    // The contract carries a proposed action only; there is no field confirming that a panel moved.
    execution: { status: "Not confirmed", note: "Recommendation only. The payload records a proposed action and has no field confirming a controller command." },
    isMock: data.metadata.dataset_kind === "MOCK",
  };
}
export type CommandCenterView = ReturnType<typeof getCommandCenterView>;
