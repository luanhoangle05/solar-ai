import { DashboardKpiGrid } from "@/components/dashboard/dashboard-kpi-grid";
import { EnvironmentalConditions } from "@/components/dashboard/environmental-conditions";
import { AiCommandCenter } from "@/components/dashboard/ai-command-center";
import { FarmHero } from "@/components/dashboard/farm-hero";

import { loadFrontendDataResult } from "@/lib/frontend-data.server";
import { getDashboardSummary } from "@/lib/dashboard";
import { getOperatorAnalysis } from "@/lib/operator-dashboard";
import "../(solar)/farm/farm.css";
import "./dashboard.css";

export default async function Dashboard() {
  const result = await loadFrontendDataResult();
  if (!result.ok) return <section className="operator-page"><p role="alert">Dashboard unavailable. There was a problem loading the farm information.</p></section>;
  const data = result.data;
  return <div className="operator-page">
    {data.errors.length > 0 && <p className="operator-alert" role="alert">Some AI analysis needs attention. Review the recommendation before proceeding.</p>}
    <div className="operator-grid">
      <EnvironmentalConditions data={data}/>
      <DashboardKpiGrid summary={getDashboardSummary(data)} metadata={data.metadata} farm={data.farm_status}/>
      <FarmHero farm={data.farm_status} targetId={data.metadata.control_target_id} weather={data.current_weather}/>
      <AiCommandCenter analysis={getOperatorAnalysis(data)}/>

    </div>
  </div>;
}
