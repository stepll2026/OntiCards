import ast
import json
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from .conftest import API_ROOT
from extensions import schema_migrations as migrations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import NullPool


def state(engine):
    with engine.connect() as connection:
        history = connection.execute(
            text(
                "SELECT version, revision, checksum, applied_at FROM public.schema_migrations ORDER BY applied_at, version"
            )
        ).all()
        head = connection.execute(
            text("SELECT version_num FROM public.alembic_version")
        ).scalar_one()
        return head, history


def legacy(engine):
    with engine.begin() as connection:
        connection.exec_driver_sql(
            (API_ROOT / "init.sql").read_text(encoding="utf-8"),
            execution_options={"no_parameters": True},
        )
        for name in ("api_protocol", "embedding_dimensions", "api_options"):
            connection.exec_driver_sql(
                "ALTER TABLE public.model_config DROP COLUMN IF EXISTS " + name
            )
        connection.execute(
            text("""
            INSERT INTO public.model_config (id, model_name, model_type, model_api_key, model_class, url)
            VALUES ('11111111-1111-1111-1111-111111111111', 'fixture-model', 'fixture-provider',
                    'fixture-key', 'fixture-role', 'https://example.invalid/v1/chat/completions')
        """)
        )


def test_ordered_revision_chain():
    _, revisions = migrations.migration_plan()
    assert [(r.revision, r.module.schema_version) for r in revisions] == [
        ("v1", "1.0"),
        ("v1_1", "1.1"),
        ("v1_2", "1.2"),
    ]
    assert revisions[-1].module.schema_version == migrations.DATABASE_SCHEMA_VERSION


def test_applied_checksum_ignores_checkout_line_endings(tmp_path):
    path = tmp_path / "version.py"
    path.write_bytes(b"line1\nline2\n")
    revision = SimpleNamespace(path=path, module=SimpleNamespace())
    before = migrations.migration_checksum(revision)
    path.write_bytes(b"line1\r\nline2\r\n")
    assert migrations.migration_checksum(revision) == before
    path.write_bytes(b"changed\n")
    assert migrations.migration_checksum(revision) != before


def test_wrong_target_or_multiple_heads_are_rejected(tmp_path):
    with pytest.raises(migrations.SchemaMigrationError, match="head"):
        migrations.migration_plan(target="v1_1")
    directory = tmp_path / "migrations"
    shutil.copytree(migrations.MIGRATIONS_DIRECTORY, directory)
    (directory / "versions/fork.py").write_text(
        "revision='fork'\ndown_revision='v1'\n", encoding="utf-8"
    )
    with pytest.raises(migrations.SchemaMigrationError, match="head"):
        migrations.migration_plan(directory)


def test_internal_database_is_postgresql_only():
    engine = create_engine("sqlite://")
    with pytest.raises(migrations.SchemaMigrationError, match="PostgreSQL"):
        migrations.upgrade_schema(engine)


def test_startup_failure_propagates_before_default_user_and_views():
    tree = ast.parse((API_ROOT / "app.py").read_text(encoding="utf-8"))
    create = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "create_app"
    )
    calls = [
        ast.unparse(node.value.func)
        for node in create.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    ]
    assert (
        calls.index("ensure_database_initialized")
        < calls.index("views.init")
        < calls.index("ensure_default_user")
    )
    init = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "ensure_database_initialized"
    )
    from flask import Flask

    app = Flask(__name__)

    def fail(*args, **kwargs):
        raise migrations.SchemaMigrationError("fixture failure")

    namespace = {"db": SimpleNamespace(engine=object()), "upgrade_schema": fail}
    # Execute the real startup wrapper without loading external services.
    exec(  # noqa: S102
        compile(ast.Module(body=[init], type_ignores=[]), "startup", "exec"), namespace
    )
    with pytest.raises(migrations.SchemaMigrationError, match="fixture failure"):
        namespace["ensure_database_initialized"](app)


def test_empty_database_upgrades_through_all_versions(database):
    assert migrations.upgrade_schema(database) == "1.2"
    head, history = state(database)
    assert head == "v1_2"
    assert [row.version for row in history] == ["1.0", "1.1", "1.2"]
    assert len({row.checksum for row in history}) == 3
    with database.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM public.business_term_templates")
            ).scalar_one()
            > 0
        )
        assert inspect(connection).has_table("users", schema="public")


def test_legacy_data_preserved_and_restart_is_noop(database):
    legacy(database)
    with database.connect() as connection:
        before = dict(
            connection.execute(text("SELECT * FROM public.model_config"))
            .mappings()
            .one()
        )
    migrations.upgrade_schema(database)
    initial = state(database)
    assert migrations.upgrade_schema(database) == "1.2"
    assert state(database) == initial
    with database.connect() as connection:
        after = dict(
            connection.execute(text("SELECT * FROM public.model_config"))
            .mappings()
            .one()
        )
        assert {name: after[name] for name in before} == before
        assert (
            after["api_protocol"] == "auto"
            and after["embedding_dimensions"] is None
            and after["api_options"] is None
        )


