import type { FarmRow, FarmStatus, FrontendData } from "../types/solar";
import { formatZoneName, getRowById, getZoneById, getZoneRows } from "./farm";
import { formatAngle, formatKwhEquivalent, formatMovementCost, formatRecordedTime, formatSignedKwh } from "./formatters";

export type FarmSimulationData = Pick<FrontendData, "farm_status" | "metadata" | "optimization" | "decision" | "safety" | "current_weather" | "candidate_predictions">;

/** Header strip: the weather snapshot and interval supplied with this run. Null when weather is unavailable. */
export function getSimulationConditions(data: FarmSimulationData) {
  const w = data.current_weather;
  return {
    weather: w ? [
      { key: "ghi", label: "GHI", value: `${w.ghi_wm2} W/m²` },
      { key: "clouds", label: "Clouds", value: `${w.cloud_cover_pct}%` },
      { key: "temperature", label: "Temperature", value: `${w.temperature_c}°C` },
      { key: "wind", label: "Wind", value: `${w.wind_speed_kmh} km/h` },
    ] as const : null,
    interval: formatRecordedTime(data.metadata.interval_start),
    horizon: `${data.metadata.prediction_horizon_minutes} min`,
  };
}

/**
 * The angle a preview may show: the manager's decided target for the control row.
 * A HOLD decision means the backend chose not to move, so there is nothing to preview,
 * even when the optimizer recommended another angle.
 */
export function getCandidateAngleRange(data: Pick<FarmSimulationData, "candidate_predictions">): { minDeg: number; maxDeg: number } | null {
  // The span of candidate angles the backend evaluated, for the illustrative tracking demo. Null when none were supplied.
  const angles = data.candidate_predictions.map(candidate => candidate.angle_deg);
  return angles.length ? { minDeg: Math.min(...angles), maxDeg: Math.max(...angles) } : null;
}
export function getPreviewAngle(data: FarmSimulationData): number | null {
  if (!getRowById(data.farm_status, data.metadata.control_target_id) || data.decision.action === "HOLD") return null;
  if (data.decision.action !== "STOW" && (!data.safety.passed || !data.optimization)) return null;
  return data.decision.target_angle_deg;
}

/**
 * Whether the control row's decision is shown for this row: it is the control target, or the payload gives it
 * the same action, state and recorded angle. The backend marks such rows when its decision applies to them equally.
 */
export function sharesControlDecision(data: FarmSimulationData, row: FarmRow): boolean {
  const target = getRowById(data.farm_status, data.metadata.control_target_id);
  if (!target) return false;
  return row.row_id === target.row_id || (row.action === data.decision.action && row.current_state === target.current_state && row.angle_deg === target.angle_deg);
}

/**
 * Among several runs over the same farm (the main run plus one per zone), the run whose decision is shown for a row.
 * Falls back to the first run, whose view then reports that no recommendation applies.
 */
export function getRunForRow(runs: FarmSimulationData[], rowId: string | null): FarmSimulationData {
  return runs.find(run => { const row = getRowById(run.farm_status, rowId); return row ? sharesControlDecision(run, row) : false; }) ?? runs[0];
}

/** The first run's farm with every run's previewed rows drawn at that run's decided target angle. Display only. */
export function getRunsPreviewFarm(runs: FarmSimulationData[]): FarmStatus {
  const angles = new Map<string, number>();
  for (const run of runs) { const angle = getPreviewAngle(run); if (angle !== null) for (const id of getPreviewRowIds(run)) angles.set(id, angle); }
  const farm = runs[0].farm_status;
  return angles.size === 0 ? farm : { ...farm, rows: farm.rows.map(row => angles.has(row.row_id) ? { ...row, angle_deg: angles.get(row.row_id)! } : row) };
}

/** How many distinct rows the runs' previews move. */
export function getRunsPreviewRowCount(runs: FarmSimulationData[]): number {
  return new Set(runs.flatMap(getPreviewRowIds)).size;
}

/** The rows a preview moves: every row the control row's decision is shown for. Empty when there is nothing to preview. */
export function getPreviewRowIds(data: FarmSimulationData): string[] {
  if (getPreviewAngle(data) === null) return [];
  return data.farm_status.rows.filter(row => sharesControlDecision(data, row)).map(row => row.row_id);
}

/**
 * A copy of the farm with the previewed rows drawn at the decided target angle.
 * Display only: the validated payload is never changed and no command is sent anywhere.
 */
export function getPreviewFarm(data: FarmSimulationData): FarmStatus {
  const angle = getPreviewAngle(data), moved = new Set(getPreviewRowIds(data));
  if (angle === null || moved.size === 0) return data.farm_status;
  return { ...data.farm_status, rows: data.farm_status.rows.map(row => moved.has(row.row_id) ? { ...row, angle_deg: angle } : row) };
}

/**
 * Details for the inspected row. The recommendation is the control target's; it is also shown for rows that share
 * its action, state and angle, with a line saying it was not computed separately. Other rows show their recorded state.
 */
export function getRowSimulationView(data: FarmSimulationData, rowId: string | null) {
  const row = getRowById(data.farm_status, rowId);
  if (!row) return null;
  const zone = getZoneById(data.farm_status, row.zone_id);
  const zoneRows = zone ? getZoneRows(data.farm_status, zone) : [];
  const position = zoneRows.findIndex(item => item.row_id === row.row_id);
  const isTarget = row.row_id === data.metadata.control_target_id;
  const appliesDecision = sharesControlDecision(data, row);
  const optimization = appliesDecision ? data.optimization : null;
  return {
    row, isTarget, appliesDecision,
    zoneName: formatZoneName(row.zone_id),
    position: position >= 0 ? `Row ${position + 1} of ${zoneRows.length}` : "Zone membership unavailable",
    currentAngle: row.angle_deg,
    recommendedAngle: optimization?.recommended_angle_deg ?? null,
    gain: optimization ? formatSignedKwh(optimization.energy_gain_kwh) : null,
    horizon: `${data.metadata.prediction_horizon_minutes} min`,
    // Each line restates a supplied payload value; none is derived by the frontend.
    reasoning: !appliesDecision ? [] : [
      ...(isTarget ? [] : [`Same state and angle as control row ${data.metadata.control_target_id}, so its decision is shown here; it was not computed separately for this row.`]),
      ...(optimization ? [
        `${formatAngle(optimization.recommended_angle_deg)} gives the best net benefit (${formatKwhEquivalent(optimization.net_benefit_kwh_equivalent)}).`,
        `Energy gain ${formatSignedKwh(optimization.energy_gain_kwh)} against movement cost ${formatMovementCost(optimization.movement_cost_kwh_equivalent)}`,
      ] : ["No optimization result was supplied for this run."]),
      `Safety ${data.safety.passed ? "passed" : "blocked"}: ${data.safety.reason}`,
      `Decision ${data.decision.action} → ${formatAngle(data.decision.target_angle_deg)}: ${data.decision.reason}`,
    ],
  };
}
export type RowSimulationView = NonNullable<ReturnType<typeof getRowSimulationView>>;
