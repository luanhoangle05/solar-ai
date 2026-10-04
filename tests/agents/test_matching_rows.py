"""Showing the control row's decision on every row in the same state and at the same angle."""

import copy
import json
import unittest

from src.agents.modeling_agent import _describe_comparison
from src.common.schema import validate_frontend_data
from src.service.recommendation_service import mark_matching_rows
from tests.agents.support import MOCK


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


class ComparisonWordingTest(unittest.TestCase):
    def test_a_near_perfect_r2_is_not_rounded_up_to_one(self) -> None:
        text = _describe_comparison([{"model": "lstm", "implementation": "pytorch", "status": "VALIDATED", "mae": 0.0048429, "rmse": 0.0092647, "r2": 0.9999849834550535}])

        self.assertIn("R2 0.999985", text)
        self.assertNotIn("R2 1,", text + ",")


if __name__ == "__main__":
    unittest.main()
