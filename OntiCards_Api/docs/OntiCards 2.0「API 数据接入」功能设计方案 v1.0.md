# OntiCards 2\.0「API 数据接入」功能设计方案 v1\.0

**文档版本：**v1\.0（产品功能设计）｜**编制日期：**2026\-07\-26｜**方案类型：**A 客户定制型

---

# §0 执行摘要

## 0\.1 一句话定位

为 OntiCards 2\.0 新增「API 数据接入」能力，让无法直连数据库的企业/数据源，通过标准化 RESTful API 协议完成端到端数据接入，实现「填 API 地址 → 自动建库建表 → 数据同步 → 生成数据卡片 → 可用查询」的全自动闭环。

## 0\.2 解决的核心问题

|\#|问题场景|典型客户|
|---|---|---|
|1|企业数据库网络隔离，无法直连|金融、政务、军工|
|2|原始数据需先治理（清洗/脱敏/归一化）|医疗、电商|
|3|异构系统需统一数据出口|中台型客户|
|4|第三方数据服务商以 API 交付|SaaS 集成商|

## 0\.3 关键决策总览

|决策项|决策结论|理由|
|---|---|---|
|数据仓选型|默认 PostgreSQL，强制外接独立实例，与元数据库物理隔离|兼容现有、运维统一、亿级内性能充足；大规模可平滑切换 ClickHouse/StarRocks|
|同步策略|每张表独立配置：one\_time\_full / scheduled\_incremental / scheduled\_full / manual|不同表的数据特征和更新频率差异大，必须独立策略|
|分页策略|游标分页 \+ 断点续传 \+ 多表并行|上游 API 不可控，需最小化对上游压力|
|大表处理|ID 范围分片（单表 \>100 万行时自动触发）|控制单批次内存和时长|
|容错机制|指数退避重试（1s/2s/4s，最多 3 次）\+ 死信队列|API 网络不稳定是常态|

## 0\.4 范围边界

|我们做|客户建设 / 我们对接|客户自建|
|---|---|---|
|API 接入引擎（连通性校验、元数据获取、同步调度、状态机、监控）|上游 API 服务（客户或第三方提供，需按本文档 API 协议实现）|数据治理规则（具体脱敏字典、清洗逻辑）|
|内置数据仓库（PostgreSQL 默认，可外接）|网络/防火墙配置（确保 OntiCards → 上游 API 可达）|安全合规审批流程|
|数据卡片/关系卡片自动生成|认证凭据提供（API Key / Bearer Token 等）|上游系统本身的改造|
|同步监控告警面板|增量锚点字段确认（由客户业务方提供）||

---

# §1 背景与痛点

## 1\.1 OntiCards 现有数据接入能力

OntiCards 2\.0 当前仅支持**直连数据库**接入模式，即用户配置数据库连接串（host/port/db/user/pass），系统直接连接目标数据库完成元数据自动抽取、数据卡片自动生成、关系卡片自动识别、实时查询执行。

这一模式在数据库可直连、网络互通、权限开放的场景下运行良好。但在以下 4 类场景中完全失效：

## 1\.2 四大不可直连场景

### 场景 A：网络隔离型（金融、政务、军工）

- **特征**：生产数据库部署在隔离网段或专网，仅允许白名单 IP 访问

- **痛点**：OntiCards 无法获得数据库直连权限

- **典型诉求**：「能否让我们只暴露一个数据接口，你们来拉？」

### 场景 B：治理前置型（医疗、电商）

- **特征**：原始数据含敏感信息（PII、交易明细），需清洗/脱敏/归一化后才能对外提供

- **痛点**：直接把 OntiCards 连到原始库 = 绕过治理层，合规风险极高

- **典型诉求**：「我们需要在数据出口前做一层治理，你们接治理后的 API」

### 场景 C：异构系统中台型（大型集团、多子公司）

- **特征**：数据分散在 ERP / CRM / MES / 财务 / HR 等多个异构系统

