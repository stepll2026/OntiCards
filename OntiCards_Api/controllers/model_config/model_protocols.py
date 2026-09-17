"""Shared request/response adapters for all model callers and configuration probes.

The application keeps its Chat Completions response contract. Provider-native
responses are normalized here so query, streaming and usage accounting agree.
"""
import json
import math
from time import monotonic
from urllib.parse import urlsplit

import requests

from controllers.model_config.model_endpoints import (
    NATIVE_PATHS,
    _is_dashscope,
    detect_protocol,
    protocol_headers,
    rerank_uses_flat_payload,
    resolve_api_url,
    validate_model_options,
)
from controllers.model_config.model_native import native_chat, native_request


class ModelServiceError(ValueError):
    """Safe to show to the user; never include provider bodies or credentials."""


def config_value(config, name, default=None):
    return config.get(name, default) if isinstance(config, dict) else getattr(config, name, default)


def model_request(config, kind, text, *, documents=None, top_n=None, stream=False, temperature=None, purpose="document"):
    protocol = config_value(config, "api_protocol", "auto") or "auto"
    dimensions = config_value(config, "embedding_dimensions")
    options = config_value(config, "api_options")
    options = {} if options is None else options
    validate_model_options(protocol, dimensions, options)
    if purpose not in {"query", "document"}:
        raise ValueError("向量用途必须为 query 或 document。")
    original_url = config_value(config, "url") or config_value(config, "api_url")
    model = config_value(config, "model_name")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("请填写模型名称。")
    url = resolve_api_url(original_url, kind, model, protocol)
    key = config_value(config, "model_api_key") or config_value(config, "api_key") or ""
    if not isinstance(key, str):
        raise ValueError("API Key 必须为文本。")
    key = key.strip()
    has_key = bool(key and key.lower() != "null")
    detected = detect_protocol(original_url, protocol, model, kind)
    headers = protocol_headers(detected, key)
    if detected not in {"openai", "dashscope"}:
        return native_request(detected, url, headers, model.strip(), kind, text, documents, top_n, stream, temperature, dimensions, options, key, purpose)
    path = urlsplit(url).path.rstrip("/")
    native_suffixes = tuple('/' + suffix for suffix in NATIVE_PATHS.values()) + ('/services/aigc/multimodal-generation/generation',)
    native = protocol == "dashscope" or (protocol == "auto" and path.endswith(native_suffixes))
    if path.endswith("/compatible-api/v1/reranks") and _is_dashscope(urlsplit(url).hostname):
        native = False
    elif kind == "rerank" and protocol == "auto" and not native:
        # Preserve existing custom full URLs that used the original keyed/nested format.
        native = not rerank_uses_flat_payload(original_url, url, has_key)
    wire_protocol = "dashscope" if native else "openai"
    payload = {"model": model.strip()}
    if kind == "base":
        content = [{"text": text}] if native and "multimodal-generation" in path else text
        messages = [{"role": "user", "content": content}]
        if native:
            parameters = {"result_format": "message"}
            if stream:
                headers["X-DashScope-SSE"] = "enable"
                parameters["incremental_output"] = True
            if temperature is not None:
                parameters["temperature"] = temperature
            payload.update(input={"messages": messages}, parameters=parameters)
        else:
            payload.update(messages=messages, stream=bool(stream))
            if temperature is not None:
                payload["temperature"] = temperature
        if options.get("max_tokens"):
            if native:
                payload["parameters"]["max_tokens"] = options["max_tokens"]
            else:
                payload["max_tokens"] = options["max_tokens"]
    elif kind == "embedding":
        if native:
            payload["input"] = {"texts": text if isinstance(text, list) else [text]}
            if dimensions is not None:
                payload["parameters"] = {"dimension": dimensions}
        else:
            payload.update(input=text, encoding_format="float")
            if dimensions is not None:
                payload["dimensions"] = dimensions
    elif kind == "rerank":
        if native:
            payload.update(input={"query": text, "documents": documents}, parameters={"top_n": top_n, "return_documents": True})
        else:
            payload.update(query=text, documents=documents, top_n=top_n, return_documents=True)
    return url, headers, payload, wire_protocol


