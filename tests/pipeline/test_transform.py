"""Canonical transformation and unchanged inference boundary."""

import copy
import json
from typing import get_type_hints
import unittest

from src.common.schema import WeatherFeatures, validate_weather_row
from src.common.tool_contracts import ToolError
from src.pipeline.transform import transform_weather
from tests.pipeline.weather_fixtures import weather_fixture


SOLAR = {"sun_elevation_deg": 60.0, "sun_azimuth_deg": 168.0}


class WeatherTransformationTests(unittest.TestCase):
    def test_exact_contract_native_numbers_and_no_target(self):
        features = transform_weather(weather_fixture(), SOLAR, panel_angle_deg=35)
        self.assertEqual(set(features), set(get_type_hints(WeatherFeatures)))
        self.assertNotIn("actual_kwh", features)
        for key, value in features.items():
            if key != "timestamp":
                self.assertIs(type(value), float)
        self.assertEqual(json.loads(json.dumps(features, allow_nan=False)), features)
        # A test-only target exercises the existing shared validator.
        validate_weather_row(dict(features, actual_kwh=5.8))

    def test_utc_normalization_preserves_instant_and_interval_start(self):
        weather = dict(weather_fixture(), timestamp="2026-06-21T13:00:00-06:00")
        result = transform_weather(weather, SOLAR, panel_angle_deg=35)
        self.assertEqual(result["timestamp"], "2026-06-21T19:00:00Z")

    def test_no_mutation_or_implicit_unit_conversion(self):
        weather, solar = weather_fixture(), copy.deepcopy(SOLAR)
        before = copy.deepcopy((weather, solar))
        result = transform_weather(weather, solar, panel_angle_deg=35)
        self.assertEqual((weather, solar), before)
        for key in ("temperature_c", "wind_speed_kmh", "ghi_wm2"):
            self.assertEqual(result[key], weather[key])

    def test_missing_invalid_and_target_inputs_fail_without_imputation(self):
        for changes in ({"ghi_wm2": None}, {"wind_speed_kmh": "14"}, {"temperature_c": float("nan")}, {"actual_kwh": 5}):
            with self.subTest(changes=changes), self.assertRaises(ToolError):
                transform_weather(dict(weather_fixture(), **changes), SOLAR, panel_angle_deg=35)

    def test_invalid_solar_and_panel_angles_fail(self):
        for solar in ({}, dict(SOLAR, sun_elevation_deg=91), dict(SOLAR, sun_azimuth_deg=360), dict(SOLAR, sun_elevation_deg=True)):
            with self.assertRaises(ToolError):
                transform_weather(weather_fixture(), solar, panel_angle_deg=35)
        for angle in (-1, 91, None, True, float("inf")):
            with self.assertRaises(ToolError):
                transform_weather(weather_fixture(), SOLAR, panel_angle_deg=angle)

    def test_night_and_boundary_angles_preserved(self):
        weather = dict(weather_fixture(), ghi_wm2=0, dni_wm2=0, dhi_wm2=0)
        solar = dict(SOLAR, sun_elevation_deg=-20)
        for angle in (0, 90):
            result = transform_weather(weather, solar, panel_angle_deg=angle)
            self.assertEqual(result["ghi_wm2"], 0)
            self.assertEqual(result["sun_elevation_deg"], -20)

    def test_transformation_does_not_claim_freshness(self):
        weather = dict(weather_fixture(), forecast_issued_at=None)
        self.assertEqual(transform_weather(weather, SOLAR, panel_angle_deg=35)["temperature_c"], 22)


if __name__ == "__main__":
    unittest.main()
