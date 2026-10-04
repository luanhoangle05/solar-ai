"""Explicit local database bootstrap and read-only smoke check. No cache logic."""

import argparse
from pathlib import Path

from src.common.config import DatabaseConfig, load_database_config
from src.common.tool_contracts import ToolError
from src.pipeline.storage import database_connection


BOOTSTRAP = Path(__file__).resolve().parents[1] / "sql" / "001_foundation.sql"
EXPECTED_TABLES = {
    ("ops", "pipeline_runs"), ("ingest", "weather_fetches"),
    ("ingest", "weather_hourly"), ("ingest", "solar_position"),
}


def bootstrap_database(config: DatabaseConfig) -> None:
    """Execute repeatable schema creation in a single transaction."""
    with database_connection(config) as connection:
        connection.execute(BOOTSTRAP.read_text(encoding="utf-8"))


def smoke_check(config: DatabaseConfig) -> dict:
    """Verify SELECT, expected relations, and timezone-aware timestamp types."""
    with database_connection(config) as connection:
        if connection.execute("SELECT 1").fetchone() != (1,):
            raise ToolError("Database SELECT check failed")
        version = connection.execute("SHOW server_version").fetchone()[0]
        tables = set(connection.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_schema IN ('ops', 'ingest') AND table_type = 'BASE TABLE'"
        ).fetchall())
        if not EXPECTED_TABLES <= tables:
            raise ToolError("Required foundation tables are missing; run bootstrap")
        invalid_times = connection.execute(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_schema IN ('ops', 'ingest') "
            "AND column_name IN ('started_at', 'finished_at', 'fetched_at', "
            "'forecast_issued_at', 'interval_start', 'calculated_for') "
            "AND data_type <> 'timestamp with time zone'"
        ).fetchone()[0]
        if invalid_times:
            raise ToolError("Foundation timestamp types do not match expected schema")
    return {"server_version": version, "tables": sorted(EXPECTED_TABLES)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("bootstrap", "smoke"))
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    try:
        config = load_database_config(args.env_file)
        if args.command == "bootstrap":
            bootstrap_database(config)
            print("Database foundation bootstrap complete.")
        else:
            print(smoke_check(config))
    except (ValueError, OSError, ToolError) as exc:
        parser.exit(1, f"Database command failed: {exc}\n")


if __name__ == "__main__":
    main()
