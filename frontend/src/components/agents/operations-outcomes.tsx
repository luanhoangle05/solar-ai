import type { CSSProperties } from "react";
import { CheckCircle2, Database, ShieldCheck, XCircle, Bot } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { actionPresentation } from "@/config/actions";
import { dataStatusVariants } from "@/config/status";
import { getSafetyCheckTone, type AgentsSummary } from "@/lib/agents";
import { formatAngle, formatDisplayName, formatKwhEquivalent } from "@/lib/formatters";
import type { FrontendData } from "@/types/solar";
import { OperationsPanel } from "./operations-panel";
export function DataQuality({ summary }: { summary: AgentsSummary }) {
  const report = summary.dataQuality;
  return <OperationsPanel title="Data Quality" icon={Database} className="ops-data" meta={<Badge variant={dataStatusVariants[report.status]}>{report.status}</Badge>}>
    <dl className="ops-facts"><div><dt>Source</dt><dd>{report.source}</dd></div><div><dt>Forecast age at run</dt><dd>{report.forecast_age_minutes === null ? "Unavailable" : `${report.forecast_age_minutes} min`}</dd></div><div><dt>Cache used</dt><dd>{report.used_cache ? "Yes" : "No"}</dd></div></dl>
    {report.issues.length ? <ul className="ops-data-issues">{report.issues.map((issue, i) => <li key={i}>{issue}</li>)}</ul> : <p className="ops-note">No reported data issues.</p>}
  </OperationsPanel>;
}
export function ManagerDecision({ data, summary }: { data: FrontendData; summary: AgentsSummary }) {
  const action = actionPresentation[summary.decision.action]; const Icon = action.icon;
  return <OperationsPanel title="Manager Decision" icon={Bot} className="ops-decision" meta={<Badge variant={summary.safety.passed ? "success" : "danger"}>Safety {summary.safety.passed ? "PASSED" : "BLOCKED"}</Badge>}>
    <p className="ops-eyebrow">Recorded decision · proposed action</p><div className="ops-action" style={{ "--action-color": action.color } as CSSProperties}><strong><Icon size={25} aria-hidden="true"/>{summary.decision.action}</strong><span>{summary.decisionAngle}</span></div><p className="ops-reason">{summary.decision.reason}</p>
    {data.optimization ? <div className="ops-recommendation"><span>Optimization recommendation <strong>{formatAngle(data.optimization.recommended_angle_deg)}</strong></span><span>Net benefit <strong>{formatKwhEquivalent(data.optimization.net_benefit_kwh_equivalent)}</strong></span></div> : <p className="ops-note">Optimization recommendation unavailable.</p>}
    <p className="ops-note">Target {data.metadata.control_target_id} · {data.candidate_predictions.length} supplied candidates · {data.metadata.energy_scope} / {data.metadata.prediction_horizon_minutes} min. Execution is not confirmed by this payload.</p>
  </OperationsPanel>;
}
export function AgentSafety({ summary, isMock }: { summary: AgentsSummary; isMock: boolean }) {
  const safety = summary.safety;
  return <OperationsPanel title="Safety Validation" icon={ShieldCheck} className="ops-safety" meta={<Badge variant={safety.passed ? "success" : "danger"}>{safety.passed ? "PASSED" : "BLOCKED"}</Badge>}>
    <p className="ops-note">{safety.reason}</p><ul className="ops-checks">{safety.checks.map((check, i) => { const Icon = check.passed ? CheckCircle2 : XCircle;
      return <li key={check.name + i} data-tone={getSafetyCheckTone(check)}><details open={!check.passed}><summary><Icon size={17} aria-hidden="true"/><span>{formatDisplayName(check.name)}</span><Badge variant={getSafetyCheckTone(check)}>{check.passed ? "PASS" : "FAIL"}</Badge><span className="ops-severity">{check.severity}</span></summary><p>{check.reason}</p></details></li>;
    })}</ul><p className="ops-note">{isMock ? "Illustrative fixture checks. " : "Supplied safety report. "}Overall status comes from the payload; this view cannot override safety.</p>
  </OperationsPanel>;
}
