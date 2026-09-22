"""Bounded structured system events, separate from legacy application log files.

Writers in different Gunicorn workers share an advisory file lock. Each append
opens the current file after locking, so rotation cannot leave another worker
writing to a renamed file. Logging is best effort and never raises into a request.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import threading
import time
import uuid
import weakref

from flask import current_app, g, has_app_context, has_request_context, request

from core.log_sanitizer import sanitize_log_text, sanitize_log_value

try:
    import fcntl
except ImportError:  # Windows development/test runtime.
    fcntl = None
    import msvcrt


EXTENSION_KEY = "onticards_system_logs"
LOG_PREFIX = "/console/api/log_center"
FIELDS = ("id", "created_at", "level", "event", "message", "request_id", "method",
          "path", "status_code", "duration_ms")
LEVELS = {"INFO", "WARNING", "ERROR"}


def _bounded_int(value, default, minimum, maximum):
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError, OverflowError):
        return default


def _safe_text(value, limit=1800):
    return sanitize_log_text(str(value))[:limit]


def _excluded_request():
    return has_request_context() and (
        request.path == LOG_PREFIX or request.path.startswith(LOG_PREFIX + "/"))


def _request_fields():
    if not has_request_context():
        return {"request_id": None, "method": None, "path": None}
    # A routing rule avoids recording credentials/identifiers embedded in path parameters.
    rule = request.url_rule.rule if request.url_rule is not None else "/<unmatched>"
    return {"request_id": getattr(g, "_system_request_id", None),
            "method": request.method[:16], "path": _safe_text(rule, 300)}


def _brief_exception(error):
    message = str(error).splitlines()[0] if str(error) else ""
    return _safe_text(type(error).__name__ + (": " + message if message else ""))


def note_request_exception(error):
    """Annotate handled exceptions without exposing a stack, SQL or request data."""
    try:
        if has_request_context() and not _excluded_request():
            g._system_request_error = _brief_exception(error)
    except Exception:
        pass


class SystemLogStore:
    def __init__(self, directory, *, max_bytes=10 * 1024 * 1024, backups=5,
                 read_max_bytes=8 * 1024 * 1024, read_max_records=20000):
        self.directory = Path(directory)
        self.max_bytes = _bounded_int(max_bytes, 10 * 1024 * 1024, 4096, 10 * 1024 * 1024)
        self.backups = _bounded_int(backups, 5, 1, 5)
        self.read_max_bytes = _bounded_int(read_max_bytes, 8 * 1024 * 1024, 1024, 8 * 1024 * 1024)
        self.read_max_records = _bounded_int(read_max_records, 20000, 1, 20000)
        self._thread_lock = threading.Lock()

    def _path(self, index=0):
        suffix = "" if index == 0 else "." + str(index)
        return self.directory / ("system-events.jsonl" + suffix)

    @contextmanager
    def _locked(self):
        if not self._thread_lock.acquire(timeout=0.05):
            raise TimeoutError("System log lock is busy")
        fd = None
        locked = False
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            lock_path = self.directory / "system-events.lock"
            if lock_path.is_symlink():
                raise OSError("Invalid system log lock")
            fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"0")
            deadline = time.monotonic() + 0.05
            while True:
                try:
                    if fcntl is not None:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    else:
                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    locked = True
                    break
                except (OSError, BlockingIOError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("System log lock is busy")
                    time.sleep(0.005)
            yield
        finally:
            try:
                if fd is not None:
                    try:
                        if locked:
                            if fcntl is not None:
                                fcntl.flock(fd, fcntl.LOCK_UN)
                            else:
                                os.lseek(fd, 0, os.SEEK_SET)
                                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    finally:
                        os.close(fd)
            finally:
                self._thread_lock.release()

    def append(self, *, level, event, message, **metadata):
        try:
            record = {"id": uuid.uuid4().hex,
                      "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                      "level": level if level in LEVELS else "ERROR",
                      "event": _safe_text(event, 80), "message": _safe_text(message),
                      "request_id": None, "method": None, "path": None,
                      "status_code": None, "duration_ms": None}
            record.update({key: value for key, value in metadata.items() if key in FIELDS and key not in {
                "id", "created_at", "level", "event", "message"}})
            record = sanitize_log_value(record)
            raw = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            # Keep each record bounded even with wide Unicode or a custom sanitizer.
            if len(raw) > min(self.max_bytes, 8192):
                record["message"] = _safe_text(record["message"], 400)
                raw = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            if len(raw) > min(self.max_bytes, 8192):
                return False
            with self._locked():
                path = self._path()
                if any(self._path(index).is_symlink() for index in range(self.backups + 1)):
                    return False
                if path.exists() and path.stat().st_size + len(raw) > self.max_bytes:
                    oldest = self._path(self.backups)
                    if oldest.exists():
                        oldest.unlink()
                    for index in range(self.backups - 1, -1, -1):
                        source = self._path(index)
                        if source.exists():
                            source.replace(self._path(index + 1))
                fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
                try:
                    view = memoryview(raw)
                    while view:
                        count = os.write(fd, view)
                        if count <= 0:
                            raise OSError("System log write failed")
                        view = view[count:]
                finally:
                    os.close(fd)
            return True
        except Exception:
            return False

    def read(self):
        """Return newest bounded records; never inspect legacy flask.log files."""
        if not self.directory.exists():
            return [], False
        records = []
        remaining = self.read_max_bytes
        truncated = False
        with self._locked():
            paths = [self._path(index) for index in range(self.backups + 1)]
            for index, path in enumerate(paths):
                if path.is_symlink():
                    raise OSError("Invalid system log file")
                if not path.exists():
                    continue
                size = path.stat().st_size
                if remaining <= 0 or len(records) >= self.read_max_records:
                    truncated = truncated or size > 0
                    continue
                amount = min(size, remaining)
                with path.open("rb") as stream:
                    stream.seek(size - amount)
                    chunk = stream.read(amount)
                remaining -= len(chunk)
                if amount < size:
                    # The first partial line may have started before the read window.
                    chunk = chunk.partition(b"\n")[2]
                    truncated = True
                for line in reversed(chunk.splitlines()):
                    if len(records) >= self.read_max_records:
                        truncated = True
                        break
                    try:
                        record = json.loads(line)
                        if not isinstance(record, dict) or record.get("level") not in LEVELS:
                            truncated = True
                            continue
                        # Re-sanitize on read; never forward arbitrary stored extra fields.
                        safe = sanitize_log_value({key: record.get(key) for key in FIELDS})
                        if not isinstance(safe.get("created_at"), str):
                            continue
                        records.append(safe)
                    except (ValueError, UnicodeError, TypeError):
                        truncated = True
                        continue
        records.sort(key=lambda record: record["created_at"], reverse=True)
        return records, truncated


class SystemLogHandler(logging.Handler):
    def __init__(self, app, store):
        super().__init__(logging.WARNING)
        self.app_ref = weakref.ref(app)
        self.store = store

    def emit(self, record):
        try:
            app = self.app_ref()
            if app is None or record.levelno < logging.WARNING or _excluded_request():
                return
            if has_app_context() and current_app._get_current_object() is not app:
                return
            # app.logger normally propagates to root; one handler receives a record once.
            marker = getattr(record, "_onticards_system_handlers", set())
            if id(self) in marker:
                return
            record._onticards_system_handlers = marker | {id(self)}
            if record.exc_info and record.exc_info[1] is not None:
                message = _brief_exception(record.exc_info[1])
            else:
                message = record.getMessage()
                if "Traceback (most recent call last)" in message:
                    message = next((line for line in reversed(message.splitlines()) if line.strip()), "Exception")
                message = _safe_text(message)
            self.store.append(level="ERROR" if record.levelno >= logging.ERROR else "WARNING",
                              event="python_log", message=message, **_request_fields())
        except Exception:
            pass


def init_app(app, *, directory=None):
    """Install metadata-only request tracking and WARNING/ERROR collection once."""
    if EXTENSION_KEY in app.extensions:
        return app.extensions[EXTENSION_KEY]
    log_dir = directory or app.config.get("SYSTEM_LOG_DIR") or Path(__file__).resolve().parents[1] / "logs"
    store = SystemLogStore(log_dir,
        max_bytes=app.config.get("SYSTEM_LOG_MAX_BYTES", 10 * 1024 * 1024),
        backups=app.config.get("SYSTEM_LOG_BACKUPS", 5),
        read_max_bytes=app.config.get("SYSTEM_LOG_READ_MAX_BYTES", 8 * 1024 * 1024),
        read_max_records=app.config.get("SYSTEM_LOG_READ_MAX_RECORDS", 20000))
    app.extensions[EXTENSION_KEY] = store
    handler = SystemLogHandler(app, store)
    app.extensions[EXTENSION_KEY + "_handler"] = handler
    app.logger.addHandler(handler)
    logging.getLogger().addHandler(handler)

    @app.before_request
    def system_request_started():
        if not _excluded_request():
            g._system_request_id = uuid.uuid4().hex
            g._system_request_started = time.monotonic()

    def completed(status, error=None):
        try:
            if _excluded_request() or getattr(g, "_system_request_logged", False):
                return
            g._system_request_logged = True
            started = getattr(g, "_system_request_started", time.monotonic())
            detail = getattr(g, "_system_request_error", None)
            if error is not None:
                detail = _brief_exception(error)
            level = "ERROR" if status >= 500 else "WARNING" if status >= 400 else "INFO"
            message = detail or f"HTTP {status}"
            store.append(level=level, event="request_completed", message=message,
                         status_code=status, duration_ms=round(max(0, time.monotonic() - started) * 1000, 2),
                         **_request_fields())
        except Exception:
            pass

    @app.after_request
    def system_request_completed(response):
        completed(response.status_code)
        return response

    @app.teardown_request
    def system_request_exception(error):
        if error is not None:
            completed(500, error)

    return store
