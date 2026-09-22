"""Exercise the real retry/execution functions without booting Flask or reaching a service.

AST isolation only removes module startup/import side effects. The actual source functions,
SQL FROM scanner and JOIN scope validator run unchanged; only I/O collaborators are mocked.
"""
import ast
import copy
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "controllers/query/query_by_datacards_agg.py"
TREE = ast.parse(SOURCE.read_text(encoding="utf-8"))


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SCOPE = load_module("isolated_sql_join_scope", "controllers/query/sql_join_scope.py")
FROM_GUARD = load_module("isolated_sql_from_guard", "controllers/query/sql_from_guard.py")


def isolated_functions():
    names = {
        "_append_join_scope_rules", "_sql_error_details", "_classify_sql_execution_error",
        "_build_sql_retry_prompt", "_all_clusters_failed", "_strip_code_fences",
        "_load_sql_retry_templates", "_retry_sql_generation", "_exec_cluster_parallel",
        "_remove_sql_comments", "_extract_sql_from_llm_text", "_strip_nolock", "_norm_ident",
        "_exec_cluster", "run_sql_safe_new", "build_cluster_tables", "_pick_template_by_db",
    }
    body = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)]
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            body.append(copy.deepcopy(node))
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id.startswith("_JOIN_SCOPE_")
            for target in node.targets
        ):
            body.append(copy.deepcopy(node))
    namespace = {
        "re": re, "json": json, "time_module": time,
        "JoinAliasScopeError": SCOPE.JoinAliasScopeError,
        "validate_join_alias_scope": SCOPE.validate_join_alias_scope,
        "iter_from_table_refs": FROM_GUARD.iter_from_table_refs,
        "text": lambda sql: sql,
        "_make_json_serializable": lambda value: value,
        "_collect_entity_ids": lambda rows, key: set(),
        "make_tables_block": lambda dialect, tables: "project(id), occupy(id, project_id), budget(id, project_id)",
        "make_rels_block": lambda tables: "project.id = occupy.project_id; project.id = budget.project_id",
        "print": lambda *args, **kwargs: None,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(SOURCE), "exec"), namespace)
    # Test templates intentionally represent older database records without failed_sql / JOIN rules.
    namespace["load_prompt"] = lambda name: (
        "旧数据库重试模板：{{error_msg}}" if name.startswith("retry_") else "旧数据库模板：{{user_question}}"
    )

    def render_prompt(template, **values):
        for key, value in values.items():
            template = template.replace("{{" + key + "}}", str(value))
        return template

    namespace["render_prompt"] = render_prompt
    return namespace


TABLES = [
    {"table_name": '"app-data"."project"', "alias": "t1", "database_name": "fixture",
     "columns": [{"name": "id", "type": "integer"}]},
    {"table_name": '"app-data"."occupy"', "alias": "t2", "database_name": "fixture",
     "columns": [{"name": "id", "type": "integer"}, {"name": "project_id", "type": "integer"}]},
    {"table_name": '"app-data"."budget"', "alias": "t3", "database_name": "fixture",
     "columns": [{"name": "id", "type": "integer"}, {"name": "project_id", "type": "integer"}]},
]
BAD_SQL = '''SELECT t1."id" FROM "app-data"."project" AS t1
LEFT JOIN "app-data"."occupy" AS t2 ON t2."project_id" = t3."project_id"
LEFT JOIN "app-data"."budget" AS t3 ON t1."id" = t3."project_id"'''
GOOD_SQL = '''SELECT t1."id" FROM "app-data"."project" AS t1
LEFT JOIN "app-data"."occupy" AS t2 ON t1."id" = t2."project_id"
LEFT JOIN "app-data"."budget" AS t3 ON t1."id" = t3."project_id"'''


class FakeDriverError(Exception):
    def __init__(self, message, sqlstate):
        super().__init__(message)
        self.pgcode = sqlstate
        self.diag = SimpleNamespace(message_primary=message)


