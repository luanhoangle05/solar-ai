"""Recommendation service. Owner: Duy.

Composes Duy's tools and agents, runs an orchestrator, and hands Tung a payload
only after it passes `validate_frontend_data`. The stage lifecycle lives in the
shared `src/agents/orchestrator.py`.

Until Luan's Data Agent and a real farm-state source are delivered, this module
supplies two clearly labeled stand-ins so a full run can be produced:
`RecordedWeatherDataAgent` (one recorded dataset hour served as the forecast)
and `simulated_farm_status` (every row assumed READY at one angle).
"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable, Sequence

from src.agents.manager_agent import DeterministicSafetyTools, ManagerAgent, RowStatusLookup
from src.agents.modeling_agent import ModelingAgent
from src.agents import orchestrator as stages
from src.agents.optimization_agent import OptimizationAgent
from src.agents.orchestrator import Orchestrator
from src.agents.reasoning import Reasoner
from src.agents.trace import Clock, TraceRecorder, utc_now_iso
from src.common.agent_contracts import DataAgentContract, DataAgentUpdate, OrchestratorContract
from src.common.config import ENERGY_SCOPE, PANELS_PER_ROW, PREDICTION_HORIZON_MINUTES, SCHEMA_VERSION, TOTAL_PANELS, ZONE_ROW_COUNTS, SimulationConfig
from src.common.schema import MODEL_NAMES, AgentState, FarmStatus, FrontendData, Metadata, WeatherFeatures, validate_frontend_data
from src.common.tool_contracts import ToolError
from src.models.advanced import boosting, lstm
from src.models.advanced.features import split_for_early_stopping
from src.models.data_loader import DatasetError, DatasetSource, hourly_weather, load_dataset_split
from src.models.evaluation import (
    EvaluatedModelingTools, ModelCandidate, StepOutcome, SystemEvaluation, evaluate_system,
)
from src.models.optimizer import DeterministicOptimizationTools


DEFAULT_IMPLEMENTATIONS = {"linear_regression": "linear_regression", "random_forest": "random_forest", "boosting": boosting.IMPLEMENTATION, "lstm": lstm.IMPLEMENTATION}
MOCK_DATA_ASSUMPTION = "SYNTHETIC EXAMPLE DATA: weather and energy labels are simulated from a documented formula (data/example/README.md); not measurements."
LIVE_DATA_ASSUMPTIONS = {
    "physics-derived": "Weather comes from the data pipeline; energy labels are physics-simulated for a reference row, not measured production. Model accuracy means agreement with that simulation.",
    "measured": "Weather and measured energy come from the data pipeline.",
    "unavailable": "Weather comes from the data pipeline; no energy labels are available.",
}
COMMON_ASSUMPTIONS = (
    "kWh is for one 20-panel row over the hour starting at interval_start.",
    "PROTOTYPE SIMULATION ASSUMPTIONS: movement and safety coefficients are not hardware-calibrated.",
    "Model comparison metrics are computed on the chronological validation window; the test window is held out.",
    "Control commands are simulation-only; no hardware is moved.",
)
RECORDED_WEATHER_ISSUE = "Recorded dataset hour served as the current forecast; forecast age is assumed to be zero, not measured."
SIMULATED_FARM_ASSUMPTION = "SIMULATED FARM SNAPSHOT: no row telemetry exists yet, so every row is shown READY at the control row's current angle."
MATCHING_ROWS_ASSUMPTION = "The decision is computed for the control row only. Rows in the same state and at the same angle are shown with the same action because the models have no per-row inputs; it was not computed for them separately."
NO_HISTORY_ASSUMPTION = "No decision history is stored yet; the history list is empty rather than filled with examples."


@dataclass(frozen=True)
class DuyAgents:
    """The three agents Duy owns, ready to be injected into the team orchestrator."""

    modeling: ModelingAgent
    optimization: OptimizationAgent
    manager: ManagerAgent


def build_metadata(source: DatasetSource, *, interval_start: str, control_target_id: str, config: SimulationConfig, extra_assumptions: Sequence[str] = ()) -> Metadata:
    """Run metadata labeled from the dataset source, so mock data can never be presented as live."""
    data_assumption = MOCK_DATA_ASSUMPTION if source.dataset_kind == "MOCK" else LIVE_DATA_ASSUMPTIONS[source.label_source]
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_kind": source.dataset_kind,
        "label_source": source.label_source,
        "energy_scope": ENERGY_SCOPE,
        "prediction_horizon_minutes": PREDICTION_HORIZON_MINUTES,
        "interval_start": interval_start,
        "control_target_id": control_target_id,
        "config_id": config.config_id,
        "assumptions": [data_assumption, *COMMON_ASSUMPTIONS, *extra_assumptions],
    }


def build_modeling_tools(source: DatasetSource, *, metadata: Metadata, extra_candidates: Sequence[ModelCandidate] = ()) -> EvaluatedModelingTools:
    """Train Duy's models on the train window and score every contract model on the validation window.

    `extra_candidates` is where Luan's baseline adapters plug in; a candidate
    supplied for `boosting` or `lstm` replaces the one trained here. A model
    nobody supplies is reported UNAVAILABLE, never estimated.
    """
    try:
        split = load_dataset_split(source)
    except (DatasetError, ValueError) as exc:
        raise ToolError(f"Training data unavailable: {exc}") from exc
    rows = [*split.train, *split.validation, *split.test]
    supplied = {candidate.model: candidate for candidate in extra_candidates}
    if boosting.MODEL_NAME not in supplied:
        supplied[boosting.MODEL_NAME] = _train_boosting_candidate(split.train)
    if lstm.MODEL_NAME not in supplied:
        supplied[lstm.MODEL_NAME] = _train_lstm_candidate(split.train, rows)
    candidates = [
        supplied.get(model) or ModelCandidate(model, DEFAULT_IMPLEMENTATIONS[model], unavailable_reason="adapter not delivered yet")
        for model in MODEL_NAMES
    ]
    return EvaluatedModelingTools(candidates, split.validation, metadata=metadata)


def _train_boosting_candidate(train_rows: Sequence) -> ModelCandidate:
    """Early stopping uses the tail of the train window, so validation stays unseen for selection."""
    try:
        predictor = boosting.train_boosting(*split_for_early_stopping(train_rows))
    except ToolError as exc:
        return ModelCandidate(boosting.MODEL_NAME, boosting.IMPLEMENTATION, unavailable_reason=f"training failed: {exc}")
    return ModelCandidate(boosting.MODEL_NAME, boosting.IMPLEMENTATION, predictor=predictor)


def _train_lstm_candidate(train_rows: Sequence, all_rows: Sequence) -> ModelCandidate:
    """The adapter keeps hourly weather (never labels) as look-back history for prediction time."""
    try:
        predictor = lstm.train_lstm(*split_for_early_stopping(train_rows), hourly_weather(all_rows))
    except ToolError as exc:
        return ModelCandidate(lstm.MODEL_NAME, lstm.IMPLEMENTATION, unavailable_reason=f"training failed: {exc}")
    return ModelCandidate(lstm.MODEL_NAME, lstm.IMPLEMENTATION, predictor=predictor)


def build_agents(
    modeling_tools: EvaluatedModelingTools, config: SimulationConfig, *,
    row_status: RowStatusLookup | None = None, clock: Clock = utc_now_iso, reasoner: Reasoner | None = None,
) -> DuyAgents:
    """`reasoner` adds an LLM-worded explanation to each agent's log; without one, agents use templated text only.

    The replay and the evaluation never pass a reasoner, so they make no LLM calls.
    """
    return DuyAgents(
        modeling=ModelingAgent(modeling_tools, config, clock=clock, reasoner=reasoner),
        optimization=OptimizationAgent(DeterministicOptimizationTools(), config, clock=clock, reasoner=reasoner),
        manager=ManagerAgent(DeterministicSafetyTools(), config, row_status=row_status, clock=clock, reasoner=reasoner),
    )


def run_decision_stages(state: AgentState, agents: DuyAgents) -> AgentState:
    """Modeling -> Optimization -> Manager on a state that already holds `data` and `weather`.

    Returns a new state; the input is not modified. A failed Modeling or
    Optimization stage is recorded in `errors` and the Manager still decides
    (HOLD or STOW). A Manager failure propagates: there is no safe decision to report.
    """
    return stages.run_decision_stages(state, agents.modeling, agents.optimization, agents.manager)


class RecordedWeatherDataAgent:
    """STAND-IN for Luan's Data Agent: serves one recorded dataset hour as the forecast.

    The report is DEGRADED, not VALID, and says why: nothing was fetched or
    freshness-checked here. Replace with the real Data Agent when it is delivered.
    """

    def __init__(self, weather: WeatherFeatures, source: DatasetSource, *, clock: Clock = utc_now_iso) -> None:
        self._weather, self._source, self._clock = weather, source, clock

    def run(self, state: AgentState) -> DataAgentUpdate:
        recorder = TraceRecorder("data", self._clock)
        recorder.log("weather_received", f"Recorded weather for {self._weather['timestamp']} read from {self._source.path.name} ({self._source.dataset_kind}, labels {self._source.label_source})")
        recorder.log("data_quality", RECORDED_WEATHER_ISSUE)
        report = {"status": "DEGRADED", "source": f"recorded:{self._source.path.name}", "forecast_age_minutes": 0.0, "used_cache": False, "issues": [RECORDED_WEATHER_ISSUE]}
        return {"data": report, "weather": self._weather, **recorder.trace()}


def simulated_farm_status(angle_deg: float) -> FarmStatus:
    """SIMULATED farm snapshot: every row READY at `angle_deg`, in the contract's four zones. Not telemetry."""
    zones, rows, first = [], [], 1
    for zone_number, row_count in enumerate(ZONE_ROW_COUNTS, start=1):
        zone_id = f"zone-{zone_number:02d}"
        row_ids = [f"row-{number:03d}" for number in range(first, first + row_count)]
        zones.append({"zone_id": zone_id, "row_ids": row_ids, "panel_count": row_count * PANELS_PER_ROW})
        rows.extend({"row_id": row_id, "zone_id": zone_id, "panel_count": PANELS_PER_ROW, "angle_deg": angle_deg, "current_state": "READY", "action": "HOLD"} for row_id in row_ids)
        first += row_count
    return {"total_panels": TOTAL_PANELS, "zones": zones, "rows": rows}


