import { Target } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { formatModelName } from "@/lib/formatters";
import type { DashboardSummary } from "@/lib/dashboard";
import type { FrontendData } from "@/types/solar";

export function OptimizationContext({ data, summary }: { data: FrontendData; summary: DashboardSummary }) {
  const rows = [
    ["Control target", data.metadata.control_target_id],
    ["Prediction horizon", `${data.metadata.prediction_horizon_minutes} min`],
    ["Energy scope", data.metadata.energy_scope],
    ["Selected model", formatModelName(summary.selectedModel?.model ?? null)],
    ["Implementation", summary.selectedModel?.implementation || "Unavailable"],
    ["Dataset kind", data.metadata.dataset_kind],
    ["Data source", data.data_agent.source],
    ["Data status", data.data_agent.status],
  ];
  return <DashboardPanel title="Run Context" icon={Target} className="dashboard-context">
    <p className="eyebrow">Read-only run parameters</p>
    <dl className="context-values">{rows.map(([label,value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    <p className="context-footnote">Energy applies to the control row. The recommendation includes movement cost.</p>
  </DashboardPanel>;
}
