"""Versioned upgrades for OntiCards' own PostgreSQL database."""

import hashlib
import logging
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

DATABASE_SCHEMA_VERSION = "1.2"
TARGET_REVISION = "v1_2"
MIGRATIONS_DIRECTORY = Path(__file__).resolve().parents[1] / "migrations"
# A session lock survives the individual migration transactions.
MIGRATION_LOCK_ID = 684023918157621
VERSION_OPTIONS = {"version_table_schema": "public"}
HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version varchar(32) PRIMARY KEY,
    revision varchar(32) UNIQUE NOT NULL,
    checksum varchar(64) NOT NULL,
    description text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


class SchemaMigrationError(RuntimeError):
    """The application must not serve requests with an unverified schema."""


def migration_plan(directory=MIGRATIONS_DIRECTORY, target=TARGET_REVISION):
    config = Config(str(Path(directory) / "alembic.ini"))
    config.set_main_option("script_location", str(directory))
    script = ScriptDirectory.from_config(config)
    if script.get_heads() != [target]:
        raise SchemaMigrationError(
            "Migration head does not match the code's target revision."
        )
    revisions = list(reversed(list(script.iterate_revisions(target, "base"))))
    previous = None
    versions = set()
    for revision in revisions:
        version = getattr(revision.module, "schema_version", None)
        if (
            revision.down_revision != previous
            or not version
            or version in versions
            or not callable(getattr(revision.module, "verify", None))
        ):
            raise SchemaMigrationError(
                "Migrations must form one complete, ordered version chain."
            )
        previous = revision.revision
        versions.add(version)
    return config, revisions


def migration_checksum(revision):
    """Published revisions and their SQL/validation dependencies are immutable."""
    files = [Path(revision.path)]
    files.extend(Path(path) for path in getattr(revision.module, "checksum_files", ()))
    digest = hashlib.sha256()
    for path in files:
        # Git may check out LF or CRLF on different operating systems.
        content = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        digest.update(content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _acquire_lock(connection, timeout):
    deadline = time.monotonic() + timeout
    while True:
        locked = connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": MIGRATION_LOCK_ID}
        ).scalar_one()
        connection.commit()
        if locked:
            return
        if time.monotonic() >= deadline:
            raise SchemaMigrationError(
                "Timed out waiting for another instance to finish schema migration."
            )
        time.sleep(min(0.2, max(0, deadline - time.monotonic())))


def _read_state(connection, revisions):
    heads = MigrationContext.configure(
        connection, opts=VERSION_OPTIONS
    ).get_current_heads()
    ids = [revision.revision for revision in revisions]
    if len(heads) > 1 or (heads and heads[0] not in ids):
        raise SchemaMigrationError(
            "Database revision is unknown or newer than this code; automatic downgrade is disabled."
        )
    count = ids.index(heads[0]) + 1 if heads else 0
    inspector = inspect(connection)
    records = []
    if inspector.has_table("schema_migrations", schema="public"):
        records = (
            connection.execute(
                text("SELECT version, revision, checksum FROM public.schema_migrations")
            )
            .mappings()
            .all()
        )
    expected = {revision.revision: revision for revision in revisions[:count]}
    if {row["revision"] for row in records} != set(expected) or len(records) != count:
        raise SchemaMigrationError(
            "Schema version and migration history disagree; manual inspection is required."
        )
    for row in records:
        revision = expected[row["revision"]]
        if row["version"] != revision.module.schema_version or row[
            "checksum"
        ] != migration_checksum(revision):
            raise SchemaMigrationError(
                "An applied migration has changed: " + revision.revision
            )
    if count:
        try:
            revisions[count - 1].module.verify(connection)
        except Exception as exc:
            raise SchemaMigrationError(
                "Database structure does not match its recorded revision: " + heads[0]
            ) from exc
    return count


def upgrade_schema(
    engine,
    *,
    logger=None,
    directory=MIGRATIONS_DIRECTORY,
    target=TARGET_REVISION,
    lock_timeout=60,
):
    """Apply each pending revision and its history entry in one transaction."""
    logger = logger or logging.getLogger(__name__)
    if engine.dialect.name != "postgresql":
        raise SchemaMigrationError(
            "OntiCards' internal schema migrations require PostgreSQL."
        )
    config, revisions = migration_plan(directory, target)
    if (
        directory == MIGRATIONS_DIRECTORY
        and revisions[-1].module.schema_version != DATABASE_SCHEMA_VERSION
    ):
        raise SchemaMigrationError(
            "DATABASE_SCHEMA_VERSION does not match the target migration."
        )
    with engine.connect() as connection:
        try:
            _acquire_lock(connection, lock_timeout)
            with connection.begin():
                count = _read_state(connection, revisions)
            current = (
                revisions[count - 1].module.schema_version if count else "unversioned"
            )
            logger.info(
                "Database schema: current=%s, target=%s",
                current,
                revisions[-1].module.schema_version,
            )
            for revision in revisions[count:]:
                version = revision.module.schema_version
                logger.info(
                    "Applying database schema %s (%s)", version, revision.revision
                )
                try:
                    with connection.begin():
                        connection.execute(text("SET LOCAL search_path TO public"))
                        connection.execute(text("SET LOCAL lock_timeout TO '60s'"))
                        config.attributes["connection"] = connection
                        config.attributes["schema_upgrade"] = True
                        command.upgrade(config, revision.revision)
                        revision.module.verify(connection)
                        connection.execute(text(HISTORY_DDL))
                        connection.execute(
                            text("""
                            INSERT INTO public.schema_migrations (version, revision, checksum, description)
                            VALUES (:version, :revision, :checksum, :description)
                        """),
                            {
                                "version": version,
                                "revision": revision.revision,
                                "checksum": migration_checksum(revision),
                                "description": revision.doc,
                            },
                        )
                except Exception as exc:
                    logger.error(
                        "Schema %s failed; its transaction was rolled back. Last completed version: %s",
                        version,
                        current,
                    )
                    raise SchemaMigrationError(
                        "Database schema upgrade failed at " + version
                    ) from exc
                current = version
                logger.info("Database schema %s applied successfully", version)
            return current
        finally:
            # Physically close this dedicated session so its advisory lock cannot
            # leak into the connection pool or be inherited by a Gunicorn worker.
            connection.invalidate()
