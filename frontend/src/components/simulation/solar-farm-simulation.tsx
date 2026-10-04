"use client";
import dynamic from "next/dynamic";
import { useMemo, useState, type CSSProperties } from "react";
import { Cloud, Crosshair, Eye, Sun, Thermometer, Wind, Check, TriangleAlert, RotateCcw } from "lucide-react";
import { FarmZones } from "@/components/farm/farm-zones";
import { Farm3DLoader } from "@/components/farm-3d/farm-3d-loader";

import { getZoneColor } from "@/config/zones";
import { getInitialSelection, getRowById, getZoneSelection, getRowCounts, formatZoneName } from "@/lib/farm";
import { getCandidateAngleRange, getPreviewAngle, getRunForRow, getRunsPreviewFarm, getRunsPreviewRowCount, getRowSimulationView, getSimulationConditions, type FarmSimulationData, type RowSimulationView } from "@/lib/farm-simulation";
import { formatAngle, formatKwhEquivalent } from "@/lib/formatters";
import { getCommandCenterView } from "@/lib/command-center";
import type { FrontendData } from "@/types/solar";
import { AgentCommandCenter } from "./agent-command-center";
import { SimulationDetails } from "./simulation-details";
import "@/app/(solar)/farm/farm.css";
import "./solar-farm-simulation.css";

// WebGL only runs in the browser; reuse the existing lab on demand.
const SunLabScene = dynamic(() => import("./sun-lab-scene"), { ssr: false, loading: () => <div className="f3-loading" role="status">Preparing the sun lab…</div> });

