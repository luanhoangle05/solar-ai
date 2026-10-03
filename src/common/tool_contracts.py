"""Dependency-injected tool interfaces; mocks and real tools share signatures.

All methods are synchronous for the first prototype. Implementations raise
ToolError on unavailable inputs/outputs; agents record it instead of inventing
success. No network, model training, or hardware commands run in this module.
"""

from dataclasses import dataclass
from typing import Protocol, TypedDict, runtime_checkable

from src.common.config import SimulationConfig
from src.common.schema import (
    CandidatePrediction, DataAgentReport, Decision, Metadata, ModelMetrics,
    ModelName, OptimizationResult, SafetyCheck, SafetyResult, WeatherFeatures,
)


class ToolError(RuntimeError):
    """Tool failure to be recorded by the owning agent/orchestrator."""


@dataclass(frozen=True)
class WeatherRequest:
    latitude_deg: float
    longitude_deg: float
    interval_start: str
    prediction_horizon_minutes: int


class RawWeather(TypedDict):
    """Provider adapter output, already normalized to declared units.

    None signals a missing observation. Solar enrichment is a separate tool.
    """

    timestamp: str
    source: str
    fetched_at: str
    forecast_issued_at: str | None
    temperature_c: float | None
    cloud_cover_pct: float | None
    precipitation_mm: float | None
    wind_speed_kmh: float | None
    wind_gust_kmh: float | None
    ghi_wm2: float | None
    dni_wm2: float | None
    dhi_wm2: float | None


class SolarPosition(TypedDict):
    sun_elevation_deg: float
    sun_azimuth_deg: float


class MovementCost(TypedDict):
    movement_degrees: float
    motor_energy_kwh: float
    wear_kwh_equivalent: float
    movement_cost_kwh_equivalent: float


class ControlReceipt(TypedDict):
    accepted: bool
    mode: str
    reason: str


@runtime_checkable
class WeatherTools(Protocol):
    """Luan's tools; Data Agent owns freshness/retry/cache decisions."""

    def fetch_weather(self, request: WeatherRequest) -> RawWeather: ...
    def validate_weather(self, weather: RawWeather, *, now: str, config: SimulationConfig) -> DataAgentReport: ...
    def calculate_solar_position(self, request: WeatherRequest) -> SolarPosition: ...
    def transform_weather(self, weather: RawWeather, solar: SolarPosition, *, panel_angle_deg: float) -> WeatherFeatures: ...
    def load_cached_weather(self, request: WeatherRequest) -> RawWeather | None: ...
    def store_weather(self, request: WeatherRequest, weather: RawWeather) -> None: ...


@runtime_checkable
class EnergyPredictor(Protocol):
    """One validated model adapter. No actual_kwh input at inference time.

    Return one nonnegative kWh value per requested angle, in the same order,
    for metadata.control_target_id over the declared prediction interval.
    LSTM history preparation belongs inside its adapter, not the optimizer.
    """

    def predict_kwh(self, weather: WeatherFeatures, candidate_angles_deg: tuple[float, ...], *, metadata: Metadata) -> list[CandidatePrediction]: ...


@runtime_checkable
class ModelingTools(Protocol):
    """Duy integrates adapters supplied by both model owners."""

    def evaluate_models(self) -> list[ModelMetrics]: ...
    def select_best_model(self, comparison: list[ModelMetrics]) -> ModelName: ...
    def get_predictor(self, model: ModelName) -> EnergyPredictor: ...


@runtime_checkable
class OptimizationTools(Protocol):
    """All coefficients passed explicitly; comparable row/hour energy units."""

    def generate_candidate_angles(self, current_angle_deg: float, *, config: SimulationConfig) -> tuple[float, ...]: ...
    def calculate_movement_cost(self, current_angle_deg: float, target_angle_deg: float, *, config: SimulationConfig) -> MovementCost: ...
    def calculate_net_benefit(self, energy_gain_kwh: float, movement_cost_kwh_equivalent: float) -> float: ...
    def optimize_angle(self, predictions: list[CandidatePrediction], current_angle_deg: float, *, config: SimulationConfig) -> OptimizationResult: ...


@runtime_checkable
class SafetyTools(Protocol):
    """Deterministic checks; an LLM cannot authorize overriding a failure.

    Severe violation -> STOW; unreliable data/failed nonsevere check -> HOLD;
    gain <= configured threshold -> HOLD; otherwise ROTATE. Future hardware
    dispatch must require the final checked decision and target row identifier.
    """

    def check_wind_safety(self, weather: WeatherFeatures, *, config: SimulationConfig) -> SafetyCheck: ...
    def check_angle_limits(self, angle_deg: float, *, config: SimulationConfig) -> SafetyCheck: ...
    def check_data_freshness(self, data: DataAgentReport, *, config: SimulationConfig) -> SafetyCheck: ...
    def check_panel_status(self, panel_state: str) -> SafetyCheck: ...
    def check_model_confidence(self, metrics: ModelMetrics) -> SafetyCheck: ...
    def apply_safety_rules(self, checks: list[SafetyCheck], optimization: OptimizationResult | None, *, current_angle_deg: float, config: SimulationConfig) -> tuple[SafetyResult, Decision]: ...
    def send_control_command(self, decision: Decision, safety: SafetyResult, *, control_target_id: str, simulation_only: bool = True) -> ControlReceipt: ...
