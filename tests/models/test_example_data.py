"""Synthetic example dataset: contract-valid, reproducible, physically plausible."""

import dataclasses
from datetime import datetime, timezone
import unittest

from scripts.generate_example_data import (
    DEFAULT_EXAMPLE_CONFIG, expected_row_kwh, generate_rows, plane_of_array_wm2,
)
from src.common.schema import WEATHER_COLUMNS, validate_weather_row
from src.models.data_loader import EXAMPLE_DATASET_PATH, load_weather_rows


SHORT_CONFIG = dataclasses.replace(
    DEFAULT_EXAMPLE_CONFIG,
    start=datetime(2026, 6, 1, tzinfo=timezone.utc),
    end=datetime(2026, 6, 15, tzinfo=timezone.utc),
)


class ExampleDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = generate_rows(SHORT_CONFIG)

    def test_rows_are_hourly_and_match_weather_contract(self) -> None:
        self.assertEqual(len(self.rows), 14 * 24)
        self.assertEqual(self.rows[0]["timestamp"], "2026-06-01T00:00:00Z")
        self.assertEqual(self.rows[1]["timestamp"], "2026-06-01T01:00:00Z")
        for row in self.rows:
            self.assertEqual(tuple(row), WEATHER_COLUMNS)
            validate_weather_row(row)

    def test_same_seed_reproduces_identical_rows(self) -> None:
        self.assertEqual(generate_rows(SHORT_CONFIG), self.rows)

    def test_different_seed_changes_rows(self) -> None:
        other = generate_rows(dataclasses.replace(SHORT_CONFIG, seed=SHORT_CONFIG.seed + 1))

        self.assertNotEqual(other, self.rows)

    def test_panel_angle_varies_across_rows(self) -> None:
        angles = {row["panel_angle_deg"] for row in self.rows}

        self.assertGreaterEqual(len(angles), 10)

    def test_night_rows_have_zero_irradiance_and_energy(self) -> None:
        night = [row for row in self.rows if row["sun_elevation_deg"] <= 0]

        self.assertTrue(night)
        for row in night:
            self.assertEqual((row["ghi_wm2"], row["dni_wm2"], row["dhi_wm2"], row["actual_kwh"]), (0.0, 0.0, 0.0, 0.0))

    def test_daytime_rows_produce_energy(self) -> None:
        high_sun = [row for row in self.rows if row["sun_elevation_deg"] > 30]

        self.assertTrue(high_sun)
        self.assertTrue(all(row["actual_kwh"] > 0 for row in high_sun))

    def test_label_stays_close_to_documented_formula(self) -> None:
        tolerance = 5 * SHORT_CONFIG.noise_fraction
        for row in self.rows:
            expected = expected_row_kwh(row, SHORT_CONFIG)
            self.assertLessEqual(abs(row["actual_kwh"] - expected), tolerance * expected + 1e-3)

    def test_energy_rises_with_irradiance_on_the_tilted_panel(self) -> None:
        day = [row for row in self.rows if row["sun_elevation_deg"] > 0]
        irradiance = [plane_of_array_wm2(row, SHORT_CONFIG) for row in day]
        energy = [row["actual_kwh"] for row in day]

        self.assertGreater(pearson(irradiance, energy), 0.95)

    def test_energy_falls_with_cloud_cover(self) -> None:
        full_season = generate_rows(DEFAULT_EXAMPLE_CONFIG)
        midday = [row for row in full_season if row["sun_elevation_deg"] > 40]
        clear = [row["actual_kwh"] for row in midday if row["cloud_cover_pct"] < 30]
        overcast = [row["actual_kwh"] for row in midday if row["cloud_cover_pct"] > 80]

        self.assertTrue(clear and overcast)
        self.assertGreater(sum(clear) / len(clear), sum(overcast) / len(overcast))

    def test_hotter_panel_loses_energy_at_equal_irradiance(self) -> None:
        noon = max(self.rows, key=lambda row: row["sun_elevation_deg"])

        cool = expected_row_kwh({**noon, "temperature_c": 5.0}, SHORT_CONFIG)
        hot = expected_row_kwh({**noon, "temperature_c": 35.0}, SHORT_CONFIG)

        self.assertGreater(cool, hot)

    def test_panel_angle_changes_expected_energy(self) -> None:
        noon = max(self.rows, key=lambda row: row["sun_elevation_deg"])
        clear_noon = {**noon, "ghi_wm2": 900.0, "dni_wm2": 900.0, "dhi_wm2": 110.0}

        by_angle = {angle: expected_row_kwh({**clear_noon, "panel_angle_deg": angle}, SHORT_CONFIG) for angle in (0.0, 30.0, 90.0)}

        self.assertGreater(by_angle[30.0], by_angle[0.0])
        self.assertGreater(by_angle[30.0], by_angle[90.0])


class CommittedExampleDatasetTest(unittest.TestCase):
    def test_committed_csv_is_the_reproducible_default_output(self) -> None:
        self.assertEqual(load_weather_rows(EXAMPLE_DATASET_PATH), generate_rows(DEFAULT_EXAMPLE_CONFIG))


def pearson(xs: list[float], ys: list[float]) -> float:
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    spread_x = sum((x - mean_x) ** 2 for x in xs) ** 0.5
    spread_y = sum((y - mean_y) ** 2 for y in ys) ** 0.5
    return covariance / (spread_x * spread_y)


if __name__ == "__main__":
    unittest.main()
