"""Recommendation service. Owner: Duy.

Composes Duy's tools and agents, runs an injected orchestrator, and hands Tung a
payload only after it passes `validate_frontend_data`. The orchestrator itself
(stage lifecycle, farm snapshot, history) is shared team code and is injected.
"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence

from src.agents.manager_agent import DeterministicSafetyTools, ManagerAgent, RowStatusLookup
from src.agents.modeling_agent import ModelingAgent
from src.agents.optimization_agent import OptimizationAgent
from src.agents.trace import Clock, utc_now_iso
from src.common.agent_contracts import OrchestratorContract
from src.common.config import ENERGY_SCOPE, PREDICTION_HORIZON_MINUTES, SCHEMA_VERSION, SimulationConfig
from src.common.schema import MODEL_NAMES, AgentState, FrontendData, Metadata, validate_frontend_data
from src.common.tool_contracts import ToolError
from src.models.advanced import boosting
from src.models.data_loader import DatasetError, DatasetSource, load_weather_rows
from src.models.evaluation import EvaluatedModelingTools, ModelCandidate, chronological_split
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
        supplied[boosting.MODEL_NAME] = _train_boosting_candidate(split.train, split.validation)
    candidates = [
        supplied.get(model) or ModelCandidate(model, DEFAULT_IMPLEMENTATIONS[model], unavailable_reason="adapter not delivered yet")
        for model in MODEL_NAMES
    ]
    return EvaluatedModelingTools(candidates, split.validation, metadata=metadata)


def _train_boosting_candidate(train_rows: Sequence, validation_rows: Sequence) -> ModelCandidate:
    try:
        predictor = boosting.train_boosting(train_rows, validation_rows)
    except ToolError as exc:
        return ModelCandidate(boosting.MODEL_NAME, boosting.IMPLEMENTATION, unavailable_reason=f"training failed: {exc}")
    return ModelCandidate(boosting.MODEL_NAME, boosting.IMPLEMENTATION, predictor=predictor)


def build_agents(modeling_tools: EvaluatedModelingTools, config: SimulationConfig, *, row_status: RowStatusLookup | None = None, clock: Clock = utc_now_iso) -> DuyAgents:
    return DuyAgents(
        modeling=ModelingAgent(modeling_tools, config, clock=clock),
        optimization=OptimizationAgent(DeterministicOptimizationTools(), config, clock=clock),
        manager=ManagerAgent(DeterministicSafetyTools(), config, row_status=row_status, clock=clock),
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
