"""Optional isolated PostgreSQL acceptance: PR50_TEST_DATABASE_URL only."""
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

            conn.execute(text("CREATE TEMP TABLE marker(value INTEGER)"))
            conn.execute(text("""
                CREATE FUNCTION pg_temp.mark_write() RETURNS INTEGER
                LANGUAGE plpgsql AS $$ BEGIN INSERT INTO marker VALUES (1); RETURN 1; END $$;
            """))
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
