"""Luan-owned PostgreSQL persistence; no provider calls or agent decisions."""

from contextlib import contextmanager
from collections.abc import Iterator
from dataclasses import asdict
from datetime import timedelta
import hashlib
import json
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb
import pvlib

from src.common.config import DatabaseConfig, DEFAULT_CONFIG, SimulationConfig
from src.common.tool_contracts import RawWeather, SolarPosition, ToolError, WeatherRequest
from src.pipeline.validate import WEATHER_FIELDS, _finite_number, _parse_timestamp, validate_weather


@contextmanager
def database_connection(config: DatabaseConfig) -> Iterator[psycopg.Connection]:
    """Commit on success, roll back on failure, and always close the connection.

    Use keyword parameters rather than constructing/logging a credential DSN.
    Database exceptions are reduced to a safe message (no credential details).
    """
    try:
        with psycopg.connect(
            dbname=config.dbname, user=config.user, password=config.password,
            host=config.host, port=config.port, connect_timeout=config.connect_timeout,
            application_name="solar-farm-ai", options="-c timezone=UTC",
        ) as connection:
            yield connection
    except psycopg.Error:
        raise ToolError("PostgreSQL operation failed; check database health and configuration") from None


def check_database_connection(config: DatabaseConfig) -> bool:
    """Perform a minimal query with automatic connection cleanup."""
    with database_connection(config) as connection:
        return connection.execute("SELECT 1").fetchone() == (1,)


def _json_hash(value: object) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError, UnicodeError):
        raise ToolError("Weather payload must contain JSON-compatible finite values") from None
    return hashlib.sha256(encoded).hexdigest()


def _request_metadata(request: WeatherRequest) -> tuple[str, dict]:
    if not isinstance(request, WeatherRequest):
        raise ToolError("request: expected WeatherRequest")
    for name, limit in (("latitude_deg", 90), ("longitude_deg", 180)):
        value = getattr(request, name)
        if not _finite_number(value) or not -limit <= value <= limit:
            raise ToolError(f"{name}: invalid coordinates")
    if type(request.prediction_horizon_minutes) is not int or request.prediction_horizon_minutes != 60:
        raise ToolError("prediction_horizon_minutes: expected shared one-hour interval")
    metadata = asdict(request)
    metadata["interval_start"] = _parse_timestamp(request.interval_start, "interval_start").isoformat()
    for name in ("latitude_deg", "longitude_deg"):
        metadata[name] = float(metadata[name]) or 0.0
    site = _json_hash([metadata["latitude_deg"], metadata["longitude_deg"]])
    return site, metadata


def _prepare_weather(request: WeatherRequest, weather: RawWeather, config: SimulationConfig):
    site, metadata = _request_metadata(request)
    expected = {"timestamp", "source", "fetched_at", "forecast_issued_at", *WEATHER_FIELDS}
    if not isinstance(weather, dict) or set(weather) != expected:
        raise ToolError("weather: expected exact RawWeather fields")
    if not isinstance(weather["source"], str) or not weather["source"].strip() or "\x00" in weather["source"]:
        raise ToolError("source: expected nonempty PostgreSQL-compatible string")
    canonical = dict(weather)
    for name in ("timestamp", "fetched_at", "forecast_issued_at"):
        if name == "forecast_issued_at" and weather[name] is None:
            continue
        canonical[name] = _parse_timestamp(weather[name], name).isoformat()
    if canonical["timestamp"] != metadata["interval_start"]:
        raise ToolError("weather timestamp does not match requested interval")
    if (canonical["forecast_issued_at"] is not None and
            _parse_timestamp(canonical["forecast_issued_at"], "forecast_issued_at") >
            _parse_timestamp(canonical["fetched_at"], "fetched_at")):
        raise ToolError("forecast_issued_at: later than fetched_at")
    for name in WEATHER_FIELDS:
        if weather[name] is not None:
            if not _finite_number(weather[name]):
                raise ToolError(f"{name}: expected finite number or None")
            canonical[name] = float(weather[name]) or 0.0
    report = validate_weather(canonical, now=canonical["fetched_at"], config=config)
    # Download time is provenance, not forecast identity. A retry keeps the
    # first stored download time and validation snapshot of that observation.
    identity = {key: value for key, value in canonical.items() if key != "fetched_at"}
    key = _json_hash({"version": 1, "request": metadata, "weather": identity})
    return site, metadata, canonical, report, key


