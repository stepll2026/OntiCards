"""Run with real disposable PostgreSQL and Weaviate, both without public listeners."""

import ast
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext, redirect_stderr, redirect_stdout
import io
import logging
import os
from pathlib import Path
import re
import secrets
from threading import Barrier
import sys
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from sqlalchemy import MetaData, Table, column, create_engine, inspect, select, table, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError, IntegrityError

from core.admin_bootstrap import (
    AdminBootstrapError, bootstrap_state, ensure_admin,
    initialize_bootstrap_state, migrate_bootstrap_state, recover_admin_collection,
)
from core.admin_collection import _request, ensure_account_collection
from core.password import compare_password


SOCKET = os.environ.get("ONTICARDS_BOOTSTRAP_TEST_SOCKET")
APP = Path(__file__).resolve().parents[1] / "app.py"
DATABASE = "onti55_consistency_test"
WEAVIATE = "http://127.0.0.1:18188"


@unittest.skipUnless(SOCKET, "set the private socket for a disposable PostgreSQL test cluster")
class AdminBootstrapPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        socket = Path(SOCKET).resolve()
        if socket.name != "socket" or socket.parent.parent != Path("/tmp"):
            raise RuntimeError("Expected a private socket directory in /tmp.")
        if not re.fullmatch(r"onti55-pg\.[A-Za-z0-9]+", socket.parent.name):
            raise RuntimeError("Expected a dedicated Issue #55 test cluster.")
        cls.url = URL.create("postgresql+psycopg2", username="postgres", database=DATABASE,
                             query={"host": str(socket), "port": "55432"})
        cls.engine = create_engine(cls.url, hide_parameters=True)
        cls.addClassCleanup(cls.engine.dispose)
        with cls.engine.connect() as db:
            assert db.scalar(text("SHOW listen_addresses")) == ""
            assert Path(db.scalar(text("SHOW data_directory"))).resolve() == socket.parent / "data"
            assert db.scalar(text("SELECT current_database()")) == DATABASE
        code, meta = _request(WEAVIATE, "/v1/meta")
        assert code == 200 and meta["version"] == "1.36.0"

        names = {"check_database_has_tables", "execute_init_sql", "ensure_database_initialized"}
        module = ast.parse(APP.read_text(encoding="utf-8"))
        funcs = [x for x in module.body if isinstance(x, ast.FunctionDef) and x.name in names]
        scope = {"__file__": str(APP), "os": os, "text": text, "db": SimpleNamespace(engine=cls.engine),
                 "initialize_bootstrap_state": initialize_bootstrap_state}
        exec(compile(ast.Module(body=funcs, type_ignores=[]), str(APP), "exec"), scope)
        app = SimpleNamespace(app_context=nullcontext, logger=logging.getLogger("bootstrap-schema"))
        user_model = SimpleNamespace(User=SimpleNamespace(__table__=table("users", column("id"), schema="public")))
        with patch.dict(sys.modules, {"models.users": user_model}), patch.dict(
            os.environ, {"ONTICARDS_BOOTSTRAP_NEW_DATABASE": DATABASE}
        ), ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(scope["ensure_database_initialized"], [app, app]))
        cls.users = Table("users", MetaData(), schema="public", autoload_with=cls.engine)
        cls.groups = Table("user_groups", MetaData(), schema="public", autoload_with=cls.engine)

    def setUp(self):
        with self.engine.begin() as db:
            db.execute(self.users.delete())
            db.execute(self.groups.delete())
            db.exec_driver_sql("DELETE FROM public.alembic_version")
            bootstrap_state.drop(db, checkfirst=True)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.password = secrets.token_hex(32)
        self.password_file = Path(temporary.name) / "password"
        self.password_file.write_text(self.password + "\n", encoding="ascii")
        self.password_file.chmod(0o600)
        self.config = {
            "ONTICARDS_BOOTSTRAP_ADMIN_USERNAME": "test-admin",
            "ONTICARDS_BOOTSTRAP_ADMIN_PASSWORD_FILE": str(self.password_file),
            "ONTICARDS_BOOTSTRAP_SECRET_ROOT": str(self.password_file.parent),
        }
        self.namespace = "datacard_datasource__" + str(uuid.uuid4()).replace("-", "_")
        self.path = "/v1/schema/" + self.namespace
        self.addCleanup(self.delete_test_collection)

    def delete_test_collection(self):
        if _request(WEAVIATE, self.path)[0] == 200:
            _request(WEAVIATE, self.path, method="DELETE")

    def fresh(self):
        with self.engine.begin() as db:
            initialize_bootstrap_state(db, self.users, {"ONTICARDS_BOOTSTRAP_NEW_DATABASE": DATABASE})

    def initialize(self, config=None, endpoint=WEAVIATE, engine=None):
        return ensure_admin(
            engine or self.engine, self.users, lambda _id: self.namespace,
            lambda name, owner, claim: ensure_account_collection(endpoint, name, owner, claim),
            self.config if config is None else config,
        )

    def create_pending(self):
        self.fresh()
        with self.assertRaisesRegex(AdminBootstrapError, "pending"):
            self.initialize(endpoint="http://127.0.0.1:18189")

    def rows(self):
        with self.engine.connect() as db:
            return [dict(row) for row in db.execute(select(self.users).order_by(self.users.c.username)).mappings()]

    def state(self):
        with self.engine.connect() as db:
            return db.execute(select(bootstrap_state)).mappings().one()

    def put_legacy_user(self, role="admin"):
        with self.engine.begin() as db:
            db.execute(self.users.insert().values(id=uuid.uuid4(), username=role, role=role, status="normal"))

    def parallel(self, function):
        gate = Barrier(2)

        def run():
            gate.wait(timeout=10)
            return function()

        with ThreadPoolExecutor(max_workers=2) as executor:
            jobs = [executor.submit(run) for _ in range(2)]
            return [job.result(timeout=25) for job in jobs]

    def test_valid_credentials_provision_an_admin_with_a_random_salt(self):
        self.fresh()
        self.assertTrue(self.initialize())
        user, = self.rows()
        self.assertEqual((user["username"], user["role"], user["status"]), ("test-admin", "admin", "normal"))
        self.assertTrue(compare_password(self.password, user["password"], user["password_salt"]))
        self.assertEqual(self.state()["phase"], "ready")
        self.assertEqual(_request(WEAVIATE, self.path)[0], 200)

    def test_empty_database_without_authorization_fails(self):
        self.fresh()
        with self.assertRaisesRegex(AdminBootstrapError, "authorize first-time setup"):
            self.initialize({})
        self.assertFalse(self.rows())
        self.assertEqual(self.state()["phase"], "fresh")

    def test_password_files_fail_closed(self):
        self.fresh()
        paths = []
        absent = self.password_file.parent / "absent"
        paths.append((absent, "missing"))
        for name, value in (("empty", b""), ("whitespace", b" " * 40 + b"\n")):
            file = self.password_file.parent / name
            file.write_bytes(value)
            file.chmod(0o600)
            paths.append((file, name))
        exposed = self.password_file.parent / "exposed"
        exposed.write_bytes(self.password_file.read_bytes())
        exposed.chmod(0o640)
        paths.append((exposed, "group readable"))
        link = self.password_file.parent / "link"
        link.symlink_to(self.password_file)
        paths.append((link, "symlink"))
        for path, label in paths:
            with self.subTest(case=label):
                config = {**self.config, "ONTICARDS_BOOTSTRAP_ADMIN_PASSWORD_FILE": str(path)}
                with self.assertRaises(AdminBootstrapError):
                    self.initialize(config)
                self.assertFalse(self.rows())
                self.assertEqual(self.state()["phase"], "fresh")

    def test_existing_admin_needs_no_secret_file(self):
        self.put_legacy_user()
        existing = self.rows()
        self.password_file.unlink()
        self.assertFalse(self.initialize({}))
        self.assertTrue(self.rows() == existing)
        self.assertEqual(self.state()["phase"], "legacy")

    def test_repeated_initialization_does_not_change_admin(self):
        self.fresh()
        self.assertTrue(self.initialize())
        existing = self.rows()
        self.assertFalse(self.initialize())
        self.assertTrue(self.rows() == existing)

    def test_concurrent_initialization_commits_exactly_one_admin(self):
        self.fresh()
        self.assertEqual(sorted(self.parallel(self.initialize)), [False, True])
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.state()["phase"], "ready")

    def test_consumed_bootstrap_cannot_be_reused_when_users_are_deleted(self):
        self.fresh()
        self.assertTrue(self.initialize())
        with self.engine.begin() as db:
            db.execute(self.users.delete())
        with self.assertRaisesRegex(AdminBootstrapError, "already consumed"):
            self.initialize()
        self.assertFalse(self.rows())

    def test_password_is_absent_from_error_and_output(self):
        self.fresh()
        invalid = secrets.token_hex(8)
        self.password_file.write_text(invalid, encoding="ascii")
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            with self.assertRaises(AdminBootstrapError) as error:
                self.initialize()
        self.assertNotIn(invalid, str(error.exception))
        self.assertEqual(output.getvalue(), "")

    def test_existing_users_and_permission_fields_are_preserved(self):
        self.put_legacy_user()
        group_id = uuid.uuid4()
        with self.engine.begin() as db:
            db.execute(self.groups.insert().values(group_id=group_id, group_name="Existing group"))
            db.execute(self.users.insert().values(id=uuid.uuid4(), username="legacy",
                status="disabled", role="normal", user_group_id=group_id))
            group_before = dict(db.execute(select(self.groups)).mappings().one())
        existing = self.rows()
        self.assertFalse(self.initialize())
        self.assertTrue(self.rows() == existing)
        with self.engine.connect() as db:
            self.assertEqual(dict(db.execute(select(self.groups)).mappings().one()), group_before)

    def test_collection_failure_keeps_committed_user_and_pending_state(self):
        self.fresh()
        with self.assertRaisesRegex(AdminBootstrapError, "pending"):
            self.initialize(endpoint="http://127.0.0.1:18189")
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.state()["phase"], "pending")
        self.assertEqual(_request(WEAVIATE, self.path)[0], 404)

    def test_concurrent_legacy_migration_is_idempotent_and_blocks_replay(self):
        self.put_legacy_user()
        self.put_legacy_user("normal")
        before = self.rows()

        def migrate():
            with self.engine.begin() as db:
                migrate_bootstrap_state(db, self.users)

        self.parallel(migrate)
        migrate()
        self.assertEqual(self.state()["phase"], "legacy")
        self.assertEqual(self.rows(), before)
        with self.engine.begin() as db:
            db.execute(self.users.delete())
        with self.assertRaisesRegex(AdminBootstrapError, "already consumed"):
            self.initialize()

    def test_unknown_provenance_fails_closed(self):
        with self.assertRaisesRegex(AdminBootstrapError, "provenance is unknown"):
            self.initialize()
        self.assertFalse(self.rows())
        self.assertEqual(_request(WEAVIATE, self.path)[0], 404)

    def test_already_empty_versioned_database_persists_historical_marker(self):
        with self.engine.begin() as db:
            db.exec_driver_sql("INSERT INTO public.alembic_version VALUES ('0001_baseline')")
        with self.assertRaisesRegex(AdminBootstrapError, "already consumed"):
            self.initialize()
        self.assertEqual(self.state()["phase"], "legacy")
        self.assertFalse(self.rows())
        self.assertEqual(_request(WEAVIATE, self.path)[0], 404)

    def test_empty_schema_requires_database_specific_authorization(self):
        with self.assertRaisesRegex(AdminBootstrapError, "explicit approval"):
            with self.engine.begin() as db:
                initialize_bootstrap_state(db, self.users, {"ONTICARDS_BOOTSTRAP_NEW_DATABASE": "other-db"})
        self.assertFalse(inspect(self.engine).has_table(bootstrap_state.name, schema="public"))

    def test_historical_id_only_marker_upgrades_and_blocks_replay(self):
        with self.engine.begin() as db:
            db.exec_driver_sql("CREATE TABLE public.admin_bootstrap_state (id smallint PRIMARY KEY)")
            db.exec_driver_sql("INSERT INTO public.admin_bootstrap_state VALUES (1)")
            migrate_bootstrap_state(db, self.users)
        self.assertEqual(self.state()["phase"], "legacy")
        with self.assertRaisesRegex(AdminBootstrapError, "already consumed"):
            self.initialize()

    def test_interrupted_migration_rolls_back_then_can_repeat(self):
        self.put_legacy_user()
        original = self.rows()
        with self.assertRaisesRegex(RuntimeError, "simulated migration interruption"):
            with self.engine.begin() as db:
                migrate_bootstrap_state(db, self.users)
                raise RuntimeError("simulated migration interruption")
        self.assertFalse(inspect(self.engine).has_table(bootstrap_state.name, schema="public"))
        self.assertEqual(self.rows(), original)
        self.assertFalse(self.initialize({}))
        self.assertEqual(self.state()["phase"], "legacy")

    def test_database_commit_failure_does_not_create_collection(self):
        self.fresh()
        real = self.engine

        class CommitFailure:
            @contextmanager
            def begin(self):
                with real.begin() as db:
                    db.exec_driver_sql("CREATE TEMP TABLE missing_parent (id integer PRIMARY KEY) ON COMMIT DROP")
                    db.exec_driver_sql("CREATE TEMP TABLE deferred_failure (id integer REFERENCES missing_parent(id)"
                                       " DEFERRABLE INITIALLY DEFERRED) ON COMMIT DROP")
                    yield db
                    db.exec_driver_sql("INSERT INTO deferred_failure VALUES (1)")

        with self.assertRaises(IntegrityError):
            self.initialize(engine=CommitFailure())
        self.assertFalse(self.rows())
        self.assertEqual(self.state()["phase"], "fresh")
        self.assertEqual(_request(WEAVIATE, self.path)[0], 404)

    def test_pending_recovers_after_restart_and_is_idempotent(self):
        self.create_pending()
        self.password_file.unlink()
        restarted = create_engine(self.url, hide_parameters=True)
        self.addCleanup(restarted.dispose)
        self.assertFalse(self.initialize({}, engine=restarted))
        self.assertFalse(self.initialize({}, engine=restarted))
        self.assertEqual(self.state()["phase"], "ready")
        self.assertEqual(_request(WEAVIATE, self.path)[0], 200)

    def test_collection_success_with_state_update_failure_is_recoverable(self):
        self.create_pending()
        with self.assertRaisesRegex(RuntimeError, "state write interrupted"):
            with self.engine.begin() as db:
                def create_then_fail(name, owner, claim):
                    ensure_account_collection(WEAVIATE, name, owner, claim)
                    raise RuntimeError("state write interrupted")
                recover_admin_collection(db, self.users, create_then_fail)
        self.assertEqual(self.state()["phase"], "pending")
        self.assertEqual(_request(WEAVIATE, self.path)[0], 200)
        self.assertFalse(self.initialize({}))
        self.assertEqual(self.state()["phase"], "ready")

    def test_existing_foreign_collection_is_never_reused_or_deleted(self):
        self.create_pending()
        foreign = {"class": self.namespace, "description": "Existing foreign owner", "vectorizer": "none"}
        self.assertIn(_request(WEAVIATE, "/v1/schema", method="POST", body=foreign)[0], (200, 201))
        with self.assertRaisesRegex(AdminBootstrapError, "ownership or schema"):
            self.initialize({})
        status, actual = _request(WEAVIATE, self.path)
        self.assertEqual(status, 200)
        self.assertEqual(actual["description"], foreign["description"])
        self.assertEqual(self.state()["phase"], "pending")

    def test_same_owner_with_incompatible_schema_fails(self):
        self.create_pending()
        wrong = {"class": self.namespace, "description": "OntiCards administrator bootstrap owner "
                 + self.state()["owner"], "vectorizer": "none", "properties": []}
        self.assertIn(_request(WEAVIATE, "/v1/schema", method="POST", body=wrong)[0], (200, 201))
        with self.assertRaisesRegex(AdminBootstrapError, "ownership or schema"):
            self.initialize({})
        self.assertEqual(self.state()["phase"], "pending")
        self.assertEqual(_request(WEAVIATE, self.path)[0], 200)

    def test_unknown_commit_result_rechecks_persisted_database_state(self):
        self.fresh()
        real = self.engine

        class LostCommitAcknowledgement:
            pending = True

            @contextmanager
            def begin(self):
                with real.begin() as db:
                    yield db
                if self.pending:
                    self.pending = False
                    raise DBAPIError("COMMIT", None, OSError("reply lost"), connection_invalidated=True)

        self.assertFalse(self.initialize(engine=LostCommitAcknowledgement()))
        self.assertEqual(self.state()["phase"], "ready")
        self.assertEqual(len(self.rows()), 1)

    def test_unknown_commit_without_persisted_account_cannot_create_collection(self):
        self.fresh()
        real = self.engine

        class LostCommitWithoutPersistence:
            pending = True

            @contextmanager
            def begin(self):
                with real.begin() as db:
                    yield db
                    if self.pending:
                        self.pending = False
                        raise DBAPIError("COMMIT", None, OSError("connection lost"), connection_invalidated=True)

        with self.assertRaises(DBAPIError):
            self.initialize(engine=LostCommitWithoutPersistence())
        self.assertFalse(self.rows())
        self.assertEqual(self.state()["phase"], "fresh")
        self.assertEqual(_request(WEAVIATE, self.path)[0], 404)
