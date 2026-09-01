"""
 @File: recall.py
 @Description: 召回与过滤
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-01-21 14:46
"""

from __future__ import annotations
import re

# 规则召回 + 向量召回 + 画像过滤 → TopK

_ABBR = {
    "uid": ["user_id","member_id","buyer_id"],
    "deleted": ["is_deleted","del_flag","is_del"],
    "amt": ["amount","pay_amount","total_amount"]
}

# 语义同义词映射：字段名虽然不同，但语义相同
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

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")

def name_sim(a: str, b: str) -> float:
    """
    计算两个字段名的相似度，支持：
    1. 完全匹配
    2. 包含关系
    3. 分词交集
    4. 语义同义词匹配
    """
    a, b = _norm(a), _norm(b)
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.7

    # 语义同义词匹配
    synonyms_a = set(_SEMANTIC_SYNONYMS.get(a, []))
    synonyms_b = set(_SEMANTIC_SYNONYMS.get(b, []))

    # 如果 a 的同义词包含 b，或 b 的同义词包含 a
    if b in synonyms_a or a in synonyms_b:
        return 0.75

    # 检查分词后的同义词匹配
    sa, sb = set(a.split("_")), set(b.split("_"))

    # 扩展同义词集合
    expanded_sa = set(sa)
    expanded_sb = set(sb)
    for word in sa:
        expanded_sa.update(_SEMANTIC_SYNONYMS.get(word, []))
    for word in sb:
        expanded_sb.update(_SEMANTIC_SYNONYMS.get(word, []))

    # 计算扩展后的交集
    expanded_inter = len(expanded_sa & sb) + len(sa & expanded_sb)
    if expanded_inter > 0:
        return min(0.65, 0.3 + 0.15 * expanded_inter)

    # 原始分词交集
    inter = len(sa & sb)
    uni = len(sa | sb) or 1
    return inter / uni

def rule_recall(target_col: str, ref_entries: list[dict], limit: int = 30) -> list[dict]:
    hints = _ABBR.get(_norm(target_col), [])
    scored = []
    for e in ref_entries:
        sim = name_sim(target_col, e["column_name"])
        if hints and any(h in _norm(e["column_name"]) for h in hints):
            sim = min(1.0, sim + 0.15)
        scored.append({**e, "name_sim": sim})
    scored.sort(key=lambda x: x["name_sim"], reverse=True)
    return scored[:limit]

def profile_filter(profile: dict, cand: dict) -> bool:
    th = (profile or {}).get("type_hint")
    cmt = (cand.get("column_comment") or "")
    ctype = (cand.get("column_type") or "").lower()

    if th == "boolean_flag":
        if "time" in ctype or "date" in ctype or "timestamp" in ctype:
            return False
        if "时间" in cmt or "日期" in cmt:
            return False
    if th == "datetime":
        if "标志" in cmt or "是否" in cmt:
            return False
    if th == "amount":
        if "状态" in cmt or "标志" in cmt:
            return False
    return True

