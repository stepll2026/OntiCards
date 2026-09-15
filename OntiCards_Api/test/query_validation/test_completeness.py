import copy
import json

import pytest
from sqlalchemy import create_engine, text

from controllers.query.query_validation import (
    QueryValidationError, parse_query, unicode_sql, check_review, plan_query,
    ensure_valid_sql, finalize_query_payload, validate_result_rows, response_status, check_display_sql,
)
from controllers.query.query_retrieval import recall_requirements, expand_dependencies


def contract():
    return {"original_question": "查询测试成员甲参与的设立完成项目，仅输出项目名称",
            "expanded_question": "投资团队成员通过 team.person_id 关联人员表",
            "requirements": [
                {"id": "person", "kind": "filter", "source": "测试成员甲", "text": "人员姓名为测试成员甲"},
                {"id": "stage", "kind": "filter", "source": "设立完成", "text": "阶段为设立完成"},
                {"id": "name", "kind": "output", "source": "项目名称", "text": "输出项目名称"}],
            "output_labels": ["项目名称"], "exact_output": True, "ambiguities": [], "cluster_count": 1}


SQL = "SELECT p.name AS 项目名称 FROM projects p JOIN team t ON p.id=t.project_id JOIN people u ON u.id=t.person_id WHERE u.name='测试成员甲' AND p.stage='cxt_slwc'"


def review():
    return {"complete": True, "issues": [], "checks": [
        {"id": "person", "status": "satisfied", "evidence": "u.name='测试成员甲'"},
        {"id": "stage", "status": "satisfied", "evidence": "p.stage='cxt_slwc'"},
        {"id": "name", "status": "satisfied", "evidence": "p.name AS 项目名称"}]}


@pytest.mark.parametrize("dialect", ["mysql", "postgresql", "mssql", "oracle", "sqlite", "trino", "kingbase", "oceanbase", "dm"])
def test_complete_multitable_query_all_dialects(dialect):
    sql = unicode_sql(SQL, dialect)
    check_review(review(), contract(), parse_query(sql, dialect), dialect)


@pytest.mark.parametrize("sql", [
    SQL.replace("u.name='测试成员甲' AND ", ""),
    SQL.replace("u.name='测试成员甲'", "u.name='另一人'"),
    SQL.replace("u.name='测试成员甲' AND p.stage='cxt_slwc'", "u.name='测试成员甲' OR p.stage='cxt_slwc'"),
    SQL.replace("WHERE u.name='测试成员甲' AND p.stage='cxt_slwc'", "WHERE p.stage='cxt_slwc' /* u.name='测试成员甲' */"),
    SQL.replace("p.name AS 项目名称", "NULL AS 项目名称"),
    SQL.replace("p.name AS 项目名称", "p.name AS 项目名称, u.name AS 成员姓名"),
])
def test_model_pass_cannot_override_missing_sql_evidence(sql):
    with pytest.raises(QueryValidationError):
        check_review(review(), contract(), parse_query(sql, "sqlite"), "sqlite")


@pytest.mark.parametrize("sql", [
    "SELECT p.name AS 项目名称 FROM projects p LEFT JOIN people u ON u.name='测试成员甲' WHERE p.stage='cxt_slwc'",
    "WITH unused AS (SELECT u.name FROM people u WHERE u.name='测试成员甲') SELECT p.name AS 项目名称 FROM projects p WHERE p.stage='cxt_slwc'",
    SQL + " UNION ALL SELECT p.name AS 项目名称 FROM projects p WHERE p.stage='cxt_slwc'",
])
def test_nonrestricting_or_unused_conditions_do_not_count(sql):
    with pytest.raises(QueryValidationError):
        check_review(review(), contract(), parse_query(sql, "sqlite"), "sqlite")


def test_missing_review_items_fail_closed():
    result = review()
    result["checks"].pop()
    with pytest.raises(QueryValidationError, match="遗漏"):
        check_review(result, contract(), parse_query(SQL, "sqlite"), "sqlite")


