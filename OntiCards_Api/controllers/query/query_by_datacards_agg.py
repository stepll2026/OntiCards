"""
 @File: query_by_datacards_agg.py
 @Description: 聚合检索 资源类 + 核心逻辑（只收 query）
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-10-27 14:56
"""
import json
import re
import time as time_module
import copy
# -*- coding: utf-8 -*-
from typing import List, Any, Set, Tuple, Optional, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date, time as datetime_time, timedelta
from decimal import Decimal
from uuid import UUID

import flask_login
from flask import request, Blueprint
from flask_restful import Resource, Api
from sqlalchemy import text

from config import get_env
from controllers.agents.qwen import QwenMaxLatest
from controllers.agents.qwen.QwenMaxLatest import qian_wen_llm_with_usage
from controllers.datasource.datasource_tool import get_db_engine, format_response
from controllers.query.sql_join_utils import (
    card_to_table_obj, build_clusters, make_tables_block, make_rels_block,
    map_connect_name_to_connect_info, infer_entity_key_from_cards,
    fetch_relationship_cards, format_relationship_cards_for_prompt,
    make_rels_block_with_relationship_cards,
    filter_relationship_data_by_tables, merge_relationship_data
)
from controllers.query.sql_prompt_loader import load_prompt, render_prompt
from controllers.datacard.data_card_db_api import get_data_card_by_doc_id
from controllers.weaviate_db_tool.weaviate_api import search_vector
from models.user_datasource_schema import UserDatasourceSchema
from models.datasource_infos import DatasourceInfo
from extensions.ext_database import db
from controllers.query_history.query_logger import QueryLogger
from controllers.business_term.term_recognizer import (
    process_question_by_libraries,
    process_question,
    get_enabled_library_ids_by_datasource
)

# === 注册 Flask Blueprint 和 API ===
query_by_datacards_agg = Blueprint('query_by_datacards_agg', __name__)
api = Api(query_by_datacards_agg)


# ---- 简单工具 ----
def _strip_code_fences(s: str) -> str:
    """
    去掉 Markdown 代码围栏：```sql ... ``` / ``` ... ```
    同时去掉围栏后的首行语言标签（sql, SQL 等）。
    """
    if not s:
        return ""
    s = s.strip()
    # 去首尾围栏
    if s.startswith("```"):
        s = re.sub(r"^\s*```[a-zA-Z0-9_-]*\s*", "", s, flags=re.DOTALL)
        s = re.sub(r"\s*```\s*$", "", s, flags=re.DOTALL)
    return s.strip()


def _remove_sql_comments(sql: str) -> str:
    """
    移除 SQL 中的注释（单行 -- 和多行 /* */）
    """
    # 移除多行注释 /* ... */
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    # 移除单行注释 -- ...
    sql = re.sub(r"--[^\n]*", "", sql)
    return sql.strip()


def _try_fix_incomplete_json(json_str: str) -> str | None:
    """
    尝试修复不完整的 JSON 字符串

    常见问题：
    1. LLM 输出被截断，缺少结尾的 } 或 ]
    2. 最后一个元素后有多余的逗号
    3. 字符串未正确闭合
    """
    if not json_str:
        return None

    fixed = json_str.strip()

    # 问题1：缺少结尾的 }
    if not fixed.endswith('}') and not fixed.endswith(']'):
        # 尝试找到最后一个完整的对象/数组
        open_braces = fixed.count('{') - fixed.count('}')
        open_brackets = fixed.count('[') - fixed.count(']')

        if open_braces > 0:
            fixed = fixed + '}' * open_braces
        if open_brackets > 0:
            fixed = fixed + ']' * open_brackets

    # 问题2：最后一个元素后有多余逗号
    fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)

    # 问题3：尝试补全未闭合的字符串（很危险，只在特定情况下尝试）
    # 如果最后一个字符不是 "，可能有未闭合的字符串
    if not fixed.endswith('"') and not fixed.endswith('}') and not fixed.endswith(']'):
        # 找到最后一个完整的 "..." 对
        last_quote = fixed.rfind('"')
        if last_quote > 0:
            before_quote = fixed[:last_quote]
            # 检查引号是否平衡
            quote_count = before_quote.count('"') - before_quote.count('\\"')
            if quote_count % 2 == 1:  # 未闭合的引号
                fixed = fixed + '"'

    return fixed


def _extract_sql_from_llm_text(raw: str):
    """
    从 LLM 文本里提取 SQL。如果是 note/解释，返回 kind='note'。
    返回 dict: {'kind':'sql'|'note'|'text', 'text': '<内容>'}

    注意：当 LLM 同时返回 ```sql``` 和 ```note``` 时，需要判断 SQL 是否有效：
    - 如果 SQL 是占位符（如 SELECT NULL WHERE FALSE），优先返回 note
    - 如果 SQL 是有效查询，优先返回 SQL，忽略说明性的 note
    """
    t = (raw or "").strip()
    if not t:
        return {"kind": "text", "text": ""}

    # 先尝试提取 SQL 和 note
    sql_match = re.search(r"```sql\s*(.+?)\s*```", t, flags=re.IGNORECASE | re.DOTALL)
    note_match = re.search(r"```note\s*(.+?)\s*```", t, flags=re.IGNORECASE | re.DOTALL)

    # 情况1：同时包含 SQL 和 note
    if sql_match and note_match:
        sql_text = sql_match.group(1).strip()
        sql_text = _remove_sql_comments(sql_text)

        # 判断是否是占位符 SQL（无效的 SQL）
        is_placeholder = (
                "SELECT NULL" in sql_text.upper() or
                "WHERE FALSE" in sql_text.upper() or
                re.search(r"SELECT\s+NULL\s+AS", sql_text, re.IGNORECASE)
        )

        if is_placeholder:
            # 占位符 SQL + note：AI 真的无法查询，返回 note
            note_body = note_match.group(1).strip()
            return {"kind": "note", "text": note_body}
        else:
            # 有效 SQL + note：AI 生成了 SQL 并附加了说明，返回 SQL
            return {"kind": "sql", "text": sql_text}

    # 情况2：只有 note（没有 SQL）
    if note_match:
        note_body = note_match.group(1).strip()
        return {"kind": "note", "text": note_body}

    # 情况3：note 起始标记（没有结束标记）
    if t.lower().startswith("```note"):
        body = _strip_code_fences(t)
        return {"kind": "note", "text": body}

    # 情况4：只有 SQL（没有 note）
    if sql_match:
        sql_text = sql_match.group(1).strip()
        sql_text = _remove_sql_comments(sql_text)
        return {"kind": "sql", "text": sql_text}

    # 情况5：裸文本中包含 SELECT/WITH
    m2 = re.search(r"\b(SELECT|WITH)\b", t, flags=re.IGNORECASE)
    if m2:
        sql_text = t[m2.start():].strip()
        sql_text = _remove_sql_comments(sql_text)
        return {"kind": "sql", "text": sql_text}

    # 情况6：都不是，当作普通文本
    return {"kind": "text", "text": t}


# ======= shared utils (identifier & nolock) =======
def _strip_nolock(x: str) -> str:
    """移除 SQL Server 的 WITH(NOLOCK)/WITH(READUNCOMMITTED) 表提示，便于表名解析"""
    return re.sub(r"\s+WITH\s*\([^)]+\)", "", x, flags=re.IGNORECASE)


def _norm_ident(ident: str) -> str:
    """
    规范化 SQL 标识符：
    - 去掉引号/反引号/方括号: "tbl", `tbl`, [tbl]
    - schema.table 仅保留最后一段（物理表名）
    - 统一小写
    """
    if not ident:
        return ""
    s = ident.strip().rstrip(",;")
    # 去掉跟随的 AS/别名（只保留第一个标识段）
    s = s.split()[0]
    s = s.replace("`", "").replace('"', "").replace("[", "").replace("]", "")
    parts = [p for p in re.split(r"\s*\.\s*", s) if p]
    return (parts[-1] if parts else s).lower()


def _infer_strategy(user_question: str) -> str:
    """
    读取 strategy_detect.txt 提示词并让 LLM 返回融合策略：
    AND / OR / PRIORITY / UNION
    - 优先匹配显式的四个关键词（大小写不敏感）
    - 若未命中，默认回退 OR（更宽松）
    """
    tpl = load_prompt("strategy_detect.txt")
    p = render_prompt(tpl, user_question=user_question)
    r = QwenMaxLatest.qian_wen_llm(p, stream_type=False)

    # 1) 取文本，做标准化
    text = (r["choices"][0]["message"]["content"] or "").strip().upper()

    # 2) 容错：有些模型可能包在 JSON / 句子里，做一次正则提取
    #    在整段文本中寻找第一个 AND|OR|PRIORITY|UNION 关键词
    import re
    m = re.search(r"\b(AND|OR|PRIORITY|UNION)\b", text)
    if m:
        return m.group(1)

    # 3) 进一步容错：中文关键字映射（可按需扩充）
    zh_map = {
        "优先": "PRIORITY",
        "以.*为准": "PRIORITY",
        "主数据": "PRIORITY",
        "权威": "PRIORITY",
        "汇总": "UNION",
        "合并": "UNION",
        "全量": "UNION",
        "去重": "UNION",
        "或者": "OR",
        "或": "OR",
        "任一": "OR",
        "任意符合": "OR",
        "同时": "AND",
        "并且": "AND",
        "且": "AND",
        "都满足": "AND",
    }
    for k, v in zh_map.items():
        if re.search(k, text):
            return v

    # 4) 兜底：OR
    return "OR"


def _fix_trino_sql_columns(sql: str, trino_tables: List[dict]) -> str:
    """
    修复Trino SQL中使用了不存在列的问题
    当检测到使用了不存在的列时，尝试自动修复：
    - 如果用于COUNT判断"是否有记录"（CASE WHEN COUNT(...) > 0），替换为COUNT(*)
    - 如果用于其他COUNT场景，使用表中第一个存在的列（优先使用id列）
    - 如果用于其他用途，使用表中第一个存在的列（优先使用id列）
    
    同时检查表名是否在白名单中，如果不在则抛出错误
    """
    # 首先从SQL中解析出实际的表别名映射（FROM/JOIN中的别名）
    # 构建：SQL中的别名 -> 完整表名 -> 列白名单
    sql_alias_to_table = {}  # SQL别名 -> 完整表名
    table_to_columns = {}  # 完整表名 -> 列集合
    whitelist_tables = set()  # 白名单表名集合（用于验证）

    # 从trino_tables构建表名到列的映射
    for t in trino_tables:
        full_table_name = t.get("table_name", "")
        columns = [c.get("name", "").lower() for c in t.get("columns", [])]
        if full_table_name:
            table_to_columns[full_table_name.lower()] = set(columns)
            whitelist_tables.add(full_table_name.lower())
            # 同时添加规范化后的表名（去掉引号，只保留表名部分）
            table_name_only = _norm_ident(full_table_name)
            whitelist_tables.add(table_name_only)

    # 从SQL中解析FROM/JOIN，建立SQL别名到表名的映射
    from_join_pattern = re.compile(
        r'(?:FROM|JOIN)\s+([`"\[\]\w\.\-/]+)(?:\s+(?:AS\s+)?([`"\[\]\w\-]+))?',
        flags=re.IGNORECASE
    )

    # 先检查所有表名是否在白名单中
    sql_tables_found = []
    for match in from_join_pattern.finditer(sql):
        raw_tbl = match.group(1) or ""
        raw_alias = match.group(2) or ""
        if raw_tbl:
            # 规范化表名用于匹配（去掉所有引号，统一格式）
            tbl_normalized = _norm_ident(raw_tbl)
            # 去掉所有引号，转换为小写，用于精确匹配
            tbl_clean = raw_tbl.replace('"', '').replace('`', '').replace('[', '').replace(']', '').lower()

            # 检查表名是否在白名单中
            is_in_whitelist = False
            matched_table = None

            # 首先尝试精确匹配（去掉引号后的完整路径）
            for full_table_name, cols in table_to_columns.items():
                full_table_clean = full_table_name.replace('"', '').lower()
                if full_table_clean == tbl_clean:
                    is_in_whitelist = True
                    matched_table = full_table_name
                    break

            # 如果精确匹配失败，尝试规范化匹配
            if not is_in_whitelist:
                for whitelist_table in whitelist_tables:
                    whitelist_normalized = _norm_ident(whitelist_table)
                    if whitelist_normalized == tbl_normalized:
                        is_in_whitelist = True
                        # 找到匹配的白名单表
                        for full_table_name, cols in table_to_columns.items():
                            if _norm_ident(full_table_name) == tbl_normalized:
                                matched_table = full_table_name
                                break
                        break

            if not is_in_whitelist:
                # 表名不在白名单中，抛出错误
                available_tables = [t.get("table_name", "") for t in trino_tables]
                raise ValueError(f'SQL包含非白名单表: {raw_tbl}。可用表: {", ".join(available_tables)}')

            sql_tables_found.append((raw_tbl, matched_table))

            if raw_alias:
                alias = _norm_ident(raw_alias)
                # 查找匹配的表（通过规范化表名匹配）
                if matched_table and matched_table in table_to_columns:
                    sql_alias_to_table[alias] = (matched_table, table_to_columns[matched_table])

    # 构建SQL别名到列白名单的映射
    alias_to_columns = {}
    for alias, (table_name, cols) in sql_alias_to_table.items():
        alias_to_columns[alias] = cols

    # 处理没有表别名的情况：如果SQL中只有一个表且没有别名，建立默认映射
    if not alias_to_columns and len(sql_tables_found) == 1:
        # 只有一个表且没有别名，直接使用表名作为"别名"
        _, matched_table = sql_tables_found[0]
        if matched_table and matched_table in table_to_columns:
            # 使用表名的最后一部分作为默认别名（用于匹配直接列引用）
            table_name_parts = matched_table.replace('"', '').split('.')
            default_alias = table_name_parts[-1].lower() if table_name_parts else ""
            alias_to_columns[default_alias] = table_to_columns[matched_table]
            # 也添加空字符串作为别名（用于匹配不带别名的列引用）
            alias_to_columns[""] = table_to_columns[matched_table]

    # 调试信息
    if alias_to_columns:
        print(f"[trino-fix] 解析到 {len(alias_to_columns)} 个SQL别名映射:")
        for alias, cols in alias_to_columns.items():
            alias_display = alias if alias else "(无别名)"
            print(
                f"[trino-fix]   别名 {alias_display} -> {len(cols)} 列: {sorted(cols)[:5]}{'...' if len(cols) > 5 else ''}")
    else:
        print(f"[trino-fix] 警告：未能解析到任何SQL别名映射")

    # 查找所有列引用：包括 alias."column" 和直接 "column" 两种情况
    # 模式1：带表别名的列引用 alias."column"
    col_ref_with_alias_pattern = re.compile(
        r'(?P<alias>[`"\[\]]?[A-Za-z_]\w*[`"\[\]]?)\s*\.\s*"(?P<col>[^"]+)"',
        re.IGNORECASE
    )

    fixed_sql = sql
    replacements = []

    # 先处理带表别名的列引用
    for match in col_ref_with_alias_pattern.finditer(sql):
        alias = _norm_ident(match.group("alias"))
        col = match.group("col").lower()
        full_match = match.group(0)

        # 检查列是否在白名单中
        if alias in alias_to_columns:
            allowed_cols = alias_to_columns[alias]
            if col not in allowed_cols:
                print(
                    f"[trino-fix] 检测到不存在的列: {full_match} (别名: {alias}, 列: {col}, 可用列: {sorted(allowed_cols)})")
                # 列不在白名单中，尝试修复
                if allowed_cols:
                    # 检查上下文，判断是否是"是否有记录"的场景
                    # 查找 COUNT(e."event_id") 在 CASE WHEN COUNT(...) > 0 中的情况
                    match_start = match.start()
                    match_end = match.end()
                    context = sql[max(0, match_start - 200):min(len(sql), match_end + 200)]

                    # 检查是否是 CASE WHEN COUNT(...) > 0 的模式（用于判断"是否有记录"）
                    # 匹配模式：CASE WHEN COUNT(e."event_id") > 0
                    is_case_when_count = re.search(
                        r'CASE\s+WHEN\s+COUNT\s*\(\s*' + re.escape(full_match) + r'\s*\)\s*>',
                        context,
                        re.IGNORECASE | re.DOTALL
                    )

                    # 检查是否是COUNT场景
                    is_count_context = re.search(
                        r'\bCOUNT\s*\(\s*' + re.escape(full_match) + r'\s*\)',
                        context,
                        re.IGNORECASE | re.DOTALL
                    )

                    if is_case_when_count:
                        # 用于"是否有记录"判断，优先使用id列，如果没有id列则使用COUNT(*)
                        if "id" in allowed_cols:
                            replacement_col = "id"
                            new_ref = f'{match.group("alias")}."{replacement_col}"'
                            replacements.append((full_match, new_ref, f"COUNT判断是否有记录，替换为id列"))
                        else:
                            replacements.append((full_match, "*", f"COUNT判断是否有记录，替换为*"))
                    elif is_count_context:
                        # COUNT场景但不是"是否有记录"判断，优先使用id列
                        if "id" in allowed_cols:
                            replacement_col = "id"
                            new_ref = f'{match.group("alias")}."{replacement_col}"'
                            replacements.append((full_match, new_ref, f"COUNT场景，列不存在，替换为id列"))
                        else:
                            replacement_col = list(allowed_cols)[0]
                            new_ref = f'{match.group("alias")}."{replacement_col}"'
                            replacements.append((full_match, new_ref, f"COUNT场景，列不存在，替换为{replacement_col}"))
                    else:
                        # 其他场景，优先使用id列，如果没有id列则使用第一个存在的列
                        if "id" in allowed_cols:
                            replacement_col = "id"
                        else:
                            replacement_col = list(allowed_cols)[0]
                        new_ref = f'{match.group("alias")}."{replacement_col}"'
                        replacements.append((full_match, new_ref, f"列不存在，替换为{replacement_col}"))
                else:
                    # 表中没有列，无法修复
                    print(f"[trino-fix] 警告：表{alias}没有可用列，无法修复列引用: {full_match}")

    # 处理直接列引用（不带表别名的情况，如 SELECT "user_id" FROM table）
    # 只在没有表别名或只有一个表的情况下检查
    if len(sql_tables_found) == 1:
        # 获取所有可用列
        _, matched_table = sql_tables_found[0]
        allowed_cols_for_direct = set()
        if matched_table and matched_table in table_to_columns:
            allowed_cols_for_direct = table_to_columns[matched_table]
        elif "" in alias_to_columns:
            allowed_cols_for_direct = alias_to_columns[""]

        if allowed_cols_for_direct:
            # 查找SELECT子句中的直接列引用（不在函数内）
            # 匹配模式：SELECT子句中的独立列引用，如 SELECT "user_id", "name", "age"
            select_pattern = re.compile(
                r'SELECT\s+(.*?)\s+FROM',
                re.IGNORECASE | re.DOTALL
            )
            select_match = select_pattern.search(sql)
            if select_match:
                select_clause = select_match.group(1)
                # 匹配独立的列引用：前面不是点号（避免匹配 alias."column"），后面是逗号、空格或FROM等
                # 使用负向前瞻和负向后顾，确保不在函数内
                independent_col_pattern = re.compile(
                    r'(?<!\.)"(?P<col>[^"]+)"(?=\s*(?:,|\s+FROM|\s+ORDER|\s+GROUP|\s+HAVING|\s+WHERE|\s*$))',
                    re.IGNORECASE
                )

                for match in independent_col_pattern.finditer(select_clause):
                    col = match.group("col").lower()
                    full_match = match.group(0)

                    # 跳过已经在replacements中的列（避免重复处理）
                    already_handled = any(old == full_match for old, _, _ in replacements)
                    if already_handled:
                        continue

                    # 检查列是否在白名单中
                    if col not in allowed_cols_for_direct:
                        print(
                            f"[trino-fix] 检测到不存在的直接列引用: {full_match} (列: {col}, 可用列: {sorted(allowed_cols_for_direct)})")
                        # 列不在白名单中，尝试修复
                        # 优先使用id列，如果没有id列则使用第一个存在的列
                        if "id" in allowed_cols_for_direct:
                            replacement_col = "id"
                        else:
                            replacement_col = list(allowed_cols_for_direct)[0]
                        new_ref = f'"{replacement_col}"'
                        replacements.append((full_match, new_ref, f"直接列引用不存在，替换为{replacement_col}"))

    # 执行替换
    if replacements:
        print(f"[trino-fix] 检测到 {len(replacements)} 个需要修复的列引用:")
        for old, new, reason in replacements:
            print(f"[trino-fix]   {old} -> {new} ({reason})")
            # 直接替换所有出现的地方
            fixed_sql = fixed_sql.replace(old, new)

        print(f"[trino-fix] 修复后的SQL: {fixed_sql[:500]}...")

    return fixed_sql


