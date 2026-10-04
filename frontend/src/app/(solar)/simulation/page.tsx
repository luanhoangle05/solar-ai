import { loadFrontendDataResult, loadZoneRuns } from "@/lib/frontend-data.server";
import { SolarFarmSimulation } from "@/components/simulation/solar-farm-simulation";
export const metadata = { title: "Simulation | SolarAI" };
export default async function Page() {
  const result = await loadFrontendDataResult();
  if (!result.ok) return <p role="alert">Simulation unavailable. There was a problem loading the farm information.</p>;
  const zoneRuns = await loadZoneRuns();
  return <SolarFarmSimulation data={result.data} zoneRuns={zoneRuns.runs} zoneRunsError={zoneRuns.error}/>;
}
