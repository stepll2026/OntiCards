"""
@File: database_schema_extractor.py
@Description: 抽取数据库中的所有表结构
@Author: 韩小豪 849631113@qq.com
@Create: 2025-09-18 13:33
"""

import copy as _copy
import hashlib
import json
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Dict, Set, List, Tuple
from typing import Optional, Any

import flask_login
from flask import Blueprint, request, current_app
from flask_login import login_required
from flask_restful import Resource, Api
from sqlalchemy import create_engine, inspect, text, quoted_name, make_url, UUID, func, distinct
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError, OperationalError, InterfaceError, NoSuchTableError, NoSuchModuleError

# 注意：generate_datacards_for_schema 是延迟导入，避免循环依赖
# from controllers.datacard.datacard_generator import generate_datacards_for_schema
# 导入数据盘查工具方法
from controllers.datasource.filedfill.fill_field_by_llm import enrich_table_before_insert, check_tables_health_batch
from controllers.weaviate_db_tool.weaviate_api import batch_delete_by_uuids
from extensions.ext_database import db
from models.datacards_datasource import DataCardDataSource
from models.datasource_infos import DatasourceInfo
from models.user_datasource_schema import UserDatasourceSchema
from models.users import User

# 导入加密模块
from core.connect_info_encryptor import encrypt_connect_info, decrypt_connect_info, is_encrypted, get_connect_info_hash

# === 注册 Flask Blueprint 和 API ===
extract_schema_from_db = Blueprint('extract_schema_from_db', __name__)
api = Api(extract_schema_from_db)

# Oracle thick模式初始化标志
_oracle_thick_initialized = False

def _init_oracle_thick_mode():
    """
    初始化Oracle thick模式（仅在需要时调用一次）
    用于支持Oracle 11g等旧版本数据库
    """
    global _oracle_thick_initialized
    if _oracle_thick_initialized:
        return

    try:
        import oracledb
        # 尝试初始化thick模式
        # 在Docker环境中，Instant Client位于 /opt/oracle/instantclient_21_14
        # 在本地Windows环境中，可能已经安装了Oracle客户端
        try:
            oracledb.init_oracle_client()
            _oracle_thick_initialized = True
            print("[INFO] Oracle thick模式已启用（支持Oracle 11g+）")
        except Exception as e:
            # thick模式初始化失败（可能找不到Instant Client）
            # 这是正常的，thin模式会继续工作（如果数据库版本>=12.1）
            print(f"[WARNING] Oracle thick模式初始化失败（将使用thin模式）: {e}")
    except ImportError:
        # oracledb未安装，跳过
        pass


# OceanBase 方言注册标志
_oceanbase_dialect_registered = False


def _register_oceanbase_dialect():
    """
    【OceanBase 适配】注册 OceanBase 兼容的 MySQL dialect reflection 解析器。

    问题背景：
    OceanBase MySQL 模式在 SHOW CREATE TABLE 输出中，会在 KEY 后面追加 OB 专属的
    `BLOCK_SIZE 16384 LOCAL` 语法（用于控制 OB 的存储属性）。标准 SQLAlchemy MySQL
    方言的 _re_key 正则不识别这种扩展，会发出 SAWarning:
        Unknown schema content: '  KEY `xxx` (`xxx`) BLOCK_SIZE 16384 LOCAL'

    影响范围：
    仅 inspector.get_table_comment() 内部在解析 SHOW CREATE TABLE 输出时会触发警告。
    ⚠️ 但表/列/主键/外键/索引的识别均通过 information_schema 查询，与该警告无关，
    这些识别完全正常，不受影响。

    解决策略：
    Monkey-patch MySQLTableDefinitionParser._prep_regexes，在正则编译后覆写
    `_re_key` 与 `_re_fk_constraint` 两个字段：
    - _re_key：扩展 BLOCK_SIZE/LOCAL 语法支持
    - _re_fk_constraint：兼容 OB 可能加上的额外选项

    兼容性：
    - dialect.name 仍为 "mysql"，所有 OB 走 MySQL 路径的逻辑无需改动
    - 其他 7 种数据库（PG/Oracle/MSSQL/SQLite/Trino/KingBase/MySQL）的反射路径
      不受影响（_prep_regexes 是 MySQL 方言私有的）
    """
    global _oceanbase_dialect_registered
    if _oceanbase_dialect_registered:
        return

    try:
        import re as _re
        from sqlalchemy.dialects.mysql import reflection as _mysql_reflection
        from sqlalchemy.dialects.mysql.reflection import (
            MySQLTableDefinitionParser,
            _re_compile,
        )

        # 保存原始方法（便于将来可能的回退/调试）
        _ORIGINAL_PREP_REGEXES = MySQLTableDefinitionParser._prep_regexes

        # OceanBase 兼容的 _re_key 正则：
        # - 保持原生 KEY_BLOCK_SIZE 支持
        # - 新增 BLOCK_SIZE ... LOCAL 语法（OB 专属）
        _OB_RE_KEY_PATTERN = (
            r"  "
            r"(?:(?P<type>\S+) )?KEY"
            r"(?: +%(iq)s(?P<name>(?:%(esc_fq)s|[^%(fq)s])+)%(fq)s)?"
            r"(?: +USING +(?P<using_pre>\S+))?"
            r" +\((?P<columns>.+?)\)"
            r"(?: +USING +(?P<using_post>\S+))?"
            # 兼容 KEY_BLOCK_SIZE 与 BLOCK_SIZE，并支持 LOCAL 修饰符
            r"(?: +(?:KEY_)?BLOCK_SIZE *[ =]? *(?P<keyblock>\S+) *(?:LOCAL)?)?"
            r"(?: +WITH PARSER +(?P<parser>\S+))?"
            r"(?: +COMMENT +(?P<comment>(\x27\x27|\x27([^\x27])*?\x27)+))?"
            r"(?: +/\*(?P<version_sql>.+)\*/ *)?"
            r",?$"
        )

        def _patched_prep_regexes(self):
            """先调用原方法，再用 OceanBase 兼容的 _re_key 覆写"""
            _ORIGINAL_PREP_REGEXES(self)

            # 复用与 _prep_regexes 同样的 quotes 字典（保持引用符一致）
            _final = self.preparer.final_quote
            quotes = {
                "iq": _re.escape(self.preparer.initial_quote),
                "fq": _re.escape(_final),
                "esc_fq": _re.escape(self.preparer._escape_identifier(_final)),
            }
            self._re_key = _re_compile(_OB_RE_KEY_PATTERN % quotes)

        # Monkey-patch
        MySQLTableDefinitionParser._prep_regexes = _patched_prep_regexes

        # 由于 _tabledef_parser 是 memoized_property，已有的 dialect 实例可能缓存了
        # 旧的 parser。这些 parser 的 _re_key 已经编译完成，patch 不会生效。
        # SQLAlchemy 没有公开的 cache invalidate API，所以新连接都会生成新 parser（生效）。
        # 若想强制重新生成，可重启进程或创建新 Engine。

        _oceanbase_dialect_registered = True
    except Exception as e:
        # 失败也不影响主流程（仍可正常连接与操作，仅 SAWarning 会出现）
        print(f"[WARNING] OceanBase 方言注册失败（SAWarning 仍可能出现但不影响功能）: {e}")


# 立即执行一次注册（模块被 import 时就完成 monkey-patch）
# 注意：调用必须放在 _register_*_dialect 函数定义之后，否则会抛 NameError。
# OceanBase 函数定义在第 73-160 行，定义完后立即注册一次。
_register_oceanbase_dialect()


# ========== KingBase 方言注册 ==========
# KingBase 方言注册标志
_kingbase_dialect_registered = False


def _register_kingbase_dialect():
    """
    注册 KingBase SQLAlchemy 方言
    KingBase 兼容 PostgreSQL 协议，需要将 ksycopg2 驱动注册到 kingbase 方言
    """
    global _kingbase_dialect_registered
    if _kingbase_dialect_registered:
        return

    try:
        from sqlalchemy.dialects import registry
        from sqlalchemy.dialects.postgresql import base as pg_base

        # 尝试导入 ksycopg2 的 SQLAlchemy 方言
        try:
            import ksycopg2
            from ksycopg2 import dialect as ksycopg2_dialect
            # 注册 kingbase 方言，使用 ksycopg2 方言
            registry.register("kingbase.ksycopg2", "ksycopg2", "dialect")
        except ImportError:
            pass

        # 尝试注册 kingbase 为 postgresql 的别名（兜底方案）
        try:
            registry.register("kingbase", "sqlalchemy.dialects", "postgresql")
        except Exception:
            pass

        _kingbase_dialect_registered = True
        print("[DEBUG] KingBase 方言注册完成")
    except Exception as e:
        print(f"[WARNING] KingBase 方言注册失败: {e}")


# ========== 达梦 DM 方言注册 ==========
# 达梦 DM 方言注册标志（避免重复注册）
_dm_dialect_registered = False


def _ensure_dm_dialect():
    """
    按需注册达梦 DM SQLAlchemy 方言（延迟注册，仅在实际创建达梦引擎时才调用）。

    达梦数据库使用 dmPython 驱动 + dmSQLAlchemy 方言包，dmSQLAlchemy 会在被导入时
    自动调用 registry.register("dm", "dm", "dialect")，从而让 SQLAlchemy
    能够识别 dm+dmPython:// 的连接 URL。

    注册成功后设置 _dm_dialect_registered = True，后续所有达梦连接不再重复尝试注册。
    如果 dmSQLAlchemy 未安装，则打印警告（不影响其他数据库），且不再重试。
    """
    global _dm_dialect_registered
    if _dm_dialect_registered:  # 已注册成功，直接返回
        return

    # _dm_dialect_registered 为 False 时，有两种情况：
    # 1. 还未尝试注册（首次调用）
    # 2. 上次尝试注册失败了（_loaded = True 但 _registered = False）
    # 用负数表示"已尝试但失败，不再重试"（避免每次创建引擎都打印重复警告）
    if _dm_dialect_registered is False:
        # 首次尝试：设置为 None（表示正在尝试中）
        _dm_dialect_registered = None

    try:
        # dmSQLAlchemy 2.0.x 包在被 import 时会自动完成 dialect 注册
        import dmSQLAlchemy  # noqa: F401
        _dm_dialect_registered = True  # 注册成功，标记为 True
        print("[DEBUG] 达梦 DM 方言注册完成（dmSQLAlchemy）")
    except ImportError as e:
        # 驱动未安装时：将标记设为负数（已尝试但失败），不再重试
        _dm_dialect_registered = -1
        print(f"[WARNING] 达梦 DM 方言注册失败（dmSQLAlchemy 未安装）: {e}")
        print(f"[WARNING] 如需支持达梦 DM，请执行: pip install dmSQLAlchemy==2.0.17")
    except Exception as e:
        _dm_dialect_registered = -1
        print(f"[WARNING] 达梦 DM 方言注册异常: {e}")


