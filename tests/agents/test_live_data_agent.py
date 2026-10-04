"""Live Data Agent: coordinates the pipeline tools, retries, falls back to cache, never invents data."""

import copy
import io
import json
import unittest
import urllib.error

from src.agents.trace import StageError
from src.common.agent_contracts import DataAgentContract
from src.common.config import DEFAULT_CONFIG
from src.common.schema import validate_frontend_data
from src.common.tool_contracts import ToolError, WeatherRequest, WeatherTools
from src.pipeline.transform import transform_weather
from src.pipeline.validate import validate_weather
from src.service.live_data_agent import CACHE_ISSUE, LiveDataAgent, PipelineWeatherTools, SystemTrustOpenMeteoClient, current_hour_request
from tests.agents.test_orchestrator import build_orchestrator, pending_state


NOW = "2026-06-21T19:10:00Z"
REQUEST = WeatherRequest(latitude_deg=51.0447, longitude_deg=-114.0719, interval_start="2026-06-21T19:00:00Z", prediction_horizon_minutes=60)
RAW = {
    "timestamp": "2026-06-21T19:00:00+00:00", "source": "test-provider", "fetched_at": "2026-06-21T19:09:00+00:00",
    "forecast_issued_at": "2026-06-21T19:05:00+00:00", "temperature_c": 22.0, "cloud_cover_pct": 15.0, "precipitation_mm": 0.0,
    "wind_speed_kmh": 14.0, "wind_gust_kmh": 24.0, "ghi_wm2": 850.0, "dni_wm2": 750.0, "dhi_wm2": 201.0,
}
SOLAR = {"sun_elevation_deg": 61.5, "sun_azimuth_deg": 170.0}


def clock() -> str:
    return NOW


class FakeTools:
    """Scripted provider and solar position; Luan's real validation and transform."""

    def __init__(self, *fetches: object, solar_error: str | None = None, cached: dict | None = None, store_error: str | None = None) -> None:
        self._fetches, self._solar_error, self.fetch_count = list(fetches), solar_error, 0
        self._cached, self._store_error, self.stored = cached, store_error, []

    def fetch_weather(self, request):
        self.fetch_count += 1
        outcome = self._fetches.pop(0) if len(self._fetches) > 1 else self._fetches[0]
        if isinstance(outcome, Exception):
            raise outcome
        return copy.deepcopy(outcome)

    def validate_weather(self, weather, *, now, config):
        return validate_weather(weather, now=now, config=config)

    def calculate_solar_position(self, request):
        if self._solar_error:
            raise ToolError(self._solar_error)
        return dict(SOLAR)

    def transform_weather(self, weather, solar, *, panel_angle_deg):
        return transform_weather(weather, solar, panel_angle_deg=panel_angle_deg)

    def load_cached_weather(self, request):
        return copy.deepcopy(self._cached)

    def store_weather(self, request, weather):
        if self._store_error:
            raise ToolError(self._store_error)
        self.stored.append(weather)


def agent(tools: FakeTools, **options: object) -> LiveDataAgent:
    return LiveDataAgent(tools, REQUEST, DEFAULT_CONFIG, panel_angle_deg=35.0, clock=clock, now=clock, **options)


