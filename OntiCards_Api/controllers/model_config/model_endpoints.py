"""Resolve model service base URLs without rewriting existing custom endpoints."""
import json
import re
from time import monotonic
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import requests


def _parse_url(url):
    if not isinstance(url, str) or not url.strip():
        raise ValueError("请输入模型接口地址。")
    value = url.strip()
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError
        if any(character.isspace() for character in value):
            raise ValueError
        _ = parsed.port
    except ValueError:
        raise ValueError("请输入合法的 HTTP 或 HTTPS 接口地址，不包含账号密码或片段。") from None
    return parsed


def _with_path(parsed, path):
    return urlunsplit(parsed._replace(path=path))


def _is_base_path(path):
    return not path or bool(re.search(r"/v\d+(?:\.\d+)?(?:beta\d*)?(?:/openai)?$", path))


def _is_dashscope(host):
    return host == "dashscope.aliyuncs.com" or host.endswith((".dashscope.aliyuncs.com", ".maas.aliyuncs.com")) or (
        host.startswith("dashscope-") and host.endswith(".aliyuncs.com")
    )


PROTOCOLS = {"auto", "openai", "dashscope", "responses", "anthropic", "gemini", "ollama", "cohere", "ark", "viking", "jina", "voyage", "azure"}
PROTOCOL_KINDS = {
    "responses": {"base"}, "anthropic": {"base"}, "gemini": {"base", "embedding"},
    "ollama": {"base", "embedding"}, "cohere": {"base", "embedding", "rerank"},
    "ark": {"embedding"}, "viking": {"rerank"}, "jina": {"embedding", "rerank"},
    "voyage": {"embedding", "rerank"}, "azure": {"base", "embedding"},
}
NATIVE_PATHS = {
    "base": "services/aigc/text-generation/generation",
    "embedding": "services/embeddings/text-embedding/text-embedding",
    "rerank": "services/rerank/text-rerank/text-rerank",
}


def validate_model_options(api_protocol="auto", embedding_dimensions=None, api_options=None):
    if not isinstance(api_protocol, str) or api_protocol not in PROTOCOLS:
        raise ValueError("请选择支持的接口协议。")
    if embedding_dimensions is not None and (
        type(embedding_dimensions) is not int or not 1 <= embedding_dimensions <= 65536
    ):
        raise ValueError("向量维数必须为 1 到 65536 的整数，或留空使用模型默认值。")
    if api_options is not None:
        if not isinstance(api_options, dict) or set(api_options) - {"max_tokens", "access_key_id", "region", "endpoint_id"}:
            raise ValueError("模型高级选项格式不正确。")
        if "max_tokens" in api_options and (type(api_options["max_tokens"]) is not int or not 1 <= api_options["max_tokens"] <= 1048576):
            raise ValueError("最大输出 Token 数必须为 1 到 1048576 的整数。")
        for name in ("access_key_id", "region", "endpoint_id"):
            if name in api_options and (not isinstance(api_options[name], str) or len(api_options[name]) > 256 or any(c.isspace() for c in api_options[name])):
                raise ValueError("鉴权及地域选项必须为不含空白的文本。")


def detect_protocol(url, api_protocol="auto", model_name="", model_class="base"):
    """Only infer known native endpoints; explicit protocol selection wins."""
    validate_model_options(api_protocol)
    if api_protocol != "auto":
        return api_protocol
    parsed = _parse_url(url)
    host, path = parsed.hostname, parsed.path.rstrip("/")
    if path.endswith("/responses"):
        return "responses"
    if path.endswith("/api/knowledge/service/rerank") or host.startswith("api-knowledgebase."):
        return "viking"
    if path.endswith("/embeddings/multimodal") or (host.startswith("ark.") and host.endswith(".volces.com") and model_class == "embedding" and any(s in model_name.lower() for s in ("embedding-vision", "embedding-multimodal"))):
        return "ark"
    if host == "api.anthropic.com" or path.endswith("/v1/messages"):
        return "anthropic"
    if (host == "generativelanguage.googleapis.com" and "/openai" not in path) or any(s in path for s in (":generateContent", ":streamGenerateContent", ":embedContent")):
        return "gemini"
    if path.endswith(("/api/chat", "/api/embed", "/api/embeddings", "/api/tags")) or (parsed.port == 11434 and path in ("", "/api")):
        return "ollama"
    if host in {"api.cohere.com", "api.cohere.ai"}:
        return "cohere"
    if host == "api.jina.ai":
        return "jina"
    if host == "api.voyageai.com":
        return "voyage"
    if host.endswith(".openai.azure.com"):
        return "azure"
    if path.endswith(tuple('/' + suffix for suffix in NATIVE_PATHS.values()) + ('/services/aigc/multimodal-generation/generation',)) or (_is_dashscope(host) and path.endswith("/api/v1")):
        return "dashscope"
    return "openai"


