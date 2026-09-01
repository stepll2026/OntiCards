# OntiCards API 接口文档

## 文档说明

本文档描述了 OntiCards 系统的所有 API 接口，用于数据库连接、数据源管理、智能查询、数据审计等功能。

**基础信息：**
- 基础路径：`/console/api`
- 认证方式：
  - **Session认证**：基于 Flask-Login 的 Session 认证（部分接口需要 `@login_required` 装饰器）
  - **API Key认证**：基于API Key的无状态认证（适用于插件接口和外部调用）
- 请求格式：JSON（Content-Type: application/json）
- 响应格式：JSON

**统一响应格式：**
```json
{
  "code": 200,
  "msg": "操作成功",
  "data": {}
}
```

---

## 目录

1. [用户管理模块](#1-用户管理模块)
2. [API Key管理模块](#2-api-key管理模块)
3. [数据源管理模块](#3-数据源管理模块)
4. [数据卡片管理模块](#4-数据卡片管理模块)
5. [数据盘点模块](#5-数据盘点模块)
6. [智能查询模块](#6-智能查询模块)
7. [数据审计模块](#7-数据审计模块)
8. [版本更新日志模块](#8-版本更新日志模块)
9. [Excel字段提取模块](#9-excel字段提取模块)
10. [模型配置信息管理模块](#10-模型配置信息管理模块)
11. [历史查询模块](#11-历史查询模块)
12. [监控中心模块](#12-监控中心模块)
13. [系统配置模块](#13-系统配置模块) 
14. [SSO单点登录模块](#14-sso单点登录模块)
15. [提示词配置模块](#15-提示词配置模块)
16. [业务术语库管理模块](#16-业务术语库管理模块)
17. [数据治理模块 - 数据质检（第一阶段）](#17-数据治理模块---数据质检第一阶段)
18. [数据治理模块 - 治理（第二阶段）](#18-数据治理模块---治理第二阶段)

---

## 1. 用户管理模块

### 1.1 用户登录

**接口描述：** 用户登录，返回 JWT Token

**请求类型：** `POST`

**接口路径：** `/console/api/login`

**是否需要登录：** 否

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| username | string | 是 | 用户名（不区分大小写） |
| password | string | 是 | 密码 |

**请求示例：**
```json
{
  "username": "admin",
  "password": "123456"
}
```

**返回示例：**
```json
{
  "code": 200,
  "message": "Login successful",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

**错误响应：**
```json
{
  "code": 400,
  "message": "Invalid username or password"
}
```

---

### 1.2 用户注册

**接口描述：** 新用户注册

**请求类型：** `PUT`

**接口路径：** `/console/api/login`

**是否需要登录：** 否

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |

**请求示例：**
```json
{
  "username": "newuser",
  "password": "123456"
}
```

**返回示例：**
```json
{
  "code": 200,
  "message": "Registration successful"
}
```

---

### 1.3 获取当前用户信息

**接口描述：** 获取当前登录用户的详细信息

**请求类型：** `GET`

**接口路径：** `/console/api/user`

**是否需要登录：** 是

**请求参数：** 无

**返回示例：**
```json
{
  "code": 200,
  "message": "获取用户信息成功",
  "data": {
    "id": "uuid-string",
    "username": "admin",
    "nickname": "管理员",
    "avatar": "http://example.com/avatar.jpg",
    "user_group_name": "管理员组",
    "role": "admin",
    "login_at": "2025-01-20T10:30:00"
  }
}
```

---

### 1.4 更新当前用户信息

**接口描述：** 更新当前登录用户的昵称和头像

**请求类型：** `PUT`

**接口路径：** `/console/api/user`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| nickname | string | 否 | 昵称 |
| avatar | string | 否 | 头像URL |

**请求示例：**
```json
{
  "nickname": "新昵称",
  "avatar": "http://example.com/new_avatar.jpg"
}
```

**返回示例：**
```json
{
  "code": 200,
  "message": "Current user updated successfully"
}
```

---

### 1.5 退出登录

**接口描述：** 用户退出登录

**请求类型：** `GET`

**接口路径：** `/console/api/logout`

**是否需要登录：** 是

**请求参数：** 无

**返回示例：**
```json
{
  "code": 200,
  "message": "Logged out successfully"
}
```

---

### 1.6 修改密码

**接口描述：** 修改用户密码

**请求类型：** `POST`

**接口路径：** `/console/api/change_password`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| id | string | 是 | 用户ID |
| old_password | string | 是 | 旧密码 |
| new_password | string | 是 | 新密码 |

**请求示例：**
```json
{
  "id": "uuid-string",
  "old_password": "old123",
  "new_password": "new123"
}
```

**返回示例：**
```json
{
  "code": 200,
  "message": "Password changed successfully"
}
```

---

### 1.7 获取所有用户列表

**接口描述：** 获取系统中所有用户列表（管理员权限）

**请求类型：** `GET`

**接口路径：** `/console/api/users/all`

**是否需要登录：** 是

**权限要求：** 管理员

**请求参数：** 无

**返回示例：**
```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "id": "uuid-string",
      "username": "admin",
      "nickname": "管理员",
      "avatar": "http://example.com/avatar.jpg",
      "status": "normal",
      "default_lang": "zh-CN",
      "user_group_name": "管理员组",
      "role": "admin",
      "login_at": "2025-01-20T10:30:00"
    }
  ]
}
```

---

### 1.8 用户管理（增删改）

**接口描述：** 管理员对用户进行创建、更新、删除操作

**请求类型：** `POST` / `PUT` / `DELETE`

**接口路径：** `/console/api/users/manage`

**是否需要登录：** 是

**权限要求：** 管理员

#### 1.8.1 创建用户（POST）

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| username | string | 是 | 用户名 |
| nickname | string | 是 | 昵称 |
| email | string | 否 | 邮箱 |
| password | string | 是 | 密码（3-20位） |
| user_group_id | string | 否 | 用户组ID |
| role | string | 是 | 角色（normal/admin） |

**请求示例：**
```json
{
  "username": "newuser",
  "nickname": "新用户",
  "email": "user@example.com",
  "password": "123456",
  "user_group_id": "uuid-string",
  "role": "normal"
}
```

#### 1.8.2 更新用户（PUT）

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| id | string | 是 | 用户ID |
| username | string | 否 | 用户名 |
| nickname | string | 否 | 昵称 |
| email | string | 否 | 邮箱 |
| user_group_id | string | 否 | 用户组ID |
| role | string | 否 | 角色 |

**请求示例：**
```json
{
  "id": "uuid-string",
  "nickname": "更新后的昵称",
  "role": "admin"
}
```

#### 1.8.3 删除用户（DELETE）

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| id | string | 是 | 用户ID |

**请求示例：**
```json
{
  "id": "uuid-string"
}
```

**返回示例：**
```json
{
  "code": 200,
  "message": "用户删除成功"
}
```

---

## 2. API Key管理模块

### 2.1 API Key认证说明

**API Key认证方式：**

API Key是一种无状态的认证方式，适用于插件接口、外部系统调用等场景。使用API Key时，不需要登录Session，只需在请求头中携带有效的API Key即可。

**支持的认证头格式：**

1. **Authorization头（推荐）**
   ```
   Authorization: <api_key>
   ```

2. **Authorization头（Bearer格式）**
   ```
   Authorization: Bearer <api_key>
   ```

3. **X-API-Key头**
   ```
   X-API-Key: <api_key>
   ```

**API Key验证规则：**
- API Key必须处于`active`状态
- API Key未过期（`expires_at`为空或未到期）
- API Key关联的用户必须存在且有效
- 每次成功调用后，系统会更新`last_used_at`字段

**错误响应：**
- `401 Unauthorized`: 缺少API Key或API Key无效
- `403 Forbidden`: API Key已禁用或已过期

---

### 2.2 查询API Key

**接口描述：** 查询API Key列表或单个API Key详情

**请求类型：** `GET`

**接口路径：** `/console/api/api_keys`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| id | string | 否 | API Key ID（UUID），传入时返回单条记录 |

**请求示例（查询列表）：**
```
GET /console/api/api_keys
```

**请求示例（查询单条）：**
```
GET /console/api/api_keys?id=550e8400-e29b-41d4-a716-446655440000
```

**返回示例（列表）：**
```json
{
  "code": 200,
  "msg": "success",
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "660e8400-e29b-41d4-a716-446655440001",
      "name": "生产环境API Key",
      "api_key": "ak_xxxxxxxxxxxxxxxxxxxxxxxx",
      "status": "active",
      "expires_at": "2025-12-31T23:59:59+00:00",
      "last_used_at": "2025-12-29T10:30:00+00:00",
      "created_at": "2025-01-01T00:00:00+00:00",
      "updated_at": "2025-01-01T00:00:00+00:00"
    }
  ]
}
```

**返回示例（单条）：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "660e8400-e29b-41d4-a716-446655440001",
    "name": "生产环境API Key",
    "api_key": "ak_xxxxxxxxxxxxxxxxxxxxxxxx",
    "status": "active",
    "expires_at": "2025-12-31T23:59:59+00:00",
    "last_used_at": "2025-12-29T10:30:00+00:00",
    "created_at": "2025-01-01T00:00:00+00:00",
    "updated_at": "2025-01-01T00:00:00+00:00"
  }
}
```

**返回字段说明：**
- `id`: API Key唯一标识
- `user_id`: 所属用户ID（用于数据隔离）
- `name`: API Key名称/备注
- `api_key`: API Key明文（仅创建时和查询时返回）
- `status`: 状态（active=可用，disabled=已禁用）
- `expires_at`: 过期时间（ISO 8601格式，null表示永不过期）
- `last_used_at`: 最后使用时间
- `created_at`: 创建时间
- `updated_at`: 更新时间

---

### 2.3 创建API Key

**接口描述：** 为指定用户创建新的API Key

**请求类型：** `POST`

**接口路径：** `/console/api/api_keys`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| user_id | string | 是 | 用户ID（UUID） |
| name | string | 是 | API Key名称/备注（用于区分不同Key） |
| api_key | string | 否 | 自定义API Key（不传则系统自动生成） |
| expires_at | string | 否 | 过期时间（ISO 8601格式，不传则永不过期） |

**请求示例（自动生成API Key）：**
```json
{
  "user_id": "660e8400-e29b-41d4-a716-446655440001",
  "name": "生产环境API Key",
  "expires_at": "2025-12-31T23:59:59+00:00"
}
```

**请求示例（自定义API Key）：**
```json
{
  "user_id": "660e8400-e29b-41d4-a716-446655440001",
  "name": "测试环境API Key",
  "api_key": "ak_custom_key_12345678901234567890",
  "expires_at": null
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "api_key": "ak_xxxxxxxxxxxxxxxxxxxxxxxx"
  }
}
```

**说明：**
1. 如果不传`api_key`参数，系统会自动生成格式为`ak_`开头的32字符随机字符串
2. API Key创建后，`api_key`明文只在创建时返回一次，后续查询不会返回完整明文
3. `expires_at`为空或null表示永不过期
4. 创建时`status`默认为`active`

---

### 2.4 更新API Key

**接口描述：** 更新API Key的名称、状态或过期时间

**请求类型：** `PUT`

**接口路径：** `/console/api/api_keys`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| id | string | 是 | API Key ID（UUID） |
| name | string | 否 | API Key名称/备注 |
| status | string | 否 | 状态（active/disabled） |
| expires_at | string | 否 | 过期时间（ISO 8601格式，null=永不过期） |

**请求示例（更新名称和状态）：**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "生产环境API Key（已更新）",
  "status": "disabled"
}
```

**请求示例（延长过期时间）：**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "expires_at": "2026-12-31T23:59:59+00:00"
}
```

**请求示例（设为永不过期）：**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "expires_at": null
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**重要规则：**
1. `expires_at`只能延长，不能缩短（安全考虑）
2. 如果原本就有过期时间，新的`expires_at`必须晚于原过期时间
3. 可以将有过期时间的Key改为永不过期（传`null`）
4. `status`只能设为`active`或`disabled`

**错误响应（尝试缩短过期时间）：**
```json
{
  "code": 400,
  "msg": "expires_at 只能延长，不能缩短",
  "data": null
}
```

---

### 2.5 删除API Key

**接口描述：** 删除指定的API Key

**请求类型：** `DELETE`

**接口路径：** `/console/api/api_keys`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| id | string | 是 | API Key ID（UUID） |

**请求示例：**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**说明：** 删除API Key后，使用该Key的所有请求将立即失效

---

## 3. 数据源管理模块

### 3.1 测试数据库连接

**接口描述：** 测试数据库连接是否可用

**请求类型：** `POST`

**接口路径：** `/console/api/connect_test`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| connect_name | string | 是 | 连接名称（用于标识） |
| db_type | string | 是 | 数据库类型（mysql/postgresql/mssql/oracle/sqlite/trino/kingbase/oceanbase/dm） |
| username | string | 是* | 用户名（部分数据库必填） |
| password | string | 是* | 密码（部分数据库必填） |
| host | string | 是* | 主机地址（部分数据库必填） |
| port | integer | 是* | 端口号（部分数据库必填） |
| database | string | 是* | 数据库名（部分数据库必填） |
| service_name | string | 否 | Oracle服务名（Oracle数据库） |
| sid | string | 否 | Oracle SID（Oracle数据库） |
| dsn | string | 否 | SQL Server DSN（SQL Server数据库） |
| sqlite_memory | boolean | 否 | SQLite内存模式（SQLite数据库） |
| sqlite_path | string | 否 | SQLite文件路径（SQLite数据库） |

**数据库类型说明：**
- **MySQL**: 需要 username, password, host, port, database
- **PostgreSQL**: 需要 username, password, host, port, database
- **SQL Server**: 需要 username, password, (dsn 或 host+port), database
- **Oracle**: 需要 username, password, host, port, (service_name 或 sid)
- **SQLite**: 需要 (sqlite_memory=true 或 sqlite_path)
- **Trino**: 需要 host, port, catalog, schema
- **电科金仓（KingBase）**: 需要 username, password, host, port, database（基于 PostgreSQL 内核，兼容 PostgreSQL 语法）
- **OceanBase（MySQL 租户模式）**: 需要 username, password, host, port, database；使用 mysql+pymysql 协议，默认端口 2881
- **达梦（DMBase）**: 需要 username, password, host, port, database（兼容 Oracle 语法）

> **💡 TIP**：OceanBase 原生提供 MySQL 与 Oracle 双兼容模式，当前 API 已支持 **MySQL 租户模式**；**Oracle 租户模式将在后续版本中支持**。

**请求示例（MySQL）：**
```json
{
  "connect_name": "生产库A",
  "db_type": "mysql",
  "username": "root",
  "password": "password123",
  "host": "192.168.1.100",
  "port": 3306,
  "database": "test_db"
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "连接成功",
  "result": {
    "database_type": "mysql",
    "database_version": "8.0.33",
    "connection": "mysql+pymysql://root:***@192.168.1.100:3306/test_db"
  }
}
```

**错误响应：**
```json
{
  "code": 400,
  "msg": "数据库连接失败: Access denied for user",
  "result": null
}
```

---

### 3.2 提取数据库表结构

**接口描述：** 从数据库中提取表结构信息，并生成数据卡片。支持全量抽取（所有表）或指定抽取（仅特定表）。

**请求类型：** `POST`

**接口路径：** `/console/api/extract_schema`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| connect_name | string | 是 | 连接名称 |
| db_type | string | 是 | 数据库类型 |
| username | string | 是* | 用户名 |
| password | string | 是* | 密码 |
| host | string | 是* | 主机地址 |
| port | integer | 是* | 端口号 |
| database | string | 是* | 数据库名 |
| service_name | string | 否 | Oracle服务名 |
| sid | string | 否 | Oracle SID |
| dsn | string | 否 | SQL Server DSN |
| sqlite_memory | boolean | 否 | SQLite内存模式 |
| sqlite_path | string | 否 | SQLite文件路径 |
| target_schema | string | 否 | 指定schema（Oracle等） |
| schema | string | 否 | 指定schema（PostgreSQL、MSSQL、Trino） |
| catalog | string | 否 | Trino专用，catalog名称 |
| is_audit | boolean | 否 | 是否执行数据盘查（默认false） |
| request_id | string | 否 | 请求ID（用于取消操作） |
| table_names | array/string | 否 | 要抽取的表名列表。不传表示全量抽取，支持数组格式 `["users","orders"]` 或逗号分隔字符串 `"users,orders"` |

**请求示例（全量抽取）：**
```json
{
  "connect_name": "生产库A",
  "db_type": "mysql",
  "username": "root",
  "password": "password123",
  "host": "192.168.1.100",
  "port": 3306,
  "database": "test_db",
  "request_id": "req-123456"
}
```

**请求示例（抽取指定表）：**
```json
{
  "connect_name": "生产库A",
  "db_type": "mysql",
  "username": "root",
  "password": "password123",
  "host": "192.168.1.100",
  "port": 3306,
  "database": "test_db",
  "table_names": ["customers", "orders"],
  "request_id": "req-123456"
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "提取成功",
  "data": {
    "insert_result": {
      "message": "success",
      "inserted": 2,
      "skipped": 0,
      "total": 2
    },
    "generated_cards": [
      {
        "id": "uuid-xxx",
        "table_name": "customers",
        "card_content": "..."
      }
    ],
    "datasource_info": {
      "id": "ds-xxx",
      "connect_name": "生产库A",
      "database_type": "mysql"
    }
  }
}
```

---

### 3.3 获取数据源中的表列表

**接口描述：** 获取数据源中的所有表和视图列表（不提取结构），用于前端展示让用户选择要抽取的表。

**请求类型：** `POST`

**接口路径：** `/console/api/list_tables`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| connect_name | string | 是 | 连接名称 |
| db_type | string | 是 | 数据库类型 |
| username | string | 是* | 用户名 |
| password | string | 是* | 密码 |
| host | string | 是* | 主机地址 |
| port | integer | 是* | 端口号 |
| database | string | 是* | 数据库名 |
| service_name | string | 否 | Oracle服务名 |
| sid | string | 否 | Oracle SID |
| dsn | string | 否 | SQL Server DSN |
| sqlite_memory | boolean | 否 | SQLite内存模式 |
| sqlite_path | string | 否 | SQLite文件路径 |
| target_schema | string | 否 | 指定schema（Oracle等） |
| schema | string | 否 | 指定schema（PostgreSQL、MSSQL、Trino） |
| catalog | string | 否 | Trino专用，catalog名称 |

**请求示例：**
```json
{
  "connect_name": "生产库A",
  "db_type": "mysql",
  "username": "root",
  "password": "password123",
  "host": "192.168.1.100",
  "port": 3306,
  "database": "test_db"
}
```

**成功响应：**
```json
{
  "code": 200,
  "msg": "success",
  "result": {
    "tables": [
      { "name": "customers", "type": "TABLE" },
      { "name": "orders", "type": "TABLE" },
      { "name": "products", "type": "TABLE" },
      { "name": "user_stats_view", "type": "VIEW" }
    ],
    "total": 4
  }
}
```

**响应字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| tables | array | 表和视图列表 |
| tables[].name | string | 表或视图的名称 |
| tables[].type | string | 类型：`TABLE`（表）或 `VIEW`（视图） |
| total | integer | 表的总数 |

**错误响应：**
```json
{
  "code": 400,
  "msg": "数据库连接失败: Access denied",
  "result": null
}
```

---

### 3.4 取消提取表结构

**接口描述：** 取消正在进行的表结构提取操作，并清理已生成的数据

**请求类型：** `POST`

**接口路径：** `/console/api/cancel_extract_schema`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| request_id | string | 是 | 请求ID |
| config | object | 否 | 数据源配置（用于清理数据） |

**请求示例：**
```json
{
  "request_id": "req-123456",
  "config": {
    "connect_name": "生产库A",
    "db_type": "mysql",
    "host": "192.168.1.100",
    "port": 3306,
    "database": "test_db"
  }
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "取消成功，已清理所有相关数据",
  "data": {
    "request_id": "req-123456",
    "deleted_schemas": 50,
    "deleted_cards": 50,
    "deleted_weaviate": 50,
    "deleted_datasource": 1,
    "status": "cancelled"
  }
}
```

---

### 3.5 获取数据源列表

**接口描述：** 分页获取当前用户的所有数据源列表

**请求类型：** `GET`

**接口路径：** `/console/api/datasource_tool`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| user_id | string | 否 | 用户ID（默认当前用户） |
| page | integer | 否 | 页码（默认1） |
| page_size | integer | 否 | 每页数量（默认10，最大100） |

**请求示例：**
```
GET /console/api/datasource_tool?page=1&page_size=20
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "查询成功",
  "data": {
    "items": [
      {
        "id": "uuid-string",
        "user_id": "uuid-string",
        "connect_name": "生产库A",
        "db_type": "mysql",
        "database_name": "test_db",
        "table_num": 50,
        "status": "available",
        "connect_info": "mysql+pymysql://root:***@192.168.1.100:3306/test_db",
        "datacard_count": 50,
        "weaviate_num": 48,
        "schemas": [
          {
            "id": "uuid-string",
            "table_name": "users",
            "db_type": "mysql",
            "database_name": "test_db",
            "db_version": "8.0",
            "is_view": false,
            "view_name": null,
            "is_filled": true,
            "catalog_type": "mysql",
            "schema_text": {
              "columns": [
                {"name": "id", "type": "int", "nullable": false, "primary_key": true},
                {"name": "name", "type": "varchar(100)", "nullable": true}
              ],
              "indexes": []
            },
            "filled_data": {
              "table_comment": "用户表",
              "business_desc": "存储系统用户信息"
            },
            "created_at": "2025-01-20T10:30:00",
            "updated_at": "2025-01-20T10:30:00"
          }
        ],
        "created_at": "2025-01-20T10:30:00",
        "updated_at": "2025-01-20T10:30:00"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 5,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false,
    "weaviate_count": 50
  }
}
```

**返回字段说明：**
- `datacard_count`: 该数据源关联的数据卡片数量
- `weaviate_num`: 该数据源在向量库中实际存在的记录数量（用于校验同步状态）
- `schemas`: 该数据源关联的表结构信息列表
  - `schema_text`: 表结构详情（已解析为JSON对象，包含列信息、索引等）
  - `filled_data`: LLM填充的业务描述信息
- `weaviate_count`: 当前用户向量库中的总记录数（跨所有数据源）

---

### 3.6 更新数据源信息

**接口描述：** 更新数据源的连接名称、状态等信息

**请求类型：** `PUT`

**接口路径：** `/console/api/datasource_tool/<ds_id>`

**是否需要登录：** 是

**路径参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| ds_id | string | 是 | 数据源ID |

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| connect_name | string | 否 | 连接名称 |
| status | string | 否 | 状态（available/unavailable） |
| db_type | string | 否 | 数据库类型 |
| database_name | string | 否 | 数据库名 |
| table_num | integer | 否 | 表数量 |

**请求示例：**
```json
{
  "connect_name": "更新后的连接名",
  "status": "available"
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "更新成功",
  "data": {
    "id": "uuid-string",
    "user_id": "uuid-string",
    "connect_name": "更新后的连接名",
    "db_type": "mysql",
    "database_name": "test_db",
    "table_num": 50,
    "status": "available",
    "connect_info": "mysql+pymysql://root:***@192.168.1.100:3306/test_db",
    "created_at": "2025-01-20T10:30:00",
    "updated_at": "2025-01-20T10:30:00",
    "schemas_updated": 0,
    "cards_updated": 1
  }
}
```

**返回字段说明：**
- `schemas_updated`: 同步更新的表结构记录数（connect_name 变更时同步）
- `cards_updated`: 同步更新的数据卡片记录数（connect_name 变更时同步）

---

### 3.7 删除数据源

**接口描述：** 删除指定的数据源及其关联的所有数据（表结构、数据卡片、向量数据、盘点数据、术语库关联等）

**请求类型：** `DELETE`

**接口路径：** `/console/api/datasource_tool/<ds_id>`

**是否需要登录：** 是

**路径参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| ds_id | string | 是 | 数据源ID |

**请求参数：** 无

**返回示例：**
```json
{
  "code": 200,
  "msg": "删除成功",
  "data": {
    "id": "uuid-string",
    "schemas_deleted": 50,
    "cards_deleted": 50,
    "term_library_links_deleted": 2,
    "inventory_jobs_deleted": 1,
    "inventory_job_results_deleted": 10,
    "table_relationships_deleted": 5,
    "table_relationship_cards_deleted": 5,
    "field_mappings_deleted": 20,
    "weaviate_count": 50,
    "weaviate_deleted": true,
    "field_index_deleted": 50
  }
}
```

**返回字段说明：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| schemas_deleted | integer | 删除的表结构记录数 |
| cards_deleted | integer | 删除的数据卡片记录数 |
| term_library_links_deleted | integer | 删除的数据源-术语库关联记录数 |
| inventory_jobs_deleted | integer | 删除的盘点任务记录数 |
| inventory_job_results_deleted | integer | 删除的盘点任务结果记录数 |
| table_relationships_deleted | integer | 删除的表关系记录数 |
| table_relationship_cards_deleted | integer | 删除的表关系卡片记录数 |
| field_mappings_deleted | integer | 删除的字段映射记录数 |
| weaviate_count | integer | 向量库中该数据源的记录数（删除前） |
| weaviate_deleted | boolean | 向量库数据是否删除成功 |
| field_index_deleted | integer | 删除的字段画像向量索引记录数 |

---

### 3.8 刷新数据源

**接口描述：** 刷新数据源，支持快速刷新（仅测试连接并更新状态）和全量刷新（重新提取表结构并更新数据卡片）两种模式

**请求类型：** `POST`

**接口路径：** `/console/api/datasource_tool/<ds_id>/refresh`

**是否需要登录：** 是

**路径参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| ds_id | string | 是 | 数据源ID |

**Query参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| mode | string | 否 | 刷新模式（quick/full，默认full） |

**模式说明：**
- **quick**：快速刷新，仅测试数据库连接并更新数据源状态，不重新提取表结构
- **full**：全量刷新，重新提取所有表结构，对比差异后更新数据卡片和向量库

#### 3.8.1 快速刷新（quick）

**请求示例：**
```
POST /console/api/datasource_tool/uuid-string/refresh?mode=quick
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "刷新完成（quick）",
  "data": {
    "mode": "quick",
    "id": "uuid-string",
    "connect_name": "生产库A",
    "status_before": "unavailable",
    "status_after": "available",
    "database_type": "mysql",
    "database_name": "test_db",
    "database_version": "8.0.33",
    "connection": "mysql+pymysql://root:***@192.168.1.100:3306/test_db",
    "error": null
  }
}
```

**返回字段说明：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| mode | string | 刷新模式（quick） |
| id | string | 数据源ID |
| connect_name | string | 连接名称 |
| status_before | string | 刷新前状态 |
| status_after | string | 刷新后状态（available/unavailable） |
| database_type | string | 数据库类型 |
| database_name | string | 数据库名称 |
| database_version | string | 数据库版本 |
| connection | string | 连接字符串（密码已脱敏） |
| error | string/null | 连接失败时的错误信息 |

#### 3.8.2 全量刷新（full）

**请求示例：**
```
POST /console/api/datasource_tool/uuid-string/refresh?mode=full
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "刷新完成（full）",
  "data": {
    "mode": "full",
    "added_tables": ["new_table1"],
    "removed_tables": ["deleted_table"],
    "changed_tables": ["updated_table1", "updated_table2"],
    "unchanged_tables": 47,
    "schemas_deleted": 1,
    "cards_deleted": 1,
    "weaviate_deleted": 1,
    "cards_generated": 3,
    "total_tables": 50
  }
}
```

**返回字段说明：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| mode | string | 刷新模式（full） |
| added_tables | array | 新增的表名列表 |
| removed_tables | array | 已删除的表名列表 |
| changed_tables | array | 结构变更的表名列表 |
| unchanged_tables | integer | 未变更的表数量 |
| schemas_deleted | integer | 删除的表结构记录数（对应removed_tables） |
| cards_deleted | integer | 删除的数据卡片数（对应removed_tables） |
| weaviate_deleted | integer | 从向量库删除的记录数 |
| cards_generated | integer | 新生成的数据卡片数（added + changed） |
| total_tables | integer | 刷新后数据源的总表数 |

---

## 4. 数据卡片管理模块

### 4.1 获取数据卡片列表

**接口描述：** 获取当前用户的所有数据卡片，支持按数据源筛选、关键字搜索、分页

**请求类型：** `GET`

**接口路径：** `/console/api/datacard_tool`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| connect_name | string | 否 | 按数据源名称筛选 |
| q | string | 否 | 关键字检索（在card_data中模糊匹配） |
| page | integer | 否 | 页码（默认1） |
| page_size | integer | 否 | 每页数量（默认50，最大200） |
| group_by | string | 否 | 分组方式（datasource/flat，默认datasource） |
| parse_json | boolean | 否 | 是否解析card_data为JSON对象（默认false） |

**请求示例：**
```
GET /console/api/datacard_tool?connect_name=生产库A&q=订单&page=1&page_size=20&parse_json=true
```

**返回示例（group_by=datasource）：**
```json
{
  "code": 200,
  "msg": "操作成功",
  "data": {
    "total_cards": 50,
    "total_datasources": 2,
    "items": [
      {
        "datasource": {
          "connect_name": "生产库A",
          "db_type": "mysql",
          "database_name": "test_db",
          "table_num": 30,
          "status": "available",
          "connect_info_masked": "mysql+pymysql://root:***@192.168.1.100:3306/test_db"
        },
        "cards": [
          {
            "doc_id": "uuid-string",
            "table_name": "orders",
            "connect_name": "生产库A",
            "connect_info_masked": "mysql+pymysql://root:***@192.168.1.100:3306/test_db",
            "w_uuid": "uuid-string",
            "card_data": "{\"table_name\":\"orders\",\"columns\":[...]}"
          }
        ]
      }
    ]
  }
}
```

**返回示例（group_by=flat）：**
```json
{
  "code": 200,
  "msg": "操作成功",
  "data": {
    "total_cards": 50,
    "total_datasources": 2,
    "items": [
      {
        "doc_id": "uuid-string",
        "table_name": "orders",
        "connect_name": "生产库A",
        "w_uuid": "uuid-string",
        "card_data": "{\"table_name\":\"orders\",\"columns\":[...]}"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 50,
    "total_pages": 3
  }
}
```

---

### 4.2 更新数据卡片

**接口描述：** 更新指定数据卡片的内容

**请求类型：** `PUT`

**接口路径：** `/console/api/datacard_tool`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| doc_id | string | 是 | 数据卡片ID（对应表结构ID） |
| card_data | object | 是 | 数据卡片内容（JSON对象） |

**请求示例：**
```json
{
  "doc_id": "uuid-string",
  "card_data": {
    "table_name": "orders",
    "table_desc": "订单表",
    "columns": [
      {
        "name": "id",
        "type": "int",
        "comment": "订单ID",
        "nullable": false
      }
    ]
  }
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "更新成功",
  "data": {
    "doc_id": "uuid-string",
    "w_uuid": "new-uuid-string",
    "card_data": {...},
    "_vector_ops": {
      "delete_old_ok": true,
      "old_w_uuid": "old-uuid-string",
      "new_w_uuid": "new-uuid-string"
    }
  }
}
```

**说明：** 更新数据卡片时，系统会自动更新向量数据库（Weaviate）中的向量数据。

---

## 5. 数据盘点模块

### 5.1 定向盘点

#### 5.1.1 获取数据源表列表

**接口描述：** 获取指定数据源下的所有表，包含表的质量等级、缺失字段数等信息

**请求类型：** `GET`

**接口路径：** `/console/api/target_inventory/tables`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| datasource_id | string | 是 | 数据源ID |

**响应示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "tables": [
      {
        "table_name": "orders",
        "quality_level": "low",
        "missing_fields_count": 5,
        "is_ai_filled": false
      },
      {
        "table_name": "customers",
        "quality_level": "high",
        "missing_fields_count": 0,
        "is_ai_filled": false
      }
    ]
  }
}
```

**质量等级说明：**
- `low`: 目标表（需要补充注释的表）
- `medium`: LLM填充表（已通过AI补充注释）
- `high`: 优质参考表（注释完整的表）

---

#### 5.1.2 启动定向盘点任务

**接口描述：** 创建定向盘点任务，对选定的目标表进行字段注释推荐和表关系推断

**请求类型：** `POST`

**接口路径：** `/console/api/target_inventory/run`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| datasource_id | string | 是 | 数据源ID |
| target_tables | array | 是 | 目标表列表（需要补充注释的表） |
| ref_tables | array | 否 | 参考表列表（用于提供候选注释） |
| dict_file_id | string | 否 | 数据字典文件ID |
| options | object | 否 | 其他配置选项 |

**请求示例：**
```json
{
  "datasource_id": "xxx-xxx-xxx",
  "target_tables": ["orders", "order_items"],
  "ref_tables": ["customers", "products"],
  "dict_file_id": "dict-001",
  "options": {
    "enable_profiling": true,
    "confidence_threshold": 0.7
  }
}
```

**响应示例：**
```json
{
  "code": 200,
  "msg": "任务创建成功",
  "data": {
    "job_id": "job-xxx-xxx",
    "status": "queued",
    "created_at": "2025-01-15T10:30:00Z"
  }
}
```

---

#### 5.1.3 确认字段映射

**接口描述：** 用户确认字段注释推荐结果，保存到字段映射表

**请求类型：** `POST`

**接口路径：** `/console/api/target_inventory/confirm`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| job_id | string | 是 | 盘点任务ID |
| mappings | array | 是 | 字段映射列表 |

**请求示例：**
```json
{
  "job_id": "job-xxx-xxx",
  "mappings": [
    {
      "source_table": "customers",
      "source_column": "customer_name",
      "target_table": "orders",
      "target_column": "cust_name",
      "mapping_type": "semantic_match",
      "confidence": 0.95
    }
  ]
}
```

---

#### 5.1.4 确认表关系

**接口描述：** 用户确认表关系推断结果，保存到表关系表

**请求类型：** `POST`

**接口路径：** `/console/api/target_inventory/confirm_relationships`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| job_id | string | 是 | 盘点任务ID |
| relationships | array | 是 | 表关系列表 |

**请求示例：**
```json
{
  "job_id": "job-xxx-xxx",
  "relationships": [
    {
      "table_a": "orders",
      "table_b": "customers",
      "relationship_type": "foreign_key",
      "join_conditions": [
        {
          "column_a": "customer_id",
          "column_b": "id",
          "operator": "="
        }
      ],
      "cardinality": "N:1",
      "confidence": 0.98
    }
  ]
}
```

---

#### 5.1.5 生成关系卡片

**接口描述：** 基于确认的表关系生成关系卡片并入库（数据库+向量库）

**请求类型：** `POST`

**接口路径：** `/console/api/target_inventory/generate_cards`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| job_id | string | 是 | 盘点任务ID |

**响应示例：**
```json
{
  "code": 200,
  "msg": "关系卡片生成成功",
  "data": {
    "cards_count": 5,
    "vector_indexed": true
  }
}
```

---

### 5.2 全域盘点

#### 5.2.1 启动全域盘点

**接口描述：** 自动对数据源所有表进行关系发现，支持单数据源和多数据源模式

**请求类型：** `POST`

**接口路径：** `/console/api/global_inventory/discover`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| datasource_id | string | 否 | 单数据源ID（与datasource_ids二选一） |
| datasource_ids | array | 否 | 多数据源ID列表（与datasource_id二选一） |
| schema_name | string | 否 | Schema名称（默认使用数据源配置的Schema） |
| confidence_threshold | float | 否 | 置信度阈值（默认0.5） |
| max_workers | int | 否 | 最大并行线程数（默认5） |
| enable_profiling | boolean | 否 | 是否启用字段画像（默认true） |

**请求示例（单数据源）：**
```json
{
  "datasource_id": "xxx-xxx-xxx",
  "schema_name": "public",
  "confidence_threshold": 0.6,
  "max_workers": 8,
  "enable_profiling": true
}
```

**请求示例（多数据源）：**
```json
{
  "datasource_ids": ["xxx-xxx-xxx", "yyy-yyy-yyy"],
  "confidence_threshold": 0.7,
  "max_workers": 10
}
```

**响应示例：**
```json
{
  "code": 200,
  "msg": "全域盘点完成",
  "data": {
    "success": true,
    "tables_count": 25,
    "relationships_count": 48,
    "cards_count": 25,
    "is_multi_source": false,
    "cross_source_count": 0,
    "execution_time": "125.3s"
  }
}
```

**响应示例（多数据源）：**
```json
{
  "code": 200,
  "msg": "全域盘点完成",
  "data": {
    "success": true,
    "tables_count": 50,
    "relationships_count": 95,
    "cards_count": 50,
    "is_multi_source": true,
    "cross_source_count": 12,
    "execution_time": "256.7s"
  }
}
```

---

#### 5.2.2 获取单表关系卡片

**接口描述：** 获取指定表的完整关系卡片数据

**请求类型：** `GET`

**接口路径：** `/console/api/global_inventory/cards/<datasource_id>/<table_name>`

**是否需要登录：** 是

**路径参数：**

| 参数名 | 类型 | 参数说明 |
|--------|------|----------|
| datasource_id | string | 数据源ID |
| table_name | string | 表名 |

**响应示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "table_name": "orders",
    "datasource_id": "xxx-xxx-xxx",
    "relationships": [
      {
        "target_table": "customers",
        "target_datasource_id": "xxx-xxx-xxx",
        "join_conditions": [
          {
            "source_column": "customer_id",
            "target_column": "id",
            "operator": "="
          }
        ],
        "relationship_type": "foreign_key",
        "relationship_strength": 0.95,
        "cardinality": "N:1",
        "is_cross_source": false
      },
      {
        "target_table": "products",
        "target_datasource_id": "yyy-yyy-yyy",
        "join_conditions": [
          {
            "source_column": "product_code",
            "target_column": "code",
            "operator": "="
          }
        ],
        "relationship_type": "semantic_match",
        "relationship_strength": 0.82,
        "cardinality": "N:1",
        "is_cross_source": true
      }
    ],
    "related_datasource_ids": ["xxx-xxx-xxx", "yyy-yyy-yyy"],
    "has_cross_source_relations": true
  }
}
```

---

#### 5.2.3 获取数据源所有关系卡片

**接口描述：** 获取指定数据源下所有表的关系卡片列表

**请求类型：** `GET`

**接口路径：** `/console/api/global_inventory/cards/<datasource_id>`

**是否需要登录：** 是

**路径参数：**

| 参数名 | 类型 | 参数说明 |
|--------|------|----------|
| datasource_id | string | 数据源ID |

**响应示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "datasource_id": "xxx-xxx-xxx",
    "cards": [
      {
        "table_name": "orders",
        "relationships_count": 3,
        "has_cross_source_relations": false
      },
      {
        "table_name": "customers",
        "relationships_count": 2,
        "has_cross_source_relations": true
      }
    ],
    "total_count": 25
  }
}
```

---

## 6. 智能查询模块

### 6.1 基于数据卡片的聚合查询（Session认证）

**接口描述：** 根据自然语言问题，智能检索相关数据卡片，生成SQL并执行查询，支持多表关联和跨数据源查询

**请求类型：** `POST`

**接口路径：** `/console/api/query_by_datacards_agg`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| query | string | 是 | 自然语言查询问题 |
| datasource_id | string | 否 | 指定单个数据源ID（UUID格式） |
| datasource_ids | array | 否 | 指定数据源ID列表（UUID格式数组） |
| enable_rerank | boolean | 否 | 是否启用重排序（默认true，可提升召回精度） |
| enable_term_rewrite | boolean | 否 | 是否启用术语展开（默认true，自动识别并展开业务术语） |
| library_ids | array | 否 | 指定术语库ID列表（不传则根据数据源自动匹配已关联的启用术语库） |

**说明：**
- 融合策略（AND/OR/PRIORITY/UNION）由系统根据自然语言问题自动推断，无需手动指定
- 查询类型（聚合/明细）由系统自动检测，无需手动指定
- 不指定数据源时，搜索当前用户的所有数据源

**请求示例：**
```json
{
  "query": "查询最近一个月订单金额大于1000的客户信息",
  "enable_rerank": true
}
```

**使用数据源ID的请求示例：**
```json
{
  "query": "查询最近一个月订单金额大于1000的客户信息",
  "datasource_ids": ["550e8400-e29b-41d4-a716-446655440000", "660e8400-e29b-41d4-a716-446655440001"],
  "enable_rerank": true
}
```

**使用单个数据源ID的请求示例：**
```json
{
  "query": "查询最近一个月订单金额大于1000的客户信息",
  "datasource_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "clusters": [
      {
        "db_type": "mysql",
        "connect_name": "生产库A",
        "cluster_tables": [
          {
            "table_name": "orders",
            "columns": [
              {"name": "order_id", "type": "int"},
              {"name": "customer_id", "type": "varchar"},
              {"name": "amount", "type": "decimal"},
              {"name": "create_time", "type": "datetime"}
            ]
          }
        ],
        "target_sql": "SELECT o.customer_id, SUM(o.amount) as total_amount FROM orders o WHERE o.create_time >= DATE_SUB(NOW(), INTERVAL 1 MONTH) AND o.amount > 1000 GROUP BY o.customer_id",
        "rows": [
          {
            "customer_id": "C001",
            "total_amount": 5000.00
          }
        ],
        "entity_ids": ["C001"],
        "datasource_ids": ["uuid1"],
        "datasource_names": ["生产库A"],
        "table_names": ["orders"],
        "warnings": []
      }
    ],
    "merge": {
      "strategy": "SINGLE_CLUSTER",
      "entity_key": "customer_id",
      "fusion_method": "none",
      "note": "单数据源查询，无需跨源融合"
    },
    "final_rows": [
      {
        "customer_id": "C001",
        "total_amount": 5000.00
      }
    ],
    "fill_warnings": [],
    "data_cards": [
      {
        "doc_id": "uuid-string",
        "table_name": "orders",
        "database_name": "ecommerce_db",
        "connect_name": "生产库A",
        "card_content": {}
      }
    ],
    "term_rewrite": {
      "enabled": true,
      "matched_count": 1,
      "matched_terms": [
        {
          "term_name": "GMV",
          "term_definition": "商品交易总额",
          "matched_alias": "订单金额",
          "library_name": "电商术语库"
        }
      ],
      "rewritten_question": "查询最近一个月GMV（商品交易总额）大于1000的客户信息"
    }
  }
}
```

**返回字段说明：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| clusters | array | 各数据源/簇的查询结果列表 |
| clusters[].db_type | string | 数据库类型（mysql/postgresql等） |
| clusters[].connect_name | string | 数据源连接名称 |
| clusters[].cluster_tables | array | 该簇涉及的表结构信息（含列定义） |
| clusters[].target_sql | string | 生成并执行的SQL语句 |
| clusters[].rows | array | 该簇的原始查询结果行 |
| clusters[].entity_ids | array | 该簇查询到的实体ID列表（用于跨源融合） |
| clusters[].datasource_ids | array | 该簇涉及的数据源ID列表 |
| clusters[].datasource_names | array | 该簇涉及的数据源名称列表 |
| clusters[].table_names | array | 该簇涉及的表名列表 |
| clusters[].warnings | array | 该簇的警告信息 |
| merge | object | 融合策略信息 |
| merge.strategy | string | 融合策略（SINGLE_CLUSTER/AND/OR/PRIORITY/UNION/TRINO_UNIFIED） |
| merge.entity_key | string | 实体主键字段名 |
| merge.fusion_method | string | 融合方法（none/llm/rule） |
| merge.final_entity_ids | array | 融合后的最终实体ID列表（多簇场景） |
| final_rows | array | 最终返回的数据行（融合后） |
| fill_warnings | array | 融合过程中的警告信息 |
| data_cards | array | 本次查询命中的数据卡片信息 |
| data_cards[].doc_id | string | 数据卡片ID |
| data_cards[].table_name | string | 表名 |
| data_cards[].database_name | string | 数据库名 |
| data_cards[].connect_name | string | 数据源连接名称 |
| data_cards[].card_content | object | 数据卡片完整内容 |
| term_rewrite | object | 术语展开信息 |
| term_rewrite.enabled | boolean | 是否启用了术语展开 |
| term_rewrite.matched_count | integer | 匹配到的术语数量 |
| term_rewrite.matched_terms | array | 匹配到的术语列表 |
| term_rewrite.matched_terms[].term_name | string | 术语名称 |
| term_rewrite.matched_terms[].term_definition | string | 术语定义 |
| term_rewrite.matched_terms[].matched_name | string | 用户问题中匹配到的名称 |
| term_rewrite.matched_terms[].library_id | string | 术语库ID |
| term_rewrite.matched_terms[].library_name | string | 术语库名称 |
| term_rewrite.matched_terms[].related_fields | array | 关联字段列表 |
| term_rewrite.matched_terms[].related_datacards | array | 关联数据卡片列表 |
| term_rewrite.rewritten_question | string | 术语展开后的问题（实际用于检索的问题） |

**说明：**
1. 系统首先使用向量检索找到相关的数据卡片
2. 如果启用了术语展开（`enable_term_rewrite=true`），会先对问题进行术语识别和改写
3. 根据数据卡片构建表结构和关系
4. **优先使用关系卡片中的JOIN条件**（如果存在），提升多表查询准确率
5. 使用LLM生成SQL查询（结合关系卡片信息）
6. 执行SQL并返回结果
7. 如果涉及多个数据源，根据融合策略合并结果（利用关系信息）

**关系卡片增强效果：**
- JOIN条件准确率提升15-20%
- 多表查询成功率提升20-25%
- 支持跨数据源关系识别
- 显著减少笛卡尔积问题

---

### 6.2 基于数据卡片的聚合查询（API Key认证插件接口）

**接口描述：** 基于API Key认证的聚合查询接口，专为插件和外部系统调用设计，无需Session登录

**请求类型：** `POST`

**接口路径：** `/console/api/query_by_datacards_agg_plugin`

**是否需要登录：** 否（使用API Key认证）

**认证方式：** 在请求头中携带API Key（参见 [2.1 API Key认证说明](#21-api-key认证说明)）

**请求头示例：**
```
Authorization: ak_xxxxxxxxxxxxxxxxxxxxxxxx
或
Authorization: Bearer ak_xxxxxxxxxxxxxxxxxxxxxxxx
或
X-API-Key: ak_xxxxxxxxxxxxxxxxxxxxxxxx
```

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| query | string | 是 | 自然语言查询问题 |
| connect_name | string | 否 | 指定数据源名称（根据名称自动转换为数据源ID，优先级高于 datasource_id） |
| datasource_id | string | 否 | 指定单个数据源ID（UUID格式） |
| datasource_ids | array | 否 | 指定数据源ID列表（UUID格式数组） |
| enable_rerank | boolean | 否 | 是否启用重排序（默认true，可提升召回精度） |
| enable_term_rewrite | boolean | 否 | 是否启用术语展开（默认true，自动识别并展开业务术语） |
| library_ids | array | 否 | 指定术语库ID列表（不传则根据数据源自动匹配已关联的启用术语库） |

**参数优先级说明：**
- `connect_name` > `datasource_id` > `datasource_ids` > 不指定（搜索所有数据源）
- 当传入 `connect_name` 时，系统会根据该名称在用户的数据源中查找对应的数据源ID

**请求示例：**
```json
{
  "query": "查询最近一个月订单金额大于1000的客户信息",
  "enable_rerank": true
}
```

**使用数据源名称的请求示例：**
```json
{
  "query": "查询最近一个月订单金额大于1000的客户信息",
  "connect_name": "生产库A",
  "enable_rerank": true
}
```

**使用数据源ID的请求示例：**
```json
{
  "query": "查询最近一个月订单金额大于1000的客户信息",
  "datasource_ids": ["550e8400-e29b-41d4-a716-446655440000", "660e8400-e29b-41d4-a716-446655440001"],
  "enable_rerank": true
}
```

**使用单个数据源ID的请求示例：**
```json
{
  "query": "查询最近一个月订单金额大于1000的客户信息",
  "datasource_id": "550e8400-e29b-41d4-a716-446655440000",
  "enable_rerank": false
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "clusters": [
      {
        "db_type": "mysql",
        "connect_name": "生产库A",
        "cluster_tables": [
          {
            "table_name": "orders",
            "columns": [
              {"name": "order_id", "type": "int"},
              {"name": "customer_id", "type": "varchar"},
              {"name": "amount", "type": "decimal"},
              {"name": "create_time", "type": "datetime"}
            ]
          }
        ],
        "target_sql": "SELECT o.customer_id, SUM(o.amount) as total_amount FROM orders o WHERE o.create_time >= DATE_SUB(NOW(), INTERVAL 1 MONTH) AND o.amount > 1000 GROUP BY o.customer_id",
        "rows": [
          {
            "customer_id": "C001",
            "total_amount": 5000.00
          }
        ],
        "entity_ids": ["C001"],
        "datasource_ids": ["uuid1"],
        "datasource_names": ["生产库A"],
        "table_names": ["orders"],
        "warnings": []
      }
    ],
    "merge": {
      "strategy": "SINGLE_CLUSTER",
      "entity_key": "customer_id",
      "fusion_method": "none",
      "note": "单数据源查询，无需跨源融合"
    },
    "final_rows": [
      {
        "customer_id": "C001",
        "total_amount": 5000.00
      }
    ],
    "fill_warnings": [],
    "data_cards": [
      {
        "doc_id": "uuid-string",
        "table_name": "orders",
        "database_name": "ecommerce_db",
        "connect_name": "生产库A",
        "card_content": {}
      }
    ],
    "term_rewrite": {
      "enabled": true,
      "matched_count": 0,
      "matched_terms": [],
      "rewritten_question": "查询最近一个月订单金额大于1000的客户信息"
    }
  }
}
```

**返回字段说明：**

与 6.1 接口相同，请参考 [6.1 返回字段说明](#61-基于数据卡片的聚合查询session认证)。主要区别在于 `term_rewrite.matched_terms` 数组中每个元素还会包含以下字段：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| term_name | string | 术语名称 |
| term_definition | string | 术语定义 |
| matched_name | string | 用户问题中匹配到的名称 |
| library_id | string | 术语库ID |
| library_name | string | 术语库名称 |
| related_fields | array | 关联字段列表 |
| related_datacards | array | 关联数据卡片列表 |

**融合策略说明：**
系统会根据自然语言问题自动推断融合策略：
- **OR（或）**: 满足任一条件即可，结果为多个数据源的并集
- **AND（且）**: 需同时满足多个条件，结果为多个数据源的交集
- **PRIORITY（优先）**: 优先使用主数据源，其他数据源作为补充
- **UNION（合并）**: 合并所有结果并去重
- **TRINO_UNIFIED（Trino统一查询）**: 当所有表都通过Trino连接时，使用Trino的跨catalog能力统一查询

**关系卡片增强说明：**
- 系统优先使用关系卡片中的JOIN条件生成SQL
- 关系卡片提供的JOIN建议包含置信度和关系类型
- 支持跨数据源关系识别（is_cross_source标识）
- 显著提升多表查询准确率（+20-25%）和JOIN条件准确率（+15-20%）
- 减少笛卡尔积等常见问题

**权限说明：**
- 基于API Key的`user_id`进行数据隔离
- 只能查询API Key所属用户有权限访问的数据源和数据卡片
- 向量检索召回的数据卡片会自动按用户ID过滤

**错误响应：**

**401 Unauthorized - 缺少API Key：**
```json
{
  "code": 401,
  "msg": "缺少 API Key",
  "data": null
}
```

**401 Unauthorized - API Key无效：**
```json
{
  "code": 401,
  "msg": "API Key 无效",
  "data": null
}
```

**403 Forbidden - API Key已禁用：**
```json
{
  "code": 403,
  "msg": "API Key 已禁用",
  "data": null
}
```

**403 Forbidden - API Key已过期：**
```json
{
  "code": 403,
  "msg": "API Key 已过期",
  "data": null
}
```

**400 Bad Request - 缺少query参数：**
```json
{
  "code": 400,
  "msg": "请提供 query",
  "data": null
}
```

**说明：**
1. 此接口与5.1功能类似，但使用API Key认证而非Session认证
2. 适用于外部系统集成、插件开发等场景
3. API Key会自动映射到所属用户，实现数据隔离
4. 每次成功调用后，系统会自动更新API Key的`last_used_at`字段
5. 向量检索和重排序的参数（如distance_threshold、max_results等）使用系统默认配置

---

## 7. 数据审计模块

### 7.1 数据质量审计

**接口描述：** 对指定表进行数据质量审计，统计各字段的空值、空字符串等情况

**请求类型：** `POST`

**接口路径：** `/console/api/data_audit`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| db_type | string | 是 | 数据库类型（mysql/postgresql/mssql/oracle/sqlite/trino/kingbase/oceanbase） |
| connect_info | object | 是 | 连接信息（包含host, port, user, password等） |
| database_name | string | 是 | 数据库名 |
| table_name | string | 是 | 表名（支持schema.table格式） |

**connect_info 对象结构：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| host | string | 是 | 主机地址 |
| port | integer | 是 | 端口号 |
| user | string | 是 | 用户名 |
| password | string | 是 | 密码 |
| schema | string | 否 | Schema名（PostgreSQL/Oracle，默认public） |

**请求示例：**
```json
{
  "db_type": "mysql",
  "connect_info": {
    "host": "192.168.1.100",
    "port": 3306,
    "user": "root",
    "password": "password123"
  },
  "database_name": "test_db",
  "table_name": "orders"
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "db_type": "mysql",
    "database": "test_db",
    "schema": null,
    "table": "orders",
    "report": [
      {
        "column_name": "customer_name",
        "data_type": "varchar(100)",
        "total_rows": 1000,
        "null_count": 50,
        "empty_str_count": 20,
        "missing_count": 70,
        "missing_pct": 7.0
      },
      {
        "column_name": "order_date",
        "data_type": "datetime",
        "total_rows": 1000,
        "null_count": 10,
        "empty_str_count": 0,
        "missing_count": 10,
        "missing_pct": 1.0
      }
    ]
  }
}
```

**返回字段说明：**
- `total_rows`: 表总行数
- `null_count`: NULL值数量
- `empty_str_count`: 空字符串数量（仅字符串类型字段）
- `missing_count`: 缺失值总数（null_count + empty_str_count）
- `missing_pct`: 缺失值百分比

---

## 8. 版本更新日志模块

### 8.1 获取版本更新日志列表

**接口描述：** 获取所有版本更新日志列表

**请求类型：** `GET`

**接口路径：** `/console/api/changelog`

**是否需要登录：** 是

**请求参数：** 无

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": [
    {
      "id": 1,
      "version": "1.0.0",
      "title": "初始版本发布",
      "content_md": "# 更新内容\n\n- 支持MySQL数据库连接\n- 支持数据卡片生成",
      "status": "public",
      "created_at": "2025-01-20T10:30:00",
      "updated_at": "2025-01-20T10:30:00"
    }
  ]
}
```

---

### 8.2 获取版本更新日志详情

**接口描述：** 获取指定版本的更新日志详情

**请求类型：** `GET`

**接口路径：** `/console/api/changelog/<cid>`

**是否需要登录：** 是

**路径参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| cid | integer | 是 | 日志ID |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": 1,
    "version": "1.0.0",
    "title": "初始版本发布",
    "content_md": "# 更新内容\n\n- 支持MySQL数据库连接\n- 支持数据卡片生成",
    "status": "public",
    "created_at": "2025-01-20T10:30:00",
    "updated_at": "2025-01-20T10:30:00"
  }
}
```

---

### 8.3 创建版本更新日志

**接口描述：** 创建新的版本更新日志

**请求类型：** `POST`

**接口路径：** `/console/api/changelog`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| version | string | 是 | 版本号（必须唯一） |
| title | string | 是 | 标题 |
| content_md | string | 是 | 内容（Markdown格式） |
| status | string | 否 | 状态（public/hidden，默认hidden） |

**请求示例：**
```json
{
  "version": "1.1.0",
  "title": "新增数据审计功能",
  "content_md": "# 更新内容\n\n- 新增数据质量审计功能\n- 优化查询性能",
  "status": "public"
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "created",
  "data": {
    "id": 2
  }
}
```

---

### 8.4 更新版本更新日志

**接口描述：** 更新指定版本的更新日志

**请求类型：** `PUT`

**接口路径：** `/console/api/changelog/<cid>`

**是否需要登录：** 是

**路径参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| cid | integer | 是 | 日志ID |

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| version | string | 否 | 版本号 |
| title | string | 否 | 标题 |
| content_md | string | 否 | 内容（Markdown格式） |
| status | string | 否 | 状态（public/hidden） |

**请求示例：**
```json
{
  "title": "更新后的标题",
  "status": "public"
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "updated",
  "data": {
    "id": 2
  }
}
```

---

### 8.5 删除版本更新日志

**接口描述：** 删除指定版本的更新日志

**请求类型：** `DELETE`

**接口路径：** `/console/api/changelog/<cid>`

**是否需要登录：** 是

**路径参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| cid | integer | 是 | 日志ID |

**返回示例：**
```json
{
  "code": 200,
  "msg": "deleted",
  "data": {
    "id": 2
  }
}
```

---

## 9. Excel字段提取模块

### 9.1 从Excel提取字段数据

**接口描述：** 从Excel文件中提取表字段描述数据，并填充到数据库表结构中

**请求类型：** `POST`

**接口路径：** `/console/api/extract_field_data_excel`

**是否需要登录：** 是

**请求参数：** FormData 格式

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| file | file | 是 | Excel文件（.xlsx或.xls，最大20MB） |
| sheet_name | string | 是 | Excel工作表名称 |
| field_data | string | 是 | 字段映射配置（JSON字符串） |

**field_data JSON结构：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| tb_name_column | string | 是 | 表名列（Excel列字母，如"A"） |
| tb_desc_column | string | 否 | 表描述列 |
| field_name_column | string | 是 | 字段名列 |
| field_desc_column | string | 是 | 字段描述列 |
| field_value_desc_column | string | 否 | 字段取值描述列 |
| has_title | boolean | 是 | 是否包含表头 |

**请求示例（FormData）：**
```
file: [Excel文件]
sheet_name: "字段描述"
field_data: {
  "tb_name_column": "A",
  "tb_desc_column": "B",
  "field_name_column": "C",
  "field_desc_column": "D",
  "field_value_desc_column": "E",
  "has_title": true
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "提取成功",
  "data": {
    "total_tables": 10,
    "filled_tables": 10,
    "total_fields": 150,
    "filled_fields": 145
  }
}
```

**说明：** 此接口会解析Excel文件，提取表名、字段名、字段描述等信息，并自动填充到对应的数据库表结构中。

---

## 10. 模型配置信息管理模块

**接口描述：** 管理系统中可用的大模型配置，包括查询、创建、更新和删除。

**基础路径：** `/console/api/model_config`

### 10.1 查询模型配置

- **请求类型：** `GET`
- **是否需要登录：** 否
- **查询参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| id | string | 否 | 模型配置ID（UUID），传入时返回单条记录 |

**请求示例：**
```
GET /console/api/model_config
GET /console/api/model_config?id=550e8400-e29b-41d4-a716-446655440000
```

**返回示例（列表）：**
```json
{
  "code": 200,
  "msg": "success",
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "model_name": "豆包大模型",
      "model_type": "豆包",
      "model_api_key": "sk-****",
      "model_class": "大语言",
      "url": "https://api.doubao.com/v1/chat/completions",
      "created_at": "2025-11-28T12:49:00+08:00",
      "updated_at": "2025-11-28T12:49:00+08:00"
    }
  ]
}
```

**返回示例（单条）：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "model_name": "豆包大模型",
    "model_type": "豆包",
    "model_api_key": "sk-****",
    "model_class": "大语言",
    "url": "https://api.doubao.com/v1/chat/completions",
    "created_at": "2025-11-28T12:49:00+08:00",
    "updated_at": "2025-11-28T12:49:00+08:00"
  }
}
```

