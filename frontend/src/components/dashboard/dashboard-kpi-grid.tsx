import { CirclePlus, PanelsTopLeft, Scale, Zap } from "lucide-react";
import type { DashboardSummary } from "@/lib/dashboard";
import { formatKwh, formatKwhEquivalent, formatSignedKwh } from "@/lib/formatters";
import type { FarmStatus, Metadata } from "@/types/solar";

export function DashboardKpiGrid({ summary, metadata, farm }: { summary: DashboardSummary; metadata: Metadata; farm: FarmStatus }) {
  const scope = `${metadata.energy_scope} / ${metadata.prediction_horizon_minutes} min`;
  const metrics = [
    { label: "Predicted Energy", value: formatKwh(summary.predictedKwh), detail: scope, icon: Zap },
    { label: "Energy Gain", value: formatSignedKwh(summary.energyGainKwh), detail: `vs baseline · ${scope}`, icon: CirclePlus },
    { label: "Total Panels", value: farm.total_panels.toLocaleString("en-US"), detail: `${farm.rows.length} rows · ${farm.zones.length} zones`, icon: PanelsTopLeft },
    { label: "Net Benefit", value: formatKwhEquivalent(summary.netBenefitKwhEquivalent), detail: `After movement cost · ${scope}`, icon: Scale },
  ];
  return <section className="dashboard-kpis" aria-label="Run key metrics">{metrics.map(({ label, value, detail, icon: Icon }) =>
    <div className="dashboard-kpi" data-unavailable={value === "Unavailable"} key={label}><Icon aria-hidden="true" /><div><h2>{label}</h2><p className="kpi-value">{value}</p><p className="dashboard-note">{detail}</p></div></div>
  )}</section>;
}
