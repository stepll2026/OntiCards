"""
 @File: 基础大语言模型_测试_含重试.py
 @Description: 模型调用封装-测试脚本
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-09-25 14:30
"""

import time
import requests

def llm_call(
        prompt: str,
        temperature: float = 0.7,
        timeout: int = 240,
        retries: int = 2) -> str:
    """

    Args:
        prompt (str): 用户输入
        temperature (float): 模型温度
        timeout (int): 请求超时时间
        retries (int): 重试次数

    Returns:
        str: 大模型返回结果
    """

    # 换为自己的api_key、api_url和 model_name
    api_key = 'xx'
    api_url = 'xx'
    model_name = 'xx'

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    # ！！！！！！！！【注意】！！！！！！！！
    # 此处的参数调用结构遵循标准的 OpenAI 规范
    # 若使用本地或私有化部署的大模型，请参考相关文档和实际调用方式修改参数结构

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


if __name__ == '__main__':
    print(llm_call("请用中文回答：你觉得梦想是什么？"))