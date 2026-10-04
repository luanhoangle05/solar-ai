"""Offline input/identity tests; no PostgreSQL required."""

from dataclasses import replace
import unittest
from unittest.mock import patch

from src.common.config import DatabaseConfig, DEFAULT_CONFIG
from src.common.tool_contracts import ToolError, WeatherRequest
from src.pipeline.storage import PostgresWeatherStorage, _prepare_weather, _request_metadata
from tests.pipeline.weather_fixtures import weather_fixture


def request_fixture():
    return WeatherRequest(40, -105, "2026-06-21T19:00:00Z", 60)


class StorageInputTests(unittest.TestCase):
    def test_retry_identity_ignores_download_time_and_timezone_spelling(self):
        request = request_fixture()
        original = weather_fixture()
        retry = dict(original, fetched_at="2026-06-21T19:01:00Z",
                     timestamp="2026-06-21T13:00:00-06:00")
        first = _prepare_weather(request, original, DEFAULT_CONFIG)
        second = _prepare_weather(replace(request, interval_start=retry["timestamp"]), retry, DEFAULT_CONFIG)
        self.assertEqual(first[-1], second[-1])
        self.assertEqual(original, weather_fixture())

    def test_revision_values_issue_source_and_site_change_identity(self):
        request, original = request_fixture(), weather_fixture()
        key = _prepare_weather(request, original, DEFAULT_CONFIG)[-1]
        for change in ({"ghi_wm2": 851}, {"source": "other"},
                       {"forecast_issued_at": "2026-06-21T18:56:00Z"}):
            self.assertNotEqual(key, _prepare_weather(request, dict(original, **change), DEFAULT_CONFIG)[-1])
        self.assertNotEqual(key, _prepare_weather(replace(request, latitude_deg=41), original, DEFAULT_CONFIG)[-1])

    def test_bad_request_rejected(self):
        for change in ({"latitude_deg": True}, {"longitude_deg": float("nan")},
                       {"latitude_deg": 91}, {"prediction_horizon_minutes": 30},
                       {"prediction_horizon_minutes": True}, {"interval_start": "2026-06-21T19:00:00"}):
            with self.subTest(change=change), self.assertRaises(ToolError):
                _request_metadata(replace(request_fixture(), **change))

    def test_bad_weather_rejected_before_connection(self):
        storage = PostgresWeatherStorage(DatabaseConfig("test", "test", "unused"))
        for change in ({"timestamp": "2026-06-21T20:00:00Z"}, {"ghi_wm2": float("nan")},
                       {"source": ""}, {"temperature_c": True}, {"ghi_wm2": "850"},
                       {"forecast_issued_at": "2026-06-21T20:00:00Z"}, {"extra": 1}):
            with self.subTest(change=change), patch("src.pipeline.storage.database_connection") as connect:
                with self.assertRaises(ToolError):
                    storage.store_weather(request_fixture(), dict(weather_fixture(), **change))
                connect.assert_not_called()

    def test_missing_measurements_are_retained_as_invalid(self):
        prepared = _prepare_weather(request_fixture(), dict(weather_fixture(), ghi_wm2=None), DEFAULT_CONFIG)
        self.assertIsNone(prepared[2]["ghi_wm2"])
        self.assertEqual(prepared[3]["status"], "INVALID")

    def test_unknown_issuance_is_not_invented(self):
        prepared = _prepare_weather(request_fixture(), dict(weather_fixture(), forecast_issued_at=None), DEFAULT_CONFIG)
        self.assertIsNone(prepared[2]["forecast_issued_at"])
        self.assertEqual(prepared[3]["status"], "INVALID")

    def test_invalid_solar_does_not_connect(self):
        storage = PostgresWeatherStorage(DatabaseConfig("test", "test", "unused"))
        for solar in ({"sun_elevation_deg": 91, "sun_azimuth_deg": 0},
                      {"sun_elevation_deg": 0, "sun_azimuth_deg": 360}, {}):
            with patch("src.pipeline.storage.database_connection") as connect:
                with self.assertRaises(ToolError):
                    storage.store_solar_position(request_fixture(), solar)
                connect.assert_not_called()
