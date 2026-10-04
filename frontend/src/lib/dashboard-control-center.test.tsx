import { beforeAll, describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { loadFrontendData } from "./frontend-data.server";
import { getDashboardSummary } from "./dashboard";
import { DashboardKpiGrid } from "../components/dashboard/dashboard-kpi-grid";
import { OptimizationResult } from "../components/dashboard/optimization-result";
import { ControlTargetDetails } from "../components/dashboard/control-target-details";
import { IrradianceSnapshot } from "../components/dashboard/irradiance-snapshot";
import { AgentActivityPreview } from "../components/dashboard/agent-activity-preview";
import { SelectedModelSummary } from "../components/dashboard/selected-model-summary";
import { FarmOverview } from "../components/dashboard/farm-overview";
import type { FrontendData } from "../types/solar";
let fixture: FrontendData;
beforeAll(async () => { fixture = await loadFrontendData(); });
function renderResult(data: FrontendData) { return renderToStaticMarkup(<OptimizationResult data={data} summary={getDashboardSummary(data)}/>); }
describe("dashboard control center contract presentation", () => {
  it("keeps energy row-scoped and farm size separate without mutating the payload", () => {
    const before = structuredClone(fixture);
    const html = renderToStaticMarkup(<DashboardKpiGrid summary={getDashboardSummary(fixture)} metadata={fixture.metadata} farm={fixture.farm_status}/>);
    expect(html).toContain("row / 60 min");
    for (const value of ["Predicted Energy", "Energy Gain", "Total Panels", "Net Benefit", "1,000", "6.09"]) expect(html).toContain(value);
    expect(fixture).toEqual(before);
  });
  it("presents a blocked negative result without positive net styling or execution controls", () => {
    const data = structuredClone(fixture);
    data.safety.passed = false;
    data.optimization!.net_benefit_kwh_equivalent = -0.2;
    const html = renderResult(data);
    expect(html).toContain("Safety BLOCKED");
    expect(html).toContain('data-positive="false"');
    expect(html).toContain("execution not confirmed");
    expect(html).not.toMatch(/<(button|input|select)\b/);
  });
  it("shows HOLD without a rotation arrow and keeps a zero-degree STOW target", () => {
    const data = structuredClone(fixture);
    data.decision.action = "HOLD";
    expect(renderResult(data)).not.toContain("→");
    expect(renderToStaticMarkup(<FarmOverview summary={getDashboardSummary(data)} farm={data.farm_status}/>)).not.toContain("→");
    data.decision.action = "STOW";
    data.decision.target_angle_deg = 0;
    expect(renderResult(data)).toContain("35° → 0°");
  });
  it("renders missing optimization and target honestly", () => {
    const data = structuredClone(fixture);
    data.optimization = null;
    data.metadata.control_target_id = "missing-row";
    expect(renderResult(data)).toContain("Optimization unavailable");
    const html = renderToStaticMarkup(<ControlTargetDetails summary={getDashboardSummary(data)} safety={data.safety}/>);
    expect(html).toContain("Control target unavailable");
    expect(html).not.toContain("row-001");
  });
  it("shows loaded irradiance, including zeros, and handles missing weather", () => {
    const data = structuredClone(fixture);
    data.current_weather!.ghi_wm2 = 0;
    let html = renderToStaticMarkup(<IrradianceSnapshot data={data}/>);
    expect(html).toContain("width:0%");
    expect(html).toContain("not a time series");
    data.current_weather = null;
    html = renderToStaticMarkup(<IrradianceSnapshot data={data}/>);
    expect(html).toContain("Environmental input unavailable");
    expect(html).not.toContain("irradiance-track");
  });
  it("does not invent agent activity or selected-model provenance", () => {
    const data = structuredClone(fixture);
    data.agent_log = [];
    data.errors = [];
    const html = renderToStaticMarkup(<AgentActivityPreview data={data}/>);
    expect(html.match(/No recorded activity\./g)).toHaveLength(4);
    expect(html).not.toContain("Online");
    expect(renderToStaticMarkup(<SelectedModelSummary model={null}/>)).toContain("Prediction model unavailable");
  });
  it("handles empty farm presentation without fabricating zones", () => {
    const data = structuredClone(fixture);
    data.farm_status.rows = [];
    data.farm_status.zones = [];
    const html = renderToStaticMarkup(<FarmOverview summary={getDashboardSummary(data)} farm={data.farm_status}/>);
    expect(html).toContain("Farm overview unavailable");
    expect(html).not.toContain("zone-arrays");
  });
});
