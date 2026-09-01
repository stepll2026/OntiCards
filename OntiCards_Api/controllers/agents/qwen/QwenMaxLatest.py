
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from models.model_config import Model_configuration
from flask import current_app
import time
import logging

logger = logging.getLogger(__name__)

# ============ 连接池配置 ============
# 创建全局 session，使用连接池复用 TCP 连接
_http_session = None


def _get_session(timeout=180, max_retries=3, backoff_factor=1.0):
    """
    获取复用了连接池的 requests Session

    Args:
        timeout: 单次请求超时时间（秒）
        max_retries: 最大重试次数
        backoff_factor: 重试间隔基数（秒），实际间隔 = backoff_factor * (2 ** 重试次数)

    特点：
    1. 连接池复用 TCP 连接，避免每次请求的握手开销
    2. 自动重试机制处理临时性错误
    3. 合理的超时机制，避免无限等待
    """
    global _http_session

    if _http_session is None:
        _http_session = requests.Session()

        # 配置重试策略
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],  # 这些状态码会触发重试
            allowed_methods=["POST", "GET"],
            raise_on_status=False,  # 不抛出异常，由我们处理
        )

        # 配置适配器，绑定连接池参数
        adapter = HTTPAdapter(
            pool_connections=10,      # 连接池中保持的连接数
            pool_maxsize=20,           # 连接池最大连接数
            max_retries=retry_strategy,
        )

        _http_session.mount("http://", adapter)
        _http_session.mount("https://", adapter)

        # 设置默认超时
        _http_session.timeout = timeout

    return _http_session


def _request_with_timing(method, url, timeout, max_retries, backoff_factor, **kwargs):
    """
    执行带详细计时的 HTTP 请求

    Returns:
        (response_dict, timing_info)
    """
    timing = {
        "total_ms": 0,
        "retry_count": 0,
        "final_status_code": None,
    }

    start_time = time.time()

    try:
        session = _get_session(timeout=timeout, max_retries=max_retries, backoff_factor=backoff_factor)

        # 使用 session 发送请求（已内置重试逻辑）
        response = session.request(method, url, timeout=timeout, **kwargs)

        timing["total_ms"] = int((time.time() - start_time) * 1000)
        timing["final_status_code"] = response.status_code

        # 尝试解析 JSON
        try:
            return response.json(), timing
        except Exception:
            # 非 JSON 响应，包装成统一格式
            return {"error": f"非 JSON 响应 (status={response.status_code})", "text": response.text[:500]}, timing

    except requests.exceptions.Timeout:
        timing["total_ms"] = int((time.time() - start_time) * 1000)
        timing["error"] = "请求超时"
        return {"error": "LLM 请求超时，请稍后重试", "timeout_seconds": timeout}, timing

    except requests.exceptions.ConnectionError as e:
        timing["total_ms"] = int((time.time() - start_time) * 1000)
        timing["error"] = "连接错误"
        return {"error": f"LLM 服务连接失败: {str(e)[:100]}", "connection_error": True}, timing

    except Exception as e:
        timing["total_ms"] = int((time.time() - start_time) * 1000)
        timing["error"] = str(e)
        return {"error": f"LLM 请求异常: {str(e)[:100]}"}, timing


