import { BrainCircuit, CheckCircle2, Table2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { getModelDisplay, type AgentsSummary } from "@/lib/agents";
import { formatModelName } from "@/lib/formatters";
import { OperationsPanel } from "./operations-panel";
function ModelMetrics({ values }: { values: string[] }) {
  return <dl className="ops-metrics">{["MAE", "RMSE", "R²"].map((label, i) => <div key={label}><dt>{label}</dt><dd>{values[i]}</dd></div>)}</dl>;
}
export function SelectedModel({ summary }: { summary: AgentsSummary }) {
  const model = summary.selectedModel ? getModelDisplay(summary.selectedModel, summary.selectedModel.model) : null;
  return <OperationsPanel title="Selected Prediction Model" icon={BrainCircuit} className="ops-selected" meta={model && <Badge variant={model.variant}>{model.status}</Badge>}>
    {model ? <><div className="ops-selected-title"><CheckCircle2 size={23} aria-hidden="true"/><div><h3>{formatModelName(model.model)}</h3><p>{model.implementation || "Implementation unavailable"}</p></div><span className="ops-selected-label">SELECTED</span></div><ModelMetrics values={model.metrics}/><p className="ops-note">Selected by the recorded modeling pipeline. {model.provenance}.</p></> : <p className="ops-empty">No model selected.</p>}
  </OperationsPanel>;
}
export function ModelComparison({ summary }: { summary: AgentsSummary }) {
  return <OperationsPanel title="Model Comparison" icon={Table2} className="ops-models" meta={<span className="ops-muted">{summary.models.length} supplied models · contract order</span>}>
    <div className="ops-model-cards">{summary.models.map(model => <article className="ops-model-card" key={model.model} data-selected={model.selected} data-unavailable={model.status === "UNAVAILABLE"}>
      <div className="ops-model-card-heading"><BrainCircuit size={18} aria-hidden="true"/><h3>{formatModelName(model.model)}</h3>{model.selected && <CheckCircle2 size={16} aria-label="Selected model"/>}</div><p className="ops-implementation">{model.implementation || "Implementation unavailable"}</p>
      <div className="ops-model-badges"><Badge variant={model.variant}>{model.status}</Badge>{model.selected && <Badge variant="success">SELECTED</Badge>}</div><ModelMetrics values={model.metrics}/><p className="ops-note">{model.provenance}</p>
    </article>)}</div>
    <details className="ops-exact-metrics"><summary>Exact model comparison table</summary><div className="ops-table-scroll" role="region" aria-label="Model metrics comparison" tabIndex={0}><table className="ops-model-table"><caption className="sr-only">Supplied model metrics and backend selection, in contract order</caption><thead><tr>{["Model", "Implementation", "Status", "MAE", "RMSE", "R²", "Selection"].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{summary.models.map(model => <tr key={model.model} data-selected={model.selected}><th scope="row">{formatModelName(model.model)}</th><td>{model.implementation || "Unavailable"}</td><td>{model.status}</td>{model.metrics.map((value, index) => <td key={index}>{value}</td>)}<td>{model.selected ? "Selected" : "—"}</td></tr>)}</tbody></table></div></details>
    {summary.models.length === 0 && <p className="ops-empty">No model comparison entries supplied.</p>}
    <p className="ops-note ops-metric-help">MAE: mean absolute error · RMSE: root mean squared error · R²: coefficient of determination, not accuracy. Selection is supplied by the backend; no frontend ranking is applied.</p>
  </OperationsPanel>;
}
