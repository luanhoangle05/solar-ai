"""Recommendation service. Owner: Duy.

Composes Duy's tools and agents, runs an injected orchestrator, and hands Tung a
payload only after it passes `validate_frontend_data`. The orchestrator itself
(stage lifecycle, farm snapshot, history) is shared team code and is injected.
"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable, Sequence

from src.agents.manager_agent import DeterministicSafetyTools, ManagerAgent, RowStatusLookup
from src.agents.modeling_agent import ModelingAgent
from src.agents.optimization_agent import OptimizationAgent
from src.agents.trace import Clock, StageError, utc_now_iso
from src.common.agent_contracts import OrchestratorContract
from src.common.config import ENERGY_SCOPE, PREDICTION_HORIZON_MINUTES, SCHEMA_VERSION, SimulationConfig
from src.common.schema import MODEL_NAMES, AgentState, FrontendData, Metadata, WeatherFeatures, validate_agent_state, validate_frontend_data
from src.common.tool_contracts import ToolError
from src.models.advanced import boosting
from src.models.data_loader import DatasetError, DatasetSource, load_weather_rows
from src.models.evaluation import (
    EvaluatedModelingTools, ModelCandidate, StepOutcome, SystemEvaluation, chronological_split, evaluate_system, to_features,
)
from src.models.optimizer import DeterministicOptimizationTools


DEFAULT_IMPLEMENTATIONS = {"linear_regression": "linear_regression", "random_forest": "random_forest", "boosting": boosting.IMPLEMENTATION, "lstm": "pytorch"}
MOCK_DATA_ASSUMPTION = "SYNTHETIC EXAMPLE DATA: weather and energy labels are simulated from a documented formula (data/example/README.md); not measurements."
LIVE_DATA_ASSUMPTION = "Dataset provenance is declared by the data pipeline (label_source)."
COMMON_ASSUMPTIONS = (
    "kWh is for one 20-panel row over the hour starting at interval_start.",
    "PROTOTYPE SIMULATION ASSUMPTIONS: movement and safety coefficients are not hardware-calibrated.",
    "Model comparison metrics are computed on the chronological validation window; the test window is held out.",
    "Control commands are simulation-only; no hardware is moved.",
)


@dataclass(frozen=True)
class DuyAgents:
    """The three agents Duy owns, ready to be injected into the team orchestrator."""

    modeling: ModelingAgent
    optimization: OptimizationAgent
    manager: ManagerAgent


def build_metadata(source: DatasetSource, *, interval_start: str, control_target_id: str, config: SimulationConfig) -> Metadata:
    """Run metadata labeled from the dataset source, so mock data can never be presented as live."""
    data_assumption = MOCK_DATA_ASSUMPTION if source.dataset_kind == "MOCK" else LIVE_DATA_ASSUMPTION
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_kind": source.dataset_kind,
        "label_source": source.label_source,
        "energy_scope": ENERGY_SCOPE,
        "prediction_horizon_minutes": PREDICTION_HORIZON_MINUTES,
        "interval_start": interval_start,
        "control_target_id": control_target_id,
        "config_id": config.config_id,
        "assumptions": [data_assumption, *COMMON_ASSUMPTIONS],
    }


def build_modeling_tools(source: DatasetSource, *, metadata: Metadata, extra_candidates: Sequence[ModelCandidate] = ()) -> EvaluatedModelingTools:
    """Train Duy's models on the train window and score every contract model on the validation window.

    `extra_candidates` is where Luan's baseline adapters (and later the LSTM)
    plug in. A model nobody supplies is reported UNAVAILABLE, never estimated.
    """
    try:
        split = chronological_split(load_weather_rows(source.path))
    except (DatasetError, ValueError) as exc:
        raise ToolError(f"Training data unavailable: {exc}") from exc
    supplied = {candidate.model: candidate for candidate in extra_candidates}
    if boosting.MODEL_NAME not in supplied:
        supplied[boosting.MODEL_NAME] = _train_boosting_candidate(split.train)
    candidates = [
        supplied.get(model) or ModelCandidate(model, DEFAULT_IMPLEMENTATIONS[model], unavailable_reason="adapter not delivered yet")
        for model in MODEL_NAMES
    ]
    return EvaluatedModelingTools(candidates, split.validation, metadata=metadata)


def _train_boosting_candidate(train_rows: Sequence) -> ModelCandidate:
    """Early stopping uses the tail of the train window, so validation stays unseen for selection."""
    try:
        predictor = boosting.train_boosting(*boosting.split_for_early_stopping(train_rows))
    except ToolError as exc:
        return ModelCandidate(boosting.MODEL_NAME, boosting.IMPLEMENTATION, unavailable_reason=f"training failed: {exc}")
    return ModelCandidate(boosting.MODEL_NAME, boosting.IMPLEMENTATION, predictor=predictor)


def build_agents(modeling_tools: EvaluatedModelingTools, config: SimulationConfig, *, row_status: RowStatusLookup | None = None, clock: Clock = utc_now_iso) -> DuyAgents:
    return DuyAgents(
        modeling=ModelingAgent(modeling_tools, config, clock=clock),
        optimization=OptimizationAgent(DeterministicOptimizationTools(), config, clock=clock),
        manager=ManagerAgent(DeterministicSafetyTools(), config, row_status=row_status, clock=clock),
    )


def run_decision_stages(state: AgentState, agents: DuyAgents) -> AgentState:
    """Modeling -> Optimization -> Manager on a state that already holds `data` and `weather`.

    Returns a new state; the input is not modified. A failed Modeling or
    Optimization stage is recorded in `errors` and the Manager still decides
    (HOLD or STOW). A Manager failure propagates: there is no safe decision to report.
    """
    for stage, agent in (("MODELING", agents.modeling), ("OPTIMIZATION", agents.optimization)):
        try:
            state = _merge_update(state, agent.run(state), stage)
        except StageError as error:
            state = {
                **_merge_update(state, error.trace, state["stage"]),
                "errors": [*state["errors"], {"agent": error.agent, "code": error.code, "message": error.message}],
            }
            break
    state = _merge_update(state, agents.manager.run(state), "COMPLETE")
    validate_agent_state(state)
    return state


def _merge_update(state: AgentState, update: dict, stage: str) -> AgentState:
    sections = {key: value for key, value in update.items() if key not in ("agent_log", "tool_calls")}
    return {
        **state,
        **sections,
        "stage": stage,
        "agent_log": [*state["agent_log"], *update["agent_log"]],
        "tool_calls": [*state["tool_calls"], *update["tool_calls"]],
    }


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
    not a measurement; pass `energy_at` to score against another energy source.
    """
    try:
        test_rows = chronological_split(load_weather_rows(source.path)).test
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
        [to_features(row) for row in test_rows], decide, energy_at,
        initial_angle_deg=initial_angle_deg, energy_source=energy_source or "caller-supplied", config=config,
    )


def _step_outcome(state: AgentState) -> StepOutcome:
    safety, decision, modeling = state["safety"], state["decision"], state["modeling"]
    # The angle a raw-energy tracker would pick: highest predicted kWh, lowest angle on ties.
    max_energy = None if modeling is None else min(modeling["candidate_predictions"], key=lambda entry: (-entry["predicted_kwh"], entry["angle_deg"]))
    return StepOutcome(
        action=decision["action"],
        target_angle_deg=decision["target_angle_deg"],
        safety_passed=safety["passed"],
        severe_violation=any(not check["passed"] and check["severity"] == "SEVERE" for check in safety["checks"]),
        max_energy_angle_deg=None if max_energy is None else max_energy["angle_deg"],
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
