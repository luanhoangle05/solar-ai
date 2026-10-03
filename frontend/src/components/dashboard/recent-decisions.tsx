import { History } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { Badge } from "@/components/ui/badge";
import { actionPresentation } from "@/config/actions";
import { formatAngle, formatKwhEquivalent, formatRecordedTime } from "@/lib/formatters";
import type { FrontendData } from "@/types/solar";

export function RecentDecisions({ history, isMock }: { history: FrontendData["history"]; isMock: boolean }) {
  const recent = [...history].sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp)).slice(0, 4);
  return (
    <DashboardPanel title="Recent Decisions" icon={History} className="dashboard-history" action={<span className="dashboard-note">{isMock ? "Mock history" : "Recorded history"}</span>}>
      {recent.length ? <ul className="recent-decisions">{recent.map((entry, index) => <li key={entry.timestamp + index}>
        <div className="history-heading"><Badge variant={actionPresentation[entry.decision.action].variant}>{entry.decision.action}</Badge><span>{entry.control_target_id} → {formatAngle(entry.decision.target_angle_deg)}</span></div>
        <p className="dashboard-note">{entry.decision.reason}</p>
        <div className="history-meta"><time dateTime={entry.timestamp}>{formatRecordedTime(entry.timestamp)}</time><span>Net {formatKwhEquivalent(entry.net_benefit_kwh_equivalent)}</span></div>
      </li>)}</ul> : <p className="dashboard-empty">No previous decisions in this payload.</p>}
    </DashboardPanel>
  );
}
