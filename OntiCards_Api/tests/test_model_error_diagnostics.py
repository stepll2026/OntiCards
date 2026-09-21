"""Verify the model HTTP wrapper without contacting an upstream service."""
import ast
import copy
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test_join_scope_retry import ROOT, SANITIZER


class RequestTimeout(Exception):
    pass


class RequestConnectionError(Exception):
    pass


def _namespace(response=None, error=None):
    path = ROOT / "controllers/agents/qwen/QwenMaxLatest.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = {"_is_model_timeout", "_request_with_timing", "_model_error_diagnostic", "qian_wen_llm", "qian_wen_llm_with_usage"}
    body = [copy.deepcopy(node) for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in functions]
    request = Mock(side_effect=error) if error else Mock(return_value=response)
    namespace = {
        "time": time, "logger": Mock(), "sanitize_log_value": SANITIZER.sanitize_log_value,
        "Urllib3TimeoutError": RequestTimeout,
        "_get_session": lambda **kwargs: SimpleNamespace(request=request),
        "requests": SimpleNamespace(exceptions=SimpleNamespace(Timeout=RequestTimeout, ConnectionError=RequestConnectionError)),
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(path), "exec"), namespace)
    return namespace


def _call(namespace):
    return namespace["qian_wen_llm_with_usage"]("fixture prompt", model_config_dict={
        "api_url": "https://example.test/v1/chat/completions", "model_name": "fixture", "api_key": "fixture-secret",
    })


def _response(payload, status=200):
    return SimpleNamespace(status_code=status, json=lambda: payload)


def test_success_usage_contract_has_no_new_diagnostic_field():
    namespace = _namespace(_response({"choices": [{"message": {"content": "SELECT 1"}}],
                                      "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}}))
    content, usage = _call(namespace)
    assert content == "SELECT 1"
    assert set(usage) == {"prompt_tokens", "completion_tokens", "total_tokens", "generation_ms"}
    assert usage["total_tokens"] == 14


@pytest.mark.parametrize("status", [401, 429, 500, 503])
def test_http_failure_includes_status_but_never_raw_body(status):
    namespace = _namespace(_response({"error": "private body api_key=fixture-secret"}, status=status))
    _, usage = _call(namespace)
    assert usage["model_error"] == {
        "code": "MODEL_HTTP_ERROR", "message": "模型服务返回 HTTP 错误", "http_status": status}
    assert "fixture-secret" not in str(usage)
    assert "private body" not in str(usage)


@pytest.mark.parametrize("error, code", [
    (RequestTimeout("private URL"), "MODEL_TIMEOUT"),
    (RequestConnectionError("private URL"), "MODEL_CONNECTION_ERROR"),
    (RuntimeError("private URL"), "MODEL_REQUEST_ERROR"),
])
def test_network_exception_is_classified_without_leaking_exception_text(error, code):
    _, usage = _call(_namespace(error=error))
    assert usage["model_error"]["code"] == code
    assert "private URL" not in str(usage)


def test_non_json_response_has_safe_format_diagnostic():
    response = SimpleNamespace(status_code=200, json=Mock(side_effect=ValueError()), text="private upstream HTML")
    _, usage = _call(_namespace(response))
    assert usage["model_error"]["code"] == "MODEL_INVALID_RESPONSE"
    assert "private upstream HTML" not in str(usage)


def test_retry_exhausted_timeout_wrapped_by_connection_error_is_still_timeout():
    reason = RuntimeError("retry exhausted")
    reason.reason = RequestTimeout("read timed out")
    wrapped = RequestConnectionError(reason)
    _, usage = _call(_namespace(error=wrapped))
    assert usage["model_error"]["code"] == "MODEL_TIMEOUT"


@pytest.mark.parametrize("payload", [[], {"choices": []}, {"choices": ["invalid"]},
                                     {"choices": [{"message": {"content": None}}]}])
def test_malformed_json_envelope_is_classified(payload):
    _, usage = _call(_namespace(_response(payload)))
    assert usage["model_error"]["code"] == "MODEL_INVALID_RESPONSE"


def test_business_error_with_http_200_is_not_a_successful_generation():
    _, usage = _call(_namespace(_response({"error": {"message": "private upstream detail"}})))
    assert usage["model_error"]["code"] == "MODEL_UPSTREAM_ERROR"
    assert usage["model_error"]["http_status"] == 200
    assert "private upstream detail" not in str(usage)
