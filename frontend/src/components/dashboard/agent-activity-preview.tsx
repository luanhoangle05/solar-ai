import Link from "next/link";
import { Bot, BrainCircuit, Database, Network, Target } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { formatDisplayName, formatRecordedTime } from "@/lib/formatters";
import { getAgentPipelineSummary } from "@/lib/agents";
import type { FrontendData } from "@/types/solar";
const agentIcons = { data: Database, modeling: BrainCircuit, optimization: Target, manager: Bot };
export function AgentActivityPreview({ data }: { data: FrontendData }) {
  return <DashboardPanel title="AI Pipeline Summary" icon={Network} className="dashboard-activity" action={<Link href="/agents" className="dashboard-link">View AI Decision Path ↗</Link>}>
    <ol className="dashboard-pipeline">{getAgentPipelineSummary(data).map(stage => { const Icon = agentIcons[stage.agent]; return <li key={stage.agent} data-issue={stage.errors.length > 0}><div className="pipeline-heading"><Icon size={20} aria-hidden="true"/><h3>{formatDisplayName(stage.agent)}</h3><span>{stage.evidence}</span></div>{stage.latest ? <details><summary>{formatDisplayName(stage.latest.action)}</summary><p>{stage.latest.result}</p><time dateTime={stage.latest.timestamp}>{formatRecordedTime(stage.latest.timestamp, false)}</time></details> : <p className="dashboard-note">No recorded activity.</p>}{stage.errors.map((error, index) => <p className="text-danger" key={index}>{error.code}: {error.message}</p>)}</li>; })}</ol>
    <p className="dashboard-note">{data.metadata.dataset_kind === "MOCK" ? "Synthetic fixture evidence" : "Loaded payload evidence"} · latest recorded event per agent.</p>
  </DashboardPanel>;
}
