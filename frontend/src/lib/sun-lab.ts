/**
 * Geometry for the single-row "sun lab": the viewer places the sun anywhere and the row turns to face it.
 * This is plain trigonometry for illustration. It is not the model's prediction, not the optimizer's
 * net-benefit recommendation, and it never produces an energy figure.
 */

/** Where the sun is, measured from the row's pivot in scene units: along the row, above it, and in front of it. */
export type SunPoint = { side: number; height: number; forward: number };
export type EvaluatedRange = { minDeg: number; maxDeg: number };

/** Presentation limits: the sun stays clear of the row, within reach of the view, and above the ground. */
export const sunLab = { start: { side: 0, height: 4.9, forward: 4.1 }, minDistance: 2.6, maxDistance: 16, minHeight: -1, minTiltDeg: -90, maxTiltDeg: 90 } as const;

const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));
const toDegrees = (radians: number) => radians * 180 / Math.PI;
const toRadians = (degrees: number) => degrees * Math.PI / 180;
const distanceOf = (point: SunPoint) => Math.hypot(point.side, point.height, point.forward);

/** Keeps a requested sun position inside the lab's limits; a position that is not a number falls back to the start. */
export function clampSunPoint(point: SunPoint): SunPoint {
  if (![point.side, point.height, point.forward].every(Number.isFinite)) return { ...sunLab.start };
  const raised = { ...point, height: Math.max(sunLab.minHeight, point.height) };
  const distance = distanceOf(raised);
  if (distance === 0) return { side: 0, height: sunLab.minDistance, forward: 0 };
  const scale = clamp(distance, sunLab.minDistance, sunLab.maxDistance) / distance;
  return { side: raised.side * scale, height: Math.max(sunLab.minHeight, raised.height * scale), forward: raised.forward * scale };
}

/** The sun's angle in the plane the row tilts in: 0 = level in front of the panels, 90 = overhead, 180 = level behind. */
export function getSunAngleDeg(point: SunPoint): number {
  if (point.height <= 0) return point.forward >= 0 ? 0 : 180;
  return toDegrees(Math.atan2(point.height, point.forward));
}

export function getSunLabState(point: SunPoint, evaluated: EvaluatedRange | null) {
  const sun = clampSunPoint(point), sunDeg = getSunAngleDeg(sun);
  // A panel tilted t degrees from horizontal faces the direction 90 - t, so facing the sun means t = 90 - sun.
  // Negative tilt leans the row backwards, giving it a full 180 degrees of travel.
  const tilt = clamp(90 - sunDeg, sunLab.minTiltDeg, sunLab.maxTiltDeg);
  // The row turns about one axis only, so a sun off to the side (or below the pivot) is never met squarely.
  const facing = (sun.height * Math.sin(toRadians(sunDeg)) + sun.forward * Math.cos(toRadians(sunDeg))) / distanceOf(sun);
  return {
    point: sun,
    elevationDeg: toDegrees(Math.atan2(sun.height, Math.hypot(sun.side, sun.forward))),
    side: sun.forward < 0 ? "behind" as const : "front" as const,
    tiltDeg: tilt,
    incidenceDeg: toDegrees(Math.acos(clamp(facing, -1, 1))),
    alignmentPct: Math.round(Math.max(0, facing) * 100),
    // Null when the payload supplied no candidate angles to compare with.
    withinEvaluatedRange: evaluated ? tilt >= evaluated.minDeg && tilt <= evaluated.maxDeg : null,
  };
}
export type SunLabState = ReturnType<typeof getSunLabState>;
