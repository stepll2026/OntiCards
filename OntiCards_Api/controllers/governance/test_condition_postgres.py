"""Optional isolated PostgreSQL acceptance: PR50_TEST_DATABASE_URL only."""
import json
import ast
import re
import os
import pathlib
import sys
import unittest
from types import SimpleNamespace
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from sqlalchemy import create_engine, text
from controllers.governance.condition_security import require_condition_expr, validate_condition_expr
from controllers.governance.dialect_adapter import DialectAdapter
from controllers.governance.audit_executor import RuleExecutor


@unittest.skipUnless(os.environ.get("PR50_TEST_DATABASE_URL"), "isolated database URL required")
class PostgresTests(unittest.TestCase):
    def test_conditions_and_side_effect_boundary(self):
        engine = create_engine(os.environ["PR50_TEST_DATABASE_URL"])
        adapter = DialectAdapter("postgresql")
        executor = RuleExecutor(engine, "postgresql", "onti", schema_name="pg_temp")
        with engine.begin() as conn:
            conn.execute(text("CREATE TEMP TABLE items(price INTEGER, phone TEXT)"))
            conn.execute(text("INSERT INTO items VALUES (-1, 'bad'), (5, '13812345678'), (150, 'bad')"))
            for column, expr, expected in [
                ("price", "column > 0 AND column < 100", 2),
                ("price", "CAST(column AS INTEGER) > 0", 1),
                ("phone", "column ~* '^1[3-9]\\d{9}$'", 2),
                ("price", "column IN (SELECT price FROM items WHERE price > 0)", 1),
            ]:
                with self.subTest(expr=expr):
                    sql = adapter.build_check_sql("items", column, expr, "custom_sql")
                    self.assertEqual(conn.execute(text(sql)).mappings().one()["failed_count"], expected)

            composite = SimpleNamespace(
                condition_expr=None, conditions_config=json.dumps({
                    "conditions": [
                        {"column": "price", "condition": "column > 0"},
                        {"column": "phone", "condition": "column = '13812345678'"},
                    ], "condition_mode": "AND"
                }), sql_text=None, target_table="items", target_column=None,
                rule_type="composite")
            composite_sql, params = executor._generate_sql(composite)
            self.assertEqual(conn.execute(text(composite_sql), params).mappings().one()["failed_count"], 2)
            composite.sql_text = composite_sql
            self.assertEqual(executor._generate_sql(composite)[0], composite_sql)

            conn.execute(text("CREATE TEMP TABLE marker(value INTEGER)"))
            conn.execute(text("""
                CREATE FUNCTION pg_temp.mark_write() RETURNS INTEGER
                LANGUAGE plpgsql AS $$ BEGIN INSERT INTO marker VALUES (1); RETURN 1; END $$;
            """))
            # A quoted name is a different PostgreSQL function than the
            # built-in, even when the SQL parser normalizes the node; those
            # calls are rejected before any SQL is built (checked below).
            quoted_expr = '"ABS"(column) > 0'
            # Real baseline control: an unconstrained expression can invoke a
            # database function with a write effect in the disposable database.
            baseline_path = pathlib.Path(os.environ["PR50_TEST_BASELINE"])
            baseline = ast.parse(baseline_path.read_text(encoding="utf-8"))
            api_class = next(n for n in baseline.body if isinstance(n, ast.ClassDef) and n.name == "RuleListApi")
            method = next(n for n in api_class.body if isinstance(n, ast.FunctionDef) and n.name == "_generate_preview_sql")
            namespace = {"re": re}
            exec(compile(ast.Module([method], []), str(baseline_path), "exec"), namespace)
            baseline_sql = namespace["_generate_preview_sql"](
                None, "items", "price", "pg_temp.mark_write() = 1",
                "custom_sql", db_type="postgresql")
            conn.execute(text(baseline_sql))
            self.assertGreater(conn.execute(text("SELECT COUNT(*) FROM marker")).scalar(), 0)
            conn.execute(text("DELETE FROM marker"))
            for expr in [
                quoted_expr, '"LOWER"(column) = \'x\'',
                "pg_temp.mark_write() = 1",
                "column IN (SELECT pg_temp.mark_write())",
                "column--1\n>0", "1--1",
                "column > 0) THEN 1 ELSE 0 END) AS failed_count FROM items UNION SELECT 2, 999 --",
                "EXISTS (SELECT 1 FROM items FOR UPDATE)",
            ]:
                with self.subTest(expr=expr):
                    self.assertFalse(validate_condition_expr(expr, "postgresql"))
                    rule = SimpleNamespace(condition_expr=expr, conditions_config=None, sql_text=None)
                    with self.assertRaises(ValueError):
                        executor._generate_sql(rule)
            self.assertEqual(conn.execute(text("SELECT COUNT(*) FROM marker")).scalar(), 0)
        engine.dispose()

    def test_execution_is_read_only_against_function_overloads(self):
        engine = create_engine(os.environ["PR50_TEST_DATABASE_URL"])
        executor = RuleExecutor(engine, "postgresql", "onti")
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS pr50_items CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS pr50_marker CASCADE"))
            conn.execute(text("CREATE TABLE pr50_items(phone TEXT, price INTEGER)"))
            conn.execute(text("INSERT INTO pr50_items VALUES ('x', -1), ('y', 5), ('z', 150)"))
            conn.execute(text("CREATE TABLE pr50_marker(value INTEGER)"))
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION public.abs(TEXT) RETURNS INTEGER
                LANGUAGE plpgsql VOLATILE AS
                $$ BEGIN INSERT INTO pr50_marker VALUES (9); RETURN 1; END $$;
            """))
        try:
            # The AST alone cannot know which overload the database binds, so a
            # legal-looking builtin name stays valid at the text layer.
            self.assertTrue(validate_condition_expr("ABS(column) > 0", "postgresql"))

            # Real baseline control: the unguarded detection SQL picks the
            # TEXT overload and writes, matching the reported P1.
            baseline_path = pathlib.Path(os.environ["PR50_TEST_BASELINE"])
            baseline = ast.parse(baseline_path.read_text(encoding="utf-8"))
            api_class = next(n for n in baseline.body if isinstance(n, ast.ClassDef) and n.name == "RuleListApi")
            method = next(n for n in api_class.body if isinstance(n, ast.FunctionDef) and n.name == "_generate_preview_sql")
            namespace = {"re": re}
            exec(compile(ast.Module([method], []), str(baseline_path), "exec"), namespace)
            baseline_sql = namespace["_generate_preview_sql"](
                None, "pr50_items", "phone", "ABS(column) > 0", "custom_sql", db_type="postgresql")
            with engine.begin() as conn:
                conn.execute(text(baseline_sql))
                self.assertGreater(conn.execute(text("SELECT COUNT(*) FROM pr50_marker")).scalar(), 0)
                conn.execute(text("DELETE FROM pr50_marker"))

            overload_rule = SimpleNamespace(
                library_id=None, id=None, rule_name="overload", rule_type="custom_sql",
                severity="warning", target_table="pr50_items", target_column="phone",
                condition_expr="ABS(column) > 0", conditions_config=None, sql_text=None,
                enabled=True)
            # The guarded execution path fails closed instead of writing.
            result = executor.execute_rule(overload_rule)
            self.assertEqual(result.status, "error", result.error_message)
            self.assertIn("read-only", (result.error_message or "").lower())
            with engine.begin() as conn:
                self.assertEqual(conn.execute(text("SELECT COUNT(*) FROM pr50_marker")).scalar(), 0)

            # Normal detection queries, including failure samples, still run.
            normal_rule = SimpleNamespace(
                library_id=None, id=None, rule_name="normal", rule_type="custom_sql",
                severity="warning", target_table="pr50_items", target_column="price",
                condition_expr="column > 0", conditions_config=None, sql_text=None,
                enabled=True)
            normal = executor.execute_rule(normal_rule)
            self.assertEqual(normal.status, "failed", normal.error_message)
            self.assertEqual((normal.total_count, normal.failed_count), (3, 1))
            self.assertTrue(normal.failed_samples)
            with engine.begin() as conn:
                self.assertEqual(conn.execute(text("SELECT COUNT(*) FROM pr50_marker")).scalar(), 0)
        finally:
            with engine.begin() as conn:
                conn.execute(text("DROP FUNCTION IF EXISTS public.abs(TEXT)"))
                conn.execute(text("DROP TABLE IF EXISTS pr50_items CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS pr50_marker CASCADE"))
            engine.dispose()

    @unittest.skipUnless(os.environ.get("PR50_TEST_DATABASE_URL_AUTOCOMMIT"),
                         "isolated autocommit database URL required")
    def test_autocommit_connection_is_rejected_before_writing(self):
        """数据源 autocommit 时 SET TRANSACTION READ ONLY 不生效，必须拒绝执行。"""
        engine = create_engine(os.environ["PR50_TEST_DATABASE_URL_AUTOCOMMIT"])
        executor = RuleExecutor(engine, "postgresql", "onti")
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS pr50_ac_items CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS pr50_ac_marker CASCADE"))
            conn.execute(text("CREATE TABLE pr50_ac_items(phone TEXT, price INTEGER)"))
            conn.execute(text("INSERT INTO pr50_ac_items VALUES ('x', -1), ('y', 5)"))
            conn.execute(text("CREATE TABLE pr50_ac_marker(value INTEGER)"))
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION public.abs(TEXT) RETURNS INTEGER
                LANGUAGE plpgsql VOLATILE AS
                $$ BEGIN INSERT INTO pr50_ac_marker VALUES (7); RETURN 1; END $$;
            """))
        try:
            rule = SimpleNamespace(
                library_id=None, id=None, rule_name="autocommit", rule_type="custom_sql",
                severity="warning", target_table="pr50_ac_items", target_column="phone",
                condition_expr="ABS(column) > 0", conditions_config=None, sql_text=None,
                enabled=True)
            result = executor.execute_rule(rule)
            self.assertEqual(result.status, "error", result.error_message)
            self.assertIn("只读事务", result.error_message or "")
            with engine.begin() as conn:
                self.assertEqual(conn.execute(text("SELECT COUNT(*) FROM pr50_ac_marker")).scalar(), 0)
                # 反证：同一 SQL 在 autocommit 连接上直接执行确实会写入。
                conn.execute(text('SELECT COUNT(*) FROM pr50_ac_items WHERE NOT (ABS("phone") > 0)'))
                self.assertGreater(
                    conn.execute(text("SELECT COUNT(*) FROM pr50_ac_marker")).scalar(), 0)
        finally:
            with engine.begin() as conn:
                conn.execute(text("DROP FUNCTION IF EXISTS public.abs(TEXT)"))
                conn.execute(text("DROP TABLE IF EXISTS pr50_ac_items CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS pr50_ac_marker CASCADE"))
            engine.dispose()


if __name__ == "__main__":
    unittest.main(verbosity=2)
