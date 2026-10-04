"""Optimization Agent: coordinates the optimization tools and explains the result."""

import copy
import unittest

from src.agents.optimization_agent import OptimizationAgent
from src.agents.trace import StageError
from src.common.agent_contracts import OptimizationAgentContract
from src.common.config import DEFAULT_CONFIG
from src.common.schema import validate_agent_state
from src.common.tool_contracts import ToolError
from src.models.optimizer import DeterministicOptimizationTools
from tests.agents.support import FIXED_TIME, fixed_clock, state_before


class RecordingTools(DeterministicOptimizationTools):
    """Real tools that also record which ones the agent used."""

    def __init__(self) -> None:
        self.used: list[str] = []

    def generate_candidate_angles(self, *args, **kwargs):
        self.used.append("generate_candidate_angles")
        return super().generate_candidate_angles(*args, **kwargs)

    def calculate_movement_cost(self, *args, **kwargs):
        self.used.append("calculate_movement_cost")
        return super().calculate_movement_cost(*args, **kwargs)

    def calculate_net_benefit(self, *args, **kwargs):
        self.used.append("calculate_net_benefit")
        return super().calculate_net_benefit(*args, **kwargs)

    def optimize_angle(self, *args, **kwargs):
        self.used.append("optimize_angle")
        return super().optimize_angle(*args, **kwargs)


class BrokenOptimizer(DeterministicOptimizationTools):
    def optimize_angle(self, *args, **kwargs):
        raise ToolError("solver exploded")


class OptimizationAgentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.state = state_before("optimization")
        self.tools = RecordingTools()
        self.agent = OptimizationAgent(self.tools, DEFAULT_CONFIG, clock=fixed_clock)

    def test_implements_agent_contract(self) -> None:
        self.assertIsInstance(self.agent, OptimizationAgentContract)

    def test_returns_only_its_own_section_and_traces(self) -> None:
        update = self.agent.run(self.state)

        self.assertEqual(set(update), {"optimization", "agent_log", "tool_calls"})

    def test_recommends_max_net_benefit_from_mock_predictions(self) -> None:
        optimization = self.agent.run(self.state)["optimization"]

        self.assertEqual(optimization["current_angle_deg"], 35)
        self.assertEqual(optimization["recommended_angle_deg"], 45)
        self.assertAlmostEqual(optimization["net_benefit_kwh_equivalent"], 0.26)

    def test_result_comes_from_the_optimize_tool(self) -> None:
        optimization = self.agent.run(self.state)["optimization"]

        expected = DeterministicOptimizationTools().optimize_angle(
            self.state["modeling"]["candidate_predictions"], self.state["weather"]["panel_angle_deg"], config=DEFAULT_CONFIG,
        )
        self.assertEqual(optimization, expected)

    def test_coordinates_every_optimization_tool_and_records_the_calls(self) -> None:
        update = self.agent.run(self.state)

        candidate_count = len(self.state["modeling"]["candidate_predictions"])
        self.assertEqual(self.tools.used.count("generate_candidate_angles"), 1)
        self.assertEqual(self.tools.used.count("calculate_movement_cost"), candidate_count)
        self.assertEqual(self.tools.used.count("calculate_net_benefit"), candidate_count)
        self.assertEqual(self.tools.used[-1], "optimize_angle")
        self.assertEqual([call["tool"] for call in update["tool_calls"]], self.tools.used)
        for call in update["tool_calls"]:
            self.assertEqual((call["agent"], call["status"], call["timestamp"]), ("optimization", "OK", FIXED_TIME))

    def test_log_explains_the_comparison_and_the_recommendation(self) -> None:
        log = {entry["action"]: entry["result"] for entry in self.agent.run(self.state)["agent_log"]}

        self.assertIn("Stay at 35 deg", log["candidate_comparison"])
        self.assertIn("60 deg", log["candidate_comparison"])
        self.assertIn("45 deg", log["recommendation"])
        self.assertIn("+0.260", log["recommendation"])

    def test_update_merges_into_a_valid_shared_state(self) -> None:
        update = self.agent.run(self.state)

        merged = {
            **self.state,
            "optimization": update["optimization"],
            "agent_log": [*self.state["agent_log"], *update["agent_log"]],
            "tool_calls": [*self.state["tool_calls"], *update["tool_calls"]],
        }
        validate_agent_state(merged)

    def test_does_not_mutate_state(self) -> None:
        before = copy.deepcopy(self.state)

        self.agent.run(self.state)

        self.assertEqual(self.state, before)

    def test_recommends_staying_when_no_move_pays_for_itself(self) -> None:
        self.state["modeling"]["candidate_predictions"] = [
            {"angle_deg": 30, "predicted_kwh": 5.79}, {"angle_deg": 35, "predicted_kwh": 5.8}, {"angle_deg": 40, "predicted_kwh": 5.81},
        ]

        update = self.agent.run(self.state)

        self.assertEqual(update["optimization"]["recommended_angle_deg"], 35)
        self.assertEqual(update["optimization"]["net_benefit_kwh_equivalent"], 0)
        self.assertIn("Stay at 35 deg", update["agent_log"][-1]["result"])

    def test_missing_modeling_raises_stage_error_instead_of_inventing_output(self) -> None:
        self.state["modeling"] = None

        with self.assertRaises(StageError) as raised:
            self.agent.run(self.state)

        self.assertEqual((raised.exception.agent, raised.exception.code), ("optimization", "OPTIMIZATION_INPUT_UNAVAILABLE"))
        self.assertEqual(raised.exception.trace["agent_log"][-1]["action"], "failed")

    def test_missing_stay_prediction_raises_stage_error(self) -> None:
        self.state["modeling"]["candidate_predictions"] = [{"angle_deg": 45, "predicted_kwh": 6.09}]

        with self.assertRaisesRegex(StageError, "stay angle"):
            self.agent.run(self.state)

    def test_tool_failure_is_recorded_in_the_trace(self) -> None:
        agent = OptimizationAgent(BrokenOptimizer(), DEFAULT_CONFIG, clock=fixed_clock)

        with self.assertRaises(StageError) as raised:
            agent.run(self.state)

        failed_call = raised.exception.trace["tool_calls"][-1]
        self.assertEqual((failed_call["tool"], failed_call["status"]), ("optimize_angle", "ERROR"))
        self.assertIn("solver exploded", failed_call["detail"])
        self.assertEqual(raised.exception.code, "OPTIMIZATION_FAILED")

    def test_agent_without_tools_is_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError):
            OptimizationAgent(None, DEFAULT_CONFIG).run(self.state)


if __name__ == "__main__":
    unittest.main()
