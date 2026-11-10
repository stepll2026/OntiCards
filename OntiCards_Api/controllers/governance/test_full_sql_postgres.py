"""Acceptance on an explicitly configured disposable PostgreSQL database only."""
import os
import pathlib
import sys
import unittest
from types import SimpleNamespace
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from sqlalchemy import create_engine, text
from controllers.governance.audit_executor import RuleExecutor
from controllers.governance.condition_security import require_read_only_sql
from controllers.governance.test_full_sql import BAD

@unittest.skipUnless(os.environ.get("PR60_TEST_DATABASE_URL"), "disposable database required")
class PostgresFullSqlTests(unittest.TestCase):
    def test_queries_and_no_writes(self):
        engine = create_engine(os.environ["PR60_TEST_DATABASE_URL"])
        executor = RuleExecutor(engine, "postgresql", "onti", schema_name="public")
        rule = SimpleNamespace(id=None, library_id=None, rule_name="full SQL",
            rule_type="custom_sql", severity="warning", target_table="items",
            target_column="price", condition_expr=None, conditions_config=None,
            enabled=True, sql_text=None)
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE items(price INTEGER, phone TEXT)"))
            conn.execute(text("INSERT INTO items VALUES (-1,'bad'),(5,'13812345678'),(150,'bad')"))
            conn.execute(text("CREATE TABLE marker(value INTEGER)"))
            conn.execute(text("""CREATE FUNCTION public.abs(TEXT) RETURNS INTEGER LANGUAGE plpgsql AS
                $$ BEGIN INSERT INTO marker VALUES (7); RETURN 1; END $$"""))
            # Positive control: this overload really writes without the executor guard.
            conn.execute(text("SELECT ABS(phone) FROM items"))
            self.assertEqual(conn.execute(text("SELECT COUNT(*) FROM marker")).scalar(), 3)
            conn.execute(text("DELETE FROM marker"))
        try:
            for sql in BAD:
                rule.sql_text = sql
                result = executor.execute_rule(rule)
                self.assertEqual(result.status, "error", (sql, result.error_message))
                self.assertIn("完整 SQL", result.error_message)
                with self.assertRaises(ValueError):
                    executor._get_sample_data(rule)
            rule.sql_text = "SELECT COUNT(*) AS total_count, SUM(CASE WHEN ABS(phone)>0 THEN 1 ELSE 0 END) AS failed_count FROM items"
            result = executor.execute_rule(rule)
            self.assertEqual(result.status, "error", result.error_message)
            self.assertIn("read-only", result.error_message.lower())
            self.assertEqual(executor._get_sample_data(rule), [])
            queries = [
                "SELECT COUNT(*) AS total_count, SUM(CASE WHEN price<0 THEN 1 ELSE 0 END) AS failed_count FROM items;",
                "WITH x AS (SELECT * FROM items) SELECT COUNT(*) AS total_count, SUM(CASE WHEN price<0 THEN 1 ELSE 0 END) AS failed_count FROM x",
                "SELECT COUNT(*) AS total_count, SUM(CASE WHEN price<0 THEN 1 ELSE 0 END) AS failed_count FROM items WHERE price IN (SELECT price FROM items)",
            ]
            for sql in queries:
                rule.sql_text = sql
                result = executor.execute_rule(rule)
                self.assertEqual((result.total_count, result.failed_count), (3, 1), result.error_message)
            # Normal sample path still returns the actual violating row.
            rule.sql_text = queries[0]
            samples = executor._get_sample_data(rule)
            self.assertEqual(samples[0]["sample_value"][0]["price"], -1)
            for sql in [
                "SELECT price, ROW_NUMBER() OVER (ORDER BY price) FROM items",
                "SELECT price FROM items UNION SELECT price FROM items",
                "SELECT phone ~ '^1[3-9]\\d{9}$', CURRENT_DATE - INTERVAL '7 days' FROM items",
            ]:
                require_read_only_sql(sql, "postgresql")
                with executor._read_only_connection() as conn:
                    self.assertTrue(conn.execute(text(sql)).all())
            with engine.begin() as conn:
                self.assertEqual(conn.execute(text("SELECT COUNT(*) FROM marker")).scalar(), 0)
                self.assertEqual(conn.execute(text("SELECT COUNT(*) FROM items")).scalar(), 3)
        finally:
            with engine.begin() as conn:
                conn.execute(text("DROP FUNCTION public.abs(TEXT)"))
                conn.execute(text("DROP TABLE items, marker"))
            engine.dispose()

if __name__ == "__main__":
    unittest.main(verbosity=2)
