import { Cloud, Droplets, Sun, Thermometer, Wind, ScanLine } from "lucide-react";
import { DataError } from "@/components/shared/data-error";
import { InspectionPage, PredictionFacts } from "@/components/shared/inspection-page";
import { OperationsPanel } from "@/components/agents/operations-panel";
import { DataQuality } from "@/components/agents/operations-outcomes";
import { getAgentsSummary } from "@/lib/agents";
import { loadFrontendDataResult } from "@/lib/frontend-data.server";
import { getWeatherView } from "@/lib/weather";

export const metadata = { title: "Weather & Irradiance | SolarAI" };
export default async function Page() {
  const result = await loadFrontendDataResult();
  if (!result.ok) return <DataError message={result.error.message} details={result.error.details}/>;
  const data = result.data, view = getWeatherView(data), conditions = view.conditions;
  const maximum = Math.max(...view.irradiance.map(item => item.value), 0);
  return <InspectionPage data={data} icon={Sun} title="Weather & Irradiance" description="Inspect the environmental inputs supplied to the current SolarAI prediction run.">
    <div className="inspect-grid">
      <OperationsPanel title="Current Environmental Inputs" icon={Thermometer}>
        {conditions ? <><div className="inspect-hero"><Thermometer size={58} aria-hidden="true"/><div><span>Temperature</span><strong>{conditions.temperature}</strong></div></div><div className="inspect-weather-values"><div><span><Cloud size={16} aria-hidden="true"/>Cloud cover</span><strong>{conditions.cloud}</strong></div><div><span><Droplets size={16} aria-hidden="true"/>Precipitation</span><strong>{conditions.precipitation}</strong></div></div></> : <p className="inspect-empty">Weather input unavailable for this payload.</p>}
        <p className="inspect-note">Single supplied snapshot for the recorded prediction interval.</p>
      </OperationsPanel>
      <OperationsPanel title="Solar Irradiance" icon={Sun} meta={<span className="ops-note">W/m² · supplied input</span>}>
        {view.irradiance.length ? <ul className="inspect-irradiance">{view.irradiance.map(item => <li key={item.label}><div><div><b>{item.label}</b><small>{item.description}</small></div><strong>{item.value} <span>W/m²</span></strong></div><div className="inspect-track" aria-hidden="true"><span style={{width:`${maximum ? item.value / maximum * 100 : 0}%`}}/></div></li>)}</ul> : <p className="inspect-empty">Irradiance inputs unavailable.</p>}
        <p className="inspect-note">Bars compare supplied irradiance values; they are not a time series.</p>
      </OperationsPanel>
      <OperationsPanel title="Wind Conditions" icon={Wind} className="inspect-wind">
        {conditions ? <><div className="inspect-hero"><Wind size={52} aria-hidden="true"/><div><span>Wind speed</span><strong>{conditions.wind}</strong></div></div><div className="inspect-weather-values"><div><span>Wind gust</span><strong>{conditions.gust}</strong></div><div><span>Assessment</span><p className="inspect-note">See the recorded safety checks for the Manager decision.</p></div></div></> : <p className="inspect-empty">Wind inputs unavailable.</p>}
      </OperationsPanel>
      <div className="inspect-quality" data-quality={view.quality.status}><DataQuality summary={getAgentsSummary(data)}/></div>
      <OperationsPanel title="Prediction Context" icon={ScanLine} className="inspect-wide"><div className="inspect-context"><div><h3>Environmental inputs → row prediction</h3><p className="inspect-note">The supplied temperature, cloud, precipitation, wind, and irradiance values describe the input to this run. Energy predictions apply to the named control row over the stated interval.</p><p className="inspect-note">{data.metadata.dataset_kind === "MOCK" ? "These weather values are hand-authored fixture inputs, not provider observations." : "Source and quality are reported by the Data Agent."}</p></div><PredictionFacts metadata={data.metadata}/></div></OperationsPanel>
    </div>
  </InspectionPage>;
}
