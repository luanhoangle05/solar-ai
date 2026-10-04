import { CandidateEnergyProfile } from "@/components/optimization/candidate-energy-profile";
import { getOptimizationSummary } from "@/lib/optimization";
import { getCandidateInsight, type DashboardSummary } from "@/lib/dashboard";
import { formatAngle, formatKwh } from "@/lib/formatters";
import type { FrontendData } from "@/types/solar";
export function CandidateEnergyPanel({ data, summary }: { data: FrontendData; summary: DashboardSummary }) {
  const view = getOptimizationSummary(data);
  return <section className="dashboard-candidates" aria-label="Candidate energy analysis">
    <CandidateEnergyProfile candidates={view.candidates} current={view.currentAngle} recommended={view.recommendedAngle} rawAngles={view.rawMaxima.map(item => item.angle_deg)} horizon={data.metadata.prediction_horizon_minutes} scope={data.metadata.energy_scope}/>
    <p className="candidate-insight">{getCandidateInsight(data)}</p>
    {summary.candidates.length > 0 && <details className="candidate-data"><summary>Candidate Table · exact values ({summary.candidates.length})</summary><table><caption className="sr-only">Candidate tilt angles and raw predicted energy</caption><thead><tr><th scope="col">Angle</th><th scope="col">Energy</th><th scope="col">Reference</th></tr></thead><tbody>{view.candidates.map(candidate => <tr key={candidate.angle_deg}><th scope="row">{formatAngle(candidate.angle_deg)}</th><td>{formatKwh(candidate.predicted_kwh, 3)}</td><td>{candidate.roles.join(" · ") || "Candidate"}</td></tr>)}</tbody></table></details>}
  </section>;
}
