import type { CandidatePrediction, FrontendData } from "../types/solar";
import { getCandidateInsight, getRawEnergyMaximum } from "./dashboard";
import { getControlTargetRow, getSelectedModel } from "./selectors";

export function getRawEnergyMaxCandidates(candidates: CandidatePrediction[]) {
  const maximum = getRawEnergyMaximum(candidates);
  return maximum ? candidates.filter(candidate => candidate.predicted_kwh === maximum.predicted_kwh) : [];
}

export function getCurrentCandidate(data: FrontendData) {
  const angle = data.optimization?.current_angle_deg;
  return data.candidate_predictions.find(candidate => candidate.angle_deg === angle) ?? null;
}

export function getRecommendedCandidate(data: FrontendData) {
  const angle = data.optimization?.recommended_angle_deg;
  return data.candidate_predictions.find(candidate => candidate.angle_deg === angle) ?? null;
}

export function getCandidateRoles(candidate: CandidatePrediction, current: number | null, recommended: number | null, maximumEnergy: number | null) {
  const roles: string[] = [];
  if (candidate.angle_deg === current) roles.push("Current");
  if (candidate.angle_deg === recommended) roles.push("Recommended");
  if (candidate.predicted_kwh === maximumEnergy) roles.push("Raw Max");
  return roles;
}

export function getOptimizationAgentEvents(data: FrontendData) {
  return data.agent_log.filter(event => event.agent === "optimization" || event.agent === "manager")
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
}

export function getOptimizationSummary(data: FrontendData) {
  const optimization = data.optimization;
  const rawMaxima = getRawEnergyMaxCandidates(data.candidate_predictions);
  const maximumEnergy = rawMaxima[0]?.predicted_kwh ?? null;
  return {
    optimization,
    currentAngle: optimization?.current_angle_deg ?? null,
    recommendedAngle: optimization?.recommended_angle_deg ?? null,
    currentCandidate: getCurrentCandidate(data),
    recommendedCandidate: getRecommendedCandidate(data),
    rawMaxima,
    candidates: [...data.candidate_predictions].sort((a, b) => a.angle_deg - b.angle_deg).map(candidate => ({
      ...candidate,
      roles: getCandidateRoles(candidate, optimization?.current_angle_deg ?? null, optimization?.recommended_angle_deg ?? null, maximumEnergy),
    })),
    model: getSelectedModel(data),
    target: getControlTargetRow(data),
    // Display explanation only; the backend remains the authority for economics and decisions.
    insight: getCandidateInsight(data),
    recommendationIsRawMax: optimization !== null && rawMaxima.some(candidate => candidate.angle_deg === optimization.recommended_angle_deg),
    events: getOptimizationAgentEvents(data),
    decision: data.decision,
    safety: data.safety,
    comparison: optimization ? {
      currentAngle: optimization.current_angle_deg,
      recommendedAngle: optimization.recommended_angle_deg,
      baseline: optimization.baseline_kwh,
      predicted: optimization.predicted_kwh,
      gain: optimization.energy_gain_kwh,
      movementCost: optimization.movement_cost_kwh_equivalent,
      netBenefit: optimization.net_benefit_kwh_equivalent,
    } : null,
  };
}

export type OptimizationSummary = ReturnType<typeof getOptimizationSummary>;
export type DisplayCandidate = OptimizationSummary["candidates"][number];
