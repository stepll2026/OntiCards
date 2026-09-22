# 主流模型协议兼容验收

## 改动范围

本轮集中于模型接入与模型设置：统一地址补全、鉴权、请求字段、响应解析、流式事件、模型目录和用途提示。查询、并行任务、报告、向量检索和连接测试共用适配层。原有数据库查询规则、NULL/零值过滤及查询进度交互沿用原行为。

新增可空 `model_config.api_options` 字段，保存最大输出 Token 数及 Viking 的 AK、地域、接入点。Viking 的 SK 复用密钥字段；日志省略含模型密钥的响应。旧配置和完整自定义地址继续可用。

## 验收清单

“通过”指依据官方接口文档/SDK构造的协议与 HTTP 测试通过，不表示已使用各服务商的真实账号调用。

| 协议 | 对话 / 流式 | 文本向量 | 重排序 | 模型目录 |
| --- | --- | --- | --- | --- |
| OpenAI Chat Completions / 兼容服务 | 通过 | 通过 | 通用重排格式通过 | 标准目录及分页通过 |
| OpenAI Responses | 通过 | 不提供 | 不提供 | 标准目录通过 |
| DashScope 原生 | 通过 | 通过 | 通过 | 原生目录及分页通过 |
| Anthropic Claude Messages | 通过 | 不提供 | 不提供 | 目录及分页通过 |
| Google Gemini | 通过 | 通过 | 不提供 | 目录、用途及分页通过 |
| Ollama | NDJSON 流式通过 | 新旧向量接口通过 | 不提供 | 本地模型列表通过 |
| Cohere | V2 SSE / V1 NDJSON 通过 | 通过 | 通过 | 目录、用途及分页通过 |
| 豆包 Ark 多模态向量 | 使用兼容对话协议 | 文本输入及对象响应通过 | 不提供 | 按服务可用性读取；支持手填 |
| Viking / 豆包原生重排 | 不提供 | 不提供 | AK/SK 签名、分数索引及排序通过 | 手动填写模型及接入点 |
| Jina | 不提供 | 通过 | 通过 | 按服务可用性读取；支持手填 |
| Voyage AI | 不提供 | 通过 | 通过 | 按服务可用性读取；支持手填 |
| Azure OpenAI | 兼容对话格式 | 通过 | 不提供 | 部署地址使用手填；保留 api-version |

OpenAI 兼容协议同时覆盖 DeepSeek、豆包对话、通义、智谱 GLM、Moonshot/Kimi、MiniMax、硅基流动及本地兼容服务的请求格式。Gemini 的 `/v1beta/openai` 基础地址也可补全路径。服务商实际支持的模型、地域、维数和额度以其服务为准。

## 行为约定

- 手选协议优先；自动识别依据已知域名和原生路径。未知代理地址仍可手选协议、填写完整 URL。
- 目录优先使用用途元数据；名称推测明确标记，未知接入点保留手填。目录不可用时提示原因，不伪造可用模型。
- Cohere、Gemini、Jina、Voyage 区分检索问题与入库文本。更换向量模型或维数后需按原流程重建索引。
- 普通文本、推理内容和 Token 用量分别归一化；不将推理内容当作最终答案。原生流中途报错或未正常结束时，连接测试判为失败。
- 拒绝不支持的协议用途、无效向量和越界/重复重排索引。重排返回的分数对应原候选文档，Viking 在完整评分后取 Top N。
- 模型测试仅发送固定少量文本；不写模型配置、不访问业务数据库内容或向量索引。带鉴权请求不自动跟随重定向。

## 验证方法

后端：`python -m pytest test/model_config -q`。覆盖实际业务调用函数、配置 CRUD、旧配置、标准/原生流、异常响应、模型目录分页及本机 HTTP 服务收发。Viking 固定签名另与官方 Python SDK 1.0.228 独立计算结果核对。

前端：`node test/model-config.browser.cjs`。使用合成配置拦截 API，验证读取、选择、手填、用途过滤、协议、维数、原生参数保存及测试反馈，不修改线上配置。

真实服务回归使用服务器已有通义账号。其他服务商尚未提供专用测试凭据，其鉴权权限、模型可用性、实际生成质量和延迟不属于本次协议测试证明的范围。

## 官方依据

- [OpenAI Responses](https://developers.openai.com/api/reference/python/resources/responses/methods/create)
- [Anthropic Messages](https://platform.claude.com/docs/en/api/messages/create)
- [Gemini 内容生成](https://ai.google.dev/api/generate-content)、[向量](https://ai.google.dev/api/embeddings)、[兼容接口](https://ai.google.dev/gemini-api/docs/openai)
- [Ollama Chat](https://docs.ollama.com/api/chat)、[Embed](https://docs.ollama.com/api/embed)
- [Cohere Chat](https://docs.cohere.com/v2/reference/chat)、[Embed](https://docs.cohere.com/v2/reference/embed)、[Rerank](https://docs.cohere.com/v2/reference/rerank)
- [Ark 官方 Python SDK](https://github.com/volcengine/volcengine-python-sdk/tree/3b116781c5b8bb648f215b29587f2ec74d9e5d02/volcenginesdkarkruntime)
- [Viking 重排](https://www.volcengine.com/docs/84313/2288345)、[签名实现](https://github.com/volcengine/volc-sdk-python/blob/main/volcengine/auth/SignerV4.py)
- [Jina](https://jina.ai/embeddings/)、[Voyage](https://docs.voyageai.com/reference/embeddings-api)、[Azure OpenAI](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/reference?view=foundry-classic)
- [MiniMax OpenAI 兼容接口](https://platform.minimax.io/docs/api-reference/text-chat-openai)
