# Local PostgreSQL foundation (Step 4 only)

One PostgreSQL 17.11 service; Python and future dbt run locally. Duy and Tung
can keep working with committed mock contracts without Docker. No weather
storage/cache, provider calls, Data Agent, dbt models or ML training is added.

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
and closes. Only connection checks are implemented; no WeatherTools cache or
storage signatures were changed. Existing SimulationConfig remains unchanged.

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
Remove-Item Env:RUN_POSTGRES_TESTS
Remove-Item Env:RUN_POSTGRES_RESTART_TEST
```

Tests insert unique temporary run IDs and clean up only their own records.
They verify repeatable bootstrap, transaction rollback, connection closure
and preservation of a committed record across container restart.

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
