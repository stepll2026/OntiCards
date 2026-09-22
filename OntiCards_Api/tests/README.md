# JOIN 作用域、重试与日志回归测试

本组测试覆盖 PostgreSQL/Kingbase 的 JOIN 别名依赖、SQL 修正重试和失败响应。
例如 `a JOIN b ON b.id=c.id JOIN c ON c.id=a.id` 提前引用后面的 `c`，应在执行前被拦截。

## 运行离线测试

在仓库根目录，用 Python 3.10+ 创建独立测试环境并运行：

```bash
python -m venv .venv-join-test
# Linux/macOS: source .venv-join-test/bin/activate
# Windows PowerShell: .\.venv-join-test\Scripts\Activate.ps1
python -m pip install pytest==8.4.2 SQLAlchemy==2.0.36 sqlglot==30.18.0 Flask==2.3.3 Flask-Login==0.6.3 Flask-RESTful==0.3.10 Flask-SQLAlchemy==3.1.1 Werkzeug==3.0.6 requests==2.32.3
python -m pytest -q OntiCards_Api/tests
```

上述运行依赖版本与项目 `requirements.txt` 一致，`pytest` 是额外测试工具。
该独立环境仅安装本组测试所需依赖；启动完整 API 仍需安装
`OntiCards_Api/requirements.txt`。请勿提交虚拟环境或生成的缓存文件。

- `test_sql_join_scope.py`：别名可见范围、相关子查询、CTE、逗号连接、LATERAL、表函数、WITH ORDINALITY、TABLESAMPLE 和括号连接。
- `test_join_scope_retry.py`：从实际源文件抽取函数，隔离应用初始化，用模拟模型与数据库 I/O 检查重试次数、重新执行安全校验、提示词快照、token/耗时累计和错误返回。
- `test_join_scope_main_compat.py`：验证 schema 引号处理和 `REPLACE()` 与 JOIN 校验、自动重试的兼容性；覆盖主接口和 plugin 的只读拦截，并检查已带引号的 schema 不会被重复包装。
- `test_sql_join_scope_postgres.py`：默认跳过，按下节启用真实 PostgreSQL 对照。
- `test_query_execution_log.py`、`test_model_error_diagnostics.py`：逐次诊断、失败持久化、模型错误分类及完整历史回放保留。
- `test_query_history_access.py`：实际 Flask 路由与临时 SQLite，验证登录、所有权、筛选和旧记录兼容。
- `test_log_sanitizer.py`、`test_system_logs.py`：脱敏幂等性、系统日志权限、轮转、并发、读取限制及写入失败隔离。功能及部署说明见 `docs/log-center.md`。

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

## JOIN 基础验证（加入日志中心前）

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

## 日志中心本地验证（2026-09-21）

离线后端回归为 **262 项通过、49 项 PostgreSQL 对照按配置跳过**。服务器最终回归结果需另行记录。
日志记录复用现有 JSONB 字段，无新增表或列，无需数据库迁移；旧记录缺少纠错过程时保持未知（unknown/未记录），不推断为零次纠错。
系统日志是 best effort：写入失败不阻断业务，可能缺失事件；每次只读取最近最多 8 MiB / 20,000 条，筛选、分页和总数均限于这个窗口。

前端生产构建通过；使用实际 Web 构建、实际日志 Flask API、合成 SQLite 和测试身份的 **7 个浏览器场景通过**，覆盖查询分页、搜索及纠错详情、空结果、系统日志脱敏、自动刷新、网络失败、普通用户权限。
浏览器仅验证 `/en/log-center`：本地默认中文入口出现与原有页面相同的重定向循环，未修改全局路由配置；本次没有访问客户网络或调用真实大模型。

Next.js 配置会跳过构建期间的类型和 lint 检查，需单独验证。在 `OntiCards_Web` 下可运行：

```bash
yarn install --frozen-lockfile
yarn tsc --noEmit --incremental --tsBuildInfoFile .next/log-center-check.tsbuildinfo
yarn build
```

保留 `incremental` 是因为项目 `tsconfig.json` 配置了 `tsBuildInfoFile`。全量 TypeScript 目前有 4 个未修改治理页面的基线 `TS2769`（`cloneElement` 的 `style` 类型不匹配），本次文件无类型错误。
仓库 ESLint 另有两条缺失规则定义；定向检查仅在调用中排除它们后，本次文件无错误，新增文件无警告，布局的 2 个既有警告不变。构建通过不代表全仓类型与 lint 问题已解决。
4 个基线错误的具体文件、行号及完整验证边界见 [日志中心说明](../docs/log-center.md#本地验证范围2026-09-21)。
