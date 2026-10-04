"""Movement cost, net benefit, candidate generation and the net-benefit optimizer."""

import dataclasses
import unittest

from src.common.config import DEFAULT_CONFIG
from src.common.schema import CandidatePrediction
from src.common.tool_contracts import OptimizationTools, ToolError
from src.models.cost_simulation import calculate_movement_cost, calculate_net_benefit
from src.models.optimizer import DeterministicOptimizationTools, generate_candidate_angles, optimize_angle


def predictions(by_angle: dict[float, float]) -> list[CandidatePrediction]:
    return [{"angle_deg": angle, "predicted_kwh": kwh} for angle, kwh in by_angle.items()]


class MovementCostTest(unittest.TestCase):
    def test_cost_is_degrees_times_motor_plus_wear_coefficients(self) -> None:
        cost = calculate_movement_cost(35.0, 45.0, config=DEFAULT_CONFIG)

        self.assertEqual(cost["movement_degrees"], 10.0)
        self.assertAlmostEqual(cost["motor_energy_kwh"], 0.02)
        self.assertAlmostEqual(cost["wear_kwh_equivalent"], 0.01)
        self.assertAlmostEqual(cost["movement_cost_kwh_equivalent"], 0.03)

    def test_direction_does_not_change_cost(self) -> None:
        self.assertEqual(
            calculate_movement_cost(45.0, 35.0, config=DEFAULT_CONFIG),
            calculate_movement_cost(35.0, 45.0, config=DEFAULT_CONFIG),
        )

    def test_staying_costs_nothing(self) -> None:
        cost = calculate_movement_cost(35.0, 35.0, config=DEFAULT_CONFIG)

        self.assertEqual(set(cost.values()), {0.0})

    def test_coefficients_come_from_config(self) -> None:
        expensive = dataclasses.replace(DEFAULT_CONFIG, config_id="test", motor_kwh_per_degree=0.01, wear_kwh_equivalent_per_degree=0.0)

        cost = calculate_movement_cost(0.0, 10.0, config=expensive)

        self.assertAlmostEqual(cost["movement_cost_kwh_equivalent"], 0.1)

    def test_net_benefit_is_gain_minus_cost(self) -> None:
        self.assertAlmostEqual(calculate_net_benefit(0.29, 0.03), 0.26)
        self.assertAlmostEqual(calculate_net_benefit(0.01, 0.03), -0.02)


class CandidateGenerationTest(unittest.TestCase):
    def test_adds_stay_angle_when_not_in_configured_candidates(self) -> None:
        candidates = generate_candidate_angles(37.5, config=DEFAULT_CONFIG)

        self.assertIn(37.5, candidates)
        self.assertEqual(candidates, tuple(sorted({37.5, *DEFAULT_CONFIG.candidate_angles_deg})))

    def test_does_not_duplicate_stay_angle(self) -> None:
        candidates = generate_candidate_angles(35.0, config=DEFAULT_CONFIG)

        self.assertEqual(candidates, tuple(float(angle) for angle in DEFAULT_CONFIG.candidate_angles_deg))

    def test_drops_configured_candidates_outside_angle_limits(self) -> None:
        narrow = dataclasses.replace(DEFAULT_CONFIG, config_id="test", max_angle_deg=45.0)

        candidates = generate_candidate_angles(35.0, config=narrow)

        self.assertEqual(candidates, (30.0, 35.0, 40.0, 45.0))

    def test_rejects_impossible_current_angle(self) -> None:
        with self.assertRaises(ToolError):
            generate_candidate_angles(float("nan"), config=DEFAULT_CONFIG)


