"""Explicit manual smoke check; one HTTP attempt, never run by test discovery."""

import argparse
from datetime import datetime, timedelta, timezone
import json

from scripts.database import smoke_check
from src.common.config import DEFAULT_CONFIG, DEMO_LATITUDE_DEG, DEMO_LONGITUDE_DEG, load_database_config
from src.common.tool_contracts import ToolError, WeatherRequest
from src.pipeline.client import OpenMeteoClient
from src.pipeline.storage import PostgresWeatherStorage, database_connection
from src.pipeline.validate import _inspect_weather, validate_weather


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latitude", type=float, default=DEMO_LATITUDE_DEG)
    parser.add_argument("--longitude", type=float, default=DEMO_LONGITUDE_DEG)
    parser.add_argument("--interval-start", help="Aware UTC-hour-aligned ISO timestamp; default next UTC hour")
    parser.add_argument("--postgres-roundtrip", action="store_true")
    args = parser.parse_args()
    db_config = load_database_config() if args.postgres_roundtrip else None
    if db_config:
        smoke_check(db_config)  # fail before using a provider request if DB is down
    start = args.interval_start or (datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
                                   + timedelta(hours=1)).isoformat()
    request = WeatherRequest(args.latitude, args.longitude, start, 60)
    client = OpenMeteoClient()
    weather = client.fetch_weather(request)
    issues, _ = _inspect_weather(weather)
    if issues:
        raise ToolError("Provider smoke data failed quality checks: " + "; ".join(issues))
    report = validate_weather(weather, now=datetime.now(timezone.utc).isoformat(), config=DEFAULT_CONFIG)
    print(json.dumps({"weather": weather, "validation": report,
                      "request_parameters": client.last_provenance["request_parameters"],
                      "returned_coordinates": client.last_provenance["returned_coordinates"],
                      "response_sha256": client.last_provenance["response_sha256"]}, indent=2))
    if db_config:
        storage = PostgresWeatherStorage(db_config)
        run_id = storage.start_run()
        storage.run_id = run_id
        try:
            storage.store_weather(request, weather)
            cached = storage.load_cached_weather(request)
            if cached != weather:
                raise ToolError("Cache differs from retrieved payload (including possible pre-existing revision); inspect before retrying")
            storage.complete_run(run_id)
            print("PostgreSQL round-trip passed: values, source, fetched_at and unknown issue time preserved.")
        finally:
            # Delete only this smoke run's records, never another run's revisions.
            with database_connection(db_config) as connection:
                connection.execute("DELETE FROM ingest.weather_hourly WHERE fetch_id IN (SELECT fetch_id FROM ingest.weather_fetches WHERE run_id=%s)", (run_id,))
                connection.execute("DELETE FROM ingest.weather_fetches WHERE run_id=%s", (run_id,))
                connection.execute("DELETE FROM ops.pipeline_runs WHERE run_id=%s", (run_id,))


if __name__ == "__main__":
    try:
        main()
    except (ToolError, ValueError) as exc:
        raise SystemExit(str(exc))
