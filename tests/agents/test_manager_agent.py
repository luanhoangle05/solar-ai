"""Deterministic safety tools and the Manager / Safety Agent decision priority."""

import copy
import dataclasses
import unittest

from src.agents.manager_agent import DeterministicSafetyTools, ManagerAgent
from src.agents.trace import StageError
from src.common.agent_contracts import ManagerAgentContract
from src.common.config import DEFAULT_CONFIG
from src.common.schema import validate_agent_state
from src.common.tool_contracts import SafetyTools, ToolError
from tests.agents.support import fixed_clock, state_before


TOOLS = DeterministicSafetyTools()
PASSING = {"name": "wind_safety", "passed": True, "severity": "SEVERE", "reason": "ok"}
OPTIMIZATION = {
    "current_angle_deg": 35.0, "recommended_angle_deg": 45.0, "baseline_kwh": 5.8, "predicted_kwh": 6.09,
    "energy_gain_kwh": 6.09 - 5.8, "movement_cost_kwh_equivalent": 0.03, "net_benefit_kwh_equivalent": (6.09 - 5.8) - 0.03,
}


def ready_row(_target_id: str) -> dict:
    return {"angle_deg": 35.0, "current_state": "READY"}


def with_net_benefit(net: float) -> dict:
    gain = net + OPTIMIZATION["movement_cost_kwh_equivalent"]
    return {**OPTIMIZATION, "predicted_kwh": OPTIMIZATION["baseline_kwh"] + gain, "energy_gain_kwh": gain, "net_benefit_kwh_equivalent": net}


class SafetyChecksTest(unittest.TestCase):
    def setUp(self) -> None:
        self.weather = state_before("safety")["weather"]
        self.data = state_before("safety")["data"]

    def test_tools_implement_shared_protocol(self) -> None:
        self.assertIsInstance(TOOLS, SafetyTools)

    def test_wind_within_limits_passes(self) -> None:
        check = TOOLS.check_wind_safety(self.weather, config=DEFAULT_CONFIG)

        self.assertEqual((check["name"], check["passed"]), ("wind_safety", True))

    def test_wind_over_limit_is_a_severe_failure(self) -> None:
        check = TOOLS.check_wind_safety({**self.weather, "wind_speed_kmh": 50.1, "wind_gust_kmh": 55}, config=DEFAULT_CONFIG)

        self.assertEqual((check["passed"], check["severity"]), (False, "SEVERE"))

    def test_gust_over_limit_is_a_severe_failure(self) -> None:
        check = TOOLS.check_wind_safety({**self.weather, "wind_gust_kmh": 70.5}, config=DEFAULT_CONFIG)

        self.assertEqual((check["passed"], check["severity"]), (False, "SEVERE"))

    def test_wind_exactly_at_limit_passes(self) -> None:
        check = TOOLS.check_wind_safety({**self.weather, "wind_speed_kmh": 50.0, "wind_gust_kmh": 70.0}, config=DEFAULT_CONFIG)

        self.assertTrue(check["passed"])

    def test_wind_limits_come_from_config(self) -> None:
        strict = dataclasses.replace(DEFAULT_CONFIG, config_id="test", max_wind_speed_kmh=10.0)

        self.assertFalse(TOOLS.check_wind_safety(self.weather, config=strict)["passed"])

    def test_angle_limits(self) -> None:
        self.assertTrue(TOOLS.check_angle_limits(90.0, config=DEFAULT_CONFIG)["passed"])
        self.assertFalse(TOOLS.check_angle_limits(90.5, config=DEFAULT_CONFIG)["passed"])
        self.assertFalse(TOOLS.check_angle_limits(-1.0, config=DEFAULT_CONFIG)["passed"])

    def test_fresh_valid_data_passes(self) -> None:
        self.assertTrue(TOOLS.check_data_freshness(self.data, config=DEFAULT_CONFIG)["passed"])

    def test_stale_or_invalid_or_unknown_age_data_blocks_rotation(self) -> None:
        cases = (
            {**self.data, "forecast_age_minutes": 30.5},
            {**self.data, "status": "STALE", "issues": ["Forecast too old"]},
            {**self.data, "status": "INVALID", "issues": ["Missing irradiance"]},
            {**self.data, "forecast_age_minutes": None},
        )
        for data in cases:
            with self.subTest(data=data):
                check = TOOLS.check_data_freshness(data, config=DEFAULT_CONFIG)
                self.assertEqual((check["passed"], check["severity"]), (False, "BLOCK_ROTATE"))

    def test_panel_status(self) -> None:
        self.assertTrue(TOOLS.check_panel_status("READY")["passed"])
        self.assertTrue(TOOLS.check_panel_status("STOWED")["passed"])
        self.assertFalse(TOOLS.check_panel_status("MOVING")["passed"])
        self.assertFalse(TOOLS.check_panel_status("FAULT")["passed"])
        self.assertFalse(TOOLS.check_panel_status("unknown")["passed"])

    def test_model_confidence_checks_availability_only(self) -> None:
        evaluated = {"model": "boosting", "implementation": "xgboost", "status": "MOCK", "mae": 0.1, "rmse": 0.2, "r2": -3.0}
        unavailable = {"model": "lstm", "implementation": "pytorch", "status": "UNAVAILABLE", "mae": None, "rmse": None, "r2": None}

        self.assertTrue(TOOLS.check_model_confidence(evaluated)["passed"])
        self.assertFalse(TOOLS.check_model_confidence(unavailable)["passed"])


