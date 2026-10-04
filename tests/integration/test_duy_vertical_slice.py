"""Example data -> trained model -> Duy's three agents -> validated FrontendData.

The orchestrator and Data Agent below are TEST-ONLY stand-ins for shared and
teammate code. They exist so Duy's stages can be proven end to end against the
mock contracts; they are not the team's orchestrator.
"""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from src.common.config import DEFAULT_CONFIG
from src.common.schema import ContractError, MODEL_NAMES, validate_frontend_data
from src.models.data_loader import EXAMPLE_DATASET_SOURCE, PIPELINE_DATASET_SOURCE, hourly_weather, load_dataset_split, load_weather_rows
from src.models.evaluation import ModelCandidate, chronological_split, to_features, unavailable_model_metrics
from src.service.recommendation_service import (
    DEFAULT_IMPLEMENTATIONS, build_agents, build_metadata, build_modeling_tools, get_recommendation, replay_test_window,
    run_decision_stages, save_recommendation,
)


MOCK = Path(__file__).resolve().parents[2] / "data" / "mock"
TARGET_ROW = "row-001"
CLOCK_TIME = "2026-08-20T12:00:00Z"
WEATHER_KEYS = ("temperature_c", "cloud_cover_pct", "precipitation_mm", "wind_speed_kmh", "wind_gust_kmh", "ghi_wm2", "dni_wm2", "dhi_wm2")


def clock() -> str:
    return CLOCK_TIME


class StubDataAgent:
    """Stands in for Luan's Data Agent: serves one held-out example row as the 'forecast'."""

    def __init__(self, weather: dict, **report_overrides: object) -> None:
        self.weather = weather
        self.report = {"status": "VALID", "source": "example_csv", "forecast_age_minutes": 5.0, "used_cache": False, "issues": [], **report_overrides}

    def run(self, state: dict) -> dict:
        return {"data": self.report, "weather": self.weather, "agent_log": [], "tool_calls": []}


class SliceOrchestrator:
    """Minimal state machine: Data -> Modeling -> Optimization -> Manager -> FrontendData."""

    def __init__(self, data, agents, farm_status: dict) -> None:
        self.data, self.agents, self.farm_status = data, agents, farm_status
        self.final_state: dict | None = None

    def run(self, state: dict) -> dict:
        update = self.data.run(state)
        state = {**state, "data": update["data"], "weather": update["weather"], "stage": "DATA"}
        self.final_state = run_decision_stages(state, self.agents)
        return self._frontend(self.final_state)

    def _frontend(self, state: dict) -> dict:
        modeling, weather, decision = state["modeling"], state["weather"], state["decision"]
        rows = [
            {**row, "angle_deg": weather["panel_angle_deg"], "action": decision["action"]} if row["row_id"] == TARGET_ROW else row
            for row in self.farm_status["rows"]
        ]
        return {
            "timestamp": state["timestamp"],
            "metadata": state["metadata"],
            "current_weather": {key: weather[key] for key in WEATHER_KEYS},
            "data_agent": state["data"],
            "model_comparison": modeling["model_comparison"] if modeling else [unavailable_model_metrics(model, implementation=DEFAULT_IMPLEMENTATIONS[model]) for model in MODEL_NAMES],
            "selected_model": modeling["selected_model"] if modeling else None,
            "candidate_predictions": modeling["candidate_predictions"] if modeling else [],
            "optimization": state["optimization"],
            "safety": state["safety"],
            "decision": decision,
            "farm_status": {**self.farm_status, "rows": rows},
            "agent_log": state["agent_log"],
            "history": [],
            "errors": state["errors"],
        }


class DuyVerticalSliceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = EXAMPLE_DATASET_SOURCE
        test_rows = chronological_split(load_weather_rows(cls.source.path)).test
        calm_day = [row for row in test_rows if row["sun_elevation_deg"] > 40 and row["wind_gust_kmh"] < 40 and row["cloud_cover_pct"] < 40]
        cls.sunny_row = max(calm_day, key=lambda row: row["dni_wm2"])
        cls.metadata = build_metadata(cls.source, interval_start=cls.sunny_row["timestamp"], control_target_id=TARGET_ROW, config=DEFAULT_CONFIG)
        cls.modeling_tools = build_modeling_tools(cls.source, metadata=cls.metadata)
        cls.farm_status = json.loads((MOCK / "sample_full_frontend_data.json").read_text(encoding="utf-8"))["farm_status"]

    def run_slice(self, *, panel_angle: float = 0.0, weather_overrides: dict | None = None, modeling_tools=None, row_state: str = "READY", **report_overrides):
        weather = {**to_features(self.sunny_row), "panel_angle_deg": panel_angle, **(weather_overrides or {})}
        agents = build_agents(
            modeling_tools or self.modeling_tools, DEFAULT_CONFIG,
            row_status=lambda _row_id: {"angle_deg": panel_angle, "current_state": row_state}, clock=clock,
        )
        orchestrator = SliceOrchestrator(StubDataAgent(weather, **report_overrides), agents, copy.deepcopy(self.farm_status))
        state = {
            "run_id": "slice-test", "timestamp": CLOCK_TIME, "metadata": self.metadata, "stage": "PENDING",
            "weather": None, "data": None, "modeling": None, "optimization": None, "safety": None, "decision": None,
            "agent_log": [], "tool_calls": [], "errors": [],
        }
        return get_recommendation(state, orchestrator), orchestrator.final_state

    def test_payload_is_labeled_mock_and_validates(self) -> None:
        payload, _ = self.run_slice()

        validate_frontend_data(payload)
        self.assertEqual((payload["metadata"]["dataset_kind"], payload["metadata"]["label_source"]), ("MOCK", "mock"))
        self.assertIn("SYNTHETIC EXAMPLE DATA", payload["metadata"]["assumptions"][0])

    def test_lowest_rmse_model_is_selected_and_undelivered_baselines_are_unavailable(self) -> None:
        payload, _ = self.run_slice()

        by_model = {entry["model"]: entry for entry in payload["model_comparison"]}
        statuses = {model: entry["status"] for model, entry in by_model.items()}
        self.assertEqual(statuses, {"linear_regression": "UNAVAILABLE", "random_forest": "UNAVAILABLE", "boosting": "MOCK", "lstm": "MOCK"})
        expected = "boosting" if by_model["boosting"]["rmse"] <= by_model["lstm"]["rmse"] else "lstm"
        self.assertEqual(payload["selected_model"], expected)

    def test_rotates_a_flat_panel_toward_the_sun_when_it_pays(self) -> None:
        payload, _ = self.run_slice(panel_angle=0.0)

        optimization, decision = payload["optimization"], payload["decision"]
        self.assertEqual(decision["action"], "ROTATE")
        self.assertEqual(decision["target_angle_deg"], optimization["recommended_angle_deg"])
        self.assertGreater(optimization["net_benefit_kwh_equivalent"], DEFAULT_CONFIG.min_net_benefit_kwh_equivalent)
        self.assertIn(0.0, [entry["angle_deg"] for entry in payload["candidate_predictions"]])

    def test_recommendation_maximizes_net_benefit_over_all_candidates(self) -> None:
        payload, _ = self.run_slice(panel_angle=0.0)

        optimization = payload["optimization"]
        rate = DEFAULT_CONFIG.motor_kwh_per_degree + DEFAULT_CONFIG.wear_kwh_equivalent_per_degree
        best_net = max(
            entry["predicted_kwh"] - optimization["baseline_kwh"] - abs(entry["angle_deg"] - optimization["current_angle_deg"]) * rate
            for entry in payload["candidate_predictions"]
        )
        self.assertAlmostEqual(optimization["net_benefit_kwh_equivalent"], best_net)

    def test_holds_at_night_because_no_move_pays_for_itself(self) -> None:
        night = {"ghi_wm2": 0.0, "dni_wm2": 0.0, "dhi_wm2": 0.0, "sun_elevation_deg": -20.0}

        payload, _ = self.run_slice(panel_angle=45.0, weather_overrides=night)

        self.assertEqual((payload["decision"]["action"], payload["decision"]["target_angle_deg"]), ("HOLD", 45.0))
        self.assertTrue(payload["safety"]["passed"])

    def test_stows_in_a_storm(self) -> None:
        payload, _ = self.run_slice(weather_overrides={"wind_speed_kmh": 62.0, "wind_gust_kmh": 95.0})

        self.assertEqual((payload["decision"]["action"], payload["decision"]["target_angle_deg"]), ("STOW", DEFAULT_CONFIG.stow_angle_deg))
        self.assertFalse(payload["safety"]["passed"])

    def test_holds_on_stale_data(self) -> None:
        payload, _ = self.run_slice(status="STALE", forecast_age_minutes=95.0, issues=["Forecast is 95 minutes old"])

        self.assertEqual((payload["decision"]["action"], payload["decision"]["target_angle_deg"]), ("HOLD", 0.0))

    def test_holds_when_row_is_faulted(self) -> None:
        payload, _ = self.run_slice(row_state="FAULT")

        self.assertEqual(payload["decision"]["action"], "HOLD")

    def test_model_failure_still_produces_a_safe_valid_payload(self) -> None:
        no_models = build_modeling_tools(self.source, metadata=self.metadata, extra_candidates=[_unavailable("boosting"), _unavailable("lstm")])

        payload, state = self.run_slice(modeling_tools=no_models)

        self.assertIsNone(payload["selected_model"])
        self.assertIsNone(payload["optimization"])
        self.assertEqual(payload["candidate_predictions"], [])
        self.assertEqual(payload["decision"]["action"], "HOLD")
        self.assertEqual([error["code"] for error in payload["errors"]], ["MODELING_FAILED"])
        self.assertEqual(state["stage"], "COMPLETE")

    def test_activity_log_shows_every_agents_reasoning_in_order(self) -> None:
        payload, state = self.run_slice()

        agents_in_order = list(dict.fromkeys(entry["agent"] for entry in payload["agent_log"]))
        self.assertEqual(agents_in_order, ["modeling", "optimization", "manager"])
        self.assertEqual({call["status"] for call in state["tool_calls"]}, {"OK"})

    def test_service_rejects_a_payload_that_breaks_the_frontend_contract(self) -> None:
        class DriftingOrchestrator:
            def run(self, state):
                payload, _ = outer.run_slice()
                return {**payload, "confidence": 0.99}

        outer = self
        with self.assertRaises(ContractError):
            get_recommendation({}, DriftingOrchestrator())

    def test_saved_json_round_trips_and_validates(self) -> None:
        payload, _ = self.run_slice()

        with tempfile.TemporaryDirectory() as directory:
            path = save_recommendation(payload, Path(directory) / "out" / "frontend_data.json")
            loaded = json.loads(path.read_text(encoding="utf-8"))

        validate_frontend_data(loaded)
        self.assertEqual(loaded, payload)


class SystemEvaluationReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = EXAMPLE_DATASET_SOURCE
        metadata = build_metadata(cls.source, interval_start=CLOCK_TIME, control_target_id=TARGET_ROW, config=DEFAULT_CONFIG)
        cls.result = replay_test_window(
            cls.source, build_modeling_tools(cls.source, metadata=metadata), DEFAULT_CONFIG,
            initial_angle_deg=35.0, control_target_id=TARGET_ROW,
        )
        cls.test_rows = chronological_split(load_weather_rows(cls.source.path)).test

    def test_every_test_hour_gets_exactly_one_decision(self) -> None:
        result = self.result

        self.assertEqual(result.hours, len(self.test_rows))
        self.assertEqual(result.rotate_count + result.hold_count + result.stow_count, result.hours)
        self.assertGreater(result.rotate_count, 0)
        self.assertGreater(result.hold_count, 0)

    def test_energy_is_labeled_as_model_predicted(self) -> None:
        self.assertRegex(self.result.energy_source, r"^model-predicted \((boosting|lstm)\)$")

    def test_totals_are_consistent(self) -> None:
        result = self.result

        self.assertAlmostEqual(result.energy_gain_kwh, result.optimized_kwh - result.baseline_kwh)
        self.assertAlmostEqual(result.net_benefit_kwh_equivalent, result.energy_gain_kwh - result.movement_cost_kwh_equivalent)
        self.assertGreater(result.movement_cost_kwh_equivalent, 0)

    def test_storm_hours_are_stowed_and_nothing_rotates_past_a_failed_check(self) -> None:
        storm_hours = sum(
            1 for row in self.test_rows
            if row["wind_speed_kmh"] > DEFAULT_CONFIG.max_wind_speed_kmh or row["wind_gust_kmh"] > DEFAULT_CONFIG.max_wind_gust_kmh
        )

        self.assertEqual(self.result.severe_safety_events, storm_hours)
        self.assertEqual(self.result.stow_count, storm_hours)
        self.assertEqual(self.result.unsafe_rotations, 0)

    def test_replay_has_no_failed_stages(self) -> None:
        self.assertEqual(self.result.error_hours, 0)

    def test_avoided_moves_never_exceed_hold_hours(self) -> None:
        self.assertLessEqual(self.result.unnecessary_moves_avoided, self.result.hold_count)


