"""Live Data Agent built on Luan's pipeline tools. Owner: Duy (interim).

`src/agents/data_agent.py` is Luan's and is still a scaffold. This module is an
interim agent with the same constructor shape, so a full run can use live
weather today; it can be deleted when Luan's agent is delivered.

The agent coordinates tools and decides only what the contract gives it:
retries, cache fallback and how the result is reported. It never fills in a
missing value and never relaxes the validation tool: a forecast whose issue
time is unknown stays INVALID, which the Manager / Safety Agent answers with HOLD.
"""

from datetime import datetime, timezone
import json
from typing import Callable
import urllib.error
import urllib.parse
import urllib.request

from src.agents.reasoning import Reasoner
from src.agents.trace import Clock, TraceRecorder, utc_now_iso
from src.common.agent_contracts import DataAgentUpdate
from src.common.config import PREDICTION_HORIZON_MINUTES, OpenMeteoConfig, SimulationConfig
from src.common.schema import AgentState, DataAgentReport, FrontendData, WeatherFeatures
from src.common.tool_contracts import RawWeather, SolarPosition, ToolError, WeatherRequest, WeatherTools
from src.pipeline.client import OpenMeteoClient, _map_response, _request_parameters
from src.pipeline.storage import PostgresWeatherStorage
from src.pipeline.solar_position import calculate_solar_position
from src.pipeline.transform import transform_weather
from src.pipeline.validate import validate_weather
from src.models.data_loader import DatasetSource
from src.models.evaluation import EvaluatedModelingTools
from src.service.recommendation_service import run_recommendation


AGENT_NAME = "data"
DEFAULT_FETCH_ATTEMPTS = 2
CACHE_ISSUE = "Provider fetch failed; a cached observation was used instead."
NO_STORE = "no weather store is configured"
LIVE_WEATHER_ASSUMPTION = "LIVE WEATHER: the forecast for this hour was fetched from the provider during this run; the models were trained on the labeled dataset named above."


class SystemTrustOpenMeteoClient:
    """Luan's Open-Meteo request and response mapping, sent with the standard library.

    `OpenMeteoClient` uses `requests`, whose bundled certificates fail TLS
    verification on machines where traffic is inspected (this one included).
    The standard library verifies against the operating system's certificate
    store instead, so verification stays on. One request per call, no retries;
    the request parameters and the mapping to RawWeather are Luan's own functions.
    """

    def __init__(self, config: OpenMeteoConfig | None = None, *, transport: Callable[..., object] = urllib.request.urlopen) -> None:
        self.config, self._transport = config or OpenMeteoConfig(), transport

    def fetch_weather(self, request: WeatherRequest) -> RawWeather:
        start, end, parameters = _request_parameters(request)
        url = f"{self.config.base_url}?{urllib.parse.urlencode(parameters)}"
        try:
            with self._transport(url, timeout=self.config.timeout_seconds) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            raise ToolError(f"Open-Meteo HTTP {exc.code}; no retry attempted") from None
        except TimeoutError:
            raise ToolError("Open-Meteo request timed out") from None
        except OSError as exc:
            raise ToolError(f"Open-Meteo connection failed ({type(exc).__name__})") from None
        fetched_at = datetime.now(timezone.utc)  # body retrieved, not forecast issuance
        try:
            payload = json.loads(body)
        except ValueError:
            raise ToolError("Open-Meteo returned malformed JSON") from None
        return _map_response(payload, start, end, fetched_at, self.config.source)