- **痛点**：每个系统协议不同、字段命名不统一、无统一查询入口

- **典型诉求**：「我们建了一个数据中台 API，你们统一接中台」

### 场景 D：第三方数据服务型（SaaS 集成商）

- **特征**：客户采购了第三方数据服务（如征信、工商、天气、行情），以 API 形式交付

- **痛点**：第三方只提供 API，不提供数据库直连

- **典型诉求**：「征信数据是第三方 API 提供的，我们想一起查」

## 1\.3 设计原则

|\#|原则|说明|
|---|---|---|
|1|上游零改造|上游 API 只需按本文档协议实现 3 个接口，无需适配 OntiCards 内部结构|
|2|数据仓隔离|应用元数据库与数据仓库 100% 物理隔离，避免混用导致的性能/安全/运维问题|
|3|表级独立策略|每张表的同步策略独立配置，不同表可不同步、不同频、不同方式|
|4|可观测性优先|每张表的同步状态、进度、异常全部可视化，问题可快速定位|
|5|渐进式扩展|先 PostgreSQL 跑通 MVP，大规模场景再引入 ClickHouse/StarRocks，不追求一步到位|

---

# §2 总体架构

## 2\.1 架构分层（与 OntiCards 现有 4 层兼容）

OntiCards 现有架构分为 4 层：L1 数据接入层、L2 语义建模层、L3 智能引擎层、L4 应用层。新增两层：L1\.5 API 接入服务层、L0\.5 内置数据仓库层。

## 2\.2 新增组件职责

|组件|职责|技术选型|
|---|---|---|
|API 接入引擎|管理 API 数据源注册、连通性校验、元数据获取|Python FastAPI \+ APScheduler|
|同步调度器|按 sync\_strategy 调度同步任务，控制并发|Celery Beat \+ Redis|
|数据写入器|将 API 返回数据写入内置数仓，支持 UPSERT|SQLAlchemy \+ PostgreSQL|
|状态机|管理每张表的同步生命周期状态|状态持久化到 PostgreSQL|
|监控告警|同步失败率、延迟、API 异常、QPS 突增|Prometheus \+ Grafana（可选）|
|内置数仓|独立 PostgreSQL 实例，落地所有 API 数据|PostgreSQL 14\+|

---

# §3 方案设计

## 3\.1 数据仓选型决策

### 3\.1\.1 核心决策：必须物理隔离

- **强制外接独立 PostgreSQL 实例**：安装 OntiCards 时，数据仓配置（host/port/db/user/pass）为必填项，不允许"不填就默认用应用库"

- **与 OntiCards 元数据库 100% 物理隔离**：至少要求不同 database，推荐不同实例

- **默认 PostgreSQL**：与产品技术栈兼容、运维统一、亿级内性能充足

### 3\.1\.2 隔离等级要求

|等级|隔离方式|适用场景|是否满足要求|
|---|---|---|---|
|最高|不同物理实例|生产环境强隔离|推荐|
|高|同一实例不同 database|中小型部署|最低要求|
|中|同一 database 不同 schema|开发测试环境|不满足|
|低|同一 schema 不同表前缀|不推荐|不满足|

### 3\.1\.3 选型决策树

### 3\.1\.4 四档推荐

|档位|数据规模|并发|推荐方案|切换路径|
|---|---|---|---|---|
|小规模|\< 1000 万行|\< 10 QPS|PostgreSQL 单实例|—|
|中规模|1000 万 \~ 1 亿行|10\~50 QPS|PostgreSQL \+ 读写分离|垂直扩容 CPU/内存/SSD|
|大规模|1 亿 \~ 10 亿行|50\~200 QPS|ClickHouse|PostgreSQL → ClickHouse（ETL 迁移）|
|实时高并发|\> 10 亿行 或 \< 1s 延迟|\> 200 QPS|StarRocks|任何上游 → StarRocks（支持实时 UPSERT）|

