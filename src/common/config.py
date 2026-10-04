"""Proposed configuration; all hardware coefficients are prototype assumptions."""

from dataclasses import dataclass, field
import os
from pathlib import Path
from collections.abc import Mapping


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


# Internal provider configuration; no changes to shared simulation contracts.
DEMO_LATITUDE_DEG = 51.0447
DEMO_LONGITUDE_DEG = -114.0719


@dataclass(frozen=True)
class OpenMeteoConfig:
    base_url: str = "https://api.open-meteo.com/v1/forecast"
    timeout_seconds: float = 15.0
    source: str = "open-meteo"

    def __post_init__(self):
        import math
        if (type(self.timeout_seconds) not in (int, float)
                or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0):
            raise ValueError("Provider timeout must be finite and positive")
        if not self.base_url.startswith("https://"):
            raise ValueError("Provider URL must use HTTPS")
        if not self.source.strip():
            raise ValueError("Provider source must be nonempty")


@dataclass(frozen=True)
class DatabaseConfig:
    """Internal PostgreSQL settings; independent of shared weather contracts."""

    dbname: str
    user: str
    password: str = field(repr=False)
    host: str = "127.0.0.1"
    port: int = 5432
    connect_timeout: int = 5

    def __post_init__(self) -> None:
        for name in ("dbname", "user", "password", "host"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or "\x00" in value:
                raise ValueError(f"Invalid database setting: {name}")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("POSTGRES_PORT must be an integer in 1..65535")
        if type(self.connect_timeout) is not int or self.connect_timeout <= 0:
            raise ValueError("connect_timeout must be a positive integer")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "DatabaseConfig":
        """Read environment only; never connect while importing configuration."""
        values = os.environ if env is None else env
        for key in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
            if not values.get(key):
                raise ValueError(f"Required environment variable: {key}")
        try:
            port = int(values.get("POSTGRES_PORT", "5432"))
        except (ValueError, TypeError):
            raise ValueError("POSTGRES_PORT must be an integer") from None
        return cls(values["POSTGRES_DB"], values["POSTGRES_USER"],
                   values["POSTGRES_PASSWORD"], values.get("POSTGRES_HOST", "127.0.0.1"), port)


def load_database_config(env_file: Path | None = None) -> DatabaseConfig:
    """Load the repo .env then apply environment overrides, matching Compose.

    Intentionally supports only the plain KEY=value subset documented in
    .env.example. No shell execution, interpolation, or global env mutation.
    Errors identify names/line numbers but never include secret values.
    """
    path = env_file if env_file is not None else Path(__file__).resolve().parents[2] / ".env"
    values: dict[str, str] = {}
    allowed = {"POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT"}
    if path.exists():
        for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            if not separator:
                raise ValueError(f"Invalid environment assignment at line {number}")
            key, value = key.strip(), value.strip()
            if key not in allowed:
                continue
            if any(char in value for char in ("$", "\"", "'", "#")) or any(c.isspace() for c in value):
                raise ValueError(f"{key}: use plain unquoted values without interpolation")
            if key in values:
                raise ValueError(f"Duplicate environment setting: {key}")
            values[key] = value
    values.update({key: os.environ[key] for key in allowed if key in os.environ})
    return DatabaseConfig.from_env(values)
