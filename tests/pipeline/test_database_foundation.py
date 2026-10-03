"""Database configuration/lifecycle unit tests; no running server required."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import psycopg

from src.common.config import DatabaseConfig, load_database_config
from src.common.tool_contracts import ToolError
from src.pipeline.storage import check_database_connection, database_connection


VALUES = {"POSTGRES_DB": "unit_db", "POSTGRES_USER": "unit_user", "POSTGRES_PASSWORD": "unit-secret"}


class DatabaseConfigTests(unittest.TestCase):
    def test_defaults_and_password_redaction(self):
        config = DatabaseConfig.from_env(VALUES)
        self.assertEqual((config.host, config.port), ("127.0.0.1", 5432))
        self.assertNotIn(VALUES["POSTGRES_PASSWORD"], repr(config))

    def test_missing_values_and_ports(self):
        for key in VALUES:
            with self.subTest(key=key), self.assertRaises(ValueError):
                DatabaseConfig.from_env({k: v for k, v in VALUES.items() if k != key})
        for port in ("bad", "0", "65536"):
            with self.subTest(port=port), self.assertRaises(ValueError):
                DatabaseConfig.from_env(dict(VALUES, POSTGRES_PORT=port))

    def test_env_file_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text("\n".join(f"{k}={v}" for k, v in VALUES.items()) + "\nPOSTGRES_PORT=5433\n", encoding="utf-8")
            with patch.dict("os.environ", {"POSTGRES_PORT": "5434"}, clear=True):
                config = load_database_config(path)
                self.assertEqual(config.port, 5434)
                self.assertEqual(config.dbname, "unit_db")

    def test_missing_file_can_use_environment(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict("os.environ", VALUES, clear=True):
            self.assertEqual(load_database_config(Path(folder) / "absent").user, "unit_user")

    def test_unsupported_secret_syntax_does_not_leak(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict("os.environ", {}, clear=True):
            path = Path(folder) / ".env"
            for secret in ("'$secret'", "two words", "secret#comment"):
                path.write_text("POSTGRES_PASSWORD=" + secret, encoding="utf-8")
                with self.assertRaises(ValueError) as error:
                    load_database_config(path)
                self.assertNotIn(secret, str(error.exception))

    def test_duplicate_setting_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text("POSTGRES_DB=a\nPOSTGRES_DB=b", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_database_config(path)


class DatabaseConnectionTests(unittest.TestCase):
    @patch("src.pipeline.storage.psycopg.connect")
    def test_query_and_clean_context_exit(self, connect):
        connection = connect.return_value.__enter__.return_value
        connection.execute.return_value.fetchone.return_value = (1,)
        self.assertTrue(check_database_connection(DatabaseConfig.from_env(VALUES)))
        connection.execute.assert_called_once_with("SELECT 1")
        connect.return_value.__exit__.assert_called_once_with(None, None, None)
        self.assertEqual(connect.call_args.kwargs["connect_timeout"], 5)

    @patch("src.pipeline.storage.psycopg.connect")
    def test_failure_is_passed_to_context_for_rollback(self, connect):
        connect.return_value.__exit__.return_value = False
        with self.assertRaises(RuntimeError):
            with database_connection(DatabaseConfig.from_env(VALUES)):
                raise RuntimeError("test rollback")
        self.assertIs(connect.return_value.__exit__.call_args.args[0], RuntimeError)

    @patch("src.pipeline.storage.psycopg.connect")
    def test_database_error_is_sanitized(self, connect):
        connect.side_effect = psycopg.OperationalError("unit-secret connection detail")
        with self.assertRaises(ToolError) as error:
            check_database_connection(DatabaseConfig.from_env(VALUES))
        self.assertNotIn("unit-secret", str(error.exception))
