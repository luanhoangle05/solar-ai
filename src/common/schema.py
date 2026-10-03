"""Versioned JSON/CSV contracts and dependency-free boundary validation.

No model, optimization, safety controller, or API implementation lives here.
TypedDict definitions are the source of field names for runtime validation.
"""

from datetime import datetime
import math
import types
from typing import Literal, TypedDict, Union, get_args, get_origin, get_type_hints

from src.common.config import (
    DEFAULT_CONFIG, PANELS_PER_ROW, PREDICTION_HORIZON_MINUTES, ROW_COUNT,
    SCHEMA_VERSION, TOTAL_PANELS, ZONE_ROW_COUNTS,
)

Action = Literal["ROTATE", "HOLD", "STOW"]
ModelName = Literal["linear_regression", "random_forest", "boosting", "lstm"]
AgentName = Literal["data", "modeling", "optimization", "manager"]
DataStatus = Literal["VALID", "DEGRADED", "STALE", "INVALID"]
MODEL_NAMES = get_args(ModelName)


class CurrentWeather(TypedDict):
    temperature_c: float
    cloud_cover_pct: float
    precipitation_mm: float
    wind_speed_kmh: float
    wind_gust_kmh: float
    ghi_wm2: float
    dni_wm2: float
    dhi_wm2: float


class WeatherFeatures(CurrentWeather):
    """Inference inputs omit the target; hour/day_of_year derive from timestamp."""

    timestamp: str
    sun_elevation_deg: float
    sun_azimuth_deg: float
    panel_angle_deg: float


class WeatherRow(WeatherFeatures):
    """Luan -> Duy; actual_kwh is the label, never an inference feature."""

    actual_kwh: float


WEATHER_COLUMNS = ("timestamp", *(name for name in get_type_hints(WeatherRow) if name != "timestamp"))
FEATURE_COLUMNS = tuple(name for name in WEATHER_COLUMNS if name not in ("timestamp", "actual_kwh"))


class Metadata(TypedDict):
    schema_version: str
    dataset_kind: Literal["MOCK", "LIVE"]
    label_source: Literal["mock", "measured", "physics-derived", "unavailable"]
    energy_scope: Literal["row"]
    prediction_horizon_minutes: int
    interval_start: str
    control_target_id: str
    config_id: str
    assumptions: list[str]


class DataAgentReport(TypedDict):
    status: DataStatus
    source: str
    forecast_age_minutes: float | None
    used_cache: bool
    issues: list[str]


class ModelMetrics(TypedDict):
    model: ModelName
    implementation: str
    status: Literal["MOCK", "VALIDATED", "UNAVAILABLE"]
    mae: float | None
    rmse: float | None
    r2: float | None


class CandidatePrediction(TypedDict):
    angle_deg: float
    predicted_kwh: float


class ModelingResult(TypedDict):
    selected_model: ModelName
    mae: float
    rmse: float
    r2: float
    model_comparison: list[ModelMetrics]
    candidate_predictions: list[CandidatePrediction]


class EvaluationFixture(TypedDict):
    """Synthetic targets/predictions backing illustrative metrics; no training."""

    actual_kwh: list[float]
    linear_regression: list[float]
    random_forest: list[float]
    boosting: list[float]
    lstm: list[float]


class ModelOutput(TypedDict):
    timestamp: str
    metadata: Metadata
    modeling: ModelingResult
    evaluation_fixture: EvaluationFixture


class OptimizationResult(TypedDict):
    current_angle_deg: float
    recommended_angle_deg: float
    baseline_kwh: float
    predicted_kwh: float
    energy_gain_kwh: float
    movement_cost_kwh_equivalent: float
    net_benefit_kwh_equivalent: float


class SafetyCheck(TypedDict):
    name: str
    passed: bool
    severity: Literal["INFO", "BLOCK_ROTATE", "SEVERE"]
    reason: str


class SafetyResult(TypedDict):
    passed: bool
    checks: list[SafetyCheck]
    reason: str


class Decision(TypedDict):
    action: Action
    target_angle_deg: float
    reason: str


class FarmZone(TypedDict):
    zone_id: str
    row_ids: list[str]
    panel_count: int


class FarmRow(TypedDict):
    row_id: str
    zone_id: str
    panel_count: int
    angle_deg: float
    current_state: Literal["READY", "MOVING", "STOWED", "FAULT"]
    action: Action


