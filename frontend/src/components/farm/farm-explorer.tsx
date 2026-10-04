"use client";

import { useState } from "react";
import { emptyRowFilters, getInitialSelection, getRowById, getZoneById, getZoneSelection, type FarmExplorerData, type FarmSummary } from "@/lib/farm";
import { FarmMap } from "./farm-map";
import { RowDetails, ZoneDetails, ZoneNavigator } from "./farm-details";
import { FarmDistributions, FarmSummaryPanel } from "./farm-summaries";
import { RowTable } from "./row-table";
import { Farm3DLoader } from "../farm-3d/farm-3d-loader";

export function FarmExplorer({ data, summary }: { data:FarmExplorerData; summary:FarmSummary }) {
  // Only inspection and filters are mutable; the validated payload is never changed.
  const [selection,setSelection] = useState(()=>getInitialSelection(data.farm_status,summary.targetRow));
  const [filters,setFilters] = useState({...emptyRowFilters});
  const [view,setView] = useState<"2d"|"3d">("2d");
  const row = getRowById(data.farm_status,selection.rowId);
  const zone = getZoneById(data.farm_status,selection.zoneId);
  function inspectRow(id:string) {
    const selected = getRowById(data.farm_status,id);
    if (selected) setSelection({rowId:selected.row_id,zoneId:selected.zone_id});
  }
  function inspectZone(id:string) { setSelection(getZoneSelection(data.farm_status,id,selection.rowId)); }
  return <div className="fx-grid" data-view={view}>
    <FarmSummaryPanel data={data} summary={summary}/>
    <div className="fx-visual">
      <div className="fx-view-bar"><span>EXPLORE THE FARM <small>Inspection only</small></span><div role="group" aria-label="Farm view"><button type="button" aria-pressed={view === "2d"} onClick={()=>setView("2d")}>2D Schematic</button><button type="button" aria-pressed={view === "3d"} onClick={()=>setView("3d")}>3D Farm</button></div></div>
      {view === "2d" ? <FarmMap farm={data.farm_status} targetId={data.metadata.control_target_id} selectedZone={selection.zoneId} selectedRow={selection.rowId} onZone={inspectZone} onRow={inspectRow}/> : <Farm3DLoader farm={data.farm_status} targetId={data.metadata.control_target_id} selectedZone={selection.zoneId} selectedRow={selection.rowId} onZone={inspectZone} onRow={inspectRow} onExit={()=>setView("2d")}/>}
    </div>
    <RowDetails data={data} row={row} onRow={inspectRow}/>
    <ZoneDetails data={data} zone={zone}/>
    <FarmDistributions summary={summary}/>
    <ZoneNavigator data={data} selectedZone={selection.zoneId} onZone={inspectZone}/>
    <RowTable farm={data.farm_status} targetId={data.metadata.control_target_id} selectedRow={selection.rowId} onRow={inspectRow} filters={filters} onFilters={setFilters}/>
    <p className="sr-only" role="status">Inspecting {row?.row_id ?? "no row"} in {zone?.zone_id ?? "no zone"}. Control target remains {data.metadata.control_target_id}.</p>
  </div>;
}
