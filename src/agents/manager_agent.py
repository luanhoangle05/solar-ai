"""Manager / Safety Agent and its deterministic safety tools. Owner: Duy.

Decision priority, applied by rule and never by an LLM:
1. a failed SEVERE check                      -> STOW at the configured stow angle
2. any other failed check, or no optimization -> HOLD at the current angle
3. net benefit <= configured threshold        -> HOLD at the current angle
4. otherwise                                  -> ROTATE to the recommended angle

These are PROTOTYPE SIMULATION rules. `send_control_command` is simulation-only;
no hardware command exists in this codebase.
"""

import math
from typing import Callable, TypedDict

from src.agents.trace import Clock, TraceRecorder, utc_now_iso
from src.common.agent_contracts import ManagerAgentUpdate
from src.common.config import SimulationConfig
from src.common.schema import (
    AgentState, DataAgentReport, Decision, ModelMetrics, OptimizationResult,
    SafetyCheck, SafetyResult, WeatherFeatures,
)
from src.common.tool_contracts import ControlReceipt, SafetyTools, ToolError


AGENT_NAME = "manager"
SEVERE = "SEVERE"
BLOCK_ROTATE = "BLOCK_ROTATE"
RELIABLE_DATA_STATUSES = ("VALID", "DEGRADED")
MOVABLE_PANEL_STATES = ("READY", "STOWED")
SIMULATION_MODE = "SIMULATION"


class RowStatus(TypedDict):
    """Observed snapshot of the controlled row, supplied by whoever owns the farm view."""

    angle_deg: float
    current_state: str


RowStatusLookup = Callable[[str], RowStatus]


def _check(name: str, passed: bool, severity: str, reason: str) -> SafetyCheck:
    return {"name": name, "passed": passed, "severity": severity, "reason": reason}


class DeterministicSafetyTools:
    """`SafetyTools` implementation: pure threshold checks against `SimulationConfig`."""

    def check_wind_safety(self, weather: WeatherFeatures, *, config: SimulationConfig) -> SafetyCheck:
        wind, gust = weather["wind_speed_kmh"], weather["wind_gust_kmh"]
        if not (math.isfinite(wind) and math.isfinite(gust)):
            return _check("wind_safety", False, SEVERE, f"Wind reading is not a finite number (wind {wind}, gust {gust})")
        if wind > config.max_wind_speed_kmh:
            return _check("wind_safety", False, SEVERE, f"Wind {wind:g} km/h exceeds the {config.max_wind_speed_kmh:g} km/h limit")
        if gust > config.max_wind_gust_kmh:
            return _check("wind_safety", False, SEVERE, f"Gust {gust:g} km/h exceeds the {config.max_wind_gust_kmh:g} km/h limit")
        return _check("wind_safety", True, SEVERE, f"Wind {wind:g} km/h and gust {gust:g} km/h are within limits ({config.max_wind_speed_kmh:g}/{config.max_wind_gust_kmh:g})")

    def check_angle_limits(self, angle_deg: float, *, config: SimulationConfig) -> SafetyCheck:
        within = math.isfinite(angle_deg) and config.min_angle_deg <= angle_deg <= config.max_angle_deg
        relation = "is within" if within else "is outside"
        return _check("angle_limits", within, SEVERE, f"Target angle {angle_deg:g} deg {relation} [{config.min_angle_deg:g}, {config.max_angle_deg:g}] deg")

    def check_data_freshness(self, data: DataAgentReport, *, config: SimulationConfig) -> SafetyCheck:
        age = data["forecast_age_minutes"]
        if data["status"] not in RELIABLE_DATA_STATUSES:
            return _check("data_freshness", False, BLOCK_ROTATE, f"Data status is {data['status']}: {'; '.join(data['issues']) or 'no detail given'}")
        if age is None or not math.isfinite(age) or age < 0:
            return _check("data_freshness", False, BLOCK_ROTATE, f"Forecast age is unknown or invalid ({age})")
        if age > config.max_forecast_age_minutes:
            return _check("data_freshness", False, BLOCK_ROTATE, f"Forecast is {age:g} min old; limit is {config.max_forecast_age_minutes:g} min")
        return _check("data_freshness", True, BLOCK_ROTATE, f"Data is {data['status']} and {age:g} min old (limit {config.max_forecast_age_minutes:g} min)")

    def check_panel_status(self, panel_state: str) -> SafetyCheck:
        movable = panel_state in MOVABLE_PANEL_STATES
        consequence = "can accept a command" if movable else "cannot accept a new command"
        return _check("panel_status", movable, BLOCK_ROTATE, f"Row state {panel_state} {consequence}")

    def check_model_confidence(self, metrics: ModelMetrics) -> SafetyCheck:
        """Availability only: no confidence score is derived from R2 or any other metric."""
        evaluated = metrics["status"] != "UNAVAILABLE" and all(metrics[key] is not None for key in ("mae", "rmse", "r2"))
        if not evaluated:
            return _check("model_confidence", False, BLOCK_ROTATE, f"Model {metrics['model']} has no evaluation metrics")
        return _check("model_confidence", True, BLOCK_ROTATE, f"Model {metrics['model']} was evaluated (validation RMSE {metrics['rmse']:.4g} kWh, status {metrics['status']})")

    def apply_safety_rules(self, checks: list[SafetyCheck], optimization: OptimizationResult | None, *, current_angle_deg: float, config: SimulationConfig) -> tuple[SafetyResult, Decision]:
        if not checks:
            raise ToolError("No safety checks were run; refusing to decide")
        failed = [check for check in checks if not check["passed"]]
        severe = [check for check in failed if check["severity"] == SEVERE]
        if severe:
            decision = _decision("STOW", config.stow_angle_deg, f"Severe safety violation: {_reasons(severe)}. Stowing at {config.stow_angle_deg:g} deg.")
        elif failed:
            decision = _decision("HOLD", current_angle_deg, f"Holding at {current_angle_deg:g} deg because a check failed: {_reasons(failed)}.")
        elif optimization is None:
            decision = _decision("HOLD", current_angle_deg, f"Holding at {current_angle_deg:g} deg: no optimization result is available.")
        else:
            decision = _economic_decision(optimization, current_angle_deg, config)
        summary = _reasons(failed) if failed else f"All {len(checks)} safety checks passed"
        return {"passed": not failed, "checks": list(checks), "reason": summary}, decision

    def send_control_command(self, decision: Decision, safety: SafetyResult, *, control_target_id: str, simulation_only: bool = True) -> ControlReceipt:
        if not simulation_only:
            raise NotImplementedError("Hardware dispatch is not implemented; commands are simulation-only")
        if decision["action"] == "ROTATE" and not safety["passed"]:
            return {"accepted": False, "mode": SIMULATION_MODE, "reason": "Rejected: ROTATE without a passing safety report"}
        return {
            "accepted": True,
            "mode": SIMULATION_MODE,
            "reason": f"Simulated {decision['action']} for {control_target_id} to {decision['target_angle_deg']:g} deg; no hardware moved",
        }


