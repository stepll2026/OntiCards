"""
 @File: data_audit.py
 @Description: 数据盘查与审计工具类
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-11-12 14:41
"""
from __future__ import annotations
from __future__ import annotations

import time

"""
数据盘查接口（多数据库版）
POST /console/api/data_audit
"""

import re
from typing import Dict, List, Optional

from flask import Blueprint, request
from flask_restful import Resource, Api
from sqlalchemy import text
from sqlalchemy.engine import Engine, Result
from sqlalchemy.exc import SQLAlchemyError

# 复用你项目已有的连接封装
from controllers.datasource.database_schema_extractor import (
    build_db_url_from_json, _to_raw_conn_str, get_db_engine
)

# 提示词配置管理器
from models.prompt_config import prompt_manager

bp_data_audit = Blueprint("bp_data_audit", __name__)
api = Api(bp_data_audit)

# —— 数据库提示词名称映射（兼容原来的文件读取方式）——
_SQL_FILE_NAMES: Dict[str, str] = {
    "postgresql": "data_audit_postgre.txt",
    "mysql": "data_audit_mysql.txt",
    "mssql": "data_audit_mssql.txt",
    "oracle": "data_audit_oracle.txt",
    "sqlite": "data_audit_sqlite.txt",
    "trino": "data_audit_trino.txt",
    # 人大金仓（KingBase）- 使用独立的 DDL SQL 文件
    "kingbase": "data_audit_kingbase.txt",
    # OceanBase MySQL 模式租户：使用独立的 DDL SQL 文件（去掉了 DROP PROCEDURE，避免 OB PREPARE 协议 bug）
    "oceanbase": "data_audit_oceanbase.txt",
    # 达梦 DM：使用独立的 DDL SQL 文件（基于 Oracle 语法，过程+临时表方式）
    "dm": "data_audit_dm.txt",
}

_SPLIT_PATTERN = r"--@@split"

def _ok(data): return {"code": 200, "msg": "success", "data": data}, 200
def _bad(msg, code=400): return {"code": code, "msg": msg, "data": None}, 200

def _normalize_db_type(s: str) -> str:
    s = (s or "").lower()
    if s in ("postgres","postgresql","pg"): return "postgresql"
    if s in ("mysql","mariadb"): return "mysql"
    if s in ("mssql","sqlserver","sql_server"): return "mssql"
    if s in ("oracle","ora"): return "oracle"
    if s in ("sqlite","sqlite3"): return "sqlite"
    if s in ("trino",): return "trino"
    # 人大金仓（KingBase）- 基于 PostgreSQL 内核，标准化为 kingbase
    if s in ("kingbase","kingbase8","kingbasees","人大金仓","金仓"): return "kingbase"
    # OceanBase MySQL 模式租户（仅 MySQL 模式；Oracle 模式由探测逻辑拒绝）
    if s in ("oceanbase","ob","oceanbase_mysql","oceanbase_mysql_mode","oceanbase-ce"): return "oceanbase"
    # 达梦 DM：标准化为 dm
    if s in ("dm","dameng","达梦"): return "dm"
    return s

def _locate_sql_file(db_type: str) -> str:
    """按 db_type 查找对应的提示词名称（优先从数据库读取）。"""
    file_name = _SQL_FILE_NAMES.get(db_type)
    if not file_name:
        raise FileNotFoundError(f"未找到 {db_type} 的提示词配置")
    # 检查数据库或缓存中是否有内容
    content = prompt_manager.get_prompt(file_name)
    if content is None:
        raise FileNotFoundError(f"未找到 {db_type} 的提示词内容")
    return file_name  # 返回名称而非路径，后续通过 prompt_manager 获取内容

def _read_sql_chunks_from_file(db_type: str) -> List[str]:
    """读取提示词内容（从数据库优先，fallback到文件），并按 --@@split 切分为可执行语句段。"""
    file_name = _locate_sql_file(db_type)
    raw = prompt_manager.get_prompt(file_name)
    if not raw:
        raise FileNotFoundError(f"未找到 {file_name} 的提示词内容")

    # Oracle 特殊处理：
    # 把“单独一行的 /”也当成分隔符，替换成 --@@split
    if db_type == "oracle":
        raw = re.sub(r'^\s*/\s*$', '--@@split', raw, flags=re.MULTILINE)

    # 统一按 --@@split 来切
    chunks = [s.strip() for s in re.split(_SPLIT_PATTERN, raw) if s.strip()]

    filtered: List[str] = []
    for s in chunks:
        lines = s.splitlines()
        if not lines:
            continue
        first = lines[0].strip().upper()
        # 过滤客户端控制语句与 SQL*Plus 结束符、以及纯注释块
        if first.startswith("DELIMITER"):   # MySQL 客户端命令
            continue
        if first == "/":                   # Oracle 单独一行的 /
            continue
        if all((ln.strip().startswith("--") or ln.strip() == "") for ln in lines):
            continue
        filtered.append(s)
    return filtered

