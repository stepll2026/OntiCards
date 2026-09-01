"""
 @File: relationship_card_generator.py
 @Description: 关系卡片生成器 - 将表关系转换为可视化的关系卡片
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-01-28
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta

# 北京时区（东八区）
tz_cst = timezone(timedelta(hours=8))


def generate_relationship_cards(
    relationships: List[Dict[str, Any]],
    datasource_id: str,
    schema_name: str = "public",
    schema_hash: str = None,
    datasource_schema_map: Dict[str, str] = None
) -> List[Dict[str, Any]]:
    """
    生成关系卡片（支持同源和跨源）

    Args:
        relationships: 关系列表
        datasource_id: 主数据源ID
        schema_name: Schema名称
        schema_hash: Schema哈希值
        datasource_schema_map: 数据源ID到schema_hash的映射（跨源时使用）

    Returns:
        关系卡片列表
    """
    # 按表对分组
    from controllers.target_inventory.relationship_inference import group_relationships_by_table_pair

    grouped = group_relationships_by_table_pair(relationships)

    cards = []
    for (table1, table2), rels in grouped.items():
        card = _create_relationship_card(
            table1, table2, rels,
            datasource_id, schema_name,
            schema_hash=schema_hash,
            datasource_schema_map=datasource_schema_map
        )
        cards.append(card)

    return cards


def _create_relationship_card(
    table1: str,
    table2: str,
    relationships: List[Dict[str, Any]],
    datasource_id: str,
    schema_name: str,
    schema_hash: str = None,
    datasource_schema_map: Dict[str, str] = None
) -> Dict[str, Any]:
    """
    创建单个关系卡片（增强版：支持跨源，包含业务关系、联表建议、融合建议）

    Args:
        table1: 表1名称
        table2: 表2名称
        relationships: 该表对的所有关系
        datasource_id: 主数据源ID
        schema_name: Schema名称
        schema_hash: Schema哈希值
        datasource_schema_map: 数据源ID到schema_hash的映射（跨源时使用）

    Returns:
        关系卡片对象
    """
    # 初始化 datasource_schema_map
    if datasource_schema_map is None:
        datasource_schema_map = {}

    # 计算整体置信度（取所有关系的平均值）
    avg_confidence = sum(r["confidence"] for r in relationships) / len(relationships)

    # 判断关系方向和类型
    direction, primary_type = _determine_direction_and_type(relationships)

    # 检测是否跨源（从关系中提取数据源信息）
    is_cross_source = False
    table1_datasource_id = datasource_id
    table2_datasource_id = datasource_id
    table1_schema_hash = schema_hash
    table2_schema_hash = schema_hash

    for rel in relationships:
        from_ds = rel.get("from_datasource_id")
        to_ds = rel.get("to_datasource_id")
        if from_ds and to_ds and from_ds != to_ds:
            is_cross_source = True
            # 确定 table1 和 table2 各自的数据源
            if rel.get("from_table") == table1:
                table1_datasource_id = from_ds
                table2_datasource_id = to_ds
                table1_schema_hash = rel.get("from_schema_hash") or datasource_schema_map.get(from_ds, schema_hash)
                table2_schema_hash = rel.get("to_schema_hash") or datasource_schema_map.get(to_ds, schema_hash)
            else:
                table1_datasource_id = to_ds
                table2_datasource_id = from_ds
                table1_schema_hash = rel.get("to_schema_hash") or datasource_schema_map.get(to_ds, schema_hash)
                table2_schema_hash = rel.get("from_schema_hash") or datasource_schema_map.get(from_ds, schema_hash)
            break

    # 提取关系字段（包含增强信息）
    fields = []
    for rel in relationships:
        field_info = {
            "from_table": rel["from_table"],
            "from_column": rel["from_column"],
            "from_datasource_id": rel.get("from_datasource_id", datasource_id),
            "to_table": rel["to_table"],
            "to_column": rel["to_column"],
            "to_datasource_id": rel.get("to_datasource_id", datasource_id),
            "type": rel["relationship_type"],
            "confidence": rel["confidence"],
            "reasoning": rel["reasoning"],
            "cardinality": rel.get("cardinality", direction)
        }

        # 添加增强信息（如果存在）
        if "business_relation" in rel:
            field_info["business_relation"] = rel["business_relation"]
        if "join_suggestion" in rel:
            field_info["join_suggestion"] = rel["join_suggestion"]
        if "fusion_suggestion" in rel:
            field_info["fusion_suggestion"] = rel["fusion_suggestion"]

        fields.append(field_info)

    # 生成关系描述（优先使用LLM生成的业务关系描述）
    description = _generate_relationship_description(table1, table2, relationships, direction)

    # 聚合业务关系信息（取置信度最高的关系的业务信息）
    best_rel = max(relationships, key=lambda r: r.get("confidence", 0))
    business_relation = best_rel.get("business_relation", {})
    join_suggestion = best_rel.get("join_suggestion", {})
    fusion_suggestion = best_rel.get("fusion_suggestion", {})

    # ✅ 业务描述：使用 best_rel 中已通过 _infer_business_relation 验证过的描述
    business_description = business_relation.get("relation_description") or description

    # 构建卡片（支持跨源）
    card = {
        "card_id": f"{table1_datasource_id}_{table1}_{table2_datasource_id}_{table2}",
        "datasource_id": datasource_id,  # 主数据源ID（兼容旧逻辑）
        "schema_name": schema_name,
        # 表1信息
        "table1": table1,
        "table1_datasource_id": table1_datasource_id,
        "table1_schema_hash": table1_schema_hash,
        # 表2信息
        "table2": table2,
        "table2_datasource_id": table2_datasource_id,
        "table2_schema_hash": table2_schema_hash,
        # 跨源标识
        "is_cross_source": is_cross_source,
        "relationship_type": primary_type,
        "direction": direction,  # "one_to_many", "many_to_one", "many_to_many", "one_to_one"
        "confidence": round(avg_confidence, 3),
        "fields": fields,
        "description": description,
        "business_description": business_description,
        "created_at": datetime.now(tz_cst).isoformat(),
        "metadata": {
            "relationship_count": len(relationships),
            "foreign_key_count": sum(1 for r in relationships if r["relationship_type"] == "foreign_key"),
            "semantic_count": sum(1 for r in relationships if r["relationship_type"] == "semantic"),
            "name_based_count": sum(1 for r in relationships if r["relationship_type"] == "name_based"),
            "same_name_count": sum(1 for r in relationships if r["relationship_type"] == "same_name"),
            "is_cross_source": is_cross_source
        },
        # 增强信息：业务关系
        "business_relation": {
            "from_entity": business_relation.get("from_entity", table1),
            "to_entity": business_relation.get("to_entity", table2),
            "relation_description": business_relation.get("relation_description", ""),
            "from_role": business_relation.get("from_role", "detail"),
            "to_role": business_relation.get("to_role", "master")
        },
        # 增强信息：联表查询建议
        "join_suggestion": {
            "recommended_join_type": join_suggestion.get("join_type", "LEFT JOIN"),
            "join_conditions": _aggregate_join_conditions(relationships),
            "sample_sql": join_suggestion.get("sample_sql", _generate_sample_sql(table1, table2, relationships, direction)),
            "use_cases": join_suggestion.get("use_cases", [])
        },
        # 增强信息：数据融合建议
        "fusion_suggestion": {
            "primary_table": fusion_suggestion.get("primary_table", table2),
            "secondary_table": fusion_suggestion.get("secondary_table", table1),
            "aggregation_hint": fusion_suggestion.get("aggregation_hint", ""),
            "fusion_strategy": fusion_suggestion.get("fusion_strategy", ""),
            "recommended_aggregations": _generate_aggregation_suggestions(table1, table2, direction)
        }
    }

    return card


def _aggregate_join_conditions(relationships: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    聚合所有关系的JOIN条件
    """
    conditions = []
    for rel in relationships:
        condition = {
            "from_column": rel["from_column"],
            "to_column": rel["to_column"],
            "condition": f"{rel['from_table']}.{rel['from_column']} = {rel['to_table']}.{rel['to_column']}",
            "confidence": rel.get("confidence", 0)
        }
        conditions.append(condition)

    # 按置信度排序
    conditions.sort(key=lambda x: x["confidence"], reverse=True)
    return conditions


