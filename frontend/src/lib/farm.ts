import type { FarmRow, FarmStatus, FarmZone, FrontendData } from "../types/solar";
import { getControlTargetRow } from "./selectors";
import { getControlTargetZone, getZoneSummaries } from "./dashboard";

export type FarmExplorerData = Pick<FrontendData, "farm_status" | "metadata" | "optimization" | "decision" | "safety">;
export type RowFilters = { search: string; zone: string; state: string; action: string };
export const emptyRowFilters: RowFilters = { search: "", zone: "", state: "", action: "" };

export function formatZoneName(id: string) {
  const match = /^zone-(\d+)$/.exec(id);
  return match ? `Zone ${Number(match[1])}` : id;
}
export function getRowById(farm: FarmStatus, id: string | null) {
  return farm.rows.find(row => row.row_id === id) ?? null;
}
export function getZoneById(farm: FarmStatus, id: string | null) {
  return farm.zones.find(zone => zone.zone_id === id) ?? null;
}
export function getZoneRows(farm: FarmStatus, zone: FarmZone) {
  // Membership comes from the supplied zone list; preserve its order.
  const rows = new Map(farm.rows.map(row => [row.row_id, row]));
  return zone.row_ids.flatMap(id => { const row = rows.get(id); return row ? [row] : []; });
}
export function getRowCounts(rows: FarmRow[]) {
  const states = { READY: 0, MOVING: 0, STOWED: 0, FAULT: 0 };
  const actions = { ROTATE: 0, HOLD: 0, STOW: 0 };
  for (const row of rows) { states[row.current_state]++; actions[row.action]++; }
  return { states, actions };
}
export function getPanelsPerRow(rows: FarmRow[]) {
  const counts = [...new Set(rows.map(row => row.panel_count))];
  return counts.length === 0 ? "Unavailable" : counts.length === 1 ? String(counts[0]) : `${Math.min(...counts)}–${Math.max(...counts)} (varies)`;
}
export function getFarmSummary(data: FrontendData) {
  return { totalPanels: data.farm_status.total_panels, totalRows: data.farm_status.rows.length,
    zoneCount: data.farm_status.zones.length, panelsPerRow: getPanelsPerRow(data.farm_status.rows),
    targetRow: getControlTargetRow(data), targetZone: getControlTargetZone(data),
    zones: getZoneSummaries(data), ...getRowCounts(data.farm_status.rows) };
}
export type FarmSummary = ReturnType<typeof getFarmSummary>;

export function getInitialSelection(farm: FarmStatus, targetRow: FarmRow | null): {rowId:string|null; zoneId:string|null} {
  const row = targetRow ?? farm.rows[0] ?? null;
  return { rowId: row?.row_id ?? null, zoneId: row?.zone_id ?? farm.zones[0]?.zone_id ?? null };
}
export function getZoneSelection(farm: FarmStatus, zoneId: string, selectedRowId: string | null): {rowId:string|null; zoneId:string|null} {
  const zone = getZoneById(farm, zoneId);
  if (!zone) return { zoneId:null, rowId:null };
  const rows = getZoneRows(farm, zone);
  return { zoneId, rowId: rows.find(row => row.row_id === selectedRowId)?.row_id ?? rows[0]?.row_id ?? null };
}
export function getRowTargetContext(data: FarmExplorerData, row: FarmRow | null) {
  if (!row || row.row_id !== data.metadata.control_target_id) return null;
  return { optimization: data.optimization, decision: data.decision, safety: data.safety };
}
export function filterFarmRows(rows: FarmRow[], filters: RowFilters) {
  const search = filters.search.trim().toLowerCase();
  return rows.filter(row => row.row_id.toLowerCase().includes(search)
    && (!filters.zone || row.zone_id === filters.zone)
    && (!filters.state || row.current_state === filters.state)
    && (!filters.action || row.action === filters.action));
}