### 10.2 新增模型配置

- **请求类型：** `POST`
- **是否需要登录：** 否
- **请求参数（JSON）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| model_name | string | 是 | 模型名称 |
| model_type | string | 是 | 模型类型（豆包/千问/DS等） |
| model_api_key | string | 是 | 模型 API Key |
| model_class | string | 是 | 模型作用类别（大语言/重排序/向量化嵌入等） |
| url | string | 是 | 模型接口地址 |

**请求示例：**
```json
{
  "model_name": "千问大模型",
  "model_type": "千问",
  "model_api_key": "sk-qianwen-key-12345",
  "model_class": "大语言",
  "url": "https://api.qianwen.com/v1/chat/completions"
}
```

**成功返回：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### 10.3 更新模型配置

- **请求类型：** `PUT`
- **是否需要登录：** 否
- **请求参数（JSON）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| id | string | 是 | 模型配置ID |
| model_name | string | 否 | 模型名称 |
| model_type | string | 否 | 模型类型 |
| model_api_key | string | 否 | 模型 API Key |
| model_class | string | 否 | 模型作用类别 |
| url | string | 否 | 模型接口地址 |

**请求示例：**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "model_name": "豆包大模型-v2",
  "model_api_key": "sk-new-key"
}
```

**成功返回：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### 10.4 删除模型配置

- **请求类型：** `DELETE`
- **是否需要登录：** 否
- **请求参数（JSON）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| id | string | 是 | 模型配置ID |

**请求示例：**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**成功返回：**
```json
{
  "code": 200,
  "msg": "deleted",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

---

## 11. 历史查询模块

### 11.1 查询历史列表

**接口描述：** 分页获取用户的查询历史记录，支持按数据源、状态、日期范围筛选

**请求类型：** `GET`

**接口路径：** `/console/api/query_history/list`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| user_id | string | 是 | 用户ID（UUID） |
| page | integer | 否 | 页码（默认1） |
| page_size | integer | 否 | 每页数量（默认20，最大100） |
| keyword | string | 否 | 搜索关键词（问题/SQL） |
| status | string | 否 | 状态筛选（success/error/timeout/all，默认all） |
| start_date | string | 否 | 开始日期（YYYY-MM-DD） |
| end_date | string | 否 | 结束日期（YYYY-MM-DD） |
| source_datasource_id | string | 否 | 按查询来源数据源ID筛选 |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "total": 100,
    "page": 1,
    "page_size": 20,
    "total_pages": 5,
    "items": [
      {
        "id": "uuid-string",
        "question": "查询最近一周的订单",
        "processed_question": "查询最近一周的GMV（成交总额）",
        "term_rewrite_info": {
          "matched_terms": [
            {
              "term_name": "GMV",
              "term_definition": "商品交易总额",
              "matched_alias": "订单"
            }
          ]
        },
        "sql": "SELECT * FROM orders WHERE ...",
        "cluster_sqls": [
          {
            "datasource_ids": ["uuid1"],
            "datasource_names": ["生产库A"],
            "table_names": ["orders"],
            "sql": "SELECT * FROM orders WHERE ..."
          }
        ],
        "source_datasource_ids": ["uuid1", "uuid2"],
        "source_datasource_names": ["生产库A", "生产库B"],
        "total_duration_ms": 2500,
        "total_tokens": 1500,
        "status": "success",
        "result_count": 50,
        "fusion_strategy": "OR",
        "has_full_result": true,
        "created_at": "2026-04-09T10:30:00"
      }
    ]
  }
}
```

**返回字段说明：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| question | string | 用户原始问题（术语展开前） |
| processed_question | string | 实际用于检索/生成SQL的问题（术语展开后） |
| term_rewrite_info | object | 术语展开详情，包含匹配的术语列表等信息 |
| cluster_sqls | array | 各数据源/簇的SQL数组，用于多数据源查询时记录各簇SQL |
| source_datasource_ids | array | 查询来源数据源ID列表（用户发起查询时选中的数据源） |
| source_datasource_names | array | 查询来源数据源名称列表 |

---

### 11.2 查询历史详情

**接口描述：** 获取单条查询历史的完整信息，包括性能指标、Token消耗、质量指标等

**请求类型：** `GET`

**接口路径：** `/console/api/query_history/<query_id>`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| user_id | string | 是 | 用户ID（UUID） |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "uuid-string",
    "user_id": "user-uuid",
    "api_key_id": "api-key-uuid",
    "question": "查询最近一周的订单",
    "processed_question": "查询最近一周的GMV（成交总额）",
    "term_rewrite_info": {
      "matched_terms": [
        {
          "term_name": "GMV",
          "term_definition": "商品交易总额",
          "matched_alias": "订单",
          "library_name": "电商术语库"
        }
      ],
      "rewrite_count": 1
    },
    "sql": "SELECT * FROM orders WHERE ...",
    "cluster_sqls": [
      {
        "datasource_ids": ["uuid1"],
        "datasource_names": ["生产库A"],
        "table_names": ["orders"],
        "sql": "SELECT * FROM orders WHERE ..."
      }
    ],
    "source_datasource_ids": ["uuid1"],
    "source_datasource_names": ["生产库A"],
    "datasource_ids": ["uuid1"],
    "datasource_names": ["生产库A"],
    "table_names": ["orders", "customers"],
    "performance": {
      "total_duration_ms": 2500,
      "vector_search_ms": 300,
      "rerank_ms": 200,
      "llm_gen_sql_ms": 800,
      "sql_execution_ms": 1200,
      "fusion_ms": 0
    },
    "tokens": {
      "embedding_tokens": 500,
      "rerank_tokens": 200,
      "llm_prompt_tokens": 600,
      "llm_completion_tokens": 200,
      "total_tokens": 1500
    },
    "result": {
      "result_count": 50
    },
    "quality": {
      "cards_recalled": 15,
      "cards_reranked": 10,
      "cards_selected": 5,
      "top1_rerank_score": 0.95,
      "avg_rerank_score": 0.88
    },
    "status": "success",
    "fusion_strategy": "OR",
    "full_response_result": {...},
    "created_at": "2026-04-09T10:30:00"
  }
}
```