def protocol_headers(protocol, api_key):
    if not isinstance(api_key, str):
        raise ValueError("API Key 必须为文本。")
    key = api_key.strip()
    headers = {"Content-Type": "application/json"}
    if protocol == "anthropic":
        headers["anthropic-version"] = "2023-06-01"
    if key and key.lower() != "null" and protocol != "viking":
        if protocol in {"anthropic", "gemini", "azure"}:
            headers[{"anthropic": "x-api-key", "gemini": "x-goog-api-key", "azure": "api-key"}[protocol]] = key
        else:
            headers["Authorization"] = "Bearer " + key
    return headers


def resolve_api_url(url, model_class="base", model_name="", api_protocol="auto"):
    validate_model_options(api_protocol)
    if not isinstance(model_class, str) or model_class not in NATIVE_PATHS:
        raise ValueError("不支持的模型用途。")
    parsed = _parse_url(url)
    path = parsed.path.rstrip("/")
    protocol = detect_protocol(url, api_protocol, model_name, model_class)
    if protocol in PROTOCOL_KINDS and model_class not in PROTOCOL_KINDS[protocol]:
        raise ValueError("所选协议不支持此模型用途，请切换用途或接口协议。")
    if protocol == "gemini":
        if not _is_base_path(path):
            return url.strip()
        name = model_name.removeprefix("models/")
        if not name or "/" in name:
            raise ValueError("请填写有效的 Gemini 模型名称。")
        return _with_path(parsed, (path or "/v1beta") + "/models/" + quote(name, safe="-_.") + (":embedContent" if model_class == "embedding" else ":generateContent"))
    if protocol == "ollama" and (_is_base_path(path) or path.endswith("/api")):
        path = path if path.endswith("/api") else (path + "/api")
        return _with_path(parsed, path + ("/embed" if model_class == "embedding" else "/chat"))
    if protocol == "viking" and _is_base_path(path):
        return _with_path(parsed, path + "/api/knowledge/service/rerank")
    if protocol == "azure" and re.search(r"/openai/deployments/[^/]+$", path):
        return _with_path(parsed, path + ("/embeddings" if model_class == "embedding" else "/chat/completions"))
    if not _is_base_path(path):
        return url.strip()  # Explicit endpoints, including custom proxy paths, remain authoritative.
    if protocol in {"responses", "anthropic", "cohere", "ark", "voyage", "jina", "azure"}:
        root = {"responses": "/v1", "anthropic": "/v1", "cohere": "/v2", "ark": "/api/v3", "voyage": "/v1", "jina": "/v1", "azure": "/openai/v1"}[protocol]
        suffix = {"responses": "responses", "anthropic": "messages", "ark": "embeddings/multimodal"}.get(protocol)
        if suffix is None:
            suffix = {"base": "chat" if protocol == "cohere" else "chat/completions", "embedding": "embed" if protocol == "cohere" else "embeddings", "rerank": "rerank"}[model_class]
        return _with_path(parsed, (path or root) + "/" + suffix)
    native = api_protocol == "dashscope" or (api_protocol == "auto" and _is_dashscope(parsed.hostname) and path.endswith("/api/v1"))
    if native:
        if model_class == "rerank" and model_name == "qwen3-rerank" and _is_dashscope(parsed.hostname):
            return _with_path(parsed, "/compatible-api/v1/reranks")
        if _is_dashscope(parsed.hostname) or not path:
            path = "/api/v1"
        path += "/" + NATIVE_PATHS[model_class]
    elif api_protocol == "auto" and model_class == "rerank" and _is_dashscope(parsed.hostname):
        path = "/compatible-api/v1/reranks" if model_name == "qwen3-rerank" else "/api/v1/services/rerank/text-rerank/text-rerank"
    else:
        suffix = {"base": "chat/completions", "embedding": "embeddings", "rerank": "rerank"}.get(model_class)
        if suffix is None:
            raise ValueError("不支持的模型用途。")
        path += "/" + suffix
    return _with_path(parsed, path)