def _exec_ddl_batch(engine: Engine, stmts: List[str], db_type: str, *, mysql_database: Optional[str] = None):
    """逐条执行 DDL；PG 需转义 %，MySQL 可先 USE 目标库；Oracle/达梦 需剔除 SQL*Plus 风格的 /。"""
    with engine.begin() as conn:
        if db_type in ("mysql", "oceanbase") and mysql_database:
            conn.exec_driver_sql(f"USE `{mysql_database}`")
        for s in stmts:
            sql_to_run = s
            if db_type == "postgresql" or db_type == "kingbase":
                # 避免 psycopg3 把 %I 误当客户端占位符
                sql_to_run = s.replace("%", "%%")
            if db_type == "oracle" or db_type == "dm":
                # 关键：剔除所有单独一行的 "/"（SQL*Plus 专用；达梦与 Oracle 兼容 SQL*Plus 风格）
                sql_to_run = "\n".join(ln for ln in sql_to_run.splitlines() if ln.strip() != "/")
            conn.exec_driver_sql(sql_to_run)


def load_data_audit_ddl(engine: Engine, db_type: str, *, mysql_database: Optional[str] = None) -> None:
    """
    一次性下发 data_audit 所需的 DDL（存储过程 / 函数）。

    - PostgreSQL / MySQL / MSSQL：DLL 中 CREATE 是幂等的（OR REPLACE / DROP IF EXISTS + CREATE），
      因此可以反复调用；本函数适用于"批量扫描多张表只发一次 DDL"的场景。
    - Oracle / SQLite / Trino：DLL 由各自特殊路径处理，无需预下发；
      本函数对它们安全 no-op。

    Args:
        engine: SQLAlchemy Engine 对象
        db_type: 数据库类型
        mysql_database: MySQL 需要 USE 的库名（可选）
    """
    db_type = _normalize_db_type(db_type)
    # OceanBase 使用独立的 DDL 文件（ob_data_audit），通过 DDL 文件自身的
    # DROP PROCEDURE IF EXISTS 实现幂等，无需额外清理逻辑
    # 达梦 DM 使用独立的 DDL 文件（data_audit_dm.txt），与 Oracle 一样走 SQL*Plus 风格
    if db_type not in ("postgresql", "mysql", "mssql", "kingbase", "oceanbase", "dm"):
        # Oracle/SQLite/Trino 在 perform_data_audit 中走应用层统计，无需 DDL
        return

    stmts = _read_sql_chunks_from_file(db_type)
    if not stmts:
        raise Exception(f"{db_type} 的外置 SQL 脚本为空或未找到可执行语句")

    _exec_ddl_batch(engine, stmts, db_type, mysql_database=mysql_database)


def _call_data_audit_proc(engine: Engine, db_type: str, schema: str, table: str):
    """
    调用已创建好的 data_audit 存储过程/函数，返回列级结果行。

    适用于 PG/MySQL/MSSQL/KingBase；Oracle/SQLite/Trino 走对应 _audit_*_direct 路径。
    OceanBase MySQL 模式使用独立的 ob_data_audit 存储过程。
    """
    if db_type == "postgresql" or db_type == "kingbase":
        # KingBase 基于 PostgreSQL 协议，复用 PG 调用方式
        return _fetch_mappings(engine, "SELECT * FROM data_audit(:s, :t)", {"s": schema, "t": table})
    if db_type == "mysql":
        # MySQL GTID 模式要求：存储过程内的临时表操作必须在事务外部执行
        # 使用 engine.connect() 而非 engine.begin() 来保持 autocommit=1
        with engine.connect() as conn:
            result = conn.execute(text("CALL data_audit(:s, :t)"), {"s": schema, "t": table})
            return [dict(row) for row in result.mappings().all()]
    if db_type == "oceanbase":
        # OceanBase MySQL 模式使用独立的 ob_data_audit 存储过程
        with engine.connect() as conn:
            result = conn.execute(text("CALL ob_data_audit(:s, :t)"), {"s": schema, "t": table})
            return [dict(row) for row in result.mappings().all()]
    if db_type == "mssql":
        return _fetch_mappings(engine, "EXEC dbo.data_audit @schema=:s, @table=:t", {"s": schema, "t": table})
    if db_type == "dm":
        # 达梦 DM：调用独立的过程（与 Oracle PL/SQL 兼容），参数：OWNER, TABLE
        # 过程内部 EXEC IMMEDIATE 'SELECT * FROM TMP_DATA_AUDIT ...' 会作为结果集返回
        with engine.connect() as conn:
            result = conn.execute(
                text("CALL data_audit(:s, :t)"),
                {"s": schema, "t": table}
            )
            return [dict(row) for row in result.mappings().all()]
    raise Exception(f"_call_data_audit_proc 不支持 db_type={db_type}")


