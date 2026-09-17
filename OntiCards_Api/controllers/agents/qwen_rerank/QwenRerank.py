import requests
from models.model_config import Model_configuration
from flask import current_app
from controllers.model_config.model_protocols import model_request, rerank_result


def QwenRerank_llm(query, documents, top_n):
    """Return the provider response; existing output/results consumers keep working."""
    app = current_app._get_current_object()
    with app.app_context():
        model_config = Model_configuration.query.filter_by(model_class='rerank').first()
        if not model_config:
            raise ValueError("未找到 model_class 为 'rerank' 的模型配置")
        url, headers, payload, protocol = model_request(model_config, "rerank", query, documents=documents, top_n=top_n)
        response = requests.post(url, headers=headers, json=payload, timeout=(10, 180), allow_redirects=False)
        try:
            response.raise_for_status()
            result = response.json()
            if protocol == "viking":
                ranked, usage = rerank_result(result, len(documents))
                return {"results": ranked[:top_n], "usage": usage}
            return result
        finally:
            response.close()


def QwenRerank_llm_with_usage(query, documents, top_n):
    response = QwenRerank_llm(query, documents, top_n)
    results, usage = rerank_result(response, len(documents))
    return results, {"total_tokens": usage.get("total_tokens", 0)}
