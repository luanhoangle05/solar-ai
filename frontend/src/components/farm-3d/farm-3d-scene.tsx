"use client";

import { Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState, type ComponentRef, type CSSProperties, type RefObject } from "react";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { Cloud, Clouds, Environment, Html, OrbitControls, Sky as DreiSky } from "@react-three/drei";
import { AdditiveBlending, CanvasTexture, Color, InstancedMesh, MeshBasicMaterial, Object3D, RepeatWrapping, SRGBColorSpace, Vector3, type DirectionalLight, type Group, type Mesh, type ShaderMaterial } from "three";
import { Box, Crosshair, Eye, RotateCcw, ScanLine } from "lucide-react";
import { getZoneColor } from "@/config/zones";
import { rowStatePresentation } from "@/config/row-states";
import { buildFarmSceneLayout, cameraDirections, getCameraPreset, getCloudDriftX, getInstanceRowId, getRowCloseUpPreset, getSceneEnvironment, getSceneRow, getSunArcPosition, sceneDimensions, sceneSky, type FarmSceneLayout, type SceneEnvironment, type SceneRow, type SceneZone, type Vec3 } from "@/lib/farm-3d";
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

function PanelInstances({ zone, texture, scenic, onRow, onHover }: { zone: SceneZone; texture: CanvasTexture; scenic: boolean; onRow: (id: string) => void; onHover: (id: string | null) => void }) {
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
  return <instancedMesh ref={mesh} castShadow receiveShadow args={[undefined, undefined, zone.panels.length]} onClick={pick} onPointerMove={event => { event.stopPropagation(); onHover(getInstanceRowId(zone, event.instanceId)); }} onPointerOut={() => onHover(null)}>
    <boxGeometry args={[sceneDimensions.panelWidth, 0.065, sceneDimensions.panelDepth]}/>
    {scenic ? <meshPhysicalMaterial map={texture} metalness={0.15} roughness={0.16} clearcoat={1} clearcoatRoughness={0.06} envMapIntensity={0.85}/> : <meshStandardMaterial map={texture} metalness={0.36} roughness={0.48}/>}
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

// Procedural textures only: nothing is downloaded, so the scene works offline.
function makeRadialTexture(stops: [number, string][]) {
  const canvas = document.createElement("canvas"); canvas.width = canvas.height = 256;
  const context = canvas.getContext("2d");
  if (context) {
    const gradient = context.createRadialGradient(128, 128, 0, 128, 128, 128);
    stops.forEach(([offset, color]) => gradient.addColorStop(offset, color));
    context.fillStyle = gradient; context.fillRect(0, 0, 256, 256);
  }
  const texture = new CanvasTexture(canvas); texture.colorSpace = SRGBColorSpace;
  return texture;
}
/** Clouds stay bright white under the lowered scene exposure instead of turning grey. */
class CloudMaterial extends MeshBasicMaterial {
  constructor() { super(); this.toneMapped = false; }
}
/** Thin streaks like the diffraction spikes a camera lens puts around a bright sun. */
function makeSunRaysTexture() {
  const canvas = document.createElement("canvas"); canvas.width = canvas.height = 256;
  const context = canvas.getContext("2d");
  if (context) {
    context.translate(128, 128);
    for (let ray = 0; ray < 12; ray++) {
      const length = ray % 2 === 0 ? 124 : 76;
      const streak = context.createLinearGradient(0, 0, length, 0);
      streak.addColorStop(0, "rgba(255,250,235,.5)"); streak.addColorStop(0.35, "rgba(255,244,215,.14)"); streak.addColorStop(1, "rgba(255,240,205,0)");
      context.fillStyle = streak;
      context.beginPath(); context.moveTo(0, -1.6); context.lineTo(length, 0); context.lineTo(0, 1.6); context.closePath(); context.fill();
      context.rotate(Math.PI / 6);
    }
  }
  const texture = new CanvasTexture(canvas); texture.colorSpace = SRGBColorSpace;
  return texture;
}
/** Deterministic pseudo-random sequence, so textures are identical on every load. */
function sequence(seed: number) { let state = seed; return () => { state = (state * 1664525 + 1013904223) % 4294967296; return state / 4294967296; }; }
function makeCloudPuffUrl() {
  const canvas = document.createElement("canvas"); canvas.width = canvas.height = 256;
  const context = canvas.getContext("2d"); const next = sequence(7);
  if (context) for (let index = 0; index < 26; index++) {
    const x = 128 + (next() - 0.5) * 120, y = 128 + (next() - 0.5) * 90, radius = 34 + next() * 46;
    const gradient = context.createRadialGradient(x, y, 0, x, y, radius);
    gradient.addColorStop(0, "rgba(255,255,255,.5)"); gradient.addColorStop(1, "rgba(255,255,255,0)");
    context.fillStyle = gradient; context.fillRect(0, 0, 256, 256);
  }
  return canvas.toDataURL();
}
function makeGroundTexture(repeat: number) {
  const canvas = document.createElement("canvas"); canvas.width = canvas.height = 256;
  const context = canvas.getContext("2d"); const next = sequence(11);
  if (context) {
    context.fillStyle = "#5d6f3c"; context.fillRect(0, 0, 256, 256);
    const tones = ["#4c6131", "#6a7b44", "#77804d", "#55683a", "#8a8558", "#44592d"];
    for (let index = 0; index < 5200; index++) { context.fillStyle = tones[Math.floor(next() * tones.length)]; context.globalAlpha = 0.25 + next() * 0.45; context.fillRect(next() * 256, next() * 256, 1 + next() * 3, 1 + next() * 3); }
    context.globalAlpha = 1;
  }
  const texture = new CanvasTexture(canvas); texture.colorSpace = SRGBColorSpace;
  texture.wrapS = texture.wrapT = RepeatWrapping; texture.repeat.set(repeat, repeat); texture.anisotropy = 8;
  return texture;
}
/** A photovoltaic module: dark cells with busbars inside an aluminium frame. */
function makeModuleTexture() {
  const canvas = document.createElement("canvas"); canvas.width = 256; canvas.height = 384;
  const context = canvas.getContext("2d");
  if (context) {
    context.fillStyle = "#c9d2da"; context.fillRect(0, 0, 256, 384);
    context.fillStyle = "#0a1630"; context.fillRect(8, 8, 240, 368);
    for (let column = 0; column < 6; column++) for (let row = 0; row < 9; row++) {
      const x = 12 + column * 39, y = 12 + row * 40;
      const cell = context.createLinearGradient(x, y, x + 36, y + 37);
      cell.addColorStop(0, "#17346e"); cell.addColorStop(1, "#0d2150");
      context.fillStyle = cell; context.fillRect(x, y, 36, 37);
      context.strokeStyle = "rgba(190,205,225,.5)"; context.lineWidth = 0.6;
      for (const bar of [9, 18, 27]) { context.beginPath(); context.moveTo(x + bar, y); context.lineTo(x + bar, y + 37); context.stroke(); }
    }
  }
  const texture = new CanvasTexture(canvas); texture.colorSpace = SRGBColorSpace; texture.anisotropy = 8;
  return texture;
}
/**
 * Atmosphere, sun, clouds, ground and shadow-casting light. Haze and cloud count follow the payload's
 * cloud cover and light strength follows its GHI; the sun's place is illustrative (no solar position is supplied).
 */
function SceneSky({ environment, layout }: { environment: SceneEnvironment; layout: FarmSceneLayout }) {
  const reach = Math.max(layout.bounds.width, layout.bounds.depth);
  const glow = useMemo(() => makeRadialTexture([[0, "rgba(255,255,250,1)"], [0.045, "rgba(255,253,240,.98)"], [0.09, "rgba(255,244,212,.55)"], [0.2, "rgba(255,232,180,.2)"], [0.45, "rgba(255,224,170,.06)"], [1, "rgba(255,220,165,0)"]]), []);
  const rays = useMemo(() => makeSunRaysTexture(), []);
  const shade = useMemo(() => makeRadialTexture([[0, "rgba(0,0,0,.85)"], [0.55, "rgba(0,0,0,.4)"], [1, "rgba(0,0,0,0)"]]), []);
  const ground = useMemo(() => makeGroundTexture(reach * 1.4), [reach]);
  const cloudUrl = useMemo(() => makeCloudPuffUrl(), []);
  useEffect(() => () => { glow.dispose(); shade.dispose(); rays.dispose(); }, [glow, shade, rays]);
  useEffect(() => () => ground.dispose(), [ground]);
  const extent = environment.shadowExtent;
  const [sunX, sunY, sunZ] = environment.sunPosition;
  const sun = useRef<Group>(null), sunLight = useRef<DirectionalLight>(null), sky = useRef<Mesh | null>(null);
  // The light keeps the sun's direction but sits close enough for its shadow camera to cover the farm.
  const lightScale = reach * 3 / sceneSky.sunDistance;
  const cloudGroups = useRef<(Group | null)[]>([]), cloudShades = useRef<(Mesh | null)[]>([]);
  // Illustrative motion: the sun follows a slow arc and clouds drift with the supplied wind speed.
  // People who ask their system for reduced motion get the still scene.
  const still = useMemo(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches, []);
  useFrame(({ clock }) => {
    if (still) return;
    const seconds = clock.elapsedTime;
    const [x, y, z] = getSunArcPosition(seconds);
    sun.current?.position.set(x, y, z);
    sunLight.current?.position.set(x * lightScale, y * lightScale, z * lightScale);
    (sky.current?.material as ShaderMaterial | undefined)?.uniforms.sunPosition.value.set(x, y, z);
    environment.clouds.forEach((cloud, index) => {
      const cloudX = getCloudDriftX(cloud.position[0], environment, seconds);
      cloudGroups.current[index]?.position.setX(cloudX);
      // The ground shadow stays on the far side of the cloud from the sun.
      cloudShades.current[index]?.position.set(cloudX - x / y * cloud.position[1], 0.16, cloud.position[2] - z / y * cloud.position[1]);
    });
  });
  // About 14 degrees across at the sun's distance: a soft halo around the disc the sky shader draws.
  const glowSize = 46 + 30 * environment.brightness;
  // Memoized so the reflection cube map is rendered once, not on every hover re-render.
  const skyProps = useMemo(() => ({ distance: 900, sunPosition: environment.sunPosition, turbidity: 1.6 + 7 * environment.cover, rayleigh: 1.9 + environment.cover, mieCoefficient: 0.0035, mieDirectionalG: 0.82 }), [environment.sunPosition, environment.cover]);
  const reflectedSky = useMemo(() => <DreiSky {...skyProps}/>, [skyProps]);
  return <>
    <DreiSky ref={node => { sky.current = node; }} {...skyProps}/><Environment resolution={128}>{reflectedSky}</Environment>
    <fog attach="fog" args={["#e6e2d6", reach * 2.4, reach * 7]}/>
    <ambientLight intensity={0.4}/><hemisphereLight args={["#cfe2ff", "#7a8055", environment.skyIntensity * 1.5]}/>
    <directionalLight ref={sunLight} castShadow color="#ffdcae" position={[sunX * lightScale, sunY * lightScale, sunZ * lightScale]} intensity={environment.sunIntensity * 2.2}
      shadow-mapSize={[2048, 2048]} shadow-bias={-0.0004} shadow-normalBias={0.03} shadow-radius={3} shadow-camera-near={1} shadow-camera-far={reach * 8} shadow-camera-left={-extent} shadow-camera-right={extent} shadow-camera-top={extent} shadow-camera-bottom={-extent}/>
    <mesh receiveShadow rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.36, 0]}><planeGeometry args={[reach * 14, reach * 14]}/><meshStandardMaterial map={ground} roughness={1} envMapIntensity={0.5}/></mesh>
    <group ref={sun} position={environment.sunPosition}>
      <sprite scale={[glowSize, glowSize, 1]}><spriteMaterial map={glow} blending={AdditiveBlending} depthWrite={false} transparent opacity={0.6} toneMapped={false} fog={false}/></sprite>
      <sprite scale={[glowSize * 0.62, glowSize * 0.62, 1]}><spriteMaterial map={rays} blending={AdditiveBlending} depthWrite={false} transparent opacity={0.35 + 0.4 * environment.brightness} toneMapped={false} fog={false}/></sprite>
    </group>
    {/* The cloud texture decodes asynchronously; this boundary lets the farm render first and the clouds appear after. */}
    <Suspense fallback={null}><Clouds texture={cloudUrl} limit={700} material={CloudMaterial}>
      {environment.clouds.map((cloud, index) => <Cloud key={index} ref={node => { cloudGroups.current[index] = node; }} seed={index + 1} position={cloud.position} bounds={[3.4 * cloud.scale, 0.8 * cloud.scale, 1.9 * cloud.scale]} volume={4.4 * cloud.scale} segments={14} opacity={0.9} speed={0.14} fade={700} color="#f3f1ec"/>)}
    </Clouds></Suspense>
    {/* Cloud sprites cannot cast real shadows, so each gets a soft ground shadow offset away from the sun. */}
    {environment.clouds.map((cloud, index) => <mesh key={index} ref={node => { cloudShades.current[index] = node; }} rotation={[-Math.PI / 2, 0, 0]} position={[cloud.position[0] - sunX / sunY * cloud.position[1], 0.16, cloud.position[2] - sunZ / sunY * cloud.position[1]]}>
      <planeGeometry args={[11 * cloud.scale, 7 * cloud.scale]}/><meshBasicMaterial map={shade} transparent opacity={0.42} depthWrite={false}/>
    </mesh>)}
  </>;
}

