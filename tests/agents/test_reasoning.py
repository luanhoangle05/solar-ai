"""LLM reasoning: explains tool results in words, never changes them, and fails safe."""

import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from src.agents.manager_agent import DeterministicSafetyTools, ManagerAgent
from src.agents.optimization_agent import OptimizationAgent
from src.agents.reasoning import (
    API_KEY_VARIABLE, DEFAULT_MODEL, LLM_TOOL, MODEL_VARIABLE, AnthropicReasoner, load_reasoner, require_grounded,
)
from src.agents.trace import TraceRecorder
from src.common.config import DEFAULT_CONFIG
from src.common.tool_contracts import ToolError
from src.models.optimizer import DeterministicOptimizationTools
from tests.agents.support import fixed_clock, state_before


FACTS = "optimize_angle [OK]: recommended 45 deg, net benefit +0.2600 kWh-eq\nrecommendation: gain +0.290 kWh, cost 0.030"
SECRET = "sk-ant-test-secret"


class FixedReasoner:
    """Stand-in LLM that returns a prepared sentence and records what it was shown."""

    def __init__(self, text: str) -> None:
        self.text, self.seen = text, []

    def explain(self, agent: str, facts: str) -> str:
        self.seen.append((agent, facts))
        return self.text


class OfflineReasoner:
    def explain(self, agent: str, facts: str) -> str:
        raise ToolError("LLM request failed: network unreachable")


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


def reply(text: str) -> FakeResponse:
    return FakeResponse(json.dumps({"content": [{"type": "text", "text": text}]}).encode())


class GroundingTest(unittest.TestCase):
    def test_accepts_text_whose_numbers_all_come_from_the_facts(self) -> None:
        text = "Moving to 45 deg gains 0.290 kWh for a cost of 0.030, a net benefit of 0.26."

        self.assertEqual(require_grounded(text, FACTS), text)

    def test_ignores_sign_and_trailing_zeros_when_matching_numbers(self) -> None:
        self.assertEqual(require_grounded("Net benefit is +0.26 kWh-eq.", FACTS), "Net benefit is +0.26 kWh-eq.")

    def test_rejects_text_containing_a_number_the_tools_never_produced(self) -> None:
        with self.assertRaisesRegex(ToolError, "12"):
            require_grounded("This saves 12 percent.", FACTS)

    def test_rejects_an_empty_explanation(self) -> None:
        with self.assertRaises(ToolError):
            require_grounded("   ", FACTS)

    def test_accepts_text_without_numbers(self) -> None:
        self.assertEqual(require_grounded("Rotating is worth the movement.", FACTS), "Rotating is worth the movement.")


class TraceReasoningTest(unittest.TestCase):
    def setUp(self) -> None:
        self.recorder = TraceRecorder("optimization", fixed_clock)
        self.recorder.call("optimize_angle", lambda: 45, lambda angle: f"recommended {angle} deg")
        self.recorder.log("recommendation", "Best net benefit is 45 deg")

    def test_no_reasoner_leaves_the_trace_unchanged(self) -> None:
        before = self.recorder.trace()

        self.recorder.reason(None)

        self.assertEqual(self.recorder.trace(), before)

    def test_reasoner_sees_only_the_recorded_tool_results(self) -> None:
        reasoner = FixedReasoner("The optimizer recommends 45 deg.")

        self.recorder.reason(reasoner)

        agent, facts = reasoner.seen[0]
        self.assertEqual(agent, "optimization")
        self.assertIn("optimize_angle [OK]: recommended 45 deg", facts)
        self.assertIn("recommendation: Best net benefit is 45 deg", facts)

    def test_explanation_is_logged_and_the_call_is_recorded(self) -> None:
        self.recorder.reason(FixedReasoner("The optimizer recommends 45 deg."))

        trace = self.recorder.trace()
        self.assertEqual(trace["agent_log"][-1]["action"], "llm_reasoning")
        self.assertEqual(trace["agent_log"][-1]["result"], "The optimizer recommends 45 deg.")
        self.assertEqual((trace["tool_calls"][-1]["tool"], trace["tool_calls"][-1]["status"]), (LLM_TOOL, "OK"))

    def test_ungrounded_explanation_is_discarded_and_recorded_as_an_error(self) -> None:
        self.recorder.reason(FixedReasoner("This is 99 percent better."))

        trace = self.recorder.trace()
        self.assertEqual(trace["tool_calls"][-1]["status"], "ERROR")
        self.assertEqual(trace["agent_log"][-1]["action"], "llm_reasoning_unavailable")
        self.assertNotIn("99", trace["agent_log"][-1]["result"])

    def test_llm_failure_never_fails_the_stage(self) -> None:
        self.recorder.reason(OfflineReasoner())

        trace = self.recorder.trace()
        self.assertEqual(trace["tool_calls"][-1]["status"], "ERROR")
        self.assertEqual(trace["agent_log"][-1]["action"], "llm_reasoning_unavailable")


