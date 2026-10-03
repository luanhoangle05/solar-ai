"""Modeling Agent: compare, select by rule, predict every candidate angle."""

import copy
import unittest

from src.agents.modeling_agent import ModelingAgent
from src.agents.trace import StageError
from src.common.agent_contracts import ModelingAgentContract
from src.common.config import DEFAULT_CONFIG
from src.common.schema import MODEL_NAMES, validate_agent_state
from src.common.tool_contracts import ModelingTools, ToolError
from src.models.evaluation import EvaluatedModelingTools, ModelCandidate, to_features
from src.models.data_loader import load_weather_rows
from tests.agents.support import MOCK, fixed_clock, state_before


class LinearInAnglePredictor:
    """Deterministic stand-in adapter: energy = scale * (10 - |angle - best| / 10)."""

    def __init__(self, best_angle: float, scale: float = 0.5) -> None:
        self.best_angle, self.scale = best_angle, scale

    def predict_kwh(self, weather, candidate_angles_deg, *, metadata):
        return [{"angle_deg": angle, "predicted_kwh": self.scale * (10 - abs(angle - self.best_angle) / 10)} for angle in candidate_angles_deg]


class FailingPredictor:
    def predict_kwh(self, weather, candidate_angles_deg, *, metadata):
        raise ToolError("adapter offline")


class ShortPredictor:
    def predict_kwh(self, weather, candidate_angles_deg, *, metadata):
        return [{"angle_deg": candidate_angles_deg[0], "predicted_kwh": 1.0}]


def build_tools(state, **predictors) -> EvaluatedModelingTools:
    """Tools with the given adapters; every other contract model is unavailable."""
    candidates = [
        ModelCandidate(model, implementation=f"test-{model}", predictor=predictors.get(model), unavailable_reason="not supplied in this test")
        for model in MODEL_NAMES
    ]
    return EvaluatedModelingTools(candidates, load_weather_rows(MOCK / "sample_weather.csv"), metadata=state["metadata"])


class ModelingAgentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.state = state_before("modeling")
        self.tools = build_tools(self.state, boosting=LinearInAnglePredictor(35.0), lstm=LinearInAnglePredictor(35.0, scale=0.3))
        self.agent = ModelingAgent(self.tools, DEFAULT_CONFIG, clock=fixed_clock)

    def test_implements_contracts(self) -> None:
        self.assertIsInstance(self.agent, ModelingAgentContract)
        self.assertIsInstance(self.tools, ModelingTools)

    def test_returns_only_its_own_section_and_traces(self) -> None:
        self.assertEqual(set(self.agent.run(self.state)), {"modeling", "agent_log", "tool_calls"})

    def test_compares_four_models_and_marks_missing_ones_unavailable(self) -> None:
        comparison = self.agent.run(self.state)["modeling"]["model_comparison"]

        self.assertEqual([entry["model"] for entry in comparison], list(MODEL_NAMES))
        statuses = {entry["model"]: entry["status"] for entry in comparison}
        self.assertEqual(statuses, {"linear_regression": "UNAVAILABLE", "random_forest": "UNAVAILABLE", "boosting": "MOCK", "lstm": "MOCK"})
        for entry in comparison:
            if entry["status"] == "UNAVAILABLE":
                self.assertEqual((entry["mae"], entry["rmse"], entry["r2"]), (None, None, None))

    def test_selects_lowest_validation_rmse_and_reports_its_metrics(self) -> None:
        modeling = self.agent.run(self.state)["modeling"]

        available = [entry for entry in modeling["model_comparison"] if entry["status"] != "UNAVAILABLE"]
        best = min(available, key=lambda entry: entry["rmse"])
        self.assertEqual(modeling["selected_model"], best["model"])
        self.assertEqual((modeling["mae"], modeling["rmse"], modeling["r2"]), (best["mae"], best["rmse"], best["r2"]))

    def test_predicts_every_candidate_angle_including_stay(self) -> None:
        self.state["weather"]["panel_angle_deg"] = 37.5

        predictions = self.agent.run(self.state)["modeling"]["candidate_predictions"]

        self.assertEqual([entry["angle_deg"] for entry in predictions], [30, 35, 37.5, 40, 45, 50, 55, 60])

    def test_predictions_come_from_the_selected_models_adapter(self) -> None:
        modeling = self.agent.run(self.state)["modeling"]

        predictor = self.tools.get_predictor(modeling["selected_model"])
        angles = tuple(entry["angle_deg"] for entry in modeling["candidate_predictions"])
        self.assertEqual(modeling["candidate_predictions"], predictor.predict_kwh(to_features(self.state["weather"]), angles, metadata=self.state["metadata"]))

    def test_records_tool_calls_in_coordination_order(self) -> None:
        update = self.agent.run(self.state)

        self.assertEqual([call["tool"] for call in update["tool_calls"]], ["evaluate_models", "select_best_model", "get_predictor", "predict_kwh"])
        self.assertEqual({call["status"] for call in update["tool_calls"]}, {"OK"})

    def test_log_states_the_selection_rule(self) -> None:
        log = {entry["action"]: entry["result"] for entry in self.agent.run(self.state)["agent_log"]}

        self.assertIn("lowest validation RMSE", log["selection"])
        self.assertIn("UNAVAILABLE", log["comparison"])
        self.assertIn("stay angle 35 deg", log["prediction"])

    def test_update_merges_into_a_valid_shared_state(self) -> None:
        update = self.agent.run(self.state)

        validate_agent_state({**self.state, "modeling": update["modeling"], "agent_log": update["agent_log"], "tool_calls": update["tool_calls"]})

    def test_does_not_mutate_state(self) -> None:
        before = copy.deepcopy(self.state)

        self.agent.run(self.state)

        self.assertEqual(self.state, before)

    def test_model_that_fails_evaluation_is_unavailable_not_fatal(self) -> None:
        tools = build_tools(self.state, boosting=LinearInAnglePredictor(35.0), random_forest=FailingPredictor())

        modeling = ModelingAgent(tools, DEFAULT_CONFIG, clock=fixed_clock).run(self.state)["modeling"]

        self.assertEqual(modeling["selected_model"], "boosting")
        self.assertIn("adapter offline", tools.unavailable_reasons()["random_forest"])

    def test_no_available_model_raises_stage_error(self) -> None:
        agent = ModelingAgent(build_tools(self.state), DEFAULT_CONFIG, clock=fixed_clock)

        with self.assertRaises(StageError) as raised:
            agent.run(self.state)

        self.assertEqual(raised.exception.code, "MODELING_FAILED")
        self.assertEqual(raised.exception.trace["tool_calls"][-1]["status"], "ERROR")

    def test_missing_weather_raises_stage_error(self) -> None:
        self.state["weather"] = None

        with self.assertRaises(StageError) as raised:
            self.agent.run(self.state)

        self.assertEqual(raised.exception.code, "MODELING_INPUT_UNAVAILABLE")

    def test_incomplete_predictions_are_rejected(self) -> None:
        agent = ModelingAgent(build_tools(self.state, boosting=ShortPredictor()), DEFAULT_CONFIG, clock=fixed_clock)

        with self.assertRaisesRegex(StageError, "one prediction per requested angle"):
            agent.run(self.state)

    def test_agent_without_tools_is_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError):
            ModelingAgent(None, DEFAULT_CONFIG).run(self.state)


if __name__ == "__main__":
    unittest.main()
