"""Owner: Duy. Time-aware evaluation and rule-based model selection.

All four models are scored the same way: through the shared `EnergyPredictor`
interface, on the same chronological windows, against the same kWh target.
Selection is a deterministic rule, never an LLM judgement.
"""

from dataclasses import dataclass
import math
from typing import Sequence, TypeVar

from src.common.schema import MODEL_NAMES, Metadata, ModelMetrics, ModelName, WeatherFeatures, WeatherRow
from src.common.tool_contracts import EnergyPredictor, ToolError


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
    predicted = [
        predictor.predict_kwh(to_features(row), (row["panel_angle_deg"],), metadata=metadata)[0]["predicted_kwh"]
        for row in rows
    ]
    return compute_metrics([row[LABEL_COLUMN] for row in rows], predicted)


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
