# Open-Meteo adapter (Step 6)

`OpenMeteoClient.fetch_weather(WeatherRequest) -> RawWeather` implements only
provider access. No agent, retries, cache fallback, dbt, labels or training.
Provider settings live in `OpenMeteoConfig` in `src/common/config.py`:
HTTPS `https://api.open-meteo.com/v1/forecast`, source `open-meteo`, and a
15-second Requests timeout. This bounds connection/read inactivity, not a
strict wall-clock deadline. Requests is an explicit pinned dependency.

## Provider mapping

Checked against [Open-Meteo forecast documentation](https://open-meteo.com/en/docs).
All requested field names match the proposed names; no aliases were necessary.

| Hourly provider variable | RawWeather | Unit | Selected time |
|---|---|---|---|
| temperature_2m | temperature_c | °C | start |
| cloud_cover | cloud_cover_pct | % | start |
| precipitation | precipitation_mm | mm | end |
| wind_speed_10m | wind_speed_kmh | km/h | start |
| wind_gusts_10m | wind_gust_kmh | km/h | end |
| shortwave_radiation | ghi_wm2 | W/m² | end |
| direct_normal_irradiance | dni_wm2 | W/m² | end |
| diffuse_radiation | dhi_wm2 | W/m² | end |

## Request and interval policy

For project interval `[T, T+1h)`, request `start_hour=T` and `end_hour=T+1h`.
These two boundary samples are the smallest window supporting the mapping.
Coordinates come directly from WeatherRequest. Explicit parameters are
`temperature_unit=celsius`, `wind_speed_unit=kmh`, `precipitation_unit=mm`,
`timezone=UTC`, `timeformat=unixtime`, and the eight-variable `hourly` list.
No explicit model is selected (provider Best Match).

The adapter uses instant temperature/cloud/wind at T as representative
start-of-interval conditions. Precipitation is the preceding-hour total,
gust the preceding-hour maximum, and radiation the preceding-hour mean,
so their values at T+1h cover the requested interval. Radiation is neither
instantaneous nor an energy quantity; no multiplication/conversion to kWh occurs.
The returned `timestamp` remains T. Solar position stays in its existing module.

Only a 60-minute, UTC-hour-aligned request is representable without inventing
interpolation. Other horizons or fractional-hour starts raise ToolError before
HTTP. Equivalent timezone-aware start strings normalize to UTC. Out-of-range
forecast dates are provider errors; the adapter does not switch to archive APIs.

## Time and quality

- `timestamp`: project interval start; never download time.
- `fetched_at`: UTC clock immediately after Requests has retrieved the body.
- `forecast_issued_at`: always None; this endpoint does not establish reliable
  model issuance. `generationtime_ms` is processing duration, not issuance.

Returned Unix timestamps are parsed as aware UTC. Response timezone/offset,
coordinate metadata, units, ordered unique hourly timestamps, matching array
lengths and required selected values are checked. No unit guessing or null
imputation occurs. Ranges/cross-field quality remain the existing validator's
responsibility; valid numeric shape does not guarantee acceptable data quality.

Unknown issuance produces INVALID under the unchanged freshness policy, even
with good weather values. This is an honest successful fetch with unavailable
freshness evidence, not operational permission to ROTATE. Step 7 must explicitly
decide how to handle that limitation. No policy change was made here.

## Provenance and storage boundary

The result has exactly the existing RawWeather fields. A defensive-copy
`client.last_provenance` snapshot retains the actual request, returned grid
coordinates, provider timezone/offset, full parsed response and SHA-256 of response
bytes. It is cleared before every attempt; clients are for sequential use.
Returned grid coordinates may differ from requested site coordinates.

The snapshot is internal and in-memory only. Existing `store_weather()` persists
the requested site, normalized RawWeather and its hash, original source/times,
validation status and request interval. It does **not** persist the external
provider envelope or the diagnostic snapshot. No new database schema or shared
contract was introduced to imply otherwise. A future internal provenance writer
can be separately approved if durable provider-envelope auditing is required.

## Failures

One HTTP attempt; redirects disabled, no retry adapter or fallback. Timeout,
connection failures, other Requests errors, non-200 status (including 400/429/500),
bad JSON, malformed metadata/arrays, missing interval/variables, wrong units,
and null/nonfinite selected values become ToolError. HTTP messages include status,
not provider response bodies. Responses close on both success and failure.

## Verification

Offline tests patch Requests and use a small synthetic response unrelated to the
canonical mocks. Normal test discovery never contacts Open-Meteo.

```powershell
.\.venv\Scripts\python.exe -m unittest tests.pipeline.test_open_meteo -v
$env:RUN_POSTGRES_TESTS = '1'
.\.venv\Scripts\python.exe -m unittest tests.integration.test_open_meteo_storage -v
Remove-Item Env:RUN_POSTGRES_TESTS
```

Explicit live check (one call), after offline tests and database bootstrap:

```powershell
.\.venv\Scripts\python.exe -m scripts.open_meteo_smoke --postgres-roundtrip
```

Defaults use Calgary coordinates from central config and the next UTC hour.
Override with `--latitude`, `--longitude`, `--interval-start`. The smoke prints
mapped values/provenance and expected freshness failure, compares the cached
payload exactly, then deletes only its own run's temporary database records.
A pre-existing different/latest cached revision causes an explicit comparison
failure, not deletion or replacement of that revision. Without
`--postgres-roundtrip`, it only fetches and validates; no database is needed.