class SafetyRulesTest(unittest.TestCase):
    def apply(self, checks, optimization=OPTIMIZATION):
        return TOOLS.apply_safety_rules(checks, optimization, current_angle_deg=35.0, config=DEFAULT_CONFIG)

    def test_rotate_when_checks_pass_and_net_benefit_clears_threshold(self) -> None:
        safety, decision = self.apply([PASSING])

        self.assertTrue(safety["passed"])
        self.assertEqual((decision["action"], decision["target_angle_deg"]), ("ROTATE", 45.0))

    def test_stow_on_severe_violation_even_with_a_good_optimization(self) -> None:
        severe = {"name": "wind_safety", "passed": False, "severity": "SEVERE", "reason": "Gust 90 km/h"}
        blocked = {"name": "data_freshness", "passed": False, "severity": "BLOCK_ROTATE", "reason": "stale"}

        safety, decision = self.apply([blocked, severe])

        self.assertFalse(safety["passed"])
        self.assertEqual((decision["action"], decision["target_angle_deg"]), ("STOW", DEFAULT_CONFIG.stow_angle_deg))
        self.assertIn("Gust 90 km/h", decision["reason"])

    def test_hold_on_stale_data(self) -> None:
        stale = {"name": "data_freshness", "passed": False, "severity": "BLOCK_ROTATE", "reason": "Forecast is 45 min old"}

        safety, decision = self.apply([PASSING, stale])

        self.assertFalse(safety["passed"])
        self.assertEqual((decision["action"], decision["target_angle_deg"]), ("HOLD", 35.0))
        self.assertIn("45 min old", decision["reason"])

    def test_hold_when_net_benefit_equals_threshold(self) -> None:
        _, decision = self.apply([PASSING], with_net_benefit(DEFAULT_CONFIG.min_net_benefit_kwh_equivalent))

        self.assertEqual((decision["action"], decision["target_angle_deg"]), ("HOLD", 35.0))
        self.assertIn("threshold", decision["reason"])

    def test_hold_when_net_benefit_is_below_threshold(self) -> None:
        _, decision = self.apply([PASSING], with_net_benefit(0.005))

        self.assertEqual(decision["action"], "HOLD")

    def test_rotate_just_above_threshold(self) -> None:
        _, decision = self.apply([PASSING], with_net_benefit(DEFAULT_CONFIG.min_net_benefit_kwh_equivalent + 0.001))

        self.assertEqual(decision["action"], "ROTATE")

    def test_hold_when_optimizer_recommends_staying(self) -> None:
        stay = {**OPTIMIZATION, "recommended_angle_deg": 35.0, "predicted_kwh": 5.8, "energy_gain_kwh": 0.0, "movement_cost_kwh_equivalent": 0.0, "net_benefit_kwh_equivalent": 0.0}

        _, decision = self.apply([PASSING], stay)

        self.assertEqual((decision["action"], decision["target_angle_deg"]), ("HOLD", 35.0))

    def test_hold_when_optimization_is_unavailable(self) -> None:
        safety, decision = self.apply([PASSING], None)

        self.assertTrue(safety["passed"])
        self.assertEqual(decision["action"], "HOLD")

    def test_threshold_comes_from_config(self) -> None:
        cautious = dataclasses.replace(DEFAULT_CONFIG, config_id="test", min_net_benefit_kwh_equivalent=1.0)

        _, decision = TOOLS.apply_safety_rules([PASSING], OPTIMIZATION, current_angle_deg=35.0, config=cautious)

        self.assertEqual(decision["action"], "HOLD")

    def test_refuses_to_decide_without_checks(self) -> None:
        with self.assertRaises(ToolError):
            self.apply([])

    def test_control_command_is_simulation_only(self) -> None:
        safety, decision = self.apply([PASSING])

        receipt = TOOLS.send_control_command(decision, safety, control_target_id="row-001")

        self.assertEqual((receipt["accepted"], receipt["mode"]), (True, "SIMULATION"))
        with self.assertRaises(NotImplementedError):
            TOOLS.send_control_command(decision, safety, control_target_id="row-001", simulation_only=False)

    def test_control_command_rejects_rotate_without_passing_safety(self) -> None:
        _, decision = self.apply([PASSING])
        failed_safety = {"passed": False, "checks": [], "reason": "tampered"}

        receipt = TOOLS.send_control_command(decision, failed_safety, control_target_id="row-001")

        self.assertFalse(receipt["accepted"])


class ManagerAgentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.state = state_before("safety")
        self.agent = ManagerAgent(TOOLS, DEFAULT_CONFIG, row_status=ready_row, clock=fixed_clock)

    def merged(self, update: dict) -> dict:
        return {**self.state, "safety": update["safety"], "decision": update["decision"], "stage": "COMPLETE", "agent_log": update["agent_log"], "tool_calls": update["tool_calls"]}

    def test_implements_agent_contract(self) -> None:
        self.assertIsInstance(self.agent, ManagerAgentContract)

    def test_returns_only_its_own_sections_and_traces(self) -> None:
        self.assertEqual(set(self.agent.run(self.state)), {"safety", "decision", "agent_log", "tool_calls"})

    def test_rotates_on_the_mock_state_and_merges_into_valid_state(self) -> None:
        update = self.agent.run(self.state)

        self.assertEqual((update["decision"]["action"], update["decision"]["target_angle_deg"]), ("ROTATE", 45.0))
        self.assertEqual([check["name"] for check in update["safety"]["checks"]], ["wind_safety", "angle_limits", "data_freshness", "panel_status", "model_confidence"])
        validate_agent_state(self.merged(update))

    def test_coordinates_every_safety_tool_then_the_rules_then_simulated_dispatch(self) -> None:
        update = self.agent.run(self.state)

        self.assertEqual(
            [call["tool"] for call in update["tool_calls"]],
            ["check_wind_safety", "check_angle_limits", "check_data_freshness", "check_panel_status", "check_model_confidence", "apply_safety_rules", "send_control_command"],
        )
        self.assertIn("SIMULATION", update["agent_log"][-1]["result"])

    def test_stows_on_high_wind(self) -> None:
        self.state["weather"]["wind_gust_kmh"] = 95

        update = self.agent.run(self.state)

        self.assertEqual((update["decision"]["action"], update["decision"]["target_angle_deg"]), ("STOW", 0.0))
        self.assertFalse(update["safety"]["passed"])
        validate_agent_state(self.merged(update))

    def test_holds_on_stale_data(self) -> None:
        self.state["data"] = {**self.state["data"], "status": "STALE", "forecast_age_minutes": 120.0, "issues": ["Forecast is two hours old"]}

        update = self.agent.run(self.state)

        self.assertEqual((update["decision"]["action"], update["decision"]["target_angle_deg"]), ("HOLD", 35))
        validate_agent_state(self.merged(update))

    def test_holds_when_gain_does_not_clear_threshold(self) -> None:
        self.state["optimization"] = with_net_benefit(0.01)

        update = self.agent.run(self.state)

        self.assertTrue(update["safety"]["passed"])
        self.assertEqual(update["decision"]["action"], "HOLD")

    def test_holds_when_row_is_faulted(self) -> None:
        agent = ManagerAgent(TOOLS, DEFAULT_CONFIG, row_status=lambda _: {"angle_deg": 35.0, "current_state": "FAULT"}, clock=fixed_clock)

        self.assertEqual(agent.run(self.state)["decision"]["action"], "HOLD")

    def test_holds_when_upstream_stages_failed(self) -> None:
        self.state.update(modeling=None, optimization=None)

        update = self.agent.run(self.state)

        self.assertEqual(update["decision"]["action"], "HOLD")
        self.assertFalse(update["safety"]["passed"])
        validate_agent_state(self.merged(update))

    def test_holds_at_observed_row_angle_when_weather_is_missing(self) -> None:
        self.state.update(weather=None, data=None, modeling=None, optimization=None)

        update = self.agent.run(self.state)

        self.assertEqual((update["decision"]["action"], update["decision"]["target_angle_deg"]), ("HOLD", 35.0))
        validate_agent_state(self.merged(update))

    def test_unknown_current_angle_raises_instead_of_assuming_one(self) -> None:
        self.state.update(weather=None, data=None, modeling=None, optimization=None)
        agent = ManagerAgent(TOOLS, DEFAULT_CONFIG, clock=fixed_clock)

        with self.assertRaises(StageError) as raised:
            agent.run(self.state)

        self.assertEqual(raised.exception.code, "SAFETY_FAILED")

    def test_without_row_status_the_panel_check_is_reported_as_not_run(self) -> None:
        update = ManagerAgent(TOOLS, DEFAULT_CONFIG, clock=fixed_clock).run(self.state)

        self.assertNotIn("panel_status", [check["name"] for check in update["safety"]["checks"]])
        self.assertIn("Check not run", {entry["action"]: entry["result"] for entry in update["agent_log"]}["panel_status"])

    def test_does_not_mutate_state(self) -> None:
        before = copy.deepcopy(self.state)

        self.agent.run(self.state)

        self.assertEqual(self.state, before)

    def test_agent_without_tools_is_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError):
            ManagerAgent(None, DEFAULT_CONFIG).run(self.state)


if __name__ == "__main__":
    unittest.main()
