"""Offline pvlib solar-position enrichment. Owner: Luan."""

from datetime import timedelta

import pandas as pd
from pvlib import solarposition

from src.common.config import PREDICTION_HORIZON_MINUTES
from src.common.tool_contracts import SolarPosition, ToolError, WeatherRequest
from src.pipeline.validate import _finite_number, _parse_timestamp


# WeatherRequest has no altitude. Explicit sea-level approximation, not a
# claim about a real farm. Return geometric elevation, not refracted elevation.
REFERENCE_ALTITUDE_M = 0.0
POSITION_METHOD = "nrel_numpy"


def calculate_solar_position(request: WeatherRequest) -> SolarPosition:
    """Return geometric elevation and north-clockwise azimuth at mid-interval.

    Midpoint is a representative position, not an integrated irradiance/PV
    energy calculation. Negative nighttime elevation is preserved. pvlib SPA
    uses its offline delta-T estimate; no location service or network is used.
    Only the existing shared one-hour horizon is accepted.
    """
    if not isinstance(request, WeatherRequest):
        raise ToolError("request: expected WeatherRequest")
    latitude, longitude = request.latitude_deg, request.longitude_deg
    if not _finite_number(latitude) or not -90 <= latitude <= 90:
        raise ToolError("latitude_deg: expected finite number within [-90, 90]")
    if not _finite_number(longitude) or not -180 <= longitude <= 180:
        raise ToolError("longitude_deg: expected finite number within [-180, 180]")
    if (type(request.prediction_horizon_minutes) is not int
            or request.prediction_horizon_minutes != PREDICTION_HORIZON_MINUTES):
        raise ToolError("prediction_horizon_minutes: expected shared one-hour interval")
    start = _parse_timestamp(request.interval_start, "interval_start")
    try:
        midpoint = start + timedelta(minutes=request.prediction_horizon_minutes / 2)
        positions = solarposition.get_solarposition(
            pd.DatetimeIndex([midpoint]), latitude=float(latitude),
            longitude=float(longitude), altitude=REFERENCE_ALTITUDE_M,
            method=POSITION_METHOD, delta_t=None,
        )
        elevation = float(positions.iloc[0]["elevation"])
        azimuth = float(positions.iloc[0]["azimuth"])
    except (ValueError, TypeError, OverflowError, KeyError, IndexError) as exc:
        raise ToolError("Solar-position calculation failed") from exc
    if not _finite_number(elevation) or not -90 <= elevation <= 90:
        raise ToolError("pvlib returned invalid elevation")
    if not _finite_number(azimuth) or not 0 <= azimuth <= 360:
        raise ToolError("pvlib returned invalid azimuth")
    return {"sun_elevation_deg": elevation, "sun_azimuth_deg": azimuth % 360.0}
