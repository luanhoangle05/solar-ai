"""The single weather-row loader: header, per-row contract, chronological order."""

import csv
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from src.common.schema import WEATHER_COLUMNS
from src.models.data_loader import (
    DATASET_KIND_ENV, DATASET_PATH_ENV, EXAMPLE_DATASET_PATH, LABEL_SOURCE_ENV,
    DatasetError, default_dataset_source, load_weather_rows,
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

    def test_rejects_file_without_data_rows(self) -> None:
        path = self.write(list(WEATHER_COLUMNS), [])

        with self.assertRaisesRegex(DatasetError, "no data rows"):
            load_weather_rows(path)

    def test_rejects_missing_file(self) -> None:
        with self.assertRaisesRegex(DatasetError, "not found"):
            load_weather_rows(self.path)


class DefaultDatasetSourceTest(unittest.TestCase):
    def test_defaults_to_example_dataset_labeled_mock(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            source = default_dataset_source()

        self.assertEqual(source.path, EXAMPLE_DATASET_PATH)
        self.assertEqual((source.dataset_kind, source.label_source), ("MOCK", "mock"))

    def test_environment_switches_to_real_dataset_without_code_change(self) -> None:
        env = {DATASET_PATH_ENV: "data/processed/weather.csv", DATASET_KIND_ENV: "LIVE", LABEL_SOURCE_ENV: "measured"}
        with mock.patch.dict(os.environ, env, clear=True):
            source = default_dataset_source()

        self.assertEqual(source.path, Path("data/processed/weather.csv"))
        self.assertEqual((source.dataset_kind, source.label_source), ("LIVE", "measured"))

    def test_rejects_mock_dataset_labeled_as_measured(self) -> None:
        env = {DATASET_KIND_ENV: "MOCK", LABEL_SOURCE_ENV: "measured"}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(DatasetError, "label"):
                default_dataset_source()


if __name__ == "__main__":
    unittest.main()
