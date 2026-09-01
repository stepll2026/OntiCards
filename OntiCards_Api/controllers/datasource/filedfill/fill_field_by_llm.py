"""
 @File: fill_field_by_llm.py
 @Description: 基于大模型对表及字段的描述进行初步填充
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-10-20 14:37
 @Update: 2026-05-06 - 改为优先从数据库读取提示词
"""

import json
import re
import logging
from pathlib import Path
from typing import Tuple, List, Dict, Any
from datetime import datetime

from controllers.agents.qwen.llm_utils import llm_call

# 提示词配置管理器
from models.prompt_config import prompt_manager


# ---------- 工具 ----------
def _is_blank(v):
    return v is None or (isinstance(v, str) and v.strip() == "")

def _strip_code_fence(s: str) -> str:
    if not isinstance(s, str):
        return s
    s = s.strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", s, flags=re.I)
    return m.group(1) if m else s

def _build_prompt_for_table(
    table_obj: dict,
    sampling_data: dict = None,
    sensitive_fields: list = None
) -> str:
    table_name = (table_obj.get("table_name") or "").strip()
    table_desc = table_obj.get("description") or ""
    cols = table_obj.get("columns") or []

    brief_cols = []
    for c in cols:
        brief_cols.append({
            "name": c.get("name"),
            "type": c.get("type"),
            "is_primary": bool(c.get("is_primary")),
            "is_foreign": bool(c.get("is_foreign")),
            "default": c.get("default"),
            "has_comment": not _is_blank(c.get("comment")),
        })

    # 优先从数据库读取提示词，fallback到文件
    prompt_file_name = "fill_field_by_llm.txt"
    prompt_data = prompt_manager.get_prompt(prompt_file_name)

    if not prompt_data:
        # Fallback 到文件（并自动同步到数据库）
        prompt_path = Path(__file__).resolve().parents[3] / "libs" / "prompt" / "fill_field_by_llm.txt"
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_data = f.read()
            prompt_manager.set_prompt(prompt_file_name, prompt_data)
        else:
            raise FileNotFoundError(f"未找到提示词文件: {prompt_file_name}")

    # 填提示词占位符
    prompt_filled = (
        prompt_data
        .replace("{{table_name}}", table_name)
        .replace("{{table_description_or_空}}", table_desc or "（空）")
        .replace("{{columns_json_brief}}", json.dumps(brief_cols, ensure_ascii=False, indent=2))
    )

    # 填充采样数据（如果有）
    if sampling_data:
        prompt_filled = prompt_filled.replace(
            "{{sampling_data_json}}",
            json.dumps(sampling_data, ensure_ascii=False, indent=2)
        )
    else:
        prompt_filled = prompt_filled.replace("{{sampling_data_json}}", "(无)")

    # 填充敏感字段信息（如果有）
    if sensitive_fields:
        prompt_filled = prompt_filled.replace(
            "{{sensitive_fields_json}}",
            json.dumps(sensitive_fields, ensure_ascii=False, indent=2)
        )
    else:
        prompt_filled = prompt_filled.replace("{{sensitive_fields_json}}", "(无)")

    return prompt_filled

def _merge_patch(orig_table: dict, patch: dict) -> Tuple[dict, bool]:
    """把 LLM 返回的补丁合并进 orig_table，仅改动空项。返回(合并后对象, 是否发生改动)"""
    changed = False

    # 表描述
    td = patch.get("table_description")
    if _is_blank(orig_table.get("description")) and isinstance(td, str) and not _is_blank(td):
        orig_table["description"] = td.strip()
        changed = True

    # 列注释
    patch_cols = {c.get("name"): c for c in (patch.get("columns") or [])}
    for c in (orig_table.get("columns") or []):
        if _is_blank(c.get("comment")):
            pc = patch_cols.get(c.get("name"))
            if pc:
                cm = pc.get("comment")
                if isinstance(cm, str) and not _is_blank(cm):
                    c["comment"] = cm.strip()
                    changed = True

    return orig_table, changed

def check_table_health(table_obj: dict) -> Dict[str, Any]:
    """
    检查单张表的健康状态，记录缺失注释的字段

    返回格式:
    {
        "table_name": "表名",
        "has_table_description": True/False,
        "missing_comment_fields": [
            {"name": "字段名", "type": "字段类型", "is_primary": True/False}
        ],
        "total_fields": 总字段数,
        "missing_count": 缺失注释的字段数
    }
    """
    table_name = (table_obj.get("table_name") or "").strip()
    table_desc = table_obj.get("description") or ""
    cols = table_obj.get("columns") or []

    missing_fields = []
    for col in cols:
        col_name = col.get("name", "")
        col_comment = col.get("comment") or ""
        if _is_blank(col_comment):
            missing_fields.append({
                "name": col_name,
                "type": col.get("type", ""),
                "is_primary": bool(col.get("is_primary", False)),
                "is_foreign": bool(col.get("is_foreign", False))
            })

    return {
        "table_name": table_name,
        "has_table_description": not _is_blank(table_desc),
        "missing_comment_fields": missing_fields,
        "total_fields": len(cols),
        "missing_count": len(missing_fields)
    }

