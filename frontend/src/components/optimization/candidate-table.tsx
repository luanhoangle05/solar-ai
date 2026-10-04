import { Table2 } from "lucide-react";
import { formatAngle, formatCandidateEnergy } from "@/lib/formatters";
import type { DisplayCandidate } from "@/lib/optimization";
import { OptimizationPanel } from "./optimization-panel";

export function CandidateTable({ candidates }: { candidates: DisplayCandidate[] }) {
  return <OptimizationPanel title="Candidate Table" icon={Table2} className="opt-candidate-table" meta={<span className="opt-note">{candidates.length} loaded candidates</span>}>
    {candidates.length ? <table className="opt-table"><caption className="sr-only">Candidate raw energy predictions in angle order. No per-candidate economics are available.</caption><thead><tr><th scope="col">Angle</th><th scope="col">Predicted energy</th><th scope="col">Role</th></tr></thead><tbody>{candidates.map(point => <tr key={point.angle_deg} data-recommended={point.roles.includes("Recommended")}><th scope="row">{formatAngle(point.angle_deg)}</th><td>{formatCandidateEnergy(point.predicted_kwh)}</td><td><div className="opt-role-list">{point.roles.length ? point.roles.map(role => <span key={role} data-role={role}>{role}</span>) : <span>Candidate</span>}</div></td></tr>)}</tbody></table> : <p className="opt-empty">No candidate predictions available.</p>}
  </OptimizationPanel>;
}