def _ensure_distinct_order_by(sql: str) -> str:
    """
    确保当使用 SELECT DISTINCT 时，ORDER BY 中的字段也在 SELECT 列表中
    Trino要求：For SELECT DISTINCT, ORDER BY expressions must appear in select list
    """
    # 检查是否使用了 DISTINCT
    if not re.search(r'\bSELECT\s+DISTINCT\b', sql, re.IGNORECASE):
        return sql

    # 提取 SELECT 子句
    select_match = re.search(r'SELECT\s+DISTINCT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
    if not select_match:
        return sql

    select_clause = select_match.group(1)

    # 提取 ORDER BY 子句（可能包含 DESC/ASC）
    order_by_match = re.search(r'ORDER\s+BY\s+(.*?)(?:\s+LIMIT|\s*$)', sql, re.IGNORECASE | re.DOTALL)
    if not order_by_match:
        return sql

    order_by_clause = order_by_match.group(1).strip()

    # 解析 SELECT 中的列（支持 alias."column" 和直接 "column"）
    select_cols = set()
    # 匹配 alias."column" 格式
    alias_col_pattern = re.compile(r'([`"\[\]]?[A-Za-z_]\w*[`"\[\]]?)\s*\.\s*"([^"]+)"', re.IGNORECASE)
    for match in alias_col_pattern.finditer(select_clause):
        alias = _norm_ident(match.group(1))
        col = match.group(2).lower()
        # 添加多种格式用于匹配
        select_cols.add(f'{match.group(1)}."{match.group(2)}"')  # 原始格式
        select_cols.add(f'{alias}."{col}"')  # 规范化格式
        select_cols.add(f'"{col}"')  # 不带别名格式

    # 匹配直接 "column" 格式（不在函数内）
    direct_col_pattern = re.compile(r'(?<!\.)"([^"]+)"', re.IGNORECASE)
    for match in direct_col_pattern.finditer(select_clause):
        col = match.group(1).lower()
        select_cols.add(f'"{match.group(1)}"')  # 原始格式
        select_cols.add(f'"{col}"')  # 小写格式

    # 解析 ORDER BY 中的列（去掉 DESC/ASC 等修饰符）
    order_by_col_refs = []
    # 匹配 alias."column" DESC/ASC 格式
    for match in alias_col_pattern.finditer(order_by_clause):
        alias = match.group(1)
        col = match.group(2)
        # 提取完整的列引用（包括可能的 DESC/ASC）
        match_start = match.start()
        # 查找后面的 DESC/ASC
        remaining = order_by_clause[match.end():]
        desc_asc_match = re.search(r'\s+(DESC|ASC)\b', remaining, re.IGNORECASE)
        if desc_asc_match:
            full_ref = order_by_clause[match_start:match.end() + desc_asc_match.end()]
        else:
            full_ref = match.group(0)

        # 规范化用于匹配
        alias_norm = _norm_ident(alias)
        col_lower = col.lower()
        order_by_col_refs.append({
            'full_ref': full_ref,
            'alias_col': f'{alias}."{col}"',
            'alias_col_norm': f'{alias_norm}."{col_lower}"',
            'direct_col': f'"{col}"',
            'direct_col_norm': f'"{col_lower}"'
        })

    # 匹配直接 "column" DESC/ASC 格式
    for match in direct_col_pattern.finditer(order_by_clause):
        col = match.group(1)
        # 提取完整的列引用（包括可能的 DESC/ASC）
        match_start = match.start()
        remaining = order_by_clause[match.end():]
        desc_asc_match = re.search(r'\s+(DESC|ASC)\b', remaining, re.IGNORECASE)
        if desc_asc_match:
            full_ref = order_by_clause[match_start:match.end() + desc_asc_match.end()]
        else:
            full_ref = match.group(0)

        col_lower = col.lower()
        order_by_col_refs.append({
            'full_ref': full_ref,
            'alias_col': None,
            'alias_col_norm': None,
            'direct_col': f'"{col}"',
            'direct_col_norm': f'"{col_lower}"'
        })

    # 检查 ORDER BY 中的列是否在 SELECT 中
    missing_cols = []
    for col_ref in order_by_col_refs:
        is_in_select = False
        # 检查各种格式
        if col_ref['alias_col'] and col_ref['alias_col'] in select_cols:
            is_in_select = True
        elif col_ref['alias_col_norm'] and col_ref['alias_col_norm'] in select_cols:
            is_in_select = True
        elif col_ref['direct_col'] and col_ref['direct_col'] in select_cols:
            is_in_select = True
        elif col_ref['direct_col_norm'] and col_ref['direct_col_norm'] in select_cols:
            is_in_select = True

        if not is_in_select:
            # 提取列引用部分（去掉 DESC/ASC）
            col_only = re.sub(r'\s+(DESC|ASC)\s*$', '', col_ref['full_ref'], flags=re.IGNORECASE).strip()
            missing_cols.append(col_only)

    if not missing_cols:
        return sql

    # 需要添加缺失的列到 SELECT 子句
    print(f"[trino-fix] 检测到 DISTINCT + ORDER BY 问题，ORDER BY 中的列不在 SELECT 中: {missing_cols}")

    # 在 SELECT 子句末尾添加缺失的列（在最后一个列之后，FROM 之前）
    # 找到最后一个列的位置（考虑换行和缩进）
    lines = select_clause.split('\n')
    last_line = lines[-1].strip()
    if last_line and not last_line.endswith(','):
        # 最后一行没有逗号，添加逗号和换行
        new_select_clause = select_clause.rstrip() + ',\n    ' + ',\n    '.join(missing_cols)
    else:
        # 最后一行有逗号，直接添加
        new_select_clause = select_clause.rstrip() + '\n    ' + ',\n    '.join(missing_cols)

    # 替换 SELECT 子句
    fixed_sql = sql[:select_match.start(1)] + new_select_clause + sql[select_match.end(1):]

    print(f"[trino-fix] 修复后的SQL（添加了ORDER BY中的列到SELECT）: {fixed_sql[:500]}...")

    return fixed_sql


def _exec_trino_unified(
    user_question: str,
    tables: List[dict],
    entity_key: str,
    user_id: str = None,
    relationship_data: dict = None
) -> dict:
    """
    Trino统一查询处理：利用Trino的跨catalog能力，生成一个统一的SQL

    Args:
        user_question: 用户问题
        tables: 表对象列表
        entity_key: 实体主键
        user_id: 用户ID（可选，用于多用户隔离）
        relationship_data: 关系卡片数据（可选，修复后与 _exec_cluster 对齐使用关系卡片增强）

    修复说明：
    - 原实现完全没使用关系卡片，跨catalog场景下传统JOIN推断效果差
    - 修复后与 _exec_cluster 走相同的判断逻辑：有关系卡片就用关系卡片增强的 rels_block，
      并把 relationship_cards_info 一并渲染到 trino_multi_table.txt 提示词中
    """
    print(f"[trino] 开始统一查询处理，共 {len(tables)} 张表")

    # 1. 获取真正的Trino连接信息
    if not tables:
        raise ValueError("表列表为空")

    # 从连接名获取Trino主连接信息
    first_table = tables[0]
    trino_connect_name = first_table.get("connect_name", "")

    # 查找Trino主连接（通常是trino-开头但不带具体数据源后缀）
    # 或者查找任何包含"trino"的连接配置
    from controllers.datasource.datasource_tool import DatasourceInfo

    # 尝试找到Trino连接配置
    trino_connect_info = None

    print(f"[DEBUG] 开始查找Trino连接，表连接名: {trino_connect_name}")

    # 方案1：查找名为"trino"的连接
    trino_connect_info = map_connect_name_to_connect_info("trino", DatasourceInfo, user_id=user_id)
    print(f"[DEBUG] 方案1查找'trino': {trino_connect_info is not None}")

    # 方案2：如果没找到，尝试去掉后缀查找
    if not trino_connect_info and trino_connect_name:
        base_name = trino_connect_name.split('-')[0]  # "trino-mysql-8" -> "trino"
        trino_connect_info = map_connect_name_to_connect_info(base_name, DatasourceInfo, user_id=user_id)
        print(f"[DEBUG] 方案2查找'{base_name}': {trino_connect_info is not None}")

    # 方案3：如果还没找到，查找第一个包含trino的连接
    if not trino_connect_info:
        from core.connect_info_encryptor import decrypt_connect_info
        all_connections = DatasourceInfo.query.all()
        print(f"[DEBUG] 所有连接配置:")
        for conn in all_connections:
            print(f"[DEBUG]   - {conn.connect_name}: {conn.connect_info[:100] if conn.connect_info else 'None'}...")
            if "trino" in conn.connect_name.lower():
                # 注意：数据库中存储的是加密后的 connect_info，需要先解密再使用
                trino_connect_info = decrypt_connect_info(conn.connect_info)
                print(f"[DEBUG] 方案3找到包含trino的连接: {conn.connect_name}")
                break

    if not trino_connect_info:
        raise ValueError(f"找不到Trino连接信息，当前连接名: {trino_connect_name}")

    print(f"[trino] 最终使用连接配置: {trino_connect_info[:100]}...")
    print(f"[trino] 连接信息类型: {type(trino_connect_info)}")

    # 检查是否是真正的Trino连接
    if not trino_connect_info or not trino_connect_info.startswith("trino://"):
        print(f"[WARNING] 找到的连接不是Trino连接: {trino_connect_info}")
        print(f"[WARNING] 回退到传统分簇处理...")
        raise ValueError("未找到真正的Trino连接配置，请添加格式为 trino://username@host:port/ 的连接")

    engine = get_db_engine(trino_connect_info)

    # 2. 构建跨catalog的表结构信息，使用完整的catalog.schema.table格式
    trino_tables = []
    for t in tables:
        connect_name = t.get("connect_name", "") or ""
        table_name = t.get("table_name")
        database_name = (t.get("database_name") or "").strip()

        catalog = None
        schema = None

        # 1) 优先从 database_name 中解析 catalog/schema（格式可能为 catalog/schema）
        if database_name:
            if "/" in database_name:
                catalog_part, schema_part = database_name.split("/", 1)
                catalog = (catalog_part or "").strip() or None
                schema = (schema_part or "").strip() or None
            else:
                # 只有 schema 信息
                schema = database_name.strip() or None

        conn_lower = connect_name.lower()

        # 2) 如果仍缺少 catalog，根据 connect_name 推断
        if not catalog and "mysql" in conn_lower:
            if re.search(r"mysql[\-_]?8", conn_lower):
                catalog = "mysql8"
            elif re.search(r"mysql[\-_]?5", conn_lower):
                catalog = "mysql5"
            else:
                catalog = "mysql"
        elif not catalog and "oracle" in conn_lower:
            catalog = "oracle"
        elif not catalog and ("pgsql" in conn_lower or "postgres" in conn_lower):
            catalog = "postgres"
        elif not catalog and conn_lower.startswith("trino-"):
            catalog = connect_name.replace("trino-", "").replace("-", "_")

        # 3) schema 兜底
        if not schema:
            if catalog in ("oracle",):
                schema = "my_schema"
            elif catalog in ("dm",):
                # 达梦 DM 默认 schema 是用户名大写，"my_schema" 仅作为兜底占位符
                schema = "my_schema"
            elif catalog in ("postgres", "postgresql"):
                schema = "public"
            else:
                schema = "default"

        if not catalog:
            raise ValueError(f"无法为表 {table_name} 推断 Trino catalog，请检查数据源配置。")

        # 构建完整表名
        full_table_name = f'"{catalog}"."{schema}"."{table_name}"'

        print(f"[trino] 表映射: {table_name} -> {full_table_name} (connect_name: {connect_name})")

        trino_table = {
            "table_name": full_table_name,  # 使用完整路径
            "alias": f"t{len(trino_tables) + 1}",
            "columns": t.get("columns", []),
            "foreign_keys": t.get("foreign_keys", []),
            "database_name": catalog,  # 用于模板渲染
        }
        # 调试信息：检查列信息是否正确传递
        col_names = [c.get("name", "") for c in trino_table.get("columns", [])]
        print(
            f"[trino] 表 {table_name} 的列信息: {len(col_names)} 列 - {col_names[:5]}{'...' if len(col_names) > 5 else ''}")
        trino_tables.append(trino_table)

    # 3. 使用Trino模板生成SQL
    tpl = load_prompt("trino_multi_table.txt")
    tables_block = make_tables_block("trino", trino_tables)

    # ✅ 修复：与 _exec_cluster 对齐，根据是否有关系卡片选择不同的 JOIN 关系块和关系卡片信息
    has_relationship_cards = relationship_data and (
        relationship_data.get("cards") or relationship_data.get("join_suggestions")
    )

    if has_relationship_cards:
        # 使用关系卡片增强的JOIN关系
        rels_block = make_rels_block_with_relationship_cards(trino_tables, relationship_data)
        # ✅ 修复：渲染关系卡片详情到提示词（之前传了空字符串位置）
        relationship_cards_info = format_relationship_cards_for_prompt(relationship_data, trino_tables)
        print(f"[trino] ✅ 使用关系卡片增强的SQL生成")
        print(f"[trino]   - 关系卡片数: {len(relationship_data.get('cards', {}))}")
        print(f"[trino]   - JOIN建议数: {len(relationship_data.get('join_suggestions', []))}")
        print(f"[trino]   - JOIN关系块长度: {len(rels_block)} 字符")
        print(f"[trino]   - 关系卡片信息长度: {len(relationship_cards_info)} 字符")
        if relationship_cards_info:
            print(f"[trino]   - 关系卡片信息预览:\n{relationship_cards_info[:500]}...")
    else:
        # 使用传统的JOIN关系推断
        rels_block = make_rels_block(trino_tables)
        relationship_cards_info = ""  # 无关系卡片时传空字符串
        print(f"[trino] ⚠️ 无关系卡片，使用传统JOIN推断")
        print(f"[trino]   - JOIN关系块: {rels_block[:200] if rels_block else '(无)'}")

    # 获取正确的catalog名称（从trino_tables中获取，而不是first_table）
    # 因为trino_tables中的表已经包含了完整的catalog.schema.table路径
    db_name_for_prompt = "跨catalog查询"
    if trino_tables:
        # 从第一个表的完整路径中提取catalog
        first_full_table = trino_tables[0].get("table_name", "")
        if first_full_table:
            # 提取catalog（去掉引号，取第一部分）
            parts = first_full_table.replace('"', '').split('.')
            if len(parts) >= 1:
                db_name_for_prompt = f"跨catalog查询（包含: {parts[0]}等）"

    prompt = render_prompt(
        tpl,
        db_name=db_name_for_prompt,
        tables_block=tables_block,
        tables_with_aliases_and_columns=tables_block,
        rels_block=rels_block,
        join_candidates=rels_block,
        # ✅ 修复：传入关系卡片信息（之前 trino_multi_table.txt 模板里 {{relationship_cards_info}} 一直为空）
        relationship_cards_info=relationship_cards_info,
        entity_key=entity_key,
        user_question=user_question,
    )

    print(f"[trino] 生成的提示词长度: {len(prompt)} 字符")

    # 4. 调用LLM生成SQL 
    try:
        response = QwenMaxLatest.qian_wen_llm(prompt, stream_type=False)
        content = response["choices"][0]["message"]["content"]

        # 使用系统内置的SQL解析函数
        parsed = _extract_sql_from_llm_text(content)

        if parsed["kind"] != "sql":
            raise ValueError(f"LLM未返回SQL: {parsed.get('text', 'unknown')}")

        sql_text = parsed["text"]
        print(f"[trino] LLM生成SQL: {sql_text}")

        # 5. 自动修复SQL中使用了不存在列的问题（仅Trino）
        try:
            sql_text = _fix_trino_sql_columns(sql_text, trino_tables)
        except Exception as fix_error:
            print(f"[trino] SQL自动修复失败: {fix_error}，继续使用原始SQL")

        # 5.5. 确保 DISTINCT + ORDER BY 的语法正确（Trino要求ORDER BY中的列必须在SELECT中）
        try:
            sql_text = _ensure_distinct_order_by(sql_text)
        except Exception as fix_error:
            print(f"[trino] DISTINCT+ORDER BY修复失败: {fix_error}，继续使用原始SQL")
        
        # 6. 执行SQL
        with engine.connect() as conn:
            data, warnings, sql_exec_ms = run_sql_safe_new(
                engine=engine,
                sql=sql_text,
                cluster_tables=trino_tables,
                db_type="trino",
                max_rows=1000,
                allow_semicolon_terminator=True
            )
            
            # 7. 构建返回结果
            entity_ids = []
            if data and isinstance(data, list) and len(data) > 0:
                # 提取entity_key值用于后续处理
                for row in data:
                    if entity_key in row and row[entity_key] is not None:
                        entity_ids.append(row[entity_key])

            print(f"[trino] 查询完成，返回 {len(data) if data else 0} 行")

            return {
                "db_type": "trino",
                "_connect_info_raw": trino_connect_info,
                "connect_info_safe": {
                    "type": "trino",
                    "database": first_table.get("database_name")
                },
                "tables": [{"table_name": t.get("table_name"), "alias": t.get("alias")} for t in trino_tables],
                "cluster_tables": trino_tables,
                "sql": sql_text,
                "target_sql": sql_text,  # 添加target_sql字段保持一致
                "data": data or [],
                "rows": data or [],  # 添加rows字段保持一致  
                "warnings": warnings or [],
                "entity_ids": entity_ids,
                "note": parsed.get("text", "")
            }

    except Exception as e:
        print(f"[trino] SQL执行失败: {str(e)}")
        raise


def _pick_template_by_db(db_type: str) -> str:
    m = {
        "mysql": "mysql_multi_table.txt",
        "postgresql": "postgresql_multi_table.txt",
        "mssql": "mssql_multi_table.txt",
        "oracle": "oracle_multi_table.txt",
        "sqlite": "sqlite_multi_table.txt",
        "trino": "trino_multi_table.txt",
        # 人大金仓（KingBase）- 基于 PostgreSQL 内核，使用独立的提示词文件
        "kingbase": "kingbase_multi_table.txt",
        # OceanBase MySQL 模式租户：使用独立的提示词文件（当前内容基于 MySQL 模板）
        "oceanbase": "oceanbase_multi_table.txt",
        # 达梦 DM：基于 Oracle 内核，使用独立的提示词文件（基于 Oracle 模板）
        "dm": "dm_multi_table.txt",
    }
    return m.get((db_type or "").lower(), "mysql_multi_table.txt")


def _find_entity_key_field(row: dict, entity_key: str) -> str | None:
    """
    在行数据中查找entity_key对应的字段名（支持别名匹配）- 全局辅助函数

    匹配规则（按优先级）：
    1. 精确匹配：字段名完全等于entity_key
    2. 别名匹配：字段名包含entity_key（如id匹配user_id、product_id）
    3. 下划线分隔匹配：字段名的最后一部分等于entity_key（如user_id的id部分）

    返回：匹配到的字段名，如果没有匹配则返回None
    """
    entity_key_lower = entity_key.lower()

    # 优先级1：精确匹配（区分大小写）
    if entity_key in row:
        return entity_key

    # 优先级2：精确匹配（不区分大小写）
    for k in row.keys():
        if k.lower() == entity_key_lower:
            return k

    # 优先级3：别名匹配（字段名包含entity_key）
    # 例如：entity_key="id" 匹配 "user_id"、"product_id"、"order_id"
    candidates = []
    for k in row.keys():
        k_lower = k.lower()
        # 检查是否包含entity_key（作为完整单词或下划线分隔的部分）
        if entity_key_lower in k_lower:
            # 匹配模式：
            # 1. entity_key 在末尾：*_id, *Id
            # 2. entity_key 在开头：id_*, Id*
            # 3. 精确匹配：id

            # 使用更宽松的匹配规则
            # 检查 entity_key 是否作为独立部分出现（通过下划线、大小写或字符串边界分隔）
            import re
            # 匹配：_id$, ^id_, _id_, 或完整的id
            pattern = rf'(^|_){re.escape(entity_key_lower)}(_|$)'
            if re.search(pattern, k_lower):
                candidates.append(k)

    # 如果找到候选字段
    if len(candidates) == 1:
        # 只有一个候选，直接返回
        return candidates[0]
    elif len(candidates) > 1:
        # 多个候选，选择最短的（更可能是主键）
        # 例如：["id", "user_id"] 选择 "id"
        shortest = min(candidates, key=len)
        return shortest

    # 没有找到匹配
    return None


def _collect_entity_ids(rows: List[dict], entity_key: str) -> Set[Any]:
    """
    收集实体 ID，同时过滤掉"空记录"（除了 entity_key 外，其他字段都是无效值）

    特殊情况：如果记录只有 entity_key 一个字段，则认为是有效的（用于聚合查询的跨簇融合）

    智能匹配：支持别名匹配，如 entity_key="id" 可以匹配 "user_id"、"product_id" 等
    """
    s = set()

    def has_valid_data(row: dict, entity_key_field: str) -> bool:
        """检查记录是否包含有效数据"""
        # 特殊情况1：如果只有 entity_key 一个字段，且有值，则认为是有效的
        if len(row) == 1 and entity_key_field in row and row[entity_key_field] is not None:
            return True

        # 特殊情况2：检查是否是统计查询结果（字段名包含 count/sum/avg/total/num 等）
        # 这些查询的结果即使为 0 也是有效的
        stat_keywords = ['count', 'sum', 'avg', 'total', 'num', 'amount', 'quantity', 'ratio', 'rate', 'percentage']
        is_stat_query = any(
            any(keyword in k.lower() for keyword in stat_keywords)
            for k in row.keys()
        )

        # 如果是统计查询，只要有非 None 的值就认为是有效的（即使值为 0）
        if is_stat_query:
            for k, v in row.items():
                if k == entity_key_field:
                    continue
                if v is not None:  # 只要不是 None，就认为是有效的（包括 0）
                    return True
            return False

        # 检查除了 entity_key 外是否有其他有效字段
        for k, v in row.items():
            if k == entity_key_field:
                continue
            # 如果有任何一个字段有有效值，则认为有有效数据
            if v is not None and v != 0 and v != 0.0 and v != "" and v is not False:
                return True
        return False

    # 首次查找entity_key字段（只需查找一次）
    entity_key_field = None
    if rows:
        entity_key_field = _find_entity_key_field(rows[0], entity_key)
        if entity_key_field:
            if entity_key_field != entity_key:
                print(f"[entity_key匹配] entity_key='{entity_key}' 匹配到别名字段: '{entity_key_field}'")
        else:
            print(f"[agg/entity_key匹配] ⚠️ 未找到 '{entity_key}' 对应字段（备用融合用，LLM语义融合不受影响）")
            print(f"[agg/entity_key匹配] 可用字段: {list(rows[0].keys()) if rows[0] else '(空)'}")
            return s

    for r in rows or []:
        if entity_key_field in r and r[entity_key_field] is not None:
            # 只收集那些有有效数据的记录的 ID
            if has_valid_data(r, entity_key_field):
                s.add(r[entity_key_field])

    return s


def _make_json_serializable(obj, _seen=None):
    """
    递归转换对象为 JSON 可序列化的格式
    处理常见的不可序列化类型：datetime, date, Decimal, bytes 等
    并检测循环引用以避免无限递归
    """
    # 初始化已访问对象的集合（用于检测循环引用）
    if _seen is None:
        _seen = set()

    # 基本类型直接返回（不需要检测循环引用）
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj

    # 检测循环引用（只对可变对象检测）
    obj_id = id(obj)
    if obj_id in _seen:
        # 检测到循环引用，返回一个安全的占位符
        return f"<CircularRef:{type(obj).__name__}>"

    # 处理特殊类型
    if isinstance(obj, datetime):
        # datetime 必须在 date 之前检查，因为 datetime 是 date 的子类
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, datetime_time):
        # 处理 time 类型（PostgreSQL 的 time 类型）
        return obj.isoformat()
    elif isinstance(obj, timedelta):
        # 处理 timedelta 类型
        return str(obj)
    elif isinstance(obj, UUID):
        # 处理 UUID 类型（PostgreSQL 的 uuid 类型）
        return str(obj)
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')
        except:
            return str(obj)
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, dict):
        # 标记当前对象为已访问
        _seen.add(obj_id)
        try:
            result = {}
            for k, v in obj.items():
                # 递归处理值，传递 _seen 集合
                result[k] = _make_json_serializable(v, _seen)
            return result
        finally:
            # 处理完后移除标记（允许在其他分支中再次访问）
            _seen.discard(obj_id)
    elif isinstance(obj, (list, tuple)):
        # 标记当前对象为已访问
        _seen.add(obj_id)
        try:
            result = [_make_json_serializable(item, _seen) for item in obj]
            return result
        finally:
            # 处理完后移除标记
            _seen.discard(obj_id)
    else:
        # 对于不认识的对象类型，尝试转换为字符串
        try:
            # 尝试检查是否是简单的可序列化类型
            import json
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            # 无法序列化，返回类型名称
            return f"<{type(obj).__name__}>"


