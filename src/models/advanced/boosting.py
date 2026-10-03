"""Owner: Duy. XGBoost adapter behind the stable model ID `boosting`."""

from dataclasses import dataclass
from typing import Sequence

import xgboost as xgb

from src.common.schema import FEATURE_COLUMNS, CandidatePrediction, Metadata, WeatherFeatures, WeatherRow
from src.common.tool_contracts import ToolError
from src.models.advanced.features import at_candidate_angles, feature_matrix, label_vector


MODEL_NAME = "boosting"
IMPLEMENTATION = "xgboost"
VALIDATION_SET_NAME = "validation"


@dataclass(frozen=True)
class BoostingConfig:
    """Training hyperparameters; early stopping watches the validation window only."""

    num_boost_round: int = 600
    early_stopping_rounds: int = 40
    max_depth: int = 6
    learning_rate: float = 0.05
    subsample: float = 0.8
    colsample_bytree: float = 0.9
    min_child_weight: float = 2.0
    seed: int = 20261004


DEFAULT_BOOSTING_CONFIG = BoostingConfig()


class BoostingPredictor:
    """`EnergyPredictor` over a trained booster; predictions are clipped at 0 kWh."""

    implementation = IMPLEMENTATION

    def __init__(self, booster: xgb.Booster) -> None:
        self._booster = booster

    def predict_kwh(self, weather: WeatherFeatures, candidate_angles_deg: tuple[float, ...], *, metadata: Metadata) -> list[CandidatePrediction]:
        candidates = at_candidate_angles(weather, candidate_angles_deg)
        try:
            raw = self._booster.predict(_to_dmatrix(candidates), iteration_range=(0, self._booster.best_iteration + 1))
        except xgb.core.XGBoostError as exc:
            raise ToolError(f"Boosting prediction failed: {exc}") from exc
        return [
            {"angle_deg": angle, "predicted_kwh": max(0.0, float(value))}
            for angle, value in zip(candidate_angles_deg, raw)
        ]


def train_boosting(train_rows: Sequence[WeatherRow], validation_rows: Sequence[WeatherRow], config: BoostingConfig = DEFAULT_BOOSTING_CONFIG) -> BoostingPredictor:
    """Fit on the train window; stop early on the validation window. Test rows are never seen."""
    if not train_rows or not validation_rows:
        raise ToolError("Boosting needs non-empty train and validation windows")
    params = {
        "objective": "reg:squarederror",
        "eval_metric": "rmse",
        "tree_method": "hist",
        "max_depth": config.max_depth,
        "eta": config.learning_rate,
        "subsample": config.subsample,
        "colsample_bytree": config.colsample_bytree,
        "min_child_weight": config.min_child_weight,
        "seed": config.seed,
        "nthread": 1,
    }
    try:
        booster = xgb.train(
            params,
            _to_dmatrix(train_rows, label_vector(train_rows)),
            num_boost_round=config.num_boost_round,
            evals=[(_to_dmatrix(validation_rows, label_vector(validation_rows)), VALIDATION_SET_NAME)],
            early_stopping_rounds=config.early_stopping_rounds,
            verbose_eval=False,
        )
    except xgb.core.XGBoostError as exc:
        raise ToolError(f"Boosting training failed: {exc}") from exc
    return BoostingPredictor(booster)


def _to_dmatrix(rows: Sequence[WeatherFeatures], labels=None) -> xgb.DMatrix:
    return xgb.DMatrix(feature_matrix(rows), label=labels, feature_names=list(FEATURE_COLUMNS))