def _fetch_mappings(engine: Engine, sql: str, params: Optional[dict] = None) -> List[dict]:
    """执行查询，返回 list[dict]（SQLAlchemy 2.x 标准写法）。"""
    with engine.begin() as conn:
        res: Result = conn.execute(text(sql), params or {})
        return [dict(row) for row in res.mappings().all()]

# 核心方法封装（供其他接口整合调用）
def perform_data_audit(engine, db_type, database_name, table_name, schema_name=None, connect_info=None):
    """
    执行数据盘查的核心工具方法

    Args:
        engine: SQLAlchemy Engine 对象
        db_type: 数据库类型 (postgresql/mysql/mssql/oracle/sqlite)
        database_name: 数据库名
        table_name: 表名
        schema_name: 模式名 (可选)
        connect_info: 连接信息字典 (可选，用于获取用户名等)

    Returns:
        dict: 包含盘查结果的字典，格式为:
        {
            "db_type": str,
            "database": str,
            "schema": str,
            "table": str,
            "report": [{
                "column_name": str,
                "data_type": str,
                "total_rows": int,
                "null_count": int,
                "empty_str_count": int,
                "missing_count": int,
                "missing_pct": float
            }]
        }

    Raises:
        Exception: 当盘查执行失败时抛出异常
    """
    try:
        db_type = _normalize_db_type(db_type)
        # connect_info 允许为 None（除 Oracle 之外不依赖），方便 audit_executor 复用
        connect_info = connect_info or {}

        # 解析 schema.table
        if "." in (table_name or ""):
            parsed_schema, table = table_name.split(".", 1)
            schema_name = (parsed_schema or "").strip() or schema_name
            table = (table or "").strip()
        else:
            table = (table_name or "").strip()
            if not schema_name:
                if db_type == "postgresql" or db_type == "kingbase":
                    schema_name = "public"
                elif db_type == "mssql":
                    schema_name = "dbo"
                elif db_type == "oracle" or db_type == "dm":
                    # Oracle/达梦：默认 schema = 用户名大写
                    schema_name = (connect_info.get("username") or "").upper()

        # SQLite：使用"伪 SQL 文件"模板 + 动态替换列名执行
        if db_type == "sqlite":
            return _handle_sqlite_audit(engine, table)

        # Oracle：直接应用层统计，不再调用 data_audit() 函数
        if db_type == "oracle":
            owner = schema_name or (connect_info.get("username") if connect_info else None) or ""
            # Oracle 的 database_name 实际上是 target_schema（逻辑上的"数据库名"）
            db_name = database_name or owner.upper()
            return _audit_oracle_direct(engine, owner.upper(), table, db_name)

        # Trino：直接应用层统计
        if db_type == "trino":
            # 对于 Trino，database_name 格式为 "catalog/schema"，需要拆分
            if database_name and "/" in database_name:
                catalog, actual_schema = database_name.split("/", 1)
                schema = schema_name or actual_schema
            else:
                catalog = (connect_info.get("catalog") if connect_info else None) or ""
                schema = schema_name or (connect_info.get("schema") if connect_info else None) or ""

            # 获取 catalog 的真实类型（从连接信息中获取，或从 catalog 名推断）
            catalog_type = None
            if connect_info:
                # 优先从连接信息中获取 catalog_type（如果有的话）
                catalog_type = connect_info.get("catalog_type")

            print(f"[DEBUG] Trino 数据盘查 - catalog: {catalog}, catalog_type: {catalog_type}, schema: {schema}, table: {table}")
            return _audit_trino_direct(engine, catalog, schema, table, catalog_type=catalog_type)

        # 其它库：先执行 DDL（函数/存储过程创建），再调用
        stmts = _read_sql_chunks_from_file(db_type)
        if not stmts:
            raise Exception(f"{db_type} 的外置 SQL 脚本为空或未找到可执行语句")

        _exec_ddl_batch(
            engine, stmts, db_type,
            mysql_database=(database_name or (connect_info.get("database") if connect_info else None))
        )

        # 调用并取结果
        if db_type == "postgresql" or db_type == "kingbase":
            schema = schema_name or "public"
            rows = _fetch_mappings(engine,
                "SELECT * FROM data_audit(:s, :t)",
                {"s": schema, "t": table}
            )

        elif db_type == "mysql":
            schema = schema_name or database_name or (connect_info.get("database") if connect_info else None)
            # MySQL GTID 模式要求：存储过程内的临时表操作必须在事务外部执行
            # 使用 engine.connect() 而非 engine.begin() 来保持 autocommit=1
            with engine.connect() as conn:
                result = conn.execute(
                    text("CALL data_audit(:s, :t)"),
                    {"s": schema, "t": table}
                )
                rows = [dict(row) for row in result.mappings().all()]

        elif db_type == "oceanbase":
            # OceanBase MySQL 模式：使用独立的 ob_data_audit 存储过程
            schema = schema_name or database_name or (connect_info.get("database") if connect_info else None)
            with engine.connect() as conn:
                result = conn.execute(
                    text("CALL ob_data_audit(:s, :t)"),
                    {"s": schema, "t": table}
                )
                rows = [dict(row) for row in result.mappings().all()]

        elif db_type == "mssql":
            schema = schema_name or "dbo"
            rows = _fetch_mappings(engine,
                "EXEC dbo.data_audit @schema=:s, @table=:t",
                {"s": schema, "t": table}
            )

        elif db_type == "dm":
            # 达梦 DM：先下发过程 DDL，再调用过程返回结果集
            schema = schema_name or (connect_info.get("username") if connect_info else None) or ""
            # 达梦默认 schema = 用户名大写，与 Oracle 完全一致
            if schema:
                schema = str(schema).upper()
            with engine.connect() as conn:
                result = conn.execute(
                    text("CALL data_audit(:s, :t)"),
                    {"s": schema, "t": table}
                )
                rows = [dict(row) for row in result.mappings().all()]

        else:
            raise Exception(f"暂不支持的 db_type：{db_type}")

        # 统一整形
        report = []
        for r in rows:
            report.append({
                "column_name": r.get("column_name"),
                "data_type": r.get("data_type"),
                "total_rows": int(r.get("total_rows") or 0),
                "null_count": int(r.get("null_count") or 0),
                "empty_str_count": int(r.get("empty_str_count") or 0),
                "missing_count": int(
                    r.get("missing_count")
                    if r.get("missing_count") is not None
                    else (int(r.get("null_count") or 0) + int(r.get("empty_str_count") or 0))
                ),
                "missing_pct": float(r.get("missing_pct") or 0.0),
            })
        report.sort(key=lambda x: (-x["missing_pct"], x["column_name"] or ""))

        return {
            "db_type": db_type,
            "database": database_name,
            "schema": schema_name,
            "table": table,
            "report": report
        }

    except SQLAlchemyError as e:
        raise Exception(f"执行失败：{str(e)}")
    except Exception as e:
        raise Exception(f"异常：{str(e)}")