**返回字段说明：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| question | string | 用户原始问题（术语展开前） |
| processed_question | string | 实际用于检索/生成SQL的问题（术语展开后） |
| term_rewrite_info | object | 术语展开详情，包含匹配的术语列表、改写次数等信息 |
| cluster_sqls | array | 各数据源/簇的SQL数组，记录多数据源查询时各簇的SQL详情 |
| source_datasource_ids | array | 查询来源数据源ID列表（用户发起查询时选中的数据源） |
| source_datasource_names | array | 查询来源数据源名称列表 |
| datasource_ids | array | 涉及的数据源ID列表（查询过程中实际涉及到的所有数据源） |
| datasource_names | array | 涉及的数据源名称列表 |

---

### 11.3 删除查询历史

**接口描述：** 删除单条查询历史记录（会级联更新聚合统计）

**请求类型：** `DELETE`

**接口路径：** `/console/api/query_history/<query_id>`

**是否需要登录：** 是

**路径参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| query_id | string | 是 | 查询历史ID（UUID） |

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| user_id | string | 是 | 用户ID（UUID） |

**返回示例：**
```json
{
  "code": 200,
  "msg": "删除成功",
  "data": {
    "deleted_id": "uuid-string"
  }
}
```

---

### 11.4 批量删除查询历史

