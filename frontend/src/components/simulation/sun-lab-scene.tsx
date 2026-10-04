"use client";
import { useEffect, useMemo, useRef, useState, type ComponentRef, type KeyboardEvent } from "react";
import { Canvas, useFrame, type ThreeEvent } from "@react-three/fiber";
import { Environment, OrbitControls, Sky } from "@react-three/drei";
import { AdditiveBlending, DoubleSide, type Group } from "three";
import { makeModuleTexture, makeRadialTexture } from "@/components/farm-3d/farm-3d-scene";
import { sceneDimensions } from "@/lib/farm-3d";
import { clampSunAngle, getSunLabState, sunAngleFromPoint, sunLab, type EvaluatedRange, type SunLabState } from "@/lib/sun-lab";
import { formatAngle } from "@/lib/formatters";

// Presentation units, like the farm scene: none of these describe measured hardware.
const lab = { panels: 6, pivotHeight: 1.6, sunRadius: 6.4, sunGrabRadius: 1.1, keyStepDeg: 2, pageStepDeg: 10, camera: [9.2, 3.6, 9.4] as [number, number, number], lookAt: [0, 3.3, 0] as [number, number, number] };
// Rotation never turns the camera edge-on to the plane the sun moves in (from the side or from above), so a drag maps to a point on the arc; it also stays above the ground.
const orbit = { minDistance: 4, maxDistance: 40, minAzimuth: 0.3, maxAzimuth: Math.PI - 0.3, minPolar: 0.35, maxPolar: Math.PI / 2 - 0.02 };
const toRadians = (degrees: number) => degrees * Math.PI / 180;
const sunPosition = (sunDeg: number): [number, number, number] => [0, lab.pivotHeight + lab.sunRadius * Math.sin(toRadians(sunDeg)), lab.sunRadius * Math.cos(toRadians(sunDeg))];

/** The row of modules on its torque tube and posts; it glides to each new tilt instead of snapping. */
function Row({ tiltDeg }: { tiltDeg: number }) {
  const table = useRef<Group>(null);
  const texture = useMemo(() => makeModuleTexture(), []);
  // Only the starting tilt is set as a prop; later tilts are eased in by the frame loop, so the row turns instead of snapping.
  const [startRotation] = useState<[number, number, number]>(() => [toRadians(tiltDeg), 0, 0]);
  useEffect(() => () => texture.dispose(), [texture]);
  useFrame((_, delta) => {
    if (!table.current) return;
    const goal = toRadians(tiltDeg), step = 1 - Math.exp(-9 * Math.min(delta, 0.1));
    table.current.rotation.x += (goal - table.current.rotation.x) * step;
  });
  const { panelWidth, panelDepth, panelPitch } = sceneDimensions;
  const width = (lab.panels - 1) * panelPitch + panelWidth;
  return <group>
    {[-width / 2 + 0.5, 0, width / 2 - 0.5].map(x => <mesh key={x} castShadow position={[x, lab.pivotHeight / 2, 0]}><cylinderGeometry args={[0.07, 0.09, lab.pivotHeight, 12]}/><meshStandardMaterial color="#8d99a3" metalness={0.6} roughness={0.45}/></mesh>)}
    <group ref={table} position={[0, lab.pivotHeight, 0]} rotation={startRotation}>
      <mesh castShadow rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[0.07, 0.07, width + 0.3, 12]}/><meshStandardMaterial color="#7f8b95" metalness={0.6} roughness={0.45}/></mesh>
      {Array.from({ length: lab.panels }, (_, index) => <mesh key={index} castShadow receiveShadow position={[(index - (lab.panels - 1) / 2) * panelPitch, 0.1, 0]}>
        <boxGeometry args={[panelWidth, 0.065, panelDepth]}/><meshPhysicalMaterial map={texture} metalness={0.15} roughness={0.16} clearcoat={1} clearcoatRoughness={0.06} envMapIntensity={0.9}/>
      </mesh>)}
    </group>
  </group>;
}