### 3\.1\.5 平滑切换路径

1. **阶段 1（MVP\-M2）**：PostgreSQL 单实例

2. **阶段 2（预警）**：PostgreSQL 主从 \+ 查询优化 \+ 索引调优

3. **阶段 3（迁移）**：冻结写入 → PostgreSQL → ClickHouse/StarRocks 全量 ETL → 切换数据源配置 → 恢复增量同步 → 验证查询一致性

## 3\.2 端到端流程

### 3\.2\.1 整体时序图

### 3\.2\.2 同步状态机

**状态说明：**

|状态|含义|可执行操作|
|---|---|---|
|init|数据源已注册，尚未启动首次同步|启动全量同步、删除|
|full\_syncing|正在执行全量数据拉取|暂停、查看进度|
|full\_done|全量同步已完成|启动增量、重新全量、删除|
|incremental\_idle|增量同步就绪，等待下次触发|手动触发、暂停、重新全量|
|incremental\_syncing|正在执行增量同步|暂停、查看进度|
|failed|同步失败，重试已耗尽|重试、暂停、删除|
|paused|用户手动暂停|恢复、删除|

## 3\.3 同步策略设计

### 3\.3\.1 四种同步策略

metadata 中每张表增加 `sync_strategy` 字段，支持以下 4 种：

|策略|说明|适用场景|
|---|---|---|
|**one\_time\_full**|一次性全量同步，完成后不再同步|静态配置表、字典表、历史快照|
|**scheduled\_incremental**|定时增量同步，基于增量锚点字段|流水表、日志表、交易表|
|**scheduled\_full**|定时全量同步，每次重新拉全量|维度表、状态表、小体量业务表|
|**manual**|完全手动触发，无自动调度|低频更新、人工审核后发布|

### 3\.3\.2 sync\_config 配置

每张表独立的同步配置（JSON 格式）：

```json
{
  "sync_strategy": "scheduled_incremental",
  "sync_config": {
    "cron": "*/5 * * * *",
    "incremental_anchor_field": "updated_at",
    "incremental_anchor_format": "iso8601",
    "batch_size": 1000,
    "max_concurrent_tables": 5,
    "retry_policy": {
      "max_retries": 3,
      "backoff_base_seconds": 1,
      "backoff_multiplier": 2
    },
    "timeout_seconds": 30
  }
}
```

### 3\.3\.3 调度器设计

- **引擎**：APScheduler（轻量）或 Celery Beat（大规模）

- **调度粒度**：最小 5 分钟（cron 表达式支持）

- **并发控制**：数据源级别 max\_concurrent\_tables（默认 5）；全局级别 max\_concurrent\_sources（默认 10）；同一表的同步任务互斥（防止重复同步）

### 3\.3\.4 大表分片策略

当单表预估行数 \> 100 万行时，自动启用 ID 范围分片：

1. 首次拉取时，获取表的主键范围 \[min\_id, max\_id\]

2. 计算分片大小 shard\_size = 100,000（可配置）

3. 生成 N 个分片任务：shard\_1: id\_from=min\_id \& id\_to=min\_id\+shard\_size；shard\_2: id\_from=min\_id\+shard\_size\+1 \& id\_to=min\_id\+2\*shard\_size；\.\.\.

4. 分片任务并行执行（受 max\_concurrent\_tables 限制）

5. 所有分片完成后，合并为 full\_done

## 3\.4 完整 API 文档

### 3\.4\.1 API 概览

|接口|方法|路径|说明|
|---|---|---|---|
|健康检查|GET|/health|连通性校验|
|元数据获取|GET|/metadata|获取所有表结构、字段、同步策略|
|数据获取|GET|/data/\{table\_name\}|获取指定表的数据（支持分页、增量筛选）|

### 3\.4\.2 认证方式

上游 API 必须支持以下三种认证方式之一，由 OntiCards 用户在配置时选择：

