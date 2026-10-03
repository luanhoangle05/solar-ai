"""Shared fixtures for agent tests: the mock completed state and a fixed clock."""

import copy
import json
from pathlib import Path

from src.common.schema import AgentState


MOCK = Path(__file__).resolve().parents[2] / "data" / "mock"
FIXED_TIME = "2026-06-21T19:00:30Z"
_STATE = json.loads((MOCK / "agent_state.json").read_text(encoding="utf-8"))


def fixed_clock() -> str:
    return FIXED_TIME


def mock_state(**overrides: object) -> AgentState:
    """A fresh copy of the mock completed state with selected sections replaced."""
    return {**copy.deepcopy(_STATE), **overrides}


def state_before(stage: str) -> AgentState:
    """The mock state as it would look when the given stage starts: later sections are null."""
    order = ("modeling", "optimization", "safety")
    cleared = order[order.index(stage):] + (("decision",) if stage in order else ())
    return mock_state(**{key: None for key in cleared}, stage=stage.upper(), agent_log=[], tool_calls=[])
