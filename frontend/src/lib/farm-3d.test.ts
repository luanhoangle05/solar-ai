import { beforeAll, describe, expect, it } from "vitest";
import { loadFrontendData } from "./frontend-data.server";
import { buildFarmSceneLayout, degreesToRadians, getCameraPreset, getInstanceRowId, getSceneRow, sceneDimensions, type FarmSceneLayout } from "./farm-3d";
import { getRowTargetContext } from "./farm";
import type { FrontendData } from "../types/solar";

let data: FrontendData;
let layout: FarmSceneLayout;
beforeAll(async () => { data = await loadFrontendData(); layout = buildFarmSceneLayout(data.farm_status); });

describe("schematic angles", () => {
  it.each([[0, 0], [35, 35 * Math.PI / 180], [90, Math.PI / 2], [-15, -Math.PI / 12]])("converts %s degrees", (angle, expected) => expect(degreesToRadians(angle)).toBeCloseTo(expected));
  it("transfers each recorded angle to every panel", () => {
    for (const zone of layout.zones) for (const panel of zone.panels) expect(panel.tilt).toBe(degreesToRadians(data.farm_status.rows.find(row => row.row_id === panel.rowId)!.angle_deg));
  });
  it("preserves actual stowed angle", () => {
    const row = data.farm_status.rows.find(row => row.current_state === "STOWED")!;
    expect(getSceneRow(layout, row.row_id)?.tilt).toBe(degreesToRadians(row.angle_deg));
    expect(row.angle_deg).toBe(0);
  });
});
describe("contract-backed layout", () => {
  it("represents four zones", () => expect(layout.zones).toHaveLength(4));
  it("represents fifty rows", () => expect(layout.rows).toHaveLength(50));
  it("produces exactly 1000 panels", () => expect(layout.panelCount).toBe(1000));
  it("regresses fixture distribution", () => expect(layout.zones.map(zone => zone.panels.length)).toEqual([260, 240, 260, 240]));
  it("regresses fixture row distribution", () => expect(layout.zones.map(zone => zone.rows.length)).toEqual([13, 12, 13, 12]));
  it("matches every zone panel total", () => layout.zones.forEach((zone, index) => expect(zone.panels.length).toBe(data.farm_status.zones[index].panel_count)));
  it("matches each row panel count", () => layout.zones.forEach(zone => zone.rows.forEach(row => expect(zone.panels.filter(panel => panel.rowId === row.row.row_id)).toHaveLength(row.row.panel_count))));
  it("preserves exact ordered membership", () => layout.zones.forEach((zone, index) => expect(zone.rows.map(row => row.row.row_id)).toEqual(data.farm_status.zones[index].row_ids)));
  it("derives slots from supplied order, not IDs", () => {
    const reversed = buildFarmSceneLayout({ ...data.farm_status, zones: [...data.farm_status.zones].reverse() });
    expect(reversed.zones[0].id).toBe(data.farm_status.zones[3].zone_id);
    expect(reversed.zones[0].position).toEqual(layout.zones[0].position);
  });
  it("places zone pairs left/right and upper/lower", () => {
    expect(layout.zones[0].position[0]).toBeLessThan(0); expect(layout.zones[1].position[0]).toBeGreaterThan(0);
    expect(layout.zones[0].position[2]).toBeLessThan(0); expect(layout.zones[2].position[2]).toBeGreaterThan(0);
  });
  it("is deterministic", () => expect(buildFarmSceneLayout(data.farm_status)).toEqual(layout));
  it("uses row panel counts rather than hardcoded twenty", () => {
    const farm = structuredClone(data.farm_status); farm.rows[0].panel_count = 7;
    expect(buildFarmSceneLayout(farm).panelCount).toBe(987);
  });
  it("leaves a corridor between zones", () => expect(layout.zones[1].position[0] - layout.zones[0].position[0] - layout.zones[0].width).toBeCloseTo(sceneDimensions.corridor));
  it("spaces rows deterministically", () => expect(layout.zones[0].rows[1].position[2] - layout.zones[0].rows[0].position[2]).toBeCloseTo(sceneDimensions.rowPitch));
  it("spaces panels deterministically", () => expect(layout.zones[0].panels[1].position[0] - layout.zones[0].panels[0].position[0]).toBeCloseTo(sceneDimensions.panelPitch));
  it("contains all panel centers in their zone bounds", () => layout.zones.forEach(zone => zone.panels.forEach(panel => {
    expect(Math.abs(panel.position[0] - zone.position[0]) + sceneDimensions.panelWidth / 2).toBeLessThan(zone.width / 2);
    expect(Math.abs(panel.position[2] - zone.position[2]) + sceneDimensions.panelDepth / 2).toBeLessThan(zone.depth / 2);
  })));
  it("derives overall bounds enclosing zones", () => layout.zones.forEach(zone => {
    expect(Math.abs(zone.position[0]) + zone.width / 2).toBeLessThanOrEqual(layout.bounds.width / 2);
    expect(Math.abs(zone.position[2]) + zone.depth / 2).toBeLessThanOrEqual(layout.bounds.depth / 2);
  }));
  it("keeps a zero-centered overview", () => expect(layout.bounds.center).toEqual([0, 0, 0]));
  it("preserves all four supplied row states without motion", () => {
    const farm = structuredClone(data.farm_status);
    const states = ["READY", "MOVING", "STOWED", "FAULT"] as const;
    states.forEach((state, i) => { farm.rows[i].current_state = state; });
    const result = buildFarmSceneLayout(farm);
    states.forEach((state, i) => {
      expect(getSceneRow(result, farm.rows[i].row_id)?.row.current_state).toBe(state);
      expect(result.zones[0].panels[i * 20].state).toBe(state);
      expect(result.zones[0].panels[i * 20].tilt).toBe(degreesToRadians(farm.rows[i].angle_deg));
    });
  });
  it("does not mutate the loaded farm", () => {
    const before = structuredClone(data); buildFarmSceneLayout(data.farm_status); expect(data).toEqual(before);
  });
});
describe("instance inspection mapping", () => {
  it("maps first instance", () => expect(getInstanceRowId(layout.zones[0], 0)).toBe("row-001"));
  it("maps last instance", () => expect(getInstanceRowId(layout.zones[3], 239)).toBe("row-050"));
  it("maps both sides of a row boundary", () => { expect(getInstanceRowId(layout.zones[0], 19)).toBe("row-001"); expect(getInstanceRowId(layout.zones[0], 20)).toBe("row-002"); });
  it("derives row index in zone", () => layout.zones.forEach(zone => zone.rows.forEach((row, index) => expect(row.index).toBe(index))));
  it("maps every range to its row", () => layout.zones.forEach(zone => zone.rows.forEach(row => {
    expect(getInstanceRowId(zone, row.firstInstance)).toBe(row.row.row_id);
    expect(getInstanceRowId(zone, row.firstInstance + row.instanceCount - 1)).toBe(row.row.row_id);
  })));
  it.each([undefined, -1, 260, 1.5])("rejects invalid instance %s", id => expect(getInstanceRowId(layout.zones[0], id)).toBeNull());
  it("finds control target", () => expect(getSceneRow(layout, data.metadata.control_target_id)?.row.row_id).toBe(data.metadata.control_target_id));
  it("keeps selected row distinct from target", () => expect(getSceneRow(layout, "row-020")?.position).not.toEqual(getSceneRow(layout, data.metadata.control_target_id)?.position));
  it("keeps recommendation isolated to target", () => {
    expect(getRowTargetContext(data, getSceneRow(layout, "row-020")!.row)).toBeNull();
    expect(getRowTargetContext(data, getSceneRow(layout, data.metadata.control_target_id)!.row)?.optimization).toBe(data.optimization);
  });
});
describe("camera and defensive empty inputs", () => {
  it("focuses the target scene position", () => expect(getCameraPreset(layout, 1.5, data.metadata.control_target_id).target).toEqual(getSceneRow(layout, data.metadata.control_target_id)?.position));
  it("focuses a selected scene position", () => expect(getCameraPreset(layout, 1.5, "row-020").target).toEqual(getSceneRow(layout, "row-020")?.position));
  it("falls back to overview for missing target", () => expect(getCameraPreset(layout, 1.5, "missing")).toEqual(getCameraPreset(layout, 1.5)));
  it("fits portrait more widely than landscape", () => expect(getCameraPreset(layout, 0.8).distance).toBeGreaterThan(getCameraPreset(layout, 1.5).distance));
  it("places overview above ground", () => expect(getCameraPreset(layout, 1.5).position[1]).toBeGreaterThan(0));
  it("handles missing row", () => expect(getSceneRow(layout, "missing")).toBeNull());
  it("handles null selection", () => expect(getSceneRow(layout, null)).toBeNull());
  it("handles empty zones", () => { const result = buildFarmSceneLayout({ ...data.farm_status, zones: [] }); expect(result.zones).toEqual([]); expect(result.panelCount).toBe(0); expect(result.bounds.width).toBe(0); });
  it("handles empty rows", () => { const result = buildFarmSceneLayout({ ...data.farm_status, rows: [] }); expect(result.rows).toEqual([]); expect(result.panelCount).toBe(0); });
  it("produces a finite camera for an empty farm", () => { const result = buildFarmSceneLayout({ ...data.farm_status, zones: [], rows: [] }); expect(getCameraPreset(result, 0).position.every(Number.isFinite)).toBe(true); });
  it("preserves noncontiguous membership order", () => { const farm = structuredClone(data.farm_status); farm.zones[0].row_ids = ["row-012", "row-002"]; expect(buildFarmSceneLayout(farm).zones[0].rows.map(row => row.row.row_id)).toEqual(["row-012", "row-002"]); });
});
