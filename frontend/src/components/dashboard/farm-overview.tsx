import type { CSSProperties } from "react";
import { Crosshair, MapPin, PanelsTopLeft } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { getZoneColor } from "@/config/zones";
import type { DashboardSummary } from "@/lib/dashboard";
import { formatAngle } from "@/lib/formatters";
import type { FarmStatus } from "@/types/solar";

export function FarmOverview({ summary, farm }: { summary: DashboardSummary; farm: FarmStatus }) {
  const row = summary.targetRow;
  return <DashboardPanel title="Solar Farm Overview" icon={PanelsTopLeft} className="dashboard-farm" action={<span className="farm-totals">{farm.total_panels.toLocaleString("en-US")} panels · {farm.rows.length} rows · {farm.zones.length} zones</span>}>
    <div className="farm-canvas"><p className="farm-view-label">Schematic overview <span>Not geographic · rows illustrative</span></p>
      <div className="farm-schematic" role="group" aria-label="Farm zone summaries">{summary.zones.map(zone =>
        <section key={zone.id} className="farm-zone" data-target={zone.isTarget} style={{ "--zone-color": getZoneColor(zone.id) } as CSSProperties}>
          <div className="zone-arrays" aria-hidden="true">{Array.from({length:6},(_,i) => <div className="solar-row-motif" key={i}/>)}</div>
          <div className="zone-label"><MapPin size={22} aria-hidden="true"/><div><h3>{zone.id.replace("zone-", "Zone ").replace(/ 0/, " ")}</h3><p>{zone.panelCount} panels · {zone.rowCount} rows</p>{zone.isTarget && <span className="zone-target"><Crosshair size={12} aria-hidden="true"/>Control target</span>}</div></div>
        </section>
      )}</div>
      <div className="farm-info-strip">{row ? <><Crosshair size={20} aria-hidden="true"/><div><span>Control target</span><strong>{row.row_id}</strong></div><div><span>Current → recommended</span><strong>{formatAngle(row.angle_deg)} → {formatAngle(summary.recommendedAngleDeg)}</strong></div><div><span>Row state</span><strong>{row.current_state}</strong></div></> : <p>Control target unavailable.</p>}</div>
    </div>
    <div className="farm-state-summary"><span>Recorded row states</span>{Object.entries(summary.rowStates).map(([state,count]) => <span key={state}><strong>{count}</strong> {state}</span>)}</div>
  </DashboardPanel>;
}
