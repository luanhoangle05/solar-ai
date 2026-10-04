import { Target } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DataError } from "@/components/shared/data-error";
import { OptimizationContext } from "@/components/optimization/optimization-context";
import { OptimizationResult } from "@/components/optimization/optimization-result";
import { CandidateEnergyProfile } from "@/components/optimization/candidate-energy-profile";
import { CurrentVsRecommended, NetBenefitBreakdown, OptimizationInsight } from "@/components/optimization/optimization-analysis";
import { CandidateTable } from "@/components/optimization/candidate-table";
import { OptimizationAgentHandoff, PredictionModel, SafetyValidation } from "@/components/optimization/optimization-support";
import { loadFrontendDataResult } from "@/lib/frontend-data.server";
import { getOptimizationSummary } from "@/lib/optimization";
import { formatRecordedTime } from "@/lib/formatters";
import "./optimization.css";

export const metadata = { title: "Optimization | SolarAI" };

export default async function Page() {
  const result = await loadFrontendDataResult();
  if (!result.ok) return <DataError message={result.error.message} details={result.error.details}/>;
  const data = result.data;
  const summary = getOptimizationSummary(data);
  return <div className="optimization-page">
    <header className="opt-page-header"><Target size={28} aria-hidden="true"/><div><h1>Optimization</h1><p>Understand how SolarAI evaluates candidate panel angles and selects the highest-value safe recommendation.</p></div><Badge variant="outline">READ-ONLY RESULT</Badge></header>
    {data.errors.length > 0 && <section className="opt-run-errors" role="alert" aria-label="Run issues">{data.errors.map((error,i) => <p key={i}><strong>{error.agent} · {error.code}</strong> {error.message}</p>)}</section>}
    <div className="opt-grid">
      <OptimizationResult summary={summary}/>
      <CurrentVsRecommended summary={summary}/>
      <OptimizationInsight summary={summary}/>
      <CandidateEnergyProfile candidates={summary.candidates} current={summary.currentAngle} recommended={summary.recommendedAngle} rawAngles={summary.rawMaxima.map(point => point.angle_deg)} horizon={data.metadata.prediction_horizon_minutes} scope={data.metadata.energy_scope}/>
      <OptimizationContext data={data} summary={summary}/>
      <NetBenefitBreakdown summary={summary}/>
      <CandidateTable candidates={summary.candidates}/>
      <SafetyValidation summary={summary}/>
      <PredictionModel summary={summary}/>
      <OptimizationAgentHandoff summary={summary}/>
    </div>
    <footer className="opt-footer"><span>{data.metadata.dataset_kind === "MOCK" ? "MOCK DEVELOPMENT DATA · synthetic predictions and outcomes" : "Recorded contract data"}</span><span>Recorded run: <time dateTime={data.timestamp}>{formatRecordedTime(data.timestamp)}</time> · {data.metadata.config_id}</span></footer>
  </div>;
}
