
import requests
from models.model_config import Model_configuration
from flask import current_app


def QwenRerank_llm(query, documents, top_n):
    """
    Rerank 调用函数（保持原有接口兼容）

    返回：API 原始响应 dict
    """
    # 获取当前 Flask app 实例
    app = current_app._get_current_object()
    # 显式添加 Flask 应用上下文
    with app.app_context():
        # 从数据库读取 API key（依赖 Flask 上下文）
        model_config = Model_configuration.query.filter_by(model_class='rerank').first()

        if not model_config:
            raise ValueError("未找到 model_class 为 'rerank' 的模型配置")

        # 从数据库记录中获取所需参数
        api_key = model_config.model_api_key
        api_url = model_config.url
        model_name = model_config.model_name

        # 判断 api_key 是否为空
        print(f"[DEBUG] Rerank 配置检查 - api_key: '{api_key}', url: '{api_url}', model: '{model_name}'")
        if api_key and api_key.strip() and api_key.lower() != 'null':
            headers = {
                'Authorization': 'Bearer ' + api_key,
                'Content-Type': 'application/json',
            }
            # api_key 不为空时，使用原有的 json_data 结构
            json_data = {
                'model': model_name,
                'input': {
                    'query': query,
                    'documents': documents,
                },
                'parameters': {
                    'return_documents': True,
                    'top_n': top_n,
                },
            }
        else:
            headers = {
                'Content-Type': 'application/json',
            }
            # api_key 为空时，使用简化的 json_data 结构
            json_data = {
                'model': model_name,
                'query': query,
                'documents': documents,
                'return_documents': True,
                'top_n': top_n
            }

        print(f"[DEBUG] Rerank 请求体: {json_data}")

        response = requests.post(
            api_url,
            headers=headers,
            json=json_data,
        )
        datas = response.json()

        return datas


def QwenRerank_llm_with_usage(query, documents, top_n):
    """
    Rerank 调用函数（带 Token 使用量统计）

    返回：(results, usage_dict)
        - results: API 原始响应中的 results 列表
        - usage_dict: Token 使用量信息
            {
                "total_tokens": int
            }
    """
    response = QwenRerank_llm(query, documents, top_n)

    # 调试：打印 API 响应结构
    print(f"[DEBUG] Rerank API 响应 keys: {list(response.keys()) if isinstance(response, dict) else 'not dict'}")
    print(f"[DEBUG] Rerank API 响应: {response}")

    # 尝试多种可能的结果字段路径
    results = None
    if isinstance(response, dict):
        # 尝试 path1: output.results
        results = response.get("output", {}).get("results")
        if results is not None:
            print(f"[DEBUG] 使用路径 output.results")

        # 尝试 path2: results (顶层)
        if results is None:
            results = response.get("results")
            if results is not None:
                print(f"[DEBUG] 使用路径 results (顶层)")

        # 尝试 path3: output.output (某些 API 结构)
        if results is None and "output" in response:
            output_val = response.get("output")
            if isinstance(output_val, dict):
                results = output_val.get("results") or output_val.get("output")
                if results is not None:
                    print(f"[DEBUG] 使用路径 output.output 或 output.results")

        # 尝试 path4: data.results
        if results is None:
            results = response.get("data", {}).get("results")
            if results is not None:
                print(f"[DEBUG] 使用路径 data.results")

    if results is None:
        results = []

    # 提取 usage
    usage = {}
    if isinstance(response, dict):
        usage = response.get("usage", {})
        # 尝试其他可能的 usage 路径
        if not usage and "output" in response:
            usage = response.get("output", {}).get("usage", {})
        if not usage and "data" in response:
            usage = response.get("data", {}).get("usage", {})

    usage_dict = {
        "total_tokens": usage.get("total_tokens", 0) if isinstance(usage, dict) else 0
    }

    print(f"[DEBUG] 最终提取的 results 数量: {len(results) if results else 0}")
    print(f"[DEBUG] 最终提取的 usage: {usage_dict}")

    return results if results else [], usage_dict