class OptimizeAngleTest(unittest.TestCase):
    def test_picks_max_net_benefit_not_max_energy(self) -> None:
        # Shared mock fixture: 60 degrees yields the most kWh, 45 degrees the most net benefit.
        candidates = predictions({30.0: 5.7, 35.0: 5.8, 40.0: 5.95, 45.0: 6.09, 50.0: 6.1, 55.0: 6.105, 60.0: 6.11})

        result = optimize_angle(candidates, 35.0, config=DEFAULT_CONFIG)

        self.assertEqual(result["recommended_angle_deg"], 45.0)
        self.assertEqual(result["current_angle_deg"], 35.0)
        self.assertEqual(result["baseline_kwh"], 5.8)
        self.assertEqual(result["predicted_kwh"], 6.09)
        self.assertAlmostEqual(result["energy_gain_kwh"], 0.29)
        self.assertAlmostEqual(result["movement_cost_kwh_equivalent"], 0.03)
        self.assertAlmostEqual(result["net_benefit_kwh_equivalent"], 0.26)

    def test_stays_when_every_move_costs_more_than_it_gains(self) -> None:
        candidates = predictions({30.0: 5.79, 35.0: 5.8, 40.0: 5.81})

        result = optimize_angle(candidates, 35.0, config=DEFAULT_CONFIG)

        self.assertEqual(result["recommended_angle_deg"], 35.0)
        self.assertEqual(result["energy_gain_kwh"], 0.0)
        self.assertEqual(result["movement_cost_kwh_equivalent"], 0.0)
        self.assertEqual(result["net_benefit_kwh_equivalent"], 0.0)

    def test_tie_prefers_least_movement(self) -> None:
        free = dataclasses.replace(DEFAULT_CONFIG, config_id="test", motor_kwh_per_degree=0.0, wear_kwh_equivalent_per_degree=0.0)
        candidates = predictions({35.0: 5.0, 40.0: 6.0, 60.0: 6.0})

        result = optimize_angle(candidates, 35.0, config=free)

        self.assertEqual(result["recommended_angle_deg"], 40.0)

    def test_tie_with_equal_movement_prefers_lowest_angle(self) -> None:
        candidates = predictions({30.0: 6.0, 35.0: 5.0, 40.0: 6.0})

        result = optimize_angle(candidates, 35.0, config=DEFAULT_CONFIG)

        self.assertEqual(result["recommended_angle_deg"], 30.0)

    def test_result_does_not_depend_on_candidate_order(self) -> None:
        by_angle = {30.0: 5.7, 35.0: 5.8, 45.0: 6.09, 60.0: 6.11}
        forward = predictions(by_angle)

        self.assertEqual(
            optimize_angle(forward, 35.0, config=DEFAULT_CONFIG),
            optimize_angle(forward[::-1], 35.0, config=DEFAULT_CONFIG),
        )

    def test_ignores_candidates_outside_angle_limits(self) -> None:
        narrow = dataclasses.replace(DEFAULT_CONFIG, config_id="test", max_angle_deg=40.0)
        candidates = predictions({35.0: 5.0, 40.0: 5.5, 60.0: 9.0})

        result = optimize_angle(candidates, 35.0, config=narrow)

        self.assertEqual(result["recommended_angle_deg"], 40.0)

    def test_requires_stay_candidate_for_the_baseline(self) -> None:
        with self.assertRaisesRegex(ToolError, "stay"):
            optimize_angle(predictions({30.0: 5.7, 45.0: 6.0}), 35.0, config=DEFAULT_CONFIG)

    def test_rejects_empty_predictions(self) -> None:
        with self.assertRaises(ToolError):
            optimize_angle([], 35.0, config=DEFAULT_CONFIG)

    def test_rejects_duplicate_or_invalid_predictions(self) -> None:
        with self.assertRaisesRegex(ToolError, "Duplicate"):
            optimize_angle(predictions({35.0: 5.0}) * 2, 35.0, config=DEFAULT_CONFIG)
        with self.assertRaisesRegex(ToolError, "nonnegative"):
            optimize_angle(predictions({35.0: 5.0, 40.0: -1.0}), 35.0, config=DEFAULT_CONFIG)

    def test_does_not_mutate_predictions(self) -> None:
        candidates = predictions({35.0: 5.8, 45.0: 6.09})
        before = [dict(entry) for entry in candidates]

        optimize_angle(candidates, 35.0, config=DEFAULT_CONFIG)

        self.assertEqual(candidates, before)


class OptimizationToolsTest(unittest.TestCase):
    def test_tool_object_implements_shared_protocol_and_delegates(self) -> None:
        tools = DeterministicOptimizationTools()
        candidates = predictions({35.0: 5.8, 45.0: 6.09})

        self.assertIsInstance(tools, OptimizationTools)
        self.assertEqual(tools.generate_candidate_angles(35.0, config=DEFAULT_CONFIG), generate_candidate_angles(35.0, config=DEFAULT_CONFIG))
        self.assertEqual(tools.calculate_movement_cost(35.0, 45.0, config=DEFAULT_CONFIG), calculate_movement_cost(35.0, 45.0, config=DEFAULT_CONFIG))
        self.assertEqual(tools.calculate_net_benefit(0.29, 0.03), calculate_net_benefit(0.29, 0.03))
        self.assertEqual(tools.optimize_angle(candidates, 35.0, config=DEFAULT_CONFIG), optimize_angle(candidates, 35.0, config=DEFAULT_CONFIG))


if __name__ == "__main__":
    unittest.main()
