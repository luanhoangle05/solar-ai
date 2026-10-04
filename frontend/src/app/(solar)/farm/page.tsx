import { PanelsTopLeft } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DataError } from "@/components/shared/data-error";
import { FarmExplorer } from "@/components/farm/farm-explorer";
import { getFarmSummary } from "@/lib/farm";
import { loadFrontendDataResult } from "@/lib/frontend-data.server";
import { formatDisplayName, formatRecordedTime } from "@/lib/formatters";
import "./farm.css";

export const metadata = { title: "Farm & Zones | SolarAI" };
export default async function Page() {
  const result = await loadFrontendDataResult();
  if (!result.ok) return <DataError message={result.error.message} details={result.error.details}/>;
  const data = result.data;
  const summary = getFarmSummary(data);
  return <div className="farm-page">
    <header className="fx-header"><PanelsTopLeft size={28} aria-hidden="true"/><div><h1>Farm & Zones</h1><p>Inspect zone layout, row states, panel angles, and the current SolarAI control target.</p></div><div className="fx-header-badges"><Badge variant={data.metadata.dataset_kind === "MOCK" ? "warning" : "outline"}>{data.metadata.dataset_kind} DATA</Badge><Badge variant="outline">READ-ONLY INSPECTION</Badge></div></header>
    {data.errors.length > 0 && <section className="fx-errors" aria-label="Pipeline issues"><h2>Recorded pipeline issues — separate from row fault states</h2>{data.errors.map((error,index)=><p key={index}><strong>{formatDisplayName(error.agent)} · {error.code}</strong> {error.message}</p>)}</section>}
    <FarmExplorer data={{farm_status:data.farm_status,metadata:data.metadata,optimization:data.optimization,decision:data.decision,safety:data.safety}} summary={summary}/>
    <footer className="fx-footer"><span>{data.metadata.dataset_kind === "MOCK" ? "MOCK fixture · synthetic farm state" : "Recorded farm snapshot"} · <time dateTime={data.timestamp}>{formatRecordedTime(data.timestamp)}</time></span><span>{data.metadata.config_id} · Schematic, not geographic</span></footer>
  </div>;
}
