"""Real Flask requests and temporary structured log files; no application startup."""
import importlib.util
import json
import logging
from pathlib import Path
import subprocess
import sys
import time
from types import ModuleType
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

from flask import Flask
from flask_login import LoginManager, UserMixin
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import real source modules without core/controller package bootstrap side effects.
# Restore sys.modules immediately so this test cannot affect other test modules.
core_package = ModuleType("core")
core_package.__path__ = [str(ROOT / "core")]
with patch.dict(sys.modules, {"core": core_package}):
    for name, relative in (("core.log_sanitizer", "core/log_sanitizer.py"),
                           ("core.system_logs", "core/system_logs.py"),
                           ("isolated_system_log_api", "controllers/log_center/system_log_api.py")):
        spec = importlib.util.spec_from_file_location(name, ROOT / relative)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    logs = sys.modules["core.system_logs"]
    API = sys.modules["isolated_system_log_api"]


class User(UserMixin):
    def __init__(self, role):
        self.id = role
        self.role = role


@pytest.fixture
def app(tmp_path):
    app = Flask("system_log_test_" + tmp_path.name)
    app.config.update(TESTING=True, SECRET_KEY="test-session-key", SYSTEM_LOG_DIR=str(tmp_path))
    login = LoginManager(app)

    @login.request_loader
    def user(request):
        role = request.headers.get("X-Test-Role")
        return User(role) if role else None

    app.register_blueprint(API.log_center_api, url_prefix="/console/api/log_center")
    logs.init_app(app)

    @app.post("/work/<item>")
    def work(item):
        app.logger.info("legacy body: private-response-content")
        return {"ok": True, "private_response": "not-collected"}

    @app.get("/warn")
    def warn():
        app.logger.warning("upstream rejected api_key=private-key")
        return {"ok": True}

    @app.get("/failure")
    def failure():
        error = ValueError("password=private-password unavailable")
        logs.note_request_exception(error)
        try:
            raise error
        except ValueError:
            app.logger.exception("diagnostic error")
        return {"error": "failed"}, 500

    @app.get("/explode")
    def explode():
        raise RuntimeError("token=secret-exception-token")

    yield app
    handler = app.extensions[logs.EXTENSION_KEY + "_handler"]
    app.logger.removeHandler(handler)
    logging.getLogger().removeHandler(handler)
    handler.close()


def fetch(app, query="", role="admin"):
    headers = {"X-Test-Role": role} if role else {}
    return app.test_client().get("/console/api/log_center/system" + query, headers=headers)


def store(app):
    return app.extensions[logs.EXTENSION_KEY]


def test_authenticated_admin_only_and_polling_produces_no_events(app):
    assert fetch(app, role=None).status_code == 401
    assert fetch(app, role="normal").status_code == 403
    response = fetch(app)
    assert response.status_code == 200
    assert response.json["data"] == {"items": [], "total": 0, "page": 1,
                                     "page_size": 20, "total_pages": 0, "truncated": False}
    assert store(app).read() == ([], False)


@pytest.mark.parametrize("query", [
    "?page=0", "?page=-1", "?page=abc", "?page_size=0", "?page_size=101", "?level=DEBUG",
    "?start_date=not-a-date", "?start_date=2026-09-22&end_date=2026-09-20",
    "?path=/etc/passwd", "?filename=flask.log", "?page=1&page=2", "?keyword=" + "x" * 201,
])
def test_api_rejects_invalid_or_file_path_parameters(app, query):
    assert fetch(app, query).status_code == 400


def test_request_event_contains_only_metadata(app):
    response = app.test_client().post("/work/private-path-secret?token=private-query-secret",
        json={"password": "private-body-secret"}, headers={"Authorization": "private-header-secret"})
    assert response.status_code == 200
    records, truncated = store(app).read()
    assert not truncated and len(records) == 1
    record = records[0]
    assert set(record) == set(logs.FIELDS)
    assert record["event"] == "request_completed"
    assert record["path"] == "/work/<item>"
    assert record["method"] == "POST" and record["status_code"] == 200
    assert record["level"] == "INFO" and record["duration_ms"] >= 0
    assert len(record["request_id"]) == 32
    raw = store(app)._path().read_text(encoding="utf-8")
    for secret in ("private-path-secret", "private-query-secret", "private-body-secret",
                   "private-header-secret", "not-collected", "private-response-content"):
        assert secret not in raw


def test_warning_exception_events_are_redacted_without_duplicate_propagation(app):
    app.test_client().get("/warn")
    app.test_client().get("/failure")
    records, _ = store(app).read()
    python_events = [record for record in records if record["event"] == "python_log"]
    assert len(python_events) == 2
    assert {event["level"] for event in python_events} == {"WARNING", "ERROR"}
    assert "ValueError" in next(event["message"] for event in python_events if event["level"] == "ERROR")
    failed = next(record for record in records if record["event"] == "request_completed" and record["status_code"] == 500)
    assert failed["level"] == "ERROR" and "ValueError" in failed["message"]
    assert "[REDACTED]" in json.dumps(records)
    assert "private-key" not in json.dumps(records)
    assert "private-password" not in json.dumps(records)
    assert "Traceback" not in json.dumps(records)


