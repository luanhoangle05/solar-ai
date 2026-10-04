import type { FarmRow, FarmStatus } from "../types/solar";
import { getZoneRows } from "./farm";

export type Vec3 = [number, number, number];
// Presentation units only: none of these distances describe measured farm geometry.
export const sceneDimensions = { panelWidth: 1.2, panelDepth: 1.8, panelPitch: 1.32, rowPitch: 2.2, margin: 2.4, corridor: 5, elevation: 1.25 } as const;
export const degreesToRadians = (degrees: number) => degrees * Math.PI / 180;
export type SceneRow = { row: FarmRow; index: number; position: Vec3; width: number; tilt: number; firstInstance: number; instanceCount: number };
export type PanelInstance = { rowId: string; panelIndex: number; position: Vec3; tilt: number; state: FarmRow["current_state"] };
export type SceneZone = { id: string; position: Vec3; width: number; depth: number; rows: SceneRow[]; panels: PanelInstance[] };
export type FarmSceneLayout = { zones: SceneZone[]; rows: SceneRow[]; panelCount: number; bounds: { width: number; depth: number; center: Vec3 } };

export function buildFarmSceneLayout(farm: FarmStatus): FarmSceneLayout {
  const d = sceneDimensions;
  const memberships = farm.zones.map(zone => getZoneRows(farm, zone));
  const maxPanels = Math.max(0, ...memberships.flat().map(row => row.panel_count));
  const maxRows = Math.max(0, ...memberships.map(rows => rows.length));
  const width = Math.max(d.panelWidth, (maxPanels - 1) * d.panelPitch + d.panelWidth) + d.margin * 2;
  const depth = Math.max(d.panelDepth, (maxRows - 1) * d.rowPitch + d.panelDepth) + d.margin * 2;
  const columns = Math.min(2, farm.zones.length);
  const bands = Math.ceil(farm.zones.length / 2);
  const zones: SceneZone[] = farm.zones.map((zone, index) => {
    const x = ((index % 2) - (columns - 1) / 2) * (width + d.corridor);
    const z = (Math.floor(index / 2) - (bands - 1) / 2) * (depth + d.corridor);
    const panels: PanelInstance[] = [];
    const rows: SceneRow[] = memberships[index].map((row, rowIndex) => {
      const position: Vec3 = [x, d.elevation, z + (rowIndex - (memberships[index].length - 1) / 2) * d.rowPitch];
      const tilt = degreesToRadians(row.angle_deg);
      const firstInstance = panels.length;
      for (let panelIndex = 0; panelIndex < row.panel_count; panelIndex++) {
        panels.push({ rowId: row.row_id, panelIndex, position: [x + (panelIndex - (row.panel_count - 1) / 2) * d.panelPitch, position[1], position[2]], tilt, state: row.current_state });
      }
      return { row, index: rowIndex, position, tilt, width: Math.max(0, (row.panel_count - 1) * d.panelPitch + d.panelWidth), firstInstance, instanceCount: row.panel_count };
    });
    return { id: zone.zone_id, position: [x, 0, z], width, depth, rows, panels };
  });
  return { zones, rows: zones.flatMap(zone => zone.rows), panelCount: zones.reduce((sum, zone) => sum + zone.panels.length, 0), bounds: { width: columns ? columns * width + (columns - 1) * d.corridor : 0, depth: bands ? bands * depth + (bands - 1) * d.corridor : 0, center: [0, 0, 0] } };
}

export function getInstanceRowId(zone: SceneZone, instanceId: number | undefined) {
  return instanceId !== undefined && Number.isInteger(instanceId) ? zone.panels[instanceId]?.rowId ?? null : null;
}
export function getSceneRow(layout: FarmSceneLayout, id: string | null) {
  return layout.rows.find(item => item.row.row_id === id) ?? null;
}
/** Default overview direction, and a near-ground one that puts the horizon and sky in the top of the frame. */
export const cameraDirections = { overview: [0.18, 0.72, 0.67], scenic: [0.35, 0.15, 0.92] } as const satisfies Record<string, Vec3>;
export function getCameraPreset(layout: FarmSceneLayout, aspect: number, rowId: string | null = null, from: Vec3 = cameraDirections.overview): { position: Vec3; target: Vec3; distance: number } {
  const row = getSceneRow(layout, rowId);
  const target: Vec3 = row ? [...row.position] : [...layout.bounds.center];
  // Fit all bounding-box corners against both camera frustum axes.
  const direction: Vec3 = [...from];
  const length = Math.hypot(...direction); direction.forEach((value, i) => { direction[i] = value / length; });
  const horizontal = Math.hypot(direction[0], direction[2]);
  const right: Vec3 = [direction[2] / horizontal, 0, -direction[0] / horizontal];
  const up: Vec3 = [direction[1] * right[2], horizontal, -direction[1] * right[0]];
  const halfWidth = row ? row.width / 2 + 3 : Math.max(10, layout.bounds.width / 2 + 3);
  const halfDepth = row ? 5 : Math.max(10, layout.bounds.depth / 2 + 3);
  const tanVertical = Math.tan(degreesToRadians(21));
  const tanHorizontal = tanVertical * Math.max(0.1, aspect);
  let distance = 12;
  for (const x of [-halfWidth, halfWidth]) for (const z of [-halfDepth, halfDepth]) for (const y of [0, 3]) {
    const depth = x * direction[0] + y * direction[1] + z * direction[2];
    distance = Math.max(distance, depth + Math.abs(x * right[0] + z * right[2]) / tanHorizontal, depth + Math.abs(x * up[0] + y * up[1] + z * up[2]) / tanVertical);
  }
  distance *= 0.96;
  return { target, distance, position: [target[0] + distance * direction[0], target[1] + distance * direction[1], target[2] + distance * direction[2]] };
}

