import type { FrontendData } from "@/types/solar";
import { getControlTargetRow } from "./selectors";
import { getAgentPipelineSummary } from "./agents";
import { formatAngle, formatKwhEquivalent, formatSignedKwh } from "./formatters";

export const analysisStepMs = 1200;
export function replayStage(elapsedMs: number, reducedMotion = false) {
  return reducedMotion ? 4 : Math.min(4, Math.max(0, Math.floor(elapsedMs / analysisStepMs)));
}
/** Operator copy describes the loaded result; this never runs an agent or changes the recommendation. */
export function getOperatorAnalysis(data: FrontendData) {
  const target = getControlTargetRow(data);
  const optimization = data.optimization;
  const evidence = getAgentPipelineSummary(data);
  const messages = [
    ["Analyzing environmental conditions…", "Reading weather and panel conditions", data.current_weather !== null],
    ["Predicting energy across panel angles…", `${data.candidate_predictions.length} available operating angles`, data.candidate_predictions.length > 0],
    ["Finding the best operating option…", "Comparing expected gain and movement cost", optimization !== null],
    ["Checking operating conditions…", "Reviewing safety constraints", true],
  ] as const;
  const stages = evidence.map((stage, index) => ({
    title: stage.errors.length ? "Analysis needs attention" : messages[index][2] ? messages[index][0] : "Analysis input unavailable",
    detail: stage.errors.length ? "Some analysis could not be completed." : !messages[index][2] ? "No result available for this step." : stage.latest ? messages[index][1] : "Reviewing available results; no agent activity supplied.",
    issue: stage.errors.length > 0 || !messages[index][2],
  }));
  const action = data.decision.action;
  const current = target?.angle_deg ?? optimization?.current_angle_deg ?? null;
  const available = optimization !== null;
  const blocked = !data.safety.passed;
  const title = blocked ? "Operating conditions need attention" : !available ? "No AI recommendation available" : action === "HOLD" ? "No adjustment recommended" : action === "STOW" ? "Stow panels" : "Recommendation Ready";
  const instruction = action === "HOLD" ? "Keep current angle" : action === "STOW" ? "Target angle" : target ? `Rotate ${target.row_id}` : "Control target unavailable";
  const angle = action === "HOLD" ? formatAngle(current) : action === "STOW" || current === null || current === data.decision.target_angle_deg ? formatAngle(data.decision.target_angle_deg) : `${formatAngle(current)} → ${formatAngle(data.decision.target_angle_deg)}`;
  const failures = data.safety.checks.filter(check => !check.passed).map(check => check.reason);
  return { stages, available, blocked, action, title, instruction, angle,
    gain: formatSignedKwh(optimization?.energy_gain_kwh ?? null),
    benefit: formatKwhEquivalent(optimization?.net_benefit_kwh_equivalent ?? null),
    positive: !blocked && action === "ROTATE" && (optimization?.net_benefit_kwh_equivalent ?? 0) > 0,
    safetyReason: failures.join(" ") || data.safety.reason,
    explanation: action === "HOLD" ? "SolarAI recommends keeping the current angle for this operating interval." : action === "STOW" ? data.decision.reason : optimization ? `${formatAngle(optimization.recommended_angle_deg)} is the operating recommendation after balancing expected energy gain with panel movement cost.` : "An AI recommendation is not available for this interval.",
  };
}
export type OperatorAnalysis = ReturnType<typeof getOperatorAnalysis>;