# 接口测试资源类
class DataAuditAPI(Resource):

    """POST /console/api/data_audit"""

    def post(self):
        """
        JSON:
        {
          "db_type": "postgresql/mysql/mssql/oracle/sqlite",
          "connect_info": {... 用于拼接连接串 ...},
          "database_name": "库名(Oracle 可忽略)",
          "table_name": "schema.table 或 table",
          "schema": "可选：MySQL=database；Postgres默认public；MSSQL默认dbo；Oracle=owner(用户名)"
        }
        """
        payload = request.get_json(silent=True) or {}
        db_type = _normalize_db_type(payload.get("db_type"))
        connect_info = payload.get("connect_info") or {}
        database_name = payload.get("database_name")
        table_name = payload.get("table_name")
        schema_from_body = payload.get("schema")

        if not db_type: return _bad("缺少 db_type")
        if not connect_info: return _bad("缺少 connect_info")
        if not table_name: return _bad("缺少 table_name")

        # 构建连接并创建 Engine
        try:
            url = build_db_url_from_json({"db_type": db_type, **connect_info, "database": database_name})
            engine = get_db_engine(_to_raw_conn_str(url), db_type=db_type)
        except Exception as e:
            return _bad(f"连接失败：{e}")

        try:
            # 调用工具方法执行数据盘查
            result = perform_data_audit(
                engine=engine,
                db_type=db_type,
                database_name=database_name,
                table_name=table_name,
                schema_name=schema_from_body,
                connect_info=connect_info
            )
            return _ok(result)

        except Exception as e:
            return _bad(str(e))

