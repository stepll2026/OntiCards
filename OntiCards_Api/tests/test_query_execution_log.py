"""Real query/retry/logger functions, isolated from Flask startup and external I/O."""
import ast
import copy
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test_join_scope_retry import (
    ROOT, TREE, BAD_SQL, GOOD_SQL, TABLES, FakeEngine, FakeDriverError,
    SANITIZER, EXECUTION_LOG, isolated_functions,
)


def _cluster(replies, engine=None):
    namespace = isolated_functions()
    engine = engine or FakeEngine()
    namespace["get_db_engine"] = lambda *args, **kwargs: engine
    namespace["qian_wen_llm_with_usage"] = Mock(side_effect=replies)
    result = namespace["_exec_cluster"]("fixture", "postgresql", "fixture-only", TABLES, "id")
    return result, engine, namespace


def _reply(sql):
    return sql, {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14, "generation_ms": 100}


def test_success_has_generation_validation_execution_even_for_empty_results():
    result, engine, _ = _cluster([_reply(GOOD_SQL)], FakeEngine(rows=[]))
    assert result["rows"] == []
    assert result["retry_count"] == 0
    events = result["execution_attempts"]
    assert [(e["stage"], e["status"]) for e in events] == [
        ("generation", "success"), ("validation", "success"), ("execution", "success")]
    assert all(e["attempt"] == 0 and e["duration_ms"] >= 0 for e in events)
    assert all(datetime.fromisoformat(e["created_at"]).tzinfo is not None for e in events)
    assert events[-1]["sql"] == GOOD_SQL
    assert engine.executed == [GOOD_SQL]


def test_successful_correction_retains_initial_sql_error_and_retry_sql():
    result, engine, _ = _cluster([_reply(BAD_SQL), _reply(GOOD_SQL)])
    events = result["execution_attempts"]
    assert [(e["attempt"], e["stage"], e["status"]) for e in events] == [
        (0, "generation", "success"), (0, "validation", "error"),
        (1, "retry", "success"), (1, "validation", "success"), (1, "execution", "success")]
    assert events[1]["error_code"] == "JOIN_ALIAS_OUT_OF_SCOPE"
    assert events[1]["sql"] == BAD_SQL
    assert events[2]["sql"] == GOOD_SQL
    assert result["retry_count"] == 1
    assert result["_llm_usage"]["total_tokens"] == 28
    assert engine.executed == [GOOD_SQL]


def test_exhausted_retries_record_all_failed_attempts_without_execution():
    result, engine, _ = _cluster([_reply(BAD_SQL)] * 3)
    failed = [e for e in result["execution_attempts"] if e["status"] == "error"]
    assert [e["attempt"] for e in failed] == [0, 1, 2]
    assert all(e["stage"] == "validation" for e in failed)
    assert result["retry_count"] == 2
    assert result["_llm_usage"]["total_tokens"] == 42
    assert engine.executed == []


def test_driver_error_is_distinct_from_validation_failure():
    engine = FakeEngine(errors=[FakeDriverError("permission denied for table project", "42501")])
    result, _, _ = _cluster([_reply(GOOD_SQL)], engine)
    assert [(e["stage"], e["status"]) for e in result["execution_attempts"]] == [
        ("generation", "success"), ("validation", "success"), ("execution", "error")]
    assert result["execution_attempts"][-1]["error_code"] == "SQL_EXECUTION_ERROR"


@pytest.mark.parametrize("initial", [True, False])
def test_model_http_failure_retains_diagnostic_without_raw_body(initial):
    failed_reply = ("private upstream body", {"total_tokens": 0, "model_error": {
        "code": "MODEL_HTTP_ERROR", "message": "模型服务返回 HTTP 错误", "http_status": 503}})
    replies = [failed_reply] if initial else [_reply(BAD_SQL), failed_reply]
    result, engine, _ = _cluster(replies)
    event = result["execution_attempts"][-1]
    assert event["stage"] == ("generation" if initial else "retry")
    assert event["error_code"] == "MODEL_HTTP_ERROR"
    assert "503" in event["message"]
    assert "private upstream body" not in str(result)
    assert engine.executed == []


def test_initial_model_exception_is_logged_without_credentials():
    result, _, _ = _cluster([RuntimeError("https://user:private-password@example.test/")])
    assert result["execution_attempts"][0]["error_code"] == "MODEL_GENERATION_ERROR"
    assert "RuntimeError" in result["execution_attempts"][0]["message"]
    assert "private-password" not in str(result)


