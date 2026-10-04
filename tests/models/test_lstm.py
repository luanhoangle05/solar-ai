"""LSTM window building (no look-ahead, no label, honest padding) and a training smoke test."""

import dataclasses
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

import numpy as np

from scripts.generate_example_data import DEFAULT_EXAMPLE_CONFIG, generate_rows
from src.common.schema import FEATURE_COLUMNS
from src.common.tool_contracts import EnergyPredictor, ToolError
from src.models.advanced.features import MODEL_FEATURE_NAMES, feature_matrix, split_for_early_stopping
from src.models.advanced.lstm import LstmConfig, _shorten_history, build_windows, hourly_history, train_lstm
from src.models.evaluation import chronological_split, evaluate_predictor, to_features


MOCK = Path(__file__).resolve().parents[2] / "data" / "mock"
METADATA = json.loads((MOCK / "sample_model_output.json").read_text(encoding="utf-8"))["metadata"]
SMOKE_DATA = dataclasses.replace(
    DEFAULT_EXAMPLE_CONFIG,
    start=datetime(2026, 5, 1, tzinfo=timezone.utc),
    end=datetime(2026, 6, 15, tzinfo=timezone.utc),
)
SMOKE_MODEL = LstmConfig(sequence_length=4, hidden_size=24, max_epochs=25, patience=6)
HOUR_COLUMN = MODEL_FEATURE_NAMES.index("temperature_c")
ANGLE_COLUMN = MODEL_FEATURE_NAMES.index("panel_angle_deg")


def hourly_rows(count: int, *, skip_hours: tuple[int, ...] = ()) -> list[dict]:
    """Rows whose temperature equals the hour number, so each window step can be identified."""
    return [
        {
            "timestamp": f"2026-06-{1 + hour // 24:02d}T{hour % 24:02d}:00:00Z",
            **{name: 1.0 for name in FEATURE_COLUMNS}, "temperature_c": float(hour), "panel_angle_deg": 30.0, "actual_kwh": 1000.0 + hour,
        }
        for hour in range(count) if hour not in skip_hours
    ]


def step_hours(windows, index: int) -> list[float | None]:
    """The hour number held by each step of one window; None for a padding step."""
    return [float(step[HOUR_COLUMN]) if is_real else None for step, is_real in zip(windows.features[index], windows.valid[index])]


class BuildWindowsTest(unittest.TestCase):
    def test_each_window_ends_at_its_target_and_holds_the_preceding_hours(self) -> None:
        rows = hourly_rows(6)

        windows = build_windows(rows, hourly_history(rows), sequence_length=3)

        self.assertEqual(windows.features.shape, (6, 3, len(MODEL_FEATURE_NAMES)))
        self.assertEqual(step_hours(windows, 5), [3.0, 4.0, 5.0])
        self.assertEqual(step_hours(windows, 2), [0.0, 1.0, 2.0])

    def test_no_window_reaches_past_its_prediction_hour(self) -> None:
        rows = hourly_rows(12)

        windows = build_windows(rows, hourly_history(rows), sequence_length=4)

        for index in range(len(rows)):
            self.assertLessEqual(max(hour for hour in step_hours(windows, index) if hour is not None), float(index))

    def test_changing_future_rows_does_not_change_earlier_windows(self) -> None:
        rows = hourly_rows(12)
        tampered = [row if index <= 6 else {**row, "temperature_c": -999.0, "ghi_wm2": 999.0} for index, row in enumerate(rows)]

        original = build_windows(rows[:7], hourly_history(rows), sequence_length=4)
        changed = build_windows(tampered[:7], hourly_history(tampered), sequence_length=4)

        np.testing.assert_array_equal(original.features, changed.features)
        np.testing.assert_array_equal(original.valid, changed.valid)

    def test_label_is_never_part_of_a_window(self) -> None:
        rows = hourly_rows(8)

        windows = build_windows(rows, hourly_history(rows), sequence_length=3)

        self.assertLess(windows.features.max(), 1000.0)

    def test_missing_history_is_padding_not_invented_weather(self) -> None:
        rows = hourly_rows(4)

        windows = build_windows(rows, hourly_history(rows), sequence_length=3)

        self.assertEqual(step_hours(windows, 0), [None, None, 0.0])
        self.assertEqual(step_hours(windows, 1), [None, 0.0, 1.0])
        self.assertEqual(step_hours(windows, 2), [0.0, 1.0, 2.0])

    def test_windows_never_span_a_gap_in_the_hourly_series(self) -> None:
        rows = hourly_rows(8, skip_hours=(4,))

        windows = build_windows(rows, hourly_history(rows), sequence_length=3)

        by_hour = {int(row["temperature_c"]): index for index, row in enumerate(rows)}
        self.assertEqual(step_hours(windows, by_hour[5]), [None, None, 5.0])
        self.assertEqual(step_hours(windows, by_hour[6]), [None, 5.0, 6.0])
        self.assertEqual(step_hours(windows, by_hour[7]), [5.0, 6.0, 7.0])

    def test_history_steps_take_the_targets_panel_angle(self) -> None:
        rows = hourly_rows(4)
        target = {**rows[3], "panel_angle_deg": 55.0}

        windows = build_windows([target], hourly_history(rows), sequence_length=3)

        self.assertEqual(windows.features[0, :, ANGLE_COLUMN].tolist(), [55.0, 55.0, 55.0])

    def test_several_angles_for_one_hour_each_get_their_own_window(self) -> None:
        rows = hourly_rows(3)
        targets = [{**rows[2], "panel_angle_deg": angle} for angle in (30.0, 45.0, 60.0)]

        windows = build_windows(targets, hourly_history(rows), sequence_length=2)

        self.assertEqual([step_hours(windows, index) for index in range(3)], [[1.0, 2.0]] * 3)
        self.assertEqual(windows.features[:, :, ANGLE_COLUMN].tolist(), [[30.0, 30.0], [45.0, 45.0], [60.0, 60.0]])

    def test_no_targets_gives_an_empty_window_set(self) -> None:
        windows = build_windows([], {}, sequence_length=3)

        self.assertEqual(windows.features.shape, (0, 3, len(MODEL_FEATURE_NAMES)))

    def test_unparseable_timestamp_raises_tool_error(self) -> None:
        with self.assertRaises(ToolError):
            build_windows([{**hourly_rows(1)[0], "timestamp": "yesterday"}], {}, sequence_length=2)


