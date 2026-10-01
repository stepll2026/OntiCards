
import requests
import json
from models.model_config import Model_configuration
from flask import current_app
from controllers.orcarouter.binding import resolve_model_config


def qian_wen_llm_stream(text,stream_type):
    # 获取当前 Flask app 实例
    app = current_app._get_current_object()
    # 显式添加 Flask 应用上下文
    with app.app_context():
        # 从数据库根据 model_class 查询模型配置
        model_config = Model_configuration.query.filter_by(model_class='base').first()

        if not model_config:
            raise ValueError("未找到 model_class 为 'base' 的模型配置")

        # 从数据库记录中获取所需参数
        # OrcaRouter 行存的是 base URL：由 model_class 推导具体端点，并用凭据 seam 解析 key
        api_url, api_key = resolve_model_config(model_config)
        model_name = model_config.model_name

        if api_key is None:
            raise ValueError(
                "OrcaRouter 账号需要重新授权（密钥已撤销或鉴权失败），请重新登录后再试"
            )

        headers = {
            'Authorization': 'Bearer ' + api_key,
            'Content-Type': 'application/json',
        }

        json_data = {
            'model': model_name,
            'messages': [
                # {
                #     'role': 'system',
                #     'content': 'You are a helpful assistant.',
                # },
                {
                    'role': 'user',
                    'content': text,
                },
            ],
            'stream': stream_type,
        }

        response = requests.post(api_url, headers=headers,
                                 json=json_data)
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                datas = line.decode('utf-8')[5:]
                try:
                    json_data = json.loads(datas)
                except:
                    json_data = ''
                if json_data != '':
                    yield json_data
                    # yield f"data: {json.dumps({'code': 200, 'data': {'type': 'modeling', 'content': ctext}}, ensure_ascii=False)}\n\n"

