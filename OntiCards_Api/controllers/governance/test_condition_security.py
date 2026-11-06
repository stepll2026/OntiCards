"""Run directly on the pack host: python controllers/governance/test_condition_security.py."""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parent
ns = {}
tree = ast.parse((ROOT / "governance_api.py").read_text(encoding="utf-8"))
# The original contribution's validator is standalone; retain a red control.
for node in tree.body:
    if isinstance(node, ast.Import) and any(a.asname == "_re_expr_sanitize" for a in node.names):
        exec(compile(ast.Module([node], []), "<original>", "exec"), ns)
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "allowed_token_re" for t in node.targets):
        exec(compile(ast.Module([node], []), "<original>", "exec"), ns)
    if isinstance(node, ast.FunctionDef) and node.name == "_validate_condition_expr":
        exec(compile(ast.Module([node], []), "<original>", "exec"), ns)
if "_validate_condition_expr" in ns:
    validate = ns["_validate_condition_expr"]
else:
    from condition_security import validate_condition_expr as validate


class ConditionTests(unittest.TestCase):
    def test_business_conditions(self):
        for expr in ["column > 0", "column>0 AND column<100",
                     "column IS NOT NULL", "column NOT IN (1, 2, 3)",
                     "column BETWEEN -1 AND 2.5", "column LIKE 'col%'",
                     "CHAR_LENGTH(column) <= 20", "price >= cost",
                     "column = 'O''Brien'", "column ~ '^a.*$'",
                     "(column IS NULL OR column = '')", "column = $$literal$$",
                     "column >= CURRENT_DATE - INTERVAL '7 days'"]:
            with self.subTest(expr=expr):
                self.assertTrue(validate(expr))

    def test_reject_statement_escape_and_side_effects(self):
        for expr in ["column > 0); DROP TABLE users; --", "' OR 1=1 --",
                     "column IN (SELECT pg_sleep(1))", "pg_sleep(1) = 0",
                     "public.pg_sleep(1) = 0", "column > 0) OR (1=1",
                     "column = 1 UNION SELECT 2", "column/*x*/ > 0",
                     "column = 1 INTO OUTFILE '/tmp/x'", "column = 1; SELECT 2",
                     "column = 'x\\' OR 1=1 --'",
                     "column column", "column IN ()", "column >", "column = @x"]:
            with self.subTest(expr=expr):
                self.assertFalse(validate(expr))

    def test_existing_dialect_contracts(self):
        import inspect
        cases = [
            ("postgresql", "column ~* '^1[3-9]\\d{9}$'"),
            ("mssql", "column >= DATEADD(day, -7, GETDATE())"),
            ("mssql", "DATEDIFF(day, column, GETUTCDATE()) < 7"),
            ("mysql", "column >= DATE_SUB(NOW(), INTERVAL 7 DAY)"),
            ("sqlite", "column >= datetime('now', '-7 days')"),
            ("postgresql", "CAST(column AS INTEGER)>0"),
            ("postgresql", "EXTRACT(YEAR FROM column)>2000"),
            ("oracle", "column >= ADD_MONTHS(TRUNC(SYSDATE), -1)"),
            ("oracle", "TO_NUMBER(column) > 0"),
            ("oracle", "INSTR(column, 'x') > 0"),
            ("oracle", "CAST(column AS VARCHAR2(4000)) <> ''"),
            ("mssql", "CAST(column AS VARCHAR(MAX)) <> ''"),
            ("mysql", "CAST(column AS CHAR) <> ''"),
            ("postgresql", "COUNT(*) = 1"),
            ("oracle", "TO_DATE(column, 'YYYY-MM-DD') <= SYSDATE"),
            ("oracle", "TO_CHAR(column, 'YYYY') = '2026'"),
            ("mysql", "column >= DATE_ADD(CURDATE(), INTERVAL 1 MONTH)"),
            ("mysql", "DATEDIFF(NOW(), column) < 7"),
            ("mysql", "YEAR(column) > 2000 AND MONTH(column) <= 12 AND DAY(column) <= 31"),
            ("postgresql", "DATE_TRUNC('day', column) <= CURRENT_TIMESTAMP"),
            ("postgresql", "SUBSTRING(column, 1, 2) = CONCAT('a', 'b')"),
            ("sqlite", "julianday(column) <= julianday('now')"),
            ("sqlite", "date(column) <= date('now')"),
            ("mssql", "LEN(LTRIM(RTRIM(column))) > 0"),
            ("postgresql", "UPPER(LOWER(TRIM(column))) <> ''"),
            ("postgresql", "COALESCE(NULLIF(column, ''), 'x') = 'x'"),
            ("postgresql", "CAST(column AS DECIMAL(10, 2)) >= 0"),
            ("postgresql", "COUNT(column) OVER (PARTITION BY column) = 1"),
            ("postgresql", "referenced_id IN (SELECT id FROM reference_table)"),
        ]
        for dialect, expr in cases:
            with self.subTest(dialect=dialect, expr=expr):
                kwargs = {"db_type": dialect} if "db_type" in inspect.signature(validate).parameters else {}
                self.assertTrue(validate(expr, **kwargs))

    def test_comment_delimiters_are_not_arithmetic(self):
        for expr in ["column--1\n>0", "1--1", "column/**/ > 0"]:
            with self.subTest(expr=expr):
                self.assertFalse(validate(expr))
        self.assertTrue(validate("column = '--;x'"))

    def test_seed_sql_templates(self):
        import sqlglot
        source = (ROOT.parents[1] / "init.sql").read_text(encoding="utf-8")
        statement = source[source.index("INSERT INTO governance_rule_templates ("):].split("ON CONFLICT", 1)[0]
        rows = sqlglot.parse_one(statement, read="postgres").expression.expressions
        # The first 24 seeded templates have SQL predicates. The remaining
        # four include natural-language/unfilled UI examples, not executable SQL.
        self.assertEqual(len(rows[:24]), 24)
        for row in rows[:24]:
            template_id, expr = row.expressions[0].this, row.expressions[4].this
            with self.subTest(template=template_id):
                self.assertTrue(validate(expr))

    def test_input_bounds(self):
        for expr in [[], {}, 1, "("*200 + "column>0" + ")"*200]:
            with self.subTest(expr=str(expr)[:40]):
                self.assertFalse(validate(expr))


if __name__ == "__main__":
    unittest.main(verbosity=2)
