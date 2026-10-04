import type { FrontendData } from "../types/solar";
import { dataStatusVariants } from "../config/status";

/** Units follow the explicit CurrentWeather field suffixes in the shared schema. */
export function getWeatherView(data: Pick<FrontendData, "current_weather" | "data_agent">) {
  const w = data.current_weather, report = data.data_agent;
  return {
    conditions: w ? { temperature: `${w.temperature_c}°C`, cloud: `${w.cloud_cover_pct}%`, precipitation: `${w.precipitation_mm} mm`, wind: `${w.wind_speed_kmh} km/h`, gust: `${w.wind_gust_kmh} km/h` } : null,
    irradiance: w ? [
      { label: "GHI", description: "Global Horizontal Irradiance", value: w.ghi_wm2 },
      { label: "DNI", description: "Direct Normal Irradiance", value: w.dni_wm2 },
      { label: "DHI", description: "Diffuse Horizontal Irradiance", value: w.dhi_wm2 },
    ] : [],
    quality: { ...report, variant: dataStatusVariants[report.status], age: report.forecast_age_minutes === null ? "Unavailable" : `${report.forecast_age_minutes} min`, cache: report.used_cache ? "Yes" : "No" },
  };
}
