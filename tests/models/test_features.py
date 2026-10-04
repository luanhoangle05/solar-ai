"""Model feature layout: contract columns plus geometry terms; never the label."""

import math
import unittest

import numpy as np

from src.common.schema import FEATURE_COLUMNS
from src.common.tool_contracts import ToolError
from src.models.advanced.features import (
    GEOMETRY_FEATURES, MODEL_FEATURE_NAMES, at_candidate_angles, feature_matrix, feature_names,
)


def weather(**overrides: float) -> dict:
    base = {
        "timestamp": "2026-06-21T19:00:00Z", "temperature_c": 22.0, "cloud_cover_pct": 15.0, "precipitation_mm": 0.0,
        "wind_speed_kmh": 14.0, "wind_gust_kmh": 24.0, "ghi_wm2": 850.0, "dni_wm2": 750.0, "dhi_wm2": 200.0,
        "sun_elevation_deg": 60.0, "sun_azimuth_deg": 168.0, "panel_angle_deg": 35.0,
    }
    return {**base, **overrides}


def geometry(row: dict) -> dict[str, float]:
    values = feature_matrix([row])[0]
    return dict(zip(GEOMETRY_FEATURES, values[len(FEATURE_COLUMNS):]))


class FeatureMatrixTest(unittest.TestCase):
    def test_layout_is_contract_columns_then_geometry_features(self) -> None:
        matrix = feature_matrix([weather(), weather(panel_angle_deg=50.0)])

        self.assertEqual(MODEL_FEATURE_NAMES, (*FEATURE_COLUMNS, *GEOMETRY_FEATURES))
        self.assertEqual(matrix.shape, (2, len(MODEL_FEATURE_NAMES)))
        self.assertEqual(matrix[0, :len(FEATURE_COLUMNS)].tolist(), [weather()[name] for name in FEATURE_COLUMNS])

    def test_geometry_can_be_left_out_per_model(self) -> None:
        raw_only = feature_matrix([weather()], geometry=False)

        self.assertEqual(feature_names(geometry=False), FEATURE_COLUMNS)
        self.assertEqual(feature_names(geometry=True), MODEL_FEATURE_NAMES)
        np.testing.assert_array_equal(raw_only, feature_matrix([weather()])[:, :len(FEATURE_COLUMNS)])

    def test_label_never_enters_the_matrix(self) -> None:
        self.assertNotIn("actual_kwh", MODEL_FEATURE_NAMES)
        np.testing.assert_array_equal(feature_matrix([weather()]), feature_matrix([{**weather(), "actual_kwh": 999.0}]))

    def test_geometry_terms_match_hand_calculation(self) -> None:
        terms = geometry(weather())
        elevation, azimuth, tilt = math.radians(60.0), math.radians(168.0), math.radians(35.0)

        self.assertAlmostEqual(terms["beam_horizontal_wm2"], 750.0 * math.sin(elevation) * math.cos(tilt))
        self.assertAlmostEqual(terms["beam_north_south_wm2"], 750.0 * math.cos(elevation) * math.sin(tilt) * math.cos(azimuth))
        self.assertAlmostEqual(terms["beam_east_west_wm2"], 750.0 * math.cos(elevation) * math.sin(tilt) * math.sin(azimuth))
        self.assertAlmostEqual(terms["sky_diffuse_tilted_wm2"], 200.0 * (1 + math.cos(tilt)) / 2)
        self.assertAlmostEqual(terms["ground_view_ghi_wm2"], 850.0 * (1 - math.cos(tilt)) / 2)

    def test_beam_terms_reconstruct_irradiance_for_any_panel_facing(self) -> None:
        row = weather()
        terms = geometry(row)
        elevation, tilt = math.radians(60.0), math.radians(35.0)

        for panel_azimuth_deg in (90.0, 180.0, 250.0):
            facing = math.radians(panel_azimuth_deg)
            from_terms = terms["beam_horizontal_wm2"] + terms["beam_north_south_wm2"] * math.cos(facing) + terms["beam_east_west_wm2"] * math.sin(facing)
            direct = 750.0 * (math.sin(elevation) * math.cos(tilt) + math.cos(elevation) * math.sin(tilt) * math.cos(math.radians(168.0) - facing))
            self.assertAlmostEqual(from_terms, direct)

    def test_flat_panel_sees_the_whole_sky_and_no_ground(self) -> None:
        terms = geometry(weather(panel_angle_deg=0.0))

        self.assertAlmostEqual(terms["sky_diffuse_tilted_wm2"], 200.0)
        self.assertAlmostEqual(terms["ground_view_ghi_wm2"], 0.0)
        self.assertAlmostEqual(terms["beam_north_south_wm2"], 0.0)
        self.assertAlmostEqual(terms["beam_east_west_wm2"], 0.0)

    def test_sun_below_horizon_gives_no_beam_even_with_a_stray_dni_reading(self) -> None:
        terms = geometry(weather(sun_elevation_deg=-10.0, dni_wm2=50.0, ghi_wm2=0.0, dhi_wm2=0.0))

        self.assertEqual((terms["beam_horizontal_wm2"], terms["beam_north_south_wm2"], terms["beam_east_west_wm2"]), (0.0, 0.0, 0.0))

    def test_only_tilt_dependent_terms_change_across_candidate_angles(self) -> None:
        matrix = feature_matrix(at_candidate_angles(weather(), (30.0, 60.0)))
        changed = {name for name, low, high in zip(MODEL_FEATURE_NAMES, matrix[0], matrix[1]) if low != high}

        self.assertEqual(changed, {"panel_angle_deg", *GEOMETRY_FEATURES})

    def test_empty_input_keeps_the_feature_width(self) -> None:
        self.assertEqual(feature_matrix([]).shape, (0, len(MODEL_FEATURE_NAMES)))

    def test_missing_or_non_finite_feature_raises_tool_error(self) -> None:
        incomplete = {name: value for name, value in weather().items() if name != "dni_wm2"}

        with self.assertRaises(ToolError):
            feature_matrix([incomplete])
        with self.assertRaises(ToolError):
            feature_matrix([weather(ghi_wm2=float("nan"))])


if __name__ == "__main__":
    unittest.main()
