"""
 @File: table_relationship_inference.py
 @Description: 表关系推断模块 - 使用LLM进行语义分析推断表与表之间的关联关系
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-02-02
 @Update: 2026-02-05 - 重构：使用LLM进行语义分析，综合字段名、注释、类型等信息推断关系
 @Update: 2026-02-09 - 优化：添加向量检索预筛选、字段画像增强、语义同义词、批量分析
 @Update: 2026-05-08 - 优化：添加并发日志支持，增强进度追踪
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple, Optional, Set
import re
import json
import os
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from controllers.agents.qwen.llm_utils import llm_call

# 提示词配置管理器
from models.prompt_config import prompt_manager

# 提示词文件名称映射
_PROMPT_FILE_NAMES = {
    "basic": "table_relationship_analysis_prompt.txt",
    "enhanced": "table_relationship_analysis_enhanced_prompt.txt",
}

# ==================== 语义同义词映射（从recall.py迁移并增强）====================
_SEMANTIC_SYNONYMS = {
    # 人名相关
    "receiver": ["name", "real_name", "user_name", "nick_name", "consignee", "recipient", "contact"],
    "consignee": ["name", "real_name", "receiver", "recipient", "contact"],
    "recipient": ["name", "real_name", "receiver", "consignee", "contact"],
    "contact": ["name", "real_name", "receiver", "consignee", "recipient"],
    "name": ["real_name", "user_name", "nick_name", "receiver", "consignee"],
    "real_name": ["name", "user_name", "nick_name", "receiver", "consignee"],
    "user_name": ["name", "real_name", "nick_name", "login_name"],
    "nick_name": ["name", "real_name", "user_name", "alias"],

    # 手机/电话相关
    "phone": ["mobile", "tel", "telephone", "cellphone", "contact_phone"],
    "mobile": ["phone", "tel", "telephone", "cellphone", "contact_phone"],
    "tel": ["phone", "mobile", "telephone", "cellphone"],
    "telephone": ["phone", "mobile", "tel", "cellphone"],

    # 地址相关
    "address": ["addr", "location", "detail_address", "full_address"],
    "addr": ["address", "location", "detail_address"],

    # ID相关
    "user_id": ["uid", "member_id", "customer_id", "buyer_id"],
    "member_id": ["user_id", "uid", "customer_id"],
    "customer_id": ["user_id", "uid", "member_id", "buyer_id"],
    "buyer_id": ["user_id", "uid", "customer_id", "purchaser_id"],

    # 订单相关
    "order_id": ["order_no", "order_number", "order_code"],
    "order_no": ["order_id", "order_number", "order_code"],

    # 商品相关
    "product_id": ["goods_id", "item_id", "sku_id", "commodity_id"],
    "goods_id": ["product_id", "item_id", "sku_id"],
    "item_id": ["product_id", "goods_id", "sku_id"],

    # 金额相关
    "amount": ["amt", "money", "sum", "total"],
    "price": ["unit_price", "sale_price", "cost"],

    # 时间相关
    "create_time": ["created_at", "gmt_create", "add_time", "insert_time"],
    "update_time": ["updated_at", "gmt_modified", "modify_time", "edit_time"],
    "created_at": ["create_time", "gmt_create", "add_time"],
    "updated_at": ["update_time", "gmt_modified", "modify_time"],
}

# 表名语义分类（用于预筛选）
_TABLE_SEMANTIC_CATEGORIES = {
    "user": ["user", "member", "customer", "buyer", "seller", "account", "person", "staff", "employee"],
    "order": ["order", "purchase", "sale", "transaction", "deal"],
    "product": ["product", "goods", "item", "sku", "commodity", "article"],
    "payment": ["payment", "pay", "transaction", "billing", "invoice"],
    "address": ["address", "addr", "location", "region", "area"],
    "category": ["category", "cat", "class", "type", "group"],
    "store": ["store", "shop", "warehouse", "inventory", "stock"],
    "logistics": ["logistics", "delivery", "shipping", "express", "transport"],
    "coupon": ["coupon", "voucher", "discount", "promotion"],
    "comment": ["comment", "review", "feedback", "rating"],
}

# 分析结果缓存（schema_hash -> {table_pair_key: relationships}）
_RELATIONSHIP_CACHE: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}


def _load_prompt_template(enhanced: bool = False) -> str:
    """
    从数据库加载提示词模板（优先），fallback到文件

    Args:
        enhanced: 是否加载增强版提示词（包含字段画像信息）

    Returns:
        提示词内容字符串，如果都不存在返回 None
    """
    prompt_key = "enhanced" if enhanced else "basic"
    file_name = _PROMPT_FILE_NAMES[prompt_key]

    # 1. 优先从数据库/缓存读取
    content = prompt_manager.get_prompt(file_name)
    if content:
        return content

    # 2. Fallback 到文件（并自动同步到数据库）
    from pathlib import Path
    root_dir = Path(__file__).resolve().parents[2]
    file_path = root_dir / "libs" / "prompt" / "global_inventory" / file_name

    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        # 同步到数据库
        prompt_manager.set_prompt(file_name, content)
        return content

    # 如果增强版不存在，回退到基础版
    if enhanced:
        print(f"[表关系推断] 增强提示词文件不存在，回退到基础版")
        return _load_prompt_template(enhanced=False)

    print(f"[表关系推断] 加载提示词文件失败，请检查配置")
    return None


# ==================== 向量检索预筛选相关函数 ====================

def _calculate_table_similarity_score(
    table1: str, fields1: List[Dict[str, Any]],
    table2: str, fields2: List[Dict[str, Any]]
) -> float:
    """
    计算两张表之间的相似度得分（用于预筛选）

    综合考虑：
    1. 表名语义相似度
    2. 字段名重叠度
    3. 关联字段模式匹配
    4. 外键命名模式检测

    Returns:
        相似度得分 0-1，越高越相关
    """
    score = 0.0

    # 1. 表名语义相似度（0-0.3分）
    table_name_score = _calculate_table_name_similarity(table1, table2)
    score += table_name_score * 0.3

    # 2. 字段名重叠度（0-0.3分）
    field_overlap_score = _calculate_field_overlap(fields1, fields2)
    score += field_overlap_score * 0.3

    # 3. 外键命名模式检测（0-0.4分）
    fk_pattern_score = _detect_fk_pattern_between_tables(table1, fields1, table2, fields2)
    score += fk_pattern_score * 0.4

    return min(1.0, score)


def _calculate_table_name_similarity(table1: str, table2: str) -> float:
    """
    计算两个表名之间的语义相似度
    """
    core1 = _extract_table_core(table1).lower()
    core2 = _extract_table_core(table2).lower()

    # 完全相同
    if core1 == core2:
        return 1.0

    # 包含关系
    if core1 in core2 or core2 in core1:
        return 0.6

    # 检查是否属于同一语义类别或有关联的类别
    cat1 = _get_table_category(core1)
    cat2 = _get_table_category(core2)

    # 相关类别对（这些类别的表之间通常有关联）
    related_pairs = {
        ("user", "order"), ("user", "address"), ("user", "payment"),
        ("order", "product"), ("order", "payment"), ("order", "logistics"),
        ("product", "category"), ("product", "store"), ("product", "comment"),
        ("store", "logistics"), ("coupon", "order"), ("coupon", "user"),
    }

    if cat1 and cat2:
        if cat1 == cat2:
            return 0.4  # 同类别
        pair = tuple(sorted([cat1, cat2]))
        if pair in related_pairs:
            return 0.5  # 相关类别

    # 分词后的交集
    words1 = set(core1.split("_"))
    words2 = set(core2.split("_"))

    if words1 & words2:
        return 0.3

    return 0.0


def _get_table_category(table_core: str) -> Optional[str]:
    """
    获取表名所属的语义类别
    """
    for category, keywords in _TABLE_SEMANTIC_CATEGORIES.items():
        for kw in keywords:
            if kw in table_core or table_core in kw:
                return category
    return None


def _calculate_field_overlap(fields1: List[Dict[str, Any]], fields2: List[Dict[str, Any]]) -> float:
    """
    计算两张表的字段名重叠度

    综合考虑多种关联模式：
    1. 外键模式：xxx_id 指向 xxx 表的 id
    2. 共享字段模式：两张表有相同或相似的业务字段（如 receiver_name, phone）
    3. 同义词模式：字段名语义相同但用词不同
    """
    # 提取两张表的所有有效字段名
    names1 = set()
    names2 = set()
    field_info1 = {}  # 保存字段详情用于后续分析
    field_info2 = {}

    for f in fields1:
        name = f.get("column_name", "").lower()
        if name and not _is_ignored_field(name):
            names1.add(_extract_field_core(name))
            field_info1[_extract_field_core(name)] = f

    for f in fields2:
        name = f.get("column_name", "").lower()
        if name and not _is_ignored_field(name):
            names2.add(_extract_field_core(name))
            field_info2[_extract_field_core(name)] = f

    if not names1 or not names2:
        return 0.0

    # 1. 直接交集（字段名完全相同）
    direct_overlap = len(names1 & names2)

    # 2. 外键模式交集
    fk_overlap = 0
    for n1 in names1:
        if n1.endswith("_id") and len(n1) > 3:
            entity = n1[:-3]
            # 检查 ref 表是否有匹配的 id 字段
            if entity in names2 or "id" in names2:
                fk_overlap += 1

    # 3. 同义词交集
    synonym_overlap = 0
    for n1 in names1:
        synonyms = _get_field_synonyms(n1)
        if names2 & synonyms:
            synonym_overlap += 1

    # 4. 共享业务字段交集（如 receiver_name, phone, address 等）
    shared_field_overlap = 0
    shared_keywords = _get_shared_field_keywords()
    for n1 in names1:
        for n2 in names2:
            # 检查是否有共同的业务关键词
            if _fields_have_shared_business_meaning(n1, n2, shared_keywords):
                shared_field_overlap += 1

    # 综合得分：不同类型的重叠给予不同权重
    # 直接匹配权重最高，同义词次之，共享字段再次，外键模式最后
    total_overlap = (
        direct_overlap * 1.0 +
        fk_overlap * 0.8 +
        synonym_overlap * 0.6 +
        shared_field_overlap * 0.4
    )

    union = len(names1 | names2)
    return min(1.0, total_overlap / union) if union > 0 else 0.0


def _is_ignored_field(name: str) -> bool:
    """
    判断字段是否应该被忽略（不是有效的关联字段）
    """
    ignored_patterns = [
        "created_at", "updated_at", "create_time", "update_time",
        "gmt_create", "gmt_modified", "deleted_at", "delete_time",
        "is_deleted", "is_active", "is_enabled", "status",
        "version", "sort", "order", "priority", "weight",
        "latitude", "longitude", "lng", "lat",  # 地理坐标
        "remark", "memo", "note", "description",  # 备注描述
        "extra", "meta", "data", "payload",  # 通用字段
        "_url$", "_path$", "_file$",  # 文件路径
        "_salt$", "_hash$",  # 安全相关
    ]
    name_lower = name.lower()
    for pattern in ignored_patterns:
        import re
        if pattern.startswith("_") and pattern.endswith("$"):
            if re.search(pattern, name_lower):
                return True
        elif pattern in name_lower:
            return True
    return False


def _get_shared_field_keywords() -> Dict[str, List[str]]:
    """
    获取共享业务字段的关键词分组

    同一组的字段表示相同或相似的业务含义，可能存在于不同表中
    """
    return {
        # 联系人信息
        "contact": ["name", "receiver_name", "contact_name", "linkman", "consignee", "recipient", "contact"],
        "phone": ["phone", "mobile", "tel", "telephone", "cellphone", "contact_phone", "receiver_phone", "link_phone"],
        "email": ["email", "mail", "receiver_email", "contact_email"],
        # 地址信息
        "address": ["address", "detail_address", "full_address", "receiver_address", "shipping_address", "delivery_address", "addr"],
        # 用户标识
        "user_id": ["user_id", "uid", "member_id", "customer_id", "buyer_id", "member"],
        "user_name": ["user_name", "username", "nickname", "display_name", "real_name"],
        # 订单相关
        "order_id": ["order_id", "order_no", "order_number", "order_code", "trade_no"],
        # 商品相关
        "product_id": ["product_id", "goods_id", "item_id", "sku_id", "commodity_id", "product"],
        "product_name": ["product_name", "goods_name", "item_name", "commodity_name", "title", "product_title"],
        # 金额相关
        "price": ["price", "amount", "total", "subtotal", "discount", "fee", "cost"],
        # 状态
        "status": ["status", "state", "order_status", "payment_status", "shipping_status", "delivery_status"],
    }


def _fields_have_shared_business_meaning(name1: str, name2: str, shared_keywords: Dict[str, List[str]]) -> bool:
    """
    判断两个字段是否具有共享的业务含义

    例如：receiver_name 和 contact_name 都表示联系人姓名
    """
    # 移除常见后缀
    clean1 = _remove_common_suffix(name1)
    clean2 = _remove_common_suffix(name2)

    # 直接相等
    if clean1 == clean2:
        return True

    # 在同一关键词组中
    for group_name, keywords in shared_keywords.items():
        if clean1 in keywords and clean2 in keywords:
            return True

    # 检查是否有共同的前缀（去掉 _id, _name 等后缀）
    prefix1 = clean1.split("_")[0] if "_" in clean1 else clean1
    prefix2 = clean2.split("_")[0] if "_" in clean2 else clean2

    if prefix1 == prefix2 and len(prefix1) > 2:
        return True

    return False


def _remove_common_suffix(name: str) -> str:
    """
    移除字段名的常见后缀，提取核心语义
    """
    suffixes = ["_id", "_code", "_no", "_name", "_type", "_status"]
    for suffix in suffixes:
        if name.endswith(suffix):
            return name[:-len(suffix)]
    return name


def _get_field_synonyms(name: str) -> Set[str]:
    """
    获取字段名的语义同义词集合
    """
    synonyms = {name}

    # 基础同义词映射
    base_synonyms = {
        "name": {"name", "real_name", "username", "nickname", "display_name", "title", "realname"},
        "phone": {"phone", "mobile", "tel", "telephone", "cellphone", "contact", "telno", "mobileno"},
        "email": {"email", "mail", "e_mail", "electronic_mail"},
        "address": {"address", "addr", "location", "detail_address", "full_address"},
        "user_id": {"user_id", "uid", "member_id", "customer_id", "buyer_id", "member", "userid"},
        "order_id": {"order_id", "order_no", "order_number", "trade_no", "orderid", "tradeno"},
        "product_id": {"product_id", "goods_id", "item_id", "sku_id", "commodity_id", "productid", "goodsid"},
        "status": {"status", "state", "stat", "order_status", "state_code"},
        "created_at": {"created_at", "create_time", "gmt_create", "add_time", "insert_time"},
        "updated_at": {"updated_at", "update_time", "gmt_modified", "modify_time"},
    }

    for key, syns in base_synonyms.items():
        if name in syns:
            synonyms.update(syns)

    return synonyms


def _detect_fk_pattern_between_tables(
    table1: str, fields1: List[Dict[str, Any]],
    table2: str, fields2: List[Dict[str, Any]]
) -> float:
    """
    检测两张表之间是否存在外键命名模式

    综合检测多种关联模式：
    1. 经典外键模式：orders.product_id -> products.id
    2. 共享字段模式：addresses.receiver_name -> logistics.receiver_name
    3. 同义词字段模式：orders.phone -> users.mobile
    """
    core1 = _extract_table_core(table1).lower()
    core2 = _extract_table_core(table2).lower()

    # 提取两张表的所有有效字段
    fields1_names = {f.get("column_name", "").lower() for f in fields1}
    fields2_names = {f.get("column_name", "").lower() for f in fields2}
    all_fields1 = [f.get("column_name", "").lower() for f in fields1 if f.get("column_name")]
    all_fields2 = [f.get("column_name", "").lower() for f in fields2 if f.get("column_name")]

    score = 0.0
    matched_patterns = []

    # ==================== 模式1: 经典外键模式 xxx_id -> table.id ====================
    # 检查 table1 中是否有指向 table2 的外键
    for field in all_fields1:
        if field.endswith("_id") and len(field) > 3:
            field_core = field[:-3]  # 去掉 _id
            # 展开缩写
            expanded = _get_abbreviation_expansion(field_core)
            # 检查是否与 table2 匹配
            if (expanded in core2 or core2 in expanded or
                core2.startswith(expanded) or core2.endswith(expanded) or
                field_core in core2 or core2 in field_core):
                score = max(score, 0.9)
                matched_patterns.append(f"fk: {field}->{table2}.id")

    # 检查 table2 中是否有指向 table1 的外键
    for field in all_fields2:
        if field.endswith("_id") and len(field) > 3:
            field_core = field[:-3]
            expanded = _get_abbreviation_expansion(field_core)
            if (expanded in core1 or core1 in expanded or
                core1.startswith(expanded) or core1.endswith(expanded) or
                field_core in core1 or core1 in field_core):
                score = max(score, 0.9)
                matched_patterns.append(f"fk: {field}->{table1}.id")

    # ==================== 模式2: 主键匹配（两表都有 id） ====================
    has_id_in_table1 = "id" in fields1_names
    has_id_in_table2 = "id" in fields2_names
    if has_id_in_table1 and has_id_in_table2:
        # 检查是否有其他外键指向这两个 id
        for field in all_fields1:
            if field.endswith("_id") and field != "id":
                score = max(score, 0.85)
        for field in all_fields2:
            if field.endswith("_id") and field != "id":
                score = max(score, 0.85)

    # ==================== 模式3: 共享字段模式（核心改进） ====================
    # 检测两张表是否有相同或相似的业务字段
    shared_keywords = _get_shared_field_keywords()
    shared_matches = 0
    for f1 in all_fields1:
        if _is_ignored_field(f1):
            continue
        for f2 in all_fields2:
            if _is_ignored_field(f2):
                continue
            # 检查是否是完全相同的字段名
            if f1 == f2:
                shared_matches += 1
                matched_patterns.append(f"shared: {f1}")
            # 检查是否有共享业务含义
            elif _fields_have_shared_business_meaning(f1, f2, shared_keywords):
                shared_matches += 0.5
                matched_patterns.append(f"shared_business: {f1}<->{f2}")
            # 检查字段核心名是否相同
            elif _extract_field_core(f1) == _extract_field_core(f2):
                shared_matches += 0.8
                matched_patterns.append(f"core_match: {f1}<->{f2}")

    if shared_matches > 0:
        # 根据共享字段数量计算得分
        shared_score = min(0.75, shared_matches * 0.15)
        score = max(score, shared_score)

    # ==================== 模式4: 同义词匹配 ====================
    synonym_matches = 0
    for f1 in all_fields1:
        if _is_ignored_field(f1):
            continue
        synonyms = _get_field_synonyms(f1)
        for f2 in all_fields2:
            if _is_ignored_field(f2):
                continue
            if f2 in synonyms:
                synonym_matches += 1
                matched_patterns.append(f"synonym: {f1}<->{f2}")

    if synonym_matches > 0:
        synonym_score = min(0.7, synonym_matches * 0.1)
        score = max(score, synonym_score)

    # ==================== 模式5: 表名包含关系 ====================
    if core1 in core2 or core2 in core1:
        score = max(score, 0.6)

    # 如果有匹配模式，打印日志
    if matched_patterns:
        print(f"[表关系推断]   匹配模式: {', '.join(matched_patterns[:5])}")  # 最多显示5个

    return score


def _get_abbreviation_expansion(abbr: str) -> str:
    """
    获取缩写的展开形式
    """
    abbreviations = {
        "uid": "user",
        "pid": "product",
        "oid": "order",
        "cid": "category",
        "sid": "store",
        "mid": "member",
        "gid": "goods",
        "aid": "address",
        "cust": "customer",
        "prod": "product",
        "cat": "category",
    }
    return abbreviations.get(abbr, abbr)


def _prefilter_table_pairs(
    target_tables_info: Dict[str, List[Dict[str, Any]]],
    ref_tables_info: Dict[str, List[Dict[str, Any]]],
    similarity_threshold: float = 0.2,
    max_pairs: int = 100
) -> List[Tuple[str, str, float]]:
    """
    预筛选表对：只保留可能存在关系的表对

    Args:
        target_tables_info: 目标表信息
        ref_tables_info: 参考表信息
        similarity_threshold: 相似度阈值
        max_pairs: 最大返回表对数

    Returns:
        [(target_table, ref_table, similarity_score), ...]
    """
    print(f"[表关系推断] 预筛选开始，目标表: {len(target_tables_info)}, 参考表: {len(ref_tables_info)}")

    scored_pairs = []

    for target_table, target_fields in target_tables_info.items():
        for ref_table, ref_fields in ref_tables_info.items():
            if target_table == ref_table:
                continue

            score = _calculate_table_similarity_score(
                target_table, target_fields,
                ref_table, ref_fields
            )

            if score >= similarity_threshold:
                scored_pairs.append((target_table, ref_table, score))

    # 按相似度排序
    scored_pairs.sort(key=lambda x: x[2], reverse=True)

    # 限制数量
    result = scored_pairs[:max_pairs]

    print(f"[表关系推断] 预筛选完成，从 {len(target_tables_info) * len(ref_tables_info)} 个表对筛选出 {len(result)} 个候选")

    return result


# ==================== 缓存相关函数 ====================

def _get_cache_key(table1: str, table2: str, threshold_tier: str = "default") -> str:
    """
    生成表对的缓存键（确保双向对称）

    Args:
        threshold_tier: 阈值档位，用于不同阈值档位之间隔离缓存。
            同一档位内可复用缓存；不同档位独立缓存，避免低阈值结果污染高阈值结果。
    """
    return f"{threshold_tier}::{'_'.join(sorted([table1, table2]))}"


def _threshold_to_tier(confidence_threshold: float) -> str:
    """
    将连续阈值映射为离散档位

    不同档位生成不同缓存键，避免互相污染：
    - very_high: 0.85+
    - high: 0.7 ~ 0.85
    - medium: 0.5 ~ 0.7
    - low: <0.5

    档位内的差异（如 0.5 与 0.55）共用缓存，由最终过滤阶段做精细区分。
    """
    try:
        t = float(confidence_threshold)
    except (TypeError, ValueError):
        return "default"

    if t >= 0.85:
        return "very_high"
    if t >= 0.7:
        return "high"
    if t >= 0.5:
        return "medium"
    return "low"


def _get_from_cache(schema_hash: str, table1: str, table2: str, threshold_tier: str = "default") -> Optional[List[Dict[str, Any]]]:
    """
    从缓存获取分析结果
    """
    if schema_hash not in _RELATIONSHIP_CACHE:
        return None

    cache_key = _get_cache_key(table1, table2, threshold_tier)
    return _RELATIONSHIP_CACHE[schema_hash].get(cache_key)


def _save_to_cache(schema_hash: str, table1: str, table2: str, relationships: List[Dict[str, Any]], threshold_tier: str = "default"):
    """
    保存分析结果到缓存
    """
    if schema_hash not in _RELATIONSHIP_CACHE:
        _RELATIONSHIP_CACHE[schema_hash] = {}

    cache_key = _get_cache_key(table1, table2, threshold_tier)
    _RELATIONSHIP_CACHE[schema_hash][cache_key] = relationships


def clear_relationship_cache(schema_hash: str = None):
    """
    清除关系缓存

    Args:
        schema_hash: 如果指定，只清除该schema的缓存；否则清除所有
    """
    global _RELATIONSHIP_CACHE
    if schema_hash:
        if schema_hash in _RELATIONSHIP_CACHE:
            del _RELATIONSHIP_CACHE[schema_hash]
    else:
        _RELATIONSHIP_CACHE = {}


# ==================== 主函数（增强版）====================

def infer_table_relationships(
    target_tables_info: Dict[str, List[Dict[str, Any]]],
    ref_tables_info: Dict[str, List[Dict[str, Any]]],
    confidence_threshold: float = 0.5,
    field_profiles: Dict[str, Dict[str, Any]] = None,
    schema_hash: str = None,
    use_prefilter: bool = True,
    similarity_threshold: float = 0.2,
    max_pairs: int = 100,
    use_cache: bool = True,
    parallel: bool = False,
    max_workers: int = 4
) -> List[Dict[str, Any]]:
    """
    推断表与表之间的关联关系（增强版：支持向量预筛选、字段画像、缓存）

    Args:
        target_tables_info: 目标表信息 {table_name: [field_info, ...]}
        ref_tables_info: 参考表信息 {table_name: [field_info, ...]}
        confidence_threshold: 置信度阈值
        field_profiles: 字段画像信息 {table_name.column_name: profile_dict}
        schema_hash: Schema哈希值（用于缓存）
        use_prefilter: 是否使用预筛选
        similarity_threshold: 预筛选相似度阈值
        max_pairs: 预筛选最大表对数
        use_cache: 是否使用缓存
        parallel: 是否并行分析
        max_workers: 并行工作线程数

    Returns:
        关系列表
    """
    # 获取 Flask app 用于在线程中创建应用上下文
    from flask import current_app
    app = None
    try:
        app = current_app._get_current_object()
    except RuntimeError:
        print(f"[表关系推断] ⚠️ 无法获取 Flask app，上下文可能不可用")

    print(f"[表关系推断] ═══════════════════════════════════════════════════════")
    print(f"[表关系推断] 📊 开始分析")
    print(f"[表关系推断]    • 目标表: {list(target_tables_info.keys())}")
    print(f"[表关系推断]    • 参考表: {list(ref_tables_info.keys())}")
    print(f"[表关系推断]    • 预筛选: {'启用' if use_prefilter else '禁用'}")
    print(f"[表关系推断]    • 并发优化: {'启用' if parallel else '禁用'} (max_workers={max_workers})")
    print(f"[表关系推断]    • 置信度阈值: {confidence_threshold} (档位: {_threshold_to_tier(confidence_threshold)})")
    print(f"[表关系推断] ═══════════════════════════════════════════════════════")

    relationships = []

    # 计算当前阈值对应的缓存档位（不同档位缓存隔离）
    threshold_tier = _threshold_to_tier(confidence_threshold)

    # 确定要分析的表对
    if use_prefilter and len(target_tables_info) * len(ref_tables_info) > 30:
        # 表对数量较多时使用预筛选（只在超过30对时启用，避免过度过滤）
        candidate_pairs = _prefilter_table_pairs(
            target_tables_info, ref_tables_info,
            similarity_threshold=similarity_threshold,
            max_pairs=max_pairs
        )
    else:
        # 表对数量较少时遍历所有
        candidate_pairs = []
        for target_table in target_tables_info:
            for ref_table in ref_tables_info:
                if target_table != ref_table:
                    candidate_pairs.append((target_table, ref_table, 1.0))

    # 分析表对
    def analyze_pair(pair_info):
        """在应用上下文中分析表对"""
        target_table, ref_table, prefilter_score = pair_info
        target_fields = target_tables_info[target_table]
        ref_fields = ref_tables_info[ref_table]

        # 检查缓存（按阈值档位隔离）
        if use_cache and schema_hash:
            cached = _get_from_cache(schema_hash, target_table, ref_table, threshold_tier)
            if cached is not None:
                print(f"[表关系推断] 命中缓存[{threshold_tier}]: {target_table} <-> {ref_table}")
                # 缓存保存的是当前档位下的结果，调用方按精确阈值再做最终过滤
                return cached

        print(f"[表关系推断] 分析表对: {target_table} <-> {ref_table} (预筛选得分: {prefilter_score:.2f}, 阈值档位: {threshold_tier})")

        # 使用 Flask 应用上下文执行 LLM 分析
        def _do_analyze():
            # ✅ 关键改动：把真实阈值传给 LLM，让 Prompt 按档位调整打分严格度
            # 这里采用"档位阈值"作为 Prompt 中的参考：同一档位内的 LLM 输出一致，
            # 由外层调用方按精确阈值再做最终过滤，行为完全向后兼容。
            tier_floor = {
                "very_high": 0.85,
                "high": 0.7,
                "medium": 0.5,
                "low": max(0.3, float(confidence_threshold)),  # low 档用真实阈值（最低 0.3）
            }.get(threshold_tier, confidence_threshold)

            table_relationships = _analyze_table_pair_with_llm(
                target_table, target_fields,
                ref_table, ref_fields,
                confidence_threshold=tier_floor,
                field_profiles=field_profiles
            )

            # 保存缓存（保存当前档位下的结果）
            if use_cache and schema_hash:
                _save_to_cache(
                    schema_hash, target_table, ref_table,
                    table_relationships, threshold_tier
                )

            return table_relationships

        # 根据是否有 app 上下文决定执行方式
        if app:
            with app.app_context():
                table_relationships = _do_analyze()
        else:
            table_relationships = _do_analyze()

        return table_relationships

    # 执行分析
    # 启用并行的条件：parallel=True 且 max_workers > 1 且表对数量 > 1
    # 注意：即使只有1对表，如果 max_workers > 1，也应该使用并行来确保线程安全
    import time
    start_time = time.time()
    completed_count = [0]
    pair_lock = threading.Lock()

    use_parallel = parallel and max_workers > 1 and len(candidate_pairs) > 1
    if use_parallel:
        # 并行分析
        print(f"[表关系推断] 🚀 启动 {max_workers} 个并发线程分析 {len(candidate_pairs)} 个表对...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(analyze_pair, pair): pair for pair in candidate_pairs}
            for future in as_completed(futures):
                try:
                    pair_rels = future.result()
                    pair = futures[future]
                    with pair_lock:
                        completed_count[0] += 1
                        elapsed = time.time() - start_time
                        rate = completed_count[0] / elapsed if elapsed > 0 else 0
                        progress = completed_count[0] / len(candidate_pairs) * 100

                        # 每完成2对或最后一对时打印
                        if completed_count[0] % 2 == 0 or completed_count[0] == len(candidate_pairs):
                            print(f"[表关系推断]   📊 进度: {completed_count[0]}/{len(candidate_pairs)} ({progress:.0f}%, {rate:.1f} 对/秒)")

                    if pair_rels:
                        # 统一过滤：只保留置信度 >= threshold 的关系
                        raw_count = len(pair_rels)
                        filtered_rels = [r for r in pair_rels if r.get("confidence", 0) >= confidence_threshold]
                        filtered_count = len(filtered_rels)
                        print(f"[表关系推断]   ✓ {pair[0]} <-> {pair[1]}: {raw_count} -> {filtered_count} 个关系")
                        relationships.extend(filtered_rels)
                except Exception as e:
                    pair = futures[future]
                    print(f"[表关系推断]   ✗ {pair[0]} <-> {pair[1]}: 分析失败 - {e}")
    else:
        # 串行分析（也支持 parallel=True 但表对数量少的情况，通过单线程执行）
        mode_str = "并行模式" if (parallel and max_workers > 1) else "串行模式"
        print(f"[表关系推断] 📝 使用 {mode_str} 分析 {len(candidate_pairs)} 个表对...")
        for pair_info in candidate_pairs:
            try:
                pair_rels = analyze_pair(pair_info)
                if pair_rels:
                    # 统一过滤：只保留置信度 >= threshold 的关系
                    raw_count = len(pair_rels)
                    filtered_rels = [r for r in pair_rels if r.get("confidence", 0) >= confidence_threshold]
                    filtered_count = len(filtered_rels)
                    print(f"[表关系推断]   ✓ {pair_info[0]} <-> {pair_info[1]}: {raw_count} -> {filtered_count} 个关系")
                    relationships.extend(filtered_rels)
                with pair_lock:
                    completed_count[0] += 1
            except Exception as e:
                print(f"[表关系推断]   ✗ {pair_info[0]} <-> {pair_info[1]}: 分析失败 - {e}")

    # 去重和合并（去重时保留更高置信度的关系）
    relationships = _deduplicate_relationships(relationships, confidence_threshold)

    elapsed_time = time.time() - start_time
    print(f"[表关系推断] ✅ 完成，发现 {len(relationships)} 个关系，耗时 {elapsed_time:.2f} 秒")

    return relationships


def _analyze_table_pair_with_llm(
    target_table: str, target_fields: List[Dict[str, Any]],
    ref_table: str, ref_fields: List[Dict[str, Any]],
    confidence_threshold: float,
    field_profiles: Dict[str, Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    使用LLM分析两张表之间的字段关系（增强版：支持字段画像）

    综合考虑：
    1. 字段名称（英文单词语义）
    2. 字段注释（中文语义）
    3. 数据类型兼容性
    4. 表名语义
    5. 字段画像（type_hint, top_values, sample_values）

    Args:
        confidence_threshold: 置信度阈值，会被注入到 Prompt 中以引导 LLM 按
            阈值档位调整打分严格度。同时解析后仍会作为最终过滤阈值使用。
    """
    # 构建字段信息摘要（包含画像信息）
    target_fields_summary = _build_fields_summary(target_table, target_fields, field_profiles)
    ref_fields_summary = _build_fields_summary(ref_table, ref_fields, field_profiles)

    # 判断是否有画像信息
    has_profiles = field_profiles is not None and len(field_profiles) > 0

    # 构建LLM提示词（使用增强版或基础版，注入阈值）
    prompt = _build_relationship_analysis_prompt(
        target_table, target_fields_summary,
        ref_table, ref_fields_summary,
        enhanced=has_profiles,
        confidence_threshold=confidence_threshold
    )

    try:
        # 调用LLM进行分析
        response = llm_call(prompt)

        # 解析LLM响应（传递 field_profiles 用于后处理验证）
        relationships = _parse_llm_relationship_response(
            response, target_table, ref_table, confidence_threshold,
            field_profiles=field_profiles,
            target_fields=target_fields,
            ref_fields=ref_fields
        )

        return relationships

    except Exception as e:
        print(f"[表关系推断] LLM分析失败: {e}，回退到规则匹配")
        # 回退到基础规则匹配（增强版，使用同义词）
        return _fallback_rule_based_analysis(
            target_table, target_fields,
            ref_table, ref_fields,
            confidence_threshold,
            field_profiles=field_profiles
        )


