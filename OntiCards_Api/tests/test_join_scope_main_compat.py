"""Cross-check JOIN validation with the schema/REPLACE fixes merged from main.

Run actual source functions in isolation; only database/model I/O is replaced.
"""
import ast
import copy
from types import SimpleNamespace

import pytest

from test_join_scope_retry import (
    ROOT, SCOPE, TABLES, FakeEngine, isolated_functions,
)


def _source_functions(namespace, relative_path, names):
    path = ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)]
    nodes.extend(copy.deepcopy(node) for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name in names)
    assert len(nodes) == len(names) + 1
    module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)
    return namespace


def _runtime(variant="main"):
    namespace = isolated_functions()
    if variant == "plugin":
        _source_functions(namespace, "controllers/query/query_by_datacards_agg_plugin.py", {
            "run_sql_safe_new", "_strip_code_fences", "_strip_nolock", "_norm_ident",
        })
    return _source_functions(namespace, "controllers/query/sql_join_utils.py", {"card_to_table_obj"})


def _card_table(namespace, raw_table, dialect="postgresql"):
    row = SimpleNamespace(id="fixture", table_name="orders", database_name="database",
                          schema_name="public", db_type=dialect)
    card = {"SQLMeta": {"table": raw_table, "columns": [
        {"name": "id", "type": "integer"}, {"name": "status", "type": "text"},
    ]}}
    return namespace["card_to_table_obj"](row, card, "fixture-only", ds_schema_name="yx-data")


@pytest.mark.parametrize("variant", ["main", "plugin"])
@pytest.mark.parametrize("dialect", ["postgresql", "kingbase"])
@pytest.mark.parametrize("raw_table, expected_table", [
    ("orders", '"yx-data".orders'),
    ("database.orders", '"yx-data".orders'),
    ("yx-data.orders", '"yx-data".orders'),
    ('"yx-data".orders', '"yx-data".orders'),
    ('"yx-data"."orders"', '"yx-data"."orders"'),
])
def test_card_schema_conversion_and_replace_select_execute(variant, dialect, raw_table, expected_table):
    namespace = _runtime(variant)
    table = _card_table(namespace, raw_table, dialect)
    assert table["table_name"] == expected_table
    sql = f'SELECT REPLACE(t1."status", \'old\', \'new\') AS status FROM {table["table_name"]} AS t1'
    engine = FakeEngine(rows=(("new",),))

    data, warnings, elapsed = namespace["run_sql_safe_new"](engine, sql, [table], dialect)

    assert data == [{"count_result": "new"}]
    assert engine.executed == [sql]
    assert engine.connect_calls == 1
    assert not any("白名单" in warning for warning in warnings)
    assert elapsed >= 0


@pytest.mark.parametrize("variant", ["main", "plugin"])
@pytest.mark.parametrize("sql", [
    'REPLACE INTO "yx-data".orders (id) VALUES (1)',
    'SELECT t1.id FROM "yx-data".orders t1; REPLACE INTO "yx-data".orders (id) VALUES (1)',
    'SELECT t1.id FROM "yx-data".orders t1; DELETE FROM "yx-data".orders',
    'WITH changed AS (DELETE FROM "yx-data".orders RETURNING id) SELECT changed.id FROM changed',
])
def test_allowing_replace_function_does_not_allow_dml(variant, sql):
    namespace = _runtime(variant)
    table = _card_table(namespace, "orders")
    engine = FakeEngine()

    with pytest.raises(ValueError):
        namespace["run_sql_safe_new"](engine, sql, [table], "postgresql")

    assert engine.executed == []
    assert engine.connect_calls == 0


BAD_REPLACE_JOIN = '''SELECT REPLACE(t1."id"::text, '1', '2') AS count_result
FROM "app-data"."project" AS t1
LEFT JOIN "app-data"."occupy" AS t2
  ON t2."project_id"::text = REPLACE(t3."project_id"::text, '-', '')
LEFT JOIN "app-data"."budget" AS t3 ON t1."id" = t3."project_id"'''

GOOD_REPLACE_JOIN = '''SELECT REPLACE(t1."id"::text, '1', '2') AS count_result
FROM "app-data"."project" AS t1
LEFT JOIN "app-data"."budget" AS t3 ON t1."id" = t3."project_id"
LEFT JOIN "app-data"."occupy" AS t2
  ON t2."project_id"::text = REPLACE(t3."project_id"::text, '-', '')'''


def test_future_alias_inside_replace_is_rejected_before_database_access():
    namespace = _runtime()
    engine = FakeEngine()

    with pytest.raises(SCOPE.JoinAliasScopeError) as caught:
        namespace["run_sql_safe_new"](engine, BAD_REPLACE_JOIN, TABLES, "postgresql")

    assert caught.value.alias == "t3"
    assert caught.value.code == "JOIN_ALIAS_OUT_OF_SCOPE"
    assert engine.executed == []
    assert engine.connect_calls == 0


def test_retry_to_replace_query_keeps_usage_and_old_prompt_compatibility():
    namespace = _runtime()
    engine = FakeEngine()
    namespace["get_db_engine"] = lambda *args, **kwargs: engine
    replies = iter([BAD_REPLACE_JOIN, GOOD_REPLACE_JOIN])
    prompts = []

    def model(prompt, **kwargs):
        prompts.append(prompt)
        return next(replies), {
            "prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14, "generation_ms": 100,
        }

    namespace["qian_wen_llm_with_usage"] = model
    result = namespace["_exec_cluster"]("fixture", "postgresql", "fixture-only", TABLES, "id")

    assert "error" not in result
    assert result["rows"] == [{"count_result": 2}]
    assert engine.executed == [GOOD_REPLACE_JOIN]
    assert len(prompts) == 2
    assert "旧数据库重试模板" in prompts[1]
    assert BAD_REPLACE_JOIN in prompts[1]
    assert "JOIN_ALIAS_OUT_OF_SCOPE" in prompts[1]
    assert all("JOIN 作用域约束" in prompt for prompt in prompts)
    assert result["_llm_usage"] == {
        "prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28, "generation_ms": 200,
    }
