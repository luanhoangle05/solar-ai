import { SlidersHorizontal } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { dataStatusVariants } from "@/config/status";
import { formatAngle, formatModelName } from "@/lib/formatters";
import type { FrontendData } from "@/types/solar";
import type { OptimizationSummary } from "@/lib/optimization";
import { OptimizationPanel } from "./optimization-panel";

export function OptimizationContext({ data, summary }: { data: FrontendData; summary: OptimizationSummary }) {
  const rows = [
    ["Control target", data.metadata.control_target_id],
    ["Current angle", formatAngle(summary.currentAngle)],
    ["Recommended angle", formatAngle(summary.recommendedAngle)],
    ["Prediction horizon", data.metadata.prediction_horizon_minutes + " min"],
    ["Energy scope", data.metadata.energy_scope + (summary.target ? " · " + summary.target.panel_count + " panels" : "")],
    ["Candidate angles", summary.candidates.length],
    ["Selected model", formatModelName(summary.model?.model ?? null)],
    ["Implementation", summary.model?.implementation || "Unavailable"],
    ["Data source", data.data_agent.source],
  ];
  return <OptimizationPanel title="Optimization Context" icon={SlidersHorizontal} className="opt-context">
    <p className="opt-eyebrow">Loaded run · read-only</p>
    <dl className="opt-facts">{rows.map(([label,value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    <div className="opt-data-health"><span>Data health</span><Badge variant={dataStatusVariants[data.data_agent.status]}>{data.data_agent.status}</Badge></div>
    <p className="opt-note">Age at recorded run: {data.data_agent.forecast_age_minutes === null ? "Unknown" : data.data_agent.forecast_age_minutes + " min"} · Cache {data.data_agent.used_cache ? "used" : "not used"}</p>
    {data.data_agent.issues.length > 0 && <ul className="opt-issues" data-status={data.data_agent.status}>{data.data_agent.issues.map((issue,i) => <li key={i}>{issue}</li>)}</ul>}
  </OptimizationPanel>;
}
