"""Helpers for logging HTTP request metadata without leaking credentials."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_SENSITIVE_KEY_PARTS = (
    "authorization",
    "api_key",
    "apikey",
    "password",
    "passwd",
    "secret",
    "token",
)
_REDACTED = "<redacted>"


def _is_sensitive_key(key):
    normalized = str(key).strip().lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def redact_url(url):
    """Return *url* with values of credential-like query parameters hidden."""
    parts = urlsplit(url)
    query = urlencode([
        (key, _REDACTED if _is_sensitive_key(key) else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def redact_mapping(values):
    """Copy a mapping/MultiDict while replacing credential-like values."""
    result = {}
    for key in values.keys():
        raw_values = values.getlist(key) if hasattr(values, "getlist") else [values[key]]
        safe_values = [_REDACTED if _is_sensitive_key(key) else value for value in raw_values]
        result[key] = safe_values[0] if len(safe_values) == 1 else safe_values
    return result
