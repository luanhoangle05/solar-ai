import type { AgentName, FrontendData, ModelMetrics, SafetyCheck } from "../types/solar";
import { formatAngle, formatDisplayName, formatMetric } from "./formatters";
import { getControlTargetRow, getSelectedModel } from "./selectors";

export const agentOrder = ["data", "modeling", "optimization", "manager"] as const;
export const agentRoles: Record<AgentName, string> = {
  data: "Validates and prepares environmental input.",
  modeling: "Evaluates prediction-model outputs.",
  optimization: "Compares candidate panel-angle outcomes.",
  manager: "Applies safety results and produces the final decision.",
};
export function formatAgentName(agent: AgentName) { return `${formatDisplayName(agent)} Agent`; }
export function getAgentEvents(data: FrontendData, agent?: AgentName) {
  return data.agent_log.filter(event => !agent || event.agent === agent)
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
}
export function getAgentPipelineSummary(data: FrontendData) {
  return agentOrder.map(agent => {
    const events = getAgentEvents(data, agent);
    const errors = data.errors.filter(error => error.agent === agent);
    return { agent, events, errors, latest: events.at(-1) ?? null,
      evidence: errors.length ? "Issue reported" : events.length ? "Recorded" : "No recorded activity" };
  });
}
export function getModelDisplay(model: ModelMetrics, selected: FrontendData["selected_model"]) {
  return { ...model, selected: model.model === selected,
    metrics: [model.mae, model.rmse, model.r2].map(value => value === null ? "—" : formatMetric(value)),
    variant: model.status === "MOCK" ? "warning" as const : model.status === "VALIDATED" ? "success" as const : "secondary" as const,
    provenance: model.status === "MOCK" ? "Synthetic fixture metrics" : model.status === "UNAVAILABLE" ? "Metrics unavailable" : "Validated status supplied by payload" };
}
export function getSafetyCheckTone(check: SafetyCheck) {
  return check.passed ? "success" : check.severity === "SEVERE" ? "danger" : "warning";
}
export function getDecisionAngleLabel(data: FrontendData) {
  const current = data.optimization?.current_angle_deg ?? getControlTargetRow(data)?.angle_deg ?? null;
  const target = data.decision.target_angle_deg;
  return data.decision.action === "HOLD" || current === target || current === null
    ? `Target ${formatAngle(target)}` : `${formatAngle(current)} → ${formatAngle(target)}`;
}
export function getAgentsSummary(data: FrontendData) {
  return { pipeline: getAgentPipelineSummary(data), events: getAgentEvents(data),
    models: data.model_comparison.map(model => getModelDisplay(model, data.selected_model)),
    selectedModel: getSelectedModel(data), decisionAngle: getDecisionAngleLabel(data),
    dataQuality: data.data_agent, safety: data.safety, decision: data.decision, errors: data.errors };
}
export type AgentsSummary = ReturnType<typeof getAgentsSummary>;