function CameraRig({ layout, request, scenic }: { layout: FarmSceneLayout; request: { id: string | null; sequence: number }; scenic: boolean }) {
  const controls = useRef<ComponentRef<typeof OrbitControls>>(null);
  const { camera, size, invalidate, controls: activeControls } = useThree();
  const direction = scenic ? cameraDirections.scenic : cameraDirections.overview;
  // In the scenic view a clicked row gets a close, photo-like angle; elsewhere a row is framed whole.
  const preset = useMemo(() => (scenic ? getRowCloseUpPreset(layout, request.id) : null) ?? getCameraPreset(layout, size.width / Math.max(1, size.height), request.id, direction), [layout, size.width, size.height, request.id, direction, scenic]);
  // The scenic view glides to each new preset; `flight` holds the destination while a glide is in progress.
  const flight = useRef<{ position: Vector3; target: Vector3 } | null>(null);
  const placed = useRef(false);
  useEffect(() => {
    // Apply the first preset after OrbitControls registers, so its initial update
    // cannot overwrite the overview with the default camera position.
    if (!activeControls || !size.width || !size.height) return;
    if (scenic && placed.current) { flight.current = { position: new Vector3(...preset.position), target: new Vector3(...preset.target) }; return; }
    placed.current = true;
    camera.position.set(...preset.position); camera.lookAt(...preset.target);
    controls.current?.target.set(...preset.target); controls.current?.update(); invalidate();
  }, [camera, invalidate, preset, request.sequence, activeControls, size.width, size.height, scenic]);
  useFrame((_, delta) => {
    const goal = flight.current, orbit = controls.current;
    if (!goal || !orbit) return;
    const step = 1 - Math.exp(-3.2 * Math.min(delta, 0.1));
    camera.position.lerp(goal.position, step); orbit.target.lerp(goal.target, step); orbit.update();
    if (camera.position.distanceTo(goal.position) < 0.03) { camera.position.copy(goal.position); orbit.target.copy(goal.target); orbit.update(); flight.current = null; }
  });
  const maxDistance = Math.max(getCameraPreset(layout, size.width / Math.max(1, size.height)).distance, preset.distance) * 1.8;
  // Dragging takes over from a glide in progress.
  return <OrbitControls ref={controls} makeDefault enableDamping={false} minDistance={scenic ? 4 : 12} maxDistance={maxDistance} minPolarAngle={0.12} maxPolarAngle={Math.PI / 2.15} onStart={() => { flight.current = null; }} onChange={() => invalidate()} />;
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
function FarmGeometry({ layout, props, labels, onRow, onHover, portal, environment }: { layout: FarmSceneLayout; props: Farm3DProps; labels: boolean; onRow: (id: string) => void; onHover: (id: string | null) => void; portal: RefObject<HTMLDivElement>; environment: SceneEnvironment | null }) {
  const scenic = environment !== null;
  const texture = useMemo(() => scenic ? makeModuleTexture() : makePanelTexture(), [scenic]);
  useEffect(() => () => texture.dispose(), [texture]);
  const target = getSceneRow(layout, props.targetId); const selected = getSceneRow(layout, props.selectedRow);
  return <>
    {environment ? <SceneSky environment={environment} layout={layout}/> : <><color attach="background" args={["#081823"]}/>
    <ambientLight intensity={0.7}/><hemisphereLight args={["#d5edff", "#183125", 1.1]}/><directionalLight position={[-20, 50, 20]} intensity={1.5}/></>}
    <mesh receiveShadow position={[0, -0.35, 0]}><boxGeometry args={[layout.bounds.width + 9, 0.5, layout.bounds.depth + 9]}/><meshStandardMaterial color="#132a30" roughness={0.95}/></mesh>
    <RowAccents rows={layout.rows}/>
    {layout.zones.map(zone => {
      const color = resolveColor(getZoneColor(zone.id));
      return <group key={zone.id}>
        <mesh receiveShadow position={zone.position}><boxGeometry args={[zone.width, 0.12, zone.depth]}/><meshStandardMaterial color={props.selectedZone === zone.id ? "#213c43" : "#182f35"}/></mesh>
        <Border center={[zone.position[0], 0.13, zone.position[2]]} width={zone.width} depth={zone.depth} color={color} thickness={props.selectedZone === zone.id ? 0.22 : 0.1}/>
        <PanelInstances zone={zone} texture={texture} scenic={scenic} onRow={onRow} onHover={onHover}/>
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
  const cloudCoverPct = props.weather?.cloudCoverPct, ghiWm2 = props.weather?.ghiWm2, windSpeedKmh = props.weather?.windSpeedKmh;
  const { width: boundsWidth, depth: boundsDepth } = layout.bounds;
  const environment = useMemo(() => cloudCoverPct === undefined || ghiWm2 === undefined ? null : getSceneEnvironment({ cloudCoverPct, ghiWm2, windSpeedKmh }, { width: boundsWidth, depth: boundsDepth, center: [0, 0, 0] }), [cloudCoverPct, ghiWm2, windSpeedKmh, boundsWidth, boundsDepth]);
  const [labels, setLabels] = useState(true);
  const [hovered, setHovered] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [request, setRequest] = useState({ id: null as string | null, sequence: 0 });
  const hoverRow = getSceneRow(layout, hovered)?.row;
  function focus(id: string | null) { setRequest(previous => ({ id, sequence: previous.sequence + 1 })); }
  // In the scenic view, clicking a row also flies the camera in for a close look at it.
  function pickRow(id: string) { props.onRow(id); if (environment !== null) focus(id); }
  return <FarmPanel title="3D Farm View" icon={Box} className="f3-panel" meta={<span className="fx-note">SCHEMATIC · {layout.panelCount.toLocaleString("en-US")} PANELS</span>}>
    <div className="f3-toolbar" aria-label="Camera and display controls">
      <button type="button" onClick={() => focus(null)}><RotateCcw size={14}/>Overview</button>
      <button type="button" onClick={() => focus(props.targetId)} disabled={!getSceneRow(layout, props.targetId)}><Crosshair size={14}/>Focus target</button>
      <button type="button" onClick={() => focus(props.selectedRow)} disabled={!getSceneRow(layout, props.selectedRow)}><ScanLine size={14}/>Focus selected</button>
      <button type="button" aria-pressed={labels} onClick={() => setLabels(value => !value)}><Eye size={14}/>{labels ? "Hide labels" : "Show labels"}</button>
    </div>
    {failed ? <SceneUnavailable onExit={props.onExit}/> : <div className="f3-canvas" data-hovered={!!hoverRow} role="group" aria-label="Schematic 3D farm. Drag to orbit, right-drag to pan, scroll or pinch to zoom. Use the row picker or table for keyboard inspection.">
      <Canvas onCreated={state => { if (environment !== null) state.gl.toneMappingExposure = 0.42; }} shadows={environment !== null} frameloop={environment !== null ? "always" : "demand"} dpr={[1, 1.5]} camera={{ fov: 42, near: 0.1, far: 2000 }} gl={{ antialias: true, powerPreference: "low-power" }} fallback={<SceneUnavailable onExit={props.onExit}/>}>
        <ContextGuard onFailure={() => setFailed(true)}/><CameraRig layout={layout} request={request} scenic={environment !== null}/><FarmGeometry layout={layout} props={props} labels={labels} onRow={pickRow} onHover={setHovered} portal={labelPortal} environment={environment}/>
      </Canvas>
      <div className="f3-label-layer" ref={labelPortal}/>
      <div className="f3-scene-caption"><span>SCHEMATIC 3D VIEW</span><strong>{layout.zones.length} zones <i/> {layout.rows.length} rows</strong></div>
      <div className="f3-hover" aria-live="off">{hoverRow ? <><strong>{hoverRow.row_id}</strong> {formatAngle(hoverRow.angle_deg)} · {hoverRow.current_state} · Recorded {hoverRow.action}</> : "Drag to orbit · Scroll / pinch to zoom · Right-drag to pan"}</div>
    </div>}
    <div className="f3-legend"><span className="f3-target-key">⊕ Control target</span><span>◇ Selected row</span>{Object.entries(rowStatePresentation).map(([state, presentation]) => <span key={state}><presentation.icon size={12} style={{ color: presentation.color }}/>{state}</span>)}</div>
    <p className="f3-note">Schematic 3D layout. Zone membership, row state, and tilt come from the loaded farm contract; geographic coordinates are not available. Panel tilt uses one illustrative axis; geographic orientation is not provided. {environment ? `Cloud count and haze follow the supplied cloud cover (${environment.cloudCount} clouds drawn) and light strength follows the supplied GHI; cloud drift speed follows the supplied wind speed. The low sun, its slow sweep and the drift direction are illustrative animation: the payload has no solar position or wind direction and covers a single hour.` : "Scene lighting is illustrative, not solar-position data."}</p>
  </FarmPanel>;
}