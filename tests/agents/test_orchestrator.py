"""Orchestrator: runs the four stages in order, merges their sections, and never bypasses safety."""

import copy
import json
import unittest

from src.agents.manager_agent import DeterministicSafetyTools, ManagerAgent
from src.agents.modeling_agent import ModelingAgent
from src.agents.optimization_agent import OptimizationAgent
from src.agents.orchestrator import Orchestrator
from src.agents.trace import StageError
from src.common.agent_contracts import OrchestratorContract
from src.common.config import DEFAULT_CONFIG
from src.common.schema import validate_agent_state, validate_frontend_data
from src.common.tool_contracts import ToolError
from src.models.optimizer import DeterministicOptimizationTools
from tests.agents.support import MOCK, fixed_clock, mock_state
from tests.agents.test_modeling_agent import FailingPredictor, LinearInAnglePredictor, build_tools


FARM = json.loads((MOCK / "sample_full_frontend_data.json").read_text(encoding="utf-8"))["farm_status"]
TARGET_ROW = "row-001"


class RecordedDataAgent:
    """Stands in for the Data Agent: returns the mock run's weather and report."""

    def __init__(self) -> None:
        completed = mock_state()
        self.update = {"data": completed["data"], "weather": completed["weather"], "agent_log": [{"timestamp": fixed_clock(), "agent": "data", "action": "weather_received", "result": "fixture weather"}], "tool_calls": []}

    def run(self, state):
        return copy.deepcopy(self.update)


class UnimplementedDataAgent:
    def run(self, state):
        raise NotImplementedError("Data Agent implementation awaits approval")


class BrokenDataAgent:
    def run(self, state):
        raise ToolError("weather provider timed out")


class BrokenManager:
    def run(self, state):
        raise StageError("manager", "SAFETY_FAILED", "no decision", {"agent_log": [], "tool_calls": []})


class EchoReasoner:
    def explain(self, agent: str, facts: str) -> str:
        return f"The {agent} agent reviewed its tool results."


def pending_state():
    return mock_state(stage="PENDING", weather=None, data=None, modeling=None, optimization=None, safety=None, decision=None, agent_log=[], tool_calls=[], errors=[])


def farm_source():
    return copy.deepcopy(FARM)


def row_status(row_id: str) -> dict:
    row = next(row for row in FARM["rows"] if row["row_id"] == row_id)
    return {"angle_deg": row["angle_deg"], "current_state": row["current_state"]}


def build_orchestrator(*, data=None, predictor=None, manager=None, reasoner=None, farm_status=farm_source) -> Orchestrator:
    state = pending_state()
    tools = build_tools(state, boosting=predictor or LinearInAnglePredictor(45.0))
    return Orchestrator(
        data or RecordedDataAgent(),
        ModelingAgent(tools, DEFAULT_CONFIG, clock=fixed_clock, reasoner=reasoner),
        OptimizationAgent(DeterministicOptimizationTools(), DEFAULT_CONFIG, clock=fixed_clock, reasoner=reasoner),
        manager or ManagerAgent(DeterministicSafetyTools(), DEFAULT_CONFIG, row_status=row_status, clock=fixed_clock, reasoner=reasoner),
        farm_status=farm_status,
    )


class OrchestratorTest(unittest.TestCase):
    def test_implements_the_shared_contract(self) -> None:
        self.assertIsInstance(build_orchestrator(), OrchestratorContract)

    def test_full_run_returns_a_valid_frontend_payload(self) -> None:
        orchestrator = build_orchestrator()

        payload = orchestrator.run(pending_state())

        validate_frontend_data(payload)
        validate_agent_state(orchestrator.final_state)
        self.assertEqual(orchestrator.final_state["stage"], "COMPLETE")
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["selected_model"], "boosting")

    def test_stages_run_in_order(self) -> None:
        payload = build_orchestrator().run(pending_state())

        order = list(dict.fromkeys(entry["agent"] for entry in payload["agent_log"]))
        self.assertEqual(order, ["data", "modeling", "optimization", "manager"])

    def test_rotate_decision_is_shown_on_the_control_row_only(self) -> None:
        payload = build_orchestrator().run(pending_state())

        rows = {row["row_id"]: row for row in payload["farm_status"]["rows"]}
        self.assertEqual(payload["decision"]["action"], "ROTATE")
        self.assertEqual(rows[TARGET_ROW]["action"], "ROTATE")
        self.assertEqual(rows[TARGET_ROW]["angle_deg"], 35.0)
        others = [row for row in FARM["rows"] if row["row_id"] != TARGET_ROW]
        self.assertEqual([rows[row["row_id"]] for row in others], others)

    def test_input_state_and_farm_snapshot_are_not_modified(self) -> None:
        state, before = pending_state(), pending_state()

        build_orchestrator().run(state)

        self.assertEqual(state, before)
        self.assertEqual(next(row for row in FARM["rows"] if row["row_id"] == TARGET_ROW)["action"], "ROTATE")

    def test_unimplemented_data_agent_is_recorded_and_the_manager_holds(self) -> None:
        payload = build_orchestrator(data=UnimplementedDataAgent()).run(pending_state())

        validate_frontend_data(payload)
        self.assertEqual(payload["decision"]["action"], "HOLD")
        self.assertEqual(payload["errors"][0]["code"], "DATA_UNAVAILABLE")
        self.assertEqual((payload["data_agent"]["status"], payload["data_agent"]["forecast_age_minutes"]), ("INVALID", None))
        self.assertIsNone(payload["current_weather"])
        self.assertIsNone(payload["selected_model"])
        self.assertEqual(payload["candidate_predictions"], [])
        self.assertIsNone(payload["optimization"])

    def test_data_tool_failure_is_recorded_and_the_manager_holds(self) -> None:
        payload = build_orchestrator(data=BrokenDataAgent()).run(pending_state())

        self.assertEqual(payload["decision"]["action"], "HOLD")
        self.assertIn("weather provider timed out", payload["errors"][0]["message"])

    def test_model_failure_is_recorded_and_safety_still_decides(self) -> None:
        payload = build_orchestrator(predictor=FailingPredictor()).run(pending_state())

        validate_frontend_data(payload)
        self.assertEqual(payload["decision"]["action"], "HOLD")
        self.assertEqual([error["agent"] for error in payload["errors"]], ["modeling"])
        self.assertIsNone(payload["selected_model"])
        self.assertTrue(all(entry["status"] == "UNAVAILABLE" and entry["rmse"] is None for entry in payload["model_comparison"]))

    def test_manager_failure_propagates_instead_of_inventing_a_decision(self) -> None:
        with self.assertRaises(StageError):
            build_orchestrator(manager=BrokenManager()).run(pending_state())

    def test_without_a_farm_source_the_run_is_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError):
            build_orchestrator(farm_status=None).run(pending_state())

    def test_llm_reasoning_appears_for_each_deciding_agent_without_changing_the_decision(self) -> None:
        plain = build_orchestrator().run(pending_state())

        explained = build_orchestrator(reasoner=EchoReasoner()).run(pending_state())

        reasoning = [entry["agent"] for entry in explained["agent_log"] if entry["action"] == "llm_reasoning"]
        self.assertEqual(reasoning, ["modeling", "optimization", "manager"])
        self.assertEqual((explained["decision"], explained["optimization"], explained["safety"]), (plain["decision"], plain["optimization"], plain["safety"]))


if __name__ == "__main__":
    unittest.main()
