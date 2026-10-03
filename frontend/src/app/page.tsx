import {
  Activity,
  ArrowUpRight,
  Database,
  Gauge,
  MoveDiagonal2,
  ShieldCheck,
  Sparkles,
  SunMedium,
} from "lucide-react";

import { DataModeBanner } from "@/components/shared/data-mode-banner";
import { DecisionCard } from "@/components/shared/decision-card";
import { MetricCard } from "@/components/shared/metric-card";
import { StatusBadge } from "@/components/shared/status-badge";
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

function ErrorState({
  message,
  details,
}: {
  message: string;
  details?: string;
}) {
  return (
    <main
      className="min-h-screen px-6 py-10 text-foreground sm:px-10 lg:px-16"
      style={{ backgroundColor: "var(--background)" }}
    >
      <div className="mx-auto max-w-4xl">
        <Card className="border-danger/40">
          <CardHeader>
            <CardDescription>Frontend Data Contract</CardDescription>
            <CardTitle className="text-danger">
              Unable to load SolarAI data
            </CardTitle>
          </CardHeader>

          <CardContent className="space-y-4">
            <p className="text-sm text-foreground">{message}</p>
            {details ? (
              <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg border border-border bg-background/50 p-4 text-xs leading-6 text-muted-foreground">
                {details}
              </pre>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}

export default async function Home() {
  const result = await loadFrontendDataResult();

  if (!result.ok) {
    return (
      <ErrorState
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
    <main
      className="min-h-screen px-5 py-6 text-foreground sm:px-8 lg:px-12"
      style={{ backgroundColor: "var(--background)" }}
    >
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <header className="flex flex-col gap-5 border-b border-border pb-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex size-12 items-center justify-center rounded-xl border border-primary/30 bg-primary/10">
              <SunMedium className="size-7 text-warning" aria-hidden="true" />
            </div>

            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-semibold tracking-tight">
                  SolarAI
                </h1>
                <StatusBadge status="ready">
                  Contract Valid
                </StatusBadge>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                AI-Powered Solar Farm Optimization
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">
              Schema {data.metadata.schema_version}
            </Badge>
            <Badge variant="secondary">
              Target {data.metadata.control_target_id}
            </Badge>
          </div>
        </header>

        <DataModeBanner metadata={data.metadata} />

        <section>
          <div className="mb-4">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-primary">
              Phase 1 Â· Validated Contract Snapshot
            </p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight">
              Optimization recommendation from the shared frontend payload
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              Every value below is loaded from the repository fixture and
              validated before rendering. The frontend does not recalculate the
              optimizer, safety controller, or model output.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
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
                      variant={
                        data.data_agent.status === "VALID"
                          ? "success"
                          : "warning"
                      }
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
                      ? ` Â· ${selectedModel.implementation}`
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
                {weather ? `${weather.temperature_c}Â°C` : "Unavailable"}
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
                    <dd>{weather.ghi_wm2} W/mÂ²</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">DNI / DHI</dt>
                    <dd>
                      {weather.dni_wm2} / {weather.dhi_wm2} W/mÂ²
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
          Phase 1 deliberately renders only contract-backed values. Detailed
          dashboard layout, optimization charts, model comparison, agent
          timeline, and farm visualization are introduced in later phases.
        </footer>
      </div>
    </main>
  );
}