def merge_rank(rule_pool: list[dict], vec_pool: list[dict], profile: dict, topk: int = 10, min_score: float = 0.35) -> dict:
    """
    合并规则召回和向量召回的结果，计算综合得分并排序

    Args:
        rule_pool: 规则召回的候选列表
        vec_pool: 向量召回的候选列表
        profile: 目标字段的画像信息
        topk: 返回前K个候选（实际返回数量可能更少，取决于相关性）
        min_score: 最低置信度阈值，低于此分数的候选将被过滤（提高到0.35以过滤不相关候选）

    Returns:
        {"topk": [...], "filtered_out": [...]}
    """
    # dedup by (source_type, table, column)
    dedup = {}
    def k(x): return f'{x.get("source_type")}::{x.get("table_name")}::{x.get("column_name")}'
    for c in rule_pool:
        dedup[k(c)] = {**c, "vector_sim": 0.0}
    for c in vec_pool:
        kk = k(c)
        base = dedup.get(kk, c)
        base["vector_sim"] = max(base.get("vector_sim", 0.0), c.get("vector_sim", 0.0))
        # 同时更新 name_sim（如果向量召回的候选在规则召回中不存在）
        if kk not in dedup:
            base["name_sim"] = 0.0
        dedup[kk] = base

    kept, filtered = [], []
    for c in dedup.values():
        if profile_filter(profile, c):
            kept.append(c)
        else:
            filtered.append(c)

    # 获取目标字段的类型信息和名称
    target_column_type = profile.get("column_type", "")
    target_column_name = profile.get("column_name", "")
    target_comment = profile.get("column_comment", "")

    # 计算综合得分
    for c in kept:
        vector_sim = float(c.get("vector_sim", 0.0))
        name_sim_score = float(c.get("name_sim", 0.0))

        # 类型匹配分（0 或 1）- 使用正确的字段名
        type_match = 1.0 if _type_compatible(c.get("column_type"), target_column_type) else 0.0

        # 画像匹配分（0~1）
        profile_match = _profile_match_score(c, profile)

        # 语义相关性过滤分（0~1）- 新增：基于字段名和注释的语义相关性
        semantic_relevance = _semantic_relevance_score(c, target_column_name, target_comment)

        # 保存各项得分到候选项中（用于前端展示和调试）
        c["type_match"] = type_match
        c["profile_match"] = profile_match
        c["semantic_relevance"] = semantic_relevance

        # 综合得分（调整权重，增加语义相关性权重）
        # 如果语义相关性很低，大幅降低总分
        if semantic_relevance < 0.2:
            # 语义完全不相关，直接给低分
            c["score"] = semantic_relevance * 0.3
        else:
            c["score"] = (
                0.30 * vector_sim +
                0.25 * name_sim_score +
                0.20 * semantic_relevance +
                0.15 * profile_match +
                0.10 * type_match
            )

    # 按得分排序
    kept.sort(key=lambda x: x.get("score", 0.0), reverse=True)

    # 过滤低于最低置信度阈值的候选
    qualified = []
    low_score_filtered = []
    for c in kept:
        if c.get("score", 0.0) >= min_score:
            qualified.append(c)
        else:
            low_score_filtered.append(c)

    # 将低分候选加入过滤列表
    filtered.extend(low_score_filtered)

    return {"topk": qualified[:topk], "filtered_out": filtered}


def _type_compatible(cand_type: str, target_type: str) -> bool:
    """类型兼容性判断"""
    if not cand_type or not target_type:
        return False

    cand = cand_type.lower()
    target = target_type.lower()

    # 数值类型兼容
    numeric_types = {"int", "integer", "bigint", "smallint", "decimal", "numeric", "float", "double"}
    if any(t in cand for t in numeric_types) and any(t in target for t in numeric_types):
        return True

    # 字符串类型兼容
    string_types = {"varchar", "char", "text", "string"}
    if any(t in cand for t in string_types) and any(t in target for t in string_types):
        return True

    # 时间类型兼容
    time_types = {"timestamp", "datetime", "date", "time"}
    if any(t in cand for t in time_types) and any(t in target for t in time_types):
        return True

    return False


def _profile_match_score(candidate: dict, profile: dict) -> float:
    """画像匹配度评分（0~1）"""
    score = 0.0
    type_hint = profile.get("type_hint")
    cand_comment = (candidate.get("column_comment") or "").lower()

    if type_hint == "boolean_flag":
        if any(kw in cand_comment for kw in ["标志", "是否", "flag", "deleted", "enabled"]):
            score += 0.5
        if "0" in cand_comment and "1" in cand_comment:
            score += 0.3

    elif type_hint == "datetime":
        if any(kw in cand_comment for kw in ["时间", "日期", "time", "date"]):
            score += 0.5

    elif type_hint == "amount":
        if any(kw in cand_comment for kw in ["金额", "费用", "价格", "amount", "price", "cost"]):
            score += 0.5

    elif type_hint == "enum":
        if any(kw in cand_comment for kw in ["状态", "类型", "status", "type"]):
            score += 0.5

    elif type_hint == "identifier":
        if any(kw in cand_comment for kw in ["id", "标识", "编号", "code"]):
            score += 0.5

    return min(1.0, score)


