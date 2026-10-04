"use client";
import { useEffect, useMemo, useRef, useState, type ComponentRef, type KeyboardEvent } from "react";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { Environment, OrbitControls, Sky } from "@react-three/drei";
import { AdditiveBlending, Plane, Raycaster, Vector2, Vector3, type Group } from "three";
import { makeModuleTexture, makeRadialTexture } from "@/components/farm-3d/farm-3d-scene";
import { sceneDimensions } from "@/lib/farm-3d";
import { clampSunPoint, getSunLabState, sunLab, type EvaluatedRange, type SunLabState, type SunPoint } from "@/lib/sun-lab";
import { formatAngle } from "@/lib/formatters";

// Presentation units, like the farm scene: none of these describe measured hardware.
const lab = { panels: 6, pivotHeight: 1.6, sunGrabRadius: 1.7, glowSize: 4.2, heldGlowSize: 5.6, keyStep: 0.4, camera: [9.2, 3.6, 9.4] as [number, number, number], lookAt: [0, 3.3, 0] as [number, number, number] };
// The view turns all the way round the row; it only stays above the ground.
const orbit = { minDistance: 4, maxDistance: 45, maxPolar: Math.PI / 2 - 0.02 };
type SunGrip = "free" | "hover" | "held";
const toRadians = (degrees: number) => degrees * Math.PI / 180;
const toScene = (sun: SunPoint): [number, number, number] => [sun.side, lab.pivotHeight + sun.height, sun.forward];
// Keyboard equivalent of dragging the sun. In the opening view, further behind the row is further right.
const keySteps: Record<string, Partial<SunPoint>> = { ArrowRight: { forward: -lab.keyStep }, ArrowLeft: { forward: lab.keyStep }, ArrowUp: { height: lab.keyStep }, ArrowDown: { height: -lab.keyStep }, PageUp: { side: lab.keyStep }, PageDown: { side: -lab.keyStep } };

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

function Scene({ sun, tiltDeg, onSun, onGrip, resetSignal }: { sun: SunPoint; tiltDeg: number; onSun: (sun: SunPoint) => void; onGrip: (grip: SunGrip) => void; resetSignal: number }) {
  const [dragging, setDragging] = useState(false);
  const [hovered, setHovered] = useState(false);
  const controls = useRef<ComponentRef<typeof OrbitControls>>(null);
  const camera = useThree(state => state.camera), canvas = useThree(state => state.gl.domElement);
  const endDrag = useRef<(() => void) | null>(null);
  useEffect(() => () => endDrag.current?.(), []);
  // The page shows a grab cursor while the sun is under the pointer or held.
  useEffect(() => { onGrip(dragging ? "held" : hovered ? "hover" : "free"); }, [onGrip, dragging, hovered]);
  // Remember the opening view once, so "Reset view" can return to it.
  useEffect(() => { controls.current?.saveState(); }, []);
  useEffect(() => { if (resetSignal > 0) controls.current?.reset(); }, [resetSignal]);
  const glow = useMemo(() => makeRadialTexture([[0, "rgba(255,255,250,1)"], [0.06, "rgba(255,252,236,.95)"], [0.14, "rgba(255,240,200,.5)"], [0.4, "rgba(255,226,170,.1)"], [1, "rgba(255,220,165,0)"]]), []);
  useEffect(() => () => glow.dispose(), [glow]);
  const position = toScene(sun);
  // The reflection map only needs the sky's general look, so it keeps the starting sun.
  const reflectedSky = useMemo(() => <Sky distance={900} sunPosition={toScene(sunLab.start)} turbidity={2.2} rayleigh={1.6}/>, []);
  // Holding the sun with the main button moves the sun; the camera controls are switched off at once so the same press does not also turn the view.
  // The sun slides across the plane that faces the viewer, so it goes wherever the pointer goes; turning the view first lets it be moved in any direction.
  // The pointer is followed on the window itself, so the drag keeps working until the button is released.
  function grab(event: ThreeEvent<PointerEvent>) {
    if (event.nativeEvent.button !== 0 || endDrag.current) return;
    event.stopPropagation();
    if (controls.current) controls.current.enabled = false;
    const held = new Vector3(...position), raycaster = new Raycaster(), pointer = new Vector2(), hit = new Vector3();
    const dragPlane = new Plane().setFromNormalAndCoplanarPoint(camera.getWorldDirection(new Vector3()), held);
    // Where on the sun it was picked up, so it does not jump to centre itself under the pointer.
    const offset = event.ray.intersectPlane(dragPlane, hit) ? held.clone().sub(hit) : new Vector3();
    const follow = (move: PointerEvent) => {
      const box = canvas.getBoundingClientRect();
      pointer.set((move.clientX - box.left) / box.width * 2 - 1, -((move.clientY - box.top) / box.height) * 2 + 1);
      raycaster.setFromCamera(pointer, camera);
      if (!raycaster.ray.intersectPlane(dragPlane, hit)) return;
      hit.add(offset); onSun({ side: hit.x, height: hit.y - lab.pivotHeight, forward: hit.z });
    };
    const stop = () => {
      window.removeEventListener("pointermove", follow); window.removeEventListener("pointerup", stop); window.removeEventListener("pointercancel", stop);
      endDrag.current = null; if (controls.current) controls.current.enabled = true; setDragging(false);
    };
    window.addEventListener("pointermove", follow); window.addEventListener("pointerup", stop); window.addEventListener("pointercancel", stop);
    endDrag.current = stop; setDragging(true);
  }
  return <>
    <OrbitControls ref={controls} enabled={!dragging} target={lab.lookAt} enablePan minDistance={orbit.minDistance} maxDistance={orbit.maxDistance} maxPolarAngle={orbit.maxPolar}/>
    <Sky distance={900} sunPosition={position} turbidity={1.6} rayleigh={2.2} mieCoefficient={0.003} mieDirectionalG={0.8}/>
    <Environment resolution={128}>{reflectedSky}</Environment>
    <ambientLight intensity={0.3}/><hemisphereLight args={["#cfe2ff", "#7a8055", 1.3]}/>
    <directionalLight castShadow color="#ffe6c4" position={position} intensity={4.4} shadow-mapSize={[2048, 2048]} shadow-bias={-0.0004} shadow-normalBias={0.03} shadow-camera-near={0.5} shadow-camera-far={50} shadow-camera-left={-12} shadow-camera-right={12} shadow-camera-top={12} shadow-camera-bottom={-12}/>
    <mesh receiveShadow rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[400, 400]}/><meshStandardMaterial color="#5f733f" roughness={1}/></mesh>
    <Row tiltDeg={tiltDeg}/>
    <group position={position}>
      {/* A generous invisible grab area around the sun. */}
      <mesh onPointerDown={grab} onPointerOver={() => setHovered(true)} onPointerOut={() => setHovered(false)}><sphereGeometry args={[lab.sunGrabRadius, 16, 16]}/><meshBasicMaterial transparent opacity={0} depthWrite={false}/></mesh>
      <mesh><sphereGeometry args={[0.55, 32, 32]}/><meshBasicMaterial color="#fffdf2" toneMapped={false}/></mesh>
      {/* The glow swells while the sun is under the pointer or held, to show it can be moved. */}
      <sprite scale={hovered || dragging ? [lab.heldGlowSize, lab.heldGlowSize, 1] : [lab.glowSize, lab.glowSize, 1]}><spriteMaterial map={glow} blending={AdditiveBlending} depthWrite={false} transparent toneMapped={false}/></sprite>
    </group>
  </>;
}

