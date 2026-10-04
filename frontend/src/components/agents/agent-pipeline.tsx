import { ArrowRight, BrainCircuit, Database, Network, ShieldCheck, Target } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { agentRoles, formatAgentName, type AgentsSummary } from "@/lib/agents";
import { formatDisplayName, formatRecordedTime } from "@/lib/formatters";
import { OperationsPanel } from "./operations-panel";
const icons = { data: Database, modeling: BrainCircuit, optimization: Target, manager: ShieldCheck };
export function AgentPipeline({ summary, isMock }: { summary: AgentsSummary; isMock: boolean }) {
  return <OperationsPanel title="Agent Pipeline" icon={Network} className="ops-pipeline" meta={<span className="ops-muted">Architecture & recorded evidence</span>}>
    <ol className="ops-stages">{summary.pipeline.map((stage, index) => {
      const Icon = icons[stage.agent];
      return <li key={stage.agent} data-agent={stage.agent}>
        <div className="ops-stage-top"><span className="ops-agent-icon"><Icon size={23} aria-hidden="true"/></span><span className="ops-step">0{index + 1}</span></div>
        <h3>{formatAgentName(stage.agent)}</h3><p className="ops-role">{agentRoles[stage.agent]}</p>
        <Badge variant={stage.errors.length ? "danger" : stage.latest ? "secondary" : "outline"}>{stage.evidence}</Badge>
        <div className="ops-latest">{stage.latest ? <><strong>{formatDisplayName(stage.latest.action)}</strong><p>{stage.latest.result}</p><time dateTime={stage.latest.timestamp}>{formatRecordedTime(stage.latest.timestamp, false)}</time></> : <p>No recorded agent activity for this stage.</p>}</div>
        {stage.errors.length > 0 && <p className="ops-error-count">{stage.errors.length} recorded issue{stage.errors.length === 1 ? "" : "s"}</p>}
        {index < summary.pipeline.length - 1 && <ArrowRight className="ops-connector" size={17} aria-hidden="true"/>}
      </li>;
    })}</ol><p className="ops-note">{isMock ? "MOCK fixture events and illustrative outcomes. " : "Recorded payload evidence. "}Stage order describes the architecture; timestamps describe the recorded activity.</p>
  </OperationsPanel>;
}
