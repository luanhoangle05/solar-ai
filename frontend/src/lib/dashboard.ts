import type { CandidatePrediction, FrontendData } from "../types/solar";
import { getControlTargetRow, getFrontendSummary, getSelectedModel } from "./selectors";
import { formatAngle } from "./formatters";

export function getControlTargetZone(data: FrontendData) {
  const row = getControlTargetRow(data);
  return data.farm_status.zones.find(zone => zone.zone_id === row?.zone_id) ?? null;
}

export function getRawEnergyMaximum(candidates: CandidatePrediction[]) {
  // Display-only comparison. Never selects a net-benefit optimum.
  return candidates.reduce<CandidatePrediction | null>((best, candidate) =>
    !best || candidate.predicted_kwh > best.predicted_kwh ? candidate : best, null);
}

export function getZoneSummaries(data: FrontendData) {
  const target = getControlTargetZone(data);
  return data.farm_status.zones.map(zone => ({
    id: zone.zone_id,
    panelCount: zone.panel_count,
    rowCount: zone.row_ids.length,
    isTarget: zone.zone_id === target?.zone_id,
  }));
}

export function getLatestAgentEvents(data: FrontendData, limit = 7) {
  // Keep the latest events, then show them in chronological narrative order.
  return [...data.agent_log]
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp))
    .slice(-Math.max(1, limit));
}

export function getCandidateInsight(data: FrontendData) {
  const maximum = getRawEnergyMaximum(data.candidate_predictions);
  const recommended = data.optimization?.recommended_angle_deg;
  if (!maximum) return "No candidate predictions available for this run.";
  if (recommended === undefined) return "Raw energy predictions are available; optimization is unavailable.";
  const ties = data.candidate_predictions.filter(candidate => candidate.predicted_kwh === maximum.predicted_kwh);
  if (ties.some(candidate => candidate.angle_deg === recommended)) {
    return "The backend recommendation also reaches the highest raw predicted energy among these candidates.";
  }
  return formatAngle(maximum.angle_deg) + (ties.length > 1 ? " shares" : " has") +
    " the highest raw predicted energy. The backend recommends " + formatAngle(recommended) +
    " using net-benefit logic; per-candidate movement costs are not shown.";
}

export function getDashboardSummary(data: FrontendData) {
  const targetRow = getControlTargetRow(data);
  return {
    ...getFrontendSummary(data),
    // Observed row state is separate from the proposed decision target.
    currentAngleDeg: targetRow?.angle_deg ?? data.optimization?.current_angle_deg ?? null,
    targetRow,
    targetZone: getControlTargetZone(data),
    selectedModel: getSelectedModel(data),
    weather: data.current_weather,
    optimization: data.optimization,
    zones: getZoneSummaries(data),
    candidates: [...data.candidate_predictions].sort((a, b) => a.angle_deg - b.angle_deg),
    rawMaximum: getRawEnergyMaximum(data.candidate_predictions),
    events: getLatestAgentEvents(data),
    rowStates: data.farm_status.rows.reduce<Record<string, number>>((counts, row) => {
      counts[row.current_state] = (counts[row.current_state] ?? 0) + 1;
      return counts;
    }, {}),
  };
}
export type DashboardSummary = ReturnType<typeof getDashboardSummary>;