# 全局异常处理装饰器，确保所有 JSON 序列化都能安全处理
def _safe_json_serializable(obj):
    """
    安全的 JSON 序列化包装器，捕获所有可能的异常
    """
    try:
        return _make_json_serializable(obj)
    except Exception as e:
        return f"<SerializationError:{type(obj).__name__}:{str(e)}>"


def _merge_sets(sets: List[Set[Any]], strategy: str) -> Set[Any]:
    if not sets:
        return set()
    if strategy == "OR":
        out = set()
        for s in sets:
            out |= s
        return out
    # 默认 AND
    out = sets[0].copy()
    for s in sets[1:]:
        out &= s
    return out


def _filter_by_ids(rows: List[dict], entity_key: str, final_ids: Set[Any]) -> List[dict]:
    return [r for r in (rows or []) if r.get(entity_key) in final_ids]


def _filter_clusters_by_question(cluster_results: List[dict], user_question: str) -> tuple[list[dict], list[str]]:
    """
    旧版簇过滤逻辑已关闭，直接返回所有簇。
    """
    return cluster_results, []


def _llm_fuse_results(
        user_question: str,
        cluster_results: List[dict],
        relationship_data: dict = None,
        model_config_dict: dict = None
) -> dict:
    """
    使用LLM进行智能结果融合（语义理解融合）

    核心理念：
    - 不依赖固定的entity_key进行硬编码匹配
    - 而是让LLM理解用户意图，通过语义分析判断记录的关联性
    - 支持名称匹配、编码匹配、组合匹配等多种融合方式

    Args:
        user_question: 用户问题
        cluster_results: 各簇的查询结果
        relationship_data: 关系卡片数据
        model_config_dict: 模型配置字典（可选，用于避免访问数据库）

    Returns:
        {
            "analysis": {...},
            "fusion_strategy": "AND/OR/PRIORITY/SINGLE_SOURCE",
            "fused_rows": [...],
            "conflicts": [...],
            "warnings": [...],
            "fusion_time_ms": 123  # 融合耗时（毫秒）
    }
    """
    fusion_start_time = time_module.time()

    try:
        # 加载融合提示词
        prompt_load_start = time_module.time()
        tpl = load_prompt("result_fusion.txt")
        prompt_load_ms = int((time_module.time() - prompt_load_start) * 1000)
        print(f"[agg] 融合提示词加载耗时: {prompt_load_ms}ms")

        # 构建簇结果文本
        data_prep_start = time_module.time()
        cluster_results_text = []
        total_rows_count = 0
        for i, r in enumerate(cluster_results):
            db_type = r.get("db_type", "unknown")
            rows = r.get("rows", [])
            tables = r.get("tables", [])
            table_names = [t.get("table_name", "") for t in tables]

            cluster_text = f"### 数据源 {i + 1} ({db_type})\n"
            cluster_text += f"涉及表: {', '.join(table_names)}\n"
            cluster_text += f"返回行数: {len(rows)}\n"

            # 限制展示的行数，避免提示词过长
            # 优化：每个簇最多展示10行（从20降低到10）
            sample_rows = rows[:10] if len(rows) > 10 else rows
            total_rows_count += len(sample_rows)

            if sample_rows:
                # 优化：限制每行的字段数量，只保留前15个字段
                simplified_rows = []
                for row in sample_rows:
                    if isinstance(row, dict):
                        # 只保留前15个字段
                        limited_row = dict(list(row.items())[:15])
                        simplified_rows.append(limited_row)
                    else:
                        simplified_rows.append(row)

                cluster_text += f"数据样例:\n```json\n{json.dumps(simplified_rows, ensure_ascii=False, indent=2, default=str)}\n```\n"
                if len(rows) > 10:
                    cluster_text += f"(还有 {len(rows) - 10} 条数据未展示)\n"
            else:
                cluster_text += "无数据返回\n"

            cluster_results_text.append(cluster_text)

        data_prep_ms = int((time_module.time() - data_prep_start) * 1000)
        print(f"[agg] 融合数据准备耗时: {data_prep_ms}ms，实际传递 {total_rows_count} 行数据")

        # ✅ 修复：构建"参与融合的表集合"，并按白名单过滤关系数据
        # 之前直接把所有数据源的 join_suggestions 一起塞给 LLM，会混入无关表的 JOIN，
        # 干扰 LLM 的语义对齐判断。这里先收集参与本次融合的所有表名，
        # 再用 filter_relationship_data_by_tables 把无关关系全部过滤掉。
        fusion_table_names_set = set()
        for r in cluster_results:
            for t in (r.get("tables") or []):
                tn = t.get("table_name", "")
                if tn:
                    fusion_table_names_set.add(tn)
        print(f"[agg] 融合阶段：参与融合的表集合 {sorted(fusion_table_names_set)}（共 {len(fusion_table_names_set)} 张表）")

        if relationship_data:
            relationship_data = filter_relationship_data_by_tables(
                relationship_data, fusion_table_names_set
            )

        # 构建关系信息文本
        relationship_info = "（未发现相关表之间的关系信息）"
        if relationship_data:
            cards = relationship_data.get("cards", {})
            join_suggestions = relationship_data.get("join_suggestions", [])

            if cards or join_suggestions:
                rel_lines = []

                # 添加JOIN建议（已被白名单过滤，仅展示融合表范围内的关系）
                if join_suggestions:
                    rel_lines.append("可用的JOIN关系:")
                    for sug in join_suggestions[:10]:  # 限制数量
                        from_t = sug.get("from_table", "")
                        to_t = sug.get("to_table", "")
                        from_c = sug.get("from_column", "")
                        to_c = sug.get("to_column", "")
                        confidence = sug.get("confidence", 0)
                        rel_lines.append(f"  - {from_t}.{from_c} = {to_t}.{to_c} (置信度: {confidence:.2f})")

                # 添加业务关系描述
                for table_name, card_info in cards.items():
                    join_summary = card_info.get("join_summary", "")
                    if join_summary:
                        rel_lines.append(f"- {table_name}: {join_summary}")

                if rel_lines:
                    relationship_info = "\n".join(rel_lines)

        # 渲染提示词（不再需要entity_key，改为语义理解融合）
        prompt_render_start = time_module.time()
        prompt = render_prompt(
            tpl,
            user_question=user_question,
            relationship_info=relationship_info,
            cluster_results="\n\n".join(cluster_results_text)
        )
        prompt_render_ms = int((time_module.time() - prompt_render_start) * 1000)
        prompt_length = len(prompt)
        print(f"[agg] 融合提示词渲染耗时: {prompt_render_ms}ms，提示词长度: {prompt_length} 字符")

        # 调用LLM
        llm_call_start = time_module.time()
        llm_ret = QwenMaxLatest.qian_wen_llm(prompt, stream_type=False, model_config_dict=model_config_dict)
        llm_call_ms = int((time_module.time() - llm_call_start) * 1000)
        print(f"[agg] 融合LLM调用耗时: {llm_call_ms}ms")

        content = llm_ret["choices"][0]["message"]["content"]

        # 解析LLM返回的JSON（增强容错）
        parse_start = time_module.time()
        result = None
        parse_error_detail = None

        # 方法1：提取 markdown json 代码块
        json_match = re.search(r"```json\s*(.+?)\s*```", content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError as e:
                parse_error_detail = f"代码块JSON解析失败: {e}"
                # 尝试修复常见问题：缺少结尾的 } 或 ]
                json_str_fixed = _try_fix_incomplete_json(json_str)
                if json_str_fixed:
                    try:
                        result = json.loads(json_str_fixed)
                        parse_error_detail = None  # 修复成功
                    except json.JSONDecodeError:
                        parse_error_detail += f" -> 修复后仍然失败: {e}"

        # 方法2：尝试直接解析（去掉首尾空白）
        if result is None:
            try:
                result = json.loads(content.strip())
            except json.JSONDecodeError as e:
                if not parse_error_detail:
                    parse_error_detail = f"直接解析失败: {e}"
                # 尝试修复
                content_fixed = _try_fix_incomplete_json(content.strip())
                if content_fixed:
                    try:
                        result = json.loads(content_fixed)
                        parse_error_detail = None
                    except json.JSONDecodeError:
                        parse_error_detail += f" -> 修复后仍然失败"

        parse_ms = int((time_module.time() - parse_start) * 1000)

        # 如果仍然解析失败，回退到规则融合
        if result is None:
            print(f"[agg] ⚠️ LLM融合JSON解析失败: {parse_error_detail}")
            print(f"[agg] LLM返回内容预览 (前500字符): {content[:500]}")
            # 返回空结果，让调用方回退到规则融合
            return None

        print(f"[agg] 融合结果解析耗时: {parse_ms}ms")

        print(f"[agg] LLM融合完成: 策略={result.get('fusion_strategy')}, 结果数={len(result.get('fused_rows', []))}")

        # 输出分析信息（如有）
        analysis = result.get("analysis", {})
        if analysis:
            relevant = analysis.get("relevant_sources", [])
            irrelevant = analysis.get("irrelevant_sources", [])
            if irrelevant:
                print(
                    f"[agg] LLM融合分析: 排除不相关数据源 {irrelevant}, 原因: {analysis.get('irrelevant_reason', '未知')}")
            if relevant:
                print(f"[agg] LLM融合分析: 相关数据源 {relevant}")

        # 计算融合耗时并添加到结果中
        fusion_time_ms = int((time_module.time() - fusion_start_time) * 1000)
        result["fusion_time_ms"] = fusion_time_ms
        print(f"[agg] LLM融合总耗时: {fusion_time_ms}ms (提示词准备: {prompt_load_ms + data_prep_ms + prompt_render_ms}ms, LLM调用: {llm_call_ms}ms, 解析: {parse_ms}ms)")

        return result

    except Exception as e:
        print(f"[agg] LLM融合失败: {e}, 回退到规则融合")
        import traceback
        print(f"[agg] 融合失败详细堆栈:\n{traceback.format_exc()}")
        # 返回空结果，让调用方回退到规则融合
        return None


def _should_use_llm_fusion(cluster_results: List[dict]) -> bool:
    """
    判断是否应该使用LLM智能融合

    设计理念：
    - 多簇场景应该优先使用 LLM 融合（基于语义理解的智能融合）
    - 只有在数据量过大或簇数量过多时才回退到规则融合
    - 不再依赖entity_key的存在性

    触发条件：
    1. 有多个簇（多数据源场景）
    2. 总行数适中（避免LLM处理过大数据）
    3. 簇数量适中（避免过于复杂的融合场景）
    """
    # 条件1：必须有多个簇
    if len(cluster_results) < 2:
        return False

    # 条件2：检查总行数是否适中
    # 提高限制：从100行提高到500行（LLM完全可以处理）
    total_rows = sum(len(r.get("rows", [])) for r in cluster_results)
    if total_rows > 500:
        print(f"[LLM融合判断] 数据量过大（{total_rows}行），回退到规则融合")
        return False

    # 条件3：簇数量适中（避免过于复杂的融合场景）
    if len(cluster_results) > 5:
        print(f"[LLM融合判断] 簇数量过多（{len(cluster_results)}个），回退到规则融合")
        return False

    # 条件4：至少有一个簇返回了数据
    valid_clusters = [r for r in cluster_results if r.get("rows")]
    if not valid_clusters:
        print(f"[LLM融合判断] 所有簇都无数据，无需融合")
        return False

    print(f"[LLM融合判断] 满足条件，使用LLM智能融合（{len(cluster_results)}个簇，共{total_rows}行）")
    return True


def _exec_cluster_parallel(cluster_idx: int, db_type: str, connect_info: dict,
                           tables: List[dict], entity_key: str, relationship_data: dict = None,
                           user_question: str = "", model_config_dict: dict = None) -> Tuple[int, dict]:
    """
    并行执行簇的包装函数（用于 ThreadPoolExecutor）

    Args:
        cluster_idx: 簇的索引（用于日志标识）
        db_type: 数据库类型
        connect_info: 连接信息
        tables: 表对象列表
        entity_key: 实体关联键
        relationship_data: 关系卡片数据（可选）
        user_question: 用户问题（用于日志）
        model_config_dict: 模型配置字典（可选，用于避免在线程中访问数据库）

    Returns:
        (cluster_idx, result): 元组，包含簇索引和执行结果
    """
    start_time = time_module.time()
    db_name = tables[0].get("database_name") if tables else "unknown"
    print(f"[_exec_cluster_parallel][{db_type}] 簇 {cluster_idx + 1} 开始执行，数据库={db_name}...")

    try:
        result = _exec_cluster(
            user_question=user_question,
            db_type=db_type,
            connect_info=connect_info,
            tables=tables,
            entity_key=entity_key,
            relationship_data=relationship_data,
            model_config_dict=model_config_dict  # 传递模型配置
        )

        elapsed_ms = int((time_module.time() - start_time) * 1000)
        print(f"[_exec_cluster_parallel][{db_type}] 簇 {cluster_idx + 1} 执行完成，返回 {len(result.get('rows', []))} 行数据，耗时 {elapsed_ms}ms")

        return (cluster_idx, result)

    except ValueError as ve:
        elapsed_ms = int((time_module.time() - start_time) * 1000)
        print(f"[_exec_cluster_parallel][{db_type}] 簇 {cluster_idx + 1} 执行失败（ValueError）: {str(ve)}")
        error_result = {
            "db_type": db_type,
            "connect_info_safe": {"type": db_type},
            "tables": [{"table_name": t.get("table_name")} for t in tables],
            "target_sql": "",
            "rows": [],
            "entity_ids": [],
            "note": f"查询条件校验失败: {str(ve)}",
            "error": str(ve),
            "warnings": ["簇执行失败"],
            "_cluster_idx": cluster_idx,
            "_elapsed_ms": elapsed_ms
        }
        return (cluster_idx, error_result)

    except Exception as e:
        elapsed_ms = int((time_module.time() - start_time) * 1000)
        import traceback
        error_detail = traceback.format_exc()
        print(f"[_exec_cluster_parallel][{db_type}] 簇 {cluster_idx + 1} 执行异常: {str(e)}")
        print(f"[_exec_cluster_parallel][{db_type}] 详细错误堆栈:\n{error_detail}")

        user_friendly_msg = "查询执行失败"
        if "does not exist" in str(e):
            if "relation" in str(e):
                user_friendly_msg = "表不存在，可能是schema配置问题"
            elif "column" in str(e):
                user_friendly_msg = "字段不存在，可能是大模型推测错误"

        error_result = {
            "db_type": db_type,
            "connect_info_safe": {"type": db_type},
            "tables": [{"table_name": t.get("table_name")} for t in tables],
            "target_sql": "",
            "rows": [],
            "entity_ids": [],
            "note": user_friendly_msg,
            "error": str(e),
            "warnings": ["簇执行失败"],
            "_cluster_idx": cluster_idx,
            "_elapsed_ms": elapsed_ms
        }
        return (cluster_idx, error_result)


# ---- 核心执行：同簇内生成单条 SQL 并执行 ----

# 获取卡片数据
# 基于语义检索查向量库，获取目标数据卡片的id，随后根据id查数据库，获取卡片内容
def get_data_card_json(
        input_question: str,
        class_name: str,  # 用户向量检索空间类名
        distance_threshold: float = None,  # 距离阈值（越小越严格），None 时从配置读取
        max_results: int = None,  # 最大返回数量，None 时从配置读取
        min_results: int = None,  # 最小返回数量，None 时从配置读取
        query_limit: int = None,  # 初始查询候选数量，None 时从配置读取
        enable_rerank: bool = True,  # 是否启用重排序（默认启用）
        rerank_top_n: int = None,  # 重排序后保留的 top N 结果（None 则使用 max_results）
        datasource_id=None  # 数据源ID过滤（支持 str 单个ID 或 list 多个ID）
):
    """
    基于向量相似度召回数据卡片（支持重排序 + 数据源过滤）

    参数：
    - input_question: 用户问题
    - class_name: 用户向量检索空间类名
    - distance_threshold: 距离阈值，建议 0.5-0.6（越小越严格）
                         None 时从环境变量 VECTOR_SEARCH_DISTANCE_THRESHOLD 读取（默认 0.55）
    - max_results: 最大返回数量，None 时从环境变量 VECTOR_SEARCH_MAX_RESULTS 读取（默认 20）
    - min_results: 最小返回数量，None 时从环境变量 VECTOR_SEARCH_MIN_RESULTS 读取（默认 2）
    - query_limit: 初始查询候选数量，None 时从环境变量 VECTOR_SEARCH_QUERY_LIMIT 读取（默认 50）
    - enable_rerank: 是否启用重排序（默认 True），可提升召回精度
    - rerank_top_n: 重排序后保留的数量（默认使用 max_results）
    - datasource_id: 数据源ID过滤（可选），支持：
        * str: 单个数据源ID，仅检索该数据源的卡片
        * list: 多个数据源ID，检索这些数据源的卡片（OR 关系）
        * None: 不过滤，检索所有卡片

    返回：
    {
        "doc_ids": [...],
        "data_card_results": [...]
    }
    """

    # 从配置中读取默认值（如果参数为 None）
    if distance_threshold is None:
        distance_threshold = float(get_env('VECTOR_SEARCH_DISTANCE_THRESHOLD'))
    if max_results is None:
        max_results = int(get_env('VECTOR_SEARCH_MAX_RESULTS'))
    if min_results is None:
        min_results = int(get_env('VECTOR_SEARCH_MIN_RESULTS'))
    if query_limit is None:
        query_limit = int(get_env('VECTOR_SEARCH_QUERY_LIMIT'))

    # 1、基于语义检索查向量库（方法中会对输入的问题向量化），返回目标卡片列表
    # 使用基于阈值的智能召回 + 重排序（可选） + 数据源过滤（可选）
    # 返回格式：(data_cards_list, usage_dict)
    data_cards_list, vector_usage = search_vector(
        input_question,
        class_name=class_name,
        distance_threshold=distance_threshold,
        max_results=max_results,
        min_results=min_results,
        query_limit=query_limit,
        enable_rerank=enable_rerank,
        rerank_top_n=rerank_top_n,
        datasource_id=datasource_id  # 新增：传递数据源ID过滤
    )

    # 2、根据向量检索结果中的doc_id查数据库，获取完整数据卡片结果
    # 提取 doc_ids 并去重（保持顺序）
    doc_ids_raw = [item["doc_id"] for item in data_cards_list]
    # 使用 dict.fromkeys() 去重并保持顺序：防止召回重复的数据卡片数据
    doc_ids = list(dict.fromkeys(doc_ids_raw))

    # 如果去重后数量减少了，打印日志
    if len(doc_ids) < len(doc_ids_raw):
        print(
            f"[向量召回去重] 原始结果 {len(doc_ids_raw)} 条，去重后 {len(doc_ids)} 条（移除了 {len(doc_ids_raw) - len(doc_ids)} 条重复数据卡片）")

    data_card_results = []
    result_doc_ids = []

    for doc_id in doc_ids:
        if not doc_id:
            continue

        # 查数据卡片库，获取完整数据卡片内容
        record = get_data_card_by_doc_id(str(doc_id))  # 假设返回 dict，例如 {"doc_id": "...", "card_data": "..."}

        # 没获取到数据卡片具体内容时的容错
        # 如果没有查到，抛出异常
        if record is None:
            raise ValueError(f"未找到对应 doc_id 的数据卡片：{doc_id}")

        # 再检查 card_data 字段
        if "card_data" not in record or record["card_data"] is None:
            raise ValueError(f"数据卡片中缺少 card_data 字段：{doc_id}")

        card_data_str = record['card_data']

        if card_data_str:
            try:
                # 将 TEXT 列的 JSON 字符串反序列化为 Python 对象
                card_data_obj = json.loads(card_data_str)
                data_card_results.append(card_data_obj)
                result_doc_ids.append(doc_id)
            except json.JSONDecodeError:
                # 如果不是合法 JSON，就原样放进去
                data_card_results.append(card_data_str)
                result_doc_ids.append(doc_id)

    result = {
        "doc_ids": [str(d) for d in result_doc_ids if d],
        "data_card_results": data_card_results,
        "usage": vector_usage  # 返回向量检索的 usage 信息
    }
    return result


# 抽取白名单工具函数
def build_cluster_tables(tables: list[dict]) -> list[dict]:
    """
    构建簇内表的白名单结构，保留字段名和类型信息
    """
    return [
        {
            "table_name": t["table_name"],
            "columns": [
                {
                    "name": c["name"],
                    "type": c.get("type", "unknown")  # 保留类型信息用于安全校验
                }
                for c in (t.get("columns") or []) if c.get("name")
            ]
        }
        for t in (tables or [])
    ]


def _exec_cluster(user_question: str, db_type: str, connect_info: str,
                  tables: List[dict], entity_key: str, relationship_data: dict = None,
                  debug: bool = False, model_config_dict: dict = None) -> dict:
    """
    - 从对应方言 txt 加载模板
    - 渲染【白名单表字段】【允许关系】【关系卡片信息】
    - 调 LLM 生成单条 SQL
    - run_sql_safe_new 执行

    Args:
        user_question: 用户问题
        db_type: 数据库类型
        connect_info: 连接信息
        tables: 表对象列表
        entity_key: 实体关联键
        relationship_data: 关系卡片数据（可选）
        debug: 调试模式
        model_config_dict: 模型配置字典（可选，用于避免在线程中访问数据库）
    """
    db_name = tables[0].get("database_name") if tables else ""
    cluster_table_names = [t.get("table_name", "unknown") for t in tables]
    print(f"[_exec_cluster][{db_type}] 开始执行，簇索引={hash(tuple(cluster_table_names)) % 10000}，表数量={len(tables)}, 数据库={db_name}")

    # 始终使用数据库特定的提示词模板
    tpl = load_prompt(_pick_template_by_db(db_type))
    tables_block = make_tables_block(db_type, tables)
    print(f"[_exec_cluster][{db_type}] 表白名单块长度: {len(tables_block)} 字符")

    # ========== 【调试】打印实际传给LLM的表白名单 ==========
    print(f"[_exec_cluster][{db_type}] ========== 传给LLM的表白名单 ==========")
    for idx, t in enumerate(tables, 1):
        table_name = t.get("table_name", "unknown")
        col_count = len(t.get("columns", []))
        print(f"[_exec_cluster][{db_type}]   {idx}. 表名: {table_name}, 字段数: {col_count}")
    print(f"[_exec_cluster][{db_type}] ==========================================")
    # ========== 【调试结束】 ==========

    # 根据是否有关系卡片选择不同的JOIN关系块和关系卡片信息
    has_relationship_cards = relationship_data and (
            relationship_data.get("cards") or relationship_data.get("join_suggestions")
    )

    if has_relationship_cards:
        # 使用关系卡片增强的JOIN关系
        rels_block = make_rels_block_with_relationship_cards(tables, relationship_data)
        relationship_cards_info = format_relationship_cards_for_prompt(relationship_data, tables)
        print(f"[_exec_cluster][{db_type}] ✅ 使用关系卡片增强的SQL生成")
        print(f"[_exec_cluster][{db_type}]   - 关系卡片数: {len(relationship_data.get('cards', {}))}")
        print(f"[_exec_cluster][{db_type}]   - JOIN建议数: {len(relationship_data.get('join_suggestions', []))}")
        print(f"[_exec_cluster][{db_type}]   - JOIN关系块长度: {len(rels_block)} 字符")
        print(f"[_exec_cluster][{db_type}]   - 关系卡片信息长度: {len(relationship_cards_info)} 字符")
        if relationship_cards_info:
            print(f"[_exec_cluster][{db_type}]   - 关系卡片信息预览:\n{relationship_cards_info[:500]}...")
    else:
        # 使用传统的JOIN关系推断
        rels_block = make_rels_block(tables)
        relationship_cards_info = ""  # 无关系卡片时传空字符串
        print(f"[_exec_cluster][{db_type}] ⚠️ 无关系卡片，使用传统JOIN推断")
        print(f"[_exec_cluster][{db_type}]   - JOIN关系块: {rels_block[:200] if rels_block else '(无)'}")

    prompt = render_prompt(
        tpl,
        user_question=user_question,
        db_name=db_name,
        tables_with_aliases_and_columns=tables_block,
        join_candidates=rels_block,
        relationship_cards_info=relationship_cards_info,
        entity_key=entity_key
    )
    print(f"[_exec_cluster][{db_type}] 提示词总长度: {len(prompt)} 字符")

    print(f"[_exec_cluster][{db_type}] 开始调用LLM生成SQL...")
    content, llm_usage = qian_wen_llm_with_usage(prompt, stream_type=False, model_config_dict=model_config_dict)
    print(f"[_exec_cluster][{db_type}] LLM返回内容长度: {len(content)} 字符")

    # 先解析 LLM 输出的"类型"
    parsed = _extract_sql_from_llm_text(content)
    print(f"[_exec_cluster][{db_type}] LLM返回类型: {parsed['kind']}")

    # 不是 SQL：作为 warning 返回该簇空结果
    if parsed["kind"] != "sql":
        cluster_tables = build_cluster_tables(tables)
        return {
            "db_type": db_type,
            # 保留原始 connect_info 用于回填查询
            "_connect_info_raw": connect_info,
            # 用于序列化的简化版本
            "connect_info_safe": {
                "type": db_type,
                "database": tables[0].get("database_name") if tables else None
            },
            # tables 中可能有复杂对象，只提取表名
            "tables": [{"table_name": t.get("table_name"), "alias": t.get("alias")} for t in tables],
            "cluster_tables": cluster_tables,
            "target_sql": "",
            "rows": [],
            "entity_ids": [],
            "note": parsed.get("text", ""),
            "warnings": ["模型未返回可执行 SQL（已跳过该簇）。"],
            "_llm_usage": llm_usage,  # LLM usage 信息
            "_sql_execution_ms": 0  # 未执行 SQL 时为 0
        }

    # 是 SQL：清洗并执行
    sql_text = _strip_code_fences(parsed["text"])
    print(f"[_exec_cluster][{db_type}] 生成的SQL:\n{sql_text}")

    # ========== 第二层防护：预校验SQL中的表是否都在白名单中 ==========
    cluster_tables = build_cluster_tables(tables)
    allowed_tables = {_norm_ident(t.get("table_name")) for t in cluster_tables}

    # 提取SQL中的表名（复用白名单校验的正则）
    _tbl_pat = re.compile(
        r"\b(?:FROM|JOIN)\s+([`\"\[]?[A-Za-z_][\w$-]*[`\"\]]?(?:\s*\.\s*[`\"\[]?[A-Za-z_][\w$-]*[`\"\]]?)*)",
        re.IGNORECASE
    )

    # 临时替换函数内的FROM避免误匹配
    temp_sql = sql_text
    temp_sql = re.sub(r'\b(EXTRACT|SUBSTRING|POSITION|TRIM)\s*\([^)]+\bFROM\b[^)]+\)',
                      'FUNC_PLACEHOLDER', temp_sql, flags=re.IGNORECASE)

    # 检查是否有非白名单表
    invalid_tables = []
    system_virtual_tables = {"dual", "information_schema", "pg_catalog"}

    # 提取 SQL 中的 CTE（公共表表达式）名称，避免将 CTE 名称误判为非白名单表
    # 匹配模式：WITH cte_name AS ( 或 , cte_name AS (
    # 注意：不能用 \b，因为 , 前面通常是 \n 或 ) 等非\w字符，
    #     \b 仅在单词字符-非单词字符边界生效，这会让 ,\n\ncte_name AS ( 这种
    #     紧随前一个 CTE 闭合括号后的 CTE 全部漏匹配。
    #     改用 (?<!\w) 排除前面是单词字符的情况，WITH 开头天然满足。
    _cte_pat = re.compile(r'(?<!\w)(?:WITH|,)\s*([A-Za-z_]\w*)\s+AS\s*\(', flags=re.IGNORECASE)
    cte_names = set()
    for m in _cte_pat.finditer(sql_text):
        cte_name = m.group(1).strip()
        if cte_name:
            cte_names.add(_norm_ident(cte_name))
    if cte_names:
        print(f"[_exec_cluster][{db_type}] 检测到 CTE 名称: {cte_names}")

    # 将 CTE 名称加入允许列表（CTE 是临时结果集，不是物理表）
    allowed_with_cte = allowed_tables.copy()
    allowed_with_cte.update(cte_names)

    for m in _tbl_pat.finditer(temp_sql):
        raw_tbl = m.group(1).strip()
        # 去掉 WITH (NOLOCK) 等提示
        raw_tbl = re.sub(r'\s+WITH\s*\(\s*NOLOCK\s*\)', '', raw_tbl, flags=re.IGNORECASE).strip()
        base = _norm_ident(raw_tbl.split()[-1])  # 取最后一段作为表名

        if base and base not in allowed_with_cte and base not in system_virtual_tables:
            invalid_tables.append(raw_tbl)

    # 如果发现非白名单表，返回友好提示，不执行SQL
    if invalid_tables:
        print(f"[_exec_cluster][{db_type}] ⚠️ SQL包含非白名单表: {invalid_tables}")
        print(f"[_exec_cluster][{db_type}] 允许的表（规范化后）: {sorted(allowed_tables)}")
        print(f"[_exec_cluster][{db_type}] 允许的表（原始名称）: {[t.get('table_name') for t in tables]}")
        print(f"[_exec_cluster][{db_type}] CTE名称: {cte_names}")
        return {
            "db_type": db_type,
            "_connect_info_raw": connect_info,
            "connect_info_safe": {
                "type": db_type,
                "database": tables[0].get("database_name") if tables else None
            },
            "tables": [{"table_name": t.get("table_name"), "alias": t.get("alias")} for t in tables],
            "cluster_tables": cluster_tables,
            "target_sql": sql_text,
            "rows": [],
            "entity_ids": [],
            "note": f"LLM生成的SQL使用了非白名单表 {', '.join(invalid_tables)}，当前白名单仅包含 {', '.join([t.get('table_name') for t in tables])}。可能需要其他数据源提供这些表的信息。",
            "warnings": [f"SQL包含非白名单表: {', '.join(invalid_tables)}，已跳过执行。"],
            "_llm_usage": llm_usage,  # LLM usage 信息
            "_sql_execution_ms": 0  # 未执行 SQL 时为 0
        }
    # ========== 预校验结束 ==========

    # 如果 SQL 中没有 FROM/JOIN，直接视为无效，避免触发安全校验错误
    if not re.search(r"\bFROM\b", sql_text, re.IGNORECASE):
        print(f"[_exec_cluster][{db_type}] ⚠️ SQL缺少FROM子句，跳过执行")
        return {
            "db_type": db_type,
            "_connect_info_raw": connect_info,
            "connect_info_safe": {
                "type": db_type,
                "database": tables[0].get("database_name") if tables else None
            },
            "tables": [{"table_name": t.get("table_name"), "alias": t.get("alias")} for t in tables],
            "cluster_tables": cluster_tables,
            "target_sql": "",
            "rows": [],
            "entity_ids": [],
            "note": "模型返回的 SQL 缺少 FROM/JOIN，已跳过该簇。",
            "warnings": ["模型未引用任何表（缺少 FROM/JOIN），已跳过该簇。"],
            "_llm_usage": llm_usage,  # LLM usage 信息
            "_sql_execution_ms": 0  # 未执行 SQL 时为 0
        }

    engine = get_db_engine(connect_info, db_type=db_type)

    # cluster_tables 已在预校验阶段定义，这里不需要重复定义

    # ========== LLM SQL 生成与重试机制 ==========
    max_retries = 2  # 最多重试次数
    last_error = None
    final_sql = sql_text
    success = False

    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"[_exec_cluster][{db_type}] 🔄 SQL白名单校验失败，尝试第 {attempt} 次重试...")

        print(f"[_exec_cluster][{db_type}] 开始执行SQL...")
        try:
            data, warnings, sql_exec_ms = run_sql_safe_new(
                engine=engine,
                sql=final_sql,
                cluster_tables=cluster_tables,
                db_type=db_type,
                max_rows=1000,
                allow_semicolon_terminator=True,
                target_schema=db_name if db_type in ("oracle", "dm") else None
            )
            print(f"[_exec_cluster][{db_type}] SQL执行成功，返回 {len(data) if isinstance(data, list) else data} 行数据，耗时 {sql_exec_ms}ms")
            if warnings:
                print(f"[_exec_cluster][{db_type}] 执行警告: {warnings}")

            # 调试：输出返回的数据内容
            if data:
                print(f"[_exec_cluster][{db_type}] 返回数据示例: {data[:3]}")  # 只输出前3行
            else:
                print(f"[_exec_cluster][{db_type}] ⚠️ 警告：SQL执行成功但返回空数据列表")

            # 过滤空记录和异常记录：只保留有有效数据的记录
            def has_valid_data_in_row(row: dict) -> bool:
                """
                检查记录是否包含有效且合理的数据

                过滤条件：
                1. 所有字段都是 None/空字符串 → 无效
                2. 存在明显异常的字段映射（如 quantity == price 且不是合理值） → 无效

                特殊情况：
                - 如果记录只有 entity_key 一个字段，且 entity_key 有值，则认为是有效的
                  （这在跨簇融合场景中是合理的，用于收集满足条件的 ID）
                - 对于统计查询（如 COUNT、SUM），即使结果为 0 也是有效的
                  （例如 {"mismatch_count": 0} 是有效结果，不应该被过滤）
                """
                # 特殊情况1：如果只有 entity_key 一个字段，且有值，则认为是有效的
                if len(row) == 1 and entity_key in row and row[entity_key] is not None:
                    return True

                # 特殊情况2：检查是否是统计查询结果（字段名包含 count/sum/avg/total/num 等）
                # 这些查询的结果即使为 0 也是有效的
                stat_keywords = ['count', 'sum', 'avg', 'total', 'num', 'amount', 'quantity', 'ratio', 'rate', 'percentage']
                is_stat_query = any(
                    any(keyword in k.lower() for keyword in stat_keywords)
                    for k in row.keys()
                )

                # 如果是统计查询，只要有非 None 的值就认为是有效的（即使值为 0）
                if is_stat_query:
                    for k, v in row.items():
                        if k == entity_key:
                            continue
                        if v is not None:  # 只要不是 None，就认为是有效的（包括 0）
                            return True
                    return False

                # 对于非统计查询，检查是否有非 entity_key 的非空非零字段
                has_non_empty = False
                for k, v in row.items():
                    if k == entity_key:
                        continue
                    if v is not None and v != 0 and v != 0.0 and v != "" and v is not False:
                        has_non_empty = True
                        break

                if not has_non_empty:
                    return False

                # 检测异常：如果同时存在 quantity 和 price 字段，且它们的值完全相同（且不是 0 或小的正常值）
                # 这通常意味着字段映射错误
                if 'quantity' in row and 'price' in row:
                    q = row['quantity']
                    p = row['price']
                    # 如果两个值都存在且相同
                    if q is not None and p is not None and q == p:
                        # 排除一些合理的情况（比如都是 0, 或者很小的正数如 0.01-10.0）
                        if q != 0 and p != 0:
                            # 如果值很大（绝对值 > 100）或者是负数，且相同，则认为是异常
                            if abs(q) > 100 or q < 0:
                                print(
                                    f"[agg] 检测到异常记录：product_id={row.get(entity_key)}, quantity={q}, price={p}（字段值相同且异常）")
                                return False

                return True

            original_count = len(data)
            # 过滤掉空记录
            filtered_data = [row for row in data if has_valid_data_in_row(row)]
            filtered_count = original_count - len(filtered_data)

            # 从过滤后的数据中收集 entity_ids（仅用于多簇融合，单簇场景不使用）
            eids = list(_collect_entity_ids(filtered_data, entity_key))

            if filtered_count > 0:
                print(f"[agg] 簇 {db_type} 原始查询结果 {original_count} 条，过滤掉 {filtered_count} 条异常/空记录")
                warnings = (warnings or [])
                warnings.append(f"过滤掉 {filtered_count} 条异常/空记录（字段值异常或都是 0/NULL）")

                # 输出生成的 SQL 用于调试
                print(f"[agg] 簇 {db_type} 生成的 SQL: {sql_text[:200]}...")  # 只输出前 200 字符

            # 注意：entity_ids 仅用于规则融合回退方案，LLM语义融合不依赖此字段
            if not eids:
                # 不添加警告，因为LLM语义融合不需要entity_ids
                print(f"[agg] 簇 {db_type} 未收集到 entity_key '{entity_key}'（LLM语义融合不受影响）")
            else:
                print(f"[agg] 簇 {db_type} 收集 entity_key '{entity_key}' 共 {len(eids)} 个（备用融合方案）")

            # 使用过滤后的数据
            data = filtered_data
            success = True
            break  # 成功，跳出重试循环

        except ValueError as ve:
            # SQL安全校验失败
            error_msg = str(ve)
            user_friendly_msg = "查询条件校验失败"

            # ========== 检查是否需要重试 ==========
            if "列不在白名单" in error_msg:
                # 提取无效列的信息
                invalid_col_match = re.search(r"列不在白名单:\s*([^\[]+)\.([^\[]+)", error_msg)
                if invalid_col_match:
                    invalid_table_alias = invalid_col_match.group(1)
                    invalid_col = invalid_col_match.group(2)

                    # 提取该表可用的列
                    available_cols_for_table = []
                    for t in tables:
                        table_name = t.get("table_name", "")
                        cols = [c.get("name") for c in (t.get("columns") or []) if c.get("name")]
                        # 简化表名用于匹配
                        simple_name = table_name.split(".")[-1] if "." in table_name else table_name
                        if simple_name.lower() == invalid_table_alias.lower() or table_name.lower() == invalid_table_alias.lower():
                            available_cols_for_table = cols
                            break

                    if attempt < max_retries:
                        print(f"[_exec_cluster][{db_type}] 🔄 检测到无效列 '{invalid_table_alias}.{invalid_col}'，准备重试...")
                        # 加载重试提示词
                        retry_tpl = load_prompt("retry_whitelist_error.txt")
                        retry_hint = render_prompt(
                            retry_tpl,
                            invalid_table_alias=invalid_table_alias,
                            invalid_col=invalid_col,
                            available_cols=', '.join(available_cols_for_table) if available_cols_for_table else '(无)'
                        )
                        print(f"[_exec_cluster][{db_type}] 🔄 进行第 {attempt + 1} 次重试...")
                        # 调用LLM重试
                        content, retry_usage = qian_wen_llm_with_usage(prompt + retry_hint, stream_type=False, model_config_dict=model_config_dict)
                        print(f"[_exec_cluster][{db_type}] 🔄 重试LLM返回内容长度: {len(content)} 字符")

                        # 解析重试结果
                        parsed_retry = _extract_sql_from_llm_text(content)
                        if parsed_retry["kind"] == "sql":
                            final_sql = _strip_code_fences(parsed_retry["text"])
                            print(f"[_exec_cluster][{db_type}] 🔄 重试生成的SQL:\n{final_sql}")
                            # 合并 usage
                            if retry_usage and llm_usage:
                                llm_usage["retry_tokens"] = retry_usage.get("tokens", 0)
                            continue  # 继续下一次循环，尝试执行重试后的SQL
                        else:
                            print(f"[_exec_cluster][{db_type}] ⚠️ 重试后仍未返回有效SQL")

            # 如果达到最大重试次数或不是白名单错误，返回错误
            if "非白名单表" in error_msg:
                table_name = error_msg.split(":")[-1].strip() if ":" in error_msg else "未知表"
                user_friendly_msg = f"SQL生成时使用了未召回的表 {table_name}，可能需要优化数据卡片描述以召回该表"
            elif "非白名单字段" in error_msg or "列不在白名单" in error_msg:
                user_friendly_msg = "SQL生成时使用了不存在的字段，可能是大模型推测错误"

            print(f"[_exec_cluster][{db_type}] ⚠️ SQL安全校验失败（已重试 {attempt} 次）: {error_msg}")
            # 返回包含SQL和错误信息的结构
            return {
                "db_type": db_type,
                "_connect_info_raw": connect_info,
                "connect_info_safe": {
                    "type": db_type,
                    "database": tables[0].get("database_name") if tables else None
                },
                "tables": [{"table_name": t.get("table_name"), "alias": t.get("alias")} for t in tables],
                "cluster_tables": build_cluster_tables(tables),
                "target_sql": " ".join(final_sql.split()),
                "rows": [],
                "entity_ids": [],
                "note": user_friendly_msg,
                "error": error_msg,
                "warnings": [f"查询执行失败，已重试 {attempt} 次"],
                "_llm_usage": llm_usage,
                "_sql_execution_ms": 0
            }

        except Exception as e:
            # SQL执行异常
            error_msg = str(e)
            user_friendly_msg = "查询执行失败"

            # 解析常见的PostgreSQL错误
            if "does not exist" in error_msg:
                if "relation" in error_msg:
                    user_friendly_msg = "表不存在，可能是schema配置问题"
                elif "column" in error_msg:
                    user_friendly_msg = "字段不存在，可能是大模型推测了错误的字段名"
            elif "permission denied" in error_msg or "Access denied" in error_msg:
                user_friendly_msg = "数据库权限不足，请检查数据源连接配置"
            elif "connection" in error_msg.lower():
                user_friendly_msg = "数据库连接失败，请检查数据源是否可用"
            elif "syntax error" in error_msg.lower():
                user_friendly_msg = "SQL语法错误，可能是大模型生成的SQL不正确"

            # ========== 检查是否需要重试（SQL执行错误也重试）==========
            # 可重试的错误类型：类型转换错误、列不存在、语法错误等
            retryable_patterns = [
                "invalid input syntax",      # PostgreSQL类型转换错误，如 integer: ""
                "cannot be cast",              # 类型转换错误
                "does not exist",              # 表/列不存在
                "ambiguous column",            # 列名歧义
                "column reference",            # 列引用错误
                "syntax error",                # 语法错误
                "division by zero",            # 除零错误
                "overflow",                    # 溢出错误
            ]

            should_retry = any(pattern in error_msg.lower() for pattern in retryable_patterns)

            if should_retry and attempt < max_retries:
                print(f"[_exec_cluster][{db_type}] 🔄 检测到可重试的SQL执行错误，准备重试...")
                print(f"[_exec_cluster][{db_type}] 🔄 错误详情: {error_msg[:200]}")

                # 加载重试提示词
                retry_tpl = load_prompt("retry_execution_error.txt")
                retry_hint = render_prompt(retry_tpl, error_msg=error_msg)
                print(f"[_exec_cluster][{db_type}] 🔄 进行第 {attempt + 1} 次重试...")
                # 调用LLM重试
                content, retry_usage = qian_wen_llm_with_usage(prompt + retry_hint, stream_type=False, model_config_dict=model_config_dict)
                print(f"[_exec_cluster][{db_type}] 🔄 重试LLM返回内容长度: {len(content)} 字符")

                # 解析重试结果
                parsed_retry = _extract_sql_from_llm_text(content)
                if parsed_retry["kind"] == "sql":
                    final_sql = _strip_code_fences(parsed_retry["text"])
                    print(f"[_exec_cluster][{db_type}] 🔄 重试生成的SQL:\n{final_sql}")
                    # 合并 usage
                    if retry_usage and llm_usage:
                        llm_usage["retry_tokens"] = retry_usage.get("tokens", 0)
                    continue  # 继续下一次循环，尝试执行重试后的SQL
                else:
                    print(f"[_exec_cluster][{db_type}] ⚠️ 重试后仍未返回有效SQL")

            # 不可重试或达到最大重试次数，返回错误
            print(f"[_exec_cluster][{db_type}] ⚠️ SQL执行异常（已重试 {attempt} 次）: {error_msg}")
            return {
                "db_type": db_type,
                "_connect_info_raw": connect_info,
                "connect_info_safe": {
                    "type": db_type,
                    "database": tables[0].get("database_name") if tables else None
                },
                "tables": [{"table_name": t.get("table_name"), "alias": t.get("alias")} for t in tables],
                "cluster_tables": build_cluster_tables(tables),
                "target_sql": " ".join(final_sql.split()),
                "rows": [],
                "entity_ids": [],
                "note": user_friendly_msg,
                "error": error_msg,
                "warnings": [f"查询执行失败，已重试 {attempt} 次"],
                "_llm_usage": llm_usage,
                "_sql_execution_ms": 0
            }

    # 注意：这里给 note 设为空字符串，避免未定义
    # 只返回可序列化的数据，避免循环引用
    out = {
        "db_type": db_type,
        # 保留原始 connect_info 用于回填查询
        "_connect_info_raw": connect_info,
        # 用于序列化的简化版本
        "connect_info_safe": {
            "type": db_type,
            "database": tables[0].get("database_name") if tables else None
        },
        # tables 中可能有复杂对象，只提取表名
        "tables": [{"table_name": t.get("table_name"), "alias": t.get("alias")} for t in tables],
        "cluster_tables": cluster_tables,
        "target_sql": " ".join(final_sql.split()),
        "rows": data,
        "entity_ids": eids,
        "note": "",
        "warnings": warnings or [],
        "_llm_usage": llm_usage,  # LLM usage 信息
        "_sql_execution_ms": sql_exec_ms  # SQL 执行时间
    }

    # 释放数据库连接池
    if engine:
        try:
            engine.dispose()
        except Exception:
            pass

    return out


