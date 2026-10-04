import { describe, expect, it } from "vitest";
import { clampSunPoint, getSunAngleDeg, getSunLabState, sunLab } from "./sun-lab";

const range = { minDeg: 30, maxDeg: 60 };
const at = (angleDeg: number, distance = 6, side = 0) => ({ side, height: distance * Math.sin(angleDeg * Math.PI / 180), forward: distance * Math.cos(angleDeg * Math.PI / 180) });

describe("single-row sun lab geometry", () => {
  it("tilts the row to face a sun in front of it", () => {
    const state = getSunLabState(at(50), range);
    expect(state.tiltDeg).toBeCloseTo(40); expect(state.incidenceDeg).toBeCloseTo(0); expect(state.alignmentPct).toBe(100);
  });
  it("lays the row flat under an overhead sun", () => expect(getSunLabState(at(90), range).tiltDeg).toBeCloseTo(0));
  it("stands the row steep for a low sun", () => expect(getSunLabState(at(10), range).tiltDeg).toBeCloseTo(80));
  it("leans the row backwards to face a sun behind it", () => {
    const state = getSunLabState(at(150), range);
    expect(state.tiltDeg).toBeCloseTo(-60); expect(state.side).toBe("behind"); expect(state.alignmentPct).toBe(100);
  });
  it("gives the row a full 180 degrees of travel", () => {
    expect(getSunLabState({ side: 0, height: 0, forward: 6 }, range).tiltDeg).toBe(90);
    expect(getSunLabState({ side: 0, height: 0, forward: -6 }, range).tiltDeg).toBe(-90);
  });
  it("never tilts outside -90 to 90 degrees", () => { for (let angle = -40; angle <= 220; angle += 5) { const { tiltDeg } = getSunLabState(at(angle), range); expect(tiltDeg).toBeGreaterThanOrEqual(-90); expect(tiltDeg).toBeLessThanOrEqual(90); } });
  it("keeps the same tilt wherever the sun sits along its line from the row", () => expect(getSunLabState(at(50, 4), range).tiltDeg).toBeCloseTo(getSunLabState(at(50, 12), range).tiltDeg));
  it("reports the lost alignment when the sun is off to the side of the row", () => {
    const state = getSunLabState({ side: 6, height: 6, forward: 0 }, range);
    expect(state.tiltDeg).toBeCloseTo(0); expect(state.incidenceDeg).toBeCloseTo(45); expect(state.alignmentPct).toBe(71); expect(state.elevationDeg).toBeCloseTo(45);
  });
  it("flags tilts inside the evaluated candidate range", () => expect(getSunLabState(at(45), range).withinEvaluatedRange).toBe(true));
  it("flags tilts outside the evaluated candidate range, including backward tilts", () => expect([getSunLabState(at(80), range).withinEvaluatedRange, getSunLabState(at(135), range).withinEvaluatedRange]).toEqual([false, false]));
  it("says nothing about the range when no candidates were supplied", () => expect(getSunLabState(at(45), null).withinEvaluatedRange).toBeNull());
  it("reads the sun angle in the tilt plane", () => expect([getSunAngleDeg(at(45)), getSunAngleDeg(at(135)), getSunAngleDeg({ side: 9, height: 3, forward: 3 })].map(Math.round)).toEqual([45, 135, 45]));
  it("holds the sun angle at the nearer end when the sun drops below the pivot", () => expect([getSunAngleDeg({ side: 0, height: -1, forward: 5 }), getSunAngleDeg({ side: 0, height: -1, forward: -5 })]).toEqual([0, 180]));
  it("keeps the sun above the ground", () => expect(clampSunPoint({ side: 0, height: -9, forward: 6 }).height).toBe(sunLab.minHeight));
  it("keeps the sun clear of the row", () => expect(Math.hypot(...Object.values(clampSunPoint({ side: 0, height: 0.5, forward: 0.5 })))).toBeCloseTo(sunLab.minDistance));
  it("keeps the sun within reach of the view", () => expect(Math.hypot(...Object.values(clampSunPoint({ side: 30, height: 40, forward: -50 })))).toBeCloseTo(sunLab.maxDistance));
  it("leaves a sun inside the limits where it was put", () => expect(clampSunPoint({ side: 2, height: 5, forward: -3 })).toEqual({ side: 2, height: 5, forward: -3 }));
  it("falls back to the starting sun for a position that is not a number", () => expect(clampSunPoint({ side: Number.NaN, height: 1, forward: 1 })).toEqual(sunLab.start));
  it("places a sun dropped exactly on the pivot straight above it", () => expect(clampSunPoint({ side: 0, height: 0, forward: 0 })).toEqual({ side: 0, height: sunLab.minDistance, forward: 0 }));
});