class LiveDataAgentTest(unittest.TestCase):
    def test_implements_the_shared_contracts(self) -> None:
        tools = FakeTools(RAW)

        self.assertIsInstance(tools, WeatherTools)
        self.assertIsInstance(agent(tools), DataAgentContract)

    def test_fresh_forecast_is_valid_and_becomes_model_inputs(self) -> None:
        update = agent(FakeTools(RAW)).run(pending_state())

        self.assertEqual(set(update), {"data", "weather", "agent_log", "tool_calls"})
        self.assertEqual((update["data"]["status"], update["data"]["forecast_age_minutes"], update["data"]["used_cache"]), ("VALID", 5.0, False))
        self.assertEqual((update["weather"]["panel_angle_deg"], update["weather"]["sun_elevation_deg"], update["weather"]["ghi_wm2"]), (35.0, 61.5, 850.0))
        self.assertEqual([call["tool"] for call in update["tool_calls"]], ["fetch_weather", "store_weather", "validate_weather", "calculate_solar_position", "transform_weather"])

    def test_a_fetched_observation_is_stored_for_later_fallback(self) -> None:
        tools = FakeTools(RAW)

        agent(tools).run(pending_state())

        self.assertEqual(tools.stored, [RAW])

    def test_storage_failure_is_recorded_and_does_not_stop_the_run(self) -> None:
        update = agent(FakeTools(RAW, store_error="database offline")).run(pending_state())

        self.assertEqual(update["data"]["status"], "VALID")
        self.assertIn("database offline", next(entry["result"] for entry in update["agent_log"] if entry["action"] == "cache"))

    def test_without_a_store_the_cache_tools_are_not_called(self) -> None:
        tools = FakeTools(RAW, store_error="must not be called")

        update = agent(tools, use_cache=False).run(pending_state())

        self.assertEqual([call["tool"] for call in update["tool_calls"]], ["fetch_weather", "validate_weather", "calculate_solar_position", "transform_weather"])

    def test_unknown_issue_time_stays_invalid_with_no_invented_age(self) -> None:
        update = agent(FakeTools({**RAW, "forecast_issued_at": None})).run(pending_state())

        self.assertEqual((update["data"]["status"], update["data"]["forecast_age_minutes"]), ("INVALID", None))
        self.assertIsNotNone(update["weather"])

    def test_stale_forecast_is_reported_stale(self) -> None:
        update = agent(FakeTools({**RAW, "forecast_issued_at": "2026-06-21T18:00:00+00:00"})).run(pending_state())

        self.assertEqual((update["data"]["status"], update["data"]["forecast_age_minutes"]), ("STALE", 70.0))

    def test_retries_a_failed_fetch(self) -> None:
        tools = FakeTools(ToolError("timed out"), RAW)

        update = agent(tools).run(pending_state())

        self.assertEqual(tools.fetch_count, 2)
        self.assertEqual(update["data"]["status"], "VALID")
        self.assertEqual([call["status"] for call in update["tool_calls"][:2]], ["ERROR", "OK"])

    def test_fetch_failure_without_cache_raises_instead_of_inventing_weather(self) -> None:
        tools = FakeTools(ToolError("connection failed"), cached=RAW)

        with self.assertRaises(StageError) as raised:
            agent(tools, use_cache=False).run(pending_state())

        self.assertEqual(tools.fetch_count, 2)
        self.assertEqual((raised.exception.agent, raised.exception.code), ("data", "DATA_UNAVAILABLE"))
        self.assertIn("connection failed", raised.exception.message)

    def test_fetch_failure_falls_back_to_cache_and_is_degraded(self) -> None:
        update = agent(FakeTools(ToolError("connection failed"), cached=RAW)).run(pending_state())

        self.assertEqual((update["data"]["status"], update["data"]["used_cache"]), ("DEGRADED", True))
        self.assertIn(CACHE_ISSUE, update["data"]["issues"])
        self.assertIsNotNone(update["weather"])

    def test_empty_cache_raises(self) -> None:
        with self.assertRaises(StageError):
            agent(FakeTools(ToolError("connection failed"))).run(pending_state())

    def test_missing_observation_gives_invalid_report_and_no_model_inputs(self) -> None:
        update = agent(FakeTools({**RAW, "ghi_wm2": None})).run(pending_state())

        self.assertEqual(update["data"]["status"], "INVALID")
        self.assertIsNone(update["weather"])

    def test_solar_failure_gives_invalid_report_and_no_model_inputs(self) -> None:
        update = agent(FakeTools(RAW, solar_error="ephemeris unavailable")).run(pending_state())

        self.assertEqual(update["data"]["status"], "INVALID")
        self.assertIsNone(update["weather"])
        self.assertIn("ephemeris unavailable", update["data"]["issues"][-1])

    def test_state_is_not_modified(self) -> None:
        state, before = pending_state(), pending_state()

        agent(FakeTools(RAW)).run(state)

        self.assertEqual(state, before)

    def test_rejects_zero_attempts(self) -> None:
        with self.assertRaises(ValueError):
            agent(FakeTools(RAW), attempts=0)


