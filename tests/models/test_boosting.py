"""Boosting (XGBoost) smoke tests on a small slice of synthetic example data."""

import dataclasses
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

from scripts.generate_example_data import DEFAULT_EXAMPLE_CONFIG, generate_rows
from src.common.tool_contracts import EnergyPredictor, ToolError
from src.models.advanced.boosting import BoostingConfig, train_boosting
from src.models.evaluation import chronological_split, evaluate_predictor, to_features


MOCK = Path(__file__).resolve().parents[2] / "data" / "mock"
METADATA = json.loads((MOCK / "sample_model_output.json").read_text(encoding="utf-8"))["metadata"]
SMOKE_DATA = dataclasses.replace(
    DEFAULT_EXAMPLE_CONFIG,
    start=datetime(2026, 5, 1, tzinfo=timezone.utc),
    end=datetime(2026, 6, 15, tzinfo=timezone.utc),
)
SMOKE_MODEL = BoostingConfig(num_boost_round=150)


class BoostingSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.split = chronological_split(generate_rows(SMOKE_DATA))
        cls.predictor = train_boosting(cls.split.train, cls.split.validation, SMOKE_MODEL)
        cls.noon = to_features(max(cls.split.test, key=lambda row: row["sun_elevation_deg"]))

    def test_implements_shared_energy_predictor_interface(self) -> None:
        self.assertIsInstance(self.predictor, EnergyPredictor)
        self.assertEqual(self.predictor.implementation, "xgboost")

    def test_returns_one_nonnegative_prediction_per_angle_in_order(self) -> None:
        angles = (60.0, 30.0, 45.0)

        predictions = self.predictor.predict_kwh(self.noon, angles, metadata=METADATA)

        self.assertEqual([entry["angle_deg"] for entry in predictions], list(angles))
        for entry in predictions:
            self.assertIsInstance(entry["predicted_kwh"], float)
            self.assertGreaterEqual(entry["predicted_kwh"], 0.0)

    def test_candidate_angle_replaces_the_current_panel_angle(self) -> None:
        angle = 40.0
        already_there = {**self.noon, "panel_angle_deg": angle}
        elsewhere = {**self.noon, "panel_angle_deg": 85.0}

        self.assertEqual(
            self.predictor.predict_kwh(already_there, (angle,), metadata=METADATA),
            self.predictor.predict_kwh(elsewhere, (angle,), metadata=METADATA),
        )

    def test_prediction_changes_with_panel_angle(self) -> None:
        predictions = self.predictor.predict_kwh(self.noon, (0.0, 30.0, 90.0), metadata=METADATA)

        self.assertGreater(len({entry["predicted_kwh"] for entry in predictions}), 1)

    def test_label_is_not_an_inference_input(self) -> None:
        with_label = {**self.noon, "actual_kwh": 999.0}

        self.assertEqual(
            self.predictor.predict_kwh(with_label, (35.0,), metadata=METADATA),
            self.predictor.predict_kwh(self.noon, (35.0,), metadata=METADATA),
        )

    def test_does_not_mutate_the_weather_input(self) -> None:
        before = dict(self.noon)

        self.predictor.predict_kwh(self.noon, (10.0, 70.0), metadata=METADATA)

        self.assertEqual(self.noon, before)

    def test_learns_more_than_the_mean_on_held_out_test_rows(self) -> None:
        metrics = evaluate_predictor(self.predictor, self.split.test, metadata=METADATA)

        self.assertGreater(metrics.r2, 0.8)

    def test_training_is_reproducible(self) -> None:
        again = train_boosting(self.split.train, self.split.validation, SMOKE_MODEL)

        self.assertEqual(
            again.predict_kwh(self.noon, (35.0, 50.0), metadata=METADATA),
            self.predictor.predict_kwh(self.noon, (35.0, 50.0), metadata=METADATA),
        )

    def test_missing_feature_raises_tool_error(self) -> None:
        incomplete = {name: value for name, value in self.noon.items() if name != "dni_wm2"}

        with self.assertRaises(ToolError):
            self.predictor.predict_kwh(incomplete, (35.0,), metadata=METADATA)

    def test_empty_training_window_raises_tool_error(self) -> None:
        with self.assertRaises(ToolError):
            train_boosting((), self.split.validation, SMOKE_MODEL)


if __name__ == "__main__":
    unittest.main()
