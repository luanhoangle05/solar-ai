"""The single weather-row loader: header, per-row contract, chronological order."""

import csv
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from src.common.schema import WEATHER_COLUMNS
from src.models.data_loader import (
    DATASET_KIND_ENV, DATASET_PATH_ENV, EXAMPLE_DATASET_PATH, EXAMPLE_DATASET_SOURCE, LABEL_SOURCE_ENV,
    PIPELINE_DATASET_PATH, PIPELINE_DATASET_SOURCE, DatasetError, DatasetSource, default_dataset_source,
    hourly_weather, load_dataset_split, load_weather_rows,
)


MOCK_CSV = Path(__file__).resolve().parents[2] / "data" / "mock" / "sample_weather.csv"
VALID_ROW = ["2026-06-21T14:00:00Z", 13, 35, 0, 10, 16, 250, 420, 115, 19, 77, 35, 1.7]
LATER_ROW = ["2026-06-21T15:00:00Z", 15, 30, 0, 11, 18, 420, 530, 132, 29, 89, 35, 2.8]


class LoadWeatherRowsTest(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "weather.csv"

    def write(self, header: list[str], rows: list[list]) -> Path:
        with self.path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        return self.path

    def test_loads_mock_csv_as_numeric_contract_rows(self) -> None:
        rows = load_weather_rows(MOCK_CSV)

        self.assertEqual(len(rows), 6)
        self.assertEqual(tuple(rows[0]), WEATHER_COLUMNS)
        self.assertEqual(rows[0]["timestamp"], "2026-06-21T14:00:00Z")
        self.assertEqual(rows[-1]["actual_kwh"], 5.8)
        self.assertIsInstance(rows[0]["ghi_wm2"], float)

    def test_rejects_header_that_differs_from_contract(self) -> None:
        header = [name for name in WEATHER_COLUMNS if name != "dhi_wm2"]
        path = self.write(header, [])

        with self.assertRaisesRegex(DatasetError, "header"):
            load_weather_rows(path)

    def test_rejects_non_numeric_value_with_line_number(self) -> None:
        broken = [*VALID_ROW[:1], "warm", *VALID_ROW[2:]]
        path = self.write(list(WEATHER_COLUMNS), [VALID_ROW, broken])

        with self.assertRaisesRegex(DatasetError, "line 3"):
            load_weather_rows(path)

    def test_rejects_row_that_fails_contract_validation(self) -> None:
        negative_energy = [*VALID_ROW[:-1], -1]
        path = self.write(list(WEATHER_COLUMNS), [negative_energy])

        with self.assertRaisesRegex(DatasetError, "line 2.*actual_kwh"):
            load_weather_rows(path)

    def test_rejects_timestamps_that_are_not_strictly_increasing(self) -> None:
        path = self.write(list(WEATHER_COLUMNS), [LATER_ROW, VALID_ROW])

        with self.assertRaisesRegex(DatasetError, "chronological"):
            load_weather_rows(path)

    def test_rejects_duplicate_timestamp(self) -> None:
        path = self.write(list(WEATHER_COLUMNS), [VALID_ROW, VALID_ROW])

        with self.assertRaisesRegex(DatasetError, "line 3.*chronological"):
            load_weather_rows(path)

    def test_rejects_wrong_number_of_values(self) -> None:
        path = self.write(list(WEATHER_COLUMNS), [VALID_ROW[:-1]])

        with self.assertRaisesRegex(DatasetError, "line 2: expected 13 values, got 12"):
            load_weather_rows(path)

    def test_skips_blank_lines_and_byte_order_mark(self) -> None:
        lines = [",".join(WEATHER_COLUMNS), ",".join(map(str, VALID_ROW)), "", ""]
        self.path.write_text(chr(10).join(lines), encoding="utf-8-sig")

        self.assertEqual(len(load_weather_rows(self.path)), 1)

    def test_accepts_several_angles_for_the_same_hour(self) -> None:
        other_angle = [*VALID_ROW[:11], 50, 1.5]
        path = self.write(list(WEATHER_COLUMNS), [VALID_ROW, other_angle, LATER_ROW])

        rows = load_weather_rows(path)

        self.assertEqual([(row["timestamp"], row["panel_angle_deg"]) for row in rows][:2], [(VALID_ROW[0], 35.0), (VALID_ROW[0], 50.0)])
        self.assertEqual([row["panel_angle_deg"] for row in hourly_weather(rows)], [35.0, 35.0])
        self.assertNotIn("actual_kwh", hourly_weather(rows)[0])

    def test_rejects_file_without_data_rows(self) -> None:
        path = self.write(list(WEATHER_COLUMNS), [])

        with self.assertRaisesRegex(DatasetError, "no data rows"):
            load_weather_rows(path)

    def test_rejects_missing_file(self) -> None:
        with self.assertRaisesRegex(DatasetError, "not found"):
            load_weather_rows(self.path)


class DefaultDatasetSourceTest(unittest.TestCase):
    def test_defaults_to_pipeline_dataset_labeled_physics_derived(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            source = default_dataset_source()

        self.assertEqual(source, PIPELINE_DATASET_SOURCE)
        self.assertEqual((source.path, source.dataset_kind, source.label_source), (PIPELINE_DATASET_PATH, "LIVE", "physics-derived"))

    def test_example_dataset_is_always_labeled_mock(self) -> None:
        with mock.patch.dict(os.environ, {DATASET_PATH_ENV: str(EXAMPLE_DATASET_PATH)}, clear=True):
            source = default_dataset_source()

        self.assertEqual(source, EXAMPLE_DATASET_SOURCE)

    def test_environment_switches_to_real_dataset_without_code_change(self) -> None:
        env = {DATASET_PATH_ENV: "data/processed/weather.csv", DATASET_KIND_ENV: "LIVE", LABEL_SOURCE_ENV: "measured"}
        with mock.patch.dict(os.environ, env, clear=True):
            source = default_dataset_source()

        self.assertEqual(source.path, Path("data/processed/weather.csv"))
        self.assertEqual((source.dataset_kind, source.label_source), ("LIVE", "measured"))

    def test_rejects_unknown_dataset_kind(self) -> None:
        with mock.patch.dict(os.environ, {DATASET_KIND_ENV: "EXAMPLE"}, clear=True):
            with self.assertRaisesRegex(DatasetError, DATASET_KIND_ENV):
                default_dataset_source()

    def test_rejects_mock_dataset_labeled_as_measured(self) -> None:
        env = {DATASET_KIND_ENV: "MOCK", LABEL_SOURCE_ENV: "measured"}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(DatasetError, "label"):
                default_dataset_source()


class LoadDatasetSplitTest(unittest.TestCase):
    def test_single_csv_is_split_chronologically(self) -> None:
        split = load_dataset_split(EXAMPLE_DATASET_SOURCE)
        rows = load_weather_rows(EXAMPLE_DATASET_PATH)

        self.assertEqual([*split.train, *split.validation, *split.test], rows)
        self.assertLess(split.train[-1]["timestamp"], split.validation[0]["timestamp"])

    def test_directory_uses_the_delivered_windows_unchanged(self) -> None:
        split = load_dataset_split(PIPELINE_DATASET_SOURCE)

        for name in ("train", "validation", "test"):
            delivered = load_weather_rows(PIPELINE_DATASET_PATH / f"{name}_sample.csv")
            self.assertEqual(list(getattr(split, name)), delivered)
        self.assertLess(split.train[-1]["timestamp"], split.validation[0]["timestamp"])
        self.assertLess(split.validation[-1]["timestamp"], split.test[0]["timestamp"])

    def test_pipeline_dataset_has_every_candidate_angle_for_every_hour(self) -> None:
        split = load_dataset_split(PIPELINE_DATASET_SOURCE)
        angles_by_hour: dict[str, set[float]] = {}
        for row in split.test:
            angles_by_hour.setdefault(row["timestamp"], set()).add(row["panel_angle_deg"])

        self.assertEqual(len(hourly_weather(split.test)), len(angles_by_hour))
        self.assertEqual({frozenset(angles) for angles in angles_by_hour.values()}, {frozenset({30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0})})

    def test_directory_missing_a_window_file_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(DatasetError, "not found"):
                load_dataset_split(DatasetSource(Path(directory), "LIVE", "physics-derived"))


if __name__ == "__main__":
    unittest.main()
