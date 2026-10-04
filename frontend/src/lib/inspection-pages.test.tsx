import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { FrontendData } from "../types/solar";
import { frontendDataSchema } from "../schemas/frontend-data";
const { load } = vi.hoisted(() => ({load:vi.fn()}));
vi.mock("./frontend-data.server", () => ({loadFrontendDataResult:load,loadZoneRuns:async()=>({runs:[],error:null})}));
import Weather from "../app/(solar)/weather/page";
import Analytics from "../app/(solar)/analytics/page";
import Simulation from "../app/(solar)/simulation/page";
import Settings from "../app/(solar)/settings/page";
let fixture: FrontendData;
beforeAll(async () => { const actual=await vi.importActual<typeof import("./frontend-data.server")>("./frontend-data.server"); fixture=await actual.loadFrontendData(); });
beforeEach(() => load.mockResolvedValue({ok:true,data:fixture}));
function unavailable() {
  const data=structuredClone(fixture);
  data.current_weather=null; data.optimization=null; data.candidate_predictions=[]; data.selected_model=null;
  data.model_comparison=data.model_comparison.map(model=>({...model,status:"UNAVAILABLE",mae:null,rmse:null,r2:null}));
  data.data_agent={status:"INVALID",source:"unavailable",forecast_age_minutes:null,used_cache:false,issues:["Missing environmental inputs"]};
  data.decision={action:"HOLD",target_angle_deg:35,reason:"Unavailable input"}; data.farm_status.rows[0].action="HOLD";
  data.history=[]; data.agent_log=[]; data.metadata.assumptions=[];
  return frontendDataSchema.parse(data);
}
describe("inspection page failure and content boundaries", () => {
  it.each([["Weather",Weather],["Analytics",Analytics],["Simulation",Simulation],["Settings",Settings]] as const)("%s shows loader failure", async (name,Page) => { load.mockResolvedValue({ok:false,error:{message:"Contract rejected"}}); expect(renderToStaticMarkup(await Page())).toContain(name === "Simulation" ? "Simulation unavailable" : "Contract rejected"); });
  it("weather renders null without replacement zeros and retains quality", async () => { load.mockResolvedValue({ok:true,data:unavailable()}); const html=renderToStaticMarkup(await Weather()); expect(html).toContain("Weather input unavailable for this payload."); expect(html).toContain("INVALID"); expect(html).toContain("Missing environmental inputs"); expect(html).not.toContain("0 mm"); });
  it("analytics renders sparse unavailable sections", async () => { load.mockResolvedValue({ok:true,data:unavailable()}); const html=renderToStaticMarkup(await Analytics()); expect(html).toContain("No candidate predictions available."); expect(html).toContain("No recorded decision history"); expect(html).toContain("No model selected."); });
  it("scenario missing stages remain honest", async () => { load.mockResolvedValue({ok:true,data:unavailable()}); const html=renderToStaticMarkup(await Simulation()); expect(html).toContain("No recorded agent activity for this stage."); expect(html).toContain("AI activity unavailable."); expect(html).toContain("No AI recommendation available."); });
  it("settings handles no assumptions with no form controls", async () => { load.mockResolvedValue({ok:true,data:unavailable()}); const html=renderToStaticMarkup(await Settings()); expect(html).toContain("No assumptions recorded in this payload."); expect(html).not.toMatch(/<(input|select|button|form)\b/); });
  it("failed safety is disclosed with STOW instead of success", async () => { const data=unavailable(); data.safety.checks[0]={...data.safety.checks[0],passed:false,reason:"Test severe wind"}; data.safety.passed=false; data.safety.reason="Test safety failure"; data.decision={action:"STOW",target_angle_deg:0,reason:"Test severe wind"}; data.farm_status.rows[0].action="STOW"; load.mockResolvedValue({ok:true,data:frontendDataSchema.parse(data)}); const html=renderToStaticMarkup(await Simulation()); expect(html).toContain("STOW"); expect(html).toContain("Needs attention"); expect(html).toContain("Test severe wind"); });
});
