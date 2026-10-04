import type { CSSProperties } from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle2, ShieldX, Trophy } from "lucide-react";
import { actionPresentation } from "@/config/actions";
import { formatAngle, formatKwhEquivalent, formatMovementCost, formatSignedKwh } from "@/lib/formatters";
import type { OptimizationSummary } from "@/lib/optimization";
import { OptimizationPanel } from "./optimization-panel";

export function OptimizationResult({ summary }: { summary: OptimizationSummary }) {
  const { optimization: result, decision, safety } = summary;
  const action = actionPresentation[decision.action];
  const ActionIcon = action.icon;
  const SafetyIcon = safety.passed ? CheckCircle2 : ShieldX;
  const current = summary.currentAngle ?? summary.target?.angle_deg ?? null;
  const decisionLabel = decision.action === "HOLD" ? "Keep current angle" : decision.action === "STOW" ? "Stow panels" : null;
  return <OptimizationPanel title="Recommendation" icon={Trophy} className="opt-result">
    <div className="opt-manager" style={{ "--action-color": action.color } as CSSProperties}>
      <p className="opt-eyebrow">Operating decision</p>
      <div><strong><ActionIcon aria-hidden="true" size={28}/>{decisionLabel ?? decision.action}</strong>{decisionLabel ? <span>{formatAngle(decision.target_angle_deg)}</span> : <span><b>{formatAngle(current)}</b><ArrowRight size={23} aria-hidden="true"/><b>{formatAngle(decision.target_angle_deg)}</b></span>}</div>
    </div>
    {result ? <div className="opt-result-metrics"><div><span>Expected Gain</span><strong>{decision.action === "STOW" ? "—" : formatSignedKwh(result.energy_gain_kwh)}</strong></div><div><span>Movement Cost</span><strong>{decision.action === "STOW" ? "—" : formatMovementCost(result.movement_cost_kwh_equivalent)}</strong></div><div data-positive={result.net_benefit_kwh_equivalent > 0}><span>Net Benefit</span><strong>{decision.action === "STOW" ? "—" : formatKwhEquivalent(result.net_benefit_kwh_equivalent)}</strong></div></div> : <p className="opt-empty">No optimization recommendation available.</p>}
    <div className="opt-result-footer"><div><span>Target</span><strong>{summary.target?.row_id ?? "Unavailable"}</strong></div><div className="opt-safety-state" data-passed={safety.passed}><SafetyIcon size={18} aria-hidden="true"/>{safety.passed ? "Safe to proceed" : "Operating action blocked"}</div><Link href="/simulation">View in Simulation <ArrowRight size={14} aria-hidden="true"/></Link></div>
  </OptimizationPanel>;
}
