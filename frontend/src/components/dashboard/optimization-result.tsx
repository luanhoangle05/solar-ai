import type { CSSProperties } from "react";
import Link from "next/link";
import { CheckCircle2, ShieldX, Trophy } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { actionPresentation } from "@/config/actions";
import { formatAngle, formatKwh, formatKwhEquivalent, formatModelName, formatMovementCost, formatSignedKwh } from "@/lib/formatters";
import { getDecisionAngleLabel } from "@/lib/agents";
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
    ["Selected model", formatModelName(summary.selectedModel?.model ?? null)],
  ];
  return <DashboardPanel title="Optimization Result" icon={Trophy} className="dashboard-result">
    <div className="manager-result" data-safe={data.safety.passed} style={{ "--action-color": data.safety.passed ? presentation.color : "var(--danger)" } as CSSProperties}><p className="eyebrow">Backend recommendation · Manager Decision</p><div><strong><Icon size={23} aria-hidden="true" />{data.decision.action}</strong><span>{getDecisionAngleLabel(data)}</span></div></div>
    <div className="result-safety" data-passed={data.safety.passed}><SafetyIcon size={20} aria-hidden="true" />Safety {data.safety.passed ? "PASSED" : "BLOCKED"}</div>
    {!summary.optimization && <p className="dashboard-unavailable">Optimization unavailable.</p>}
    <p className="result-scope">Energy scope: {data.metadata.energy_scope} / {data.metadata.prediction_horizon_minutes} min</p>
    <dl className="result-values">{rows.map(([label,value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    <div className="result-net" data-positive={data.safety.passed && (summary.netBenefitKwhEquivalent ?? 0) > 0}><span>Net benefit <small>After movement-cost equivalent</small></span><strong>{formatKwhEquivalent(summary.netBenefitKwhEquivalent)}</strong></div>
    <details className="decision-rationale"><summary>Recorded decision rationale</summary><p className="decision-reason">{data.decision.reason}</p></details>
    <Link href="/optimization" className="result-navigation">View Optimization Details <span aria-hidden="true">↗</span></Link>
    <p className="dashboard-note execution-note">Proposed action · execution not confirmed.</p>
  </DashboardPanel>;
}
