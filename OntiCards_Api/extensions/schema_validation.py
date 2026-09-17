"""Checks used by the initial versioned PostgreSQL migrations."""

import json
from pathlib import Path

from sqlalchemy import inspect

API_ROOT = Path(__file__).resolve().parents[1]
BASELINE_FILE = API_ROOT / "migrations" / "baseline_v1.json"


def verify_baseline(connection):
    required = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    inspector = inspect(connection)
    tables = set(inspector.get_table_names(schema="public"))
    missing = []
    for table, columns in required.items():
        if table not in tables:
            missing.append(table)
            continue
        actual = {
            column["name"] for column in inspector.get_columns(table, schema="public")
        }
        missing.extend(table + "." + name for name in columns if name not in actual)
    if missing:
        raise ValueError(
            "Database does not match the supported V1 baseline; missing: "
            + ", ".join(missing)
        )


def verify_model_columns(connection, *, native_options=False):
    from sqlalchemy import Integer, String
    from sqlalchemy.dialects.postgresql import JSONB

    columns = {
        column["name"]: column
        for column in inspect(connection).get_columns("model_config", schema="public")
    }
    protocol = columns.get("api_protocol", {})
    dimensions = columns.get("embedding_dimensions", {})
    if (
        not isinstance(protocol.get("type"), String)
        or protocol["type"].length != 32
        or protocol.get("nullable") is not False
        or protocol.get("default")
        not in ("'auto'::character varying", "'auto'::text", "'auto'")
        or not isinstance(dimensions.get("type"), Integer)
        or dimensions.get("nullable") is not True
    ):
        raise ValueError(
            "model_config protocol/dimensions columns do not match schema V1.1."
        )
    if native_options:
        options = columns.get("api_options", {})
        if (
            not isinstance(options.get("type"), JSONB)
            or options.get("nullable") is not True
        ):
            raise ValueError("model_config.api_options does not match schema V1.2.")