/** A photo-like three-quarter view of one row: in front of the tilted panel faces, off to one side and a little above them. */
export const rowCloseUp = { direction: [0.6, 0.45, 0.66], distance: 8 } as const satisfies { direction: Vec3; distance: number };
export function getRowCloseUpPreset(layout: FarmSceneLayout, rowId: string | null): { position: Vec3; target: Vec3; distance: number } | null {
  const row = getSceneRow(layout, rowId);
  if (!row) return null;
  const length = Math.hypot(...rowCloseUp.direction), distance = rowCloseUp.distance;
  const [x, y, z] = row.position;
  return { target: [x, y, z], distance, position: [x + rowCloseUp.direction[0] / length * distance, y + rowCloseUp.direction[1] / length * distance, z + rowCloseUp.direction[2] / length * distance] };
}

/** Weather values the scenic 3D view reacts to. Both come straight from the payload's current_weather. */
export type SceneWeather = { cloudCoverPct: number; ghiWm2: number; windSpeedKmh?: number };
export type SceneCloud = { position: Vec3; scale: number };
export const sceneSky = { maxClouds: 48, cloudHeight: 16, fullSunGhi: 1000, sunPeriodSeconds: 120, maxWindKmh: 120, sunDistance: 400, sunSweepDeg: 26, sunMinElevationDeg: 5, sunLiftDeg: 5 } as const;
const fraction = (value: number) => value - Math.floor(value);
/**
 * Presentation of the supplied weather. Cloud count follows cloud cover and light strength follows GHI.
 * The payload has no sun position, so where the sun sits is illustrative and fixed.
 */
export function getSceneEnvironment(weather: SceneWeather, bounds: FarmSceneLayout["bounds"]) {
  const cover = Math.min(1, Math.max(0, weather.cloudCoverPct / 100));
  const brightness = Math.min(1, Math.max(0, weather.ghiWm2 / sceneSky.fullSunGhi));
  const cloudCount = Math.ceil(cover * sceneSky.maxClouds);
  // Clouds sit high and mostly beyond the farm, so from the low camera they appear in the sky.
  const spanX = (bounds.width / 2 + 12) * 2.4, spanZ = bounds.depth / 2 + 8;
  // Deterministic placement: the same payload always draws the same sky.
  const clouds: SceneCloud[] = Array.from({ length: cloudCount }, (_, index) => ({
    position: [(fraction(Math.sin(index * 12.9898 + 1.3) * 43758.5453) * 2 - 1) * spanX, sceneSky.cloudHeight + fraction(Math.sin(index * 4.1 + 2.7) * 1375.31) * 14, spanZ * (0.4 - fraction(Math.sin(index * 78.233 + 0.7) * 24634.6345) * 4.4)],
    scale: 2.4 + fraction(Math.sin(index * 3.7 + 5.1) * 9871.13) * 2.6,
  }));
  const sunPosition = getSunArcPosition(0);
  // Clouds drift faster in stronger supplied wind; the payload has no wind direction, so the heading is illustrative.
  const cloudDrift = 0.25 + 0.03 * Math.min(sceneSky.maxWindKmh, Math.max(0, weather.windSpeedKmh ?? 0));
  return { cover, cloudCount, clouds, sunPosition, cloudDrift, driftSpan: spanX, brightness, sunIntensity: 0.8 + 3 * brightness, skyIntensity: 0.6 + 0.8 * brightness * (1 - 0.5 * cover), shadowExtent: Math.max(bounds.width, bounds.depth) / 2 + 24 };
}
export type SceneEnvironment = ReturnType<typeof getSceneEnvironment>;
/**
 * Where the sun is after `seconds`: low in the sky ahead of the scenic camera, sweeping slowly from one side
 * of the view to the other and back while rising a little. Illustrative only; it is not a solar-position calculation.
 */
export function getSunArcPosition(seconds: number): Vec3 {
  const swing = Math.cos(seconds * 2 * Math.PI / sceneSky.sunPeriodSeconds);
  const [cameraX, , cameraZ] = cameraDirections.scenic, length = Math.hypot(cameraX, cameraZ);
  // The horizontal direction the scenic camera looks in, turned by the sweep angle.
  const aheadX = -cameraX / length, aheadZ = -cameraZ / length;
  const sweep = degreesToRadians(sceneSky.sunSweepDeg) * swing;
  const elevation = degreesToRadians(sceneSky.sunMinElevationDeg + sceneSky.sunLiftDeg * (1 - swing * swing));
  const flat = Math.cos(elevation) * sceneSky.sunDistance;
  return [(aheadX * Math.cos(sweep) - aheadZ * Math.sin(sweep)) * flat, Math.sin(elevation) * sceneSky.sunDistance, (aheadX * Math.sin(sweep) + aheadZ * Math.cos(sweep)) * flat];
}
/** A cloud's x position after drifting for `seconds`, wrapped so it re-enters from the far side. */
export function getCloudDriftX(startX: number, environment: Pick<SceneEnvironment, "cloudDrift" | "driftSpan">, seconds: number): number {
  const span = environment.driftSpan * 2;
  return ((startX + environment.driftSpan + seconds * environment.cloudDrift) % span + span) % span - environment.driftSpan;
}
