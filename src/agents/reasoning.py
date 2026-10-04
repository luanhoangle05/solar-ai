"""Owner: Duy. Optional LLM explanation of an agent's own tool results.

The LLM never calculates and never decides. It is shown the tool results an
agent has already recorded and writes a short explanation of them. The text
is accepted only if every number in it was produced by a tool; otherwise it is
discarded. With no API key, or on any failure, agents keep their templated
explanation and the run is unaffected.

Uses only the standard library, so it adds no dependency.
"""

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Mapping, Protocol

from src.common.schema import AgentName
from src.common.tool_contracts import ToolError


LLM_TOOL = "explain_with_llm"
API_KEY_VARIABLE = "ANTHROPIC_API_KEY"
MODEL_VARIABLE = "SOLAR_LLM_MODEL"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
MAX_OUTPUT_TOKENS = 220
TIMEOUT_SECONDS = 20.0
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
# A number not glued to a word, so "R2" and "row-001" labels are compared as written in both texts.
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")
_SYSTEM_PROMPT = (
    "You are the {agent} agent in a solar-farm panel-angle control system. Your tools have already run; "
    "their recorded results are in the user message. In two or three plain sentences, explain what the tools "
    "found and why the outcome follows from them. Rules: use only the facts given; copy every number exactly "
    "as it is written there; never calculate, round, convert or estimate a number; write counts as words; "
    "do not mention dates or times; do not change, question or add to the outcome. Control commands in this "
    "system are simulation-only: describe an action as recommended or simulated, never as hardware having moved. "
    "Plain text only."
)

Transport = Callable[..., object]


class Reasoner(Protocol):
    def explain(self, agent: AgentName, facts: str) -> str: ...


def _numbers(text: str) -> set[float]:
    return {float(match) for match in _NUMBER.findall(text)}


def require_grounded(text: str, facts: str) -> str:
    """Return the explanation only if it is non-empty and every number in it appears in the tool results."""
    cleaned = text.strip()
    if not cleaned:
        raise ToolError("LLM returned an empty explanation")
    invented = sorted(_numbers(cleaned) - _numbers(facts))
    if invented:
        raise ToolError(f"LLM explanation rejected: it contains numbers no tool produced ({', '.join(f'{value:g}' for value in invented)})")
    return cleaned


class AnthropicReasoner:
    """Asks the Anthropic Messages API for an explanation. One short request per agent per run."""

    def __init__(self, api_key: str, *, model: str = DEFAULT_MODEL, timeout: float = TIMEOUT_SECONDS, transport: Transport = urllib.request.urlopen) -> None:
        self._api_key, self.model, self._timeout, self._transport = api_key, model, timeout, transport

    def explain(self, agent: AgentName, facts: str) -> str:
        body = {
            "model": self.model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "system": _SYSTEM_PROMPT.format(agent=agent),
            "messages": [{"role": "user", "content": facts}],
        }
        request = urllib.request.Request(
            API_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={"x-api-key": self._api_key, "anthropic-version": API_VERSION, "content-type": "application/json"},
        )
        try:
            with self._transport(request, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ToolError(f"LLM request failed with HTTP {exc.code}") from exc
        except (OSError, ValueError) as exc:
            raise ToolError(f"LLM request failed: {type(exc).__name__}") from exc
        text = "".join(block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text").strip()
        if not text:
            raise ToolError("LLM reply contained no text")
        return text


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    entries = (line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if "=" in line and not line.lstrip().startswith("#"))
    return {key.strip(): value.strip() for key, value in entries}


def load_reasoner(environment: Mapping[str, str] | None = None, env_file: Path = ENV_FILE) -> Reasoner | None:
    """The configured LLM reasoner, or None when no API key is set (agents then use templated text only)."""
    settings = {**_read_env_file(env_file), **(os.environ if environment is None else environment)}
    api_key = settings.get(API_KEY_VARIABLE, "").strip()
    if not api_key:
        return None
    return AnthropicReasoner(api_key, model=settings.get(MODEL_VARIABLE, "").strip() or DEFAULT_MODEL)