def _generate_sample_sql(
    table1: str, table2: str,
    relationships: List[Dict[str, Any]],
    direction: str
) -> str:
    """
    生成示例SQL
    """
    if not relationships:
        return ""

    # 使用置信度最高的关系生成JOIN条件
    best_rel = max(relationships, key=lambda r: r.get("confidence", 0))

    # 根据方向选择JOIN类型
    join_type = "LEFT JOIN" if direction in ["many_to_one", "one_to_many"] else "INNER JOIN"

    join_condition = f"{best_rel['from_table']}.{best_rel['from_column']} = {best_rel['to_table']}.{best_rel['to_column']}"

    sql = f"""SELECT *
FROM {table1}
{join_type} {table2} ON {join_condition}"""

    return sql


def _generate_aggregation_suggestions(table1: str, table2: str, direction: str) -> List[str]:
    """
    生成聚合建议列表
    """
    suggestions = []

    if direction == "many_to_one":
        suggestions = [
            f"COUNT({table1}.*) - 统计{table1}记录数",
            f"GROUP BY {table2}.id - 按{table2}分组聚合",
            f"SUM/AVG/MAX/MIN - 对{table1}的数值字段进行聚合计算"
        ]
    elif direction == "one_to_many":
        suggestions = [
            f"COUNT({table2}.*) - 统计关联的{table2}记录数",
            f"JSON_AGG({table2}.*) - 将{table2}记录聚合为JSON数组",
            f"STRING_AGG - 将{table2}的某字段聚合为字符串"
        ]
    elif direction == "one_to_one":
        suggestions = [
            f"直接JOIN合并两表字段",
            f"COALESCE - 处理可能的空值情况"
        ]
    else:  # many_to_many
        suggestions = [
            f"COUNT(DISTINCT {table1}.id) - 统计去重后的{table1}数量",
            f"COUNT(DISTINCT {table2}.id) - 统计去重后的{table2}数量",
            f"交叉分析 - 分析两表的关联模式"
        ]

    return suggestions


