"""Standalone column quoting regression tests; no app or database credentials."""
import ast
import importlib.util
from pathlib import Path
import sqlite3
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("dialect_adapter", ROOT / "dialect_adapter.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
DialectAdapter = module.DialectAdapter

# Load only the real preview methods, without importing the application.
tree = ast.parse((ROOT / "governance_api.py").read_text(encoding="utf-8"))
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "RuleListApi")
methods = [n for n in cls.body if isinstance(n, ast.FunctionDef)
           and n.name in ("_generate_preview_sql", "_generate_composite_preview_sql")]
stub = types.ModuleType("controllers.governance.dialect_adapter")
stub.DialectAdapter = DialectAdapter
sys.modules[stub.__name__] = stub
import re
namespace = {"re": re}
exec(compile(ast.Module(body=methods, type_ignores=[]), "<actual-preview-methods>", "exec"), namespace)

class ColumnQuotingTests(unittest.TestCase):
    def test_delimiter_escaping(self):
        for dialect in module.DIALECT_CONFIGS:
            with self.subTest(dialect=dialect):
                adapter = DialectAdapter(dialect)
                close = adapter.dialect.identifier_quote[-1]
                name = "a" + close + "; SELECT 1 --"
                expected = adapter.dialect.identifier_quote.format(name.replace(close, close * 2))
                self.assertEqual(adapter.quote_identifier(name), expected)

    def test_only_bare_placeholder_is_replaced(self):
        for dialect in module.DIALECT_CONFIGS:
            with self.subTest(dialect=dialect):
                adapter = DialectAdapter(dialect)
                expr = """COLUMN <> 'column' AND column_name > 0 AND "column" > 0 AND [column] > 0 AND `column` > 0"""
                expected = adapter.quote_identifier("column") + expr[len("COLUMN"):]
                result = adapter.adapt_condition_expr(expr, "column")
                self.assertEqual(result, expected)
                self.assertEqual(adapter.adapt_condition_expr(result, "column"), result)

    def test_backslash_identifier_does_not_become_regex_replacement(self):
        self.assertEqual(DialectAdapter("postgresql").adapt_condition_expr("column > 0", r"a\1"),
                         '"a\\1" > 0')

    def test_preview_uses_dialect_and_does_not_requote(self):
        for dialect in module.DIALECT_CONFIGS:
            adapter = DialectAdapter(dialect)
            for column in ("amount", "column", 'a"b', "a]b", "a`b", r"a\1"):
                with self.subTest(dialect=dialect, column=column):
                    expression = adapter.adapt_condition_expr("column > 0", column)
                    single = namespace["_generate_preview_sql"](None, "items", column, expression,
                                                                 "custom_sql", db_type=dialect)
                    composite = namespace["_generate_composite_preview_sql"](
                        None, "items", [{"column": column, "condition": expression}], db_type=dialect)
                    for sql in (single, composite):
                        self.assertIn("NOT (" + expression + ")", sql)

    def test_public_preview_builders_preserve_conditions(self):
        for dialect in module.DIALECT_CONFIGS:
            adapter = DialectAdapter(dialect)
            for name in ("column", r"a\1"):
                expression = adapter.quote_identifier(name) + " <> 'column'"
                with self.subTest(dialect=dialect, name=name):
                    single = adapter.build_check_sql("items", name, expression, "custom_sql")
                    multi = adapter.build_multi_condition_sql(
                        "items", [{"column": name, "condition": expression}])
                    for sql in (single, multi):
                        self.assertIn("NOT (" + expression + ")", sql)

    def test_sqlite_real_execution_and_injection_control(self):
        db = sqlite3.connect(":memory:")
        try:
            adapter = DialectAdapter("sqlite")
            for name in ('column', 'a"b', 'x") OR 1=1 --'):
                quoted = adapter.quote_identifier(name)
                db.execute("CREATE TABLE items (" + quoted + " INTEGER)")
                db.executemany("INSERT INTO items VALUES (?)", [(1,), (-1,)])
                sql = namespace["_generate_composite_preview_sql"](
                    None, "items", [{"column": name, "condition": "column > 0"}], db_type="sqlite")
                self.assertEqual(db.execute(sql).fetchone(), (2, 1))
                db.execute("DROP TABLE items")
        finally:
            db.close()

if __name__ == "__main__":
    unittest.main(verbosity=2)