def run_recommendation(
    source: DatasetSource,
    data_agent: DataAgentContract,
    modeling_tools: EvaluatedModelingTools,
    config: SimulationConfig,
    *,
    interval_start: str,
    current_angle_deg: float,
    control_target_id: str,
    run_id: str,
    extra_assumptions: Sequence[str] = (),
    reasoner: Reasoner | None = None,
    clock: Clock = utc_now_iso,
) -> FrontendData:
    """One full run, Data -> Modeling -> Optimization -> Manager, with the given Data Agent.

    `source` is the dataset the models were trained on; it labels the payload.
    The farm snapshot is simulated and the payload's assumptions say so.
    `reasoner` adds LLM-worded explanations to the agent log; it cannot change any result.
    """
    farm = simulated_farm_status(current_angle_deg)
    row_states = {row["row_id"]: {"angle_deg": row["angle_deg"], "current_state": row["current_state"]} for row in farm["rows"]}
    agents = build_agents(modeling_tools, config, row_status=row_states.__getitem__, clock=clock, reasoner=reasoner)
    orchestrator = Orchestrator(data_agent, agents.modeling, agents.optimization, agents.manager, farm_status=lambda: farm)
    metadata = build_metadata(
        source, interval_start=interval_start, control_target_id=control_target_id, config=config,
        extra_assumptions=(*extra_assumptions, SIMULATED_FARM_ASSUMPTION, MATCHING_ROWS_ASSUMPTION, NO_HISTORY_ASSUMPTION),
    )
    state: AgentState = {
        "run_id": run_id, "timestamp": clock(), "metadata": metadata, "stage": "PENDING",
        "weather": None, "data": None, "modeling": None, "optimization": None, "safety": None, "decision": None,
        "agent_log": [], "tool_calls": [], "errors": [],
    }
    payload = mark_matching_rows(get_recommendation(state, orchestrator))
    validate_frontend_data(payload)
    return payload