@pytest.mark.parametrize("output, expected_code", [
    ("Cannot generate SQL", "MODEL_SQL_MISSING"),
    ("SELECT 1", "SQL_FROM_MISSING"),
    (GOOD_SQL.replace('"app-data"."budget"', '"app-data"."forbidden"'), "SQL_TABLE_NOT_ALLOWED"),
])
def test_preexecution_failures_have_a_terminal_event(output, expected_code):
    result, engine, _ = _cluster([_reply(output)])
    assert result["execution_attempts"][-1]["error_code"] == expected_code
    assert result["execution_attempts"][-1]["status"] == "error"
    assert result["retry_count"] == 0
    assert engine.connect_calls == 0


def test_events_are_bounded_redacted_and_separate_between_requests():
    events = []
    for _ in range(40):
        EXECUTION_LOG.append_execution_attempt(events, attempt=0, stage="execution", status="error",
            sql="SELECT 'postgresql://user:private-password@example.test/db'", message="x" * 13000)
    assert len(events) == 24
    assert "private-password" not in str(events)
    assert all(len(e["message"]) <= 12000 for e in events)
    first, _, _ = _cluster([_reply(GOOD_SQL)])
    second, _, _ = _cluster([_reply(BAD_SQL)] * 3)
    assert first["execution_attempts"] is not second["execution_attempts"]
    assert len(first["execution_attempts"]) == 3


def test_redaction_failure_does_not_change_query_result(monkeypatch):
    monkeypatch.setattr(EXECUTION_LOG, "sanitize_log_text", Mock(side_effect=RuntimeError("redactor unavailable")))
    result, engine, _ = _cluster([_reply(GOOD_SQL)])
    assert "error" not in result
    assert result["rows"] == [{"count_result": 2}]
    assert engine.executed == [GOOD_SQL]


def _logger_namespace():
    namespace = isolated_functions()
    namespace["db"] = SimpleNamespace(session=SimpleNamespace(add=Mock(), commit=Mock(), rollback=Mock()))
    namespace["QueryLog"] = lambda **kwargs: SimpleNamespace(**kwargs)
    logger_path = ROOT / "controllers/query_history/query_logger.py"
    logger_tree = ast.parse(logger_path.read_text(encoding="utf-8"))
    logger_class = next(node for node in logger_tree.body if isinstance(node, ast.ClassDef) and node.name == "QueryLogger")
    log_query = next(node for node in TREE.body if isinstance(node, ast.FunctionDef) and node.name == "_log_query")
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        copy.deepcopy(logger_class), copy.deepcopy(log_query),
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(logger_path), "exec"), namespace)
    namespace["QueryLogger"]._increment_daily_stats = Mock()
    return namespace


def _log_args(cluster, success):
    return dict(
        user_id="fixture-user", question="fixture question", sql=cluster["target_sql"],
        source_datasource_ids=[], source_datasource_names=[], datasource_ids=[], datasource_names=[],
        table_names=["project"], metrics={"total_duration_ms": 1000, "llm_gen_sql_ms": 900, "vector_search_ms": 800},
        tokens={"total_tokens": 42, "llm_prompt_tokens": 30, "llm_completion_tokens": 12}, quality={},
        result_count=len(cluster["rows"]), merge_strategy="OR", success=success,
        error_message="query failed" if not success else None,
        full_response_result={"clusters": [cluster], "final_rows": cluster["rows"]},
        cluster_sqls=[{"sql": cluster["target_sql"], "fusion_strategy": "OR"}],
    )


@pytest.mark.parametrize("success", [True, False])
def test_success_and_failure_persist_sql_attempts_tokens_and_wall_clock(success):
    cluster, _, _ = _cluster([_reply(GOOD_SQL)] if success else [_reply(BAD_SQL)] * 3)
    namespace = _logger_namespace()
    namespace["_log_query"](**_log_args(cluster, success))
    record = namespace["db"].session.add.call_args.args[0]
    assert record.status == ("success" if success else "error")
    assert record.total_duration_ms == 1000
    assert record.total_tokens == 42
    assert record.sql == cluster["target_sql"]
    assert record.full_response_result["clusters"][0]["execution_attempts"] == cluster["execution_attempts"]
    summary = record.cluster_sqls[0]
    assert summary["db_type"] == "postgresql"
    assert summary["table_names"]
    assert summary["attempts"] == cluster["execution_attempts"]
    assert summary["retry_count"] == cluster["retry_count"]
    assert namespace["QueryLogger"]._increment_daily_stats.call_args.kwargs["tokens"]["total_tokens"] == 42
    namespace["db"].session.commit.assert_called_once()


