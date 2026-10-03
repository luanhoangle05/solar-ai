"""Metric math, chronological splitting and rule-based model selection."""

import json
import math
from pathlib import Path
import unittest

from src.common.config import DEFAULT_CONFIG
from src.common.schema import MODEL_NAMES, ModelMetrics
from src.common.tool_contracts import ToolError
from src.models.data_loader import load_weather_rows
from src.models.evaluation import (
    StepOutcome, build_model_metrics, chronological_split, compute_metrics, evaluate_predictor, evaluate_system,
    select_best_model, selection_reason, unavailable_model_metrics,
)


MOCK = Path(__file__).resolve().parents[2] / "data" / "mock"


def metrics_entry(model: str, rmse: float | None) -> ModelMetrics:
    if rmse is None:
        return unavailable_model_metrics(model, implementation=model)
    return {"model": model, "implementation": model, "status": "MOCK", "mae": rmse / 2, "rmse": rmse, "r2": 0.5}


class ComputeMetricsTest(unittest.TestCase):
    def test_matches_hand_calculation(self) -> None:
        metrics = compute_metrics(actual=[1.0, 2.0, 3.0, 4.0], predicted=[1.5, 2.0, 2.0, 5.0])

        self.assertAlmostEqual(metrics.mae, 0.625)
        self.assertAlmostEqual(metrics.rmse, math.sqrt(2.25 / 4))
        self.assertAlmostEqual(metrics.r2, 1 - 2.25 / 5.0)

    def test_perfect_prediction_has_zero_error_and_unit_r2(self) -> None:
        metrics = compute_metrics(actual=[0.0, 1.0, 2.0], predicted=[0.0, 1.0, 2.0])

        self.assertEqual((metrics.mae, metrics.rmse, metrics.r2), (0.0, 0.0, 1.0))

    def test_r2_is_negative_when_worse_than_the_mean(self) -> None:
        metrics = compute_metrics(actual=[1.0, 2.0, 3.0], predicted=[3.0, 2.0, 1.0])

        self.assertLess(metrics.r2, 0)

    def test_agrees_with_shared_mock_fixture_metrics(self) -> None:
        output = json.loads((MOCK / "sample_model_output.json").read_text(encoding="utf-8"))
        fixture = output["evaluation_fixture"]

        for entry in output["modeling"]["model_comparison"]:
            metrics = compute_metrics(fixture["actual_kwh"], fixture[entry["model"]])
            for key in ("mae", "rmse", "r2"):
                self.assertAlmostEqual(getattr(metrics, key), entry[key], places=9)

    def test_rejects_length_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "length"):
            compute_metrics(actual=[1.0, 2.0], predicted=[1.0])

    def test_rejects_constant_targets_because_r2_is_undefined(self) -> None:
        with self.assertRaisesRegex(ValueError, "constant"):
            compute_metrics(actual=[2.0, 2.0, 2.0], predicted=[1.0, 2.0, 3.0])

    def test_rejects_non_finite_predictions(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite"):
            compute_metrics(actual=[1.0, 2.0], predicted=[1.0, float("nan")])


class ChronologicalSplitTest(unittest.TestCase):
    def test_splits_in_time_order_without_overlap(self) -> None:
        rows = [{"timestamp": f"2026-06-01T{hour:02d}:00:00Z"} for hour in range(20)]

        split = chronological_split(rows, train_fraction=0.7, validation_fraction=0.15)

        self.assertEqual((len(split.train), len(split.validation), len(split.test)), (14, 3, 3))
        self.assertEqual([*split.train, *split.validation, *split.test], rows)
        self.assertLess(split.train[-1]["timestamp"], split.validation[0]["timestamp"])
        self.assertLess(split.validation[-1]["timestamp"], split.test[0]["timestamp"])

    def test_rejects_fractions_that_leave_no_test_window(self) -> None:
        rows = [{"timestamp": f"2026-06-01T{hour:02d}:00:00Z"} for hour in range(20)]

        with self.assertRaisesRegex(ValueError, "fraction"):
            chronological_split(rows, train_fraction=0.8, validation_fraction=0.2)

    def test_rejects_dataset_too_small_for_three_windows(self) -> None:
        rows = [{"timestamp": "2026-06-01T00:00:00Z"}, {"timestamp": "2026-06-01T01:00:00Z"}]

        with self.assertRaisesRegex(ValueError, "rows"):
            chronological_split(rows, train_fraction=0.7, validation_fraction=0.15)


class EvaluatePredictorTest(unittest.TestCase):
    def test_scores_each_row_at_its_own_angle_without_the_label(self) -> None:
        rows = load_weather_rows(MOCK / "sample_weather.csv")
        metadata = json.loads((MOCK / "sample_model_output.json").read_text(encoding="utf-8"))["metadata"]
        seen = []

        class ConstantPredictor:
            def predict_kwh(self, weather, candidate_angles_deg, *, metadata):
                seen.append((weather, candidate_angles_deg))
                return [{"angle_deg": angle, "predicted_kwh": 4.0} for angle in candidate_angles_deg]

        metrics = evaluate_predictor(ConstantPredictor(), rows, metadata=metadata)

        actual = [row["actual_kwh"] for row in rows]
        self.assertAlmostEqual(metrics.mae, sum(abs(4.0 - value) for value in actual) / len(actual))
        self.assertEqual(len(seen), len(rows))
        for (weather, angles), row in zip(seen, rows):
            self.assertNotIn("actual_kwh", weather)
            self.assertEqual(angles, (row["panel_angle_deg"],))


class ModelSelectionTest(unittest.TestCase):
    def test_selects_lowest_validation_rmse(self) -> None:
        comparison = [metrics_entry("linear_regression", 0.4), metrics_entry("random_forest", 0.2), metrics_entry("boosting", 0.1), metrics_entry("lstm", 0.3)]

        self.assertEqual(select_best_model(comparison), "boosting")

    def test_ignores_unavailable_models(self) -> None:
        comparison = [metrics_entry("linear_regression", None), metrics_entry("random_forest", None), metrics_entry("boosting", 0.3), metrics_entry("lstm", 0.5)]

        self.assertEqual(select_best_model(comparison), "boosting")

    def test_tie_goes_to_the_earlier_model_in_the_documented_order(self) -> None:
        comparison = [metrics_entry("lstm", 0.2), metrics_entry("boosting", 0.2), metrics_entry("random_forest", 0.2), metrics_entry("linear_regression", 0.9)]

        self.assertEqual(select_best_model(comparison), "random_forest")

    def test_raises_tool_error_when_no_model_is_available(self) -> None:
        comparison = [metrics_entry(model, None) for model in MODEL_NAMES]

        with self.assertRaises(ToolError):
            select_best_model(comparison)

    def test_reason_names_the_rule_and_the_rmse(self) -> None:
        comparison = [metrics_entry("linear_regression", None), metrics_entry("random_forest", None), metrics_entry("boosting", 0.25), metrics_entry("lstm", None)]

        reason = selection_reason(comparison, "boosting")

        self.assertIn("lowest validation RMSE", reason)
        self.assertIn("0.25", reason)
        self.assertIn("1 of 4", reason)


class ModelMetricsBuilderTest(unittest.TestCase):
    def test_unavailable_entry_has_null_metrics_never_zero(self) -> None:
        entry = unavailable_model_metrics("lstm", implementation="pytorch")

        self.assertEqual(entry, {"model": "lstm", "implementation": "pytorch", "status": "UNAVAILABLE", "mae": None, "rmse": None, "r2": None})

    def test_metrics_on_mock_data_are_labeled_mock(self) -> None:
        metrics = compute_metrics(actual=[1.0, 2.0, 3.0], predicted=[1.0, 2.0, 2.0])

        mock_entry = build_model_metrics("boosting", "xgboost", metrics, dataset_kind="MOCK")
        live_entry = build_model_metrics("boosting", "xgboost", metrics, dataset_kind="LIVE")

        self.assertEqual(mock_entry["status"], "MOCK")
        self.assertEqual(live_entry["status"], "VALIDATED")
        self.assertEqual(mock_entry["rmse"], metrics.rmse)


class EvaluateSystemTest(unittest.TestCase):
    """Scripted decisions over four hours; energy is 1 kWh per 10 degrees of tilt."""

    def setUp(self) -> None:
        script = {
            "h1": StepOutcome("ROTATE", 45.0, safety_passed=True, severe_violation=False, max_energy_angle_deg=60.0),
            "h2": StepOutcome("HOLD", 45.0, safety_passed=True, severe_violation=False, max_energy_angle_deg=60.0),
            "h3": StepOutcome("STOW", 0.0, safety_passed=False, severe_violation=True, max_energy_angle_deg=60.0),
            "h4": StepOutcome("HOLD", 0.0, safety_passed=True, severe_violation=False, max_energy_angle_deg=0.0),
        }
        self.seen_angles: list[float] = []

        def decide(weather: dict) -> StepOutcome:
            self.seen_angles.append(weather["panel_angle_deg"])
            return script[weather["timestamp"]]

        self.result = evaluate_system(
            [{"timestamp": hour, "panel_angle_deg": 99.0} for hour in script], decide, lambda weather, angle: angle / 10,
            initial_angle_deg=35.0, energy_source="test formula", config=DEFAULT_CONFIG,
        )

    def test_each_decision_sees_the_angle_left_by_the_previous_one(self) -> None:
        self.assertEqual(self.seen_angles, [35.0, 45.0, 45.0, 0.0])

    def test_counts_actions(self) -> None:
        result = self.result

        self.assertEqual((result.hours, result.rotate_count, result.hold_count, result.stow_count), (4, 1, 2, 1))

    def test_energy_cost_and_net_benefit_totals(self) -> None:
        result = self.result

        self.assertAlmostEqual(result.baseline_kwh, 4 * 3.5)
        self.assertAlmostEqual(result.optimized_kwh, 4.5 + 4.5 + 0.0 + 0.0)
        self.assertAlmostEqual(result.energy_gain_kwh, 9.0 - 14.0)
        self.assertAlmostEqual(result.movement_cost_kwh_equivalent, (10 + 45) * 0.003)
        self.assertAlmostEqual(result.net_benefit_kwh_equivalent, -5.0 - 0.165)
        self.assertEqual(result.energy_source, "test formula")

    def test_counts_avoided_moves_and_safety_events(self) -> None:
        result = self.result

        # h2: a raw-energy tracker wanted 60 deg but the safe decision held. h4: nothing to avoid.
        self.assertEqual(result.unnecessary_moves_avoided, 1)
        self.assertEqual(result.severe_safety_events, 1)
        self.assertEqual(result.unsafe_rotations, 0)

    def test_flags_a_rotation_issued_despite_failed_safety(self) -> None:
        unsafe = StepOutcome("ROTATE", 45.0, safety_passed=False, severe_violation=False, max_energy_angle_deg=45.0)

        result = evaluate_system(
            [{"timestamp": "h1", "panel_angle_deg": 35.0}], lambda weather: unsafe, lambda weather, angle: 1.0,
            initial_angle_deg=35.0, energy_source="test formula", config=DEFAULT_CONFIG,
        )

        self.assertEqual(result.unsafe_rotations, 1)


if __name__ == "__main__":
    unittest.main()