def model_catalog_url(url, api_protocol="auto"):
    validate_model_options(api_protocol)
    parsed = _parse_url(url)
    path = parsed.path.rstrip("/")
    protocol = detect_protocol(url, api_protocol)
    if protocol == "viking":
        raise ValueError("Viking 重排未提供此模型列表接口，请手动填写模型名称及可选接入点 ID。")
    if protocol == "ollama":
        root = path.rsplit("/api", 1)[0] if "/api" in path else path
        return _with_path(parsed, root + "/api/tags")
    if protocol == "gemini":
        root = path.split("/models", 1)[0]
        return _with_path(parsed, (root or "/v1beta") + "/models")
    if protocol == "cohere":
        root = re.sub(r"/v[12](?:/.*)?$", "", path)
        return _with_path(parsed, root + "/v1/models")
    if protocol == "azure" and "/deployments/" in path:
        raise ValueError("Azure 部署地址不提供模型目录，请手动填写部署名称。")
    if api_protocol in {"auto", "dashscope"} and _is_dashscope(parsed.hostname):
        return _with_path(parsed, "/api/v1/models")
    if "/services/" in path:
        path = path.split("/services/", 1)[0]
    for suffix in ("/chat/completions", "/embeddings/multimodal", "/embeddings", "/reranks", "/rerank", "/completions", "/models", "/responses", "/messages"):
        if path.endswith(suffix):
            path = path[:-len(suffix)]
            break
    if not _is_base_path(path):
        raise ValueError("无法从此完整地址确定模型列表接口，请填写基础地址或手动输入模型名称。")
    if _is_dashscope(parsed.hostname) and path == "/compatible-api/v1":
        path = "/compatible-mode/v1"
    if not path:
        path = {"anthropic": "/v1", "responses": "/v1", "jina": "/v1", "voyage": "/v1", "ark": "/api/v3", "azure": "/openai/v1"}.get(protocol, "")
    return _with_path(parsed, path + "/models")


def rerank_uses_flat_payload(configured_url, resolved_url, has_api_key):
    if not has_api_key:
        return True
    original = _parse_url(configured_url)
    compatible_base = _is_base_path(original.path.rstrip("/"))
    dashscope_compatible = _is_dashscope(original.hostname) and original.path.rstrip("/") == "/compatible-api/v1/reranks"
    known_flat_endpoint = original.hostname in {"api.siliconflow.cn", "api.siliconflow.com"} and original.path.rstrip("/").endswith("/v1/rerank")
    # Existing explicit custom endpoints retain their keyed request format.
    return (compatible_base or dashscope_compatible or known_flat_endpoint) and urlsplit(resolved_url).path.rstrip("/").endswith(("/rerank", "/reranks"))


class ModelDiscoveryError(Exception):
    pass


def classify_model(item):
    """Provider metadata is evidence; names are explicitly labelled hints, never allowlists."""
    aliases = {
        "base": {"chat", "chat/completions", "text-generation", "text_generation", "conversation", "conversational", "tg", "reasoning", "generatecontent", "responses", "messages"},
        # DashScope's live catalog uses TR for BOTH embedding and rerank models.
        # Treat that broad tag as inconclusive instead of labelling rerank as embedding.
        "embedding": {"embedding", "embeddings", "embed", "embedcontent", "text-embedding", "text_embedding", "feature-extraction"},
        "rerank": {"rerank", "reranks", "reranking", "text-rerank", "text_rerank"},
        "other": {"ig", "vg", "tts", "asr", "image-generation", "text-to-image", "text-to-speech", "automatic-speech-recognition"},
    }
    values = []
    for key in ("capabilities", "supported_endpoints", "supported_endpoint_types", "supportedGenerationMethods", "endpoints", "type", "model_type", "task", "task_type", "pipeline_tag"):
        value = item.get(key)
        if isinstance(value, dict):
            values.extend(k for k, enabled in value.items() if enabled is True)
        elif isinstance(value, list):
            values.extend(value)
        elif isinstance(value, str):
            values.append(value)
    values = {v.lower().strip("/").removeprefix("v1/") for v in values if isinstance(v, str)}
    capabilities = [kind for kind, names in aliases.items() if names & values]
    source = "metadata"
    identifier = (item.get("id") or item.get("model") or item.get("name") or "").strip()
    if not capabilities:
        source = "name"
        name = identifier.lower()
        if "rerank" in name:
            capabilities = ["rerank"]
        elif "embedding" in name or re.search(r"(?:^|[/_-])embed(?:$|[/_-])", name):
            capabilities = ["embedding"]
        elif re.search(r"(?:^|[/_-])(image|tts|asr|video|whisper|sora)(?:$|[/_-])", name):
            capabilities = ["other"]
        elif re.search(r"(?:^|/)(?:gpt-|chatgpt-|qwen|deepseek-|glm-|llama-|mistral-|claude-|gemini-|doubao-|moonshot-|kimi-|command-|o[134](?:-|$))", name):
            capabilities = ["base"]
        else:
            source = "unknown"
    return {"id": identifier, "capabilities": capabilities, "capability_source": source}