def qian_wen_llm(text, stream_type, model_config_dict=None):
    """
    LLM 调用函数（保持原有接口兼容）

    优化点：
    1. 连接池复用 TCP 连接，减少握手开销
    2. 超时机制，避免无限等待
    3. 自动重试，处理临时性错误（429/5xx）

    Args:
        text: 输入文本
        stream_type: 是否流式输出
        model_config_dict: 可选的模型配置字典，用于避免在线程中访问数据库
            {
                "api_key": str,
                "api_url": str,
                "model_name": str
            }

    返回：API 原始响应 dict（与原来完全一致）
    """
    # 如果传入了配置字典，直接使用（避免访问数据库）
    if model_config_dict:
        api_key = model_config_dict.get("api_key")
        api_url = model_config_dict.get("api_url")
        model_name = model_config_dict.get("model_name")
        # 支持在配置中自定义超时
        timeout = model_config_dict.get("timeout", 360)
    else:
        # 获取当前 Flask app 实例
        app = current_app._get_current_object()
        # 显式添加 Flask 应用上下文
        with app.app_context():
            # 从数据库读取 API key（依赖 Flask 上下文）
            model_config = Model_configuration.query.filter_by(model_class='base').first()

            if not model_config:
                raise ValueError("未找到 model_class 为 'base' 的模型配置")

            # 从数据库记录中获取所需参数
            api_key = model_config.model_api_key
            api_url = model_config.url
            model_name = model_config.model_name
            # 支持在配置中自定义超时
            timeout = getattr(model_config, 'timeout', 180)

    # 判断 api_key 是否为空
    if api_key and api_key.strip() and api_key.lower() != 'null':
        headers = {
            'Authorization': 'Bearer ' + api_key,
            'Content-Type': 'application/json',
        }
    else:
        headers = {
            'Content-Type': 'application/json',
        }

    json_data = {
        'model': model_name,
        'messages': [
            {
                'role': 'user',
                'content': text,
            },
        ],
        'stream': stream_type,
    }

    # 执行请求（带超时和重试）
    response, timing = _request_with_timing(
        "POST",
        api_url,
        timeout=timeout,
        max_retries=3,
        backoff_factor=1.0,
        headers=headers,
        json=json_data,
    )

    # 记录详细日志
    if timing.get("error"):
        logger.warning(f"[LLM] 请求失败: {timing['error']}, 耗时: {timing['total_ms']}ms")
    elif timing.get("final_status_code") and timing["final_status_code"] != 200:
        logger.warning(f"[LLM] 请求返回非 200 状态码: {timing['final_status_code']}, 耗时: {timing['total_ms']}ms")
    else:
        logger.info(f"[LLM] 请求成功, 耗时: {timing['total_ms']}ms")

    # 如果返回的是错误响应（非 200），包装成与原来一致的格式
    if timing.get("final_status_code") and timing["final_status_code"] != 200:
        # 模拟原来的 requests.post().json() 返回格式
        error_msg = response.get("error", f"HTTP {timing['final_status_code']}")
        return {
            "error": error_msg,
            "choices": [{"message": {"content": f"请求失败: {error_msg}"}, "finish_reason": "error"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }

    # 如果返回的是我们自定义的错误格式，也转成与原来一致的格式
    if "error" in response and "choices" not in response:
        return {
            "error": response.get("error", "未知错误"),
            "choices": [{"message": {"content": response.get("error", "未知错误")}, "finish_reason": "error"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }

    return response


def qian_wen_llm_with_usage(text, stream_type=False, model_config_dict=None):
    """
    LLM 调用函数（带 Token 使用量统计）

    优化点：
    1. 连接池复用 TCP 连接
    2. 超时机制
    3. 自动重试

    Args:
        text: 输入文本
        stream_type: 是否流式输出
        model_config_dict: 可选的模型配置字典

    返回：(content, usage_dict) - 与原来完全一致
        - content: LLM 返回的文本内容
        - usage_dict: Token 使用量信息
            {
                "prompt_tokens": int,
                "completion_tokens": int,
                "total_tokens": int,
                "generation_ms": int  # LLM 生成耗时（毫秒）
            }
    """
    start_time = time.time()

    response = qian_wen_llm(text, stream_type, model_config_dict)

    # 提取 content（兼容错误响应格式）
    choices = response.get("choices", [{}])
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message", {})
        content = message.get("content", "") if isinstance(message, dict) else str(message)
    else:
        content = ""

    # 提取 usage
    usage = response.get("usage", {})
    usage_dict = {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "generation_ms": int((time.time() - start_time) * 1000)
    }

    return content, usage_dict


def reset_session():
    """
    重置全局 session（用于测试或配置变更后重新初始化）
    """
    global _http_session
    _http_session = None
