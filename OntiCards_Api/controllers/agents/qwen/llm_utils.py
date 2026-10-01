"""
 @File: llm_utils.py
 @Description: 模型调用封装
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-09-25 14:30
"""

import requests
import json
import time

from flask import current_app
from extensions.ext_database import db
from models.model_config import Model_configuration
from controllers.orcarouter.binding import resolve_model_config


def llm_call(
        prompt: str,
        temperature: float = 0.7,
        timeout: int = 240,
        retries: int = 2) -> str:
    """
    General-purpose LLM call function with configurable parameters.
    所有配置信息（api_key, api_url, model_name）都从数据库中读取。
    
    注意：此函数必须在 Flask 应用上下文中调用。

    Args:
        prompt (str): User prompt
        temperature (float): Sampling temperature
        timeout (int): Timeout per request (seconds)
        retries (int): Retry count on failure

    Returns:
        str: LLM-generated content or fallback safe string
    """
    # 从数据库根据 model_class 查询模型配置
    # 使用 db.session 确保在应用上下文中正确工作
    try:
        model_config = db.session.query(Model_configuration).filter_by(model_class='base').first()
    except RuntimeError as e:
        # 如果没有应用上下文，提供更清晰的错误信息
        raise RuntimeError(f"llm_call 需要在 Flask 应用上下文中调用: {e}")

    if not model_config:
        raise ValueError("未找到 model_class 为 'base' 的模型配置")

    # 从数据库记录中获取所需参数
    # OrcaRouter 行存的是 base URL：由 model_class 推导具体端点，并用凭据 seam 解析 key
    api_url, api_key = resolve_model_config(model_config)
    model_name = model_config.model_name

    # key 为 None 表示该 OrcaRouter 账号已被标记为 needs_reauth（密钥被撤销或返回 401），
    # 这里明确失败，避免继续使用已失效的凭据。
    if api_key is None:
        raise ValueError(
            "OrcaRouter 账号需要重新授权（密钥已撤销或鉴权失败），请重新登录后再试"
        )

    # 判断 api_key 是否为空
    if api_key and api_key.strip() and api_key.lower() != 'null':
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }
    else:
        headers = {
            'Content-Type': 'application/json',
        }

    payload = {
        'model': model_name,
        'messages': [
            {
                'role': 'user',
                'content': prompt
            }
        ],

        'temperature': temperature,
    }

    for attempt in range(retries + 1):
        try:
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except requests.exceptions.Timeout:
            print(f"[WARN] LLM request timed out (attempt {attempt + 1}/{retries})")
        except Exception as e:
            print(f"[ERROR] LLM request failed (attempt {attempt + 1}/{retries}): {e}")

        time.sleep(2)  # wait before retry

    # Fallback: ensure downstream JSON parsing won't crash
    return '{"error": "LLM call failed after retries."}'
