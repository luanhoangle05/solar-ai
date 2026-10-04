-- Bootstrap, not a migration engine. Python executes this in one transaction.
-- IF NOT EXISTS makes unchanged bootstrap reruns safe. Future schema changes
-- require a new reviewed SQL version; this file does not repair schema drift.
CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS ingest;

CREATE TABLE IF NOT EXISTS ops.pipeline_runs (
    run_id uuid PRIMARY KEY,
    started_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at timestamptz,
    status text NOT NULL CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED')),
    config_version text NOT NULL,
    records_received integer NOT NULL DEFAULT 0 CHECK (records_received >= 0),
    records_accepted integer NOT NULL DEFAULT 0 CHECK (records_accepted >= 0),
    error_code text,
    error_message text,
    CHECK (finished_at IS NULL OR finished_at >= started_at)
);

CREATE TABLE IF NOT EXISTS ingest.weather_fetches (
    fetch_id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES ops.pipeline_runs(run_id),
    idempotency_key text NOT NULL UNIQUE CHECK (length(idempotency_key) > 0),
    site_id text NOT NULL,
    latitude_deg double precision NOT NULL CHECK (latitude_deg BETWEEN -90 AND 90),
    longitude_deg double precision NOT NULL CHECK (longitude_deg BETWEEN -180 AND 180),
    provider text NOT NULL,
    provider_model text,
    request_parameters jsonb NOT NULL,
    fetched_at timestamptz NOT NULL,
    forecast_issued_at timestamptz,
    payload jsonb NOT NULL,
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (forecast_issued_at IS NULL OR forecast_issued_at <= fetched_at)
);

CREATE TABLE IF NOT EXISTS ingest.weather_hourly (
    fetch_id uuid NOT NULL REFERENCES ingest.weather_fetches(fetch_id),
    interval_start timestamptz NOT NULL,
    prediction_horizon_minutes integer NOT NULL CHECK (prediction_horizon_minutes = 60),
    temperature_c double precision,
    cloud_cover_pct double precision,
    precipitation_mm double precision,
    wind_speed_kmh double precision,
    wind_gust_kmh double precision,
    ghi_wm2 double precision,
    dni_wm2 double precision,
    dhi_wm2 double precision,
    validation_status text NOT NULL CHECK (validation_status IN ('VALID', 'DEGRADED', 'STALE', 'INVALID')),
    validation_issues jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(validation_issues) = 'array'),
    PRIMARY KEY (fetch_id, interval_start, prediction_horizon_minutes)
);

CREATE INDEX IF NOT EXISTS weather_hourly_interval_idx
    ON ingest.weather_hourly(interval_start);
CREATE INDEX IF NOT EXISTS weather_fetches_site_time_idx
    ON ingest.weather_fetches(site_id, fetched_at DESC);

CREATE TABLE IF NOT EXISTS ingest.solar_position (
    site_id text NOT NULL,
    latitude_deg double precision NOT NULL CHECK (latitude_deg BETWEEN -90 AND 90),
    longitude_deg double precision NOT NULL CHECK (longitude_deg BETWEEN -180 AND 180),
    interval_start timestamptz NOT NULL,
    prediction_horizon_minutes integer NOT NULL CHECK (prediction_horizon_minutes = 60),
    calculated_for timestamptz NOT NULL,
    calculation_version text NOT NULL,
    sun_elevation_deg double precision NOT NULL CHECK (sun_elevation_deg BETWEEN -90 AND 90),
    sun_azimuth_deg double precision NOT NULL CHECK (sun_azimuth_deg >= 0 AND sun_azimuth_deg < 360),
    PRIMARY KEY (site_id, interval_start, prediction_horizon_minutes, calculation_version),
    CHECK (calculated_for >= interval_start
        AND calculated_for < interval_start + prediction_horizon_minutes * INTERVAL '1 minute')
);
