"""Bounded redaction for diagnostic logs, independent of Flask and database setup."""
import re


REDACTED = "[REDACTED]"
MAX_TEXT = 12000
_SECRET_KEY = re.compile(
    r"(?:^|[_-])(?:password|passwd|pwd|secret|authorization|cookie|api[_-]?key|"
    r"access[_-]?token|refresh[_-]?token|connect[_-]?info|connection[_-]?(?:string|url)|"
    r"database[_-]?url|dsn)(?:$|[_-])|^token$", re.I)
_DB_URL = re.compile(r"\b(?:postgres(?:ql)?|mysql|mariadb|oracle|mssql|redis|mongodb)"
                     r"(?:\+[\w-]+)?://[^\s<>\"']+", re.I)
_URL_CREDENTIALS = re.compile(r"(\b[a-z][\w+.-]*://)[^\s/@]+@", re.I)
_QUOTED_SECRET = re.compile(
    r"([\"']?(?:password|passwd|pwd|secret|(?:access_|refresh_)?token|authorization|"
    r"cookie|api[_-]?key|connect[_-]?info|connection[_-]?(?:string|url)|database[_-]?url|dsn)"
    r"[\"']?\s*[:=]\s*)([\"'])((?:\\.|(?!\2).)*)(\2)", re.I | re.S)
_BARE_SECRET = re.compile(
    r"(\b(?:password|passwd|pwd|secret|(?:access_|refresh_)?token|authorization|"
    r"cookie|api[_-]?key|connect[_-]?info|connection[_-]?(?:string|url)|database[_-]?url|dsn)"
    r"\s*[:=]\s*)(?![\"']|\[REDACTED\])([^\s,;&}\]]+)", re.I)
_AUTH = re.compile(r"\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+", re.I)
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")


def sanitize_log_text(value):
    if value is None:
        return ""
    # Bound regex work as well as stored output. Redact before the final truncation.
    text = str(value)[:MAX_TEXT * 4]
    text = _DB_URL.sub(REDACTED, text)
    text = _URL_CREDENTIALS.sub(lambda m: m.group(1) + REDACTED + "@", text)
    text = _QUOTED_SECRET.sub(lambda m: m.group(1) + m.group(2) + REDACTED + m.group(2), text)
    text = _AUTH.sub(REDACTED, text)
    text = _BARE_SECRET.sub(lambda m: m.group(1) + REDACTED, text)
    text = _JWT.sub(REDACTED, text)
    return text[:MAX_TEXT] + (" …[truncated]" if len(text) > MAX_TEXT else "")


def sanitize_log_value(value, _depth=0):
    if _depth > 12:
        return "[truncated]"
    if isinstance(value, dict):
        return {
            str(key): REDACTED if _SECRET_KEY.search(str(key)) else sanitize_log_value(item, _depth + 1)
            for key, item in list(value.items())[:100]
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_log_value(item, _depth + 1) for item in value[:100]]
    if isinstance(value, str):
        return sanitize_log_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return sanitize_log_text(value)
