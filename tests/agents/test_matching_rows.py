"""Showing the control row's decision on every row in the same state and at the same angle."""

import copy
import json
import unittest

from src.agents.modeling_agent import _describe_comparison
from src.common.config import DEFAULT_CONFIG
from src.models.data_loader import EXAMPLE_DATASET_SOURCE
from src.common.schema import validate_frontend_data
from src.service.recommendation_service import ZONE_RUNS_ASSUMPTION, mark_matching_rows, recommend_for_zones, simulated_zone_farm
from tests.agents.support import MOCK, fixed_clock, mock_state
from tests.agents.test_modeling_agent import LinearInAnglePredictor, build_tools


PAYLOAD = json.loads((MOCK / "sample_full_frontend_data.json").read_text(encoding="utf-8"))
TARGET_ROW = PAYLOAD["metadata"]["control_target_id"]


def actions(payload: dict) -> dict:
    return {row["row_id"]: row["action"] for row in payload["farm_status"]["rows"]}


class MatchingRowsTest(unittest.TestCase):
    def test_ready_rows_at_the_control_rows_angle_show_its_decision(self) -> None:
        marked = mark_matching_rows(PAYLOAD)

        validate_frontend_data(marked)
        matching = [row for row in marked["farm_status"]["rows"] if row["current_state"] == "READY" and row["angle_deg"] == 35.0]
        self.assertEqual(len(matching), 48)
        self.assertEqual({row["action"] for row in matching}, {"ROTATE"})

    def test_rows_in_another_state_are_left_alone(self) -> None:
        marked = mark_matching_rows(PAYLOAD)

        stowed = [row for row in marked["farm_status"]["rows"] if row["current_state"] == "STOWED"]
        self.assertEqual([row["action"] for row in stowed], ["STOW", "STOW"])

    def test_rows_at_another_angle_are_left_alone(self) -> None:
        payload = copy.deepcopy(PAYLOAD)
        other = next(row for row in payload["farm_status"]["rows"] if row["row_id"] != TARGET_ROW and row["current_state"] == "READY")
        other["angle_deg"] = 50.0

        marked = mark_matching_rows(payload)

        self.assertEqual(actions(marked)[other["row_id"]], "HOLD")

    def test_no_row_angle_is_changed(self) -> None:
        marked = mark_matching_rows(PAYLOAD)

        self.assertEqual([row["angle_deg"] for row in marked["farm_status"]["rows"]], [row["angle_deg"] for row in PAYLOAD["farm_status"]["rows"]])

    def test_input_payload_is_not_modified(self) -> None:
        before = copy.deepcopy(PAYLOAD)

        mark_matching_rows(PAYLOAD)

        self.assertEqual(PAYLOAD, before)

    def test_hold_decision_keeps_matching_rows_on_hold(self) -> None:
        payload = copy.deepcopy(PAYLOAD)
        payload["decision"] = {"action": "HOLD", "target_angle_deg": 35.0, "reason": "below threshold"}
        next(row for row in payload["farm_status"]["rows"] if row["row_id"] == TARGET_ROW)["action"] = "HOLD"

        marked = mark_matching_rows(payload)

        self.assertEqual({row["action"] for row in marked["farm_status"]["rows"] if row["current_state"] == "READY"}, {"HOLD"})


class ZoneRunsTest(unittest.TestCase):
    """The stand-in model peaks at 45 degrees, so a zone already there holds and the others rotate to it."""

    @classmethod
    def setUpClass(cls) -> None:
        state = mock_state()
        tools = build_tools(state, boosting=LinearInAnglePredictor(45.0))
        cls.payloads = recommend_for_zones(
            EXAMPLE_DATASET_SOURCE, state["weather"], tools, DEFAULT_CONFIG,
            zone_angles=[60.0, 45.0, 35.0, 30.0], run_id="zones-test", clock=fixed_clock,
        )

    def test_one_valid_payload_per_zone_with_that_zones_first_row_as_control(self) -> None:
        for payload in self.payloads:
            validate_frontend_data(payload)
        self.assertEqual([payload["metadata"]["control_target_id"] for payload in self.payloads], ["row-001", "row-014", "row-026", "row-039"])

    def test_each_zone_is_decided_from_its_own_starting_angle(self) -> None:
        decisions = [(payload["optimization"]["current_angle_deg"], payload["decision"]["action"], payload["decision"]["target_angle_deg"]) for payload in self.payloads]

        self.assertEqual(decisions, [(60.0, "ROTATE", 45.0), (45.0, "HOLD", 45.0), (35.0, "ROTATE", 45.0), (30.0, "ROTATE", 45.0)])

    def test_every_payload_carries_the_same_farm_with_each_zones_action(self) -> None:
        farms = [payload["farm_status"] for payload in self.payloads]
        by_zone = {zone["zone_id"]: {row["action"] for row in farms[0]["rows"] if row["zone_id"] == zone["zone_id"]} for zone in farms[0]["zones"]}

        self.assertTrue(all(farm == farms[0] for farm in farms))
        self.assertEqual(by_zone, {"zone-01": {"ROTATE"}, "zone-02": {"HOLD"}, "zone-03": {"ROTATE"}, "zone-04": {"ROTATE"}})

    def test_rows_keep_their_zones_starting_angle(self) -> None:
        angles = {row["zone_id"]: row["angle_deg"] for row in self.payloads[0]["farm_status"]["rows"]}

        self.assertEqual(angles, {"zone-01": 60.0, "zone-02": 45.0, "zone-03": 35.0, "zone-04": 30.0})

    def test_payloads_say_they_are_zone_runs(self) -> None:
        self.assertTrue(all(ZONE_RUNS_ASSUMPTION in payload["metadata"]["assumptions"] for payload in self.payloads))

    def test_a_zone_angle_is_required_for_every_zone(self) -> None:
        with self.assertRaises(ValueError):
            simulated_zone_farm([60.0, 45.0])


class ComparisonWordingTest(unittest.TestCase):
    def test_a_near_perfect_r2_is_not_rounded_up_to_one(self) -> None:
        text = _describe_comparison([{"model": "lstm", "implementation": "pytorch", "status": "VALIDATED", "mae": 0.0048429, "rmse": 0.0092647, "r2": 0.9999849834550535}])

        self.assertIn("R2 0.999985", text)
        self.assertNotIn("R2 1,", text + ",")


if __name__ == "__main__":
    unittest.main()
