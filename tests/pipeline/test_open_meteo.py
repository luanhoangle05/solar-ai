"""Deterministic mocked HTTP tests; never call the provider."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import unittest
from unittest.mock import Mock, patch
from typing import get_type_hints

import requests

from src.common.config import OpenMeteoConfig, DEFAULT_CONFIG
from src.common.tool_contracts import RawWeather, ToolError, WeatherRequest
from src.pipeline.client import OpenMeteoClient, VARIABLES
from src.pipeline.validate import validate_weather


REQUEST = WeatherRequest(51.0447, -114.0719, "2026-06-21T19:00:00Z", 60)


def provider_fixture():
    return {
        "latitude": 51.05, "longitude": -114.05, "timezone": "GMT",
        "utc_offset_seconds": 0, "generationtime_ms": 0.123,
        "hourly_units": {"time": "unixtime", **{name: value[1] for name, value in VARIABLES.items()}},
        "hourly": {
            "time": [1782068400, 1782072000],
            "temperature_2m": [22, 23], "cloud_cover": [15, 20],
            "precipitation": [99, 0.1], "wind_speed_10m": [14, 15],
            "wind_gusts_10m": [99, 24], "shortwave_radiation": [99, 850],
            "direct_normal_irradiance": [99, 750], "diffuse_radiation": [99, 201],
        },
    }


def response_fixture(payload=None, status=200):
    payload = provider_fixture() if payload is None else payload
    response = Mock(status_code=status)
    response.json.return_value = deepcopy(payload)
    response.content = json.dumps(payload).encode()
    return response


class OpenMeteoTests(unittest.TestCase):
    def fetch(self, payload=None, request=REQUEST):
        response = response_fixture(payload)
        with patch("src.pipeline.client.requests.get", return_value=response):
            result = OpenMeteoClient().fetch_weather(request)
        response.close.assert_called_once()
        return result

    def test_url_coordinates_horizon_units_and_single_attempt(self):
        response = response_fixture()
        with patch("src.pipeline.client.requests.get", return_value=response) as get:
            OpenMeteoClient().fetch_weather(REQUEST)
        get.assert_called_once_with("https://api.open-meteo.com/v1/forecast", params={
            "latitude": 51.0447, "longitude": -114.0719,
            "hourly": ",".join(VARIABLES), "timezone": "UTC", "timeformat": "unixtime",
            "temperature_unit": "celsius", "wind_speed_unit": "kmh", "precipitation_unit": "mm",
            "start_hour": "2026-06-21T19:00", "end_hour": "2026-06-21T20:00",
        }, timeout=15.0, allow_redirects=False)

    def test_all_eight_values_and_exact_contract(self):
        result = self.fetch()
        self.assertEqual(set(result), set(get_type_hints(RawWeather)))
        for field, expected in {"temperature_c": 22, "cloud_cover_pct": 15,
                "precipitation_mm": 0.1, "wind_speed_kmh": 14, "wind_gust_kmh": 24,
                "ghi_wm2": 850, "dni_wm2": 750, "dhi_wm2": 201}.items():
            self.assertEqual(result[field], expected)
        self.assertEqual(result["source"], "open-meteo")

    def test_real_utc_retrieval_time_and_unknown_issue(self):
        before = datetime.now(timezone.utc)
        weather = self.fetch()
        after = datetime.now(timezone.utc)
        fetched = datetime.fromisoformat(weather["fetched_at"])
        self.assertLessEqual(before, fetched)
        self.assertLessEqual(fetched, after)
        self.assertEqual(fetched.utcoffset().total_seconds(), 0)
        self.assertEqual(weather["timestamp"], "2026-06-21T19:00:00+00:00")
        self.assertIsNone(weather["forecast_issued_at"])

    def test_generation_duration_and_extra_issue_field_are_not_issue_time(self):
        payload = provider_fixture()
        payload.update(generationtime_ms=1782068000000, forecast_issued_at="untrusted")
        self.assertIsNone(self.fetch(payload)["forecast_issued_at"])

    def test_existing_freshness_policy_remains_invalid(self):
        weather = self.fetch()
        report = validate_weather(weather, now=weather["fetched_at"], config=DEFAULT_CONFIG)
        self.assertEqual(report["status"], "INVALID")
        self.assertEqual(report["issues"], ["forecast_issued_at: unknown; freshness cannot be established"])

    def test_equivalent_request_timezone(self):
        result = self.fetch(request=replace(REQUEST, interval_start="2026-06-21T13:00:00-06:00"))
        self.assertEqual(result["timestamp"], "2026-06-21T19:00:00+00:00")

    def test_invalid_requests_do_not_connect(self):
        for change in ({"latitude_deg": 91}, {"longitude_deg": -181}, {"latitude_deg": True},
                       {"prediction_horizon_minutes": 30}, {"prediction_horizon_minutes": True},
                       {"interval_start": "2026-06-21T19:30:00Z"},
                       {"interval_start": "2026-06-21T19:00:00"}):
            with self.subTest(change=change), patch("src.pipeline.client.requests.get") as get:
                with self.assertRaises(ToolError):
                    OpenMeteoClient().fetch_weather(replace(REQUEST, **change))
                get.assert_not_called()

    def test_midnight_fetch_window(self):
        from src.pipeline.client import _request_parameters
        _, _, params = _request_parameters(replace(REQUEST, interval_start="2026-06-21T23:00:00Z"))
        self.assertEqual(params["end_hour"], "2026-06-22T00:00")

    def test_all_required_units_checked(self):
        for variable in VARIABLES:
            payload = provider_fixture()
            payload["hourly_units"][variable] = "wrong"
            with self.subTest(variable=variable), self.assertRaisesRegex(ToolError, "unit"):
                self.fetch(payload)

    def test_missing_variables(self):
        for variable in VARIABLES:
            payload = provider_fixture()
            del payload["hourly"][variable]
            with self.subTest(variable=variable), self.assertRaisesRegex(ToolError, "missing hourly variable"):
                self.fetch(payload)

    def test_array_length_mismatches(self):
        for variable in VARIABLES:
            payload = provider_fixture()
            payload["hourly"][variable].pop()
            with self.subTest(variable=variable), self.assertRaisesRegex(ToolError, "array-length"):
                self.fetch(payload)

    def test_required_null_and_invalid_numeric_values(self):
        for variable, (_, _, aggregate) in VARIABLES.items():
            for invalid in (None, True, "12", float("nan"), float("inf")):
                payload = provider_fixture()
                payload["hourly"][variable][int(aggregate)] = invalid
                with self.subTest(variable=variable, invalid=invalid), self.assertRaises(ToolError):
                    self.fetch(payload)

    def test_nighttime_zero_and_negative_temperature_preserved(self):
        payload = provider_fixture()
        payload["hourly"]["temperature_2m"][0] = -20
        for field in ("shortwave_radiation", "direct_normal_irradiance", "diffuse_radiation"):
            payload["hourly"][field][1] = 0
        result = self.fetch(payload)
        self.assertEqual(result["temperature_c"], -20)
        self.assertEqual(result["ghi_wm2"], 0)

    def test_bad_response_shapes(self):
        for payload in ([], {}, {"error": True}, dict(provider_fixture(), hourly=None),
                        dict(provider_fixture(), hourly_units=None), dict(provider_fixture(), utc_offset_seconds=3600),
                        dict(provider_fixture(), timezone="America/Calgary"), dict(provider_fixture(), latitude=None)):
            with self.subTest(payload=payload), self.assertRaises(ToolError):
                self.fetch(payload)

    def test_bad_timestamps_and_missing_interval(self):
        for times in (["bad", "bad"], [True, False], [10**30, 10**30+3600],
                      [1782068400, 1782068400], [1782072000, 1782068400],
                      [1782068401, 1782072001], [1782064800, 1782068400]):
            payload = provider_fixture()
            payload["hourly"]["time"] = times
            with self.subTest(times=times), self.assertRaises(ToolError):
                self.fetch(payload)

    def test_malformed_json_closes_response(self):
        response = response_fixture()
        response.json.side_effect = ValueError("bad JSON")
        with patch("src.pipeline.client.requests.get", return_value=response), self.assertRaisesRegex(ToolError, "malformed JSON"):
            OpenMeteoClient().fetch_weather(REQUEST)
        response.close.assert_called_once()

    def test_timeout_connection_and_other_request_errors_no_retries(self):
        for error, message in ((requests.Timeout(), "timed out"),
                               (requests.ConnectionError(), "connection failed"),
                               (requests.RequestException(), "HTTP request failed")):
            with patch("src.pipeline.client.requests.get", side_effect=error) as get:
                with self.assertRaisesRegex(ToolError, message):
                    OpenMeteoClient().fetch_weather(REQUEST)
                get.assert_called_once()

    def test_http_failures_and_redirect_no_retry(self):
        for status in (400, 401, 429, 500, 503, 302):
            response = response_fixture(status=status)
            with patch("src.pipeline.client.requests.get", return_value=response) as get:
                with self.assertRaisesRegex(ToolError, f"HTTP {status}"):
                    OpenMeteoClient().fetch_weather(REQUEST)
                get.assert_called_once()
            response.close.assert_called_once()

    def test_provenance_isolated_and_cleared_on_failure(self):
        client, response = OpenMeteoClient(), response_fixture()
        with patch("src.pipeline.client.requests.get", return_value=response):
            weather = client.fetch_weather(REQUEST)
        provenance = client.last_provenance
        self.assertEqual(provenance["response_sha256"], hashlib.sha256(response.content).hexdigest())
        self.assertEqual(provenance["returned_coordinates"]["latitude"], 51.05)
        self.assertEqual(provenance["request_parameters"]["latitude"], REQUEST.latitude_deg)
        self.assertEqual(provenance["fetched_at"], weather["fetched_at"])
        provenance["payload"].clear()
        self.assertTrue(client.last_provenance["payload"])
        with patch("src.pipeline.client.requests.get", side_effect=requests.Timeout()), self.assertRaises(ToolError):
            client.fetch_weather(REQUEST)
        self.assertIsNone(client.last_provenance)

    def test_configuration_timeout_validation(self):
        for timeout in (0, -1, float("inf"), float("nan"), True):
            with self.assertRaises(ValueError):
                OpenMeteoConfig(timeout_seconds=timeout)

    def test_custom_provider_configuration(self):
        with patch("src.pipeline.client.requests.get", return_value=response_fixture()) as get:
            result = OpenMeteoClient(OpenMeteoConfig(timeout_seconds=2, source="open-meteo-demo")).fetch_weather(REQUEST)
        self.assertEqual(get.call_args.kwargs["timeout"], 2)
        self.assertEqual(result["source"], "open-meteo-demo")
