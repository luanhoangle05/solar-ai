"use client";

import { useState } from "react";
import { emptyRowFilters, getInitialSelection, getRowById, getZoneById, getZoneSelection, type FarmExplorerData, type FarmSummary } from "@/lib/farm";
import { FarmMap } from "./farm-map";
import { RowDetails, ZoneDetails, ZoneNavigator } from "./farm-details";
import { FarmDistributions, FarmSummaryPanel } from "./farm-summaries";
import { RowTable } from "./row-table";

export function FarmExplorer({ data, summary }: { data:FarmExplorerData; summary:FarmSummary }) {
  // Only inspection and filters are mutable; the validated payload is never changed.
  const [selection,setSelection] = useState(()=>getInitialSelection(data.farm_status,summary.targetRow));
  const [filters,setFilters] = useState({...emptyRowFilters});
  const row = getRowById(data.farm_status,selection.rowId);
  const zone = getZoneById(data.farm_status,selection.zoneId);
  function inspectRow(id:string) {
    const selected = getRowById(data.farm_status,id);
    if (selected) setSelection({rowId:selected.row_id,zoneId:selected.zone_id});
  }
  function inspectZone(id:string) { setSelection(getZoneSelection(data.farm_status,id,selection.rowId)); }
  return <div className="fx-grid">
    <FarmSummaryPanel data={data} summary={summary}/>
    <FarmMap farm={data.farm_status} targetId={data.metadata.control_target_id} selectedZone={selection.zoneId} selectedRow={selection.rowId} onZone={inspectZone} onRow={inspectRow}/>
    <RowDetails data={data} row={row} onRow={inspectRow}/>
    <ZoneDetails data={data} zone={zone}/>
    <FarmDistributions summary={summary}/>
    <ZoneNavigator data={data} selectedZone={selection.zoneId} onZone={inspectZone}/>
    <RowTable farm={data.farm_status} targetId={data.metadata.control_target_id} selectedRow={selection.rowId} onRow={inspectRow} filters={filters} onFilters={setFilters}/>
    <p className="sr-only" role="status">Inspecting {row?.row_id ?? "no row"} in {zone?.zone_id ?? "no zone"}. Control target remains {data.metadata.control_target_id}.</p>
  </div>;
}
