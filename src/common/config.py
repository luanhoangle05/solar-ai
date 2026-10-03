"""Proposed configuration; all hardware coefficients are prototype assumptions."""

from dataclasses import dataclass


SCHEMA_VERSION = "0.1.0"
CONFIG_ID = "prototype-row-hour-v1"
TOTAL_PANELS = 1000
ROW_COUNT = 50
PANELS_PER_ROW = 20
# Whole-row control: 260/240/260/240 panels, not four equal 250-panel zones.
ZONE_ROW_COUNTS = (13, 12, 13, 12)
PREDICTION_HORIZON_MINUTES = 60
ENERGY_SCOPE = "row"


@dataclass(frozen=True)
class SimulationConfig:
    """PROTOTYPE SIMULATION ASSUMPTIONS; not measured or hardware-certified.

    Costs and gains apply to one 20-panel row over the same forecast interval.
    Wear is already expressed in kWh-equivalent, not currency. No monetary
    savings can be reported until a documented conversion has been agreed.
    Angles are tilt from horizontal; actuator geometry remains future work.
    """

    config_id: str = CONFIG_ID
    motor_kwh_per_degree: float = 0.002
    wear_kwh_equivalent_per_degree: float = 0.001
    min_net_benefit_kwh_equivalent: float = 0.02
    min_angle_deg: float = 0.0
    max_angle_deg: float = 90.0
    stow_angle_deg: float = 0.0
    max_wind_speed_kmh: float = 50.0
    max_wind_gust_kmh: float = 70.0
    max_forecast_age_minutes: float = 30.0
    candidate_angles_deg: tuple[float, ...] = (30, 35, 40, 45, 50, 55, 60)


DEFAULT_CONFIG = SimulationConfig()
