"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ComponentRef, type CSSProperties, type RefObject } from "react";
import { Canvas, useThree, type ThreeEvent } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import { CanvasTexture, Color, InstancedMesh, Object3D, SRGBColorSpace } from "three";
import { Box, Crosshair, Eye, RotateCcw, ScanLine } from "lucide-react";
import { getZoneColor } from "@/config/zones";
import { rowStatePresentation } from "@/config/row-states";
import { buildFarmSceneLayout, getCameraPreset, getInstanceRowId, getSceneRow, sceneDimensions, type FarmSceneLayout, type SceneRow, type SceneZone, type Vec3 } from "@/lib/farm-3d";
import { formatZoneName } from "@/lib/farm";
import { formatAngle } from "@/lib/formatters";
import { FarmPanel } from "@/components/farm/farm-panel";
import { SceneUnavailable, type Farm3DProps } from "./farm-3d-loader";

function resolveColor(value: string) {
  const variable = /^var\((--[^)]+)\)$/.exec(value);
  return variable ? getComputedStyle(document.documentElement).getPropertyValue(variable[1]).trim() : value;
}
function makePanelTexture() {
  const canvas = document.createElement("canvas"); canvas.width = 128; canvas.height = 256;
  const context = canvas.getContext("2d");
  if (context) {
    context.fillStyle = "#102f60"; context.fillRect(0, 0, 128, 256);
    context.strokeStyle = "#395e86"; context.lineWidth = 1;
    for (let x = 0; x <= 128; x += 32) { context.beginPath(); context.moveTo(x, 0); context.lineTo(x, 256); context.stroke(); }
    for (let y = 0; y <= 256; y += 32) { context.beginPath(); context.moveTo(0, y); context.lineTo(128, y); context.stroke(); }
    context.strokeStyle = "#7897b2"; context.lineWidth = 2; context.strokeRect(1, 1, 126, 254);
  }
  const texture = new CanvasTexture(canvas); texture.colorSpace = SRGBColorSpace;
  return texture;
}

function PanelInstances({ zone, texture, onRow, onHover }: { zone: SceneZone; texture: CanvasTexture; onRow: (id: string) => void; onHover: (id: string | null) => void }) {
  const mesh = useRef<InstancedMesh>(null);
  const invalidate = useThree(state => state.invalidate);
  useLayoutEffect(() => {
    if (!mesh.current) return;
    const object = new Object3D(); const color = new Color();
    zone.panels.forEach((panel, index) => {
      object.position.set(...panel.position); object.rotation.set(panel.tilt, 0, 0); object.updateMatrix();
      mesh.current!.setMatrixAt(index, object.matrix);
      mesh.current!.setColorAt(index, color.set(panel.state === "STOWED" ? "#8296a3" : "#ffffff"));
    });
    mesh.current.instanceMatrix.needsUpdate = true;
    if (mesh.current.instanceColor) mesh.current.instanceColor.needsUpdate = true;
    mesh.current.computeBoundingSphere(); invalidate();
  }, [zone, invalidate]);
  function pick(event: ThreeEvent<MouseEvent>) {
    event.stopPropagation();
    if (event.delta > 5) return; // Camera drags must not become inspection clicks.
    const id = getInstanceRowId(zone, event.instanceId); if (id) onRow(id);
  }
  return <instancedMesh ref={mesh} args={[undefined, undefined, zone.panels.length]} onClick={pick} onPointerMove={event => { event.stopPropagation(); onHover(getInstanceRowId(zone, event.instanceId)); }} onPointerOut={() => onHover(null)}>
    <boxGeometry args={[sceneDimensions.panelWidth, 0.065, sceneDimensions.panelDepth]}/>
    <meshStandardMaterial map={texture} metalness={0.36} roughness={0.48}/>
  </instancedMesh>;
}

