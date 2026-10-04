import { beforeAll, describe, expect, it } from "vitest";
import { loadFrontendData } from "./frontend-data.server";
import { getControlTargetRow } from "./selectors";
import { getControlTargetZone } from "./dashboard";
import { emptyRowFilters, filterFarmRows, formatZoneName, getFarmSummary, getInitialSelection, getPanelsPerRow, getRowById, getRowCounts, getRowTargetContext, getZoneById, getZoneRows, getZoneSelection } from "./farm";
import { rowStatePresentation } from "../config/row-states";
import { actionPresentation } from "../config/actions";
import type { FrontendData } from "../types/solar";

let data:FrontendData;
beforeAll(async()=> { data=await loadFrontendData(); });

describe("farm contract derivations",()=> {
  it("reads total panels from the contract",()=>expect(getFarmSummary(data).totalPanels).toBe(1000));
  it("counts loaded rows",()=>expect(getFarmSummary(data).totalRows).toBe(50));
  it("counts loaded zones",()=>expect(getFarmSummary(data).zoneCount).toBe(4));
  it("derives panels per row",()=>expect(getPanelsPerRow(data.farm_status.rows)).toBe("20"));
  it("handles differing row sizes honestly",()=>expect(getPanelsPerRow([{...data.farm_status.rows[0],panel_count:10},data.farm_status.rows[1]])).toBe("10–20 (varies)"));
  it("handles empty panel distribution",()=>expect(getPanelsPerRow([])).toBe("Unavailable"));
  it("reuses target-row lookup",()=>expect(getFarmSummary(data).targetRow).toEqual(getControlTargetRow(data)));
  it("reuses target-zone lookup",()=>expect(getFarmSummary(data).targetZone).toEqual(getControlTargetZone(data)));
  it("falls back to first row if target is missing",()=> {
    const missing={...data,metadata:{...data.metadata,control_target_id:"missing"}};
    const summary=getFarmSummary(missing);
    expect(summary.targetRow).toBeNull(); expect(summary.targetZone).toBeNull();
    expect(getInitialSelection(missing.farm_status,summary.targetRow).rowId).toBe("row-001");
  });
  it("handles a defensive empty farm",()=>expect(getInitialSelection({total_panels:0,rows:[],zones:[]},null)).toEqual({rowId:null,zoneId:null}));
  it("finds an existing row",()=>expect(getRowById(data.farm_status,"row-020")?.row_id).toBe("row-020"));
  it("returns null for unknown row",()=>expect(getRowById(data.farm_status,"missing")).toBeNull());
  it("finds an existing zone",()=>expect(getZoneById(data.farm_status,"zone-02")?.zone_id).toBe("zone-02"));
  it("returns null for unknown zone",()=>expect(getZoneById(data.farm_status,null)).toBeNull());
  it("groups rows by supplied membership in supplied order",()=> {
    const zone={...data.farm_status.zones[0],row_ids:["row-010","row-002","row-008"]};
    expect(getZoneRows(data.farm_status,zone).map(row=>row.row_id)).toEqual(zone.row_ids);
  });
  it("safely skips absent membership rows",()=>expect(getZoneRows(data.farm_status,{...data.farm_status.zones[0],row_ids:["missing"]})).toEqual([]));
  it("preserves zone panel distribution, not equal quarters",()=>expect(getFarmSummary(data).zones.map(zone=>zone.panelCount)).toEqual([260,240,260,240]));
  it("preserves zone row distribution",()=>expect(getFarmSummary(data).zones.map(zone=>zone.rowCount)).toEqual([13,12,13,12]));
  it("counts farm states including zero categories",()=>expect(getRowCounts(data.farm_status.rows).states).toEqual({READY:48,MOVING:0,STOWED:2,FAULT:0}));
  it("counts recorded farm actions",()=>expect(getRowCounts(data.farm_status.rows).actions).toEqual({ROTATE:1,HOLD:47,STOW:2}));
  it("counts zone states",()=>expect(getRowCounts(getZoneRows(data.farm_status,data.farm_status.zones[3])).states).toEqual({READY:10,MOVING:0,STOWED:2,FAULT:0}));
  it("counts zone actions",()=>expect(getRowCounts(getZoneRows(data.farm_status,data.farm_status.zones[0])).actions).toEqual({ROTATE:1,HOLD:12,STOW:0}));
  it.each(["READY","MOVING","STOWED","FAULT"] as const)("supports %s independently of action",state=> {
    const row={...data.farm_status.rows[0],current_state:state};
    expect(getRowCounts([row]).states[state]).toBe(1); expect(getRowCounts([row]).actions.ROTATE).toBe(1);
    expect(rowStatePresentation[state].icon).toBeDefined();
  });
  it.each(["ROTATE","HOLD","STOW"] as const)("supports recorded %s independently of state",action=> {
    const row={...data.farm_status.rows[0],action};
    expect(getRowCounts([row]).actions[action]).toBe(1); expect(getRowCounts([row]).states.READY).toBe(1);
    expect(actionPresentation[action].icon).toBeDefined();
  });
  it("does not turn pipeline errors into row faults",()=> {
    const withErrors={...data,errors:[{agent:"data" as const,code:"TEST",message:"Pipeline issue"}]};
    expect(getFarmSummary(withErrors).states.FAULT).toBe(0);
  });
});