# ---------- ORACLE：涉及复杂的表空间和权限控制，容易导致盘点审计的sql语句执行报错，这里直接在代码逻辑层统计 ----------
def _audit_oracle_direct(engine: Engine, owner: str, table: str, database_name: str = None):
    """
    Oracle 版数据盘查：不建 TYPE / FUNCTION，直接应用层统计。
    - 只统计 NULL；Oracle 把 '' 当成 NULL，所以 empty_str_count 恒为 0
    - 支持大小写混合的表名（保持原样）
    - database_name 用于返回值的 database 字段（Oracle 中通常是 target_schema）
    """
    owner_u = (owner or "").upper()
    # 关键修复：不强制转换表名为大写，保持原样
    table_name = (table or "").strip()

    with engine.begin() as conn:
        # 1) 总行数 - 先尝试原始表名，失败后再尝试大写表名
        total = 0
        table_to_use = table_name

        try:
            total_sql = f'SELECT COUNT(*) FROM "{owner_u}"."{table_name}"'
            total = conn.execute(text(total_sql)).scalar() or 0
        except Exception as e:
            # 如果失败且表名不是全大写，尝试使用大写表名
            if table_name != table_name.upper():
                try:
                    table_upper = table_name.upper()
                    total_sql = f'SELECT COUNT(*) FROM "{owner_u}"."{table_upper}"'
                    total = conn.execute(text(total_sql)).scalar() or 0
                    table_to_use = table_upper  # 记录成功的表名格式
                except Exception:
                    # 两种方式都失败，抛出原始异常
                    raise e
            else:
                raise e

        # 2) 列信息 - 使用 all_tab_columns 查询，先尝试原始表名
        cols = []
        try:
            cols = conn.execute(
                text("""
                     SELECT column_name, data_type
                     FROM all_tab_columns
                     WHERE owner = :own
                       AND table_name = :tbl
                     ORDER BY column_id
                     """),
                {"own": owner_u, "tbl": table_name.upper()},
            ).fetchall()

            # 如果没有结果且表名不是全大写，尝试使用原始表名
            if not cols and table_name != table_name.upper():
                cols = conn.execute(
                    text("""
                         SELECT column_name, data_type
                         FROM all_tab_columns
                         WHERE owner = :own
                           AND table_name = :tbl
                         ORDER BY column_id
                         """),
                    {"own": owner_u, "tbl": table_name},
                ).fetchall()
        except Exception:
            # 查询列信息失败，返回空列表
            cols = []

        report = []
        for col_name, data_type in cols:
            col_name_u = col_name  # all_tab_columns 里本身就是大写未加引号的列名
            # 3) NULL 数（Oracle: '' 也会算作 NULL）
            null_sql = (
                f'SELECT COUNT(*) FROM "{owner_u}"."{table_to_use}" '
                f'WHERE "{col_name_u}" IS NULL'
            )
            null_count = conn.execute(text(null_sql)).scalar() or 0

            missing = int(null_count)
            pct = 0.0 if total == 0 else round(100.0 * missing / int(total), 2)

            report.append({
                "column_name": col_name_u,
                "data_type": data_type,
                "total_rows": int(total),
                "null_count": int(null_count),
                "empty_str_count": 0,  # Oracle: '' 即 NULL
                "missing_count": int(missing),
                "missing_pct": float(pct),
            })

        report.sort(key=lambda x: (-x["missing_pct"], x["column_name"] or ""))

        return {
            "db_type": "oracle",
            "database": database_name or owner_u,
            "schema": owner_u,
            "table": table_name,
            "report": report
        }

# ---------- TRINO：直接在应用层统计，类似 Oracle 的处理方式 ----------
def _is_trino_transient_conn_error(e: Exception) -> bool:
    msg = str(e).lower()
    # 覆盖你日志里的关键特征：JDBC_ERROR / connection attempt failed
    return (
        "jdbc_error" in msg
        or "connection attempt failed" in msg
        or "server disconnected" in msg
        or "connection refused" in msg
        or "connection reset" in msg
        or "timed out" in msg
    )

def _trino_scalar_with_retry(engine: Engine, sql_text, params: dict | None = None, *, retries: int = 2, sleep_sec: float = 0.3):
    """
    只给 Trino 盘查用的轻量重试：
    - 遇到疑似瞬时连接错误：关闭本次连接，重新开连接重试
    - 其它错误：直接抛出（避免掩盖真实 SQL/权限/表不存在等问题）
    """
    last = None
    for i in range(retries + 1):
        try:
            with engine.begin() as conn:
                return conn.execute(sql_text, params or {}).scalar()
        except Exception as e:
            last = e
            if not _is_trino_transient_conn_error(e) or i == retries:
                raise
            time.sleep(sleep_sec * (i + 1))
    raise last