# ========== 请求状态管理（内存缓存） ==========
class RequestStatusManager:
    """
    管理请求状态的单例类
    使用内存字典存储请求状态，支持并发安全访问
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._status_dict: Dict[str, str] = {}
                    cls._instance._dict_lock = threading.Lock()
        return cls._instance

    def set_status(self, request_id: str, status: str):
        """设置请求状态：processing, completed, failed, cancelled"""
        with self._dict_lock:
            self._status_dict[request_id] = status

    def get_status(self, request_id: str) -> str:
        """获取请求状态"""
        with self._dict_lock:
            return self._status_dict.get(request_id, "unknown")

    def is_cancelled(self, request_id: str) -> bool:
        """检查请求是否已被取消"""
        status = self.get_status(request_id)
        result = status == "cancelled"
        print(f"[DEBUG] RequestStatusManager.is_cancelled: request_id={request_id}, status={status}, result={result}")
        return result

    def remove_status(self, request_id: str):
        """删除请求状态"""
        with self._dict_lock:
            self._status_dict.pop(request_id, None)

    def cleanup_old_requests(self, max_age_seconds: int = 3600):
        """清理过期的请求状态（可选，定期调用）"""
        # 简化版本：直接清空所有已完成/失败/取消的请求
        with self._dict_lock:
            to_remove = [
                rid for rid, status in self._status_dict.items()
                if status in ("completed", "failed", "cancelled")
            ]
            for rid in to_remove:
                self._status_dict.pop(rid, None)

# 全局请求状态管理器实例
request_status_manager = RequestStatusManager()

# 数据源连接的全局异常处理和捕获
class AppDBConnectError(Exception):
    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg
        super().__init__(msg)

# 请求已取消异常
class RequestCancelledException(Exception):
    """当检测到请求已被取消时抛出此异常"""
    pass


# 1) 程序连接数据库时使用的默认驱动映射：用户无需选择 driver
DEFAULT_DRIVERS = {
    "mysql": "pymysql",
    "postgresql": "psycopg",
    "mssql": "pyodbc",
    "oracle": "oracledb",  # 使用 python-oracledb (thin模式，无需Oracle客户端库)
    "sqlite": None,  # sqlite 不需要 driver
    "trino": None,  # Trino 使用 sqlalchemy-trino，方言名称直接是 trino
    # 人大金仓（KingBase）- 使用 ksycopg2 驱动
    "kingbase": "ksycopg2",
    # OceanBase MySQL 模式租户：复用 pymysql（OB 官方推荐 PyMySQL，OB-MySQL 模式协议层
    # 完全兼容 MySQL 5.7/8.0，不需要专属驱动）。注意：OB-Oracle 模式必须用 oracledb
    # （cx_Oracle 系），与本条目无关；本系统当前仅支持 OB-MySQL 模式，OB-Oracle
    # 模式会在 get_db_engine 的模式探测中被拒绝。
    "oceanbase": "pymysql",
    # 达梦数据库 DM：使用官方 dmPython 驱动（依赖达梦客户端动态库 dmPython.cp*-*.so/.pyd），
    # 配合 dmSQLAlchemy 提供 SQLAlchemy 方言注册
    "dm": "dmPython",
}

# 2) 字段别名映射：把前端各种命名风格统一成内部键
ALIASES = {
    "db_type": ["dbType", "type", "db", "dialect"],
    "username": ["user", "userName", "name", "uid"],
    "password": ["pass", "pwd"],
    "host": ["server", "hostname", "address"],
    "port": ["serverPort"],
    "database": ["db", "dbname", "databaseName"],
    "service_name": ["serviceName", "service", "svc"],
    "sid": ["SID"],
    "dsn": ["DSN", "dsnName"],
    "sqlite_memory": ["memory", "inMemory"],
    "sqlite_path": ["path", "file", "filepath"],
    "catalog": ["Catalog"],  # Trino catalog
    "schema": ["Schema"],  # 已有的 schema，增加别名
    "target_schema": ["targetSchema", "TargetSchema"],  # Oracle 目标 schema（用户有权限的其他 schema）
    "http_scheme": ["httpScheme", "protocol"],  # Trino HTTP协议（程序自动选择，用户可选手动指定）
    # 允许把其余未识别项透传到 query
}

# 3) 各数据库必填项规则（最小可用参数集）
REQUIRED_RULES = {
    "mysql": [["username", "password", "host", "port", "database"]],
    "postgresql": [["username", "password", "host", "port", "database"]],
    # mssql 支持两种：DSN 方式 或 host 方式（二选一规则用两个列表表示）
    "mssql": [["username", "password", "dsn", "database"],
              ["username", "password", "host", "port", "database"]],
    # oracle: service_name 或 sid 二选一
    "oracle": [["username", "password", "host", "port", "service_name"],
               ["username", "password", "host", "port", "sid"]],
    # sqlite: memory 或 path 二选一
    "sqlite": [["sqlite_memory"], ["sqlite_path"]],
    # trino: 需要 host, port, catalog, schema, username（password 可选，支持无密码认证）
    "trino": [["username", "host", "port", "catalog", "schema"]],
    # kingbase: 与 postgresql 相同，schema 选填，默认 public
    "kingbase": [["username", "password", "host", "port", "database"]],
    # OceanBase MySQL 模式租户：与 MySQL 同样的连接参数集
    # 注意：username 字段在 OB-MySQL 模式下应填写「用户名@租户名」格式（如 root@mysql001）
    "oceanbase": [["username", "password", "host", "port", "database"]],
    # 达梦 DM：达梦没有 database/service_name/sid 的概念，schema 默认 = 用户名大写。
    # 用户只需要：username / password / host / port（可选 target_schema 切换其他 schema）。
    "dm": [["username", "password", "host", "port"]],
}

# 清洗需要序列化的数据
def _json_safe(obj):
    if isinstance(obj, Decimal):
        # 也可以 return str(obj)，看你需要
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except Exception:
            return obj.hex()
    # 兼容 SQLAlchemy Row / namedtuple
    if hasattr(obj, "_asdict"):
        return obj._asdict()
    # 兜底：把未知对象转成字符串，避免抛 TypeError
    return str(obj)

def _deep_json_safe(data):
    """
    深度清洗，确保 data 可被 json.dumps 序列化。
    """
    import json
    # 先序列化再反序列化，强制把所有“非常规对象”变成基础类型
    return json.loads(json.dumps(data, default=_json_safe))

def _canonicalize_key(k: str) -> str:
    """将任意风格的键名映射到规范键；不存在则原样返回"""
    low = k.strip()
    for canonical, alts in ALIASES.items():
        if low == canonical or low in alts:
            return canonical
    return low


def _normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """1) 统一键名；2) 去空格；3) 端口转 int；4) 处理布尔和空字符串；5) 处理host中的协议前缀"""
    norm: Dict[str, Any] = {}
    # 先检查原始payload中是否已经有http_scheme相关的字段
    has_http_scheme = False
    for k in (payload or {}).keys():
        ck = _canonicalize_key(str(k))
        if ck in ("http_scheme", "httpScheme", "protocol"):
            has_http_scheme = True
            break

    for k, v in (payload or {}).items():
        ck = _canonicalize_key(str(k))
        # 字符串清理
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                v = None
        # 处理host字段：如果包含http://或https://前缀，提取协议并移除前缀
        if ck == "host" and isinstance(v, str) and v:
            # 移除协议前缀（http:// 或 https://）
            if v.startswith("https://"):
                v = v[8:]  # 移除 "https://"
                # 如果用户没有明确指定http_scheme，从host中提取并设置
                if not has_http_scheme:
                    norm["http_scheme"] = "https"
            elif v.startswith("http://"):
                v = v[7:]  # 移除 "http://"
                # 如果用户没有明确指定http_scheme，从host中提取并设置
                if not has_http_scheme:
                    norm["http_scheme"] = "http"
            # 移除尾部斜杠（如果有）
            v = v.rstrip("/")
        # 端口转 int（需要特别处理空字符串和 None 的情况）
        if ck == "port":
            if v is None or v == "":
                v = None
            else:
                try:
                    v = int(v)
                except (ValueError, TypeError):
                    raise ValueError("端口(port)需要是整数")
        # 布尔 normalize
        if ck in ("sqlite_memory",) and isinstance(v, str):
            v = v.lower() in ("1", "true", "yes", "on")
        norm[ck] = v
    return norm

def _pick_db_type(payload: Dict[str, Any]) -> str:
    db_type = str(payload.get("db_type") or "").lower()
    if not db_type:
        raise ValueError("缺少 db_type（数据库类型）")
    if db_type not in DEFAULT_DRIVERS:
        raise ValueError(f"不支持的数据库类型：{db_type}")
    return db_type

# mssql自动选择 SQL Server ODBC 驱动（17/18 优先）
def _auto_pick_mssql_driver() -> str | None:
    """
    自动选择本机可用的 SQL Server ODBC 驱动。
    优先 18，再 17，最后退到系统自带的 'SQL Server'（不推荐但可用）。
    """
    try:
        import pyodbc
        installed = set(pyodbc.drivers())  # 例如 {'ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server'}
        for name in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server"):
            if name in installed:
                return name
    except Exception:
        pass
    return None

def _check_required(db_type: str, data: Dict[str, Any]) -> None:
    """满足其中一个规则即可；否则抛出详细错误"""
    rules = REQUIRED_RULES[db_type]
    for rule in rules:
        if all(data.get(x) not in (None, "") for x in rule):
            return
    # 如果没有任何一条规则被满足，给出提示
    variants = ["、".join(rule) for rule in rules]
    hint = " 或 ".join([f"[{v}]" for v in variants])
    raise ValueError(f"{db_type} 连接缺少必填项，请至少满足其一：{hint}")

# 获取原文连接字符串
def _to_raw_conn_str(url_or_str) -> str:
    # URL.__str__ 会隐藏密码；必须显式 render_as_string(hide_password=False)
    if isinstance(url_or_str, URL):
        return url_or_str.render_as_string(hide_password=False)
    return str(url_or_str)

def build_db_url(
        db_type: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        *,
        oracle_service_name: Optional[str] = None,
        oracle_sid: Optional[str] = None,
        oracle_mode_sysdba: bool = False,
        sqlite_memory: bool = False,
        sqlite_path: Optional[str] = None,
        mssql_dsn: Optional[str] = None,
        trino_catalog: Optional[str] = None,
        trino_schema: Optional[str] = None,
) -> str | URL:
    driver = DEFAULT_DRIVERS.get(db_type)
    # KingBase：兼容 PostgreSQL 协议，使用 postgresql:// 前缀
    # 不指定具体驱动，让 SQLAlchemy 自动选择（支持 ksycopg2/psycopg 等）
    if db_type == "kingbase":
        drivername = "postgresql"
    else:
        drivername = f"{db_type}+{driver}" if driver else db_type
    query = dict(query or {})
    # SQLite
    if db_type == "sqlite":
        if sqlite_memory:
            return "sqlite:///:memory:"
        if sqlite_path:
            # 绝对路径推荐四斜杠
            return f"sqlite:///{sqlite_path}"
        return "sqlite://"

    # Oracle
    if db_type == "oracle":
        if oracle_service_name:
            query.setdefault("service_name", oracle_service_name)
        if oracle_sid:
            query.setdefault("sid", oracle_sid)
        if oracle_mode_sysdba:
            query.setdefault("mode", "SYSDBA")
        return URL.create(
            drivername=drivername,
            username=username,
            password=password,
            host=host,
            port=port,
            database=None,
            query=query or None
        )

    # SQL Server DSN
    if db_type == "mssql" and mssql_dsn:
        return URL.create(
            drivername=drivername,
            username=username,
            password=password,
            host=mssql_dsn,  # DSN 放在 host 位
            database=database,
            query=query or None
        )

    # Trino
    if db_type == "trino":
        print(f"[DEBUG] Trino 连接参数 - catalog: {trino_catalog}, schema: {trino_schema}")
        print(f"[DEBUG] Trino 连接参数 - username: {username}, password: {'<有值>' if password else '<空>'}")
        print(f"[DEBUG] Trino 连接参数 - host: {host}, port: {port}")
        print(f"[DEBUG] Trino 连接参数 - query: {query}")

        # Trino 连接字符串格式: trino://username:password@host:port/catalog/schema
        # database 字段用于拼接 catalog/schema
        if trino_catalog and trino_schema:
            database = f"{trino_catalog}/{trino_schema}"
        elif trino_catalog:
            database = trino_catalog

        # Trino 通过 HTTP/HTTPS 协议连接，当使用密码认证时建议使用 HTTPS
        # 如果用户提供了 http_scheme，使用用户指定的值，否则根据是否有密码自动选择
        if "http_scheme" not in query:
            if password:
                query["http_scheme"] = "https"
            else:
                query["http_scheme"] = "http"

        print(f"[DEBUG] Trino 最终 database: {database}, http_scheme: {query.get('http_scheme')}")

        url = URL.create(
            drivername=drivername,
            username=username,
            password=password,
            host=host,
            port=port,
            database=database,
            query=query or None
        )
        print(f"[DEBUG] Trino 生成的连接 URL: {url}")
        return url

    # OceanBase MySQL 模式租户：协议层 100% 兼容 MySQL，必须显式走 mysql+pymysql 前缀
    # （不能写 oceanbase+pymysql，因为 SQLAlchemy 没注册这个方言）
    if db_type == "oceanbase":
        return URL.create(
            drivername=f"mysql+{driver}",   # 即 "mysql+pymysql"
            username=username,
            password=password,
            host=host,
            port=port,
            database=database,
            query=query or None
        )

    # 通用
    return URL.create(
        drivername=drivername,
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
        query=query or None
    )

# 拼接数据库连接字符串
def build_db_url_from_json(payload: Dict[str, Any]) -> str | URL:
    """
    前端 JSON -> 连接 URL
    1) 统一字段  2) 校验必填  3) 拼接 URL
    4) 未识别字段自动进 query（保留可扩展性）
    """
    print(f"[DEBUG] build_db_url_from_json 收到参数: {payload}")
    data = _normalize_payload(payload)
    db_type = _pick_db_type(data)
    print(f"[DEBUG] 归一化后数据: {data}")
    print(f"[DEBUG] 数据库类型: {db_type}")

    # 为 PostgreSQL、MSSQL 和 KingBase 设置 schema 的默认值（当 schema 为空时）
    if not data.get("schema"):
        if db_type == "postgresql" or db_type == "kingbase":
            data["schema"] = "public"
            print(f"[DEBUG] {db_type} schema 为空，使用默认值: public")
        elif db_type == "mssql":
            data["schema"] = "dbo"
            print(f"[DEBUG] MSSQL schema 为空，使用默认值: dbo")

    # 分离出内部已知字段，其余放入 query
    known_keys = {
        "db_type", "username", "password", "host", "port", "database",
        "service_name", "sid", "dsn", "sqlite_memory", "sqlite_path", "oracle_mode_sysdba", "schema", "connect_name",
        "catalog",  # Trino 的 catalog 参数
        "target_schema",  # Oracle 目标 schema（用户有权限的其他 schema）；达梦同样适用
        "request_id",  # 前端传来的请求标识，不应该作为数据库连接参数
        "table_names"  # 要抽取的表名列表，不应该作为数据库连接参数
    }
    # 注意：http_scheme 不在 known_keys 中，如果用户传递会自动进入 query，在 build_db_url 中会被检查
    query: Dict[str, Any] = {}
    for k, v in list(data.items()):
        if k not in known_keys and v is not None:
            query[k] = v  # 未知参数透传到 ?k=v

    # 仅对 mssql 的 DSN-less 连接自动补 driver
    if db_type == "mssql" and not data.get("dsn"):
        if "driver" not in query or not query["driver"]:
            picked = _auto_pick_mssql_driver()
            if picked:
                query["driver"] = picked
            # 若未能探测到已安装驱动，就保持不填，后续会在 get_db_engine 里给出友好错误

    # 仅对 MySQL/OceanBase MySQL 模式做兼容：schema 视作 database（如果没传 database）
    if db_type in ("mysql", "oceanbase") and not data.get("database") and data.get("schema"):
        data["database"] = data["schema"]

    # 必填校验
    _check_required(db_type, data)

    # 生成 URL
    return build_db_url(
        db_type=db_type,
        username=data.get("username"),
        password=data.get("password"),
        host=data.get("host"),
        port=data.get("port"),
        database=data.get("database"),
        query=query or None,
        oracle_service_name=data.get("service_name"),
        oracle_sid=data.get("sid"),
        oracle_mode_sysdba=bool(data.get("oracle_mode_sysdba")),
        sqlite_memory=bool(data.get("sqlite_memory")),
        sqlite_path=data.get("sqlite_path"),
        mssql_dsn=data.get("dsn"),
        trino_catalog=data.get("catalog"),
        trino_schema=data.get("schema"),
    )

def _get_database_version(engine):
    """获取数据库版本信息"""
    print("用户输入的 engine =", engine)
    try:
        with engine.connect() as conn:
            dialect_name = (engine.dialect.name or "").lower()

            if "mysql" in dialect_name:
                return conn.execute(text("SELECT VERSION()")).scalar()

            elif "postgres" in dialect_name:
                return conn.execute(text("SELECT version()")).scalar()

            elif "oracle" in dialect_name:
                # 只取 banner 列的第一行
                return conn.execute(text("SELECT banner FROM v$version WHERE rownum = 1")).scalar()

            elif "dm" in dialect_name or "dameng" in dialect_name:
                # 达梦数据库：查询 v$version 取 banner；某些版本可能没有 banner 列，退到 svr_version / 版本函数
                try:
                    banner = conn.execute(text("SELECT banner FROM v$version WHERE rownum = 1")).scalar()
                    if banner:
                        return banner
                except Exception:
                    pass
                try:
                    # 兜底方案：达梦内置 SF_GET_SERVER_VERSION() / SELECT * FROM V$VERSION LIMIT 1
                    return conn.execute(text("SELECT SF_GET_SERVER_VERSION() FROM DUAL")).scalar()
                except Exception:
                    return "达梦 DM (version unknown)"

            elif "mssql" in dialect_name:
                return conn.execute(text("SELECT @@VERSION")).scalar()

            elif "trino" in dialect_name:
                # Trino 环境下，直接查询 system.runtime.nodes 获取版本信息
                # 这是一个系统表，不依赖具体的 catalog
                try:
                    return conn.execute(text("SELECT node_version FROM system.runtime.nodes LIMIT 1")).scalar()
                except Exception:
                    # 如果系统表查询失败，返回一个通用的 Trino 标识
                    return "Trino (version unknown)"

            else:
                return f"unknown (dialect={dialect_name})"

    except Exception as e:
        return f"version_unknown: {e}"


def _should_quote(name: str, engine) -> bool:
    """
    判断是否需要对标识符加引号。

    核心原则：
    - Oracle：如果表名包含小写字母，需要加引号（因为可能是用引号创建的）
      * 如果表名全大写，不加引号（Oracle默认行为）
      * 如果表名包含小写字母，加引号（保持原样）
      * 如果包含特殊字符/空格，加引号
    - 其他数据库：沿用 SQLAlchemy 的判断逻辑
    """
    name_str = name if isinstance(name, str) else str(name)
    dialect = (engine.dialect.name or "").lower()

    # Oracle/达梦：根据表名格式决定是否加引号（达梦与 Oracle 兼容，引号规则一致）
    if dialect == "oracle" or dialect == "dm":
        # 如果包含特殊字符，必须加引号
        if any(not (c.isalnum() or c in "_$#") for c in name_str):
            return True
        # 如果包含小写字母，加引号（可能是用引号创建的表）
        if any(c.islower() for c in name_str):
            return True
        # 全大写，不加引号（默认行为）
        return False

    # ===== 非 Oracle，保持原有行为 =====
    prep = engine.dialect.identifier_preparer
    try:
        if hasattr(prep, "requires_quotes"):
            return prep.requires_quotes(name_str)
        if hasattr(prep, "_requires_quotes"):
            return prep._requires_quotes(name_str)
    except Exception:
        pass

    return not name_str.isupper() or any(not (c.isalnum() or c in "_$#") for c in name_str)



def _get_column_names_raw(engine, table_name, schema=None):
    """从数据库元数据字典获取列名，保持大小写原样"""
    dialect = engine.dialect.name.lower()
    if dialect == "oracle":
        schema = schema or engine.username.upper()
        sql = text("""
                   SELECT column_name
                   FROM all_tab_columns
                   WHERE table_name = :tname
                     AND owner = :owner
                   ORDER BY column_id
                   """)
        with engine.connect() as conn:
            # 先尝试使用大写表名（Oracle默认行为）
            rows = conn.execute(sql, {"tname": table_name.upper(), "owner": schema.upper()}).fetchall()
            # 如果没有结果且表名不是全大写，尝试使用原始表名（可能是带引号创建的）
            if not rows and table_name != table_name.upper():
                rows = conn.execute(sql, {"tname": table_name, "owner": schema.upper()}).fetchall()
        return [r[0] for r in rows]  # Oracle 默认返回全大写
    elif dialect == "dm":
        # 达梦兼容 Oracle 元数据视图，all_tab_columns 同名可用
        # 达梦默认情况下 owner 是模式名（用户名为大写，默认模式 = 用户名大写）
        schema = schema or engine.username.upper()
        sql = text("""
                   SELECT column_name
                   FROM all_tab_columns
                   WHERE table_name = :tname
                     AND owner = :owner
                   ORDER BY column_id
                   """)
        with engine.connect() as conn:
            # 达梦默认行为：表名大写存储
            rows = conn.execute(sql, {"tname": table_name.upper(), "owner": schema.upper()}).fetchall()
            # 兜底：如果没有结果且表名非全大写，尝试原始大小写
            if not rows and table_name != table_name.upper():
                rows = conn.execute(sql, {"tname": table_name, "owner": schema.upper()}).fetchall()
        return [r[0] for r in rows]
    elif dialect == "postgresql" or dialect == "kingbase":
        schema = schema or "public"
        sql = text("""
                   SELECT column_name
                   FROM information_schema.columns
                   WHERE table_name = :tname
                     AND table_schema = :schema
                   ORDER BY ordinal_position
                   """)
        with engine.connect() as conn:
            rows = conn.execute(sql, {"tname": table_name, "schema": schema}).fetchall()
        return [r[0] for r in rows]
    # MySQL / SQL Server 一般不会强制折叠，可以直接返回 inspector 的 name
    return None


def _get_columns_from_all_tab_columns(engine, table_name, schema=None):
    """
    达梦 DM: 从 ALL_TAB_COLUMNS 系统视图兜底获取列信息，
    解决 inspector.get_columns() 对视图反射失败的问题。
    """
    schema = schema or engine.username.upper()
    sql = text("""
        SELECT
            COLUMN_NAME,
            DATA_TYPE,
            DATA_LENGTH,
            DATA_PRECISION,
            DATA_SCALE,
            NULLABLE,
            DATA_DEFAULT,
            COLUMN_ID
        FROM ALL_TAB_COLUMNS
        WHERE TABLE_NAME = :tname
          AND OWNER = :owner
        ORDER BY COLUMN_ID
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"tname": table_name.upper(), "owner": schema.upper()}).fetchall()
        if not rows and table_name != table_name.upper():
            rows = conn.execute(sql, {"tname": table_name, "owner": schema.upper()}).fetchall()

    result = []
    for r in rows:
        col_name, data_type, data_length, data_precision, data_scale, nullable, data_default, column_id = r
        col_type = _build_column_type(data_type, data_length, data_precision, data_scale)
        result.append({
            "name": col_name,
            "type": col_type,
            "nullable": nullable == "Y",
            "default": str(data_default) if data_default is not None else None,
            "comment": "",
            "autoincrement": False,
        })
    return result


def _build_column_type(data_type, data_length, data_precision, data_scale):
    """根据达梦 ALL_TAB_COLUMNS 的字段构造 SQLAlchemy 类型对象"""
    from sqlalchemy import String, Integer, BigInteger, Float, Numeric, Text, DateTime, Time, LargeBinary

    dt = (data_type or "").upper()
    if dt in ("VARCHAR", "VARCHAR2", "CHAR", "NCHAR", "NVARCHAR", "NVARCHAR2"):
        return String(length=data_length or 255)
    elif dt in ("INTEGER", "INT", "SMALLINT", "TINYINT"):
        return Integer()
    elif dt == "BIGINT":
        return BigInteger()
    elif dt in ("NUMBER", "NUMERIC", "DEC", "DECIMAL"):
        if data_precision is not None and data_scale is not None and data_scale > 0:
            return Numeric(precision=int(data_precision), scale=int(data_scale))
        elif data_precision is not None:
            return Numeric(precision=int(data_precision))
        else:
            return Float()
    elif dt in ("FLOAT", "DOUBLE", "DOUBLE PRECISION", "BINARY_FLOAT", "BINARY_DOUBLE"):
        return Float()
    elif dt in ("CLOB", "TEXT", "NCLOB", "LONG"):
        return Text()
    elif dt in ("BLOB", "BINARY", "VARBINARY", "LONG VARBINARY", "IMAGE"):
        return LargeBinary(length=data_length)
    elif dt in ("DATE", "DATETIME", "TIMESTAMP"):
        return DateTime()
    elif dt == "TIME":
        return Time()
    else:
        return String(length=data_length or 255)