def _build_fields_summary(
    table_name: str,
    fields: List[Dict[str, Any]],
    field_profiles: Dict[str, Dict[str, Any]] = None
) -> List[Dict[str, str]]:
    """
    构建字段信息摘要，用于LLM分析（增强版：包含画像信息）
    """
    summary = []
    for field in fields:
        column_name = field.get("column_name", "")
        field_info = {
            "name": column_name,
            "type": field.get("column_type", ""),
            "comment": field.get("column_comment", "") or field.get("comment", "") or ""
        }

        # 添加画像信息（如果有）
        if field_profiles:
            profile_key = f"{table_name}.{column_name}"
            profile = field_profiles.get(profile_key, {})

            if profile:
                # 添加类型提示
                type_hint = profile.get("type_hint")
                if type_hint:
                    field_info["type_hint"] = type_hint

                # 添加格式提示
                format_hint = profile.get("format_hint")
                if format_hint:
                    field_info["format_hint"] = format_hint

                # 添加唯一值数量（判断是否是标识符）
                distinct_est = profile.get("distinct_est")
                if distinct_est is not None:
                    field_info["distinct_count"] = distinct_est

                # 添加高频值（用于判断枚举值、语义相似性）
                top_values = profile.get("top_values", [])
                if top_values:
                    # 只保留前3个高频值
                    field_info["top_values"] = [v.get("v") for v in top_values[:3] if v.get("v")]

                # 添加样例值（用于判断数据格式）
                sample_values = profile.get("sample_values", [])
                if sample_values:
                    field_info["sample_values"] = sample_values[:3]

                # 添加空值率（判断是否是必填字段）
                null_rate = profile.get("null_rate_est")
                if null_rate is not None and null_rate > 0:
                    field_info["null_rate"] = f"{null_rate}%"

        summary.append(field_info)
    return summary