def _determine_direction_and_type(relationships: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    判断关系方向和主要类型

    优先使用LLM分析返回的cardinality字段，如果没有则基于规则推断

    Returns:
        (direction, primary_type)
    """
    # 统计关系类型
    type_counts = {}
    for rel in relationships:
        rel_type = rel["relationship_type"]
        type_counts[rel_type] = type_counts.get(rel_type, 0) + 1

    # 主要类型是出现次数最多的
    primary_type = max(type_counts.items(), key=lambda x: x[1])[0]

    # 优先使用LLM分析返回的cardinality字段
    cardinality_counts = {}
    for rel in relationships:
        cardinality = rel.get("cardinality")
        if cardinality:
            cardinality_counts[cardinality] = cardinality_counts.get(cardinality, 0) + 1

    if cardinality_counts:
        # 使用出现次数最多的cardinality作为方向
        # 同时考虑置信度加权
        weighted_cardinality = {}
        for rel in relationships:
            cardinality = rel.get("cardinality")
            if cardinality:
                confidence = rel.get("confidence", 0.5)
                weighted_cardinality[cardinality] = weighted_cardinality.get(cardinality, 0) + confidence

        if weighted_cardinality:
            direction = max(weighted_cardinality.items(), key=lambda x: x[1])[0]
            return direction, primary_type

    # 回退：基于外键关系判断
    fk_rels = [r for r in relationships if r["relationship_type"] == "foreign_key"]

    if fk_rels:
        # 外键关系通常是多对一
        direction = "many_to_one"
    else:
        # 检查是否有ID字段关联，推断关系方向
        direction = _infer_direction_from_fields(relationships)

    return direction, primary_type


def _infer_direction_from_fields(relationships: List[Dict[str, Any]]) -> str:
    """
    根据字段特征推断关系方向

    Args:
        relationships: 关系列表

    Returns:
        关系方向
    """
    for rel in relationships:
        to_column = rel.get("to_column", "").lower()
        from_column = rel.get("from_column", "").lower()

        # 如果目标字段是主键(id)，通常是多对一关系
        if to_column == "id":
            return "many_to_one"

        # 如果源字段是主键(id)，通常是一对多关系
        if from_column == "id":
            return "one_to_many"

        # 如果两边都是xxx_id类型，可能是多对多
        if from_column.endswith("_id") and to_column.endswith("_id"):
            return "many_to_many"

    # 默认返回多对多
    return "many_to_many"


def _generate_relationship_description(
    table1: str,
    table2: str,
    relationships: List[Dict[str, Any]],
    direction: str
) -> str:
    """
    生成关系描述文本

    Args:
        table1: 表1名称
        table2: 表2名称
        relationships: 关系列表
        direction: 关系方向

    Returns:
        描述文本
    """
    # 提取关系字段
    field_pairs = []
    for rel in relationships:
        field_pairs.append(f"{rel['from_column']} -> {rel['to_column']}")

    fields_str = "、".join(field_pairs[:3])  # 最多显示3个
    if len(field_pairs) > 3:
        fields_str += f" 等{len(field_pairs)}个字段"

    # 根据方向生成描述
    direction_map = {
        "one_to_many": "一对多",
        "many_to_one": "多对一",
        "many_to_many": "多对多",
        "one_to_one": "一对一"
    }

    direction_text = direction_map.get(direction, "关联")

    description = f"表 {table1} 与表 {table2} 存在{direction_text}关系，通过字段 {fields_str} 关联"

    return description


def format_cards_for_display(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    格式化关系卡片用于前端展示

    Args:
        cards: 关系卡片列表

    Returns:
        格式化后的卡片列表
    """
    formatted = []

    for card in cards:
        formatted.append({
            "id": card["card_id"],
            "table1": card["table1"],
            "table2": card["table2"],
            "type": card["relationship_type"],
            "direction": card["direction"],
            "confidence": card["confidence"],
            "description": card["description"],
            "field_count": len(card["fields"]),
            "fields": card["fields"]
        })

    # 按置信度降序排序
    formatted.sort(key=lambda x: x["confidence"], reverse=True)

    return formatted


def export_cards_to_graph_format(cards: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    将关系卡片导出为图数据格式（用于可视化，支持两种格式）

    Args:
        cards: 关系卡片列表
            - 旧格式：表对卡片（包含 table1, table2, fields 等）
            - 新格式：标准卡片（包含 DocInfo, TableInfo, Relationships 等）

    Returns:
        图数据 {nodes: [...], edges: [...]}
    """
    nodes = {}
    edges = []

    for card in cards:
        # 判断卡片格式
        if "DocInfo" in card:
            # ✅ 新格式：标准卡片（以表为中心）
            _process_standard_card(card, nodes, edges)
        else:
            # ❌ 旧格式：表对卡片（兼容）
            _process_legacy_card(card, nodes, edges)

    return {
        "nodes": list(nodes.values()),
        "edges": edges
    }


def _process_standard_card(
    card: Dict[str, Any],
    nodes: Dict[str, Any],
    edges: List[Dict[str, Any]]
):
    """
    处理标准格式的关系卡片（以表为中心）- 返回格式对齐全域盘点

    标准格式：
    {
        "DocInfo": {...},
        "TableInfo": {"table_name": "users", ...},
        "Relationships": [
            {
                "related_table": "orders",
                "relationship_type": "one_to_many",
                "confidence": 0.95,
                "join_fields": [...],
                ...
            }
        ],
        ...
    }
    """
    doc_info = card.get("DocInfo", {})
    table_info = card.get("TableInfo", {})
    relationships = card.get("Relationships", [])

    current_table = table_info.get("table_name")
    datasource_id = doc_info.get("datasource_id")

    if not current_table:
        return

    # 添加当前表节点（格式对齐全域盘点）
    if current_table not in nodes:
        nodes[current_table] = {
            "id": current_table,
            "label": current_table,
            "type": "table",
            "datasource_id": datasource_id,
            "related_count": 0,  # 会在下面累加
            "cross_source_count": 0  # 会在下面累加
        }

    # 处理每个关联关系
    for rel in relationships:
        related_table = rel.get("related_table")
        if not related_table:
            continue

        # 判断是否跨源
        is_cross_source = rel.get("is_cross_source", False)
        related_datasource_id = rel.get("related_datasource_id", datasource_id)

        # 添加关联表节点
        if related_table not in nodes:
            nodes[related_table] = {
                "id": related_table,
                "label": related_table,
                "type": "table",
                "datasource_id": related_datasource_id,
                "related_count": 0,
                "cross_source_count": 0
            }

        # 更新节点的关联计数
        nodes[current_table]["related_count"] += 1
        nodes[related_table]["related_count"] += 1

        if is_cross_source:
            nodes[current_table]["cross_source_count"] += 1
            nodes[related_table]["cross_source_count"] += 1

        # 转换 join_fields 为 join_conditions 格式（对齐全域盘点）
        join_fields = rel.get("join_fields", [])
        join_conditions = []
        for jf in join_fields:
            join_conditions.append({
                "local_field": jf.get("local_field"),
                "remote_field": jf.get("remote_field"),
                "confidence": jf.get("confidence", 0),
                "mapping_type": jf.get("relationship_type", "semantic")
            })

        # 生成边ID
        edge_id = f"{datasource_id}_{current_table}_{related_datasource_id}_{related_table}"

        # 添加边（格式对齐全域盘点）
        edge = {
            "id": edge_id,
            "source": current_table,
            "target": related_table,
            "source_datasource_id": datasource_id,
            "target_datasource_id": related_datasource_id,
            "is_cross_source": is_cross_source,
            "label": rel.get("relationship_type", "Semantic"),
            "strength": rel.get("confidence", 0),  # 对齐字段名
            "cardinality": rel.get("relationship_type", "many_to_many"),  # 对齐字段名
            "join_conditions": join_conditions  # 对齐格式
        }
        edges.append(edge)


def _process_legacy_card(
    card: Dict[str, Any],
    nodes: Dict[str, Any],
    edges: List[Dict[str, Any]]
):
    """
    处理旧格式的关系卡片（表对卡片）- 返回格式对齐全域盘点

    旧格式：
    {
        "table1": "users",
        "table2": "orders",
        "card_id": "...",
        "relationship_type": "one_to_many",
        "confidence": 0.9,
        "fields": [...],
        ...
    }
    """
    table1 = card["table1"]
    table2 = card["table2"]

    # 获取数据源信息
    datasource_id = card.get("datasource_id", card.get("table1_datasource_id"))
    table1_datasource_id = card.get("table1_datasource_id", datasource_id)
    table2_datasource_id = card.get("table2_datasource_id", datasource_id)
    is_cross_source = card.get("is_cross_source", False)

    # 添加节点（格式对齐全域盘点）
    if table1 not in nodes:
        nodes[table1] = {
            "id": table1,
            "label": table1,
            "type": "table",
            "datasource_id": table1_datasource_id,
            "related_count": 0,
            "cross_source_count": 0
        }

    if table2 not in nodes:
        nodes[table2] = {
            "id": table2,
            "label": table2,
            "type": "table",
            "datasource_id": table2_datasource_id,
            "related_count": 0,
            "cross_source_count": 0
        }

    # 更新节点的关联计数
    nodes[table1]["related_count"] += 1
    nodes[table2]["related_count"] += 1

    if is_cross_source:
        nodes[table1]["cross_source_count"] += 1
        nodes[table2]["cross_source_count"] += 1

    # 转换 fields 为 join_conditions 格式
    fields = card.get("fields", [])
    join_conditions = []
    for field in fields:
        join_conditions.append({
            "local_field": field.get("from_column"),
            "remote_field": field.get("to_column"),
            "confidence": field.get("confidence", 0),
            "mapping_type": field.get("type", "semantic")
        })

    # 获取基数：优先使用 direction，否则使用 relationship_type
    cardinality = card.get("direction") or card.get("relationship_type") or "many_to_many"
    
    # 添加边（格式对齐全域盘点）
    edge = {
        "id": card.get("card_id", f"{table1}_{table2}"),
        "source": table1,
        "target": table2,
        "source_datasource_id": table1_datasource_id,
        "target_datasource_id": table2_datasource_id,
        "is_cross_source": is_cross_source,
        "label": card.get("relationship_type", "Semantic"),
        "strength": card.get("confidence", 0),  # 对齐字段名
        "cardinality": cardinality,  # 使用正确的基数
        "join_conditions": join_conditions  # 对齐格式
    }
    edges.append(edge)