function Border({ center, width, depth, color, thickness = 0.12 }: { center: Vec3; width: number; depth: number; color: string; thickness?: number }) {
  return <group position={center}>{([-1, 1] as const).map(side => <group key={side}>
    <mesh position={[0, 0, side * depth / 2]}><boxGeometry args={[width, 0.06, thickness]}/><meshBasicMaterial color={color}/></mesh>
    <mesh position={[side * width / 2, 0, 0]}><boxGeometry args={[thickness, 0.06, depth]}/><meshBasicMaterial color={color}/></mesh>
  </group>)}</group>;
}
function RowAccents({ rows }: { rows: SceneRow[] }) {
  const indicators = useRef<InstancedMesh>(null);
  const supports = useRef<InstancedMesh>(null);
  const invalidate = useThree(state => state.invalidate);
  useLayoutEffect(() => {
    if (!indicators.current || !supports.current) return;
    const object = new Object3D(); const color = new Color();
    rows.forEach((row, index) => {
      object.position.set(row.position[0] - row.width / 2 - 0.5, 0.23, row.position[2]);
      object.scale.set(0.25, 0.1, row.row.current_state === "FAULT" ? 1.2 : 0.65); object.updateMatrix();
      indicators.current!.setMatrixAt(index, object.matrix);
      indicators.current!.setColorAt(index, color.set(resolveColor(rowStatePresentation[row.row.current_state].color)));
      object.position.set(row.position[0], 0.65, row.position[2]); object.scale.set(row.width, 0.18, 0.18); object.updateMatrix();
      supports.current!.setMatrixAt(index, object.matrix);
    });
    for (const mesh of [indicators.current, supports.current]) { mesh.instanceMatrix.needsUpdate = true; mesh.computeBoundingSphere(); }
    if (indicators.current.instanceColor) indicators.current.instanceColor.needsUpdate = true;
    invalidate();
  }, [rows, invalidate]);
  return <><instancedMesh ref={indicators} args={[undefined, undefined, rows.length]}><boxGeometry/><meshBasicMaterial/></instancedMesh><instancedMesh ref={supports} args={[undefined, undefined, rows.length]}><boxGeometry/><meshStandardMaterial color="#63788a" roughness={0.8}/></instancedMesh></>;
}
function RowMarker({ row, target, labels, portal }: { row: SceneRow; target: boolean; labels: boolean; portal: RefObject<HTMLDivElement> }) {
  const color = target ? "#35e6d0" : "#f0f6ff";
  const depth = target ? 2.35 : 2.05;
  return <group><group position={row.position} rotation={[row.tilt, 0, 0]}><Border center={[0, 0.08, 0]} width={row.width + (target ? 0.9 : 0.45)} depth={depth} color={color} thickness={target ? 0.15 : 0.08}/></group>
    {labels && <Html portal={portal} position={[row.position[0] + (target ? -1 : 1) * (row.width / 2 + 1), 2.1, row.position[2]]} center zIndexRange={[10, 0]} style={{ pointerEvents: "none" }}><span className={`f3-marker ${target ? "is-target" : ""}`}>{target ? "⊕ TARGET" : "◇ SELECTED"}<strong>{row.row.row_id}</strong></span></Html>}
  </group>;
}

function CameraRig({ layout, request }: { layout: FarmSceneLayout; request: { id: string | null; sequence: number } }) {
  const controls = useRef<ComponentRef<typeof OrbitControls>>(null);
  const { camera, size, invalidate, controls: activeControls } = useThree();
  const preset = useMemo(() => getCameraPreset(layout, size.width / Math.max(1, size.height), request.id), [layout, size.width, size.height, request.id]);
  useEffect(() => {
    // Apply the first preset after OrbitControls registers, so its initial update
    // cannot overwrite the overview with the default camera position.
    if (!activeControls || !size.width || !size.height) return;
    camera.position.set(...preset.position); camera.lookAt(...preset.target);
    controls.current?.target.set(...preset.target); controls.current?.update(); invalidate();
  }, [camera, invalidate, preset, request.sequence, activeControls, size.width, size.height]);
  const maxDistance = getCameraPreset(layout, size.width / Math.max(1, size.height)).distance * 1.8;
  return <OrbitControls ref={controls} makeDefault enableDamping={false} minDistance={12} maxDistance={maxDistance} minPolarAngle={0.12} maxPolarAngle={Math.PI / 2.15} onChange={() => invalidate()} />;
}
function ContextGuard({ onFailure }: { onFailure: () => void }) {
  const gl = useThree(state => state.gl);
  useEffect(() => {
    const canvas = gl.domElement;
    function lost(event: Event) { event.preventDefault(); onFailure(); }
    canvas.addEventListener("webglcontextlost", lost);
    return () => canvas.removeEventListener("webglcontextlost", lost);
  }, [gl, onFailure]);
  return null;
}
function FarmGeometry({ layout, props, labels, onHover, portal }: { layout: FarmSceneLayout; props: Farm3DProps; labels: boolean; onHover: (id: string | null) => void; portal: RefObject<HTMLDivElement> }) {
  const texture = useMemo(() => makePanelTexture(), []);
  useEffect(() => () => texture.dispose(), [texture]);
  const target = getSceneRow(layout, props.targetId); const selected = getSceneRow(layout, props.selectedRow);
  return <>
    <color attach="background" args={["#081823"]}/>
    <ambientLight intensity={0.7}/><hemisphereLight args={["#d5edff", "#183125", 1.1]}/><directionalLight position={[-20, 50, 20]} intensity={1.5}/>
    <mesh position={[0, -0.35, 0]}><boxGeometry args={[layout.bounds.width + 9, 0.5, layout.bounds.depth + 9]}/><meshStandardMaterial color="#132a30" roughness={0.95}/></mesh>
    <RowAccents rows={layout.rows}/>
    {layout.zones.map(zone => {
      const color = resolveColor(getZoneColor(zone.id));
      return <group key={zone.id}>
        <mesh position={zone.position}><boxGeometry args={[zone.width, 0.12, zone.depth]}/><meshStandardMaterial color={props.selectedZone === zone.id ? "#213c43" : "#182f35"}/></mesh>
        <Border center={[zone.position[0], 0.13, zone.position[2]]} width={zone.width} depth={zone.depth} color={color} thickness={props.selectedZone === zone.id ? 0.22 : 0.1}/>
        <PanelInstances zone={zone} texture={texture} onRow={props.onRow} onHover={onHover}/>
        {labels && <Html portal={portal} position={[zone.position[0], 2.5, zone.position[2] - zone.depth / 2 + 0.5]} center zIndexRange={[15, 0]}><button className="f3-zone-label" style={{ "--zone-color": getZoneColor(zone.id) } as CSSProperties} type="button" aria-pressed={props.selectedZone === zone.id} onClick={() => props.onZone(zone.id)}><strong>{formatZoneName(zone.id)}</strong><span>{zone.rows.length} rows · {zone.panels.length} panels</span></button></Html>}
      </group>;
    })}
    {target && <RowMarker row={target} target labels={labels} portal={portal}/>}
    {selected && <RowMarker row={selected} target={false} labels={labels && selected.row.row_id !== props.targetId} portal={portal}/>}
  </>;
}

