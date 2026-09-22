import requests
from models.model_config import Model_configuration
from flask import current_app
from controllers.model_config.model_protocols import model_request, normalize_chat, iter_chat_events


def qian_wen_llm_stream(text, stream_type):
    app = current_app._get_current_object()
    with app.app_context():
        model_config = Model_configuration.query.filter_by(model_class='base').first()
        if not model_config:
            raise ValueError("未找到 model_class 为 'base' 的模型配置")
        url, headers, payload, protocol = model_request(model_config, "base", text, stream=stream_type)
        response = requests.post(url, headers=headers, json=payload, stream=bool(stream_type), timeout=(10, 180), allow_redirects=False)
        try:
            response.raise_for_status()
            if stream_type:
                yield from iter_chat_events(response, protocol)
            else:
                yield normalize_chat(response.json(), protocol)
        finally:
            response.close()
