"""Focused regression tests for MariaDB data-source connection handling."""

from __future__ import annotations

import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


API_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = API_ROOT / "controllers" / "datasource" / "database_schema_extractor.py"


def _stub_module(name: str, **attributes):
    module = types.ModuleType(name)
    for attribute, value in attributes.items():
        setattr(module, attribute, value)
    return module


def _load_extractor_module():
    """Load the connection module without initializing unrelated application services."""
    # The application initializes Flask-SQLAlchemy before registering controllers.
    # Mirror that import order so SQLAlchemy's pool event targets are registered.
    from flask_sqlalchemy import SQLAlchemy

    SQLAlchemy()

    stubs = {
        "controllers.datasource.filedfill.fill_field_by_llm": _stub_module(
            "controllers.datasource.filedfill.fill_field_by_llm",
            enrich_table_before_insert=MagicMock(),
            check_tables_health_batch=MagicMock(),
        ),
        "controllers.weaviate_db_tool.weaviate_api": _stub_module(
            "controllers.weaviate_db_tool.weaviate_api",
            batch_delete_by_uuids=MagicMock(),
        ),
        "models.datacards_datasource": _stub_module(
            "models.datacards_datasource", DataCardDataSource=type("DataCardDataSource", (), {})
        ),
        "models.datasource_infos": _stub_module(
            "models.datasource_infos", DatasourceInfo=type("DatasourceInfo", (), {})
        ),
        "models.user_datasource_schema": _stub_module(
            "models.user_datasource_schema", UserDatasourceSchema=type("UserDatasourceSchema", (), {})
        ),
        "models.users": _stub_module("models.users", User=type("User", (), {})),
        "core.connect_info_encryptor": _stub_module(
            "core.connect_info_encryptor",
            encrypt_connect_info=lambda value: value,
            decrypt_connect_info=lambda value: value,
            is_encrypted=lambda _value: False,
            get_connect_info_hash=lambda value: value,
        ),
    }

    spec = importlib.util.spec_from_file_location("mariadb_extractor_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


extractor = _load_extractor_module()


class MariaDBConnectionTests(unittest.TestCase):
    def _payload(self, **overrides):
        payload = {
            "db_type": "mariadb",
            "username": "reporter",
            "password": "p@ss/word",
            "host": "db.internal",
            "port": "3307",
            "database": "analytics",
        }
        payload.update(overrides)
        return payload

    def test_builds_mysql_pymysql_url_for_mariadb(self):
        url = extractor.build_db_url_from_json(self._payload())

        self.assertEqual(url.drivername, "mysql+pymysql")
        self.assertEqual(url.username, "reporter")
        self.assertEqual(url.password, "p@ss/word")
        self.assertEqual(url.host, "db.internal")
        self.assertEqual(url.port, 3307)
        self.assertEqual(url.database, "analytics")

    def test_requires_ordinary_mysql_connection_fields(self):
        payload = self._payload()
        del payload["database"]

        with self.assertRaisesRegex(ValueError, "mariadb.*database"):
            extractor.build_db_url_from_json(payload)

    def test_schema_alias_is_used_as_database(self):
        payload = self._payload(database=None, schema="warehouse")

        url = extractor.build_db_url_from_json(payload)

        self.assertEqual(url.database, "warehouse")
        self.assertEqual(
            extractor._resolve_schema_name("mariadb", {"database": "warehouse"}),
            "warehouse",
        )
        self.assertEqual(extractor._infer_db_name("mariadb", url), "warehouse")

    def test_response_keeps_mariadb_product_identity(self):
        mysql_dialect_engine = SimpleNamespace(dialect=SimpleNamespace(name="mysql"))

        self.assertEqual(
            extractor._database_type_for_response("mariadb", mysql_dialect_engine),
            "mariadb",
        )
        self.assertEqual(
            extractor._database_type_for_response("mysql", mysql_dialect_engine),
            "mysql",
        )

    def test_existing_mysql_and_oceanbase_urls_are_unchanged(self):
        mysql_url = extractor.build_db_url_from_json(self._payload(db_type="mysql"))
        oceanbase_url = extractor.build_db_url_from_json(self._payload(db_type="oceanbase"))

        self.assertEqual(mysql_url.drivername, "mysql+pymysql")
        self.assertEqual(oceanbase_url.drivername, "mysql+pymysql")
        self.assertEqual(mysql_url.database, "analytics")
        self.assertEqual(oceanbase_url.database, "analytics")


@unittest.skipUnless(os.getenv("MARIADB_TEST_HOST"), "requires a disposable MariaDB instance")
class MariaDBIntegrationTests(unittest.TestCase):
    def test_backend_connection_and_metadata_paths(self):
        database = os.getenv("MARIADB_TEST_DATABASE", "onticards_maria")
        payload = {
            "db_type": "mariadb",
            "username": os.getenv("MARIADB_TEST_USER", "onticards"),
            "password": os.getenv("MARIADB_TEST_PASSWORD", "testpass"),
            "host": os.environ["MARIADB_TEST_HOST"],
            "port": int(os.getenv("MARIADB_TEST_PORT", "3306")),
            "database": database,
        }

        url = extractor.build_db_url_from_json(payload)
        engine = extractor.get_db_engine(extractor._to_raw_conn_str(url), db_type="mariadb")
        try:
            inspector = extractor.inspect(engine)
            objects = extractor.get_tables(inspector, engine, payload)
            object_types = {item["name"]: item["type"] for item in objects}

            self.assertEqual(engine.dialect.name, "mysql")
            self.assertIn("MariaDB", extractor._get_database_version(engine))
            self.assertEqual(object_types["customer_profiles"], "TABLE")
            self.assertEqual(object_types["active_customer_profiles"], "VIEW")

            table_info = extractor._extract_table_info(
                inspector,
                "customer_profiles",
                schema=database,
            )
            columns = {column["name"]: column["type"] for column in table_info["columns"]}
            self.assertIn("profile", columns)

            with engine.connect() as connection:
                sequence_ddl = connection.execute(
                    extractor.text("SHOW CREATE SEQUENCE invoice_seq")
                ).fetchone()
                next_value = connection.execute(
                    extractor.text("SELECT NEXT VALUE FOR invoice_seq")
                ).scalar_one()
            self.assertIn("CREATE SEQUENCE", str(sequence_ddl).upper())
            self.assertGreaterEqual(next_value, 100)
            self.assertEqual(
                extractor._database_type_for_response("mariadb", engine),
                "mariadb",
            )
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
