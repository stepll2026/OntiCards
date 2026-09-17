import requests
from models.model_config import Model_configuration
from flask import current_app
from controllers.model_config.model_protocols import model_request, embedding_result


def qwen_llm_embeddings(text, purpose="document"):
    vector, _ = qwen_llm_embeddings_with_usage(text, purpose=purpose)
    return vector


def qwen_llm_embeddings_with_usage(text, purpose="document"):
    """Preserve the (vector, usage) contract for compatible and native services."""
    app = current_app._get_current_object()
    with app.app_context():
        model_config = Model_configuration.query.filter_by(model_class='embedding').first()
        if not model_config:
            raise ValueError("未找到 model_class 为 'embedding' 的模型配置")
        url, headers, payload, _ = model_request(model_config, "embedding", text, purpose=purpose)
        response = requests.post(url, headers=headers, json=payload, timeout=(10, 180), allow_redirects=False)
        try:
            response.raise_for_status()
            vector, usage = embedding_result(response.json(), getattr(model_config, "embedding_dimensions", None))
            return vector, {"total_tokens": usage.get("total_tokens", 0)}
        finally:
            response.close()
