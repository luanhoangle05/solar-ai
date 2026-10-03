"""Owner: Duy. Time-aware evaluation and rule-based model selection.

All four models are scored the same way: through the shared `EnergyPredictor`
interface, on the same chronological windows, against the same kWh target.
Selection is a deterministic rule, never an LLM judgement.
"""

from dataclasses import dataclass
import math
from typing import Callable, Sequence, TypeVar

from src.common.config import SimulationConfig
from src.common.schema import MODEL_NAMES, Metadata, ModelMetrics, ModelName, WeatherFeatures, WeatherRow
from src.common.tool_contracts import EnergyPredictor, ToolError
from src.models.cost_simulation import calculate_movement_cost, calculate_net_benefit


TRAIN_FRACTION = 0.7
VALIDATION_FRACTION = 0.15
LABEL_COLUMN = "actual_kwh"

Row = TypeVar("Row")


@dataclass(frozen=True)
class RegressionMetrics:
    mae: float
    rmse: float
    r2: float


@dataclass(frozen=True)
class ChronologicalSplit:
    """Consecutive windows of time-ordered rows: train, then validation, then test."""

    train: tuple
    validation: tuple
    test: tuple


def chronological_split(rows: Sequence[Row], *, train_fraction: float = TRAIN_FRACTION, validation_fraction: float = VALIDATION_FRACTION) -> ChronologicalSplit:
    """Split already time-ordered rows without shuffling; later rows never train earlier ones."""
    if not (0 < train_fraction < 1 and 0 < validation_fraction < 1 and train_fraction + validation_fraction < 1):
        raise ValueError(f"Invalid split fraction: train {train_fraction} + validation {validation_fraction} must leave a test window")
    train_end = int(len(rows) * train_fraction)
    validation_end = train_end + int(len(rows) * validation_fraction)
    split = ChronologicalSplit(tuple(rows[:train_end]), tuple(rows[train_end:validation_end]), tuple(rows[validation_end:]))
    if not (split.train and split.validation and split.test):
        raise ValueError(f"Too few rows ({len(rows)}) for train/validation/test windows")
    return split


def compute_metrics(actual: Sequence[float], predicted: Sequence[float]) -> RegressionMetrics:
    """MAE, RMSE and R2 in the units of the target (kWh per row per hour)."""
    if len(actual) != len(predicted):
        raise ValueError(f"Evaluation length mismatch: {len(actual)} targets, {len(predicted)} predictions")
    if not actual:
        raise ValueError("Cannot compute metrics on zero samples")
    if not all(math.isfinite(value) for value in (*actual, *predicted)):
        raise ValueError("Evaluation values must be finite")
    mean = sum(actual) / len(actual)
    total_variation = sum((value - mean) ** 2 for value in actual)
    if total_variation == 0:
        raise ValueError("R2 is undefined for constant targets")
    residuals = [estimate - value for estimate, value in zip(predicted, actual)]
    squared_error = sum(residual ** 2 for residual in residuals)
    return RegressionMetrics(
        mae=sum(abs(residual) for residual in residuals) / len(actual),
        rmse=math.sqrt(squared_error / len(actual)),
        r2=1 - squared_error / total_variation,
    )


def to_features(row: WeatherRow) -> WeatherFeatures:
    """Inference inputs for a labeled row: everything except the label."""
    return {name: value for name, value in row.items() if name != LABEL_COLUMN}


def evaluate_predictor(predictor: EnergyPredictor, rows: Sequence[WeatherRow], *, metadata: Metadata) -> RegressionMetrics:
    """Score one model on labeled rows, each at the panel angle it was recorded at."""
    predicted = [_predict_at_recorded_angle(predictor, row, metadata) for row in rows]
    return compute_metrics([row[LABEL_COLUMN] for row in rows], predicted)