class AgentReasoningTest(unittest.TestCase):
    def test_optimization_result_is_identical_with_and_without_the_llm(self) -> None:
        state = state_before("optimization")
        plain = OptimizationAgent(DeterministicOptimizationTools(), DEFAULT_CONFIG, clock=fixed_clock).run(state)

        explained = OptimizationAgent(DeterministicOptimizationTools(), DEFAULT_CONFIG, clock=fixed_clock, reasoner=FixedReasoner("Rotating is worth it.")).run(state)

        self.assertEqual(explained["optimization"], plain["optimization"])
        self.assertEqual(explained["agent_log"][-1]["action"], "llm_reasoning")
        self.assertEqual(explained["agent_log"][:-1], plain["agent_log"])

    def test_manager_decision_is_identical_with_and_without_the_llm(self) -> None:
        state = state_before("safety")
        plain = ManagerAgent(DeterministicSafetyTools(), DEFAULT_CONFIG, clock=fixed_clock).run(state)

        explained = ManagerAgent(DeterministicSafetyTools(), DEFAULT_CONFIG, clock=fixed_clock, reasoner=FixedReasoner("STOW the row regardless of the checks.")).run(state)

        self.assertEqual((explained["safety"], explained["decision"]), (plain["safety"], plain["decision"]))
        self.assertEqual(explained["agent_log"][-1]["agent"], "manager")

    def test_manager_still_decides_when_the_llm_is_offline(self) -> None:
        state = state_before("safety")
        plain = ManagerAgent(DeterministicSafetyTools(), DEFAULT_CONFIG, clock=fixed_clock).run(state)

        update = ManagerAgent(DeterministicSafetyTools(), DEFAULT_CONFIG, clock=fixed_clock, reasoner=OfflineReasoner()).run(state)

        self.assertEqual(update["decision"], plain["decision"])


class AnthropicReasonerTest(unittest.TestCase):
    def test_sends_the_facts_and_returns_the_reply_text(self) -> None:
        sent = []

        def transport(request, timeout):
            sent.append((request, timeout))
            return reply("  Rotating is worth it.  ")

        text = AnthropicReasoner(SECRET, model="test-model", transport=transport).explain("optimization", FACTS)

        request, _timeout = sent[0]
        body = json.loads(request.data)
        self.assertEqual(text, "Rotating is worth it.")
        self.assertEqual(request.get_header("X-api-key"), SECRET)
        self.assertEqual(body["model"], "test-model")
        self.assertEqual(body["messages"], [{"role": "user", "content": FACTS}])
        self.assertIn("optimization", body["system"])

    def test_http_failure_becomes_a_tool_error_without_leaking_the_key(self) -> None:
        def transport(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"error": {"message": "invalid x-api-key"}}'))

        with self.assertRaises(ToolError) as raised:
            AnthropicReasoner(SECRET, transport=transport).explain("manager", FACTS)

        self.assertIn("401", str(raised.exception))
        self.assertNotIn(SECRET, str(raised.exception))

    def test_network_failure_becomes_a_tool_error(self) -> None:
        def transport(request, timeout):
            raise TimeoutError("timed out")

        with self.assertRaises(ToolError):
            AnthropicReasoner(SECRET, transport=transport).explain("manager", FACTS)

    def test_reply_without_text_becomes_a_tool_error(self) -> None:
        with self.assertRaises(ToolError):
            AnthropicReasoner(SECRET, transport=lambda request, timeout: FakeResponse(b'{"content": []}')).explain("manager", FACTS)


class LoadReasonerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.env_file = Path(self.directory.name) / ".env"

    def test_no_key_means_no_llm(self) -> None:
        self.assertIsNone(load_reasoner({}, self.env_file))

    def test_blank_key_means_no_llm(self) -> None:
        self.env_file.write_text(f"{API_KEY_VARIABLE}=\n", encoding="utf-8")

        self.assertIsNone(load_reasoner({}, self.env_file))

    def test_reads_the_key_from_the_env_file(self) -> None:
        self.env_file.write_text(f"# comment\n{API_KEY_VARIABLE}={SECRET}\n", encoding="utf-8")

        reasoner = load_reasoner({}, self.env_file)

        self.assertIsInstance(reasoner, AnthropicReasoner)
        self.assertEqual(reasoner.model, DEFAULT_MODEL)

    def test_environment_overrides_the_env_file(self) -> None:
        self.env_file.write_text(f"{API_KEY_VARIABLE}=from-file\n", encoding="utf-8")

        reasoner = load_reasoner({API_KEY_VARIABLE: SECRET, MODEL_VARIABLE: "other-model"}, self.env_file)

        self.assertEqual(reasoner.model, "other-model")


if __name__ == "__main__":
    unittest.main()
