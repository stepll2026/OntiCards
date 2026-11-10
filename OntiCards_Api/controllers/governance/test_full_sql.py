"""Full SQL boundary regression; isolated fixtures, no model/provider services."""
import pathlib
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from sqlalchemy import text
from extensions.ext_database import db
from controllers.governance import test_condition_api as fixtures
from controllers.governance.audit_executor import RuleExecutor
from controllers.governance.condition_security import require_conditions_payload

BAD = [
    "SELECT 1; DELETE FROM items", "COMMIT", "BEGIN", "SET TRANSACTION READ WRITE",
    "DELETE FROM items RETURNING *", "UPDATE items SET price=0", "DROP TABLE items",
    "WITH x AS (DELETE FROM items RETURNING *) SELECT * FROM x",
    "SELECT * INTO copy_items FROM items", "SELECT * FROM items FOR UPDATE",
    "SELECT set_config('transaction_read_only', 'off', true)",
    "SELECT public.abs(price) FROM items", 'SELECT "ABS"(price) FROM items',
    "SELECT nextval('seq')", "SELECT * FROM read_csv('/tmp/x')",
    "SELECT 1 INTO OUTFILE '/tmp/x'", "SELECT @x := 1",
]

class FullSqlTests(unittest.TestCase):
    def test_payload_rejects_side_effects(self):
        for sql in BAD:
            for field in ("sql_text", "sql_preview"):
                with self.subTest(sql=sql, field=field):
                    with self.assertRaises(ValueError):
                        require_conditions_payload({field: sql})

    def test_read_queries(self):
        queries = [
            "SELECT COUNT(*) AS total_count, SUM(CASE WHEN price<0 THEN 1 ELSE 0 END) AS failed_count FROM items;",
            "WITH x AS (SELECT price FROM items) SELECT * FROM x UNION ALL SELECT price FROM items",
            "SELECT price, ROW_NUMBER() OVER (ORDER BY price) AS n FROM items",
            "SELECT * FROM items WHERE price IN (SELECT price FROM reference_items)",
            "SELECT '; -- literal' AS label",
        ]
        for sql in queries:
            with self.subTest(sql=sql):
                require_conditions_payload({"sql_text": sql})

class FullSqlApiTests(unittest.TestCase):
    setUp = fixtures.ConditionApiTests.setUp

    def test_all_payload_routes(self):
        for sql in BAD:
            for path, method, extra in [
                ("/rules", "post", {"create_source": "manual"}),
                ("/rules", "post", {"create_source": "template"}),
                ("/rules", "post", {"create_source": "ai", "rule_config": {"sql_preview": sql}}),
                ("/rules/id", "put", {}),
                ("/preview", "post", {}),
            ]:
                for field in ("sql_text", "sql_preview"):
                    body = dict(library_id="fixture", target_table="items", **extra)
                    body[field] = sql
                    with self.subTest(sql=sql, path=path, field=field, extra=extra):
                        response = getattr(self.client, method)(path, json=body)
                        self.assertEqual(response.status_code, 400, response.get_json())
                        self.assertIn("完整 SQL", response.get_json()["msg"])

    def test_nested_ai_sql_is_checked(self):
        from models.governance_rule import GovernanceRule
        with patch.object(GovernanceRule, "query", fixtures.Query(None)):
            response = self.client.post("/rules", json={
                "library_id": "fixture", "create_source": "ai", "rule_name": "nested",
                "rule_config": {"target_table": "items", "sql_preview": "COMMIT"}})
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertIn("完整 SQL", response.get_json()["msg"])

    def test_stored_sql_and_sample_reject_before_database_access(self):
        executor = RuleExecutor(db.engine, "sqlite", "fixture")
        for sql in BAD:
            self.rule.sql_text = sql
            with self.subTest(sql=sql), patch.object(executor, "_read_only_connection") as connection:
                with self.assertRaises(ValueError):
                    executor._generate_sql(self.rule)
                with self.assertRaises(ValueError):
                    executor._get_sample_data(self.rule)
                connection.assert_not_called()

    def test_update_and_execute_full_statistics(self):
        sql = "SELECT COUNT(*) AS total_count, SUM(CASE WHEN price<0 THEN 1 ELSE 0 END) AS failed_count FROM items WHERE price < 0 OR price >= 0"
        with patch.object(db.session, "commit"):
            response = self.client.put("/rules/id", json={"sql_text": sql})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self.rule.sql_text, sql)
        with db.engine.begin() as conn:
            conn.execute(text("CREATE TABLE items(price INTEGER)"))
            conn.execute(text("INSERT INTO items VALUES (-1), (5), (150)"))
        executor = RuleExecutor(db.engine, "sqlite", "fixture")
        result = executor.execute_rule(self.rule)
        self.assertNotEqual(result.status, "error", result.error_message)
        self.assertEqual((result.total_count, result.failed_count), (3, 1))

if __name__ == "__main__":
    unittest.main(verbosity=2)
