import type { FrontendData } from "../types/solar";
import { getAgentsSummary } from "./agents";
import { getOptimizationSummary } from "./optimization";
import { formatAngle, formatModelName } from "./formatters";
import { getControlTargetRow } from "./selectors";
import { getWeatherView } from "./weather";

export function getScenarioView(data: FrontendData) {
  const agents = getAgentsSummary(data);
  return {
    optimization: getOptimizationSummary(data),
    agents: {...agents, events: agents.events.filter(event => event.agent !== "data")},
    input: { target: data.metadata.control_target_id, horizon: data.metadata.prediction_horizon_minutes,
      scope: data.metadata.energy_scope, model: formatModelName(data.selected_model),
      candidateCount: data.candidate_predictions.length,
      currentAngle: getControlTargetRow(data)?.angle_deg ?? data.optimization?.current_angle_deg ?? null,
      weather: getWeatherView(data).conditions },
    // Static inspection stages describe evidence, never elapsed progress or execution.
    stages: [
      { title:"Environmental Input", evidence:data.current_weather ? "8 supplied measurements" : "Input unavailable", available:data.current_weather !== null },
      { title:"Data Validation", evidence:data.data_agent.status, available:data.data_agent.status === "VALID" },
      { title:"Model Prediction", evidence:formatModelName(data.selected_model), available:data.selected_model !== null },
      { title:"Candidate Comparison", evidence:`${data.candidate_predictions.length} supplied candidates`, available:data.candidate_predictions.length > 0 },
      { title:"Optimization", evidence:data.optimization ? `Recommended ${formatAngle(data.optimization.recommended_angle_deg)}` : "Result unavailable", available:data.optimization !== null },
      { title:"Safety", evidence:data.safety.passed ? "PASS" : "FAIL", available:data.safety.passed },
      { title:"Manager Decision", evidence:`${data.decision.action} → ${formatAngle(data.decision.target_angle_deg)}`, available:true },
    ],
  };
}
