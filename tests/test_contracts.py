"""Boundary and cross-fixture checks; these are not trained-model tests."""

import copy
import csv
import inspect
import json
from pathlib import Path
import unittest

from src.agents.data_agent import DataAgent
from src.agents.manager_agent import ManagerAgent
from src.agents.modeling_agent import ModelingAgent
from src.agents.optimization_agent import OptimizationAgent
from src.agents.orchestrator import Orchestrator
from src.common.agent_contracts import (
    DataAgentContract, ManagerAgentContract, ModelingAgentContract,
    OptimizationAgentContract, OrchestratorContract,
)
from src.common.config import DEFAULT_CONFIG
from src.common.schema import (
    ContractError, FEATURE_COLUMNS, MODEL_NAMES, WEATHER_COLUMNS,
    validate_agent_state, validate_frontend_data, validate_model_output,
    validate_weather_row,
)
from src.common.tool_contracts import EnergyPredictor


MOCK = Path(__file__).resolve().parents[1] / "data" / "mock"


def read_json(name: str) -> dict:
    return json.loads((MOCK / name).read_text(encoding="utf-8"))


def safe_unavailable_payload() -> dict:
    """A missing-data fixture variant, not a running safety controller."""
    value = read_json("sample_full_frontend_data.json")
    value["current_weather"] = None
    value["data_agent"].update(status="INVALID", source="unavailable", forecast_age_minutes=None, issues=["Weather missing"])
    value["selected_model"] = None
    value["candidate_predictions"] = []
    value["optimization"] = None
    for entry in value["model_comparison"]:
        entry.update(status="UNAVAILABLE", mae=None, rmse=None, r2=None)
    value["safety"] = {"passed": False, "checks": [{"name": "data_freshness", "passed": False, "severity": "BLOCK_ROTATE", "reason": "Weather missing"}], "reason": "Weather missing"}
    value["decision"] = {"action": "HOLD", "target_angle_deg": 35.0, "reason": "Weather unavailable"}
    value["farm_status"]["rows"][0]["action"] = "HOLD"
    value["errors"] = [{"agent": "data", "code": "WEATHER_UNAVAILABLE", "message": "No usable observation or cache"}]
    return value


class WeatherContractTests(unittest.TestCase):
    def setUp(self) -> None:
        with (MOCK / "sample_weather.csv").open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            self.assertEqual(tuple(reader.fieldnames), WEATHER_COLUMNS)
            self.rows = [{k: v if k == "timestamp" else float(v) for k, v in row.items()} for row in reader]

    def test_mock_csv_has_valid_chronological_rows(self):
        self.assertGreaterEqual(len(self.rows), 4)
        for row in self.rows:
            validate_weather_row(row)
        times = [row["timestamp"] for row in self.rows]
        self.assertEqual(times, sorted(set(times)))

    def test_label_excluded_from_features(self):
        self.assertNotIn("actual_kwh", FEATURE_COLUMNS)
        self.assertIn("panel_angle_deg", FEATURE_COLUMNS)

    def test_csv_weather_matches_shared_state_and_frontend(self):
        features = {k: v for k, v in self.rows[-1].items() if k != "actual_kwh"}
        state = read_json("agent_state.json")
        frontend = read_json("sample_full_frontend_data.json")
        self.assertEqual(features, state["weather"])
        for key, value in frontend["current_weather"].items():
            self.assertEqual(value, features[key])

    def test_missing_extra_and_wrong_types_rejected(self):
        for change in (lambda r: r.pop("ghi_wm2"), lambda r: r.update(extra=1), lambda r: r.update(ghi_wm2="850"), lambda r: r.update(ghi_wm2=True)):
            row = copy.deepcopy(self.rows[-1])
            change(row)
            with self.assertRaises(ContractError):
                validate_weather_row(row)

    def test_invalid_numbers_and_ranges_rejected(self):
        for key, val in (("ghi_wm2", float("nan")), ("temperature_c", float("inf")), ("cloud_cover_pct", 101), ("actual_kwh", -1), ("sun_azimuth_deg", 360), ("panel_angle_deg", -5), ("wind_gust_kmh", 1)):
            with self.subTest(key=key, value=val), self.assertRaises(ContractError):
                validate_weather_row(dict(self.rows[-1], **{key: val}))

    def test_timezone_required(self):
        row = dict(self.rows[-1], timestamp="2026-06-21T19:00:00")
        with self.assertRaises(ContractError):
            validate_weather_row(row)


class PayloadContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frontend = read_json("sample_full_frontend_data.json")
        self.model = read_json("sample_model_output.json")
        self.state = read_json("agent_state.json")

    def test_all_json_fixtures_validate(self):
        validate_frontend_data(self.frontend)
        validate_model_output(self.model)
        validate_agent_state(self.state)

    def test_fixture_sections_agree_across_owner_boundaries(self):
        self.assertEqual(self.model["metadata"], self.frontend["metadata"])
        self.assertEqual(self.state["metadata"], self.frontend["metadata"])
        self.assertEqual(self.state["modeling"], self.model["modeling"])
        for key in ("candidate_predictions", "model_comparison", "selected_model"):
            self.assertEqual(self.model["modeling"][key], self.frontend[key])
        for key in ("optimization", "safety", "decision", "agent_log"):
            self.assertEqual(self.state[key], self.frontend[key])
        self.assertEqual(self.state["data"], self.frontend["data_agent"])

    def test_unknown_schema_and_unmarked_mock_rejected(self):
        for key, value in (("schema_version", "999"), ("label_source", "measured"), ("energy_scope", "farm"), ("prediction_horizon_minutes", 15)):
            payload = copy.deepcopy(self.frontend)
            payload["metadata"][key] = value
            with self.subTest(key=key), self.assertRaises(ContractError):
                validate_frontend_data(payload)

    def test_metrics_must_match_synthetic_vectors(self):
        self.model["evaluation_fixture"]["boosting"][0] += 1
        with self.assertRaises(ContractError):
            validate_model_output(self.model)

    def test_all_four_models_required_and_unavailable_cannot_be_selected(self):
        self.frontend["model_comparison"].pop()
        with self.assertRaises(ContractError):
            validate_frontend_data(self.frontend)
        payload = safe_unavailable_payload()
        payload["selected_model"] = "boosting"
        with self.assertRaises(ContractError):
            validate_frontend_data(payload)

    def test_model_ids_unique(self):
        self.frontend["model_comparison"][0]["model"] = "boosting"
        with self.assertRaises(ContractError):
            validate_frontend_data(self.frontend)

    def test_mock_metrics_cannot_claim_live_evaluation(self):
        self.frontend["metadata"].update(dataset_kind="LIVE", label_source="measured")
        with self.assertRaises(ContractError):
            validate_frontend_data(self.frontend)

    def test_net_benefit_and_baseline_must_agree(self):
        for mutate in (
            lambda p: p["optimization"].update(net_benefit_kwh_equivalent=999),
            lambda p: p["candidate_predictions"][1].update(predicted_kwh=999),
            lambda p: p["candidate_predictions"].append(p["candidate_predictions"][0]),
        ):
            payload = copy.deepcopy(self.frontend)
            mutate(payload)
            with self.assertRaises(ContractError):
                validate_frontend_data(payload)

    def test_fixture_illustrates_net_benefit_not_raw_energy(self):
        """Fixture arithmetic only; optimizer behavior is still unimplemented."""
        opt = self.frontend["optimization"]
        candidates = self.frontend["candidate_predictions"]
        coefficient = DEFAULT_CONFIG.motor_kwh_per_degree + DEFAULT_CONFIG.wear_kwh_equivalent_per_degree
        by_net = max(candidates, key=lambda c: c["predicted_kwh"] - opt["baseline_kwh"] - abs(c["angle_deg"] - opt["current_angle_deg"]) * coefficient)
        by_energy = max(candidates, key=lambda c: c["predicted_kwh"])
        self.assertEqual(opt["recommended_angle_deg"], by_net["angle_deg"])
        self.assertNotEqual(by_net["angle_deg"], by_energy["angle_deg"])

    def test_missing_data_can_be_displayed_without_fake_predictions(self):
        validate_frontend_data(safe_unavailable_payload())

    def test_stale_data_cannot_authorize_rotation(self):
        for updates in ({"status": "STALE", "issues": ["Stale forecast"]}, {"forecast_age_minutes": 60}):
            payload = copy.deepcopy(self.frontend)
            payload["data_agent"].update(updates)
            with self.assertRaises(ContractError):
                validate_frontend_data(payload)

    def test_cache_fallback_is_representable(self):
        """Contract representation only, not retry/cache implementation."""
        self.frontend["data_agent"].update(status="DEGRADED", source="mock_cache", used_cache=True, issues=["Provider unavailable; fresh cache used"])
        validate_frontend_data(self.frontend)

    def test_unknown_action_rejected(self):
        self.frontend["decision"]["action"] = "MOVE"
        with self.assertRaises(ContractError):
            validate_frontend_data(self.frontend)

    def test_severe_failure_requires_stow_even_when_economically_positive(self):
        self.frontend["safety"]["passed"] = False
        self.frontend["safety"]["checks"][0].update(passed=False, reason="MOCK severe gust")
        with self.assertRaises(ContractError):
            validate_frontend_data(self.frontend)
        self.frontend["decision"].update(action="STOW", target_angle_deg=0)
        self.frontend["farm_status"]["rows"][0]["action"] = "STOW"
        validate_frontend_data(self.frontend)

    def test_hold_preserves_angle(self):
        payload = safe_unavailable_payload()
        payload["decision"]["target_angle_deg"] = 45
        with self.assertRaises(ContractError):
            validate_frontend_data(payload)

    def test_low_gain_rotation_rejected_but_hold_supported(self):
        opt = self.frontend["optimization"]
        opt["movement_cost_kwh_equivalent"] = opt["energy_gain_kwh"] - 0.01
        opt["net_benefit_kwh_equivalent"] = 0.01
        with self.assertRaises(ContractError):
            validate_frontend_data(self.frontend)
        self.frontend["decision"].update(action="HOLD", target_angle_deg=35)
        self.frontend["farm_status"]["rows"][0]["action"] = "HOLD"
        validate_frontend_data(self.frontend)

    def test_farm_inventory_and_membership(self):
        farm = self.frontend["farm_status"]
        self.assertEqual(len(farm["rows"]), 50)
        self.assertEqual([z["panel_count"] for z in farm["zones"]], [260, 240, 260, 240])
        farm["zones"][1]["row_ids"][0] = "row-001"
        with self.assertRaises(ContractError):
            validate_frontend_data(self.frontend)

    def test_pending_state_has_null_stages(self):
        self.state["stage"] = "PENDING"
        for key in ("weather", "data", "modeling", "optimization", "safety", "decision"):
            self.state[key] = None
        self.state["agent_log"] = []
        self.state["tool_calls"] = []
        validate_agent_state(self.state)

    def test_shared_state_cannot_rotate_on_stale_data(self):
        self.state["data"].update(status="STALE", issues=["Stale forecast"])
        with self.assertRaises(ContractError):
            validate_agent_state(self.state)

    def test_complete_and_failed_state_require_evidence(self):
        self.state["decision"] = None
        with self.assertRaises(ContractError):
            validate_agent_state(self.state)
        self.state["stage"] = "FAILED"
        with self.assertRaises(ContractError):
            validate_agent_state(self.state)


