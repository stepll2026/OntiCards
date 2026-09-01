"""
 @File: value_profiling.py
 @Description: 画像提取与构建
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-01-21 14:45
"""

from __future__ import annotations
import re
from collections import Counter
from sqlalchemy import text

# 用于“deleted 0/1 => 删除标志；时间戳 => 删除时间”这类画像推断

_TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(\s+\d{2}:\d{2}:\d{2})?$")

def infer_type_hint(values: list[str]) -> tuple[str, list[str]]:
    notes = []
    if not values:
        return "unknown", ["empty"]

    uniq = set(values)
    if uniq.issubset({"0","1"}):
        return "boolean_flag", ["only_0_1"]
    if uniq.issubset({"true","false","True","False"}):
        return "boolean_flag", ["only_true_false"]

    time_hit = sum(1 for v in values if _TIME_RE.match(v))
    if time_hit / max(len(values),1) >= 0.6:
        return "datetime", ["looks_like_time"]

    # numeric
    num_hit = 0
    for v in values:
        try:
            float(v); num_hit += 1
        except Exception:
            pass
    if num_hit / max(len(values),1) >= 0.8:
        if len(uniq) <= 10:
            return "enum", ["numeric_small_enum"]
        return "amount", ["numeric"]

    # high cardinality
    if len(uniq) / max(len(values),1) >= 0.7:
        return "identifier", ["high_cardinality"]

    return "text", ["fallback_text"]

def profile_field(
    column_name: str,
    column_type: str,
    column_comment: str = "",
    sample_values: list = None
) -> dict:
    """
    为单个字段生成画像（不需要数据库连接）

    Args:
        column_name: 字段名
        column_type: 字段类型
        column_comment: 字段注释
        sample_values: 样例值列表

    Returns:
        字段画像字典
    """
    if sample_values is None:
        sample_values = []

    # 转换为字符串
    svals = [str(v) for v in sample_values if v is not None]

    # 统计
    c = Counter(svals)
    top = c.most_common(5)

    # 推断类型提示
    type_hint, notes = infer_type_hint(svals)

    # 推断格式提示
    format_hint = infer_format_hint(svals, type_hint)

    # 计算空值率
    null_count = len(sample_values) - len(svals)
    null_rate_est = round(null_count / max(len(sample_values), 1) * 100, 2) if sample_values else 0

    # 脱敏样例值
    sanitized_samples = sanitize_sample_values(svals, column_name, type_hint)

    return {
        "column_name": column_name,
        "column_type": column_type,
        "column_comment": column_comment,
        "sample_size": len(sample_values),
        "non_null_sample": len(svals),
        "null_rate_est": null_rate_est,
        "distinct_est": len(c),
        "top_values": [{"v": k, "cnt": v} for k, v in top],
        "type_hint": type_hint,
        "format_hint": format_hint,
        "notes": notes,
        "sample_values": sanitized_samples
    }


