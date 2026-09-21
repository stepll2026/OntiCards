# JOIN 作用域与重试回归测试

本组测试覆盖 PostgreSQL/Kingbase 的 JOIN 别名依赖、SQL 修正重试和失败响应。
例如 `a JOIN b ON b.id=c.id JOIN c ON c.id=a.id` 提前引用后面的 `c`，应在执行前被拦截。

## 运行离线测试

在仓库根目录，用 Python 3.10+ 创建独立测试环境并运行：

```bash
python -m venv .venv-join-test
# Linux/macOS: source .venv-join-test/bin/activate
# Windows PowerShell: .\.venv-join-test\Scripts\Activate.ps1
python -m pip install pytest==8.4.2 SQLAlchemy==2.0.36 sqlglot==30.18.0
python -m pytest -q OntiCards_Api/tests
```

该独立环境仅安装本组测试所需依赖；启动完整 API 仍需安装
`OntiCards_Api/requirements.txt`。请勿提交虚拟环境或生成的缓存文件。

- `test_sql_join_scope.py`：别名可见范围、相关子查询、CTE、逗号连接、LATERAL、表函数、WITH ORDINALITY、TABLESAMPLE 和括号连接。
- `test_join_scope_retry.py`：从实际源文件抽取函数，隔离应用初始化，用模拟模型与数据库 I/O 检查重试次数、重新执行安全校验、提示词快照、token/耗时累计和错误返回。
- `test_join_scope_main_compat.py`：验证 schema 引号处理和 `REPLACE()` 与 JOIN 校验、自动重试的兼容性；覆盖主接口和 plugin 的只读拦截，并检查已带引号的 schema 不会被重复包装。
- `test_sql_join_scope_postgres.py`：默认跳过，按下节启用真实 PostgreSQL 对照。

## 运行真实 PostgreSQL 对照

测试机需具备 Docker，并预先准备 `postgres:16` 镜像：

```bash
docker pull postgres:16
# Linux/macOS
ONTICARDS_TEST_POSTGRES=1 python -m pytest -q OntiCards_Api/tests
```

Windows PowerShell：

```powershell
$env:ONTICARDS_TEST_POSTGRES = '1'
python -m pytest -q OntiCards_Api/tests
```

测试自行创建并清理临时 PostgreSQL 容器，关闭容器网络、不映射端口，使用内存中的合成数据。
不会读取应用 `.env`，也不接收业务数据库连接串。
通过 `BEGIN READ ONLY; EXPLAIN ...` 比较校验器与 PostgreSQL 的接受/拒绝结果；另验证 LEFT JOIN 保留未匹配主表记录，以及带连字符 schema 中的 `REPLACE()` 查询结果。后者在临时容器内创建合成表，并回滚测试事务。
启用后，Docker 或镜像不可用会让测试失败。
可用 `ONTICARDS_TEST_POSTGRES_IMAGE=postgres:15-alpine` 指定其他已准备好的 PostgreSQL 镜像进行版本兼容检查；默认使用 `postgres:16`。

## 行为与边界

生成和修正提示词均追加 JOIN 作用域规则。旧数据库提示词仍可使用，失败 SQL 和错误原因会显式补入。
并行任务在请求线程获取重试模板快照，避免在线程内因缓存失效访问 Flask 数据库上下文。
原有最多两次修正保持不变；每次修正后重新执行安全校验，不自动改写 JOIN。
模型修正失败时保留原 SQL 和错误，已返回的模型调用用量累计到查询日志。

SQLGlot 负责解析，独立模块检查关系别名，不代替数据库的列、类型、权限校验或业务口径审核。
无法解析和尚未支持的结构会明确失败并尝试修正。表函数和 TABLESAMPLE 的参数仍需通过作用域检查。
TABLESAMPLE 表达式解析使用本模块内的 PostgreSQL 解析器子类，未修改 SQLGlot 全局方言。

所有查询簇失败时接口返回 HTTP 422；正常空结果保持成功，部分成功保持原有流程。
新增运行依赖 `sqlglot==30.18.0`，重新构建 API 镜像时必须安装。
本组测试不替代真实模型、完整 API 启动和客户环境的端到端联调。

## 已完成的验证

同步主干 schema 与 `REPLACE()` 修复后，在现有 API 镜像的 Python 3.10.21 环境中，
117 项作用域测试、23 项隔离集成测试、30 项交叉兼容测试和 49 项真实 PostgreSQL 16 对照
全部通过，共 219 项；同样的 49 项数据库对照在 PostgreSQL 15 中再次全部通过。
本地离线测试为 170 项通过、49 项数据库测试按配置跳过。

交叉回归发现并补充修复了已带引号 schema 被再次包装的问题：`"yx-data".orders` 保持原样。
相应 8 项兼容用例在修复前失败，修复后通过；未改变其他方言或表名前缀处理路径。

另在独立隔离环境中，用实际查询函数、原模型 HTTP wrapper、SQLAlchemy 和临时 PostgreSQL
串联验证了以下 5 个场景。模型由本地可控 HTTP 服务模拟，500 和缺少 `choices` 的响应是测试主动注入的。

| 场景 | 预期及实际结果 |
| --- | --- |
| 错误 SQL 后返回修正 SQL | 先拦截错误，再执行修正版；8 行合成结果与基准一致，保留未匹配记录及关联条件 |
| 连续返回错误 SQL | 两次修正后停止，没有向数据库执行错误 SQL，保留失败原因 |
| 正常查询没有数据 | 成功返回空结果 |
| 修正请求返回 HTTP 500 | 返回明确的修正失败信息，保留原 SQL 和 JOIN 诊断 |
| 修正响应缺少 `choices` | 返回明确的修正失败信息，未出现 `KeyError` |

串联验证为便于核对应用层重试次数，将测试专用 HTTP 自动重试设为 0；生产 wrapper 的重试配置未修改。
以上结果验证了异常处理和数据库执行链路，尚未验证真实大模型的生成质量、服务超时或完整网页操作。
