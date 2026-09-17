"""Native wire formats. All callers still receive Chat Completions-style results."""
import hashlib
import hmac
from datetime import datetime, timezone
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import requests


def viking_headers(url, body, access_key, secret_key, region="cn-beijing", now=None):
    """Volcengine Signature V4, signing the exact bytes requests sends as JSON."""
    if not access_key or not secret_key or secret_key.lower() == "null":
        raise ValueError("Viking 重排需要 Access Key ID 和 Secret Access Key。")
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    parsed = urlsplit(url)
    prepared = requests.Request("POST", url, json=body).prepare()
    digest = hashlib.sha256(prepared.body).hexdigest()
    headers = {"Content-Type": "application/json", "Host": parsed.netloc, "X-Date": stamp, "X-Content-Sha256": digest}
    signed_names = ";".join(sorted(k.lower() for k in headers))
    canonical_headers = "".join(f"{key.lower()}:{value.strip()}\n" for key, value in sorted(headers.items(), key=lambda item: item[0].lower()))
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)), quote_via=quote, safe="~")
    canonical = "\n".join(["POST", quote(parsed.path or "/", safe="/-_.~"), query, canonical_headers, signed_names, digest])
    scope = f"{stamp[:8]}/{region}/air/request"
    string_to_sign = "\n".join(["HMAC-SHA256", stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    key = secret_key.encode()
    for value in (stamp[:8], region, "air", "request"):
        key = hmac.new(key, value.encode(), hashlib.sha256).digest()
    signature = hmac.new(key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    headers["Authorization"] = f"HMAC-SHA256 Credential={access_key}/{scope}, SignedHeaders={signed_names}, Signature={signature}"
    return headers


def native_request(protocol, url, headers, model, kind, text, documents, top_n, stream, temperature, dimensions, options, key, purpose):
    body = {"model": model}
    max_tokens = options.get("max_tokens")
    if kind == "base":
        if protocol == "responses":
            body.update(input=text, stream=bool(stream), store=False)
            if max_tokens:
                body["max_output_tokens"] = max_tokens
        elif protocol == "gemini":
            body = {"contents": [{"role": "user", "parts": [{"text": text}]}]}
            if max_tokens:
                body["generationConfig"] = {"maxOutputTokens": max_tokens}
            if temperature is not None:
                body.setdefault("generationConfig", {})["temperature"] = temperature
            parsed = urlsplit(url)
            path = parsed.path.replace(":streamGenerateContent", ":generateContent")
            query = dict(parse_qsl(parsed.query, keep_blank_values=True))
            if stream:
                path = path.replace(":generateContent", ":streamGenerateContent")
                query["alt"] = "sse"
            elif query.get("alt") == "sse":
                query.pop("alt")
            url = urlunsplit(parsed._replace(path=path, query=urlencode(query)))
        else:
            body.update(messages=[{"role": "user", "content": text}], stream=bool(stream))
            if protocol == "cohere" and "/v1/" in urlsplit(url).path:
                body.pop("messages")
                body["message"] = text
            if protocol == "anthropic":
                body["max_tokens"] = max_tokens or 4096
            elif protocol == "ollama":
                if max_tokens:
                    body["options"] = {"num_predict": max_tokens}
            elif max_tokens:
                body["max_tokens"] = max_tokens
        if temperature is not None and protocol != "gemini":
            if protocol == "ollama":
                body.setdefault("options", {})["temperature"] = temperature
            else:
                body["temperature"] = temperature
    elif kind == "embedding":
        if protocol == "ark":
            # The platform embeds one text at a time; multimodal is the wire format.
            if not isinstance(text, str):
                raise ValueError("豆包多模态向量接口每次仅支持一段检索文本。")
            body.update(input=[{"type": "text", "text": text}], encoding_format="float")
        elif protocol == "gemini":
            body = {"model": model if model.startswith("models/") else "models/" + model,
                    "content": {"parts": [{"text": text}]},
                    "taskType": "RETRIEVAL_QUERY" if purpose == "query" else "RETRIEVAL_DOCUMENT"}
        elif protocol == "cohere":
            body.update(texts=text if isinstance(text, list) else [text], input_type="search_query" if purpose == "query" else "search_document", embedding_types=["float"])
        elif protocol == "ollama":
            # Retain the older full /api/embeddings endpoint as well as /api/embed.
            body["prompt" if urlsplit(url).path.endswith("/api/embeddings") else "input"] = text
        else:
            body["input"] = text if isinstance(text, list) else [text]
            if protocol == "voyage":
                body["input_type"] = "query" if purpose == "query" else "document"
            elif protocol == "jina":
                body.update(task="retrieval.query" if purpose == "query" else "retrieval.passage", embedding_type="float")
            else:
                body["encoding_format"] = "float"
        if dimensions is not None:
            field = {"gemini": "outputDimensionality", "cohere": "output_dimension", "voyage": "output_dimension"}.get(protocol, "dimensions")
            body[field] = dimensions
    elif kind == "rerank":
        if protocol == "viking":
            body = {"rerank_model": model, "datas": [{"query": text, "content": doc, "title": ""} for doc in documents]}
            if options.get("endpoint_id"):
                body["endpoint_id"] = options["endpoint_id"]
            headers = viking_headers(url, body, options.get("access_key_id"), key, options.get("region") or "cn-beijing")
        else:
            body.update(query=text, documents=documents, top_n=top_n)
            if protocol == "jina":
                body["return_documents"] = True
    return url, headers, body, protocol


def text_parts(parts):
    if isinstance(parts, str):
        return parts
    if not isinstance(parts, list):
        return ""
    return "".join(p.get("text", "") for p in parts if isinstance(p, dict) and p.get("type", "text") in {"text", "output_text"} and isinstance(p.get("text"), str) and not p.get("thought"))


def native_chat(payload, protocol, stream=False):
    """Return content, finish reason, usage source; lifecycle events have no content."""
    kind = payload.get("type", "")
    usage_payload = payload
    finish = None
    content = ""
    reasoning = ""
    if protocol == "responses":
        if kind in {"response.failed", "response.incomplete", "error"} or payload.get("status") in {"failed", "incomplete", "cancelled"}:
            raise ValueError("模型未完成对话，请检查输出限制或重试。")
        if stream:
            if kind == "response.output_text.delta":
                content = payload.get("delta", "")
            elif kind == "response.completed":
                usage_payload, finish = payload.get("response") or {}, "stop"
            elif kind == "response.reasoning_summary_text.delta":
                reasoning = payload.get("delta", "")
        else:
            content = "".join(text_parts(item.get("content")) for item in payload.get("output", []) if isinstance(item, dict) and item.get("type") == "message")
            finish = "stop"
    elif protocol == "anthropic":
        if stream:
            if kind == "message_start":
                usage_payload = payload.get("message") or {}
            elif kind == "content_block_start":
                block = payload.get("content_block") or {}
                content = block.get("text", "") if block.get("type") == "text" else ""
            elif kind == "content_block_delta":
                delta = payload.get("delta") or {}
                content = delta.get("text", "") if delta.get("type") == "text_delta" else ""
                reasoning = delta.get("thinking", "") if delta.get("type") == "thinking_delta" else ""
            elif kind == "message_delta":
                finish = (payload.get("delta") or {}).get("stop_reason")
        else:
            content, finish = text_parts(payload.get("content")), payload.get("stop_reason")
    elif protocol == "gemini":
        feedback = payload.get("promptFeedback") or {}
        if feedback.get("blockReason"):
            raise ValueError("模型服务未生成文本，请调整请求内容。")
        candidates = payload.get("candidates") or []
        if candidates:
            candidate = candidates[0]
            parts = (candidate.get("content") or {}).get("parts", [])
            content = text_parts(parts)
            reasoning = "".join(p.get("text", "") for p in parts if p.get("thought") and isinstance(p.get("text"), str))
            finish = candidate.get("finishReason")
            if finish in {"SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "MALFORMED_FUNCTION_CALL"}:
                raise ValueError("模型服务未完成文本生成。")
    elif protocol == "ollama":
        message = payload.get("message") or {}
        content, reasoning = message.get("content", ""), message.get("thinking", "")
        finish = payload.get("done_reason", "stop") if payload.get("done") else None
    elif protocol == "cohere":
        if payload.get("finish_reason") == "ERROR" or (payload.get("delta") or {}).get("finish_reason") == "ERROR":
            raise ValueError("模型服务未完成对话。")
        if stream:
            delta = payload.get("delta") or {}
            if kind == "content-delta":
                content = ((delta.get("message") or {}).get("content") or {}).get("text", "")
            elif kind == "message-end":
                usage_payload, finish = delta, delta.get("finish_reason", "stop")
            elif payload.get("event_type") == "text-generation":
                content = payload.get("text", "")
            elif payload.get("event_type") == "stream-end":
                usage_payload = payload.get("response") or {}
                finish = payload.get("finish_reason", "stop")
        else:
            content = payload.get("text") or text_parts((payload.get("message") or {}).get("content"))
            finish = payload.get("finish_reason")
    if not isinstance(content, str):
        raise ValueError("模型返回了无效的文本格式。")
    return content, reasoning, finish, usage_payload
