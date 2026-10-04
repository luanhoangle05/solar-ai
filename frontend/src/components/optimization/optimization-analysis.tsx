import { ArrowRight, GitCompareArrows, Lightbulb, Scale } from "lucide-react";
import { formatAngle, formatCandidateEnergy, formatKwh, formatKwhEquivalent, formatMovementCost, formatSignedKwh } from "@/lib/formatters";
import type { OptimizationSummary } from "@/lib/optimization";
import { OptimizationPanel } from "./optimization-panel";

export function OptimizationInsight({ summary }: { summary: OptimizationSummary }) {
  const result = summary.optimization;
  return <OptimizationPanel title="Why this recommendation" icon={Lightbulb} className="opt-insight">
    <div className="opt-insight-comparison"><div><span>Recommended operating angle</span><strong>{formatAngle(summary.recommendedAngle)}</strong><small>{formatCandidateEnergy(result?.predicted_kwh ?? null)}</small></div><ArrowRight size={22} aria-hidden="true"/><div><span>Highest raw prediction{summary.rawMaxima.length > 1 ? "s (tied)" : ""}</span><strong>{summary.rawMaxima.length ? summary.rawMaxima.map(point => formatAngle(point.angle_deg)).join(" / ") : "Unavailable"}</strong><small>{formatCandidateEnergy(summary.rawMaxima[0]?.predicted_kwh ?? null)}</small></div></div>
    <p className="opt-insight-text">{summary.insight}</p>
    {!summary.recommendationIsRawMax && summary.rawMaxima.length > 0 && <p className="opt-why-not"><strong>Why not {summary.rawMaxima.map(point => formatAngle(point.angle_deg)).join(" / ")}?</strong> The highest raw prediction is shown for comparison. The recorded recommendation also accounts for the supplied movement cost and overall net benefit.</p>}
    <p className="opt-note">Candidate-level costs are not provided, so the chart and table compare energy predictions only.</p>
  </OptimizationPanel>;
}

export function CurrentVsRecommended({ summary }: { summary: OptimizationSummary }) {
  const comparison = summary.comparison;
  const change = comparison ? comparison.recommendedAngle - comparison.currentAngle : null;
  return <OptimizationPanel title="Current vs Recommended" icon={GitCompareArrows} className="opt-comparison">
    {comparison ? <table className="opt-table"><caption className="sr-only">Current and recommended operating configuration</caption><thead><tr><th scope="col">Parameter</th><th scope="col">Current</th><th scope="col">Recommended</th></tr></thead><tbody><tr><th scope="row">Angle</th><td>{formatAngle(comparison.currentAngle)}</td><td>{formatAngle(comparison.recommendedAngle)}</td></tr><tr><th scope="row">Energy</th><td>{formatKwh(comparison.baseline)}</td><td>{formatKwh(comparison.predicted)}</td></tr><tr><th scope="row">Change</th><td>—</td><td>{change === null ? "Unavailable" : `${change > 0 ? "+" : ""}${change}°`}</td></tr><tr><th scope="row">Action</th><td>—</td><td>{summary.decision.action}</td></tr></tbody></table> : <p className="opt-empty">No optimization comparison available.</p>}
  </OptimizationPanel>;
}

export function NetBenefitBreakdown({ summary }: { summary: OptimizationSummary }) {
  const result = summary.optimization;
  // Bar lengths only visualize supplied values; they do not reconstruct optimizer economics.
  const maximum = result ? Math.max(Math.abs(result.energy_gain_kwh), result.movement_cost_kwh_equivalent, Math.abs(result.net_benefit_kwh_equivalent)) : 0;
  const bars = result ? [
    { label:"Energy gain", value:result.energy_gain_kwh, text:formatSignedKwh(result.energy_gain_kwh), tone:"gain" },
    { label:"Movement cost (deduction)", value:result.movement_cost_kwh_equivalent, text:formatMovementCost(result.movement_cost_kwh_equivalent), tone:"cost" },
    { label:"Net benefit", value:result.net_benefit_kwh_equivalent, text:formatKwhEquivalent(result.net_benefit_kwh_equivalent), tone:"net" },
  ] : [];
  return <OptimizationPanel title="Net Benefit Breakdown" icon={Scale} className="opt-breakdown">
    {result ? <><p className="opt-note">Baseline {formatKwh(result.baseline_kwh)} → predicted {formatKwh(result.predicted_kwh)}</p><div className="opt-benefit-bars">{bars.map(bar => <div key={bar.label} data-tone={bar.value < 0 ? "negative" : bar.tone}><div><span>{bar.label}</span><strong>{bar.text}</strong></div><div className="opt-bar-track" aria-hidden="true"><span style={{width:(maximum ? Math.abs(bar.value)/maximum*100 : 0)+"%"}}/></div></div>)}</div><p className="opt-note">Cost and net benefit use kWh-equivalent. Cost is not a currency value or a measurement of electricity consumed.</p></> : <p className="opt-empty">No optimization economics available.</p>}
  </OptimizationPanel>;
}
