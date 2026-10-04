import { BrainCircuit, CheckCircle2, Network, ShieldCheck, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { formatDisplayName, formatMetric, formatModelName, formatRecordedTime } from "@/lib/formatters";
import type { OptimizationSummary } from "@/lib/optimization";
import { OptimizationPanel } from "./optimization-panel";

export function SafetyValidation({ summary }: { summary: OptimizationSummary }) {
  const safety = summary.safety;
  return <OptimizationPanel title="Operating Conditions & Safety" icon={ShieldCheck} className="opt-safety" meta={<Badge variant={safety.passed ? "success" : "danger"}>{safety.passed ? "PASSED" : "BLOCKED"}</Badge>}>
    {safety.checks.length ? <ul className="opt-safety-list">{safety.checks.map((check,index) => { const Icon = check.passed ? CheckCircle2 : XCircle; return <li key={check.name+index} data-state={check.passed ? "passed" : check.severity === "SEVERE" ? "severe" : "failed"}><details open={!check.passed}><summary><Icon size={14} aria-hidden="true"/><span>{formatDisplayName(check.name)}</span><strong>{check.passed ? "Passed" : "Failed"}</strong></summary><p>{formatDisplayName(check.severity)} · {check.reason}</p></details></li>; })}</ul> : <p className="opt-empty">Operating-condition status unavailable.</p>}
    <p className="opt-note">{safety.passed ? "All recorded operating checks passed." : safety.reason}</p>
  </OptimizationPanel>;
}

export function PredictionModel({ summary }: { summary: OptimizationSummary }) {
  const model = summary.model;
  return <OptimizationPanel title="Prediction Model" icon={BrainCircuit} className="opt-model" meta={model && <Badge variant={model.status === "MOCK" ? "warning" : model.status === "VALIDATED" ? "success" : "secondary"}>{model.status}</Badge>}>
    {model ? <><div className="opt-model-name"><strong>{formatModelName(model.model)}</strong></div><dl className="opt-model-metrics"><div><dt><abbr title="Mean absolute error">MAE</abbr></dt><dd>{formatMetric(model.mae)}</dd></div><div><dt><abbr title="Root mean square error">RMSE</abbr></dt><dd>{formatMetric(model.rmse)}</dd></div><div><dt><abbr title="Coefficient of determination">R²</abbr></dt><dd>{formatMetric(model.r2)}</dd></div></dl><p className="opt-note">{model.status === "MOCK" ? "Example metrics for this recorded demonstration." : "Metrics and model status supplied with this result."}</p></> : <p className="opt-empty">Prediction model unavailable.</p>}
  </OptimizationPanel>;
}

export function OptimizationAgentHandoff({ summary }: { summary: OptimizationSummary }) {
  return <OptimizationPanel title="Optimization → Manager" icon={Network} className="opt-handoff">
    {summary.events.length ? <ol className="opt-handoff-events">{summary.events.map((event,index) => <li key={event.timestamp+index}><h3>{formatDisplayName(event.agent)} Agent <span>{formatDisplayName(event.action)}</span></h3><p>{event.result}</p><time dateTime={event.timestamp}>{formatRecordedTime(event.timestamp,false)}</time></li>)}</ol> : <p className="opt-empty">No optimization or manager events recorded.</p>}
  </OptimizationPanel>;
}
