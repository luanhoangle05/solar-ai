import { beforeAll, describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { loadFrontendData } from "./frontend-data.server";
import { analysisTransition, getSimulationCommandView, type AnalysisStep } from "./command-center";
import { getPreviewAngle, getPreviewFarm, getRowSimulationView } from "./farm-simulation";
import { getSimulationOverviewSelection, RowPanel, SolarFarmSimulation } from "../components/simulation/solar-farm-simulation";
import { SimulationDisclosure } from "../components/simulation/simulation-details";
import { getRowCounts, getZoneSelection } from "./farm";
import { SceneUnavailable } from "../components/farm-3d/farm-3d-loader";
import type { FrontendData } from "../types/solar";
let fixture: FrontendData;
beforeAll(async () => { fixture = await loadFrontendData(); });
const render = (data = fixture) => renderToStaticMarkup(<SolarFarmSimulation data={data}/>);
const renderRowPanel = (rowId: string, focused = false) => {
  const view = getRowSimulationView(fixture, rowId);
  if (!view) throw new Error(`Missing fixture row ${rowId}`);
  return renderToStaticMarkup(<RowPanel view={view} data={fixture} previewRows={1} runCount={1} previewAngle={getPreviewAngle(fixture)} isPreviewing={false} onPreview={()=>{}} focused={focused} onFocus={()=>{}} onOverview={()=>{}}/>);
};
describe("Simulation operator experience", () => {
  it("removes the permanent technical sections and starts with AI", () => {
    const html = render();
    expect(html).not.toMatch(/<h1|Scenario Input|Manager Decision|Candidate Energy Profile|Why This Angle|Safety Validation|Recommendation → Decision/i);
    expect(html.indexOf("AI Agent Command Center")).toBeLessThan(html.indexOf('aria-label="Solar Farm"'));
    expect(html).toContain("acc-agents");
    expect(html.replace(/<[^>]*>/g, "")).not.toMatch(/replay/i);
    for (const label of ["2D", "3D", "Sun lab"]) expect(html).toContain(`>${label}</button>`);
    expect(html).toContain("Run AI Analysis");
    expect(html).not.toContain("Run Again");
  });
  it("preserves the Farm header, environment, tilt and visible row reasoning above lower details", () => {
    const html = render();
    for (const text of ["Solar Farm Simulation", "Analysis interval", "60 min prediction horizon", "850 W/m²", "15%", "22°C", "14 km/h", "Selected Row", "Agent reasoning for this row", "Side view of the row tilted 35°"]) expect(html).toContain(text);
    expect(html.indexOf("Environmental conditions")).toBeLessThan(html.indexOf('aria-label="Solar Farm"'));
    expect(html.indexOf("Agent reasoning for this row")).toBeLessThan(html.indexOf('aria-label="Zone summary"'));
    expect((html.match(/class="acc-agent"/g) ?? []).length).toBe(4);
  });
  it("reports unavailable additional analyses without hiding the main Farm", () => {
    const html = renderToStaticMarkup(<SolarFarmSimulation data={fixture} zoneRunsError="Unavailable"/>);
    expect(html).toContain("Only the main analysis is shown.");
    expect(html).toContain("Selected Row");
  });
  it("starts on Data, advances once per stage, prevents duplicate starts, and restarts", () => {
    let step: AnalysisStep = -1;
    step = analysisTransition(step, { type:"start", available:true });
    const stages = getSimulationCommandView(fixture).stages;
    const seen: string[] = [];
    for (let index=0; index<4; index++) {
      expect(step).toBe(index);
      expect(analysisTransition(step, {type:"start",available:true})).toBe(step);
      expect(stages.filter((_,i)=>i===step)).toHaveLength(1);
      seen.push(stages[step].agent);
      step=analysisTransition(step,{type:"advance"});
    }
    expect(seen).toEqual(["data","modeling","optimization","manager"]);
    expect(step).toBe(4);
    expect(analysisTransition(step,{type:"advance"})).toBe(4);
    expect(analysisTransition(step,{type:"start",available:true})).toBe(0);
  });
  it("supports immediate reduced-motion completion and refuses unavailable results", () => {
    expect(analysisTransition(-1,{type:"start",available:true,reducedMotion:true})).toBe(4);
    expect(analysisTransition(-1,{type:"start",available:false})).toBe(-1);
    expect(analysisTransition(2,{type:"finish"})).toBe(4);
    expect(analysisTransition(-1,{type:"advance"})).toBe(-1);
  });
  it("maps the loaded recommendation and preserves source data", () => {
    const before=structuredClone(fixture);
    expect(getSimulationCommandView(fixture)).toMatchObject({title:"Recommendation Ready",angle:"35° → 45°",targetId:"row-001",available:true});
    const html=render();
    for (const text of ["35°","45°","+0.29 kWh","+0.26 kWh eq.","Safe to proceed","Per row · next 60 min"]) expect(html).toContain(text);
    getPreviewFarm(fixture);
    expect(fixture).toEqual(before);
  });
  it("keeps target recommendations separate from other inspected rows", () => {
    const other=getRowSimulationView(fixture,"row-020");
    expect(other).toMatchObject({isTarget:false,recommendedAngle:null,gain:null});
    const zone = fixture.farm_status.zones[3];
    expect(getZoneSelection(fixture.farm_status,zone.zone_id,"row-001")).toEqual({zoneId:zone.zone_id,rowId:zone.row_ids[0]});
  });
  it("keeps the complete Selected Row structure for target and non-target rows", () => {
    const target = renderRowPanel("row-001");
    const other = renderRowPanel("row-033");
    const required = ["sfs-diagram", "Current Angle", "Recommended", "Expected Gain", "Net Benefit", "Agent reasoning for this row"];
    for (const label of required) {
      expect(target).toContain(label);
      expect(other).toContain(label);
    }
    for (const value of ["45°", "+0.29 kWh", "+0.26 kWh eq."]) expect(target).toContain(value);
    expect(other).toContain("No active recommendation for this row.");
    expect(other).toContain("No recommendation is shown for this row because it is not covered by the current optimization decision.");
    expect(other).toMatch(/Recommended<\/span><strong>—<\/strong>/);
    expect(other).toMatch(/Expected Gain<\/dt><dd>—<\/dd>/);
    expect(other).toMatch(/Net Benefit<\/dt><dd[^>]*>—<\/dd>/);
    expect(other).not.toContain("45°");
    expect(other).not.toContain("+0.29 kWh");
    expect(other).not.toContain("+0.26 kWh eq.");
  });
  it("restores the control target selection for Back to Farm without hardcoding a row", () => {
    expect(getSimulationOverviewSelection(fixture)).toEqual({ zoneId:"zone-01", rowId:"row-001" });
    const data=structuredClone(fixture);
    data.metadata.control_target_id="row-033";
    expect(getSimulationOverviewSelection(data)).toEqual({ zoneId:"zone-03", rowId:"row-033" });
    const before=renderRowPanel("row-001");
    renderRowPanel("row-033", true);
    const after=renderRowPanel("row-001");
    expect(after).toBe(before);
    expect(after).toContain("TARGET");
    expect(renderRowPanel("row-033", true)).toContain("Back to Farm");
  });
  it("only previews the target and preserves current angles for every other row", () => {
    const farm=getPreviewFarm(fixture);
    expect(farm.rows.filter((row,index)=>row.angle_deg!==fixture.farm_status.rows[index].angle_deg).map(row=>row.row_id)).toEqual(["row-001"]);
    expect(farm.rows[0].angle_deg).toBe(fixture.decision.target_angle_deg);
  });
  it("does not preview HOLD or display a fake movement arrow", () => {
    const data=structuredClone(fixture); data.decision.action="HOLD";
    expect(getPreviewAngle(data)).toBeNull();
    expect(getSimulationCommandView(data).angle).toBe("35°");
    expect(render(data)).toContain("Keep current angle");
    expect(render(data)).not.toContain(">Angle Preview</button>");
  });
  it("blocks normal rotation previews on failed safety", () => {
    const data=structuredClone(fixture); data.safety.passed=false;
    data.safety.checks[0]={...data.safety.checks[0],passed:false,reason:"Wind above limit"};
    expect(getPreviewAngle(data)).toBeNull();
    expect(getPreviewFarm(data)).toBe(data.farm_status);
    const html=render(data);
    expect(html).toContain("Rotation blocked"); expect(html).toContain("Wind above limit");
    expect(html).not.toContain("Safe to proceed");
    expect(getSimulationCommandView(data).stages[3].completed).not.toContain("approved");
  });
  it("preserves STOW at zero without gain celebration", () => {
    const data=structuredClone(fixture); data.decision={action:"STOW",target_angle_deg:0,reason:"Severe wind"}; data.safety.passed=false; data.safety.reason="Severe wind";
    expect(getPreviewAngle(data)).toBe(0);
    expect(getPreviewFarm(data).rows[0].angle_deg).toBe(0);
    const html=render(data); expect(html).toContain("Protective stow recommendation"); expect(html).toContain("0°"); expect(html).toMatch(/Expected Gain<\/dt><dd>—<\/dd>/);
  });
  it("shows no fabricated result when optimization or target is missing", () => {
    const data=structuredClone(fixture); data.optimization=null;
    expect(getSimulationCommandView(data).available).toBe(false);
    expect(getPreviewAngle(data)).toBeNull();
    expect(render(data)).toContain("No AI recommendation available.");
    data.metadata.control_target_id="missing";
    expect(getSimulationCommandView(data).targetId).toBeNull();
  });
  it("handles empty farm, weather, agents and candidates", () => {
    const data=structuredClone(fixture); data.farm_status.rows=[]; data.farm_status.zones=[]; data.current_weather=null; data.agent_log=[]; data.candidate_predictions=[];
    const html=render(data);
    for(const text of ["Farm data unavailable.","No row selected.","Environmental data unavailable.","AI activity unavailable.","No angles available"]) expect(html).toContain(text);
  });
  it("starts the four detail disclosures closed with accessible controls", () => {
    const html=render();
    expect(html.match(/aria-expanded="false"/g)).toHaveLength(4);
    expect(html.match(/aria-controls=/g)).toHaveLength(4);
    expect(html).not.toContain("<table");
    for(const label of ["Row Explorer","Agent Activity","Candidate Angles","Safety Details"]) expect(html).toContain(label);
    expect(renderToStaticMarkup(<SimulationDisclosure title="Test" summary="Open" defaultOpen><p>Detail</p></SimulationDisclosure>)).toContain('aria-expanded="true"');
  });
  it("shows exact zone and row-state summaries without a duplicate chart", () => {
    expect(getRowCounts(fixture.farm_status.rows).states).toEqual({READY:48,MOVING:0,STOWED:2,FAULT:0});
    const html=render(); expect(html).toContain("260 panels · 13 rows"); expect(html).toContain("240 panels · 12 rows");
    expect(html).not.toContain("Panels by Zone");
  });
  it("keeps 3D failures understandable", () => {
    const html=renderToStaticMarkup(<SceneUnavailable operator onExit={()=>{}}/>);
    expect(html).toContain("3D view isn’t available on this device."); expect(html).toContain("Return to 2D");
  });
  it("flags incomplete agents rather than claiming successful stages", () => {
    const data=structuredClone(fixture); data.current_weather=null; data.candidate_predictions=[];
    const view=getSimulationCommandView(data);
    expect(view.stages[0].issue).toBe(true); expect(view.stages[1].issue).toBe(true);
    expect(view.stages[0].completed).toBe("Analysis needs attention");
  });
});