class FarmStatus(TypedDict):
    total_panels: int
    zones: list[FarmZone]
    rows: list[FarmRow]


class AgentLogEntry(TypedDict):
    timestamp: str
    agent: AgentName
    action: str
    result: str


class ToolCall(TypedDict):
    timestamp: str
    agent: AgentName
    tool: str
    status: Literal["OK", "ERROR"]
    detail: str


class RunError(TypedDict):
    agent: AgentName
    code: str
    message: str


class HistoricalDecision(TypedDict):
    timestamp: str
    control_target_id: str
    decision: Decision
    net_benefit_kwh_equivalent: float


class FrontendData(TypedDict):
    timestamp: str
    metadata: Metadata
    current_weather: CurrentWeather | None
    data_agent: DataAgentReport
    model_comparison: list[ModelMetrics]
    selected_model: ModelName | None
    candidate_predictions: list[CandidatePrediction]
    optimization: OptimizationResult | None
    safety: SafetyResult
    decision: Decision
    farm_status: FarmStatus
    agent_log: list[AgentLogEntry]
    history: list[HistoricalDecision]
    errors: list[RunError]


class AgentState(TypedDict):
    """Unrun stages are null, not invented successes or zero predictions.

    Orchestrator owns lifecycle, logs, errors, and merging stage return values.
    """

    run_id: str
    timestamp: str
    metadata: Metadata
    stage: Literal["PENDING", "DATA", "MODELING", "OPTIMIZATION", "SAFETY", "COMPLETE", "FAILED"]
    weather: WeatherFeatures | None
    data: DataAgentReport | None
    modeling: ModelingResult | None
    optimization: OptimizationResult | None
    safety: SafetyResult | None
    decision: Decision | None
    agent_log: list[AgentLogEntry]
    tool_calls: list[ToolCall]
    errors: list[RunError]


