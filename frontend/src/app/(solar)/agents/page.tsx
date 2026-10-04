import { Network } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DataError } from "@/components/shared/data-error";
import { AgentPipeline } from "@/components/agents/agent-pipeline";
import { ModelComparison, SelectedModel } from "@/components/agents/model-comparison";
import { AgentSafety, DataQuality, ManagerDecision } from "@/components/agents/operations-outcomes";
import { AgentActivity, RunProvenance } from "@/components/agents/agent-activity";
import { dataStatusVariants } from "@/config/status";
import { getAgentsSummary } from "@/lib/agents";
import { loadFrontendDataResult } from "@/lib/frontend-data.server";
import "./agents.css";
export const metadata = { title: "AI Operations | SolarAI" };
export default async function Page() {
  const result = await loadFrontendDataResult();
  if (!result.ok) return <DataError message={result.error.message} details={result.error.details}/>;
  const data = result.data; const summary = getAgentsSummary(data); const isMock = data.metadata.dataset_kind === "MOCK";
  return <div className="agents-page"><header className="ops-header"><Network size={29} aria-hidden="true"/><div><h1>AI Operations</h1><p>Trace how SolarAI data, modeling, optimization, and safety agents produce a final panel-angle recommendation.</p></div><div className="ops-header-badges"><Badge variant={isMock ? "warning" : "outline"}>{data.metadata.dataset_kind} DATA</Badge><Badge variant={dataStatusVariants[data.data_agent.status]}>{data.data_agent.status}</Badge><Badge variant="outline">{summary.pipeline.length} AGENT STAGES</Badge></div></header>
    <div className="ops-grid"><ManagerDecision data={data} summary={summary}/><AgentPipeline summary={summary} isMock={isMock}/><AgentSafety summary={summary} isMock={isMock}/><SelectedModel summary={summary}/><DataQuality summary={summary}/><ModelComparison summary={summary}/><AgentActivity summary={summary}/><RunProvenance data={data} summary={summary}/></div>
  </div>;
}
