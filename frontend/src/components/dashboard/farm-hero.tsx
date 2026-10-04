"use client";
import { useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Info, PanelsTopLeft } from "lucide-react";
import { FarmZones } from "@/components/farm/farm-zones";
import { Farm3DLoader } from "@/components/farm-3d/farm-3d-loader";
import { getInitialSelection, getRowById, getZoneSelection, formatZoneName } from "@/lib/farm";
import { formatAngle } from "@/lib/formatters";
import type { FarmStatus, CurrentWeather } from "@/types/solar";

export function FarmHero({ farm, targetId, weather }: {farm:FarmStatus; targetId:string; weather:CurrentWeather|null}) {
  const [view,setView] = useState<"2d"|"3d">("2d");
  const [selection,setSelection] = useState(()=>getInitialSelection(farm,getRowById(farm,targetId)));
  const row = getRowById(farm,selection.rowId);
  function inspectRow(id:string) { const item=getRowById(farm,id); if(item) setSelection({rowId:item.row_id,zoneId:item.zone_id}); }
  function inspectZone(id:string) { setSelection(getZoneSelection(farm,id,selection.rowId)); }
  const available = farm.rows.length > 0 && farm.zones.length > 0;
  return <section className="operator-farm operator-card" data-view={view} aria-labelledby="farm-heading">
    <header className="operator-card-heading"><PanelsTopLeft size={19} aria-hidden="true"/><h2 id="farm-heading">Solar Farm Overview</h2><div className="operator-view-switch" role="group" aria-label="Farm view"><button type="button" aria-pressed={view === "2d"} onClick={()=>setView("2d")}>2D</button><button type="button" aria-pressed={view === "3d"} onClick={()=>setView("3d")}>3D</button></div></header>
    {!available ? <p className="operator-empty">Farm status unavailable</p> : view === "2d" ? <div className="operator-farm-canvas"><FarmZones mode="operator" farm={farm} targetId={getRowById(farm,targetId)?.row_id ?? null} selectedRow={selection.rowId} selectedZone={selection.zoneId} onRow={inspectRow} onZone={inspectZone}/><details className="operator-view-info"><summary aria-label="About the farm view"><Info size={16}/></summary><p>Illustrative layout. Zone membership and row states reflect the available farm data.</p></details></div> : <Farm3DLoader farm={farm} targetId={targetId} selectedRow={selection.rowId} selectedZone={selection.zoneId} onRow={inspectRow} onZone={inspectZone} onExit={()=>setView("2d")} operator weather={weather ? {cloudCoverPct:weather.cloud_cover_pct,ghiWm2:weather.ghi_wm2,windSpeedKmh:weather.wind_speed_kmh} : undefined}/>}
    {available && <div className="operator-farm-inspection"><label>Inspect row<select aria-label="Inspect loaded row" value={selection.rowId ?? ""} onChange={event=>inspectRow(event.target.value)}>{farm.rows.map(item=><option value={item.row_id} key={item.row_id}>{item.row_id} · {formatZoneName(item.zone_id)}</option>)}</select></label><p role="status">{row ? <><strong>{formatAngle(row.angle_deg)}</strong><span>{row.current_state}</span>{row.row_id === targetId && <span className="operator-target-badge">Control Target</span>}</> : "No row selected"}</p></div>}
    <Link className="operator-farm-link" href="/simulation" prefetch={false}>Explore in Simulation <ArrowUpRight size={16} aria-hidden="true"/></Link>
  </section>;
}
