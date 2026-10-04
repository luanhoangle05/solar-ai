"""The single weather-row loader: header, per-row contract, chronological order."""

import csv
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from src.common.schema import FEATURE_COLUMNS, WEATHER_COLUMNS
from src.models.advanced.features import feature_matrix, label_vector
from src.models.data_loader import (
    DATASET_KIND_ENV, DATASET_PATH_ENV, EXAMPLE_DATASET_PATH, EXAMPLE_DATASET_SOURCE, LABEL_SOURCE_ENV,
    FULL_SPLIT_FILE_NAMES, PIPELINE_DATASET_PATH, PIPELINE_DATASET_SOURCE, SAMPLE_SPLIT_FILE_NAMES, DatasetError, DatasetSource,
    default_dataset_source,
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

        with self.assertRaisesRegex(DatasetError, "line 3: duplicate row"):
            load_weather_rows(path)

    def test_rejects_weather_that_differs_between_angle_rows_of_one_hour(self) -> None:
        other_angle_other_weather = [VALID_ROW[0], 99, *VALID_ROW[2:11], 50, 1.5]
        path = self.write(list(WEATHER_COLUMNS), [VALID_ROW, other_angle_other_weather])

        with self.assertRaisesRegex(DatasetError, "line 3: weather .* differs"):
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

    def test_unknown_path_must_declare_its_provenance(self) -> None:
        with mock.patch.dict(os.environ, {DATASET_PATH_ENV: "data/processed/weather.csv"}, clear=True):
            with self.assertRaisesRegex(DatasetError, "not a known dataset"):
                default_dataset_source()

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

    def test_directory_without_a_complete_set_of_split_files_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(DatasetError, "train.csv"):
                load_dataset_split(DatasetSource(Path(directory), "LIVE", "physics-derived"))


def angle_rows(timestamp: str, kwh: float) -> list[list]:
    """The seven candidate-angle rows of one hour; the label tells the files apart."""
    return [[timestamp, 13, 35, 0, 10, 16, 250, 420, 115, 19, 77, angle, kwh] for angle in (30, 35, 40, 45, 50, 55, 60)]


def hours(year: int, count: int, kwh: float) -> list[list]:
    return [row for hour in range(count) for row in angle_rows(f"{year}-01-15T{hour:02d}:00:00Z", kwh)]


class DeliveredSplitFilesTest(unittest.TestCase):
    """Three delivered files are the split; they are never cut again by row percentage."""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.source = DatasetSource(self.directory, "LIVE", "physics-derived")

    def write(self, file_name: str, rows: list[list]) -> None:
        with (self.directory / file_name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(WEATHER_COLUMNS)
            writer.writerows(rows)

    def write_set(self, names: dict[str, str], *, label_offset: float = 0.0) -> None:
        # Deliberately far from 70/15/15, so a percentage re-split could not reproduce these sizes.
        self.write(names["train"], hours(2023, 3, 1.0 + label_offset))
        self.write(names["validation"], hours(2024, 5, 2.0 + label_offset))
        self.write(names["test"], hours(2025, 4, 3.0 + label_offset))

    def assert_windows(self, split, *, label_offset: float = 0.0) -> None:
        for name, year, hour_count, kwh in (("train", "2023", 3, 1.0), ("validation", "2024", 5, 2.0), ("test", "2025", 4, 3.0)):
            rows = getattr(split, name)
            self.assertEqual(len(rows), hour_count * 7, name)
            self.assertEqual({row["timestamp"][:4] for row in rows}, {year}, name)
            self.assertEqual({row["actual_kwh"] for row in rows}, {kwh + label_offset}, name)

    def test_full_dataset_file_names_load_as_the_delivered_windows(self) -> None:
        self.write_set(FULL_SPLIT_FILE_NAMES)

        split = load_dataset_split(self.source)

        self.assertEqual(FULL_SPLIT_FILE_NAMES, {"train": "train.csv", "validation": "validation.csv", "test": "test.csv"})
        self.assert_windows(split)
        for name, file_name in FULL_SPLIT_FILE_NAMES.items():
            self.assertEqual(list(getattr(split, name)), load_weather_rows(self.directory / file_name))

    def test_sample_file_names_still_load_as_the_delivered_windows(self) -> None:
        self.write_set(SAMPLE_SPLIT_FILE_NAMES)

        self.assert_windows(load_dataset_split(self.source))

    def test_full_dataset_files_take_priority_over_sample_files(self) -> None:
        self.write_set(SAMPLE_SPLIT_FILE_NAMES, label_offset=0.5)
        self.write_set(FULL_SPLIT_FILE_NAMES)

        self.assert_windows(load_dataset_split(self.source))

    def test_a_single_combined_file_never_overrides_the_delivered_windows(self) -> None:
        self.write_set(FULL_SPLIT_FILE_NAMES)
        self.write("full_dataset.csv", [*hours(2023, 3, 9.0), *hours(2024, 5, 9.0), *hours(2025, 4, 9.0)])

        self.assert_windows(load_dataset_split(self.source))

    def test_an_incomplete_full_set_is_an_error_even_when_a_sample_set_is_complete(self) -> None:
        self.write_set(SAMPLE_SPLIT_FILE_NAMES, label_offset=0.5)
        self.write("train.csv", hours(2023, 3, 1.0))
        self.write("validation.csv", hours(2024, 5, 2.0))

        with self.assertRaisesRegex(DatasetError, "missing test.csv"):
            load_dataset_split(self.source)

    def test_a_directory_with_only_a_combined_file_is_not_split_by_percentage(self) -> None:
        self.write("full_dataset.csv", hours(2023, 20, 1.0))

        with self.assertRaisesRegex(DatasetError, "train.csv"):
            load_dataset_split(self.source)

    def test_overlapping_windows_are_rejected(self) -> None:
        self.write("train.csv", hours(2024, 3, 1.0))
        self.write("validation.csv", hours(2024, 5, 2.0))
        self.write("test.csv", hours(2025, 4, 3.0))

        with self.assertRaisesRegex(DatasetError, "overlap"):
            load_dataset_split(self.source)

    def test_label_is_the_target_and_never_a_feature_and_timestamp_is_not_a_feature(self) -> None:
        self.write_set(FULL_SPLIT_FILE_NAMES)
        train = load_dataset_split(self.source).train

        features = feature_matrix(train, geometry=False)

        self.assertEqual(list(label_vector(train)), [row["actual_kwh"] for row in train])
        self.assertNotIn("actual_kwh", FEATURE_COLUMNS)
        self.assertNotIn("timestamp", FEATURE_COLUMNS)
        self.assertEqual(features.shape, (len(train), len(FEATURE_COLUMNS)))
        self.assertEqual(train[0]["timestamp"], "2023-01-15T00:00:00Z")
        # Changing only the label leaves the feature matrix untouched.
        relabeled = [{**row, "actual_kwh": row["actual_kwh"] + 5.0} for row in train]
        self.assertTrue((feature_matrix(relabeled) == feature_matrix(train)).all())


if __name__ == "__main__":
    unittest.main()
