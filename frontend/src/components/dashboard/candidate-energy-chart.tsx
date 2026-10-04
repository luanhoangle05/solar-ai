"use client";

import { CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { CandidatePrediction } from "@/types/solar";
import { getRawEnergyMaximum } from "@/lib/dashboard";
import { formatAngle, formatKwh } from "@/lib/formatters";

interface CandidateEnergyChartProps {
  candidates: CandidatePrediction[];
  currentAngle: number | null;
  recommendedAngle: number | null;
}

export function CandidateEnergyChart({ candidates, currentAngle, recommendedAngle }: CandidateEnergyChartProps) {
  const maximum = getRawEnergyMaximum(candidates);
  const current = candidates.find(candidate => candidate.angle_deg === currentAngle);
  const recommended = candidates.find(candidate => candidate.angle_deg === recommendedAngle);
  return (
    <div className="candidate-chart" role="img" aria-label="Raw predicted energy in kilowatt-hours by candidate tilt angle in degrees. Full values are in the candidate data table below.">
      <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={{ width: 640, height: 210 }}>
        <LineChart data={candidates} margin={{ top: 15, right: 18, bottom: 3, left: -9 }} accessibilityLayer>
          <CartesianGrid stroke="var(--border)" strokeOpacity={0.65} />
          <XAxis dataKey="angle_deg" type="number" domain={["dataMin", "dataMax"]} tickFormatter={value => formatAngle(Number(value))} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
          <YAxis width={45} domain={[0, "auto"]} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} tickLine={false} axisLine={false} />
          <Tooltip content={({ active, payload }) => {
            const point = payload?.[0]?.payload as CandidatePrediction | undefined;
            if (!active || !point) return null;
            const roles = [point.angle_deg === currentAngle && "Current", point.angle_deg === recommendedAngle && "Recommended", point.predicted_kwh === maximum?.predicted_kwh && "Highest raw energy"].filter(Boolean);
            return <div className="chart-tooltip"><strong>Angle {formatAngle(point.angle_deg)}</strong><p>{formatKwh(point.predicted_kwh, 3)} predicted</p>{roles.length > 0 && <span>{roles.join(" · ")}</span>}</div>;
          }} />
          <Line type="linear" dataKey="predicted_kwh" name="Predicted energy" stroke="var(--primary)" strokeWidth={2.5} dot={{ r: 3, fill: "var(--primary)" }} activeDot={{ r: 5 }} isAnimationActive={false} />
          {candidates.filter(point => point.predicted_kwh === maximum?.predicted_kwh).map(point => <ReferenceDot key={point.angle_deg} zIndex={100} x={point.angle_deg} y={point.predicted_kwh} r={10} fill="var(--card)" stroke="var(--warning)" strokeWidth={2} />)}
          {current && <ReferenceDot zIndex={100} x={current.angle_deg} y={current.predicted_kwh} r={7} fill="var(--card)" stroke="var(--foreground)" strokeWidth={2} />}
          {recommended && <ReferenceDot zIndex={100} x={recommended.angle_deg} y={recommended.predicted_kwh} r={8} fill="var(--success)" stroke="var(--card)" strokeWidth={2} />}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
