# PR #50 本轮验证记录（候选修正，尚未交付）

## 修复了什么

原补丁使用反向引用重复第一个 token，导致普通的 `column > 0` 也不能保存，同时漏掉单条件更新、预览和历史条件执行。候选修正使用有限表达式语法校验，覆盖新增、更新、预览及执行；只替换裸 column 占位符，保留字符串和已引用标识符，并转义列名中的引用符。

## 有什么作用

在拼接治理条件前阻断语句逃逸和任意函数调用，允许比较、范围、枚举、逻辑、算术及白名单函数。治理模块内的新增和更新共用校验，避免只保护部分入口。

## 验证结果

基线 main：`2e597d05f3673891f9ffdef08e2c45084dbd42dc`。原贡献：`047851848fca3962571197e01274945e267df06f`。已普通合入 main，保留贡献者原历史。

实测均在 kol-stage2：原贡献回归负对照失败（15 个失败子例、1 个类型错误）；候选条件测试 3 项、Flask/SQLite 测试 6 项、现有方言测试 31 项通过。基线 SQL 对照表明，同一两行数据的违规数可以被额外子查询从 1 改成 0。

执行入口：

```sh
python controllers/governance/test_condition_security.py
python controllers/governance/test_condition_api.py
python controllers/governance/test_dialect_adapter.py
```

Flask/SQLite 测试使用既有 API 镜像 `sha256:4d712690199b17ea76030095e97037b2b656bf6fba502c06fe79a0367e195f63`，只读挂载候选源码、无网络、临时 /tmp、删除 capabilities。数据库查询/所有权和写入会话使用合成 fixture；生成的 SQL 在真实内存 SQLite 上执行。文件摘要见 [tested-files.sha256](tested-files.sha256)，各项完整结果见本目录对应日志；独立终审尚未完成。

## 剩余限制

候选语法目前不接受子查询、窗口函数、类型转换或含反斜线的字符串，需要在独立审查中核实这些限制对现有模板和历史规则的影响，不能视为已可交付。未进行 PostgreSQL/MySQL 等真实引擎测试、完整应用部署、模型调用或托管 CI。

显式确认的完整 SQL（sql_text/sql_preview）是现有独立功能；本变更只约束条件表达式，不能宣称完整 SQL 输入或数据源权限已获得沙箱保护。未改 UI，无截图要求。远端临时源码待审查结束后清理，本轮未新增镜像、持久卷或网络。