def mark_matching_rows(payload: FrontendData) -> FrontendData:
    """Show the control row's action on every row in the same state and at the same angle.

    Returns a new payload; no angle changes and no decision is computed for the
    other rows. With no per-row model inputs they would receive the same answer,
    which the payload's assumptions state. Rows that differ are left as they are.
    """
    rows = payload["farm_status"]["rows"]
    target = next(row for row in rows if row["row_id"] == payload["metadata"]["control_target_id"])
    marked = [
        {**row, "action": target["action"]} if (row["current_state"], row["angle_deg"]) == (target["current_state"], target["angle_deg"]) else row
        for row in rows
    ]
    return {**payload, "farm_status": {**payload["farm_status"], "rows": marked}}


def recommend_for_recorded_hour(
    source: DatasetSource,
    weather: WeatherFeatures,
    modeling_tools: EvaluatedModelingTools,
    config: SimulationConfig,
    *,
    control_target_id: str,
    run_id: str,
    reasoner: Reasoner | None = None,
    clock: Clock = utc_now_iso,
) -> FrontendData:
    """A full run for one recorded dataset hour at the angle in `weather`, using the recorded-weather stand-in."""
    return run_recommendation(
        source, RecordedWeatherDataAgent(weather, source, clock=clock), modeling_tools, config,
        interval_start=weather["timestamp"], current_angle_deg=weather["panel_angle_deg"],
        control_target_id=control_target_id, run_id=run_id, reasoner=reasoner, clock=clock,
    )