**接口描述：** 批量删除查询历史记录，支持按ID列表、日期范围、保留天数删除

**请求类型：** `DELETE`

**接口路径：** `/console/api/query_history/batch`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| user_id | string | 是 | 用户ID（UUID） |
| query_ids | string | 否 | 要删除的ID列表，逗号分隔 |
| before_date | string | 否 | 删除此日期之前的所有记录（YYYY-MM-DD） |
| keep_days | integer | 否 | 保留最近多少天的记录 |

**说明：** `query_ids`、`before_date`、`keep_days` 三个条件至少要传一个。

**返回示例：**
```json
{
  "code": 200,
  "msg": "成功删除 50 条记录",
  "data": {
    "deleted_count": 50,
    "total_found": 50
  }
}
```

---

### 11.5 查询历史统计

**接口描述：** 获取用户的查询统计概览

**请求类型：** `GET`

**接口路径：** `/console/api/query_history/stats`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| user_id | string | 是 | 用户ID（UUID） |
| source_datasource_id | string | 否 | 按数据源筛选 |
| start_date | string | 否 | 开始日期 |
| end_date | string | 否 | 结束日期 |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "period": {
      "start_date": "2026-04-01",
      "end_date": "至今"
    },
    "total_queries": 500,
    "success_queries": 480,
    "error_queries": 15,
    "timeout_queries": 5,
    "success_rate": 96.0,
    "total_tokens": 75000,
    "avg_duration_ms": 2300,
    "min_duration_ms": 500,
    "max_duration_ms": 15000
  }
}
```

---

## 12. 监控中心模块

### 12.1 监控总览

**接口描述：** 获取监控概览数据，包含实时统计、趋势数据、对比分析等

**请求类型：** `GET`

**接口路径：** `/console/api/monitoring/overview`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| user_id | string | 是 | 用户ID（UUID） |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "recent_24h": {
      "total_queries": 150,
      "success_queries": 145,
      "error_queries": 3,
      "timeout_queries": 2,
      "success_rate": 96.67,
      "avg_duration_ms": 2300,
      "total_tokens": 22500,
      "embedding_tokens": 7500,
      "rerank_tokens": 3000,
      "llm_tokens": 12000
    },
    "today": {
      "total_queries": 45,
      "success_queries": 43,
      "total_tokens": 6750
    },
    "daily_trend": [...],
    "summary_30d": {
      "total_queries": 1500,
      "total_tokens": 225000,
      "total_cost_yuan": 1.25
    },
    "cost_note": "⚠️ 成本为预估值，仅供参考，实际费用以云厂商账单为准",
    "comparison": {
      "vs_yesterday": {...},
      "vs_last_week": {...}
    },
    "hourly_distribution": {...},
    "datasource_stats": {...},
    "status_breakdown": {...},
    "quality_metrics": {...}
  }
}
```

---

### 12.2 监控趋势

**接口描述：** 获取监控趋势数据，支持按天统计查询量、Token消耗、成本等

**请求类型：** `GET`

**接口路径：** `/console/api/monitoring/trend`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| user_id | string | 是 | 用户ID（UUID） |
| days | integer | 否 | 天数（默认30，最大365） |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "days": 30,
    "items": [
      {
        "date": "2026-04-09",
        "total_queries": 50,
        "success_queries": 48,
        "error_queries": 1,
        "timeout_queries": 1,
        "success_rate": 96.0,
        "tokens": {
          "embedding": 2500,
          "rerank": 1000,
          "llm": 4000,
          "total": 7500
        },
        "cost_yuan": 0.045,
        "performance": {...},
        "quality": {...}
      }
    ],
    "statistics": {...},
    "growth_analysis": {...},
    "peak_valley": {...},
    "weekly_pattern": {...}
  }
}
```

---

### 12.3 实时监控

**接口描述：** 获取实时监控数据（最近1小时）

**请求类型：** `GET`

**接口路径：** `/console/api/monitoring/realtime`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| user_id | string | 是 | 用户ID（UUID） |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "summary": {
      "total_queries": 25,
      "avg_duration_ms": 2100,
      "total_tokens": 3750
    },
    "minute_data": [...],
    "current_status": {...},
    "qps_stats": {...},
    "error_alerts": {...},
    "recent_queries": {...},
    "datasource_health": {...}
  }
}
```

---

### 12.4 性能分析

**接口描述：** 获取性能分析数据，包括各环节耗时分布、数据源性能等

**请求类型：** `GET`

**接口路径：** `/console/api/monitoring/performance`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| user_id | string | 是 | 用户ID（UUID） |
| days | integer | 否 | 天数（默认7，最大30） |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "period_days": 7,
    "stage_averages": {
      "vector_search_ms": 300,
      "rerank_ms": 200,
      "llm_gen_sql_ms": 800,
      "sql_execution_ms": 1000,
      "total_avg_ms": 2300
    },
    "slow_queries_top10": [...],
    "latency_distribution": {...},
    "stage_breakdown": {...},
    "datasource_performance": {...},
    "performance_trend": {...},
    "query_patterns": {...}
  }
}
```

---

## 13. 系统配置模块

### 13.1 获取Token价格配置

**接口描述：** 获取当前Token价格配置（Embedding、Rerank、LLM输入/输出）

**请求类型：** `GET`

**接口路径：** `/console/api/system_config/token_prices`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| user_id | string | 否 | 用户ID（为空查系统级配置） |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "scope": "system",
    "embedding": {
      "key": "token_price_embedding",
      "value": "0.0007",
      "description": "Embedding Token 单价（元/千token）"
    },
    "rerank": {
      "key": "token_price_rerank",
      "value": "0.002",
      "description": "Rerank Token 单价（元/千token）"
    },
    "llm_input": {
      "key": "token_price_llm_input",
      "value": "0.002",
      "description": "LLM 输入 Token 单价（元/千token）"
    },
    "llm_output": {
      "key": "token_price_llm_output",
      "value": "0.006",
      "description": "LLM 输出 Token 单价（元/千token）"
    }
  }
}
```

---

### 13.2 更新Token价格配置

**接口描述：** 批量更新Token价格配置

**请求类型：** `PUT`

**接口路径：** `/console/api/system_config/token_prices`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| embedding | float | 否 | Embedding 价格（元/千token） |
| rerank | float | 否 | Rerank 价格（元/千token） |
| llm_input | float | 否 | LLM 输入价格（元/千token） |
| llm_output | float | 否 | LLM 输出价格（元/千token） |
| user_id | string | 否 | 目标用户ID（为空表示系统级） |

**请求示例：**
```json
{
  "embedding": 0.0008,
  "rerank": 0.0025,
  "llm_input": 0.003,
  "llm_output": 0.008
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "message": "系统级价格配置更新成功",
    "scope": "system",
    "updated": [
      {"key": "token_price_embedding", "value": "0.0008"}
    ]
  }
}
```

---

### 13.3 获取数据保留配置

**接口描述：** 获取数据保留天数配置

**请求类型：** `GET`

**接口路径：** `/console/api/system_config/data_retention`

**是否需要登录：** 是

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "scope": "system",
    "query_logs_retention_days": {
      "value": "180",
      "description": "查询日志保留天数",
      "unit": "天"
    },
    "stats_retention_days": {
      "value": "365",
      "description": "聚合统计保留天数",
      "unit": "天"
    }
  }
}
```

---

### 13.4 更新数据保留配置

**接口描述：** 更新数据保留天数配置

**请求类型：** `PUT`

**接口路径：** `/console/api/system_config/data_retention`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| query_logs_retention_days | integer | 否 | 查询日志保留天数（1-3650） |
| stats_retention_days | integer | 否 | 聚合统计保留天数（1-3650） |
| user_id | string | 否 | 目标用户ID（为空表示系统级） |

---

### 13.5 手动触发数据清理

**接口描述：** 手动触发过期数据清理任务

**请求类型：** `POST`

**接口路径：** `/console/api/system_config/cleanup`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| type | string | 否 | 清理类型：logs/stats/all（默认all） |

**返回示例：**
```json
{
  "code": 200,
  "msg": "数据清理完成",
  "data": {
    "type": "all",
    "results": {
      "query_logs": {"deleted": 100},
      "query_stats_daily": {"deleted": 5}
    },
    "total_deleted": 105,
    "duration_ms": 500,
    "executed_at": "2026-04-09T10:30:00"
  }
}
```

---

### 13.6 获取系统配置列表

**接口描述：** 获取所有系统配置项

**请求类型：** `GET`

**接口路径：** `/console/api/system_config/config`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| key | string | 否 | 配置键名（不传则返回全部） |
| scope | string | 否 | 范围：system/user/all（默认all） |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "configs": [
      {
        "id": "uuid",
        "config_key": "token_price_embedding",
        "config_value": "0.0007",
        "description": "Embedding Token 单价（元/千token）",
        "user_id": null,
        "scope": "system"
      }
    ]
  }
}
```

---

### 13.7 更新系统配置

**接口描述：** 更新或创建系统配置

**请求类型：** `PUT`

**接口路径：** `/console/api/system_config/config`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| key | string | 是 | 配置键名 |
| value | string | 是 | 配置值 |
| description | string | 否 | 配置描述 |
| user_id | string | 否 | 目标用户ID（为空表示系统级） |

---

### 13.8 删除系统配置

**接口描述：** 删除系统配置（关键配置不可删除）

**请求类型：** `DELETE`

**接口路径：** `/console/api/system_config/config`

**是否需要登录：** 是

---

## 14. SSO单点登录模块

### 14.1 SSO登录接口

**接口描述：** 通过JWT Token实现SSO单点登录，无需用户名密码即可完成认证

**请求类型：** `GET`

**接口路径：** `/sso/login`

**是否需要登录：** 否

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| token | string | 是 | JWT Token（URL编码后传递） |
| redirect_url | string | 是 | 登录成功后的回调地址（URL编码后传递） |

**URL编码说明：**
- `token` 参数需要使用 `encodeURIComponent()` 进行URL编码
- `redirect_url` 参数需要使用 `encodeURIComponent()` 进行URL编码

**完整URL格式：**
```
/sso/login?token={encodeURIComponent(JWT Token)}&redirect_url={encodeURIComponent(回调地址)}
```

**JWT Token结构：**

| 部分 | 名称 | 说明 |
|------|------|------|
| 第一部分 | Header | 声明算法和类型，格式为 `{"alg":"HS256","typ":"JWT"}` |
| 第二部分 | Payload | 存放实际的用户数据 |
| 第三部分 | Signature | 用共享密钥对前两部分签名 |

**Payload必填字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| username | string | 用户的唯一标识，不能为空 |
| user_id | string | 用户在企业系统中的ID，不能为空 |
| exp | number | Token过期时间（Unix时间戳），建议设置为5分钟后 |

**Payload可选字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| nickname | string | 用户昵称 |
| email | string | 用户邮箱 |
| source | string | 来源标识，用于区分不同系统，默认default |
| iat | number | Token签发时间（Unix时间戳） |

**JWT Token生成示例（Python）：**
```python
import jwt
from datetime import datetime, timedelta, timezone

SECRET_KEY = "your_shared_secret_key"

payload = {
    "username": "zhang_san",
    "user_id": "SYS_USER_001",
    "nickname": "张三",
    "email": "zhangsan@example.com",
    "source": "your_app",
    "iat": datetime.now(timezone.utc),
    "exp": datetime.now(timezone.utc) + timedelta(minutes=5)
}

token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
print(token)
```

**JWT Token生成示例（Node.js）：**
```javascript
const jwt = require('jsonwebtoken');

const secretKey = 'your_shared_secret_key';

const payload = {
    username: 'zhang_san',
    user_id: 'SYS_USER_001',
    nickname: '张三',
    email: 'zhangsan@example.com',
    source: 'your_app'
};

const token = jwt.sign(payload, secretKey, {
    algorithm: 'HS256',
    expiresIn: '5m'
});

console.log(token);
```

**跳转示例：**
```javascript
// 生成Token
const token = jwt.sign(payload, secretKey, { algorithm: 'HS256', expiresIn: '5m' });

// 构造SSO登录URL
const ssoUrl = `${API_BASE}/sso/login?token=${encodeURIComponent(token)}&redirect_url=${encodeURIComponent(FRONTEND_URL)}`;

// 跳转
window.location.href = ssoUrl;
```

**登录成功响应：**

登录成功后，浏览器会跳转到指定的 `redirect_url`，并在URL中携带 `access_token` 参数：

```
{redirect_url}?access_token={OntiCards平台Token}
```

