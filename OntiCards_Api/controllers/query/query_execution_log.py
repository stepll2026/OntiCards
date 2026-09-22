"""Bounded, sanitized query-attempt records; recording never changes query behavior."""
from datetime import datetime, timezone

from core.log_sanitizer import sanitize_log_text


MAX_EXECUTION_EVENTS = 24
MAX_LOG_TEXT = 12000

_PRIVATE_QUERY_FIELDS = frozenset({
    "_connect_info_raw", "connect_info", "connection_string", "connection_url", "database_url", "dsn",
    "api_key", "model_api_key", "model_config_dict", "password", "passwd", "pwd",
    "authorization", "cookie", "token", "access_token", "refresh_token", "secret",
    "prompt", "prompts", "retry_prompt", "retry_templates", "raw_body", "raw_response",
})
_BUSINESS_QUERY_FIELDS = frozenset({
    "rows", "final_rows", "sql", "target_sql", "question", "processed_question",
    "term_rewrite", "term_rewrite_info",
})


def sanitize_execution_attempts(events):
    """Only the new diagnostic records are size-limited, never business replay data."""
    if not isinstance(events, list):
        return []
    clean = []
    for event in events[:MAX_EXECUTION_EVENTS]:
        if not isinstance(event, dict):
            continue
        if event.get("stage") not in {"generation", "validation", "execution", "retry"}:
            continue
        if event.get("status") not in {"success", "error"}:
            continue
        try:
            clean.append({
                "attempt": max(0, int(event.get("attempt") or 0)),
                "stage": event["stage"], "status": event["status"],
                "sql": sanitize_log_text(event.get("sql") or "")[:MAX_LOG_TEXT],
                "error_code": sanitize_log_text(event.get("error_code") or "")[:MAX_LOG_TEXT],
                "message": sanitize_log_text(event.get("message") or "")[:MAX_LOG_TEXT],
                "duration_ms": max(0, int(event.get("duration_ms") or 0)),
                "created_at": sanitize_log_text(event.get("created_at") or "")[:MAX_LOG_TEXT],
            })
        except (ValueError, TypeError):
            continue
    return clean


def sanitize_query_response(value):
    """Preserve existing query replay data; redact only diagnostics/private configuration.

    Query SQL, questions, terms and result rows retain their original authorized
    storage semantics. In particular rows can have >100 columns/rows and long
    values, including business columns whose names resemble configuration keys.
    """
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            name = str(key).lower()
            if name in _PRIVATE_QUERY_FIELDS:
                continue
            if name in _BUSINESS_QUERY_FIELDS:
                clean[key] = item
            elif name in {"execution_attempts", "attempts"}:
                clean[key] = sanitize_execution_attempts(item)
            elif name in {"error", "error_message"} and isinstance(item, str):
                clean[key] = sanitize_log_text(item)
            else:
                clean[key] = sanitize_query_response(item)
        return clean
    if isinstance(value, list):
        return [sanitize_query_response(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_query_response(item) for item in value)
    return value


def append_execution_attempt(events, *, attempt, stage, status, sql="", error_code="",
                             message="", duration_ms=0):
    try:
        if events is None or len(events) >= MAX_EXECUTION_EVENTS:
            return
        if stage not in {"generation", "validation", "execution", "retry"} or status not in {"success", "error"}:
            return
        events.append({
            "attempt": max(0, int(attempt)),
            "stage": stage,
            "status": status,
            "sql": sanitize_log_text(str(sql or ""))[:MAX_LOG_TEXT],
            "error_code": sanitize_log_text(str(error_code or ""))[:MAX_LOG_TEXT],
            "message": sanitize_log_text(str(message or ""))[:MAX_LOG_TEXT],
            "duration_ms": max(0, int(duration_ms or 0)),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        # A logging/redaction failure must not execute, retry, or fail a user query.
        return


def build_logged_cluster_sqls(full_response_result, fallback=None):
    """Use final cluster results as the source of truth for history SQL and attempts."""
    clusters = (full_response_result or {}).get("clusters", [])
    if not isinstance(clusters, list) or not clusters:
        return sanitize_query_response(fallback or [])
    result = []
    for index, cluster in enumerate(clusters):
        if not isinstance(cluster, dict):
            continue
        old = fallback[index] if fallback and index < len(fallback) and isinstance(fallback[index], dict) else {}
        tables = cluster.get("table_names") or [
            table.get("table_name") for table in cluster.get("tables", []) if isinstance(table, dict)
        ]
        events = cluster.get("execution_attempts") or []
        result.append({
            "cluster_index": index,
            "db_type": cluster.get("db_type", ""),
            "datasource_ids": cluster.get("datasource_ids") or old.get("datasource_ids") or [],
            "datasource_names": cluster.get("datasource_names") or old.get("datasource_names") or [],
            "table_names": tables or old.get("table_names") or [],
            "sql": cluster.get("target_sql") or old.get("sql") or "",
            "attempts": events[:MAX_EXECUTION_EVENTS] if isinstance(events, list) else [],
            "retry_count": max(0, int(cluster.get("retry_count") or 0)),
            "fusion_strategy": old.get("fusion_strategy", ""),
        })
    return sanitize_query_response(result)
