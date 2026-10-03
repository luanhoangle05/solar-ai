"""Small test-only observations; canonical shared mock files are untouched."""

from src.common.tool_contracts import RawWeather


NOW = "2026-06-21T19:00:00Z"


def weather_fixture() -> RawWeather:
    return {
        "timestamp": "2026-06-21T19:00:00Z",
        "source": "test_fixture",
        "fetched_at": "2026-06-21T18:59:00Z",
        "forecast_issued_at": "2026-06-21T18:55:00Z",
        "temperature_c": 22, "cloud_cover_pct": 15,
        "precipitation_mm": 0, "wind_speed_kmh": 14, "wind_gust_kmh": 24,
        "ghi_wm2": 850, "dni_wm2": 750, "dhi_wm2": 201,
    }