class ContractError(ValueError):
    """Malformed or internally inconsistent contract payload."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _shape(value: object, expected: object, path: str = "payload") -> None:
    """Strict typed shape, including unknown keys, nullability and finite floats."""
    origin = get_origin(expected)
    args = get_args(expected)
    if origin in (Union, types.UnionType):
        for option in args:
            try:
                _shape(value, option, path)
                return
            except ContractError:
                pass
        raise ContractError(f"{path}: does not match {expected}")
    if origin is Literal:
        _require(value in args, f"{path}: expected one of {args}")
    elif origin is list:
        _require(isinstance(value, list), f"{path}: expected list")
        for index, item in enumerate(value):
            _shape(item, args[0], f"{path}[{index}]")
    elif hasattr(expected, "__required_keys__"):
        _require(isinstance(value, dict), f"{path}: expected object")
        fields = get_type_hints(expected)
        _require(set(value) == set(fields), f"{path}: missing/unknown fields: {set(value) ^ set(fields)}")
        for key, field_type in fields.items():
            _shape(value[key], field_type, f"{path}.{key}")
    elif expected is float:
        _require(type(value) in (int, float) and math.isfinite(value), f"{path}: expected finite number")
    elif expected is type(None):
        _require(value is None, f"{path}: expected null")
    else:
        _require(type(value) is expected, f"{path}: expected {expected}")


def _timestamp(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"Invalid timestamp: {value}") from exc
    _require(parsed.utcoffset() is not None, "Timestamps must include a timezone")


def _metadata(value: Metadata) -> None:
    _require(value["schema_version"] == SCHEMA_VERSION, "Unsupported schema version")
    _require(value["prediction_horizon_minutes"] == PREDICTION_HORIZON_MINUTES, "Expected one-hour energy interval")
    _require(bool(value["control_target_id"]), "Missing control target")
    _require(bool(value["config_id"]), "Missing config identifier")
    _timestamp(value["interval_start"])
    if value["dataset_kind"] == "MOCK":
        _require(value["label_source"] == "mock", "Mock fixtures must be labeled mock")
    else:
        _require(value["label_source"] != "mock", "Live payload cannot have mock labels")


def _weather(value: dict) -> None:
    for key in ("precipitation_mm", "wind_speed_kmh", "wind_gust_kmh", "ghi_wm2", "dni_wm2", "dhi_wm2"):
        _require(value[key] >= 0, f"{key} cannot be negative")
    _require(0 <= value["cloud_cover_pct"] <= 100, "Cloud cover outside [0, 100]")
    _require(value["wind_gust_kmh"] >= value["wind_speed_kmh"], "Gust below sustained wind")
    if "sun_elevation_deg" in value:
        _require(-90 <= value["sun_elevation_deg"] <= 90, "Invalid sun elevation")
        _require(0 <= value["sun_azimuth_deg"] < 360, "Invalid sun azimuth")
        _require(0 <= value["panel_angle_deg"] <= 90, "Invalid panel tilt")
        _timestamp(value["timestamp"])


def validate_weather_row(value: object) -> None:
    """Validate parsed numeric CSV values; raw strings must first be converted."""
    _shape(value, WeatherRow)
    _weather(value)
    _require(value["actual_kwh"] >= 0, "actual_kwh cannot be negative")


def _data(value: DataAgentReport) -> None:
    age = value["forecast_age_minutes"]
    _require(age is None or age >= 0, "Negative forecast age")
    if age is None:
        _require(value["status"] in ("STALE", "INVALID"), "Unknown forecast age cannot be reliable")
    _require(bool(value["source"]), "Missing data source")
    if value["status"] != "VALID":
        _require(bool(value["issues"]), "Non-VALID data needs an explanation")


def _modeling(value: ModelingResult, is_mock: bool) -> None:
    entries = value["model_comparison"]
    _require(len(entries) == len(MODEL_NAMES) and {e["model"] for e in entries} == set(MODEL_NAMES), "Expected exactly four distinct models")
    for entry in entries:
        metrics = [entry[key] for key in ("mae", "rmse", "r2")]
        if entry["status"] == "UNAVAILABLE":
            _require(all(m is None for m in metrics), "Unavailable metrics must be null")
        else:
            _require(all(m is not None for m in metrics), "Available model needs all metrics")
            _require(0 <= entry["mae"] <= entry["rmse"] + 1e-9, "Expected RMSE >= MAE >= 0")
            _require(entry["r2"] <= 1, "R2 cannot exceed 1 (negative R2 is allowed)")
            _require(is_mock or entry["status"] != "MOCK", "Live payload contains mock metrics")
    selected = next((e for e in entries if e["model"] == value["selected_model"]), None)
    _require(selected is not None and selected["status"] != "UNAVAILABLE", "Selected model is unavailable")
    for key in ("mae", "rmse", "r2"):
        _require(value[key] == selected[key], f"Selected model {key} mismatch")
    candidates = value["candidate_predictions"]
    _require(bool(candidates), "No candidate predictions")
    _require(len({c["angle_deg"] for c in candidates}) == len(candidates), "Duplicate candidate angle")
    for candidate in candidates:
        _require(0 <= candidate["angle_deg"] <= 90 and candidate["predicted_kwh"] >= 0, "Invalid candidate angle or energy")


def _optimization(value: OptimizationResult) -> None:
    for key in ("current_angle_deg", "recommended_angle_deg"):
        _require(0 <= value[key] <= 90, f"Invalid {key}")
    for key in ("baseline_kwh", "predicted_kwh", "movement_cost_kwh_equivalent"):
        _require(value[key] >= 0, f"Negative {key}")
    _require(math.isclose(value["energy_gain_kwh"], value["predicted_kwh"] - value["baseline_kwh"], abs_tol=1e-9), "Energy gain mismatch")
    _require(math.isclose(value["net_benefit_kwh_equivalent"], value["energy_gain_kwh"] - value["movement_cost_kwh_equivalent"], abs_tol=1e-9), "Net benefit mismatch")


def _safety(value: SafetyResult) -> None:
    _require(bool(value["checks"]), "Safety checks cannot be empty")
    _require(value["passed"] == all(c["passed"] for c in value["checks"]), "Safety summary contradicts checks")


def _decision(decision: Decision, safety: SafetyResult, optimization: OptimizationResult | None) -> None:
    _require(0 <= decision["target_angle_deg"] <= 90, "Invalid control angle")
    severe = any(not c["passed"] and c["severity"] == "SEVERE" for c in safety["checks"])
    _require(not severe or decision["action"] == "STOW", "Severe violation requires STOW")
    if decision["action"] == "ROTATE":
        _require(safety["passed"], "ROTATE cannot bypass safety")
        _require(optimization is not None, "ROTATE needs optimization")
        _require(decision["target_angle_deg"] == optimization["recommended_angle_deg"], "ROTATE target mismatch")
        _require(optimization["net_benefit_kwh_equivalent"] > 0, "ROTATE requires positive net benefit")
    if decision["action"] == "HOLD" and optimization is not None:
        _require(decision["target_angle_deg"] == optimization["current_angle_deg"], "HOLD must preserve current angle")


def _farm(value: FarmStatus, control_target_id: str) -> None:
    rows, zones = value["rows"], value["zones"]
    _require(value["total_panels"] == TOTAL_PANELS, "Expected 1000 panels")
    _require(len(rows) == ROW_COUNT and len(zones) == len(ZONE_ROW_COUNTS), "Expected 50 rows and 4 zones")
    row_map = {r["row_id"]: r for r in rows}
    _require(len(row_map) == ROW_COUNT, "Duplicate row ID")
    _require(control_target_id in row_map, "Unknown control row")
    _require(len({z["zone_id"] for z in zones}) == len(zones), "Duplicate zone ID")
    memberships = []
    for zone in zones:
        memberships.extend(zone["row_ids"])
        _require(bool(zone["row_ids"]), "Zone cannot be empty")
        for row_id in zone["row_ids"]:
            _require(row_id in row_map and row_map[row_id]["zone_id"] == zone["zone_id"], "Invalid zone membership")
        _require(zone["panel_count"] == len(zone["row_ids"]) * PANELS_PER_ROW, "Zone panel count mismatch")
    _require(len(memberships) == ROW_COUNT and set(memberships) == set(row_map), "Each row must belong to exactly one zone")
    for row in rows:
        _require(row["panel_count"] == PANELS_PER_ROW and 0 <= row["angle_deg"] <= 90, "Invalid row count or angle")
    _require(sum(z["panel_count"] for z in zones) == TOTAL_PANELS, "Farm panel total mismatch")


def validate_model_output(value: object) -> None:
    _shape(value, ModelOutput)
    _timestamp(value["timestamp"])
    _metadata(value["metadata"])
    _require(value["metadata"]["dataset_kind"] == "MOCK", "Evaluation fixture is only for mock development")
    _modeling(value["modeling"], True)
    fixture = value["evaluation_fixture"]
    actual = fixture["actual_kwh"]
    _require(len(actual) >= 2, "Need at least two evaluation samples")
    mean = sum(actual) / len(actual)
    total = sum((x - mean) ** 2 for x in actual)
    _require(total > 0, "R2 fixture requires nonconstant targets")
    for entry in value["modeling"]["model_comparison"]:
        predicted = fixture[entry["model"]]
        _require(len(predicted) == len(actual), "Evaluation lengths differ")
        _require(all(x >= 0 for x in actual + predicted), "Negative fixture energy")
        residual = [p - a for p, a in zip(predicted, actual)]
        squared = sum(e * e for e in residual)
        expected = (sum(abs(e) for e in residual) / len(actual), math.sqrt(squared / len(actual)), 1 - squared / total)
        for key, metric in zip(("mae", "rmse", "r2"), expected):
            _require(entry[key] is not None and math.isclose(entry[key], metric, abs_tol=1e-9), f"Mock {key} does not match fixture")


def validate_frontend_data(value: object) -> None:
    _shape(value, FrontendData)
    _timestamp(value["timestamp"])
    _metadata(value["metadata"])
    if value["current_weather"] is not None:
        _weather(value["current_weather"])
    _data(value["data_agent"])
    if value["selected_model"] is None:
        entries = value["model_comparison"]
        _require(len(entries) == len(MODEL_NAMES) and {e["model"] for e in entries} == set(MODEL_NAMES), "Expected four unavailable model entries")
        _require(all(e["status"] == "UNAVAILABLE" and all(e[k] is None for k in ("mae", "rmse", "r2")) for e in entries), "No model selected: metrics must be unavailable")
        _require(not value["candidate_predictions"] and value["optimization"] is None, "No selected model: cannot claim predictions or optimization")
    else:
        selected = next((e for e in value["model_comparison"] if e["model"] == value["selected_model"]), None)
        _require(selected is not None, "Unknown selected model")
        _modeling({"selected_model": value["selected_model"], "mae": selected["mae"], "rmse": selected["rmse"], "r2": selected["r2"], "model_comparison": value["model_comparison"], "candidate_predictions": value["candidate_predictions"]}, value["metadata"]["dataset_kind"] == "MOCK")
    if value["optimization"] is not None:
        _optimization(value["optimization"])
    _safety(value["safety"])
    _decision(value["decision"], value["safety"], value["optimization"])
    if value["decision"]["action"] == "ROTATE":
        _require(value["data_agent"]["status"] in ("VALID", "DEGRADED"), "Unreliable data cannot authorize ROTATE")
        _require(value["current_weather"] is not None, "ROTATE requires weather")
    predictions = {c["angle_deg"]: c["predicted_kwh"] for c in value["candidate_predictions"]}
    opt = value["optimization"]
    if opt is not None:
        _require(predictions.get(opt["current_angle_deg"]) == opt["baseline_kwh"], "Missing/mismatched stay baseline")
        _require(predictions.get(opt["recommended_angle_deg"]) == opt["predicted_kwh"], "Missing/mismatched recommended prediction")
    _farm(value["farm_status"], value["metadata"]["control_target_id"])
    row = next(r for r in value["farm_status"]["rows"] if r["row_id"] == value["metadata"]["control_target_id"])
    if value["decision"]["action"] == "HOLD":
        _require(value["decision"]["target_angle_deg"] == row["angle_deg"], "HOLD target differs from row angle")
    _require(row["action"] == value["decision"]["action"], "Target row action differs from decision")
    if value["metadata"]["config_id"] == DEFAULT_CONFIG.config_id:
        if value["decision"]["action"] == "ROTATE":
            _require(opt["net_benefit_kwh_equivalent"] > DEFAULT_CONFIG.min_net_benefit_kwh_equivalent, "ROTATE gain below prototype threshold")
            _require(value["data_agent"]["forecast_age_minutes"] <= DEFAULT_CONFIG.max_forecast_age_minutes, "ROTATE with stale forecast")
        if value["decision"]["action"] == "STOW":
            _require(value["decision"]["target_angle_deg"] == DEFAULT_CONFIG.stow_angle_deg, "STOW angle differs from config")
    for entry in value["agent_log"] + value["history"]:
        _timestamp(entry["timestamp"])


def validate_agent_state(value: object) -> None:
    _shape(value, AgentState)
    _require(bool(value["run_id"]), "Missing run_id")
    _timestamp(value["timestamp"])
    _metadata(value["metadata"])
    if value["weather"] is not None:
        _weather(value["weather"])
    if value["data"] is not None:
        _data(value["data"])
    if value["modeling"] is not None:
        _modeling(value["modeling"], value["metadata"]["dataset_kind"] == "MOCK")
    if value["optimization"] is not None:
        _optimization(value["optimization"])
    if value["safety"] is not None:
        _safety(value["safety"])
    if value["decision"] is not None:
        _require(value["safety"] is not None, "Decision requires safety report")
        _decision(value["decision"], value["safety"], value["optimization"])
        if value["decision"]["action"] == "ROTATE":
            _require(value["data"] is not None and value["data"]["status"] in ("VALID", "DEGRADED"), "ROTATE requires reliable data")
            _require(value["weather"] is not None and value["modeling"] is not None, "ROTATE requires weather and model output")
            if value["metadata"]["config_id"] == DEFAULT_CONFIG.config_id:
                _require(value["data"]["forecast_age_minutes"] <= DEFAULT_CONFIG.max_forecast_age_minutes, "ROTATE with stale forecast")
                _require(value["optimization"]["net_benefit_kwh_equivalent"] > DEFAULT_CONFIG.min_net_benefit_kwh_equivalent, "ROTATE gain below prototype threshold")
    if value["stage"] == "COMPLETE":
        _require(value["decision"] is not None and value["safety"] is not None, "Complete state requires final safety and decision")
    if value["stage"] == "FAILED":
        _require(bool(value["errors"]), "Failed run must explain its error")
    for entry in value["agent_log"] + value["tool_calls"]:
        _timestamp(entry["timestamp"])
