import { ChartNoAxesCombined, Gauge, Target, Zap, TrendingUp, BrainCircuit, Grid2X2, ListChecks } from "lucide-react";
import { DataError } from "@/components/shared/data-error";
import { InspectionPage } from "@/components/shared/inspection-page";
import { MetricCard } from "@/components/shared/metric-card";
import { OperationsPanel } from "@/components/agents/operations-panel";
import { ModelComparison, SelectedModel } from "@/components/agents/model-comparison";
import { CandidateEnergyProfile } from "@/components/optimization/candidate-energy-profile";
import { CandidateTable } from "@/components/optimization/candidate-table";
import { NetBenefitBreakdown, OptimizationInsight } from "@/components/optimization/optimization-analysis";
import { ModelErrorChart } from "@/components/analytics/model-error-chart";
import { RecordedHistory } from "@/components/analytics/recorded-history";
import { actionPresentation } from "@/config/actions";
import { rowStatePresentation } from "@/config/row-states";
import { getAnalyticsView } from "@/lib/analytics";
import { loadFrontendDataResult } from "@/lib/frontend-data.server";
import { formatAngle, formatKwh, formatKwhEquivalent, formatModelName } from "@/lib/formatters";
export const metadata = { title: "Analytics | SolarAI" };
export default async function Page() {
  const result = await loadFrontendDataResult();
  if (!result.ok) return <DataError message={result.error.message} details={result.error.details}/>;
  const data = result.data, view = getAnalyticsView(data), summary = view.optimization;
  return <InspectionPage data={data} icon={ChartNoAxesCombined} title="Analytics" description="Review the recorded prediction, optimization, model, farm, and decision signals available in this SolarAI payload.">
    <div className="inspect-kpis">
      <MetricCard icon={Gauge} label="Current angle" value={formatAngle(summary.currentAngle)} detail={data.metadata.control_target_id}/>
      <MetricCard icon={Target} label="Recommended angle" value={formatAngle(summary.recommendedAngle)} detail="Backend recommendation"/>
      <MetricCard icon={Zap} label="Predicted energy" value={formatKwh(summary.optimization?.predicted_kwh ?? null)} detail={`${data.metadata.energy_scope} / ${data.metadata.prediction_horizon_minutes} min`}/>
      <MetricCard icon={TrendingUp} label="Net benefit" value={formatKwhEquivalent(summary.optimization?.net_benefit_kwh_equivalent ?? null)} detail="After movement cost"/>
      <MetricCard icon={BrainCircuit} label="Selected model" value={formatModelName(data.selected_model)} detail={`${data.decision.action} · Safety ${data.safety.passed ? "PASS" : "FAIL"}`}/>
    </div>
    <div className="inspect-grid inspect-analytics">
      <CandidateEnergyProfile candidates={summary.candidates} current={summary.currentAngle} recommended={summary.recommendedAngle} rawAngles={summary.rawMaxima.map(point=>point.angle_deg)} horizon={data.metadata.prediction_horizon_minutes} scope={data.metadata.energy_scope}/>
      <NetBenefitBreakdown summary={summary}/>
      <OperationsPanel title="Model Error Comparison" icon={ChartNoAxesCombined}><ModelErrorChart models={data.model_comparison}/><p className="inspect-note">Supplied MAE / RMSE values. R² is displayed separately in the exact model metrics. {data.metadata.dataset_kind === "MOCK" && "Synthetic fixture metrics; no trained-model performance claim."}</p></OperationsPanel>
      <SelectedModel summary={view.agents}/>
      <div className="inspect-wide"><OptimizationInsight summary={summary}/></div>
      <div className="inspect-wide"><ModelComparison summary={view.agents}/></div>
      <RecordedHistory view={view}/>
      {([ ["Farm Row States",Grid2X2,view.farm.states,rowStatePresentation], ["Recorded Row Actions",ListChecks,view.farm.actions,actionPresentation] ] as const).map(([title,icon,counts,presentation])=><OperationsPanel key={title} title={title} icon={icon}>{view.rowCount ? <ul className="inspect-counts">{Object.entries(counts).map(([label,count])=><li key={label}><div><span>{label}</span><strong>{count} {count === 1 ? "row" : "rows"}</strong></div><div className="inspect-track" aria-hidden="true"><span style={{width:`${count/view.rowCount*100}%`,background: (presentation as Record<string,{color:string}>)[label].color}}/></div></li>)}</ul> : <p className="inspect-empty">No farm rows supplied.</p>}<p className="inspect-note">Loaded farm snapshot · {view.rowCount} rows. Recorded actions do not confirm command execution.</p></OperationsPanel>)}
      <div className="inspect-wide"><CandidateTable candidates={summary.candidates}/></div>
    </div>
  </InspectionPage>;
}
