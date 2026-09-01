"""
@File: check_model_db_alignment.py
@Description: 检查 SQLAlchemy 模型与数据库表结构是否对齐
@Create: 2026-07-31

功能：
1. 自动扫描项目根目录下 models/ 中的所有模型
2. 读取 PostgreSQL 数据库实际表结构
3. 对比模型定义与数据库表结构
4. 报告缺失列、多余列、类型差异、NULL 约束差异等

使用方法：
    python check_model_db_alignment.py

依赖：
    pip install sqlalchemy psycopg2-binary python-dotenv
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import dotenv
from sqlalchemy import create_engine
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import (
    ARRAY,
    DATE,
    JSON,
    JSONB,
    TIME,
    TIMESTAMP,
    UUID,
)
from sqlalchemy.engine import Engine


# ============================================================
# 1. 项目路径配置
# ============================================================

# 你的 OntiCards_Api 项目根目录
PROJECT_ROOT = Path(r"G:\工作\OntiCards_Api").resolve()

# models 目录
MODELS_DIR = PROJECT_ROOT / "models"

# models 对应的 Python 包名
MODELS_PACKAGE = "models"


def validate_project_paths() -> None:
    """检查项目根目录和 models 目录是否存在。"""

    if not PROJECT_ROOT.exists():
        raise FileNotFoundError(
            f"项目根目录不存在：{PROJECT_ROOT}\n"
            "请检查 PROJECT_ROOT 配置是否正确。"
        )

    if not PROJECT_ROOT.is_dir():
        raise NotADirectoryError(
            f"项目根路径不是目录：{PROJECT_ROOT}"
        )

    if not MODELS_DIR.exists():
        raise FileNotFoundError(
            f"models 目录不存在：{MODELS_DIR}\n"
            f"当前项目根目录：{PROJECT_ROOT}\n"
            "请确认模型文件是否位于项目根目录下的 models 文件夹中。"
        )

    if not MODELS_DIR.is_dir():
        raise NotADirectoryError(
            f"models 路径不是目录：{MODELS_DIR}"
        )


# 把项目根目录放到 Python 模块搜索路径最前面
project_root_str = str(PROJECT_ROOT)

if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)


# ============================================================
# 2. 数据库连接配置
# ============================================================

def load_env() -> None:
    """加载项目根目录下的 .env 文件。"""

    env_path = PROJECT_ROOT / ".env"

    if env_path.exists():
        dotenv.load_dotenv(dotenv_path=env_path)


def get_db_url() -> str:
    """根据环境变量构建 PostgreSQL 连接 URL。"""

    db_username = os.environ.get(
        "DB_USERNAME",
        "postgres",
    )
    db_password = os.environ.get(
        "DB_PASSWORD",
        "master_pz123",
    )
    db_host = os.environ.get(
        "DB_HOST",
        "8.134.183.233",
    )
    db_port = os.environ.get(
        "DB_PORT",
        "55432",
    )
    db_database = os.environ.get(
        "DB_DATABASE",
        "init_test3",
    )
    db_charset = os.environ.get(
        "DB_CHARSET",
        "UTF8",
    )

    extras = (
        f"?client_encoding={db_charset}"
        if db_charset
        else ""
    )

    return (
        f"postgresql://"
        f"{db_username}:{db_password}"
        f"@{db_host}:{db_port}/{db_database}"
        f"{extras}"
    )


load_env()
DATABASE_URL = get_db_url()


# ============================================================
# 3. 数据结构定义
# ============================================================

class ModelColumnInfo:
    """SQLAlchemy 模型字段信息。"""

    def __init__(
        self,
        name: str,
        col_type: str,
        nullable: bool,
        primary_key: bool,
        default: Any = None,
        comment: str = "",
    ):
        self.name = name
        self.col_type = col_type
        self.nullable = nullable
        self.primary_key = primary_key
        self.default = default
        self.comment = comment

    def __repr__(self) -> str:
        pk_text = " PK" if self.primary_key else ""
        nullable_text = (
            " NULL"
            if self.nullable
            else " NOT NULL"
        )

        return (
            f"{self.name}: "
            f"{self.col_type}"
            f"{pk_text}"
            f"{nullable_text}"
        )


class DBColumnInfo:
    """数据库实际字段信息。"""

    def __init__(
        self,
        name: str,
        col_type: str,
        nullable: bool,
        primary_key: bool,
        default: Any = None,
        comment: str = "",
    ):
        self.name = name
        self.col_type = (
            col_type.lower()
            if col_type
            else ""
        )
        self.nullable = nullable
        self.primary_key = primary_key
        self.default = default
        self.comment = comment

    def __repr__(self) -> str:
        pk_text = " PK" if self.primary_key else ""
        nullable_text = (
            " NULL"
            if self.nullable
            else " NOT NULL"
        )

        return (
            f"{self.name}: "
            f"{self.col_type}"
            f"{pk_text}"
            f"{nullable_text}"
        )


class AlignmentResult:
    """单张表的模型和数据库对齐检查结果。"""

    def __init__(self, table_name: str):
        self.table_name = table_name
        self.status = "PASS"
        self.issues: List[str] = []

        self.model_columns: Dict[
            str,
            ModelColumnInfo,
        ] = {}

        self.db_columns: Dict[
            str,
            DBColumnInfo,
        ] = {}

        self.skip_reason = ""

    def add_issue(self, issue: str) -> None:
        self.issues.append(issue)
        self.status = "FAIL"

    def __repr__(self) -> str:
        if self.status == "SKIP":
            return (
                f"[SKIP] {self.table_name} - "
                f"{self.skip_reason}"
            )

        if self.status == "PASS":
            return (
                f"[PASS] {self.table_name} - "
                "表结构与模型对齐"
            )

        lines = [
            f"[FAIL] {self.table_name} - "
            f"发现 {len(self.issues)} 个问题："
        ]

        for issue in self.issues:
            lines.append(f"  - {issue}")

        return "\n".join(lines)


# ============================================================
# 4. 类型转换和标准化
# ============================================================

def get_sqlalchemy_column_type(column) -> str:
    """从 SQLAlchemy Column 中获取类型字符串。"""

    column_type = column.type

    if column_type is None:
        return "none"

    if isinstance(column_type, UUID):
        return "uuid"

    if isinstance(column_type, (JSON, JSONB)):
        return "json"

    if isinstance(column_type, ARRAY):
        item_type = get_sqlalchemy_type_name(
            column_type.item_type
        )
        return f"{item_type}[]"

    if isinstance(column_type, TIMESTAMP):
        if column_type.timezone:
            return "timestamp with time zone"

        return "timestamp without time zone"

    if isinstance(column_type, DATE):
        return "date"

    if isinstance(column_type, TIME):
        if getattr(column_type, "timezone", False):
            return "time with time zone"

        return "time without time zone"

    return get_sqlalchemy_type_name(column_type)


def get_sqlalchemy_type_name(column_type) -> str:
    """获取普通 SQLAlchemy 类型名称。"""

    type_name = type(column_type).__name__.lower()

    type_aliases = {
        "string": "varchar",
        "unicode": "varchar",
        "text": "text",
        "integer": "integer",
        "biginteger": "bigint",
        "smallinteger": "smallint",
        "boolean": "boolean",
        "float": "float",
        "numeric": "numeric",
        "decimal": "numeric",
        "datetime": "timestamp",
        "date": "date",
        "time": "time",
        "largebinary": "bytea",
    }

    type_name = type_aliases.get(
        type_name,
        type_name,
    )

    length = getattr(
        column_type,
        "length",
        None,
    )

    if length:
        return f"{type_name}({length})"

    precision = getattr(
        column_type,
        "precision",
        None,
    )

    if precision is not None:
        scale = getattr(
            column_type,
            "scale",
            None,
        )

        if scale is None:
            return f"{type_name}({precision})"

        return (
            f"{type_name}"
            f"({precision},{scale})"
        )

    return type_name


def normalize_type_string(type_str: str) -> str:
    """标准化模型类型和数据库类型字符串。"""

    if not type_str:
        return ""

    normalized = type_str.lower().strip()

    replacements = [
        ("character varying", "varchar"),
        ("double precision", "float"),
        ("timestamp with time zone", "timestamptz"),
        ("timestamp without time zone", "timestamp"),
        ("time with time zone", "timetz"),
        ("time without time zone", "time"),
        ("decimal", "numeric"),
        ("bool", "boolean"),
        ("int4", "integer"),
        ("int8", "bigint"),
        ("int2", "smallint"),
    ]

    for old, new in replacements:
        normalized = normalized.replace(
            old,
            new,
        )

    # 去掉多余空格
    normalized = " ".join(normalized.split())

    return normalized


def get_base_type(type_str: str) -> str:
    """从 varchar(255) 等类型中提取基础类型。"""

    normalized = normalize_type_string(type_str)

    if "(" in normalized:
        return normalized.split("(", 1)[0]

    return normalized


# ============================================================
# 5. 模型字段读取
# ============================================================

def extract_model_columns(
    model_class,
) -> Dict[str, ModelColumnInfo]:
    """从 SQLAlchemy 模型类提取字段信息。"""

    columns: Dict[
        str,
        ModelColumnInfo,
    ] = {}

    if not hasattr(model_class, "__mapper__"):
        return columns

    for column in model_class.__mapper__.columns:
        column_name = column.name or column.key

        column_info = ModelColumnInfo(
            name=column_name,
            col_type=get_sqlalchemy_column_type(
                column
            ),
            nullable=bool(column.nullable),
            primary_key=bool(
                column.primary_key
            ),
            default=(
                str(column.default)
                if column.default
                else None
            ),
            comment=column.comment or "",
        )

        columns[column_name] = column_info

    return columns


# ============================================================
# 6. 数据库字段读取
# ============================================================

def get_db_columns(
    inspector,
    table_name: str,
    schema: str = "public",
) -> Dict[str, DBColumnInfo]:
    """从数据库读取指定表的字段信息。"""

    columns: Dict[
        str,
        DBColumnInfo,
    ] = {}

    db_columns = inspector.get_columns(
        table_name,
        schema=schema,
    )

    pk_constraint = inspector.get_pk_constraint(
        table_name,
        schema=schema,
    )

    pk_columns = set(
        pk_constraint.get(
            "constrained_columns",
            [],
        )
        or []
    )

    for column in db_columns:
        column_name = column["name"]

        column_info = DBColumnInfo(
            name=column_name,
            col_type=(
                str(column["type"]).lower()
                if column.get("type")
                else ""
            ),
            nullable=bool(
                column.get(
                    "nullable",
                    True,
                )
            ),
            primary_key=(
                column_name in pk_columns
            ),
            default=(
                str(column.get("default"))
                if column.get("default")
                is not None
                else None
            ),
            comment=(
                column.get("comment")
                or ""
            ),
        )

        columns[column_name] = column_info

    return columns


# ============================================================
# 7. 单表对齐检查
# ============================================================

def check_table_alignment(
    table_name: str,
    model_class,
    inspector,
    schema: str = "public",
) -> AlignmentResult:
    """检查单张表的模型与数据库结构。"""

    result = AlignmentResult(table_name)

    result.model_columns = extract_model_columns(
        model_class
    )

    if not result.model_columns:
        result.status = "SKIP"
        result.skip_reason = (
            "模型无字段定义或无法解析"
        )
        return result

    try:
        result.db_columns = get_db_columns(
            inspector=inspector,
            table_name=table_name,
            schema=schema,
        )

    except Exception as error:
        result.status = "SKIP"
        result.skip_reason = (
            "数据库表无法访问："
            f"{error}"
        )
        return result

    if not result.db_columns:
        result.status = "SKIP"
        result.skip_reason = (
            "数据库表没有字段定义"
        )
        return result

    model_column_names = set(
        result.model_columns.keys()
    )

    db_column_names = set(
        result.db_columns.keys()
    )

    # 模型存在，但数据库不存在的字段
    missing_in_db = (
        model_column_names
        - db_column_names
    )

    for column_name in sorted(missing_in_db):
        column_info = (
            result.model_columns[
                column_name
            ]
        )

        result.add_issue(
            f"列 '{column_name}'："
            "模型中存在，但数据库中缺失；"
            f"模型类型={column_info.col_type}"
        )

    # 数据库存在，但模型不存在的字段
    extra_in_db = (
        db_column_names
        - model_column_names
    )

    for column_name in sorted(extra_in_db):
        column_info = (
            result.db_columns[
                column_name
            ]
        )

        result.add_issue(
            f"列 '{column_name}'："
            "数据库中存在，但模型中未定义；"
            f"数据库类型={column_info.col_type}"
        )

    common_columns = (
        model_column_names
        & db_column_names
    )

    for column_name in sorted(common_columns):
        model_column = (
            result.model_columns[
                column_name
            ]
        )

        db_column = (
            result.db_columns[
                column_name
            ]
        )

        model_type = normalize_type_string(
            model_column.col_type
        )

        db_type = normalize_type_string(
            db_column.col_type
        )

        model_base_type = get_base_type(
            model_type
        )

        db_base_type = get_base_type(
            db_type
        )

        # json 和 jsonb 在 PostgreSQL 中功能等价，视为兼容
        compatible_types = {
            ("json", "jsonb"),
            ("jsonb", "json"),
        }

        # 基础类型不一致（但 json/jsonb 除外）
        if model_base_type != db_base_type:
            # json 和 jsonb 视为等价，不报告问题
            if (model_base_type, db_base_type) not in compatible_types:
                result.add_issue(
                    f"列 '{column_name}'："
                    "字段类型不一致；"
                    f"模型类型={model_column.col_type}，"
                    f"数据库类型={db_column.col_type}"
                )

        # varchar、numeric 等参数类型检查（宽松模式）
        elif model_base_type in {
            "varchar",
            "numeric",
        }:
            # 标准化后比较：移除所有空格后比较
            # 例如 numeric(5,4) 和 numeric(5, 4) 视为相同
            normalized_model = model_type.replace(" ", "").replace(",", ",")
            normalized_db = db_type.replace(" ", "").replace(",", ",")

            if normalized_model != normalized_db:
                result.add_issue(
                    f"列 '{column_name}'："
                    "类型参数不一致；"
                    f"模型类型={model_column.col_type}，"
                    f"数据库类型={db_column.col_type}"
                )

        # 主键定义检查
        if (
            model_column.primary_key
            != db_column.primary_key
        ):
            result.add_issue(
                f"列 '{column_name}'："
                "主键定义不一致；"
                f"模型 primary_key="
                f"{model_column.primary_key}，"
                f"数据库 primary_key="
                f"{db_column.primary_key}"
            )

        # NULL 约束检查
        if (
            model_column.nullable
            != db_column.nullable
        ):
            result.add_issue(
                f"列 '{column_name}'："
                "NULL 约束不一致；"
                f"模型 nullable="
                f"{model_column.nullable}，"
                f"数据库 nullable="
                f"{db_column.nullable}"
            )

    return result


# ============================================================
# 8. 加载模型
# ============================================================

def load_models(
    models_dir: Path,
) -> Dict[str, Any]:
    """加载 models 目录下的 SQLAlchemy 模型。"""

    models: Dict[str, Any] = {}

    if not models_dir.exists():
        raise FileNotFoundError(
            f"模型目录不存在：{models_dir}"
        )

    model_files = sorted(
        models_dir.glob("*.py")
    )

    if not model_files:
        print(
            f"警告：models 目录中没有找到 "
            f"Python 文件：{models_dir}"
        )
        return models

    for model_file in model_files:
        filename = model_file.name

        if filename.startswith("_"):
            continue

        if filename in {
            "utils.py",
        }:
            continue

        module_name = model_file.stem
        full_module_name = (
            f"{MODELS_PACKAGE}."
            f"{module_name}"
        )

        try:
            module = __import__(
                full_module_name,
                fromlist=[""],
            )

        except Exception as error:
            print(
                f"  [WARNING] 无法加载模块 "
                f"'{full_module_name}'：{error}"
            )
            continue

        for attribute_name in dir(module):
            if attribute_name.startswith("_"):
                continue

            try:
                attribute = getattr(
                    module,
                    attribute_name,
                )
            except Exception:
                continue

            if not isinstance(attribute, type):
                continue

            if not hasattr(
                attribute,
                "__tablename__",
            ):
                continue

            if not hasattr(
                attribute,
                "__mapper__",
            ):
                continue

            table_name = getattr(
                attribute,
                "__tablename__",
                None,
            )

            if not table_name:
                continue

            if table_name not in models:
                models[table_name] = attribute

    return models


# ============================================================
# 9. 检查全部模型
# ============================================================

def check_all_models_alignment(
    models_dir: Path,
    engine: Engine,
    schema: str = "public",
) -> List[AlignmentResult]:
    """检查所有模型与数据库表结构。"""

    inspector = sa_inspect(engine)
    results: List[AlignmentResult] = []

    print()
    print("=" * 70)
    print("正在扫描 models 目录")
    print("=" * 70)
    print(f"项目根目录：{PROJECT_ROOT}")
    print(f"模型目录：{models_dir}")
    print(f"模型包名：{MODELS_PACKAGE}")

    models = load_models(models_dir)

    print(
        f"\n成功加载 {len(models)} 个模型"
    )

    if models:
        for table_name in sorted(models):
            print(f"  - {table_name}")

    print()
    print("正在读取数据库表列表……")

    db_tables = set(
        inspector.get_table_names(
            schema=schema
        )
    )

    print(
        f"数据库 public schema "
        f"共有 {len(db_tables)} 张表"
    )

    print()
    print("=" * 70)
    print("开始检查模型与数据库表结构")
    print("=" * 70)

    for table_name, model_class in sorted(
        models.items()
    ):
        print(
            f"检查表：{table_name}……",
            end=" ",
        )

        if table_name not in db_tables:
            result = AlignmentResult(
                table_name
            )
            result.status = "SKIP"
            result.skip_reason = (
                "数据库中不存在此表"
            )
            results.append(result)

            print(
                f"SKIP："
                f"{result.skip_reason}"
            )
            continue

        result = check_table_alignment(
            table_name=table_name,
            model_class=model_class,
            inspector=inspector,
            schema=schema,
        )

        results.append(result)

        if result.status == "PASS":
            print("PASS")

        elif result.status == "FAIL":
            print(
                f"FAIL："
                f"{len(result.issues)} 个问题"
            )

        else:
            print(
                f"SKIP："
                f"{result.skip_reason}"
            )

    return results


# ============================================================
# 10. 输出汇总
# ============================================================

def print_summary(
    results: List[AlignmentResult],
) -> bool:
    """打印检查结果摘要。"""

    passed = sum(
        1
        for result in results
        if result.status == "PASS"
    )

    failed = sum(
        1
        for result in results
        if result.status == "FAIL"
    )

    skipped = sum(
        1
        for result in results
        if result.status == "SKIP"
    )

    print()
    print("=" * 70)
    print("检查结果摘要")
    print("=" * 70)
    print(f"总计检查：{len(results)} 张表")
    print(f"通过：    {passed} 张表")
    print(f"失败：    {failed} 张表")
    print(f"跳过：    {skipped} 张表")
    print("=" * 70)

    if failed > 0:
        print()
        print("[失败表详情]")

        for result in results:
            if result.status != "FAIL":
                continue

            print()
            print(result)

    if skipped > 0:
        print()
        print("[跳过表详情]")

        for result in results:
            if result.status != "SKIP":
                continue

            print(
                f"  - {result.table_name}："
                f"{result.skip_reason}"
            )

    return failed == 0


# ============================================================
# 11. 主函数
# ============================================================

def main() -> None:
    """程序入口。"""

    print("=" * 70)
    print("SQLAlchemy 模型与数据库表结构对齐检查工具")
    print("=" * 70)

    try:
        validate_project_paths()

    except Exception as error:
        print()
        print(f"路径检查失败：{error}")
        sys.exit(1)

    print()
    print(f"项目根目录：{PROJECT_ROOT}")
    print(f"模型目录：{MODELS_DIR}")
    print(
        "数据库连接："
        f"{DATABASE_URL.split('@')[-1]}"
    )
    print(
        "检查时间："
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print()
    print("正在连接数据库……")

    engine: Engine

    try:
        engine = create_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
        )

        with engine.connect() as connection:
            connection.execute(
                text("SELECT 1")
            )

        print("数据库连接成功。")

    except Exception as error:
        print(
            f"数据库连接失败：{error}"
        )
        sys.exit(1)

    try:
        results = check_all_models_alignment(
            models_dir=MODELS_DIR,
            engine=engine,
            schema="public",
        )

        if not results:
            print()
            print(
                "没有加载到任何 SQLAlchemy 模型。"
            )
            print(
                "请检查 models 目录、模型导入依赖"
                "以及模型类是否定义了 "
                "__tablename__ 和 __mapper__。"
            )
            sys.exit(1)

        success = print_summary(results)

    finally:
        engine.dispose()

    if success:
        print()
        print(
            "所有检查通过："
            "模型与数据库表结构已对齐。"
        )
        sys.exit(0)

    print()
    print(
        "检查失败："
        "请根据上述详情修复模型或数据库。"
    )
    sys.exit(1)


if __name__ == "__main__":
    main()