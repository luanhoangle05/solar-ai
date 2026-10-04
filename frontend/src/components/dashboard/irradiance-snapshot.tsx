import { Sun } from "lucide-react";
import { DashboardPanel } from "./dashboard-panel";
import { getWeatherView } from "@/lib/weather";
import type { FrontendData } from "@/types/solar";

export function IrradianceSnapshot({ data }: { data: FrontendData }) {
  const view = getWeatherView(data);
  const maximum = Math.max(0, ...view.irradiance.map(item => item.value));
  return <DashboardPanel title="Irradiance Snapshot" icon={Sun} className="dashboard-irradiance">
    <p className="dashboard-note">Environmental inputs for this recorded run.</p>
    {view.irradiance.length ? <><dl className="irradiance-bars">{view.irradiance.map(item => <div key={item.label}><dt><abbr title={item.description}>{item.label}</abbr></dt><dd><strong>{item.value} <small>W/m²</small></strong><span className="irradiance-track" aria-hidden="true"><i style={{ width: `${maximum ? item.value / maximum * 100 : 0}%` }}/></span></dd></div>)}</dl><p className="irradiance-temperature">Temperature <strong>{view.conditions?.temperature}</strong></p></> : <p className="dashboard-empty">Environmental input unavailable.</p>}
    <p className="dashboard-note">Zero-baseline comparison · not a time series.</p>
  </DashboardPanel>;
}