def test_unhandled_request_exception_is_recorded_during_teardown(app):
    with pytest.raises(RuntimeError):
        app.test_client().get("/explode")
    records, _ = store(app).read()
    events = [event for event in records if event["event"] == "request_completed"]
    assert len(events) == 1
    assert events[0]["status_code"] == 500
    assert "RuntimeError" in events[0]["message"]
    assert "secret-exception-token" not in json.dumps(records)


def test_root_logger_background_events_are_collected(app):
    logging.getLogger("test.background.worker").warning("background worker unhealthy")
    records, _ = store(app).read()
    assert len(records) == 1
    assert records[0]["request_id"] is None
    assert records[0]["message"] == "background worker unhealthy"


def test_level_keyword_local_date_and_pagination(app):
    for index in range(5):
        assert store(app).append(level="ERROR" if index % 2 == 0 else "INFO",
                                 event="fixture", message=f"Synthetic issue {index}")
    today = datetime.now(API.LOCAL_TIMEZONE).date().isoformat()
    response = fetch(app, f"?level=ERROR&keyword=SYNTHETIC&start_date={today}&end_date={today}&page_size=2")
    assert response.status_code == 200
    data = response.json["data"]
    assert data["total"] == 3 and data["total_pages"] == 2 and len(data["items"]) == 2
    second = fetch(app, f"?level=ERROR&page=2&page_size=2").json["data"]
    assert len(second["items"]) == 1
    assert {item["id"] for item in data["items"]}.isdisjoint({item["id"] for item in second["items"]})
    yesterday = (datetime.now(API.LOCAL_TIMEZONE).date() - timedelta(days=1)).isoformat()
    assert fetch(app, f"?end_date={yesterday}").json["data"]["total"] == 0
    assert fetch(app, "?start_date=2020-01-01T00:00:00%2B08:00").json["data"]["total"] == 5


def test_calendar_date_uses_china_midnight_boundaries(app):
    timestamps = [
        ("before", "2026-09-20T15:59:59.999+00:00"),
        ("start", "2026-09-20T16:00:00.000+00:00"),
        ("end", "2026-09-21T15:59:59.999+00:00"),
        ("after", "2026-09-21T16:00:00.000+00:00"),
    ]
    lines = [json.dumps({"id": label, "created_at": timestamp, "level": "INFO",
                         "event": "fixture", "message": label})
             for label, timestamp in timestamps]
    store(app)._path().write_text("\n".join(lines) + "\n", encoding="utf-8")
    response = fetch(app, "?start_date=2026-09-21&end_date=2026-09-21")
    assert response.status_code == 200
    assert {record["message"] for record in response.json["data"]["items"]} == {"start", "end"}
    assert response.json["data"]["total"] == 2


def test_retention_rotation_has_file_and_size_bounds(tmp_path):
    events = logs.SystemLogStore(tmp_path, max_bytes=4096, backups=2)
    for index in range(70):
        assert events.append(level="INFO", event="fixture", message=f"{index}:" + "x" * 900)
    files = list(tmp_path.glob("system-events.jsonl*"))
    assert len(files) == 3
    assert all(path.stat().st_size <= 4096 for path in files)
    records, _ = events.read()
    assert any(record["message"].startswith("69:") for record in records)
    assert not any(record["message"].startswith("0:") for record in records)


def test_bounded_read_marks_truncated_and_ignores_legacy_logs(app):
    store(app).read_max_records = 2
    (store(app).directory / "flask.log").write_text("password=legacy-secret", encoding="utf-8")
    for index in range(5):
        store(app).append(level="INFO", event="fixture", message=str(index))
    data = fetch(app).json["data"]
    assert data["truncated"] is True and data["total"] == 2
    assert "legacy-secret" not in json.dumps(data)
    store(app).read_max_records = 20000
    store(app).read_max_bytes = 1024
    for index in range(10):
        store(app).append(level="INFO", event="fixture", message="x" * 400)
    assert store(app).read()[1] is True


def test_oversize_messages_and_corrupt_records_are_bounded(app):
    assert store(app).append(level="ERROR", event="fixture", message="密" * 100000)
    assert store(app)._path().stat().st_size <= 8192
    with store(app)._path().open("ab") as stream:
        stream.write(b"not json\n")
    records, truncated = store(app).read()
    assert len(records) == 1 and truncated