def _audit_trino_direct(engine: Engine, catalog: str, schema: str, table: str, catalog_type: str = None):
    """
    Trino 版数据盘查：不使用存储过程，直接应用层统计。
    - 统计 NULL 值
    - 对字符串类型字段，额外统计空字符串（针对不同 catalog 类型适配）
    """
    # 检测 catalog 类型，用于适配不同的 SQL 语法
    # 优先使用传入的 catalog_type，否则从 catalog 名称推断
    if not catalog_type:
        catalog_type = catalog.lower()
    else:
        catalog_type = catalog_type.lower()
        
    print(f"[DEBUG] Trino 数据盘查 - catalog: {catalog}, 使用的 catalog_type: {catalog_type}")
    
    with engine.begin() as conn:
        # 1) 总行数
        total_sql = text(f'SELECT COUNT(*) FROM {catalog}.{schema}.{table}')
        total = _trino_scalar_with_retry(engine, total_sql) or 0

        # 2) 列信息 - 对于MSSQL，参考正常MSSQL的实现方式
        if catalog_type in ('mssql', 'sqlserver'):
            return _audit_trino_mssql_like(engine, catalog, schema, table, total)
        
        # 其他catalog类型的通用处理
        # 根据 catalog 类型确定字段名引号策略
        def quote_column(col_name: str) -> str:
            """根据 catalog 类型为字段名添加合适的引号"""
            if catalog_type in ('postgresql', 'postgres'):
                return f'"{col_name}"'
            elif catalog_type in ('mysql', 'mariadb'):
                return f'`{col_name}`'
            elif catalog_type in ('oracle'):
                return f'"{col_name}"'
            else:
                return col_name

        cols_sql = text(f"""
            SELECT column_name, data_type
            FROM {catalog}.information_schema.columns
            WHERE table_schema = :schema AND table_name = :table
            ORDER BY ordinal_position
        """)
        cols = conn.execute(cols_sql, {"schema": schema, "table": table}).fetchall()

        report = []
        for col_name, data_type in cols:
            print(f"[DEBUG] 处理字段: {col_name}, 类型: {data_type}")
            
            # 判断数据类型
            data_type_lower = data_type.lower()
            is_array = 'array(' in data_type_lower
            is_string = any(t in data_type_lower for t in ['char', 'text', 'varchar'])
            
            # 为字段名添加合适的引号
            quoted_col_name = quote_column(col_name)
            
            # 3) NULL 数
            null_sql = text(f'''
                SELECT COUNT(*) FROM {catalog}.{schema}.{table}
                WHERE {quoted_col_name} IS NULL
            ''')
            
            try:
                null_count = _trino_scalar_with_retry(engine, null_sql) or 0
            except Exception as e:
                print(f"[WARN] Trino 字段 {col_name} NULL 检查失败，跳过: {e}")
                null_count = 0

            # 4) 空字符串数
            empty_count = 0
            
            # 数组类型字段的特殊处理
            if is_array:
                try:
                    empty_sql = text(f'''
                        SELECT COUNT(*) FROM {catalog}.{schema}.{table}
                        WHERE {quoted_col_name} IS NOT NULL 
                        AND (cardinality({quoted_col_name}) = 0)
                    ''')
                    empty_count = _trino_scalar_with_retry(engine, empty_sql) or 0
                except Exception as e:
                    print(f"[WARN] Trino 数组字段 {col_name} 空数组检查失败，跳过: {e}")
                    empty_count = 0
            
            # 普通字符串类型字段的处理
            elif is_string:
                try:
                    if catalog_type in ('mysql', 'mariadb'):
                        empty_sql = text(f'''
                            SELECT COUNT(*) FROM {catalog}.{schema}.{table}
                            WHERE {quoted_col_name} IS NOT NULL AND TRIM({quoted_col_name}) = ''
                        ''')
                    elif catalog_type in ('postgresql', 'postgres'):
                        empty_sql = text(f'''
                            SELECT COUNT(*) FROM {catalog}.{schema}.{table}
                            WHERE {quoted_col_name} IS NOT NULL AND length(trim({quoted_col_name})) = 0
                        ''')
                    elif catalog_type in ('oracle'):
                        empty_sql = text(f'''
                            SELECT COUNT(*) FROM {catalog}.{schema}.{table}
                            WHERE {quoted_col_name} IS NOT NULL AND LENGTH(TRIM({quoted_col_name})) = 0
                        ''')
                    else:
                        empty_sql = text(f'''
                            SELECT COUNT(*) FROM {catalog}.{schema}.{table}
                            WHERE {quoted_col_name} = ''
                        ''')
                    
                    empty_count = _trino_scalar_with_retry(engine, empty_sql) or 0
                    
                except Exception as e:
                    print(f"[WARN] Trino 字段 {col_name} 空字符串检查失败，跳过: {e}")
                    empty_count = 0

            missing = int(null_count) + int(empty_count)
            pct = 0.0 if total == 0 else round(100.0 * missing / int(total), 2)

            report.append({
                "column_name": col_name,
                "data_type": data_type,
                "total_rows": int(total),
                "null_count": int(null_count),
                "empty_str_count": int(empty_count),
                "missing_count": int(missing),
                "missing_pct": float(pct),
            })

        report.sort(key=lambda x: (-x["missing_pct"], x["column_name"] or ""))

        return {
            "db_type": "trino",
            "database": catalog,
            "schema": schema,
            "table": table,
            "report": report
        }


