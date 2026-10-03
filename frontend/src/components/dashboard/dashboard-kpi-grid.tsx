import { Activity, Gauge, MoveDiagonal2, TrendingUp, Zap } from "lucide-react";
import { MetricCard } from "@/components/shared/metric-card";
import { actionPresentation } from "@/config/actions";
import type { DashboardSummary } from "@/lib/dashboard";
import { formatAngle, formatKwh, formatKwhEquivalent, formatSignedKwh } from "@/lib/formatters";
import type { Metadata } from "@/types/solar";

export function DashboardKpiGrid({ summary, metadata }: { summary: DashboardSummary; metadata: Metadata }) {
  return (
    <section className="dashboard-kpis" aria-label="Run key metrics">
      <MetricCard label="Current angle" value={formatAngle(summary.currentAngleDeg)} detail={metadata.control_target_id + " · observed"} icon={Gauge} />
      <MetricCard label="Recommended angle" value={formatAngle(summary.recommendedAngleDeg)} detail="Optimization candidate" icon={MoveDiagonal2} />
      <MetricCard label="Predicted energy" value={formatKwh(summary.predictedKwh)} detail={metadata.prediction_horizon_minutes + " min / " + metadata.energy_scope} icon={Zap} />
      <MetricCard label="Energy gain" value={formatSignedKwh(summary.energyGainKwh)} detail="Compared with baseline" icon={TrendingUp} />
      <MetricCard label="Net benefit" value={formatKwhEquivalent(summary.netBenefitKwhEquivalent)} detail="After movement cost" icon={Activity} />
      <MetricCard label="Manager decision" value={summary.decisionAction} detail={"Target " + formatAngle(summary.decisionTargetAngleDeg)} icon={actionPresentation[summary.decisionAction].icon} />
    </section>
  );
}