**方式 A：API Key（Header）**

```http
GET /metadata
X-API-Key: {api_key}
```

**方式 B：Bearer Token**

```http
GET /metadata
Authorization: Bearer {token}
```

**方式 C：Basic Auth**

```http
GET /metadata
Authorization: Basic {base64(username:password)}
```

### 3\.4\.3 接口 1：健康检查 /health

**请求**

```http
GET /health
```

**成功响应（200）**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-07-26T10:00:00Z"
}
```

**异常响应**

|HTTP 码|含义|响应体|
|---|---|---|
|503|服务不可用|\{"status": "unhealthy", "reason": "database\_connection\_failed"\}|

### 3\.4\.4 接口 2：元数据获取 /metadata

**请求**

```http
GET /metadata
```

**成功响应（200）**

```json
{
  "version": "1.0.0",
  "generated_at": "2026-07-26T10:00:00Z",
  "tables": [
    {
      "table_name": "orders",
      "table_comment": "订单主表",
      "primary_key": ["order_id"],
      "columns": [
        {
          "name": "order_id",
          "type": "varchar(64)",
          "nullable": false,
          "comment": "订单编号"
        },
        {
          "name": "user_id",
          "type": "varchar(64)",
          "nullable": false,
          "comment": "用户编号"
        },
        {
          "name": "amount",
          "type": "decimal(18,2)",
          "nullable": false,
          "comment": "订单金额"
        },
        {
          "name": "status",
          "type": "varchar(20)",
          "nullable": false,
          "comment": "订单状态"
        },
        {
          "name": "created_at",
          "type": "timestamp",
          "nullable": false,
          "comment": "创建时间"
        },
        {
          "name": "updated_at",
          "type": "timestamp",
          "nullable": false,
          "comment": "更新时间"
        }
      ],
      "sync_strategy": "scheduled_incremental",
      "sync_config": {
        "incremental_anchor_field": "updated_at",
        "incremental_anchor_format": "iso8601",
        "batch_size": 1000
      },
      "estimated_row_count": 5000000
    }
  ]
}
```

### 3\.4\.5 字段类型映射

|API 返回类型|PostgreSQL 类型|说明|
|---|---|---|
|varchar\(N\)|VARCHAR\(N\)|变长字符串|
|char\(N\)|CHAR\(N\)|定长字符串|
|text|TEXT|长文本|
|int / integer|INTEGER|32 位整型|
|bigint|BIGINT|64 位整型|
|decimal\(P,S\)|DECIMAL\(P,S\)|精确小数|
|float / double|DOUBLE PRECISION|浮点数|
|boolean|BOOLEAN|布尔值|
|timestamp|TIMESTAMP|日期时间|
|date|DATE|日期|
|json|JSONB|JSON 数据|

### 3\.4\.6 接口 3：数据获取 /data/\{table\_name\}

**请求**

```http
GET /data/{table_name}?cursor={cursor}&limit={limit}&since={since}&id_from={id_from}&id_to={id_to}
```

**查询参数**

|参数|类型|必填|说明|
|---|---|---|---|
|cursor|string|否|游标，首次传 0 或不传，后续传上次返回的 next\_cursor|
|limit|integer|否|每批次最大行数，默认 1000，最大 10000|
|since|string|否|增量锚点值（如 updated\_at），仅增量同步时使用|
|id\_from|string|否|ID 范围起始（大表分片时使用）|
|id\_to|string|否|ID 范围结束（大表分片时使用）|

**成功响应（200）**

```json
{
  "table_name": "orders",
  "columns": ["order_id", "user_id", "amount", "status", "created_at", "updated_at"],
  "rows": [
    ["ORD-001", "USR-001", 199.99, "paid", "2026-07-20T10:00:00Z", "2026-07-20T10:05:00Z"],
    ["ORD-002", "USR-002", 299.99, "shipped", "2026-07-21T11:00:00Z", "2026-07-21T14:00:00Z"]
  ],
  "next_cursor": "eyJvcmRlcklkIjogIk9SRC0wMDIifQ==",
  "has_more": true,
  "fetched_count": 2,
  "total_estimated": 5000000
}
```

**关键约束**

- `next_cursor` 为空字符串或 null 时，表示无更多数据

- 返回的 `columns` 顺序必须与 `rows` 中每行数据顺序一致

- `total_estimated` 为预估总行数（用于进度展示），允许不精确

- 当 `since` 参数存在时，仅返回 `incremental_anchor_field >= since` 的数据

### 3\.4\.7 错误码体系

**HTTP 标准码**

|码|场景|客户端处理|
|---|---|---|
|200|成功|正常处理|
|400|请求参数错误|记录日志，不重试|
|401|认证失败|检查 API Key / Token 配置|
|403|权限不足|检查授权范围|
|429|限流触发|指数退避重试|
|500|上游内部错误|指数退避重试|
|503|服务不可用|指数退避重试|

**业务错误码（响应体中）**

```json
{
  "error_code": "TABLE_NOT_FOUND",
  "error_message": "Table 'order_items' does not exist",
  "request_id": "req_abc123"
}
```

|error\_code|说明|处理建议|
|---|---|---|
|TABLE\_NOT\_FOUND|表不存在|检查 metadata 是否过期，重新获取|
|INVALID\_CURSOR|游标无效|从 cursor=0 重新开始|
|INVALID\_SINCE|增量锚点格式错误|检查 incremental\_anchor\_format 配置|
|RATE\_LIMITED|触发限流|降低并发，指数退避|

### 3\.4\.8 限流策略

|维度|限制|说明|
|---|---|---|
|QPS 上限|默认 10 req/s，可配置|单数据源的总体请求频率上限|
|并发数|默认 5，可配置|单数据源同时进行的表同步数|
|批次大小|默认 1000，最大 10000|每页返回数据行数|
|自适应降级|遇 429 自动降低 50% QPS|动态调整，恢复后逐步提升|

### 3\.4\.9 幂等保证

- **写入幂等**：内置数仓使用 `INSERT ... ON CONFLICT (primary_key) DO UPDATE`（UPSERT）

- **游标持久化**：每张表的 last\_cursor 和 last\_anchor 持久化到 PostgreSQL

- **任务去重**：同一表的同步任务在运行期间互斥（Redis 分布式锁）

- **断点续传**：同步失败后可从 last\_cursor 恢复，无需从头开始

## 3\.5 容错与权限

### 3\.5\.1 重试机制

- **最大重试次数**：3 次

- **退避算法**：指数退避 — 第 1 次等待 1 秒，第 2 次等待 2 秒，第 3 次等待 4 秒

- **触发重试的异常**：网络超时、连接重置、5xx 错误、429 限流

- **不重试的异常**：4xx（除 429）、认证失败、表不存在

### 3\.5\.2 死信队列

- 3 次重试均失败后，同步任务进入死信队列（Dead Letter Queue）

- 死信队列中的任务可人工查看失败原因、手动重试或标记为忽略

- 死信队列保留 30 天，超期自动清理

### 3\.5\.3 权限隔离

|隔离维度|实现方式|
|---|---|
|Schema 隔离|每个 API 数据源对应独立 schema：`api_src_{source_id}`|
|数据空间隔离|不同数据源的表完全隔离，不可跨 schema JOIN|
|权限边界|OntiCards 中为每个数据源独立配置查询权限|
|敏感字段|上游 API 负责脱敏，OntiCards 按原样存储和查询|

### 3\.5\.4 安全设计

|措施|实现|
|---|---|
|传输安全|强制 HTTPS，拒绝 HTTP|
|API Key 存储|AES\-256\-GCM 加密存储于 OntiCards 配置库|
|密钥轮换|支持手动更新，旧密钥 24h 内仍有效|
|敏感字段|上游在 /data 接口中脱敏，OntiCards 不感知|
|审计日志|所有同步操作记录：时间、操作人、表、行数、耗时、状态|

## 3\.6 监控告警

### 3\.6\.1 监控指标

|指标|类型|告警阈值|
|---|---|---|
|sync\_success\_rate|比率|\< 95% 告警|
|sync\_latency\_p99|延迟|\> 5 分钟告警|
|api\_error\_rate|比率|\> 5% 告警|
|api\_qps|速率|突增 \> 200% 告警|
|dead\_letter\_count|计数|\> 0 告警|
|data\_freshness|时间|增量同步延迟 \> 2×cron 周期|

### 3\.6\.2 告警通道

- 飞书消息（默认）

- 邮件（可选）

- Webhook（可选，对接客户告警系统）

---

# §4 范围边界

## 4\.1 明确不做

|\#|不做的事项|原因|
|---|---|---|
|1|上游 API 的实现|由客户或第三方提供，OntiCards 只消费|
|2|具体数据治理规则（脱敏字典、清洗逻辑）|业务决策，由客户业务人员主导|
|3|上游系统的改造|只要求按本文档 API 协议实现 3 个接口|
|4|UI 原型设计|仅描述关键交互流程，具体 UI 由前端设计师出|
|5|实时 CDC（Change Data Capture）同步|本期只做定时拉取，CDC 为远期方向|
|6|多租户隔离（SaaS 级别）|本期按数据源级隔离，多租户为远期方向|
|7|自动 schema 变更同步（上游加字段/改类型）|本期手动刷新 metadata，自动检测为远期方向|

## 4\.2 风险与缓解

|风险|影响|概率|缓解措施|
|---|---|---|---|
|上游 API 性能差，同步极慢|高|中|① 分片并行 ② 自适应限流 ③ 支持大表分片|
|上游 API 不稳定，频繁失败|高|高|① 指数退避重试 ② 死信队列 ③ 断点续传|
|数据量超预期，PostgreSQL 扛不住|高|低|① 选型决策树提前预警 ② 平滑迁移工具|
|上游字段类型与 OntiCards 不兼容|中|中|① 完善类型映射表 ② 不兼容类型转 TEXT \+ 告警|
|增量锚点字段设计不合理，导致数据遗漏|高|中|① 文档明确要求单调递增/更新时间戳 ② 一致性校验工具|
|API Key 泄露|高|低|① AES 加密存储 ② 支持密钥轮换 ③ 操作审计|

## 4\.3 对现有 OntiCards 功能的影响

|模块|影响|处理方式|
|---|---|---|
|数据库直连接入|无影响|现有逻辑完全保留|
|数据卡片生成|新增数据源类型|复用现有逻辑，传入 API 源的表结构即可|
|NL2SQL 查询|无影响|查询目标变为内置数仓，对引擎透明|
|权限管理|新增数据源维度|按 source\_id 增加一级权限过滤|
|安装部署|新增数据仓配置项|安装向导增加数据仓连接串必填项|

---

# §5 附录

## 5\.1 术语表

|术语|说明|
|---|---|
|NL2SQL|Natural Language to SQL，自然语言转 SQL 查询|
|UPSERT|INSERT 时如主键冲突则 UPDATE，保证幂等写入|
|CDC|Change Data Capture，变更数据捕获|
|游标分页|Cursor\-based pagination，基于游标而非 OFFSET 的分页方式|
|增量锚点|Incremental anchor，用于判断数据是否变更的字段（如 updated\_at）|
|死信队列|Dead Letter Queue，存放多次重试失败任务的队列|
|Schema|数据库中的命名空间，用于逻辑隔离不同数据源的表|

## 5\.2 参考资料

- OntiCards 产品说明文档 V2\.0

- 初步方案（API 数据接入思路）

- PostgreSQL 14 官方文档

- OpenAPI 3\.0 规范

