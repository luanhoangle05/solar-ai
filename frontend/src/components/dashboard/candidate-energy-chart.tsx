"use client";

import { CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { CandidatePrediction } from "@/types/solar";
import { formatAngle, formatKwh } from "@/lib/formatters";

interface CandidateEnergyChartProps {
  candidates: CandidatePrediction[];
  currentAngle: number | null;
  recommendedAngle: number | null;
}

export function CandidateEnergyChart({ candidates, currentAngle, recommendedAngle }: CandidateEnergyChartProps) {
  const current = candidates.find(candidate => candidate.angle_deg === currentAngle);
  const recommended = candidates.find(candidate => candidate.angle_deg === recommendedAngle);
  return (
    <div className="candidate-chart" role="img" aria-label="Raw predicted energy in kilowatt-hours by candidate tilt angle in degrees. Full values are in the candidate data table below.">
      <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={{ width: 640, height: 210 }}>
        <LineChart data={candidates} margin={{ top: 20, right: 24, bottom: 14, left: 0 }} accessibilityLayer>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="angle_deg" type="number" domain={["dataMin", "dataMax"]} tickFormatter={value => formatAngle(Number(value))} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
          <YAxis width={45} domain={[0, "auto"]} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} tickLine={false} axisLine={false} />
          <Tooltip
            contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: "var(--foreground)" }}
            formatter={value => [formatKwh(typeof value === "number" ? value : null, 3), "Predicted energy"]}
            labelFormatter={label => "Tilt " + formatAngle(Number(label))}
          />
          <Line type="linear" dataKey="predicted_kwh" name="Predicted energy" stroke="var(--primary)" strokeWidth={2.5} dot={{ r: 3, fill: "var(--primary)" }} activeDot={{ r: 5 }} isAnimationActive={false} />
          {current && <ReferenceDot zIndex={100} x={current.angle_deg} y={current.predicted_kwh} r={7} fill="var(--card)" stroke="var(--foreground)" strokeWidth={2} />}
          {recommended && <ReferenceDot zIndex={100} x={recommended.angle_deg} y={recommended.predicted_kwh} r={8} fill="var(--success)" stroke="var(--card)" strokeWidth={2} />}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}