def _check_response(payload):
    if not isinstance(payload, dict):
        raise ModelServiceError("模型服务未返回有效的 JSON 对象，请核对接口协议。")
    if payload.get("error") or payload.get("type") == "error" or payload.get("code") not in (None, "", 0, 200, "200") or payload.get("success") is False:
        raise ModelServiceError("模型服务返回错误，请核对模型用途、权限和接口协议。")
    if isinstance(payload.get("base_resp"), dict) and payload["base_resp"].get("status_code") not in (None, 0):
        raise ModelServiceError("模型服务返回错误，请核对模型用途、权限和接口协议。")


def normalized_usage(payload):
    usage = payload.get("usage") or {}
    if not isinstance(usage, dict):
        usage = {}
    if isinstance(usage.get("tokens"), dict):
        usage = usage["tokens"]  # Cohere distinguishes measured tokens from billed units.
    if not usage and isinstance(payload.get("meta"), dict):
        usage = payload["meta"].get("billed_units") or {}
    if isinstance(payload.get("usageMetadata"), dict):
        meta = payload["usageMetadata"]
        output_tokens = sum(v for v in (meta.get("candidatesTokenCount"), meta.get("thoughtsTokenCount")) if type(v) is int and v >= 0)
        usage = {"prompt_tokens": meta.get("promptTokenCount", 0), "completion_tokens": output_tokens, "total_tokens": meta.get("totalTokenCount")}
    if "prompt_eval_count" in payload:
        usage = {"prompt_tokens": payload.get("prompt_eval_count", 0), "completion_tokens": payload.get("eval_count", 0)}
    prompt = usage.get("prompt_tokens", usage.get("input_tokens", 0))
    completion = usage.get("completion_tokens", usage.get("output_tokens", 0))
    prompt = prompt if type(prompt) is int and prompt >= 0 else 0
    completion = completion if type(completion) is int and completion >= 0 else 0
    total = usage.get("total_tokens")
    total = total if type(total) is int and total >= 0 else prompt + completion
    return {**usage, "prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total}


def _finite_number(value):
    try:
        return type(value) in (float, int) and math.isfinite(value)
    except OverflowError:
        return False


def normalize_chat(payload, protocol, *, stream=False):
    _check_response(payload)
    if protocol in {"responses", "anthropic", "gemini", "ollama", "cohere"}:
        try:
            content, reasoning, finish, usage_source = native_chat(payload, protocol, stream)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ModelServiceError("模型未返回完整有效的对话，请核对协议、输出限制及请求内容。") from None
        if not stream and not content.strip():
            raise ModelServiceError("未收到对话文本，请核对模型用途及协议。")
        message = {"role": "assistant", "content": content}
        if reasoning:
            message["reasoning_content"] = reasoning
        return {"id": payload.get("id"), "choices": [{"index": 0, "delta" if stream else "message": message, "finish_reason": finish}], "usage": normalized_usage(usage_source)}
    if protocol != "dashscope":
        return payload  # Preserve compatible-provider extensions and existing callers' contract.
    output = payload.get("output")
    if not isinstance(output, dict):
        raise ModelServiceError("对话响应缺少 output，请核对接口协议。")
    choices = output.get("choices")
    if choices is None and isinstance(output.get("text"), str):
        choices = [{"message": {"role": "assistant", "content": output["text"]}, "finish_reason": output.get("finish_reason")}]
    if not isinstance(choices, list):
        raise ModelServiceError("对话响应缺少文本结果，请核对模型用途。")
    normalized = []
    for index, choice in enumerate(choices):
        if not isinstance(choice, dict):
            raise ModelServiceError("对话响应格式不正确。")
        if not isinstance(choice.get("message"), dict):
            raise ModelServiceError("对话响应缺少 message 对象。")
        message = dict(choice["message"])
        content = message.get("content")
        if isinstance(content, list):
            message["content"] = "".join(part.get("text", "") for part in content if isinstance(part, dict) and isinstance(part.get("text"), str))
        item = {**choice, "index": choice.get("index", index)}
        item["delta" if stream else "message"] = message
        if stream:
            item.pop("message", None)
        normalized.append(item)
    return {"id": payload.get("request_id"), "choices": normalized, "usage": normalized_usage(payload)}


def embedding_result(payload, expected_dimensions=None):
    _check_response(payload)
    output = payload.get("output")
    rows = payload.get("data")
    if not isinstance(rows, list):
        rows = output.get("embeddings") if isinstance(output, dict) else None
    vector = rows[0].get("embedding") if isinstance(rows, list) and rows and isinstance(rows[0], dict) else None
    if vector is None and isinstance(payload.get("data"), dict):
        vector = payload["data"].get("embedding")  # Ark multimodal.
    if vector is None and isinstance(payload.get("embedding"), dict):
        vector = payload["embedding"].get("values")  # Gemini.
    if vector is None:
        embeddings = payload.get("embeddings")
        if isinstance(embeddings, dict):
            embeddings = embeddings.get("float")  # Cohere.
        if isinstance(embeddings, list) and embeddings:
            vector = embeddings[0]  # Ollama or Cohere.
    if vector is None and isinstance(payload.get("embedding"), list):
        vector = payload["embedding"]  # Older Ollama /api/embeddings.
    if not isinstance(vector, list) or not vector or not all(_finite_number(v) for v in vector):
        raise ModelServiceError("未返回有效的向量，请确认选择的是文本向量模型及对应接口。")
    if expected_dimensions is not None and len(vector) != expected_dimensions:
        raise ModelServiceError(f"返回向量为 {len(vector)} 维，与配置的 {expected_dimensions} 维不一致。")
    return vector, normalized_usage(payload)


def rerank_result(payload, document_count=None):
    _check_response(payload)
    output, data = payload.get("output"), payload.get("data")
    results = payload.get("results")
    if results is None and isinstance(output, dict):
        results = output.get("results")
        if results is None:
            results = output.get("output")
    if results is None and isinstance(data, list) and all(_finite_number(score) for score in data):
        if document_count is not None and len(data) != document_count:
            raise ModelServiceError("重排序结果数量不正确。")
        results = sorted([{"index": i, "relevance_score": score} for i, score in enumerate(data)], key=lambda row: row["relevance_score"], reverse=True)
    if results is None and isinstance(data, dict):
        results = data.get("results")
        if results is None and isinstance(data.get("scores"), list):
            scores = data["scores"]
            if (document_count is not None and len(scores) != document_count) or not all(_finite_number(score) for score in scores):
                raise ModelServiceError("重排序结果数量或分数不正确。")
            results = sorted([{"index": index, "relevance_score": score} for index, score in enumerate(scores)], key=lambda row: row["relevance_score"], reverse=True)
    if not isinstance(results, list):
        raise ModelServiceError("未返回重排序结果，请核对模型用途及接口协议。")
    seen = set()
    for row in results:
        if not isinstance(row, dict):
            raise ModelServiceError("重排序结果格式不正确。")
        index, score = row.get("index"), row.get("relevance_score")
        if type(index) is not int or index < 0 or index in seen or (document_count is not None and index >= document_count):
            raise ModelServiceError("重排序返回了无效或重复的文档索引。")
        if not _finite_number(score):
            raise ModelServiceError("重排序未返回有效的相关性分数。")
        seen.add(index)
    usage_payload = next((candidate for candidate in (payload, output, data) if isinstance(candidate, dict) and candidate.get("usage")), {})
    if not usage_payload and isinstance(data, dict) and type(data.get("token_usage")) is int:
        usage_payload = {"usage": {"total_tokens": data["token_usage"]}}
    if not usage_payload:
        usage_payload = payload
    return results, normalized_usage(usage_payload)


def iter_chat_events(response, protocol, deadline=None, max_bytes=None):
    """Parse SSE (including comments, CRLF and multi-line events), then normalize."""
    parts, size = [], 0
    anthropic_usage = {}
    terminal = False

    def decode_event(data):
        nonlocal terminal
        try:
            payload = json.loads(data)
        except (ValueError, UnicodeError):
            raise ModelServiceError("模型流式响应不是有效 JSON，请核对协议。") from None
        event = normalize_chat(payload, protocol, stream=True)
        terminal = terminal or payload.get("type") in {"response.completed", "message_stop", "message-end"} or payload.get("event_type") == "stream-end" or payload.get("done") is True or (protocol == "gemini" and any(c.get("finishReason") for c in payload.get("candidates", []) if isinstance(c, dict)))
        if protocol == "anthropic":
            raw_usage = (payload.get("message") or {}).get("usage") if payload.get("type") == "message_start" else payload.get("usage")
            if isinstance(raw_usage, dict):
                anthropic_usage.update(raw_usage)
            event["usage"] = normalized_usage({"usage": anthropic_usage})
        return event

    for line in response.iter_lines(chunk_size=1):
        if deadline is not None and monotonic() > deadline:
            raise ModelServiceError("模型测试超时，请检查服务或重试。")
        size += len(line)
        if max_bytes is not None and size > max_bytes:
            raise ModelServiceError("模型测试响应过大。")
        try:
            line = line.decode("utf-8") if isinstance(line, bytes) else line
        except UnicodeError:
            raise ModelServiceError("模型流式响应编码不正确。") from None
        if (protocol == "ollama" or (protocol == "cohere" and line.lstrip().startswith("{"))) and line.strip():
            yield decode_event(line)
        elif line.startswith("data:"):
            parts.append(line[5:].lstrip())
        elif not line and parts:
            data, parts = "\n".join(parts), []
            if data.strip() == "[DONE]":
                return
            yield decode_event(data)
    if parts:
        data = "\n".join(parts)
        if data.strip() != "[DONE]":
            yield decode_event(data)
    if protocol in {"responses", "anthropic", "gemini", "ollama", "cohere"} and not terminal:
        raise ModelServiceError("模型文本流未正常结束，请重试。")


def probe_model(config):
    """Small opt-in inference; never saves config or accesses user data/vector indexes."""
    kind = config_value(config, "model_class")
    if not isinstance(kind, str) or kind not in {"base", "embedding", "rerank"}:
        raise ValueError("请选择对话、向量或重排序用途。")
    streaming = config_value(config, "test_stream", False)
    if type(streaming) is not bool or (streaming and kind != "base"):
        raise ValueError("仅对话模型支持流式测试。")
    sample = "Reply with exactly OK." if kind == "base" else "模型连接测试"
    docs = ["模型连接与文本检索", "苹果和香蕉"] if kind == "rerank" else None
    url, headers, body, protocol = model_request(config, kind, sample, documents=docs, top_n=2, stream=streaming)
    started, details = monotonic(), {}
    deadline = started + 45
    try:
        with requests.post(url, headers=headers, json=body, timeout=(5, 35), stream=True, allow_redirects=False) as response:
            status = response.status_code
            if status in {401, 403}:
                raise ModelServiceError("服务商鉴权失败，请核对 API Key、模型权限及地域。")
            if not 200 <= status < 300:
                raise ModelServiceError(f"模型测试失败（HTTP {status}），请核对模型用途、协议与地址。")
            if streaming:
                chars, chunks = 0, 0
                for event in iter_chat_events(response, protocol, deadline, 4 * 1024 * 1024):
                    choices = event.get("choices", [])
                    if not isinstance(choices, list):
                        raise ModelServiceError("模型流式响应格式不正确。")
                    for choice in choices:
                        delta = choice.get("delta") if isinstance(choice, dict) else None
                        content = delta.get("content") if isinstance(delta, dict) else None
                        if isinstance(content, str):
                            chars += len(content)
                            chunks += 1
                if not chars:
                    raise ModelServiceError("未收到对话文本流，请核对模型用途及协议。")
                details.update(stream=True, text_chunks=chunks)
            else:
                content, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if monotonic() > deadline or size > 4 * 1024 * 1024:
                        raise ModelServiceError("模型测试响应超时或过大。")
                    content.append(chunk)
                try:
                    result = json.loads(b"".join(content))
                except (ValueError, UnicodeError):
                    raise ModelServiceError("模型服务未返回有效 JSON，请核对接口协议。") from None
                if kind == "base":
                    result = normalize_chat(result, protocol)
                    choices = result.get("choices")
                    message = choices[0].get("message") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
                    content = message.get("content") if isinstance(message, dict) else None
                    if not isinstance(content, str) or not content.strip():
                        raise ModelServiceError("未收到对话文本，请核对模型用途及协议。")
                elif kind == "embedding":
                    vector, _ = embedding_result(result, config_value(config, "embedding_dimensions"))
                    details["dimensions"] = len(vector)
                else:
                    results, _ = rerank_result(result, len(docs))
                    if len(results) != len(docs):
                        raise ModelServiceError("重排序测试结果不完整。")
                    details["ranked_documents"] = len(results)
    except requests.RequestException:
        raise ModelServiceError("无法连接模型服务或请求超时，请核对地址和网络。") from None
    return {"success": True, "model_class": kind, "protocol": protocol,
            "latency_ms": round((monotonic() - started) * 1000), **details}
