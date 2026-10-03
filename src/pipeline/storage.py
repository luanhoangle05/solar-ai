"""PostgreSQL connection foundation only. Weather storage/cache is Step 5."""

from contextlib import contextmanager
from collections.abc import Iterator

import psycopg

from src.common.config import DatabaseConfig
from src.common.tool_contracts import ToolError


@contextmanager
def database_connection(config: DatabaseConfig) -> Iterator[psycopg.Connection]:
    """Commit on success, roll back on failure, and always close the connection.

    Use keyword parameters rather than constructing/logging a credential DSN.
    Database exceptions are reduced to a safe message (no credential details).
    """
    try:
        with psycopg.connect(
            dbname=config.dbname, user=config.user, password=config.password,
            host=config.host, port=config.port, connect_timeout=config.connect_timeout,
            application_name="solar-farm-ai", options="-c timezone=UTC",
        ) as connection:
            yield connection
    except psycopg.Error:
        raise ToolError("PostgreSQL operation failed; check database health and configuration") from None


def check_database_connection(config: DatabaseConfig) -> bool:
    """Perform a minimal query with automatic connection cleanup."""
    with database_connection(config) as connection:
        return connection.execute("SELECT 1").fetchone() == (1,)