class PipelineWeatherTools:
    """`WeatherTools` assembled from Luan's public pipeline functions; adds no behavior of its own.

    `storage` is Luan's PostgreSQL store. Without one there is no cache: the
    cache tools raise ToolError instead of pretending to load or save anything.
    """

    def __init__(self, client: OpenMeteoClient | SystemTrustOpenMeteoClient | None = None, storage: PostgresWeatherStorage | None = None) -> None:
        self._client, self._storage = client or OpenMeteoClient(OpenMeteoConfig()), storage

    def fetch_weather(self, request: WeatherRequest) -> RawWeather:
        return self._client.fetch_weather(request)

    def validate_weather(self, weather: RawWeather, *, now: str, config: SimulationConfig) -> DataAgentReport:
        return validate_weather(weather, now=now, config=config)

    def calculate_solar_position(self, request: WeatherRequest) -> SolarPosition:
        return calculate_solar_position(request)

    def transform_weather(self, weather: RawWeather, solar: SolarPosition, *, panel_angle_deg: float) -> WeatherFeatures:
        return transform_weather(weather, solar, panel_angle_deg=panel_angle_deg)

    def load_cached_weather(self, request: WeatherRequest) -> RawWeather | None:
        if self._storage is None:
            raise ToolError(f"Cannot load cached weather: {NO_STORE}")
        return self._storage.load_cached_weather(request)

    def store_weather(self, request: WeatherRequest, weather: RawWeather) -> None:
        if self._storage is None:
            raise ToolError(f"Cannot store weather: {NO_STORE}")
        self._storage.store_weather(request, weather)


