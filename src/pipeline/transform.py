"""Canonical weather -> inference features, without targets. Owner: Luan."""

from typing import get_type_hints

import pandas as pd

from src.common.schema import WeatherFeatures
from src.common.tool_contracts import RawWeather, SolarPosition, ToolError
from src.pipeline.validate import WEATHER_FIELDS, _finite_number, _inspect_weather


def transform_weather(
    weather: RawWeather, solar: SolarPosition, *, panel_angle_deg: float
) -> WeatherFeatures:
    """Return new UTC/native-float features; never impute missing observations.

    RawWeather already specifies C, %, mm, km/h, W/m2 and interval-start
    timestamps. Do not guess provider units or shift timestamps here. Those
    mappings belong to the future provider adapter. Solar position must refer
    to the same interval (the caller owns this association).

    This pure transformation has no clock/config argument: it checks structure
    and ranges, not current freshness. Call validate_weather before operational
    use; historical records can still be transformed for offline preparation.
    """
    issues, times = _inspect_weather(weather)
    if issues:
        raise ToolError("Cannot transform weather: " + "; ".join(issues))
    if not isinstance(solar, dict) or set(solar) != set(get_type_hints(SolarPosition)):
        raise ToolError("solar: expected exactly the SolarPosition fields")
    elevation, azimuth = solar["sun_elevation_deg"], solar["sun_azimuth_deg"]
    if not _finite_number(elevation) or not -90 <= elevation <= 90:
        raise ToolError("sun_elevation_deg: expected finite number within [-90, 90]")
    if not _finite_number(azimuth) or not 0 <= azimuth < 360:
        raise ToolError("sun_azimuth_deg: expected finite number within [0, 360)")
    if not _finite_number(panel_angle_deg) or not 0 <= panel_angle_deg <= 90:
        raise ToolError("panel_angle_deg: expected finite number within [0, 90]")
    timestamp = pd.Timestamp(times["timestamp"]).isoformat().replace("+00:00", "Z")
    return {
        "timestamp": timestamp,
        **{field: float(weather[field]) for field in WEATHER_FIELDS},
        "sun_elevation_deg": float(elevation),
        "sun_azimuth_deg": float(azimuth),
        "panel_angle_deg": float(panel_angle_deg),
    }
