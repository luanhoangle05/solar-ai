"""Optimization Agent. Owner: Duy.

Coordinates the optimization tools over the Modeling Agent's candidate
predictions and explains the result. Costs, net benefit and the choice come
from the tools; the agent only forms the gain argument they require.
"""

from src.agents.trace import Clock, TraceRecorder, utc_now_iso
from src.common.agent_contracts import OptimizationAgentUpdate
from src.common.config import SimulationConfig
from src.common.schema import AgentState, CandidatePrediction, OptimizationResult
from src.common.tool_contracts import OptimizationTools, ToolError


AGENT_NAME = "optimization"


class OptimizationAgent:
    def __init__(self, tools: OptimizationTools, config: SimulationConfig, *, clock: Clock = utc_now_iso) -> None:
        self.tools, self.config, self._clock = tools, config, clock

    def run(self, state: AgentState) -> OptimizationAgentUpdate:
        """Compare candidates by net benefit and return only the `optimization` section."""
        if self.tools is None:
            raise NotImplementedError("Optimization Agent has no tools configured")
        recorder = TraceRecorder(AGENT_NAME, self._clock)
        weather, modeling = state["weather"], state["modeling"]
        if weather is None or modeling is None:
            raise recorder.fail("OPTIMIZATION_INPUT_UNAVAILABLE", "Cannot optimize: weather or model predictions are unavailable")
        current_angle = weather["panel_angle_deg"]
        predictions = modeling["candidate_predictions"]
        try:
            self._compare_candidates(recorder, predictions, current_angle)
            optimization = recorder.call(
                "optimize_angle",
                lambda: self.tools.optimize_angle(predictions, current_angle, config=self.config),
                lambda result: f"recommended {result['recommended_angle_deg']:g} deg, net benefit {result['net_benefit_kwh_equivalent']:+.4f} kWh-eq",
            )
        except ToolError as exc:
            raise recorder.fail("OPTIMIZATION_FAILED", f"Optimization tool failed: {exc}") from exc
        recorder.log("recommendation", _explain(optimization))
        return {"optimization": optimization, **recorder.trace()}

    def _compare_candidates(self, recorder: TraceRecorder, predictions: list[CandidatePrediction], current_angle: float) -> None:
        """Ask the tools for each candidate's cost and net benefit so the comparison is visible."""
        expected = recorder.call(
            "generate_candidate_angles",
            lambda: self.tools.generate_candidate_angles(current_angle, config=self.config),
            lambda angles: f"{len(angles)} candidates including stay angle {current_angle:g} deg",
        )
        by_angle = {entry["angle_deg"]: entry["predicted_kwh"] for entry in predictions}
        missing = [angle for angle in expected if angle not in by_angle]
        if current_angle not in by_angle:
            raise ToolError(f"Model predictions do not include the stay angle {current_angle:g} deg")
        if missing:
            recorder.log("candidate_coverage", f"No prediction for candidate angles {missing}; comparing the {len(by_angle)} predicted angles")
        baseline = by_angle[current_angle]
        lines = []
        for angle, predicted in sorted(by_angle.items()):
            cost = recorder.call(
                "calculate_movement_cost",
                lambda: self.tools.calculate_movement_cost(current_angle, angle, config=self.config),
                lambda result: f"{angle:g} deg: {result['movement_degrees']:g} deg of travel costs {result['movement_cost_kwh_equivalent']:.4f} kWh-eq",
            )["movement_cost_kwh_equivalent"]
            # The gain is passed as an argument expression; the tool owns the net-benefit formula.
            net = recorder.call(
                "calculate_net_benefit",
                lambda: self.tools.calculate_net_benefit(predicted - baseline, cost),
                lambda result: f"{angle:g} deg: net benefit {result:+.4f} kWh-eq",
            )
            lines.append(f"{angle:g} deg -> {predicted:.3f} kWh, cost {cost:.3f}, net {net:+.3f}")
        recorder.log("candidate_comparison", f"Stay at {current_angle:g} deg predicts {baseline:.3f} kWh. " + "; ".join(lines))


def _explain(optimization: OptimizationResult) -> str:
    current, recommended = optimization["current_angle_deg"], optimization["recommended_angle_deg"]
    if recommended == current:
        return f"Stay at {current:g} deg: no candidate gains more energy than its movement costs."
    return (
        f"Best net benefit is {recommended:g} deg: {optimization['energy_gain_kwh']:+.3f} kWh gain "
        f"- {optimization['movement_cost_kwh_equivalent']:.3f} movement cost = {optimization['net_benefit_kwh_equivalent']:+.3f} kWh-eq "
        f"versus staying at {current:g} deg. The Manager Agent decides whether this clears safety and the threshold."
    )
