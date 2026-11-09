# PR #50 条件表达式验证记录

## 修复了什么

原贡献的正则错误地重复第一个 token，连 `column > 0` 都会被拒绝；单条件更新、SQL 预览和旧规则执行也未完整覆盖。现使用固定版本 SQLGlot 解析实际数据库方言，检查查询包装结构和允许的 AST 节点，再按源码位置替换裸列占位符，避免改坏字符串或已引用列名。列名中的引用符会转义。

修复覆盖新增与更新的单/复合条件、模板条件、自带规则配置、预览、执行及样本查询。更新复合条件使用规则自身的数据库类型，消除原贡献中的未定义变量；复合规则按真实 JSON 字符串保存后可以执行，样本归因也使用同一安全替换，避免把正常字符串误判为列引用。

检测查询另外在数据库执行边界加只读事务保护：条件校验无法判断数据库最终绑定到哪个同名函数重载，因此 PostgreSQL/金仓上执行规则和失败样本查询的事务会先设为只读并回读确认；普通事务连接上永久表写入会被拒绝，若连接无法建立只读事务（例如数据源配置了 autocommit），则直接报错而不是静默放行。

## 有什么作用

在条件被拼入 SQL 前拒绝多语句、注释、结构逃逸、未知/限定名称/引用名称函数、写入型子查询及外部表函数，同时保留原有日期函数、类型转换、正则、窗口表达式和只读引用子查询。即使目标库已有同名的写入型用户函数重载，普通事务连接上的检测查询也被数据库拒绝写入，无法确认只读时会报错而不是继续执行。

例如，手机号正则里的反斜线仍保留原样，`DATEADD` 和 `DATE_SUB` 按实际方言解析；字符串 `'column; --'` 不会被改写或误当成注释。

## 验证结果

- 实际 main：`2e597d05f3673891f9ffdef08e2c45084dbd42dc`。
- 原贡献：`047851848fca3962571197e01274945e267df06f`，已通过普通 merge 纳入 main 的后续更改。
- 上一轮代码/测试提交：`bfc484636406249db127298d2eb4ec36bba322c6`；本轮新增只读事务保护与对应回归用例。
- kol-stage2 实测：6 项条件测试（含现有方言函数矩阵及 24 个种子 SQL 条件）、10 项 Flask/SQLite 测试、31 项既有方言测试、3 项隔离 PostgreSQL 测试均通过（含 psycopg3 `?autocommit=true` 数据源必须被拒绝的用例）。
- PostgreSQL 直接加载 main 的原 SQL 构造器：合成函数确实向标记表写入；带只读保护的实际 `execute_rule` 执行路径把同一条件判为规则错误，标记表保持为空，而正常条件规则及其失败样本仍可执行并返回正确统计。数据源启用 autocommit 时，只读事务无法建立，执行器回读 `transaction_read_only` 确认不到只读即报错，不会静默执行。
- 红测对照：同一新用例在未加保护的执行器上失败，`ABS(column) > 0` 被当作正常规则执行（`passed`），证明该用例确实覆盖了写入型重载；见 [只读红测](readonly/readonly-red.log) 与 [只读绿测](readonly/test_condition_postgres.py.log)。最初一次红测（[readonly-red-1.log](readonly/readonly-red-1.log)）同样暴露该行为，但其中另一个用例因测试自身依赖已修复的旧基线而报错；该断言已改为只验证“引用函数名被拒绝”，未放宽任何安全断言。
- autocommit 红测：上一版只读保护在 `?autocommit=true` 连接上不生效（`SET TRANSACTION READ ONLY` 只产生警告），同一恶意条件被当作正常规则执行；加入回读校验后该用例通过。见 [autocommit 红测](readonly/autocommit-red.log)。
- Flask 测试实际调用新增/更新/预览方法；所有权、ORM 查询及写入使用合成 fixture，生成 SQL 在真实 SQLite 上执行。这不是完整登录/持久化服务部署测试。
- API 依赖镜像沿用既有 `sha256:4d712690199b17ea76030095e97037b2b656bf6fba502c06fe79a0367e195f63`，源码只读挂载，SQLGlot 30.29.0 wheel 离线安装到一次性 /tmp。镜像、wheel、文件摘要与日志均在本目录。
- 原补丁红测、初版有限语法造成的 10 项方言兼容性失败、首次 PostgreSQL 正则 fixture 多转义失败均保留；最终修正了 fixture 转义，未放宽统计断言。独审新增的复合规则异常和样本误归因另有 [红测](composite-red.log)；针对本功能实际生成的聚合 SQL 重测后，JSON 字符串与已解码配置、未确认与已确认 SQL 均得到正确的违规列归因。
- 本轮文件摘要以 [readonly/readonly-tested-files.sha256](readonly/readonly-tested-files.sha256) 为准；它按当前被测代码重新生成，替代此前按更早工作区记录的 `ast-tested-files.sha256` 中已过期的条目。