def run_sql_safe_new(
        engine,
        sql: str,
        cluster_tables: list,
        db_type: str | None = None,
        *,
        max_rows: int = 1000,
        allow_semicolon_terminator: bool = True,
        target_schema: str | None = None,
):
    """
    多表白名单 + 安全校验 + 执行。
    参数:
      - engine: SQLAlchemy engine
      - sql:    待执行的 SQL（期望是一条 SELECT）
      - cluster_tables: 同簇内允许参与查询的表清单，形如：
            [
              {"table_name": "user_5_1", "columns": [{"name": "account"}, {"name": "status"}]},
              {"table_name": "user_5_2", "columns": [{"name": "user_id"}, {"name": "name"}, {"name": "age"}]},
              ...
            ]
        注意: table_name 建议是“最终物理名”（不带库/模式前缀），columns 只需 name 字段即可。
      - db_type: 可选，仅用于大小写/引用符处理的微调（"mysql"/"postgresql"/"mssql"/"oracle"/"sqlite"...）
      - max_rows: 最多返回行数（防止无条件全表扫）
      - allow_semicolon_terminator: 允许以单个分号作结尾
      - target_schema: Oracle 目标 schema（用于设置 session current_schema）

    返回:
      (data, warnings)
        - data: list[dict]（SELECT）或 {"rowcount": int}（非返回行）
        - warnings: list[str]
    失败:
      - 抛出 ValueError（非法/危险/超出白名单）
    """

    warnings: list[str] = []

    # ---------- 0) 预处理：去两端空白 ----------
    raw_sql = _strip_code_fences(sql or "")
    sql_stripped = raw_sql.strip()

    # ---------- 1) 基础安全防护 ----------
    # 仅允许单条语句，默认允许末尾单个分号；禁用注释与危险关键字
    # 1.1 注释（-- 与 /* */）直接拒绝
    if re.search(r"(--|/\*)", sql_stripped, flags=re.IGNORECASE):
        raise ValueError("SQL 中包含注释标记（-- 或 /* */），为安全起见不允许执行。")

    # 1.2 末尾分号检查
    # 1.2 末尾分号检查（仅允许单条语句；可允许一个结尾分号）
    if ";" in sql_stripped:
        if allow_semicolon_terminator:
            # 去掉末尾分号后，仍然不允许出现任何分号（避免多语句）
            sql_wo_trailing = re.sub(r";\s*$", "", sql_stripped)
            if ";" in sql_wo_trailing:
                raise ValueError("仅允许单条 SQL 语句，检测到多个分号或多条语句。")
            sql_stripped = sql_wo_trailing
        else:
            raise ValueError("SQL 不允许包含分号。")

    # 1.3 只允许 SELECT
    head = sql_stripped.lstrip()[:10].upper()
    if not (head.startswith("SELECT") or head.startswith("WITH")):
        raise ValueError("仅允许执行 SELECT 查询（支持以 WITH 开头的 CTE）。")

    # 1.4 危险关键字黑名单（基本 DDL/DML/管理语句）
    blacklist = [
        r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bMERGE\b",
        r"\bREPLACE\b", r"\bUPSERT\b",
        r"\bDROP\b", r"\bALTER\b", r"\bTRUNCATE\b", r"\bCREATE\b",
        r"\bGRANT\b", r"\bREVOKE\b",
        r"\bEXEC\b", r"\bEXECUTE\b", r"\bCALL\b",
        r"\bUSE\b", r"\bSET\s+\w+",
        r"\bATTACH\b", r"\bDETACH\b",
    ]
    if re.search("|".join(blacklist), sql_stripped, flags=re.IGNORECASE):
        raise ValueError("检测到潜在危险关键字，拒绝执行。")

    # ---------- 1.x 全局 FROM/JOIN 物理表白名单扫描（先拒绝注释后再做扫描） ----------
    _tbl_pat = re.compile(
        r"\b(?:FROM|JOIN)\s+([`\"\[]?[A-Za-z_][\w$-]*[`\"\]]?(?:\s*\.\s*[`\"\[]?[A-Za-z_][\w$-]*[`\"\]]?)*)",
        re.IGNORECASE
    )

    # 提取 SQL 中的 CTE（公共表表达式）名称，避免将 CTE 名称误判为非白名单表
    # 匹配模式：WITH cte_name AS ( 或 , cte_name AS (
    # 注意：不能用 \b，因为 , 前面通常是 \n 或 ) 等非\w字符，
    #     \b 仅在单词字符-非单词字符边界生效，会让紧随前一个 CTE 闭合括号后的
    #     CTE 全部漏匹配。改用 (?<!\w) 排除前面是单词字符的情况。
    _cte_pat = re.compile(r'(?<!\w)(?:WITH|,)\s*([A-Za-z_]\w*)\s+AS\s*\(', flags=re.IGNORECASE)
    cte_names = set()
    for m in _cte_pat.finditer(sql_stripped):
        cte_name = m.group(1).strip()
        if cte_name:
            cte_names.add(_norm_ident(cte_name))
    if cte_names:
        print(f"[cte-check] 检测到 CTE 名称: {cte_names}")

    # 注意：这里先不依赖列白名单；只校验"物理表是否在 cluster_tables 允许的集合"即可
    allowed_physical = {_norm_ident(t.get("table_name")) for t in (cluster_tables or [])}
    # 将 CTE 名称加入允许列表（CTE 是临时结果集，不是物理表）
    allowed_physical.update(cte_names)

    # 系统虚拟表白名单（这些表是安全的，不需要在 cluster_tables 中）
    system_virtual_tables = {
        "dual",  # Oracle 虚拟表
        "information_schema",  # 通用信息模式
        "pg_catalog",  # PostgreSQL 系统目录
    }

    # 为了避免误匹配函数内的 FROM（如 EXTRACT(YEAR FROM ...), SUBSTRING(... FROM ...)），
    # 先将这些函数调用临时替换
    temp_sql_for_table_check = sql_stripped
    temp_sql_for_table_check = re.sub(r'\b(EXTRACT|SUBSTRING|POSITION|TRIM)\s*\([^)]+\bFROM\b[^)]+\)',
                                      'FUNC_WITH_FROM_PLACEHOLDER', temp_sql_for_table_check, flags=re.IGNORECASE)

    for m in _tbl_pat.finditer(temp_sql_for_table_check):
        raw_tbl = _strip_nolock(m.group(1)).strip()
        base = _norm_ident(raw_tbl.split()[-1])  # schema.table 取最后一段
        if base and base not in allowed_physical and base not in system_virtual_tables:
            # 调试：输出白名单中的表名，帮助定位问题
            print(f"[whitelist-check] ⚠️ 检测到非白名单表: {raw_tbl} (规范化后: {base})")
            print(f"[whitelist-check] 白名单中的表: {sorted(allowed_physical)}")
            print(f"[whitelist-check] CTE名称: {cte_names}")
            raise ValueError(f"检测到非白名单表: {raw_tbl}")

    # ---------- 2) 准备白名单（表 & 列） ----------
    allowed_tables: dict[str, set[str]] = {}  # 物理表名(小写) -> 该表允许列(小写)集合
    # 对于 Trino 跨 catalog 查询，需要同时支持完整路径和规范化表名
    table_name_mapping: dict[str, str] = {}  # 规范化表名 -> 原始表名（用于调试）

    for t in cluster_tables or []:
        raw_table_name = t.get("table_name", "")
        tname = _norm_ident(raw_table_name)
        cols = set()
        for c in (t.get("columns") or []):
            cname = _norm_ident(c.get("name"))
            if cname:
                cols.add(cname)
        if tname:
            # 如果同一个规范化表名已经存在，合并列信息
            if tname in allowed_tables:
                allowed_tables[tname].update(cols)
            else:
                allowed_tables[tname] = cols
            table_name_mapping[tname] = raw_table_name
            # 调试信息：打印白名单中的表名（原始 vs 规范化后）
            print(f"[whitelist-build] 表名: 原始={raw_table_name}, 规范化={tname}")

    # 将 CTE 名称加入 allowed_tables（用于后续列白名单校验）
    # CTE 的列来自其内部 SELECT，我们可以将其列白名单设为空集合（不校验列）
    for cte_name in cte_names:
        if cte_name not in allowed_tables:
            allowed_tables[cte_name] = set()  # 空集合表示不检查列
            print(f"[whitelist-build] CTE加入白名单: {cte_name}")

    # 添加系统虚拟表到 allowed_tables（不需要列白名单）
    for sys_table in system_virtual_tables:
        if sys_table not in allowed_tables:
            allowed_tables[sys_table] = set()  # 空列集合表示不检查列

    if not allowed_tables:
        raise ValueError("未提供任何允许的表/列白名单。")

    # ---------- 3) 解析表与别名（FROM / JOIN） ----------
    # 注意：这是一个“健壮的正则近似解析”，能满足 90% 常见书写（含 AS 与不含 AS）。
    # 对含有子查询的复杂 FROM (SELECT ...) x 这种别名，我们无法进一步校验子查询内部列，只能校验外层使用的 alias 字段。
    #
    # 匹配 FROM 与 JOIN 后面的 第一个标识符(可能带库/模式) + 可选 AS + 可选别名
    table_alias_map: dict[str, str] = {}  # alias(小写) -> 物理表名(小写)
    physical_to_aliases: dict[str, set[str]] = {}  # 物理表名 -> 该表出现过的别名集合

    # 为了避免误匹配函数内的 FROM（如 EXTRACT(YEAR FROM ...), SUBSTRING(... FROM ...)），
    # 先将常见的带 FROM 关键字的函数调用临时替换
    temp_sql_for_from = sql_stripped
    # 替换 EXTRACT(...FROM...) 和 SUBSTRING(...FROM...) 等函数
    temp_sql_for_from = re.sub(r'\b(EXTRACT|SUBSTRING|POSITION|TRIM)\s*\([^)]+\bFROM\b[^)]+\)',
                               'FUNC_WITH_FROM_PLACEHOLDER', temp_sql_for_from, flags=re.IGNORECASE)

    # 捕获 FROM 与 JOIN 片段
    from_join_pattern = re.compile(
        r"(?:FROM|JOIN)\s+([`\"\[\]\w\.\-/]+)(?:\s+(?:AS\s+)?([`\"\[\]\w\-]+))?",
        flags=re.IGNORECASE
    )
    for m in from_join_pattern.finditer(temp_sql_for_from):
        raw_tbl = m.group(1) or ""
        raw_alias = m.group(2) or ""
        tbl = _norm_ident(raw_tbl)  # 规范化表名（去掉引号、路径，只保留最后一段）
        alias = _norm_ident(raw_alias) if raw_alias else tbl  # 无别名时用表名自身作为 alias

        # 校验表是否在白名单
        # 对于 Trino 跨 catalog 查询，SQL 中的表名可能是完整路径（如 "mysql8"."webtest1"."device_m8"），
        # 但规范化后应该和 cluster_tables 中的表名匹配（都是 device_m8）
        if tbl not in allowed_tables:
            # 检查是否是 CTE 别名（SQL 可能会用不同的别名引用 CTE，如 JOIN latest_ab AS ab）
            # 此时 tbl 是实际使用的别名，raw_tbl 是规范化前的别名
            # 如果 tbl 在 cte_names 中，说明这是对 CTE 的引用
            if tbl in cte_names:
                # CTE 别名映射到 CTE 自身（CTE 别名的"物理表"就是 CTE 名称）
                table_alias_map[alias] = tbl
                physical_to_aliases.setdefault(tbl, set()).add(alias)
                continue
            warnings.append(
                f"检测到 FROM/JOIN 标识符 {raw_tbl} (规范化后: {tbl}) 非物理白名单表，可能是 CTE 或子查询别名，已跳过白名单表校验。")
            continue

        table_alias_map[alias] = tbl
        physical_to_aliases.setdefault(tbl, set()).add(alias)

    if not table_alias_map:
        raise ValueError("未在 SQL 中解析到任何 FROM/JOIN 的表名；请确认 SQL 语法。")

    # ---------- 4) 解析列引用（SELECT 列、WHERE/ON/ORDER/GROUP/HAVING 中的 alias.col） ----------
    # 统一抓取形如  a.b  的列，a 是别名或表名，b 是列名；兼容引用符
    # 注意：会抓到函数参数里的 a.b；这是我们期望的。
    #
    # 为了避免误将 FROM/JOIN 中的 schema.table（如 public.courses）识别为列引用，
    # 先将 FROM/JOIN 子句替换为占位符
    temp_sql_for_col = temp_sql_for_from
    temp_sql_for_col = re.sub(
        r"(?:FROM|JOIN)\s+([`\"\[\]\w\.\-/]+)(?:\s+(?:AS\s+)?([`\"\[\]\w\-]+))?",
        r"FROM_JOIN_PLACEHOLDER",
        temp_sql_for_col,
        flags=re.IGNORECASE
    )

    col_ref_pattern = re.compile(
        r"(?P<alias>[`\"\[\]]?[A-Za-z_]\w*[`\"\[\]]?)\s*\.\s*(?P<col>[`\"\[\]]?[A-Za-z_]\w*[`\"\[\]]?)"
    )
    for am in col_ref_pattern.finditer(temp_sql_for_col):
        raw_a = am.group("alias")
        raw_c = am.group("col")
        a = _norm_ident(raw_a)
        c = _norm_ident(raw_c)

        # 校验别名
        if a not in table_alias_map:
            # 有可能是子查询的别名引用其内部列；我们无法深入校验，只能提示警告
            warnings.append(f"检测到无法识别来源的别名列引用: {raw_a}.{raw_c}（可能来自子查询，已跳过白名单校验）")
            continue

        # 校验列
        physical = table_alias_map[a]
        # 如果是CTE（允许列为空集合），跳过列白名单校验
        # CTE的列来自其内部SELECT定义，无法预知其结构，所以不校验CTE的列
        if physical in cte_names:
            continue
        allowed_cols = allowed_tables.get(physical, set())
        if c not in allowed_cols:
            # 提供更详细的错误信息，包括可用的列
            available_cols = sorted(allowed_cols) if allowed_cols else []
            cols_str = ", ".join(available_cols[:10])  # 只显示前10个列
            if len(available_cols) > 10:
                cols_str += f", ... (共 {len(available_cols)} 列)"
            raise ValueError(
                f"列不在白名单: {raw_a}.{raw_c}（表: {physical}，规范化列名: {c}）。"
                f"可用列: {cols_str if cols_str else '(无)'}"
            )

    # 4.1 禁止出现通配列 * 或 别名.* （严格白名单）
    # 注意：需要排除聚合函数中的 COUNT(*) 和乘法运算符 * 等合法用法
    # 
    # 策略：提取 SELECT 和 FROM 之间的列列表部分，然后检查是否有裸露的 * 或 别名.*
    # 这样可以避免误判 WHERE 子句中的运算符

    # 先将所有括号内包含 * 的内容临时替换，避免误判 COUNT(*) 等函数
    temp_sql = re.sub(r'\([^)]*\*[^)]*\)', '(PLACEHOLDER)', sql_stripped)
    # 再将乘法运算符替换（更宽泛的模式：任何 非空格字符 * 数字）
    temp_sql = re.sub(r'(\S+)\s*\*\s*(\d+(?:\.\d+)?)', r'\1 MULT \2', temp_sql)
    temp_sql = re.sub(r'(\d+(?:\.\d+)?)\s*\*\s*(\S+)', r'\1 MULT \2', temp_sql)

    # 只匹配 SELECT 后直接跟 * 或列表中的 , * 或 别名.* 的情况
    # 注意：使用更精确的模式，确保匹配的是列通配符而不是运算符
    star_pattern = re.compile(
        r"(?:\bSELECT\b\s+\*)|"  # SELECT *
        r"(?:\bSELECT\b[^,]*,\s*\*\s*(?:,|FROM))|"  # SELECT ..., *, ... 或 SELECT ..., * FROM
        r"(?:[`\"\[\]]?[A-Za-z_]\w*[`\"\[\]]?)\s*\.\s*\*",  # 别名.*
        flags=re.IGNORECASE
    )
    if star_pattern.search(temp_sql):
        raise ValueError("不允许使用 * 或 别名.*，请明确列名（已启用严格白名单模式）。")

    # ---------- 5) 适度的 LIMIT 防护 ----------
    # 对于未显式 LIMIT 的查询，添加一个行数上限提示（不直接改写 SQL，只是提醒）
    if (re.search(r"\bLIMIT\s+\d+\b", sql_stripped, re.IGNORECASE) is None
            and re.search(r"\bFETCH\s+FIRST\s+\d+\s+ROWS\s+ONLY\b", sql_stripped, re.IGNORECASE) is None
            and re.search(r"\bSELECT\s+TOP\s+\d+\b", sql_stripped, re.IGNORECASE) is None):
        warnings.append(f"未检测到行数限制，若结果过大将只返回前 {max_rows} 行。")

    # ---------- 6) 执行 ----------
    exec_start = time_module.time()
    with engine.connect() as conn:
        # Oracle 特殊处理：如果有 target_schema，需要先切换 session schema
        # 达梦 DM 与 Oracle 兼容，沿用同样逻辑（达梦支持 SET SCHEMA "name"）
        if (db_type == "oracle" or db_type == "dm") and target_schema:
            try:
                # 达梦 SQL 写法：SET SCHEMA "name"；Oracle：ALTER SESSION SET current_schema = "name"
                if db_type == "dm":
                    conn.execute(text(f'SET SCHEMA "{target_schema}"'))
                    print(f"[run_sql_safe_new] 达梦 DM 已切换 session schema: {target_schema}")
                else:
                    conn.execute(text(f'ALTER SESSION SET current_schema = "{target_schema}"'))
                    print(f"[run_sql_safe_new] Oracle 已切换 session schema: {target_schema}")
            except Exception as e:
                print(f"[run_sql_safe_new] ⚠️ {db_type} 切换 schema 失败: {e}")

        result = conn.execute(text(sql_stripped))
        sql_execution_ms = int((time_module.time() - exec_start) * 1000)
        if result.returns_rows:
            rows = result.fetchall()
            keys = result.keys()
            # 将每行数据转换为字典，并立即序列化特殊类型
            data = []
            for row in rows[:max_rows]:
                row_dict = dict(zip(keys, row))
                # 对每行数据应用序列化处理，确保特殊类型（time, UUID, date等）正确转换
                serialized_row = _make_json_serializable(row_dict)
                data.append(serialized_row)

            if len(rows) > max_rows:
                warnings.append(f"结果行数 {len(rows)} 超过上限 {max_rows}，已截断返回。")
            return data, warnings, sql_execution_ms
        else:
            return {"rowcount": result.rowcount}, warnings, sql_execution_ms


