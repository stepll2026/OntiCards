# Weaviate 持久化部署与升级清单

本指南适用于仓库根目录的单节点 Docker Compose 部署；命令从仓库根目录执行。它是升级操作前的检查清单，不代表已经完成旧数据卷的升级演练。

## 当前版本与连接约定

| 项目 | 仓库当前值 |
| --- | --- |
| 服务端镜像 | `cr.weaviate.io/semitechnologies/weaviate:1.36.0`（`docker-compose.yaml`） |
| Python 客户端 | `weaviate-client==4.20.4`（`OntiCards_Api/requirements.txt`） |
| 持久化目录 | 宿主机 `./volumes/weaviate/data` → 容器 `/var/lib/weaviate` |
| API 到服务端 | Compose 网络内 HTTP `onticards-weaviate:8080`、gRPC `50051` |

官方[客户端版本对应表](https://docs.weaviate.io/weaviate/client-libraries/python#releases)将服务端 `1.36.x` 与 Python 客户端 `4.20.x` 对应。本仓库保留上述精确锁定值；对应表不是所有历史版本、功能和数据格式均兼容的保证。更改服务端版本时，应一起审查客户端的版本要求和应用调用，在隔离环境验证后再调整精确版本，勿使用 `latest` 或无版本约束的客户端升级。客户端 v4 需要 gRPC；当前两个端口只需在 Compose 网络内互通，无须新增宿主机端口映射。

应用镜像重建不会清空向量库目录，也不会把旧数据转换为可任意跳版本的数据格式。新建空目录部署和复用历史目录升级是两种不同操作。

## 先确定升级路径

遵循官方[迁移指南](https://docs.weaviate.io/deploy/migration)：先完整备份，每次只跨一个次版本，每一阶段选择该次版本的最新补丁并写成精确镜像标签。例如旧库在 `1.34.x`，应逐步经过 `1.35.x` 再到 `1.36.x`，不能直接跳过中间次版本。这里的 `x` 是待核实的补丁号，不能直接填入 Compose。

`1.36.0` 是当前仓库部署基线，不是“最新补丁”声明，也不是任意旧卷可直接升级到它的承诺。迁移时先核对官方发布说明、已知问题及每阶段的迁移要求，另行记录和审查选定的精确补丁配置；本次文档更新不修改任何版本。迁移到较新补丁后的卷，不应被下一次普通部署重新以旧的 `1.36.0` 打开：保留已验证的部署配置与对应应用版本。

对于更老的卷，需从实际运行版本逐级规划。尤其注意 `1.25` 的 Raft 迁移、进入 `1.26+` 前的元数据同步要求，以及早于 `1.30` 的集合迁移说明；不要仅按镜像标签机械重启。官方指南要求进入 `1.26+` 前检查 `/v1/cluster/statistics` 的预期节点数及 `synchronized: true`。

## 升级前备份（必须先验证能恢复）

- 记录当前镜像标签与 digest、服务端实际版本、应用提交、客户端版本、Compose 配置、集合及对象数量。妥善保管配置中的密钥，不将其上传公开日志。
- 当前 Compose **未配置备份模块和备份存储**，`ENABLE_API_BASED_MODULES` 不等于启用备份。按官方[备份说明](https://docs.weaviate.io/deploy/configuration/backups)单独配置备份后端及权限，确认备份最终状态为成功，保存备份 ID、版本及存储位置，并在隔离实例恢复验证。生产备份应存放在独立于原数据目录的可靠存储上。
- 注意备份范围：当前 `1.36.0` 的原生备份仅包含活跃租户；如使用多租户，先核对并激活所需租户，不能把缺少非活跃租户的备份当作完整备份。外置数据、应用配置和 PostgreSQL 需另行备份。
- 如采用停机文件级备份，先停止所有写入方（含 API、外部导入任务），再停止 Weaviate，完整保存宿主机数据目录及权限、配置和原镜像信息；不要在服务写入时直接复制目录。使用副本在隔离环境验证原版本能启动并读回数据后再迁移。
- 预留备份和索引迁移所需空间与维护窗口。恢复测试未成功，或运行版本/卷来源不明时，停止升级。

## 每个阶段的操作与验收

1. 先在**隔离环境的备份副本**上演练完整路径，不让实验容器挂载原卷；验证后再安排实际维护窗口。停止 API 和其他写入方，保存该阶段可恢复备份。
2. 在独立保存的部署配置中仅将 `onticards-weaviate.image` 改为本阶段经过核对的精确标签。每阶段先运行以下静态检查；若使用 override 文件，每条 Compose 命令都必须带同一组 `-f` 参数：

   ```bash
   docker compose config -q
   docker compose config --images
   ```

   确认最终镜像、挂载目录和服务名符合计划。`config -q` 只验证配置解析，不验证数据格式、备份恢复或服务可用性。

3. 仅启动本阶段 Weaviate，避免在旧服务端阶段启动当前应用客户端：

   ```bash
   docker compose pull onticards-weaviate
   docker compose up -d --no-deps onticards-weaviate
   docker compose ps onticards-weaviate
   docker compose logs --tail=200 onticards-weaviate
   docker compose exec -T onticards-weaviate wget -qO- http://127.0.0.1:8080/v1/meta
   docker compose exec -T onticards-weaviate wget -qO- http://127.0.0.1:8080/v1/.well-known/ready
   docker compose exec -T onticards-weaviate wget -qO- http://127.0.0.1:8080/v1/cluster/statistics
   ```

   检查实际版本、就绪状态、迁移错误与节点同步；对照备份记录核对集合和对象数量，使用该阶段兼容客户端抽样查询。全部符合预期才进入下一次版本；失败则停在当前阶段排查。

4. 到达选定目标并核对客户端兼容后，重建和启动应用：`docker compose up -d --build`。检查服务健康和 API 日志，通过实际数据卡片检索确认 HTTP/gRPC 连接及已有向量查询正常；在隔离环境完成新增数据与检索验证。保留每阶段结果和最终精确配置。

## 失败恢复

停止写入并保留失败卷用于诊断。不要通过降低镜像标签让旧服务直接打开已迁移卷；在独立目录恢复升级前的已验证备份，使用与该备份匹配的原服务端、客户端和应用配置。验证数据及检索后再切换。恢复到备份时点会丢失其后的写入，应事先明确停写窗口及恢复点。官方迁移指南列有特定降级限制，不能假定反向改标签即可回滚。
