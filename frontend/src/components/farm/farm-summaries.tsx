import { Activity, BarChart3, Crosshair, Layers } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { rowStatePresentation } from "@/config/row-states";
import { actionPresentation } from "@/config/actions";
import { getZoneColor } from "@/config/zones";
import { formatZoneName, type FarmExplorerData, type FarmSummary } from "@/lib/farm";
import { formatAngle } from "@/lib/formatters";
import { FarmPanel } from "./farm-panel";

export function FarmSummaryPanel({ data, summary }: { data:FarmExplorerData; summary:FarmSummary }) {
  return <FarmPanel title="Farm Summary" icon={Layers} className="fx-farm-summary" meta={<Badge variant="outline">SNAPSHOT</Badge>}>
    <dl className="fx-summary-numbers"><div><dt>Panels</dt><dd>{summary.totalPanels.toLocaleString("en-US")}</dd></div><div><dt>Rows</dt><dd>{summary.totalRows}</dd></div><div><dt>Zones</dt><dd>{summary.zoneCount}</dd></div><div><dt>Panels / row</dt><dd>{summary.panelsPerRow}</dd></div></dl>
    <div className="fx-fixed-target"><Crosshair size={20} aria-hidden="true"/><div><span>CONTROL TARGET · FIXED</span><strong>{data.metadata.control_target_id}</strong><small>{summary.targetZone ? formatZoneName(summary.targetZone.zone_id) : "Zone unavailable"} · Current {formatAngle(summary.targetRow?.angle_deg ?? null)}</small></div><Badge variant={data.safety.passed ? "success" : "danger"}>{data.safety.passed ? "PASSED" : "BLOCKED"}</Badge></div>
    <p className="fx-note">Manager decision: <strong>{data.decision.action} · {formatAngle(data.decision.target_angle_deg)}</strong> · Proposed, not execution-confirmed.</p>
  </FarmPanel>;
}
export function FarmDistributions({ summary }: { summary:FarmSummary }) {
  const maximum = Math.max(1,...summary.zones.map(zone=>zone.panelCount));
  return <><FarmPanel title="Recorded Row States" icon={Activity} className="fx-state-summary" meta={<span className="fx-note">{summary.totalRows} total rows</span>}>
    <div className="fx-state-counts">{(Object.keys(rowStatePresentation) as (keyof typeof rowStatePresentation)[]).map(state => { const presentation = rowStatePresentation[state]; const Icon = presentation.icon;
      return <div key={state}><Icon size={17} style={{color:presentation.color}} aria-hidden="true"/><strong>{summary.states[state]}</strong><span>{state}</span></div>;
    })}</div><div className="fx-segmented" aria-hidden="true">{(Object.keys(rowStatePresentation) as (keyof typeof rowStatePresentation)[]).map(state => <span key={state} style={{width:`${summary.totalRows ? summary.states[state]/summary.totalRows*100 : 0}%`,background:rowStatePresentation[state].color}}/>)}</div>
    <div className="fx-action-legend"><span>Recorded actions</span>{(Object.keys(actionPresentation) as (keyof typeof actionPresentation)[]).map(action => { const Icon = actionPresentation[action].icon; return <span key={action}><Icon size={13} aria-hidden="true"/>{action} <strong>{summary.actions[action]}</strong></span>; })}</div>
  </FarmPanel><FarmPanel title="Panels by Zone" icon={BarChart3} className="fx-zone-comparison" meta={<span className="fx-note">Panel count · zero baseline</span>}>
    <ul className="fx-bars">{summary.zones.map(zone => <li key={zone.id}><span>{formatZoneName(zone.id)}</span><div aria-hidden="true"><i style={{width:`${zone.panelCount/maximum*100}%`,background:getZoneColor(zone.id)}}/></div><strong>{zone.panelCount}</strong><small>{zone.rowCount} rows</small></li>)}</ul>
  </FarmPanel></>;
}
