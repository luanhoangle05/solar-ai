"""Owner: Duy. Build the synthetic EXAMPLE dataset for model development.

Everything here is simulated from a simple, documented formula using only the
standard library. It is not measured data and not provider weather. Outputs
built on it must be labeled dataset_kind "MOCK" / label_source "mock".
See data/example/README.md for the formula and its assumptions.

Run from the repository root:  python -m scripts.generate_example_data
"""

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import math
from pathlib import Path
import random

from src.common.config import PANELS_PER_ROW
from src.common.schema import WEATHER_COLUMNS, WeatherRow, validate_weather_row
from src.models.data_loader import EXAMPLE_DATASET_PATH


LOGGER = logging.getLogger(__name__)

SOLAR_CONSTANT_WM2 = 1361.0
REFERENCE_IRRADIANCE_WM2 = 1000.0
REFERENCE_CELL_TEMPERATURE_C = 25.0
NOCT_AMBIENT_C = 20.0
NOCT_IRRADIANCE_WM2 = 800.0
HOURS_PER_INTERVAL = 1.0
MINUTES_PER_DEGREE_LONGITUDE = 4.0
DAYS_PER_YEAR = 365.0
DEGREES_PER_HOUR = 15.0
WEATHER_DECIMALS = 1
SUN_ANGLE_DECIMALS = 2
ENERGY_DECIMALS = 4


@dataclass(frozen=True)
class ExampleDataConfig:
    """EXAMPLE-DATA ASSUMPTIONS; a hypothetical site, not a surveyed farm."""

    seed: int = 20261004
    start: datetime = datetime(2026, 3, 1, tzinfo=timezone.utc)
    end: datetime = datetime(2026, 9, 1, tzinfo=timezone.utc)
    latitude_deg: float = 52.0
    longitude_deg: float = -113.0
    panel_azimuth_deg: float = 180.0
    panel_rated_kw: float = 0.35
    system_efficiency: float = 0.9
    temperature_coefficient_per_c: float = -0.004
    noct_c: float = 45.0
    ground_albedo: float = 0.2
    noise_fraction: float = 0.03
    panel_angle_step_deg: int = 5
    panel_angle_max_deg: int = 90
    clear_sky_transmittance: float = 0.7
    clear_sky_diffuse_fraction: float = 0.1
    overcast_ghi_loss: float = 0.75
    overcast_ghi_exponent: float = 3.4
    cloud_beam_exponent: float = 1.2
    cloud_persistence: float = 0.5
    cloud_hourly_sigma_pct: float = 12.0
    rain_cloud_threshold_pct: float = 75.0
    rain_probability: float = 0.35
    rain_mean_mm: float = 1.5
    seasonal_mean_temperature_c: float = 8.0
    seasonal_amplitude_c: float = 10.0
    warmest_day_of_year: int = 200
    diurnal_amplitude_c: float = 6.0
    warmest_solar_hour: float = 15.0
    cloud_cooling_c: float = 3.0
    temperature_sigma_c: float = 1.0
    wind_gamma_shape: float = 4.0
    wind_gamma_scale_kmh: float = 3.5
    storm_day_probability: float = 0.04
    storm_extra_wind_kmh: float = 35.0
    wind_hourly_sigma_fraction: float = 0.2
    gust_factor_min: float = 1.3
    gust_factor_span: float = 0.5


DEFAULT_EXAMPLE_CONFIG = ExampleDataConfig()


@dataclass(frozen=True)
class DayWeather:
    """Slow-moving conditions shared by every hour of one local solar day."""

    cloud_pct: float
    wind_kmh: float


def generate_rows(config: ExampleDataConfig = DEFAULT_EXAMPLE_CONFIG) -> list[WeatherRow]:
    """Hourly rows over [start, end); the same config always gives the same rows."""
    rng = random.Random(config.seed)
    rows: list[WeatherRow] = []
    day_weather: DayWeather | None = None
    interval_start = config.start
    while interval_start < config.end:
        if day_weather is None or _is_local_solar_midnight(interval_start, config):
            day_weather = _next_day_weather(day_weather, rng, config)
        row = _build_row(interval_start, day_weather, rng, config)
        validate_weather_row(row)
        rows.append(row)
        interval_start += timedelta(hours=HOURS_PER_INTERVAL)
    return rows