@pytest.mark.parametrize('evidence', ['FROM projects p', 'JOIN team t ON p.id=t.project_id',
    'FROM projects p INNER JOIN team t ON p.id=t.project_id JOIN people u ON u.id=t.person_id'])
def test_scope_evidence_supports_from_and_join_fragments(evidence):
    plan = contract()
    plan['requirements'].append({'id': 'scope', 'kind': 'scope', 'text': '查询项目', 'source': '项目'})
    audit = review()
    audit['checks'].append({'id': 'scope', 'status': 'satisfied', 'evidence': evidence})
    check_review(audit, plan, parse_query(SQL, 'sqlite'), 'sqlite')


def test_scope_fragment_must_match_every_join():
    plan = contract()
    plan['requirements'].append({'id': 'scope', 'kind': 'scope', 'text': '查询项目', 'source': '项目'})
    audit = review()
    audit['checks'].append({'id': 'scope', 'status': 'satisfied', 'evidence': 'FROM projects p LEFT JOIN team t ON p.id=t.project_id'})
    with pytest.raises(QueryValidationError):
        check_review(audit, plan, parse_query(SQL, 'sqlite'), 'sqlite')


@pytest.mark.parametrize('join_kind', ['', 'INNER ', 'LEFT '])
def test_existing_child_filter_can_be_evidenced_by_required_join(join_kind):
    plan = contract()
    plan['requirements'].append({'id': 'exists', 'kind': 'filter', 'text': '有团队记录', 'source': '参与'})
    audit = review()
    audit['checks'].append({'id': 'exists', 'status': 'satisfied', 'evidence': 'INNER JOIN team t ON p.id=t.project_id'})
    tree = parse_query(SQL.replace('JOIN team', join_kind + 'JOIN team'), 'sqlite')
    if join_kind == 'LEFT ':
        with pytest.raises(QueryValidationError):
            check_review(audit, plan, tree, 'sqlite')
    else:
        check_review(audit, plan, tree, 'sqlite')


@pytest.mark.parametrize('include_missing_column', [False, True])
def test_display_evidence_may_quote_multiple_exact_projections(include_missing_column):
    plan = contract()
    plan['exact_output'] = False
    plan['requirements'].append({'id': 'display', 'kind': 'output', 'text': '显示中文名称', 'source': '名称'})
    audit = review()
    audit['checks'].append({'id': 'display', 'status': 'satisfied', 'evidence': 'p.name AS 项目名称, u.name AS 人员姓名'})
    sql = SQL if include_missing_column else SQL.replace('p.name AS 项目名称', 'p.name AS 项目名称, u.name AS 人员姓名')
    if include_missing_column:
        with pytest.raises(QueryValidationError):
            check_review(audit, plan, parse_query(sql, 'sqlite'), 'sqlite')
    else:
        check_review(audit, plan, parse_query(sql, 'sqlite'), 'sqlite')


def test_later_full_join_does_not_make_inner_on_a_required_filter():
    plan = contract()
    plan['requirements'] = [plan['requirements'][0]]
    plan['exact_output'] = False
    audit = review()
    audit['checks'] = [audit['checks'][0]]
    sql = "SELECT p.name AS 项目名称 FROM projects p JOIN people u ON u.name='测试成员甲' FULL JOIN team t ON t.project_id=p.id"
    with pytest.raises(QueryValidationError):
        check_review(audit, plan, parse_query(sql, 'postgresql'), 'postgresql')


@pytest.mark.parametrize('sql', ['SELECT FROM', 'SELECT x FROM', 'SELECT x FROM t; SELECT x FROM t', 'SELECT x INTO other FROM t'])
def test_invalid_or_mutating_sql_is_rejected(sql):
    with pytest.raises(QueryValidationError):
        parse_query(sql, 'sqlite')


