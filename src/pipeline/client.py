"""One-attempt Open-Meteo adapter. No retries, cache decisions or solar math."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib

import requests

from src.common.config import OpenMeteoConfig, PREDICTION_HORIZON_MINUTES
from src.common.tool_contracts import RawWeather, ToolError, WeatherRequest
from src.pipeline.validate import _finite_number, _parse_timestamp


# provider name: (canonical field, required unit, preceding-hour aggregate)
VARIABLES = {
    "temperature_2m": ("temperature_c", "°C", False),
    "cloud_cover": ("cloud_cover_pct", "%", False),
    "precipitation": ("precipitation_mm", "mm", True),
    "wind_speed_10m": ("wind_speed_kmh", "km/h", False),
    "wind_gusts_10m": ("wind_gust_kmh", "km/h", True),
    "shortwave_radiation": ("ghi_wm2", "W/m²", True),
    "direct_normal_irradiance": ("dni_wm2", "W/m²", True),
    "diffuse_radiation": ("dhi_wm2", "W/m²", True),
}


def _request_parameters(request: WeatherRequest):
    if not isinstance(request, WeatherRequest):
        raise ToolError("Open-Meteo requires WeatherRequest")
    for name, limit in (("latitude_deg", 90), ("longitude_deg", 180)):
        value = getattr(request, name)
        if not _finite_number(value) or not -limit <= value <= limit:
            raise ToolError(f"Open-Meteo: invalid {name}")
    if (type(request.prediction_horizon_minutes) is not int
            or request.prediction_horizon_minutes != PREDICTION_HORIZON_MINUTES):
        raise ToolError("Open-Meteo supports the shared 60-minute horizon only")
    start = _parse_timestamp(request.interval_start, "interval_start")
    if start.minute or start.second or start.microsecond:
        raise ToolError("Open-Meteo hourly data requires a UTC hour-aligned interval; no interpolation is performed")
    try:
        end = start + timedelta(minutes=PREDICTION_HORIZON_MINUTES)
    except OverflowError:
        raise ToolError("Open-Meteo interval is out of range") from None
    return start, end, {
        "latitude": float(request.latitude_deg), "longitude": float(request.longitude_deg),
        "hourly": ",".join(VARIABLES), "timezone": "UTC", "timeformat": "unixtime",
        "temperature_unit": "celsius", "wind_speed_unit": "kmh", "precipitation_unit": "mm",
        "start_hour": start.strftime("%Y-%m-%dT%H:%M"),
        "end_hour": end.strftime("%Y-%m-%dT%H:%M"),
    }


def _map_response(payload, start, end, fetched_at, source) -> RawWeather:
    if not isinstance(payload, dict) or payload.get("error"):
        raise ToolError("Open-Meteo: unexpected response object or provider error")
    if type(payload.get("utc_offset_seconds")) is not int or payload["utc_offset_seconds"] != 0:
        raise ToolError("Open-Meteo: expected UTC offset zero")
    if payload.get("timezone") not in ("GMT", "UTC", "Etc/UTC", "Etc/GMT"):
        raise ToolError("Open-Meteo: unexpected provider timezone")
    for field, limit in (("latitude", 90), ("longitude", 180)):
        if not _finite_number(payload.get(field)) or not -limit <= payload[field] <= limit:
            raise ToolError(f"Open-Meteo: invalid returned {field}")
    hourly, units = payload.get("hourly"), payload.get("hourly_units")
    if not isinstance(hourly, dict) or not isinstance(units, dict):
        raise ToolError("Open-Meteo: missing hourly data or units")
    times = hourly.get("time")
    if not isinstance(times, list) or not times or units.get("time") != "unixtime":
        raise ToolError("Open-Meteo: expected Unix hourly timestamps")
    parsed = []
    for value in times:
        if type(value) is not int:
            raise ToolError("Open-Meteo: invalid hourly timestamp")
        try:
            instant = datetime.fromtimestamp(value, timezone.utc)
        except (ValueError, OverflowError, OSError):
            raise ToolError("Open-Meteo: out-of-range hourly timestamp") from None
        if instant.minute or instant.second or (parsed and instant <= parsed[-1]):
            raise ToolError("Open-Meteo: timestamps must be ordered, unique UTC hours")
        parsed.append(instant)
    try:
        start_index, end_index = parsed.index(start), parsed.index(end)
    except ValueError:
        raise ToolError("Open-Meteo: requested interval is unavailable") from None
    weather = {
        "timestamp": start.isoformat(), "source": source,
        "fetched_at": fetched_at.isoformat(), "forecast_issued_at": None,
    }
    for provider, (field, unit, aggregate) in VARIABLES.items():
        values = hourly.get(provider)
        if not isinstance(values, list):
            raise ToolError(f"Open-Meteo: missing hourly variable {provider}")
        if len(values) != len(times):
            raise ToolError(f"Open-Meteo: array-length mismatch for {provider}")
        if units.get(provider) != unit:
            raise ToolError(f"Open-Meteo: unexpected unit for {provider}")
        value = values[end_index if aggregate else start_index]
        if not _finite_number(value):
            raise ToolError(f"Open-Meteo: null or nonfinite/non-numeric required value for {provider}")
        weather[field] = float(value)
    return weather


class OpenMeteoClient:
    """Storage-independent implementation of WeatherTools.fetch_weather.

    last_provenance is an internal diagnostic snapshot, not a second weather
    contract. It is cleared before every attempt and never added to RawWeather.
    Instances are intended for sequential use by the later synchronous agent.
    """

    def __init__(self, config: OpenMeteoConfig = OpenMeteoConfig()):
        self.config = config
        self._last_provenance = None

    @property
    def last_provenance(self):
        return deepcopy(self._last_provenance)

    def fetch_weather(self, request: WeatherRequest) -> RawWeather:
        self._last_provenance = None
        start, end, params = _request_parameters(request)
        try:
            # Requests' default adapter performs no retries. Disable redirects
            # too, so this method issues only one HTTP request per invocation.
            response = requests.get(self.config.base_url, params=params,
                                    timeout=self.config.timeout_seconds, allow_redirects=False)
        except requests.Timeout:
            raise ToolError("Open-Meteo request timed out") from None
        except requests.ConnectionError:
            raise ToolError("Open-Meteo connection failed") from None
        except requests.RequestException:
            raise ToolError("Open-Meteo HTTP request failed") from None
        try:
            fetched_at = datetime.now(timezone.utc)  # body retrieved, not forecast issuance
            if response.status_code != 200:
                raise ToolError(f"Open-Meteo HTTP {response.status_code}; no retry attempted")
            try:
                payload = response.json()
            except ValueError:
                raise ToolError("Open-Meteo returned malformed JSON") from None
            weather = _map_response(payload, start, end, fetched_at, self.config.source)
            self._last_provenance = {
                "endpoint": self.config.base_url, "request_parameters": params,
                "fetched_at": weather["fetched_at"], "forecast_issued_at": None,
                "returned_coordinates": {"latitude": payload["latitude"], "longitude": payload["longitude"]},
                "timezone": payload["timezone"], "utc_offset_seconds": payload["utc_offset_seconds"],
                "payload": deepcopy(payload),
                "response_sha256": hashlib.sha256(response.content).hexdigest(),
            }
            return weather
        finally:
            response.close()