**示例：**
```
https://frontend.onticards.com/overview?access_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**前端接收Token示例：**
```javascript
// 从URL获取 access_token 参数
function getAccessToken() {
    const params = new URLSearchParams(window.location.search);
    return params.get('access_token');
}

// 存储Token
const token = getAccessToken();
if (token) {
    localStorage.setItem('access_token', token);

    // 清理URL中的token参数（防止token泄露）
    window.history.replaceState({}, document.title, window.location.pathname);
}
```

**错误响应：**

| HTTP状态码 | error字段 | 原因 |
|------------|-----------|------|
| 400 | `缺少token参数` | URL中没有传token |
| 400 | `缺少redirect_url参数` | URL中没有传redirect_url |
| 400 | `token中缺少必要的用户信息` | Payload中username或user_id为空 |
| 401 | `token已过期` | Token的exp已过期 |
| 401 | `token无效` | 签名验证失败（密钥不匹配或内容被篡改） |

**错误响应示例：**
```json
{
  "code": 401,
  "msg": "token无效",
  "error": "token无效"
}
```

**错误页面示例：**
当SSO登录失败时，会返回错误信息页面：
```html
<!DOCTYPE html>
<html>
<head>
    <title>SSO Login Error</title>
</head>
<body>
    <h1>SSO Login Failed</h1>
    <p>Error: token无效</p>
</body>
</html>
```

---

### 14.2 SSO登录流程说明

**整体流程：**

```
1. 企业系统验证用户身份
   ↓
2. 企业后端生成JWT Token（包含用户信息）
   ↓
3. 拼接SSO登录URL
   {OntiCards API地址}/sso/login?token={JWT Token}&redirect_url={回调地址}
   ↓
4. 用户浏览器跳转到OntiCards SSO接口
   ↓
5. OntiCards验证JWT签名和有效期
   ↓
6. 创建/关联用户，生成平台Token
   ↓
7. 跳转到回调地址，携带access_token
   ↓
8. 前端接收Token，登录完成
```

**用户创建/关联逻辑：**

1. **接收JWT Token** → 获取URL中的token参数
2. **解析Header** → 获取算法信息（HS256）
3. **验证签名** → 用共享密钥验证token是否被篡改
4. **检查过期** → 验证exp是否有效
5. **提取Payload** → 获取username、user_id等用户信息
6. **查询用户** → 根据 `idp_user_id` + `idp_source` 查找已存在用户
7. **创建/关联** → 新用户自动创建，老用户关联登录
8. **生成Token** → 生成OntiCards自己的登录Token
9. **跳转回调** → 携带新Token跳转到 redirect_url

---

### 14.3 SSO测试页面

**SSO测试中心：**
```
http://localhost:9000/static/sso_test.html
```

**回调测试页面：**
```
http://localhost:9000/static/sso_callback.html
```

**测试页面功能：**
- 生成测试用JWT Token
- 填写回调地址
- 一键发起SSO登录
- 查看登录结果

---

### 14.4 SSO配置说明

**服务端配置（环境变量）：**

| 配置项 | 说明 |
|--------|------|
| SSO_SECRET_KEY | SSO共享密钥，用于JWT签名验证 |

**配置示例：**
```env
SSO_SECRET_KEY=K7x#9mP$2nL@qR8
```

**密钥要求：**
- 建议使用64位以上的随机字符串
- 客户端和服务端必须使用相同的密钥
- 生产环境请使用强密钥，不要使用示例密钥

---

### 14.5 SSO安全性说明

| 安全措施 | 说明 |
|----------|------|
| Token有效期限制 | 建议设置为5分钟内，防止Token泄露风险 |
| HMAC-SHA256签名 | 使用共享密钥对Token签名，防止篡改 |
| 用户级数据隔离 | SSO用户与其他用户数据完全隔离 |
| 完整的审计日志 | 记录所有SSO登录行为 |
| URL参数清理 | 前端需清理URL中的token参数 |

---

### 14.6 SSO与API Key的区别

| 对比项 | SSO单点登录 | API Key |
|--------|-------------|---------|
| 用途 | 用户身份认证 | API接口调用认证 |
| 认证对象 | 自然人用户 | 第三方系统/应用 |
| 认证方式 | JWT Token | API Key字符串 |
| 使用场景 | 企业统一登录 | 第三方系统集成 |
| 数据范围 | 用户个人数据 | 与API Key绑定的用户数据 |
| Token有效期 | 短期（建议5分钟） | 可配置（长期或短期） |

---

## 15. 提示词配置模块

**模块说明：** 提供系统提示词模板的管理功能，支持从文件同步到数据库、在线编辑、热更新等操作。

**基础路径：** `/console/api/prompt_config`

**提示词文件存储位置：** `libs/prompt/query_agg_prompt/`

**支持的提示词文件列表：**

| 文件名 | 说明 | 分类 |
|--------|------|------|
| mysql_multi_table.txt | MySQL 多表查询SQL生成提示词 | 多表查询 |
| postgresql_multi_table.txt | PostgreSQL 多表查询SQL生成提示词 | 多表查询 |
| mssql_multi_table.txt | SQL Server 多表查询SQL生成提示词 | 多表查询 |
| oracle_multi_table.txt | Oracle 多表查询SQL生成提示词 | 多表查询 |
| sqlite_multi_table.txt | SQLite 多表查询SQL生成提示词 | 多表查询 |
| trino_multi_table.txt | Trino 多表查询SQL生成提示词 | 多表查询 |
| kingbase_multi_table.txt | 电科金仓（KingBase）多表查询SQL生成提示词 | 多表查询 |
| oceanbase_multi_table.txt | OceanBase（MySQL 租户模式）多表查询SQL生成提示词（与 MySQL 协议兼容） | 多表查询 |
| dm_multi_table.txt | 达梦（DMBase）多表查询SQL生成提示词（兼容 Oracle 语法） | 多表查询 |
| strategy_detect.txt | 查询策略检测提示词 | 查询策略 |
| result_fusion.txt | 结果融合提示词 | 结果融合 |
| sql_with_relationship.txt | 关联查询SQL生成提示词 | 关联查询 |
| retry_whitelist_error.txt | SQL白名单错误重试提示词 | 重试提示 |
| retry_execution_error.txt | SQL执行错误重试提示词 | 重试提示 |
| table_relationship_analysis_prompt.txt | 表关系分析提示词（基础版） | 表关系分析 |
| table_relationship_analysis_enhanced_prompt.txt | 表关系分析提示词（增强版） | 表关系分析 |
| fill_field_by_llm.txt | LLM字段描述填充提示词 | 字段填充 |
| data_audit_*.txt | 数据盘查DDL SQL模板（按数据库类型） | 数据盘查 |

**提示词加载优先级：** 数据库（优先） > 缓存 > 文件（fallback）

---

### 15.1 获取提示词列表

**接口描述：** 分页获取提示词列表，支持搜索、分类筛选、数据库类型筛选

**请求类型：** `GET`

**接口路径：** `/console/api/prompt_config/list`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| page | integer | 否 | 页码（默认1） |
| page_size | integer | 否 | 每页数量（默认20，最大100） |
| search | string | 否 | 搜索关键词（搜索文件名和描述） |
| category | string | 否 | 分类筛选（如：多表查询、查询策略、结果融合等） |
| db_type | string | 否 | 数据库类型筛选（如：MySQL、PostgreSQL等） |
| include_prompt | boolean | 否 | 是否包含提示词内容（默认false，仅列表展示时可设为true提升性能） |

**请求示例：**
```
GET /console/api/prompt_config/list?page=1&page_size=20&category=多表查询
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "items": [
      {
        "id": "uuid-string",
        "file_name": "mysql_multi_table.txt",
        "description": "MySQL 多表查询SQL生成 提示词",
        "category": "多表查询",
        "db_type": "MySQL",
        "prompt_length": 15360
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 17,
      "total_pages": 1
    }
  }
}
```

---

### 15.2 获取单个提示词详情

**接口描述：** 通过UUID获取单个提示词的完整内容

**请求类型：** `GET`

**接口路径：** `/console/api/prompt_config/<id>`

**是否需要登录：** 是

**路径参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| id | string | 是 | 提示词UUID |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "uuid-string",
    "file_name": "mysql_multi_table.txt",
    "prompt": "你是一名专业的 MySQL SQL 查询生成器...",
    "description": "MySQL 多表查询SQL生成 提示词",
    "category": "多表查询",
    "db_type": "MySQL",
    "prompt_length": 15360
  }
}
```

---

### 15.3 通过文件名获取提示词

**接口描述：** 通过文件名获取提示词内容

**请求类型：** `GET`

**接口路径：** `/console/api/prompt_config/file/<file_name>`

**是否需要登录：** 是

**路径参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| file_name | string | 是 | 文件名（如：mysql_multi_table.txt） |

**请求示例：**
```
GET /console/api/prompt_config/file/mysql_multi_table.txt
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "uuid-string",
    "file_name": "mysql_multi_table.txt",
    "prompt": "你是一名专业的 MySQL SQL 查询生成器...",
    "description": "MySQL 多表查询SQL生成 提示词",
    "category": "多表查询",
    "db_type": "MySQL",
    "from_cache": true
  }
}
```

---

### 15.4 创建提示词

**接口描述：** 创建新的提示词配置

**请求类型：** `POST`

**接口路径：** `/console/api/prompt_config/list`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| file_name | string | 是 | 文件名（必须以.txt结尾，不能包含特殊字符） |
| prompt | string | 是 | 提示词内容 |
| description | string | 否 | 描述信息 |

**请求示例：**
```json
{
  "file_name": "custom_prompt.txt",
  "prompt": "自定义提示词内容...",
  "description": "自定义提示词"
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "创建成功",
  "data": {
    "id": "uuid-string",
    "file_name": "custom_prompt.txt",
    "description": "自定义提示词",
    "message": "创建成功"
  }
}
```

**错误响应（文件名已存在）：**
```json
{
  "code": 409,
  "msg": "文件名 'xxx.txt' 已存在，如需更新请使用 PUT 接口"
}
```

---

### 15.5 更新提示词

**接口描述：** 更新提示词内容或描述

**请求类型：** `PUT`

**接口路径：** `/console/api/prompt_config/<id>`

**是否需要登录：** 是

**路径参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| id | string | 是 | 提示词UUID |

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| prompt | string | 否 | 提示词内容 |
| description | string | 否 | 描述信息 |

**请求示例：**
```json
{
  "prompt": "更新后的提示词内容...",
  "description": "更新后的描述"
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "更新成功",
  "data": {
    "id": "uuid-string",
    "file_name": "mysql_multi_table.txt",
    "updated_fields": ["prompt", "description"],
    "message": "更新成功"
  }
}
```

**说明：** 更新后会自动清除该提示词的缓存，下次请求时会从数据库读取最新内容（热更新）。

---

### 15.6 删除提示词

**接口描述：** 删除指定的提示词配置

**请求类型：** `DELETE`

**接口路径：** `/console/api/prompt_config/<id>`

**是否需要登录：** 是

**路径参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| id | string | 是 | 提示词UUID |

**返回示例：**
```json
{
  "code": 200,
  "msg": "删除成功",
  "data": {
    "file_name": "custom_prompt.txt",
    "message": "删除成功"
  }
}
```

---

### 15.7 同步提示词（文件到数据库）

**接口描述：** 将提示词文件内容同步到数据库，支持单个文件或全部文件

**请求类型：** `POST`

**接口路径：** `/console/api/prompt_config/sync`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| file_name | string | 否 | 文件名（不传则同步全部） |
| file_path | string | 否 | 文件路径（用于指定非默认路径的文件） |

**请求示例（同步单个文件）：**
```json
{
  "file_name": "mysql_multi_table.txt"
}
```

**请求示例（同步全部）：**
```json
{}
```

**返回示例（同步单个）：**
```json
{
  "code": 200,
  "msg": "同步成功",
  "data": {
    "file_name": "mysql_multi_table.txt",
    "message": "同步成功",
    "prompt_length": 15360
  }
}
```

**返回示例（同步全部）：**
```json
{
  "code": 200,
  "msg": "同步完成",
  "data": {
    "success": ["mysql_multi_table.txt", "postgresql_multi_table.txt", ...],
    "failed": [],
    "total": 17,
    "message": "同步完成，成功 17 个，失败 0 个"
  }
}
```

---

### 15.8 获取提示词分类列表

**接口描述：** 获取所有提示词分类及统计信息

**请求类型：** `GET`

**接口路径：** `/console/api/prompt_config/categories`

**是否需要登录：** 是

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "categories": [
      {
        "name": "多表查询",
        "count": 6,
        "db_types": ["MySQL", "PostgreSQL", "SQL Server", "Oracle", "SQLite", "Trino", "电科金仓（KingBase）", "OceanBase（MySQL 租户模式）", "达梦（DMBase）"]
      },
      {
        "name": "查询策略",
        "count": 1,
        "db_types": ["通用"]
      },
      {
        "name": "结果融合",
        "count": 1,
        "db_types": ["通用"]
      },
      {
        "name": "重试提示",
        "count": 2,
        "db_types": ["通用"]
      }
    ],
    "db_types": ["MySQL", "PostgreSQL", "SQL Server", "Oracle", "SQLite", "Trino", "电科金仓（KingBase）", "OceanBase（MySQL 租户模式）", "达梦（DMBase）", "通用"]
  }
}
```

---

### 15.9 脚本同步工具

**说明：** 除了API接口，还提供了命令行脚本用于同步提示词文件到数据库。

**脚本位置：** `scripts/sync_prompts_to_db.py`

**使用方法：**

```bash
# 1. 进入项目目录
cd OntiCards_Api

# 2. 运行同步脚本（需要Flask应用上下文）
python scripts/sync_prompts_to_db.py
```

**交互式操作菜单：**
```
============================================================
提示词同步工具
============================================================
[1] 同步所有提示词到数据库
[2] 列出数据库中的提示词
[3] 清空所有提示词（谨慎）
[4] 退出
```

**编程式调用：**

```python
from app import app
from controllers.prompt_config.sync_prompts_to_db import sync_all_prompts

with app.app_context():
    result = sync_all_prompts()
    print(result)
    # {'success': [...], 'failed': [...], 'total': 17}
```

---

## 16. 业务术语库管理模块

业务术语库模块提供了完整的术语管理功能，支持创建术语库、管理业务术语、从模板导入术语以及将术语库关联到数据源。该模块主要用于NL2SQL场景中的术语扩展和改写，帮助系统更准确地理解用户的自然语言查询。

**核心功能：**
- 术语库管理：创建、查询、更新、删除术语库
- 业务术语管理：在术语库中添加、编辑、删除业务术语
- 术语模板：从预置模板快速导入行业术语
- 数据源关联：将术语库关联到数据源，实现术语自动识别和改写

**应用场景：**
- 用户输入"查询GMV"，系统自动识别"GMV"为业务术语，展开为"成交总额"
- 支持多个别名映射到同一标准术语，如"订单金额"、"交易额"都映射到"GMV"
- 不同数据源可以关联不同的术语库，实现术语的精准识别

### 16.1 术语库管理

#### 16.1.1 获取术语库列表

**接口描述**：获取当前用户的所有术语库列表，支持分页、搜索、分类筛选和状态筛选。

**请求类型**：`GET`

**接口路径**：`/console/api/business_term/libraries`

**是否需要登录**：是

**请求参数（Query）**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| page | integer | 否 | 页码，默认1 |
| page_size | integer | 否 | 每页数量，默认20，最大100 |
| search | string | 否 | 搜索关键词（匹配库名称或描述） |
| category | string | 否 | 分类筛选（如：电商、金融、医疗等） |
| status | string | 否 | 状态筛选（active/inactive） |

**返回示例**：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "items": [
      {
        "id": "uuid",
        "name": "电商术语库",
        "description": "电商领域常用术语",
        "category": "电商",
        "status": "active",
        "term_count": 25,
        "created_at": "2026-05-14T10:00:00",
        "updated_at": "2026-05-14T10:00:00"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 5,
      "total_pages": 1
    }
  }
}
```

**返回字段说明**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | string | 术语库ID（UUID） |
| name | string | 术语库名称 |
| description | string | 术语库描述 |
| category | string | 分类（电商、金融、医疗等） |
| status | string | 状态（active=启用，inactive=禁用） |
| term_count | integer | 术语数量 |
| created_at | string | 创建时间（ISO 8601格式） |
| updated_at | string | 更新时间（ISO 8601格式） |

---

#### 16.1.2 创建术语库

**接口描述**：创建新的术语库。

**请求类型**：`POST`

**接口路径**：`/console/api/business_term/libraries`

**是否需要登录**：是

**请求参数（Body）**：

```json
{
  "name": "电商术语库",
  "description": "电商领域常用术语",
  "category": "电商"
}
```

**请求字段说明**：

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| name | string | 是 | 术语库名称（最大100字符） |
| description | string | 否 | 术语库描述 |
| category | string | 否 | 分类标签 |

**返回示例**：

```json
{
  "code": 200,
  "msg": "创建成功",
  "data": {
    "id": "uuid",
    "name": "电商术语库",
    "message": "创建成功"
  }
}
```

**错误响应**：

```json
{
  "code": 409,
  "msg": "术语库 '电商术语库' 已存在",
  "data": null
}
```

---

#### 16.1.3 获取术语库详情

**接口描述**：获取指定术语库的详细信息，包含该库下的所有术语（支持分页）。

**请求类型**：`GET`

**接口路径**：`/console/api/business_term/libraries/<library_id>`

**是否需要登录**：是

**路径参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| library_id | string | 是 | 术语库ID（UUID） |

**请求参数（Query）**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| terms_page | integer | 否 | 术语列表页码，默认1 |
| terms_page_size | integer | 否 | 术语列表每页数量，默认100 |
| terms_search | string | 否 | 术语搜索关键词 |
| terms_status | string | 否 | 术语状态筛选 |

**返回示例**：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "uuid",
    "name": "电商术语库",
    "description": "电商领域常用术语",
    "category": "电商",
    "status": "active",
    "term_count": 2,
    "created_at": "2026-05-14T10:00:00",
    "updated_at": "2026-05-14T10:00:00",
    "terms": [
      {
        "id": "uuid",
        "term_name": "GMV",
        "term_alias": ["成交总额", "交易总额"],
        "term_definition": "商品交易总额",
        "status": "active",
        "created_at": "2026-05-14T10:00:00"
      }
    ],
    "terms_pagination": {
      "page": 1,
      "page_size": 100,
      "total": 2,
      "total_pages": 1
    }
  }
}
```

**返回字段说明**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| terms | array | 术语列表 |
| terms[].id | string | 术语ID |
| terms[].term_name | string | 术语名称 |
| terms[].term_alias | array | 术语别名列表 |
| terms[].term_definition | string | 术语定义 |
| terms[].status | string | 术语状态 |
| terms_pagination | object | 术语列表分页信息 |

---

#### 16.1.4 更新术语库

**接口描述**：更新指定术语库的信息。

**请求类型**：`PUT`

**接口路径**：`/console/api/business_term/libraries/<library_id>`

**是否需要登录**：是

**路径参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| library_id | string | 是 | 术语库ID（UUID） |

**请求参数（Body）**：

```json
{
  "name": "电商术语库（更新）",
  "description": "电商领域常用术语（已更新）",
  "status": "active"
}
```

**请求字段说明**：

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| name | string | 否 | 术语库名称 |
| description | string | 否 | 术语库描述 |
| category | string | 否 | 分类标签 |
| status | string | 否 | 状态（active/inactive） |

**返回示例**：

```json
{
  "code": 200,
  "msg": "更新成功",
  "data": {
    "id": "uuid",
    "updated_fields": ["name", "description"],
    "message": "更新成功"
  }
}
```

---

#### 16.1.5 删除术语库

**接口描述**：删除指定的术语库及其包含的所有术语（级联删除）。

**请求类型**：`DELETE`

**接口路径**：`/console/api/business_term/libraries/<library_id>`

**是否需要登录**：是

**路径参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| library_id | string | 是 | 术语库ID（UUID） |

**返回示例**：

```json
{
  "code": 200,
  "msg": "删除成功",
  "data": {
    "id": "uuid",
    "message": "删除成功，关联术语一并删除"
  }
}
```

**说明**：删除术语库时，会同时删除该库下的所有术语，以及数据源与该术语库的关联关系。

### 16.2 业务术语管理

#### 16.2.1 获取术语列表

**接口描述**：获取术语列表，支持按术语库筛选、分页、搜索和状态筛选。

**请求类型**：`GET`

**接口路径**：`/console/api/business_term/list`

**是否需要登录**：是

**请求参数（Query）**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| library_id | string | 是 | 术语库ID（必填，筛选指定库的术语） |
| page | integer | 否 | 页码，默认1 |
| page_size | integer | 否 | 每页数量，默认20，最大100 |
| search | string | 否 | 搜索关键词（匹配术语名称、别名或定义） |
| status | string | 否 | 状态筛选（active/inactive） |

**返回示例**：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "items": [
      {
        "id": "uuid",
        "library_id": "uuid",
        "term_name": "GMV",
        "term_alias": ["成交总额", "交易总额"],
        "term_definition": "商品交易总额",
        "applicable_conditions": "适用于电商场景",
        "status": "active",
        "created_at": "2026-05-14T10:00:00",
        "updated_at": "2026-05-14T10:00:00"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 50,
      "total_pages": 3
    }
  }
}
```