def _split_ids_for_db(ids: list, db_type: str, chunk_for_oracle: int = 1000, chunk_default: int = 1000):
    ids = list(ids or [])
    if not ids:
        return []
    n = chunk_for_oracle if (db_type or "").lower() == "oracle" else chunk_default
    return [ids[i:i + n] for i in range(0, len(ids), n)]


def _sql_literal(v):
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
        return str(v)
    # 简单转义单引号
    return "'" + str(v).replace("'", "''") + "'"


def _build_projection_sql(db_type: str, tables: list, entity_key: str, need_cols: list,
                          id_batch: list[str | int]) -> str:
    """
    构造投影查询 SQL：只返回 entity_key + need_cols，WHERE entity_key IN (id_batch)
    优先选择包含 entity_key 的表作为主表；若所有表都不含该键，则抛出异常。
    """
    main_table = None
    main_table_cols = []

    for t in tables:
        cols = [c.get("name") for c in (t.get("columns") or []) if c.get("name")]
        if any(c.lower() == entity_key.lower() for c in cols):
            main_table = t["table_name"]
            main_table_cols = cols
            break

    if not main_table:
        raise ValueError(f"簇内所有表均不包含实体键 {entity_key}，无法构造投影查询")

    # 过滤出主表实际存在的列（避免查询不存在的列）
    main_table_cols_lower = {c.lower() for c in main_table_cols}
    valid_cols = [entity_key]
    for c in need_cols:
        if c != entity_key and c.lower() in main_table_cols_lower:
            valid_cols.append(c)

    col_list = ", ".join([f"{main_table}.{c}" for c in valid_cols])
    in_list = ", ".join([_sql_literal(x) for x in id_batch])
    return f"SELECT {col_list} FROM {main_table} WHERE {main_table}.{entity_key} IN ({in_list})"