START_UNIX, END_UNIX = 1782068400, 1782072000  # 2026-06-21T19:00Z and 20:00Z
PROVIDER_REPLY = {
    "latitude": 51.04, "longitude": -114.07, "utc_offset_seconds": 0, "timezone": "GMT",
    "hourly_units": {"time": "unixtime", "temperature_2m": "\u00b0C", "cloud_cover": "%", "precipitation": "mm", "wind_speed_10m": "km/h", "wind_gusts_10m": "km/h", "shortwave_radiation": "W/m\u00b2", "direct_normal_irradiance": "W/m\u00b2", "diffuse_radiation": "W/m\u00b2"},
    "hourly": {"time": [START_UNIX, END_UNIX], "temperature_2m": [22.0, 23.0], "cloud_cover": [15, 20], "precipitation": [0.0, 0.1], "wind_speed_10m": [14.0, 15.0], "wind_gusts_10m": [20.0, 24.0], "shortwave_radiation": [800.0, 850.0], "direct_normal_irradiance": [700.0, 750.0], "diffuse_radiation": [190.0, 201.0]},
}


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


class SystemTrustClientTest(unittest.TestCase):
    def test_maps_the_provider_reply_with_the_pipeline_rules(self) -> None:
        requested = []

        def transport(url, timeout):
            requested.append(url)
            return Reply(json.dumps(PROVIDER_REPLY).encode())

        weather = SystemTrustOpenMeteoClient(transport=transport).fetch_weather(REQUEST)

        self.assertIn("latitude=51.0447", requested[0])
        self.assertTrue(requested[0].startswith("https://"))
        # Instant values come from the interval start, preceding-hour aggregates from its end.
        self.assertEqual((weather["temperature_c"], weather["wind_speed_kmh"], weather["wind_gust_kmh"], weather["ghi_wm2"]), (22.0, 14.0, 24.0, 850.0))
        self.assertIsNone(weather["forecast_issued_at"])

    def test_http_error_becomes_a_tool_error(self) -> None:
        def transport(url, timeout):
            raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, io.BytesIO(b""))

        with self.assertRaisesRegex(ToolError, "503"):
            SystemTrustOpenMeteoClient(transport=transport).fetch_weather(REQUEST)

    def test_connection_failure_becomes_a_tool_error(self) -> None:
        def transport(url, timeout):
            raise urllib.error.URLError("certificate verify failed")

        with self.assertRaisesRegex(ToolError, "connection failed"):
            SystemTrustOpenMeteoClient(transport=transport).fetch_weather(REQUEST)

    def test_malformed_reply_becomes_a_tool_error(self) -> None:
        with self.assertRaisesRegex(ToolError, "malformed"):
            SystemTrustOpenMeteoClient(transport=lambda url, timeout: Reply(b"<html>")).fetch_weather(REQUEST)

    def test_pipeline_tools_without_a_store_refuse_cache_operations(self) -> None:
        tools = PipelineWeatherTools(SystemTrustOpenMeteoClient(transport=lambda url, timeout: Reply(b"{}")))

        self.assertIsInstance(tools, WeatherTools)
        with self.assertRaises(ToolError):
            tools.load_cached_weather(REQUEST)
        with self.assertRaises(ToolError):
            tools.store_weather(REQUEST, RAW)

    def test_current_hour_request_is_hour_aligned_utc(self) -> None:
        from datetime import datetime, timedelta, timezone

        request = current_hour_request(51.0, -114.0, now=datetime(2026, 10, 4, 9, 47, 12, tzinfo=timezone(timedelta(hours=-6))))

        self.assertEqual((request.interval_start, request.prediction_horizon_minutes), ("2026-10-04T15:00:00Z", 60))


class LiveDataInFullRunTest(unittest.TestCase):
    def test_fresh_live_weather_can_authorize_rotate(self) -> None:
        payload = build_orchestrator(data=agent(FakeTools(RAW))).run(pending_state())

        validate_frontend_data(payload)
        self.assertEqual(payload["decision"]["action"], "ROTATE")
        self.assertEqual(payload["data_agent"]["source"], "test-provider")

    def test_unknown_issue_time_makes_the_manager_hold(self) -> None:
        payload = build_orchestrator(data=agent(FakeTools({**RAW, "forecast_issued_at": None}))).run(pending_state())

        validate_frontend_data(payload)
        self.assertEqual(payload["decision"]["action"], "HOLD")
        self.assertIsNotNone(payload["optimization"])

    def test_provider_outage_is_recorded_and_the_manager_holds(self) -> None:
        payload = build_orchestrator(data=agent(FakeTools(ToolError("connection failed")))).run(pending_state())

        validate_frontend_data(payload)
        self.assertEqual(payload["decision"]["action"], "HOLD")
        self.assertEqual(payload["errors"][0]["code"], "DATA_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