def _build_relationship_analysis_prompt(
    target_table: str, target_fields: List[Dict[str, str]],
    ref_table: str, ref_fields: List[Dict[str, str]],
    enhanced: bool = False,
    confidence_threshold: float = 0.5
) -> str:
    """
    构建LLM分析提示词（从文件加载模板，支持增强版）

    Args:
        confidence_threshold: 用户传入的置信度阈值，会被注入到 Prompt 中以引导 LLM
            根据阈值档位调整打分严格度。占位符：{confidence_threshold}
    """
    # 尝试从文件加载提示词模板
    template = _load_prompt_template(enhanced=enhanced)

    if template:
        # 使用文件中的模板，替换占位符
        prompt = template.replace("{target_table}", target_table)
        prompt = prompt.replace("{target_fields}", json.dumps(target_fields, ensure_ascii=False, indent=2))
        prompt = prompt.replace("{ref_table}", ref_table)
        prompt = prompt.replace("{ref_fields}", json.dumps(ref_fields, ensure_ascii=False, indent=2))
        # 注入阈值（保留3位小数，避免浮点打印噪声）
        prompt = prompt.replace("{confidence_threshold}", f"{float(confidence_threshold):.3f}")
        return prompt

    # 回退：使用默认提示词（增强版）
    profile_hint = ""
    if enhanced:
        profile_hint = """
注意：字段信息中包含以下画像数据，请充分利用：
- type_hint: 数据类型提示（identifier=标识符, amount=金额, datetime=时间, boolean_flag=布尔标志, enum=枚举）
- format_hint: 格式提示（如uuid, numeric-id, yyyy-mm-dd等）
- distinct_count: 唯一值数量（高基数通常是标识符）
- top_values: 高频值（可判断枚举值或语义）
- sample_values: 样例值（可判断数据格式）

请根据这些画像信息辅助判断字段之间的关联关系：
- 两个字段如果 type_hint 都是 identifier，且字段名有关联，很可能是外键关系
- 如果 top_values 有重叠，可能存在语义关联
- 如果 sample_values 格式相似（如都是UUID），增加关联置信度
"""

    threshold_str = f"{float(confidence_threshold):.3f}"
    return f"""分析以下两张表之间的字段关联关系：

目标表: {target_table}
字段: {json.dumps(target_fields, ensure_ascii=False, indent=2)}

参考表: {ref_table}
字段: {json.dumps(ref_fields, ensure_ascii=False, indent=2)}
{profile_hint}
当前用户设定的置信度阈值为：{threshold_str}
- 低于 {threshold_str} 的关系**不要输出**；
- 请让你的打分反映"是否愿意为此关系担保到 {threshold_str} 以上"；
- 阈值越高，越倾向"宁缺毋滥"；阈值越低，越倾向"广撒网"。

请以JSON数组格式输出关联关系，包含：from_column, to_column, relationship_type, confidence, reasoning, cardinality, business_relation, join_suggestion, fusion_suggestion
"""