# ---- 资源类：聚合检索----

def _log_query(
        user_id: str,
        question: str,
        sql: str,
        source_datasource_ids: list,
        source_datasource_names: list,
        datasource_ids: list,
        datasource_names: list,
        table_names: list,
        metrics: dict,
        tokens: dict,
        quality: dict,
        result_count: int,
        merge_strategy: str,
        success: bool = True,
        error_message: str = None,
        full_response_result: dict = None,
        cluster_sqls: list = None,
        # === 新增参数 ===
        processed_question: str = None,
        term_rewrite_info: dict = None
):
    """
    查询日志记录辅助函数

    将查询性能、Token消耗、召回质量等指标记录到数据库。
    """
    try:
        # 计算总耗时
        metrics['total_duration_ms'] = metrics.get('vector_search_ms', 0) + \
                                       metrics.get('rerank_ms', 0) + \
                                       metrics.get('llm_gen_sql_ms', 0) + \
                                       metrics.get('llm_fusion_ms', 0) + \
                                       metrics.get('sql_execution_ms', 0)

        if success:
            QueryLogger.log_success(
                user_id=user_id,
                question=question,
                sql=sql,
                source_datasource_ids=source_datasource_ids,
                source_datasource_names=source_datasource_names,
                datasource_ids=datasource_ids,
                datasource_names=datasource_names,
                table_names=table_names,
                performance=metrics,
                tokens=tokens,
                result_count=result_count,
                cards_recalled=quality.get('cards_recalled', 0),
                cards_reranked=quality.get('cards_reranked', 0),
                cards_selected=quality.get('cards_selected', 0),
                top1_rerank_score=quality.get('top1_rerank_score'),
                avg_rerank_score=quality.get('avg_rerank_score'),
                fusion_strategy=merge_strategy,
                full_response_result=full_response_result,
                cluster_sqls=cluster_sqls,
                # === 新增参数 ===
                processed_question=processed_question,
                term_rewrite_info=term_rewrite_info
            )
        else:
            QueryLogger.log_error(
                user_id=user_id,
                question=question,
                error_message=error_message,
                total_duration_ms=metrics.get('total_duration_ms', 0),
                source_datasource_ids=source_datasource_ids,
                source_datasource_names=source_datasource_names,
                datasource_ids=datasource_ids,
                datasource_names=datasource_names
            )

        db.session.commit()
        print(f"[查询日志] 记录成功: user_id={user_id}, status={'success' if success else 'error'}")
    except Exception as e:
        import traceback
        print(f"[查询日志] 记录失败: {str(e)}")
        print(f"[查询日志] 详细错误: {traceback.format_exc()}")
        try:
            db.session.rollback()
        except Exception:
            pass


