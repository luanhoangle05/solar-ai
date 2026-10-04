import Link from "next/link";
import { Bot, BrainCircuit, Database, Network, Target } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { formatDisplayName, formatRecordedTime } from "@/lib/formatters";
import type { FrontendData } from "@/types/solar";

const agentIcons = { data: Database, modeling: BrainCircuit, optimization: Target, manager: Bot };
export function AgentActivityPreview({ events, isMock }: { events: FrontendData["agent_log"]; isMock: boolean }) {
  return <DashboardPanel title="AI Agent Flow" icon={Network} className="dashboard-activity" action={<Link href="/agents" className="dashboard-link">Agents ↗</Link>}>
    <p className="dashboard-note">{isMock ? "Fixture events" : "Recorded events"} · chronological</p>
    {events.length ? <ol className="agent-events">{events.map((event,index) => { const Icon = agentIcons[event.agent]; return <li key={event.timestamp + index}><span className="agent-event-icon"><Icon size={15} aria-hidden="true"/></span><details><summary><span>{formatDisplayName(event.agent)}</span> {formatDisplayName(event.action)}</summary><p>{event.result}</p><time dateTime={event.timestamp}>{formatRecordedTime(event.timestamp,false)}</time></details></li>; })}</ol> : <p className="dashboard-empty">No agent activity recorded for this run.</p>}
  </DashboardPanel>;
}
