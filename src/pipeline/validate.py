"""Offline validation of canonical RawWeather. Owner: Luan.

No imputation or unit guessing. This checks data quality, not wind safety.
Forecast age is measured from issuance, never from download or interval time.
"""

from datetime import datetime, timezone
import math
from numbers import Real
from typing import get_type_hints

from src.common.config import SimulationConfig
from src.common.schema import CurrentWeather, DataAgentReport
from src.common.tool_contracts import RawWeather, ToolError


WEATHER_FIELDS = tuple(get_type_hints(CurrentWeather))
NONNEGATIVE_FIELDS = tuple(
    field for field in WEATHER_FIELDS
    if field not in ("temperature_c", "cloud_cover_pct")
)


def _parse_timestamp(value: object, name: str) -> datetime:
    """Read an explicit ISO timestamp and normalize it to UTC."""
    if not isinstance(value, str):
        raise ToolError(f"{name}: expected timezone-aware ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            raise ValueError("timezone missing")
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise ToolError(f"{name}: invalid or timezone-naive timestamp") from exc


def _finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, Real):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, ValueError):
        return False


def _inspect_weather(weather: RawWeather) -> tuple[list[str], dict[str, datetime]]:
    """Shared structural checks for validation and transformation."""
    issues: list[str] = []
    times: dict[str, datetime] = {}
    if not isinstance(weather, dict):
        return ["weather: expected RawWeather object"], times
    expected = get_type_hints(RawWeather)
    for field in expected:
        if field not in weather:
            issues.append(f"{field}: missing required field")
    if set(weather) - set(expected):
        issues.append("weather: unexpected fields outside RawWeather contract")
    if not isinstance(weather.get("source"), str) or not weather["source"].strip():
        issues.append("source: must be a nonempty string")
    for field in ("timestamp", "fetched_at", "forecast_issued_at"):
        if field == "forecast_issued_at" and weather.get(field) is None:
            continue  # Unknown issuance is represented, not fabricated.
        try:
            times[field] = _parse_timestamp(weather.get(field), field)
        except ToolError as exc:
            issues.append(str(exc))
    if "forecast_issued_at" in times and "fetched_at" in times:
        if times["forecast_issued_at"] > times["fetched_at"]:
            issues.append("forecast_issued_at: later than fetched_at")
    for field in WEATHER_FIELDS:
        value = weather.get(field)
        if not _finite_number(value):
            issues.append(f"{field}: expected finite number, not missing/string/bool")
        elif field in NONNEGATIVE_FIELDS and value < 0:
            issues.append(f"{field}: cannot be negative")
        elif field == "cloud_cover_pct" and not 0 <= value <= 100:
            issues.append("cloud_cover_pct: must be within [0, 100]")
    wind, gust = weather.get("wind_speed_kmh"), weather.get("wind_gust_kmh")
    if _finite_number(wind) and _finite_number(gust) and gust < wind:
        issues.append("wind_gust_kmh: below sustained wind_speed_kmh")
    return issues, times


def validate_weather(
    weather: RawWeather, *, now: str, config: SimulationConfig
) -> DataAgentReport:
    """Return VALID, STALE, or INVALID without mutating the observation.

    Age equal to the configured maximum is still valid. Invalid observations
    take precedence over stale age. Bad caller clock/config raises ToolError.
    used_cache remains False: only the future Data Agent knows retrieval mode
    and can mark cache fallback/DEGRADED status after checking eligibility.
    """
    current_time = _parse_timestamp(now, "now")
    limit = config.max_forecast_age_minutes
    if not _finite_number(limit) or limit < 0:
        raise ToolError("max_forecast_age_minutes: expected finite nonnegative limit")
    issues, times = _inspect_weather(weather)
    issued = times.get("forecast_issued_at")
    age: float | None = None
    if issued is None:
        issues.append("forecast_issued_at: unknown; freshness cannot be established")
    elif issued > current_time:
        issues.append("forecast_issued_at: later than now")
    else:
        age = (current_time - issued).total_seconds() / 60.0
    if "fetched_at" in times and times["fetched_at"] > current_time:
        issues.append("fetched_at: later than now")
    status = "INVALID" if issues else "VALID"
    if age is not None and age > limit:
        issues.append(f"forecast_age_minutes: {age:g} exceeds limit {limit:g}")
        if status == "VALID":
            status = "STALE"
    source = weather.get("source") if isinstance(weather, dict) else None
    return {
        "status": status,
        "source": source if isinstance(source, str) and source.strip() else "unknown",
        "forecast_age_minutes": age,
        "used_cache": False,
        "issues": issues,
    }
