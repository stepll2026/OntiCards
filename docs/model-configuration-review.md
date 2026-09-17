# 模型配置与接入

## 功能范围

- 基础地址自动补全对话、向量及重排序路径，同时支持完整接口地址。
- 读取服务商模型目录，按用途提示能力，支持选择和手动填写模型名称或接入点。
- 支持自动识别及手选 12 种协议，统一鉴权、请求、响应及流式处理。具体能力见 [协议兼容验收](mainstream-model-compatibility.md)。
- 提供普通连接与流式连接测试，以及向量维数、最大输出 Token 数和 Viking 参数配置。
- 业务调用复用适配层；模型协议及参数随预加载配置传递，检索向量标记查询用途。

## 数据库升级

已有环境在启动新版 API 前依次执行以下增量迁移：

1. [`20260916_model_protocol.sql`](../OntiCards_Api/scripts/migrations/20260916_model_protocol.sql)：添加 `api_protocol` 和 `embedding_dimensions`。
2. [`20260916_model_native_options.sql`](../OntiCards_Api/scripts/migrations/20260916_model_native_options.sql)：添加 `api_options`。

迁移可以重复执行。旧配置的协议默认为 `auto`，维数及扩展参数可以为空。新建环境使用已更新的 `init.sql`；已有环境仅执行上述增量迁移。更换向量模型或维数后，需按原流程重建向量索引。

## 验证

在仓库根目录运行：

```shell
python -m pytest OntiCards_Api/test/model_config -q
```

模型部分独立回归结果：**268 项通过**。覆盖配置读写、旧配置兼容、协议请求与响应、流式异常、模型目录、用途识别及本机 HTTP 收发。

前端测试位于 `OntiCards_Web/test/model-config.browser.cjs`，通过合成配置验证读取、选择、手填、用途过滤及测试反馈。实际服务调用已验证 DashScope；其他服务商通过协议测试，尚未使用各自的真实账号验证。
