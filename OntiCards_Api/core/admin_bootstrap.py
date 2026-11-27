"""Explicit, transaction-scoped provisioning of the first administrator."""

import base64
import os
import re
import secrets
import stat
import uuid
from pathlib import Path

from sqlalchemy import CheckConstraint, Column, MetaData, SmallInteger, String, Table, inspect, select, text
from sqlalchemy.exc import DBAPIError

from core.password import hash_password, valid_password


bootstrap_state = Table(
    "admin_bootstrap_state",
    MetaData(),
    Column("id", SmallInteger, primary_key=True, autoincrement=False),
    Column("phase", String(12), nullable=False, server_default="legacy"),
    Column("namespace", String(128)),
    Column("owner", String(32)),
    Column("claim", String(64)),
    CheckConstraint("id = 1", name="admin_bootstrap_state_singleton"),
    schema="public",
)


class AdminBootstrapError(RuntimeError):
    pass


def _bootstrap_credentials(environ):
    username = environ.get("ONTICARDS_BOOTSTRAP_ADMIN_USERNAME", "")
    location = environ.get("ONTICARDS_BOOTSTRAP_ADMIN_PASSWORD_FILE", "")
    if not username or not location:
        raise AdminBootstrapError(
            "No users exist. Set ONTICARDS_BOOTSTRAP_ADMIN_USERNAME and "
            "ONTICARDS_BOOTSTRAP_ADMIN_PASSWORD_FILE to authorize first-time setup."
        )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@+-]{0,31}", username):
        raise AdminBootstrapError("The administrator bootstrap username is invalid.")

    try:
        path = Path(location)
        root = Path(environ.get("ONTICARDS_BOOTSTRAP_SECRET_ROOT", "/run/secrets"))
        if not root.is_absolute() or ".." in root.parts or path.parent != root:
            raise OSError
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        directory = os.open(root.anchor, flags)
        try:
            for part in root.parts[1:]:
                child = os.open(part, flags, dir_fd=directory)
                os.close(directory)
                directory = child
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
                    raise OSError
                password = stream.read(131).decode("ascii").removesuffix("\n").removesuffix("\r")
        finally:
            os.close(directory)
        if not re.fullmatch(r"[!-~]{32,128}", password) or len(set(password)) < 12:
            raise ValueError
        valid_password(password)
    except (AttributeError, OSError, ValueError):
        raise AdminBootstrapError(
            "The administrator bootstrap password file must contain one strong random password."
        ) from None
    return username, password


def _lock_users(connection, users):
    table_name = connection.dialect.identifier_preparer.format_table(users)
    connection.exec_driver_sql(f"LOCK TABLE {table_name} IN SHARE ROW EXCLUSIVE MODE")


def _read_state(connection):
    return connection.execute(select(bootstrap_state).where(bootstrap_state.c.id == 1)).mappings().one_or_none()


def initialize_bootstrap_state(connection, users, environ):
    """Record fresh provenance alongside schema creation, before any account provisioning."""
    database = connection.scalar(text("SELECT current_database()"))
    if environ.get("ONTICARDS_BOOTSTRAP_NEW_DATABASE") != database:
        raise AdminBootstrapError(
            "An empty schema needs explicit approval via ONTICARDS_BOOTSTRAP_NEW_DATABASE."
        )
    _lock_users(connection, users)
    bootstrap_state.create(connection, checkfirst=True)
    connection.execute(bootstrap_state.insert().values(id=1, phase="fresh"))


def migrate_bootstrap_state(connection, users):
    """Backfill legacy installations under the same lock as user provisioning."""
    _lock_users(connection, users)
    has_users = connection.scalar(select(users.c.id).limit(1)) is not None
    inspector = inspect(connection)
    has_history = has_users or (
        inspector.has_table("alembic_version", schema="public")
        and connection.scalar(text("SELECT EXISTS (SELECT 1 FROM public.alembic_version)"))
    )
    if not inspector.has_table(bootstrap_state.name, schema=bootstrap_state.schema):
        if not has_history:
            return has_users, None
        bootstrap_state.create(connection)
    else:
        columns = {column["name"] for column in inspector.get_columns(
            bootstrap_state.name, schema=bootstrap_state.schema)}
        if not {"phase", "namespace", "owner", "claim"}.issubset(columns):
            # The previously released candidate used an id-only completion marker.
            connection.exec_driver_sql(
                "ALTER TABLE public.admin_bootstrap_state "
                "ADD COLUMN IF NOT EXISTS phase varchar(12) NOT NULL DEFAULT 'legacy', "
                "ADD COLUMN IF NOT EXISTS namespace varchar(128), "
                "ADD COLUMN IF NOT EXISTS owner varchar(32), "
                "ADD COLUMN IF NOT EXISTS claim varchar(64)"
            )
    state = _read_state(connection)
    if has_history and state is None:
        connection.execute(bootstrap_state.insert().values(id=1, phase="legacy"))
    elif has_users and state["phase"] == "fresh":
        connection.execute(bootstrap_state.update().where(bootstrap_state.c.id == 1).values(phase="legacy"))
    elif state is not None and state["phase"] == "pending" and state["claim"] is None:
        connection.execute(bootstrap_state.update().where(bootstrap_state.c.id == 1).values(
            claim=secrets.token_hex(32),
        ))
    return has_users, _read_state(connection)


