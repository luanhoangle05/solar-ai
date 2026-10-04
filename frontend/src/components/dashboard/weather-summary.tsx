import Link from "next/link";
import { Cloud, Droplets, Sun, Thermometer, Wind } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { Badge } from "@/components/ui/badge";
import { dataStatusVariants } from "@/config/status";
import type { CurrentWeather, DataAgentReport } from "@/types/solar";
import { getWeatherView } from "@/lib/weather";

export function WeatherSummary({ weather, report, isMock }: { weather: CurrentWeather | null; report: DataAgentReport; isMock: boolean }) {
  const view = getWeatherView({current_weather: weather, data_agent: report});
  return <DashboardPanel title="Environmental Input" icon={Sun} className="dashboard-weather" action={<Link href="/weather" className="dashboard-link" aria-label="Weather workspace">↗</Link>}>
    <p className="eyebrow">{isMock ? "Mock fixture" : "Recorded conditions"}</p>
    {weather && view.conditions ? <><div className="weather-temperature"><Sun aria-hidden="true"/><div><span>Solar irradiance · GHI</span><strong>{weather.ghi_wm2} <small>W/m²</small></strong></div></div>
      <dl className="weather-values"><div><dt><Thermometer aria-hidden="true"/>Temperature</dt><dd>{view.conditions.temperature}</dd></div><div><dt><Cloud aria-hidden="true"/>Cloud cover</dt><dd>{view.conditions.cloud}</dd></div><div><dt><Wind aria-hidden="true"/>Wind</dt><dd>{view.conditions.wind}</dd></div><div><dt><Wind aria-hidden="true"/>Wind gust</dt><dd>{view.conditions.gust}</dd></div><div><dt><Droplets aria-hidden="true"/>Precipitation</dt><dd>{view.conditions.precipitation}</dd></div><div><dt>DNI / DHI</dt><dd>{weather.dni_wm2} / {weather.dhi_wm2} <small>W/m²</small></dd></div></dl>
    </> : <p className="dashboard-empty">Environmental input unavailable.</p>}
    <div className="weather-status"><span>Data: <Badge variant={dataStatusVariants[report.status]}>{report.status}</Badge></span><span>{report.source}</span></div>
    <p className="dashboard-note">Age at {isMock ? "fixture" : "recorded"} run: {report.forecast_age_minutes === null ? "Unknown" : report.forecast_age_minutes + " min"} · Cache: {report.used_cache ? "Yes" : "No"}</p>
    {report.issues.length > 0 && <ul className="data-issues">{report.issues.map((issue,index) => <li key={index}>{issue}</li>)}</ul>}
  </DashboardPanel>;
}
