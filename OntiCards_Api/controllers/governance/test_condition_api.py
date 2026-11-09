"""Isolated Flask/SQLite tests; no app factory, provider keys or external services."""
import json
from types import SimpleNamespace
import pathlib
import sys
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from flask import Flask
from flask_login import LoginManager, UserMixin
from sqlalchemy import text
from extensions.ext_database import db
from controllers.governance.governance_api import (
    RuleListApi, RuleDetailApi, RulePreviewApi)
from controllers.governance.dialect_adapter import DialectAdapter
from controllers.governance.audit_executor import RuleExecutor
from controllers.governance.condition_security import replace_column

# API ownership/query fixtures are synthetic; SQL expressions execute on real SQLite.
class Query:
    def __init__(self, obj):
        self.obj = obj
    def filter_by(self, **kw): return self
    def filter(self, *args): return self
    def join(self, *args): return self
    def first(self): return self.obj
    def get(self, key): return self.obj

class ConditionApiTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY="isolated-test", SQLALCHEMY_DATABASE_URI="sqlite://")
        db.init_app(self.app)
        login = LoginManager(self.app)
        class User(UserMixin):
            id = "synthetic-owner"
        @login.request_loader
        def load(req): return User()
        self.app.add_url_rule("/rules", endpoint="create", view_func=lambda: RuleListApi().post(), methods=["POST"])
        self.app.add_url_rule("/rules/id", endpoint="update", view_func=lambda: RuleDetailApi().put("id"), methods=["PUT"])
        self.app.add_url_rule("/preview", endpoint="preview", view_func=lambda: RulePreviewApi().post(), methods=["POST"])
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)
        from models.governance_rule import GovernanceRule
        self.rule = GovernanceRule(id=uuid.uuid4(), rule_name="fixture", rule_type="custom_sql",
                                   target_table="items", target_column="price", db_type="sqlite")
        query_patch = patch.object(GovernanceRule, "query", Query(self.rule))
        query_patch.start()
        self.addCleanup(query_patch.stop)
        from models.governance_rule_library import GovernanceRuleLibrary
        from models.datasource_infos import DatasourceInfo
        for model, fixture in [
            (GovernanceRuleLibrary, SimpleNamespace(datasource_id="fixture")),
            (DatasourceInfo, SimpleNamespace(db_type="sqlite", schema_name=None)),
        ]:
            fixture_patch = patch.object(model, "query", Query(fixture))
            fixture_patch.start()
            self.addCleanup(fixture_patch.stop)

    def test_reject_before_orm_queries(self):
        bad = ["column > 0); DROP TABLE users; --", "column IN (SELECT pg_sleep(1))", "pg_sleep(1) = 0"]
        for expr in bad:
            for path, method, body in [
                ("/rules", "post", {"condition_expr": expr}),
                ("/rules/id", "put", {"condition_expr": expr}),
                ("/rules", "post", {"conditions": [{"column": "price", "condition": expr}]}),
                ("/rules/id", "put", {"conditions": [{"column": "price", "condition": expr}]}),
                ("/preview", "post", {"target_table": "items", "condition_expr": expr}),
                ("/preview", "post", {"target_table": "items", "conditions": [{"column": "price", "condition": expr}]})
            ]:
                with self.subTest(expr=expr, path=path, method=method):
                    body["library_id"] = str(uuid.uuid4())
                    response = getattr(self.client, method)(path, json=body)
                    self.assertEqual(response.status_code, 400, response.get_json())
                    self.assertIn("条件表达式", response.get_json()["msg"])

    def test_create_single_and_composite(self):
        from models.governance_rule import GovernanceRule
        from models.governance_rule_library import GovernanceRuleLibrary
        from models.datasource_infos import DatasourceInfo
        library = SimpleNamespace(datasource_id="fixture")
        datasource = SimpleNamespace(db_type="sqlite", schema_name=None)
        base = {"library_id": str(uuid.uuid4()), "rule_name": "new", "target_table": "items",
                "target_column": "price", "condition_expr": "column > 0"}
        with patch.object(GovernanceRule, "query", Query(None)), \
             patch.object(GovernanceRuleLibrary, "query", Query(library)), \
             patch.object(DatasourceInfo, "query", Query(datasource)), \
             patch.object(db.session, "add") as add, patch.object(db.session, "commit"):
            response = self.client.post("/rules", json=base)
            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertEqual(add.call_args.args[0].condition_expr, '"price" > 0')
            base.update(rule_type="composite", conditions=[{"column": "price", "condition": "column > 0"}])
            response = self.client.post("/rules", json=base)
            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertIn('NOT ("price" > 0)', add.call_args.args[0].sql_text)

    def test_update_single_and_composite(self):
        with patch.object(db.session, "commit") as commit:
            r = self.client.put("/rules/id", json={"condition_expr": "column > 0"})
            self.assertEqual(r.status_code, 200, r.get_json())
            self.assertEqual(self.rule.condition_expr, "column > 0")
            r = self.client.put("/rules/id", json={
                "conditions": [{"column": "price", "condition": "column > 0"}]})
            self.assertEqual(r.status_code, 200, r.get_json())
            self.assertEqual(json.loads(self.rule.conditions_config)["conditions"][0]["condition"], '"price" > 0')
            self.assertEqual(commit.call_count, 2)

    def test_stored_rule_execution_rejects_injection(self):
        executor = RuleExecutor(db.engine, "sqlite", "fixture")
        self.rule.condition_expr = "column IN (SELECT pg_sleep(1))"
        with self.assertRaises(ValueError):
            executor._generate_sql(self.rule)
        self.rule.condition_expr = "column > 0"
        with db.engine.begin() as conn:
            conn.execute(text("CREATE TABLE items(price INTEGER)"))
            conn.execute(text("INSERT INTO items VALUES (-1), (5), (150)"))
            sql, params = executor._generate_sql(self.rule)
            self.assertEqual(conn.execute(text(sql), params).mappings().one()["failed_count"], 1)

    def test_persisted_composite_rules_execute_and_sample(self):
        executor = RuleExecutor(db.engine, "sqlite", "fixture")
        self.rule.rule_type = "composite"
        self.rule.target_column = None
        self.rule.condition_expr = None
        self.rule.set_conditions([
            {"column": "price", "condition": "column = 'column'"},
            {"column": "qty", "condition": "column > 0"},
        ], "AND")
        self.assertIsInstance(self.rule.conditions_config, str)
        with db.engine.begin() as conn:
            conn.execute(text("CREATE TABLE items(price TEXT, qty INTEGER)"))
            conn.execute(text("INSERT INTO items VALUES ('column', -1)"))
        generated_sql = executor._generate_sql(self.rule)[0]
        for confirmed_sql in [None, generated_sql]:
            with self.subTest(confirmed_sql=confirmed_sql):
                self.rule.sql_text = confirmed_sql
                sql, params = executor._generate_sql(self.rule)
                with db.engine.begin() as conn:
                    rows = conn.execute(text(sql), params).mappings().all()
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]["failed_count"], 1)
                samples = executor._get_sample_data(self.rule)
                self.assertEqual([v["column"] for v in samples[0]["violated_conditions"]], ["qty"])

    def test_composite_sample_attribution_preserves_literal(self):
        executor = RuleExecutor(db.engine, "sqlite", "fixture")
        self.rule.rule_type = "composite"
        self.rule.target_column = None
        self.rule.condition_expr = None
        # Also support already-decoded configuration objects.
        self.rule.conditions_config = {"conditions": [
            {"column": "price", "condition": "column = 'column'"},
            {"column": "qty", "condition": "column > 0"},
        ], "condition_mode": "AND"}
        with db.engine.begin() as conn:
            conn.execute(text("CREATE TABLE items(price TEXT, qty INTEGER)"))
            conn.execute(text("INSERT INTO items VALUES ('column', -1)"))
        samples = executor._get_sample_data(self.rule)
        self.assertEqual([v["column"] for v in samples[0]["violated_conditions"]], ["qty"])

    def test_execute_rule_runs_detection_query(self):
        executor = RuleExecutor(db.engine, "sqlite", "fixture")
        self.rule.condition_expr = "column > 0"
        with db.engine.begin() as conn:
            conn.execute(text("CREATE TABLE items(price INTEGER)"))
            conn.execute(text("INSERT INTO items VALUES (-1), (5), (150)"))
        result = executor.execute_rule(self.rule)
        self.assertNotEqual(result.status, "error", result.error_message)
        self.assertEqual((result.total_count, result.failed_count), (3, 1))
        self.assertTrue(result.failed_samples)

    def test_preview_uses_actual_dialect_and_preserves_literals(self):
        for dialect, name, quoted in [
            ("mysql", "odd`column", "`odd``column`"),
            ("mssql", "odd]column", "[odd]]column]"),
            ("postgresql", 'odd"column', '"odd""column"'),
            ("oracle", 'odd"column', '"odd""column"'),
        ]:
            with self.subTest(dialect=dialect):
                response = self.client.post("/preview", json={
                    "target_table": "items", "target_column": name, "db_type": dialect,
                    "condition_expr": "COLUMN = 'column; --'"})
                self.assertEqual(response.status_code, 200, response.get_json())
                sql = response.get_json()["data"]["sql"]
                self.assertIn(quoted, sql)
                self.assertIn("'column; --'", sql)
        for dialect, expr in [
            ("mssql", "column >= DATEADD(day, -7, GETDATE())"),
            ("mysql", "column >= DATE_SUB(NOW(), INTERVAL 7 DAY)"),
            ("sqlite", "column >= datetime('now', '-7 days')"),
        ]:
            with self.subTest(dialect=dialect, expr=expr):
                response = self.client.post("/preview", json={
                    "target_table": "items", "target_column": "price",
                    "db_type": dialect, "condition_expr": expr})
                self.assertEqual(response.status_code, 200, response.get_json())

    def test_real_preview_and_sqlite_execution(self):
        response = self.client.post("/preview", json={
            "target_table": "items", "target_column": "price", "db_type": "sqlite",
            "condition_expr": "column > 0 AND column < 100"})
        self.assertEqual(response.status_code, 200, response.get_json())
        sql = response.get_json()["data"]["sql"]
        with self.app.app_context():
            with db.engine.begin() as conn:
                conn.execute(text("CREATE TABLE items(price INTEGER)"))
                conn.execute(text("INSERT INTO items VALUES (-1), (5), (150)"))
                row = conn.execute(text(sql)).mappings().one()
                self.assertEqual((row["total_count"], row["failed_count"]), (3, 2))

    def test_placeholder_literals_and_escaped_identifiers(self):
        adapter = DialectAdapter("sqlite")
        self.assertEqual(replace_column("COLUMN = 'column' AND mycolumn = 'x'", adapter.quote_identifier('odd"column')),
                         '"odd""column" = \'column\' AND mycolumn = \'x\'')
        with self.app.app_context():
            with db.engine.begin() as conn:
                conn.execute(text('CREATE TABLE t("odd""column" TEXT)'))
                conn.execute(text('INSERT INTO t VALUES (\'column\'), (\'other\')'))
                sql = adapter.build_check_sql("t", 'odd"column', "column = 'column'", "custom_sql")
                self.assertEqual(conn.execute(text(sql)).mappings().one()["failed_count"], 1)

if __name__ == "__main__":
    unittest.main(verbosity=2)
