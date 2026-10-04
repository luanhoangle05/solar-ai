"""Lightweight state machine, not an LLM agent. Owners: all three at integration.

Flow: Data -> Modeling -> Optimization -> Manager / Safety -> FrontendData.
Each agent returns only its own sections; this module merges them, appends the
traces and records errors. A failed stage is recorded and the run still goes to
the Manager / Safety Agent, which decides HOLD or STOW from what is available.
No stage output is ever invented to complete the normal path.
"""

from typing import Callable, Sequence

from src.agents.trace import StageError
from src.common.agent_contracts import (
    DataAgentContract, ManagerAgentContract, ModelingAgentContract,
    OptimizationAgentContract,
)
from src.common.schema import (
    MODEL_NAMES, AgentState, DataAgentReport, FarmStatus, FrontendData, HistoricalDecision, ModelMetrics, RunError,
    validate_agent_state, validate_frontend_data,
)
from src.common.tool_contracts import ToolError


FarmStatusSource = Callable[[], FarmStatus]
TRACE_KEYS = ("agent_log", "tool_calls")
CURRENT_WEATHER_KEYS = ("temperature_c", "cloud_cover_pct", "precipitation_mm", "wind_speed_kmh", "wind_gust_kmh", "ghi_wm2", "dni_wm2", "dhi_wm2")
NOT_RUN = "not run"


def merge_update(state: AgentState, update: dict, stage: str) -> AgentState:
    """A new state with one agent's owned sections merged in and its traces appended."""
    sections = {key: value for key, value in update.items() if key not in TRACE_KEYS}
    return {
        **state,
        **sections,
        "stage": stage,
        "agent_log": [*state["agent_log"], *update["agent_log"]],
        "tool_calls": [*state["tool_calls"], *update["tool_calls"]],
    }


def _with_error(state: AgentState, error: RunError) -> AgentState:
    return {**state, "errors": [*state["errors"], error]}


def run_data_stage(state: AgentState, data: DataAgentContract) -> AgentState:
    """Run the Data Agent. A failure, or an agent that is not implemented yet, is recorded; `data` and `weather` stay null."""
    state = {**state, "stage": "DATA"}
    try:
        return merge_update(state, data.run(state), "DATA")
    except StageError as error:
        return _with_error(merge_update(state, error.trace, "DATA"), {"agent": error.agent, "code": error.code, "message": error.message})
    except (ToolError, NotImplementedError) as error:
        return _with_error(state, {"agent": "data", "code": "DATA_UNAVAILABLE", "message": f"Data Agent produced no report: {error}"})


def run_decision_stages(state: AgentState, modeling: ModelingAgentContract, optimization: OptimizationAgentContract, manager: ManagerAgentContract) -> AgentState:
    """Modeling -> Optimization -> Manager on a state that has been through the data stage.

    Returns a new state; the input is not modified. A failed Modeling or
    Optimization stage is recorded in `errors` and the Manager still decides
    (HOLD or STOW). A Manager failure propagates: there is no safe decision to report.
    """
    for stage, agent in (("MODELING", modeling), ("OPTIMIZATION", optimization)):
        try:
            state = merge_update(state, agent.run(state), stage)
        except StageError as error:
            state = _with_error(merge_update(state, error.trace, state["stage"]), {"agent": error.agent, "code": error.code, "message": error.message})
            break
    state = merge_update(state, manager.run(state), "COMPLETE")
    validate_agent_state(state)
    return state


def _unavailable_data_report(state: AgentState) -> DataAgentReport:
    """What the payload says about data when the Data Agent returned nothing: unknown age, never zero."""
    issues = [error["message"] for error in state["errors"] if error["agent"] == "data"] or ["Data Agent returned no report"]
    return {"status": "INVALID", "source": "unavailable", "forecast_age_minutes": None, "used_cache": False, "issues": issues}


def _unrun_model_comparison() -> list[ModelMetrics]:
    return [{"model": model, "implementation": NOT_RUN, "status": "UNAVAILABLE", "mae": None, "rmse": None, "r2": None} for model in MODEL_NAMES]


def build_frontend_data(state: AgentState, farm_status: FarmStatus, history: Sequence[HistoricalDecision] = ()) -> FrontendData:
    """Shape a completed state into the frontend payload. Sections that never ran are null or empty, not estimated."""
    modeling, weather, decision = state["modeling"], state["weather"], state["decision"]
    target_id = state["metadata"]["control_target_id"]
    # The decision is a proposal: the controlled row keeps its observed angle and shows the proposed action.
    rows = [{**row, "action": decision["action"]} if row["row_id"] == target_id else row for row in farm_status["rows"]]
    return {
        "timestamp": state["timestamp"],
        "metadata": state["metadata"],
        "current_weather": None if weather is None else {key: weather[key] for key in CURRENT_WEATHER_KEYS},
        "data_agent": state["data"] or _unavailable_data_report(state),
        "model_comparison": modeling["model_comparison"] if modeling else _unrun_model_comparison(),
        "selected_model": modeling["selected_model"] if modeling else None,
        "candidate_predictions": modeling["candidate_predictions"] if modeling else [],
        "optimization": state["optimization"],
        "safety": state["safety"],
        "decision": decision,
        "farm_status": {**farm_status, "rows": rows},
        "agent_log": state["agent_log"],
        "history": list(history),
        "errors": state["errors"],
    }


class Orchestrator:
    """Flow: Data -> Modeling -> Optimization -> Safety -> frontend.

    Errors and unreliable data route to Safety before any command; no
    model/optimizer success is fabricated to complete the normal path.
    `farm_status` supplies the 50-row farm snapshot the dashboard shows and
    `history` the earlier decisions; this class does not create either.
    """

    def __init__(
        self, data: DataAgentContract, modeling: ModelingAgentContract,
        optimization: OptimizationAgentContract, manager: ManagerAgentContract,
        *, farm_status: FarmStatusSource | None = None, history: Sequence[HistoricalDecision] = (),
    ) -> None:
        self.data, self.modeling = data, modeling
        self.optimization, self.manager = optimization, manager
        self._farm_status, self._history = farm_status, tuple(history)
        self.final_state: AgentState | None = None

    def run(self, state: AgentState) -> FrontendData:
        """Own the lifecycle, merge each agent's sections, record traces and errors, return a validated payload."""
        if self._farm_status is None:
            raise NotImplementedError("Orchestrator has no farm status source configured")
        after_data = run_data_stage(state, self.data)
        self.final_state = run_decision_stages(after_data, self.modeling, self.optimization, self.manager)
        payload = build_frontend_data(self.final_state, self._farm_status(), self._history)
        validate_frontend_data(payload)
        return payload