def compare_table_before_after(before_table: dict, after_table: dict) -> Dict[str, Any]:
    """
    对比填充前后的表状态，记录哪些字段被成功填充

    返回格式:
    {
        "table_name": "表名",
        "table_description_filled": True/False,  # 表描述是否被填充
        "filled_fields": [
            {"name": "字段名", "type": "字段类型", "comment": "填充后的注释"}
        ],
        "still_missing_fields": [
            {"name": "字段名", "type": "字段类型", "is_primary": True/False}
        ],
        "filled_count": 成功填充的字段数,
        "still_missing_count": 仍然缺失的字段数
    }
    """
    table_name = (before_table.get("table_name") or "").strip()
    before_cols = {col.get("name", ""): col for col in (before_table.get("columns") or [])}
    after_cols = {col.get("name", ""): col for col in (after_table.get("columns") or [])}

    filled_fields = []
    still_missing_fields = []

    # 检查表描述是否被填充
    before_desc = before_table.get("description") or ""
    after_desc = after_table.get("description") or ""
    table_description_filled = _is_blank(before_desc) and not _is_blank(after_desc)

    # 对比每个字段
    for col_name, before_col in before_cols.items():
        if not col_name:
            continue

        before_comment = before_col.get("comment") or ""
        after_col = after_cols.get(col_name, {})
        after_comment = after_col.get("comment") or ""

        if _is_blank(before_comment):
            # 填充前缺失注释
            if not _is_blank(after_comment):
                # 填充后有了注释，记录为成功填充
                filled_fields.append({
                    "name": col_name,
                    "type": after_col.get("type", before_col.get("type", "")),
                    "comment": after_comment,
                    "is_primary": bool(after_col.get("is_primary", before_col.get("is_primary", False))),
                    "is_foreign": bool(after_col.get("is_foreign", before_col.get("is_foreign", False)))
                })
            else:
                # 填充后仍然缺失，记录为仍然缺失
                still_missing_fields.append({
                    "name": col_name,
                    "type": before_col.get("type", ""),
                    "is_primary": bool(before_col.get("is_primary", False)),
                    "is_foreign": bool(before_col.get("is_foreign", False))
                })

    return {
        "table_name": table_name,
        "table_description_filled": table_description_filled,
        "filled_fields": filled_fields,
        "still_missing_fields": still_missing_fields,
        "filled_count": len(filled_fields),
        "still_missing_count": len(still_missing_fields)
    }

