import { CloudSun, Sun, Wind } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { Badge } from "@/components/ui/badge";
import { dataStatusVariants } from "@/config/status";
import type { CurrentWeather, DataAgentReport } from "@/types/solar";

export function WeatherSummary({ weather, report, isMock }: { weather: CurrentWeather | null; report: DataAgentReport; isMock: boolean }) {
  return (
    <DashboardPanel title="Current Conditions" icon={CloudSun} className="dashboard-weather" action={<Badge variant={dataStatusVariants[report.status]}>{report.status}</Badge>}>
      {weather ? <>
        <div className="weather-highlights">
          <div><CloudSun size={30} className="text-warning" aria-hidden="true" /><strong>{weather.temperature_c}°C</strong><span>Temperature</span></div>
          <div><Sun size={24} className="text-warning" aria-hidden="true" /><strong>{weather.ghi_wm2}<small> W/m²</small></strong><span>Global irradiance · GHI</span></div>
        </div>
        <dl className="weather-values">
          <div><dt>Cloud cover</dt><dd>{weather.cloud_cover_pct}%</dd></div>
          <div><dt>Precipitation</dt><dd>{weather.precipitation_mm} mm</dd></div>
          <div><dt><Wind size={12} aria-hidden="true" /> Wind</dt><dd>{weather.wind_speed_kmh} km/h</dd></div>
          <div><dt>Gust</dt><dd>{weather.wind_gust_kmh} km/h</dd></div>
          <div><dt>DNI</dt><dd>{weather.dni_wm2} W/m²</dd></div>
          <div><dt>DHI</dt><dd>{weather.dhi_wm2} W/m²</dd></div>
        </dl>
      </> : <p className="dashboard-empty">Weather unavailable.</p>}
      <dl className="data-agent-details">
        <div><dt>Data source</dt><dd>{report.source}</dd></div>
        <div><dt>Forecast age at {isMock ? "fixture run" : "recorded run"}</dt><dd>{report.forecast_age_minutes === null ? "Unknown" : report.forecast_age_minutes + " min"}</dd></div>
        <div><dt>Cache used</dt><dd>{report.used_cache ? "Yes" : "No"}</dd></div>
      </dl>
      {report.issues.length > 0 && <ul className="data-issues" aria-label="Data agent issues">{report.issues.map((issue, index) => <li key={index}>{issue}</li>)}</ul>}
    </DashboardPanel>
  );
}
