# 治理检测完整 SQL 的只读边界

这是 Issue #60 / PR #50 的后续加固。条件表达式仍按原有规则校验；完整 SQL 使用同一固定版本 SQLGlot（30.29.0）和内建表达式白名单，保持输入原文，不做方言转换。

保存（手动、模板、AI 的 sql_text / sql_preview，包括 rule_config.sql_preview）、更新和预览会检查传入的完整 SQL。已有规则在检测执行及失败样本提取前重新检查，避免历史数据绕过校验。失败样本实际生成的 SQL 也再次检查。PostgreSQL / Kingbase 保留原有数据库只读事务保护，并回读确认状态；无法建立只读事务时拒绝执行。

允许单条受支持的 SELECT 查询、只读 CTE、UNION / INTERSECT / EXCEPT、引用子查询、日期和正则表达式、窗口及聚合统计；可以有一个结尾分号。检测结果仍由原有执行器解释，因此统计查询应返回 total_count、failed_count 等原有约定字段。例如：
```sql
SELECT COUNT(*) AS total_count,
       SUM(CASE WHEN price < 0 THEN 1 ELSE 0 END) AS failed_count
FROM items;
```

拒绝多语句、事务和会话控制、写入 CTE、SELECT INTO / 文件输出、行锁、变量赋值、外部表函数、自定义或限定名称的函数、引用函数名及未列入白名单的结构。完整 SQL 当前也不支持注释、查询提示、超过 65536 字符 / 4096 token / 64 层括号的输入。拒绝时返回“完整 SQL 必须是受支持的单条只读查询”及原因；不会静默执行未识别的结构。

AST 校验不能判定目标数据库中内建函数名称是否被用户重载，数据库只读事务是额外保护；这不替代只读账号权限，也不限制查询耗时、锁等待或所有数据库外部副作用。其他数据库沿用原有连接方式，不能宣称已获得 PostgreSQL 同等的事务保护。本轮仅在隔离合成数据 SQLite / PostgreSQL 上实测，其他方言通过解析与现有方言回归验证。

执行器原有失败样本仅识别约定的 CASE WHEN ... THEN 1 ELSE 0 END 条件；复杂 CTE / 集合查询不会自动获得通用的样本语义。此次保持原有统计与样本约定，不扩大结果解释范围。