def test_tsql_unicode_does_not_change_comments_identifiers_or_escapes():
    sql = "SELECT '设立完成', N'人民币', 'O''中文', [中文'列] FROM t -- '注释'"
    fixed = unicode_sql(sql, "mssql")
    assert fixed == "SELECT N'设立完成', N'人民币', N'O''中文', [中文'列] FROM t -- '注释'"
    assert unicode_sql(fixed, "mssql") == fixed
    assert unicode_sql(sql, "postgresql") == sql


def test_plan_is_anchored_in_original_and_does_not_accept_rewrite_loss():
    plan = contract()
    observed = []
    def llm(prompt, **kwargs):
        observed.append(prompt)
        return json.dumps(plan, ensure_ascii=False), {}
    value = plan_query(plan["original_question"], "丢失姓名的展开", llm)
    assert "测试成员甲" in observed[0]
    assert value["original_question"] == plan["original_question"]
    plan["requirements"][0]["source"] = "伪造内容"
    with pytest.raises(QueryValidationError):
        plan_query(value["original_question"], "", llm)


def test_ambiguity_requires_clarification():
    plan = contract()
    plan["ambiguities"] = ["统计全部项目还是仅有团队记录的项目？"]
    with pytest.raises(QueryValidationError) as error:
        plan_query(plan["original_question"], "", lambda *a, **k: (json.dumps(plan), {}))
    assert error.value.report["status"] == "needs_clarification"


def test_repair_runs_once_and_rechecks_exact_repaired_sql():
    answers = iter([json.dumps({"complete": False, "issues": ["缺少姓名条件"]}),
                    json.dumps({"sql": SQL}), json.dumps(review())])
    seen = []
    def llm(prompt, **kwargs):
        seen.append(prompt)
        return next(answers), {"total_tokens": 1}
    sql, report, usage = ensure_valid_sql(SQL.replace("u.name='测试成员甲' AND ", ""), "sqlite",
                                          [{"_query_contract": contract()}], llm, "生成 SQL")
    assert sql == SQL and report["repairs"] == 1 and usage["total_tokens"] == 3
    assert "测试成员甲" in seen[-1]


def test_invalid_review_does_not_execute_or_retry_as_success():
    with pytest.raises(QueryValidationError) as exc:
        ensure_valid_sql(SQL, "sqlite", [{"_query_contract": contract()}], lambda *a, **k: ('', {}), "")
    assert exc.value.report["status"] == "unverified"


def test_retrieval_preserves_union_and_passes_same_scope_to_each_search():
    calls = []
    def retrieve(question, **kwargs):
        calls.append(kwargs)
        key = str(len(calls))
        return {"doc_ids": [key], "data_card_results": [{"SQLMeta": {"table": key}}], "usage": {"embedding_tokens": 3}}
    result = recall_requirements(contract(), retrieve, datasource_id=["owned"], class_name="user_space")
    assert len(result["doc_ids"]) == len(calls) == 5
    assert all(c == calls[0] for c in calls)
    assert result["usage"]["embedding_tokens"] == 15


def test_dependency_closure_preserves_main_table_and_terminates_cycles():
    def card(name, ref):
        return {"SQLMeta": {"table": name, "foreign_keys": [{"ref_table": ref}]}}
    cards = {"team": card("team", "people"), "people": card("people", "projects"), "projects": card("projects", "team")}
    result = {"doc_ids": ["team"], "data_card_results": [cards["team"]]}
    expand_dependencies(result, lambda source, refs: [(name, cards[name]) for name in refs])
    assert set(result["doc_ids"]) == set(cards)


def payload(rows=None):
    return {"query_contract": contract(), "final_rows": rows if rows is not None else [{"项目名称": "测试项目"}],
            "clusters": [{"target_sql": SQL, "rows": rows or [], "columns": ["项目名称"],
                          "validation": {"status": "verified", "columns": ["项目名称"], "checks": review()["checks"]}}]}


def test_empty_result_is_valid_and_metadata_is_preserved():
    result = payload([])
    finalize_query_payload(result, None)
    assert response_status(result, 200, "ok") == (200, "ok")
    assert result["validation"]["columns"] == ["项目名称"]