def profile_columns(engine, table_full_name: str, columns: list[str], sample_size: int = 200) -> dict:
    if not columns:
        return {}

    dialect = engine.dialect.name  # postgresql/mysql/mssql/oracle/...

    # 根据数据库类型选择引号风格
    if dialect == "mysql":
        # MySQL 使用反引号
        col_quote = "`"
    else:
        # PostgreSQL/SQL Server/Oracle 等使用双引号
        col_quote = '"'

    cols_sql = ", ".join([col_quote + c + col_quote for c in columns])

    # 构建表名（根据数据库类型调整引号）
    if dialect == "mysql":
        # MySQL: schema.table 直接拼接（不使用引号包裹整体）
        # 解析 schema 和 table（先分割，再移除引号）
        parts = table_full_name.split('"."')
        if len(parts) == 2:
            # 移除各部分的双引号
            schema_part = parts[0].replace('"', '')
            table_part = parts[1].replace('"', '')
            # schema 和 table 名都加上反引号（因为可能包含特殊字符如 -）
            table_sql = "`" + schema_part + "`.`" + table_part + "`"
        else:
            # 只有表名
            parts2 = table_full_name.split('"."')
            if len(parts2) == 1:
                parts2 = table_full_name.split('`.`')
            if len(parts2) == 1:
                parts2 = table_full_name.replace('"', '').split('.')
            table_sql = "`" + parts2[-1].replace('"', '') + "`"
        sql = text("SELECT " + cols_sql + " FROM " + table_sql + " LIMIT :limit")
    elif dialect in ("mssql",):
        sql = text(f"SELECT TOP (:limit) {cols_sql} FROM {table_full_name}")
    elif dialect in ("oracle", "dm"):
        # 达梦 DM：与 Oracle 兼容，使用 FETCH FIRST
        sql = text(f"SELECT {cols_sql} FROM {table_full_name} FETCH FIRST :limit ROWS ONLY")
    else:
        # postgresql / trino / sqlite 等
        sql = text(f"SELECT {cols_sql} FROM {table_full_name} LIMIT :limit")

    with engine.connect() as conn:
        rows = conn.execute(sql, {"limit": sample_size}).fetchall()

    profiles = {}
    for i, col in enumerate(columns):
        raw = [r[i] for r in rows if r[i] is not None]
        svals = [str(v) for v in raw]
        c = Counter(svals)
        top = c.most_common(5)
        type_hint, notes = infer_type_hint(svals)

        # 新增：format_hint 推断
        format_hint = infer_format_hint(svals, type_hint)

        # 新增：null_rate_est 计算
        null_count = len(rows) - len(raw)
        null_rate_est = round(null_count / max(len(rows), 1) * 100, 2)

        # 新增：脱敏样例值
        sanitized_samples = sanitize_sample_values(svals, col, type_hint)

        profiles[col] = {
            "sample_size": len(rows),
            "non_null_sample": len(raw),
            "null_rate_est": null_rate_est,  # 新增
            "distinct_est": len(c),
            "top_values": [{"v": k, "cnt": v} for k, v in top],
            "type_hint": type_hint,
            "format_hint": format_hint,  # 新增
            "notes": notes,
            "sample_values": sanitized_samples  # 新增
        }
    return profiles


def infer_format_hint(values: list[str], type_hint: str) -> str:
    """
    推断格式提示
    """
    if not values:
        return ""

    if type_hint == "datetime":
        # 检测时间格式
        sample = values[0]
        if re.match(r"^\d{4}-\d{2}-\d{2}$", sample):
            return "yyyy-mm-dd"
        elif re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", sample):
            return "yyyy-mm-dd hh:mm:ss"
        elif re.match(r"^\d{10}$", sample):
            return "10-digit-timestamp"
        elif re.match(r"^\d{13}$", sample):
            return "13-digit-timestamp"

    elif type_hint == "identifier":
        sample = values[0]
        if re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", sample, re.I):
            return "uuid"
        elif re.match(r"^\d+$", sample):
            return "numeric-id"

    elif type_hint == "boolean_flag":
        uniq = set(values)
        if uniq.issubset({"0", "1"}):
            return "0/1"
        elif uniq.issubset({"true", "false", "True", "False"}):
            return "true/false"
        elif uniq.issubset({"Y", "N"}):
            return "Y/N"

    return ""


def sanitize_sample_values(values: list[str], column_name: str, type_hint: str) -> list[str]:
    """
    对样例值进行脱敏处理

    规则：
    1. 敏感字段（phone/email/idcard/name）：只保留格式特征
    2. 字符串：截断到 64 字符
    3. 高基数标识符：只保留前缀
    """
    col_lower = column_name.lower()

    # 敏感字段检测
    sensitive_keywords = {
        "phone": ["phone", "mobile", "tel", "电话", "手机"],
        "email": ["email", "mail", "邮箱"],
        "idcard": ["idcard", "id_card", "身份证"],
        "name": ["name", "姓名", "username", "user_name"]
    }

    sensitive_type = None
    for stype, keywords in sensitive_keywords.items():
        if any(kw in col_lower for kw in keywords):
            sensitive_type = stype
            break

    if sensitive_type:
        # 敏感字段：只返回格式特征
        if sensitive_type == "phone":
            return ["[11位数字]", "[手机号格式]"]
        elif sensitive_type == "email":
            return ["[邮箱格式]", "xxx@xxx.com"]
        elif sensitive_type == "idcard":
            return ["[18位身份证]"]
        elif sensitive_type == "name":
            return ["[姓名]", "[2-4字符]"]

    # 非敏感字段：截断 + 脱敏
    sanitized = []
    for v in values[:5]:  # 最多保留 5 个样例
        if len(v) > 64:
            sanitized.append(v[:64] + "...")
        elif type_hint == "identifier" and len(v) > 20:
            # 标识符：只保留前缀
            sanitized.append(v[:10] + "***")
        else:
            sanitized.append(v)

    return sanitized
