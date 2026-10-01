import requests
from models.model_config import Model_configuration
from flask import current_app
from controllers.orcarouter.binding import resolve_model_config


def qwen_llm_embeddings(text):
    """
    Embedding 调用函数（保持原有接口兼容）

    返回：向量列表
    """
    vector, _ = qwen_llm_embeddings_with_usage(text)
    return vector


def qwen_llm_embeddings_with_usage(text):
    """
    Embedding 调用函数（带 Token 使用量统计）

    返回：(vector, usage_dict)
        - vector: 向量列表
        - usage_dict: Token 使用量信息
            {
                "total_tokens": int
            }
    """
    # 获取当前 Flask app 实例
    app = current_app._get_current_object()
    # 显式添加 Flask 应用上下文
    with app.app_context():
        model_config = Model_configuration.query.filter_by(model_class='embedding').first()

        if not model_config:
            raise ValueError("未找到 model_class 为 'embedding' 的模型配置")

        # 从数据库记录中获取所需参数
        # OrcaRouter 行存的是 base URL：由 model_class 推导具体端点，并用凭据 seam 解析 key
        api_url, api_key = resolve_model_config(model_config)
        model_name = model_config.model_name

        if api_key is None:
            raise ValueError(
                "OrcaRouter 账号需要重新授权（密钥已撤销或鉴权失败），请重新登录后再试"
            )

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
            'input': text ,
            'dimension': '1024',
            'encoding_format': 'float',
        }
        print(f"[DEBUG] model: {model_name}, input长度: {len(text)}")
        response = requests.post(api_url, headers=headers, json=json_data)
        parsed_data = response.json()

        # 检查 API 响应状态
        if not response.ok:
            print(f"[ERROR] Embedding API 返回错误:")
            print(f"  status_code: {response.status_code}")
            print(f"  response: {parsed_data}")
            raise Exception(f"Embedding API 返回错误: {response.status_code}, {parsed_data}")

        # 检查响应格式
        if "data" not in parsed_data:
            print(f"[ERROR] Embedding API 响应缺少 data 字段:")
            print(f"  status_code: {response.status_code}")
            print(f"  response: {parsed_data}")
            raise Exception(f"Embedding API 响应格式异常: {parsed_data}")

        embedding_vector = parsed_data["data"][0]["embedding"]

        # 提取 usage
        usage = parsed_data.get("usage", {})
        usage_dict = {
            "total_tokens": usage.get("total_tokens", 0)
        }

        return embedding_vector, usage_dict