def test_multiple_store_instances_share_rotation_lock(tmp_path):
    stores = [logs.SystemLogStore(tmp_path, max_bytes=4096, backups=5) for _ in range(4)]
    def write(index):
        started = time.monotonic()
        saved = stores[index % 4].append(level="INFO", event="fixture", message=f"record-{index}")
        return index, saved, time.monotonic() - started
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(write, range(30), timeout=5))
    # Lock contention is best effort: a timed-out append explicitly returns False.
    # This fixture is smaller than the retained capacity, so every True must exist
    # on disk, and no False may masquerade as a successful append.
    assert all(saved is True or saved is False for _, saved, _ in results)
    assert all(elapsed < 2 for _, _, elapsed in results)
    accepted = {f"record-{index}" for index, saved, _ in results if saved}
    assert accepted
    records, truncated = stores[0].read()
    assert not truncated
    assert len(records) == len(accepted)
    assert {record["message"] for record in records} == accepted
    assert len({record["id"] for record in records}) == len(accepted)


@pytest.mark.parametrize("lock_kind", ["thread", "file"])
def test_lock_timeout_returns_false_without_writing_and_recovers(tmp_path, lock_kind):
    owner = logs.SystemLogStore(tmp_path)
    contender = owner if lock_kind == "thread" else logs.SystemLogStore(tmp_path)
    held_lock = owner._thread_lock if lock_kind == "thread" else owner._locked()
    with ThreadPoolExecutor(max_workers=1) as executor:
        # Keep the competing lock held until append has returned. If it waits
        # indefinitely the future deadline fails, then releasing the lock allows
        # worker cleanup instead of leaving an indefinitely blocked test thread.
        with held_lock:
            started = time.monotonic()
            future = executor.submit(contender.append, level="INFO", event="fixture", message="not-written")
            assert future.result(timeout=2) is False
            assert time.monotonic() - started < 2
    assert owner.read() == ([], False)
    assert contender.append(level="INFO", event="fixture", message="after-release") is True
    records, truncated = owner.read()
    assert not truncated and [record["message"] for record in records] == ["after-release"]


def test_two_worker_processes_keep_complete_json_during_rotation(tmp_path):
    program = """
import json, sys, time, types
from pathlib import Path
root, directory, worker = sys.argv[1:]
package = types.ModuleType('core')
package.__path__ = [str(Path(root) / 'core')]
sys.modules['core'] = package
from core.system_logs import SystemLogStore
directory = Path(directory)
(directory / (worker + '.ready')).write_text('ready')
deadline = time.monotonic() + 8
while len(list(directory.glob('*.ready'))) < 2:
    if time.monotonic() > deadline:
        raise RuntimeError('worker barrier timed out')
    time.sleep(.01)
store = SystemLogStore(directory, max_bytes=4096, backups=5)
results = []
for index in range(15):
    message = worker + ':' + str(index)
    results.append({'message': message, 'saved': store.append(level='INFO', event='worker', message=message)})
print(json.dumps(results))
"""
    processes = [subprocess.Popen([sys.executable, "-c", program, str(ROOT), str(tmp_path), str(index)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for index in range(2)]
    results = []
    try:
        for process in processes:
            stdout, stderr = process.communicate(timeout=15)
            assert process.returncode == 0, stderr
            results.extend(json.loads(stdout))
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    records, truncated = logs.SystemLogStore(tmp_path, max_bytes=4096, backups=5).read()
    assert len(results) == 30
    assert all(result["saved"] is True or result["saved"] is False for result in results)
    accepted = {result["message"] for result in results if result["saved"]}
    assert accepted
    assert not truncated and len(records) == len(accepted)
    assert {record["message"] for record in records} == accepted
    assert len({record["id"] for record in records}) == len(accepted)


def test_logging_io_failure_does_not_change_business_response(app, monkeypatch):
    def failed(*args, **kwargs):
        raise OSError("private-storage-detail")
    monkeypatch.setattr(logs.os, "open", failed)
    assert app.test_client().post("/work/1", json={"ok": True}).status_code == 200
    assert app.test_client().get("/warn").status_code == 200
    assert app.test_client().get("/failure").status_code == 500


def test_read_failure_returns_bounded_generic_error(app, monkeypatch):
    def failed():
        raise OSError("password=should-not-be-returned")
    monkeypatch.setattr(store(app), "read", failed)
    response = fetch(app)
    assert response.status_code == 503
    assert "should-not-be-returned" not in response.get_data(as_text=True)


def test_init_is_idempotent(app):
    handler = app.extensions[logs.EXTENSION_KEY + "_handler"]
    before = len(app.before_request_funcs[None])
    assert logs.init_app(app) is store(app)
    assert len(app.before_request_funcs[None]) == before
    assert app.logger.handlers.count(handler) == 1
    assert logging.getLogger().handlers.count(handler) == 1