def _predict_at_recorded_angle(predictor: EnergyPredictor, row: WeatherRow, metadata: Metadata) -> float:
    angle = row["panel_angle_deg"]
    try:
        (entry,) = predictor.predict_kwh(to_features(row), (angle,), metadata=metadata)
        predicted_angle, predicted_kwh = entry["angle_deg"], float(entry["predicted_kwh"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ToolError(f"Predictor returned a malformed result at {row['timestamp']}: {exc!r}") from exc
    if predicted_angle != angle or not math.isfinite(predicted_kwh) or predicted_kwh < 0:
        raise ToolError(f"Predictor returned an invalid prediction at {row['timestamp']}: {entry}")
    return predicted_kwh


def build_model_metrics(model: ModelName, implementation: str, metrics: RegressionMetrics, *, dataset_kind: str) -> ModelMetrics:
    """Computed metrics; on mock/example data they are labeled MOCK, not VALIDATED."""
    status = "MOCK" if dataset_kind == "MOCK" else "VALIDATED"
    return {"model": model, "implementation": implementation, "status": status, "mae": metrics.mae, "rmse": metrics.rmse, "r2": metrics.r2}


def unavailable_model_metrics(model: ModelName, *, implementation: str) -> ModelMetrics:
    """A model that could not be trained or evaluated: null metrics, never zeros."""
    return {"model": model, "implementation": implementation, "status": "UNAVAILABLE", "mae": None, "rmse": None, "r2": None}


def select_best_model(comparison: Sequence[ModelMetrics]) -> ModelName:
    """Lowest validation RMSE among available models; ties go to the earlier model in MODEL_NAMES."""
    available = _available(comparison)
    if not available:
        raise ToolError("No model is available for selection")
    return min(available, key=lambda entry: (entry["rmse"], MODEL_NAMES.index(entry["model"])))["model"]


def selection_reason(comparison: Sequence[ModelMetrics], selected: ModelName) -> str:
    chosen = next(entry for entry in comparison if entry["model"] == selected)
    return (
        f"Selected {selected} ({chosen['implementation']}): lowest validation RMSE {chosen['rmse']:.4g} kWh "
        f"among {len(_available(comparison))} of {len(comparison)} available models; ties resolve in the order {', '.join(MODEL_NAMES)}."
    )


@dataclass(frozen=True)
class ModelCandidate:
    """One of the four contract models: a trained adapter, or the reason there is none."""

    model: ModelName
    implementation: str
    predictor: EnergyPredictor | None = None
    unavailable_reason: str | None = None


class EvaluatedModelingTools:
    """`ModelingTools` over trained adapters, scored on one shared validation window.

    Luan's baselines and Duy's advanced models plug in through the same
    `EnergyPredictor` interface. A model that is missing or fails evaluation is
    reported UNAVAILABLE with null metrics; it is never given invented numbers.
    """

    def __init__(self, candidates: Sequence[ModelCandidate], validation_rows: Sequence[WeatherRow], *, metadata: Metadata) -> None:
        by_model = {candidate.model: candidate for candidate in candidates}
        if len(by_model) != len(candidates) or set(by_model) != set(MODEL_NAMES):
            raise ValueError(f"Expected exactly one candidate for each of {MODEL_NAMES}")
        self._candidates = by_model
        self._validation_rows = tuple(validation_rows)
        self._metadata = metadata
        self._unavailable_reasons: dict[ModelName, str] = {}
        self._comparison: tuple[ModelMetrics, ...] | None = None

    def evaluate_models(self) -> list[ModelMetrics]:
        """Score every model once; the trained adapters and the window do not change afterwards."""
        if self._comparison is None:
            self._comparison = tuple(self._evaluate(self._candidates[model]) for model in MODEL_NAMES)
        return [dict(entry) for entry in self._comparison]

    def select_best_model(self, comparison: list[ModelMetrics]) -> ModelName:
        return select_best_model(comparison)

    def get_predictor(self, model: ModelName) -> EnergyPredictor:
        candidate = self._candidates.get(model)
        if candidate is None or candidate.predictor is None:
            raise ToolError(f"No predictor available for model {model!r}")
        return candidate.predictor

    def unavailable_reasons(self) -> dict[ModelName, str]:
        """Why each unavailable model has no metrics, as found by the last evaluation."""
        return dict(self._unavailable_reasons)

    def _evaluate(self, candidate: ModelCandidate) -> ModelMetrics:
        if candidate.predictor is None:
            return self._unavailable(candidate, candidate.unavailable_reason or "no adapter supplied")
        try:
            metrics = evaluate_predictor(candidate.predictor, self._validation_rows, metadata=self._metadata)
        except (ToolError, ValueError) as exc:
            return self._unavailable(candidate, f"evaluation failed: {exc}")
        self._unavailable_reasons.pop(candidate.model, None)
        return build_model_metrics(candidate.model, candidate.implementation, metrics, dataset_kind=self._metadata["dataset_kind"])

    def _unavailable(self, candidate: ModelCandidate, reason: str) -> ModelMetrics:
        self._unavailable_reasons[candidate.model] = reason
        return unavailable_model_metrics(candidate.model, implementation=candidate.implementation)


def _available(comparison: Sequence[ModelMetrics]) -> list[ModelMetrics]:
    return [entry for entry in comparison if entry["status"] != "UNAVAILABLE" and entry["rmse"] is not None]


@dataclass(frozen=True)
class StepOutcome:
    """What the decision pipeline concluded for one hour."""

    action: str
    target_angle_deg: float
    safety_passed: bool
    severe_violation: bool
    raw_energy_gain_kwh: float | None
    stage_failed: bool = False


@dataclass(frozen=True)
class SystemEvaluation:
    """Replay totals in kWh-equivalent for one row. `energy_source` says where the kWh come from."""

    hours: int
    energy_source: str
    baseline_kwh: float
    optimized_kwh: float
    energy_gain_kwh: float
    movement_cost_kwh_equivalent: float
    net_benefit_kwh_equivalent: float
    rotate_count: int
    hold_count: int
    stow_count: int
    unnecessary_moves_avoided: int
    severe_safety_events: int
    unsafe_rotations: int
    error_hours: int


@dataclass(frozen=True)
class _Step:
    outcome: StepOutcome
    angle_before_deg: float
    angle_after_deg: float
    baseline_kwh: float
    optimized_kwh: float
    movement_cost_kwh_equivalent: float


def evaluate_system(
    weather_rows: Sequence[WeatherFeatures],
    decide: Callable[[WeatherFeatures], StepOutcome],
    energy_at: Callable[[WeatherFeatures, float], float],
    *,
    initial_angle_deg: float,
    energy_source: str,
    config: SimulationConfig,
) -> SystemEvaluation:
    """Replay the decision pipeline hour by hour against a row that never moves.

    Baseline: the row stays at `initial_angle_deg` for every hour. Optimized: the
    row follows each decision (ROTATE and STOW move it and pay movement cost; the
    move is treated as instantaneous at the start of the hour). The baseline
    never stows, so storm hours cost the optimized row energy by design.

    An unnecessary move avoided is a HOLD hour with passing safety in which a
    tracker that ignores movement cost would still have moved: the best
    candidate's predicted energy gain exceeded `min_net_benefit_kwh_equivalent`.
    `error_hours` counts hours where a stage failed and the decision is a
    fallback; a replay with error hours is not a clean measurement.
    """
    steps: list[_Step] = []
    angle = initial_angle_deg
    for weather in weather_rows:
        outcome = decide({**weather, "panel_angle_deg": angle})
        angle_after = outcome.target_angle_deg if outcome.action in ("ROTATE", "STOW") else angle
        steps.append(_Step(
            outcome=outcome,
            angle_before_deg=angle,
            angle_after_deg=angle_after,
            baseline_kwh=energy_at(weather, initial_angle_deg),
            optimized_kwh=energy_at(weather, angle_after),
            movement_cost_kwh_equivalent=calculate_movement_cost(angle, angle_after, config=config)["movement_cost_kwh_equivalent"],
        ))
        angle = angle_after
    baseline = sum(step.baseline_kwh for step in steps)
    optimized = sum(step.optimized_kwh for step in steps)
    movement_cost = sum(step.movement_cost_kwh_equivalent for step in steps)
    return SystemEvaluation(
        hours=len(steps),
        energy_source=energy_source,
        baseline_kwh=baseline,
        optimized_kwh=optimized,
        energy_gain_kwh=optimized - baseline,
        movement_cost_kwh_equivalent=movement_cost,
        net_benefit_kwh_equivalent=calculate_net_benefit(optimized - baseline, movement_cost),
        rotate_count=_count(steps, "ROTATE"),
        hold_count=_count(steps, "HOLD"),
        stow_count=_count(steps, "STOW"),
        unnecessary_moves_avoided=sum(1 for step in steps if _avoided_move(step.outcome, config)),
        severe_safety_events=sum(1 for step in steps if step.outcome.severe_violation),
        unsafe_rotations=sum(1 for step in steps if step.outcome.action == "ROTATE" and not step.outcome.safety_passed),
        error_hours=sum(1 for step in steps if step.outcome.stage_failed),
    )


def _count(steps: Sequence[_Step], action: str) -> int:
    return sum(1 for step in steps if step.outcome.action == action)


def _avoided_move(outcome: StepOutcome, config: SimulationConfig) -> bool:
    raw_gain = outcome.raw_energy_gain_kwh
    wanted_to_move = raw_gain is not None and raw_gain > config.min_net_benefit_kwh_equivalent
    return outcome.action == "HOLD" and outcome.safety_passed and wanted_to_move
