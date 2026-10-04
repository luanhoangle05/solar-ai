import { DataError } from "@/components/shared/data-error";
import { DashboardKpiGrid } from "@/components/dashboard/dashboard-kpi-grid";
import { FarmOverview } from "@/components/dashboard/farm-overview";
import { OptimizationContext } from "@/components/dashboard/optimization-context";
import { OptimizationResult } from "@/components/dashboard/optimization-result";
import { ControlTargetDetails } from "@/components/dashboard/control-target-details";
import { IrradianceSnapshot } from "@/components/dashboard/irradiance-snapshot";
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
import "../(solar)/optimization/optimization.css";
import "./dashboard.css";

export default async function Dashboard() {
  const result = await loadFrontendDataResult();
  if (!result.ok) return <DataError message={result.error.message} details={result.error.details} />;
  const data = result.data;
  const summary = getDashboardSummary(data);
  const isMock = data.metadata.dataset_kind === "MOCK";
  return <><header className="dashboard-heading"><div><h1>Dashboard</h1><p>SolarAI control center · recorded run</p></div><span>{isMock ? "MOCK DATA" : "RECORDED DATA"} · Read-only</span></header><SystemIssues errors={data.errors}/><div className="dashboard">
    <div className="dashboard-rail dashboard-left">
    <WeatherSummary weather={summary.weather} report={data.data_agent} isMock={isMock}/>
    <OptimizationContext data={data} summary={summary}/>
    <SelectedModelSummary model={summary.selectedModel}/>
    </div>
    <div className="dashboard-rail dashboard-center">
    <DashboardKpiGrid summary={summary} metadata={data.metadata} farm={data.farm_status}/>
    <FarmOverview summary={summary} farm={data.farm_status}/>
    <div className="dashboard-charts">
    <CandidateEnergyPanel data={data} summary={summary}/>
    <IrradianceSnapshot data={data}/>
    </div>
    <AgentActivityPreview data={data}/>
    </div>
    <div className="dashboard-rail dashboard-right">
    <OptimizationResult data={data} summary={summary}/>
    <ControlTargetDetails summary={summary} safety={data.safety}/>
    <SafetySummary safety={data.safety}/>
    </div>
    <details className="dashboard-run-details"><summary>Recorded decision history ({data.history.length})</summary><RecentDecisions history={data.history} isMock={isMock}/></details>
    <footer className="dashboard-footer"><span>{isMock ? "MOCK development fixture · synthetic data" : "Recorded contract snapshot"} · {isMock ? "Fixture run" : "Run"}: <time dateTime={data.timestamp}>{formatRecordedTime(data.timestamp)}</time></span><span>{data.metadata.config_id} · Read-only</span></footer>
  </div></>;
}