def _extract_table_info(inspector, table_name, schema=None, is_view=False):
    """
    提取单个表或视图的详细信息
    table_name: 使用数据库原样的名字（如 'DDTCCY1' 或 'MyTable'）
    is_view: 是否为视图，默认为False（表）
    """
    engine = inspector.bind
    # 仅当需要时加引号，避免把全大写未加引号的表名硬生生变成有引号的小写
    reflect_name = quoted_name(table_name, quote=_should_quote(table_name, engine))

    table_info = {
        "table_name": table_name,  # 对外展示原样
        "schema": schema,
        "description": _get_table_comment(inspector, reflect_name, schema=schema),
        "columns": [],
        "primary_keys": [],
        "foreign_keys": [],
        "indexes": [],
        "is_view": is_view,  # 新增：标识是否为视图
        "view_name": table_name if is_view else None  # 新增：视图名称（如果是视图）
    }

    # 列
    try:
        columns = inspector.get_columns(reflect_name, schema=schema)
    except Exception as e:
        # 视图可能无法获取列信息，尝试其他方式
        # 达梦 DM dialect 对视图的 inspector.get_columns() 会抛出 NoSuchTableError，
        # 但我们有 _get_columns_from_all_tab_columns 兜底方案，所以不打印警告（避免干扰）
        dialect = engine.dialect.name.lower()
        if not (dialect == "dm" and is_view):
            print(f"[WARN] 无法获取 {table_name} 的列信息（可能是视图）: {e}")
        columns = []

    # 达梦 DM dialect 的 inspector.get_columns() 对视图会失败，兜底从 ALL_TAB_COLUMNS 查询
    dialect = engine.dialect.name.lower()
    if not columns and dialect == "dm":
        columns = _get_columns_from_all_tab_columns(engine, table_name, schema=schema)

    # 再获取数据库原始列名（如果支持）
    raw_names = _get_column_names_raw(engine, table_name, schema=schema)
    if raw_names and len(raw_names) == len(columns):
        for i, col in enumerate(columns):
            col["name"] = raw_names[i]

    # 保持原样名字输出
    for col in columns:
        column_info = {
            "name": col["name"],  # 这里就是数据库里的原样大小写
            "type": str(col["type"]),
            "nullable": col.get("nullable", True),
            "default": str(col.get("default")) if col.get("default") is not None else None,
            "comment": col.get("comment", ""),
            "is_primary": False,
            "is_foreign": False
        }
        table_info["columns"].append(column_info)

    # 主键（视图通常没有主键）
    if not is_view:
        try:
            pkc = inspector.get_pk_constraint(reflect_name, schema=schema) or {}
            primary_keys = pkc.get("constrained_columns") or []
            table_info["primary_keys"] = primary_keys
            for c in table_info["columns"]:
                if c["name"] in primary_keys:
                    c["is_primary"] = True
        except Exception:
            pass
    else:
        # 视图没有主键
        table_info["primary_keys"] = []

    # 外键（视图通常没有外键）
    if not is_view:
        try:
            fks = inspector.get_foreign_keys(reflect_name, schema=schema) or []
            for fk in fks:
                table_info["foreign_keys"].append({
                    "name": fk.get("name", ""),
                    "columns": fk.get("constrained_columns", []),
                    "referenced_table": fk.get("referred_table"),
                    "referenced_schema": fk.get("referred_schema"),
                    "referenced_columns": fk.get("referred_columns", []),
                    "on_update": fk.get("onupdate", ""),
                    "on_delete": fk.get("ondelete", "")
                })
            fk_cols = {c for fk in fks for c in (fk.get("constrained_columns") or [])}
            for c in table_info["columns"]:
                if c["name"] in fk_cols:
                    c["is_foreign"] = True
        except Exception:
            pass
    else:
        # 视图没有外键
        table_info["foreign_keys"] = []

    # 索引（视图通常没有索引）
    if not is_view:
        try:
            idxs = inspector.get_indexes(reflect_name, schema=schema) or []
            for idx in idxs:
                table_info["indexes"].append({
                    "name": idx.get("name"),
                    "columns": idx.get("column_names", []),
                    "unique": bool(idx.get("unique")),
                    "type": idx.get("type", "unknown")
                })
        except Exception:
            pass
    else:
        # 视图没有索引
        table_info["indexes"] = []

    return table_info


def _get_table_comment(inspector, table_name, schema=None):
    """获取表注释（跨数据库；table_name 可为 quoted_name）"""
    try:
        c = inspector.get_table_comment(table_name, schema=schema) or {}
        return c.get("text", "") or ""
    except NoSuchTableError:
        # Oracle/达梦 特殊处理：表名大小写敏感性问题
        # 如果查询失败，可能是因为表名大小写不匹配
        dialect = (inspector.bind.dialect.name or "").lower()
        if dialect == "oracle" or dialect == "dm":
            try:
                # 尝试使用大写表名（Oracle/达梦默认行为）
                table_name_str = str(table_name)
                if table_name_str != table_name_str.upper():
                    c = inspector.get_table_comment(table_name_str.upper(), schema=schema) or {}
                    return c.get("text", "") or ""
            except Exception:
                pass
        # 如果仍然失败，返回空字符串（避免阻塞整个流程）
        return ""
    except NotImplementedError:
        if inspector.bind.dialect.name == "mysql":
            try:
                result = inspector.bind.execute(
                    text(
                        "SELECT table_comment FROM information_schema.tables "
                        "WHERE table_schema = DATABASE() AND table_name = :t"
                    ),
                    {"t": str(table_name)}
                ).scalar()
                return result or ""
            except Exception:
                return ""
    except Exception:
        # 其他异常也返回空字符串，避免阻塞
        return ""
    return ""


# 根据不同数据库类型获取对应库或表空间下的所有表名
def get_tables(inspector, engine, payload):
    """
    获取数据库中的表和视图列表
    
    支持的数据源类型：
    - MySQL: 同时获取表和视图
    - PostgreSQL: 同时获取表和视图
    - Oracle: 同时获取表和视图
    - MSSQL: 同时获取表和视图
    - SQLite: 同时获取表和视图
    - Trino: 仅获取表（视图支持有限）
    
    返回格式：
    统一返回字典列表，每个元素为：{"name": "表名或视图名", "type": "TABLE" 或 "VIEW"}
    """
    dialect = engine.dialect.name.lower()
    username = (payload.get("username") or "").upper()
    database = payload.get("database")

    if dialect == "oracle":
        # Oracle: 同时获取表和视图
        # 优先使用 target_schema（用户指定的 schema），否则使用 username（默认行为）
        target_schema = payload.get("target_schema") or username
        result = []
        try:
            with engine.connect() as conn:
                # 查询所有表
                try:
                    table_rows = conn.execute(
                        text("SELECT table_name FROM all_tables WHERE owner = :owner ORDER BY table_name"),
                        {"owner": target_schema.upper()}
                    ).fetchall()
                    for row in table_rows:
                        result.append({"name": row[0], "type": "TABLE"})
                    print(f"[INFO] Oracle 获取到 {len(table_rows)} 个表 (schema={target_schema})")
                except Exception as e:
                    print(f"[WARN] Oracle 查询表列表失败: {e}")

                # 查询所有视图 - 优先使用 all_views，如果失败则尝试 user_views
                view_rows = []
                try:
                    # 方法1: 使用 all_views（需要权限查看所有视图）
                    view_rows = conn.execute(
                        text("SELECT view_name FROM all_views WHERE owner = :owner ORDER BY view_name"),
                        {"owner": target_schema.upper()}
                    ).fetchall()
                    print(f"[INFO] Oracle 从 all_views 获取到 {len(view_rows)} 个视图 (schema={target_schema})")
                except Exception as e1:
                    print(f"[WARN] Oracle 从 all_views 查询视图失败: {e1}")
                    try:
                        # 方法2: 使用 user_views（只能查看当前用户的视图，但不需要额外权限）
                        # 注意：user_views 不需要 owner 条件，因为它只包含当前用户的视图
                        view_rows = conn.execute(
                            text("SELECT view_name FROM user_views ORDER BY view_name")
                        ).fetchall()
                        print(f"[INFO] Oracle 从 user_views 获取到 {len(view_rows)} 个视图")
                    except Exception as e2:
                        print(f"[WARN] Oracle 从 user_views 查询视图也失败: {e2}")

                # 添加视图到结果
                for row in view_rows:
                    result.append({"name": row[0], "type": "VIEW"})

                print(f"[INFO] Oracle 总共获取到 {len(result)} 个对象（表+视图）(schema={target_schema})")

        except Exception as e:
            # 如果整体查询失败，降级为只获取表
            print(f"[ERROR] Oracle 获取表和视图列表失败，尝试仅获取表: {e}")
            import traceback
            print(f"[ERROR] 完整错误堆栈:\n{traceback.format_exc()}")
            try:
                with engine.connect() as conn:
                    rows = conn.execute(
                        text("SELECT table_name FROM all_tables WHERE owner = :owner ORDER BY table_name"),
                        {"owner": target_schema.upper()}
                    ).fetchall()
                    result = [{"name": r[0], "type": "TABLE"} for r in rows]
                    print(f"[INFO] Oracle 降级模式：获取到 {len(result)} 个表 (schema={target_schema})")
            except Exception as e2:
                print(f"[ERROR] Oracle 降级模式也失败: {e2}")
                result = []
        return result

    if dialect == "dm":
        # 达梦 DM: 与 Oracle 高度兼容，使用同样的 all_tables/all_views 查询模式
        # 达梦默认 schema = 用户名大写；支持 target_schema 切换其他模式
        target_schema = (payload.get("target_schema") or payload.get("schema") or username)
        target_schema_str = (target_schema or "").upper()
        result = []
        try:
            with engine.connect() as conn:
                # 查询所有表
                try:
                    table_rows = conn.execute(
                        text("SELECT table_name FROM all_tables WHERE owner = :owner ORDER BY table_name"),
                        {"owner": target_schema_str}
                    ).fetchall()
                    for row in table_rows:
                        result.append({"name": row[0], "type": "TABLE"})
                    print(f"[INFO] 达梦 获取到 {len(table_rows)} 个表 (schema={target_schema_str})")
                except Exception as e:
                    print(f"[WARN] 达梦 查询表列表失败: {e}")

                # 查询所有视图
                view_rows = []
                try:
                    view_rows = conn.execute(
                        text("SELECT view_name FROM all_views WHERE owner = :owner ORDER BY view_name"),
                        {"owner": target_schema_str}
                    ).fetchall()
                    print(f"[INFO] 达梦 从 all_views 获取到 {len(view_rows)} 个视图 (schema={target_schema_str})")
                except Exception as e1:
                    print(f"[WARN] 达梦 从 all_views 查询视图失败: {e1}")
                    try:
                        view_rows = conn.execute(
                            text("SELECT view_name FROM user_views ORDER BY view_name")
                        ).fetchall()
                        print(f"[INFO] 达梦 从 user_views 获取到 {len(view_rows)} 个视图")
                    except Exception as e2:
                        print(f"[WARN] 达梦 从 user_views 查询视图也失败: {e2}")

                for row in view_rows:
                    result.append({"name": row[0], "type": "VIEW"})

                print(f"[INFO] 达梦 总共获取到 {len(result)} 个对象（表+视图）(schema={target_schema_str})")

        except Exception as e:
            print(f"[ERROR] 达梦 获取表和视图列表失败，尝试仅获取表: {e}")
            import traceback
            print(f"[ERROR] 完整错误堆栈:\n{traceback.format_exc()}")
            try:
                with engine.connect() as conn:
                    rows = conn.execute(
                        text("SELECT table_name FROM all_tables WHERE owner = :owner ORDER BY table_name"),
                        {"owner": target_schema_str}
                    ).fetchall()
                    result = [{"name": r[0], "type": "TABLE"} for r in rows]
                    print(f"[INFO] 达梦 降级模式：获取到 {len(result)} 个表 (schema={target_schema_str})")
            except Exception as e2:
                print(f"[ERROR] 达梦 降级模式也失败: {e2}")
                result = []
        return result

    elif dialect == "postgresql" or dialect == "kingbase":
        # PostgreSQL/KingBase: 同时获取表和视图
        result = []
        schema = payload.get("schema") or "public"
        print(f"[DEBUG] {dialect} 获取表列表，使用 schema: {schema}")
        try:
            with engine.connect() as conn:
                # 查询所有表和视图
                sql = text("""
                           SELECT table_name, table_type
                           FROM information_schema.tables
                           WHERE table_schema = :schema_name
                             AND (table_type = 'BASE TABLE' OR table_type = 'VIEW')
                           ORDER BY table_name
                           """)
                rows = conn.execute(sql, {"schema_name": schema}).fetchall()
                print(f"[DEBUG] {dialect} 在 schema '{schema}' 下查询到的表: {rows}")
                for row in rows:
                    table_name = row[0]
                    table_type = row[1] if len(row) > 1 else 'BASE TABLE'
                    # 将 'BASE TABLE' 转换为 'TABLE'，保持一致性
                    type_str = 'VIEW' if table_type == 'VIEW' else 'TABLE'
                    result.append({"name": table_name, "type": type_str})
        except Exception as e:
            # 如果查询失败，降级为只获取表
            print(f"[WARN] {dialect} 获取视图列表失败，仅获取表: {e}")
            table_names = inspector.get_table_names(schema=schema)
            result = [{"name": name, "type": "TABLE"} for name in table_names]
        return result

    elif dialect == "mssql":
        # MSSQL: 同时获取表和视图
        result = []
        schema = payload.get("schema") or "dbo"
        try:
            with engine.connect() as conn:
                # 查询所有表和视图
                sql = text("""
                           SELECT TABLE_NAME, TABLE_TYPE
                           FROM INFORMATION_SCHEMA.TABLES
                           WHERE TABLE_SCHEMA = :schema_name
                             AND (TABLE_TYPE = 'BASE TABLE' OR TABLE_TYPE = 'VIEW')
                           ORDER BY TABLE_NAME
                           """)
                rows = conn.execute(sql, {"schema_name": schema}).fetchall()
                for row in rows:
                    table_name = row[0]
                    table_type = row[1] if len(row) > 1 else 'BASE TABLE'
                    # 将 'BASE TABLE' 转换为 'TABLE'，保持一致性
                    type_str = 'VIEW' if table_type == 'VIEW' else 'TABLE'
                    result.append({"name": table_name, "type": type_str})
        except Exception as e:
            # 如果查询失败，降级为只获取表
            print(f"[WARN] MSSQL 获取视图列表失败，仅获取表: {e}")
            table_names = inspector.get_table_names(schema=schema)
            result = [{"name": name, "type": "TABLE"} for name in table_names]
        return result

    elif dialect == "mysql":
        # MySQL: 同时获取表和视图
        result = []
        try:
            with engine.connect() as conn:
                # 查询所有表和视图，使用 information_schema 或 SHOW FULL TABLES
                # 优先使用 information_schema，更可靠
                if database:
                    sql = text("""
                               SELECT TABLE_NAME, TABLE_TYPE
                               FROM information_schema.TABLES
                               WHERE TABLE_SCHEMA = :db_name
                                 AND (TABLE_TYPE = 'BASE TABLE' OR TABLE_TYPE = 'VIEW')
                               ORDER BY TABLE_NAME
                               """)
                    rows = conn.execute(sql, {"db_name": database}).fetchall()
                else:
                    # 如果没有指定数据库，使用 SHOW FULL TABLES（在当前数据库上下文中）
                    sql = text("SHOW FULL TABLES")
                    rows = conn.execute(sql).fetchall()

                for row in rows:
                    table_name = row[0]
                    table_type = row[1] if len(row) > 1 else 'BASE TABLE'
                    # 将 'BASE TABLE' 转换为 'TABLE'，保持一致性
                    type_str = 'VIEW' if table_type == 'VIEW' else 'TABLE'
                    result.append({"name": table_name, "type": type_str})
        except Exception as e:
            # 如果查询失败，降级为只获取表
            print(f"[WARN] MySQL 获取视图列表失败，仅获取表: {e}")
            table_names = inspector.get_table_names(schema=database)
            result = [{"name": name, "type": "TABLE"} for name in table_names]
        return result

    elif dialect == "sqlite":
        # SQLite: 同时获取表和视图
        result = []
        try:
            with engine.connect() as conn:
                # 查询所有表和视图
                sql = text("""
                           SELECT name, type
                           FROM sqlite_master
                           WHERE (type = 'table' OR type = 'view')
                             AND name NOT LIKE 'sqlite_%'
                           ORDER BY name
                           """)
                rows = conn.execute(sql).fetchall()
                for row in rows:
                    table_name = row[0]
                    table_type = row[1] if len(row) > 1 else 'table'
                    # 将 'table' 转换为 'TABLE'，'view' 转换为 'VIEW'
                    type_str = 'VIEW' if table_type.lower() == 'view' else 'TABLE'
                    result.append({"name": table_name, "type": type_str})
        except Exception as e:
            # 如果查询失败，降级为只获取表
            print(f"[WARN] SQLite 获取视图列表失败，仅获取表: {e}")
            table_names = inspector.get_table_names()
            result = [{"name": name, "type": "TABLE"} for name in table_names]
        return result

    elif dialect == "trino":
        # Trino: 同时获取指定 catalog/schema 下的表与视图
        schema = payload.get("schema")
        catalog = payload.get("catalog") or payload.get("database")
        if not schema:
            print(f"[WARN] Trino 获取表/视图失败：缺少 schema 参数（catalog={catalog}）")
            return []

        result = []
        seen_names: Set[Tuple[str, str]] = set()

        def _append(items: List[str], obj_type: str):
            for name in items or []:
                key = (name, obj_type)
                if key in seen_names:
                    continue
                seen_names.add(key)
                result.append({"name": name, "type": obj_type})

        try:
            table_names = inspector.get_table_names(schema=schema)
            _append(table_names, "TABLE")
            print(f"[DEBUG] Trino 获取到 {len(table_names or [])} 个表（catalog={catalog}, schema={schema}）")
        except Exception as e:
            print(f"[WARN] Trino 获取表列表失败（catalog={catalog}, schema={schema}）: {e}")

        try:
            view_names = inspector.get_view_names(schema=schema)
            _append(view_names, "VIEW")
            print(f"[DEBUG] Trino 获取到 {len(view_names or [])} 个视图（catalog={catalog}, schema={schema}）")
        except Exception as e:
            # 部分 Trino catalog 可能不支持视图，打印告警即可
            print(f"[WARN] Trino 获取视图列表失败（catalog={catalog}, schema={schema}）: {e}")

        return result

    else:
        # 其他数据库类型：只返回表，保持向后兼容
        table_names = inspector.get_table_names()
        return [{"name": name, "type": "TABLE"} for name in table_names]


# 数据入库（以表为单位）
def bad_request(msg, code=400):  # 异常返回封装
    return {"error": msg}, code


