"""
 @File: 向量化嵌入模型_测试.py
 @Description: 模型调用封装-测试脚本
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-09-25 14:30
"""

import requests

def qwen_llm_embeddings(text):

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
        'input': text,
        'dimension': '1024',
        'encoding_format': 'float',
    }
    response = requests.post(api_url, headers=headers, json=json_data)
    parsed_data = response.json()
    embedding_vector = parsed_data["data"][0]["embedding"]
    return embedding_vector

if __name__ == "__main__":
    print(qwen_llm_embeddings("hello world"))