# 批量删除失败回归验证

## 修复了什么

批量删除原来吞掉单条异常并无条件返回 True；现在继续尝试后续 UUID，逐条记录失败 UUID、异常类型/信息（或 SDK 返回 False），输出成功和失败计数。只有全部请求获 SDK 成功确认时返回 True，部分或全部失败返回 False。沿用现有 bool 契约，没有增加返回对象或修改跨模块事务。

## 有什么作用

现有检查 bool 的清理调用方可以识别未全部完成，关系卡片清理也传递 False，维护者可从日志区分部分完成和全部失败。

## 验证结果

基线 main：d7d0336ef5fbd1b3a1c1fce57a88d8c4f2cb3160。kol-stage2 主机 Python 3.12.3，在唯一目录 /tmp/onti-issue62-0f569596 执行 `python3 test_doc_id_cleanup.py`。测试解析完整生产文件、原样编译目标函数，以内存替身替换 Weaviate 边界，无凭据、模型或数据库连接。

- [基线失败日志](red.log)：新增测试在原函数上运行 12 项，4 项失败，均为失败仍返回 True（exit 1）。
- [修复后日志](green.log)：12 项通过（exit 0）。包括单条异常后继续、SDK False、全部失败、全部成功、关系清理传播失败、空输入和缺失 collection、原有分页清理测试。
- [远端实测源码摘要](tested-files.sha256)：对应生产文件和测试文件。
- 没有运行 GitHub hosted CI，没有 UI 改动，无截图要求。
- SDK 返回语义参考 [Weaviate 官方删除文档](https://docs.weaviate.io/weaviate/manage-objects/delete)：Python delete_by_id 可因 404 返回 False。

独立审查的固定 head/base、结果与清理回执在 PR 正文和原工单报告记录。

## 剩余限制

没有运行真实 Weaviate 服务、网络故障注入或整个应用；SDK 成功响应不能证明对象原先存在或后续无并发写入。False 包括 SDK 未确认删除（例如不存在的 UUID），不引入自动重试。原有忽略返回值的调用方仍忽略返回值，跨数据库清理顺序不在本次模块内修复范围。

本轮只新增上述远端目录及其中两份源码、日志、摘要；使用主机 Python，新增镜像/容器/网络/卷均为 0，未操作共享服务。证据取回及独立审查结束后定向移除远端目录，保留本地任务分支和证据。