def write_csv(rows: list[WeatherRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=WEATHER_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def plane_of_array_wm2(row: WeatherRow, config: ExampleDataConfig) -> float:
    """Irradiance on the tilted panel: beam + sky diffuse + ground reflection."""
    elevation = math.radians(row["sun_elevation_deg"])
    tilt = math.radians(row["panel_angle_deg"])
    azimuth_offset = math.radians(row["sun_azimuth_deg"] - config.panel_azimuth_deg)
    cos_incidence = math.sin(elevation) * math.cos(tilt) + math.cos(elevation) * math.sin(tilt) * math.cos(azimuth_offset)
    beam = row["dni_wm2"] * max(0.0, cos_incidence)
    sky_diffuse = row["dhi_wm2"] * (1 + math.cos(tilt)) / 2
    ground_reflected = row["ghi_wm2"] * config.ground_albedo * (1 - math.cos(tilt)) / 2
    return beam + sky_diffuse + ground_reflected


def expected_row_kwh(row: WeatherRow, config: ExampleDataConfig) -> float:
    """Noise-free energy for one 20-panel row over the hour."""
    irradiance = plane_of_array_wm2(row, config)
    cell_temperature = row["temperature_c"] + irradiance * (config.noct_c - NOCT_AMBIENT_C) / NOCT_IRRADIANCE_WM2
    temperature_factor = 1 + config.temperature_coefficient_per_c * (cell_temperature - REFERENCE_CELL_TEMPERATURE_C)
    row_rated_kw = config.panel_rated_kw * PANELS_PER_ROW
    power_kw = row_rated_kw * irradiance / REFERENCE_IRRADIANCE_WM2 * config.system_efficiency * temperature_factor
    return max(0.0, power_kw * HOURS_PER_INTERVAL)


def _next_day_weather(previous: DayWeather | None, rng: random.Random, config: ExampleDataConfig) -> DayWeather:
    fresh_cloud = rng.betavariate(0.8, 1.0) * 100
    cloud = fresh_cloud if previous is None else (
        config.cloud_persistence * previous.cloud_pct + (1 - config.cloud_persistence) * fresh_cloud
    )
    wind = rng.gammavariate(config.wind_gamma_shape, config.wind_gamma_scale_kmh)
    if rng.random() < config.storm_day_probability:
        wind += config.storm_extra_wind_kmh
    return DayWeather(cloud_pct=cloud, wind_kmh=wind)


def _build_row(interval_start: datetime, day: DayWeather, rng: random.Random, config: ExampleDataConfig) -> WeatherRow:
    midpoint = interval_start + timedelta(hours=HOURS_PER_INTERVAL / 2)
    exact_elevation, azimuth = _sun_position(midpoint, config)
    # Round first so the stored elevation and the irradiance agree about day versus night.
    elevation = round(exact_elevation, SUN_ANGLE_DECIMALS) + 0.0
    cloud_pct = _clamp(day.cloud_pct + rng.gauss(0, config.cloud_hourly_sigma_pct), 0, 100)
    ghi, dni, dhi = _irradiance(elevation, cloud_pct / 100, config)
    wind = max(0.0, day.wind_kmh * (1 + rng.gauss(0, config.wind_hourly_sigma_fraction)))
    gust = wind * (config.gust_factor_min + rng.random() * config.gust_factor_span)
    wind_rounded = round(wind, WEATHER_DECIMALS)
    features = {
        "timestamp": interval_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "temperature_c": round(_temperature_c(midpoint, cloud_pct, elevation, rng, config), WEATHER_DECIMALS) + 0.0,
        "cloud_cover_pct": round(cloud_pct, WEATHER_DECIMALS),
        "precipitation_mm": round(_precipitation_mm(cloud_pct, rng, config), WEATHER_DECIMALS),
        "wind_speed_kmh": wind_rounded,
        "wind_gust_kmh": max(wind_rounded, round(gust, WEATHER_DECIMALS)),
        "ghi_wm2": ghi,
        "dni_wm2": dni,
        "dhi_wm2": dhi,
        "sun_elevation_deg": elevation,
        "sun_azimuth_deg": round(azimuth, SUN_ANGLE_DECIMALS) % 360,
        "panel_angle_deg": float(rng.randrange(0, config.panel_angle_max_deg + 1, config.panel_angle_step_deg)),
    }
    # The label is computed from the rounded features, so the CSV alone reproduces it up to noise.
    noise = rng.gauss(0, config.noise_fraction)
    energy = max(0.0, expected_row_kwh(features, config) * (1 + noise))
    return {**features, "actual_kwh": round(energy, ENERGY_DECIMALS)}


def _is_local_solar_midnight(interval_start: datetime, config: ExampleDataConfig) -> bool:
    """Daily regimes change at night on site, not at UTC midnight in mid-afternoon."""
    local = interval_start + timedelta(hours=config.longitude_deg / DEGREES_PER_HOUR)
    return local.hour == 0


def _sun_position(instant: datetime, config: ExampleDataConfig) -> tuple[float, float]:
    """NOAA low-accuracy solar position: (elevation, azimuth clockwise from north)."""
    hour = instant.hour + instant.minute / 60
    year_angle = 2 * math.pi / DAYS_PER_YEAR * (instant.timetuple().tm_yday - 1 + (hour - 12) / 24)
    equation_of_time_min = 229.18 * (
        0.000075 + 0.001868 * math.cos(year_angle) - 0.032077 * math.sin(year_angle)
        - 0.014615 * math.cos(2 * year_angle) - 0.040849 * math.sin(2 * year_angle)
    )
    declination = (
        0.006918 - 0.399912 * math.cos(year_angle) + 0.070257 * math.sin(year_angle)
        - 0.006758 * math.cos(2 * year_angle) + 0.000907 * math.sin(2 * year_angle)
        - 0.002697 * math.cos(3 * year_angle) + 0.00148 * math.sin(3 * year_angle)
    )
    solar_minutes = hour * 60 + equation_of_time_min + MINUTES_PER_DEGREE_LONGITUDE * config.longitude_deg
    hour_angle = math.radians(solar_minutes / MINUTES_PER_DEGREE_LONGITUDE - 180)
    latitude = math.radians(config.latitude_deg)
    sin_elevation = math.sin(latitude) * math.sin(declination) + math.cos(latitude) * math.cos(declination) * math.cos(hour_angle)
    elevation = math.degrees(math.asin(_clamp(sin_elevation, -1, 1)))
    azimuth = math.degrees(math.atan2(
        math.sin(hour_angle),
        math.cos(hour_angle) * math.sin(latitude) - math.tan(declination) * math.cos(latitude),
    )) + 180
    return elevation, azimuth % 360


def _irradiance(elevation_deg: float, cloud_fraction: float, config: ExampleDataConfig) -> tuple[float, float, float]:
    """(GHI, DNI, DHI) in W/m2, rounded so that GHI = DNI * sin(elevation) + DHI."""
    if elevation_deg <= 0:
        return 0.0, 0.0, 0.0
    sin_elevation = math.sin(math.radians(elevation_deg))
    air_mass = 1 / (sin_elevation + 0.50572 * (elevation_deg + 6.07995) ** -1.6364)
    clear_dni = SOLAR_CONSTANT_WM2 * config.clear_sky_transmittance ** (air_mass ** 0.678)
    clear_dhi = config.clear_sky_diffuse_fraction * SOLAR_CONSTANT_WM2 * sin_elevation
    clear_ghi = clear_dni * sin_elevation + clear_dhi
    ghi = clear_ghi * (1 - config.overcast_ghi_loss * cloud_fraction ** config.overcast_ghi_exponent)
    dni = round(clear_dni * (1 - cloud_fraction) ** config.cloud_beam_exponent, WEATHER_DECIMALS)
    dhi = round(max(0.0, ghi - dni * sin_elevation), WEATHER_DECIMALS)
    return round(dni * sin_elevation + dhi, WEATHER_DECIMALS), dni, dhi


def _temperature_c(instant: datetime, cloud_pct: float, elevation_deg: float, rng: random.Random, config: ExampleDataConfig) -> float:
    day_of_year = instant.timetuple().tm_yday
    seasonal = config.seasonal_mean_temperature_c + config.seasonal_amplitude_c * math.cos(
        2 * math.pi * (day_of_year - config.warmest_day_of_year) / DAYS_PER_YEAR
    )
    solar_hour = (instant.hour + instant.minute / 60 + config.longitude_deg / DEGREES_PER_HOUR) % 24
    diurnal = config.diurnal_amplitude_c * math.cos(2 * math.pi * (solar_hour - config.warmest_solar_hour) / 24)
    cloud_cooling = config.cloud_cooling_c * cloud_pct / 100 if elevation_deg > 0 else 0.0
    return seasonal + diurnal - cloud_cooling + rng.gauss(0, config.temperature_sigma_c)


def _precipitation_mm(cloud_pct: float, rng: random.Random, config: ExampleDataConfig) -> float:
    is_raining = cloud_pct > config.rain_cloud_threshold_pct and rng.random() < config.rain_probability
    return rng.expovariate(1 / config.rain_mean_mm) if is_raining else 0.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    rows = generate_rows(DEFAULT_EXAMPLE_CONFIG)
    write_csv(rows, EXAMPLE_DATASET_PATH)
    LOGGER.info("Wrote %d synthetic example rows to %s", len(rows), EXAMPLE_DATASET_PATH)


if __name__ == "__main__":
    main()
