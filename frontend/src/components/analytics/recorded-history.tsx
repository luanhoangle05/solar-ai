import { History } from "lucide-react";
import { OperationsPanel } from "@/components/agents/operations-panel";
import { Badge } from "@/components/ui/badge";
import { actionPresentation } from "@/config/actions";
import { formatAngle, formatKwhEquivalent, formatRecordedTime } from "@/lib/formatters";
import type { getAnalyticsView } from "@/lib/analytics";

export function RecordedHistory({ view }: { view: ReturnType<typeof getAnalyticsView> }) {
  return <OperationsPanel title="Decision History" icon={History} className="inspect-wide" meta={<span className="ops-note">{view.history.length} historical records</span>}>
    <div className="inspect-current"><strong>Current Run</strong><span>{formatRecordedTime(view.current.timestamp)} · {view.current.target}</span><Badge variant={actionPresentation[view.current.decision.action].variant}>{view.current.decision.action} → {formatAngle(view.current.decision.target_angle_deg)}</Badge><span>Net {formatKwhEquivalent(view.current.netBenefit)}</span></div>
    {view.history.length ? <div className="inspect-table-scroll" tabIndex={0} role="region" aria-label="Recorded decision history"><table className="opt-table"><caption>Recorded History · discrete decisions, not telemetry</caption><thead><tr>{["Recorded time (UTC)","Target","Decision","Target angle","Net benefit"].map(label=><th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{view.history.map((event,i)=><tr key={event.timestamp+i}><th scope="row"><time dateTime={event.timestamp}>{formatRecordedTime(event.timestamp)}</time></th><td>{event.control_target_id}</td><td><Badge variant={actionPresentation[event.decision.action].variant}>{event.decision.action}</Badge></td><td>{formatAngle(event.decision.target_angle_deg)}</td><td>{formatKwhEquivalent(event.net_benefit_kwh_equivalent)}</td></tr>)}</tbody></table></div> : <p className="inspect-empty">No recorded decision history in this payload.</p>}
    <p className="inspect-note">Current run is shown separately. No intermediate observations or historical energy values are inferred.</p>
  </OperationsPanel>;
}
