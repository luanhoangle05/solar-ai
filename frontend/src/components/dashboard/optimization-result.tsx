import type { CSSProperties } from "react";
import { CheckCircle2, ShieldX, Trophy } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { actionPresentation } from "@/config/actions";
import { formatAngle, formatKwh, formatKwhEquivalent, formatMovementCost, formatSignedKwh } from "@/lib/formatters";
import type { DashboardSummary } from "@/lib/dashboard";
import type { FrontendData } from "@/types/solar";

export function OptimizationResult({ data, summary }: { data: FrontendData; summary: DashboardSummary }) {
  const presentation = actionPresentation[data.decision.action];
  const Icon = presentation.icon;
  const SafetyIcon = data.safety.passed ? CheckCircle2 : ShieldX;
  const rows = [
    ["Current angle", formatAngle(summary.currentAngleDeg)],
    ["Recommended angle", formatAngle(summary.recommendedAngleDeg)],
    ["Baseline energy", formatKwh(summary.optimization?.baseline_kwh ?? null)],
    ["Predicted energy", formatKwh(summary.predictedKwh)],
    ["Energy gain", formatSignedKwh(summary.energyGainKwh)],
    ["Movement cost", summary.optimization ? formatMovementCost(summary.optimization.movement_cost_kwh_equivalent) : "Unavailable"],
    ["Net benefit", formatKwhEquivalent(summary.netBenefitKwhEquivalent)],
  ];
  return <DashboardPanel title="Optimization Result" icon={Trophy} className="dashboard-result">
    <div className="result-safety" data-passed={data.safety.passed}><SafetyIcon size={20} aria-hidden="true" />Safety {data.safety.passed ? "PASSED" : "BLOCKED"}</div>
    <dl className="result-values" data-positive-net={(summary.netBenefitKwhEquivalent ?? 0) > 0}>{rows.map(([label,value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    <div className="manager-result" style={{ "--action-color": presentation.color } as CSSProperties}><p className="eyebrow">Manager Decision · proposed</p><div><strong><Icon size={23} aria-hidden="true" />{data.decision.action}</strong><span>→ {formatAngle(data.decision.target_angle_deg)}</span></div></div>
    <p className="decision-reason">{data.decision.reason}</p>
    <p className="dashboard-note">Read-only recommendation · execution not confirmed.</p>
  </DashboardPanel>;
}