def insert_table_info_to_db(payload: dict, user_id: str, connect_info: str, connect_name: str, request_id: str = None,
                            db_connect_info_payload: dict = None, schema_name: str = None):
    """
    只插入不存在的表；已存在的表跳过
    返回: {"message":"success", "inserted":N, "skipped":M, "total":T}, 200
    若无任何可插入项，则 inserted=0, skipped=T

    参数:
        request_id: 请求ID，用于在处理过程中检查是否已被取消
        db_connect_info_payload: 数据库连接信息（用于 Trino catalog_type）
        schema_name: 当前数据源的 schema 名（PG/MSSQL/Oracle 用于区分同 connect_info 不同 schema）。
                     MySQL/Trino/SQLite 可为 None。同一参数也会被写入表的 schema_name 列。
    """

    print("------------初次表提取结果入库------------")
    print(f"payload keys: {list(payload.keys())}\nuser_id:{user_id}\nrequest_id:{request_id}\nschema_name:{schema_name}")

    db_type = (payload.get("database_type") or "").lower()
    db_version = payload.get("database_version", "")
    tables = payload.get("tables", [])

    # 获取 catalog_type：仅当 db_type 为 trino 时需要
    catalog_type = None
    if db_type == "trino" and db_connect_info_payload:
        catalog_type = db_connect_info_payload.get("catalog")
        print(f"[INFO] Trino 连接，catalog_type: {catalog_type}")

    if not (db_type and user_id and connect_info and connect_name):  # ← 校验数据源名称非空
        return bad_request("请求参数缺失: 数据库类型, 用户id, 连接信息,连接名称 等")
    if not isinstance(tables, list) or not tables:
        return bad_request("库中不存在数据表，请检查数据源是否为空")

    url = make_url(connect_info)
    # 获取 target_schema（用于 Oracle 的 database_name）
    oracle_target_schema = None
    if db_connect_info_payload and db_connect_info_payload.get("target_schema"):
        oracle_target_schema = db_connect_info_payload.get("target_schema")

    if db_type == "oracle":
        # Oracle: 有 target_schema 则使用它，否则使用 username
        db_name_for_rows = oracle_target_schema or (url.username or "").upper()
    elif db_type == "dm":
        # 达梦: 优先 target_schema / schema，否则使用 username（达梦默认 schema = 用户名大写）
        db_name_for_rows = (
            db_connect_info_payload.get("target_schema")
            or db_connect_info_payload.get("schema")
            or (url.username or "").upper()
        )
    elif db_type in ("postgresql", "mysql", "mssql", "kingbase"):
        db_name_for_rows = url.database
    elif db_type == "sqlite":
        db_name_for_rows = url.database or ":memory:"
    elif db_type == "trino":
        # Trino: database 字段格式为 "catalog/schema"，我们存储完整路径
        db_name_for_rows = url.database or ""
    else:
        db_name_for_rows = url.database

    # 检查请求是否已被取消
    if request_id and request_status_manager.is_cancelled(request_id):
        print(f"[CANCELLED] 请求 {request_id} 已被取消，停止入库操作")
        raise RequestCancelledException(f"请求 {request_id} 已被取消")

    # 1) 拉取已存在的表名集合
    # 重要：按 db_type 分支决定是否带 schema_name 过滤
    # - PG/MSSQL/Oracle：必须按 schema_name 严格匹配（避免把"同 connect_info 不同 schema 的同名表"误判为已存在）
    # - MySQL/Trino/SQLite：保持原行为，仅按 (user_id, connect_info) 过滤
    # 使用稳定的哈希值进行比较（因为 AES-GCM 加密每次使用随机 nonce）
    connect_info_hash = get_connect_info_hash(connect_info)

    existing_query = db.session.query(UserDatasourceSchema.table_name).filter(
        UserDatasourceSchema.user_id == user_id,
        UserDatasourceSchema.connect_info_hash == connect_info_hash,
    )
    existing_query = _add_schema_filter(existing_query, db_type, schema_name)
    existing_names = set(
        r[0]
        for r in existing_query.all()
    )

    # 筛选出需要处理的表
    tables_to_process = []
    skipped = 0
    total = 0

    for t in tables:
        total += 1
        table_name = (t.get("table_name") or "").strip()
        if not table_name:
            # 跳过异常项，但不中断整个流程
            skipped += 1
            continue

        if table_name in existing_names:
            # 已存在：跳过
            skipped += 1
            continue

        tables_to_process.append(t)

    # 记录原始对象的视图元信息，避免后续富化过程丢失
    view_meta_map: Dict[str, Dict[str, Any]] = {}
    for t in tables_to_process:
        name = (t.get("table_name") or "").strip()
        if not name:
            continue
        original_is_view = bool(t.get("is_view"))
        original_view_name = t.get("view_name") if original_is_view else None
        if original_is_view and not original_view_name:
            original_view_name = name
        view_meta_map[name] = {
            "is_view": original_is_view,
            "view_name": original_view_name
        }

    # 在进行LLM填充前，先进行表健康检查，记录有问题的表
    health_check_result = None
    if tables_to_process:
        try:
            health_check_result = check_tables_health_batch(
                tables=tables_to_process,
                user_id=user_id,
                connect_info=connect_info
            )
        except Exception as e:
            # 健康检查失败不影响后续流程
            print(f"[HEALTH_CHECK][WARN] 健康检查失败: {e}")

    # 并行调用 LLM 进行字段补充（使用线程池）
    # 为了在"填充后健康检查"里能对比前后状态，这里对待处理表做一次快照，避免原地修改影响对比
    tables_before_snapshot = _copy.deepcopy(tables_to_process)

    # 获取 Flask app 实例，用于在线程中创建应用上下文
    app = current_app._get_current_object()

    def enrich_single_table(table_obj: dict) -> Tuple[dict, str, bool]:
        """
        对单张表进行富化处理（包含采样数据）
        返回: (enriched_obj, table_name, changed)
        注意：此函数在线程池中运行，需要手动创建 Flask 应用上下文
        """
        table_name = (table_obj.get("table_name") or "").strip()
        try:
            # 在线程中显式创建 Flask 应用上下文
            with app.app_context():
                # 1. 采样表数据
                sampling_data = None
                sensitive_fields = []
                try:
                    from controllers.datacard.datacard_sampling import DataCardSamplingService
                    from sqlalchemy import create_engine

                    sampling_service = DataCardSamplingService(
                        db_type=db_type or "postgresql",
                        schema=schema_name
                    )

                    # 创建临时连接采样
                    temp_engine = create_engine(connect_info, pool_pre_ping=True)
                    with temp_engine.connect() as temp_conn:
                        # 提取字段名列表
                        column_names = [col.get("name") for col in table_obj.get("columns", [])]
                        if column_names:
                            sampling_data = sampling_service.sample_table_data(
                                temp_conn, table_name, column_names
                            )

                            # 构建采样数据字典（用于 prompt）
                            sampling_data_dict = {}
                            for col_name, sample_obj in sampling_data.items():
                                if sample_obj.distinct_values:
                                    # 转换 datetime 等类型为字符串
                                    display_values = []
                                    for v in sample_obj.distinct_values[:10]:
                                        if hasattr(v, 'isoformat'):
                                            display_values.append(v.isoformat())
                                        elif isinstance(v, (int, float, str, bool, type(None))):
                                            display_values.append(v)
                                        else:
                                            display_values.append(str(v))
                                    sampling_data_dict[col_name] = display_values

                            # 快速识别敏感字段（基于字段名）
                            sensitive_fields = [
                                {"name": col_name}
                                for col_name in column_names
                                if sampling_service._quick_sensitive_check(col_name)
                            ]

                    temp_engine.dispose()
                    print(f"[ENRICH/PREINSERT] {table_name}: 采样完成，{len(sampling_data_dict)} 个字段有数据")

                except Exception as sampling_err:
                    print(f"[ENRICH/PREINSERT][WARN] {table_name} 采样失败: {sampling_err}")
                    sampling_data_dict = None
                    sensitive_fields = []

                # 2. 调用 LLM 填充字段注释（传入采样数据和敏感字段信息）
                enriched_obj, changed = enrich_table_before_insert(
                    table_obj,
                    sampling_data=sampling_data_dict,
                    sensitive_fields=sensitive_fields
                )

            print(f"[ENRICH/PREINSERT] {table_name} changed={changed}")
            return enriched_obj, table_name, changed
        except Exception as e:
            # 任何异常都不阻塞入库，降级为原始对象
            print(f"[ENRICH/PREINSERT][WARN] {table_name}: {e}")
            return table_obj, table_name, False

    # 使用线程池并行处理（最多10个并发，避免过多并发请求）
    enriched_results = []
    max_workers = min(10, len(tables_to_process)) if tables_to_process else 1

    if tables_to_process:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_table = {
                executor.submit(enrich_single_table, t): t
                for t in tables_to_process
            }

            # 收集结果（保持原始顺序）
            for t in tables_to_process:
                # 在处理每个表之前检查是否已取消
                if request_id and request_status_manager.is_cancelled(request_id):
                    print(f"[CANCELLED] 请求 {request_id} 已被取消，停止富化处理")
                    raise RequestCancelledException(f"请求 {request_id} 已被取消")

                for future in future_to_table:
                    if future_to_table[future] == t:
                        enriched_obj, table_name, changed = future.result()
                        enriched_results.append((enriched_obj, table_name))
                        break

    # 在填充后，再次进行健康检查，对比填充前后的状态
    health_check_result_after = None
    if tables_to_process and enriched_results:
        try:
            enriched_tables = [obj for obj, _ in enriched_results]
            health_check_result_after = check_tables_health_batch(
                tables=tables_before_snapshot,
                user_id=user_id,
                connect_info=connect_info,
                enriched_tables=enriched_tables
            )
        except Exception as e:
            # 健康检查失败不影响后续流程
            print(f"[HEALTH_CHECK][WARN] 填充后健康检查失败: {e}")

    # 构建入库记录
    rows_to_insert = []
    # 预构建 before/after 的表名映射，便于生成 filled_data
    before_problem_map = {}
    try:
        for item in (health_check_result or {}).get("problematic_tables", []) or []:
            name = (item or {}).get("table_name")
            if name:
                before_problem_map[name] = item
    except Exception:
        before_problem_map = {}

    after_problem_map = {}
    try:
        for item in (health_check_result_after or {}).get("problematic_tables", []) or []:
            name = (item or {}).get("table_name")
            if name:
                after_problem_map[name] = item
    except Exception:
        after_problem_map = {}

    for enriched_obj, table_name in enriched_results:
        # 再次检查是否已取消
        if request_id and request_status_manager.is_cancelled(request_id):
            print(f"[CANCELLED] 请求 {request_id} 已被取消，停止构建入库记录")
            raise RequestCancelledException(f"请求 {request_id} 已被取消")

        # 恢复/增强视图标识，防止在富化过程中丢失
        view_meta = view_meta_map.get(table_name) or {}
        is_view = bool(enriched_obj.get("is_view"))
        if not is_view and view_meta.get("is_view"):
            is_view = True
        view_name = enriched_obj.get("view_name")
        if is_view and not view_name:
            view_name = view_meta.get("view_name") or table_name

        # 确保 schema_text 中也包含准确的视图信息
        enriched_obj["is_view"] = bool(is_view)
        enriched_obj["view_name"] = view_name if is_view else None

        schema_text = json.dumps(enriched_obj, ensure_ascii=False)

        # 依据"填充前是否存在缺失"来标记 is_filled；并将明细写入 filled_data
        before_entry = before_problem_map.get(table_name) or {}
        after_entry = after_problem_map.get(table_name) or {}

        # 生成 per-table 的 detailed_fill（与原 JSON 中的风格一致）
        detailed_fill = {}
        try:
            fill_result = (after_entry or {}).get("fill_result") or {}
            filled_map = {}
            for it in (fill_result.get("filled_fields") or []):
                n = (it or {}).get("name")
                c = (it or {}).get("comment")
                if n and c is not None:
                    filled_map[n] = c
            still_missing_names = [
                i.get("name")
                for i in (fill_result.get("still_missing_fields") or [])
                if i.get("name")
            ]
            detailed_fill = {
                "table_name": table_name,
                "filled_map": filled_map,
                "still_missing_fields": still_missing_names,
                # 由 LLM 补全后的表级描述
                "filled_table_description": (enriched_obj or {}).get("description")
            }
        except Exception:
            detailed_fill = {
                "table_name": table_name,
                "filled_table_description": (enriched_obj or {}).get("description")
            }

        # 是否进行过填充：以"填充前是否存在缺失"为准
        had_missing_before = bool(before_entry)
        per_table_payload = {
            "table_name": table_name,
            "before": before_entry or {},
            "fill_result": (after_entry or {}).get("fill_result") or {},
            "detailed_fill": detailed_fill
        }

        # [已移除] 数据盘查功能已迁移至治理规则库模块
        # 原 perform_data_audit() 调用已移除

        rows_to_insert.append(UserDatasourceSchema(
            user_id=user_id,
            db_type=db_type,
            connect_info=encrypt_connect_info(connect_info),  # 加密存储
            connect_info_hash=get_connect_info_hash(connect_info),  # 稳定哈希值用于匹配
            database_name=db_name_for_rows,
            connect_name=connect_name,
            schema_text=schema_text,
            table_name=table_name,
            db_version=db_version,
            catalog_type=catalog_type,
            schema_name=schema_name,  # 新增：写入当前数据源对应的 schema 名
            is_view=is_view,
            view_name=view_name,
            is_filled=had_missing_before,
            filled_data=(json.dumps(per_table_payload, ensure_ascii=False) if had_missing_before else None)
        ))

    if not rows_to_insert:
        # 没有任何可插入项：返回 200 + 统计，而不是 409
        return {
            "message": "success",
            "inserted": 0,
            "skipped": skipped,
            "total": total,
            "health_before": health_check_result or {},
            "health_after": health_check_result_after or {}
        }, 200

    # 最后一次检查：在提交数据库事务前
    if request_id and request_status_manager.is_cancelled(request_id):
        print(f"[CANCELLED] 请求 {request_id} 已被取消，不提交数据库事务")
        raise RequestCancelledException(f"请求 {request_id} 已被取消")

    try:
        db.session.add_all(rows_to_insert)
        db.session.commit()
        return {
            "message": "success",
            "inserted": len(rows_to_insert),
            "skipped": skipped,
            "total": total,
            "health_before": health_check_result or {},
            "health_after": health_check_result_after or {}
        }, 200

    except IntegrityError as e:
        # 极少数并发下仍可能冲突；逐条兜底插入“仍不存在”的
        db.session.rollback()
        actually_inserted = 0
        for row in rows_to_insert:
            try:
                # 再查一次，防止并发期间被别人插入了
                # 按 db_type 分支决定是否带 schema_name（避免不同 schema 同 table_name 互相误判已存在）
                # 使用 connect_info_hash 进行稳定匹配（因为加密值每次 nonce 不同）
                exists_query = db.session.query(UserDatasourceSchema.id).filter(
                    UserDatasourceSchema.user_id == row.user_id,
                    UserDatasourceSchema.connect_info_hash == row.connect_info_hash,
                    UserDatasourceSchema.table_name == row.table_name,
                )
                exists_query = _add_schema_filter(exists_query, db_type, row.schema_name)
                exists = exists_query.first()
                if exists:
                    continue
                db.session.add(row)
                db.session.commit()
                actually_inserted += 1
            except IntegrityError:
                db.session.rollback()
                # 这条就算并发插入了，继续下一条
                continue

        return {
            "message": "success",
            "inserted": actually_inserted,
            "skipped": total - actually_inserted,
            "total": total,
            "note": "部分并发冲突已自动跳过",
            "health_before": health_check_result or {},
            "health_after": health_check_result_after or {}
        }, 200


def _fix_mssql_connection_for_legacy_ssl(connection_string_str: str) -> str | None:
    """
    针对 MSSQL 的 legacy SSL sigalg 问题修复连接字符串
    返回修复后的连接字符串，如果无法修复则返回 None
    支持两种格式：
    1. URL 格式：mssql+pyodbc://server/db
    2. ODBC DSN 格式：DRIVER={ODBC Driver 17};SERVER=...;...
    """
    try:
        # 尝试 URL 格式
        if "://" in connection_string_str:
            url_obj = make_url(connection_string_str)
            q = dict(url_obj.query or {})
            q["Encrypt"] = "yes"
            q["TrustServerCertificate"] = "yes"
            url_obj = url_obj.set(query=q)
            return url_obj.render_as_string(hide_password=False)

        # 处理 ODBC DSN 格式（分号分隔的键值对）
        # 格式如：DRIVER={ODBC Driver 17};SERVER=...;DATABASE=...;UID=...;PWD=...
        if any(keyword in connection_string_str.upper() for keyword in ["DRIVER=", "SQL SERVER", "SERVER=", "PYODBC"]):
            parts = connection_string_str.split(";")
            fixed_parts = []
            has_encrypt = False
            has_trust_cert = False

            for part in parts:
                part_stripped = part.strip()
                part_upper = part_stripped.upper()
                if part_upper.startswith("ENCRYPT="):
                    fixed_parts.append("ENCRYPT=yes")
                    has_encrypt = True
                elif part_upper.startswith("TRUSTSERVERCERTIFICATE="):
                    fixed_parts.append("TRUSTSERVERCERTIFICATE=yes")
                    has_trust_cert = True
                else:
                    fixed_parts.append(part_stripped)

            # 如果没有 ENCRYPT 参数，添加它
            if not has_encrypt:
                # 在 DRIVER 之后插入
                new_parts = []
                for part in fixed_parts:
                    new_parts.append(part)
                    if part.upper().startswith("DRIVER="):
                        new_parts.append("ENCRYPT=yes")
                        new_parts.append("TrustServerCertificate=yes")
                        break
                if len(new_parts) == len(fixed_parts):
                    # DRIVER 不在开头，在末尾添加
                    new_parts.append("ENCRYPT=yes")
                    new_parts.append("TrustServerCertificate=yes")
                fixed_parts = new_parts

            return ";".join(fixed_parts)

        return None
    except Exception as e:
        print(f"[DEBUG] 修复 MSSQL 连接字符串失败: {e}")
        return None


def _fix_mssql_odbc_dsn(connection_string_str: str) -> str | None:
    """
    专门针对 ODBC DSN 格式的 MSSQL 连接字符串修复 legacy SSL 问题
    ODBC DSN 格式示例：
    DRIVER={ODBC Driver 17 for SQL Server};SERVER=host;DATABASE=db;UID=user;PWD=pass
    """
    try:
        if "DRIVER=" not in connection_string_str.upper():
            return None

        parts = connection_string_str.split(";")
        fixed_parts = []
        existing_keys = {}

        for part in parts:
            part_stripped = part.strip()
            if not part_stripped:
                continue

            # 提取键名（忽略大小写）
            if "=" in part_stripped:
                key = part_stripped.split("=")[0].strip().upper()
                existing_keys[key] = part_stripped

        # 构建修复后的连接字符串
        # 移除 ENCRYPT 和 TRUSTSERVERCERTIFICATE（如果存在）
        for key, value in existing_keys.items():
            if key not in ("ENCRYPT", "TRUSTSERVERCERTIFICATE"):
                fixed_parts.append(value)

        # 添加加密参数
        fixed_parts.append("Encrypt=yes")
        fixed_parts.append("TrustServerCertificate=yes")

        return ";".join(fixed_parts)
    except Exception as e:
        print(f"[DEBUG] 修复 ODBC DSN 连接字符串失败: {e}")
        return None