class PostgresWeatherStorage:
    """Storage portion of WeatherTools, preserving its two method signatures.

    RawWeather has no validation field; the immutable validation snapshot
    remains in weather_hourly. The future agent revalidates cache at its clock.
    An optional run_id groups writes under an explicitly started pipeline run.
    Otherwise a successful new fetch gets one automatically completed run.
    """

    def __init__(self, config: DatabaseConfig, *, simulation_config: SimulationConfig = DEFAULT_CONFIG,
                 run_id: UUID | None = None):
        self.config = config
        self.simulation_config = simulation_config
        self.run_id = run_id

    def start_run(self) -> UUID:
        run_id = uuid4()
        with database_connection(self.config) as connection:
            self._insert_run(connection, run_id)
        return run_id

    def _insert_run(self, connection, run_id):
        connection.execute("INSERT INTO ops.pipeline_runs(run_id,status,config_version) VALUES (%s,'RUNNING',%s)",
                           (run_id, self.simulation_config.config_id))

    def _finish_run(self, run_id: UUID, status: str, error_code=None, error_message=None):
        with database_connection(self.config) as connection:
            row = connection.execute("SELECT status FROM ops.pipeline_runs WHERE run_id=%s FOR UPDATE", (run_id,)).fetchone()
            if row is None or row[0] != "RUNNING":
                raise ToolError("Pipeline run is missing or already finished")
            connection.execute("""UPDATE ops.pipeline_runs SET status=%s,finished_at=clock_timestamp(),
                error_code=%s,error_message=%s,
                records_received=(SELECT count(*) FROM ingest.weather_hourly h JOIN ingest.weather_fetches f USING(fetch_id) WHERE f.run_id=%s),
                records_accepted=(SELECT count(*) FROM ingest.weather_hourly h JOIN ingest.weather_fetches f USING(fetch_id) WHERE f.run_id=%s AND h.validation_status IN ('VALID','DEGRADED'))
                WHERE run_id=%s""", (status, error_code, error_message, run_id, run_id, run_id))

    def complete_run(self, run_id: UUID) -> None:
        self._finish_run(run_id, "SUCCEEDED")

    def fail_run(self, run_id: UUID, *, error_code: str, error_message: str) -> None:
        if not all(isinstance(value, str) and value.strip() and "\x00" not in value
                   for value in (error_code, error_message)):
            raise ToolError("Run failure requires a nonempty error code and safe summary")
        self._finish_run(run_id, "FAILED", error_code[:100], error_message[:1000])

    def run_counts(self, run_id: UUID) -> dict[str, int]:
        with database_connection(self.config) as connection:
            if connection.execute("SELECT 1 FROM ops.pipeline_runs WHERE run_id=%s", (run_id,)).fetchone() is None:
                raise ToolError("Pipeline run does not exist")
            fetches, rows, accepted = connection.execute("""SELECT count(DISTINCT f.fetch_id),count(h.fetch_id),
                count(h.fetch_id) FILTER (WHERE h.validation_status IN ('VALID','DEGRADED'))
                FROM ingest.weather_fetches f LEFT JOIN ingest.weather_hourly h USING(fetch_id) WHERE f.run_id=%s""", (run_id,)).fetchone()
            return {"fetches": fetches, "rows": rows, "accepted": accepted}

    def store_weather(self, request: WeatherRequest, weather: RawWeather) -> None:
        site, metadata, canonical, report, key = _prepare_weather(request, weather, self.simulation_config)
        payload = dict(weather)
        payload_hash = _json_hash(payload)
        with database_connection(self.config) as connection:
            # Serialize identical retries, including concurrent writers, before
            # creating an automatic run. Unique constraints remain authoritative.
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (int(key[:15], 16),))
            if connection.execute("SELECT 1 FROM ingest.weather_fetches WHERE idempotency_key=%s", (key,)).fetchone():
                return
            run_id = self.run_id or uuid4()
            if self.run_id is None:
                self._insert_run(connection, run_id)
            else:
                row = connection.execute("SELECT status FROM ops.pipeline_runs WHERE run_id=%s FOR UPDATE", (run_id,)).fetchone()
                if row is None or row[0] != "RUNNING":
                    raise ToolError("Weather writes require a running pipeline run")
            fetch_id = uuid4()
            connection.execute("""INSERT INTO ingest.weather_fetches
                (fetch_id,run_id,idempotency_key,site_id,latitude_deg,longitude_deg,provider,
                 request_parameters,fetched_at,forecast_issued_at,payload,payload_sha256)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (fetch_id, run_id, key, site, metadata["latitude_deg"], metadata["longitude_deg"],
                 canonical["source"], Jsonb(metadata), canonical["fetched_at"], canonical["forecast_issued_at"],
                 Jsonb(payload), payload_hash))
            # Field names are the fixed shared CurrentWeather fields, never user SQL.
            columns = ",".join(WEATHER_FIELDS)
            placeholders = ",".join(["%s"] * (len(WEATHER_FIELDS) + 5))
            connection.execute(f"""INSERT INTO ingest.weather_hourly
                (fetch_id,interval_start,prediction_horizon_minutes,{columns},validation_status,validation_issues)
                VALUES ({placeholders})""", (fetch_id, canonical["timestamp"], 60,
                    *(canonical[name] for name in WEATHER_FIELDS), report["status"], Jsonb(report["issues"])))
            if self.run_id is None:
                connection.execute("""UPDATE ops.pipeline_runs SET status='SUCCEEDED',finished_at=clock_timestamp(),
                    records_received=1,records_accepted=%s WHERE run_id=%s""",
                    (int(report["status"] in ("VALID", "DEGRADED")), run_id))

    def load_cached_weather(self, request: WeatherRequest) -> RawWeather | None:
        site, metadata = _request_metadata(request)
        with database_connection(self.config) as connection:
            row = connection.execute("""SELECT f.payload FROM ingest.weather_fetches f
                JOIN ingest.weather_hourly h USING(fetch_id)
                WHERE f.site_id=%s AND f.latitude_deg=%s AND f.longitude_deg=%s
                  AND h.interval_start=%s AND h.prediction_horizon_minutes=%s
                ORDER BY f.forecast_issued_at DESC NULLS LAST,f.fetched_at DESC,f.idempotency_key DESC LIMIT 1""",
                (site, metadata["latitude_deg"], metadata["longitude_deg"], metadata["interval_start"], 60)).fetchone()
            return row[0] if row else None

    def store_solar_position(self, request: WeatherRequest, solar: SolarPosition, *,
                             calculation_version: str = f"pvlib-{pvlib.__version__}:nrel_numpy:sea-level:midpoint:v1") -> None:
        site, metadata = _request_metadata(request)
        if not isinstance(solar, dict) or set(solar) != {"sun_elevation_deg", "sun_azimuth_deg"}:
            raise ToolError("solar: expected SolarPosition fields")
        elevation, azimuth = solar["sun_elevation_deg"], solar["sun_azimuth_deg"]
        if (not _finite_number(elevation) or not -90 <= elevation <= 90 or
                not _finite_number(azimuth) or not 0 <= azimuth < 360):
            raise ToolError("solar: invalid angles")
        if not isinstance(calculation_version, str) or not calculation_version.strip() or "\x00" in calculation_version:
            raise ToolError("calculation_version: expected nonempty string")
        start = _parse_timestamp(metadata["interval_start"], "interval_start")
        values = (site, metadata["latitude_deg"], metadata["longitude_deg"], start, 60,
                  start + timedelta(minutes=30), calculation_version, float(elevation), float(azimuth))
        with database_connection(self.config) as connection:
            connection.execute("""INSERT INTO ingest.solar_position
                (site_id,latitude_deg,longitude_deg,interval_start,prediction_horizon_minutes,
                 calculated_for,calculation_version,sun_elevation_deg,sun_azimuth_deg)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""", values)
            stored = connection.execute("""SELECT sun_elevation_deg,sun_azimuth_deg FROM ingest.solar_position
                WHERE site_id=%s AND interval_start=%s AND prediction_horizon_minutes=60 AND calculation_version=%s""",
                (site, start, calculation_version)).fetchone()
            if stored != (float(elevation), float(azimuth)):
                raise ToolError("Solar calculation differs for the same version; use a new calculation_version")
