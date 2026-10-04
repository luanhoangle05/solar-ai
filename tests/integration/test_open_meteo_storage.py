"""Mock provider HTTP plus real PostgreSQL; no internet in automated tests."""

from dataclasses import replace
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from src.common.config import DEFAULT_CONFIG, load_database_config
from src.pipeline.client import OpenMeteoClient
from src.pipeline.storage import PostgresWeatherStorage, database_connection
from src.pipeline.validate import validate_weather
from tests.pipeline.test_open_meteo import REQUEST, response_fixture


@unittest.skipUnless(os.environ.get("RUN_POSTGRES_TESTS") == "1", "Opt-in PostgreSQL integration")
class OpenMeteoStorageTests(unittest.TestCase):
    def test_mapped_provider_roundtrip_without_contract_extensions(self):
        config = load_database_config()
        storage = PostgresWeatherStorage(config)
        run_id = storage.start_run()
        storage.run_id = run_id
        request = replace(REQUEST, latitude_deg=50 + (uuid4().int % 10**12) / 10**12)
        try:
            with patch("src.pipeline.client.requests.get", return_value=response_fixture()) as get:
                weather = OpenMeteoClient().fetch_weather(request)
            get.assert_called_once()
            report = validate_weather(weather, now=weather["fetched_at"], config=DEFAULT_CONFIG)
            self.assertEqual(report["status"], "INVALID")
            storage.store_weather(request, weather)
            self.assertEqual(storage.load_cached_weather(request), weather)
            with database_connection(config) as connection:
                row = connection.execute("""SELECT f.provider,f.forecast_issued_at,h.validation_status,h.validation_issues
                    FROM ingest.weather_fetches f JOIN ingest.weather_hourly h USING(fetch_id) WHERE f.run_id=%s""", (run_id,)).fetchone()
            self.assertEqual(row, ("open-meteo", None, "INVALID", report["issues"]))
        finally:
            with database_connection(config) as connection:
                connection.execute("DELETE FROM ingest.weather_hourly WHERE fetch_id IN (SELECT fetch_id FROM ingest.weather_fetches WHERE run_id=%s)", (run_id,))
                connection.execute("DELETE FROM ingest.weather_fetches WHERE run_id=%s", (run_id,))
                connection.execute("DELETE FROM ops.pipeline_runs WHERE run_id=%s", (run_id,))
