import Link from "next/link";
import { Cloud, CloudSun, Droplets, Sun, Wind } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { Badge } from "@/components/ui/badge";
import { dataStatusVariants } from "@/config/status";
import type { CurrentWeather, DataAgentReport } from "@/types/solar";

export function WeatherSummary({ weather, report, isMock }: { weather: CurrentWeather | null; report: DataAgentReport; isMock: boolean }) {
  return <DashboardPanel title="Weather Conditions" icon={CloudSun} className="dashboard-weather" action={<Link href="/weather" className="dashboard-link" aria-label="Weather workspace">↗</Link>}>
    <p className="eyebrow">{isMock ? "Mock fixture" : "Recorded conditions"}</p>
    {weather ? <><div className="weather-temperature"><Sun aria-hidden="true"/><div><strong>{weather.temperature_c}°C</strong><span>Temperature</span></div></div>
      <dl className="weather-values"><div><dt><Sun aria-hidden="true"/>Global irradiance</dt><dd>{weather.ghi_wm2} <small>W/m²</small></dd></div><div><dt><Wind aria-hidden="true"/>Wind</dt><dd>{weather.wind_speed_kmh} <small>km/h</small></dd></div><div><dt><Cloud aria-hidden="true"/>Cloud cover</dt><dd>{weather.cloud_cover_pct}%</dd></div><div><dt><Wind aria-hidden="true"/>Wind gust</dt><dd>{weather.wind_gust_kmh} <small>km/h</small></dd></div><div><dt><Droplets aria-hidden="true"/>Precipitation</dt><dd>{weather.precipitation_mm} <small>mm</small></dd></div><div><dt>Direct / diffuse</dt><dd>{weather.dni_wm2} / {weather.dhi_wm2} <small>W/m²</small></dd></div></dl>
    </> : <p className="dashboard-empty">Weather unavailable.</p>}
    <div className="weather-status"><span>Data: <Badge variant={dataStatusVariants[report.status]}>{report.status}</Badge></span><span>{report.source}</span></div>
    <p className="dashboard-note">Age at {isMock ? "fixture" : "recorded"} run: {report.forecast_age_minutes === null ? "Unknown" : report.forecast_age_minutes + " min"} · Cache: {report.used_cache ? "Yes" : "No"}</p>
    {report.issues.length > 0 && <ul className="data-issues">{report.issues.map((issue,index) => <li key={index}>{issue}</li>)}</ul>}
  </DashboardPanel>;
}