def _economic_decision(optimization: OptimizationResult, current_angle_deg: float, config: SimulationConfig) -> Decision:
    net, threshold = optimization["net_benefit_kwh_equivalent"], config.min_net_benefit_kwh_equivalent
    recommended = optimization["recommended_angle_deg"]
    if recommended == current_angle_deg:
        return _decision("HOLD", current_angle_deg, f"Holding at {current_angle_deg:g} deg: staying has the best net benefit.")
    # A move must always pay for itself, even if a config sets a negative threshold.
    if not net > max(threshold, 0.0):
        return _decision("HOLD", current_angle_deg, f"Holding at {current_angle_deg:g} deg: best net benefit {net:+.4f} kWh-eq does not exceed the {threshold:g} kWh-eq threshold.")
    return _decision("ROTATE", recommended, f"Rotate to {recommended:g} deg: net benefit {net:+.4f} kWh-eq exceeds the {threshold:g} kWh-eq threshold and all safety checks passed.")


def _decision(action: str, target_angle_deg: float, reason: str) -> Decision:
    return {"action": action, "target_angle_deg": float(target_angle_deg), "reason": reason}


def _reasons(checks: list[SafetyCheck]) -> str:
    return "; ".join(f"{check['name']}: {check['reason']}" for check in checks)


