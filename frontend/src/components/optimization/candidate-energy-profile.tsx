"use client";

import { useId } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartNoAxesCombined } from "lucide-react";
import { formatAngle, formatCandidateEnergy } from "@/lib/formatters";
import type { DisplayCandidate } from "@/lib/optimization";
import { OptimizationPanel } from "./optimization-panel";

export function CandidateEnergyProfile({ candidates, current, recommended, rawAngles, horizon, scope }: {
  candidates: DisplayCandidate[]; current: number | null; recommended: number | null; rawAngles: number[]; horizon: number; scope: string;
}) {
  const gradientId = useId();
  const descriptionId = useId();
  const maxima = rawAngles.length ? rawAngles.map(formatAngle).join(", ") : "Unavailable";
  return <OptimizationPanel title="Candidate Energy Profile" icon={ChartNoAxesCombined} className="opt-profile" meta={<span className="opt-note">{scope} / {horizon} min</span>}>
    <p className="opt-note">Predicted energy for each backend-provided candidate angle.</p>
    <div className="opt-marker-key"><span>○ Current <strong>{formatAngle(current)}</strong></span><span>● Recommended <strong>{formatAngle(recommended)}</strong></span><span>◇ Raw max <strong>{maxima}</strong></span></div>
    <p id={descriptionId} className="sr-only">Predicted energy by candidate panel angle. Current {formatAngle(current)}, recommended {formatAngle(recommended)}, highest raw predicted-energy candidates {maxima}. Exact values and combined roles are in the Candidate Table below.</p>
    {candidates.length ? <div className="opt-chart" role="group" aria-label="Candidate energy chart" aria-describedby={descriptionId}>
      <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={{width:640,height:270}}>
        <AreaChart data={candidates} margin={{top:18,right:22,bottom:20,left:0}} accessibilityLayer>
          <defs><linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--primary)" stopOpacity={0.4}/><stop offset="100%" stopColor="var(--primary)" stopOpacity={0.02}/></linearGradient></defs>
          <CartesianGrid stroke="var(--border)" strokeOpacity={0.7}/>
          <XAxis dataKey="angle_deg" type="number" domain={["dataMin","dataMax"]} tickFormatter={value => formatAngle(Number(value))} tick={{fill:"var(--muted-foreground)",fontSize:11}} tickLine={false} axisLine={{stroke:"var(--border)"}} label={{value:"Panel angle (°)",position:"insideBottom",offset:-12,fill:"var(--muted-foreground)",fontSize:11}}/>
          <YAxis domain={["auto","auto"]} width={45} tick={{fill:"var(--muted-foreground)",fontSize:11}} tickLine={false} axisLine={false}/>
          <Tooltip content={({active,payload}) => {
            const point = payload?.[0]?.payload as DisplayCandidate | undefined;
            return active && point ? <div className="opt-tooltip"><strong>Angle {formatAngle(point.angle_deg)}</strong><p>{formatCandidateEnergy(point.predicted_kwh)} predicted</p><span>{point.roles.join(" · ") || "Candidate"}</span></div> : null;
          }}/>
          <Area type="linear" dataKey="predicted_kwh" stroke="#2bb8ff" strokeWidth={2.5} fill={"url(#" + gradientId + ")"} dot={{r:4,fill:"#2bb8ff",stroke:"var(--card)"}} activeDot={{r:6}} isAnimationActive={false}/>
          {candidates.filter(point => point.roles.length > 0).map(point => <ReferenceDot key={point.angle_deg} x={point.angle_deg} y={point.predicted_kwh} r={point.roles.includes("Raw Max") ? 9 : 7} zIndex={100} fill={point.roles.includes("Recommended") ? "var(--success)" : "var(--card)"} stroke={point.roles.includes("Raw Max") ? "var(--warning)" : point.roles.includes("Recommended") ? "var(--success)" : "#74d8ff"} strokeWidth={3}/>)}
        </AreaChart>
      </ResponsiveContainer>
    </div> : <p className="opt-empty">No candidate predictions available.</p>}
    <div className="opt-chart-footer"><span>Predicted energy (kWh) · scaled axis</span><span>Raw predictions · not a net-benefit curve</span></div>
    <p className="opt-note">Hover or use arrow keys on the chart to inspect exact values and combined roles.</p>
  </OptimizationPanel>;
}