def _detect_and_guard_oceanbase_mode(engine):
    """
    【OceanBase 适配】探测 OceanBase 租户的兼容模式（OB 1.4+ 跨 3.x/4.x 都支持）。

    探测策略（按可靠性从高到低）：
      1) SHOW VARIABLES LIKE 'ob_compatibility_mode'    — 主探测（3.x/4.x 都稳定支持）
      2) SELECT VERSION()                                — 兜底1（看是否含 OceanBase 关键字）
      3) SHOW VARIABLES LIKE 'version_comment'           — 兜底2（同上关键字匹配）

    结果处理：
      - mode=ORACLE  → 直接拒绝并抛出 AppDBConnectError(400, 友好提示)
      - mode=MYSQL   → 通过
      - mode=UNKNOWN → 默认按 OCEANBASE_STRICT_MODE 环境变量决定：
                       - 默认宽松（false）：警告 + 放行（不影响生产）
                       - 严格模式（true）：拒绝，避免误识别非 OB 数据库

    探测到的 OB 版本号会写回 DatasourceInfo.db_version（如果调用方传了 datasource_id），
    便于运维排查。当前仅打印日志；如需写回，可在外层调用方（connect_test 接口）处理。
    """
    import os
    from sqlalchemy import text as _sa_text

    detect_info = {"mode": "UNKNOWN", "ob_version": None, "method": "none"}

    with engine.connect() as conn:
        # === 1) 主探测：ob_compatibility_mode 变量 ===
        try:
            row = conn.execute(_sa_text("SHOW VARIABLES LIKE 'ob_compatibility_mode'")).fetchone()
            if row and len(row) >= 2 and row[1]:
                detect_info["mode"] = str(row[1]).upper()
                detect_info["method"] = "compat_mode_var"
        except Exception:
            pass

        # === 2) 兜底1：SELECT VERSION() 含 OceanBase 关键字 ===
        if detect_info["mode"] == "UNKNOWN":
            try:
                row = conn.execute(_sa_text("SELECT VERSION()")).fetchone()
                if row and row[0]:
                    ver = str(row[0])
                    detect_info["ob_version"] = ver
                    if "oceanbase" in ver.lower():
                        detect_info["mode"] = "MYSQL"   # 能拿到这种格式说明是 MySQL 模式
                        detect_info["method"] = "version_string"
            except Exception:
                pass

        # === 3) 兜底2：version_comment 含 OceanBase 关键字 ===
        if detect_info["mode"] == "UNKNOWN":
            try:
                row = conn.execute(_sa_text("SHOW VARIABLES LIKE 'version_comment'")).fetchone()
                if row and len(row) >= 2 and row[1] and "oceanbase" in str(row[1]).lower():
                    detect_info["mode"] = "MYSQL"
                    detect_info["method"] = "version_comment_var"
            except Exception:
                pass

    # === 结果处理 ===
    mode = detect_info["mode"]
    ver = detect_info["ob_version"]
    method = detect_info["method"]

    if mode == "ORACLE":
        raise AppDBConnectError(
            code=400,
            msg=(
                "当前数据源为 OceanBase Oracle 模式租户"
                f"（探测方式：{method}，OB 版本：{ver or '未知'}），"
                "系统当前仅支持 OceanBase MySQL 模式租户。"
                "请在 OB 集群中创建 MySQL 模式租户后再接入。"
            ),
        )

    if mode == "MYSQL":
        print(
            f"[DEBUG] OceanBase 兼容模式探测成功：mode=MYSQL, "
            f"ob_version={ver}, detect_method={method}"
        )
        return detect_info

    # mode == "UNKNOWN" → 全部探测失败
    strict = os.environ.get("OCEANBASE_STRICT_MODE", "false").lower() == "true"
    if strict:
        raise AppDBConnectError(
            code=400,
            msg=(
                "无法识别 OceanBase 兼容模式（已将 SHOW VARIABLES LIKE "
                "'ob_compatibility_mode'、SELECT VERSION()、SHOW VARIABLES LIKE "
                "'version_comment' 全部尝试失败）。这通常意味着数据库版本过低或被"
                "定制修改。请使用 OBClient 手工验证，或将环境变量 OCEANBASE_STRICT_MODE"
                "设为 false 后重试。"
            ),
        )

    print(
        f"[WARN] OceanBase 兼容模式探测失败，按 MySQL 模式继续。"
        f"mode=UNKNOWN, ob_version={ver}, method={method}。"
        f"如需更严格策略，请设置环境变量 OCEANBASE_STRICT_MODE=true。"
    )
    return detect_info


def get_db_engine(connection_string_str: str, db_type: str = None):
    """
    创建可用的 SQLAlchemy engine，并在连接失败时抛出 AppDBConnectError(code, msg)：
      - 400：常见可修复错误（驱动缺失/未指定、库不存在/登录失败、超时/网络等）
      - 500：未知异常
    兼容：MySQL 在服务端不支持 utf8mb4 时自动降级为 utf8 并重试。
    自动处理 MSSQL 的 legacy SSL sigalg 问题。

    Args:
        connection_string_str: SQLAlchemy 连接字符串
        db_type: 数据库类型（可选，用于 KingBase 等特殊处理）
    """
    try:
        # 忽略 SQLAlchemy 对新版本 SQL Server 的版本识别警告
        import warnings
        warnings.filterwarnings("ignore", category=Warning, module="sqlalchemy.*")

        # 从连接字符串提取 drivername 判断数据库类型
        from sqlalchemy.engine.url import make_url
        try:
            url = make_url(connection_string_str)
            url_db_type = url.drivername.split("+")[0].lower()  # 提取 dialect 部分
        except Exception:
            url_db_type = None

        # 最终数据库类型：优先使用传入的 db_type
        final_db_type = (db_type or url_db_type or "").lower()

        # Oracle oracledb 驱动特殊处理
        if "oracle" in connection_string_str.lower() and "oracledb" in connection_string_str.lower():
            # 初始化thick模式（支持Oracle 11g）
            _init_oracle_thick_mode()

        # KingBase 特殊处理（兼容 PostgreSQL 协议）
        create_engine_kwargs = {}
        if final_db_type == "kingbase":
            # KingBase 返回的版本字符串格式是 "KingbaseES V009R001C010"
            # 需要 patch PostgreSQL 方言的 _get_server_version_info 方法来兼容
            from sqlalchemy.dialects.postgresql import base as pg_base
            _original_get_version = pg_base.PGDialect._get_server_version_info

            def _kingbase_get_version(self, connection):
                try:
                    return _original_get_version(self, connection)
                except AssertionError:
                    # KingBase 版本字符串无法解析，返回兼容版本
                    return (9, 6)

            pg_base.PGDialect._get_server_version_info = _kingbase_get_version
            print("[DEBUG] KingBase 连接，已 patch _get_server_version_info")

        # 达梦 DM：按需注册方言（仅在首次创建达梦引擎时触发一次）
        if final_db_type == "dm":
            _ensure_dm_dialect()

        engine = create_engine(connection_string_str, **create_engine_kwargs)

        # 立刻试连，触发真实握手（可提前暴露连接/认证/库名问题）
        # 根据数据库类型选择合适的测试 SQL
        if "trino://" in connection_string_str.lower():
            # Trino 使用简单的 SELECT 1
            test_sql = "SELECT 1"
        elif ("oracle" in connection_string_str.lower() or "dm+dmPython" in connection_string_str.lower()) and "trino://" not in connection_string_str.lower():
            # 原生 Oracle 连接使用 DUAL；达梦 DM 也兼容 DUAL 语法，沿用 Oracle 风格
            test_sql = "SELECT 1 FROM DUAL"
        else:
            # 其他数据库使用 SELECT 1
            test_sql = "SELECT 1"
        with engine.connect() as conn:
            conn.execute(text(test_sql))

        # 【OceanBase 适配】当 db_type 为 oceanbase 时，探测租户兼容模式
        # - ORACLE 模式 → 直接拒绝并抛出友好错误
        # - MYSQL 模式 → 通过（继续后续逻辑）
        # - 探测失败 → 视环境变量 OCEANBASE_STRICT_MODE 决定是否拒绝（默认宽松）
        if final_db_type == "oceanbase":
            _detect_and_guard_oceanbase_mode(engine)

        # 【达梦 DM 适配】连接成功后打印一条可读日志，便于运维排查
        # 达梦没有像 OceanBase 那样的"模式探测"问题（DM 没有 Oracle/MySQL 模式之分），
        # 但需要确认 dialect 名称是 dm，否则说明 dmSQLAlchemy 未正确注册
        if final_db_type == "dm":
            dialect_name = (engine.dialect.name or "").lower()
            if dialect_name != "dm":
                print(f"[WARNING] 达梦连接成功，但 dialect 名称为 '{dialect_name}'（期望 'dm'），"
                      f"dmSQLAlchemy 可能未正确安装或注册")

        return engine

    except OperationalError as oe:
        # ------- 先尝试捕获 psycopg3 的原生 OperationalError -------
        # psycopg3 的异常可能不是 sqlalchemy.exc.OperationalError 的子类
        try:
            import psycopg
            # 获取原始错误消息（可能来自底层驱动）
            err_raw = str(oe)
            if oe.__cause__:
                err_raw = str(oe.__cause__)
            err_low = err_raw.lower()

            # 检查是否是 psycopg 的连接错误
            if ("socket is not connected" in err_low or
                    "connection refused" in err_low or
                    "could not send" in err_low):
                raise AppDBConnectError(400, "数据库服务器无法访问，请检查主机地址和端口是否正确")

            if "timeout" in err_low or "timed out" in err_low:
                raise AppDBConnectError(400, "连接响应超时，请检查网络状况及服务器可访问后重试")
        except AppDBConnectError:
            raise
        except (ImportError, AttributeError):
            pass

        # ------- MySQL 特判：utf8mb4 → utf8 自动降级并重试 -------
        msg_all = str(oe)
        msg_low = msg_all.lower()
        is_mysql = "mysql" in connection_string_str.lower()
        if is_mysql and ("unknown character set" in msg_low and "utf8mb4" in msg_low):
            url_obj = make_url(connection_string_str)
            q = dict(url_obj.query or {})
            q["charset"] = "utf8"
            url_obj = url_obj.set(query=q)
            downgraded = url_obj.render_as_string(hide_password=False)
            print("检测到 MySQL5 不支持 utf8mb4，自动降级为 utf8 并重试：",
                  url_obj.render_as_string(hide_password=True))
            try:
                engine = create_engine(downgraded)
                # 根据数据库类型选择合适的测试 SQL
                if "trino://" in downgraded.lower():
                    test_sql = "SELECT 1"
                elif ("oracle" in downgraded.lower() or "dm+dmPython" in downgraded.lower()) and "trino://" not in downgraded.lower():
                    # Oracle / 达梦 DM：使用 DUAL
                    test_sql = "SELECT 1 FROM DUAL"
                else:
                    test_sql = "SELECT 1"
                with engine.connect() as conn:
                    conn.execute(text(test_sql))
                return engine
            except Exception:
                raise AppDBConnectError(400, "数据库连接失败,请检查连接信息后重试")

        # ------- MSSQL 特判：自签名证书 SSL 错误自动添加 TrustServerCertificate -------
        # 检测 MSSQL 连接（包括 ODBC DSN 格式）
        conn_upper = connection_string_str.upper()
        is_mssql = (
            "mssql" in connection_string_str.lower() or
            "pyodbc" in connection_string_str.lower() or
            ("DRIVER=" in conn_upper and "SQL SERVER" in conn_upper) or
            ("DRIVER=" in conn_upper and "ODBC DRIVER" in conn_upper)
        )
        is_ssl_cert_error = (
            "ssl routines" in msg_low and "certificate verify failed" in msg_low
        ) or (
            "self-signed certificate" in msg_low
        ) or (
            "0a000086" in msg_low
        ) or (
            "0a00014d" in msg_low or "legacy sigalg" in msg_low
        )
        if is_mssql and is_ssl_cert_error:
            fixed_conn = _fix_mssql_connection_for_legacy_ssl(connection_string_str)
            if fixed_conn:
                print(f"检测到 MSSQL SSL 错误（包括旧签名算法问题），自动修复连接字符串并重试")
                try:
                    engine = create_engine(fixed_conn)
                    test_sql = "SELECT 1"
                    with engine.connect() as conn:
                        conn.execute(text(test_sql))
                    return engine
                except Exception:
                    pass  # 继续尝试其他修复方案或抛出友好错误

            # 如果上面的修复失败，再尝试专门的 ODBC DSN 格式处理
            # 这对于使用 "DRIVER={ODBC Driver 17};SERVER=..." 格式的连接特别重要
            if "DRIVER=" in connection_string_str.upper():
                odbc_fixed = _fix_mssql_odbc_dsn(connection_string_str)
                if odbc_fixed and odbc_fixed != connection_string_str:
                    print(f"检测到 MSSQL ODBC DSN 格式 SSL 错误，自动修复连接参数并重试")
                    try:
                        engine = create_engine(odbc_fixed)
                        test_sql = "SELECT 1"
                        with engine.connect() as conn:
                            conn.execute(text(test_sql))
                        return engine
                    except Exception:
                        pass

        # ------- 非 MySQL：做友好分类（优先库不存在，再到登录失败） -------
        # 优先使用完整的异常消息（可能已包含底层驱动错误信息）
        err_raw = str(getattr(oe, "orig", oe))
        if err_raw == str(oe) or not err_raw:
            # 如果 orig 属性无效，尝试从 __cause__ 获取
            if oe.__cause__:
                err_raw = str(oe.__cause__)
            else:
                err_raw = str(oe)
        err_low = err_raw.lower()

        # === ① 库不存在/不可用（SQL Server 常见 4060；中英双语关键字） ===
        # 英文：cannot open database / requested by the login / does not exist
        # 中文：无法打开登录所请求的数据库 / 数据库 不存在 / 未找到
        db_not_exist = (
                "cannot open database" in err_low or
                "requested by the login" in err_low or
                " does not exist" in err_low or
                "4060" in err_low or
                ("无法打开登录所请求的数据库" in err_raw) or
                ("数据库" in err_raw and ("不存在" in err_raw or "未找到" in err_raw))
        )
        if db_not_exist:
            # 按你的期望文案返回
            raise AppDBConnectError(400, "数据源或数据库不存在，请检查连接信息")

        # === ② 登录失败（如 18456 / “login failed”） ===
        if "login failed" in err_low or "18456" in err_low or "登录失败" in err_raw:
            raise AppDBConnectError(400, "用户名或密码错误，请检查后重试")

        # === ②.1 密码认证失败（PostgreSQL/MySQL 等） ===
        if ("password authentication failed" in err_low or
                "password failed" in err_low or
                "authentication failed" in err_low or
                "access denied for user" in err_low or
                ("access denied" in err_low and "password" in err_low) or
                "密码错误" in err_raw or
                "认证失败" in err_raw):
            raise AppDBConnectError(400, "用户名或密码错误，请检查后重试")

        # === ②.2 MySQL 特定错误 ===
        if "unknown database" in err_low:
            # MySQL 错误码 1049：数据库不存在
            raise AppDBConnectError(400, "数据库不存在，请检查数据库名称是否正确")
        if ("can't connect to mysql" in err_low or
                "10061" in err_low or  # Windows: 由于目标计算机积极拒绝，无法连接
                "10060" in err_low or  # Windows: 由于连接超时，无法连接
                "lost connection to mysql" in err_low):
            raise AppDBConnectError(400, "数据库服务器无法访问，请检查主机地址和端口是否正确")
        if "host is blocked" in err_low:
            raise AppDBConnectError(400, "数据库连接被拒绝，该主机已被阻止，请稍后重试或联系管理员")
        if "too many connections" in err_low:
            raise AppDBConnectError(400, "数据库连接数已满，请稍后重试")

        # === ②.3 Oracle 特定错误（ORA-xxxxx） ===
        if ("ora-12154" in err_low or  # TNS: 无法解析指定的连接标识符
                "ora-12541" in err_low or  # TNS: 无监听器
                "ora-12505" in err_low or  # TNS: 监听程序无法识别 SID
                "ora-12170" in err_low):  # TNS: 连接超时
            raise AppDBConnectError(400, "Oracle 数据库无法访问，请检查主机地址和端口是否正确")
        if "ora-01017" in err_low:  # 无效的用户名/密码
            raise AppDBConnectError(400, "用户名或密码错误，请检查后重试")
        if "ora-28000" in err_low:  # 账户被锁定
            raise AppDBConnectError(400, "Oracle 账户已被锁定，请联系数据库管理员解锁")

        # === ②.4 SQLite 特定错误 ===
        if "file is not a database" in err_low:
            raise AppDBConnectError(400, "SQLite 数据库文件已损坏或不是有效的数据库文件")
        if "unable to open database file" in err_low:
            raise AppDBConnectError(400, "SQLite 数据库文件无法访问，请检查文件路径是否正确")
        if "disk i/o error" in err_low:
            raise AppDBConnectError(400, "SQLite 数据库磁盘读写错误，请检查磁盘空间和文件权限")

        # === ②.5 达梦 DM 特定错误 ===
        # 达梦错误码格式：-6602/-7001 等，错误信息包含中文
        if ("dm" in err_low or "dameng" in err_low) and ("用户名" in err_raw or "密码" in err_raw or "password" in err_low):
            raise AppDBConnectError(400, "用户名或密码错误，请检查后重试")
        if "网络通信" in err_raw or "-7001" in err_low or "-6602" in err_low:
            # -6602: 网络包错误；-7001: 连接中断
            raise AppDBConnectError(400, "达梦数据库服务器无法访问，请检查主机地址和端口是否正确")
        if "-2502" in err_low or "无效的用户名" in err_raw or "invalid username" in err_low:
            raise AppDBConnectError(400, "用户名或密码错误，请检查后重试")
        if "-2511" in err_low or "账户已被锁定" in err_raw or "account is locked" in err_low:
            raise AppDBConnectError(400, "达梦账户已被锁定，请联系数据库管理员解锁")
        if "-1424" in err_low or "无效的连接" in err_raw:
            raise AppDBConnectError(400, "达梦数据库服务器无法访问，请检查主机地址和端口是否正确")
        if "-5105" in err_low or "对象不存在" in err_raw:
            raise AppDBConnectError(400, "达梦数据库对象不存在，请检查连接信息")

        # === ②.5 Trino 特定错误 ===
        if "trino requires authentication" in err_low:
            raise AppDBConnectError(400, "Trino 需要认证，请检查认证信息是否正确")
        if ("trino" in err_low and
                ("connection refused" in err_low or "timeout" in err_low or "connection fail" in err_low)):
            raise AppDBConnectError(400, "Trino 服务器无法访问，请检查主机地址和端口是否正确")

        # === ③ Oracle版本不支持（DPY-3010: Oracle 11g需要thick模式） ===
        if "dpy-3010" in err_low or "not supported by python-oracledb in thin mode" in err_low:
            raise AppDBConnectError(400,
                                    "Oracle数据库版本过低（11g），需要安装Oracle Instant Client。请联系管理员或使用Oracle 12.1+版本")

        # === ④ 网络/实例/端口异常或超时 ===
        if ("timeout" in err_low or "timed out" in err_low or
                "could not open a connection" in err_low or
                "a network-related or instance-specific error" in err_low or
                "server does not exist" in err_low or
                "connection refused" in err_low or
                "socket is not connected" in err_low or
                "超时" in err_raw or "无法连接" in err_raw):
            raise AppDBConnectError(400, "数据库服务器无法访问，请检查主机地址和端口是否正确")

        # === ⑤ 兜底（输出详细错误信息用于调试）===
        import traceback
        print(f"[DEBUG] OperationalError详情: {type(oe).__name__}: {str(oe)}")
        print(f"[DEBUG] 原始错误: {err_raw}")
        print(f"[DEBUG] 完整堆栈:\n{traceback.format_exc()}")
        raise AppDBConnectError(400, f"数据库连接失败: {err_raw[:200]}")

    except InterfaceError as ie:
        # 典型：ODBC 驱动未安装/未指定（IM002 等）
        err_raw = str(getattr(ie, "orig", ie))
        err_low = err_raw.lower()
        import traceback
        print(f"[DEBUG] InterfaceError详情: {type(ie).__name__}: {str(ie)}")
        print(f"[DEBUG] 原始错误: {err_raw}")
        print(f"[DEBUG] 完整堆栈:\n{traceback.format_exc()}")

        if ("im002" in err_low or "no default driver" in err_low or
                "未发现数据源名称" in err_raw or "未指定默认驱动程序" in err_raw):
            raise AppDBConnectError(400,
                                    "ODBC 驱动未安装或未指定。请在服务器安装 Microsoft ODBC Driver 17/18 for SQL Server，或在连接中指定 driver 参数")
        raise AppDBConnectError(400, f"数据库接口错误: {err_raw[:200]}")

    except AssertionError as ae:
        # 典型：KingBase 等兼容 PostgreSQL 的数据库，SQLAlchemy 无法识别版本字符串
        # 例如：AssertionError: Could not determine version from string 'KingbaseES V009R001C010'
        err_raw = str(ae)
        import traceback
        print(f"[DEBUG] AssertionError详情: {str(ae)}")
        print(f"[DEBUG] 完整堆栈:\n{traceback.format_exc()}")

        # 检查是否是 KingBase 版本识别问题
        if "could not determine version" in err_raw.lower() and "kingbase" in connection_string_str.lower():
            raise AppDBConnectError(400,
                                    "数据库版本识别失败，数据库可能不完全兼容 PostgreSQL 协议。"
                                    "请确认 KingBase 版本支持 PostgreSQL 兼容模式，或联系管理员检查数据库配置。")

        # 其他 AssertionError，输出友好信息
        raise AppDBConnectError(400, f"数据库连接失败: {err_raw[:200]}")

    except NoSuchModuleError as nsme:
        # 典型：Can't load plugin: sqlalchemy.dialects:kingbase.ksycopg2
        err_raw = str(nsme)
        import traceback
        print(f"[DEBUG] NoSuchModuleError详情: {type(nsme).__name__}: {err_raw}")
        print(f"[DEBUG] 完整堆栈:\n{traceback.format_exc()}")

        # 提取驱动名称
        driver_name = None
        import re
        match = re.search(r"sqlalchemy\.dialects:(\w+)\.(\w+)", err_raw)
        if match:
            driver_name = match.group(2)
        else:
            # 尝试匹配 "No module named 'xxx'"
            match = re.search(r"module named '(\w+)'", err_raw)
            if match:
                driver_name = match.group(1)

        # 技术原因提示映射
        technical_hints = {
            "pymysql": "MySQL 数据库连接失败",
            "psycopg": "PostgreSQL 数据库连接失败",
            "psycopg2": "PostgreSQL 数据库连接失败",
            "pyodbc": "SQL Server 数据库连接失败",
            "oracledb": "Oracle 数据库连接失败",
            "mysqlconnector": "MySQL 数据库连接失败",
            "pymssql": "SQL Server 数据库连接失败",
            "cx_oracle": "Oracle 数据库连接失败",
            "sqlite3": "SQLite 数据库连接失败",
            # 人大金仓 KingBase
            "ksycopg2": "人大金仓 KingBase 数据库连接失败",
            "kingbase": "人大金仓 KingBase 数据库连接失败",
        }

        if driver_name:
            base_msg = technical_hints.get(driver_name.lower(), "数据库连接失败")
            hint = f"{base_msg}，可能是数据库服务配置问题，请联系管理员检查服务器配置"
        else:
            hint = "数据库驱动未安装或不可用，请联系管理员检查服务器配置"

        raise AppDBConnectError(400, hint)

    except Exception as e:
        import traceback
        print(f"[DEBUG] 连接异常详情: {type(e).__name__}: {str(e)}")
        print(f"[DEBUG] 完整堆栈:\n{traceback.format_exc()}")
        raise AppDBConnectError(500, f"数据库连接异常: {str(e)}")