def test_partial_cluster_cannot_be_promoted_to_a_verified_final_result():
    result = payload()
    result['clusters'][0]['validation']['status'] = 'partial'
    finalize_query_payload(result, None)
    assert response_status(result, 200, 'ok')[0] == 422
    assert result['final_rows'] == []


@pytest.mark.parametrize("failure", ["error", "truncated", "missing_column", "binary", "unverified", "fusion"])
def test_failed_results_cannot_appear_successful(failure):
    result = payload()
    if failure == "error": result["clusters"][0]["error"] = "数据库连接失败"
    if failure == "truncated": result["clusters"][0]["warnings"] = ["结果已截断"]
    if failure == "missing_column": result["final_rows"] = [{"其他列": 123}]
    if failure == "binary": result["final_rows"] = [{"项目名称": b'\xff'}]
    if failure == "unverified": result["clusters"][0].pop("validation")
    if failure == "fusion": result["clusters"].append(copy.deepcopy(result["clusters"][0]))
    finalize_query_payload(result, None)
    assert response_status(result, 200, "ok")[0] == 422
    assert result["final_rows"] == []
    assert all(c["rows"] == [] for c in result["clusters"])


def test_runner_preserves_zero_null_rows_and_empty_metadata(endpoint):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE samples(value INTEGER, label TEXT)"))
        connection.execute(text("INSERT INTO samples VALUES (0, NULL), (1, '测试')"))
    columns = []
    rows, warnings, _ = endpoint["run_sql_safe_new"](engine, "SELECT value AS 数值, label AS 名称 FROM samples", [{"table_name": "samples", "columns": [{"name": "value"}, {"name": "label"}]}], "sqlite", columns_out=columns)
    assert rows == [{"数值": 0, "名称": None}, {"数值": 1, "名称": "测试"}]
    assert columns == ["数值", "名称"]
    rows, _, _ = endpoint["run_sql_safe_new"](engine, "SELECT value AS 数值 FROM samples WHERE value=9", [{"table_name": "samples", "columns": [{"name": "value"}]}], "sqlite", columns_out=columns)
    assert rows == [] and columns == ["数值"]


@pytest.mark.parametrize("sql", ["SELECT value AS 重名, label AS 重名 FROM samples", "SELECT raw AS 币种 FROM samples"])
def test_runner_rejects_duplicate_headers_and_binary_ids(endpoint, sql):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE samples(value INTEGER, label TEXT, raw BLOB)"))
        connection.execute(text("INSERT INTO samples VALUES (0, 'test', x'ff')"))
    with pytest.raises(QueryValidationError):
        endpoint["run_sql_safe_new"](engine, sql, [{"table_name": "samples", "columns": [{"name": name} for name in ("value", "label", "raw")]}], "sqlite")


def test_runner_reports_actual_truncation(endpoint):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE samples(value INTEGER)"))
        connection.execute(text("INSERT INTO samples VALUES (1), (2), (3)"))
    rows, warnings, _ = endpoint["run_sql_safe_new"](engine, "SELECT value FROM samples", [{"table_name": "samples", "columns": [{"name": "value"}]}], "sqlite", max_rows=2)
    assert len(rows) == 2 and any("已截断" in message for message in warnings)


def test_enum_codes_require_mapping_and_explicit_raw_request_is_respected():
    tables = [{"table_name": "team", "columns": [{"name": "role", "comment": "角色 a_:A角； b_:B角"}]}]
    tree = parse_query("SELECT t.role AS 角色 FROM team t", "sqlite")
    with pytest.raises(QueryValidationError, match="枚举编码"):
        check_display_sql(tree, tables, "输出角色")
    check_display_sql(tree, tables, "输出角色原始编码")
    check_display_sql(parse_query("SELECT CASE t.role WHEN 'a_' THEN 'A角' WHEN 'b_' THEN 'B角' ELSE t.role END AS 角色 FROM team t", "sqlite"), tables, "输出角色")


