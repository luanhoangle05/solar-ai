import type { CSSProperties } from "react";
import { CheckCircle2, ShieldX, Trophy } from "lucide-react";
import { actionPresentation } from "@/config/actions";
import { formatAngle, formatKwh, formatKwhEquivalent, formatMovementCost, formatSignedKwh } from "@/lib/formatters";
import type { OptimizationSummary } from "@/lib/optimization";
import { OptimizationPanel } from "./optimization-panel";

export function OptimizationResult({ summary }: { summary: OptimizationSummary }) {
  const { optimization: result, decision, safety } = summary;
  const action = actionPresentation[decision.action];
  const ActionIcon = action.icon;
  const SafetyIcon = safety.passed ? CheckCircle2 : ShieldX;
  return <OptimizationPanel title="Optimization Result" icon={Trophy} className="opt-result">
    <div className="opt-safety-state" data-passed={safety.passed}><SafetyIcon size={20} aria-hidden="true"/>Safety {safety.passed ? "PASSED" : "BLOCKED"}</div>
    <div className="opt-manager" style={{ "--action-color": action.color } as CSSProperties}>
      <p className="opt-eyebrow">Manager decision · proposed action</p>
      <div><strong><ActionIcon aria-hidden="true" size={28}/>{decision.action}</strong><span>{formatAngle(summary.currentAngle ?? summary.target?.angle_deg ?? null)} → {formatAngle(decision.target_angle_deg)}</span></div>
    </div>
    {result ? <><p className="opt-recommendation-line">Current {formatAngle(result.current_angle_deg)} · Recommended {formatAngle(result.recommended_angle_deg)}</p>
      <div className="opt-result-metrics"><div><span>Baseline energy</span><strong>{formatKwh(result.baseline_kwh)}</strong></div><div><span>Predicted energy</span><strong>{formatKwh(result.predicted_kwh)}</strong></div><div><span>Energy gain</span><strong>{formatSignedKwh(result.energy_gain_kwh)}</strong></div><div><span>Movement cost</span><strong>{formatMovementCost(result.movement_cost_kwh_equivalent)}</strong></div></div>
      <div className="opt-net-callout" data-positive={result.net_benefit_kwh_equivalent > 0}><span>Net benefit</span><strong>{formatKwhEquivalent(result.net_benefit_kwh_equivalent)}</strong></div>
    </> : <p className="opt-empty">Optimization unavailable. No optimization result exists in this payload.</p>}
    <p className="opt-decision-reason">{decision.reason}</p>
    <p className="opt-note">Execution not confirmed. This view cannot command hardware.</p>
  </OptimizationPanel>;
}
