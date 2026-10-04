/**
 * Geometry for the single-row "sun lab": the viewer places the sun and the row turns to face it.
 * This is plain trigonometry for illustration. It is not the model's prediction, not the optimizer's
 * net-benefit recommendation, and it never produces an energy figure.
 */

/** Sun angle is measured in the plane the row tilts in: 0 = horizon in front of the panels, 90 = overhead, 180 = horizon behind. */
export const sunLab = { minSunDeg: 5, maxSunDeg: 175, startSunDeg: 50, minTiltDeg: 0, maxTiltDeg: 90 } as const;
export type EvaluatedRange = { minDeg: number; maxDeg: number };

const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));
const toRadians = (degrees: number) => degrees * Math.PI / 180;

export function clampSunAngle(sunDeg: number): number {
  return clamp(Number.isFinite(sunDeg) ? sunDeg : sunLab.startSunDeg, sunLab.minSunDeg, sunLab.maxSunDeg);
}

/** The sun angle for a pointer position in the tilt plane, given the height of the row's pivot. */
export function sunAngleFromPoint(height: number, forward: number, pivotHeight: number): number {
  return clampSunAngle(Math.atan2(height - pivotHeight, forward) * 180 / Math.PI);
}

export function getSunLabState(sunDeg: number, evaluated: EvaluatedRange | null) {
  const sun = clampSunAngle(sunDeg);
  // A panel tilted t degrees from horizontal faces the direction 90 - t, so facing the sun means t = 90 - sun.
  const tilt = clamp(90 - sun, sunLab.minTiltDeg, sunLab.maxTiltDeg);
  const incidence = Math.abs(sun - (90 - tilt));
  return {
    sunDeg: sun,
    elevationDeg: Math.min(sun, 180 - sun),
    side: sun > 90 ? "behind" as const : "front" as const,
    tiltDeg: tilt,
    // 0 when the panel faces the sun squarely; grows once the sun passes behind a row that cannot tilt backwards.
    incidenceDeg: incidence,
    alignmentPct: Math.round(Math.max(0, Math.cos(toRadians(incidence))) * 100),
    // Null when the payload supplied no candidate angles to compare with.
    withinEvaluatedRange: evaluated ? tilt >= evaluated.minDeg && tilt <= evaluated.maxDeg : null,
  };
}
export type SunLabState = ReturnType<typeof getSunLabState>;