def _infer_db_name(db_type: str, connect_info: str) -> str | None:
    url = make_url(connect_info)
    dbt = (db_type or "").lower()
    if dbt == "oracle":
        # 约定：Oracle 用“OWNER（用户名大写）”作为 database_name
        return (url.username or "").upper()
    elif dbt == "dm":
        # 达梦：用用户名大写作为 database_name（与 Oracle 一致，因为达梦默认 schema = 用户名）
        # 如果用户传了 target_schema，则用 target_schema
        return (url.username or "").upper()
    elif dbt in ("postgresql", "mysql", "mssql", "kingbase"):
        return url.database
    elif dbt == "sqlite":
        return url.database or ":memory:"
    elif dbt == "trino":
        # Trino 的 database 字段是 catalog/schema 格式，提取 catalog 部分
        db = url.database or ""
        return db.split("/")[0] if "/" in db else db
    return url.database


# ================== 跨方言 schema_name 计算 / 关联过滤（统一封装） ==================
# 这些数据库类型属于"同一 connect_info 不同 schema 必须视为不同数据源"
# MySQL/Trino/SQLite 的 schema/database 已体现在 connect_info 中，无需 schema 维度去重
SCHEMA_AWARE_DB_TYPES = {"postgresql", "mssql", "oracle", "kingbase", "dm"}


def _resolve_schema_name(db_type: Optional[str],
                         db_payload: Optional[Dict[str, Any]],
                         connection_string_str: Optional[str] = None) -> Optional[str]:
    """
    根据 db_type 和入参计算"该数据源对应的 schema_name"。
    用于:
      - datasource_infos.schema_name 写入
      - user_datasource_schemas.schema_name 写入
      - 所有"按 (user_id, connect_info) 关联"的查询按 db_type 加上 schema_name 过滤

    输入:
      db_type: 数据库类型（postgres/mssql/oracle/trino/mysql/sqlite 等任意大小写）
      db_payload: 前端传来的连接入参 dict（应包含 schema / target_schema / database 等字段）
      connection_string_str: 原始连接串（仅作为兜底，便于日志/兼容）

    输出:
      - PostgreSQL/MSSQL: payload.schema 或默认 "public" / "dbo"
      - Oracle: payload.target_schema 或 username.upper()
      - Trino: payload.schema（必填，未填返回 None）
      - MySQL: payload.database（仅用于 UI 展示和 schema 字段冗余，非用于去重键）
      - 其他: None
    """
    dbt = (db_type or "").lower() if db_type else ""
    payload = db_payload or {}

    if dbt == "postgresql" or dbt == "kingbase":
        return payload.get("schema") or "public"
    if dbt == "mssql":
        return payload.get("schema") or "dbo"
    if dbt == "oracle":
        # 优先使用 target_schema（用户指定的 schema），否则使用 username（默认行为）
        ts = payload.get("target_schema")
        if ts:
            return ts
        un = payload.get("username")
        if un:
            return str(un).upper()
        return None
    if dbt == "dm":
        # 达梦与 Oracle 行为类似：默认 schema 等于用户名大写
        # 同时支持通过 schema 或 target_schema 字段显式指定其他模式
        ts = payload.get("target_schema") or payload.get("schema")
        if ts:
            return str(ts).upper()
        un = payload.get("username")
        if un:
            return str(un).upper()
        return None
    if dbt == "trino":
        # trino 的 schema 必填（你 REQUIRED_RULES 就要求 schema）:contentReference[oaicite:1]{index=1}
        return payload.get("schema")
    if dbt == "mysql":
        # mysql 没 schema，schema_name 这里可存数据库名，方便 UI 展示统一
        return payload.get("database")
    if dbt == "oceanbase":
        # OceanBase MySQL 模式租户：与 MySQL 行为一致，无 schema 分离维度
        # schema_name 直接存 database_name，便于 UI 展示和数据库内一致性
        return payload.get("database")
    # sqlite / 其它
    return None


def _add_schema_filter(query, db_type: Optional[str], schema_name: Optional[str]):
    """
    给"按 (user_id, connect_info) 关联 user_datasource_schemas"的 query 加上 schema_name 过滤。
    仅对"按 schema 区分的数据库"（PG/MSSQL/Oracle）做严格匹配，其他数据库不加此过滤。

    设计原则:
      - 对于 PG/MSSQL/Oracle：必须按 schema_name 严格匹配，避免误删/误改同 connect_info 不同 schema 的数据
      - 对于 MySQL/Trino/SQLite：不加 schema_name 过滤（保持原有按 (user_id, connect_info) 的行为）
      - 对于 db_type 未知或空：默认不加 schema_name 过滤（保守，保持兼容）

    输入:
      query: 已构造的 SQLAlchemy Query 对象（通常是 db.session.query(UserDatasourceSchema).filter(...)）
      db_type: 数据库类型字符串
      schema_name: 该数据源的 schema_name（可能为 None）

    输出:
      加上 schema_name 过滤后的 query 对象
    """
    dbt = (db_type or "").lower() if db_type else ""
    if dbt in SCHEMA_AWARE_DB_TYPES and schema_name is not None:
        return query.filter(UserDatasourceSchema.schema_name == schema_name)
    # 其他类型不增加 schema_name 过滤
    return query


def _has_schema_dim(db_type: Optional[str]) -> bool:
    """判断该 db_type 是否需要 schema 维度做去重 / 关联。"""
    dbt = (db_type or "").lower() if db_type else ""
    return dbt in SCHEMA_AWARE_DB_TYPES


# 数据源信息入库
def upsert_datasource_info(user_id: str,
                           connect_info: str,
                           connect_name: str,
                           db_type: str,
                           database_name: str,
                           status: str = "available",
                           schema_name: str = None,
                           catalog_type: str = None):
    """
    聚合更新数据源信息表 datasource_info
    - 若不存在：新建记录
    返回：(记录 dict, created 标记)

    注意：重复添加的校验已在接口入口处完成（相同 connect_name 拒绝；相同 connect_info +
          schema_name 组合按 db_type 分支拒绝），此函数只处理新建场景，不会走到"已存在"的分支。
    """

    # 统一兜底：如果没传或传了空，就从 connect_info 推断
    if not database_name:
        database_name = _infer_db_name(db_type, connect_info) or ""

    # 计算连接信息哈希值（用于稳定匹配）和加密值（用于存储）
    connect_info_hash = get_connect_info_hash(connect_info)
    encrypted_connect_info = encrypt_connect_info(connect_info)

    # 聚合统计表数量（按 db_type 决定是否带 schema_name 过滤）
    # 使用 connect_info_hash 进行匹配（因为加密值每次不同）
    base_schema_query = db.session.query(
        func.count(distinct(UserDatasourceSchema.table_name))
    ).filter_by(
        user_id=str(user_id),
        connect_info_hash=connect_info_hash
    )
    schema_query = _add_schema_filter(base_schema_query, db_type, schema_name)
    table_count = schema_query.scalar() or 0

    # 查询是否已存在（按 db_type 分支决定是否带 schema_name）
    # 注：DatasourceInfo 的 schema_name 字段就是该记录的特征维度
    existing_query = db.session.query(DatasourceInfo).filter_by(
        user_id=str(user_id),
        connect_info=encrypted_connect_info
    )
    if _has_schema_dim(db_type):
        # 与 schema_name 同时去重（PG/MSSQL/Oracle）
        if schema_name is None:
            schema_name = _resolve_schema_name(db_type, {"connect_info": connect_info}, connect_info)
        existing_query = existing_query.filter(DatasourceInfo.schema_name == schema_name)
    existing = existing_query.one_or_none()

    now = datetime.now(timezone.utc)
    created = False  # 是否新建标记

    # —— 理论上不会走到 existing 分支，因为入口已校验重复添加，此处仅作安全兜底 ——
    if existing:
        existing_name = existing.connect_name or "<未知>"
        schema_hint = f"（schema：{schema_name}）" if _has_schema_dim(db_type) and schema_name else ""
        raise ValueError(f"数据源已存在{schema_hint}（名称：{existing_name}），重复添加")
    # 创建新记录
    new_info = DatasourceInfo(
        id=uuid.uuid4(),  # 防止数据库层无默认值时报错
        user_id=str(user_id),
        connect_info=encrypted_connect_info,  # 复用之前计算的加密值
        connect_info_hash=connect_info_hash,  # 稳定哈希值用于关联匹配
        connect_name=connect_name,
        db_type=db_type,
        database_name=database_name,
        schema_name=schema_name,
        table_num=table_count,
        status=status,
        catalog_type=catalog_type,  # 新增 catalog_type 字段
        created_at=now,
        updated_at=now
    )
    db.session.add(new_info)
    db.session.flush()  # 立即生成 id
    target = new_info
    created = True

    # 提交事务
    db.session.commit()
    print(f"[数据源添加] [OK] 事务提交成功")

    # 序列化输出（带 op 标识）
    info_dict = target.to_dict()
    info_dict["op"] = "created" if created else "updated"

    return info_dict, created


# 接口响应结果封装
def format_response(data=None, code=200, msg="操作成功"):
    """
    统一响应结构：{code:int, msg:str, data:any}
    """
    return {"code": code, "msg": msg, "data": _deep_json_safe(data)}, code


# 获取数据源中的所有表名列表
class ListTablesAPI(Resource):
    @login_required
    def post(self):
        """
        获取数据源中的所有表和视图列表（不提取结构，用于前端展示让用户选择）

        参数:
            与 /extract_schema 保持一致（含 connect_name）

        返回:
            成功：{"code":200, "msg":"success", "result":{"tables":[...], "total":N}}
            失败：{"code":4xx/500, "msg":"...", "result": None}
        """
        payload = request.get_json() or {}

        connect_name = payload.get("connect_name")
        if not connect_name or not str(connect_name).strip():
            return {"code": 400, "msg": "缺少必填字段：connect_name", "result": None}, 400

        engine = None
        try:
            connection_string_URL = build_db_url_from_json(payload)
            connection_string_str = _to_raw_conn_str(connection_string_URL)
            db_type = payload.get("db_type")

            engine = get_db_engine(connection_string_str, db_type=db_type)
            inspector = inspect(engine)

            tables = get_tables(inspector, engine, payload)

            return {
                "code": 200,
                "msg": "success",
                "result": {
                    "tables": tables,
                    "total": len(tables)
                }
            }, 200

        except AppDBConnectError as e:
            return {"code": e.code, "msg": e.msg, "result": None}, e.code

        except (OperationalError, InterfaceError) as db_err:
            err_msg = str(db_err)
            err_lower = err_msg.lower()
            if "socket is not connected" in err_lower or "connection refused" in err_lower:
                return {"code": 400, "msg": "数据库服务器无法访问，请检查主机地址和端口是否正确", "result": None}, 400
            if "timeout" in err_lower or "timed out" in err_lower:
                return {"code": 400, "msg": "连接响应超时，请检查网络状况及服务器可访问后重试", "result": None}, 400
            if "password authentication failed" in err_lower or "password failed" in err_lower or \
                    "authentication failed" in err_lower or "access denied" in err_lower or "login failed" in err_lower:
                return {"code": 400, "msg": "用户名或密码错误，请检查后重试", "result": None}, 400
            friendly_msg = _get_friendly_error_message(db_err)
            return {"code": 400, "msg": friendly_msg, "result": None}, 400

        except ValueError as e:
            return {"code": 400, "msg": f"连接参数错误: {str(e)}", "result": None}, 400

        except ModuleNotFoundError as e:
            driver_name = _extract_driver_name(str(e))
            hint = _get_driver_install_hint(driver_name)
            return {"code": 400, "msg": hint, "result": None}, 400

        except Exception as e:
            print(f"[ERROR] ListTablesAPI 异常: {str(e)}")
            print(traceback.format_exc())
            friendly_msg = _get_friendly_error_message(e)
            return {"code": 500, "msg": friendly_msg, "result": None}, 500

        finally:
            if engine is not None:
                try:
                    engine.dispose()
                except Exception:
                    pass


