import type { CSSProperties } from "react";
import { Crosshair, MapPin, ScanLine } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { actionPresentation } from "@/config/actions";
import { rowStatePresentation } from "@/config/row-states";
import { getZoneColor } from "@/config/zones";
import { formatZoneName, getRowCounts, getRowTargetContext, getZoneRows, type FarmExplorerData } from "@/lib/farm";
import { formatAngle, formatKwhEquivalent } from "@/lib/formatters";
import type { FarmRow, FarmZone } from "@/types/solar";
import { FarmPanel } from "./farm-panel";

export function RowDetails({ data, row, onRow }: { data: FarmExplorerData; row: FarmRow | null; onRow: (id:string) => void }) {
  const context = getRowTargetContext(data,row);
  const ActionIcon = row ? actionPresentation[row.action].icon : Crosshair;
  return <FarmPanel title="Row Inspection" icon={ScanLine} className="fx-row-details" meta={<Badge variant="outline">READ-ONLY</Badge>}>
    <label className="fx-row-picker">Inspect loaded row<select aria-label="Inspect loaded row" value={row?.row_id ?? ""} onChange={event => onRow(event.target.value)}><option value="" disabled>Select row</option>{data.farm_status.rows.map(item => <option key={item.row_id} value={item.row_id}>{item.row_id} · {formatZoneName(item.zone_id)}</option>)}</select></label>
    {row ? <><div className="fx-row-title"><h3>{row.row_id}</h3><Badge variant={rowStatePresentation[row.current_state].variant}>{row.current_state}</Badge>{context && <span className="fx-target-tag"><Crosshair size={12} aria-hidden="true"/>TARGET</span>}</div>
      <div className="fx-row-preview"><svg viewBox="0 0 170 64" role="img" aria-label={`Current row tilt ${formatAngle(row.angle_deg)} from horizontal`}><line x1="25" y1="52" x2="145" y2="52" stroke="#496176"/><line x1="82" y1="52" x2="82" y2="25" stroke="#788a98" strokeWidth="3"/><g transform={`translate(82 25) rotate(${-row.angle_deg})`}><rect x="-53" y="-5" width="106" height="10" rx="1" fill="#145697" stroke="#84cced"/><path d="M-35 -5v10 M-17 -5v10 M0 -5v10 M17 -5v10 M35 -5v10" stroke="#719cc7"/></g></svg><div><span>Current angle</span><strong>{formatAngle(row.angle_deg)}</strong><small>{row.panel_count} panels · illustrative strip</small></div></div>
      <dl className="fx-facts"><div><dt>Zone</dt><dd>{formatZoneName(row.zone_id)}</dd></div><div><dt>Recorded action</dt><dd><ActionIcon size={13} aria-hidden="true"/>{row.action}</dd></div><div><dt>Control target</dt><dd>{context ? "Yes" : "No"}</dd></div></dl>
      {context ? <div className="fx-target-context"><p><Crosshair size={13} aria-hidden="true"/>Control-target recommendation</p><dl className="fx-facts"><div><dt>Recommended angle</dt><dd>{formatAngle(context.optimization?.recommended_angle_deg ?? null)}</dd></div><div><dt>Manager decision</dt><dd style={{color:actionPresentation[context.decision.action].color}}>{context.decision.action} · {formatAngle(context.decision.target_angle_deg)}</dd></div><div><dt>Net benefit</dt><dd>{formatKwhEquivalent(context.optimization?.net_benefit_kwh_equivalent ?? null)}</dd></div><div><dt>Safety</dt><dd><Badge variant={context.safety.passed ? "success" : "danger"}>{context.safety.passed ? "PASSED" : "BLOCKED"}</Badge></dd></div></dl><details className="fx-decision-reason"><summary>Recorded decision rationale</summary><p className="fx-note">{context.decision.reason}</p></details></div> : <p className="fx-non-target">This row is not the current optimization control target. No row-specific recommendation is supplied.</p>}
      <p className="fx-note">Observed state and recorded action are distinct. Hardware execution is not confirmed.</p>
    </> : <p className="fx-empty">No row available for inspection.</p>}
  </FarmPanel>;
}

export function ZoneDetails({ data, zone }: { data: FarmExplorerData; zone: FarmZone | null }) {
  if (!zone) return <FarmPanel title="Zone Details" icon={MapPin} className="fx-zone-details"><p className="fx-empty">No zone selected.</p></FarmPanel>;
  const counts = getRowCounts(getZoneRows(data.farm_status,zone));
  return <FarmPanel title="Zone Details" icon={MapPin} className="fx-zone-details" meta={<strong style={{color:getZoneColor(zone.zone_id)}}>{formatZoneName(zone.zone_id)}</strong>}>
    <div className="fx-zone-numbers"><span><strong>{zone.panel_count}</strong> panels</span><span><strong>{zone.row_ids.length}</strong> rows</span></div>
    <p className="fx-note">Contains control target: <strong>{zone.row_ids.includes(data.metadata.control_target_id) ? "Yes" : "No"}</strong></p>
    <div className="fx-zone-counts"><p><span>States</span>{Object.entries(counts.states).map(([state,count]) => <small key={state}>{count} {state}</small>)}</p><p><span>Recorded actions</span>{Object.entries(counts.actions).map(([action,count]) => <small key={action}>{count} {action}</small>)}</p></div>
    <details className="fx-members"><summary>Exact row membership ({zone.row_ids.length})</summary><ul>{zone.row_ids.map(id => <li key={id}>{id}</li>)}</ul></details>
  </FarmPanel>;
}

export function ZoneNavigator({ data, selectedZone, onZone }: { data: FarmExplorerData; selectedZone:string|null; onZone:(id:string)=>void }) {
  return <nav className="fx-zone-nav" aria-label="Zone inspection">{data.farm_status.zones.map(zone => <button type="button" key={zone.zone_id} aria-pressed={selectedZone === zone.zone_id} onClick={() => onZone(zone.zone_id)} style={{"--zone-color":getZoneColor(zone.zone_id)} as CSSProperties}><MapPin size={17} aria-hidden="true"/><span><strong>{formatZoneName(zone.zone_id)}</strong><small>{zone.panel_count} panels · {zone.row_ids.length} rows</small></span>{zone.row_ids.includes(data.metadata.control_target_id) && <Crosshair size={15} aria-label="Contains control target"/>}</button>)}</nav>;
}
