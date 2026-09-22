# 豆包协议兼容测试

日期：2026-09-16。仅使用合成凭据和响应做协议验证，未使用豆包专用账号执行真实推理。

## 当前结论

豆包专项 40 项测试全部通过。覆盖普通对话、SSE 流式、标准文本向量、Ark 多模态向量的文本输入，以及 Viking 原生重排。

- 普通对话和标准文本向量：选择自动识别或 OpenAI 兼容，基础地址填写 `https://ark.cn-beijing.volces.com/api/v3`，模型名称和 `ep-` 接入点均可手填。
- 多模态向量：已知多模态向量名称或完整 `/embeddings/multimodal` 路径可自动识别；不透明接入点可选择“豆包多模态向量”。平台发送文本类型输入，解析 `data.embedding`。
- Viking 重排：选择对应协议，填写 AK、SK、地域和可选接入点。使用 `datas` / `rerank_model` 及 V4 签名；将分数映射回原文档索引后排序。
- 目录：尝试兼容目录，服务不提供时明确提示手填；没有将管理接口 `ListEndpoints` 冒充运行时 `/models`。
- 用途：目录能力字段作为元数据依据；名称提示标记为推测，未知 `ep-` 保留手填，连接测试验证实际用途。

原生重排使用 `auto/viking` 配置；手选 OpenAI 时保留 OpenAI 网关语义，用户的显式协议选择优先。

真实账号的权限、地域、模型开通状态、维数支持及生成质量仍需专用凭据验证。更多协议与完整测试范围见 [主流模型兼容验收](mainstream-model-compatibility.md)。

复现：`python -m pytest OntiCards_Api/test/model_config/test_doubao_contract.py -q`。

## 官方依据

方舟 SDK 核对版本：`volcengine/volcengine-python-sdk@3b116781c5b8bb648f215b29587f2ec74d9e5d02`。

- [方舟基础地址](https://github.com/volcengine/volcengine-python-sdk/blob/3b116781c5b8bb648f215b29587f2ec74d9e5d02/volcenginesdkarkruntime/_constants.py)
- [普通和流式对话请求](https://github.com/volcengine/volcengine-python-sdk/blob/3b116781c5b8bb648f215b29587f2ec74d9e5d02/volcenginesdkarkruntime/resources/chat/completions.py)
- [文本向量请求](https://github.com/volcengine/volcengine-python-sdk/blob/3b116781c5b8bb648f215b29587f2ec74d9e5d02/volcenginesdkarkruntime/resources/embeddings.py)
- [多模态向量请求](https://github.com/volcengine/volcengine-python-sdk/blob/3b116781c5b8bb648f215b29587f2ec74d9e5d02/volcenginesdkarkruntime/resources/multimodal_embeddings.py)与[响应](https://github.com/volcengine/volcengine-python-sdk/blob/3b116781c5b8bb648f215b29587f2ec74d9e5d02/volcenginesdkarkruntime/types/multimodal_embedding/embedding_response.py)
- [方舟管理接口 ListEndpoints](https://github.com/volcengine/volcengine-python-sdk/blob/3b116781c5b8bb648f215b29587f2ec74d9e5d02/volcenginesdkark/api/ark_api.py)
- [Viking 知识库原生重排及签名](https://github.com/volcengine/volc-sdk-python/blob/main/volcengine/viking_knowledgebase/VikingKnowledgeBaseService.py)，2026-09-16 核对。
