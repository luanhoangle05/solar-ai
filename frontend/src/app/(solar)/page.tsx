import { FlaskConical, LayoutDashboard } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { DataError } from "@/components/shared/data-error";
import { DecisionCard } from "@/components/shared/decision-card";
import { DashboardKpiGrid } from "@/components/dashboard/dashboard-kpi-grid";
import { FarmOverview } from "@/components/dashboard/farm-overview";
import { OptimizationSummary } from "@/components/dashboard/optimization-summary";
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

  return (
    <div className="dashboard">
      <div className="dashboard-title"><PageHeader icon={LayoutDashboard} title="Dashboard" description="Operational overview of SolarAI weather, prediction, optimization, safety, and farm state." /></div>
      <div className="dashboard-provenance">
        <FlaskConical size={15} aria-hidden="true" />
        <p>{isMock ? "Development fixture · Synthetic weather, model, optimization, and farm data. Not production measurements or hardware authorization." : "Recorded contract data · recommendations do not confirm hardware execution."}</p>
      </div>
      <SystemIssues errors={data.errors} />
      <DecisionCard decision={data.decision} safetyPassed={data.safety.passed} currentAngle={summary.currentAngleDeg} />
      <DashboardKpiGrid summary={summary} metadata={data.metadata} />
      <OptimizationSummary optimization={summary.optimization} />
      <CandidateEnergyPanel data={data} summary={summary} />
      <WeatherSummary weather={summary.weather} report={data.data_agent} isMock={isMock} />
      <FarmOverview summary={summary} farm={data.farm_status} />
      <SafetySummary safety={data.safety} />
      <SelectedModelSummary model={summary.selectedModel} />
      <AgentActivityPreview events={summary.events} isMock={isMock} />
      <RecentDecisions history={data.history} isMock={isMock} />
      <footer className="dashboard-footer">
        <span>{isMock ? "Fixture run" : "Recorded"}: <time dateTime={data.timestamp}>{formatRecordedTime(data.timestamp)}</time></span>
        <span>{data.metadata.config_id} · {data.errors.length === 0 ? "No system issues reported" : data.errors.length + " system issues reported"}</span>
      </footer>
    </div>
  );
}