# 传入数据库连接url，提取库中的所有表结构数据
class ExtractSchemaAPI(Resource):
    @login_required
    def post(self):
        """
        从数据库提取结构信息并输出为JSON

        参数:
            connection_string: 数据库连接字符串
            request_id: 可选，前端生成的唯一请求ID，用于支持取消操作

        返回:
            成功时返回数据库结构字典，失败时返回错误信息
        """

        # 解析请求参数，获取连接配置信息（含必填和问号传参：若不在必填内则匹配进问号处传参中）
        db_connect_info_payload = request.get_json()

        # 获取请求ID（前端传来的唯一标识）
        request_id = (db_connect_info_payload or {}).get("request_id")

        # 如果有 request_id，记录请求状态为 processing
        if request_id:
            request_status_manager.set_status(request_id, "processing")
            print(f"[REQUEST] 开始处理请求 {request_id}")

        # 获取数据源名称
        connect_name = (db_connect_info_payload or {}).get("connect_name")
        if not connect_name or not str(connect_name).strip():
            if request_id:
                request_status_manager.set_status(request_id, "failed")
            return format_response(None, 400, "缺少必填字段：connect_name")

        # 获取数据盘查参数
        # [已移除] 数据盘查功能已迁移至治理规则库模块
        # is_audit = bool((db_connect_info_payload or {}).get("is_audit", False))
        # print(f"[INFO] 数据盘查参数 is_audit: {is_audit}")

        # 获取真实数据库连接字符串
        print("用户输入的参数为:", str(db_connect_info_payload))
        connection_string_URL = build_db_url_from_json(
            db_connect_info_payload)  # URL，SQLAlchemy 的 URL 默认会在 str(URL) 时隐藏密码。同样 engine.url 的 __str__ 也会隐藏。
        connection_string_str = _to_raw_conn_str(connection_string_URL)  # 原始字符串，不脱敏
        print("数据库连接串为:", connection_string_str)
        safe_connection_string = make_url(connection_string_URL).render_as_string(
            hide_password=True)  # 脱敏串，str，用以入库和日志输出
        print("日志脱敏串为:", safe_connection_string)  # 用以日志脱敏

        # ===== 提前计算 db_type / schema_name（用于去重校验）=====
        # 注：必须先于去重校验，避免 schema_name 还没算出来就去查重
        db_type_raw = (db_connect_info_payload.get("dbType")
                       or db_connect_info_payload.get("db_type")
                       or "").lower()
        current_schema_name = _resolve_schema_name(
            db_type_raw, db_connect_info_payload, connection_string_str
        )
        print(f"[数据源添加] db_type={db_type_raw}, schema_name={current_schema_name}")

        # ===== 重复添加校验 =====
        # 规则（按需求）：
        #   1) 同用户的 connect_name 全局唯一
        #   2) 同用户的 (connect_info, schema_name) 按 db_type 分支判断：
        #      - PG/MSSQL/Oracle: 相同 (connect_info, schema_name) 视为同一数据源，禁止重复
        #      - MySQL/Trino/SQLite: 相同 (connect_info) 视为同一数据源，禁止重复
        user_id_str = str(flask_login.current_user.id)

        # 1) connect_name 唯一性
        existing_by_name = db.session.query(DatasourceInfo).filter_by(
            user_id=user_id_str,
            connect_name=connect_name
        ).one_or_none()
        if existing_by_name:
            error_msg = f"数据源名称「{connect_name}」已被占用，请换一个名称"
            print(f"[数据源添加] 拒绝重复添加: {error_msg}")
            if request_id:
                request_status_manager.set_status(request_id, "failed")
            return format_response(None, 409, error_msg)

        # 2) (connect_info, schema_name) 唯一性（按 db_type 分支）
        # 注意：数据库中存储的是加密后的 connect_info，查询时需要加密后再比较
        encrypted_connect_info = encrypt_connect_info(connection_string_str)
        existing_datasource_query = db.session.query(DatasourceInfo).filter_by(
            user_id=user_id_str,
            connect_info=encrypted_connect_info
        )
        if _has_schema_dim(db_type_raw):
            # PG/MSSQL/Oracle: 必须把 schema_name 加入 WHERE
            # 注意：schema_name 来自 resolve_schema_name，已经按 db_type 规则（Oracle 大写等）归一化
            if current_schema_name is None:
                # PG/MSSQL/Oracle 的 schema_name 不应为空（否则会去重失败抛 value error）。
                # 这种情况视为"用户没有指定 schema"，按兜底逻辑给一个标记值去查
                existing_datasource_query = existing_datasource_query.filter(
                    DatasourceInfo.schema_name.is_(None)
                )
            else:
                existing_datasource_query = existing_datasource_query.filter(
                    DatasourceInfo.schema_name == current_schema_name
                )
        # MySQL/Trino/SQLite: 仅按 connect_info 去重，无 schema_name 维度

        existing_datasource = existing_datasource_query.one_or_none()
        if existing_datasource:
            # 数据源已存在，拒绝添加
            schema_hint = f"，schema：{current_schema_name}" if (_has_schema_dim(db_type_raw) and current_schema_name) else ""
            error_msg = (
                f"该数据源连接已存在"
                f"{schema_hint}（名称：{existing_datasource.connect_name}）。"
                f"如需更换名称，请前往设置修改，而非重新添加。"
            )
            print(f"[数据源添加] 拒绝重复添加: {error_msg}")
            if request_id:
                request_status_manager.set_status(request_id, "failed")
            return format_response(None, 409, error_msg)
        # ===== 重复添加校验结束 =====

        # 同步更新 db_connect_info_payload 中的 schema 默认值（如果在 build_db_url_from_json 中设置了默认值）
        if not db_connect_info_payload.get("schema"):
            db_type_from_payload = (db_connect_info_payload.get("dbType") or db_connect_info_payload.get("db_type") or "").lower()
            if db_type_from_payload == "postgresql" or db_type_from_payload == "kingbase":
                db_connect_info_payload["schema"] = "public"
                print(f"[DEBUG] 同步设置 {db_type_from_payload} schema 默认值: public")
            elif db_type_from_payload == "mssql":
                db_connect_info_payload["schema"] = "dbo"
                print(f"[DEBUG] 同步设置 MSSQL schema 默认值: dbo")

        # 获取数据库引擎
        try:
            engine = get_db_engine(connection_string_str, db_type=db_type_raw)
        except AppDBConnectError as e:
            # 统一友好返回
            if request_id:
                request_status_manager.set_status(request_id, "failed")
            return format_response(None, e.code, e.msg)

        try:
            # 检查请求是否已被取消
            if request_id and request_status_manager.is_cancelled(request_id):
                print(f"[CANCELLED] 请求 {request_id} 已被取消")
                return format_response(None, 499, "请求已取消")

            # --- 公共流程（放在 try/except 之后） ---
            inspector = inspect(engine)

            # 如果是 KingBase/OceanBase 等特殊数据库（SQLAlchemy dialect 名与用户传入类型不一致），
            # 返回原始传入的 db_type，而不是 engine.dialect.name
            if db_type_raw in ("kingbase", "oceanbase"):
                dialect_name_for_return = db_type_raw
            else:
                dialect_name_for_return = str(engine.dialect.name)

            database_info = {
                "database_type": dialect_name_for_return,
                "database_version": _get_database_version(engine),
                "generated_at": datetime.utcnow().isoformat(),
                "schema_name": current_schema_name,  # 新增：传递 schema_name 用于数据卡片生成时的过滤
                "tables": []
            }

            # 获取所有表名（对于MySQL，返回字典列表；对于其他数据库，返回字符串列表）
            tables = get_tables(inspector, engine, db_connect_info_payload)
            print("tables =", tables)

            # 新增：过滤指定表（如果用户指定了 table_names）
            selected_tables = (db_connect_info_payload or {}).get("table_names", [])
            if selected_tables:
                if isinstance(selected_tables, str):
                    selected_tables = [s.strip() for s in selected_tables.split(",") if s.strip()]
                print(f"[INFO] 用户指定抽取 {len(selected_tables)} 个表: {selected_tables}")
                tables = [
                    t for t in tables
                    if (t.get("name") if isinstance(t, dict) else t) in selected_tables
                ]
                print(f"[INFO] 过滤后剩余 {len(tables)} 个表")

            # 检查请求是否已被取消
            if request_id and request_status_manager.is_cancelled(request_id):
                print(f"[CANCELLED] 请求 {request_id} 在获取表名后被取消")
                return format_response(None, 499, "请求已取消")

            # 选择 schema（按方言）
            dialect = engine.dialect.name.lower()
            if dialect == "oracle":
                # 优先使用 target_schema（用户指定的 schema），否则使用 username（默认行为）
                target_schema = (db_connect_info_payload.get("target_schema") or db_connect_info_payload.get("username") or "").upper()
            elif dialect == "dm":
                # 达梦 DM：与 Oracle 类似，target_schema / schema 优先，否则使用 username 大写
                target_schema = (
                    db_connect_info_payload.get("target_schema")
                    or db_connect_info_payload.get("schema")
                    or db_connect_info_payload.get("username")
                    or ""
                ).upper()
            elif dialect == "mysql":
                target_schema = db_connect_info_payload.get("database")
            elif dialect == "postgresql" or dialect == "kingbase":
                target_schema = db_connect_info_payload.get("schema") or "public"
            elif dialect == "mssql":
                target_schema = db_connect_info_payload.get("schema") or "dbo"
            elif dialect == "trino":
                target_schema = db_connect_info_payload.get("schema")
            else:
                target_schema = None

            # 处理表和视图列表
            for tbl_item in tables:
                # 在提取每个表之前检查是否已取消
                if request_id and request_status_manager.is_cancelled(request_id):
                    print(f"[CANCELLED] 请求 {request_id} 在提取表结构时被取消")
                    return format_response(None, 499, "请求已取消")

                # 统一处理：所有数据库现在都返回字典格式 {"name": "table_name", "type": "TABLE" 或 "VIEW"}
                # 保留字符串兼容处理，以防万一
                if isinstance(tbl_item, dict):
                    table_name = tbl_item.get("name")
                    table_type = tbl_item.get("type", "TABLE")
                    is_view = (table_type == "VIEW")
                else:
                    # 兼容旧格式：字符串（表名）- 理论上不应该走到这里
                    table_name = tbl_item
                    is_view = False

                if not table_name:
                    continue

                # Oracle 表名大小写容错处理
                # 保存原始表名（从 get_tables 返回的实际表名）
                original_table_name = table_name

                # 对于 Oracle，先尝试使用原始表名，失败后再尝试大写表名
                dialect_name = (inspector.bind.dialect.name or "").lower()
                table_info = None

                if dialect_name == "oracle":
                    # 策略：先尝试原始表名（可能是小写的带引号创建的表）
                    try:
                        table_info = _extract_table_info(inspector, original_table_name, schema=target_schema, is_view=is_view)
                    except NoSuchTableError:
                        # 如果失败且表名不是全大写，尝试使用大写表名（Oracle默认行为）
                        if original_table_name != original_table_name.upper():
                            try:
                                table_info = _extract_table_info(inspector, original_table_name.upper(), schema=target_schema, is_view=is_view)
                            except NoSuchTableError:
                                # 两种方式都失败，抛出异常
                                raise
                        else:
                            # 表名已经是大写，直接抛出异常
                            raise
                else:
                    # 非 Oracle 数据库，直接使用原始表名
                    table_info = _extract_table_info(inspector, original_table_name, schema=target_schema, is_view=is_view)

                # 关键：确保返回的 table_info 中的 table_name 是原始表名
                if table_info:
                    table_info["table_name"] = original_table_name

                database_info["tables"].append(table_info)

            # 表结构数据批量入库
            rs_body, rs_status = insert_table_info_to_db(
                database_info,
                flask_login.current_user.id,
                connection_string_str,
                connect_name,
                request_id,
                db_connect_info_payload=db_connect_info_payload,
                schema_name=current_schema_name,  # 新增：传 schema_name 用于写入与去重
            )

            # 重复数据源异常处理：若 insert_table_info_to_db 返回 {"error": "该数据源已存在"}, 409
            if rs_status == 409 and isinstance(rs_body, dict) and rs_body.get("error") == "该数据源已存在":
                # 直接返回给前端
                if request_id:
                    request_status_manager.set_status(request_id, "failed")
                return format_response(None, 409, "该数据源已存在")

            # 只要非 200 且 message 也不是 success，就直接返回错误，避免写 datasource_info
            if not (rs_status == 200 or (isinstance(rs_body, dict) and rs_body.get("message") == "success")):
                if request_id:
                    request_status_manager.set_status(request_id, "failed")
                return format_response(None, rs_status, rs_body.get("error", "表结构入库失败"))

            # 检查请求是否已被取消
            if request_id and request_status_manager.is_cancelled(request_id):
                print(f"[CANCELLED] 请求 {request_id} 在入库后被取消")
                return format_response(None, 499, "请求已取消")

            # 成功后更新数据源摘要信息
            # 满足"写表成功"的判定后，才 upsert datasource_info
            # 获取 catalog_type（仅 Trino 需要）
            current_catalog_type = None
            current_db_type = (db_connect_info_payload.get("dbType")
                               or db_connect_info_payload.get("db_type")
                               or str(engine.dialect.name))
            if current_db_type == "trino":
                current_catalog_type = db_connect_info_payload.get("catalog")

            # 复用去重校验阶段已经算出的 schema_name（保证与去重键完全一致）
            schema_name = current_schema_name
            dbt = (current_db_type or "").lower()

            # Oracle 若传入了 target_schema，则 database_name 也保存 target_schema（概念更清晰）
            # 若无 target_schema，则传 None 让 upsert_datasource_info 使用其兜底逻辑（database_name=username）
            # 达梦 DM 与 Oracle 行为一致：target_schema 优先；否则使用 username
            oracle_database_name = None
            if (dbt == "oracle" or dbt == "dm") and (
                db_connect_info_payload.get("target_schema") or db_connect_info_payload.get("schema")
            ):
                oracle_database_name = (
                    db_connect_info_payload.get("target_schema")
                    or db_connect_info_payload.get("schema")
                )

            datasource_info, created = upsert_datasource_info(
                user_id=str(flask_login.current_user.id),
                connect_info=connection_string_str,  # 若需脱敏可改成 safe_connection_string
                connect_name=connect_name,
                db_type=current_db_type,
                database_name=oracle_database_name,
                status="available",
                schema_name=schema_name,
                catalog_type=current_catalog_type  # 传递 catalog_type
            )

            # 取消将健康检查结果写入 JSON 文件；该信息已按表写入 UserDatasourceSchema.is_filled / filled_data

            # 检查请求是否已被取消（在开始耗时的数据卡片生成前最后检查一次）
            if request_id and request_status_manager.is_cancelled(request_id):
                print(f"[CANCELLED] 请求 {request_id} 在更新数据源信息后被取消，跳过数据卡片生成")
                # 虽然表结构已入库，但跳过数据卡片生成，返回取消状态
                return format_response(None, 499, "请求已取消")

            # 初步数据卡片生成和入库
            # 注意：generate_datacards_for_schema 是耗时操作（可能需要几秒到几十秒）
            # 现在已经在函数内部添加了多个取消检查点，可以及时响应取消请求
            print(f"[INFO] 开始生成数据卡片...")
            user_class = getattr(flask_login.current_user, "weaviate_class_name", None)
            # 延迟导入，避免循环依赖
            from controllers.datacard.datacard_generator import generate_datacards_for_schema
            all_data_cards = generate_datacards_for_schema(
                database_info,
                flask_login.current_user.id,
                connection_string_str,
                connect_name,
                datasource_id=str(datasource_info.get("id")) if datasource_info else None,  # 传入 datasource_id（datasource_info 是字典）
                request_id=request_id,
                weaviate_class_name=user_class,  # 新增
            )

            # 数据卡片生成后再次检查是否已取消
            if request_id and request_status_manager.is_cancelled(request_id):
                print(f"[CANCELLED] 请求 {request_id} 在数据卡片生成后被取消")
                print(f"[WARNING] 数据卡片可能已部分入库，但主表结构数据完整")
                # 注意：此时数据卡片可能已经入库，但由于是独立的操作，不影响主流程
                return format_response(None, 499, "请求已取消")

            # 标记请求为已完成
            if request_id:
                request_status_manager.set_status(request_id, "completed")
                print(f"[REQUEST] 请求 {request_id} 处理完成")

            # 组装返回（datasource_info 一定带上，因为只有成功才会走到这里）
            data = {
                "insert_result": rs_body,
                "generated_cards": all_data_cards or [],
                "datasource_info": datasource_info
            }

            if not all_data_cards:
                print("[INFO] 没有生成任何数据名片。")
                print(f"-------------------数据卡片生成结束-------------------")
                return format_response(data, 200, "没有新的数据卡片需要生成")
            print(f"-------------------数据卡片生成成功-------------------")

            return format_response(data, 200, "提取成功")

        except RequestCancelledException as e:
            # 请求被取消，回滚数据库事务
            db.session.rollback()
            if request_id:
                request_status_manager.set_status(request_id, "cancelled")
            print(f"[CANCELLED] 请求 {request_id} 已取消，已回滚数据库事务")
            return format_response(None, 499, "请求已取消")

        except Exception as e:
            # 其他异常处理
            db.session.rollback()
            if request_id:
                request_status_manager.set_status(request_id, "failed")
            print(f"[ERROR] 请求 {request_id} 处理失败: {str(e)}")
            return format_response(None, 500, f"处理失败: {str(e)}")


# ========== 连接测试接口辅助函数 ==========
def _extract_driver_name(err_msg: str) -> str | None:
    """从错误信息中提取缺失的驱动名称"""
    import re
    # 常见驱动名称模式
    drivers = ["pymysql", "psycopg", "psycopg2", "pyodbc", "oracledb",
               "mysqlconnector", "pymssql", "cx_oracle", "sqlite3", "ksycopg2"]
    for driver in drivers:
        if driver in err_msg.lower():
            return driver
    # 尝试匹配 "No module named 'xxx'"
    match = re.search(r"module named '(\w+)'", err_msg)
    if match:
        return match.group(1)
    return None


def _get_driver_install_hint(driver_name: str | None) -> str:
    """根据驱动名称返回面向用户的友好提示（不暴露技术细节）"""
    # 技术原因提示映射 - 对用户隐藏技术实现
    technical_hints = {
        "pymysql": "MySQL 数据库连接失败",
        "psycopg": "PostgreSQL 数据库连接失败",
        "psycopg2": "PostgreSQL 数据库连接失败",
        "pyodbc": "SQL Server 数据库连接失败",
        "oracledb": "Oracle 数据库连接失败",
        "mysqlconnector": "MySQL 数据库连接失败",
        "pymssql": "SQL Server 数据库连接失败",
        "cx_oracle": "Oracle 数据库连接失败",
        "sqlite3": "SQLite 数据库连接失败",
        # 人大金仓 KingBase
        "ksycopg2": "人大金仓 KingBase 数据库连接失败"
    }

    if driver_name:
        base_msg = technical_hints.get(driver_name.lower(), "数据库连接失败")
    else:
        base_msg = "数据库连接失败"

    return f"{base_msg}，可能是数据库服务配置问题，请联系管理员检查服务器配置"