class ManagerAgent:
    def __init__(self, tools: SafetyTools, config: SimulationConfig, *, row_status: RowStatusLookup | None = None, clock: Clock = utc_now_iso) -> None:
        self.tools, self.config, self._row_status, self._clock = tools, config, row_status, clock

    def run(self, state: AgentState) -> ManagerAgentUpdate:
        """Run every available check, then let the rule tool decide. Returns `safety` and `decision` only."""
        if self.tools is None:
            raise NotImplementedError("Manager / Safety Agent has no tools configured")
        recorder = TraceRecorder(AGENT_NAME, self._clock)
        target_id = state["metadata"]["control_target_id"]
        try:
            row = self._observe_row(target_id)
            current_angle = self._current_angle(state, row)
            checks = self._run_checks(recorder, state, row, current_angle)
            safety, decision = recorder.call(
                "apply_safety_rules",
                lambda: self.tools.apply_safety_rules(checks, state["optimization"], current_angle_deg=current_angle, config=self.config),
                lambda result: f"{result[1]['action']} at {result[1]['target_angle_deg']:g} deg",
            )
            recorder.log("safety", safety["reason"])
            recorder.log("decision", decision["reason"])
            receipt = recorder.call(
                "send_control_command",
                lambda: self.tools.send_control_command(decision, safety, control_target_id=target_id, simulation_only=True),
                lambda result: result["reason"],
            )
            recorder.log("dispatch", f"{receipt['mode']}: {receipt['reason']}")
        except ToolError as exc:
            raise recorder.fail("SAFETY_FAILED", f"Safety evaluation failed; no command issued: {exc}") from exc
        return {"safety": safety, "decision": decision, **recorder.trace()}

    def _observe_row(self, target_id: str) -> RowStatus | None:
        if self._row_status is None:
            return None
        try:
            return self._row_status(target_id)
        except Exception as exc:
            raise ToolError(f"Row status lookup failed for {target_id}: {exc!r}") from exc

    @staticmethod
    def _current_angle(state: AgentState, row: RowStatus | None) -> float:
        """The observed angle (row snapshot first); never assumed when no source reports it."""
        if row is not None:
            return row["angle_deg"]
        if state["weather"] is not None:
            return state["weather"]["panel_angle_deg"]
        raise ToolError("Current row angle is unknown: no weather features and no row status source")

    @staticmethod
    def _angle_consistency(state: AgentState, current_angle: float) -> SafetyCheck:
        """Gain and cost are only meaningful if every stage started from the observed angle."""
        weather, optimization = state["weather"], state["optimization"]
        assumed = {
            "weather features": None if weather is None else weather["panel_angle_deg"],
            "optimization": None if optimization is None else optimization["current_angle_deg"],
        }
        mismatched = [f"{source} assumed {angle:g} deg" for source, angle in assumed.items() if angle is not None and angle != current_angle]
        if mismatched:
            return _check("angle_consistency", False, BLOCK_ROTATE, f"Observed row angle is {current_angle:g} deg but {'; '.join(mismatched)}")
        return _check("angle_consistency", True, BLOCK_ROTATE, f"All stages used the observed row angle {current_angle:g} deg")

    def _run_checks(self, recorder: TraceRecorder, state: AgentState, row: RowStatus | None, current_angle: float) -> list[SafetyCheck]:
        weather, data, modeling, optimization = state["weather"], state["data"], state["modeling"], state["optimization"]
        target_angle = current_angle if optimization is None else optimization["recommended_angle_deg"]
        checks = [
            _check("wind_safety", False, BLOCK_ROTATE, "Weather is unavailable; wind cannot be verified") if weather is None
            else self._call_check(recorder, "check_wind_safety", lambda: self.tools.check_wind_safety(weather, config=self.config)),
            self._call_check(recorder, "check_angle_limits", lambda: self.tools.check_angle_limits(target_angle, config=self.config)),
            _check("data_freshness", False, BLOCK_ROTATE, "Data Agent report is unavailable") if data is None
            else self._call_check(recorder, "check_data_freshness", lambda: self.tools.check_data_freshness(data, config=self.config)),
        ]
        checks.append(self._angle_consistency(state, current_angle))
        if row is None:
            recorder.log("panel_status", "Check not run: no row status source is configured for this run")
        else:
            checks.append(self._call_check(recorder, "check_panel_status", lambda: self.tools.check_panel_status(row["current_state"])))
        selected = None if modeling is None else next(
            (entry for entry in modeling["model_comparison"] if entry["model"] == modeling["selected_model"]), None
        )
        if selected is None:
            checks.append(_check("model_confidence", False, BLOCK_ROTATE, "No model output is available"))
        else:
            checks.append(self._call_check(recorder, "check_model_confidence", lambda: self.tools.check_model_confidence(selected)))
        return checks

    @staticmethod
    def _call_check(recorder: TraceRecorder, tool: str, run: Callable[[], SafetyCheck]) -> SafetyCheck:
        return recorder.call(tool, run, lambda check: f"{'passed' if check['passed'] else 'FAILED'} ({check['severity']}): {check['reason']}")
