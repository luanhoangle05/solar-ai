import { beforeAll, describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { loadFrontendData } from "./frontend-data.server";
import { getFrontendSummary } from "./selectors";
import { formatAngle } from "./formatters";
import { FarmMap } from "../components/farm/farm-map";
import { Farm3DLoader, SceneUnavailable } from "../components/farm-3d/farm-3d-loader";
import { PredictionFacts } from "../components/shared/inspection-page";
import { NetBenefitBreakdown } from "../components/optimization/optimization-analysis";
import { getOptimizationSummary } from "./optimization";
import type { FrontendData } from "../types/solar";

let fixture: FrontendData;
beforeAll(async () => { fixture = await loadFrontendData(); });
const inspect = () => {};

describe("hardening data truth and graceful inspection", () => {
  it("preserves fractional angles instead of presenting distinct candidates as equal", () => {
    expect(formatAngle(35.25)).toBe("35.25°");
    expect(formatAngle(35.35)).toBe("35.35°");
    expect(formatAngle(0)).toBe("0°");
    expect(formatAngle(null)).toBe("Unavailable");
  });
  it("never falls back to a proposed target for missing current observations", () => {
    const data = structuredClone(fixture);
    data.optimization = null;
    data.farm_status.rows = [];
    expect(getFrontendSummary(data).currentAngleDeg).toBeNull();
    expect(getFrontendSummary(data).decisionTargetAngleDeg).toBe(45);
  });
  it("uses the recorded row angle when the optimization is unavailable", () => {
    const data = structuredClone(fixture);
    data.optimization = null;
    expect(getFrontendSummary(data).currentAngleDeg).toBe(35);
  });
  it("shows an explicit empty zone state in the schematic", () => {
    const farm = { ...fixture.farm_status, rows: [], zones: [] };
    const html = renderToStaticMarkup(<FarmMap farm={farm} targetId="missing" selectedZone={null} selectedRow={null} onZone={inspect} onRow={inspect}/>);
    expect(html).toContain("No zones available in this payload.");
  });
  it("shows an explicit empty row state for each retained zone", () => {
    const farm = { ...fixture.farm_status, rows: [] };
    const html = renderToStaticMarkup(<FarmMap farm={farm} targetId="missing" selectedZone={null} selectedRow={null} onZone={inspect} onRow={inspect}/>);
    expect(html).toContain("No rows available in this zone.");
  });
  it.each(["rows", "zones"] as const)("keeps empty %s out of WebGL and offers 2D inspection", (key) => {
    const farm = { ...fixture.farm_status, [key]: [] };
    const html = renderToStaticMarkup(<Farm3DLoader farm={farm} targetId="missing" selectedZone={null} selectedRow={null} onZone={inspect} onRow={inspect} onExit={inspect}/>);
    expect(html).toContain("No farm geometry available in this payload.");
    expect(html).toContain("Return to 2D");
    expect(html).not.toContain("<canvas");
  });
  it("offers a readable WebGL fallback with retained selection", () => {
    const html = renderToStaticMarkup(<SceneUnavailable onExit={inspect}/>);
    expect(html).toContain("3D visualization unavailable on this device.");
    expect(html).toContain("Your inspection selection is retained.");
    expect(html).toContain("Return to 2D");
  });
  it("retains long target identifiers in read-only scope details", () => {
    const target = "row-" + "long-contract-identifier-".repeat(12);
    const html = renderToStaticMarkup(<PredictionFacts metadata={{ ...fixture.metadata, control_target_id: target }}/>);
    expect(html).toContain(target);
    expect(html).not.toMatch(/<(input|button|select)\b/);
  });
  it("renders negative net benefit with its supplied sign and equivalent units", () => {
    const data = structuredClone(fixture);
    data.optimization!.net_benefit_kwh_equivalent = -0.03;
    const before = structuredClone(data);
    const html = renderToStaticMarkup(<NetBenefitBreakdown summary={getOptimizationSummary(data)}/>);
    expect(html).toContain("-0.03 kWh eq.");
    expect(html).not.toContain("+0.03 kWh eq.");
    expect(data).toEqual(before);
  });
});
