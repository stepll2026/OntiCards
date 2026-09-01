"""
 @File: relationship_inference.py
 @Description: 关系推断引擎 - 基于字段映射结果推断表间关系
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-01-28
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple
import re


def infer_relationships(
    field_mappings: Dict[str, Dict[str, Any]],
    target_tables: List[str],
    ref_tables: List[str],
    confidence_threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """
    基于字段映射结果推断表间关系

    Args:
        field_mappings: 字段映射结果 {table_name: {column_name: mapping_info}}
        target_tables: 目标表列表
        ref_tables: 参考表列表
        confidence_threshold: 置信度阈值，低于此值的关系不返回

    Returns:
        关系列表，每个关系包含：
        {
            "from_table": "table1",
            "from_column": "user_id",
            "to_table": "table2",
            "to_column": "id",
            "relationship_type": "foreign_key",  # foreign_key, semantic, name_based
            "confidence": 0.85,
            "reasoning": "字段名匹配且语义相似"
        }
    """
    relationships = []

    print(f"[关系推断] 开始分析，目标表: {target_tables}, 参考表: {ref_tables}")
    print(f"[关系推断] 字段映射包含 {len(field_mappings)} 个表")

    # 遍历所有目标表的字段映射
    for target_table, columns in field_mappings.items():
        if target_table not in target_tables:
            continue

        print(f"[关系推断] 分析目标表 {target_table}，包含 {len(columns)} 个字段")

        for column_name, mapping_info in columns.items():
            # 获取最佳候选
            candidates = mapping_info.get("candidates", [])
            if not candidates:
                print(f"[关系推断]   - {target_table}.{column_name}: 无候选，跳过")
                continue

            best_candidate = candidates[0]
            confidence = best_candidate.get("confidence", 0.0)

            if confidence < confidence_threshold:
                # 对于可能的外键字段，即使置信度低也要尝试推断
                # 检查字段名是否符合外键命名规则
                if _looks_like_foreign_key(column_name):
                    print(f"[关系推断]   ~ {target_table}.{column_name}: 置信度 {confidence:.2f} < {confidence_threshold}，但字段名像外键，继续分析")
                else:
                    print(f"[关系推断]   - {target_table}.{column_name}: 置信度 {confidence:.2f} < {confidence_threshold}，跳过")
                    continue

            # 解析来源
            source = best_candidate.get("source", "")
            source_table, source_column = _parse_source(source)

            if not source_table or not source_column:
                print(f"[关系推断]   - {target_table}.{column_name}: 来源解析失败 (source={source})，跳过")
                continue

            # 判断关系类型
            rel_type, rel_confidence, reasoning = _determine_relationship_type(
                target_table, column_name,
                source_table, source_column,
                mapping_info, best_candidate
            )

            # 只保留高置信度的关系
            if rel_confidence >= confidence_threshold:
                print(f"[关系推断]   ✓ {target_table}.{column_name} -> {source_table}.{source_column} (置信度: {rel_confidence:.2f}, 类型: {rel_type})")
                relationships.append({
                    "from_table": target_table,
                    "from_column": column_name,
                    "to_table": source_table,
                    "to_column": source_column,
                    "relationship_type": rel_type,
                    "confidence": rel_confidence,
                    "reasoning": reasoning
                })
            else:
                print(f"[关系推断]   - {target_table}.{column_name} -> {source_table}.{source_column}: 关系置信度 {rel_confidence:.2f} < {confidence_threshold}，跳过")

    # 去重和合并
    relationships = _deduplicate_relationships(relationships)

    print(f"[关系推断] 完成，发现 {len(relationships)} 个关系")

    return relationships


def _parse_source(source: str) -> Tuple[str, str]:
    """
    解析来源字符串，提取表名和字段名

    Args:
        source: 来源字符串，格式如 "table.column" 或 "dict:column"

    Returns:
        (table_name, column_name) 元组
    """
    if not source:
        return "", ""

    # 处理字典来源
    if source.startswith("dict:"):
        return "", source[5:]

    # 处理表.字段格式
    parts = source.split(".")
    if len(parts) == 2:
        return parts[0], parts[1]

    return "", ""


def _looks_like_foreign_key(column_name: str) -> bool:
    """
    判断字段名是否像外键

    常见外键命名模式：
    - *_id (如 user_id, order_id)
    - *_code (如 user_code, product_code)
    - *_key (如 user_key)
    - *_no (如 order_no)
    """
    if not column_name:
        return False

    lower_name = column_name.lower()

    # 检查常见外键后缀
    fk_suffixes = ["_id", "_code", "_key", "_no", "_num"]
    for suffix in fk_suffixes:
        if lower_name.endswith(suffix):
            return True

    # 检查是否就叫 id
    if lower_name == "id":
        return False  # 主键不算外键

    return False


def _determine_relationship_type(
    from_table: str, from_column: str,
    to_table: str, to_column: str,
    mapping_info: Dict[str, Any],
    candidate: Dict[str, Any]
) -> Tuple[str, float, str]:
    """
    判断关系类型和置信度

    Returns:
        (relationship_type, confidence, reasoning)
    """
    confidence = candidate.get("confidence", 0.0)
    reasoning_parts = []

    # 1. 检查是否为外键关系（基于命名规则）
    is_fk, fk_confidence = _check_foreign_key_pattern(from_column, to_column, to_table)

    if is_fk:
        reasoning_parts.append(f"字段名符合外键命名规则")
        # 对于外键模式，使用更高的置信度（取原始置信度和外键置信度的最大值）
        final_confidence = max(confidence, fk_confidence)
        return "foreign_key", final_confidence, "；".join(reasoning_parts)

    # 2. 检查是否为语义关系
    profile = mapping_info.get("profile", {})
    type_hint = profile.get("type_hint", "")

    if type_hint in ["id", "code", "key"]:
        reasoning_parts.append(f"字段类型为{type_hint}，可能为关联字段")
        # 对于ID类型字段，提升置信度
        boosted_confidence = min(0.8, confidence + 0.2)
        return "semantic", boosted_confidence, "；".join(reasoning_parts)

    # 3. 基于名称的弱关系
    if _check_name_similarity(from_column, to_column):
        reasoning_parts.append("字段名相似")
        # 名称相似也提升置信度
        boosted_confidence = min(0.7, confidence + 0.15)
        return "name_based", boosted_confidence, "；".join(reasoning_parts)

    # 4. 默认为语义关系
    return "semantic", confidence, candidate.get("reasoning", "语义相似")


def _check_foreign_key_pattern(from_column: str, to_column: str, to_table: str) -> Tuple[bool, float]:
    """
    检查是否符合外键命名规则

    常见模式：
    - user_id -> users.id
    - order_id -> orders.id
    - customer_code -> customers.code

    Returns:
        (is_foreign_key, confidence)
    """
    from_lower = from_column.lower()
    to_lower = to_column.lower()
    table_lower = to_table.lower()

    # 模式1: {table_name}_id -> {table_name}s.id
    if from_lower.endswith("_id") and to_lower == "id":
        prefix = from_lower[:-3]  # 去掉 _id
        # 检查表名是否匹配（考虑单复数）
        if prefix == table_lower or prefix + "s" == table_lower or prefix == table_lower.rstrip("s"):
            return True, 0.95

    # 模式2: {table_name}_code -> {table_name}.code
    if from_lower.endswith("_code") and to_lower == "code":
        prefix = from_lower[:-5]  # 去掉 _code
        if prefix == table_lower or prefix + "s" == table_lower or prefix == table_lower.rstrip("s"):
            return True, 0.90

    # 模式3: {table_name}_key -> {table_name}.key
    if from_lower.endswith("_key") and to_lower in ["key", "id"]:
        prefix = from_lower[:-4]  # 去掉 _key
        if prefix == table_lower or prefix + "s" == table_lower or prefix == table_lower.rstrip("s"):
            return True, 0.90

    return False, 0.0


def _check_name_similarity(name1: str, name2: str) -> bool:
    """
    检查两个字段名是否相似
    """
    name1_lower = name1.lower()
    name2_lower = name2.lower()

    # 完全相同
    if name1_lower == name2_lower:
        return True

    # 包含关系
    if name1_lower in name2_lower or name2_lower in name1_lower:
        return True

    # 去掉常见前缀/后缀后相同
    for suffix in ["_id", "_code", "_key", "_no", "_num"]:
        n1 = name1_lower.rstrip(suffix)
        n2 = name2_lower.rstrip(suffix)
        if n1 == n2:
            return True

    return False


def _deduplicate_relationships(relationships: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    去重和合并关系

    如果同一对表字段有多个关系，保留置信度最高的
    """
    seen = {}

    for rel in relationships:
        key = (rel["from_table"], rel["from_column"], rel["to_table"], rel["to_column"])

        if key not in seen or rel["confidence"] > seen[key]["confidence"]:
            seen[key] = rel

    return list(seen.values())


def group_relationships_by_table_pair(
    relationships: List[Dict[str, Any]]
) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    """
    按表对分组关系

    Returns:
        {(table1, table2): [relationship1, relationship2, ...]}
    """
    grouped = {}

    for rel in relationships:
        from_table = rel["from_table"]
        to_table = rel["to_table"]

        # 统一排序，确保 (A, B) 和 (B, A) 被视为同一对
        key = tuple(sorted([from_table, to_table]))

        if key not in grouped:
            grouped[key] = []

        grouped[key].append(rel)

    return grouped