class InterfaceTests(unittest.TestCase):
    def test_mock_predictor_can_implement_shared_interface(self):
        class FixturePredictor:
            def predict_kwh(self, weather, candidate_angles_deg, *, metadata):
                fixture = read_json("sample_model_output.json")
                by_angle = {p["angle_deg"]: p for p in fixture["modeling"]["candidate_predictions"]}
                return [copy.deepcopy(by_angle[a]) for a in candidate_angles_deg]

        predictor = FixturePredictor()
        self.assertIsInstance(predictor, EnergyPredictor)
        state = read_json("agent_state.json")
        self.assertNotIn("actual_kwh", state["weather"])
        result = predictor.predict_kwh(state["weather"], (35, 45), metadata=state["metadata"])
        self.assertEqual([p["angle_deg"] for p in result], [35, 45])
        self.assertEqual(list(inspect.signature(FixturePredictor.predict_kwh).parameters), list(inspect.signature(EnergyPredictor.predict_kwh).parameters))

    def test_agents_are_explicit_stubs_and_do_not_mutate_state(self):
        state = read_json("agent_state.json")
        before = copy.deepcopy(state)
        agents = (
            (DataAgent(None, None, DEFAULT_CONFIG), DataAgentContract),
            (ModelingAgent(None, DEFAULT_CONFIG), ModelingAgentContract),
            (OptimizationAgent(None, DEFAULT_CONFIG), OptimizationAgentContract),
            (ManagerAgent(None, DEFAULT_CONFIG), ManagerAgentContract),
            (Orchestrator(None, None, None, None), OrchestratorContract),
        )
        for agent, interface in agents:
            with self.subTest(agent=type(agent).__name__):
                self.assertIsInstance(agent, interface)
                with self.assertRaises(NotImplementedError):
                    agent.run(state)
        self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main()