def test_previously_manual_columns_are_adopted(database):
    legacy(database)
    with database.begin() as connection:
        for filename in (
            "20260916_model_protocol.sql",
            "20260916_model_native_options.sql",
        ):
            connection.exec_driver_sql(
                (API_ROOT / "scripts/migrations" / filename).read_text(encoding="utf-8")
            )
        connection.execute(
            text(
                "UPDATE public.model_config SET api_protocol='openai', embedding_dimensions=256, api_options=CAST(:options AS jsonb)"
            ),
            {"options": json.dumps({"max_tokens": 128})},
        )
    migrations.upgrade_schema(database)
    with database.connect() as connection:
        assert connection.execute(
            text(
                "SELECT api_protocol, embedding_dimensions, api_options FROM public.model_config"
            )
        ).one() == ("openai", 256, {"max_tokens": 128})
    assert len(state(database)[1]) == 3


@pytest.mark.parametrize(
    "failed_revision,previous", [("v1", None), ("v1_1", "v1"), ("v1_2", "v1_1")]
)
def test_failure_rolls_back_ddl_and_version_then_resumes(
    database, monkeypatch, failed_revision, previous
):
    real_upgrade = migrations.command.upgrade

    def failing(config, revision):
        real_upgrade(config, revision)
        if revision == failed_revision:
            config.attributes["connection"].execute(
                text("CREATE TABLE public.uncommitted_marker (id int)")
            )
            raise RuntimeError("simulated interruption after DDL")

    monkeypatch.setattr(migrations.command, "upgrade", failing)
    with pytest.raises(migrations.SchemaMigrationError, match="failed"):
        migrations.upgrade_schema(database)
    with database.connect() as connection:
        inspector = inspect(connection)
        assert not inspector.has_table("uncommitted_marker", schema="public")
        if previous is None:
            assert inspector.get_table_names(schema="public") == []
        else:
            assert (
                connection.execute(
                    text("SELECT version_num FROM public.alembic_version")
                ).scalar_one()
                == previous
            )
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM public.schema_migrations WHERE revision=:revision"
                    ),
                    {"revision": failed_revision},
                ).scalar_one()
                == 0
            )
    monkeypatch.setattr(migrations.command, "upgrade", real_upgrade)
    assert migrations.upgrade_schema(database) == "1.2"
    assert len(state(database)[1]) == 3


@pytest.mark.parametrize(
    "tampering", ["newer_version", "checksum", "missing_history", "missing_column"]
)
def test_inconsistent_or_newer_database_blocks_startup(database, tampering):
    migrations.upgrade_schema(database)
    statements = {
        "newer_version": "UPDATE public.alembic_version SET version_num='v99'",
        "checksum": "UPDATE public.schema_migrations SET checksum='modified' WHERE revision='v1'",
        "missing_history": "DELETE FROM public.schema_migrations WHERE revision='v1_1'",
        "missing_column": "ALTER TABLE public.model_config DROP COLUMN api_options",
    }
    with database.begin() as connection:
        connection.execute(text(statements[tampering]))
    with pytest.raises((migrations.SchemaMigrationError, ValueError)):
        migrations.upgrade_schema(database)


def test_unknown_legacy_schema_is_not_overwritten(database):
    with database.begin() as connection:
        connection.execute(text("CREATE TABLE public.important_data (value text)"))
        connection.execute(text("INSERT INTO public.important_data VALUES ('keep-me')"))
    with pytest.raises(migrations.SchemaMigrationError):
        migrations.upgrade_schema(database)
    with database.connect() as connection:
        assert (
            connection.execute(
                text("SELECT value FROM public.important_data")
            ).scalar_one()
            == "keep-me"
        )
        assert inspect(connection).get_table_names(schema="public") == [
            "important_data"
        ]


def test_wrong_existing_column_type_is_not_silently_accepted(database):
    legacy(database)
    with database.begin() as connection:
        connection.execute(
            text("ALTER TABLE public.model_config ADD COLUMN api_options text")
        )
    with pytest.raises(migrations.SchemaMigrationError, match="1.2"):
        migrations.upgrade_schema(database)
    assert state(database)[0] == "v1_1"


def test_concurrent_startups_apply_once(database):
    barrier = threading.Barrier(2)

    def start():
        barrier.wait(timeout=5)
        return migrations.upgrade_schema(database)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(start) for _ in range(2)]
        assert [future.result(timeout=60) for future in futures] == ["1.2", "1.2"]
    assert len(state(database)[1]) == 3


def test_wait_for_migration_lock_is_bounded(database):
    with database.connect() as owner:
        owner.execute(
            text("SELECT pg_advisory_lock(:key)"), {"key": migrations.MIGRATION_LOCK_ID}
        )
        owner.commit()
        with pytest.raises(migrations.SchemaMigrationError, match="Timed out"):
            migrations.upgrade_schema(database, lock_timeout=0.05)
    assert migrations.upgrade_schema(database) == "1.2"


def test_initialization_works_with_non_default_database_owner(admin_engine):
    suffix = uuid.uuid4().hex
    role = "onticards_schema_role_" + suffix
    name = "onticards_schema_test_" + suffix
    with admin_engine.connect() as connection:
        connection.exec_driver_sql(
            'CREATE ROLE "' + role + "\" LOGIN PASSWORD 'fixture-password'"
        )
        connection.exec_driver_sql(
            'CREATE DATABASE "' + name + '" OWNER "' + role + '"'
        )
    engine = create_engine(
        admin_engine.url.set(database=name, username=role, password="fixture-password"),
        poolclass=NullPool,
    )
    try:
        assert migrations.upgrade_schema(engine) == "1.2"
    finally:
        engine.dispose()
        with admin_engine.connect() as connection:
            connection.exec_driver_sql('DROP DATABASE "' + name + '" WITH (FORCE)')
            connection.exec_driver_sql('DROP ROLE "' + role + '"')
