"""Modeling Agent wording: what the trace, and so the LLM, is given to quote."""

import unittest

from src.agents.modeling_agent import _describe_comparison


class ComparisonWordingTest(unittest.TestCase):
    def test_a_near_perfect_r2_is_not_rounded_up_to_one(self) -> None:
        text = _describe_comparison([{"model": "lstm", "implementation": "pytorch", "status": "VALIDATED", "mae": 0.0048429, "rmse": 0.0092647, "r2": 0.9999849834550535}])

        self.assertIn("R2 0.999985", text)
        self.assertNotIn("R2 1,", text + ",")


if __name__ == "__main__":
    unittest.main()