const noZoneRuns: FarmSimulationData[] = [];
const weatherIcons = { ghi: Sun, clouds: Cloud, temperature: Thermometer, wind: Wind } as const;
export function getSimulationOverviewSelection(data: Pick<FrontendData, "farm_status" | "metadata">) {
  return getInitialSelection(data.farm_status, getRowById(data.farm_status, data.metadata.control_target_id));
}
export function SolarFarmSimulation({ data, zoneRuns = noZoneRuns, zoneRunsError = null }: { data: FrontendData; zoneRuns?: FarmSimulationData[]; zoneRunsError?: string | null }) {
  const runs = useMemo(() => [data, ...zoneRuns], [data, zoneRuns]);
  const targetId = data.metadata.control_target_id;
  const [selection, setSelection] = useState(() => getSimulationOverviewSelection(data));
  const [view, setView] = useState<"2d" | "3d" | "lab">("3d");
  const [preview, setPreview] = useState(false);
  const [camera, setCamera] = useState({ id: null as string | null, sequence: 0 });
  const run = getRunForRow(runs, selection.rowId);
  const rowView = getRowSimulationView(run, selection.rowId);
  const previewRows = useMemo(() => getRunsPreviewRowCount(runs), [runs]);
  const previewAngle = getPreviewAngle(run);
  const isPreviewing = preview && previewRows > 0;
  const farm = useMemo(() => isPreviewing ? getRunsPreviewFarm(runs) : data.farm_status, [isPreviewing, data, runs]);
  const conditions = getSimulationConditions(data);
  const command = getCommandCenterView(data);
  const states = getRowCounts(data.farm_status.rows).states;
  function inspectRow(id: string) { const row = getRowById(data.farm_status, id); if (row) { setSelection({ rowId: row.row_id, zoneId: row.zone_id }); setPreview(false); setCamera(value => ({ id: null, sequence: value.sequence + 1 })); } }
  function inspectZone(id: string) { setSelection(getZoneSelection(data.farm_status, id, selection.rowId)); setPreview(false); setCamera(value => ({ id: null, sequence: value.sequence + 1 })); }
  function focus(id: string | null) { setCamera(value => ({ id, sequence: value.sequence + 1 })); }
  function backToFarm() {
    setSelection(getSimulationOverviewSelection(data));
    setPreview(false);
    focus(null);
  }
  const w = data.current_weather;
  const sceneWeather = useMemo(() => w ? { cloudCoverPct: w.cloud_cover_pct, ghiWm2: w.ghi_wm2, windSpeedKmh: w.wind_speed_kmh } : undefined, [w]);
  const candidates = run.candidate_predictions;
  const trackingRange = useMemo(() => getCandidateAngleRange({ candidate_predictions: candidates }) ?? undefined, [candidates]);
  const sceneProps = { farm, targetId, selectedZone: selection.zoneId, selectedRow: selection.rowId, onZone: inspectZone, onRow: inspectRow };
  const hasFarm = farm.rows.length > 0 && farm.zones.length > 0;
  return <div className="simulation-experience">
    <AgentCommandCenter view={command}/>
    <header className="sfs-header"><div className="sfs-title"><Sun size={26} aria-hidden="true"/><div><h2>Solar Farm Simulation</h2><p>Explore panel angles and environmental conditions.</p></div></div><div className="sfs-time"><span>Analysis interval</span><strong>{conditions.interval}</strong><small>{conditions.horizon} prediction horizon</small></div>
    <section className="sfs-weather" aria-label="Environmental conditions">{conditions.weather ? conditions.weather.map(item => { const Icon = weatherIcons[item.key]; return <div key={item.key}><Icon size={20} aria-hidden="true"/><span>{item.label}</span><strong>{item.value}</strong></div>; }) : <p>Environmental data unavailable.</p>}</section>
    </header>
    <div className="sfs-body">
      <section className="sfs-scene" aria-label="Solar Farm" data-preview={isPreviewing}>
        <header className="sfs-scene-bar"><h2><Sun size={18} aria-hidden="true"/>Solar Farm</h2>{isPreviewing && <span className="sfs-preview-tag">Angle Preview · {previewRows} rows · visual only</span>}<div role="group" aria-label="Farm view"><button type="button" aria-pressed={view === "2d"} onClick={() => setView("2d")}>2D</button><button type="button" aria-pressed={view === "3d"} onClick={() => setView("3d")}>3D</button><button type="button" aria-pressed={view === "lab"} onClick={() => setView("lab")}>Sun lab</button></div></header>
        {!hasFarm ? <p className="sim-empty">Farm data unavailable.</p> : view === "3d" ? <Farm3DLoader {...sceneProps} operator simulation weather={sceneWeather} trackingRange={trackingRange} cameraRequest={camera} onFocus={focus} onExit={() => setView("2d")}/> : view === "lab" ? (rowView ? <SunLabScene rowId={rowView.row.row_id} recordedAngle={rowView.currentAngle} recommendedAngle={rowView.recommendedAngle} evaluated={trackingRange ?? null}/> : <div className="f3-loading" role="status">Select a row to open the sun lab.</div>) : <div className="sfs-map"><FarmZones mode="operator" {...sceneProps}/><p className="sfs-map-caption">Select a row to explore · TARGET marks the recommendation</p></div>}
        {hasFarm && <div className="sfs-picker"><label htmlFor="simulation-row">Inspect row</label><select id="simulation-row" value={selection.rowId ?? ""} onChange={event => inspectRow(event.target.value)}>{data.farm_status.rows.map(row => <option key={row.row_id} value={row.row_id}>{row.row_id} · {formatZoneName(row.zone_id)}</option>)}</select><span>{isPreviewing ? "Visual preview only" : "Current panel angles"}</span></div>}
      </section>
      {rowView ? <RowPanel view={rowView} data={run} previewRows={previewRows} runCount={runs.length} previewAngle={previewAngle} isPreviewing={isPreviewing} onPreview={() => setPreview(value => !value)} focused={camera.id === selection.rowId} onFocus={() => { setView("3d"); focus(selection.rowId); }} onOverview={backToFarm}/> : <aside className="sfs-row"><h2>Selected Row</h2><p>No row selected.</p></aside>}
    </div>
    {zoneRunsError && <p className="sim-warning" role="alert">Additional zone analyses could not be loaded. Only the main analysis is shown.</p>}
    <div className="sim-summaries"><section className="sfs-zones" aria-label="Zone summary">{data.farm_status.zones.map(zone => <button type="button" key={zone.zone_id} aria-pressed={selection.zoneId === zone.zone_id} onClick={() => inspectZone(zone.zone_id)} style={{ "--zone-color": getZoneColor(zone.zone_id) } as CSSProperties}><i aria-hidden="true"/><strong>{formatZoneName(zone.zone_id)}</strong><span>{zone.panel_count} panels · {zone.row_ids.length} rows</span></button>)}</section><section className="sfs-status" aria-label="Row Status"><h2>Row Status</h2><dl>{Object.entries(states).map(([state,count]) => <div key={state} data-state={state}><dt>{state}</dt><dd>{count}</dd></div>)}</dl></section></div>
    <SimulationDetails data={data} selectedRow={selection.rowId} onRow={inspectRow}/>
    <p className="sr-only" role="status">Selected {selection.rowId ?? "no row"}.{isPreviewing ? ` Angle Preview for ${previewRows} rows. Visual preview only.` : ""}</p>
  </div>;
}
export function RowPanel({ view, data, previewRows, runCount, previewAngle, isPreviewing, onPreview, focused, onFocus, onOverview }: { view: RowSimulationView; data: FarmSimulationData; previewRows: number; runCount: number; previewAngle: number | null; isPreviewing: boolean; onPreview: () => void; focused: boolean; onFocus: () => void; onOverview: () => void }) {
  const { row } = view;
  const action = data.decision.action;
  const recommended = view.appliesDecision && (data.optimization || action === "STOW") ? data.decision.target_angle_deg : null;
  const canPreview = view.appliesDecision && previewAngle !== null && previewAngle !== row.angle_deg;
  const canToggle = view.appliesDecision && (canPreview || (runCount > 1 && previewRows > 0));
  const shownAngle = isPreviewing && canPreview ? previewAngle : view.currentAngle;
  const gains = Boolean(view.appliesDecision && data.optimization && action !== "STOW");
  const hasRecommendation = recommended !== null;
  const netBenefit = gains ? formatKwhEquivalent(data.optimization!.net_benefit_kwh_equivalent) : "—";
  return <aside className="sfs-row" aria-label="Selected Row" data-blocked={view.appliesDecision && !data.safety.passed}>
    <header><h2>Selected Row</h2>{view.isTarget && <span className="sfs-target"><Crosshair size={11} aria-hidden="true"/>TARGET</span>}</header>
    <h3>{row.row_id}</h3><p className="sfs-row-meta">{view.zoneName} · {row.panel_count} panels <span>{row.current_state}</span></p>
    <TiltDiagram current={view.currentAngle} recommended={canPreview ? previewAngle : null} shown={shownAngle} panels={row.panel_count}/>
    <div className="sfs-angles"><div><span>Current Angle</span><strong>{formatAngle(view.currentAngle)}</strong></div><div><span>{action === "HOLD" && view.appliesDecision ? "Keep current angle" : action === "STOW" && view.appliesDecision ? "Stow target" : "Recommended"}</span><strong>{recommended === null ? "—" : formatAngle(action === "HOLD" ? view.currentAngle : recommended)}</strong></div></div>
    <dl className="sfs-benefits"><div><dt>Expected Gain</dt><dd>{gains ? view.gain : "—"}</dd></div><div><dt>Net Benefit</dt><dd data-positive={gains && data.safety.passed && data.optimization!.net_benefit_kwh_equivalent > 0}>{netBenefit}</dd></div></dl>
    {gains && <p className="sim-scope">Per {data.metadata.energy_scope} · next {view.horizon}</p>}
    <p className="sfs-safety" data-safe={hasRecommendation && data.safety.passed && action !== "STOW"} data-neutral={!hasRecommendation}>{!hasRecommendation ? <Eye size={15} aria-hidden="true"/> : data.safety.passed && action !== "STOW" ? <Check size={15} aria-hidden="true"/> : <TriangleAlert size={15} aria-hidden="true"/>}{!hasRecommendation ? "No active recommendation for this row." : action === "STOW" ? "Protective stow recommendation" : !data.safety.passed ? "Rotation blocked" : "Safe to proceed"}</p>
    {view.appliesDecision && !data.optimization && action !== "STOW" ? <p className="sfs-no-recommendation">No AI recommendation available.</p> : view.appliesDecision && action === "HOLD" ? <p className="sfs-no-recommendation">No adjustment recommended.</p> : null}
    <section className="sfs-reasoning" aria-label="Row reasoning"><h4>Agent reasoning for this row</h4>{view.reasoning.length > 0 ? <ul>{view.reasoning.map((line, index) => <li key={index}>{line}</li>)}</ul> : <div className="sfs-reasoning-empty"><p>No recommendation is shown for this row because it is not covered by the current optimization decision.</p><p>Current recorded state: {row.current_state}.</p><p>Current recorded angle: {formatAngle(view.currentAngle)}.</p></div>}</section>
    <div className="sfs-row-actions"><button type="button" onClick={focused ? onOverview : onFocus}>{focused ? <RotateCcw size={15} aria-hidden="true"/> : <Crosshair size={15} aria-hidden="true"/>}{focused ? "Back to Farm" : "Focus Row"}</button>{canToggle && <button type="button" aria-pressed={isPreviewing} onClick={onPreview}><Eye size={15} aria-hidden="true"/>{isPreviewing ? "Show Current Angle" : runCount > 1 ? `Preview all zone decisions (${previewRows} rows)` : "Angle Preview"}</button>}</div>
    {isPreviewing && <p className="sim-scope">Visual preview only</p>}
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
