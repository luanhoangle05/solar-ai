import Link from "next/link";
import { Crosshair, PanelsTopLeft } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { FarmZones } from "@/components/farm/farm-zones";
import { rowStatePresentation } from "@/config/row-states";
import type { DashboardSummary } from "@/lib/dashboard";
import { formatAngle } from "@/lib/formatters";
import type { FarmStatus } from "@/types/solar";

export function FarmOverview({ summary, farm }: { summary: DashboardSummary; farm: FarmStatus }) {
  const row = summary.targetRow;
  return <DashboardPanel title="Solar Farm Overview" icon={PanelsTopLeft} className="dashboard-farm" action={<span className="farm-totals">{farm.total_panels.toLocaleString("en-US")} panels · {farm.rows.length} rows · {farm.zones.length} zones</span>}>
    <div className="farm-canvas"><p className="farm-view-label">Schematic overview <span>Not geographic · rows illustrative</span></p>
      {farm.zones.length && farm.rows.length ? <FarmZones mode="overview" farm={farm} targetId={row?.row_id ?? null}/> : <p className="dashboard-empty">Farm overview unavailable.</p>}
      <div className="farm-info-strip">{row ? <><Crosshair size={20} aria-hidden="true"/><div><span>Control target</span><strong>{row.row_id}</strong></div><div><span>Current / recommended</span><strong>{formatAngle(row.angle_deg)}{summary.decisionAction === "HOLD" || summary.recommendedAngleDeg === null || row.angle_deg === summary.recommendedAngleDeg ? " / " : " → "}{formatAngle(summary.recommendedAngleDeg)}</strong></div><div><span>Row state</span><strong style={{color: rowStatePresentation[row.current_state].color}}>{row.current_state}</strong></div></> : <p>Control target unavailable.</p>}</div>
    </div>
    <div className="farm-state-summary"><span>Recorded row states</span>{Object.entries(summary.rowStates).map(([state,count]) => <span key={state}><strong>{count}</strong> {state}</span>)}<Link href="/farm" prefetch={false} className="farm-open-link">Open Farm ↗</Link></div>
  </DashboardPanel>;
}
