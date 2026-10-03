import { ChartNoAxesCombined } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { CandidateEnergyChart } from "./candidate-energy-chart";
import { getCandidateInsight, type DashboardSummary } from "@/lib/dashboard";
import { formatAngle, formatKwh } from "@/lib/formatters";
import type { FrontendData } from "@/types/solar";

export function CandidateEnergyPanel({ data, summary }: { data: FrontendData; summary: DashboardSummary }) {
  return (
    <DashboardPanel title="Candidate Energy Profile" icon={ChartNoAxesCombined} className="dashboard-candidates" action={<span className="dashboard-note">{data.metadata.prediction_horizon_minutes} min / {data.metadata.energy_scope}</span>}>
      {summary.candidates.length ? <>
        <div className="chart-legend"><span>○ Current {formatAngle(summary.currentAngleDeg)}</span><span className="text-success">● Recommended {formatAngle(summary.recommendedAngleDeg)}</span></div>
        <p className="dashboard-note">Y: predicted energy (kWh) · X: panel tilt (degrees)</p>
        <CandidateEnergyChart candidates={summary.candidates} currentAngle={summary.currentAngleDeg} recommendedAngle={summary.recommendedAngleDeg} />
        <p className="candidate-insight">{getCandidateInsight(data)}</p>
        <p className="dashboard-note mt-2">Raw predicted energy by candidate angle. Recommendation uses backend net-benefit logic.</p>
        <details className="candidate-data">
          <summary>View candidate data ({summary.candidates.length})</summary>
          <table>
            <caption className="sr-only">Candidate tilt angles and raw predicted energy</caption>
            <thead><tr><th scope="col">Angle</th><th scope="col">Energy</th><th scope="col">Reference</th></tr></thead>
            <tbody>{summary.candidates.map(candidate => (
              <tr key={candidate.angle_deg}>
                <th scope="row">{formatAngle(candidate.angle_deg)}</th>
                <td>{formatKwh(candidate.predicted_kwh, 3)}</td>
                <td>{[candidate.angle_deg === summary.currentAngleDeg && "Current", candidate.angle_deg === summary.recommendedAngleDeg && "Recommended", candidate.predicted_kwh === summary.rawMaximum?.predicted_kwh && "Raw maximum"].filter(Boolean).join(" · ") || "Candidate"}</td>
              </tr>
            ))}</tbody>
          </table>
        </details>
      </> : <p className="dashboard-empty">No candidate predictions available for this run.</p>}
    </DashboardPanel>
  );
}