class LiveDataAgent:
    """Fetch -> validate -> solar position -> features, with retries and a cache fallback.

    `use_cache=False` is for runs with no weather store: the cache tools are then not called at all.
    """

    def __init__(
        self, tools: WeatherTools, request: WeatherRequest, config: SimulationConfig, *,
        panel_angle_deg: float, use_cache: bool = True, attempts: int = DEFAULT_FETCH_ATTEMPTS,
        clock: Clock = utc_now_iso, now: Clock | None = None, reasoner: Reasoner | None = None,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        self.tools, self.request, self.config = tools, request, config
        self._panel_angle_deg, self._use_cache, self._attempts = panel_angle_deg, use_cache, attempts
        # Trace timestamps are whole seconds; freshness is judged against a full-precision clock so a just-fetched
        # observation is never reported as fetched in the future.
        self._clock, self._now, self._reasoner = clock, now or _precise_utc_now, reasoner

    def run(self, state: AgentState) -> DataAgentUpdate:
        """Return only `data` and `weather`. Raises StageError when no observation can be obtained at all."""
        recorder = TraceRecorder(AGENT_NAME, self._clock)
        raw, used_cache = self._obtain(recorder)
        try:
            report = recorder.call(
                "validate_weather",
                lambda: self.tools.validate_weather(raw, now=self._now(), config=self.config),
                lambda result: f"{result['status']}; forecast age {_age(result)}; {len(result['issues'])} issue(s)",
            )
        except ToolError as exc:
            raise recorder.fail("DATA_VALIDATION_FAILED", f"Weather could not be validated: {exc}") from exc
        if used_cache:
            report = _mark_cached(report)
        weather, report = self._features(recorder, raw, report)
        recorder.log("data_quality", _describe(report, weather is not None))
        recorder.reason(self._reasoner)
        return {"data": report, "weather": weather, **recorder.trace()}

    def _obtain(self, recorder: TraceRecorder) -> tuple[RawWeather, bool]:
        """The provider's observation, or the cached one when every attempt fails; never a made-up one."""
        failure = "no attempt made"
        for attempt in range(1, self._attempts + 1):
            try:
                raw = recorder.call("fetch_weather", lambda: self.tools.fetch_weather(self.request), lambda result: f"attempt {attempt}: received from {result.get('source', 'unknown')}")
            except ToolError as exc:
                failure = str(exc)
                continue
            self._store(recorder, raw)
            return raw, False
        if not self._use_cache:
            raise recorder.fail("DATA_UNAVAILABLE", f"Weather fetch failed after {self._attempts} attempt(s) and no cache is configured: {failure}")
        try:
            cached = recorder.call("load_cached_weather", lambda: self.tools.load_cached_weather(self.request), lambda result: "cached observation found" if result is not None else "no cached observation")
        except ToolError as exc:
            raise recorder.fail("DATA_UNAVAILABLE", f"Weather fetch failed ({failure}) and the cache lookup failed: {exc}") from exc
        if cached is None:
            raise recorder.fail("DATA_UNAVAILABLE", f"Weather fetch failed after {self._attempts} attempt(s) and the cache holds nothing for this interval: {failure}")
        return cached, True

    def _store(self, recorder: TraceRecorder, raw: RawWeather) -> None:
        """Keep the observation for later cache fallback. A storage failure is recorded and does not stop the run."""
        if not self._use_cache:
            recorder.log("cache", "Observation not stored: this run has no weather store configured")
            return
        try:
            recorder.call("store_weather", lambda: self.tools.store_weather(self.request, raw), lambda _: "observation stored for cache fallback")
        except ToolError as exc:
            recorder.log("cache", f"Observation could not be stored; continuing without it: {exc}")

    def _features(self, recorder: TraceRecorder, raw: RawWeather, report: DataAgentReport) -> tuple[WeatherFeatures | None, DataAgentReport]:
        """Model inputs for the observation, or None (and an INVALID report) when they cannot be built."""
        try:
            solar = recorder.call(
                "calculate_solar_position", lambda: self.tools.calculate_solar_position(self.request),
                lambda result: f"elevation {result['sun_elevation_deg']:.1f} deg, azimuth {result['sun_azimuth_deg']:.1f} deg",
            )
            weather = recorder.call(
                "transform_weather", lambda: self.tools.transform_weather(raw, solar, panel_angle_deg=self._panel_angle_deg),
                lambda result: f"features for {result['timestamp']} at panel angle {result['panel_angle_deg']:g} deg",
            )
        except ToolError as exc:
            return None, {**report, "status": "INVALID", "issues": [*report["issues"], f"Model inputs could not be built: {exc}"]}
        return weather, report


def _precise_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _age(report: DataAgentReport) -> str:
    age = report["forecast_age_minutes"]
    return "unknown" if age is None else f"{age:g} min"


def _mark_cached(report: DataAgentReport) -> DataAgentReport:
    """A cached observation is never better than DEGRADED, and says why."""
    status = "DEGRADED" if report["status"] == "VALID" else report["status"]
    return {**report, "status": status, "used_cache": True, "issues": [*report["issues"], CACHE_ISSUE]}


def _describe(report: DataAgentReport, has_features: bool) -> str:
    issues = "; ".join(report["issues"]) or "none"
    features = "model inputs built" if has_features else "no model inputs"
    return f"Data status {report['status']} from {report['source']}; forecast age {_age(report)}; {features}. Issues: {issues}"


def current_hour_request(latitude_deg: float, longitude_deg: float, *, now: datetime | None = None) -> WeatherRequest:
    """A request for the UTC hour that is in progress, which is the interval the provider and the models work in."""
    start = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return WeatherRequest(latitude_deg, longitude_deg, start.strftime("%Y-%m-%dT%H:%M:%SZ"), PREDICTION_HORIZON_MINUTES)


def recommend_live(
    source: DatasetSource,
    request: WeatherRequest,
    modeling_tools: EvaluatedModelingTools,
    config: SimulationConfig,
    *,
    current_angle_deg: float,
    control_target_id: str,
    run_id: str,
    tools: WeatherTools | None = None,
    use_cache: bool = False,
    reasoner: Reasoner | None = None,
    clock: Clock = utc_now_iso,
) -> FrontendData:
    """A full run on weather fetched now. Makes one or two provider requests; no cache unless a store is configured."""
    data_agent = LiveDataAgent(
        tools or PipelineWeatherTools(SystemTrustOpenMeteoClient()), request, config,
        panel_angle_deg=current_angle_deg, use_cache=use_cache, clock=clock, reasoner=reasoner,
    )
    return run_recommendation(
        source, data_agent, modeling_tools, config,
        interval_start=request.interval_start, current_angle_deg=current_angle_deg, control_target_id=control_target_id,
        run_id=run_id, extra_assumptions=(LIVE_WEATHER_ASSUMPTION,), reasoner=reasoner, clock=clock,
    )
