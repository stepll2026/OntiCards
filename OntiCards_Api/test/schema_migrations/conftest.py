import os
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(API_ROOT))


@pytest.fixture(scope="session")
def admin_engine():
    url = os.environ.get("SCHEMA_TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set SCHEMA_TEST_DATABASE_URL to an isolated PostgreSQL test database."
        )
    parsed = make_url(url)
    if parsed.database != "onticards_schema_test_admin":
        pytest.fail(
            "Refusing database lifecycle tests outside onticards_schema_test_admin."
        )
    engine = create_engine(parsed, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    yield engine
    engine.dispose()


@pytest.fixture
def database(admin_engine):
    name = "onticards_schema_test_" + uuid.uuid4().hex
    with admin_engine.connect() as connection:
        connection.exec_driver_sql('CREATE DATABASE "' + name + '"')
    engine = create_engine(admin_engine.url.set(database=name), poolclass=NullPool)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin_engine.connect() as connection:
            connection.exec_driver_sql('DROP DATABASE "' + name + '" WITH (FORCE)')