class PipelineDatasetTest(unittest.TestCase):
    """The same stages on Luan's dataset: real archived weather with physics-derived labels."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PIPELINE_DATASET_SOURCE
        cls.split = load_dataset_split(cls.source)
        cls.metadata = build_metadata(cls.source, interval_start=cls.split.test[0]["timestamp"], control_target_id=TARGET_ROW, config=DEFAULT_CONFIG)
        cls.tools = build_modeling_tools(cls.source, metadata=cls.metadata)
        cls.comparison = {entry["model"]: entry for entry in cls.tools.evaluate_models()}

    def test_outputs_are_labeled_live_and_physics_derived_never_mock(self) -> None:
        self.assertEqual((self.metadata["dataset_kind"], self.metadata["label_source"]), ("LIVE", "physics-derived"))
        self.assertIn("not measured production", self.metadata["assumptions"][0])
        self.assertEqual({self.comparison[model]["status"] for model in ("boosting", "lstm")}, {"VALIDATED"})

    def test_both_advanced_models_are_scored_on_the_delivered_validation_window(self) -> None:
        for model in ("boosting", "lstm"):
            self.assertGreater(self.comparison[model]["r2"], 0.9)
        self.assertEqual({self.comparison[model]["status"] for model in ("linear_regression", "random_forest")}, {"UNAVAILABLE"})

    def test_replay_makes_one_decision_per_test_hour_without_errors(self) -> None:
        result = replay_test_window(self.source, self.tools, DEFAULT_CONFIG, initial_angle_deg=35.0, control_target_id=TARGET_ROW)

        self.assertEqual(result.hours, len(hourly_weather(self.split.test)))
        self.assertEqual(result.rotate_count + result.hold_count + result.stow_count, result.hours)
        self.assertEqual((result.error_hours, result.unsafe_rotations), (0, 0))

    def test_a_real_hour_produces_a_payload_the_frontend_contract_accepts(self) -> None:
        midday = max(hourly_weather(self.split.test), key=lambda hour: hour["sun_elevation_deg"])
        weather = {**midday, "panel_angle_deg": 35.0}
        agents = build_agents(self.tools, DEFAULT_CONFIG, row_status=lambda _row_id: {"angle_deg": 35.0, "current_state": "READY"}, clock=clock)
        farm_status = json.loads((MOCK / "sample_full_frontend_data.json").read_text(encoding="utf-8"))["farm_status"]
        orchestrator = SliceOrchestrator(StubDataAgent(weather, source="pipeline_csv"), agents, farm_status)
        state = {
            "run_id": "pipeline-test", "timestamp": CLOCK_TIME, "metadata": self.metadata, "stage": "PENDING",
            "weather": None, "data": None, "modeling": None, "optimization": None, "safety": None, "decision": None,
            "agent_log": [], "tool_calls": [], "errors": [],
        }

        payload = get_recommendation(state, orchestrator)

        self.assertEqual(payload["errors"], [])
        self.assertIn(payload["decision"]["action"], ("ROTATE", "HOLD"))
        self.assertEqual({entry["status"] for entry in payload["model_comparison"]}, {"VALIDATED", "UNAVAILABLE"})


def _unavailable(model: str) -> ModelCandidate:
    return ModelCandidate(model, DEFAULT_IMPLEMENTATIONS[model], unavailable_reason="disabled for this test")


if __name__ == "__main__":
    unittest.main()