def _get_friendly_error_message(e: Exception) -> str:
    """从任意异常中提取面向用户的友好提示"""
    err_msg = str(e)
    err_lower = err_msg.lower()

    # 用户友好的错误模式匹配（按优先级排序）
    patterns = [
        # 认证/权限相关
        (["authentication failed", "password authentication failed", "permission denied",
          "access denied", "ora-01017", "ora-28000"],
         "用户名或密码错误，请检查后重试"),
        # 数据库不存在
        (["unknown database", "database '", "does not exist", "ora-1017",
          "4060", "cannot open database", "database not found"],
         "数据库不存在，请检查数据库名称是否正确"),
        # MySQL 连接相关
        (["can't connect to mysql", "10061", "10060", "lost connection to mysql",
          "host is blocked", "host is blocked due to too many"],
         "数据库服务器无法访问，请检查主机地址和端口是否正确"),
        # 连接相关
        (["connection refused", "ECONNREFUSED", "连接被拒绝"],
         "数据库服务器无法访问，请检查主机地址和端口是否正确"),
        (["host not found", "name resolution", "dns", "找不到主机", "未知的主机"],
         "无法找到数据库服务器，请检查主机地址是否正确"),
        (["network is unreachable", "网络不可达"],
         "网络连接失败，请检查网络设置"),
        (["socket is not connected", "could not send"],
         "数据库服务器无法访问，请检查主机地址和端口是否正确"),
        # Oracle TNS 错误
        (["ora-12154", "ora-12541", "ora-12505", "ora-12170"],
         "Oracle 服务器无法访问，请检查主机地址和端口是否正确"),
        # 资源相关
        (["too many connections", "connection limit", "连接数已满"],
         "数据库连接数已满，请稍后重试"),
        (["out of memory", "OOM"],
         "数据库资源不足，请联系数据库管理员"),
        # 超时
        (["timeout", "timed out", "超时"],
         "连接响应超时，请检查服务器是否可访问、网络是否通畅后重试"),
        # SSL/TLS
        (["ssl", "certificate", "tls", "ssl handshake"],
         "安全连接失败，请联系管理员检查 SSL 配置"),
        # 字符集
        (["charset", "encoding", "utf-8", "utf8", "character", "字符集"],
         "数据编码不匹配，请联系管理员检查数据库配置"),
        # SQLite 特定
        (["file is not a database"],
         "SQLite 数据库文件已损坏或不是有效的数据库文件"),
        (["unable to open database file"],
         "SQLite 数据库文件无法访问，请检查文件路径是否正确"),
        (["disk i/o error"],
         "SQLite 数据库磁盘读写错误，请检查磁盘空间和文件权限"),
        # Trino 特定
        (["trino requires authentication"],
         "Trino 需要认证，请检查认证信息是否正确"),
        (["trino", "connection refused", "timeout", "connection fail"],
         "Trino 服务器无法访问，请检查主机地址和端口是否正确"),
    ]

    for keywords, hint in patterns:
        for kw in keywords:
            if kw in err_lower:
                return hint

    # 如果没有匹配的模式，返回通用提示
    if len(err_msg) > 80:
        return "数据库连接失败，请检查连接信息是否正确"
    return f"数据库连接失败: {err_msg}"


# ========== 新增：连接测试接口 ==========
class ConnectTestAPI(Resource):
    @login_required
    def post(self):
        """
        仅测试数据库连接是否可用，不做元数据提取与入库。
        参数：与 /extract_schema 保持一致（含 connect_name）
        返回：
            成功：{"code":200, "msg":"连接成功", "result":{"database_type": "...", "database_version":"...", "connection": "<脱敏连接串>"}}
            失败：{"code":4xx/500, "msg":"...", "result": None}
        """
        payload = request.get_json() or {}

        # 与 /extract_schema 保持一致：校验 connect_name（要求“参数一致”）
        connect_name = (payload or {}).get("connect_name")
        if not connect_name or not str(connect_name).strip():
            return {"code": 400, "msg": "缺少必填字段：connect_name", "result": None}, 400

        engine = None
        try:
            # 1) 构建连接 URL（保持你原有的别名归一与必填校验）
            connection_url = build_db_url_from_json(payload)  # URL 对象（str() 会隐藏密码）
            raw_conn_str = _to_raw_conn_str(connection_url)  # 原始字符串（不脱敏）
            safe_conn_str = make_url(connection_url).render_as_string(hide_password=True)  # 脱敏串

            # 提取原始 db_type 用于返回
            original_db_type = (payload.get("dbType") or payload.get("db_type") or "").lower()

            # 2) 建立 Engine 并立即试连（与你的 get_db_engine 保持一致的分类错误）
            engine = get_db_engine(raw_conn_str, db_type=original_db_type)

            # 3) 读取版本信息以辅助定位（不影响成功/失败判断）
            # 如果是 KingBase/OceanBase/达梦 等特殊数据库（SQLAlchemy dialect 名与用户传入类型不一致），
            # 返回原始传入的 db_type，而不是 engine.dialect.name
            if original_db_type in ("kingbase", "oceanbase", "dm"):
                db_type = original_db_type
            else:
                db_type = str(engine.dialect.name)
            db_ver = _get_database_version(engine)

            return {
                "code": 200,
                "msg": "连接成功",
                "result": {
                    "database_type": db_type,
                    "database_version": db_ver,
                    "connection": safe_conn_str
                }
            }, 200

        except AppDBConnectError as e:
            print(f"[DEBUG] AppDBConnectError: {e.msg}")
            print(f"[DEBUG] 完整堆栈:\n{traceback.format_exc()}")
            return {"code": e.code, "msg": e.msg, "result": None}, e.code

        except (OperationalError, InterfaceError) as db_err:
            # 捕获 SQLAlchemy 的数据库连接错误（包括 psycopg/psycopg2 等驱动抛出的错误）
            err_msg = str(db_err)
            print(f"[DEBUG] Database Error: {type(db_err).__name__}: {err_msg}")
            print(f"[DEBUG] 完整堆栈:\n{traceback.format_exc()}")

            # 尝试提取底层驱动错误
            orig_err = getattr(db_err, "orig", db_err)
            if orig_err and orig_err != db_err:
                err_msg = str(orig_err)
            err_lower = err_msg.lower()

            # 根据错误类型返回友好提示
            if "socket is not connected" in err_lower or "connection refused" in err_lower:
                return {"code": 400,
                        "msg": "数据库服务器无法访问，请检查主机地址和端口是否正确",
                        "result": None}, 400
            if "timeout" in err_lower or "timed out" in err_lower:
                return {"code": 400,
                        "msg": "连接响应超时，请检查网络状况及服务器可访问后重试",
                        "result": None}, 400
            if ("password authentication failed" in err_lower or
                    "password failed" in err_lower or
                    "authentication failed" in err_lower or
                    "access denied for user" in err_lower or
                    "login failed" in err_lower or
                    "18456" in err_lower):
                return {"code": 400,
                        "msg": "用户名或密码错误，请检查后重试",
                        "result": None}, 400

            # 兜底
            friendly_msg = _get_friendly_error_message(db_err)
            return {"code": 400, "msg": friendly_msg, "result": None}, 400

        except ValueError as e:
            # 参数校验错误（如必填字段缺失、字段格式错误）
            err_msg = str(e)
            print(f"[DEBUG] ValueError 参数校验错误: {err_msg}")
            print(f"[DEBUG] 完整堆栈:\n{traceback.format_exc()}")
            return {"code": 400, "msg": f"连接参数错误: {err_msg}", "result": None}, 400

        except ModuleNotFoundError as e:
            # 驱动未安装（如 pymysql、psycopg、oracledb 等）
            err_msg = str(e)
            driver_name = _extract_driver_name(err_msg)
            print(f"[DEBUG] ModuleNotFoundError 驱动缺失: {err_msg}")
            print(f"[DEBUG] 完整堆栈:\n{traceback.format_exc()}")
            hint = _get_driver_install_hint(driver_name)
            return {"code": 400, "msg": hint, "result": None}, 400

        except NoSuchModuleError as nsme:
            # SQLAlchemy 无法加载驱动（如 Can't load plugin: sqlalchemy.dialects:kingbase.ksycopg2）
            err_raw = str(nsme)
            print(f"[DEBUG] NoSuchModuleError详情: {type(nsme).__name__}: {err_raw}")
            print(f"[DEBUG] 完整堆栈:\n{traceback.format_exc()}")

            # 提取驱动名称
            driver_name = None
            import re
            match = re.search(r"sqlalchemy\.dialects:(\w+)\.(\w+)", err_raw)
            if match:
                driver_name = match.group(2)
            else:
                match = re.search(r"module named '(\w+)'", err_raw)
                if match:
                    driver_name = match.group(1)

            # 技术原因提示映射
            technical_hints = {
                "pymysql": "MySQL 数据库连接失败",
                "psycopg": "PostgreSQL 数据库连接失败",
                "psycopg2": "PostgreSQL 数据库连接失败",
                "pyodbc": "SQL Server 数据库连接失败",
                "oracledb": "Oracle 数据库连接失败",
                "mysqlconnector": "MySQL 数据库连接失败",
                "pymssql": "SQL Server 数据库连接失败",
                "cx_oracle": "Oracle 数据库连接失败",
                "sqlite3": "SQLite 数据库连接失败",
                # 人大金仓 KingBase
                "ksycopg2": "人大金仓 KingBase 数据库连接失败",
                "kingbase": "人大金仓 KingBase 数据库连接失败",
                # 达梦 DM
                "dmPython": "达梦 DM 数据库连接失败",
                "dmSQLAlchemy": "达梦 DM 数据库连接失败",
                "dm": "达梦 DM 数据库连接失败",
            }

            if driver_name:
                base_msg = technical_hints.get(driver_name.lower(), "数据库连接失败")
                hint = f"{base_msg}，可能是数据库服务配置问题，请联系管理员检查服务器配置"
            else:
                hint = "数据库驱动未安装或不可用，请联系管理员检查服务器配置"

            return {"code": 400, "msg": hint, "result": None}, 400

        except ConnectionError as e:
            # 网络连接被拒绝（不是 SQLAlchemy 的 OperationalError）
            err_msg = str(e)
            print(f"[DEBUG] ConnectionError 网络连接错误: {err_msg}")
            print(f"[DEBUG] 完整堆栈:\n{traceback.format_exc()}")
            return {"code": 400,
                    "msg": "无法连接到数据库服务器，请检查主机地址、端口号是否正确，以及数据库服务是否已启动",
                    "result": None}, 400

        except TimeoutError as e:
            # 连接超时
            print(f"[DEBUG] TimeoutError 连接超时: {str(e)}")
            print(f"[DEBUG] 完整堆栈:\n{traceback.format_exc()}")
            return {"code": 400,
                    "msg": "数据库连接超时，请检查网络是否通畅、服务器是否可访问，或尝试增加超时时间",
                    "result": None}, 400

        except ImportError as e:
            # 导入错误（驱动安装但导入失败，可能是依赖库缺失）
            err_msg = str(e)
            print(f"[DEBUG] ImportError 导入错误: {err_msg}")
            print(f"[DEBUG] 完整堆栈:\n{traceback.format_exc()}")
            return {"code": 500,
                    "msg": "数据库配置异常，请联系管理员检查服务器环境",
                    "result": None}, 500

        except Exception as e:
            # 兜底 - 添加详细日志
            print(f"[DEBUG] 连接测试异常: {str(e)}")
            print(f"[DEBUG] 异常类型: {type(e).__name__}")
            print(f"[DEBUG] 完整堆栈:\n{traceback.format_exc()}")

            # 尝试从原始异常中提取更友好的错误信息
            friendly_msg = _get_friendly_error_message(e)
            return {"code": 500, "msg": friendly_msg, "result": None}, 500

        finally:
            # 关键：释放连接池里可能残留的 psycopg 连接
            if engine is not None:
                try:
                    engine.dispose()
                except Exception:
                    pass

# ========== 新增：取消请求接口 ==========
class CancelExtractSchemaAPI(Resource):
    @login_required
    def post(self):
        """
        取消数据源提取请求并清理相关数据

        参数:
            request_id: 必填，前端传来的请求ID
            config: 可选，数据源配置（用于构建连接字符串并清理数据）

        返回:
            成功：{"code":200, "msg":"取消成功", "data":{"request_id": "...", "deleted_schemas": N, "deleted_cards": M, "deleted_datasource": 1}}
            失败：{"code":4xx/500, "msg":"...", "data": None}
        """
        payload = request.get_json() or {}
        request_id = payload.get("request_id")
        config = payload.get("config")  # 新增：前端传来的配置对象

        if not request_id or not str(request_id).strip():
            return format_response(None, 400, "缺少必填字段：request_id")

        try:
            # 1. 标记请求为已取消
            request_status_manager.set_status(request_id, "cancelled")
            print(f"[CANCEL] 请求 {request_id} 已标记为取消状态")

            # 2. 清理已写入的数据
            deleted_schemas = 0
            deleted_cards = 0
            deleted_datasource = 0
            deleted_weaviate = 0

            user_id = str(flask_login.current_user.id)

            # 如果提供了配置，构建连接字符串
            connect_info = None
            cancel_db_type = None
            cancel_schema_name = None
            if config:
                try:
                    connection_string_URL = build_db_url_from_json(config)
                    connect_info = _to_raw_conn_str(connection_string_URL)
                    # 提前算 db_type 和 schema_name，用于按 db_type 分支精准定位
                    cancel_db_type = (config.get("dbType")
                                      or config.get("db_type")
                                      or "").lower()
                    cancel_schema_name = _resolve_schema_name(cancel_db_type, config, connect_info)
                    print(f"[CANCEL] 从配置构建连接字符串成功 db_type={cancel_db_type} schema_name={cancel_schema_name}")
                except Exception as e:
                    print(f"[CANCEL/WARN] 构建连接字符串失败: {str(e)}")

            if connect_info and str(connect_info).strip():
                print(f"[CANCEL] 开始清理数据：user_id={user_id}, connect_info={connect_info}, schema_name={cancel_schema_name}")

                # 2.1 删除表结构数据（UserDatasourceSchema）
                # 按 db_type 分支决定是否带 schema_name 过滤（避免误删同 connect_info 不同 schema 的行）
                # 使用稳定的哈希值进行比较
                connect_info_hash = get_connect_info_hash(connect_info)
                schemas_to_delete_query = db.session.query(UserDatasourceSchema).filter(
                    UserDatasourceSchema.user_id == user_id,
                    UserDatasourceSchema.connect_info_hash == connect_info_hash
                )
                schemas_to_delete_query = _add_schema_filter(schemas_to_delete_query, cancel_db_type, cancel_schema_name)
                schemas_to_delete = schemas_to_delete_query.all()

                deleted_schemas = len(schemas_to_delete)
                schema_doc_ids = []  # 收集所有表结构的 doc_id

                if deleted_schemas > 0:
                    print(f"[CANCEL] 找到 {deleted_schemas} 条表结构数据，准备删除")
                    for schema in schemas_to_delete:
                        # 收集 doc_id（用于关联删除数据卡片）
                        if schema.id:
                            schema_doc_ids.append(str(schema.id))
                        db.session.delete(schema)

                # 2.2 删除数据卡片（DataCardDataSource）
                # 注意：DataCardDataSource 没有 user_id 和 connect_info 字段
                # 需要通过 doc_id 关联到 UserDatasourceSchema.id 来删除
                cards_to_delete = []
                if schema_doc_ids:
                    cards_to_delete = db.session.query(DataCardDataSource).filter(
                        DataCardDataSource.doc_id.in_(schema_doc_ids)
                    ).all()

                # 收集需要从 Weaviate 删除的 UUID
                weaviate_uuids = []
                for card in cards_to_delete:
                    if card.w_uuid:
                        try:
                            weaviate_uuids.append(uuid.UUID(card.w_uuid))
                        except:
                            pass

                deleted_cards = len(cards_to_delete)
                if deleted_cards > 0:
                    print(f"[CANCEL] 找到 {deleted_cards} 条数据卡片，准备删除")
                    for card in cards_to_delete:
                        db.session.delete(card)

                # 2.3 删除 Weaviate 向量库中的数据
                if weaviate_uuids:
                    try:
                        u = User.query.filter_by(id=user_id).first()
                        user_class = getattr(u, "weaviate_class_name", None)
                        batch_delete_by_uuids(weaviate_uuids, class_name=user_class)
                        deleted_weaviate = len(weaviate_uuids)
                        print(f"[CANCEL] 成功从 Weaviate 删除 {deleted_weaviate} 条数据")
                    except Exception as we:
                        print(f"[CANCEL/WARN] Weaviate 删除失败（可忽略）: {str(we)}")

                # 2.4 删除数据源信息（DatasourceInfo）
                # 按 db_type 分支决定是否带 schema_name 过滤（避免误删同 connect_info 不同 schema 的记录）
                # 使用 connect_info_hash 进行稳定匹配（因为加密值每次不同）
                connect_info_hash = get_connect_info_hash(connect_info)
                ds_to_delete_query = db.session.query(DatasourceInfo).filter(
                    DatasourceInfo.user_id == user_id,
                    DatasourceInfo.connect_info_hash == connect_info_hash
                )
                if _has_schema_dim(cancel_db_type):
                    if cancel_schema_name is None:
                        ds_to_delete_query = ds_to_delete_query.filter(
                            DatasourceInfo.schema_name.is_(None)
                        )
                    else:
                        ds_to_delete_query = ds_to_delete_query.filter(
                            DatasourceInfo.schema_name == cancel_schema_name
                        )
                datasource_to_delete = ds_to_delete_query.first()

                if datasource_to_delete:
                    print(f"[CANCEL] 找到数据源信息，准备删除")
                    db.session.delete(datasource_to_delete)
                    deleted_datasource = 1

                # 提交所有删除操作
                db.session.commit()
                print(
                    f"[CANCEL] 清理完成：schemas={deleted_schemas}, cards={deleted_cards}, weaviate={deleted_weaviate}, datasource={deleted_datasource}")
            else:
                print(f"[CANCEL] 未提供 connect_info，仅标记取消状态（无需清理数据）")

            return format_response(
                {
                    "request_id": request_id,
                    "deleted_schemas": deleted_schemas,
                    "deleted_cards": deleted_cards,
                    "deleted_weaviate": deleted_weaviate,
                    "deleted_datasource": deleted_datasource,
                    "status": "cancelled"
                },
                200,
                "取消成功，已清理所有相关数据"
            )

        except Exception as e:
            print(f"[ERROR] 取消请求失败: {str(e)}")
            import traceback
            traceback.print_exc()
            db.session.rollback()  # 回滚事务
            return format_response(None, 500, f"取消失败: {str(e)}")


api.add_resource(ExtractSchemaAPI, '/extract_schema')
api.add_resource(ListTablesAPI, '/list_tables')
api.add_resource(ConnectTestAPI, '/connect_test')
api.add_resource(CancelExtractSchemaAPI, '/cancel_extract_schema')