def discover_models(url, api_key="", api_protocol="auto"):
    """Read a bounded provider catalog; never persist credentials or configurations."""
    catalog_url = model_catalog_url(url, api_protocol)
    if not isinstance(api_key, str):
        raise ValueError("API Key 必须为文本。")
    protocol = detect_protocol(url, api_protocol)
    headers = {**protocol_headers(protocol, api_key), "Accept": "application/json"}
    found = {}
    deadline = monotonic() + 20
    params = {"page_size": 100} if urlsplit(catalog_url).path.endswith("/api/v1/models") else {}
    seen_cursors = set()
    truncated = False
    for page in range(1, 11):
        remaining = deadline - monotonic()
        if remaining <= 0:
            truncated = True
            break
        try:
            # Keep requests on the configured host; do not follow credentialed redirects.
            request_url = urlsplit(catalog_url)
            query = dict(parse_qsl(request_url.query, keep_blank_values=True))
            query.update(params)
            request_url = urlunsplit(request_url._replace(query=urlencode(query)))
            with requests.get(request_url, headers=headers, timeout=min(10, remaining), allow_redirects=False, stream=True) as response:
                status = response.status_code
                if status in {401, 403}:
                    raise ModelDiscoveryError("服务商鉴权失败，请核对 API Key 和接口地址；也可手动填写模型名称。")
                if status != 200:
                    raise ModelDiscoveryError(f"模型列表读取失败（HTTP {status}），服务商可能不支持此接口；可手动填写模型名称。")
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 4 * 1024 * 1024 or monotonic() > deadline:
                        raise ModelDiscoveryError("模型列表响应过大或超时，请手动填写模型名称。")
                    chunks.append(chunk)
                payload = json.loads(b"".join(chunks))
        except requests.RequestException:
            raise ModelDiscoveryError("无法连接模型列表接口或请求超时，请检查地址和网络；也可手动填写模型名称。") from None
        except (ValueError, UnicodeError):
            raise ModelDiscoveryError("服务商未返回有效的模型列表，可继续手动填写模型名称。") from None
        if not isinstance(payload, dict):
            raise ModelDiscoveryError("服务商未返回有效的模型列表，可继续手动填写模型名称。")
        output = payload.get("output") if isinstance(payload.get("output"), dict) else {}
        items = payload.get("data") if isinstance(payload.get("data"), list) else output.get("models")
        if items is None:
            items = payload.get("models")
        if not isinstance(items, list):
            raise ModelDiscoveryError("服务商未返回有效的模型列表，可继续手动填写模型名称。")
        before = len(found)
        for item in items:
            identifier = (item.get("id") or item.get("model") or item.get("name")) if isinstance(item, dict) else None
            if isinstance(identifier, str) and identifier.strip():
                classified = classify_model(item)
                existing = found.get(classified["id"])
                if not existing or existing["capability_source"] != "metadata":
                    found[classified["id"]] = classified
        if len(found) > 2000:
            found = dict(list(found.items())[:2000])
            truncated = True
            break
        page_token = payload.get("nextPageToken") or payload.get("next_page_token")
        if page_token:
            if not isinstance(page_token, str) or page_token in seen_cursors or len(found) == before:
                truncated = True
                break
            seen_cursors.add(page_token)
            params = {"pageToken" if protocol == "gemini" else "page_token": page_token}
        elif payload.get("has_more"):
            cursor = payload.get("last_id")
            if not isinstance(cursor, str) or not cursor or cursor in seen_cursors or len(found) == before:
                truncated = True
                break
            seen_cursors.add(cursor)
            params = {"after": cursor}
        elif isinstance(output.get("total"), int) and output["total"] > len(found):
            if len(found) == before:
                truncated = True
                break
            params = {"page_no": page + 1, "page_size": output.get("page_size", 20)}
        else:
            break
    else:
        truncated = True
    message = "已读取部分模型，可搜索选择或手动填写。" if truncated else "" if found else "服务商未返回模型，可手动填写模型名称。"
    return {"models": sorted(found.values(), key=lambda item: item["id"]), "partial": truncated, "message": message}