function Scene({ sunDeg, tiltDeg, onSun, resetSignal }: { sunDeg: number; tiltDeg: number; onSun: (sunDeg: number) => void; resetSignal: number }) {
  const [dragging, setDragging] = useState(false);
  const controls = useRef<ComponentRef<typeof OrbitControls>>(null);
  // Remember the opening view once, so "Reset view" can return to it.
  useEffect(() => { controls.current?.saveState(); }, []);
  useEffect(() => { if (resetSignal > 0) controls.current?.reset(); }, [resetSignal]);
  const glow = useMemo(() => makeRadialTexture([[0, "rgba(255,255,250,1)"], [0.06, "rgba(255,252,236,.95)"], [0.14, "rgba(255,240,200,.5)"], [0.4, "rgba(255,226,170,.1)"], [1, "rgba(255,220,165,0)"]]), []);
  useEffect(() => () => glow.dispose(), [glow]);
  const position = sunPosition(sunDeg);
  // The reflection map only needs the sky's general look, so it keeps the starting sun.
  const reflectedSky = useMemo(() => <Sky distance={900} sunPosition={sunPosition(sunLab.startSunDeg)} turbidity={2.2} rayleigh={1.6}/>, []);
  function place(event: ThreeEvent<PointerEvent>) { event.stopPropagation(); onSun(sunAngleFromPoint(event.point.y, event.point.z, lab.pivotHeight)); }
  // Holding the sun with the main button moves the sun; the camera controls are switched off at once so the same press does not also turn the view.
  // (The scene's pointer handlers run before the controls' own, and the controls ignore a press while disabled.)
  function grab(event: ThreeEvent<PointerEvent>) { if (event.button !== 0) return; event.stopPropagation(); if (controls.current) controls.current.enabled = false; setDragging(true); }
  useEffect(() => {
    if (!dragging) return;
    const stop = () => setDragging(false);
    window.addEventListener("pointerup", stop); window.addEventListener("pointercancel", stop);
    return () => { window.removeEventListener("pointerup", stop); window.removeEventListener("pointercancel", stop); };
  }, [dragging]);
  return <>
    <OrbitControls ref={controls} enabled={!dragging} target={lab.lookAt} enablePan minDistance={orbit.minDistance} maxDistance={orbit.maxDistance} minAzimuthAngle={orbit.minAzimuth} maxAzimuthAngle={orbit.maxAzimuth} minPolarAngle={orbit.minPolar} maxPolarAngle={orbit.maxPolar}/>
    <Sky distance={900} sunPosition={position} turbidity={1.6} rayleigh={2.2} mieCoefficient={0.003} mieDirectionalG={0.8}/>
    <Environment resolution={128}>{reflectedSky}</Environment>
    <ambientLight intensity={0.3}/><hemisphereLight args={["#cfe2ff", "#7a8055", 1.3]}/>
    <directionalLight castShadow color="#ffe6c4" position={[position[0] + 1.5, position[1], position[2]]} intensity={4.4} shadow-mapSize={[2048, 2048]} shadow-bias={-0.0004} shadow-normalBias={0.03} shadow-camera-near={1} shadow-camera-far={40} shadow-camera-left={-12} shadow-camera-right={12} shadow-camera-top={12} shadow-camera-bottom={-12}/>
    <mesh receiveShadow rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[400, 400]}/><meshStandardMaterial color="#5f733f" roughness={1}/></mesh>
    <Row tiltDeg={tiltDeg}/>
    {/* The path the sun moves along. */}
    <mesh position={[0, lab.pivotHeight, 0]} rotation={[0, -Math.PI / 2, 0]}><torusGeometry args={[lab.sunRadius, 0.025, 8, 96, Math.PI]}/><meshBasicMaterial color="#ffe9b0" transparent opacity={0.45} toneMapped={false}/></mesh>
    {/* While the sun is held, the pointer is read on the whole plane the sun moves in, so the drag keeps working when the pointer leaves the sun. */}
    <mesh position={[0, lab.pivotHeight, 0]} rotation={[0, Math.PI / 2, 0]} onPointerMove={event => { if (dragging) place(event); }}>
      <planeGeometry args={[60, 60]}/><meshBasicMaterial transparent opacity={0} depthWrite={false} side={DoubleSide}/>
    </mesh>
    <group position={position}>
      {/* A generous invisible grab area around the sun. */}
      <mesh onPointerDown={grab}><sphereGeometry args={[lab.sunGrabRadius, 16, 16]}/><meshBasicMaterial transparent opacity={0} depthWrite={false}/></mesh>
      <mesh><sphereGeometry args={[0.55, 32, 32]}/><meshBasicMaterial color="#fffdf2" toneMapped={false}/></mesh>
      <sprite scale={[4.2, 4.2, 1]}><spriteMaterial map={glow} blending={AdditiveBlending} depthWrite={false} transparent toneMapped={false}/></sprite>
    </group>
  </>;
}

