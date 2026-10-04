import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { formatRecordedTime } from "@/lib/formatters";
import type { FrontendData, Metadata } from "@/types/solar";
import "@/app/(solar)/optimization/optimization.css";
import "@/app/(solar)/agents/agents.css";
import "./inspection.css";

export function InspectionPage({ data, icon, title, description, label = "READ-ONLY SNAPSHOT", children }: {
  data: FrontendData; icon: LucideIcon; title: string; description: string; label?: string; children: ReactNode;
}) {
  return <div className="inspection-page"><PageHeader icon={icon} title={title} description={description} actions={<><Badge variant={data.metadata.dataset_kind === "MOCK" ? "warning" : "outline"}>{data.metadata.dataset_kind} DATA</Badge><Badge variant="outline">{label}</Badge></>}/>
    {data.errors.length > 0 && <section className="inspect-errors" aria-label="Recorded pipeline issues">{data.errors.map((error, i) => <p key={i}><strong>{error.agent} · {error.code}</strong> {error.message}</p>)}</section>}
    {children}<footer className="inspect-footer"><span>{data.metadata.dataset_kind === "MOCK" ? "MOCK development data · synthetic inputs and outcomes" : "Recorded contract data"}</span><span>Run: <time dateTime={data.timestamp}>{formatRecordedTime(data.timestamp)}</time></span></footer>
  </div>;
}
export function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return <dl className="inspect-facts">{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>;
}
export function PredictionFacts({ metadata }: { metadata: Metadata }) {
  return <Facts rows={[["Control target", metadata.control_target_id], ["Energy scope", metadata.energy_scope], ["Prediction horizon", `${metadata.prediction_horizon_minutes} min`], ["Interval start", formatRecordedTime(metadata.interval_start)]]}/>;
}