def test_chinese_headers_and_explicit_english_alias():
    tree = parse_query("SELECT name AS project_name FROM projects", "sqlite")
    with pytest.raises(QueryValidationError, match="中文名称"):
        check_display_sql(tree, [], "查询项目名称")
    check_display_sql(tree, [], "查询项目名称，列名为 project_name")


def test_real_cluster_repairs_missing_condition_before_running_sql(endpoint):
    from conftest import load_functions
    filename = endpoint["run_sql_safe_new"].__code__.co_filename.rsplit('\\', 1)[-1].rsplit('/', 1)[-1]
    load_functions(filename, ["_exec_cluster", "build_cluster_tables", "_extract_sql_from_llm_text", "_remove_sql_comments"], endpoint)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE projects(id INTEGER, name TEXT, stage TEXT)"))
        connection.execute(text("CREATE TABLE people(id INTEGER, name TEXT)"))
        connection.execute(text("CREATE TABLE team(project_id INTEGER, person_id INTEGER)"))
        connection.execute(text("INSERT INTO projects VALUES (1,'命中项目','cxt_slwc'), (2,'错误扩大范围','cxt_slwc')"))
        connection.execute(text("INSERT INTO people VALUES (1,'测试成员甲'), (2,'其他人')"))
        connection.execute(text("INSERT INTO team VALUES (1,1), (2,2)"))
    responses = iter([SQL.replace("u.name='测试成员甲' AND ", ""),
                      json.dumps({"complete": False, "issues": ["遗漏姓名条件"]}),
                      json.dumps({"sql": SQL}), json.dumps(review())])
    endpoint.update(get_db_engine=lambda *a, **k: engine,
                    load_prompt=lambda *a: "用户问题：{{user_question}}",
                    render_prompt=lambda template, **k: template.replace('{{user_question}}', k['user_question']),
                    _pick_template_by_db=lambda *a: "sqlite_multi_table.txt",
                    make_tables_block=lambda *a: "schema", make_rels_block=lambda *a: "relations",
                    qian_wen_llm_with_usage=lambda *a, **k: (next(responses), {}),
                    _collect_entity_ids=lambda *a: set())
    tables = [{"table_name": name, "columns": [{"name": column, "type": "TEXT"} for column in columns],
               "_query_contract": contract()} for name, columns in [
                   ("projects", ["id", "name", "stage"]), ("people", ["id", "name"]),
                   ("team", ["project_id", "person_id"])]]
    result = endpoint["_exec_cluster"](contract()["original_question"], "sqlite", "", tables, "id")
    assert result.get("error") is None, result
    assert result["rows"] == [{"项目名称": "命中项目"}]
    assert result["validation"]["status"] == "verified"


def test_error_logging_and_wall_clock_time_match_response(endpoint):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from conftest import load_functions
    filename = endpoint["run_sql_safe_new"].__code__.co_filename.rsplit('\\', 1)[-1].rsplit('/', 1)[-1]
    name = '_log_query_plugin' if 'plugin' in filename else '_log_query'
    load_functions(filename, [name, 'format_response'], endpoint)
    logger = SimpleNamespace(log_success=Mock(), log_error=Mock())
    endpoint.update(QueryLogger=logger, db=SimpleNamespace(session=Mock()),
                    qian_wen_llm_with_usage=None, _base_format_response=lambda data, code, msg: (dict(data=data, code=code, msg=msg), code))
    data = payload()
    data['clusters'][0]['error'] = 'execution failed'
    metrics = {"total_duration_ms": 9500, "vector_search_ms": 100, "rerank_ms": 20}
    endpoint[name](user_id='owner', question='question', sql=SQL, source_datasource_ids=[],
                   source_datasource_names=[], datasource_ids=[], datasource_names=[], table_names=[],
                   metrics=metrics, tokens={}, quality={}, result_count=1, merge_strategy='SINGLE_CLUSTER',
                   success=True, full_response_result=data)
    logger.log_success.assert_not_called()
    assert logger.log_error.call_args.kwargs['total_duration_ms'] == 9500
    assert endpoint['format_response'](data, 200, 'success')[1] == 422
