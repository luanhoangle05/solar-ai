import { Crosshair } from "lucide-react";
import { getDashboardSummary } from "@/lib/dashboard";
import { formatZoneName } from "@/lib/farm";
import { formatAngle } from "@/lib/formatters";
import type { FrontendData } from "@/types/solar";
export function OperatorControlTarget({ data }: {data:FrontendData}) {
  const { targetRow:row, targetZone:zone } = getDashboardSummary(data);
  return <section className="operator-target operator-card"><header className="operator-card-heading"><Crosshair size={19} aria-hidden="true"/><h2>Control Target</h2>{row && <span>{row.row_id}</span>}</header>{row ? <dl><div><dt>Zone</dt><dd>{zone ? formatZoneName(zone.zone_id) : "Unavailable"}</dd></div><div><dt>Panels</dt><dd>{row.panel_count}</dd></div><div><dt>Current Angle</dt><dd>{formatAngle(row.angle_deg)}</dd></div><div><dt>Recommended Angle</dt><dd>{data.optimization || data.decision.action === "STOW" ? formatAngle(data.decision.target_angle_deg) : "Unavailable"}</dd></div><div><dt>State</dt><dd>{row.current_state}</dd></div><div><dt>Recommendation</dt><dd>{data.optimization || data.decision.action === "STOW" ? data.decision.action : "Unavailable"}</dd></div></dl> : <p className="operator-empty">Control target unavailable</p>}</section>;
}
