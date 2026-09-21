import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    "isolated_log_sanitizer", Path(__file__).resolve().parents[1] / "core/log_sanitizer.py")
sanitizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sanitizer)


@pytest.mark.parametrize("text, secret", [
    ('password=private-value', 'private-value'),
    ('{"password": "two word secret"}', 'two word secret'),
    ('password=\'two word secret\'', 'two word secret'),
    ('{"api_key":"key-123"}', 'key-123'),
    ('Authorization: Bearer private-token', 'private-token'),
    ('https://user:private-value@host/path', 'private-value'),
    ('postgresql+psycopg://user:private-value@host/db', 'private-value'),
    ('https://host/path?access_token=private-value&ok=true', 'private-value'),
    ('connect_info="postgresql://user:private-value@host/db"', 'private-value'),
    ('{"password": "before\\\"after"}', 'after'),
])
def test_redacts_sensitive_text(text, secret):
    result = sanitizer.sanitize_log_text(text)
    assert secret not in result
    assert "[REDACTED]" in result
    assert sanitizer.sanitize_log_text(result) == result


def test_redacts_nested_credentials_without_hiding_token_metrics():
    value = {"total_tokens": 42, "prompt_tokens": 20, "model_error": {"code": "HTTP_500"},
             "clusters": [{"_connect_info_raw": "private", "api_key": "secret", "sql": "SELECT 1"}]}
    result = sanitizer.sanitize_log_value(value)
    assert result["total_tokens"] == 42
    assert result["prompt_tokens"] == 20
    assert result["model_error"] == {"code": "HTTP_500"}
    assert result["clusters"] == [{"_connect_info_raw": "[REDACTED]", "api_key": "[REDACTED]", "sql": "SELECT 1"}]
    assert value["clusters"][0]["api_key"] == "secret"


def test_bounds_recursive_and_long_diagnostic_input():
    cycle = []
    cycle.append(cycle)
    assert "truncated" in str(sanitizer.sanitize_log_value(cycle))
    assert len(sanitizer.sanitize_log_text("x" * 100000)) < 12100