export default function Farm3DScene(props: Farm3DProps) {
  // The sibling DOM portal is attached before Canvas mounts its scene children.
  const labelPortal = useRef<HTMLDivElement>(null!);
  const layout = useMemo(() => buildFarmSceneLayout(props.farm), [props.farm]);
  const [labels, setLabels] = useState(true);
  const [hovered, setHovered] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [request, setRequest] = useState({ id: null as string | null, sequence: 0 });
  const hoverRow = getSceneRow(layout, hovered)?.row;
  function focus(id: string | null) { setRequest(previous => ({ id, sequence: previous.sequence + 1 })); }
  return <FarmPanel title="3D Farm View" icon={Box} className="f3-panel" meta={<span className="fx-note">SCHEMATIC · {layout.panelCount.toLocaleString("en-US")} PANELS</span>}>
    <div className="f3-toolbar" aria-label="Camera and display controls">
      <button type="button" onClick={() => focus(null)}><RotateCcw size={14}/>Overview</button>
      <button type="button" onClick={() => focus(props.targetId)} disabled={!getSceneRow(layout, props.targetId)}><Crosshair size={14}/>Focus target</button>
      <button type="button" onClick={() => focus(props.selectedRow)} disabled={!getSceneRow(layout, props.selectedRow)}><ScanLine size={14}/>Focus selected</button>
      <button type="button" aria-pressed={labels} onClick={() => setLabels(value => !value)}><Eye size={14}/>{labels ? "Hide labels" : "Show labels"}</button>
    </div>
    {failed ? <SceneUnavailable onExit={props.onExit}/> : <div className="f3-canvas" data-hovered={!!hoverRow} role="group" aria-label="Schematic 3D farm. Drag to orbit, right-drag to pan, scroll or pinch to zoom. Use the row picker or table for keyboard inspection.">
      <Canvas frameloop="demand" dpr={[1, 1.5]} camera={{ fov: 42, near: 0.1, far: 2000 }} gl={{ antialias: true, powerPreference: "low-power" }} fallback={<SceneUnavailable onExit={props.onExit}/>}>
        <ContextGuard onFailure={() => setFailed(true)}/><CameraRig layout={layout} request={request}/><FarmGeometry layout={layout} props={props} labels={labels} onHover={setHovered} portal={labelPortal}/>
      </Canvas>
      <div className="f3-label-layer" ref={labelPortal}/>
      <div className="f3-scene-caption"><span>SCHEMATIC 3D VIEW</span><strong>{layout.zones.length} zones <i/> {layout.rows.length} rows</strong></div>
      <div className="f3-hover" aria-live="off">{hoverRow ? <><strong>{hoverRow.row_id}</strong> {formatAngle(hoverRow.angle_deg)} · {hoverRow.current_state} · Recorded {hoverRow.action}</> : "Drag to orbit · Scroll / pinch to zoom · Right-drag to pan"}</div>
    </div>}
    <div className="f3-legend"><span className="f3-target-key">⊕ Control target</span><span>◇ Selected row</span>{Object.entries(rowStatePresentation).map(([state, presentation]) => <span key={state}><presentation.icon size={12} style={{ color: presentation.color }}/>{state}</span>)}</div>
    <p className="f3-note">Schematic 3D layout. Zone membership, row state, and tilt come from the loaded farm contract; geographic coordinates are not available. Panel tilt uses one illustrative axis; geographic orientation is not provided. Scene lighting is illustrative, not solar-position data.</p>
  </FarmPanel>;
}