**返回字段说明**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | string | 术语ID（UUID） |
| library_id | string | 所属术语库ID |
| term_name | string | 术语名称 |
| term_alias | array | 术语别名列表（JSON数组） |
| term_definition | string | 术语定义 |
| applicable_conditions | string | 适用条件 |
| status | string | 状态（active/inactive） |

---

#### 16.2.2 创建术语

**接口描述**：在指定术语库中创建新术语。

**请求类型**：`POST`

**接口路径**：`/console/api/business_term/list`

**是否需要登录**：是

**请求参数（Body）**：

```json
{
  "library_id": "uuid",
  "term_name": "GMV",
  "term_alias": ["成交总额", "交易总额"],
  "term_definition": "商品交易总额",
  "applicable_conditions": "适用于电商场景",
  "remarks": "核心指标"
}
```

**请求字段说明**：

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| library_id | string | 是 | 术语库ID（UUID） |
| term_name | string | 是 | 术语名称（最大255字符） |
| term_alias | array | 否 | 术语别名列表 |
| term_definition | string | 是 | 术语定义 |
| applicable_conditions | string | 否 | 适用条件 |
| remarks | string | 否 | 备注信息 |
| related_datacards | array | 否 | 关联数据卡片 |
| related_fields | array | 否 | 关联字段 |
| related_terms | array | 否 | 关联术语 |

**返回示例**：

```json
{
  "code": 200,
  "msg": "创建成功",
  "data": {
    "id": "uuid",
    "term_name": "GMV",
    "message": "创建成功"
  }
}
```

**错误响应**：

```json
{
  "code": 409,
  "msg": "术语 'GMV' 已存在",
  "data": null
}
```

---

#### 16.2.3 获取术语详情

**接口描述**：获取指定术语的详细信息。

**请求类型**：`GET`

**接口路径**：`/console/api/business_term/<term_id>`

**是否需要登录**：是

**路径参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| term_id | string | 是 | 术语ID（UUID） |

**返回示例**：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "uuid",
    "library_id": "uuid",
    "term_name": "GMV",
    "term_alias": ["成交总额", "交易总额"],
    "term_definition": "商品交易总额",
    "applicable_conditions": "适用于电商场景",
    "remarks": "核心指标",
    "related_datacards": [],
    "related_fields": [],
    "related_terms": [],
    "status": "active",
    "created_at": "2026-05-14T10:00:00",
    "updated_at": "2026-05-14T10:00:00"
  }
}
```

---

#### 16.2.4 更新术语

**接口描述**：更新指定术语的信息。

**请求类型**：`PUT`

**接口路径**：`/console/api/business_term/<term_id>`

**是否需要登录**：是

**路径参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| term_id | string | 是 | 术语ID（UUID） |

**请求参数（Body）**：

```json
{
  "term_name": "GMV（更新）",
  "term_alias": ["成交总额", "交易总额", "总GMV"],
  "term_definition": "商品交易总额（已更新）",
  "status": "active"
}
```

**请求字段说明**：

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| term_name | string | 否 | 术语名称 |
| term_alias | array | 否 | 术语别名列表 |
| term_definition | string | 否 | 术语定义 |
| applicable_conditions | string | 否 | 适用条件 |
| remarks | string | 否 | 备注信息 |
| status | string | 否 | 状态（active/inactive） |

**返回示例**：

```json
{
  "code": 200,
  "msg": "更新成功",
  "data": {
    "id": "uuid",
    "updated_fields": ["term_name", "term_alias"],
    "message": "更新成功"
  }
}
```

---

#### 16.2.5 删除术语

**接口描述**：删除指定的术语。

**请求类型**：`DELETE`

**接口路径**：`/console/api/business_term/<term_id>`

**是否需要登录**：是

**路径参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| term_id | string | 是 | 术语ID（UUID） |

**返回示例**：

```json
{
  "code": 200,
  "msg": "删除成功",
  "data": {
    "id": "uuid",
    "message": "删除成功"
  }
}
```

### 16.3 术语模板管理

#### 16.3.1 获取模板分类列表

**接口描述**：获取所有术语模板的分类统计信息，包括每个分类下的模板名称和术语数量。

**请求类型**：`GET`

**接口路径**：`/console/api/business_term/templates/categories`

**是否需要登录**：是

**返回示例**：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "categories": [
      {
        "category": "电商",
        "templates": [
          {
            "template_name": "电商核心指标",
            "count": 15
          },
          {
            "template_name": "电商用户行为",
            "count": 10
          }
        ]
      },
      {
        "category": "金融",
        "templates": [
          {
            "template_name": "金融风控指标",
            "count": 20
          }
        ]
      }
    ]
  }
}
```

**返回字段说明**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| category | string | 分类名称 |
| templates | array | 该分类下的模板列表 |
| templates[].template_name | string | 模板名称 |
| templates[].count | integer | 该模板包含的术语数量 |

---

#### 16.3.2 获取模板列表

**接口描述**：获取术语模板列表，支持按分类和模板名称筛选。

**请求类型**：`GET`

**接口路径**：`/console/api/business_term/templates`

**是否需要登录**：是

**请求参数（Query）**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| category | string | 否 | 分类筛选（如：电商、金融） |
| template_name | string | 否 | 模板名称筛选 |

**返回示例**：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "items": [
      {
        "id": "uuid",
        "category": "电商",
        "template_name": "电商核心指标",
        "term_name": "GMV",
        "term_alias": ["成交总额", "交易总额"],
        "term_definition": "商品交易总额",
        "applicable_conditions": "适用于电商场景"
      }
    ],
    "total": 15
  }
}
```

**返回字段说明**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | string | 模板术语ID |
| category | string | 分类 |
| template_name | string | 模板名称 |
| term_name | string | 术语名称 |
| term_alias | array | 术语别名列表 |
| term_definition | string | 术语定义 |
| applicable_conditions | string | 适用条件 |

---

#### 16.3.3 从模板导入术语

**接口描述**：从预置模板批量导入术语到指定术语库。支持按模板ID、分类或模板名称导入。

**请求类型**：`POST`

**接口路径**：`/console/api/business_term/templates/import`

**是否需要登录**：是

**请求参数（Body）**：

```json
{
  "library_id": "uuid",
  "template_ids": ["uuid1", "uuid2"],
  "category": "电商",
  "template_name": "电商核心指标"
}
```

**请求字段说明**：

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| library_id | string | 是 | 目标术语库ID |
| template_ids | array | 否 | 模板术语ID列表（精确导入指定术语） |
| category | string | 否 | 按分类导入（导入该分类下所有术语） |
| template_name | string | 否 | 按模板名称导入（导入该模板下所有术语） |

**说明**：`template_ids`、`category`、`template_name` 三个参数至少需要指定一个。

**返回示例**：

```json
{
  "code": 200,
  "msg": "导入完成",
  "data": {
    "imported_count": 12,
    "skipped_count": 3,
    "message": "导入成功 12 个，跳过 3 个（已存在）",
    "skipped_items": ["GMV", "DAU", "MAU"]
  }
}
```

**返回字段说明**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| imported_count | integer | 成功导入的术语数量 |
| skipped_count | integer | 跳过的术语数量（已存在） |
| skipped_items | array | 跳过的术语名称列表 |

---

### 16.4 数据源-术语库关联管理

#### 16.4.1 获取数据源已添加的术语库列表

**接口描述**：获取指定数据源已添加的术语库列表，支持分页和状态筛选。

**请求类型**：`GET`

**接口路径**：`/console/api/business_term/datasource/<datasource_id>/libraries`

**是否需要登录**：是

**路径参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| datasource_id | string | 是 | 数据源ID（UUID） |

**请求参数（Query）**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| page | integer | 否 | 页码，默认1 |
| page_size | integer | 否 | 每页数量，默认20，最大100 |
| is_enabled | string | 否 | 启用状态筛选（true/false） |

**返回示例**：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "items": [
      {
        "id": "uuid",
        "datasource_id": "uuid",
        "library_id": "uuid",
        "library_name": "电商术语库",
        "library_category": "电商",
        "term_count": 25,
        "is_enabled": true,
        "added_at": "2026-05-14T10:00:00"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 3,
      "total_pages": 1
    }
  }
}
```

**返回字段说明**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | string | 关联记录ID |
| datasource_id | string | 数据源ID |
| library_id | string | 术语库ID |
| library_name | string | 术语库名称 |
| library_category | string | 术语库分类 |
| term_count | integer | 术语数量 |
| is_enabled | boolean | 是否启用 |
| added_at | string | 添加时间 |

---

#### 16.4.2 为数据源添加术语库

**接口描述**：将术语库关联到指定数据源。

**请求类型**：`POST`

**接口路径**：`/console/api/business_term/datasource/<datasource_id>/libraries`

**是否需要登录**：是

**路径参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| datasource_id | string | 是 | 数据源ID（UUID） |

**请求参数（Body）**：

```json
{
  "library_id": "uuid",
  "is_enabled": true
}
```

**请求字段说明**：

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| library_id | string | 是 | 术语库ID |
| is_enabled | boolean | 否 | 是否启用，默认true |

**返回示例**：

```json
{
  "code": 200,
  "msg": "添加成功",
  "data": {
    "id": "uuid",
    "datasource_id": "uuid",
    "library_id": "uuid",
    "library_name": "电商术语库",
    "is_enabled": true,
    "message": "术语库添加成功"
  }
}
```

**错误响应**：

```json
{
  "code": 409,
  "msg": "术语库 '电商术语库' 已添加到此数据源",
  "data": null
}
```

---

#### 16.4.3 更新数据源术语库状态

**接口描述**：更新数据源关联的术语库状态（启用/禁用）。

**请求类型**：`PUT`

**接口路径**：`/console/api/business_term/datasource/<datasource_id>/libraries/<ds_library_id>`

**是否需要登录**：是

**路径参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| datasource_id | string | 是 | 数据源ID（UUID） |
| ds_library_id | string | 是 | 数据源术语库关联ID（UUID） |

**请求参数（Body）**：

```json
{
  "is_enabled": false
}
```

**请求字段说明**：

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| is_enabled | boolean | 是 | 是否启用 |

**返回示例**：

```json
{
  "code": 200,
  "msg": "更新成功",
  "data": {
    "id": "uuid",
    "is_enabled": false,
    "message": "状态更新成功"
  }
}
```

---

#### 16.4.4 从数据源移除术语库

**接口描述**：从数据源移除关联的术语库。

**请求类型**：`DELETE`

**接口路径**：`/console/api/business_term/datasource/<datasource_id>/libraries/<ds_library_id>`

**是否需要登录**：是

**路径参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| datasource_id | string | 是 | 数据源ID（UUID） |
| ds_library_id | string | 是 | 数据源术语库关联ID（UUID） |

**返回示例**：

```json
{
  "code": 200,
  "msg": "移除成功",
  "data": {
    "id": "uuid",
    "message": "术语库 '电商术语库' 已从数据源移除"
  }
}
```

---

#### 16.4.5 获取数据源可添加的术语库列表

**接口描述**：获取数据源可添加的术语库列表（未添加的术语库），支持搜索和筛选。

**请求类型**：`GET`

**接口路径**：`/console/api/business_term/datasource/<datasource_id>/available`

**是否需要登录**：是

**路径参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| datasource_id | string | 是 | 数据源ID（UUID） |

**请求参数（Query）**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| search | string | 否 | 搜索关键词（匹配库名称或描述） |
| category | string | 否 | 分类筛选 |

**返回示例**：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "items": [
      {
        "id": "uuid",
        "name": "金融术语库",
        "description": "金融领域常用术语",
        "category": "金融",
        "status": "active",
        "term_count": 30,
        "created_at": "2026-05-14T10:00:00"
      }
    ],
    "total": 5
  }
}
```

**说明**：该接口只返回状态为 `active` 且未添加到该数据源的术语库。

**返回字段说明**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | string | 术语库ID（UUID） |
| name | string | 术语库名称 |
| description | string | 术语库描述 |
| category | string | 分类 |
| status | string | 状态（active/inactive） |
| term_count | integer | 术语数量 |
| created_at | string | 创建时间（ISO 8601格式） |

---

## 17. 数据治理模块 - 数据质检（第一阶段）

> **模块说明：** 数据治理分为两个阶段，第一阶段为**数据质检**（已完成），第二阶段为**实际治理**（待实现）。
> 本章节记录的是第一阶段"数据质检"的所有接口，涵盖规则库管理、规则管理、规则执行、报告生成等完整链路。
> 第二阶段"治理"接口请参见 [第18章](#18-数据治理模块---治理第二阶段)。

**基础路径：** `/console/api/governance`

**核心功能：**
- 规则库管理：创建、查询、更新、删除规则库
- 规则管理：三种创建模式（手动专家/AI自然语言/模板导入）、规则解析、SQL预览、规则建议
- 规则执行：批量执行规则、基础空值检测、表关系发现
- 报告生成：生成可下载的质检报告（MD/DOCX/PDF/XLSX格式）
- 质量概览：数据质量评分、评级、趋势分析

**接口清单：**

| 分类 | 接口数 | 说明 |
|------|--------|------|
| 规则库管理 | 4 | CRUD + 详情 |
| 规则管理 | 6 | CRUD + 启用禁用 + 单条测试执行 |
| 规则解析/预览/建议 | 3 | 自然语言解析、SQL预览、智能建议 |
| 规则执行引擎 | 1 | 批量执行（环节二核心） |
| 报告管理 | 6 | CRUD + 下载 + 文件删除 |
| 报告生成 | 2 | 生成文档 + 查询状态（环节三核心） |
| 规则模板 | 3 | 列表 + 详情 + 导入 |
| 治理概览与元数据 | 3 | 质量概览 + 数据源表/列查询 |

---

### 17.1 规则库管理

#### 17.1.1 获取规则库列表

**接口描述：** 分页获取当前用户的规则库列表，支持搜索和数据源筛选。

**请求类型：** `GET`

**接口路径：** `/console/api/governance/libraries`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| page | integer | 否 | 页码（默认1） |
| page_size | integer | 否 | 每页数量（默认20） |
| search | string | 否 | 搜索关键词（匹配规则库名称） |
| datasource_id | string | 否 | 按数据源ID筛选 |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "items": [
      {
        "id": "uuid-string",
        "name": "订单数据质量规则库",
        "description": "针对订单表的数据质量检测",
        "datasource_id": "uuid-string",
        "connect_name": "生产库A",
        "database_name": "ecommerce_db",
        "datasource_db_type": "mysql",
        "status": "active",
        "rule_count": 15,
        "created_at": "2026-06-01T10:00:00"
      }
    ],
    "total": 5,
    "page": 1,
    "page_size": 20,
    "pages": 1
  }
}
```

---

#### 17.1.2 创建规则库

**接口描述：** 创建新的规则库，必须关联数据源。

**请求类型：** `POST`

**接口路径：** `/console/api/governance/libraries`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| name | string | 是 | 规则库名称（最大100字符） |
| datasource_id | string | 是 | 数据源ID（UUID） |
| description | string | 否 | 规则库描述 |

**请求示例：**
```json
{
  "name": "订单数据质量规则库",
  "datasource_id": "550e8400-e29b-41d4-a716-446655440000",
  "description": "针对订单表的数据质量检测"
}
```

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "uuid-string",
    "name": "订单数据质量规则库",
    "datasource_id": "uuid-string",
    "datasource_name": "生产库A",
    "description": "针对订单表的数据质量检测",
    "status": "active",
    "created_at": "2026-06-01T10:00:00"
  }
}
```

**错误响应：**
```json
{
  "code": 400,
  "msg": "datasource_id 不能为空，创建规则库必须关联数据源"
}
```

---

#### 17.1.3 获取规则库详情

**接口描述：** 获取指定规则库的详细信息，包含规则列表和数据源信息。

**请求类型：** `GET`

**接口路径：** `/console/api/governance/libraries/<library_id>`

**是否需要登录：** 是

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "uuid-string",
    "name": "订单数据质量规则库",
    "description": "针对订单表的数据质量检测",
    "datasource_id": "uuid-string",
    "datasource": {
      "id": "uuid-string",
      "name": "生产库A",
      "db_type": "mysql"
    },
    "rules": [
      {
        "id": "uuid-string",
        "rule_name": "手机号非空检测",
        "rule_type": "null_check",
        "target_table": "orders",
        "target_column": "phone",
        "severity": "critical",
        "enabled": true
      }
    ],
    "created_at": "2026-06-01T10:00:00"
  }
}
```

---

#### 17.1.4 更新规则库

**接口描述：** 更新规则库的名称、描述或状态。

**请求类型：** `PUT`

**接口路径：** `/console/api/governance/libraries/<library_id>`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| name | string | 否 | 规则库名称 |
| description | string | 否 | 规则库描述 |
| status | string | 否 | 状态（active/inactive） |

**请求示例：**
```json
{
  "name": "更新后的规则库名称",
  "status": "inactive"
}
```

---

#### 17.1.5 删除规则库

**接口描述：** 删除规则库（会级联删除该规则库下的所有规则）。

**请求类型：** `DELETE`

**接口路径：** `/console/api/governance/libraries/<library_id>`

**是否需要登录：** 是

**返回示例：**
```json
{
  "code": 200,
  "msg": "删除成功"
}
```

---

### 17.2 规则管理

#### 17.2.1 获取规则列表

**接口描述：** 获取规则列表，支持按规则库、类型、启用状态、创建来源筛选。

**请求类型：** `GET`