def _audit_trino_mssql_like(engine: Engine, catalog: str, schema: str, table: str, total: int):
    """
    专门针对Trino MSSQL catalog的数据盘查实现
    参考正常MSSQL存储过程的逻辑，使用动态SQL和CASE WHEN的方式
    """
    print(f"[DEBUG] 使用MSSQL专用盘查逻辑 - catalog: {catalog}, schema: {schema}, table: {table}")
    
    with engine.begin() as conn:
        # 首先验证数据的真实情况
        print(f"[DEBUG] 验证表数据 - 总行数: {total}")
        
        # 直接查看每个字段的实际数据内容
        cols_sql = text(f"""
            SELECT column_name, data_type
            FROM {catalog}.information_schema.columns
            WHERE table_schema = :schema AND table_name = :table
            ORDER BY ordinal_position
        """)
        cols_preview = conn.execute(cols_sql, {"schema": schema, "table": table}).fetchall()
        
        for col_name, _ in cols_preview:
            try:
                # 直接查看字段的实际值
                preview_sql = text(f"SELECT [{col_name}] FROM {catalog}.{schema}.{table} LIMIT 5")
                values = conn.execute(preview_sql).fetchall()
                print(f"[DEBUG] 字段 {col_name} 实际值示例: {[row[0] for row in values]}")
            except Exception as e:
                print(f"[DEBUG] 无法获取字段 {col_name} 的值: {e}")
        
        # 获取字段列表 - 使用information_schema
        cols_sql = text(f"""
            SELECT column_name, data_type
            FROM {catalog}.information_schema.columns
            WHERE table_schema = :schema AND table_name = :table
            ORDER BY ordinal_position
        """)
        cols = conn.execute(cols_sql, {"schema": schema, "table": table}).fetchall()

        report = []
        for col_name, data_type in cols:
            print(f"[DEBUG] 处理字段: {col_name}, 类型: {data_type}")
            
            # 判断是否为字符串类型（参考MSSQL存储过程的逻辑）
            data_type_lower = data_type.lower()
            is_string_type = any(t in data_type_lower for t in ['char', 'nchar', 'varchar', 'nvarchar', 'text', 'ntext'])
            
            # 使用方括号引用字段名（MSSQL风格）
            quoted_col_name = f'[{col_name}]'
            
            # 使用最基本的方式检查NULL值
            print(f"[DEBUG] 使用基础方式检查字段 {col_name}")
            
            # 针对数组类型的NULL检查 - 检查数组元素是否为NULL
            null_count = 0
            
            try:
                if 'integer' in data_type_lower:
                    # 对于整数数组，检查数组第一个元素是否为NULL
                    null_sql = text(f'''
                        SELECT COUNT(*) 
                        FROM {catalog}.{schema}.{table}
                        WHERE {quoted_col_name} IS NOT NULL 
                        AND cardinality({quoted_col_name}) > 0 
                        AND {quoted_col_name}[1] IS NULL
                    ''')
                else:
                    # 对于字符串数组，检查数组第一个元素是否为NULL
                    null_sql = text(f'''
                        SELECT COUNT(*) 
                        FROM {catalog}.{schema}.{table}
                        WHERE {quoted_col_name} IS NOT NULL 
                        AND cardinality({quoted_col_name}) > 0 
                        AND {quoted_col_name}[1] IS NULL
                    ''')
                
                null_count = conn.execute(null_sql).scalar() or 0
                print(f"[DEBUG] 字段 {col_name} 数组元素NULL检查: {null_count}")
                
            except Exception as e:
                print(f"[DEBUG] 字段 {col_name} 数组元素NULL检查失败: {e}")
                null_count = 0
            
            print(f"[DEBUG] 字段 {col_name} 最终NULL计数: {null_count}")

            # 对于字符串字段，检查空字符串和空格
            empty_count = 0
            if is_string_type:
                print(f"[DEBUG] 字段 {col_name} 是字符串类型，检查空字符串和空格")
                
                # 策略1: 检查数组第一个元素是否为空字符串
                try:
                    empty_string_sql = text(f'''
                        SELECT COUNT(*) 
                        FROM {catalog}.{schema}.{table}
                        WHERE {quoted_col_name} IS NOT NULL 
                        AND cardinality({quoted_col_name}) > 0 
                        AND {quoted_col_name}[1] = ''
                    ''')
                    empty_string_count = conn.execute(empty_string_sql).scalar() or 0
                    print(f"[DEBUG] 字段 {col_name} 空字符串检查: {empty_string_count}")
                    empty_count += empty_string_count
                except Exception as e:
                    print(f"[DEBUG] 字段 {col_name} 空字符串检查失败: {e}")
                
                # 策略2: 检查数组第一个元素是否为空格（TRIM后为空）
                try:
                    trim_empty_sql = text(f'''
                        SELECT COUNT(*) 
                        FROM {catalog}.{schema}.{table}
                        WHERE {quoted_col_name} IS NOT NULL 
                        AND cardinality({quoted_col_name}) > 0 
                        AND {quoted_col_name}[1] IS NOT NULL
                        AND trim({quoted_col_name}[1]) = ''
                    ''')
                    trim_empty_count = conn.execute(trim_empty_sql).scalar() or 0
                    print(f"[DEBUG] 字段 {col_name} 空格/空白检查: {trim_empty_count}")
                    empty_count += trim_empty_count
                except Exception as e:
                    print(f"[DEBUG] 字段 {col_name} 空格检查失败: {e}")
                    
                print(f"[DEBUG] 字段 {col_name} 最终空字符串计数: {empty_count}")

            missing = int(null_count) + int(empty_count)
            pct = 0.0 if total == 0 else round(100.0 * missing / int(total), 2)

            report.append({
                "column_name": col_name,
                "data_type": data_type,
                "total_rows": int(total),
                "null_count": int(null_count),
                "empty_str_count": int(empty_count),
                "missing_count": int(missing),
                "missing_pct": float(pct),
            })

        report.sort(key=lambda x: (-x["missing_pct"], x["column_name"] or ""))

        return {
            "db_type": "trino",
            "database": catalog,
            "schema": schema,
            "table": table,
            "report": report
        }

