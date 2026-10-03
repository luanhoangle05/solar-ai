import type { CSSProperties } from "react";
import Link from "next/link";
import { Crosshair, PanelsTopLeft } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { getZoneColor } from "@/config/zones";
import type { DashboardSummary } from "@/lib/dashboard";
import { formatAngle } from "@/lib/formatters";
import type { FarmStatus } from "@/types/solar";

export function FarmOverview({ summary, farm }: { summary: DashboardSummary; farm: FarmStatus }) {
  const row = summary.targetRow;
  return (
    <DashboardPanel title="Solar Farm Overview" icon={PanelsTopLeft} className="dashboard-farm" action={<Link href="/farm" className="dashboard-link">Farm & zones ↗</Link>}>
      <div className="farm-caption">
        <p><strong>{farm.total_panels.toLocaleString("en-US")}</strong> panels <span> / </span><strong>{farm.rows.length}</strong> rows <span> / </span><strong>{farm.zones.length}</strong> zones</p>
        <span>Schematic · not geographic</span>
      </div>
      <div className="farm-schematic" role="group" aria-label="Farm zone summaries">
        {summary.zones.map(zone => (
          <section key={zone.id} className="farm-zone" data-target={zone.isTarget} style={{ "--zone-color": getZoneColor(zone.id) } as CSSProperties}>
            <div className="zone-heading">
              <h3>{zone.id.replace("zone-", "Zone ").replace(/ 0/, " ")}</h3>
              {zone.isTarget && <span className="zone-target"><Crosshair size={12} aria-hidden="true" />Control target</span>}
            </div>
            <div className="solar-row-motif" aria-hidden="true" />
            <p><strong>{zone.panelCount}</strong> panels <span>· {zone.rowCount} rows</span></p>
          </section>
        ))}
      </div>
      {row ? (
        <dl className="target-row-summary">
          <div><dt>Control target</dt><dd>{row.row_id}</dd></div>
          <div><dt>Zone</dt><dd>{row.zone_id}</dd></div>
          <div><dt>Panels</dt><dd>{row.panel_count}</dd></div>
          <div><dt>Observed tilt</dt><dd>{formatAngle(row.angle_deg)}</dd></div>
          <div><dt>State</dt><dd>{row.current_state}</dd></div>
          <div><dt>Proposed action</dt><dd>{row.action}</dd></div>
        </dl>
      ) : <p className="dashboard-note">Control target unavailable.</p>}
      <div className="farm-state-summary"><span>Recorded row states</span>{Object.entries(summary.rowStates).map(([state, count]) => <span key={state}><strong>{count}</strong> {state}</span>)}</div>
    </DashboardPanel>
  );
}
