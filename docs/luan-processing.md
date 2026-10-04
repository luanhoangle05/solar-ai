# Luan processing checkpoint: Steps 1–3

Only offline validation, canonical transformation and solar position are
implemented. The provider, storage, Data Agent, dbt and models remain stubs.
Shared contracts and canonical mock files are unchanged.

## Running the tests

Use the existing Python 3.11 environment from the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The approved dependencies for this checkpoint are pinned in requirements.txt:
pandas 2.3.3 and pvlib 0.13.1. pvlib also installs scientific dependencies and
Requests; no weather API is called by this code or these tests.

## Validation

`validate_weather(weather, *, now, config)` returns the existing
`DataAgentReport`. It accepts canonical RawWeather fields only. Nulls,
nonfinite values, numeric strings, booleans, malformed/naive timestamps,
negative nonnegative quantities, cloud cover outside 0..100, gust below
sustained wind, and impossible issuance/fetch chronology are INVALID.
Negative temperature and zero nighttime radiation are valid.

Forecast age comes from `forecast_issued_at`. Unknown or future issuance is
INVALID with null age. Future fetch timestamps are INVALID. Forecast target
intervals may be in the future. Age greater than the configured maximum is
STALE; equality is allowed. Structural invalidity takes priority over stale
age. The caller supplies the clock, making tests deterministic. Bad caller
clock/configuration raises ToolError rather than fabricating a report.

This is data validation, not a wind-safety controller. `used_cache` is False
because the pure validator cannot know where the caller obtained a record.
The future Data Agent must mark actual cache use and any DEGRADED status.

## Transformation

`transform_weather(weather, solar, *, panel_angle_deg)` produces exactly
WeatherFeatures. It returns a new object with UTC ISO timestamps and native
float values, excludes target/provenance fields, validates solar/tilt ranges,
and never fills missing values or clamps invalid values.

RawWeather already specifies C, %, mm, km/h, W/m2 and interval-start semantics.
The transform preserves these units and does not guess Fahrenheit, m/s, or
provider time conventions. Open-Meteo mapping and conversion belong to the
later provider adapter. Unknown forecast issuance can be transformed, but
cannot pass operational freshness validation. Transformation has no clock
argument and does not authorize using stale weather operationally.

SolarPosition carries no timestamp in the existing contract. The caller is
responsible for pairing it with weather from the same site/interval.

## Solar-position convention

`calculate_solar_position(request)` validates coordinates, an aware interval
start, and the existing 60-minute horizon. It uses pvlib's NREL NumPy SPA
implementation, evaluated at interval midpoint (start + 30 minutes). This is
a representative solar position, not an integrated irradiance or PV label.

Output is geometric elevation (not atmospheric-refraction-adjusted elevation)
and azimuth clockwise from north in [0, 360). Negative nighttime elevation is
preserved. With no altitude in WeatherRequest, the adapter explicitly uses
sea level as an approximation. Delta-T is estimated locally by pvlib; no
network lookup is needed. Real-site altitude support can be considered later
without silently changing the shared request.

The reference test uses the NREL example coordinates/time and published
geometric elevation/azimuth recorded in pvlib's reference tests, with 0.02
degree tolerance for differing altitude/delta-T settings:
https://github.com/pvlib/pvlib-python/blob/v0.13.1/tests/test_solarposition.py

## Remaining decisions

No shared-contract change was needed. Before a live pipeline, establish
provider issue-time availability/freshness policy and interval mapping. The
Data Agent's current-angle wiring and actual site parameters remain later
integration decisions. None blocks PostgreSQL/Compose foundation work after
the next explicit approval. No database/container tooling has been installed
or configured by this checkpoint.
