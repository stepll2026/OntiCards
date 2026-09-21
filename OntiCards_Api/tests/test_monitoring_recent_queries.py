"""Recent-query JSON contracts using real Flask and SQLite ORM execution.

Only the target production method is loaded; application startup, configuration,
PostgreSQL-only aggregate functions and external services are not initialized.
"""
import ast
import copy
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
import pytest


ROOT = Path(__file__).resolve().parents[1]
OWNER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
WINDOW_START = datetime(2026, 9, 21, 8)


@pytest.fixture
def recent_queries():
    app = Flask(__name__)
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite://")
    database = SQLAlchemy(app)

    class QueryLog(database.Model):
        __tablename__ = "query_logs"
        id = database.Column(database.String, primary_key=True)
        user_id = database.Column(database.String, nullable=False)
        question = database.Column(database.Text)
        status = database.Column(database.String, nullable=False)
        total_tokens = database.Column(database.Integer, nullable=True)
        total_duration_ms = database.Column(database.Integer, nullable=True)
        error_message = database.Column(database.Text)
        source_datasource_names = database.Column(database.JSON)
        created_at = database.Column(database.DateTime, nullable=False)

    path = ROOT / "controllers/monitoring/monitoring_api.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    resource = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                    and node.name == "MonitoringRealtimeResource")
    method = next(node for node in resource.body if isinstance(node, ast.FunctionDef)
                  and node.name == "_get_recent_queries")
    isolated = ast.Module(body=[copy.deepcopy(method)], type_ignores=[])
    namespace = {"QueryLog": QueryLog}
    exec(compile(ast.fix_missing_locations(isolated), str(path), "exec"), namespace)

    @app.get("/recent-queries")
    def recent():
        # Exercise the real method and Flask's JSON encoder, rather than inspecting
        # a hand-built dict or mocking query.filter/order_by/limit behavior.
        return namespace["_get_recent_queries"](None, request.args.get("user_id", OWNER), WINDOW_START)

    with app.app_context():
        database.create_all()

        def add(identifier, status, tokens, *, owner=OWNER, created_at=None):
            database.session.add(QueryLog(
                id=identifier, user_id=owner, status=status, total_tokens=tokens,
                question="fixture " + identifier, total_duration_ms=12,
                error_message="fixture failure" if status in {"error", "timeout"} else None,
                source_datasource_names=["synthetic datasource"],
                created_at=created_at or WINDOW_START + timedelta(minutes=30),
            ))

        yield SimpleNamespace(client=app.test_client(), database=database, record=QueryLog, add=add)
        database.session.remove()
        database.drop_all()


@pytest.mark.parametrize("status", ["success", "error", "timeout"])
@pytest.mark.parametrize("tokens", [1234, 0, None], ids=["nonzero", "zero", "unknown"])
def test_success_error_timeout_preserve_actual_token_value_in_json(recent_queries, status, tokens):
    recent_queries.add("target", status, tokens)
    recent_queries.database.session.commit()

    response = recent_queries.client.get("/recent-queries")

    assert response.status_code == 200
    key = "success_samples" if status == "success" else "error_samples"
    other = "error_samples" if status == "success" else "success_samples"
    assert response.json[other] == []
    samples = response.json[key]
    assert len(samples) == 1 and samples[0]["id"] == "target"
    assert "tokens" in samples[0]
    assert samples[0]["tokens"] == tokens
    if tokens is None:
        assert samples[0]["tokens"] is None  # Unknown usage must not become a fabricated zero.
    else:
        assert type(samples[0]["tokens"]) is int
    assert samples[0]["status" if status == "success" else "error_type"] == status
    assert samples[0]["duration_ms"] == 12


def test_recent_samples_filter_owner_status_and_inclusive_window_boundary(recent_queries):
    for status in ("success", "error", "timeout"):
        recent_queries.add("foreign-" + status, status, 999, owner=OTHER)
        recent_queries.add("old-" + status, status, 888,
                           created_at=WINDOW_START - timedelta(microseconds=1))
    recent_queries.add("success-boundary", "success", 0, created_at=WINDOW_START)
    recent_queries.add("success-recent", "success", 40,
                       created_at=WINDOW_START + timedelta(minutes=20))
    recent_queries.add("error-boundary", "error", None, created_at=WINDOW_START)
    recent_queries.add("timeout-recent", "timeout", 21,
                       created_at=WINDOW_START + timedelta(minutes=10))
    recent_queries.add("pending", "pending", 777)
    recent_queries.database.session.commit()

    response = recent_queries.client.get("/recent-queries")

    assert response.status_code == 200
    assert [row["id"] for row in response.json["success_samples"]] == ["success-recent", "success-boundary"]
    assert [row["id"] for row in response.json["error_samples"]] == ["timeout-recent", "error-boundary"]
    assert [row["tokens"] for row in response.json["error_samples"]] == [21, None]


def test_recent_sample_limits_apply_after_owner_time_filter_and_keep_newest(recent_queries):
    for index in range(8):
        recent_queries.add(f"success-{index}", "success", index,
                           created_at=WINDOW_START + timedelta(minutes=index))
    for index in range(6):
        recent_queries.add(f"failed-{index}", "error" if index % 2 == 0 else "timeout", index,
                           created_at=WINDOW_START + timedelta(minutes=index))
    recent_queries.add("foreign-newest", "error", 999, owner=OTHER,
                       created_at=WINDOW_START + timedelta(minutes=59))
    recent_queries.database.session.commit()

    response = recent_queries.client.get("/recent-queries")

    assert response.status_code == 200
    assert [row["id"] for row in response.json["success_samples"]] == [f"success-{i}" for i in (7, 6, 5, 4, 3)]
    assert [row["id"] for row in response.json["error_samples"]] == [f"failed-{i}" for i in (5, 4, 3)]
    assert [row["tokens"] for row in response.json["error_samples"]] == [5, 4, 3]