function describeTilt(state: SunLabState, evaluated: EvaluatedRange | null): string {
  const lean = state.tiltDeg < 0 ? "leaning back" : "leaning forward";
  if (state.withinEvaluatedRange === null || !evaluated) return lean;
  return state.withinEvaluatedRange ? "within evaluated range" : `${lean} · outside evaluated ${formatAngle(evaluated.minDeg)}–${formatAngle(evaluated.maxDeg)}`;
}

/**
 * One row and a sun the viewer can hold and move anywhere; the row turns through a full 180 degrees to face it.
 * The view itself orbits, zooms and pans like the 3D farm.
 * Everything shown is geometry computed here for illustration; no payload value is changed or implied.
 */
export default function SunLabScene({ rowId, recordedAngle, recommendedAngle, evaluated }: { rowId: string; recordedAngle: number; recommendedAngle: number | null; evaluated: EvaluatedRange | null }) {
  const [sun, setSun] = useState<SunPoint>(sunLab.start);
  const [resetSignal, setResetSignal] = useState(0);
  const [grip, setGrip] = useState<SunGrip>("free");
  const state: SunLabState = getSunLabState(sun, evaluated);
  const placement = state.side === "behind" ? "behind the row" : "in front of the row";
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Home") { event.preventDefault(); setSun(sunLab.start); return; }
    const step = keySteps[event.key];
    if (!step) return;
    event.preventDefault();
    setSun(current => clampSunPoint({ side: current.side + (step.side ?? 0), height: current.height + (step.height ?? 0), forward: current.forward + (step.forward ?? 0) }));
  }
  return <div className="lab">
    <div className="lab-canvas" role="group" aria-label="Single-row sun lab">
      <div className="lab-stage" data-grip={grip} role="application" tabIndex={0} onKeyDown={onKeyDown} aria-label={`Sun and panel row. Hold the sun and move it anywhere; drag elsewhere to rotate the view, scroll to zoom, right-drag to move. Arrow keys move the sun, Page Up and Page Down move it along the row, Home puts it back. Sun ${Math.round(state.elevationDeg)} degrees high, ${placement}; panel tilt ${Math.round(state.tiltDeg)} degrees.`}>
      <Canvas shadows dpr={[1, 1.5]} camera={{ fov: 44, near: 0.1, far: 2000, position: lab.camera }} onCreated={({ gl }) => { gl.toneMappingExposure = 0.36; }}>
        <Scene sun={state.point} tiltDeg={state.tiltDeg} onSun={next => setSun(clampSunPoint(next))} onGrip={setGrip} resetSignal={resetSignal}/>
      </Canvas>
      </div>
      <button type="button" className="lab-reset" onClick={() => { setSun(sunLab.start); setResetSignal(count => count + 1); }}>Reset view</button>
      <div className="lab-tag">SUN LAB · {rowId} · geometric illustration, not a model prediction</div>
      <dl className="lab-readout">
        <div><dt>Sun height</dt><dd>{formatAngle(Math.round(state.elevationDeg))}<small>{placement}</small></dd></div>
        <div data-tone="tilt"><dt>Panel tilt</dt><dd>{formatAngle(Math.round(state.tiltDeg))}<small>{describeTilt(state, evaluated)}</small></dd></div>
        <div><dt>Facing the sun</dt><dd>{state.alignmentPct}%<small>{formatAngle(Math.round(state.incidenceDeg))} off square</small></dd></div>
      </dl>
    </div>
    <p className="lab-note">Hold the sun and move it anywhere: the row turns through a full 180° so its face points at the sun, leaning back when the sun is behind it. The row turns about one axis, so a sun off to one side is never faced squarely. This is geometry only. The recorded angle for {rowId} is {formatAngle(recordedAngle)}{recommendedAngle !== null ? ` and the backend recommends ${formatAngle(recommendedAngle)}` : ""}; the backend weighs predicted energy against movement cost, which this view does not model.</p>
  </div>;
}
