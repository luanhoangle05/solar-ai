"""Modeling Agent. Owner: Duy.

Coordinates the modeling tools: compare the four contract models, select one
by rule, and predict energy for every candidate angle including the stay angle.
"""

import math

from src.agents.reasoning import Reasoner
from src.agents.trace import Clock, TraceRecorder, utc_now_iso
from src.common.agent_contracts import ModelingAgentUpdate
from src.common.config import SimulationConfig
from src.common.schema import MODEL_NAMES, AgentState, CandidatePrediction, ModelMetrics
from src.common.tool_contracts import ModelingTools, ToolError
from src.models.evaluation import selection_reason
from src.models.optimizer import generate_candidate_angles


AGENT_NAME = "modeling"


class ModelingAgent:
    def __init__(self, tools: ModelingTools, config: SimulationConfig, *, clock: Clock = utc_now_iso, reasoner: Reasoner | None = None) -> None:
        self.tools, self.config, self._clock, self._reasoner = tools, config, clock, reasoner

    def run(self, state: AgentState) -> ModelingAgentUpdate:
        """Return only the `modeling` section; raise StageError rather than invent output."""
        if self.tools is None:
            raise NotImplementedError("Modeling Agent has no tools configured")
        recorder = TraceRecorder(AGENT_NAME, self._clock)
        weather = state["weather"]
        if weather is None:
            raise recorder.fail("MODELING_INPUT_UNAVAILABLE", "Cannot predict: weather features are unavailable")
        try:
            comparison = recorder.call("evaluate_models", self.tools.evaluate_models, _describe_comparison)
            _require_four_models(comparison)
            recorder.log("comparison", _describe_comparison(comparison))
            selected = recorder.call("select_best_model", lambda: self.tools.select_best_model(comparison), lambda model: f"selected {model}")
            chosen = _selected_entry(comparison, selected)
            recorder.log("selection", selection_reason(comparison, selected))
            predictor = recorder.call("get_predictor", lambda: self.tools.get_predictor(selected), lambda _: f"{chosen['implementation']} adapter ready")
            angles = generate_candidate_angles(weather["panel_angle_deg"], config=self.config)
            predictions = recorder.call(
                "predict_kwh",
                lambda: predictor.predict_kwh(weather, angles, metadata=state["metadata"]),
                lambda result: f"{len(result)} candidate predictions",
            )
            _require_valid_predictions(predictions, angles)
        except ToolError as exc:
            raise recorder.fail("MODELING_FAILED", f"Modeling tool failed: {exc}") from exc
        recorder.log("prediction", _describe_predictions(predictions, weather["panel_angle_deg"]))
        modeling = {
            "selected_model": selected,
            "mae": chosen["mae"],
            "rmse": chosen["rmse"],
            "r2": chosen["r2"],
            "model_comparison": comparison,
            "candidate_predictions": predictions,
        }
        recorder.reason(self._reasoner)
        return {"modeling": modeling, **recorder.trace()}


def _require_four_models(comparison: list[ModelMetrics]) -> None:
    if len(comparison) != len(MODEL_NAMES) or {entry["model"] for entry in comparison} != set(MODEL_NAMES):
        raise ToolError(f"Model comparison must contain exactly {MODEL_NAMES}")


def _selected_entry(comparison: list[ModelMetrics], selected: str) -> ModelMetrics:
    chosen = next((entry for entry in comparison if entry["model"] == selected), None)
    if chosen is None or chosen["status"] == "UNAVAILABLE":
        raise ToolError(f"Selected model {selected!r} has no available metrics")
    return chosen


def _require_valid_predictions(predictions: list[CandidatePrediction], angles: tuple[float, ...]) -> None:
    if [entry["angle_deg"] for entry in predictions] != list(angles):
        raise ToolError("Predictor did not return one prediction per requested angle, in order")
    for entry in predictions:
        if not (math.isfinite(entry["predicted_kwh"]) and entry["predicted_kwh"] >= 0):
            raise ToolError(f"Predictor returned an invalid energy for {entry['angle_deg']:g} deg: {entry['predicted_kwh']}")


def _describe_comparison(comparison: list[ModelMetrics]) -> str:
    # R2 keeps six significant digits: four would print a near-perfect fit as exactly 1.
    parts = [
        f"{entry['model']}: UNAVAILABLE" if entry["status"] == "UNAVAILABLE"
        else f"{entry['model']} ({entry['implementation']}): RMSE {entry['rmse']:.4g}, MAE {entry['mae']:.4g}, R2 {entry['r2']:.6g}"
        for entry in comparison
    ]
    return "Validation-window metrics in kWh. " + "; ".join(parts)


def _describe_predictions(predictions: list[CandidatePrediction], current_angle: float) -> str:
    parts = [f"{entry['angle_deg']:g} deg -> {entry['predicted_kwh']:.3f} kWh" for entry in predictions]
    return f"Predicted row energy for the next hour at {len(predictions)} angles (stay angle {current_angle:g} deg included): " + "; ".join(parts)
