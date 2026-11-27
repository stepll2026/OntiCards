# 首次管理员引导

全新 PostgreSQL 数据库需要部署者显式授权创建首位管理员。已有用户和已完成引导的数据库沿用当前账号。数据库来源不明时，先由维护者核实部署记录或按授权流程恢复数据。

## Docker Compose

在部署目录完成数据库和应用配置后，为新库生成仅运行 API 的用户可读的密码文件。下面使用 32 个随机字节，终端只得到命令退出状态。密码文件应归 API 运行用户所有。

```bash
umask 077
mkdir -p .secrets
(set -C; python3 -c 'import secrets; print(secrets.token_hex(32))' > .secrets/onticards_admin_password)
export ONTICARDS_BOOTSTRAP_ADMIN_USERNAME=your-chosen-admin
export ONTICARDS_BOOTSTRAP_NEW_DATABASE=prod-ontiCards
docker compose -f docker-compose.yaml -f docker-compose.bootstrap.yaml config -q
docker compose -f docker-compose.yaml -f docker-compose.bootstrap.yaml up -d --build --wait
```

将库名换成实际创建、专用于该实例的空数据库。确认 API `/readyz` 通过并成功登录后，妥善保管当前凭据，去掉覆盖配置并重建 API。

```bash
docker compose up -d --no-deps --no-build --force-recreate --wait onticards_api
unset ONTICARDS_BOOTSTRAP_ADMIN_USERNAME ONTICARDS_BOOTSTRAP_NEW_DATABASE
```

重建后再次确认登录，再依团队的凭据保管要求移除本地引导密码文件。已有实例通常使用基本 Compose 文件升级。

## 独立 API

在 API 的配置环境中填写 PostgreSQL 与 Weaviate。首次启动时设置 `ONTICARDS_BOOTSTRAP_NEW_DATABASE`、`ONTICARDS_BOOTSTRAP_ADMIN_USERNAME` 和 `ONTICARDS_BOOTSTRAP_ADMIN_PASSWORD_FILE`。密码文件须在 `/run/secrets` 或通过 `ONTICARDS_BOOTSTRAP_SECRET_ROOT` 指定的绝对目录中。路径和密码文件不得使用符号链接。文件必须归 API 运行用户所有并使用 `0600`。

```bash
cd OntiCards_Api
flask --app app initialize-schema
flask --app app db upgrade
gunicorn --bind 127.0.0.1:9103 'app:create_runtime_app()'
```

生产部署用同一个迁移任务完成初始化，再启动其余副本。启动后检查 `/readyz` 和实际登录。确认成功后从启动环境移除所有引导参数和密码文件挂载，重启再验。使用持久 PostgreSQL 存储和备份，保留 `public.admin_bootstrap_state`。

## 故障恢复

管理员和一次性标记在同一个 PostgreSQL 事务提交。提交之后才创建 Weaviate 集合。短暂故障时状态保留为 pending。恢复 Weaviate 并重启 API 后，引导只重试已登记的集合同步。就绪检查验证所属账号、claim 和集合结构。已有管理员删除或历史库用户清空均不会重新开启首次引导。

历史迁移保留已有用户、管理员权限和组记录。旧版可能已经创建管理员，仍需维护者核查历史账号。由其他尚未发布验收分支迁移到了更高 Alembic 版本的数据库，应继续使用与该版本匹配的分支。
