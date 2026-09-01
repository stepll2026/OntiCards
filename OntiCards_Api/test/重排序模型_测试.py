"""
 @File: 重排序模型_测试.py
 @Description: 模型调用封装-测试脚本
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-09-25 14:30
"""

import requests

def QwenRerank_llm(query, documents, top_n):
    # 从数据库记录中获取所需参数
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

    # 千问系列的重排序模型请求参数结构
    json_data = {
        'model': model_name,
        'input': {
            'query': query,
            'documents': documents
            ,
        },
        'parameters': {
            'return_documents': True,
            'top_n': top_n,
        },
    }

    # 其他的重排序模型，如本地或私有化部署的，可能的请求参数结构如下：
    # json_data = {
    #     'model': model_name,
    #     'query': query,
    #     'documents': documents,
    #     'return_documents': True,
    #     'top_n': top_n
    # }

    response = requests.post(
        api_url,
        headers=headers,
        json=json_data,
    )
    datas = response.json()

    return datas

if __name__ == '__main__':
    raw = QwenRerank_llm(
        "苹果手机的价格",
        [
            "苹果最新发布了iPhone 15，售价5999元起。",
            "小米手机价格更便宜，性价比更高。",
            "苹果是一种水果，富含维生素。",
            "iPhone 的 Pro 版本售价7999元起。"
        ],
        3
    )

    # 1. 取出 results
    results = raw["output"]["results"]

    # 2. 输出格式化结果
    print("=== 排序结果 ===")
    for rank, item in enumerate(results, start=1):
        text = item["document"]["text"]
        score = item["relevance_score"]
        index = item["index"]   # 原始 documents 里的下标
        print(f"\n第 {rank} 名：")
        print(f"  原始下标：{index}")
        print(f"  相关性得分：{score:.4f}")
        print(f"  文本：{text}")
