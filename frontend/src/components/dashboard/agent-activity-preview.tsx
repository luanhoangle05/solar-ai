import Link from "next/link";
import { Bot, BrainCircuit, Database, Network, Target } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { formatDisplayName, formatRecordedTime } from "@/lib/formatters";
import type { FrontendData } from "@/types/solar";

const agentIcons = { data: Database, modeling: BrainCircuit, optimization: Target, manager: Bot };

export function AgentActivityPreview({ events, isMock }: { events: FrontendData["agent_log"]; isMock: boolean }) {
  return (
    <DashboardPanel title="AI Agent Activity" icon={Network} className="dashboard-activity" action={<Link href="/agents" className="dashboard-link">Agents ↗</Link>}>
      <p className="dashboard-note mb-3">{isMock ? "Illustrative fixture events" : "Recorded events"} · chronological order</p>
      {events.length ? <ol className="agent-events">{events.map((event, index) => {
        const Icon = agentIcons[event.agent];
        return <li key={event.timestamp + index}>
          <span className="agent-event-icon"><Icon size={16} aria-hidden="true" /></span>
          <div><div className="agent-event-heading"><h3>{formatDisplayName(event.agent)} Agent</h3><time dateTime={event.timestamp}>{formatRecordedTime(event.timestamp, false)}</time></div>
            <p className="agent-action">{formatDisplayName(event.action)}</p><p className="dashboard-note">{event.result}</p>
          </div>
        </li>;
      })}</ol> : <p className="dashboard-empty">No agent activity recorded for this run.</p>}
    </DashboardPanel>
  );
}