def _semantic_relevance_score(candidate: dict, target_column_name: str, target_comment: str) -> float:
    """
    语义相关性评分（0~1）

    基于字段名和注释的语义相关性判断候选是否与目标字段相关
    用于过滤掉完全不相关的候选（如 phone 不应该推荐 category_id）
    """
    cand_name = (candidate.get("column_name") or "").lower()
    cand_comment = (candidate.get("column_comment") or "").lower()
    target_name = (target_column_name or "").lower()
    target_cmt = (target_comment or "").lower()

    score = 0.0

    # 1. 字段名相似性（已经在 name_sim 中计算，这里做补充判断）
    # 如果字段名完全相同或包含关系，给高分
    if target_name == cand_name:
        score += 0.5
    elif target_name in cand_name or cand_name in target_name:
        score += 0.3
    else:
        # 检查字段名的核心词是否匹配（去掉常见前缀后缀）
        target_core = _extract_field_core(target_name)
        cand_core = _extract_field_core(cand_name)
        if target_core and cand_core and (target_core == cand_core or target_core in cand_core or cand_core in target_core):
            score += 0.25

    # 2. 语义类别匹配
    # 定义语义类别及其关键词（更精确的匹配）
    semantic_categories = {
        # 联系方式类
        "phone": ["phone", "mobile", "tel", "telephone", "cellphone", "手机", "电话", "联系电话", "座机", "contact_phone", "mobile_phone"],
        "email": ["email", "mail", "邮箱", "邮件", "电子邮件"],

        # 地址类
        "address": ["address", "addr", "地址", "详细地址", "收货地址", "邮编", "postcode", "zipcode", "street"],
        "region": ["province", "city", "district", "country", "area", "region", "省份", "城市", "地区", "国家", "省", "市", "区", "县"],

        # 人员信息类
        "person_name": ["real_name", "nick_name", "username", "user_name", "姓名", "用户名", "昵称", "真实姓名", "收货人", "联系人", "receiver", "consignee", "recipient", "contact_name"],
        "gender": ["gender", "sex", "性别"],
        "age": ["age", "birthday", "birth", "年龄", "生日", "出生日期"],
        "id_card": ["id_card", "id_no", "identity", "身份证", "证件号", "证件"],

        # 标识类（更严格）
        "primary_id": ["_id", "uuid", "guid", "主键", "唯一标识"],

        # 时间类
        "time": ["_time", "_date", "_at", "created", "updated", "modified", "时间", "日期", "创建时间", "更新时间", "修改时间"],

        # 状态类
        "status": ["status", "state", "is_", "has_", "状态", "标志", "是否", "启用", "禁用", "deleted", "enabled", "disabled"],

        # 金额类
        "amount": ["amount", "price", "cost", "fee", "money", "total_amount", "pay_amount", "金额", "价格", "费用", "总额", "单价", "总价"],
        "discount": ["discount", "coupon", "优惠", "折扣", "减免"],

        # 数量类
        "count": ["count", "num", "quantity", "qty", "数量", "个数", "总数", "件数"],
        "weight": ["weight", "重量", "净重", "毛重"],
        "size": ["length", "width", "height", "尺寸", "长度", "宽度", "高度"],

        # 业务实体类
        "user": ["user_id", "member_id", "customer_id", "buyer_id", "seller_id", "用户", "会员", "客户", "买家", "卖家"],
        "order": ["order_id", "order_no", "订单", "工单"],
        "product": ["product_id", "goods_id", "item_id", "sku_id", "商品", "产品", "货品"],
        "category": ["category_id", "cat_id", "分类", "类别", "品类"],
        "brand": ["brand_id", "brand", "品牌"],
        "store": ["store_id", "shop_id", "warehouse_id", "店铺", "门店", "仓库"],

        # 编码类（与标识类分开，更严格）
        "business_code": ["order_no", "order_number", "product_code", "sku_code", "item_code", "订单号", "商品编码", "SKU编码"],

        # 描述类
        "remark": ["remark", "comment", "note", "description", "memo", "备注", "说明", "描述", "留言"],
        "title": ["title", "subject", "标题", "主题", "名称"],
        "content": ["content", "body", "text", "内容", "正文"],

        # 图片/文件类
        "image": ["image", "img", "photo", "picture", "avatar", "logo", "图片", "照片", "头像", "图标"],
        "file": ["file", "attachment", "document", "文件", "附件", "文档"],
        "url": ["url", "link", "path", "链接", "路径"],
    }

    # 判断目标字段属于哪个语义类别
    target_categories = set()
    for cat, keywords in semantic_categories.items():
        for kw in keywords:
            if kw in target_name or kw in target_cmt:
                target_categories.add(cat)
                break

    # 判断候选字段属于哪个语义类别
    cand_categories = set()
    for cat, keywords in semantic_categories.items():
        for kw in keywords:
            if kw in cand_name or kw in cand_comment:
                cand_categories.add(cat)
                break

    # 如果有共同的语义类别，给高分
    common_categories = target_categories & cand_categories
    if common_categories:
        # 根据匹配的类别数量给分
        score += min(0.5, 0.3 + 0.1 * len(common_categories))
    elif target_categories and cand_categories and not common_categories:
        # 如果两者都有明确的语义类别但不相同，说明不相关
        # 例如：phone 和 category_id 明显不相关
        # 根据类别的"距离"来决定惩罚程度
        penalty = _calculate_category_penalty(target_categories, cand_categories)
        score -= penalty

    # 3. 注释关键词匹配
    # 提取目标注释中的关键词
    target_keywords = set()
    for word in re.split(r'[^a-z\u4e00-\u9fff]+', target_cmt):
        if len(word) >= 2:
            target_keywords.add(word)

    # 检查候选注释是否包含目标关键词
    matched_keywords = 0
    for kw in target_keywords:
        if kw in cand_comment:
            matched_keywords += 1

    if matched_keywords > 0:
        score += min(0.2, 0.1 * matched_keywords)

    return max(0.0, min(1.0, score))


