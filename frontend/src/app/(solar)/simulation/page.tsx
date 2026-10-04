import { Workflow, ListFilter, ScanLine } from "lucide-react";
import { DataError } from "@/components/shared/data-error";
import { InspectionPage, Facts, PredictionFacts } from "@/components/shared/inspection-page";
import { OperationsPanel } from "@/components/agents/operations-panel";
import { AgentSafety, ManagerDecision } from "@/components/agents/operations-outcomes";
import { AgentActivity } from "@/components/agents/agent-activity";
import { CandidateEnergyProfile } from "@/components/optimization/candidate-energy-profile";
import { CandidateTable } from "@/components/optimization/candidate-table";
import { OptimizationInsight } from "@/components/optimization/optimization-analysis";
import { loadFrontendDataResult, loadZoneRuns } from "@/lib/frontend-data.server";
import type { FarmSimulationData } from "@/lib/farm-simulation";
import type { FrontendData } from "@/types/solar";
const toSimulationData = (run: FrontendData): FarmSimulationData => ({ farm_status: run.farm_status, metadata: run.metadata, optimization: run.optimization, decision: run.decision, safety: run.safety, current_weather: run.current_weather, candidate_predictions: run.candidate_predictions });
import { getScenarioView } from "@/lib/simulation";
import { getCommandCenterView } from "@/lib/command-center";
import { AgentCommandCenter } from "@/components/simulation/agent-command-center";
import { SolarFarmSimulation } from "@/components/simulation/solar-farm-simulation";
import { formatAngle } from "@/lib/formatters";
export const metadata = { title: "Simulation | SolarAI" };
export default async function Page() {
  const result = await loadFrontendDataResult();
  if (!result.ok) return <DataError message={result.error.message} details={result.error.details}/>;
  const data = result.data, view = getScenarioView(data), summary = view.optimization;
  const zoneRuns = await loadZoneRuns();
  return <InspectionPage data={data} icon={Workflow} title="Simulation" label="RECORDED SCENARIO" description="Review the candidate-angle scenario and decision path contained in the current SolarAI payload.">
    <div className="inspect-grid inspect-scenario">
      <ManagerDecision data={data} summary={view.agents}/>
      <AgentCommandCenter view={getCommandCenterView(data)}/>
      <SolarFarmSimulation data={toSimulationData(data)} zoneRuns={zoneRuns.runs.map(toSimulationData)} zoneRunsError={zoneRuns.error}/>
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
