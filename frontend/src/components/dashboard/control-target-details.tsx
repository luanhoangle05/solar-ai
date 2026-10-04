import { Crosshair } from "lucide-react";
import Link from "next/link";
import { DashboardPanel } from "./dashboard-panel";
import { formatAngle } from "@/lib/formatters";
import type { DashboardSummary } from "@/lib/dashboard";
import type { FrontendData } from "@/types/solar";
import { formatZoneName } from "@/lib/farm";
import { rowStatePresentation } from "@/config/row-states";

export function ControlTargetDetails({ summary, safety }: { summary: DashboardSummary; safety: FrontendData["safety"] }) {
  const row = summary.targetRow;
  const zone = summary.targetZone;
  return <DashboardPanel title="Control Target" icon={Crosshair} className="dashboard-target" action={<Link href="/farm" className="dashboard-link">Farm ↗</Link>}>
    {row ? <><div className="target-identity"><Crosshair aria-hidden="true" size={23}/><strong>{row.row_id}</strong><span style={{color:rowStatePresentation[row.current_state].color}}>{row.current_state}</span></div>
    <div className="target-row-visual"><div className="row-preview-art" aria-hidden="true"><div className="preview-array"/><div className="preview-support"/></div><p className="dashboard-note">Schematic row<br/>{row.panel_count} panels<br/>Observed {formatAngle(row.angle_deg)}</p></div><dl className="result-values">
      <div><dt>Zone</dt><dd>{zone ? formatZoneName(zone.zone_id) : "Unavailable"}</dd></div><div><dt>Panels / current angle</dt><dd>{row.panel_count} / {formatAngle(row.angle_deg)}</dd></div><div><dt>Recorded action</dt><dd>{row.action}</dd></div><div><dt>Recommended angle</dt><dd>{formatAngle(summary.recommendedAngleDeg)}</dd></div><div><dt>Safety</dt><dd>{safety.passed ? "PASSED" : "BLOCKED"}</dd></div>
    </dl></> : <p className="dashboard-empty">Control target unavailable.</p>}
  </DashboardPanel>;
}