**接口路径：** `/console/api/governance/rules`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| page | integer | 否 | 页码（默认1） |
| page_size | integer | 否 | 每页数量（默认20） |
| library_id | string | 否 | 按规则库筛选 |
| rule_type | string | 否 | 按规则类型筛选 |
| enabled | string | 否 | 按启用状态筛选（true/false） |
| create_source | string | 否 | 创建来源（manual/ai/template） |
| search | string | 否 | 搜索关键词 |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "items": [
      {
        "id": "uuid-string",
        "library_id": "uuid-string",
        "rule_name": "手机号非空检测",
        "rule_type": "null_check",
        "rule_type_name": "空值检测",
        "target_table": "orders",
        "target_column": "phone",
        "condition_expr": "phone IS NOT NULL",
        "severity": "critical",
        "enabled": true,
        "create_source": "template",
        "created_at": "2026-06-01T10:00:00"
      }
    ],
    "total": 50,
    "page": 1,
    "page_size": 20,
    "pages": 3
  }
}
```

---

#### 17.2.2 创建规则

**接口描述：** 创建新规则，支持三种模式。

**请求类型：** `POST`

**接口路径：** `/console/api/governance/rules`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| library_id | string | 是 | 规则库ID |
| rule_name | string | 是 | 规则名称 |
| rule_type | string | 是 | 规则类型 |
| target_table | string | 是 | 目标表名 |
| target_column | string | 否 | 目标列名（单条件必填） |
| condition_expr | string | 否 | SQL条件表达式（专家模式） |
| conditions | array | 否 | 多条件数组（复合规则模式） |
| condition_mode | string | 否 | 条件组合模式（AND/OR，默认AND） |
| severity | string | 否 | 严重程度（critical/warning/info） |
| enabled | boolean | 否 | 是否启用（默认true） |

**规则类型说明：**

| 类型 | 说明 | 示例条件 |
|------|------|----------|
| null_check | 空值检测 | `column IS NOT NULL` |
| unique | 唯一性检测 | `column IS UNIQUE` |
| format | 格式检测 | `column ~ '^\d{11}$'` |
| threshold | 阈值检测 | `column >= 0` |
| enum | 枚举值检测 | `column IN ('A', 'B')` |
| length_check | 长度检测 | `LENGTH(column) <= 100` |
| range_check | 范围检测 | `column BETWEEN 0 AND 100` |
| date_check | 日期逻辑检测 | `column <= CURRENT_DATE` |
| consistency_check | 一致性检测 | `column_a = column_b` |
| freshness_check | 新鲜度检测 | `column >= NOW() - INTERVAL '7 days'` |
| value_distribution | 值分布检测 | `NULL` |
| custom_sql | 自定义SQL | 用户自定义 |
| composite | 复合规则 | 多条件组合 |
| table_stats | 表统计 | `NULL` |

**请求示例（手动专家模式）：**
```json
{
  "library_id": "uuid-string",
  "rule_name": "订单金额必须为正数",
  "rule_type": "threshold",
  "target_table": "orders",
  "target_column": "total_amount",
  "condition_expr": "total_amount > 0",
  "severity": "critical",
  "enabled": true
}
```

**请求示例（复合规则模式）：**
```json
{
  "library_id": "uuid-string",
  "rule_name": "订单完整性检测",
  "rule_type": "composite",
  "target_table": "orders",
  "conditions": [
    {"column": "customer_id", "condition": "customer_id IS NOT NULL"},
    {"column": "total_amount", "condition": "total_amount > 0"},
    {"column": "order_date", "condition": "order_date IS NOT NULL"}
  ],
  "condition_mode": "AND",
  "severity": "critical"
}
```

**请求示例（AI自然语言模式）：**
```json
{
  "library_id": "uuid-string",
  "rule_name": "订单金额检测",
  "create_source": "ai",
  "rule_config": {
    "target_table": "orders",
    "target_column": "total_amount",
    "rule_type": "threshold",
    "condition_expr": "total_amount > 0",
    "severity": "warning"
  }
}
```

---

#### 17.2.3 获取规则详情

**请求类型：** `GET`

**接口路径：** `/console/api/governance/rules/<rule_id>`

**是否需要登录：** 是

---

#### 17.2.4 更新规则

**请求类型：** `PUT`

**接口路径：** `/console/api/governance/rules/<rule_id>`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| datasource_id | string | 否 | 数据源ID（用于权限验证） |

**请求参数（Body）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| library_id | string | 否 | 规则库ID（可移动规则到其他规则库） |
| rule_name | string | 否 | 规则名称 |
| rule_type | string | 否 | 规则类型 |
| target_table | string | 否 | 目标表名 |
| target_column | string | 否 | 目标列名（复合规则模式下不更新） |
| condition_expr | string | 否 | SQL条件表达式 |
| conditions | array | 否 | 复合条件数组（自动切换为复合规则模式） |
| condition_mode | string | 否 | 条件组合模式（AND/OR） |
| severity | string | 否 | 严重程度（critical/warning/info） |
| enabled | boolean | 否 | 是否启用 |
| sql_text | string | 否 | 自定义SQL文本 |

**说明：**
- 更新 `conditions` 时会自动切换为复合规则模式
- `target_column` 在复合规则模式下不会更新
- 复合规则切换到非复合规则时会清空 `conditions_config`

---

#### 17.2.5 删除规则

**请求类型：** `DELETE`

**接口路径：** `/console/api/governance/rules/<rule_id>`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| datasource_id | string | 否 | 数据源ID（用于权限验证） |

---

#### 17.2.6 启用/禁用规则

**接口描述：** 切换规则的启用状态。

**请求类型：** `PUT`

**接口路径：** `/console/api/governance/rules/<rule_id>/toggle`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| datasource_id | string | 否 | 数据源ID（用于权限验证） |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "uuid-string",
    "enabled": false,
    "msg": "禁用成功"
  }
}
```

---

#### 17.2.7 测试执行单条规则

**接口描述：** 验证规则配置是否正确，实时执行单条规则并返回结果。

**请求类型：** `POST`

**接口路径：** `/console/api/governance/rules/execute`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| datasource_id | string | 是 | 数据源ID |
| rule_id | string | 是 | 规则ID |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "uuid-string",
    "rule_id": "uuid-string",
    "rule_name": "手机号非空检测",
    "rule_type": "null_check",
    "table_name": "orders",
    "column_name": "phone",
    "total_count": 10000,
    "passed_count": 9980,
    "failed_count": 20,
    "failed_rate": 0.20,
    "status": "passed",
    "execution_time_ms": 125
  }
}
```

---

### 17.3 规则解析与建议

#### 17.3.1 规则解析（自然语言 → 结构化规则）

**接口描述：** 将自然语言描述的规则解析为结构化规则配置，支持二阶段交互（解析 + 确认）。

**请求类型：** `POST`

**接口路径：** `/console/api/governance/rules/parse`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| user_input | string | 是 | 自然语言规则描述（如"订单金额不能为负"） |
| datasource_id | string | 是 | 数据源ID |
| target_table | string | 否 | 用户指定的目标表 |
| target_column | string | 否 | 用户指定的目标列 |
| selected_table | string | 否 | 用户从候选中选择的表（阶段2） |
| selected_column | string | 否 | 用户从候选中选择的列（阶段2） |
| target_columns | string | 否 | 多列目标（逗号分隔） |
| db_type | string | 否 | 数据库类型（自动从数据源获取） |

**返回示例（阶段1 - 成功解析）：**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "needs_confirmation": false,
    "stage": "rule_preview",
    "confidence": 0.95,
    "rule_config": {
      "rule_type": "threshold",
      "target_table": "orders",
      "target_column": "total_amount",
      "condition_expr": "total_amount > 0",
      "severity": "warning"
    },
    "sql_preview": "SELECT * FROM orders WHERE NOT (total_amount > 0) LIMIT 20",
    "reasoning": "检测到数值类型的金额字段，建议使用阈值规则"
  }
}
```

**返回示例（阶段1 - 需要确认）：**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "needs_confirmation": true,
    "stage": "table_selection",
    "confidence": 0.7,
    "rule_config": null,
    "candidates": {
      "type": "table",
      "items": [
        {"name": "orders", "score": 0.9, "reason": "表名匹配", "description": "订单主表"},
        {"name": "sales_orders", "score": 0.7, "reason": "实体匹配", "description": "销售订单"}
      ]
    },
    "reasoning": "找到多个候选表，请确认"
  }
}
```

---

#### 17.3.2 SQL预览

**接口描述：** 根据规则配置生成检测SQL并预览，支持四种模式。

**请求类型：** `POST`

**接口路径：** `/console/api/governance/rules/preview`

**是否需要登录：** 是

**请求参数（模板模式）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| template_id | string | 是* | 模板ID（模板模式必填） |
| target_table | string | 是 | 目标表名 |
| target_column | string | 否 | 目标列名 |
| condition_expr | string | 否 | 条件表达式（可覆盖模板默认值） |
| db_type | string | 否 | 数据库类型 |

**请求参数（单条件专家模式）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| rule_type | string | 是 | 规则类型 |
| target_table | string | 是 | 目标表名 |
| target_column | string | 是 | 目标列名 |
| condition_expr | string | 是 | SQL条件表达式 |
| db_type | string | 否 | 数据库类型 |

**请求参数（复合规则模式）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| rule_type | string | 是 | 固定为 `composite` |
| target_table | string | 是 | 目标表名 |
| conditions | array | 是 | 条件数组 `[{column, condition}, ...]` |
| condition_mode | string | 否 | AND/OR |
| db_type | string | 否 | 数据库类型 |

**模式优先级：** `template_id > conditions > condition_expr > auto`

**返回示例：**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "sql": "SELECT * FROM orders WHERE NOT (total_amount > 0) LIMIT 20",
    "scope": "column",
    "mode": "expert",
    "rule_type": "threshold",
    "rule_type_label": "阈值检测",
    "description": "专家模式：直接使用用户输入的条件",
    "template_name": null
  }
}
```

**返回字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 是否成功 |
| sql | string | 生成的检测SQL |
| scope | string | 检测范围（column/table） |
| mode | string | 生成模式（template/expert/multi_condition/auto） |
| rule_type | string | 规则类型 |
| rule_type_label | string | 规则类型名称 |
| description | string | 模式说明 |
| template_name | string | 模板名称（仅模板模式时返回） |

---

#### 17.3.3 规则建议

**接口描述：** 基于数据源表结构，智能推荐适用的规则模板。

**请求类型：** `POST`

**接口路径：** `/console/api/governance/rules/suggest`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| datasource_id | string | 是 | 数据源ID |
| target_table | string | 否 | 目标表名（不填则分析全表） |
| db_type | string | 否 | 数据库类型（自动从数据源获取） |

**返回示例：**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "source": "llm",
    "suggestions": [
      {
        "table": "users",
        "column": "phone",
        "column_comment": "手机号码",
        "data_type": "varchar(20)",
        "rule_type": "format",
        "rule_name": "手机号格式检测",
        "rule_description": "手机号应为11位，以1开头",
        "confidence": 0.95,
        "reasoning": "基于列名和注释推断为手机号字段，建议进行格式校验"
      },
      {
        "table": "orders",
        "column": "total_amount",
        "column_comment": "订单总金额",
        "data_type": "decimal(10,2)",
        "rule_type": "threshold_positive",
        "rule_name": "正数检测",
        "rule_description": "金额字段建议检测正数",
        "confidence": 0.90,
        "reasoning": "基于列名和注释推断为金额字段，建议检测正数"
      }
    ]
  }
}
```

**返回字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 是否成功 |
| source | string | 推荐来源（llm/fallback/empty） |
| suggestions | array | 推荐规则列表 |
| suggestions[].table | string | 目标表名 |
| suggestions[].column | string | 目标列名 |
| suggestions[].column_comment | string | 列注释 |
| suggestions[].data_type | string | 数据类型 |
| suggestions[].rule_type | string | 规则类型 |
| suggestions[].rule_name | string | 规则名称 |
| suggestions[].rule_description | string | 规则描述 |
| suggestions[].confidence | float | 置信度（0-1） |
| suggestions[].reasoning | string | 推荐理由 |
| message | string | 额外提示信息（仅 source=empty 时返回） |

---

### 17.4 规则执行引擎（环节二核心）

#### 17.4.1 批量执行规则

**接口描述：** 执行规则库中的规则，收集质检结果，生成报告。是数据质检阶段的核心接口。

**请求类型：** `POST`

**接口路径：** `/console/api/governance/execute`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| datasource_id | string | 是 | 数据源ID |
| library_ids | array | 否 | 规则库ID列表（与rule_ids互斥） |
| rule_ids | array | 否 | 规则ID列表（与library_ids互斥） |
| include_basic_audit | boolean | 否 | 是否包含基础空值检测（默认false） |
| include_relation_discovery | boolean | 否 | 是否包含表关系发现（默认false） |

**说明：** 不传 `library_ids` 或 `rule_ids` 时，仅执行基础空值检测。

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "report_id": "uuid-string",
    "quality_score": 85.5,
    "grade": "良好",
    "summary": {
      "total_rules": 20,
      "passed_rules": 17,
      "failed_rules": 3,
      "error_rules": 0,
      "quality_score": 85.0,
      "grade": "良好"
    },
    "execution_time": "2026-07-21T14:30:00",
    "basic_audit": {
      "tables_count": 5,
      "tables": [...]
    },
    "basic_audit_detail": {
      "rules_count": 15,
      "results": [
        {
          "id": "result-uuid",
          "rule_id": null,
          "rule_name": "空值检测: users.phone",
          "rule_type": "null_check",
          "severity": "warning",
          "table_name": "users",
          "column_name": "phone",
          "total_count": 10000,
          "passed_count": 9980,
          "failed_count": 20,
          "failed_rate": 0.20,
          "failed_samples": [...],
          "status": "passed"
        }
      ]
    },
    "quality_audit": {
      "rules_count": 5,
      "results": [
        {
          "id": "result-uuid",
          "rule_id": "rule-uuid",
          "rule_name": "手机号非空检测",
          "rule_type": "null_check",
          "severity": "critical",
          "table_name": "users",
          "column_name": "phone",
          "total_count": 10000,
          "passed_count": 9980,
          "failed_count": 20,
          "failed_rate": 0.20,
          "failed_samples": [...],
          "status": "passed"
        }
      ]
    },
    "relation_discovery": {
      "tables_count": 20,
      "relationships_count": 15,
      "cards_count": 10,
      "statistics": {...},
      "relationships": [...],
      "cards": [...]
    }
  }
}
```

**返回字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| report_id | string | 报告ID（执行容器，后续用于生成报告文档） |
| quality_score | float | 质量评分（0-100） |
| grade | string | 质量等级（优秀/良好/一般/较差/差） |
| summary | object | 执行汇总信息 |
| execution_time | string | 执行时间（ISO格式） |
| basic_audit | object | 基础空值检测汇总（仅当 include_basic_audit=true 时返回） |
| basic_audit.tables_count | int | 检测的表数量 |
| basic_audit.tables | array | 各表的空值检测结果 |
| basic_audit_detail | object | 基础空值检测执行明细（rules_count + results列表） |
| basic_audit_detail.results[] | array | 每条规则的执行结果，字段包含 id/rule_id/rule_name/rule_type/severity/table_name/column_name/total_count/passed_count/failed_count/failed_rate/failed_samples/status |
| quality_audit | object | 基于规则库的质检明细（仅当存在规则执行结果时返回） |
| quality_audit.results[] | array | 规则执行结果列表，字段同上 |
| relation_discovery | object | 表关系发现结果（仅当 include_relation_discovery=true 时返回） |
| relation_discovery.tables_count | int | 扫描的表数量 |
| relation_discovery.relationships_count | int | 发现的关系数量 |
| relation_discovery.relationships[] | array | 关系详情列表 |
| relation_discovery.cards[] | array | 关系卡片列表 |

**质量评分计算：**
- 通过率 = passed_count / total_count × 100
- 严重扣分 = critical_fails × 5 + warning_fails × 2
- 最终评分 = max(0, min(100, 通过率 - 扣分))

**质量等级阈值：**

| 等级 | 评分范围 |
|------|----------|
| 优秀 | ≥95分 |
| 良好 | ≥85分 |
| 一般 | ≥70分 |
| 较差 | ≥60分 |
| 差 | <60分 |

---

### 17.5 报告管理

#### 17.5.1 获取报告列表

**请求类型：** `GET`

**接口路径：** `/console/api/governance/reports`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| page | integer | 否 | 页码（默认1） |
| page_size | integer | 否 | 每页数量（默认20） |
| datasource_id | string | 否 | 按数据源筛选 |

---

#### 17.5.2 获取报告详情

**请求类型：** `GET`

**接口路径：** `/console/api/governance/reports/<report_id>`

**是否需要登录：** 是

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "report-uuid",
    "user_id": "user-uuid",
    "datasource_id": "datasource-uuid",
    "report_name": "质检结果_2026-07-23",
    "execution_time": "2026-07-23T10:30:00",
    "scope_tables": null,
    "rules_applied": 20,
    "include_quality": true,
    "include_basic_audit": true,
    "include_relationship": false,
    "quality_score": 85.5,
    "grade": "良好",
    "basic_audit_result": {
      "users": {
        "columns": {
          "phone": {"null_count": 20, "null_rate": 0.002, "total_count": 10000},
          "email": {"null_count": 5, "null_rate": 0.0005, "total_count": 10000}
        },
        "total_count": 10000
      }
    },
    "basic_audit_detail": {
      "rules_count": 15,
      "results": [
        {
          "id": "result-uuid",
          "rule_id": null,
          "rule_name": "空值检测: users.phone",
          "rule_type": "null_check",
          "severity": "warning",
          "table_name": "users",
          "column_name": "phone",
          "total_count": 10000,
          "passed_count": 9980,
          "failed_count": 20,
          "failed_rate": 0.002,
          "failed_samples": [...],
          "status": "passed"
        }
      ]
    },
    "full_relation_discovery": null,
    "quality_audit_result": [
      {
        "id": "result-uuid",
        "rule_id": "rule-uuid",
        "rule_name": "手机号非空检测",
        "rule_type": "null_check",
        "severity": "critical",
        "table_name": "users",
        "column_name": "phone",
        "total_count": 10000,
        "passed_count": 9980,
        "failed_count": 20,
        "failed_rate": 0.002,
        "failed_samples": [...],
        "status": "passed"
      }
    ],
    "summary": {
      "total_rules": 20,
      "passed_rules": 18,
      "failed_rules": 2,
      "error_rules": 0,
      "quality_score": 85.0,
      "grade": "良好"
    },
    "created_at": "2026-07-23T10:30:00",
    "exported_file_path": "/exports/report_xxx.docx",
    "exported_file_type": "docx",
    "exported_file_name": "质检报告_2026年07月23日.docx",
    "file_size": 123456,
    "file_created_at": "2026-07-23T11:00:00",
    "file_status": "completed",
    "file_error_msg": null,
    "has_export": true,
    "history_files": [
      {
        "id": "file-uuid",
        "file_name": "质检报告_2026年07月23日.docx",
        "file_path": "/exports/report_xxx.docx",
        "file_type": "docx",
        "file_size": 123456,
        "created_at": "2026-07-23T11:00:00"
      }
    ]
  }
}
```

**返回字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 报告ID |
| user_id | string | 创建用户ID |
| datasource_id | string | 关联数据源ID |
| report_name | string | 报告名称 |
| execution_time | string | 执行时间 |
| scope_tables | array | 涉及的表列表 |
| rules_applied | int | 应用的规则数量 |
| include_quality | boolean | 是否包含质量检测 |
| include_basic_audit | boolean | 是否包含基础空值检测 |
| include_relationship | boolean | 是否包含关系发现 |
| quality_score | float | 质量评分（0-100） |
| grade | string | 质量等级 |
| basic_audit_result | object | 基础空值检测完整结果（以表为单位） |
| basic_audit_detail | object | 基础空值检测执行明细（rules_count + results） |
| full_relation_discovery | object | 关系盘点完整结果 |
| quality_audit_result | array | 基于规则库的质检结果列表 |
| summary | object | 执行汇总信息 |
| created_at | string | 记录创建时间 |
| exported_file_path | string | 导出文件路径 |
| exported_file_type | string | 导出文件类型 |
| exported_file_name | string | 导出文件显示名称 |
| file_size | int | 文件大小（字节） |
| file_created_at | string | 文件创建时间 |
| file_status | string | 文件生成状态（pending/generating/completed/failed） |
| file_error_msg | string | 文件生成失败时的错误信息 |
| has_export | boolean | 是否有可用导出文件 |
| history_files | array | 历史导出文件列表（包含 id/file_name/file_path/file_type/file_size/created_at） |

---

#### 17.5.3 删除报告

**请求类型：** `DELETE`

**接口路径：** `/console/api/governance/reports/<report_id>`

**是否需要登录：** 是

**返回示例：**
```json
{
  "code": 200,
  "msg": "删除成功",
  "data": {
    "report_id": "uuid-string",
    "files_deleted": 2,
    "files_not_found": [],
    "rule_execution_results_cleared": "cascade",
    "table_relationships_deleted": 5,
    "table_relationship_cards_deleted": 3
  }
}
```

**返回字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| report_id | string | 报告ID |
| files_deleted | int | 物理删除的文件数量 |
| files_not_found | array | 文件不存在（已被删除）的路径列表 |
| rule_execution_results_cleared | string | 规则执行结果清理方式（cascade） |
| table_relationships_deleted | int | 删除的关系记录数量 |
| table_relationship_cards_deleted | int | 删除的关系卡片数量 |

---

#### 17.5.4 修改报告名称

**请求类型：** `PUT`

**接口路径：** `/console/api/governance/reports/<report_id>`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| report_name | string | 是 | 新的报告名称（最多255个字符） |

**请求示例：**
```json
{
  "report_name": "新的报告名称_2026-07-23"
}
```

**返回示例：**

*成功返回：*
```json
{
  "code": 200,
  "msg": "修改成功",
  "data": {
    "report_id": "uuid-string",
    "report_name": "新的报告名称_2026-07-23",
    "files_updated": 3,
    "updated_at": "2026-07-23T10:30:00"
  }
}
```

*失败返回（报告不存在）：*
```json
{
  "code": 404,
  "msg": "报告不存在"
}
```

*失败返回（名称为空）：*
```json
{
  "code": 400,
  "msg": "report_name 不能为空"
}
```

*失败返回（名称过长）：*
```json
{
  "code": 400,
  "msg": "报告名称不能超过255个字符"
}
```

**返回字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| report_id | string | 报告ID |
| report_name | string | 修改后的报告名称 |
| files_updated | int | 同步更新的历史文件记录数（governance_report_files 表） |
| updated_at | string | 报告记录创建时间（名称修改后数据库层面不单独记录更新时间） |

**同步更新说明：**

本接口会同时更新以下两张表，保证数据一致性：

| 表 | 字段 | 说明 |
|----|------|------|
| governance_reports | report_name | 主报告表报告名称 |
| governance_report_files | report_name | 历史导出文件关联表（冗余存储，前端 history_files 列表展示用） |

**不会影响的字段（说明）：**

| 字段 | 说明 |
|------|------|
| exported_file_name / exported_file_path | 已导出文件的文件名和路径（磁盘上的物理文件）保持不变 |
| history_files[].file_name | 已导出文件的文件名保持不变 |
| execution_response | 执行明细 JSON 中不包含报告名称字段，无需同步 |

**前端影响：**

- 报告列表中显示的报告名称会更新为新值
- 报告详情页的 `history_files` 列表中每条历史记录的 `report_name` 字段也会同步更新
- 已下载/已生成报告的文件名不会改变（如需重新生成才能体现在文件名中）

---

#### 17.5.5 下载报告文件

**接口描述：** 下载报告生成的文档文件，支持下载历史文件。

**请求类型：** `GET`

**接口路径：** `/console/api/governance/reports/<report_id>/download`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| file_id | string | 否 | 指定文件ID（不传则下载最新文件） |

---

#### 17.5.6 删除报告文件

**请求类型：** `DELETE`

**接口路径：** `/console/api/governance/reports/<report_id>/file`

**是否需要登录：** 是

---

#### 17.5.7 删除导出文件记录

**请求类型：** `DELETE`

**接口路径：** `/console/api/governance/files/<file_id>`

**是否需要登录：** 是

---

### 17.6 报告生成（环节三核心）

#### 17.6.1 生成报告文档

**接口描述：** 基于已有报告（report_id），生成可下载的文档。是数据质检阶段的最终输出接口。

**请求类型：** `POST`

**接口路径：** `/console/api/governance/report`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| report_id | string | 是 | 报告ID（来自环节二 /execute 接口） |
| format | string | 否 | 文档格式（默认docx），可选：docx/pdf/xlsx/md |
| file_name | string | 否 | 自定义文件名（不传则使用默认命名规则） |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "report_id": "uuid-string",
    "file_path": "/path/to/report.docx",
    "file_name": "质检报告_2026年07月21日.docx",
    "file_size": 12345,
    "format": "docx",
    "mode": "soffice"
  }
}
```