def _extract_field_core(field_name: str) -> str:
    """
    提取字段名的核心词（去掉常见前缀后缀）
    例如：user_id -> user, create_time -> create, is_deleted -> deleted
    """
    name = field_name.lower()

    # 去掉常见前缀
    prefixes = ["is_", "has_", "can_", "f_", "c_", "t_", "fld_"]
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break

    # 去掉常见后缀
    suffixes = ["_id", "_no", "_code", "_name", "_time", "_date", "_at", "_by", "_flag", "_status", "_type"]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break

    return name


def _calculate_category_penalty(target_cats: set, cand_cats: set) -> float:
    """
    计算语义类别不匹配的惩罚分数
    某些类别之间完全不相关，惩罚更重
    """
    # 定义兼容的类别组（同组内可以互相推荐）
    compatible_groups = [
        {"phone", "email"},  # 联系方式内部可以互相推荐
        {"address", "region"},  # 地址类内部可以互相推荐
        {"amount", "discount"},  # 金额类内部可以互相推荐
        {"count", "weight", "size"},  # 数量类内部可以互相推荐
        {"remark", "title", "content"},  # 描述类内部可以互相推荐
        {"image", "file", "url"},  # 文件类内部可以互相推荐
        {"person_name", "gender", "age", "id_card"},  # 人员信息类内部可以互相推荐
        {"user", "person_name"},  # 用户和人名相关
        {"order", "business_code"},  # 订单和业务编码相关
        {"product", "category", "brand"},  # 商品相关
    ]

    # 检查目标和候选是否在同一个兼容组内
    for group in compatible_groups:
        if target_cats & group and cand_cats & group:
            return 0.1  # 同组内，轻微惩罚

    # 定义完全不兼容的类别对（这些类别之间不应该互相推荐）
    incompatible_pairs = [
        # 联系方式 vs 业务实体
        ({"phone", "email"}, {"product", "order", "category", "brand", "store", "business_code"}),
        # 地址 vs 金额/数量/状态
        ({"address", "region"}, {"amount", "count", "status", "primary_id"}),
        # 人名 vs 业务实体
        ({"person_name"}, {"product", "category", "brand", "order", "business_code"}),
        # 时间 vs 联系方式/地址/人名
        ({"time"}, {"phone", "email", "address", "person_name"}),
        # 金额 vs 联系方式/地址/人名
        ({"amount"}, {"phone", "email", "address", "person_name", "region"}),
        # 状态 vs 联系方式/地址/人名/金额
        ({"status"}, {"phone", "email", "address", "person_name", "amount", "region"}),
        # 标识ID vs 联系方式/地址/人名/描述
        ({"primary_id"}, {"phone", "email", "address", "person_name", "remark", "title", "content"}),
        # 编码 vs 联系方式/人名
        ({"business_code"}, {"phone", "email", "person_name", "address"}),
    ]

    for group1, group2 in incompatible_pairs:
        if (target_cats & group1 and cand_cats & group2) or (target_cats & group2 and cand_cats & group1):
            return 0.5  # 完全不兼容，重惩罚

    # 默认惩罚
    return 0.25
