"use client";
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { ArrowRight, Cloud, Crosshair, Eye, MousePointerClick, Play, RotateCcw, Settings2, Sun, Thermometer, Timer, Wind, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { FarmMap } from "@/components/farm/farm-map";
import { Farm3DLoader } from "@/components/farm-3d/farm-3d-loader";
import { rowStatePresentation } from "@/config/row-states";
import { getInitialSelection, getRowById, getZoneSelection } from "@/lib/farm";
import { getCandidateAngleRange, getPreviewAngle, getPreviewFarm, getPreviewRowIds, getRowSimulationView, getSimulationConditions, type FarmSimulationData, type RowSimulationView } from "@/lib/farm-simulation";
import { formatAngle } from "@/lib/formatters";
import "@/app/(solar)/farm/farm.css";
import "./solar-farm-simulation.css";

// WebGL only runs in the browser, so the lab is loaded on demand like the farm scene.
const SunLabScene = dynamic(() => import("./sun-lab-scene"), { ssr: false, loading: () => <div className="f3-loading" role="status">Preparing the sun lab…</div> });

const weatherIcons = { ghi: Sun, clouds: Cloud, temperature: Thermometer, wind: Wind } as const;

/**
 * Farm view for the recorded run. Selecting a row only changes what is inspected.
 * "Preview" redraws the control-target row at the backend's recommended angle on screen only:
 * the payload is not changed and no controller command exists in this app.
 */
export function SolarFarmSimulation({ data }: { data: FarmSimulationData }) {
  const targetId = data.metadata.control_target_id;
  const [selection, setSelection] = useState(() => getInitialSelection(data.farm_status, getRowById(data.farm_status, data.metadata.control_target_id)));
  const [view, setView] = useState<"2d" | "3d" | "lab">("3d");
  const [isPreviewing, setIsPreviewing] = useState(false);
  const conditions = getSimulationConditions(data);
  const previewAngle = getPreviewAngle(data);
  // Memoized so the 3D scene rebuilds only when the preview is toggled, not on every row selection.
  const farm = useMemo(() => isPreviewing ? getPreviewFarm(data) : data.farm_status, [isPreviewing, data]);
  const rowView = getRowSimulationView(data, selection.rowId);
  function inspectRow(id: string) {
    const row = getRowById(data.farm_status, id);
    if (row) setSelection({ rowId: row.row_id, zoneId: row.zone_id });
  }
  function inspectZone(id: string) { setSelection(getZoneSelection(data.farm_status, id, selection.rowId)); }
  const cloudCoverPct = data.current_weather?.cloud_cover_pct, ghiWm2 = data.current_weather?.ghi_wm2, windSpeedKmh = data.current_weather?.wind_speed_kmh;
  const sceneWeather = useMemo(() => cloudCoverPct === undefined || ghiWm2 === undefined ? undefined : { cloudCoverPct, ghiWm2, windSpeedKmh }, [cloudCoverPct, ghiWm2, windSpeedKmh]);
  const candidates = data.candidate_predictions;
  const trackingRange = useMemo(() => getCandidateAngleRange({ candidate_predictions: candidates }) ?? undefined, [candidates]);
  const sceneProps = { farm, targetId, selectedZone: selection.zoneId, selectedRow: selection.rowId, onZone: inspectZone, onRow: inspectRow };

  return <section className="sfs" aria-label="Solar Farm Simulation">
    <header className="sfs-header">
      <div className="sfs-title"><Settings2 size={26} aria-hidden="true"/><div><h2>Solar Farm Simulation</h2><p>Interactive 3D view of the recorded farm state and the recommended panel angle.</p></div></div>
      {conditions.weather
        ? <dl className="sfs-weather">{conditions.weather.map(item => { const Icon = weatherIcons[item.key]; return <div key={item.key} data-kind={item.key}><Icon size={26} aria-hidden="true"/><dt>{item.label}</dt><dd>{item.value}</dd></div>; })}</dl>
        : <p className="sfs-weather-missing">Weather input unavailable for this payload.</p>}
      <div className="sfs-time"><Timer size={22} aria-hidden="true"/><div><span>Recorded interval</span><strong>{conditions.interval}</strong><small>{conditions.horizon} prediction horizon · single recorded step</small></div></div>
    </header>
    <div className="sfs-body">
      <div className="sfs-scene" data-preview={isPreviewing}>
        <div className="sfs-scene-bar">
          <span><MousePointerClick size={14} aria-hidden="true"/>{view === "lab" ? "Hold the sun and move it anywhere · Drag elsewhere to rotate · Scroll to zoom · Right-drag to move" : "Drag to rotate · Scroll to zoom · Click a row to zoom in on it · Overview to zoom back out"}</span>
          {isPreviewing && <span className="sfs-preview-tag"><Eye size={13} aria-hidden="true"/>PREVIEW · {data.decision.action} · {targetId} drawn at {formatAngle(previewAngle)}</span>}
          <div role="group" aria-label="Farm view"><button type="button" aria-pressed={view === "2d"} onClick={() => setView("2d")}>2D</button><button type="button" aria-pressed={view === "3d"} onClick={() => setView("3d")}>3D</button><button type="button" aria-pressed={view === "lab"} onClick={() => setView("lab")}>Sun lab</button></div>
        </div>
        {view === "3d" ? <Farm3DLoader {...sceneProps} weather={sceneWeather} trackingRange={trackingRange} onExit={() => setView("2d")}/>
          : view === "lab" ? (rowView ? <SunLabScene rowId={rowView.row.row_id} recordedAngle={rowView.currentAngle} recommendedAngle={rowView.recommendedAngle} evaluated={trackingRange ?? null}/> : <div className="f3-loading" role="status">Select a row to open the sun lab.</div>)
          : <FarmMap {...sceneProps}/>}
      </div>
      {rowView
        ? <RowPanel view={rowView} action={data.decision.action} previewAngle={previewAngle} previewRows={getPreviewRowIds(data).length} isPreviewing={isPreviewing} onPreview={setIsPreviewing}/>
        : <aside className="sfs-row"><p className="sfs-empty">No row available for inspection.</p></aside>}
    </div>
    <p className="sr-only" role="status">Inspecting {selection.rowId ?? "no row"}.{isPreviewing ? ` Previewing ${targetId} at ${formatAngle(previewAngle)}; no command is sent.` : ""}</p>
  </section>;
}

function RowPanel({ view, action, previewAngle, previewRows, isPreviewing, onPreview }: { view: RowSimulationView; action: string; previewAngle: number | null; previewRows: number; isPreviewing: boolean; onPreview: (value: boolean) => void }) {
  const { row } = view;
  const canPreview = view.isTarget && previewAngle !== null;
  const shownAngle = isPreviewing && canPreview ? previewAngle : view.currentAngle;
  return <aside className="sfs-row" aria-label="Selected row">
    <div className="sfs-row-head"><span className="sfs-dot" data-target={view.isTarget} aria-hidden="true"/><div><h3>Selected Row: {row.row_id}</h3><p>{view.zoneName} <i/> {view.position}</p></div>
      <div className="sfs-row-badges"><Badge variant={rowStatePresentation[row.current_state].variant}>{row.current_state}</Badge>{view.isTarget && <span className="sfs-target"><Crosshair size={11} aria-hidden="true"/>CONTROL TARGET</span>}</div></div>
    <TiltDiagram current={view.currentAngle} recommended={canPreview ? previewAngle : null} shown={shownAngle} panels={row.panel_count}/>
    <div className="sfs-angles">
      <div><span>Current angle</span><strong>{formatAngle(view.currentAngle)}</strong></div>
      <ArrowRight size={20} aria-hidden="true"/>
      <div data-tone="recommended"><span>Recommended angle</span><strong>{view.recommendedAngle === null ? "—" : formatAngle(view.recommendedAngle)}</strong></div>
      <div className="sfs-gain"><Zap size={24} aria-hidden="true"/><span>Estimated gain</span><strong>{view.gain ?? "—"}</strong><small>{view.gain ? `per ${view.horizon}` : "not supplied"}</small></div>
    </div>
    <div className="sfs-reasoning">
      <h4><Settings2 size={15} aria-hidden="true"/>Agent reasoning for this row</h4>
      {view.reasoning.length
        ? <ul>{view.reasoning.map((line, index) => <li key={index}>{line}</li>)}</ul>
        : <p>This row is not the current optimization control target. No row-specific recommendation is supplied; it shows its recorded state ({row.current_state}) and recorded action ({row.action}).</p>}
      {canPreview && <button type="button" className="sfs-apply" aria-pressed={isPreviewing} onClick={() => onPreview(!isPreviewing)}>
        {isPreviewing ? <><RotateCcw size={15} aria-hidden="true"/>Show recorded {formatAngle(view.currentAngle)}</> : <><Play size={15} aria-hidden="true"/>Preview {action} to {formatAngle(previewAngle)} on {previewRows > 1 ? `${previewRows} rows` : row.row_id}</>}
      </button>}
      {view.isTarget && !canPreview && <p>The manager decision is HOLD, so there is no movement to preview.</p>}
    </div>
    <p className="sfs-note">{previewRows > 1 ? `The decision is computed for the control row; the payload shows the same action on ${previewRows} rows in the same state and at the same angle. ` : ""}Preview redraws the row on screen only. The payload records a proposed action; no controller command is sent or confirmed.</p>
  </aside>;
}

/** Side view of one panel on its post, tilted from horizontal. Illustrative geometry; the angles are payload values. */
function TiltDiagram({ current, recommended, shown, panels }: { current: number; recommended: number | null; shown: number; panels: number }) {
  const ghost = recommended !== null && recommended !== shown ? recommended : recommended !== null && current !== shown ? current : null;
  const label = `Side view of the row tilted ${formatAngle(shown)} from horizontal${ghost !== null ? `; outline shows ${formatAngle(ghost)}` : ""}`;
  return <div className="sfs-diagram"><svg viewBox="0 0 320 150" role="img" aria-label={label}>
    <defs><linearGradient id="sfs-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#0d3a66"/><stop offset="1" stopColor="#0a2238"/></linearGradient></defs>
    <rect width="320" height="150" rx="8" fill="url(#sfs-sky)"/>
    <circle cx="262" cy="34" r="13" fill="#ffd866"/><circle cx="262" cy="34" r="22" fill="#ffd86622"/>
    <rect y="124" width="320" height="26" fill="#12303a"/><line x1="0" y1="124" x2="320" y2="124" stroke="#2f5f6c"/>
    <line x1="150" y1="124" x2="150" y2="78" stroke="#8ea2b3" strokeWidth="5"/>
    {ghost !== null && <g transform={`translate(150 78) rotate(${-ghost})`}><rect x="-78" y="-6" width="156" height="12" rx="2" fill="none" stroke="#22e39a" strokeDasharray="5 4"/></g>}
    <g transform={`translate(150 78) rotate(${-shown})`} className="sfs-diagram-panel"><rect x="-78" y="-6" width="156" height="12" rx="2" fill="#1b5fae" stroke="#8fd3ff"/><path d="M-52 -6v12 M-26 -6v12 M0 -6v12 M26 -6v12 M52 -6v12" stroke="#7fb0de"/></g>
    <text x="14" y="24" fill="#cfe6f7" fontSize="12">{formatAngle(shown)} tilt</text>
    <text x="14" y="142" fill="#8fb0c8" fontSize="9">{panels} panels · illustrative side view</text>
  </svg></div>;
}
