import { Target } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { formatAngle, formatKwh, formatKwhEquivalent, formatModelName, formatMovementCost } from "@/lib/formatters";
import type { DashboardSummary } from "@/lib/dashboard";
import type { FrontendData } from "@/types/solar";

export function OptimizationContext({ data, summary }: { data: FrontendData; summary: DashboardSummary }) {
  const rows = [
    ["Prediction horizon", data.metadata.prediction_horizon_minutes + " min / " + data.metadata.energy_scope],
    ["Baseline energy", formatKwh(summary.optimization?.baseline_kwh ?? null)],
    ["Predicted energy", formatKwh(summary.predictedKwh)],
    ["Movement cost", summary.optimization ? formatMovementCost(summary.optimization.movement_cost_kwh_equivalent) : "Unavailable"],
    ["Net benefit", formatKwhEquivalent(summary.netBenefitKwhEquivalent)],
    ["Selected model", formatModelName(data.selected_model)],
    ["Candidates", summary.candidates.length],
    ["Control target", data.metadata.control_target_id],
    ["Data status", data.data_agent.status],
  ];
  return <DashboardPanel title="Optimization Context" icon={Target} className="dashboard-context">
    <p className="eyebrow">Read-only run parameters</p>
    <div className="angle-comparison"><div><span>Current angle</span><strong>{formatAngle(summary.currentAngleDeg)}</strong></div><span aria-hidden="true">→</span><div><span>Recommended</span><strong>{formatAngle(summary.recommendedAngleDeg)}</strong></div></div>
    <dl className="context-values">{rows.map(([label,value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    <p className="context-footnote">Energy applies to the control row. The recommendation includes movement cost.</p>
  </DashboardPanel>;
}