class FakeEngine:
    def __init__(self, errors=(), rows=((2,),)):
        self.connect_calls = 0
        self.executed = []
        self.errors = list(errors)
        self.rows = rows
        self.disposed = False

    def connect(self):
        self.connect_calls += 1
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql):
        self.executed.append(sql)
        if self.errors:
            raise self.errors.pop(0)
        return SimpleNamespace(returns_rows=True, fetchall=lambda: self.rows, keys=lambda: ["count_result"])

    def dispose(self):
        self.disposed = True


class JoinScopeRetryTests(unittest.TestCase):
    def setUp(self):
        self.ns = isolated_functions()
        self.engine = FakeEngine()
        self.ns["get_db_engine"] = lambda *args, **kwargs: self.engine
        self.prompts = []

    def cluster(self, generated_sqls, dialect="postgresql"):
        responses = iter(generated_sqls)

        def llm(prompt, **kwargs):
            self.prompts.append(prompt)
            return "```sql\n" + next(responses) + "\n```", {"tokens": 1}

        self.ns["qian_wen_llm_with_usage"] = llm
        return self.ns["_exec_cluster"]("统计三张表", dialect, "fixture-only", TABLES, "id")

    def test_forward_join_rejected_before_opening_database(self):
        with self.assertRaises(SCOPE.JoinAliasScopeError):
            self.ns["run_sql_safe_new"](self.engine, BAD_SQL, TABLES, "postgresql")
        self.assertEqual(self.engine.connect_calls, 0)
        self.assertEqual(self.engine.executed, [])

    def test_retry_success_executes_only_corrected_sql(self):
        result = self.cluster([BAD_SQL, GOOD_SQL])
        self.assertEqual(result["rows"], [{"count_result": 2}])
        self.assertNotIn("error", result)
        self.assertEqual(self.engine.executed, [GOOD_SQL])
        self.assertEqual(len(self.prompts), 2)
        self.assertIn(BAD_SQL, self.prompts[1])

    def test_each_failed_attempt_is_sent_and_retries_are_bounded(self):
        second_bad = BAD_SQL.replace('t2."project_id"', 't2."id"')
        result = self.cluster([BAD_SQL, second_bad, BAD_SQL])
        self.assertIn("error", result)
        self.assertEqual(result["rows"], [])
        self.assertEqual(len(self.prompts), 3)
        self.assertIn(second_bad, self.prompts[2])
        self.assertNotIn(BAD_SQL, self.prompts[2])
        self.assertEqual(self.engine.executed, [])
        self.assertEqual(self.engine.connect_calls, 0)

    def test_corrected_sql_is_rechecked_against_table_whitelist(self):
        forbidden = GOOD_SQL.replace('"app-data"."budget"', '"app-data"."not_allowed"')
        result = self.cluster([BAD_SQL, forbidden])
        self.assertIn("非白名单表", result["error"])
        self.assertEqual(len(self.prompts), 2)
        self.assertEqual(self.engine.executed, [])

    def test_corrected_sql_is_rechecked_for_multiple_statements(self):
        result = self.cluster([BAD_SQL, GOOD_SQL + '; DELETE FROM "app-data"."project"'])
        self.assertIn("error", result)
        self.assertEqual(self.engine.executed, [])
        self.assertEqual(self.engine.connect_calls, 0)

    def test_old_database_templates_still_include_mandatory_rules(self):
        self.cluster([BAD_SQL, GOOD_SQL])
        for prompt in self.prompts:
            self.assertIn("JOIN 作用域约束", prompt)
            self.assertIn("INNER/LEFT/RIGHT/FULL JOIN", prompt)
            self.assertIn("ON/WHERE", prompt)
        self.assertIn("本次失败 SQL", self.prompts[1])
        self.assertIn(BAD_SQL, self.prompts[1])

    def test_kingbase_uses_scope_validation(self):
        result = self.cluster([BAD_SQL, GOOD_SQL], dialect="kingbase")
        self.assertNotIn("error", result)
        self.assertEqual(self.engine.executed, [GOOD_SQL])

    def test_other_dialects_do_not_call_new_validator(self):
        self.ns["validate_join_alias_scope"] = Mock(side_effect=AssertionError("PG-only validator called"))
        result = self.ns["run_sql_safe_new"](self.engine, GOOD_SQL, TABLES, "mysql")
        self.assertEqual(result[0], [{"count_result": 2}])
        self.assertEqual(self.ns["_append_join_scope_rules"]("original", "mysql"), "original")

    def test_driver_from_clause_error_retries_with_failed_sql(self):
        self.engine.errors = [FakeDriverError('missing FROM-clause entry for table "t3"', "42P01")]
        result = self.cluster([GOOD_SQL, GOOD_SQL])
        self.assertNotIn("error", result)
        self.assertEqual(len(self.engine.executed), 2)
        self.assertIn(GOOD_SQL, self.prompts[1])
        self.assertIn('missing FROM-clause entry for table "t3"', self.prompts[1])

    def test_driver_42p10_invalid_reference_is_alias_error(self):
        info = self.ns["_classify_sql_execution_error"](
            FakeDriverError('invalid reference to FROM-clause entry for table "b"', "42P10"), "postgresql")
        self.assertTrue(info["retryable"])
        self.assertEqual(info["code"], "JOIN_ALIAS_OUT_OF_SCOPE")

    def test_42p01_missing_relation_is_not_alias_error(self):
        info = self.ns["_classify_sql_execution_error"](
            FakeDriverError('relation "missing_table" does not exist', "42P01"), "postgresql")
        self.assertTrue(info["retryable"])
        self.assertEqual(info["code"], "SQL_UNDEFINED_RELATION")

    def test_driver_diagnostics_exclude_sqlalchemy_parameter_dump(self):
        original = FakeDriverError('missing FROM-clause entry for table "b"', "42P01")
        wrapper = RuntimeError("sensitive SQL/parameters should not enter error details")
        wrapper.orig = original
        message, state = self.ns["_sql_error_details"](wrapper)
        self.assertEqual(message, str(original))
        self.assertEqual(state, "42P01")
        fallback, _ = self.ns["_sql_error_details"](RuntimeError("syntax error\n[SQL: secret]\n[parameters: hidden]"))
        self.assertEqual(fallback, "syntax error")

    def test_permission_error_does_not_trigger_model_retries(self):
        self.engine.errors = [FakeDriverError("permission denied for table project", "42501")]
        result = self.cluster([GOOD_SQL])
        self.assertIn("error", result)
        self.assertEqual(len(self.prompts), 1)

    def test_all_retry_usage_is_accumulated_with_real_wrapper_fields(self):
        replies = iter([BAD_SQL, BAD_SQL, GOOD_SQL])
        usage = {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14, "generation_ms": 100}
        self.ns["qian_wen_llm_with_usage"] = lambda *args, **kwargs: (next(replies), usage.copy())
        result = self.ns["_exec_cluster"]("fixture", "postgresql", "fixture-only", TABLES, "id")
        self.assertNotIn("error", result)
        self.assertEqual(result["_llm_usage"], {
            "prompt_tokens": 30, "completion_tokens": 12, "total_tokens": 42, "generation_ms": 300})

    def test_non_sql_retry_still_counts_usage_and_preserves_failed_sql(self):
        replies = iter([BAD_SQL, "I cannot generate this query"])
        self.ns["qian_wen_llm_with_usage"] = lambda *args, **kwargs: (next(replies), {
            "prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14, "generation_ms": 100})
        result = self.ns["_exec_cluster"]("fixture", "postgresql", "fixture-only", TABLES, "id")
        self.assertIn("模型未返回可执行 SQL", result["error"])
        self.assertEqual(result["target_sql"], " ".join(BAD_SQL.split()))
        self.assertEqual(result["_llm_usage"]["total_tokens"], 28)
        self.assertEqual(result["warnings"], ["查询执行失败，已重试 1 次"])

    def test_scope_retry_model_exception_is_a_structured_failure(self):
        self.ns["qian_wen_llm_with_usage"] = Mock(side_effect=[
            (BAD_SQL, {"total_tokens": 14}), TimeoutError("private URL/token must not be returned")])
        result = self.ns["_exec_cluster"]("fixture", "postgresql", "fixture-only", TABLES, "id")
        self.assertIn("TimeoutError", result["error"])
        self.assertNotIn("private URL", result["error"])
        self.assertEqual(result["target_sql"], " ".join(BAD_SQL.split()))
        self.assertEqual(result["_llm_usage"]["total_tokens"], 14)
        self.assertTrue(self.ns["_all_clusters_failed"]([result]))
        self.assertEqual(self.engine.executed, [])

    def test_driver_retry_model_exception_preserves_driver_diagnostic(self):
        self.engine.errors = [FakeDriverError('missing FROM-clause entry for table "t3"', "42P01")]
        self.ns["qian_wen_llm_with_usage"] = Mock(side_effect=[
            (GOOD_SQL, {"total_tokens": 14}), RuntimeError("private upstream detail")])
        result = self.ns["_exec_cluster"]("fixture", "postgresql", "fixture-only", TABLES, "id")
        self.assertIn('missing FROM-clause entry for table "t3"', result["error"])
        self.assertIn("RuntimeError", result["error"])
        self.assertEqual(result["target_sql"], " ".join(GOOD_SQL.split()))
        self.assertEqual(self.engine.executed, [GOOD_SQL])

    def test_whitelist_retry_uses_failed_sql_and_accumulates_usage(self):
        bad_column = GOOD_SQL.replace('SELECT t1."id"', 'SELECT t1."not_allowed"')
        replies = iter([bad_column, GOOD_SQL])

        def llm(prompt, **kwargs):
            self.prompts.append(prompt)
            return next(replies), {"total_tokens": 14}

        self.ns["qian_wen_llm_with_usage"] = llm
        result = self.ns["_exec_cluster"]("fixture", "postgresql", "fixture-only", TABLES, "id")
        self.assertNotIn("error", result)
        self.assertIn(bad_column, self.prompts[1])
        self.assertEqual(result["_llm_usage"]["total_tokens"], 28)
        self.assertEqual(self.engine.executed, [GOOD_SQL])

    def test_preexecution_failures_are_not_successful_empty_results(self):
        cases = [
            ("I cannot generate SQL", "MODEL_SQL_MISSING"),
            ("SELECT 1", "SQL_FROM_MISSING"),
            (GOOD_SQL.replace('"app-data"."budget"', '"app-data"."forbidden"'), "SQL_TABLE_NOT_ALLOWED"),
        ]
        for output, code in cases:
            with self.subTest(code=code):
                self.ns["qian_wen_llm_with_usage"] = lambda *args, **kwargs: (output, {"total_tokens": 14})
                result = self.ns["_exec_cluster"]("fixture", "postgresql", "fixture-only", TABLES, "id")
                self.assertEqual(result["error_code"], code)
                self.assertTrue(self.ns["_all_clusters_failed"]([result]))
                self.assertTrue(self.ns["_all_clusters_failed"]([{"error": "scope error"}, result]))
        self.assertEqual(self.engine.connect_calls, 0)

    def test_parallel_retry_uses_snapshot_after_retry_cache_is_invalidated(self):
        original_load = self.ns["load_prompt"]
        snapshots = self.ns["_load_sql_retry_templates"]()
        self.assertEqual(set(snapshots), {"retry_execution_error.txt", "retry_whitelist_error.txt"})

        def uncached_load(name):
            if name.startswith("retry_"):
                raise RuntimeError("Working outside of application context.")
            return original_load(name)

        self.ns["load_prompt"] = uncached_load
        replies = iter([BAD_SQL, GOOD_SQL])
        self.ns["qian_wen_llm_with_usage"] = lambda *args, **kwargs: (next(replies), {"total_tokens": 14})
        with ThreadPoolExecutor(max_workers=1) as executor:
            index, result = executor.submit(
                self.ns["_exec_cluster_parallel"], 0, "postgresql", "fixture-only", TABLES, "id",
                retry_templates=snapshots).result()
        self.assertEqual(index, 0)
        self.assertNotIn("error", result)
        self.assertEqual(self.engine.executed, [GOOD_SQL])
        self.assertEqual(result["_llm_usage"]["total_tokens"], 28)

    def test_retry_template_load_failure_has_context_independent_fallback(self):
        self.ns["load_prompt"] = Mock(side_effect=RuntimeError("prompt database unavailable"))
        snapshots = self.ns["_load_sql_retry_templates"]()
        self.ns["qian_wen_llm_with_usage"] = Mock(return_value=(GOOD_SQL, {"total_tokens": 2}))
        sql, error = self.ns["_retry_sql_generation"](
            "prompt", "postgresql", BAD_SQL, "scope failure", {}, retry_templates=snapshots)
        self.assertIsNone(error)
        self.assertEqual(sql, GOOD_SQL)
        prompt = self.ns["qian_wen_llm_with_usage"].call_args.args[0]
        self.assertIn(BAD_SQL, prompt)
        self.assertIn("scope failure", prompt)
        self.assertIn("JOIN 作用域约束", prompt)

    def test_legitimate_empty_result_is_not_all_failed(self):
        self.engine.rows = []
        result = self.cluster([GOOD_SQL])
        self.assertEqual(result["rows"], [])
        self.assertNotIn("error", result)
        self.assertFalse(self.ns["_all_clusters_failed"]([result]))
        self.assertFalse(self.ns["_all_clusters_failed"]([]))
        self.assertFalse(self.ns["_all_clusters_failed"]([{"error": "failed"}, result]))

    def test_all_failed_endpoint_branch_returns_422_and_logs_failure(self):
        # Execute the actual endpoint branch, avoiding unrelated retrieval/auth/network setup.
        branch = next(node for node in ast.walk(TREE) if isinstance(node, ast.If)
                      and isinstance(node.test, ast.Call)
                      and isinstance(node.test.func, ast.Name)
                      and node.test.func.id == "_all_clusters_failed")
        function = ast.FunctionDef(
            name="endpoint_failure_branch",
            args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=[copy.deepcopy(branch)], decorator_list=[])
        logs = []
        self.ns.update({
            "cluster_results": [{"error": "scope failure", "target_sql": BAD_SQL,
                                 "rows": [], "_connect_info_raw": "private"}],
            "data_cards_info": [], "merge_strategy": "OR", "entity_key": "id", "user_id": "fixture",
            "original_question": "fixture question", "user_question": "fixture question",
            "source_datasource_ids": [], "source_datasource_names": [], "datasource_ids": [],
            "datasource_names": [], "table_names": [], "metrics": {}, "tokens": {}, "quality": {},
            "start_time": time.time(), "term_rewrite_performed": False,
            "_log_query": lambda **kwargs: logs.append(kwargs),
            "format_response": lambda payload, status, message: (payload, status, message),
        })
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), str(SOURCE), "exec"), self.ns)
        payload, status, message = self.ns["endpoint_failure_branch"]()
        self.assertEqual(status, 422)
        self.assertEqual(payload["error"], "ALL_CLUSTERS_FAILED")
        self.assertNotEqual(message, "success")
        self.assertEqual(len(logs), 1)
        self.assertFalse(logs[0]["success"])
        self.assertNotIn("_connect_info_raw", payload["clusters"][0])
        self.ns["cluster_results"] = [{"rows": [], "target_sql": GOOD_SQL}]
        self.assertIsNone(self.ns["endpoint_failure_branch"]())
        self.assertEqual(len(logs), 1)


if __name__ == "__main__":
    unittest.main()
