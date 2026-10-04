import { DataError } from "@/components/shared/data-error";
import { DashboardKpiGrid } from "@/components/dashboard/dashboard-kpi-grid";
import { FarmOverview } from "@/components/dashboard/farm-overview";
import { OptimizationContext } from "@/components/dashboard/optimization-context";
import { OptimizationResult } from "@/components/dashboard/optimization-result";
import { ControlTargetDetails, PanelRowPreview } from "@/components/dashboard/control-target-details";
import { CandidateEnergyPanel } from "@/components/dashboard/candidate-energy-panel";
import { WeatherSummary } from "@/components/dashboard/weather-summary";
import { SafetySummary } from "@/components/dashboard/safety-summary";
import { SelectedModelSummary } from "@/components/dashboard/selected-model-summary";
import { AgentActivityPreview } from "@/components/dashboard/agent-activity-preview";
import { RecentDecisions } from "@/components/dashboard/recent-decisions";
import { SystemIssues } from "@/components/dashboard/system-issues";
import { loadFrontendDataResult } from "@/lib/frontend-data.server";
import { getDashboardSummary } from "@/lib/dashboard";
import { formatRecordedTime } from "@/lib/formatters";
import "./dashboard.css";

export default async function Dashboard() {
  const result = await loadFrontendDataResult();
  if (!result.ok) return <DataError message={result.error.message} details={result.error.details} />;
  const data = result.data;
  const summary = getDashboardSummary(data);
  const isMock = data.metadata.dataset_kind === "MOCK";
  return <><h1 className="sr-only">SolarAI Dashboard</h1><SystemIssues errors={data.errors}/><div className="dashboard">
    <OptimizationResult data={data} summary={summary}/>
    <DashboardKpiGrid summary={summary} metadata={data.metadata}/>
    <WeatherSummary weather={summary.weather} report={data.data_agent} isMock={isMock}/>
    <FarmOverview summary={summary} farm={data.farm_status}/>
    <OptimizationContext data={data} summary={summary}/>
    <CandidateEnergyPanel data={data} summary={summary}/>
    <ControlTargetDetails summary={summary}/>
    <PanelRowPreview summary={summary}/>
    <AgentActivityPreview events={summary.events} isMock={isMock}/>
    <details className="dashboard-run-details" open={!data.safety.passed}><summary>Safety checks, model provenance & decision history</summary><div className="run-detail-grid"><SafetySummary safety={data.safety}/><SelectedModelSummary model={summary.selectedModel}/><RecentDecisions history={data.history} isMock={isMock}/></div></details>
    <footer className="dashboard-footer"><span>{isMock ? "MOCK development fixture · synthetic data" : "Recorded contract snapshot"} · {isMock ? "Fixture run" : "Run"}: <time dateTime={data.timestamp}>{formatRecordedTime(data.timestamp)}</time></span><span>{data.metadata.config_id} · Read-only</span></footer>
  </div></>;
}
