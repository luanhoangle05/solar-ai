"""Owner: Duy. Choose the candidate angle with the highest net benefit.

Net benefit = predicted energy gain over staying - movement cost. The stay
(current) angle is always a candidate with zero movement cost, so the result
is never worse than not moving. Ties: least movement, then lowest angle.
"""

import math
from typing import Sequence

from src.common.config import SimulationConfig
from src.common.schema import CandidatePrediction, OptimizationResult
from src.common.tool_contracts import MovementCost, ToolError
from src.models.cost_simulation import calculate_movement_cost, calculate_net_benefit

# Net benefits closer than this are a tie, so float noise cannot defeat the tie rules.
NET_BENEFIT_TIE_DECIMALS = 9


def generate_candidate_angles(current_angle_deg: float, *, config: SimulationConfig) -> tuple[float, ...]:
    """Configured candidates inside the angle limits, plus the stay angle, ascending."""
    if not math.isfinite(current_angle_deg):
        raise ToolError(f"Current angle must be finite, got {current_angle_deg}")
    configured = {float(angle) for angle in config.candidate_angles_deg if _within_limits(angle, config)}
    return tuple(sorted({float(current_angle_deg), *configured}))


def optimize_angle(predictions: Sequence[CandidatePrediction], current_angle_deg: float, *, config: SimulationConfig) -> OptimizationResult:
    """Pick the max-net-benefit candidate; requires a prediction for the stay angle."""
    by_angle = _validated_predictions(predictions)
    if current_angle_deg not in by_angle:
        raise ToolError(f"Missing stay prediction for the current angle {current_angle_deg}; cannot compute a baseline")
    baseline_kwh = by_angle[current_angle_deg]
    options = [
        _evaluate_candidate(angle, predicted_kwh, current_angle_deg, baseline_kwh, config)
        for angle, predicted_kwh in by_angle.items()
        if angle == current_angle_deg or _within_limits(angle, config)
    ]
    return min(options, key=_preference)


def _evaluate_candidate(angle_deg: float, predicted_kwh: float, current_angle_deg: float, baseline_kwh: float, config: SimulationConfig) -> OptimizationResult:
    energy_gain_kwh = predicted_kwh - baseline_kwh
    cost = calculate_movement_cost(current_angle_deg, angle_deg, config=config)["movement_cost_kwh_equivalent"]
    return {
        "current_angle_deg": current_angle_deg,
        "recommended_angle_deg": angle_deg,
        "baseline_kwh": baseline_kwh,
        "predicted_kwh": predicted_kwh,
        "energy_gain_kwh": energy_gain_kwh,
        "movement_cost_kwh_equivalent": cost,
        "net_benefit_kwh_equivalent": calculate_net_benefit(energy_gain_kwh, cost),
    }


def _preference(option: OptimizationResult) -> tuple[float, float, float]:
    """Sort key: highest net benefit, then least movement, then lowest angle."""
    movement = abs(option["recommended_angle_deg"] - option["current_angle_deg"])
    return (-round(option["net_benefit_kwh_equivalent"], NET_BENEFIT_TIE_DECIMALS), movement, option["recommended_angle_deg"])


def _validated_predictions(predictions: Sequence[CandidatePrediction]) -> dict[float, float]:
    if not predictions:
        raise ToolError("No candidate predictions to optimize")
    by_angle = {entry["angle_deg"]: entry["predicted_kwh"] for entry in predictions}
    if len(by_angle) != len(predictions):
        raise ToolError("Duplicate candidate angle in predictions")
    for angle, predicted_kwh in by_angle.items():
        if not (math.isfinite(angle) and math.isfinite(predicted_kwh) and predicted_kwh >= 0):
            raise ToolError(f"Candidate {angle} needs a finite, nonnegative predicted kWh, got {predicted_kwh}")
    return by_angle


def _within_limits(angle_deg: float, config: SimulationConfig) -> bool:
    return config.min_angle_deg <= angle_deg <= config.max_angle_deg


class DeterministicOptimizationTools:
    """`OptimizationTools` implementation backed by the functions in this package."""

    def generate_candidate_angles(self, current_angle_deg: float, *, config: SimulationConfig) -> tuple[float, ...]:
        return generate_candidate_angles(current_angle_deg, config=config)

    def calculate_movement_cost(self, current_angle_deg: float, target_angle_deg: float, *, config: SimulationConfig) -> MovementCost:
        return calculate_movement_cost(current_angle_deg, target_angle_deg, config=config)

    def calculate_net_benefit(self, energy_gain_kwh: float, movement_cost_kwh_equivalent: float) -> float:
        return calculate_net_benefit(energy_gain_kwh, movement_cost_kwh_equivalent)

    def optimize_angle(self, predictions: list[CandidatePrediction], current_angle_deg: float, *, config: SimulationConfig) -> OptimizationResult:
        return optimize_angle(predictions, current_angle_deg, config=config)
