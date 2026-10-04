import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { frontendDataSchema } from "../schemas/frontend-data";
import type { FrontendData } from "../types/solar";

const { load } = vi.hoisted(() => ({load:vi.fn()}));
vi.mock("./frontend-data.server", () => ({loadFrontendDataResult:load}));
import OptimizationPage from "../app/(solar)/optimization/page";
import { OptimizationResult } from "../components/optimization/optimization-result";
import { SafetyValidation } from "../components/optimization/optimization-support";
import { getOptimizationSummary } from "./optimization";

let fixture: FrontendData;
beforeAll(async () => {
  const actual=await vi.importActual<typeof import("./frontend-data.server")>("./frontend-data.server");
  fixture=await actual.loadFrontendData();
});
beforeEach(() => load.mockResolvedValue({ok:true,data:fixture}));
const renderPage = async () => renderToStaticMarkup(await OptimizationPage());
const renderResult = (data: FrontendData) => renderToStaticMarkup(<OptimizationResult summary={getOptimizationSummary(data)}/>);

describe("Phase 13 optimization experience", () => {
  it("keeps the complete decision analysis visible without debug-heavy copy", async () => {
    const html=await renderPage();
    for (const text of ["Optimization","Understand why SolarAI selected this operating angle.","Recommendation","35°","45°","Expected Gain","+0.29 kWh","Movement Cost","0.03 kWh eq.","Net Benefit","+0.26 kWh eq.","row-001","Candidate Energy","Current","Recommended","Raw max","Why this recommendation","Candidate Comparison","Operating Conditions &amp; Safety","Prediction Details"]) expect(html).toContain(text);
    expect(html).not.toMatch(/READ-ONLY RESULT|RECORDED CONTRACT|MOCK DEVELOPMENT DATA|Optimization → Manager/i);
    expect(html).not.toMatch(/>(Run Optimization|Apply|Execute|Re-optimize)<\/button>/i);
  });
  it("distinguishes the raw energy maximum from the operating recommendation", async () => {
    const html=await renderPage();
    expect(html).toContain("Recommended operating angle");
    expect(html).toContain("Highest raw prediction");
    expect(html).toContain("Why not 60°?");
    expect(html).toContain("45°");
    expect(html).not.toMatch(/45°[^<]{0,30}(highest|maximum) raw energy/i);
  });
  it("renders ROTATE, HOLD, and STOW without inventing execution", () => {
    expect(renderResult(fixture)).toContain("ROTATE");
    const hold=structuredClone(fixture);
    hold.decision={action:"HOLD",target_angle_deg:hold.optimization!.current_angle_deg,reason:"Maintain current operating angle"};
    hold.farm_status.rows[0].action="HOLD";
    hold.optimization={...hold.optimization!,recommended_angle_deg:hold.optimization!.current_angle_deg,predicted_kwh:hold.optimization!.baseline_kwh,energy_gain_kwh:0,movement_cost_kwh_equivalent:0,net_benefit_kwh_equivalent:0};
    expect(renderResult(frontendDataSchema.parse(hold))).toContain("Keep current angle");
    const stow=structuredClone(fixture);
    stow.decision={action:"STOW",target_angle_deg:0,reason:"Protective wind response"};
    stow.farm_status.rows[0].action="STOW";
    stow.safety={...stow.safety,passed:false,reason:"Wind limit exceeded",checks:stow.safety.checks.map((check,index)=>index === 0 ? {...check,passed:false,reason:"Wind limit exceeded"} : check)};
    const stowHtml=renderResult(frontendDataSchema.parse(stow));
    expect(stowHtml).toContain("Stow panels");
    expect(stowHtml).toContain("Operating action blocked");
    expect(stowHtml).not.toContain("Safe to proceed");
  });
  it("uses explicit empty states for unavailable recommendation, candidates, and safety checks", async () => {
    const data=structuredClone(fixture);
    data.optimization=null;
    data.candidate_predictions=[];
    data.safety={...data.safety,checks:[],reason:""};
    data.decision={action:"HOLD",target_angle_deg:data.farm_status.rows[0].angle_deg,reason:"No optimization result"};
    data.farm_status.rows[0].action="HOLD";
    data.selected_model=null;
    load.mockResolvedValue({ok:true,data});
    const html=await renderPage();
    expect(html).toContain("No optimization recommendation available.");
    expect(html).toContain("Candidate comparison unavailable.");
    expect(html).toContain("Operating-condition status unavailable.");
  });
  it("keeps Prediction Details collapsed and exposes an accessible chart description", async () => {
    const html=await renderPage();
    expect(html).toMatch(/<details class="opt-prediction-details"><summary>Prediction Details<\/summary>/);
    expect(html).toContain('aria-label="Candidate energy chart"');
    expect(html).toContain("Exact values and combined roles are in the Candidate Comparison table below.");
  });
  it("preserves all primary analysis sections", async () => {
    const html=await renderPage();
    for (const section of ["Candidate Energy","Why this recommendation","Net Benefit Breakdown","Candidate Comparison","Operating Conditions &amp; Safety"]) expect(html).toContain(section);
  });
  it("renders the safety empty state independently", () => {
    const data=structuredClone(fixture);
    data.safety={...data.safety,checks:[],reason:""};
    expect(renderToStaticMarkup(<SafetyValidation summary={getOptimizationSummary(data)}/>)).toContain("Operating-condition status unavailable.");
  });
});
