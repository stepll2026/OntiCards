# 数据库结构版本与自动升级

API 启动时检查 OntiCards 自身 PostgreSQL 数据库的结构版本，按顺序执行代码中尚未应用的迁移。升级完成后才初始化默认用户并开始提供服务。用户接入的业务数据库和 Weaviate 索引不在此机制的管理范围内。

## 当前版本链

| 结构版本 | Alembic revision | 内容 |
| --- | --- | --- |
| V1 / 1.0 | `v1` | 核验已有数据库的基线表和字段，或初始化空库 |
| V1.1 / 1.1 | `v1_1` | 模型配置增加协议和向量维数 |
| V1.2 / 1.2 | `v1_2` | 模型配置增加原生协议参数 |

代码在 `OntiCards_Api/extensions/schema_migrations.py` 中声明 `DATABASE_SCHEMA_VERSION` 和 `TARGET_REVISION`。迁移脚本的 `down_revision` 确定执行顺序，不使用版本字符串排序。

例如，数据库当前为 V1，代码要求 V1.2，则启动过程依次执行 V1.1、V1.2；当前为 V1.1 时仅执行 V1.2；已是 V1.2 时核验记录后正常启动。

## 版本记录

新建 `public.schema_migrations` 表，记录每次成功升级的版本、revision、脚本校验值、说明和完成时间。沿用 `public.alembic_version` 保存当前 revision，两者必须一致。

```sql
SELECT version, revision, description, applied_at
FROM public.schema_migrations
ORDER BY applied_at, version;

SELECT version_num FROM public.alembic_version;
```

每一步结构修改、当前版本更新和历史记录写入都在同一事务中提交。失败时回滚当前步骤并终止启动，已经成功提交的前置版本保留。排除故障后重新启动，会从最后一个成功版本继续。

## 已有环境与新部署

- **已有库但没有版本记录**：先核验 `migrations/baseline_v1.json` 中的基线表和字段，再从 V1 开始登记和升级。基线对应引入此机制时的上游结构；缺失基线结构的更早版本或定制库会停止启动并报告缺失项，不会重跑初始化脚本覆盖数据。
- **已手动添加模型字段**：仍按版本链登记；迁移使用 `ADD COLUMN IF NOT EXISTS`，并核验字段类型、可空性和协议默认值，保留已保存的模型设置。
- **空库**：在事务中执行 `init.sql` 并应用版本链。初始化过程支持自定义数据库用户；该用户需有建表、修改结构及安装所需扩展的权限。
- **多实例同时启动**：PostgreSQL 会话锁保证一次只有一个实例执行升级。其他实例等待后重新检查版本；等待超过 60 秒则退出，可在升级完成后重启。
- **代码回退或记录异常**：数据库版本超出代码认识的版本、历史记录不完整或已执行脚本被修改时，停止启动。启动流程不自动降级数据库。

已有环境拉取代码并重建 API 后，会在启动时自动迁移，无需再次手动执行本次模型字段 SQL。升级前按日常发布流程备份数据库。容器启动失败时可通过 `docker compose logs onticards_api` 查看目标版本和异常原因。

## 后续如何增加 V1.3

1. 在 `migrations/versions/` 增加新的 Alembic 脚本，设置唯一 `revision`、`schema_version = "1.3"`，并将 `down_revision` 指向 `v1_2`。
2. 在 `upgrade()` 中编写经过验证的增量修改；在 `verify(connection)` 中核验该版本所需结构。额外 SQL 文件列入 `checksum_files`，随代码一并提交。
3. 更新 `DATABASE_SCHEMA_VERSION` 和 `TARGET_REVISION`。保留旧迁移脚本及其依赖文件；修复已发布的迁移应新增版本。
4. 同步新安装所用的 `init.sql`。迁移要兼容初始化脚本已经包含目标结构的情况，核验已有字段，避免重复创建或覆盖数据。
5. 在隔离的 PostgreSQL 环境验证跨版本升级、失败回滚、重复执行和现有数据保留，再发布代码。

该机制执行开发者随版本提交的迁移脚本；不会根据 ORM 差异自动猜测删列、改类型或清理数据。每个版本使用事务，脚本不得自行 `COMMIT`、切换为自动提交或执行 `CREATE INDEX CONCURRENTLY` 等不能放在事务中的操作。此类升级需要单独设计发布步骤。

## 测试

```bash
# SCHEMA_TEST_DATABASE_URL 必须指向隔离的测试实例，库名固定如下：
export SCHEMA_TEST_DATABASE_URL='postgresql+psycopg2://user:password@host/onticards_schema_test_admin'
python -m pytest OntiCards_Api/test/schema_migrations -q
```

测试账号需要创建临时数据库和角色的权限。测试只创建、删除本轮生成的 `onticards_schema_test_*` 数据库和 `onticards_schema_role_*` 角色。不提供连接地址时，仅运行无需数据库的检查，其余用例标记为跳过。

实现依据：[Alembic 连接复用](https://alembic.sqlalchemy.org/en/latest/cookbook.html#sharing-a-connection-across-one-or-more-programmatic-migration-commands)、[PostgreSQL 会话锁](https://www.postgresql.org/docs/15/explicit-locking.html#ADVISORY-LOCKS)。
