import { describe, expect, it } from "vitest";
import { clampSunAngle, getSunLabState, sunAngleFromPoint, sunLab } from "./sun-lab";

const range = { minDeg: 30, maxDeg: 60 };
describe("single-row sun lab geometry", () => {
  it("tilts the row to face the sun", () => expect(getSunLabState(50, range)).toMatchObject({ tiltDeg: 40, incidenceDeg: 0, alignmentPct: 100 }));
  it("lays the row flat under an overhead sun", () => expect(getSunLabState(90, range)).toMatchObject({ tiltDeg: 0, elevationDeg: 90, incidenceDeg: 0 }));
  it("stands the row steep for a low sun", () => expect(getSunLabState(10, range).tiltDeg).toBe(80));
  it("keeps the row flat once the sun passes behind it, and reports the lost alignment", () => {
    const state = getSunLabState(150, range);
    expect(state).toMatchObject({ tiltDeg: 0, side: "behind", elevationDeg: 30, incidenceDeg: 60, alignmentPct: 50 });
  });
  it("flags tilts inside the evaluated candidate range", () => expect(getSunLabState(45, range).withinEvaluatedRange).toBe(true));
  it("flags tilts outside the evaluated candidate range", () => expect([getSunLabState(80, range).withinEvaluatedRange, getSunLabState(20, range).withinEvaluatedRange]).toEqual([false, false]));
  it("says nothing about the range when no candidates were supplied", () => expect(getSunLabState(45, null).withinEvaluatedRange).toBeNull());
  it("never tilts outside 0 to 90 degrees", () => { for (let sun = 0; sun <= 180; sun += 5) { const { tiltDeg } = getSunLabState(sun, range); expect(tiltDeg).toBeGreaterThanOrEqual(0); expect(tiltDeg).toBeLessThanOrEqual(90); } });
  it("keeps the sun above the horizon", () => expect([clampSunAngle(-40), clampSunAngle(400), clampSunAngle(Number.NaN)]).toEqual([sunLab.minSunDeg, sunLab.maxSunDeg, sunLab.startSunDeg]));
  it("reads the sun angle from a pointer position", () => {
    expect(sunAngleFromPoint(6, 5, 1)).toBeCloseTo(45);
    expect(sunAngleFromPoint(9, 0, 1)).toBeCloseTo(90);
    expect(sunAngleFromPoint(6, -5, 1)).toBeCloseTo(135);
  });
  it("clamps a pointer below the horizon to the lowest sun", () => expect(sunAngleFromPoint(-3, 5, 1)).toBe(sunLab.minSunDeg));
  it("keeps the sun at the far end of the arc when the pointer drops below the horizon behind the row", () => expect(sunAngleFromPoint(-3, -5, 1)).toBe(sunLab.maxSunDeg));
});
