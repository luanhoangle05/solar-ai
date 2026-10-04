import { Crosshair, PanelsTopLeft } from "lucide-react";
import Link from "next/link";
import { DashboardPanel } from "./dashboard-panel";
import { formatAngle } from "@/lib/formatters";
import type { DashboardSummary } from "@/lib/dashboard";

export function ControlTargetDetails({ summary }: { summary: DashboardSummary }) {
  const row = summary.targetRow;
  const zone = summary.targetZone;
  return <DashboardPanel title="Control Target Details" icon={Crosshair} className="dashboard-target" action={<Link href="/farm" className="dashboard-link">Farm ↗</Link>}>
    {row ? <><div className="target-identity"><Crosshair aria-hidden="true" size={26}/><strong>{row.row_id}</strong><span>{row.current_state}</span></div><dl className="result-values">
      <div><dt>Zone</dt><dd>{row.zone_id}</dd></div><div><dt>Panels / observed angle</dt><dd>{row.panel_count} / {formatAngle(row.angle_deg)}</dd></div><div><dt>Proposed row action</dt><dd>{row.action}</dd></div><div><dt>Zone panels / rows</dt><dd>{zone ? zone.panel_count + " / " + zone.row_ids.length : "Unavailable"}</dd></div>
    </dl></> : <p className="dashboard-empty">Control target unavailable.</p>}
  </DashboardPanel>;
}

export function PanelRowPreview({ summary }: { summary: DashboardSummary }) {
  const row = summary.targetRow;
  return <DashboardPanel title="Panel / Row Preview" icon={PanelsTopLeft} className="dashboard-preview" action={<span className="eyebrow">Read-only</span>}>
    <div className="row-preview-art" aria-hidden="true"><div className="preview-array"/><div className="preview-support"/></div>
    {row ? <><div className="preview-caption"><strong>{row.row_id}</strong><span>{row.panel_count} panels · {row.current_state}</span></div><div className="angle-comparison"><div><span>Current</span><strong>{formatAngle(row.angle_deg)}</strong></div><span aria-hidden="true">→</span><div><span>Recommended</span><strong>{formatAngle(summary.recommendedAngleDeg)}</strong></div></div></> : <p className="dashboard-empty">Row preview unavailable.</p>}
    <p className="dashboard-note">Illustration only · observed and proposed tilt.</p>
  </DashboardPanel>;
}