def test_persistence_failure_rolls_back_without_raising():
    cluster, _, _ = _cluster([_reply(GOOD_SQL)])
    namespace = _logger_namespace()
    namespace["db"].session.commit.side_effect = RuntimeError("database unavailable")
    assert namespace["_log_query"](**_log_args(cluster, True)) is None
    namespace["db"].session.rollback.assert_called_once()


def test_existing_log_error_callers_remain_compatible_and_sensitive_json_is_redacted():
    namespace = _logger_namespace()
    record = namespace["QueryLogger"].log_error("fixture", "question", "password=private-password")
    assert record.total_tokens == 0
    assert record.cluster_sqls is None
    assert "private-password" not in record.error_message
    summary = EXECUTION_LOG.build_logged_cluster_sqls({"clusters": [{
        "db_type": "postgresql", "target_sql": "SELECT 1",
        "_connect_info_raw": "private-password", "execution_attempts": [{
            "attempt": 0, "stage": "execution", "status": "error",
            "message": "postgresql://user:private-password@example.test/db",
        }],
    }]})
    assert "private-password" not in str(summary)
    assert "_connect_info_raw" not in summary[0]


@pytest.mark.parametrize("success", [True, False])
def test_replay_rows_columns_long_values_questions_sql_and_terms_are_not_truncated(success):
    cluster, _, _ = _cluster([_reply(GOOD_SQL)] if success else [_reply(BAD_SQL)] * 3)
    long_value = "business-value-" + "x" * 15000
    long_sql = "SELECT '" + long_value + "' AS value FROM project"
    rows = [{f"column_{column}": column for column in range(105)} for _ in range(105)]
    rows[0]["column_0"] = long_value
    # These are authorized result column values, not connection configuration.
    rows[0]["password"] = "business-column-value"
    rows[0]["attempts"] = ["business-value"] * 105
    terms = {"matched_terms": [{"term_name": f"term_{i}", "definition": long_value} for i in range(105)]}
    cluster.update(rows=rows, target_sql=long_sql, _connect_info_raw="private-config",
                   model_config_dict={"api_key": "private-config"})
    namespace = _logger_namespace()
    args = _log_args(cluster, success)
    args.update(question=long_value, sql=long_sql, processed_question=long_value,
                term_rewrite_info=terms)
    args["full_response_result"].update(term_rewrite=terms, metadata={f"key_{i}": i for i in range(105)})

    namespace["_log_query"](**args)

    record = namespace["db"].session.add.call_args.args[0]
    saved = record.full_response_result
    assert len(saved["final_rows"]) == 105
    assert len(saved["final_rows"][0]) == 107
    assert saved["final_rows"] == rows
    assert saved["clusters"][0]["rows"] == rows
    assert len(saved["metadata"]) == 105
    assert saved["term_rewrite"] == terms
    assert record.term_rewrite_info == terms
    assert record.question == record.processed_question == long_value
    assert record.sql == record.cluster_sqls[0]["sql"] == long_sql
    assert saved["clusters"][0]["target_sql"] == long_sql
    assert "_connect_info_raw" not in saved["clusters"][0]
    assert "model_config_dict" not in saved["clusters"][0]
    # Sanitization must not mutate the original response object.
    assert cluster["_connect_info_raw"] == "private-config"


def test_only_diagnostic_attempts_are_bounded_while_fallback_sql_replay_is_complete():
    long_sql = "SELECT '" + "x" * 15000 + "' AS value FROM project"
    event = {"attempt": 0, "stage": "execution", "status": "error", "sql": long_sql,
             "message": "password=private-password " + "x" * 15000,
             "created_at": "2026-09-21T00:00:00+00:00", "prompt": "private-prompt"}
    fallback = [{"sql": long_sql, "attempts": [event] * 30, "_connect_info_raw": "private-config"}
                for _ in range(105)]

    result = EXECUTION_LOG.build_logged_cluster_sqls({"clusters": []}, fallback)

    assert len(result) == 105
    assert all(item["sql"] == long_sql for item in result)
    assert all(len(item["attempts"]) == 24 for item in result)
    assert all(len(e["sql"]) == 12000 and len(e["message"]) <= 12000 for e in result[0]["attempts"])
    assert "private-password" not in str(result[0]["attempts"])
    assert "private-prompt" not in str(result[0]["attempts"])
    assert "_connect_info_raw" not in result[0]
