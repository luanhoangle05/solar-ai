"""LSTM sequence building (no look-ahead, no label) and a training smoke test."""

import dataclasses
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

import numpy as np

from scripts.generate_example_data import DEFAULT_EXAMPLE_CONFIG, generate_rows
from src.common.schema import FEATURE_COLUMNS
from src.common.tool_contracts import EnergyPredictor, ToolError
from src.models.advanced.features import feature_matrix, split_for_early_stopping
from src.models.advanced.lstm import LstmConfig, build_sequences, train_lstm
from src.models.evaluation import chronological_split, evaluate_predictor, to_features


MOCK = Path(__file__).resolve().parents[2] / "data" / "mock"
METADATA = json.loads((MOCK / "sample_model_output.json").read_text(encoding="utf-8"))["metadata"]
SMOKE_DATA = dataclasses.replace(
    DEFAULT_EXAMPLE_CONFIG,
    start=datetime(2026, 5, 1, tzinfo=timezone.utc),
    end=datetime(2026, 6, 15, tzinfo=timezone.utc),
)
SMOKE_MODEL = LstmConfig(sequence_length=4, hidden_size=24, max_epochs=25, patience=6)
ANGLE_COLUMN = FEATURE_COLUMNS.index("panel_angle_deg")


def hourly_rows(count: int, *, skip_hours: tuple[int, ...] = ()) -> list[dict]:
    """Rows whose every feature equals the hour number, so windows are easy to read."""
    return [
        {"timestamp": f"2026-06-{1 + hour // 24:02d}T{hour % 24:02d}:00:00Z", **{name: float(hour) for name in FEATURE_COLUMNS}, "actual_kwh": 1000.0 + hour}
        for hour in range(count) if hour not in skip_hours
    ]


class BuildSequencesTest(unittest.TestCase):
    def test_each_window_ends_at_its_target_and_holds_the_preceding_hours(self) -> None:
        sequences = build_sequences(hourly_rows(6), sequence_length=3)

        self.assertEqual(sequences.target_indices, (2, 3, 4, 5))
        self.assertEqual(sequences.inputs.shape, (4, 3, len(FEATURE_COLUMNS)))
        self.assertEqual(sequences.inputs[0, :, 0].tolist(), [0.0, 1.0, 2.0])
        self.assertEqual(sequences.inputs[-1, :, 0].tolist(), [3.0, 4.0, 5.0])

    def test_no_window_reaches_past_its_prediction_hour(self) -> None:
        rows = hourly_rows(12)

        sequences = build_sequences(rows, sequence_length=4)

        for window, target in zip(sequences.inputs, sequences.target_indices):
            self.assertLessEqual(window.max(), float(target))

    def test_changing_future_rows_does_not_change_earlier_windows(self) -> None:
        rows = hourly_rows(12)
        tampered = [row if index <= 6 else {**row, **{name: -999.0 for name in FEATURE_COLUMNS}} for index, row in enumerate(rows)]

        original = build_sequences(rows, sequence_length=4)
        changed = build_sequences(tampered, sequence_length=4)

        up_to_cutoff = [position for position, target in enumerate(original.target_indices) if target <= 6]
        self.assertTrue(up_to_cutoff)
        np.testing.assert_array_equal(original.inputs[up_to_cutoff], changed.inputs[up_to_cutoff])

    def test_label_is_never_part_of_a_window(self) -> None:
        sequences = build_sequences(hourly_rows(8), sequence_length=3)

        self.assertLess(sequences.inputs.max(), 1000.0)

    def test_windows_never_span_a_gap_in_the_hourly_series(self) -> None:
        rows = hourly_rows(10, skip_hours=(4,))

        sequences = build_sequences(rows, sequence_length=3)

        target_hours = [int(rows[index]["temperature_c"]) for index in sequences.target_indices]
        self.assertEqual(target_hours, [2, 3, 7, 8, 9])

    def test_first_target_limits_targets_but_windows_reach_back(self) -> None:
        sequences = build_sequences(hourly_rows(8), sequence_length=3, first_target=6)

        self.assertEqual(sequences.target_indices, (6, 7))
        self.assertEqual(sequences.inputs[0, :, 0].tolist(), [4.0, 5.0, 6.0])

    def test_too_few_rows_gives_no_sequences(self) -> None:
        sequences = build_sequences(hourly_rows(2), sequence_length=3)

        self.assertEqual(sequences.target_indices, ())
        self.assertEqual(sequences.inputs.shape, (0, 3, len(FEATURE_COLUMNS)))


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

    def test_missing_history_raises_tool_error_instead_of_guessing(self) -> None:
        unseen_hour = {**self.noon, "timestamp": "2031-01-01T12:00:00Z"}

        with self.assertRaisesRegex(ToolError, "history is missing"):
            self.predictor.predict_kwh(unseen_hour, (35.0,), metadata=METADATA)

    def test_too_few_rows_raises_tool_error(self) -> None:
        with self.assertRaises(ToolError):
            train_lstm(self.fit_rows[:2], self.stop_rows[:1], self.history, SMOKE_MODEL)

    def test_does_not_mutate_the_weather_input(self) -> None:
        before = dict(self.noon)

        self.predictor.predict_kwh(self.noon, (10.0, 70.0), metadata=METADATA)

        self.assertEqual(self.noon, before)


if __name__ == "__main__":
    unittest.main()
