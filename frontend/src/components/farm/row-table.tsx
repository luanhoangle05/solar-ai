import { ListFilter, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { rowStatePresentation } from "@/config/row-states";
import { actionPresentation } from "@/config/actions";
import { emptyRowFilters, filterFarmRows, formatZoneName, type RowFilters } from "@/lib/farm";
import { formatAngle } from "@/lib/formatters";
import type { FarmStatus } from "@/types/solar";
import { FarmPanel } from "./farm-panel";

export function RowTable({ farm, targetId, selectedRow, onRow, filters, onFilters, compact = false }: {
  compact?:boolean;
  farm:FarmStatus; targetId:string; selectedRow:string|null; onRow:(id:string)=>void;
  filters:RowFilters; onFilters:(filters:RowFilters)=>void;
}) {
  const rows = filterFarmRows(farm.rows,filters);
  function update(key:keyof RowFilters,value:string) { onFilters({...filters,[key]:value}); }
  return <FarmPanel title="Row Explorer" icon={ListFilter} className="fx-table-panel" meta={<span className="fx-note" role="status">{rows.length} of {farm.rows.length} rows shown</span>}>
    <div className="fx-filters"><label><span><Search size={12} aria-hidden="true"/>Search row ID</span><input aria-label="Search row ID" type="search" value={filters.search} onChange={event=>update("search",event.target.value)} placeholder="e.g. row-020"/></label>
      <label><span>Zone filter</span><select aria-label="Zone filter" value={filters.zone} onChange={event=>update("zone",event.target.value)}><option value="">All zones</option>{farm.zones.map(zone=><option key={zone.zone_id} value={zone.zone_id}>{formatZoneName(zone.zone_id)}</option>)}</select></label>
      <label><span>State filter</span><select aria-label="State filter" value={filters.state} onChange={event=>update("state",event.target.value)}><option value="">All states</option>{Object.keys(rowStatePresentation).map(state=><option key={state}>{state}</option>)}</select></label>
      <label><span>Action filter</span><select aria-label="Action filter" value={filters.action} onChange={event=>update("action",event.target.value)}><option value="">{compact ? "All actions" : "All recorded actions"}</option>{Object.keys(actionPresentation).map(action=><option key={action}>{action}</option>)}</select></label>
      <button type="button" className="fx-reset-filters" onClick={()=>onFilters({...emptyRowFilters})}>Clear filters</button>
    </div>
    {!compact && <p className="fx-note">Filters affect this table only; the farm views retain every row. {selectedRow && !rows.some(row=>row.row_id===selectedRow) ? `Selected ${selectedRow} is outside these filters; inspection is retained.` : "Select a row to inspect its recorded state."}</p>}
    <div className="fx-table-scroll" tabIndex={0} role="region" aria-label="Loaded farm rows"><table><caption className="sr-only">{compact ? "Farm rows" : "Observed farm rows and recorded actions; inspection does not change the control target"}</caption><thead><tr>{["Row / inspect","Zone","Panels","Angle","State",compact ? "Action" : "Recorded action","Control target"].map(label=><th scope="col" key={label}>{label}</th>)}</tr></thead>
      <tbody>{rows.map(row=><tr key={row.row_id} data-selected={row.row_id===selectedRow}><th scope="row"><button type="button" aria-pressed={row.row_id===selectedRow} aria-label={`Inspect ${row.row_id} in table`} onClick={()=>onRow(row.row_id)}>{row.row_id}<span>{row.row_id===selectedRow ? "SELECTED" : "Inspect"}</span></button></th><td>{formatZoneName(row.zone_id)}</td><td>{row.panel_count}</td><td>{formatAngle(row.angle_deg)}</td><td><Badge variant={rowStatePresentation[row.current_state].variant}>{row.current_state}</Badge></td><td>{row.action}</td><td>{row.row_id===targetId ? <span className="fx-target-tag">TARGET</span> : "—"}</td></tr>)}</tbody>
    </table>{!rows.length && <p className="fx-empty">No loaded rows match these filters.</p>}</div>
  </FarmPanel>;
}
