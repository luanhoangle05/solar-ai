import { Activity, AlertTriangle, CheckCircle2 } from "lucide-react";
import { formatAgentName, type AgentsSummary } from "@/lib/agents";
import { formatDisplayName, formatRecordedTime } from "@/lib/formatters";
import type { FrontendData } from "@/types/solar";
import { OperationsPanel } from "./operations-panel";
export function AgentActivity({ summary }: { summary: AgentsSummary }) {
  return <OperationsPanel title="Agent Activity" icon={Activity} className="ops-activity" meta={<span className="ops-muted">{summary.events.length} recorded events · UTC</span>}>
    {summary.events.length ? <ol className="ops-timeline">{summary.events.map((event, i) => <li key={event.timestamp + i} data-agent={event.agent}><div><h3>{formatAgentName(event.agent)} <span>{formatDisplayName(event.action)}</span></h3><time dateTime={event.timestamp}>{formatRecordedTime(event.timestamp)}</time></div><p>{event.result}</p></li>)}</ol> : <p className="ops-empty">No recorded agent activity for this payload.</p>}
  </OperationsPanel>;
}
export function RunProvenance({ data, summary }: { data: FrontendData; summary: AgentsSummary }) {
  return <><section className="ops-issues" aria-label="System issues" data-errors={summary.errors.length > 0}>
    {summary.errors.length ? <><h2><AlertTriangle size={17} aria-hidden="true"/>System Issues</h2><ul>{summary.errors.map((error, i) => <li key={i}><strong>{formatAgentName(error.agent)} · {error.code}</strong><p>{error.message}</p></li>)}</ul></> : <p><CheckCircle2 size={16} aria-hidden="true"/>No recorded pipeline errors</p>}
    </section><footer className="ops-provenance"><h2>Run Provenance</h2><dl>
      <div><dt>{data.metadata.dataset_kind === "MOCK" ? "Fixture run" : "Recorded run"}</dt><dd><time dateTime={data.timestamp}>{formatRecordedTime(data.timestamp)}</time></dd></div>
      <div><dt>Dataset / labels</dt><dd>{data.metadata.dataset_kind} / {data.metadata.label_source}</dd></div><div><dt>Schema</dt><dd>{data.metadata.schema_version}</dd></div>
      <div><dt>Scope / horizon</dt><dd>{data.metadata.energy_scope} / {data.metadata.prediction_horizon_minutes} min</dd></div><div><dt>Control target</dt><dd>{data.metadata.control_target_id}</dd></div><div><dt>Configuration</dt><dd>{data.metadata.config_id}</dd></div>
    </dl></footer></>;
}
