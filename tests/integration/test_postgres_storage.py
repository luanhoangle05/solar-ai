"""Real storage behavior. Isolated run IDs and coordinates; no shared fixtures edited."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from uuid import uuid4

from src.common.config import load_database_config
from src.common.tool_contracts import ToolError
from src.pipeline.solar_position import calculate_solar_position
from src.pipeline.storage import PostgresWeatherStorage, _request_metadata, database_connection
from src.pipeline.validate import _parse_timestamp
from tests.pipeline.test_storage import request_fixture
from tests.pipeline.weather_fixtures import weather_fixture


@unittest.skipUnless(os.environ.get("RUN_POSTGRES_TESTS") == "1", "Opt-in PostgreSQL integration")
class PostgresStorageTests(unittest.TestCase):
    def setUp(self):
        self.config = load_database_config()
        self.storage = PostgresWeatherStorage(self.config)
        self.run_id = self.storage.start_run()
        self.storage.run_id = self.run_id
        self.request = replace(request_fixture(), latitude_deg=30 + (uuid4().int % 10**12) / 10**12)
        self.weather = weather_fixture()
        self.site = _request_metadata(self.request)[0]
        self.addCleanup(self.cleanup)

    def cleanup(self):
        with database_connection(self.config) as connection:
            connection.execute("DELETE FROM ingest.solar_position WHERE site_id=%s", (self.site,))
            connection.execute("DELETE FROM ingest.weather_hourly WHERE fetch_id IN (SELECT fetch_id FROM ingest.weather_fetches WHERE site_id=%s)", (self.site,))
            # Includes auto-created runs, if a test uses unbound storage.
            ids = [row[0] for row in connection.execute("SELECT run_id FROM ingest.weather_fetches WHERE site_id=%s", (self.site,))]
            connection.execute("DELETE FROM ingest.weather_fetches WHERE site_id=%s", (self.site,))
            for run_id in set(ids + [self.run_id]):
                connection.execute("DELETE FROM ops.pipeline_runs WHERE run_id=%s", (run_id,))

    def test_store_fetch_hourly_provenance_and_cache(self):
        self.assertIsNone(self.storage.store_weather(self.request, self.weather))
        self.assertEqual(self.storage.load_cached_weather(self.request), self.weather)
        with database_connection(self.config) as connection:
            row = connection.execute("""SELECT f.provider,f.latitude_deg,f.request_parameters,f.payload_sha256,
                h.ghi_wm2,h.validation_status,h.validation_issues,f.forecast_issued_at,f.fetched_at
                FROM ingest.weather_fetches f JOIN ingest.weather_hourly h USING(fetch_id) WHERE f.run_id=%s""", (self.run_id,)).fetchone()
        self.assertEqual(row[0], self.weather["source"])
        self.assertEqual(row[1], self.request.latitude_deg)
        self.assertEqual(row[2]["prediction_horizon_minutes"], 60)
        self.assertEqual(len(row[3]), 64)
        self.assertEqual(row[4:7], (850, "VALID", []))
        self.assertEqual(row[7], _parse_timestamp(self.weather["forecast_issued_at"], "issue"))
        self.assertEqual(row[8], _parse_timestamp(self.weather["fetched_at"], "fetch"))

    def test_wrong_site_interval_and_horizon(self):
        self.storage.store_weather(self.request, self.weather)
        self.assertIsNone(self.storage.load_cached_weather(replace(self.request, longitude_deg=-104)))
        self.assertIsNone(self.storage.load_cached_weather(replace(self.request, interval_start="2026-06-21T20:00:00Z")))
        with self.assertRaises(ToolError):
            self.storage.load_cached_weather(replace(self.request, prediction_horizon_minutes=30))

    def test_duplicate_retry_keeps_original_fetch_time(self):
        self.storage.store_weather(self.request, self.weather)
        self.storage.store_weather(self.request, dict(self.weather, fetched_at="2026-06-22T00:00:00Z"))
        self.assertEqual(self.storage.run_counts(self.run_id), {"fetches": 1, "rows": 1, "accepted": 1})
        self.assertEqual(self.storage.load_cached_weather(self.request), self.weather)

    def test_concurrent_duplicate_is_idempotent(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(lambda _: self.storage.store_weather(self.request, self.weather), range(4)))
        self.assertEqual(self.storage.run_counts(self.run_id)["fetches"], 1)

    def test_revisions_preserved_and_issue_time_wins_over_fetch_time(self):
        newest = dict(self.weather, forecast_issued_at="2026-06-21T18:58:00Z", ghi_wm2=900)
        older_downloaded_later = dict(self.weather, fetched_at="2026-06-21T20:00:00Z")
        self.storage.store_weather(self.request, newest)
        self.storage.store_weather(self.request, older_downloaded_later)
        self.assertEqual(self.storage.load_cached_weather(self.request), newest)
        self.assertEqual(self.storage.run_counts(self.run_id)["rows"], 2)

    def test_fetch_time_breaks_equal_issue_ties(self):
        newer = dict(self.weather, fetched_at="2026-06-21T19:05:00Z", ghi_wm2=901)
        self.storage.store_weather(self.request, newer)
        self.storage.store_weather(self.request, self.weather)
        self.assertEqual(self.storage.load_cached_weather(self.request), newer)

    def test_exact_time_tie_has_stable_hash_order(self):
        self.storage.store_weather(self.request, self.weather)
        self.storage.store_weather(self.request, dict(self.weather, ghi_wm2=901))
        with database_connection(self.config) as connection:
            expected = connection.execute("SELECT payload FROM ingest.weather_fetches WHERE run_id=%s ORDER BY idempotency_key DESC LIMIT 1", (self.run_id,)).fetchone()[0]
        self.assertEqual(self.storage.load_cached_weather(self.request), expected)
        self.assertEqual(self.storage.load_cached_weather(self.request), expected)

    def test_unknown_issue_is_preserved_and_ranks_after_known(self):
        unknown = dict(self.weather, forecast_issued_at=None, fetched_at="2026-06-21T22:00:00Z")
        self.storage.store_weather(self.request, unknown)
        self.assertEqual(self.storage.load_cached_weather(self.request), unknown)
        self.storage.store_weather(self.request, self.weather)
        self.assertEqual(self.storage.load_cached_weather(self.request), self.weather)

    def test_invalid_status_preserved_without_filter_or_imputation(self):
        invalid = dict(self.weather, ghi_wm2=None)
        self.storage.store_weather(self.request, invalid)
        self.assertEqual(self.storage.load_cached_weather(self.request), invalid)
        with database_connection(self.config) as connection:
            status, issues = connection.execute("SELECT validation_status,validation_issues FROM ingest.weather_hourly h JOIN ingest.weather_fetches f USING(fetch_id) WHERE f.run_id=%s", (self.run_id,)).fetchone()
        self.assertEqual(status, "INVALID")
        self.assertTrue(issues)
        self.assertEqual(self.storage.run_counts(self.run_id)["accepted"], 0)

    def test_stale_status_and_equivalent_timezone_lookup(self):
        stale = dict(self.weather, forecast_issued_at="2026-06-21T17:00:00Z")
        self.storage.store_weather(self.request, stale)
        equivalent = replace(self.request, interval_start="2026-06-21T13:00:00-06:00")
        self.assertEqual(self.storage.load_cached_weather(equivalent), stale)
        with database_connection(self.config) as connection:
            status = connection.execute("SELECT validation_status FROM ingest.weather_hourly h JOIN ingest.weather_fetches f USING(fetch_id) WHERE f.run_id=%s", (self.run_id,)).fetchone()[0]
        self.assertEqual(status, "STALE")

    def test_unknown_issue_revisions_use_fetch_time(self):
        first = dict(self.weather, forecast_issued_at=None)
        second = dict(first, fetched_at="2026-06-21T19:05:00Z", ghi_wm2=901)
        self.storage.store_weather(self.request, second)
        self.storage.store_weather(self.request, first)
        self.assertEqual(self.storage.load_cached_weather(self.request), second)

    def test_partial_fetch_rolls_back_on_hourly_failure(self):
        # Force a real CHECK violation after the fetch INSERT, inside its transaction.
        with patch("src.pipeline.storage.validate_weather", return_value={"status": "BROKEN", "issues": []}):
            with self.assertRaisesRegex(ToolError, "PostgreSQL operation failed"):
                self.storage.store_weather(self.request, self.weather)
        self.assertEqual(self.storage.run_counts(self.run_id), {"fetches": 0, "rows": 0, "accepted": 0})
        self.assertIsNone(self.storage.load_cached_weather(self.request))
        self.storage.store_weather(self.request, self.weather)
        self.assertEqual(self.storage.run_counts(self.run_id)["rows"], 1)

    def test_solar_repeatability_midpoint_and_version_conflict(self):
        solar = calculate_solar_position(self.request)
        self.storage.store_solar_position(self.request, solar)
        self.storage.store_solar_position(self.request, solar)
        with database_connection(self.config) as connection:
            rows = connection.execute("SELECT calculated_for,sun_elevation_deg,sun_azimuth_deg FROM ingest.solar_position WHERE site_id=%s", (self.site,)).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], _parse_timestamp(self.request.interval_start, "start") + timedelta(minutes=30))
        self.assertEqual(rows[0][1:], (solar["sun_elevation_deg"], solar["sun_azimuth_deg"]))
        with self.assertRaises(ToolError):
            self.storage.store_solar_position(self.request, dict(solar, sun_elevation_deg=0))
        self.storage.store_solar_position(self.request, solar, calculation_version="new-version")

    def test_run_complete_and_reject_later_write(self):
        self.storage.store_weather(self.request, self.weather)
        self.storage.complete_run(self.run_id)
        with database_connection(self.config) as connection:
            row = connection.execute("SELECT status,records_received,records_accepted,finished_at FROM ops.pipeline_runs WHERE run_id=%s", (self.run_id,)).fetchone()
        self.assertEqual(row[:3], ("SUCCEEDED", 1, 1))
        self.assertIsNotNone(row[3])
        with self.assertRaises(ToolError):
            self.storage.store_weather(self.request, dict(self.weather, ghi_wm2=901))

    def test_run_failure_summary(self):
        self.storage.fail_run(self.run_id, error_code="STORAGE", error_message="Safe test summary")
        with database_connection(self.config) as connection:
            row = connection.execute("SELECT status,error_code,error_message FROM ops.pipeline_runs WHERE run_id=%s", (self.run_id,)).fetchone()
        self.assertEqual(row, ("FAILED", "STORAGE", "Safe test summary"))

    def test_unbound_store_creates_completed_run_once(self):
        storage = PostgresWeatherStorage(self.config)
        storage.store_weather(self.request, self.weather)
        storage.store_weather(self.request, self.weather)
        with database_connection(self.config) as connection:
            rows = connection.execute("SELECT r.status,r.records_received FROM ops.pipeline_runs r JOIN ingest.weather_fetches f USING(run_id) WHERE f.site_id=%s", (self.site,)).fetchall()
        self.assertEqual(rows, [("SUCCEEDED", 1)])

    def test_reconnect_preserves_payload(self):
        self.storage.store_weather(self.request, self.weather)
        self.assertEqual(PostgresWeatherStorage(self.config).load_cached_weather(self.request), self.weather)

    @unittest.skipUnless(os.environ.get("RUN_POSTGRES_RESTART_TEST") == "1", "Opt-in container restart")
    def test_weather_survives_container_restart(self):
        self.storage.store_weather(self.request, self.weather)
        root = Path(__file__).resolve().parents[2]
        subprocess.run(["docker", "compose", "restart", "postgres"], cwd=root, check=True, timeout=60)
        subprocess.run(["docker", "compose", "up", "-d", "--wait", "--wait-timeout", "60", "postgres"], cwd=root, check=True, timeout=90)
        self.assertEqual(PostgresWeatherStorage(self.config).load_cached_weather(self.request), self.weather)