class QueryByDataCardsAgg(Resource):
    @flask_login.login_required
    def post(self):
        body = request.get_json() or {}
        user_question = (body.get("query") or "").strip()
        if not user_question:
            return format_response(None, 400, "请提供 query")

        # 记录开始时间，用于性能统计
        start_time = time_module.time()
        user_id = str(flask_login.current_user.id)

        # 初始化性能指标收集器
        metrics = {
            "vector_search_ms": 0,
            "rerank_ms": 0,
            "llm_gen_sql_ms": 0,
            "llm_fusion_ms": 0,
            "sql_execution_ms": 0,
            "total_duration_ms": 0
        }

        # 初始化 Token 使用量收集器
        tokens = {
            "embedding_tokens": 0,
            "rerank_tokens": 0,
            "llm_prompt_tokens": 0,
            "llm_completion_tokens": 0,
            "total_tokens": 0
        }

        # 初始化召回质量指标
        quality = {
            "cards_recalled": 0,
            "cards_reranked": 0,
            "cards_selected": 0,
            "top1_rerank_score": None,
            "avg_rerank_score": None
        }

        # 收集涉及的数据源信息
        source_datasource_ids = []  # 查询来源数据源ID（用户发起查询时选中的数据源）
        source_datasource_names = []  # 查询来源数据源名称
        datasource_ids = []  # 涉及的数据源ID（查询过程中涉及到的所有数据源）
        datasource_names = []  # 涉及的数据源名称
        table_names = []

        # 新增：接收数据源ID参数（可选）
        # 支持单个数据源ID或数据源ID列表
        datasource_id = body.get("datasource_id")
        datasource_ids_param = body.get("datasource_ids")  # 支持传入数据源ID列表

        # 统一处理数据源过滤参数：优先使用列表，其次使用单个ID
        datasource_filter = None  # 用于传递给向量检索的过滤参数
        if datasource_ids_param and isinstance(datasource_ids_param, list):
            # 传入的是数据源ID列表
            source_datasource_ids = datasource_ids_param
            datasource_filter = datasource_ids_param  # 传递列表给向量检索
            print(f"[聚合检索] 指定数据源过滤（列表模式）: datasource_ids={source_datasource_ids}")
        elif datasource_id:
            # 传入的是单个数据源ID
            source_datasource_ids = [datasource_id] if datasource_id else []
            datasource_filter = datasource_id  # 传递单个ID给向量检索
            print(f"[聚合检索] 指定数据源过滤: datasource_id={datasource_id}")

        # 获取可选参数：是否启用重排序（默认启用）
        enable_rerank = body.get("enable_rerank", True)

        # 1) 推断融合策略（AND/OR），用户不输入参数，自动识别
        t0 = time_module.time()
        merge_strategy = _infer_strategy(user_question)
        metrics["llm_gen_sql_ms"] += int((time_module.time() - t0) * 1000)

        # === 术语识别与展开（新增） ===
        # 先保存原始问题，后续用于日志记录
        original_question = user_question
        # 获取可选参数：是否启用术语转写（默认启用）
        enable_term_rewrite = body.get("enable_term_rewrite", True)
        matched_terms = []
        rewritten_question = user_question  # 初始化默认值
        term_rewrite_performed = False  # 标记是否实际进行了术语展开
        print(f"[术语展开] 初始化: enable_term_rewrite={enable_term_rewrite}, term_rewrite_performed={term_rewrite_performed}")
        if enable_term_rewrite:
            try:
                library_ids = body.get("library_ids", [])  # 指定术语库ID列表
                if library_ids and isinstance(library_ids, list):
                    # 优先使用指定的术语库ID列表
                    rewritten_question, matched_terms, did_rewrite = process_question_by_libraries(
                        user_question, library_ids
                    )
                    print(f"[术语展开] 使用指定的术语库: library_ids={library_ids}")
                elif datasource_id:
                    # 根据 datasource_id 自动获取已添加并启用的术语库
                    enabled_library_ids = get_enabled_library_ids_by_datasource(datasource_id)
                    if enabled_library_ids:
                        rewritten_question, matched_terms, did_rewrite = process_question_by_libraries(
                            user_question, enabled_library_ids
                        )
                        print(f"[术语展开] 数据源={datasource_id}, 启用库={enabled_library_ids}")
                    else:
                        did_rewrite = False
                        rewritten_question = user_question
                        print(f"[术语展开] 数据源={datasource_id} 无关联的启用的术语库，跳过术语展开")
                        print(f"[术语展开] 跳过详情: enabled_library_ids={enabled_library_ids}, term_rewrite_performed={term_rewrite_performed}")
                elif datasource_ids_param and isinstance(datasource_ids_param, list):
                    # 处理多个数据源：聚合所有涉及的术语库
                    all_enabled_library_ids = []
                    for ds_id in datasource_ids_param:
                        library_ids_for_ds = get_enabled_library_ids_by_datasource(ds_id)
                        if library_ids_for_ds:
                            all_enabled_library_ids.extend(library_ids_for_ds)
                            print(f"[术语展开] 数据源={ds_id}, 找到启用库={library_ids_for_ds}")
                    all_enabled_library_ids = list(set(all_enabled_library_ids))  # 去重
                    if all_enabled_library_ids:
                        rewritten_question, matched_terms, did_rewrite = process_question_by_libraries(
                            user_question, all_enabled_library_ids
                        )
                        print(f"[术语展开] 多数据源聚合: datasource_ids={datasource_ids_param}, 启用库={all_enabled_library_ids}")
                    else:
                        did_rewrite = False
                        rewritten_question = user_question
                        print(f"[术语展开] 数据源列表无关联的启用的术语库，跳过术语展开")
                        print(f"[术语展开] 跳过详情: all_enabled_library_ids={all_enabled_library_ids}, term_rewrite_performed={term_rewrite_performed}")
                else:
                    # 没有指定数据源，也没有指定术语库，查询所有启用的术语
                    rewritten_question, matched_terms, did_rewrite = process_question(user_question)
                    print(f"[术语展开] 未指定数据源，使用所有启用的术语库")

                if did_rewrite:
                    print(f"[术语展开] 识别到 {len(matched_terms)} 个术语")
                    print(f"[术语展开] 原文：{user_question}")
                    print(f"[术语展开] 转写：{rewritten_question}")
                    user_question = rewritten_question
                    term_rewrite_performed = True
            except Exception as e:
                print(f"[术语展开] 术语识别出错: {e}")
                import traceback
                traceback.print_exc()

        # 2) 向量检索 + 数据卡（支持重排序 + 数据源过滤）
        t1 = time_module.time()
        rs_json = get_data_card_json(
            user_question,
            enable_rerank=enable_rerank,
            class_name=flask_login.current_user.weaviate_class_name,
            datasource_id=datasource_filter  # 使用统一的过滤参数（支持单个ID或列表）
        )
        metrics["vector_search_ms"] += int((time_module.time() - t1) * 1000)
        doc_ids = rs_json.get("doc_ids") or []
        card_list = rs_json.get("data_card_results") or []
        
        # 收集向量检索的 usage 信息（embedding + rerank tokens, rerank ms, rerank scores）
        vector_usage = rs_json.get("usage", {})
        tokens["embedding_tokens"] = vector_usage.get("embedding_tokens", 0)
        tokens["rerank_tokens"] = vector_usage.get("rerank_tokens", 0)
        metrics["rerank_ms"] = vector_usage.get("rerank_ms", 0)
        quality["cards_reranked"] = vector_usage.get("reranked_count", 0)
        quality["top1_rerank_score"] = vector_usage.get("top1_rerank_score")
        quality["avg_rerank_score"] = vector_usage.get("avg_rerank_score")

        # 收集召回统计
        quality["cards_recalled"] = len(doc_ids)

        # 按用户隔离查 schema 行，并将 connect_name → connect_info
        table_objs = []
        data_cards_info = []  # 收集数据卡片信息，用于前端"查看详情"

        print(f"[DEBUG] 开始构建表对象，共 {len(doc_ids)} 个数据卡片...")
        for idx, (doc_id, card) in enumerate(zip(doc_ids, card_list)):
            try:
                schema_row = UserDatasourceSchema.query.filter_by(
                    id=doc_id, user_id=flask_login.current_user.id
                ).first()
                if not schema_row:
                    print(f"[DEBUG] ⚠️ 卡片 {idx + 1} (doc_id={doc_id}) 未找到schema_row，跳过")
                    continue

                connect_name = ((card or {}).get("DocInfo") or {}).get("connect_name")
                connect_info = map_connect_name_to_connect_info(
                    connect_name,
                    DatasourceInfo,
                    user_id=str(flask_login.current_user.id)  # 增加用户隔离
                )
                if not connect_info:
                    # 没找到连接配置，跳过或记录 warning
                    print(f"[DEBUG] ⚠️ 卡片 {idx + 1} (表名={schema_row.table_name}) 未找到连接信息，跳过")
                    continue

                # 提前查询 DatasourceInfo 获取 schema_name（用于正确生成 schema.table 前缀）
                ds_schema_name = None
                ds_info = DatasourceInfo.query.filter_by(
                    connect_name=connect_name,
                    user_id=str(flask_login.current_user.id)
                ).first()
                if ds_info and ds_info.schema_name:
                    ds_schema_name = ds_info.schema_name
                    print(f"[DEBUG] 卡片 {idx + 1} 使用 schema_name: {ds_schema_name} (from DatasourceInfo)")

                table_obj = card_to_table_obj(schema_row, card, connect_info, ds_schema_name=ds_schema_name)
                table_objs.append(table_obj)
                print(f"[DEBUG] ✅ 卡片 {idx + 1}: {table_obj.get('table_name')} (connect_name={connect_name})")
                
                # 收集表名（去重）
                table_name = table_obj.get("table_name")
                if table_name and table_name not in table_names:
                    table_names.append(table_name)

                # 收集数据卡片详细信息（立即序列化，避免循环引用）
                data_cards_info.append({
                    "doc_id": doc_id,
                    "table_name": schema_row.table_name if schema_row else None,
                    "database_name": schema_row.database_name if schema_row else None,
                    "connect_name": connect_name,
                    "card_content": _make_json_serializable(card)  # 立即序列化，避免后续循环引用问题
                })
                
                # 收集数据源信息（去重）（增加用户隔离），ds_info 已在上面查询
                if ds_info:
                    ds_id = str(ds_info.id)
                    ds_name = ds_info.database_name or ds_info.connect_name
                    if ds_id not in datasource_ids:
                        datasource_ids.append(ds_id)
                    if ds_name not in datasource_names:
                        datasource_names.append(ds_name)
            except Exception as e:
                print(f"[DEBUG] ❌ 构建卡片 {idx + 1} (doc_id={doc_id}) 的表对象时出错: {str(e)}")
                import traceback
                traceback.print_exc()
                continue

        print(f"[DEBUG] 表对象构建完成，成功 {len(table_objs)} 个")

        # 在收集涉及的数据源信息后，补充来源数据源的名称
        # source_datasource_ids 已经在请求参数中获取，现在需要获取对应的名称
        if source_datasource_ids:
            from uuid import UUID as PyUUID
            for ds_id in source_datasource_ids:
                # 确保 ds_id 是单个字符串而不是列表
                if isinstance(ds_id, list):
                    ds_id = ds_id[0] if ds_id else None
                if not ds_id:
                    continue
                try:
                    ds_uuid = PyUUID(str(ds_id))
                    ds_info = DatasourceInfo.query.filter_by(id=ds_uuid).first()
                    if ds_info:
                        ds_name = ds_info.database_name or ds_info.connect_name
                        if ds_name not in source_datasource_names:
                            source_datasource_names.append(ds_name)
                    print(f"[聚合检索] 来源数据源: id={ds_id}, name={source_datasource_names[-1] if source_datasource_names else '未知'}")
                except ValueError:
                    print(f"[聚合检索] ⚠️ 无效的数据源ID: {ds_id}，跳过")
                    continue

        entity_key = infer_entity_key_from_cards(table_objs)  # 获取主键

        # 3) 获取关系卡片（用于SQL生成时的JOIN条件增强）
        # 从召回的数据卡片中提取表名和数据源ID，批量查询关系卡片
        relationship_data_cache = {}  # {datasource_id: relationship_data}
        table_names_by_datasource = {}  # {datasource_id: [table_names]}

        for t in table_objs:
            # 通过 connect_name 查找 DatasourceInfo 获取 datasource_id（增加用户隔离）
            connect_name = t.get("connect_name")
            if connect_name:
                ds_info = DatasourceInfo.query.filter_by(
                    connect_name=connect_name,
                    user_id=str(flask_login.current_user.id)
                ).first()
                if ds_info:
                    ds_id = str(ds_info.id)
                    if ds_id not in table_names_by_datasource:
                        table_names_by_datasource[ds_id] = []
                    table_names_by_datasource[ds_id].append(t.get("table_name"))

        # 批量获取每个数据源的关系卡片
        for ds_id, table_names in table_names_by_datasource.items():
            try:
                rel_data = fetch_relationship_cards(
                    datasource_id=ds_id,
                    table_names=table_names,
                    user_id=str(flask_login.current_user.id)
                )
                relationship_data_cache[ds_id] = rel_data
                print(
                    f"[agg] 数据源 {ds_id} 获取到 {len(rel_data.get('cards', {}))} 张关系卡片, {len(rel_data.get('join_suggestions', []))} 个JOIN建议")
            except Exception as e:
                print(f"[agg] 获取数据源 {ds_id} 的关系卡片失败: {e}")
                relationship_data_cache[ds_id] = {"cards": {}, "join_suggestions": [], "missing_tables": table_names}

        if not table_objs:
            # 记录日志：未命中数据卡片
            total_duration_ms = int((time_module.time() - start_time) * 1000)
            empty_payload = {
                "clusters": [],
                "merge": {"strategy": merge_strategy, "entity_key": entity_key},
                "final_rows": [],
                "data_cards": []
            }
            _log_query(
                user_id=user_id,
                question=original_question,
                sql=None,
                source_datasource_ids=source_datasource_ids,
                source_datasource_names=source_datasource_names,
                datasource_ids=datasource_ids,
                datasource_names=datasource_names,
                table_names=[],
                metrics={**metrics, "total_duration_ms": total_duration_ms},
                tokens=tokens,
                result_count=0,
                quality=quality,
                merge_strategy=merge_strategy,
                success=False,
                error_message="未命中可用数据卡片",
                full_response_result=empty_payload,
                cluster_sqls=None,
                # === 只在术语展开时填充 ===
                processed_question=user_question if term_rewrite_performed else None,
                term_rewrite_info={
                    "enabled": enable_term_rewrite,
                    "matched_count": len(matched_terms),
                    "matched_terms": matched_terms,
                    "rewritten_question": rewritten_question
                } if term_rewrite_performed else None
            )
            print(f"[查询日志] 术语展开状态: term_rewrite_performed={term_rewrite_performed}, processed_question={'有值' if (user_question if term_rewrite_performed else None) else 'None'}")
            return format_response(
                {
                    "clusters": [],
                    "merge": {"strategy": merge_strategy, "entity_key": entity_key},
                    "final_rows": [],
                    "data_cards": _make_json_serializable(data_cards_info),  # 返回数据卡片信息
                    "term_rewrite": {
                        "enabled": enable_term_rewrite,
                        "matched_count": len(matched_terms),
                        "matched_terms": matched_terms,
                        "rewritten_question": rewritten_question
                    }
                },
                200,
                "未命中可用数据卡片"
            )

        # 3) Trino特殊处理：检查是否所有表都通过Trino连接访问
        # 调试：打印所有表的连接信息
        print("[DEBUG] 所有表的连接信息:")
        try:
            for i, t in enumerate(table_objs):
                connect_name = t.get("connect_name", "")
                table_name = t.get("table_name")
                db_type = t.get("db_type")
                print(f"  表{i + 1}: {table_name} -> connect_name: '{connect_name}', db_type: '{db_type}'")
            print("[DEBUG] 表连接信息输出完成")
        except Exception as e:
            print(f"[DEBUG] ❌ 输出表连接信息时出错: {str(e)}")
            import traceback
            traceback.print_exc()

        # 检查是否所有表都通过Trino连接（connect_name以"trino-"开头）
        print("[DEBUG] 开始检查Trino连接...")
        try:
            trino_connected_tables = [t for t in table_objs if
                                      (t.get("connect_name") or "").lower().startswith("trino-")]
            is_all_trino_connected = len(trino_connected_tables) == len(table_objs) and len(table_objs) > 0

            print(f"[DEBUG] 通过Trino连接的表: {len(trino_connected_tables)}/{len(table_objs)}")
            print(f"[DEBUG] 是否全部通过Trino: {is_all_trino_connected}")
        except Exception as e:
            print(f"[DEBUG] ❌ Trino检查时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            # 设置为False继续执行
            is_all_trino_connected = False
            trino_connected_tables = []

        if is_all_trino_connected:
            print(f"[DEBUG] 进入Trino统一处理分支...")
            # 所有表都通过Trino连接，使用统一的跨catalog处理
            print(f"[agg] 检测到纯Trino连接查询，使用跨catalog模式，共 {len(trino_connected_tables)} 张表")

            # ✅ 修复：合并所有数据源的关系卡片，用于 Trino 统一查询的关系增强
            # 跨catalog场景下，trino_connected_tables 涉及多个数据源（每个 trino-xxx 连接对应一个数据源），
            # 所以需要把每个数据源的 relationship_data 都收集起来，合并后传给 _exec_trino_unified
            trino_relationship_data = {"cards": {}, "join_suggestions": [], "missing_tables": []}
            for t in trino_connected_tables:
                connect_name = t.get("connect_name")
                if not connect_name:
                    continue
                ds_info = DatasourceInfo.query.filter_by(
                    connect_name=connect_name,
                    user_id=str(flask_login.current_user.id)
                ).first()
                if ds_info:
                    ds_id = str(ds_info.id)
                    rel_data = relationship_data_cache.get(ds_id)
                    if rel_data:
                        # 注意：cards 用 table_name 作 key，
                        # 跨catalog场景下不同 catalog 的同名物理表可能 key 冲突，
                        # 这里先简单合并（同 catalog.schema 不会冲突，跨 catalog 时优先保留后写的）
                        trino_relationship_data["cards"].update(rel_data.get("cards", {}))
                        trino_relationship_data["join_suggestions"].extend(rel_data.get("join_suggestions", []))

            has_trino_rel_cards = trino_relationship_data.get("cards") or trino_relationship_data.get("join_suggestions")
            if has_trino_rel_cards:
                print(f"[agg] Trino统一查询：合并后 {len(trino_relationship_data['cards'])} 张关系卡片, {len(trino_relationship_data['join_suggestions'])} 个JOIN建议")
            else:
                print(f"[agg] Trino统一查询：未发现关系卡片")

            try:
                trino_result = _exec_trino_unified(
                    user_question=user_question,
                    tables=trino_connected_tables,
                    entity_key=entity_key,
                    user_id=user_id,  # 传入 user_id 用于用户隔离
                    relationship_data=trino_relationship_data,  # ✅ 修复：传入关系卡片数据
                )

                # 直接返回Trino结果，不需要跨簇融合
                # 但需要做一次深度清理，移除不可序列化/循环引用字段
                clean_trino_cluster = {k: v for k, v in trino_result.items() if not k.startswith("_")}
                safe_cluster = _make_json_serializable(clean_trino_cluster)
                safe_final_rows = _make_json_serializable(trino_result.get("data", []))
                payload = {
                    "clusters": [safe_cluster],
                    "merge": {"strategy": "TRINO_UNIFIED", "entity_key": entity_key},
                    "final_rows": safe_final_rows,
                    "data_cards": _make_json_serializable(data_cards_info),
                    "term_rewrite": {
                        "enabled": enable_term_rewrite,
                        "matched_count": len(matched_terms),
                        "matched_terms": matched_terms,
                        "rewritten_question": rewritten_question
                    }
                }

                # 记录查询日志
                total_duration_ms = int((time_module.time() - start_time) * 1000)
                # 构建 cluster_sqls（TRINO_UNIFIED 场景下只有一条 SQL）
                trino_cluster_sqls = [{
                    "datasource_ids": datasource_ids or [],
                    "datasource_names": datasource_names or [],
                    "table_names": table_names or [],
                    "sql": safe_cluster.get("target_sql") or '',
                    "fusion_strategy": "TRINO_UNIFIED"
                }]
                _log_query(
                    user_id=user_id,
                    question=original_question,
                    sql=safe_cluster.get("target_sql"),
                    source_datasource_ids=source_datasource_ids,
                    source_datasource_names=source_datasource_names,
                    datasource_ids=datasource_ids,
                    datasource_names=datasource_names,
                    table_names=table_names,
                    metrics={**metrics, "total_duration_ms": total_duration_ms},
                    tokens=tokens,
                    result_count=len(safe_final_rows),
                    quality=quality,
                    merge_strategy="TRINO_UNIFIED",
                    success=True,
                    full_response_result=payload,
                    cluster_sqls=trino_cluster_sqls,
                    # === 只在术语展开时填充 ===
                    processed_question=user_question if term_rewrite_performed else None,
                    term_rewrite_info={
                        "enabled": enable_term_rewrite,
                        "matched_count": len(matched_terms),
                        "matched_terms": matched_terms,
                        "rewritten_question": rewritten_question
                    } if term_rewrite_performed else None
                )
                print(f"[查询日志] 术语展开状态: term_rewrite_performed={term_rewrite_performed}, processed_question={'有值' if (user_question if term_rewrite_performed else None) else 'None'}")

                return format_response(payload, 200, "查询成功")

            except ValueError as ve:
                # 如果是连接配置问题，回退到传统分簇处理
                if "未找到真正的Trino连接配置" in str(ve):
                    print(f"[agg] Trino连接配置问题，回退到传统分簇处理: {str(ve)}")
                    # 继续执行传统分簇逻辑
                else:
                    return format_response(None, 400, f"Trino配置错误：{str(ve)}")
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                print(f"[agg] Trino统一查询异常：{str(e)}")
                print(f"[agg] 详细错误：\n{error_detail}")
                return format_response(None, 500, f"Trino查询异常：{str(e)}")

        # 3) 分簇（同 db_type + connect_info 的放一起，准备簇内联查）
        print(f"[DEBUG] 开始分簇，共 {len(table_objs)} 个表对象...")
        try:
            clusters = build_clusters(table_objs)
            print(f"[DEBUG] 分簇完成，生成 {len(clusters)} 个簇")
        except Exception as e:
            print(f"[DEBUG] ❌ 分簇时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return format_response(None, 500, f"分簇失败：{str(e)}")

        # 4) 簇内生成单条 SQL 并执行（带关系卡片增强，支持并行执行）
        print(f"[agg] 开始簇内执行，共 {len(clusters)} 个簇")
        cluster_results = []

        # 策略：单簇串行执行，多簇并行执行以提升性能
        # 并行执行时，使用 ThreadPoolExecutor 并行处理多个簇的 SQL 生成和执行
        if len(clusters) == 1:
            # 单簇场景：使用原有串行逻辑（简单直接）
            print(f"[agg] 单簇场景，使用串行执行模式")
            idx = 0
            for (db_type, connect_info), tables in clusters.items():
                print(f"[agg] 处理第 {idx + 1}/{len(clusters)} 个簇: db_type={db_type}, 表数量={len(tables)}")
                try:
                    # 获取该簇涉及的数据源的关系卡片
                    cluster_relationship_data = None
                    if tables:
                        first_table = tables[0]
                        connect_name = first_table.get("connect_name")
                        if connect_name:
                            ds_info = DatasourceInfo.query.filter_by(
                                connect_name=connect_name,
                                user_id=str(flask_login.current_user.id)
                            ).first()
                            if ds_info:
                                ds_id = str(ds_info.id)
                                cluster_relationship_data = relationship_data_cache.get(ds_id)

                    print(f"[agg] 簇 {idx + 1} 开始执行 _exec_cluster...")
                    r = _exec_cluster(
                        user_question=user_question,
                        db_type=db_type,
                        connect_info=connect_info,
                        tables=tables,
                        entity_key=entity_key,
                        relationship_data=cluster_relationship_data,
                    )
                    print(f"[agg] 簇 {idx + 1} 执行完成，返回 {len(r.get('rows', []))} 行数据")

                    # 收集 LLM usage 信息
                    llm_usage = r.get("_llm_usage", {})
                    tokens["llm_prompt_tokens"] += llm_usage.get("prompt_tokens", 0)
                    tokens["llm_completion_tokens"] += llm_usage.get("completion_tokens", 0)
                    tokens["total_tokens"] += llm_usage.get("total_tokens", 0)
                    metrics["llm_gen_sql_ms"] += llm_usage.get("generation_ms", 0)

                    # 收集 SQL 执行时间
                    metrics["sql_execution_ms"] += r.get("_sql_execution_ms", 0)

                    # 收集选中的卡片数
                    cards_selected = len(r.get("cluster_tables", []))
                    quality["cards_selected"] += cards_selected

                    cluster_results.append(r)
                except ValueError as ve:
                    print(f"[agg] ⚠️ 簇 {idx + 1} 执行失败（ValueError）: {str(ve)}")
                    error_result = {
                        "db_type": db_type,
                        "connect_info_safe": {"type": db_type},
                        "tables": [{"table_name": t.get("table_name")} for t in tables],
                        "target_sql": "",
                        "rows": [],
                        "entity_ids": [],
                        "note": f"查询条件校验失败: {str(ve)}",
                        "error": str(ve),
                        "warnings": ["簇执行失败"]
                    }
                    cluster_results.append(error_result)
                except Exception as e:
                    import traceback
                    error_detail = traceback.format_exc()
                    print(f"[agg] ⚠️ 簇 {idx + 1} 执行异常: {str(e)}")
                    print(f"[agg] 详细错误堆栈:\n{error_detail}")

                    user_friendly_msg = "查询执行失败"
                    if "does not exist" in str(e):
                        if "relation" in str(e):
                            user_friendly_msg = "表不存在，可能是schema配置问题"
                        elif "column" in str(e):
                            user_friendly_msg = "字段不存在，可能是大模型推测错误"

                    error_result = {
                        "db_type": db_type,
                        "connect_info_safe": {"type": db_type},
                        "tables": [{"table_name": t.get("table_name")} for t in tables],
                        "target_sql": "",
                        "rows": [],
                        "entity_ids": [],
                        "note": user_friendly_msg,
                        "error": str(e),
                        "warnings": ["簇执行失败"]
                    }
                    cluster_results.append(error_result)
                idx += 1
        else:
            # 多簇场景：使用并行执行模式提升性能
            print(f"[agg] 多簇场景（{len(clusters)} 个），使用并行执行模式")

            # 预加载所有可能用到的提示词到缓存（避免在线程中访问数据库）
            print(f"[agg] 预加载提示词模板到缓存...")
            from controllers.query.sql_prompt_loader import load_prompt
            unique_db_types = set()
            for (db_type, _), _ in clusters.items():
                unique_db_types.add(db_type)

            for db_type in unique_db_types:
                try:
                    template_name = _pick_template_by_db(db_type)
                    load_prompt(template_name)  # 预加载到缓存
                    print(f"[agg] ✅ 已预加载提示词: {template_name}")
                except Exception as e:
                    print(f"[agg] ⚠️ 预加载提示词失败 ({db_type}): {e}")

            # 同时预加载其他可能用到的提示词
            try:
                load_prompt("strategy_detect.txt")
                load_prompt("result_fusion.txt")
                print(f"[agg] ✅ 已预加载通用提示词")
            except Exception as e:
                print(f"[agg] ⚠️ 预加载通用提示词失败: {e}")

            # 预加载模型配置（避免在线程中访问数据库）
            print(f"[agg] 预加载模型配置...")
            model_config_dict = None
            try:
                from models.model_config import Model_configuration
                model_config = Model_configuration.query.filter_by(model_class='base').first()
                if model_config:
                    model_config_dict = {
                        "api_key": model_config.model_api_key,
                        "api_url": model_config.url,
                        "model_name": model_config.model_name
                    }
                    print(f"[agg] ✅ 已预加载模型配置: {model_config.model_name}")
                else:
                    print(f"[agg] ⚠️ 未找到模型配置")
            except Exception as e:
                print(f"[agg] ⚠️ 预加载模型配置失败: {e}")

            # 准备并行任务参数
            cluster_tasks = []
            for idx, ((db_type, connect_info), tables) in enumerate(clusters.items()):
                # 准备关系卡片数据
                cluster_relationship_data = None
                if tables:
                    first_table = tables[0]
                    connect_name = first_table.get("connect_name")
                    if connect_name:
                        ds_info = DatasourceInfo.query.filter_by(
                            connect_name=connect_name,
                            user_id=str(flask_login.current_user.id)
                        ).first()
                        if ds_info:
                            ds_id = str(ds_info.id)
                            cluster_relationship_data = relationship_data_cache.get(ds_id)

                cluster_tasks.append({
                    "idx": idx,
                    "db_type": db_type,
                    "connect_info": connect_info,
                    "tables": tables,
                    "relationship_data": cluster_relationship_data,
                    "model_config_dict": model_config_dict,  # 传递模型配置
                })

            # 使用 ThreadPoolExecutor 并行执行
            # 限制最大并发数，避免过多并发对系统造成压力
            max_workers = min(len(cluster_tasks), 5)
            parallel_start_time = time_module.time()
            print(f"[agg] 启动并行执行，最大并发数: {max_workers}")

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_task = {}
                for task in cluster_tasks:
                    future = executor.submit(
                        _exec_cluster_parallel,
                        cluster_idx=task["idx"],
                        db_type=task["db_type"],
                        connect_info=task["connect_info"],
                        tables=task["tables"],
                        entity_key=entity_key,
                        relationship_data=task["relationship_data"],
                        user_question=user_question,
                        model_config_dict=task["model_config_dict"],  # 传递模型配置
                    )
                    future_to_task[future] = task["idx"]

                # 收集结果（按索引顺序排列）
                results_dict = {}
                for future in as_completed(future_to_task):
                    task_idx = future_to_task[future]
                    try:
                        returned_idx, result = future.result()
                        results_dict[returned_idx] = result
                        print(f"[agg] ✅ 并行任务完成: 簇 {returned_idx + 1}")
                    except Exception as e:
                        print(f"[agg] ❌ 并行任务异常: 簇 {task_idx}, 错误: {str(e)}")
                        results_dict[task_idx] = {
                            "db_type": clusters.items().__getitem__(task_idx)[0][0] if task_idx < len(list(clusters.items())) else "unknown",
                            "connect_info_safe": {"type": "unknown"},
                            "tables": [],
                            "target_sql": "",
                            "rows": [],
                            "entity_ids": [],
                            "note": f"并行执行异常: {str(e)}",
                            "error": str(e),
                            "warnings": ["簇执行失败"]
                        }

            # 按原始顺序整理结果
            cluster_results = [results_dict.get(i) for i in range(len(cluster_tasks)) if results_dict.get(i) is not None]

            parallel_elapsed_ms = int((time_module.time() - parallel_start_time) * 1000)
            print(f"[agg] 并行执行完成，耗时 {parallel_elapsed_ms}ms（串行预估耗时约 {parallel_elapsed_ms * max_workers}ms）")

            # 汇总 LLM usage 和 metrics 信息
            for r in cluster_results:
                llm_usage = r.get("_llm_usage", {})
                tokens["llm_prompt_tokens"] += llm_usage.get("prompt_tokens", 0)
                tokens["llm_completion_tokens"] += llm_usage.get("completion_tokens", 0)
                tokens["total_tokens"] += llm_usage.get("total_tokens", 0)
                metrics["llm_gen_sql_ms"] += llm_usage.get("generation_ms", 0)

                # 收集 SQL 执行时间
                metrics["sql_execution_ms"] += r.get("_sql_execution_ms", 0)

                # 收集选中的卡片数
                cards_selected = len(r.get("cluster_tables", []))
                quality["cards_selected"] += cards_selected

        # 4.5) 过滤与问题无关的簇，防止无关结果进入融合环节
        cluster_results, cluster_filter_warnings = _filter_clusters_by_question(cluster_results, user_question)
        print(f"[agg] 簇过滤完成，剩余 {len(cluster_results)} 个簇")

        # 5) 跨簇融合 - 尝试使用LLM智能融合（带关系卡片），失败则回退到规则融合
        # 注意：单簇场景也会走融合流程，但会被识别为无需融合，直接返回结果
        # ✅ 修复：使用 merge_relationship_data 合并（join_suggestions 按 (from,to,from_c,to_c) 去重并保留 confidence 最高的那条）
        merged_relationship_data = merge_relationship_data(*list(relationship_data_cache.values()))
        print(
            f"[agg] 融合阶段：合并后共 {len(merged_relationship_data['cards'])} 张关系卡片, {len(merged_relationship_data['join_suggestions'])} 个JOIN建议")

        # 判断是否使用LLM融合（不再依赖entity_key）
        use_llm_fusion = _should_use_llm_fusion(cluster_results)
        print(f"[agg] 是否使用LLM融合: {use_llm_fusion}")
        llm_fusion_result = None

        if use_llm_fusion:
            print(f"[agg] 检测到多数据源场景，尝试使用LLM语义理解融合...")
            llm_fusion_result = _llm_fuse_results(
                user_question=user_question,
                cluster_results=cluster_results,
                relationship_data=merged_relationship_data,
                model_config_dict=model_config_dict  # 传递预加载的模型配置
            )

        # 如果LLM融合成功，直接使用其结果
        if llm_fusion_result and llm_fusion_result.get("fused_rows"):
            print(f"[agg] ✅ 使用LLM融合结果，融合后 {len(llm_fusion_result.get('fused_rows', []))} 行数据")
            final_rows = llm_fusion_result.get("fused_rows", [])
            merge_strategy = llm_fusion_result.get("fusion_strategy", merge_strategy)
            fill_warnings = list(cluster_filter_warnings or [])
            fill_warnings.extend(llm_fusion_result.get("warnings", []))

            # 处理冲突信息
            conflicts = llm_fusion_result.get("conflicts", [])
            for conflict in conflicts:
                entity_desc = conflict.get('entity_desc', '未知实体')
                fill_warnings.append(
                    f"[融合冲突] {entity_desc}: "
                    f"字段 '{conflict.get('field')}' 有多个值，{conflict.get('resolution', '')}"
                )

            # 清理 cluster_results
            clean_cluster_results = []
            for r in cluster_results:
                clean_r = {k: v for k, v in r.items() if not k.startswith('_')}
                clean_cluster_results.append(clean_r)

            payload = {
                "clusters": _make_json_serializable(clean_cluster_results),
                "merge": {
                    "strategy": merge_strategy,
                    "entity_key": entity_key,
                    "fusion_method": "llm",  # 标记使用了LLM融合
                },
                "final_rows": _make_json_serializable(final_rows),
                "fill_warnings": fill_warnings,
                "data_cards": _make_json_serializable(data_cards_info),
                "term_rewrite": {
                    "enabled": enable_term_rewrite,
                    "matched_count": len(matched_terms),
                    "matched_terms": matched_terms,
                    "rewritten_question": rewritten_question
                }
            }

            # 记录查询日志
            total_duration_ms = int((time_module.time() - start_time) * 1000)
            # 构建 cluster_sqls（从各簇结果中提取 SQL）
            llm_fusion_cluster_sqls = []
            for cr in cluster_results:
                cluster_sql = {
                    'datasource_ids': cr.get('datasource_ids', []) or [],
                    'datasource_names': cr.get('datasource_names', []) or [],
                    'table_names': cr.get('table_names', []) or [],
                    'sql': cr.get('target_sql') or '',
                    'fusion_strategy': cr.get('fusion_strategy', merge_strategy)
                }
                llm_fusion_cluster_sqls.append(cluster_sql)
            _log_query(
                user_id=user_id,
                question=original_question,
                sql=llm_fusion_cluster_sqls[0].get('sql') if llm_fusion_cluster_sqls else None,
                source_datasource_ids=source_datasource_ids,
                source_datasource_names=source_datasource_names,
                datasource_ids=datasource_ids,
                datasource_names=datasource_names,
                table_names=table_names,
                metrics={**metrics, "llm_fusion_ms": llm_fusion_result.get("fusion_time_ms", 0),
                         "total_duration_ms": total_duration_ms},
                tokens=tokens,
                result_count=len(final_rows),
                quality=quality,
                merge_strategy=merge_strategy,
                success=True,
                full_response_result=payload,
                cluster_sqls=llm_fusion_cluster_sqls,
                # === 只在术语展开时填充 ===
                processed_question=user_question if term_rewrite_performed else None,
                term_rewrite_info={
                    "enabled": enable_term_rewrite,
                    "matched_count": len(matched_terms),
                    "matched_terms": matched_terms,
                    "rewritten_question": rewritten_question
                } if term_rewrite_performed else None
            )
            print(f"[查询日志] 术语展开状态: term_rewrite_performed={term_rewrite_performed}, processed_question={'有值' if (user_question if term_rewrite_performed else None) else 'None'}")

            return format_response(payload, 200, "success")

        # ==============================================================
        # 单簇场景优化：直接返回SQL查询结果，无需融合
        # ==============================================================
        if len(cluster_results) == 1:
            single_cluster = cluster_results[0]
            single_rows = single_cluster.get("rows", [])
            single_warnings = list(cluster_filter_warnings or [])
            single_warnings.extend(single_cluster.get("warnings", []))

            print(f"[agg] ✅ 单簇场景：直接返回SQL查询结果，无需融合（共 {len(single_rows)} 行）")

            # 清理 cluster_results，移除不可序列化的字段
            clean_cluster_results = []
            for r in cluster_results:
                clean_r = {k: v for k, v in r.items() if not k.startswith('_')}
                clean_cluster_results.append(clean_r)

            payload = {
                "clusters": _make_json_serializable(clean_cluster_results),
                "merge": {
                    "strategy": "SINGLE_CLUSTER",  # 标记为单簇场景
                    "entity_key": entity_key,
                    "fusion_method": "none",  # 无需融合
                    "note": "单数据源查询，无需跨源融合"
                },
                "final_rows": _make_json_serializable(single_rows),
                "fill_warnings": single_warnings,
                "data_cards": _make_json_serializable(data_cards_info),
                "term_rewrite": {
                    "enabled": enable_term_rewrite,
                    "matched_count": len(matched_terms),
                    "matched_terms": matched_terms,
                    "rewritten_question": rewritten_question
                }
            }

            # 记录查询日志
            total_duration_ms = int((time_module.time() - start_time) * 1000)
            # 构建 cluster_sqls
            single_cluster_sqls = [{
                'datasource_ids': single_cluster.get('datasource_ids', []) or [],
                'datasource_names': single_cluster.get('datasource_names', []) or [],
                'table_names': single_cluster.get('table_names', []) or [],
                'sql': single_cluster.get("target_sql") or '',
                'fusion_strategy': 'SINGLE_CLUSTER'
            }]
            _log_query(
                user_id=user_id,
                question=original_question,
                sql=single_cluster.get("target_sql"),
                source_datasource_ids=source_datasource_ids,
                source_datasource_names=source_datasource_names,
                datasource_ids=datasource_ids,
                datasource_names=datasource_names,
                table_names=table_names,
                metrics={**metrics, "total_duration_ms": total_duration_ms},
                tokens=tokens,
                result_count=len(single_rows),
                quality=quality,
                merge_strategy="SINGLE_CLUSTER",
                success=True,
                full_response_result=payload,
                cluster_sqls=single_cluster_sqls,
                # === 只在术语展开时填充 ===
                processed_question=user_question if term_rewrite_performed else None,
                term_rewrite_info={
                    "enabled": enable_term_rewrite,
                    "matched_count": len(matched_terms),
                    "matched_terms": matched_terms,
                    "rewritten_question": rewritten_question
                } if term_rewrite_performed else None
            )
            print(f"[查询日志] 术语展开状态: term_rewrite_performed={term_rewrite_performed}, processed_question={'有值' if (user_question if term_rewrite_performed else None) else 'None'}")

            return format_response(payload, 200, "success")

        # ==============================================================
        # 多簇场景：使用规则融合逻辑（LLM融合失败时的回退方案）
        # ==============================================================
        print(f"[agg] 多簇场景（{len(cluster_results)}个簇），使用规则融合逻辑")

        # 只收集有实际查询结果且 entity_key 真实存在于表中的簇
        def _has_entity_key_in_cluster(cluster: dict, entity_key: str) -> bool:
            """检查 entity_key 是否真实存在于簇的任意表中（不是别名）"""
            cluster_tables = cluster.get("cluster_tables") or []
            for table in cluster_tables:
                columns = table.get("columns") or []
                for col in columns:
                    if col.get("name") == entity_key:
                        return True
            return False

        entity_sets = []
        for r in cluster_results:
            has_ids = r.get("entity_ids") is not None and len(r.get("entity_ids") or []) > 0
            has_key = _has_entity_key_in_cluster(r, entity_key)

            if has_ids and has_key:
                entity_sets.append(set(r.get("entity_ids") or []))
                print(f"[agg] 簇 {r.get('db_type')} 参与融合，entity_ids={r.get('entity_ids')}")
            elif has_ids and not has_key:
                print(f"[agg] 簇 {r.get('db_type')} 跳过融合：entity_key '{entity_key}' 不存在于表中（可能是别名）")
            elif not has_ids:
                print(f"[agg] 簇 {r.get('db_type')} 跳过融合：无查询结果")

        def _merge_sets_ext(entity_sets, strategy: str):
            if not entity_sets:
                return set()
            s = (strategy or "OR").upper()
            if s == "AND":
                out = set.intersection(*entity_sets) if entity_sets else set()
            elif s == "OR":
                out = set.union(*entity_sets) if entity_sets else set()
            elif s == "PRIORITY":
                # 选"优先簇"：你可以用更复杂的启发式；这里简单用：返回行数最多且列覆盖度高的簇
                pri = max(cluster_results, key=lambda r: (len(r.get("entity_ids") or []),
                                                          len(r.get("rows", [{}])[0].keys() if r.get("rows") else [])),
                          default=None)
                out = set(pri.get("entity_ids") or []) if pri else set()
            elif s == "UNION":
                out = set.union(*entity_sets) if entity_sets else set()
            else:
                out = set.union(*entity_sets) if entity_sets else set()
            return out

        final_ids = _merge_sets_ext(entity_sets, merge_strategy)
        print(f"[agg] 融合策略={merge_strategy}，参与簇数={len(entity_sets)}，final_entity_ids={sorted(final_ids)}")

        # 6) 构造最终结果：直接从 cluster_results 中提取符合 final_ids 的行
        # 不需要回填查询，因为第一次查询已经返回了完整的数据（包括 JOIN 和 WHERE 条件）

        # 6.0) 检测查询类型：是"明细列表查询"还是"聚合查询"
        # 明细列表查询：列出、显示、查询、展示 + 多个字段（如时间、地点等明细信息）
        # 聚合查询：统计、总和、平均、最大、最小、计数等
        def is_detail_list_query(user_question: str) -> bool:
            """
            判断是否是明细列表查询（需要保留多条记录），而不是聚合查询
            
            明细列表查询的特征：
            1. 包含"列出"、"显示"、"查询"、"列举"等动词
            2. 包含多个明细字段（如时间、地点、教师、教室等）
            3. 不包含聚合关键词（如"总和"、"平均"、"统计"等）
            
            聚合查询的特征：
            1. 包含聚合关键词（如"最"、"总"、"平均"、"统计"等）
            2. 通常只关注少数字段（如只关心"销量最好的产品名称和销量"）
            """
            q = user_question.lower()

            # 明细列表关键词
            detail_keywords = ['列出', '显示', '查询', '列举', '展示', '查看', '有哪些', '都有什么']
            # 聚合关键词
            agg_keywords = ['最高', '最低', '最大', '最小', '最多', '最少', '总和', '平均', '统计', '计数', '排名',
                            '第一', '第二']

            # 时间/地点等明细字段关键词（这些通常意味着需要明细列表）
            detail_field_keywords = ['时间', '地点', '教室', '日期', '星期', '地址', '位置', '仓库', '负责人']

            has_detail_verb = any(kw in q for kw in detail_keywords)
            has_agg_keyword = any(kw in q for kw in agg_keywords)
            has_detail_fields = any(kw in q for kw in detail_field_keywords)

            # 如果有明细动词，且有明细字段，且没有聚合关键词 → 明细列表查询
            if has_detail_verb and has_detail_fields and not has_agg_keyword:
                return True

            # 如果有多个明细字段关键词（2个及以上），即使没有明确的动词 → 也可能是明细列表查询
            detail_field_count = sum(1 for kw in detail_field_keywords if kw in q)
            if detail_field_count >= 2 and not has_agg_keyword:
                return True

            return False

        # 判断当前查询类型
        is_detail_query = is_detail_list_query(user_question)
        print(f"[agg] 查询类型检测：{'明细列表查询' if is_detail_query else '聚合查询'}")

        rows_by_id = {}
        all_detail_rows = []  # 用于明细列表查询，保留所有记录
        fill_warnings = list(cluster_filter_warnings or [])

        # 6.1) 收集每个簇的警告信息
        for r in cluster_results:
            db_type = r.get("db_type", "unknown")
            cluster_warnings = r.get("warnings", [])

            # 添加簇级别的警告
            if cluster_warnings:
                for w in cluster_warnings:
                    fill_warnings.append(f"[{db_type}] {w}")

            # 添加跳过融合的原因
            has_rows = r.get("rows") and len(r.get("rows")) > 0
            has_entity_ids = r.get("entity_ids") and len(r.get("entity_ids")) > 0
            has_key = _has_entity_key_in_cluster(r, entity_key)

            if not has_rows:
                fill_warnings.append(f"[{db_type}] 无查询结果（跳过融合）")
            elif not has_entity_ids:
                fill_warnings.append(f"[{db_type}] 结果中未包含实体键 '{entity_key}'（跳过融合）")
            elif not has_key:
                fill_warnings.append(f"[{db_type}] 实体键 '{entity_key}' 不存在于表结构中（可能是别名，跳过融合）")

        # 6.2) 根据查询类型，采用不同的融合策略
        field_conflicts = {}  # {entity_id: {field_name: [value1, value2, ...]}}

        use_final_ids = len(final_ids) > 0
        fallback_row_counter = 0

        # 缓存每个簇的entity_key字段映射（避免重复查找）
        entity_key_field_cache = {}  # {簇索引: 实际字段名}

        for r_idx, r in enumerate(cluster_results):
            # 只处理有查询结果的簇
            if not r.get("rows"):
                continue

            db_type = r.get("db_type", "unknown")

            # 查找该簇中的entity_key对应字段（只查找一次）
            if r_idx not in entity_key_field_cache:
                first_row = r.get("rows")[0] if r.get("rows") else {}
                entity_key_field = _find_entity_key_field(first_row, entity_key)
                if not entity_key_field:
                    print(f"[融合] ⚠️ 簇 {db_type} 中未找到entity_key='{entity_key}'对应的字段，跳过该簇")
                    continue
                entity_key_field_cache[r_idx] = entity_key_field
                if entity_key_field != entity_key:
                    print(f"[融合] 簇 {db_type}: entity_key='{entity_key}' 匹配到别名字段: '{entity_key_field}'")

            entity_key_field = entity_key_field_cache[r_idx]

            for row in r.get("rows"):
                k = row.get(entity_key_field)  # 使用匹配到的字段名

                if use_final_ids:
                    if k is None or k not in final_ids:
                        continue
                else:
                    # 无融合 ID 可用时，允许保留所有记录；若缺少实体键，生成占位键以便后续处理
                    if k is None:
                        fallback_row_counter += 1
                        k = f"__row_{fallback_row_counter}"
                    # 同时确保该占位键不会进入 final_ids（final_ids 已为空）

                if is_detail_query:
                    # 明细列表查询：保留所有记录，不去重
                    all_detail_rows.append(row.copy())
                else:
                    # 聚合查询：按 entity_id 去重，合并字段
                    if k not in rows_by_id:
                        rows_by_id[k] = row.copy()
                    else:
                        # 检测字段冲突
                        for field, new_value in row.items():
                            if field in rows_by_id[k]:
                                old_value = rows_by_id[k][field]
                                # 如果值不同，记录冲突
                                if old_value != new_value and field != entity_key_field:  # 使用匹配到的字段名
                                    if k not in field_conflicts:
                                        field_conflicts[k] = {}
                                    if field not in field_conflicts[k]:
                                        field_conflicts[k][field] = [old_value]
                                    if new_value not in field_conflicts[k][field]:
                                        field_conflicts[k][field].append(new_value)

                        # 合并字段（后来的覆盖先前的）
                        rows_by_id[k].update(row)

        # 6.3) 添加字段冲突警告（仅在聚合查询模式下）
        if not is_detail_query and field_conflicts:
            for entity_id, fields in field_conflicts.items():
                for field_name, values in fields.items():
                    fill_warnings.append(
                        f"[融合] 实体 {entity_key}={entity_id} 的字段 '{field_name}' 在多个簇中值不同：{values}（已采用最后一个簇的值）"
                    )

        # 6.4) 检查融合结果是否为空
        if is_detail_query:
            if not all_detail_rows and final_ids:
                fill_warnings.append(
                    f"[融合] 融合策略 '{merge_strategy}' 计算出 {len(final_ids)} 个实体ID，但无法从任何簇中提取到对应的完整行数据"
                )
        else:
            if not rows_by_id and final_ids:
                fill_warnings.append(
                    f"[融合] 融合策略 '{merge_strategy}' 计算出 {len(final_ids)} 个实体ID，但无法从任何簇中提取到对应的完整行数据"
                )

        # 6.5) 过滤掉"空记录"：除了 entity_key 外，其他字段都是 NULL/0/空字符串的记录
        def _is_empty_record(row: dict, entity_key: str) -> bool:
            """
            判断一条记录是否为"空记录"（除了 entity_key 外，其他字段都是无效值）

            判断标准：
            1. 如果记录只有 entity_key 一个字段 → 空记录
            2. 如果所有非 entity_key 字段都是无效值（None/0/0.0/空字符串） → 空记录
            3. 如果大部分字段（>= 70%）是无效值，且没有任何有意义的值 → 空记录
            4. 否则为有效记录

            特殊情况：
            - 对于统计查询（如 COUNT、SUM），即使结果为 0 也不是空记录
              （例如 {"mismatch_count": 0} 是有效结果，不应该被过滤）
            """
            # 特殊情况：检查是否是统计查询结果（字段名包含 count/sum/avg/total/num 等）
            # 这些查询的结果即使为 0 也是有效的
            stat_keywords = ['count', 'sum', 'avg', 'total', 'num', 'ratio', 'rate', 'percentage']
            is_stat_query = any(
                any(keyword in k.lower() for keyword in stat_keywords)
                for k in row.keys() if k != entity_key
            )

            # 如果是统计查询，只要有非 None 的值就不是空记录（即使值为 0）
            if is_stat_query:
                for k, v in row.items():
                    if k == entity_key:
                        continue
                    if v is not None:  # 只要不是 None，就不是空记录（包括 0）
                        return False
                return True  # 所有统计字段都是 None，才是空记录

            if len(row) <= 1:
                return True  # 只有 entity_key，肯定是空记录

            non_key_fields = {k: v for k, v in row.items() if k != entity_key}
            if not non_key_fields:
                return True

            # 定义"无效值"：None、0、0.0、空字符串、False
            def is_invalid_value(v):
                return v is None or v == 0 or v == 0.0 or v == "" or v is False

            # 统计无效值的数量
            invalid_count = sum(1 for v in non_key_fields.values() if is_invalid_value(v))

            # 情况 1：所有非 entity_key 字段都是无效值 → 空记录
            if invalid_count == len(non_key_fields):
                return True

            # 情况 2：大部分字段（>= 70%）是无效值 → 检查是否有有意义的值
            if invalid_count >= len(non_key_fields) * 0.7:
                has_meaningful_value = False
                for k, v in non_key_fields.items():
                    # 有意义的值：非空字符串、非零数字、布尔 True 等
                    if not is_invalid_value(v):
                        # 进一步检查：如果是字符串，长度要 > 0
                        if isinstance(v, str) and len(v.strip()) > 0:
                            has_meaningful_value = True
                            break
                        # 如果是数字，且不是 0/0.0
                        elif isinstance(v, (int, float)) and v != 0 and v != 0.0:
                            has_meaningful_value = True
                            break
                        # 其他类型的非 None 值
                        elif not isinstance(v, (str, int, float)):
                            has_meaningful_value = True
                            break

                if not has_meaningful_value:
                    return True

            return False

        # 根据查询类型和融合策略，过滤空记录并生成最终结果
        # 
        # 重要逻辑：
        # - OR/UNION 查询：不过滤空记录（因为满足任一条件即可，某些字段缺失是正常的）
        # - AND/PRIORITY 查询：过滤空记录（因为需要同时满足多个条件，字段应该完整）
        should_filter_empty = merge_strategy in ['AND', 'PRIORITY']

        if is_detail_query:
            # 明细列表查询：根据策略决定是否过滤 all_detail_rows
            before_filter_count = len(all_detail_rows)

            if should_filter_empty:
                filtered_detail_rows = [
                    row for row in all_detail_rows
                    if not _is_empty_record(row, entity_key)
                ]

                filtered_count = before_filter_count - len(filtered_detail_rows)
                if filtered_count > 0:
                    fill_warnings.append(
                        f"[融合] 已过滤 {filtered_count} 条空记录（这些记录除了 {entity_key} 外，其他字段都是 NULL/0/空值）"
                    )
            else:
                # OR/UNION 查询：不过滤，保留所有记录（满足任一条件即可）
                filtered_detail_rows = all_detail_rows

            final_rows = filtered_detail_rows
        else:
            # 聚合查询：根据策略决定是否过滤 rows_by_id
            before_filter_count = len(rows_by_id)

            if should_filter_empty:
                filtered_rows_by_id = {
                    k: v for k, v in rows_by_id.items()
                    if not _is_empty_record(v, entity_key)
                }

                filtered_count = before_filter_count - len(filtered_rows_by_id)
                if filtered_count > 0:
                    fill_warnings.append(
                        f"[融合] 已过滤 {filtered_count} 条空记录（这些记录除了 {entity_key} 外，其他字段都是 NULL/0/空值）"
                    )
            else:
                # OR/UNION 查询：不过滤，保留所有记录（满足任一条件即可）
                filtered_rows_by_id = rows_by_id

            final_rows = list(filtered_rows_by_id.values())

        # 清理 cluster_results，移除不可序列化的字段
        clean_cluster_results = []
        for r in cluster_results:
            clean_r = {k: v for k, v in r.items() if not k.startswith('_')}
            clean_cluster_results.append(clean_r)

        # 构造 payload，确保所有数据都是 JSON 可序列化的
        is_aggregation = any(kw in user_question.lower() for kw in
                             ['统计', '总和', '平均', '最高', '最低', '最大', '最小', '排名', '报告', '分析'])
        query_type = "aggregation" if is_aggregation else "detail_list"

        payload = {
            "clusters": _make_json_serializable(clean_cluster_results),
            "merge": {
                "strategy": merge_strategy,
                "entity_key": entity_key,
                "final_entity_ids": list(final_ids),
            },
            "final_rows": _make_json_serializable(final_rows),
            "fill_warnings": fill_warnings,
            "data_cards": _make_json_serializable(data_cards_info),
            "term_rewrite": {
                "enabled": enable_term_rewrite,
                "matched_count": len(matched_terms),
                "matched_terms": matched_terms,
                "rewritten_question": rewritten_question
            }
        }

        # 记录查询日志
        total_duration_ms = int((time_module.time() - start_time) * 1000)
        # 构建 cluster_sqls（从各簇结果中提取 SQL）
        rule_fusion_cluster_sqls = []
        for idx, cr in enumerate(cluster_results):
            cluster_sql = {
                'cluster_index': idx,
                'datasource_ids': cr.get('datasource_ids', []) or [],
                'datasource_names': cr.get('datasource_names', []) or [],
                'table_names': cr.get('table_names', []) or [],
                'sql': cr.get('target_sql') or '',
                'fusion_strategy': merge_strategy
            }
            rule_fusion_cluster_sqls.append(cluster_sql)
        _log_query(
            user_id=user_id,
            question=original_question,
            sql=rule_fusion_cluster_sqls[0].get('sql') if rule_fusion_cluster_sqls else None,
            source_datasource_ids=source_datasource_ids,
            source_datasource_names=source_datasource_names,
            datasource_ids=datasource_ids,
            datasource_names=datasource_names,
            table_names=table_names,
            metrics={**metrics, "total_duration_ms": total_duration_ms},
            tokens=tokens,
            result_count=len(final_rows),
            quality=quality,
            merge_strategy=merge_strategy,
            success=True,
            full_response_result=payload,
            cluster_sqls=rule_fusion_cluster_sqls,
            # === 只在术语展开时填充 ===
            processed_question=user_question if term_rewrite_performed else None,
            term_rewrite_info={
                "enabled": enable_term_rewrite,
                "matched_count": len(matched_terms),
                "matched_terms": matched_terms,
                "rewritten_question": rewritten_question
            } if term_rewrite_performed else None
        )
        print(f"[查询日志] 术语展开状态: term_rewrite_performed={term_rewrite_performed}, processed_question={'有值' if (user_question if term_rewrite_performed else None) else 'None'}")

        return format_response(payload, 200, "success")


api.add_resource(QueryByDataCardsAgg, "/query_by_datacards_agg")
