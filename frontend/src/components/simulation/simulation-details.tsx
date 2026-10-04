"use client";
import { useId, useState, type ReactNode } from "react";
import { ChevronDown, Check, TriangleAlert } from "lucide-react";
import { RowTable } from "@/components/farm/row-table";
import { emptyRowFilters } from "@/lib/farm";
import { formatAgentName, getAgentEvents } from "@/lib/agents";
import { formatAngle, formatCandidateEnergy, formatDisplayName } from "@/lib/formatters";
import type { FrontendData } from "@/types/solar";

export function SimulationDisclosure({ title, summary, children, defaultOpen = false }: { title: string; summary: string; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return <section className="sim-disclosure"><h2><button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(value => !value)}><ChevronDown size={17} aria-hidden="true"/><span>{title}</span><small>{summary}</small></button></h2><div id={id} hidden={!open}>{open && <div className="sim-disclosure-body">{children}</div>}</div></section>;
}
const eventCopy: Record<string, string> = { weather_received: "Environmental data received", validation: "Environmental checks reviewed", comparison: "Energy estimates compared", selection: "Prediction method selected", candidate_comparison: "Operating angles evaluated", recommendation: "Angle recommendation available", safety: "Operating conditions reviewed", llm_reasoning: "Analysis explanation available", llm_reasoning_unavailable: "Analysis explanation unavailable" };
export function SimulationDetails({ data, selectedRow, onRow }: { data: FrontendData; selectedRow: string | null; onRow: (id: string) => void }) {
  const [filters, setFilters] = useState({ ...emptyRowFilters });
  const events = getAgentEvents(data);
  return <div className="sim-details">
    <SimulationDisclosure title="Row Explorer" summary={`${data.farm_status.rows.length} rows`}><RowTable compact farm={data.farm_status} targetId={data.metadata.control_target_id} selectedRow={selectedRow} onRow={onRow} filters={filters} onFilters={setFilters}/></SimulationDisclosure>
    <SimulationDisclosure title="Agent Activity" summary={events.length ? `${events.length} events` : "AI activity unavailable."}>{events.length ? <ol className="sim-activity">{events.map((event, index) => <li key={`${event.agent}-${index}`}><span aria-hidden="true"/><div><strong>{formatAgentName(event.agent)}</strong><p>{eventCopy[event.action] ?? "Analysis activity available"}</p></div></li>)}</ol> : <p>AI activity unavailable.</p>}</SimulationDisclosure>
    <SimulationDisclosure title="Candidate Angles" summary={data.candidate_predictions.length ? `${data.candidate_predictions.length} options` : "No angles available"}>{data.candidate_predictions.length ? <><p className="sim-scope">Energy per {data.metadata.energy_scope} · next {data.metadata.prediction_horizon_minutes} min</p><table className="sim-candidates"><thead><tr><th scope="col">Angle</th><th scope="col">Predicted Energy</th></tr></thead><tbody>{data.candidate_predictions.map(candidate => <tr key={candidate.angle_deg}><th scope="row">{formatAngle(candidate.angle_deg)}</th><td>{formatCandidateEnergy(candidate.predicted_kwh)}</td></tr>)}</tbody></table></> : <p>No candidate angles available.</p>}</SimulationDisclosure>
    <SimulationDisclosure title="Safety Details" summary={data.safety.passed ? "Safe" : "Needs attention"} defaultOpen={!data.safety.passed}><ul className="sim-safety-list">{data.safety.checks.map(check => <li key={check.name} data-passed={check.passed}>{check.passed ? <Check size={17} aria-hidden="true"/> : <TriangleAlert size={17} aria-hidden="true"/>}<div><strong>{formatDisplayName(check.name)}</strong><p>{check.passed ? "Passed" : check.reason}</p></div></li>)}</ul></SimulationDisclosure>
  </div>;
}