def replay_test_window(
    source: DatasetSource,
    modeling_tools: EvaluatedModelingTools,
    config: SimulationConfig,
    *,
    initial_angle_deg: float,
    control_target_id: str,
    energy_at: Callable[[WeatherFeatures, float], float] | None = None,
    energy_source: str | None = None,
) -> SystemEvaluation:
    """System evaluation: replay the decision stages over the held-out test window.

    REPLAY ASSUMPTIONS: each hour's recorded weather is treated as a fresh, valid
    forecast for that hour, and row state is not simulated (the panel-status check
    is reported as not run). By default energy is the selected model's prediction,
    not a measurement, and it grades the model's choices with the model's own
    numbers, so it is optimistic; pass `energy_at` to score against another
    energy source. The test window is replayed one decision per hour, whatever
    number of angle rows the dataset holds for that hour.
    """
    try:
        test_hours = hourly_weather(load_dataset_split(source).test)
    except (DatasetError, ValueError) as exc:
        raise ToolError(f"Replay data unavailable: {exc}") from exc
    agents = build_agents(modeling_tools, config)
    report = {"status": "VALID", "source": f"replay:{source.path.name}", "forecast_age_minutes": 0.0, "used_cache": False, "issues": []}

    def metadata_for(weather: WeatherFeatures) -> Metadata:
        return build_metadata(source, interval_start=weather["timestamp"], control_target_id=control_target_id, config=config)

    def decide(weather: WeatherFeatures) -> StepOutcome:
        state: AgentState = {
            "run_id": f"replay-{weather['timestamp']}", "timestamp": weather["timestamp"], "metadata": metadata_for(weather), "stage": "DATA",
            "weather": weather, "data": report, "modeling": None, "optimization": None, "safety": None, "decision": None,
            "agent_log": [], "tool_calls": [], "errors": [],
        }
        return _step_outcome(run_decision_stages(state, agents))

    if energy_at is None:
        selected = modeling_tools.select_best_model(modeling_tools.evaluate_models())
        predictor = modeling_tools.get_predictor(selected)
        energy_source = f"model-predicted ({selected})"

        def energy_at(weather: WeatherFeatures, angle_deg: float) -> float:
            return predictor.predict_kwh(weather, (angle_deg,), metadata=metadata_for(weather))[0]["predicted_kwh"]

    return evaluate_system(
        test_hours, decide, energy_at,
        initial_angle_deg=initial_angle_deg, energy_source=energy_source or "caller-supplied", config=config,
    )


def _step_outcome(state: AgentState) -> StepOutcome:
    safety, decision, optimization = state["safety"], state["decision"], state["optimization"]
    candidates = [] if state["modeling"] is None else state["modeling"]["candidate_predictions"]
    # What a tracker that ignores movement cost would gain: best predicted kWh minus the stay prediction.
    raw_gain = None if optimization is None else max(entry["predicted_kwh"] for entry in candidates) - optimization["baseline_kwh"]
    return StepOutcome(
        action=decision["action"],
        target_angle_deg=decision["target_angle_deg"],
        safety_passed=safety["passed"],
        severe_violation=any(not check["passed"] and check["severity"] == "SEVERE" for check in safety["checks"]),
        raw_energy_gain_kwh=raw_gain,
        stage_failed=bool(state["errors"]),
    )


def get_recommendation(state: AgentState, orchestrator: OrchestratorContract) -> FrontendData:
    """Run the orchestrator and return its payload only if it satisfies the frontend contract.

    A malformed payload raises `ContractError`; it is never passed on to the frontend.
    """
    payload = orchestrator.run(state)
    validate_frontend_data(payload)
    return payload


def save_recommendation(payload: FrontendData, path: Path) -> Path:
    """Write a validated payload as the JSON file the frontend loads."""
    validate_frontend_data(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
