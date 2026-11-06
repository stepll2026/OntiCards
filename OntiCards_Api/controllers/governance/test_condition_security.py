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
                     "(column IS NULL OR column = '')",
                     "column >= CURRENT_DATE - INTERVAL '7 days'"]:
            with self.subTest(expr=expr):
                self.assertTrue(validate(expr))

    def test_reject_statement_escape_and_side_effects(self):
        for expr in ["column > 0); DROP TABLE users; --", "' OR 1=1 --",
                     "column IN (SELECT secret FROM users)", "pg_sleep(1) = 0",
                     "public.pg_sleep(1) = 0", "column > 0) OR (1=1",
                     "column = 1 UNION SELECT 2", "column/*x*/ > 0",
                     "column = 1 INTO OUTFILE '/tmp/x'", "column = 1; SELECT 2",
                     "column = $$evil$$", "column = 'x\\' OR 1=1 --'",
                     "column column", "column IN ()", "column >", "column = @x"]:
            with self.subTest(expr=expr):
                self.assertFalse(validate(expr))

    def test_input_bounds(self):
        for expr in [[], {}, 1, "("*200 + "column>0" + ")"*200]:
            with self.subTest(expr=str(expr)[:40]):
                self.assertFalse(validate(expr))


if __name__ == "__main__":
    unittest.main(verbosity=2)