class ShortenHistoryTest(unittest.TestCase):
    def setUp(self) -> None:
        rows = hourly_rows(200)
        self.windows = build_windows(rows[10:], hourly_history(rows), sequence_length=5)
        self.shortened = _shorten_history(self.windows, LstmConfig(sequence_length=5, history_dropout=0.5))

    def test_target_step_is_always_kept_and_features_are_untouched(self) -> None:
        self.assertTrue(self.shortened.valid[:, -1].all())
        np.testing.assert_array_equal(self.shortened.features, self.windows.features)

    def test_only_a_leading_run_of_history_is_hidden(self) -> None:
        for flags in self.shortened.valid:
            first_real = int(np.argmax(flags))
            self.assertTrue(flags[first_real:].all())

    def test_roughly_the_configured_share_of_windows_is_shortened_including_to_no_history(self) -> None:
        real_steps = self.shortened.valid.sum(axis=1)

        self.assertTrue(0.35 < (real_steps < 5).mean() < 0.65)
        self.assertIn(1, real_steps)

    def test_zero_dropout_leaves_windows_unchanged(self) -> None:
        unchanged = _shorten_history(self.windows, LstmConfig(sequence_length=5, history_dropout=0.0))

        np.testing.assert_array_equal(unchanged.valid, self.windows.valid)

    def test_shortening_is_reproducible(self) -> None:
        again = _shorten_history(self.windows, LstmConfig(sequence_length=5, history_dropout=0.5))

        np.testing.assert_array_equal(again.valid, self.shortened.valid)


class LstmSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = generate_rows(SMOKE_DATA)
        cls.split = chronological_split(cls.rows)
        cls.fit_rows, cls.stop_rows = split_for_early_stopping(cls.split.train)
        cls.history = [to_features(row) for row in cls.rows]
        cls.predictor = train_lstm(cls.fit_rows, cls.stop_rows, cls.history, SMOKE_MODEL)
        cls.noon = to_features(max(cls.split.test, key=lambda row: row["sun_elevation_deg"]))

    def test_implements_shared_energy_predictor_interface(self) -> None:
        self.assertIsInstance(self.predictor, EnergyPredictor)
        self.assertEqual(self.predictor.implementation, "pytorch")

    def test_returns_one_nonnegative_prediction_per_angle_in_order(self) -> None:
        angles = (60.0, 30.0, 45.0)

        predictions = self.predictor.predict_kwh(self.noon, angles, metadata=METADATA)

        self.assertEqual([entry["angle_deg"] for entry in predictions], list(angles))
        for entry in predictions:
            self.assertIsInstance(entry["predicted_kwh"], float)
            self.assertGreaterEqual(entry["predicted_kwh"], 0.0)

    def test_prediction_changes_with_panel_angle(self) -> None:
        predictions = self.predictor.predict_kwh(self.noon, (0.0, 30.0, 90.0), metadata=METADATA)

        self.assertGreater(len({entry["predicted_kwh"] for entry in predictions}), 1)

    def test_candidate_angle_replaces_the_current_panel_angle(self) -> None:
        self.assertEqual(
            self.predictor.predict_kwh({**self.noon, "panel_angle_deg": 40.0}, (40.0,), metadata=METADATA),
            self.predictor.predict_kwh({**self.noon, "panel_angle_deg": 85.0}, (40.0,), metadata=METADATA),
        )

    def test_prediction_ignores_rows_after_the_prediction_hour(self) -> None:
        cutoff = self.noon["timestamp"]
        future_blind = [row for row in self.history if row["timestamp"] < cutoff]
        truncated = train_lstm(self.fit_rows, self.stop_rows, future_blind, SMOKE_MODEL)

        self.assertEqual(
            truncated.predict_kwh(self.noon, (35.0, 50.0), metadata=METADATA),
            self.predictor.predict_kwh(self.noon, (35.0, 50.0), metadata=METADATA),
        )

    def test_scaling_is_fitted_on_fit_rows_only(self) -> None:
        scaler = self.predictor._scaler

        np.testing.assert_allclose(scaler.mean, feature_matrix(self.fit_rows).mean(axis=0))
        self.assertEqual(scaler.target_scale, max(row["actual_kwh"] for row in self.fit_rows))
        self.assertFalse(np.allclose(scaler.mean, feature_matrix(self.split.train).mean(axis=0)))

    def test_later_labels_cannot_influence_training(self) -> None:
        relabeled_history = [{**row, "actual_kwh": 999.0} for row in self.rows]
        retrained = train_lstm(self.fit_rows, self.stop_rows, relabeled_history, SMOKE_MODEL)

        self.assertEqual(
            retrained.predict_kwh(self.noon, (35.0, 50.0), metadata=METADATA),
            self.predictor.predict_kwh(self.noon, (35.0, 50.0), metadata=METADATA),
        )

    def test_learns_more_than_the_mean_on_held_out_test_rows(self) -> None:
        metrics = evaluate_predictor(self.predictor, self.split.test, metadata=METADATA)

        self.assertGreater(metrics.r2, 0.5)

    def test_training_is_reproducible(self) -> None:
        again = train_lstm(self.fit_rows, self.stop_rows, self.history, SMOKE_MODEL)

        self.assertEqual(
            again.predict_kwh(self.noon, (35.0, 50.0), metadata=METADATA),
            self.predictor.predict_kwh(self.noon, (35.0, 50.0), metadata=METADATA),
        )

    def test_predicts_for_an_hour_with_no_stored_history(self) -> None:
        unseen_hour = {**self.noon, "timestamp": "2031-01-01T12:00:00Z"}

        predictions = self.predictor.predict_kwh(unseen_hour, (30.0, 60.0), metadata=METADATA)

        self.assertEqual([entry["angle_deg"] for entry in predictions], [30.0, 60.0])
        self.assertTrue(all(entry["predicted_kwh"] >= 0 for entry in predictions))
        self.assertNotEqual(predictions, self.predictor.predict_kwh(self.noon, (30.0, 60.0), metadata=METADATA))

    def test_still_learns_daytime_energy_without_any_stored_history(self) -> None:
        metrics = evaluate_predictor(self.predictor.without_history(), self.split.test, metadata=METADATA)

        self.assertGreater(metrics.r2, 0.5)

    def test_trains_on_several_angle_rows_per_hour(self) -> None:
        hours = self.rows[:240]
        expanded = [{**row, "panel_angle_deg": angle} for row in hours for angle in (30.0, 45.0, 60.0)]
        fit_rows, stop_rows = split_for_early_stopping(expanded)

        predictor = train_lstm(fit_rows, stop_rows, [to_features(row) for row in expanded], SMOKE_MODEL)
        predictions = predictor.predict_kwh(to_features(hours[100]), (30.0, 45.0, 60.0), metadata=METADATA)

        self.assertEqual([entry["angle_deg"] for entry in predictions], [30.0, 45.0, 60.0])

    def test_empty_training_window_raises_tool_error(self) -> None:
        with self.assertRaises(ToolError):
            train_lstm((), self.stop_rows, self.history, SMOKE_MODEL)

    def test_does_not_mutate_the_weather_input(self) -> None:
        before = dict(self.noon)

        self.predictor.predict_kwh(self.noon, (10.0, 70.0), metadata=METADATA)

        self.assertEqual(self.noon, before)


if __name__ == "__main__":
    unittest.main()
