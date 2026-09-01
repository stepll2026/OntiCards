"""
 @File: 基础大语言模型_测试.py
 @Description: 模型调用封装-测试脚本
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-09-25 14:30
"""

import requests

def qian_wen_llm(text,stream_type):

        # 换为自己的api_key、api_url和 model_name
        api_key = 'xx'
        api_url = 'xx'
        model_name = 'xx'

        headers = {
            'Authorization': 'Bearer ' + api_key,
            'Content-Type': 'application/json',
        }

        # ！！！！！！！！【注意】！！！！！！！！
        # 此处的参数调用结构遵循标准的 OpenAI 规范
        # 若使用本地或私有化部署的大模型，请参考相关文档和实际调用方式修改参数结构

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

        response = requests.post(api_url, headers=headers,json=json_data)

        return response.json()

if __name__ == '__main__':
    print(qian_wen_llm('请用中文回答：你觉得梦想是什么？', stream_type=False)["choices"][0]["message"]["content"]) # 0 / Flase : 非流式返回)