def check_tables_health_batch(tables: List[dict], user_id: str = None, connect_info: str = None,
                              enriched_tables: List[dict] = None) -> Dict[str, Any]:
    """
    批量检查多张表的健康状态，并可选择性地对比填充前后的状态

    参数:
        tables: 填充前的表列表
        user_id: 用户ID
        connect_info: 连接信息
        enriched_tables: 填充后的表列表（可选），如果提供则进行填充前后对比

    返回格式:
    {
        "check_time": "检查时间",
        "user_id": "用户ID",
        "connect_info": "连接信息",
        "total_tables": 总表数,
        "problematic_tables": [
            {
                "table_name": "表名",
                "has_table_description": True/False,
                "missing_comment_fields": [...],
                "total_fields": 总字段数,
                "missing_count": 缺失注释的字段数,
                "fill_result": {  # 如果提供了enriched_tables，则包含此字段
                    "table_description_filled": True/False,
                    "filled_fields": [...],
                    "still_missing_fields": [...],
                    "filled_count": 成功填充的字段数,
                    "still_missing_count": 仍然缺失的字段数
                }
            }
        ],
        "summary": {
            "tables_with_problems": 有问题的表数量,
            "total_missing_fields": 总缺失字段数,
            "total_filled_fields": 总成功填充字段数（如果进行了对比）,
            "total_still_missing_fields": 总仍然缺失字段数（如果进行了对比）
        }
    }
    """
    problematic_tables = []
    total_missing_fields = 0
    total_filled_fields = 0
    total_still_missing_fields = 0

    # 构建填充后表的映射（如果提供了）
    enriched_map = {}
    if enriched_tables:
        enriched_map = {t.get("table_name", ""): t for t in enriched_tables if t.get("table_name")}

    for table_obj in tables:
        health_info = check_table_health(table_obj)

        # 如果提供了填充后的表，进行对比
        if enriched_map:
            table_name = (table_obj.get("table_name") or "").strip()
            enriched_table = enriched_map.get(table_name)
            if enriched_table:
                fill_result = compare_table_before_after(table_obj, enriched_table)
                health_info["fill_result"] = fill_result
                total_filled_fields += fill_result["filled_count"]
                total_still_missing_fields += fill_result["still_missing_count"]

        # 如果表描述缺失或存在字段注释缺失，则记录为有问题的表
        if not health_info["has_table_description"] or health_info["missing_count"] > 0:
            problematic_tables.append(health_info)
            total_missing_fields += health_info["missing_count"]

    summary = {
        "tables_with_problems": len(problematic_tables),
        "total_missing_fields": total_missing_fields
    }

    # 如果进行了填充对比，添加填充统计
    if enriched_map:
        summary["total_filled_fields"] = total_filled_fields
        summary["total_still_missing_fields"] = total_still_missing_fields

    result = {
        "check_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": user_id or "",
        "connect_info": connect_info or "",
        "total_tables": len(tables),
        "problematic_tables": problematic_tables,
        "summary": summary
    }

    # 记录到日志
    logger = logging.getLogger(__name__)
    logger.info(f"[TABLE_HEALTH_CHECK] 表健康检查完成: 总表数={len(tables)}, "
                f"有问题的表数={len(problematic_tables)}, 总缺失字段数={total_missing_fields}")

    if enriched_map:
        logger.info(f"[TABLE_HEALTH_CHECK] 填充结果: 成功填充字段数={total_filled_fields}, "
                   f"仍然缺失字段数={total_still_missing_fields}")

    if problematic_tables:
        logger.warning(f"[TABLE_HEALTH_CHECK] 发现 {len(problematic_tables)} 张表存在问题:")
        for table_info in problematic_tables:
            table_name = table_info['table_name']
            logger.warning(f"[TABLE_HEALTH_CHECK] 表名: {table_name}, "
                          f"表描述缺失: {not table_info['has_table_description']}, "
                          f"缺失字段注释数: {table_info['missing_count']}/{table_info['total_fields']}")

            if table_info['missing_comment_fields']:
                missing_field_names = [f["name"] for f in table_info['missing_comment_fields']]
                logger.warning(f"[TABLE_HEALTH_CHECK] 缺失注释的字段: {', '.join(missing_field_names)}")

            # 如果有填充结果，记录填充信息
            if "fill_result" in table_info:
                fill_result = table_info["fill_result"]
                if fill_result["filled_count"] > 0:
                    filled_field_names = [f["name"] for f in fill_result["filled_fields"]]
                    logger.info(f"[TABLE_HEALTH_CHECK] 表 {table_name} 成功填充 {fill_result['filled_count']} 个字段: "
                               f"{', '.join(filled_field_names)}")
                if fill_result["still_missing_count"] > 0:
                    still_missing_names = [f["name"] for f in fill_result["still_missing_fields"]]
                    logger.warning(f"[TABLE_HEALTH_CHECK] 表 {table_name} 仍有 {fill_result['still_missing_count']} 个字段缺失注释: "
                                  f"{', '.join(still_missing_names)}")
                if fill_result["table_description_filled"]:
                    logger.info(f"[TABLE_HEALTH_CHECK] 表 {table_name} 的表描述已成功填充")

    return result

def enrich_table_before_insert(
    table_obj: dict,
    sampling_data: dict = None,
    sensitive_fields: list = None
) -> Tuple[dict, bool]:
    """
    入库前的单表富化：
    - 仅当 description 或任一 columns[].comment 为空时调用 LLM
    - 合并返回的补丁，只填空，不覆盖
    - 支持传入采样数据和敏感字段信息以增强注释质量

    Args:
        table_obj: 表对象
        sampling_data: 采样数据（可选），格式为 {字段名: [值列表]}
        sensitive_fields: 敏感字段列表（可选），格式为 [{name: str, reason: str}]

    Returns:
        (new_table_obj, changed)
    """
    need_table_desc = _is_blank(table_obj.get("description"))
    need_any_col = any(_is_blank(c.get("comment")) for c in (table_obj.get("columns") or []));
    if not (need_table_desc or need_any_col):
        return table_obj, False  # 无需富化

    prompt = _build_prompt_for_table(table_obj, sampling_data, sensitive_fields)

    # llm_call 函数内部会从数据库读取配置，无需在此处查询
    raw = llm_call(prompt=prompt, temperature=0.3, retries=2)  # 低温稳定
    text = _strip_code_fence(raw)

    try:
        patch = json.loads(text)
    except Exception:
        # 解析失败则原样入库（不中断）
        return table_obj, False

    return _merge_patch(table_obj, patch)
