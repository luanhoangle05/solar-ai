import { Gauge, Target, TrendingUp, Zap } from "lucide-react";
import type { DashboardSummary } from "@/lib/dashboard";
import { formatAngle } from "@/lib/formatters";
import type { Metadata } from "@/types/solar";

export function DashboardKpiGrid({ summary, metadata }: { summary: DashboardSummary; metadata: Metadata }) {
  const metrics = [
    { label: "Current angle", value: formatAngle(summary.currentAngleDeg), unit: "", detail: metadata.control_target_id + " · observed", icon: Gauge },
    { label: "Recommended angle", value: formatAngle(summary.recommendedAngleDeg), unit: "", detail: "Backend recommendation", icon: Target },
    { label: "Predicted energy", value: summary.predictedKwh?.toFixed(2) ?? "Unavailable", unit: summary.predictedKwh === null ? "" : "kWh", detail: metadata.prediction_horizon_minutes + " min / " + metadata.energy_scope, icon: Zap },
    { label: "Net benefit", value: summary.netBenefitKwhEquivalent === null ? "Unavailable" : (summary.netBenefitKwhEquivalent > 0 ? "+" : "") + summary.netBenefitKwhEquivalent.toFixed(2), unit: summary.netBenefitKwhEquivalent === null ? "" : "kWh eq.", detail: "After movement cost", icon: TrendingUp },
  ];
  return <section className="dashboard-kpis" aria-label="Run key metrics">{metrics.map(({ label, value, unit, detail, icon: Icon }) =>
    <div className="dashboard-kpi" data-unavailable={value === "Unavailable"} key={label}><Icon aria-hidden="true" /><div><h2>{label}</h2><p className="kpi-value">{value} <small>{unit}</small></p><p className="dashboard-note">{detail}</p></div></div>
  )}</section>;
}