def _parse_llm_relationship_response(
    response: str,
    target_table: str,
    ref_table: str,
    confidence_threshold: float,
    field_profiles: Dict[str, Dict[str, Any]] = None,
    target_fields: List[Dict[str, Any]] = None,
    ref_fields: List[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    解析LLM返回的关系分析结果

    验证规则：
    1. 关系类型验证：根据类型判断是否合理
    2. 命名语义验证：字段名是否真的指向同一个业务实体
    3. 类型兼容性验证：数据类型是否兼容
    4. 置信度合理性：置信度是否与证据强度匹配
    """
    relationships = []

    # 构建字段画像查询表
    target_profile_map = {}
    if field_profiles and target_fields:
        for f in target_fields:
            col = f.get("column_name", "")
            profile = field_profiles.get(f"{target_table}.{col}", {})
            target_profile_map[col] = profile

    ref_profile_map = {}
    if field_profiles and ref_fields:
        for f in ref_fields:
            col = f.get("column_name", "")
            profile = field_profiles.get(f"{ref_table}.{col}", {})
            ref_profile_map[col] = profile

    # 构建字段名查询表（用于类型和注释信息）
    target_field_map = {f.get("column_name", ""): f for f in (target_fields or [])}
    ref_field_map = {f.get("column_name", ""): f for f in (ref_fields or [])}

    try:
        # 尝试提取JSON内容
        json_str = _extract_first_json_array(response)
        if not json_str:
            print(f"[表关系推断] 无法从LLM响应中提取JSON")
            raise ValueError("无法从LLM响应中提取JSON")

        parsed = json.loads(json_str)

        if not isinstance(parsed, list):
            print(f"[表关系推断] LLM响应格式错误，期望数组")
            raise ValueError("LLM响应格式错误，期望数组")

        for item in parsed:
            confidence = float(item.get("confidence", 0))
            from_col = item.get("from_column", "")
            to_col = item.get("to_column", "")
            rel_type = item.get("relationship_type", "semantic")

            # 验证必要字段
            if not from_col or not to_col:
                continue

            # ==================== 后处理验证规则 ====================
            # 设计原则：阈值由 Prompt + 最终过滤阶段统一控制，
            # 这里只做"质量护栏"——阻止明显错误的关系得到高分。
            # 不再硬性钳制 confidence 的上下限，避免与用户阈值档位冲突。

            # 规则1: 关系类型与命名模式的逻辑校验（不强制改 confidence，只做合理性标注）
            if rel_type == "foreign_key":
                from_lower = from_col.lower()
                to_lower = to_col.lower()
                is_fk_pattern = (
                    (from_lower.endswith("_id") and to_lower == "id") or
                    (from_lower.endswith("_id") and to_lower.endswith("_id"))
                )
                if not is_fk_pattern:
                    # 不是外键模式，降级为 shared_field 或 semantic（合理的逻辑校验）
                    rel_type = "shared_field" if from_lower == to_lower else "semantic"
                    print(f"[表关系推断]   ⚠️ 外键模式不匹配，降级为 {rel_type}: {from_col} -> {to_col}")

            # 规则2: 字段名完全相同的 shared_field 应升级类型（仅类型升级，不动 confidence）
            if from_col.lower() == to_col.lower() and rel_type in ["semantic", "value_overlap"]:
                rel_type = "shared_field"

            # 规则3: reasoning 长度作为证据强度的轻量参考（仅下调，不上调，避免越权）
            reasoning = item.get("reasoning", "")
            if reasoning and len(reasoning) < 15:
                confidence = min(confidence, 0.6)
                print(f"[表关系推断]   ⚠️ reasoning 过短，证据不足，confidence 下调到 ≤0.6")

            # 规则4: 类型兼容性护栏（关键数据质量校验，避免数值型被错配为文本型）
            from_type = item.get("from_type", "")
            to_type = item.get("to_type", "")
            # 从字段信息中补充类型
            if not from_type and from_col in target_field_map:
                from_type = target_field_map[from_col].get("column_type", "")
            if not to_type and to_col in ref_field_map:
                to_type = ref_field_map[to_col].get("column_type", "")

            if from_type and to_type:
                if not _are_types_compatible(from_type, to_type):
                    # 类型不兼容：限制 confidence 上限，避免高阈值档位误保留
                    confidence = min(confidence, 0.5)
                    rel_type = "semantic"  # 类型不兼容，不是外键
                    print(f"[表关系推断]   ⚠️ 类型不兼容: {from_type} vs {to_type}，confidence 上限设为 0.5")

            # 规则5: 基数关系默认值
            cardinality = item.get("cardinality", "")
            if cardinality == "":
                cardinality = "many_to_one"

            # 规则6: 确认外键关系的实体一致性（轻量下调，不强制改类型）
            if rel_type == "foreign_key":
                fk_entity = _extract_fk_entity(from_col)
                ref_table_lower = ref_table.lower()

                # 如果被引用字段是主键(id)，则外键关系合理
                if to_col.lower() == "id":
                    # 被引用端是主键，检查引用端是否指向正确的实体
                    if fk_entity and fk_entity not in ref_table_lower:
                        # 外键实体与表名不匹配，但可能是缩写
                        expanded = _get_abbreviation_expansion(fk_entity)
                        if expanded not in ref_table_lower:
                            confidence = min(confidence, 0.75)
                            print(f"[表关系推断]   ⚠️ 外键实体可能不匹配: {fk_entity} vs {ref_table}，confidence 下调到 ≤0.75")

            # ==================== 构建关系对象 ====================

            rel = {
                "from_table": target_table,
                "from_column": from_col,
                "to_table": ref_table,
                "to_column": to_col,
                "relationship_type": rel_type,
                "confidence": round(confidence, 4),
                "reasoning": reasoning,
                "cardinality": cardinality,
                "evidence": {
                    "llm_analyzed": True,
                    "name_match": _calculate_name_match_score(from_col, to_col),
                    "type_compatible": from_type and to_type and _are_types_compatible(from_type, to_type)
                }
            }

            # 业务关系信息
            # ✅ 策略：优先使用 LLM 返回的实体名称（如果合理），否则自行推断
            # 原因：LLM 能基于表名、字段名等信息智能推断实体
            business_relation_llm = item.get("business_relation", {})
            
            # 从 LLM 响应中获取实体名称（如果 LLM 提供了）
            llm_from_entity = business_relation_llm.get("from_entity", "")
            llm_to_entity = business_relation_llm.get("to_entity", "")
            llm_relation_desc = business_relation_llm.get("relation_description", "")
            
            # 使用 LLM 返回的实体名称（如果非空），否则自行推断
            from_entity = llm_from_entity if llm_from_entity else _infer_entity_name(target_table)
            to_entity = llm_to_entity if llm_to_entity else _infer_entity_name(ref_table)
            
            # 生成 relation_description
            # 如果 LLM 返回了合理的描述，使用它；否则根据 cardinality 生成
            if llm_relation_desc:
                relation_description = llm_relation_desc
            else:
                relation_description = _generate_relation_description(from_entity, to_entity, rel["cardinality"])
            
            rel["business_relation"] = {
                "from_entity": from_entity,
                "to_entity": to_entity,
                "relation_description": relation_description,
                "from_role": business_relation_llm.get("from_role", "detail"),
                "to_role": business_relation_llm.get("to_role", "master")
            }

            # 联表查询建议
            join_suggestion = item.get("join_suggestion", {})
            if join_suggestion:
                rel["join_suggestion"] = {
                    "join_type": join_suggestion.get("join_type", "LEFT JOIN"),
                    "join_condition": join_suggestion.get("join_condition",
                        f"{target_table}.{from_col} = {ref_table}.{to_col}"),
                    "sample_sql": join_suggestion.get("sample_sql", ""),
                    "use_cases": join_suggestion.get("use_cases", [])
                }
            else:
                rel["join_suggestion"] = _generate_join_suggestion(
                    target_table, from_col,
                    ref_table, to_col,
                    rel["cardinality"]
                )

            # 数据融合建议
            fusion_suggestion = item.get("fusion_suggestion", {})
            if fusion_suggestion:
                rel["fusion_suggestion"] = {
                    "primary_table": fusion_suggestion.get("primary_table", ref_table),
                    "secondary_table": fusion_suggestion.get("secondary_table", target_table),
                    "aggregation_hint": fusion_suggestion.get("aggregation_hint", ""),
                    "fusion_strategy": fusion_suggestion.get("fusion_strategy", "")
                }
            else:
                rel["fusion_suggestion"] = _generate_fusion_suggestion(
                    target_table, from_col,
                    ref_table, to_col,
                    rel["cardinality"],
                    rel.get("business_relation", {})
                )

            relationships.append(rel)

    except json.JSONDecodeError as e:
        print(f"[表关系推断] JSON解析失败: {e}")
    except Exception as e:
        print(f"[表关系推断] 解析LLM响应失败: {e}")

    return relationships


def _is_foreign_key_field(col_name: str) -> bool:
    """
    判断字段名是否像外键（xxx_id 模式，但不只是泛泛的 id）
    """
    if not col_name:
        return False
    col_lower = col_name.lower()
    # 匹配 xxx_id 模式，但不是孤零零的 id
    if col_lower.endswith("_id") and len(col_lower) > 3:
        return True
    if col_lower.endswith("_ids"):  # 可能是多对多关系
        return True
    return False


def _extract_fk_entity(col_name: str) -> str:
    """
    从外键字段名提取其指向的实体
    例如: user_id -> user, order_id -> order, create_user_id -> user
    """
    if not col_name:
        return ""
    col_lower = col_name.lower()

    # 移除 _id 或 _ids 后缀
    if col_lower.endswith("_ids"):
        entity = col_lower[:-4]
    elif col_lower.endswith("_id"):
        entity = col_lower[:-3]
    else:
        return col_lower

    # 移除常见前缀
    prefixes_to_remove = ["create_", "update_", "delete_", "modify_", "add_", "fk_", "ref_"]
    for prefix in prefixes_to_remove:
        if entity.startswith(prefix):
            entity = entity[len(prefix):]
            break

    return entity


def _calculate_name_match_score(col1: str, col2: str) -> float:
    """
    计算两个字段名的匹配程度（0-1）
    """
    if not col1 or not col2:
        return 0.0

    col1_lower = col1.lower()
    col2_lower = col2.lower()

    # 完全相同
    if col1_lower == col2_lower:
        return 1.0

    # 一个包含另一个
    if col1_lower in col2_lower or col2_lower in col1_lower:
        return 0.8

    # 都是 xxx_id，提取实体比较
    entity1 = _extract_fk_entity(col1)
    entity2 = _extract_fk_entity(col2)
    if entity1 and entity2:
        if entity1 == entity2:
            return 0.9  # 同实体匹配
        else:
            return 0.3  # 不同实体，低分

    # 基础相似度
    common_chars = set(col1_lower) & set(col2_lower)
    if common_chars:
        return len(common_chars) / max(len(set(col1_lower)), len(set(col2_lower)))

    return 0.1


def _extract_first_json_array(text: str) -> str:
    """
    从文本中提取第一个完整的JSON数组

    处理 LLM 可能返回多个JSON对象或多余内容的情况

    Args:
        text: 原始文本

    Returns:
        第一个JSON数组字符串，如果找不到则返回 None
    """
    if not text:
        return None

    # 找到第一个 '[' 的位置
    start_idx = text.find('[')
    if start_idx == -1:
        return None

    # 从第一个 '[' 开始，逐字符扫描，匹配括号
    depth = 0
    in_string = False
    escape_next = False

    for i in range(start_idx, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == '\\' and in_string:
            escape_next = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
        elif char == '[':
            depth += 1
        elif char == ']':
            depth -= 1
            if depth == 0:
                # 找到匹配的 ']'
                return text[start_idx:i+1]

    return None


# 类型兼容性映射
_TYPE_COMPATIBILITY = {
    # 整数类型互兼容
    "tinyint": ["tinyint", "smallint", "int", "bigint", "mediumint"],
    "smallint": ["tinyint", "smallint", "int", "bigint", "mediumint"],
    "mediumint": ["tinyint", "smallint", "int", "bigint", "mediumint"],
    "int": ["tinyint", "smallint", "int", "bigint", "mediumint"],
    "bigint": ["tinyint", "smallint", "int", "bigint", "mediumint"],
    "integer": ["tinyint", "smallint", "int", "bigint", "mediumint"],
    # 字符串类型互兼容
    "varchar": ["varchar", "char", "text", "mediumtext", "longtext", "tinytext"],
    "char": ["varchar", "char", "text", "mediumtext", "longtext", "tinytext"],
    "text": ["varchar", "char", "text", "mediumtext", "longtext", "tinytext"],
    # UUID/UUID类型
    "uuid": ["uuid", "varchar", "char"],
    # 日期时间类型
    "datetime": ["datetime", "timestamp", "date"],
    "timestamp": ["datetime", "timestamp", "date"],
    "date": ["datetime", "timestamp", "date"],
}


def _are_types_compatible(type1: str, type2: str) -> bool:
    """
    判断两个数据库类型是否兼容

    Args:
        type1: 类型1（如 "int", "varchar(50)"）
        type2: 类型2

    Returns:
        True 如果兼容，False 如果不兼容
    """
    if not type1 or not type2:
        return True  # 未知类型，不做判断

    # 提取基础类型（去除长度、精度等）
    base_type1 = _extract_base_type(type1)
    base_type2 = _extract_base_type(type2)

    if base_type1 == base_type2:
        return True

    # 检查兼容性映射
    compatible_types = _TYPE_COMPATIBILITY.get(base_type1, [])
    if base_type2 in compatible_types:
        return True

    # 检查反向映射
    compatible_types = _TYPE_COMPATIBILITY.get(base_type2, [])
    if base_type1 in compatible_types:
        return True

    return False


def _extract_base_type(type_str: str) -> str:
    """
    从类型字符串中提取基础类型

    例如: "varchar(50)" -> "varchar", "decimal(10,2)" -> "decimal"
    """
    if not type_str:
        return ""

    # 转小写
    type_lower = type_str.lower().strip()

    # 移除括号及其内容
    import re
    base = re.sub(r'\([^)]*\)', '', type_lower).strip()

    return base


def _infer_entity_name(table_name: str) -> str:
    """
    从表名推断业务实体名称（中文）

    匹配规则：优先匹配更长的关键词，确保 "user_address" 匹配 "地址" 而非 "用户"
    """
    # 提取表名核心词
    core = _extract_table_core(table_name)

    # 常见实体映射（按关键词长度降序排列，优先匹配更长的词）
    # 例如："user_address" 应匹配 "address"(6) 而非 "user"(4)
    entity_map = [
        # 长度 >= 6 的关键词
        ("customer", "客户"),
        ("employee", "员工"),
        ("product", "商品"),
        ("address", "地址"),
        ("category", "分类"),
        ("merchant", "商户"),
        ("inventory", "库存"),
        ("logistics", "物流"),
        ("delivery", "配送"),
        ("coupon", "优惠券"),
        ("promotion", "促销"),
        ("notification", "通知"),
        ("department", "部门"),
        ("permission", "权限"),
        ("attachment", "附件"),
        # 长度 5 的关键词
        ("member", "会员"),
        ("goods", "商品"),
        ("store", "店铺"),
        ("order", "订单"),
        ("payment", "支付"),
        ("comment", "评论"),
        ("review", "评价"),
        ("message", "消息"),
        # 长度 4 的关键词
        ("user", "用户"),
        ("cart", "购物车"),
        ("shop", "店铺"),
        ("stock", "库存"),
        ("role", "角色"),
        ("menu", "菜单"),
        ("file", "文件"),
        ("image", "图片"),
        # 长度 <= 3 的关键词
        ("item", "商品项"),
        ("log", "日志"),
        ("record", "记录"),
        ("config", "配置"),
        ("setting", "设置"),
    ]

    # 优先匹配最长的关键词
    best_match = None
    best_length = 0

    for key, value in entity_map:
        if key in core and len(key) > best_length:
            best_match = value
            best_length = len(key)

    if best_match:
        return best_match

    # 默认返回表名核心词
    return core


def _generate_relation_description(from_entity: str, to_entity: str, cardinality: str) -> str:
    """
    根据基数关系生成关系描述

    Args:
        from_entity: from 端实体名称
        to_entity: to 端实体名称
        cardinality: 基数关系

    Returns:
        关系描述字符串
    """
    cardinality_desc = {
        "one_to_one": f"一个{from_entity}对应一个{to_entity}",
        "one_to_many": f"一个{to_entity}可以关联多个{from_entity}",
        "many_to_one": f"多个{from_entity}关联同一个{to_entity}",
        "many_to_many": f"{from_entity}和{to_entity}之间存在多对多关系"
    }
    return cardinality_desc.get(cardinality, f"{from_entity}与{to_entity}存在关联")


def _infer_business_relation(
    from_table: str, from_column: str,
    to_table: str, to_column: str,
    cardinality: str
) -> Dict[str, str]:
    """
    推断业务关系
    """
    from_entity = _infer_entity_name(from_table)
    to_entity = _infer_entity_name(to_table)

    # 根据基数关系确定角色
    role_map = {
        "one_to_one": ("detail", "master"),
        "one_to_many": ("detail", "master"),
        "many_to_one": ("detail", "master"),
        "many_to_many": ("fact", "dimension")
    }

    from_role, to_role = role_map.get(cardinality, ("detail", "master"))

    return {
        "from_entity": from_entity,
        "to_entity": to_entity,
        "relation_description": _generate_relation_description(from_entity, to_entity, cardinality),
        "from_role": from_role,
        "to_role": to_role
    }


def _generate_join_suggestion(
    from_table: str, from_column: str,
    to_table: str, to_column: str,
    cardinality: str
) -> Dict[str, Any]:
    """
    生成联表查询建议
    """
    # 根据基数关系推荐JOIN类型
    join_type_map = {
        "one_to_one": "INNER JOIN",
        "one_to_many": "LEFT JOIN",
        "many_to_one": "LEFT JOIN",
        "many_to_many": "INNER JOIN"
    }

    join_type = join_type_map.get(cardinality, "LEFT JOIN")
    join_condition = f"{from_table}.{from_column} = {to_table}.{to_column}"

    # 生成示例SQL
    sample_sql = f"""SELECT *
FROM {from_table}
{join_type} {to_table} ON {join_condition}"""

    # 生成使用场景
    from_entity = _infer_entity_name(from_table)
    to_entity = _infer_entity_name(to_table)

    use_cases = []
    if cardinality == "many_to_one":
        use_cases = [
            f"查询{from_entity}及其关联的{to_entity}信息",
            f"按{to_entity}统计{from_entity}数量",
            f"筛选特定{to_entity}下的所有{from_entity}"
        ]
    elif cardinality == "one_to_many":
        use_cases = [
            f"查询{to_entity}及其所有{from_entity}",
            f"统计每个{to_entity}的{from_entity}数量",
            f"查找没有{from_entity}的{to_entity}"
        ]
    elif cardinality == "one_to_one":
        use_cases = [
            f"查询{from_entity}的完整信息（包含{to_entity}详情）",
            f"合并{from_entity}和{to_entity}数据"
        ]
    else:
        use_cases = [
            f"查询{from_entity}和{to_entity}的关联数据",
            f"分析{from_entity}与{to_entity}的关系"
        ]

    return {
        "join_type": join_type,
        "join_condition": join_condition,
        "sample_sql": sample_sql,
        "use_cases": use_cases
    }


def _generate_fusion_suggestion(
    from_table: str, from_column: str,
    to_table: str, to_column: str,
    cardinality: str,
    business_relation: Dict[str, str]
) -> Dict[str, str]:
    """
    生成数据融合建议
    """
    from_entity = business_relation.get("from_entity", _infer_entity_name(from_table))
    to_entity = business_relation.get("to_entity", _infer_entity_name(to_table))
    from_role = business_relation.get("from_role", "detail")
    to_role = business_relation.get("to_role", "master")

    # 确定主从表
    if to_role == "master" or cardinality in ["many_to_one", "one_to_many"]:
        primary_table = to_table
        secondary_table = from_table
    else:
        primary_table = from_table
        secondary_table = to_table

    # 生成聚合建议
    aggregation_hints = {
        "many_to_one": f"可按{to_entity}聚合{from_entity}数据，如统计数量、求和、平均值等",
        "one_to_many": f"可展开{to_entity}的{from_entity}列表，或聚合为统计指标",
        "one_to_one": f"可直接合并{from_entity}和{to_entity}的字段",
        "many_to_many": f"需要通过关联表连接，可分析{from_entity}和{to_entity}的关联模式"
    }

    # 生成融合策略
    fusion_strategies = {
        "many_to_one": f"以{to_entity}为主体，将{from_entity}数据聚合后作为属性补充；适合构建{to_entity}的全景视图",
        "one_to_many": f"以{to_entity}为主体，{from_entity}作为子记录展开或聚合；适合主从数据展示",
        "one_to_one": f"直接横向合并两表数据，形成完整的{from_entity}信息；注意处理空值情况",
        "many_to_many": f"需要分析具体业务场景，可能需要构建关联矩阵或进行双向聚合"
    }

    return {
        "primary_table": primary_table,
        "secondary_table": secondary_table,
        "aggregation_hint": aggregation_hints.get(cardinality, "根据业务需求选择合适的聚合方式"),
        "fusion_strategy": fusion_strategies.get(cardinality, "根据业务场景确定融合策略")
    }


def _fallback_rule_based_analysis(
    target_table: str, target_fields: List[Dict[str, Any]],
    ref_table: str, ref_fields: List[Dict[str, Any]],
    confidence_threshold: float,
    field_profiles: Dict[str, Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    回退的规则匹配分析（增强版：使用同义词和画像信息）
    """
    relationships = []

    for target_field in target_fields:
        target_column = target_field.get("column_name", "")
        target_type = target_field.get("column_type", "")
        target_comment = target_field.get("column_comment", "") or target_field.get("comment", "") or ""

        # 获取目标字段的画像信息
        target_profile = None
        if field_profiles:
            target_profile = field_profiles.get(f"{target_table}.{target_column}", {})

        for ref_field in ref_fields:
            ref_column = ref_field.get("column_name", "")
            ref_type = ref_field.get("column_type", "")
            ref_comment = ref_field.get("column_comment", "") or ref_field.get("comment", "") or ""

            # 获取参考字段的画像信息
            ref_profile = None
            if field_profiles:
                ref_profile = field_profiles.get(f"{ref_table}.{ref_column}", {})

            rel_info = _analyze_field_relationship_rule_based(
                target_table, target_column, target_type, target_comment,
                ref_table, ref_column, ref_type, ref_comment,
                target_profile=target_profile,
                ref_profile=ref_profile
            )

            if rel_info and rel_info["confidence"] >= confidence_threshold:
                relationships.append(rel_info)

    return relationships


def _analyze_field_relationship_rule_based(
    from_table: str, from_column: str, from_type: str, from_comment: str,
    to_table: str, to_column: str, to_type: str, to_comment: str,
    target_profile: Dict[str, Any] = None,
    ref_profile: Dict[str, Any] = None
) -> Optional[Dict[str, Any]]:
    """
    基于规则的字段关系分析

    检测策略（按优先级）：
    1. 外键模式：xxx_id -> table.id
    2. 共享字段：两张表有相同或相似的业务字段
    3. 同义词匹配：字段名语义等价
    4. 注释相似度
    5. 值域重叠
    """
    from_lower = from_column.lower()
    to_lower = to_column.lower()

    # 跳过可忽略的字段
    ignored_fields = {"created_at", "updated_at", "create_time", "update_time",
                     "gmt_create", "gmt_modified", "deleted_at", "is_deleted"}
    if from_lower in ignored_fields or to_lower in ignored_fields:
        return None

    # 检查数据类型兼容性
    type_compatible = _check_type_compatibility(from_type, to_type)

    # 检查画像兼容性
    profile_compatible = _check_profile_compatibility(target_profile, ref_profile)

    rel = None

    # 策略1: 外键模式 xxx_id -> table.id
    fk_result = _check_fk_pattern(from_column, to_column, to_table)
    if fk_result:
        confidence = fk_result["confidence"]
        if type_compatible:
            confidence = min(0.95, confidence + 0.05)
        if profile_compatible:
            confidence = min(0.98, confidence + 0.03)
        rel = {
            "from_table": from_table,
            "from_column": from_column,
            "to_table": to_table,
            "to_column": to_column,
            "relationship_type": "foreign_key",
            "confidence": confidence,
            "reasoning": fk_result["reasoning"],
            "cardinality": "many_to_one",
            "evidence": {"fk_pattern": True, "type_match": type_compatible, "profile_match": profile_compatible}
        }

    # 策略2: 共享字段（字段名完全相同或核心名相同）
    if not rel:
        from_core = _extract_field_core(from_lower)
        to_core = _extract_field_core(to_lower)

        # 完全相同的字段名
        if from_lower == to_lower and _is_meaningful_link_field(from_lower):
            confidence = 0.85 if type_compatible else 0.7
            if profile_compatible:
                confidence = min(0.92, confidence + 0.05)
            cardinality = _infer_cardinality_by_field(from_lower, to_lower, from_table, to_table)
            rel = {
                "from_table": from_table,
                "from_column": from_column,
                "to_table": to_table,
                "to_column": to_column,
                "relationship_type": "shared_field",
                "confidence": confidence,
                "reasoning": f"共享字段: 两表都有 '{from_column}' 字段",
                "cardinality": cardinality,
                "evidence": {"name_match": 1.0, "type_match": type_compatible, "profile_match": profile_compatible}
            }

        # 核心名相同（如 receiver_name vs receiver_name）
        elif from_core == to_core and from_core and _is_meaningful_link_field(from_lower):
            confidence = 0.8 if type_compatible else 0.65
            if profile_compatible:
                confidence = min(0.88, confidence + 0.05)
            cardinality = _infer_cardinality_by_field(from_lower, to_lower, from_table, to_table)
            rel = {
                "from_table": from_table,
                "from_column": from_column,
                "to_table": to_table,
                "to_column": to_column,
                "relationship_type": "shared_field",
                "confidence": confidence,
                "reasoning": f"共享业务字段: {from_column} 和 {to_column} 表示相同业务含义",
                "cardinality": cardinality,
                "evidence": {"name_match": 0.9, "type_match": type_compatible, "profile_match": profile_compatible}
            }

    # 策略3: 语义同义词匹配
    if not rel:
        synonym_match = _check_synonym_match(from_lower, to_lower)
        if synonym_match and _is_meaningful_link_field(from_lower):
            confidence = synonym_match["confidence"]
            if type_compatible:
                confidence = min(0.85, confidence + 0.10)
            if profile_compatible:
                confidence = min(0.88, confidence + 0.05)
            cardinality = _infer_cardinality_by_field(from_lower, to_lower, from_table, to_table)
            rel = {
                "from_table": from_table,
                "from_column": from_column,
                "to_table": to_table,
                "to_column": to_column,
                "relationship_type": "semantic",
                "confidence": confidence,
                "reasoning": synonym_match["reasoning"],
                "cardinality": cardinality,
                "evidence": {"synonym_match": True, "type_match": type_compatible, "profile_match": profile_compatible}
            }

    # 策略4: 共享业务关键词匹配（receiver_, phone_, address_ 等）
    if not rel:
        shared_keywords = _get_shared_field_keywords()
        if _fields_have_shared_business_meaning(from_lower, to_lower, shared_keywords):
            confidence = 0.75 if type_compatible else 0.6
            if profile_compatible:
                confidence = min(0.82, confidence + 0.05)
            cardinality = _infer_cardinality_by_field(from_lower, to_lower, from_table, to_table)
            rel = {
                "from_table": from_table,
                "from_column": from_column,
                "to_table": to_table,
                "to_column": to_column,
                "relationship_type": "shared_field",
                "confidence": confidence,
                "reasoning": f"共享业务属性: {from_column} 和 {to_column} 属于同一业务语义组",
                "cardinality": cardinality,
                "evidence": {"shared_business": True, "type_match": type_compatible, "profile_match": profile_compatible}
            }

    # 策略5: 注释相似度匹配
    if not rel and from_comment and to_comment:
        comment_similarity = _calculate_comment_similarity(from_comment, to_comment)
        if comment_similarity > 0.6 and _is_meaningful_link_field(from_lower):
            confidence = round(comment_similarity * 0.85, 4)
            if profile_compatible:
                confidence = min(0.85, confidence + 0.05)
            cardinality = _infer_cardinality_by_field(from_lower, to_lower, from_table, to_table)
            rel = {
                "from_table": from_table,
                "from_column": from_column,
                "to_table": to_table,
                "to_column": to_column,
                "relationship_type": "semantic",
                "confidence": confidence,
                "reasoning": f"注释语义相似: '{from_comment}' ≈ '{to_comment}'",
                "cardinality": cardinality,
                "evidence": {"comment_similarity": comment_similarity, "type_match": type_compatible, "profile_match": profile_compatible}
            }

    # 策略6: 画像值域重叠匹配
    if not rel and target_profile and ref_profile:
        value_overlap = _check_value_overlap(target_profile, ref_profile)
        if value_overlap and value_overlap["overlap_score"] > 0.5 and _is_meaningful_link_field(from_lower):
            confidence = value_overlap["overlap_score"] * 0.85
            if type_compatible:
                confidence = min(0.88, confidence + 0.05)
            cardinality = _infer_cardinality_by_field(from_lower, to_lower, from_table, to_table)
            rel = {
                "from_table": from_table,
                "from_column": from_column,
                "to_table": to_table,
                "to_column": to_column,
                "relationship_type": "value_overlap",
                "confidence": round(confidence, 4),
                "reasoning": value_overlap["reasoning"],
                "cardinality": cardinality,
                "evidence": {"value_overlap": value_overlap["overlap_score"], "type_match": type_compatible}
            }

    # 如果找到关系，添加增强信息
    if rel:
        cardinality = rel.get("cardinality", "many_to_many")

        # 添加业务关系信息
        rel["business_relation"] = _infer_business_relation(
            from_table, from_column,
            to_table, to_column,
            cardinality
        )

        # 添加联表查询建议
        rel["join_suggestion"] = _generate_join_suggestion(
            from_table, from_column,
            to_table, to_column,
            cardinality
        )

        # 添加数据融合建议
        rel["fusion_suggestion"] = _generate_fusion_suggestion(
            from_table, from_column,
            to_table, to_column,
            cardinality,
            rel["business_relation"]
        )

    return rel


def _check_synonym_match(from_field: str, to_field: str) -> Optional[Dict[str, Any]]:
    """
    检查两个字段名是否是同义词关系
    """
    from_core = _extract_field_core(from_field)
    to_core = _extract_field_core(to_field)

    # 直接同义词匹配
    from_synonyms = set(_SEMANTIC_SYNONYMS.get(from_core, []))
    to_synonyms = set(_SEMANTIC_SYNONYMS.get(to_core, []))

    if to_core in from_synonyms:
        return {
            "confidence": 0.75,
            "reasoning": f"字段名是同义词: {from_field} ≈ {to_field} ({from_core} <-> {to_core})"
        }

    if from_core in to_synonyms:
        return {
            "confidence": 0.75,
            "reasoning": f"字段名是同义词: {from_field} ≈ {to_field} ({from_core} <-> {to_core})"
        }

    # 扩展同义词匹配（二级同义词）
    common_synonyms = from_synonyms & to_synonyms
    if common_synonyms:
        return {
            "confidence": 0.65,
            "reasoning": f"字段名有共同同义词: {from_field}, {to_field} -> {list(common_synonyms)[0]}"
        }

    return None


def _check_profile_compatibility(profile1: Dict[str, Any], profile2: Dict[str, Any]) -> bool:
    """
    检查两个字段的画像是否兼容
    """
    if not profile1 or not profile2:
        return True  # 没有画像时默认兼容

    # 检查类型提示是否兼容
    type_hint1 = profile1.get("type_hint", "")
    type_hint2 = profile2.get("type_hint", "")

    if type_hint1 and type_hint2:
        # 相同类型提示
        if type_hint1 == type_hint2:
            return True

        # 兼容的类型提示组
        compatible_hints = {
            ("identifier", "identifier"),
            ("identifier", "amount"),
            ("amount", "amount"),
            ("enum", "enum"),
            ("text", "text"),
        }
        if (type_hint1, type_hint2) in compatible_hints or (type_hint2, type_hint1) in compatible_hints:
            return True

        # 不兼容的类型提示
        incompatible_hints = {
            ("boolean_flag", "identifier"),
            ("boolean_flag", "amount"),
            ("datetime", "identifier"),
            ("datetime", "amount"),
        }
        if (type_hint1, type_hint2) in incompatible_hints or (type_hint2, type_hint1) in incompatible_hints:
            return False

    # 检查格式提示是否兼容
    format_hint1 = profile1.get("format_hint", "")
    format_hint2 = profile2.get("format_hint", "")

    if format_hint1 and format_hint2:
        # 相同格式
        if format_hint1 == format_hint2:
            return True

        # 不兼容的格式
        if "uuid" in format_hint1 and "uuid" not in format_hint2:
            return False
        if "uuid" in format_hint2 and "uuid" not in format_hint1:
            return False

    return True


def _check_value_overlap(profile1: Dict[str, Any], profile2: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    检查两个字段的值域是否有重叠
    """
    if not profile1 or not profile2:
        return None

    # 获取高频值
    top_values1 = set()
    for v in profile1.get("top_values", []):
        val = v.get("v") if isinstance(v, dict) else v
        if val:
            top_values1.add(str(val).lower())

    top_values2 = set()
    for v in profile2.get("top_values", []):
        val = v.get("v") if isinstance(v, dict) else v
        if val:
            top_values2.add(str(val).lower())

    if not top_values1 or not top_values2:
        return None

    # 计算重叠
    overlap = top_values1 & top_values2
    if not overlap:
        return None

    overlap_score = len(overlap) / min(len(top_values1), len(top_values2))

    if overlap_score > 0.3:
        return {
            "overlap_score": overlap_score,
            "reasoning": f"字段值域有重叠: 共同值 {list(overlap)[:3]}"
        }

    return None


def _is_meaningful_link_field(field_name: str) -> bool:
    """
    判断字段是否是有意义的关联字段

    包括但不限于：
    1. ID类字段：xxx_id, xxx_code, xxx_no, xxx_uuid
    2. 共享业务字段：receiver_name, phone, address, email 等
    """
    field_lower = field_name.lower()

    # 排除的字段模式（不参与关联）
    exclude_patterns = [
        r"^(created|updated|create|update|gmt).*?(at|time|date)$",  # 时间戳
        r"^(is_|has_|can_)?(deleted|del|remove)",  # 删除标记
        r"^status$",  # 状态（除非有特殊含义）
        r"^remark$",  # 备注
        r"^description$",  # 描述
        r"^memo$",  # 备忘录
        r"^(latitude|longitude|lng|lat)$",  # 坐标
        r"^(sort|order|priority|weight)$",  # 排序
        r"^(version|revision)$",  # 版本
        r"_(url|path|file|salt|hash)$",  # 路径/安全
    ]

    for pattern in exclude_patterns:
        if re.search(pattern, field_lower):
            return False

    # 典型的关联字段模式：ID类
    link_patterns = [
        r"_id$",           # xxx_id
        r"^id$",           # id
        r"^uid$",          # uid
        r"_code$",         # xxx_code
        r"_no$",           # xxx_no
        r"_number$",       # xxx_number
        r"_key$",          # xxx_key
        r"_uuid$",         # xxx_uuid
    ]

    for pattern in link_patterns:
        if re.search(pattern, field_lower):
            return True

    # 共享业务字段（跨表可能存在的相同或相似字段）
    shared_field_patterns = [
        r"^(name|receiver_name|contact_name|consignee|recipient|linkman)$",  # 名称
        r"^(phone|mobile|tel|telephone|cellphone|receiver_phone|contact_phone)$",  # 电话
        r"^(email|mail|receiver_email|contact_email)$",  # 邮箱
        r"^(address|detail_address|receiver_address|shipping_address|delivery_address)$",  # 地址
        r"^(user_name|nickname|display_name|real_name)$",  # 用户名
        r"^(title|product_name|goods_name|item_name)$",  # 名称类
        r"^(price|amount|total|subtotal|discount|fee|cost)$",  # 金额
        r"^(status|state|order_status|payment_status|shipping_status)$",  # 状态
        r"^(remark|memo|note|description|detail)$",  # 描述（这些有时也可作为关联）
        r"^(created_at|updated_at|create_time|update_time)$",  # 时间（有时可关联）
    ]

    for pattern in shared_field_patterns:
        if re.search(pattern, field_lower):
            return True

    return False


def _check_fk_pattern(from_column: str, to_column: str, to_table: str) -> Optional[Dict[str, Any]]:
    """
    检查外键模式
    """
    from_lower = from_column.lower()
    to_lower = to_column.lower()
    table_core = _extract_table_core(to_table)

    # 提取字段核心词
    from_core = _extract_field_core(from_lower)

    # 模式: xxx_id -> table.id
    if to_lower == "id" and from_core:
        # 字段核心词与表名匹配
        if from_core in table_core or table_core.startswith(from_core) or table_core.endswith(from_core):
            return {
                "confidence": 0.90,
                "reasoning": f"外键模式: {from_column} -> {to_table}.id"
            }

    return None


def _extract_field_core(field_name: str) -> str:
    """
    提取字段名的核心词
    """
    field_lower = field_name.lower()

    # 特殊缩写映射
    abbreviations = {
        "uid": "user",
        "pid": "product",
        "oid": "order",
        "cid": "category",
        "sid": "store",
    }

    if field_lower in abbreviations:
        return abbreviations[field_lower]

    # 去掉常见前缀
    prefixes = ["is_", "has_", "can_", "f_", "c_", "t_", "fld_"]
    for prefix in prefixes:
        if field_lower.startswith(prefix):
            field_lower = field_lower[len(prefix):]
            break

    # 去掉常见后缀
    suffixes = ["_id", "_no", "_code", "_name", "_time", "_date", "_at", "_by", "_flag", "_status", "_type", "_key", "_uuid"]
    for suffix in suffixes:
        if field_lower.endswith(suffix):
            return field_lower[:-len(suffix)]

    return field_lower


def _extract_table_core(table_name: str) -> str:
    """
    提取表名的核心词
    """
    table_lower = table_name.lower()
    # 去掉常见前缀
    core = re.sub(r"^(ref_|t_|tbl_|tb_|dim_|fact_|ods_|dwd_|dws_|ads_|target_)", "", table_lower)
    # 去掉常见后缀
    core = re.sub(r"(_info|_data|_master|_detail|_list|_table|_record)$", "", core)
    return core


def _check_type_compatibility(type1: str, type2: str) -> bool:
    """
    检查两个数据类型是否兼容
    """
    if not type1 or not type2:
        return True

    t1 = type1.lower()
    t2 = type2.lower()

    # 数值类型兼容
    numeric_types = {"int", "integer", "bigint", "smallint", "tinyint", "decimal", "numeric", "float", "double", "number", "serial"}
    if any(nt in t1 for nt in numeric_types) and any(nt in t2 for nt in numeric_types):
        return True

    # 字符串类型兼容
    string_types = {"varchar", "char", "text", "string", "nvarchar", "nchar"}
    if any(st in t1 for st in string_types) and any(st in t2 for st in string_types):
        return True

    # UUID类型兼容
    uuid_types = {"uuid", "guid"}
    if any(ut in t1 for ut in uuid_types) and any(ut in t2 for ut in uuid_types):
        return True

    return False


def _calculate_comment_similarity(comment1: str, comment2: str) -> float:
    """
    计算两个注释的相似度
    """
    if not comment1 or not comment2:
        return 0.0

    # 简单的字符重叠计算
    c1 = set(comment1)
    c2 = set(comment2)

    intersection = len(c1 & c2)
    union = len(c1 | c2)

    if union == 0:
        return 0.0

    return intersection / union


def _infer_cardinality_by_field(from_field: str, to_field: str, from_table: str, to_table: str) -> str:
    """
    根据字段特征推断基数关系
    """
    from_lower = from_field.lower()
    to_lower = to_field.lower()

    # 如果目标字段是 id（主键），通常是多对一
    if to_lower == "id":
        return "many_to_one"

    # 如果两边都是 id，可能是一对一
    if from_lower == "id" and to_lower == "id":
        return "one_to_one"

    # 默认多对多
    return "many_to_many"


def _deduplicate_relationships(
    relationships: List[Dict[str, Any]],
    confidence_threshold: float = 0.0
) -> List[Dict[str, Any]]:
    """
    去重并过滤：同一对字段只保留置信度最高的关系，并过滤低于阈值的关系

    Args:
        relationships: 关系列表
        confidence_threshold: 置信度阈值，低于此值的关系会被过滤
    """
    seen = {}

    for rel in relationships:
        # 过滤：低于阈值的关系直接跳过
        if rel.get("confidence", 0) < confidence_threshold:
            continue

        key = (rel["from_table"], rel["from_column"], rel["to_table"], rel["to_column"])

        if key not in seen or rel["confidence"] > seen[key]["confidence"]:
            seen[key] = rel

    return list(seen.values())


def group_relationships_by_table_pair(
    relationships: List[Dict[str, Any]]
) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    """
    按表对分组关系
    """
    grouped = {}

    for rel in relationships:
        from_table = rel["from_table"]
        to_table = rel["to_table"]
        table_pair = tuple(sorted([from_table, to_table]))

        if table_pair not in grouped:
            grouped[table_pair] = []

        grouped[table_pair].append(rel)

    return grouped


def format_relationships_for_display(relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    格式化关系列表用于前端展示
    """
    grouped = group_relationships_by_table_pair(relationships)

    formatted = {
        "table_pairs": [],
        "summary": {
            "total_relationships": len(relationships),
            "total_table_pairs": len(grouped),
            "by_type": {
                "foreign_key": 0,
                "semantic": 0,
                "same_name": 0,
                "synonym": 0
            }
        }
    }

    for rel in relationships:
        rel_type = rel.get("relationship_type", "semantic")
        formatted["summary"]["by_type"][rel_type] = formatted["summary"]["by_type"].get(rel_type, 0) + 1

    for (table1, table2), rels in grouped.items():
        avg_confidence = sum(r["confidence"] for r in rels) / len(rels)

        formatted["table_pairs"].append({
            "table1": table1,
            "table2": table2,
            "relationship_count": len(rels),
            "avg_confidence": round(avg_confidence, 4),
            "relationships": rels
        })

    formatted["table_pairs"].sort(key=lambda x: x["avg_confidence"], reverse=True)

    return formatted