describe("inspection and target distinction",()=> {
  it("defaults to the actual target row",()=>expect(getInitialSelection(data.farm_status,getControlTargetRow(data))).toEqual({rowId:"row-001",zoneId:"zone-01"}));
  it("selects another zone without changing target",()=> {
    const selection=getZoneSelection(data.farm_status,"zone-02","row-001");
    expect(selection).toEqual({zoneId:"zone-02",rowId:"row-014"}); expect(data.metadata.control_target_id).toBe("row-001");
  });
  it("retains inspected row within selected zone",()=>expect(getZoneSelection(data.farm_status,"zone-02","row-020").rowId).toBe("row-020"));
  it("handles an empty zone",()=> {
    const farm={...data.farm_status,zones:[{zone_id:"empty",panel_count:0,row_ids:[]}]};
    expect(getZoneSelection(farm,"empty",null)).toEqual({zoneId:"empty",rowId:null});
  });
  it("handles unknown zone selection",()=>expect(getZoneSelection(data.farm_status,"missing",null)).toEqual({zoneId:null,rowId:null}));
  it("retains actual target metadata",()=>expect(getFarmSummary(data).targetRow).toMatchObject({row_id:"row-001",zone_id:"zone-01",angle_deg:35,current_state:"READY",action:"ROTATE",panel_count:20}));
  it("provides optimization context only to target",()=>expect(getRowTargetContext(data,getControlTargetRow(data))).toEqual({optimization:data.optimization,decision:data.decision,safety:data.safety}));
  it("excludes target recommendation from a non-target row",()=>expect(getRowTargetContext(data,getRowById(data.farm_status,"row-020"))).toBeNull());
  it("handles no inspected row",()=>expect(getRowTargetContext(data,null)).toBeNull());
  it("preserves absent optimization without synthesizing a recommendation",()=>expect(getRowTargetContext({...data,optimization:null},getControlTargetRow(data))?.optimization).toBeNull());
  it("identifies the target zone",()=>expect(getFarmSummary(data).zones[0].isTarget).toBe(true));
  it("does not mark another zone as target",()=>expect(getFarmSummary(data).zones[1].isTarget).toBe(false));
  it.each([["zone-01","Zone 1"],["zone-12","Zone 12"],["north","north"]])("formats %s without hardcoded index",(id,label)=>expect(formatZoneName(id)).toBe(label));
});

describe("loaded row filters",()=> {
  it("searches exact row IDs case-insensitively",()=>expect(filterFarmRows(data.farm_status.rows,{...emptyRowFilters,search:" ROW-020 "}).map(row=>row.row_id)).toEqual(["row-020"]));
  it("filters by zone",()=>expect(filterFarmRows(data.farm_status.rows,{...emptyRowFilters,zone:"zone-02"})).toHaveLength(12));
  it("filters by state",()=>expect(filterFarmRows(data.farm_status.rows,{...emptyRowFilters,state:"STOWED"}).map(row=>row.row_id)).toEqual(["row-049","row-050"]));
  it("filters by recorded action",()=>expect(filterFarmRows(data.farm_status.rows,{...emptyRowFilters,action:"ROTATE"}).map(row=>row.row_id)).toEqual(["row-001"]));
  it("combines all filters",()=>expect(filterFarmRows(data.farm_status.rows,{search:"049",zone:"zone-04",state:"STOWED",action:"STOW"}).map(row=>row.row_id)).toEqual(["row-049"]));
  it("returns an honest empty result",()=>expect(filterFarmRows(data.farm_status.rows,{...emptyRowFilters,zone:"zone-01",state:"STOWED"})).toEqual([]));
  it("clearing filters returns all loaded rows",()=>expect(filterFarmRows(data.farm_status.rows,emptyRowFilters)).toEqual(data.farm_status.rows));
  it("does not mutate loaded data during selection or filtering",()=> {
    const before=structuredClone(data); getFarmSummary(data); getZoneSelection(data.farm_status,"zone-04","row-001");
    filterFarmRows(data.farm_status.rows,{...emptyRowFilters,state:"STOWED"}); expect(data).toEqual(before);
  });
});
