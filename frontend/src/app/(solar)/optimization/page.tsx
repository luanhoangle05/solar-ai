import { Target } from "lucide-react";
import { DataError } from "@/components/shared/data-error";
import { OptimizationContext } from "@/components/optimization/optimization-context";
import { OptimizationResult } from "@/components/optimization/optimization-result";
import { CandidateEnergyProfile } from "@/components/optimization/candidate-energy-profile";
import { CurrentVsRecommended, NetBenefitBreakdown, OptimizationInsight } from "@/components/optimization/optimization-analysis";
import { CandidateTable } from "@/components/optimization/candidate-table";
import { PredictionModel, SafetyValidation } from "@/components/optimization/optimization-support";
import { loadFrontendDataResult } from "@/lib/frontend-data.server";
import { getOptimizationSummary } from "@/lib/optimization";
import "./optimization.css";

export const metadata = { title: "Optimization | SolarAI" };

export default async function Page() {
  const result = await loadFrontendDataResult();
  if (!result.ok) return <DataError message={result.error.message} details={result.error.details}/>;
  const data = result.data;
  const summary = getOptimizationSummary(data);
  return <div className="optimization-page">
    <header className="opt-page-header"><Target size={28} aria-hidden="true"/><div><h1>Optimization</h1><p>Understand why SolarAI selected this operating angle.</p></div></header>
    {data.errors.length > 0 && <section className="opt-run-errors" role="alert" aria-label="Run issues">{data.errors.map((error,i) => <p key={i}><strong>{error.agent} · {error.code}</strong> {error.message}</p>)}</section>}
    <div className="opt-grid">
      <OptimizationResult summary={summary}/>
      <CandidateEnergyProfile candidates={summary.candidates} current={summary.currentAngle} recommended={summary.recommendedAngle} rawAngles={summary.rawMaxima.map(point => point.angle_deg)} horizon={data.metadata.prediction_horizon_minutes} scope={data.metadata.energy_scope}/>
      <OptimizationInsight summary={summary}/>
      <CurrentVsRecommended summary={summary}/>
      <NetBenefitBreakdown summary={summary}/>
      <CandidateTable candidates={summary.candidates}/>
      <SafetyValidation summary={summary}/>
      <details className="opt-prediction-details"><summary>Prediction Details</summary><div><PredictionModel summary={summary}/><OptimizationContext data={data} summary={summary}/></div></details>
    </div>
  </div>;
}
