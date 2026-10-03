# Local PostgreSQL foundation and storage (Steps 4–5)

One PostgreSQL 17.11 service; Python and future dbt run locally. Duy and Tung
can keep working with committed mock contracts without Docker. Weather storage
and cache retrieval are implemented; provider calls, Data Agent, dbt models
and ML training remain deferred.

## Setup

Use the repository root and the existing Python 3.11 virtual environment.
Install the approved requirements if setting up a new checkout:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` only if `.env` does not already exist. Fill in a
private random password. Never commit `.env`. It is already ignored by Git.
The example deliberately has an empty password so startup fails until set.
Use plain unquoted `KEY=value` entries without spaces, `$`, quotes or inline
comments, supported identically by this project's small loader and Compose.
A random hex password avoids interpolation/quoting surprises. Shell variables
override file entries; use the same environment for Compose and Python.

Settings: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD are required;
POSTGRES_HOST defaults to 127.0.0.1 and POSTGRES_PORT to 5432. Host is for local
Python connections, not a Docker bind address. The Compose port is always
bound to 127.0.0.1. Change POSTGRES_PORT if another service uses 5432.
Configuration is centralized in src/common/config.py; passwords are excluded
from config repr and connection errors. Do not print `docker compose config`
or inspect container environment output when sharing logs: it can show secrets.

```powershell
docker compose up -d
docker compose ps
docker compose up -d --wait --wait-timeout 60
.\.venv\Scripts\python.exe -m scripts.database bootstrap
.\.venv\Scripts\python.exe -m scripts.database smoke
```

The health check tests server readiness; the Python smoke command verifies
authenticated connectivity and the expected tables/timestamp types.

## Bootstrap and schema ownership

`sql/001_foundation.sql` is run explicitly through psycopg in one transaction.
It uses CREATE IF NOT EXISTS for repeatable reruns and is not tied to Docker's
first-start hooks. Run it twice safely. It does not migrate existing schemas
or repair drift; future changes require a new reviewed SQL version.

Created objects:

- ops.pipeline_runs: execution status/counts/errors, keyed by run_id.
- ingest.weather_fetches: request/provider/site/payload provenance; unique
  idempotency_key and fetch_id. The future loader must derive a stable key
  including request/site and forecast revision/payload identity. Repeated
  attempts reuse the key; revised forecasts get new keys instead of overwrites.
- ingest.weather_hourly: one interval per fetch; composite primary key stops
  duplicate intervals within the same fetch while preserving revised fetches.
- ingest.solar_position: one site/interval/calculation version. Site IDs must
  identify immutable coordinates; calculation_version captures assumptions.

Fetched time, nullable forecast issue time and interval start remain distinct
timestamptz columns. Hourly ingestion fields allow missing/invalid source data
with validation_status/issues; SQL constraints are not a replacement for
Python weather validation or future dbt tests. No energy labels or marts exist.

The connection context commits successful operations, rolls back failed ones
and closes. No WeatherTools cache or storage signatures were changed.
Existing SimulationConfig remains unchanged.

## Weather storage and cache (Step 5)

`PostgresWeatherStorage(config)` implements the existing `store_weather(request,
weather) -> None` and `load_cached_weather(request) -> RawWeather | None`
signatures. It is the storage component for a future WeatherTools adapter,
not a complete WeatherTools implementation or Data Agent.

Flow: check representability and request alignment → compute validation and
identity → transaction → fetch provenance plus hourly row → commit.
Each RawWeather call contains one interval, so each new fetch currently owns
one hourly row. A future provider may have a multi-hour envelope; that adapter
must map it without inventing unavailable provenance.

The shared request has coordinates but no site ID. Internally the site ID is
a SHA-256 of canonical numeric latitude/longitude (signed zero normalized).
No coordinate rounding is used. Cache lookup requires matching coordinates,
UTC interval start and the shared 60-minute horizon. Other horizons raise
ToolError, rather than returning a different interval.

The fetch stores source, coordinates, normalized request parameters, original
fetched_at/forecast_issued_at, and a copy/hash of the supplied RawWeather payload.
That payload is the normalized adapter output, **not** an original external
provider response: the current shared interface supplies neither a provider
envelope nor provider-model metadata. `provider_model` stays NULL.

Hourly rows retain all canonical values, including missing values and invalid
ranges, plus validation status/issues computed at the original fetch time
using the supplied SimulationConfig. Malformed timestamps, mismatched intervals,
nonfinite numbers and values that cannot be represented by the contract are
rejected before persistence. Missing issue time stays NULL and validates INVALID.
No imputation, filtering for freshness, or timestamp refresh occurs on read.
RawWeather has no validation field: the validation snapshot stays in PostgreSQL;
the future Data Agent must revalidate retrieved weather at its current clock.

### Idempotency and revisions

The version-1 key hashes canonical request metadata, source, issue timestamp,
interval and weather values, excluding fetched_at. UTC-equivalent timestamps
and equivalent numeric spellings share an identity. An unchanged retry keeps
the first fetch time, payload and validation snapshot, even if downloaded again
later. A changed issue time or weather value creates a new revision. No historical
revision is overwritten or deleted. An advisory transaction lock serializes
identical concurrent writes; the database unique key is the final constraint.
Duplicates create neither hourly rows nor automatic run records. A duplicate
already owned by an earlier run stays attributed to that first run.

Cache order is `forecast_issued_at DESC NULLS LAST`, then `fetched_at DESC`,
then `idempotency_key DESC` for a stable tie. Known issuance takes precedence
over unknown issuance. With no known issuance, the latest fetch wins. The shared
request has no provider selector, so all sources at the site participate.
The result can be invalid or stale; storage does not decide acceptability.
It returns the original payload including original timestamp spellings.

### Solar positions and pipeline runs

`store_solar_position(request, solar)` persists enrichment calculated by the
existing offline pvlib function. `calculated_for` is exactly interval start plus
30 minutes. Its key is site/interval/horizon/calculation version; the default
version records pvlib version, algorithm, altitude assumption and midpoint.
Identical repeats are no-ops. Different angles under the same key raise ToolError;
a changed calculation requires an explicit new version. This helper persists
supplied angles; it does not calculate them or generate energy labels.

`start_run()` returns a UUID. Pass it as `run_id` when constructing storage to
group writes, then call `complete_run()` or `fail_run()` explicitly. Writes lock
the run and require RUNNING status. Finalization computes persisted row and
accepted-row counts; `run_counts()` also returns fetch counts. Accepted means
VALID/DEGRADED at ingestion, not a promise of freshness now. Counts describe
unique persisted observations, not retry attempts. Failure summaries must be
caller-sanitized and are length-limited. Finalization of an already finished run
raises ToolError. Unbound writes create one completed run per new fetch atomically.

A failed weather write rolls back its fetch, hourly row and automatic run together.
Explicit runs remain RUNNING until the caller records failure. Solar persistence
is a separate atomic operation; orchestration across stages remains deferred.
Connections always close; PostgreSQL errors become the existing ToolError without
database/credential details. Failures are not silently swallowed.

## Tests

Normal tests do not require a running database; real DB tests skip by default:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Opt-in database tests after bootstrap (the restart flag restarts only this
project's PostgreSQL service; avoid using it during someone else's query):

```powershell
$env:RUN_POSTGRES_TESTS = '1'
$env:RUN_POSTGRES_RESTART_TEST = '1'
.\.venv\Scripts\python.exe -m unittest tests.integration.test_postgres_foundation -v
.\.venv\Scripts\python.exe -m unittest tests.integration.test_postgres_storage -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:RUN_POSTGRES_TESTS
Remove-Item Env:RUN_POSTGRES_RESTART_TEST
```

Tests insert unique temporary run IDs and clean up only their own records.
They verify repeatable bootstrap, transaction rollback, connection closure
and preservation of a committed record across container restart.
Storage tests additionally cover site/interval isolation, concurrent retries,
revision selection, original provenance, invalid-data retention, atomic write
failure, run lifecycle, solar repeatability and weather surviving restart.

## Lifecycle and local security

```powershell
docker compose stop
docker compose start
docker compose down
```

Stop and down preserve the named volume `solar-farm-ai_postgres_data`. The
service has no automatic restart policy; start it explicitly when needed.

**DESTRUCTIVE, intentional reset only:** `docker compose down --volumes`
deletes this project's local database volume and all its contents. This is
not part of normal startup or tests. Bootstrap again after an intentional reset.

Changing POSTGRES_USER/PASSWORD/DB does not update an initialized volume.
Use SQL administration or an intentional disposable-data reset; never assume
restarting Compose rotates database credentials. The local bootstrap user is
a database superuser created by the image. This loopback-only setup is for
development, not production. Restrict database roles and use managed secrets
before any future remote deployment. A named volume is persistence, not backup.