def _provision_admin(connection, users, collection_name, environ):
    """Commit the account and pending collection together. No external calls here."""
    username, password = _bootstrap_credentials(environ)
    salt = secrets.token_bytes(16)
    user_id = uuid.uuid4()
    namespace = collection_name(user_id)
    connection.execute(users.insert().values(
        id=user_id,
        username=username,
        nickname=username,
        password=base64.b64encode(hash_password(password, salt)).decode("ascii"),
        password_salt=base64.b64encode(salt).decode("ascii"),
        role="admin",
        status="normal",
        weaviate_class_name=namespace,
    ))
    connection.execute(bootstrap_state.update().where(bootstrap_state.c.id == 1).values(
        phase="pending", namespace=namespace, owner=user_id.hex, claim=secrets.token_hex(32),
    ))


def bound_admin_collection(connection, users, state):
    owner = state["owner"] or ""
    namespace = state["namespace"]
    claim = state["claim"]
    if not re.fullmatch(r"[a-f0-9]{32}", owner) or not namespace:
        raise AdminBootstrapError("The committed administrator collection binding is invalid.")
    if claim is not None and not re.fullmatch(r"[a-f0-9]{64}", claim):
        raise AdminBootstrapError("The committed administrator collection claim is invalid.")
    bound = connection.scalar(select(users.c.id).where(
        users.c.id == uuid.UUID(hex=owner), users.c.weaviate_class_name == namespace,
    ))
    if bound is None:
        raise AdminBootstrapError("The administrator collection has no matching account.")
    return namespace, owner, claim


def read_bootstrap_collection_for_readiness(connection, users):
    state = _read_state(connection)
    if state is not None and state["phase"] == "legacy":
        return None
    if state is None or state["phase"] != "ready":
        raise AdminBootstrapError("Administrator collection synchronization is pending.")
    if not state["claim"]:
        raise AdminBootstrapError("Administrator collection ownership requires reconciliation.")
    return bound_admin_collection(connection, users, state)


def retire_bootstrap_binding(connection, user_ids):
    """Retire an authorized deletion without reopening administrator setup."""
    ids = [user_id.hex for user_id in user_ids]
    if ids:
        connection.execute(bootstrap_state.update().where(bootstrap_state.c.owner.in_(ids)).values(
            phase="legacy", namespace=None, owner=None, claim=None,
        ))


def recover_admin_collection(connection, users, ensure_collection):
    """Retry committed provisioning; never touch unrelated collections."""
    has_users, state = migrate_bootstrap_state(connection, users)
    if not has_users or state is None or state["phase"] not in {"pending", "ready"}:
        return False
    if state["phase"] == "ready":
        return True
    ensure_collection(*bound_admin_collection(connection, users, state))
    connection.execute(bootstrap_state.update().where(bootstrap_state.c.id == 1).values(phase="ready"))
    return True


def ensure_admin(engine, users, collection_name, ensure_collection, environ):
    created = False
    refusal = None
    try:
        with engine.begin() as connection:
            has_users, state = migrate_bootstrap_state(connection, users)
            if not has_users:
                if state is None:
                    refusal = "Database provenance is unknown. Restore an existing administrator or confirm deployment history."
                elif state["phase"] != "fresh":
                    refusal = "Administrator bootstrap was already consumed. Restore or recover an existing account."
                else:
                    _provision_admin(connection, users, collection_name, environ)
                    created = True
    except DBAPIError as error:
        if not error.connection_invalidated:
            raise
        # A connection may be lost while receiving COMMIT. Require persisted state
        # on a different connection before performing any external side effect.
        with engine.begin() as connection:
            if recover_admin_collection(connection, users, ensure_collection):
                return False
        raise
    if refusal is not None:
        # Preserve any historical marker even when startup must reject provisioning.
        raise AdminBootstrapError(refusal)
    with engine.begin() as connection:
        recover_admin_collection(connection, users, ensure_collection)
    return created
