"""Offline solar reference, timezone, input and failure tests."""

from dataclasses import replace
import unittest
from unittest.mock import patch

import pandas as pd

from src.common.tool_contracts import ToolError, WeatherRequest
from src.pipeline.solar_position import calculate_solar_position
from src.pipeline.transform import transform_weather
from tests.pipeline.weather_fixtures import weather_fixture


class SolarPositionTests(unittest.TestCase):
    def setUp(self):
        # Midpoint is the NREL SPA example instant: 12:30:30 MST.
        self.request = WeatherRequest(39.742476, -105.1786, "2003-10-17T12:00:30-07:00", 60)

    def test_published_spa_reference(self):
        # NREL example, also recorded in pvlib v0.13.1 tests:
        # https://github.com/pvlib/pvlib-python/blob/v0.13.1/tests/test_solarposition.py
        # Geometric elevation/azimuth; tolerance accommodates this adapter's
        # sea-level altitude and automatic delta-T vs the reference settings.
        result = calculate_solar_position(self.request)
        self.assertAlmostEqual(result["sun_elevation_deg"], 39.872046, delta=0.02)
        self.assertAlmostEqual(result["sun_azimuth_deg"], 194.340241, delta=0.02)
        self.assertEqual(set(result), {"sun_elevation_deg", "sun_azimuth_deg"})

    def test_equivalent_timezone_inputs_match(self):
        utc = replace(self.request, interval_start="2003-10-17T19:00:30Z")
        self.assertEqual(calculate_solar_position(self.request), calculate_solar_position(utc))

    def test_midpoint_passed_to_pvlib_and_geometric_field_selected(self):
        result_frame = pd.DataFrame({"elevation": [10.0], "apparent_elevation": [11.0], "azimuth": [360.0]})
        with patch("src.pipeline.solar_position.solarposition.get_solarposition", return_value=result_frame) as call:
            result = calculate_solar_position(self.request)
        self.assertEqual(call.call_args.args[0][0], pd.Timestamp("2003-10-17T19:30:30Z"))
        self.assertEqual(result, {"sun_elevation_deg": 10.0, "sun_azimuth_deg": 0.0})

    def test_night_preserves_negative_elevation(self):
        result = calculate_solar_position(replace(self.request, interval_start="2003-10-17T00:00:00-07:00"))
        self.assertLess(result["sun_elevation_deg"], 0)
        self.assertTrue(0 <= result["sun_azimuth_deg"] < 360)

    def test_invalid_coordinates_and_horizons_fail(self):
        for changes in ({"latitude_deg": 91}, {"longitude_deg": -181}, {"latitude_deg": True}, {"longitude_deg": float("nan")}, {"prediction_horizon_minutes": 0}, {"prediction_horizon_minutes": 60.0}, {"prediction_horizon_minutes": 120}):
            with self.subTest(changes=changes), self.assertRaises(ToolError):
                calculate_solar_position(replace(self.request, **changes))

    def test_invalid_and_naive_times_fail(self):
        for timestamp in ("bad", "2026-06-21T12:00:00", None):
            with self.assertRaises(ToolError):
                calculate_solar_position(replace(self.request, interval_start=timestamp))

    def test_backend_errors_and_nonfinite_output_fail(self):
        with patch("src.pipeline.solar_position.solarposition.get_solarposition", side_effect=ValueError("bad calculation")):
            with self.assertRaises(ToolError):
                calculate_solar_position(self.request)
        for field in ("elevation", "azimuth"):
            frame = pd.DataFrame({"elevation": [20.0], "azimuth": [100.0]})
            frame[field] = float("nan")
            with patch("src.pipeline.solar_position.solarposition.get_solarposition", return_value=frame):
                with self.assertRaises(ToolError):
                    calculate_solar_position(self.request)

    def test_offline_enrichment_composes_with_transformation(self):
        weather = weather_fixture()
        request = replace(self.request, interval_start=weather["timestamp"])
        solar = calculate_solar_position(request)
        features = transform_weather(weather, solar, panel_angle_deg=35)
        self.assertEqual(features["sun_elevation_deg"], solar["sun_elevation_deg"])
        self.assertNotIn("actual_kwh", features)


if __name__ == "__main__":
    unittest.main()
