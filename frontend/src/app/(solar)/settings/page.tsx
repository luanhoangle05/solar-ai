import { Settings, Database, ScanLine, Crosshair, FileJson2, Grid2X2, ListChecks, Fingerprint } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DataError } from "@/components/shared/data-error";
import { InspectionPage, Facts, PredictionFacts } from "@/components/shared/inspection-page";
import { OperationsPanel } from "@/components/agents/operations-panel";
import { DataQuality } from "@/components/agents/operations-outcomes";
import { getAgentsSummary } from "@/lib/agents";
import { loadFrontendDataResult } from "@/lib/frontend-data.server";
import { getSystemConfigView } from "@/lib/system-config";
import { formatAngle, formatModelName, formatRecordedTime } from "@/lib/formatters";
export const metadata = { title: "System Configuration | SolarAI" };
export default async function Page() {
  const result=await loadFrontendDataResult();
  if (!result.ok) return <DataError message={result.error.message} details={result.error.details}/>;
  const data=result.data, view=getSystemConfigView(data), meta=view.metadata, target=view.farm.targetRow;
  return <InspectionPage data={data} icon={Settings} title="System Configuration" label="READ ONLY" description="Inspect the schema, prediction scope, data mode, and configuration metadata associated with this SolarAI run.">
    <div className="inspect-grid">
      <OperationsPanel title="Data Mode" icon={Database} meta={<Badge variant="outline">CONFIGURATION SNAPSHOT</Badge>}><div className="inspect-mode" data-mode={meta.dataset_kind}><Database size={35} aria-hidden="true"/><div><strong>{meta.dataset_kind}</strong><p>Label source: {meta.label_source}</p></div></div><p className="inspect-note">{meta.dataset_kind === "MOCK" ? "Synthetic development fixture. Inputs, predictions, metrics, and decisions are illustrative." : "Dataset mode is supplied by the contract. This page displays the recorded payload."}</p></OperationsPanel>
      <OperationsPanel title="Prediction Scope" icon={ScanLine}><PredictionFacts metadata={meta}/><p className="inspect-note">Energy values refer to the control row over this interval, not total farm output.</p></OperationsPanel>
      <OperationsPanel title="Control Target" icon={Crosshair}><Facts rows={[["Target ID",meta.control_target_id],["Zone",target?.zone_id ?? "Unavailable"],["Panels in target row",target?.panel_count ?? "Unavailable"],["Observed angle",formatAngle(target?.angle_deg ?? null)],["Recorded row state",target?.current_state ?? "Unavailable"]]}/></OperationsPanel>
      <OperationsPanel title="Schema & Contract" icon={FileJson2}><Facts rows={[["Schema version",meta.schema_version],["Configuration ID",meta.config_id],["Selected prediction model",formatModelName(view.selectedModel?.model ?? null)]]}/><p className="inspect-note">Validated against the existing shared FrontendData contract. Configuration identifiers and scope are supplied values.</p></OperationsPanel>
      <OperationsPanel title="Farm Configuration Summary" icon={Grid2X2} className="inspect-wide"><div className="inspect-farm-totals">{[["Panels",view.farm.totalPanels],["Rows",view.farm.totalRows],["Zones",view.farm.zoneCount],["Panels per row",view.farm.panelsPerRow]].map(([label,value])=><div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div><p className="inspect-note">Counts describe the loaded farm status; this view does not edit the farm layout.</p></OperationsPanel>
      <OperationsPanel title="Recorded Assumptions" icon={ListChecks} className="inspect-wide">{meta.assumptions.length ? <ol className="inspect-assumptions">{meta.assumptions.map((assumption,i)=><li key={i}><span aria-hidden="true">{String(i+1).padStart(2,"0")}</span><p>{assumption}</p></li>)}</ol> : <p className="inspect-empty">No assumptions recorded in this payload.</p>}</OperationsPanel>
      <DataQuality summary={getAgentsSummary(data)}/>
      <OperationsPanel title="Run Provenance" icon={Fingerprint}><Facts rows={[["Recorded run",formatRecordedTime(view.timestamp)],["Interval start",formatRecordedTime(meta.interval_start)],["Source",view.source.source],["Label source",meta.label_source],["Configuration",meta.config_id]]}/><p className="inspect-note">A read-only record of this run. Configuration changes require a supported backend capability.</p></OperationsPanel>
    </div>
  </InspectionPage>;
}
