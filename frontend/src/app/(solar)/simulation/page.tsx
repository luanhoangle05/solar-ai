import { Workflow, ListFilter, ScanLine } from "lucide-react";
import { DataError } from "@/components/shared/data-error";
import { InspectionPage, Facts, PredictionFacts } from "@/components/shared/inspection-page";
import { OperationsPanel } from "@/components/agents/operations-panel";
import { AgentSafety, ManagerDecision } from "@/components/agents/operations-outcomes";
import { AgentActivity } from "@/components/agents/agent-activity";
import { CandidateEnergyProfile } from "@/components/optimization/candidate-energy-profile";
import { CandidateTable } from "@/components/optimization/candidate-table";
import { OptimizationInsight } from "@/components/optimization/optimization-analysis";
import { loadFrontendDataResult } from "@/lib/frontend-data.server";
import { getScenarioView } from "@/lib/simulation";
import { formatAngle } from "@/lib/formatters";
export const metadata = { title: "Simulation | SolarAI" };
export default async function Page() {
  const result = await loadFrontendDataResult();
  if (!result.ok) return <DataError message={result.error.message} details={result.error.details}/>;
  const data = result.data, view = getScenarioView(data), summary = view.optimization;
  return <InspectionPage data={data} icon={Workflow} title="Simulation" label="RECORDED SCENARIO" description="Review the candidate-angle scenario and decision path contained in the current SolarAI payload.">
    <div className="inspect-grid inspect-scenario">
      <ManagerDecision data={data} summary={view.agents}/>
      <OperationsPanel title="Recorded Scenario Pipeline" icon={Workflow} className="inspect-wide inspect-pipeline" meta={<span className="ops-note">Payload evidence · read only</span>}>
        <ol className="inspect-stages">{view.stages.map((stage,i)=><li key={stage.title} data-available={stage.available}><span className="inspect-step">{String(i+1).padStart(2,"0")}</span><h3>{stage.title}</h3><p>{stage.evidence}</p></li>)}</ol><p className="inspect-note">Read from input to decision. Stage numbers explain the recorded data path; they do not indicate runtime progress.</p>
      </OperationsPanel>
      <OperationsPanel title="Scenario Input" icon={ListFilter} className="inspect-input"><div className="inspect-context"><PredictionFacts metadata={data.metadata}/><Facts rows={[["Current row angle",formatAngle(view.input.currentAngle)],["Selected model",view.input.model],["Candidate count",view.input.candidateCount],["Temperature",view.input.weather?.temperature ?? "Unavailable"],["Wind speed / gust",view.input.weather ? `${view.input.weather.wind} / ${view.input.weather.gust}` : "Unavailable"]]}/></div></OperationsPanel>
      <div className="inspect-wide"><CandidateEnergyProfile candidates={summary.candidates} current={summary.currentAngle} recommended={summary.recommendedAngle} rawAngles={summary.rawMaxima.map(point=>point.angle_deg)} horizon={view.input.horizon} scope={view.input.scope}/></div>
      <div className="inspect-wide"><OptimizationInsight summary={summary}/></div>
      <AgentSafety summary={view.agents} isMock={data.metadata.dataset_kind === "MOCK"}/>
      <OperationsPanel title="Recommendation → Decision" icon={ScanLine}><Facts rows={[["Backend recommendation",formatAngle(summary.recommendedAngle)],["Safety result",data.safety.passed ? "PASS" : "FAIL"],["Manager action",data.decision.action],["Manager target",formatAngle(data.decision.target_angle_deg)]]}/><p className="inspect-note">{data.safety.reason}</p><p className="inspect-note">{data.decision.reason}</p><p className="inspect-note">The row snapshot remains {formatAngle(view.input.currentAngle)}. The decision target is a proposed action, not confirmation of panel movement.</p></OperationsPanel>
      <div className="inspect-wide"><AgentActivity summary={view.agents}/></div>
      <div className="inspect-wide"><CandidateTable candidates={summary.candidates}/></div>
    </div>
  </InspectionPage>;
}
