"""Quality and freshness behavior, with a fixed injected clock."""

import copy
from dataclasses import replace
import unittest

from src.common.config import DEFAULT_CONFIG
from src.common.tool_contracts import ToolError
from src.pipeline.validate import validate_weather
from tests.pipeline.weather_fixtures import NOW, weather_fixture


class WeatherValidationTests(unittest.TestCase):
    def report(self, weather):
        return validate_weather(weather, now=NOW, config=DEFAULT_CONFIG)

    def test_valid_report_and_no_mutation(self):
        weather = weather_fixture()
        original = copy.deepcopy(weather)
        self.assertEqual(self.report(weather), {
            "status": "VALID", "source": "test_fixture",
            "forecast_age_minutes": 5.0, "used_cache": False, "issues": [],
        })
        self.assertEqual(weather, original)

    def test_freshness_boundary_and_old_forecast_with_recent_fetch(self):
        for issued, expected in (("18:30:00", "VALID"), ("18:29:59", "STALE")):
            weather = weather_fixture()
            weather["forecast_issued_at"] = f"2026-06-21T{issued}Z"
            with self.subTest(issued=issued):
                self.assertEqual(self.report(weather)["status"], expected)

    def test_equivalent_timezones(self):
        weather = weather_fixture()
        weather["forecast_issued_at"] = "2026-06-21T12:55:00-06:00"
        self.assertEqual(self.report(weather)["forecast_age_minutes"], 5)

    def test_unknown_and_future_issuance_are_not_fresh(self):
        for issued in (None, "2026-06-21T19:01:00Z"):
            report = self.report(dict(weather_fixture(), forecast_issued_at=issued))
            self.assertEqual(report["status"], "INVALID")
            self.assertIsNone(report["forecast_age_minutes"])
            self.assertTrue(report["issues"])

    def test_future_fetch_and_issuance_after_fetch_rejected(self):
        for fetched in ("2026-06-21T19:01:00Z", "2026-06-21T18:50:00Z"):
            self.assertEqual(self.report(dict(weather_fixture(), fetched_at=fetched))["status"], "INVALID")

    def test_future_forecast_interval_is_allowed(self):
        self.assertEqual(self.report(dict(weather_fixture(), timestamp="2026-06-22T19:00:00Z"))["status"], "VALID")

    def test_missing_and_extra_fields_rejected(self):
        for key in weather_fixture():
            weather = weather_fixture()
            del weather[key]
            with self.subTest(key=key):
                self.assertEqual(self.report(weather)["status"], "INVALID")
        self.assertEqual(self.report(dict(weather_fixture(), actual_kwh=5))["status"], "INVALID")

    def test_bad_numeric_values_rejected(self):
        for value in (None, "850", True, float("nan"), float("inf"), -1, 10**400):
            with self.subTest(value=str(value)[:30]):
                self.assertEqual(self.report(dict(weather_fixture(), ghi_wm2=value))["status"], "INVALID")

    def test_ranges_and_invalid_precedence(self):
        for field, value in (("cloud_cover_pct", 101), ("cloud_cover_pct", -1), ("wind_gust_kmh", 1), ("precipitation_mm", -1)):
            weather = dict(weather_fixture(), **{field: value})
            weather["forecast_issued_at"] = "2026-06-21T17:00:00Z"
            self.assertEqual(self.report(weather)["status"], "INVALID")

    def test_night_and_cold_weather_not_imputed(self):
        weather = dict(weather_fixture(), temperature_c=-20, ghi_wm2=0, dni_wm2=0, dhi_wm2=0)
        self.assertEqual(self.report(weather)["status"], "VALID")

    def test_malformed_timestamps_and_source_rejected(self):
        for field, value in (("timestamp", "bad"), ("timestamp", "2026-06-21T19:00:00"), ("fetched_at", None), ("source", " ")):
            self.assertEqual(self.report(dict(weather_fixture(), **{field: value}))["status"], "INVALID")

    def test_bad_caller_clock_or_config_raises_tool_error(self):
        with self.assertRaises(ToolError):
            validate_weather(weather_fixture(), now="bad", config=DEFAULT_CONFIG)
        for limit in (-1, float("nan"), True):
            with self.assertRaises(ToolError):
                validate_weather(weather_fixture(), now=NOW, config=replace(DEFAULT_CONFIG, max_forecast_age_minutes=limit))


if __name__ == "__main__":
    unittest.main()