**生成模式说明：**

| 模式 | 说明 |
|------|------|
| soffice | 使用 LibreOffice soffice 转换（推荐，格式最完整） |
| python-docx | 降级使用 python-docx 生成 Word |
| openpyxl | 降级使用 openpyxl 生成 Excel |
| markdown | 生成 Markdown 文件 |

**报告文档结构（六大章节）：**
1. 基本信息
2. 质量概览（三大模块质检结果汇总）
3. 基础空值检测结果（以表为单位）
4. 执行明细（基于规则库）
5. 失败样本明细（全字段违规记录）
6. LLM智能总结 + 改进建议

---

#### 17.6.2 查询报告文档生成状态

**接口描述：** 查询报告文档的生成状态。

**请求类型：** `GET`

**接口路径：** `/console/api/governance/report/<report_id>`

**是否需要登录：** 是

**返回示例：**
```json
{
  "code": 200,
  "data": {
    "report_id": "uuid-string",
    "file_status": "completed",
    "file_error_msg": null,
    "exported_file_name": "质检报告_2026年07月21日.docx",
    "exported_file_path": "/path/to/report.docx",
    "file_size": 12345
  }
}
```

**file_status 状态值：**

| 状态 | 说明 |
|------|------|
| pending | 待生成 |
| generating | 生成中 |
| completed | 生成完成 |
| failed | 生成失败 |

---

### 17.7 规则模板

#### 17.7.1 获取系统模板列表

**接口描述：** 获取所有预置规则模板，支持按类型分组和关键字搜索。

**请求类型：** `GET`

**接口路径：** `/console/api/governance/templates`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| keyword | string | 否 | 搜索关键词（匹配模板名称和描述） |
| rule_type | string | 否 | 按规则类型筛选 |
| group_by | string | 否 | 分组方式（默认按rule_type分组） |
| library_id | string | 否 | 关联规则库ID，用于标记"已在该规则库中的模板" |
| datasource_id | string | 否 | 数据源ID，用于返回"该数据源下建议应用的模板"标记 |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "groups": [
      {
        "rule_type": "null_check",
        "rule_type_name": "空值检测",
        "templates": [
          {
            "id": "uuid-string",
            "template_id": "tmpl-null-check",
            "template_name": "空值检测",
            "default_condition": "column IS NOT NULL",
            "applicable_columns": ["varchar", "text", "int", "decimal"]
          }
        ]
      }
    ],
    "total": 27
  }
}
```

---

#### 17.7.2 获取模板详情

**请求类型：** `GET`

**接口路径：** `/console/api/governance/templates/<template_id>`

**是否需要登录：** 是

---

#### 17.7.3 从模板导入规则

**接口描述：** 基于模板创建规则。

**请求类型：** `POST`

**接口路径：** `/console/api/governance/templates/import`

**是否需要登录：** 是

**请求参数：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| library_id | string | 是 | 目标规则库ID |
| template_ids | array | 是 | 模板ID列表（支持批量导入） |
| target_table | string | 否 | 指定目标表 |
| target_column | string | 否 | 指定目标列 |
| override_name | boolean | 否 | 是否追加表/列名到规则名称后缀（默认true） |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "imported_count": 2,
    "target_table": "orders",
    "target_column": null,
    "rules": [
      {
        "id": "rule-uuid",
        "rule_name": "空值检测(orders)",
        "rule_type": "null_check",
        "target_table": "orders",
        "severity": "warning",
        "enabled": true
      }
    ]
  }
}
```

---

### 17.8 治理概览与元数据

#### 17.8.1 质量概览

**接口描述：** 获取治理模块首页统计数据，包括评分、评级、趋势、维度评分、严重问题摘要等。

**请求类型：** `GET`

**接口路径：** `/console/api/governance/quality/overview`

**是否需要登录：** 是

**请求参数（Query）：**

| 参数名 | 类型 | 是否必填 | 参数说明 |
|--------|------|----------|----------|
| datasource_id | string | 否 | 按数据源过滤 |
| date_range | string | 否 | 统计时间范围（7d/30d/90d/custom:start,end，默认30d） |

**返回示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "quality_score": 85.5,
    "grade": "良好",
    "report_count": 50,
    "library_count": 5,
    "rule_count": 120,
    "enabled_rule_count": 100,
    "dimensions": {
      "completeness": 92.5,
      "uniqueness": 88.0,
      "validity": 85.0,
      "consistency": 90.0,
      "timeliness": 95.0,
      "composite": 80.0
    },
    "critical_findings": [
      {
        "rule_name": "手机号非空检测",
        "table_name": "users",
        "column_name": "phone",
        "failed_count": 20,
        "failed_rate": 0.002,
        "status": "failed",
        "severity": "critical",
        "rule_id": "rule-uuid",
        "report_id": "report-uuid"
      }
    ],
    "report_trend": [
      {
        "date": "2026-07-20",
        "count": 5,
        "avg_score": 87.5
      }
    ],
    "rule_type_stats": [
      {
        "type": "null_check",
        "type_name": "空值检测",
        "count": 50,
        "percentage": 41.7
      }
    ],
    "date_range": {
      "start": "2026-06-21T00:00:00",
      "end": "2026-07-21T00:00:00",
      "range": "30d"
    }
  }
}
```

**返回字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| quality_score | float | 最新报告的质量评分（0-100） |
| grade | string | 质量等级（优秀/良好/一般/较差/差） |
| report_count | int | 报告总数 |
| library_count | int | 规则库数量 |
| rule_count | int | 规则总数 |
| enabled_rule_count | int | 启用规则数量 |
| dimensions | object | 各质量维度评分（completeness/uniqueness/validity/consistency/timeliness/composite） |
| critical_findings | array | 严重问题摘要列表 |
| critical_findings[].rule_name | string | 规则名称 |
| critical_findings[].table_name | string | 目标表名 |
| critical_findings[].column_name | string | 目标列名 |
| critical_findings[].failed_count | int | 违规数量 |
| critical_findings[].failed_rate | float | 违规率 |
| critical_findings[].status | string | 执行状态 |
| critical_findings[].severity | string | 严重程度 |
| critical_findings[].rule_id | string | 规则ID |
| critical_findings[].report_id | string | 报告ID |
| report_trend | array | 报告趋势数据（按天统计） |
| report_trend[].date | string | 日期 |
| report_trend[].count | int | 报告数量 |
| report_trend[].avg_score | float | 当日平均质量评分 |
| rule_type_stats | array | 规则类型统计 |
| rule_type_stats[].type | string | 规则类型代码 |
| rule_type_stats[].type_name | string | 规则类型名称 |
| rule_type_stats[].count | int | 该类型规则数量 |
| rule_type_stats[].percentage | float | 占比百分比 |
| date_range | object | 统计时间范围 |
| date_range.start | string | 开始时间（ISO格式） |
| date_range.end | string | 结束时间（ISO格式） |
| date_range.range | string | 范围标识（7d/30d/90d/custom:xxx） |

---

#### 17.8.2 获取数据源下的所有表

**请求类型：** `GET`

**接口路径：** `/console/api/governance/datasources/<datasource_id>/tables`

**是否需要登录：** 是

---

#### 17.8.3 获取指定表的字段列表

**请求类型：** `GET`

**接口路径：** `/console/api/governance/datasources/<datasource_id>/tables/<table_name>/columns`

**是否需要登录：** 是

---

### 17.9 数据质检完整链路流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        数据质检阶段完整链路（已实现）                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【环节一：规则创建】                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  用户操作                                                             │   │
│  │  ├── 手动专家模式：直接输入 SQL 条件                                   │   │
│  │  ├── AI自然语言模式：输入"订单金额不能为负" → LLM解析 → 用户确认      │   │
│  │  ├── 模板导入模式：选择预置模板，填入表/列                             │   │
│  │  └── 规则建议：基于Schema智能推荐适用规则                              │   │
│  │                                                                       │   │
│  │  核心接口                                                             │   │
│  │  ├── POST /governance/rules/parse    → 自然语言解析                   │   │
│  │  ├── POST /governance/rules/preview  → SQL预览验证                    │   │
│  │  └── POST /governance/rules          → 创建规则                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                         │
│  【环节二：规则执行】                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  POST /governance/execute  （核心接口）                                │   │
│  │                                                                       │   │
│  │  输入: {                                                             │   │
│  │    datasource_id: "xxx",                                             │   │
│  │    library_ids: ["lib1", "lib2"],                                    │   │
│  │    include_basic_audit: true,                                        │   │
│  │    include_relation_discovery: true                                   │   │
│  │  }                                                                   │   │
│  │                                                                       │   │
│  │  执行:                                                               │   │
│  │  1. AuditExecutor.execute_only() → 执行规则库规则                     │   │
│  │  2. 基础空值检测（可选）                                              │   │
│  │  3. 表关系发现（可选）                                                 │   │
│  │  4. 计算质量评分 + 更新报告                                            │   │
│  │  5. 存入 execution_response（唯一真实数据源）                          │   │
│  │                                                                       │   │
│  │  输出: {                                                             │   │
│  │    report_id: "xxx",                                                 │   │
│  │    quality_score: 85.5,                                              │   │
│  │    grade: "良好",                                                    │   │
│  │    summary: {...}                                                    │   │
│  │  }                                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                         │
│  【环节三：报告生成】                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  POST /governance/report  （核心接口）                                 │   │
│  │                                                                       │   │
│  │  输入: {                                                             │   │
│  │    report_id: "xxx",     // 来自环节二                              │   │
│  │    format: "docx",       // docx/pdf/xlsx/md                        │   │
│  │    file_name: "自定义名称"                                            │   │
│  │  }                                                                   │   │
│  │                                                                       │   │
│  │  执行:                                                               │   │
│  │  1. 读取 execution_response                                           │   │
│  │  2. LibreOfficeExporter / MarkdownExporter 生成文档                   │   │
│  │  3. 记录文件到 governance_report_files                                │   │
│  │                                                                       │   │
│  │  输出: {                                                             │   │
│  │    report_id: "xxx",                                                 │   │
│  │    file_path: "/path/to/report.docx",                                │   │
│  │    file_name: "质检报告_2026年07月21日.docx",                        │   │
│  │    file_size: 12345,                                                 │   │
│  │    mode: "soffice"                                                   │   │
│  │  }                                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 18. 数据治理模块 - 治理（第二阶段）

> **模块说明：** 第二阶段为**实际治理**阶段，基于第一阶段数据质检发现的问题，执行针对性的治理动作。
> 例如：对账差异处理、问题数据修复/回填、数据隔离/清洗、告警通知等。
> **此章节内容待实现，完成后将补充具体接口文档。**

### 18.1 治理任务管理（待实现）

#### 18.1.1 创建治理任务

**状态：** 待实现

**说明：** 根据质检报告发现的问题，创建针对性的治理任务。

---

#### 18.1.2 执行治理动作

**状态：** 待实现

**说明：** 执行具体的数据修复、对账、回填等治理操作。

---

#### 18.1.3 治理结果查询

**状态：** 待实现

**说明：** 查询治理任务的执行结果和状态。

---

### 18.2 数据修复（待实现）

#### 18.2.1 批量修复问题数据

**状态：** 待实现

---

#### 18.2.2 数据回填

**状态：** 待实现

---

#### 18.2.3 数据清洗

**状态：** 待实现

---

### 18.3 对账核对（待实现）

#### 18.3.1 创建对账任务

**状态：** 待实现

---

#### 18.3.2 执行对账

**状态：** 待实现

---

#### 18.3.3 对账结果处理

**状态：** 待实现

---

### 18.4 告警通知（待实现）

#### 18.4.1 配置告警规则

**状态：** 待实现

---

#### 18.4.2 告警历史查询

**状态：** 待实现

---

### 18.5 治理流程自动化（待实现）

#### 18.5.1 配置治理规则

**状态：** 待实现

**说明：** 配置质检问题 → 自动触发治理动作的映射规则。

---

#### 18.5.2 执行自动化治理

**状态：** 待实现

---

#### 18.5.3 治理审计日志

**状态：** 待实现

---

## 错误码说明

| 错误码 | 说明 |
|--------|------|
| 200 | 操作成功 |
| 400 | 请求参数错误 |
| 401 | 未登录或Token无效 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 409 | 资源冲突（如版本号已存在） |
| 500 | 服务器内部错误 |

---

## 注意事项

1. **认证机制**：大部分接口需要登录认证，请在请求头中携带有效的Session Cookie或JWT Token
2. **数据源连接**：不同数据库类型的连接参数不同，请参考各数据库的必填参数说明
3. **异步操作**：表结构提取为异步操作，会立即返回请求ID，实际处理在后台进行
4. **向量检索**：数据卡片查询使用向量检索技术，需要配置Weaviate向量数据库
5. **SQL生成**：智能查询功能依赖LLM生成SQL，需要配置相应的API密钥
6. **文件上传**：Excel文件上传限制为20MB，支持.xlsx和.xls格式
7. **分页查询**：列表类接口支持分页，建议合理设置page_size避免性能问题

---

## 项目功能概述

### 核心功能

1. **多数据源管理**：支持MySQL、PostgreSQL、SQL Server、Oracle、SQLite、Trino、电科金仓（KingBase）、OceanBase（MySQL 租户模式）、达梦（DMBase）等多种数据库
2. **智能表结构提取**：自动提取数据库表结构，生成标准化的数据卡片
3. **向量检索**：基于Weaviate向量数据库，实现数据卡片的语义检索
4. **智能SQL生成**：基于LLM技术，根据自然语言问题自动生成SQL查询
5. **跨数据源查询**：支持多数据源联合查询，支持多种融合策略
6. **业务术语库**：支持创建和管理业务术语库，实现NL2SQL场景中的术语识别和改写，提升查询准确性
7. **数据质量审计**：对数据库表进行数据质量检查，统计空值、空字符串等
8. **用户权限管理**：完整的用户、用户组、角色权限管理体系

### 技术架构

- **后端框架**：Flask + Flask-RESTful
- **数据库ORM**：SQLAlchemy
- **向量数据库**：Weaviate
- **LLM集成**：支持通义千问等大语言模型
    - 基础对话：qwen-max-latest
    - 重排序Rerank：通义   千问的 gte-rerank-v2
    - 文本向量化嵌入模型：通义千问的 text-embedding-v3
- **数据库支持**：MySQL、PostgreSQL、SQL Server、Oracle、SQLite、Trino、**电科金仓（KingBase）**、**OceanBase（MySQL 租户模式）**、**达梦（DMBase）**

### 业务流程

1. **数据源接入**：用户配置数据库连接信息，系统测试连接并提取表结构
2. **数据卡片生成**：系统自动为每个表生成数据卡片，包含表结构、字段描述等信息
3. **向量化存储**：数据卡片内容向量化后存储到Weaviate，支持语义检索
4. **智能查询**：用户输入自然语言问题，系统检索相关数据卡片，生成SQL并执行
5. **结果融合**：多数据源查询时，根据融合策略合并结果

---

## 附录

### 数据库连接字符串格式示例

**MySQL:**
```
mysql+pymysql://username:password@host:port/database
```

**PostgreSQL:**
```
postgresql+psycopg://username:password@host:port/database
```

**SQL Server:**
```
mssql+pyodbc://username:password@dsn_name/database
或
mssql+pyodbc://username:password@host:port/database?driver=OOntiCards+Driver+17+for+SQL+Server
```

**Oracle:**
```
oracle+oracledb://username:password@host:port/?service_name=SERVICE_NAME
或
oracle+oracledb://username:password@host:port/?sid=SID
```

**SQLite:**
```
sqlite:///path/to/database.db
或
sqlite:///:memory:  (内存模式)
```

**Trino:**
```
trino://username@host:port/catalog/schema
```

**电科金仓（KingBase）:**
```
postgresql+psycopg://username:password@host:port/database
```

**OceanBase（MySQL 租户模式）:**
```
mysql+pymysql://username:password@host:port/database
```
> OceanBase MySQL 租户使用 mysql+pymysql 协议（默认端口 2881），连接串形式与 MySQL 一致。Oracle 租户模式将在后续版本中支持。

**达梦（DMBase）:**
```
dm+pymysql://username:password@host:port/database
```
> 达梦数据库使用 dm+pymysql 协议，兼容 Oracle 语法风格。

---

**文档版本：** 1.5.1
**最后更新：** 2026-08-04
**维护者：** OntiCards开发团队