实际入口：

```sh
python controllers/governance/test_condition_security.py
python controllers/governance/test_condition_api.py
python controllers/governance/test_dialect_adapter.py
# 仅对一次性测试数据库设置 PR50_TEST_DATABASE_URL 和 PR50_TEST_BASELINE
python controllers/governance/test_condition_postgres.py
```

最终记录：[条件](ast-test_condition_security.py.log)、[API/SQLite](ast-test_condition_api.py.log)、[方言](ast-test_dialect_adapter.py.log)、[PostgreSQL](test_condition_postgres.py.log)、[文件摘要](ast-tested-files.sha256)、[模板矩阵](template-matrix.jsonl)、[兼容性红测](compatibility-red.log)、[PostgreSQL 首轮失败](postgres-attempt1.log)。

选择依据：源码及既有依赖中没有可用 SQL AST 库；小探针显示自制语法需要重新实现已支持的日期、CAST、正则和引用查询，而固定的 SQLGlot 能解析这些已有语法，因此选择复用库并限制实际 AST。参见 [官方 API](https://sqlglot.com/sqlglot.html) 和 [探针原始输出](ast-probe.jsonl)。并非仅调用解析器就视为安全。

早期 [baseline-control.log](baseline-control.log) 只证明额外只读子查询能改变统计，本身不证明结构注入；现有引用模板本就需要只读子查询。最终安全负对照采用真实 main 构造器调用写入型函数（含大小写敏感的引用函数名），并检查写入标记及执行前拒绝；[引用函数红测](quoted-function-red.log) 记录了 SQLGlot 归一化函数名造成的绕过，现于 AST 校验前按实际方言 token 拒绝引用函数调用；不沿用早期不充分的推断。

## 剩余限制

显式确认的完整 SQL（sql_text/sql_preview）是已有独立功能，本次没有重新定义其权限边界；条件校验不能当成数据库权限或任意 SQL 的沙箱。未知函数、引用函数名及未覆盖的 AST 结构会拒绝，需要明确评估后才扩展。

只读事务目前只加在已实证存在同名函数重载写入风险的 PostgreSQL/金仓检测查询上；其他方言仍只做条件校验与 SQL 生成，未实测对应数据库的同类风险，也未加同样的执行期保护。数据源若配置了 `autocommit`（连接没有事务块，`SET TRANSACTION READ ONLY` 不生效），治理检测会直接报错而不是静默执行，需要修正数据源配置；该保护也不等同于数据库沙箱，不覆盖临时表、外部连接（如 dblink）等数据库自身能力。若某条规则原本依赖检测 SQL 的写入副作用（含显式 `sql_text` 里的写语句或 `FOR UPDATE`），现在会直接报错而不是写入，这是本次修复的预期行为变化。

PostgreSQL 和 SQLite 为本轮真实引擎；其他数据库仅验证解析/SQL 生成与引用行为，未实测对应数据库服务。未进行完整应用部署、模型调用或托管 CI。种子模板里的未填自然语言示例不被当作可执行 SQL 验证。

未改 UI。隔离 PostgreSQL 容器及内部网络已清理，无生产数据库、共享服务或既有镜像改动；远端临时源码在独审完成后定向清理。
