"""Opt-in real PostgreSQL tests. Ordinary discovery skips this entire class."""

import os
import subprocess
from pathlib import Path
import unittest
from uuid import uuid4

import psycopg

from scripts.database import bootstrap_database, smoke_check, EXPECTED_TABLES
from src.common.config import load_database_config
from src.pipeline.storage import database_connection


@unittest.skipUnless(os.environ.get("RUN_POSTGRES_TESTS") == "1", "Opt-in PostgreSQL integration")
class PostgresFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_database_config()

    def test_connectivity_tables_and_connection_closes(self):
        self.assertEqual(set(smoke_check(self.config)["tables"]), EXPECTED_TABLES)
        with database_connection(self.config) as connection:
            self.assertEqual(connection.execute("SELECT 1").fetchone(), (1,))
        self.assertTrue(connection.closed)

    def test_bootstrap_twice_preserves_records(self):
        run_id = uuid4()
        try:
            with database_connection(self.config) as connection:
                connection.execute("INSERT INTO ops.pipeline_runs(run_id,status,config_version) VALUES (%s,'RUNNING','bootstrap-test')", (run_id,))
            bootstrap_database(self.config)
            bootstrap_database(self.config)
            with database_connection(self.config) as connection:
                self.assertEqual(connection.execute("SELECT count(*) FROM ops.pipeline_runs WHERE run_id=%s", (run_id,)).fetchone(), (1,))
        finally:
            with database_connection(self.config) as connection:
                connection.execute("DELETE FROM ops.pipeline_runs WHERE run_id=%s", (run_id,))

    def test_unique_keys_and_transaction_rollback(self):
        run_id = uuid4()
        with database_connection(self.config) as connection:
            with self.assertRaises(psycopg.errors.UniqueViolation):
                with connection.transaction():
                    for _ in range(2):
                        connection.execute("INSERT INTO ops.pipeline_runs(run_id,status,config_version) VALUES (%s,'RUNNING','rollback-test')", (run_id,))
            self.assertEqual(connection.execute("SELECT count(*) FROM ops.pipeline_runs WHERE run_id=%s", (run_id,)).fetchone(), (0,))

    @unittest.skipUnless(os.environ.get("RUN_POSTGRES_RESTART_TEST") == "1", "Opt-in container restart")
    def test_committed_data_survives_container_restart(self):
        run_id = uuid4()
        try:
            with database_connection(self.config) as connection:
                connection.execute("INSERT INTO ops.pipeline_runs(run_id,status,config_version) VALUES (%s,'RUNNING','restart-test')", (run_id,))
            root = Path(__file__).resolve().parents[2]
            subprocess.run(["docker", "compose", "restart", "postgres"], cwd=root, check=True, timeout=60)
            subprocess.run(["docker", "compose", "up", "-d", "--wait", "--wait-timeout", "60", "postgres"], cwd=root, check=True, timeout=90)
            with database_connection(self.config) as connection:
                self.assertEqual(connection.execute("SELECT config_version FROM ops.pipeline_runs WHERE run_id=%s", (run_id,)).fetchone(), ("restart-test",))
        finally:
            with database_connection(self.config) as connection:
                connection.execute("DELETE FROM ops.pipeline_runs WHERE run_id=%s", (run_id,))