# ---------- SQLite：读取"伪 SQL 文件"，在应用层循环执行 ----------
def _handle_sqlite_audit(engine: Engine, table: str):
    """按 data_audit_sqlite.txt 的模板逐列统计，返回统一 JSON。"""

    # 读取模板 SQL（从数据库或文件）
    file_name = _locate_sql_file("sqlite")
    raw = prompt_manager.get_prompt(file_name)
    if not raw:
        raise FileNotFoundError(f"未找到 sqlite 的提示词内容")
    parts = [s.strip() for s in re.split(_SPLIT_PATTERN, raw) if s.strip()]
    if len(parts) < 4:
        raise Exception("sqlite 模板 SQL 不完整（需要 total / pragma / null / empty 四段）")

    sql_total_tpl, sql_pragma_tpl, sql_null_tpl, sql_empty_tpl = parts[:4]

    # 去掉每段前面的注释行，避免 SQLAlchemy 误判"无结果集"
    def strip_leading_comments(sql_chunk: str) -> str:
        lines = sql_chunk.splitlines()
        cleaned = []
        for ln in lines:
            # 去掉以 -- 开头的注释行
            if ln.lstrip().startswith("--"):
                continue
            cleaned.append(ln)
        return "\n".join(cleaned).strip()

    sql_total_tpl = strip_leading_comments(sql_total_tpl)
    sql_pragma_tpl = strip_leading_comments(sql_pragma_tpl)
    sql_null_tpl = strip_leading_comments(sql_null_tpl)
    sql_empty_tpl = strip_leading_comments(sql_empty_tpl)

    with engine.begin() as conn:
        # 1. 总行数
        total_sql = sql_total_tpl.format(table_name=table)
        total = conn.execute(text(total_sql)).scalar() or 0

        # 2. 列信息
        pragma_sql = sql_pragma_tpl.format(table_name=table)
        cols = conn.execute(text(pragma_sql)).fetchall()

        report = []
        for c in cols:
            # PRAGMA table_info 返回 (cid, name, type, notnull, dflt_value, pk)
            col_name = c[1]
            col_type = (c[2] or "").upper()

            # 3. NULL 数
            null_sql = sql_null_tpl.format(table_name=table, column_name=col_name)
            null_count = conn.execute(text(null_sql)).scalar() or 0

            # 4. 空字符串（仅字符型）
            if any(k in col_type for k in ("CHAR", "CLOB", "TEXT", "VARCHAR", "NVARCHAR", "NCHAR")):
                empty_sql = sql_empty_tpl.format(table_name=table, column_name=col_name)
                empty_count = conn.execute(text(empty_sql)).scalar() or 0
            else:
                empty_count = 0

            missing = int(null_count) + int(empty_count)
            pct = 0.0 if total == 0 else round(100.0 * missing / int(total), 2)

            report.append({
                "column_name": col_name,
                "data_type": col_type,
                "total_rows": int(total),
                "null_count": int(null_count),
                "empty_str_count": int(empty_count),
                "missing_count": int(missing),
                "missing_pct": float(pct),
            })

        report.sort(key=lambda x: (-x["missing_pct"], x["column_name"] or ""))

        return {
            "db_type": "sqlite",
            "database": (engine.url.database or ":memory:"),
            "schema": None,
            "table": table,
            "report": report
        }

# 资源接口注册
api.add_resource(DataAuditAPI, "/data_audit")