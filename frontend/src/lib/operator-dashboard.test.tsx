import { beforeAll, describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { loadFrontendData } from "./frontend-data.server";
import { getOperatorAnalysis, replayStage } from "./operator-dashboard";
import { AiCommandCenter } from "../components/dashboard/ai-command-center";
import type { FrontendData } from "../types/solar";
let fixture: FrontendData;
beforeAll(async () => { fixture = await loadFrontendData(); });
const render = (data: FrontendData) => renderToStaticMarkup(<AiCommandCenter analysis={getOperatorAnalysis(data)}/>);
describe("operator recommendation truthfulness", () => {
  it("replays presentation without changing loaded business state", () => {
    const before = structuredClone(fixture);
    const html = render(fixture);
    expect(html).toContain("Run AI Analysis");
    expect(html).not.toMatch(/Replay|Run Again|Analyzing…/);
    expect(html).toContain('href="/simulation"');
    expect(html).toContain("Recommendation only");
    expect(html).not.toMatch(/Run Optimization|Apply Configuration|Execute ROTATE/);
    expect(fixture).toEqual(before);
    expect([0,1200,2400,3600,4800,10000].map(ms => replayStage(ms))).toEqual([0,1,2,3,4,4]);
    expect(replayStage(0, true)).toBe(4);
  });
  it("keeps HOLD stationary and preserves the loaded STOW target", () => {
    const data = structuredClone(fixture);
    data.decision.action = "HOLD";
    expect(getOperatorAnalysis(data).angle).not.toContain("→");
    expect(render(data)).toContain("Keep current angle");
    data.decision.action = "STOW";
    data.decision.target_angle_deg = 0;
    expect(getOperatorAnalysis(data).angle).toBe("0°");
    expect(render(data)).toContain("Protective stow recommendation");
    expect(render(data)).not.toContain("Run AI Analysis");
  });
  it("does not celebrate blocked or negative outcomes", () => {
    const data = structuredClone(fixture);
    data.optimization!.net_benefit_kwh_equivalent = -0.2;
    expect(getOperatorAnalysis(data).positive).toBe(false);
    data.safety.passed = false;
    const html = render(data);
    expect(html).toContain("Operation blocked");
    expect(html).not.toContain("Your operating recommendation is ready.");
    expect(html).not.toContain("Safe to proceed");
  });
  it("does not claim a recommendation when optimization is absent", () => {
    const data = structuredClone(fixture);
    data.optimization = null;
    expect(render(data)).toContain("No AI recommendation available");
    expect(render(data)).not.toContain("Safe to proceed");
    expect(render(data)).not.toContain("Run AI Analysis");
  });
  it("handles absent weather, candidates, activity, and target without inventing evidence", () => {
    const data = structuredClone(fixture);
    data.current_weather = null;
    data.candidate_predictions = [];
    data.agent_log = [];
    data.errors = [];
    data.metadata.control_target_id = "missing-row";
    const analysis = getOperatorAnalysis(data);
    expect(analysis.stages[0].issue).toBe(true);
    expect(analysis.stages[1].issue).toBe(true);
    expect(analysis.stages[2].detail).toContain("no agent activity supplied");
    data.decision.action = "ROTATE";
    expect(getOperatorAnalysis(data).instruction).toBe("Control target unavailable");
  });
});
