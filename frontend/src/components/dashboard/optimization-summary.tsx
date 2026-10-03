import { Scale } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { formatAngle, formatKwh, formatKwhEquivalent, formatMovementCost, formatSignedKwh } from "@/lib/formatters";
import type { OptimizationResult } from "@/types/solar";

export function OptimizationSummary({ optimization }: { optimization: OptimizationResult | null }) {
  return (
    <DashboardPanel title="Optimization Summary" icon={Scale} className="dashboard-optimization">
      {optimization ? <>
        <dl className="optimization-values">
          <div><dt>Current → recommended</dt><dd>{formatAngle(optimization.current_angle_deg)} → {formatAngle(optimization.recommended_angle_deg)}</dd></div>
          <div><dt>Baseline → predicted</dt><dd>{formatKwh(optimization.baseline_kwh)} → {formatKwh(optimization.predicted_kwh)}</dd></div>
          <div><dt>Energy gain</dt><dd>{formatSignedKwh(optimization.energy_gain_kwh)}</dd></div>
          <div><dt>Movement cost</dt><dd>{formatMovementCost(optimization.movement_cost_kwh_equivalent)}</dd></div>
          <div className="net-benefit"><dt>Net benefit</dt><dd>{formatKwhEquivalent(optimization.net_benefit_kwh_equivalent)}</dd></div>
        </dl>
        <p className="dashboard-note">Net value includes movement cost, not raw energy alone.</p>
      </> : <p className="dashboard-empty">Optimization unavailable.</p>}
    </DashboardPanel>
  );
}