/**
 * One row and a sun the viewer can hold and move; the row turns to face it. The view itself orbits, zooms and pans like the 3D farm.
 * Everything shown is geometry computed here for illustration; no payload value is changed or implied.
 */
export default function SunLabScene({ rowId, recordedAngle, recommendedAngle, evaluated }: { rowId: string; recordedAngle: number; recommendedAngle: number | null; evaluated: EvaluatedRange | null }) {
  const [sunDeg, setSunDeg] = useState<number>(sunLab.startSunDeg);
  const [resetSignal, setResetSignal] = useState(0);
  const state: SunLabState = getSunLabState(sunDeg, evaluated);
  // Keyboard equivalent of dragging the sun. A larger sun angle is further right in the opening view.
  const keySteps: Record<string, number> = { ArrowRight: lab.keyStepDeg, ArrowUp: lab.keyStepDeg, ArrowLeft: -lab.keyStepDeg, ArrowDown: -lab.keyStepDeg, PageUp: lab.pageStepDeg, PageDown: -lab.pageStepDeg };
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Home" || event.key === "End") { event.preventDefault(); setSunDeg(event.key === "Home" ? sunLab.minSunDeg : sunLab.maxSunDeg); return; }
    const step = keySteps[event.key];
    if (step === undefined) return;
    event.preventDefault(); setSunDeg(current => clampSunAngle(current + step));
  }
  return <div className="lab">
    <div className="lab-canvas" role="group" aria-label="Single-row sun lab. Hold the sun and move it along its arc. Drag elsewhere to rotate the view, scroll to zoom, right-drag to move.">
      <div className="lab-stage" role="slider" tabIndex={0} onKeyDown={onKeyDown} aria-label="Sun position" aria-valuemin={sunLab.minSunDeg} aria-valuemax={sunLab.maxSunDeg} aria-valuenow={Math.round(state.sunDeg)} aria-valuetext={`Sun ${Math.round(state.elevationDeg)} degrees high, ${state.side === "behind" ? "behind" : "in front of"} the row; panel tilt ${Math.round(state.tiltDeg)} degrees`}>
      <Canvas shadows dpr={[1, 1.5]} camera={{ fov: 44, near: 0.1, far: 2000, position: lab.camera }} onCreated={({ gl }) => { gl.toneMappingExposure = 0.36; }}>
        <Scene sunDeg={state.sunDeg} tiltDeg={state.tiltDeg} onSun={setSunDeg} resetSignal={resetSignal}/>
      </Canvas>
      </div>
      <button type="button" className="lab-reset" onClick={() => setResetSignal(count => count + 1)}>Reset view</button>
      <div className="lab-tag">SUN LAB · {rowId} · geometric illustration, not a model prediction</div>
      <dl className="lab-readout">
        <div><dt>Sun height</dt><dd>{formatAngle(Math.round(state.elevationDeg))}<small>{state.side === "behind" ? "behind the row" : "in front of the row"}</small></dd></div>
        <div data-tone="tilt"><dt>Panel tilt</dt><dd>{formatAngle(Math.round(state.tiltDeg))}<small>{state.withinEvaluatedRange === false && evaluated ? `outside evaluated ${formatAngle(evaluated.minDeg)}–${formatAngle(evaluated.maxDeg)}` : state.withinEvaluatedRange ? "within evaluated range" : "faces the sun"}</small></dd></div>
        <div><dt>Facing the sun</dt><dd>{state.alignmentPct}%<small>{formatAngle(Math.round(state.incidenceDeg))} off square</small></dd></div>
      </dl>
    </div>
    <p className="lab-note">Hold the sun and move it: the row turns so its face points at the sun, and lies flat once the sun passes behind it. This is geometry only. The recorded angle for {rowId} is {formatAngle(recordedAngle)}{recommendedAngle !== null ? ` and the backend recommends ${formatAngle(recommendedAngle)}` : ""}; the backend weighs predicted energy against movement cost, which this view does not model.</p>
  </div>;
}
