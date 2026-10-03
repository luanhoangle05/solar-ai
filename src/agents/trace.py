"""Owner: Duy. Trace recording shared by the Modeling, Optimization and Manager agents.

Agents coordinate tools and explain what the tools returned. Every tool call
and every reasoning step is recorded here so the run can be audited and shown
in the frontend activity log. Explanations are templated from tool results;
no LLM is involved and nothing is calculated in this module.
"""

from datetime import datetime, timezone
from typing import Callable, TypeVar

from src.common.agent_contracts import StageTrace
from src.common.schema import AgentLogEntry, AgentName, ToolCall
from src.common.tool_contracts import ToolError


Result = TypeVar("Result")
Clock = Callable[[], str]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class StageError(ToolError):
    """An agent could not produce its section; carries the trace gathered so far.

    The orchestrator records the failure and still routes to the Manager /
    Safety Agent. A stage never returns invented output to finish the run.
    """

    def __init__(self, agent: AgentName, code: str, message: str, trace: StageTrace) -> None:
        super().__init__(message)
        self.agent, self.code, self.message, self.trace = agent, code, message, trace


class TraceRecorder:
    """Collects one agent's log entries and tool calls for a single run."""

    def __init__(self, agent: AgentName, clock: Clock = utc_now_iso) -> None:
        self._agent, self._clock = agent, clock
        self._agent_log: list[AgentLogEntry] = []
        self._tool_calls: list[ToolCall] = []

    def log(self, action: str, result: str) -> None:
        self._agent_log.append({"timestamp": self._clock(), "agent": self._agent, "action": action, "result": result})

    def call(self, tool: str, run: Callable[[], Result], describe: Callable[[Result], str]) -> Result:
        """Run one tool, record OK/ERROR, and re-raise tool failures unchanged."""
        try:
            result = run()
        except ToolError as exc:
            self._record(tool, "ERROR", str(exc))
            raise
        self._record(tool, "OK", describe(result))
        return result

    def fail(self, code: str, message: str) -> StageError:
        """Log the failure and build the error for the caller to raise."""
        self.log("failed", message)
        return StageError(self._agent, code, message, self.trace())

    def trace(self) -> StageTrace:
        return {"agent_log": list(self._agent_log), "tool_calls": list(self._tool_calls)}

    def _record(self, tool: str, status: str, detail: str) -> None:
        self._tool_calls.append({"timestamp": self._clock(), "agent": self._agent, "tool": tool, "status": status, "detail": detail})
