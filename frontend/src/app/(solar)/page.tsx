import {
  Activity,
  ArrowUpRight,
  Database,
  Gauge,
  MoveDiagonal2,
  ShieldCheck,
  Sparkles,
  LayoutDashboard,
} from "lucide-react";

import { DataModeBanner } from "@/components/shared/data-mode-banner";
import { DecisionCard } from "@/components/shared/decision-card";
import { MetricCard } from "@/components/shared/metric-card";
import { PageHeader } from "@/components/layout/page-header";
import { DataError } from "@/components/shared/data-error";
import { dataStatusVariants } from "@/config/status";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  formatAngle,
  formatKwh,
  formatKwhEquivalent,
  formatModelName,
  formatSignedKwh,
} from "@/lib/formatters";
import { loadFrontendDataResult } from "@/lib/frontend-data.server";
import {
  getControlTargetRow,
  getFrontendSummary,
  getSelectedModel,
} from "@/lib/selectors";

export default async function Home() {
  const result = await loadFrontendDataResult();

  if (!result.ok) {
    return (
      <DataError
        message={result.error.message}
        details={result.error.details}
      />
    );
  }

  const data = result.data;
  const summary = getFrontendSummary(data);
  const targetRow = getControlTargetRow(data);
  const selectedModel = getSelectedModel(data);
  const weather = data.current_weather;

  return (
    <div className="flex min-w-0 flex-col gap-4">
        <PageHeader icon={LayoutDashboard} title="Dashboard" description="Validated contract snapshot for solar farm optimization." actions={<Badge variant="outline">Target {data.metadata.control_target_id}</Badge>} />
        <DataModeBanner metadata={data.metadata} />

        <section>
          <div className="mb-3">
            <h2 className="text-base font-semibold">Optimization recommendation</h2>
            <p className="mt-1 text-xs text-muted-foreground">Contract-provided values for one row over a {data.metadata.prediction_horizon_minutes}-minute interval.</p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            <MetricCard
              label="Current Angle"
              value={formatAngle(summary.currentAngleDeg)}
              detail={`Observed ${data.metadata.control_target_id}`}
              icon={Gauge}
            />
            <MetricCard
              label="Recommended Angle"
              value={formatAngle(summary.recommendedAngleDeg)}
              detail="Optimization recommendation"
              icon={MoveDiagonal2}
            />
            <MetricCard
              label="Predicted Energy"
              value={formatKwh(summary.predictedKwh)}
              detail={`${data.metadata.prediction_horizon_minutes}-minute ${data.metadata.energy_scope} interval`}
              icon={Sparkles}
            />
            <MetricCard
              label="Energy Gain"
              value={formatSignedKwh(summary.energyGainKwh)}
              detail="Provided by optimizer contract"
              icon={ArrowUpRight}
            />
            <MetricCard
              label="Net Benefit"
              value={formatKwhEquivalent(
                summary.netBenefitKwhEquivalent,
              )}
              detail="After movement cost, supplied by backend contract"
              icon={Activity}
            />
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
          <DecisionCard
            decision={data.decision}
            safetyPassed={data.safety.passed}
          />

          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardDescription>Contract & Data Health</CardDescription>
                  <CardTitle className="mt-2">
                    Validated before render
                  </CardTitle>
                </div>
                <ShieldCheck
                  className="size-6 text-success"
                  aria-hidden="true"
                />
              </div>
            </CardHeader>

            <CardContent>
              <dl className="grid gap-3 text-sm">
                <div className="flex items-center justify-between gap-4 border-b border-border pb-3">
                  <dt className="text-muted-foreground">Data Agent</dt>
                  <dd>
                    <Badge
                      variant={dataStatusVariants[data.data_agent.status]}
                    >
                      {data.data_agent.status}
                    </Badge>
                  </dd>
                </div>

                <div className="flex items-center justify-between gap-4 border-b border-border pb-3">
                  <dt className="text-muted-foreground">Source</dt>
                  <dd className="font-medium">{data.data_agent.source}</dd>
                </div>

                <div className="flex items-center justify-between gap-4 border-b border-border pb-3">
                  <dt className="text-muted-foreground">
                    Forecast age at fixture run
                  </dt>
                  <dd className="font-medium">
                    {data.data_agent.forecast_age_minutes === null
                      ? "Unknown"
                      : `${data.data_agent.forecast_age_minutes} min`}
                  </dd>
                </div>

                <div className="flex items-center justify-between gap-4 border-b border-border pb-3">
                  <dt className="text-muted-foreground">Selected model</dt>
                  <dd className="font-medium">
                    {formatModelName(data.selected_model)}
                    {selectedModel
                      ? ` · ${selectedModel.implementation}`
                      : ""}
                  </dd>
                </div>

                <div className="flex items-center justify-between gap-4">
                  <dt className="text-muted-foreground">Safety checks</dt>
                  <dd className="font-medium">
                    {data.safety.checks.filter((check) => check.passed).length}
                    /{data.safety.checks.length} passed
                  </dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </section>

        <section className="grid gap-4 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <CardDescription>Current Weather</CardDescription>
              <CardTitle className="mt-2">
                {weather ? `${weather.temperature_c}°C` : "Unavailable"}
              </CardTitle>
            </CardHeader>

            <CardContent>
              {weather ? (
                <dl className="grid gap-3 text-sm">
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">Cloud cover</dt>
                    <dd>{weather.cloud_cover_pct}%</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">Wind / gust</dt>
                    <dd>
                      {weather.wind_speed_kmh} / {weather.wind_gust_kmh} km/h
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">GHI</dt>
                    <dd>{weather.ghi_wm2} W/m²</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">DNI / DHI</dt>
                    <dd>
                      {weather.dni_wm2} / {weather.dhi_wm2} W/m²
                    </dd>
                  </div>
                </dl>
              ) : (
                <p className="text-sm text-muted-foreground">
                  The contract contains no current-weather payload.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardDescription>Farm Contract</CardDescription>
              <CardTitle className="mt-2">
                {data.farm_status.total_panels.toLocaleString()} panels
              </CardTitle>
            </CardHeader>

            <CardContent>
              <dl className="grid gap-3 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Zones</dt>
                  <dd>{data.farm_status.zones.length}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Rows</dt>
                  <dd>{data.farm_status.rows.length}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Control row</dt>
                  <dd>{targetRow?.row_id ?? "Unavailable"}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Row state</dt>
                  <dd>{targetRow?.current_state ?? "Unavailable"}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardDescription>Run Provenance</CardDescription>
              <CardTitle className="mt-2">Reproducible fixture</CardTitle>
            </CardHeader>

            <CardContent className="space-y-4">
              <div className="flex items-start gap-3 text-sm">
                <Database
                  className="mt-0.5 size-4 shrink-0 text-primary"
                  aria-hidden="true"
                />
                <div>
                  <p className="font-medium text-foreground">
                    {data.metadata.config_id}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    Energy scope: {data.metadata.energy_scope}; horizon:{" "}
                    {data.metadata.prediction_horizon_minutes} minutes.
                  </p>
                </div>
              </div>

              <p className="text-xs leading-5 text-muted-foreground">
                Fixture timestamp: {data.timestamp}
              </p>
            </CardContent>
          </Card>
        </section>

        <footer className="border-t border-border py-5 text-xs leading-5 text-muted-foreground">
          This snapshot renders only contract-backed values. Detailed
          dashboard layout, optimization charts, model comparison, agent
          timeline, and farm visualization are introduced in later phases.
        </footer>
    </div>
  );
}
