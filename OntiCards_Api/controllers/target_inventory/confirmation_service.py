"""
 @File: confirmation_service.py
 @Description: 确认服务 - 处理用户确认字段推荐和表关系的逻辑
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-02-02
"""

from __future__ import annotations
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm.attributes import flag_modified
from extensions.ext_database import db

# 北京时区（东八区）
tz_cst = timezone(timedelta(hours=8))
from models.global_inventory import (
    TargetInventoryJobResult,
    FieldMapping,
    TableRelationship,
    TableRelationshipCard
)
from models.datacards_datasource import DataCardDataSource


def confirm_field_recommendations(
    job_id: str,
    datasource_id: str,
    schema_hash: str,
    confirmations: Dict[str, Dict[str, Dict[str, Any]]]
) -> Dict[str, Any]:
    """
    确认字段推荐结果

    Args:
        job_id: 任务ID
        datasource_id: 数据源ID
        schema_hash: Schema哈希值
        confirmations: 用户确认的字段映射
            {
                "table_name": {
                    "column_name": {
                        "action": "accept" or "reject" or "custom",
                        "selected_candidate": {...},  # 用户选择的候选项
                        "custom_comment": "自定义注释"  # 如果action是custom
                    }
                }
            }

    Returns:
        {
            "success": True,
            "updated_fields": 10,
            "created_mappings": 8,
            "updated_datacards": 3
        }
    """
    print(f"[字段推荐确认] 开始处理，任务ID: {job_id}")

    result = {
        "success": False,
        "updated_fields": 0,
        "created_mappings": 0,
        "updated_datacards": 0,
        "errors": []
    }

    try:
        # 1. 获取任务结果
        job_result = TargetInventoryJobResult.query.filter_by(job_id=job_id).first()
        if not job_result:
            result["errors"].append(f"任务结果不存在: {job_id}")
            return result

        # 1.1 获取字段画像信息（用于提取源字段类型）
        field_profiles = job_result.field_profiles_json or {}

        # 2. 更新 confirm_json
        if not job_result.confirm_json:
            job_result.confirm_json = {}

        job_result.confirm_json["field_recommendations"] = confirmations
        job_result.confirm_json["confirmed_at"] = datetime.now(tz_cst).isoformat()
        # 标记 JSON 字段已修改，确保 SQLAlchemy 能检测到变化
        flag_modified(job_result, "confirm_json")

        # 3. 更新 field_mappings_json（用户确认后的最终映射）
        if not job_result.field_mappings_json:
            job_result.field_mappings_json = {}

        for table_name, columns in confirmations.items():
            if table_name not in job_result.field_mappings_json:
                job_result.field_mappings_json[table_name] = {}

            for column_name, confirmation in columns.items():
                action = confirmation.get("action")

                if action == "accept":
                    # 用户接受推荐
                    selected = confirmation.get("selected_candidate")
                    if selected:
                        job_result.field_mappings_json[table_name][column_name] = {
                            "confirmed": True,
                            "source": selected.get("source"),
                            "comment": selected.get("column_comment"),
                            "confidence": selected.get("confidence"),
                            "confirmed_at": datetime.now(tz_cst).isoformat()
                        }
                        result["updated_fields"] += 1

                elif action == "custom":
                    # 用户自定义注释
                    custom_comment = confirmation.get("custom_comment")
                    if custom_comment:
                        job_result.field_mappings_json[table_name][column_name] = {
                            "confirmed": True,
                            "source": "user_custom",
                            "comment": custom_comment,
                            "confidence": 1.0,
                            "confirmed_at": datetime.now(tz_cst).isoformat()
                        }
                        result["updated_fields"] += 1

                elif action == "reject":
                    # 用户拒绝推荐，保留原注释
                    job_result.field_mappings_json[table_name][column_name] = {
                        "confirmed": True,
                        "source": "original",
                        "comment": confirmation.get("original_comment", ""),
                        "confidence": 1.0,
                        "confirmed_at": datetime.now(tz_cst).isoformat()
                    }

        # 4. 持久化到 field_mapping 表
        for table_name, columns in confirmations.items():
            for column_name, confirmation in columns.items():
                action = confirmation.get("action")
                print(f"[DEBUG] 处理字段: {table_name}.{column_name}, action={action}")

                if action in ["accept", "custom"]:
                    selected = confirmation.get("selected_candidate")
                    print(f"[DEBUG] selected_candidate: {selected}")

                    # 获取源字段类型（从 field_profiles_json 中提取）
                    profile_key = f"{table_name}.{column_name}"
                    source_profile = field_profiles.get(profile_key, {})
                    source_column_type = source_profile.get("column_type", "")

                    # 兜底：如果从 profile 获取不到，尝试从 selected_candidate 获取
                    # 当 selected 是 LLM 生成的候选项时，它的 table_name 和 column_name 就是源表/源字段
                    # 此时它的 column_type 就是源字段类型
                    if not source_column_type and selected:
                        # 检查 selected 是否就是源字段自身（LLM 生成的情况）
                        if selected.get("table_name") == table_name and selected.get("column_name") == column_name:
                            source_column_type = selected.get("column_type", "")
                        # 或者尝试从 source_column_type 字段获取（如果前端传了的话）
                        if not source_column_type:
                            source_column_type = selected.get("source_column_type", "")

                    print(f"[DEBUG] profile_key={profile_key}, source_column_type={source_column_type}")

                    # 判断候选项的来源类型
                    candidate_source_type = ""
                    if selected:
                        candidate_source_type = selected.get("source_type", "")
                        # 兜底：如果 source_type 为空，尝试从 source 字段推断
                        if not candidate_source_type:
                            source_str = selected.get("source", "")
                            if source_str.startswith("llm:"):
                                candidate_source_type = "llm"
                            elif source_str.startswith("dict:"):
                                candidate_source_type = "dict"
                            elif source_str.startswith("vector:"):
                                candidate_source_type = "vector"
                            elif "." in source_str and not source_str.startswith("llm"):
                                # 格式如 "ref_order_master.user_id"，来自参考表
                                candidate_source_type = "ref_table"
                    print(f"[DEBUG] candidate_source_type={candidate_source_type} (推断自 source={selected.get('source', '') if selected else ''})")

                    # 确定映射类型
                    if action == "custom":
                        mapping_type = "user_defined"
                        print(f"[DEBUG] 进入分支: custom")
                    elif candidate_source_type == "llm":
                        mapping_type = "llm_generated"
                        print(f"[DEBUG] 进入分支: llm")
                    elif candidate_source_type == "dict":
                        mapping_type = "dict_match"
                        print(f"[DEBUG] 进入分支: dict")
                    elif candidate_source_type in ["ref_table", "vector"]:
                        # 从参考表匹配的，根据置信度细分
                        if selected and selected.get("confidence", 0) >= 0.9:
                            mapping_type = "exact_match"
                        else:
                            mapping_type = "semantic_match"
                        print(f"[DEBUG] 进入分支: ref_table/vector")
                    else:
                        mapping_type = "semantic_match"
                        print(f"[DEBUG] 进入分支: else (default)")

                    # 创建或更新字段映射记录（按 job_id 查询，避免跨任务冲突）
                    mapping = FieldMapping.query.filter_by(
                        datasource_id=datasource_id,
                        schema_hash=schema_hash,
                        source_table=table_name,
                        source_column=column_name,
                        source_job_id=job_id
                    ).first()

                    if not mapping:
                        mapping = FieldMapping(
                            datasource_id=datasource_id,
                            schema_hash=schema_hash,
                            source_table=table_name,
                            source_column=column_name,
                            source_job_id=job_id
                        )
                        db.session.add(mapping)
                        result["created_mappings"] += 1

                    # 设置源字段类型
                    mapping.source_type = source_column_type

                    # 根据不同情况设置目标字段信息
                    if action == "custom":
                        # 用户自定义注释：没有目标表映射，设为自身
                        print(f"[DEBUG] 设置目标: action=custom, 使用自身")
                        mapping.target_table = table_name
                        mapping.target_column = column_name
                        mapping.target_type = source_column_type
                        mapping.mapping_type = mapping_type
                        mapping.confidence = 1.0
                        mapping.mapping_basis = {
                            "user_custom": True,
                            "custom_comment": confirmation.get("custom_comment")
                        }
                    elif candidate_source_type in ["llm", "dict"]:
                        # LLM生成或字典匹配的注释：没有真正的目标表映射，设为自身
                        print(f"[DEBUG] 设置目标: source_type={candidate_source_type}, 使用自身")
                        mapping.target_table = table_name
                        mapping.target_column = column_name
                        mapping.target_type = source_column_type
                        mapping.mapping_type = mapping_type
                        mapping.confidence = selected.get("confidence", 0.0) if selected else 0.0
                        mapping.mapping_basis = {
                            "source": selected.get("source") if selected else None,
                            "source_type": candidate_source_type,
                            "column_comment": selected.get("column_comment", "") if selected else "",
                            "reasoning": selected.get("reasoning", "") if selected else "",
                            "is_self_reference": True  # 标记为自引用（无跨表映射）
                        }
                    elif selected:
                        # 从参考表匹配的注释：有真正的目标表映射
                        print(f"[DEBUG] 设置目标: 从 selected 提取")
                        target_table = selected.get("table_name") or selected.get("target_table") or ""
                        target_column = selected.get("column_name") or selected.get("target_column") or ""
                        target_type = selected.get("column_type") or selected.get("target_type") or ""

                        # 兜底：如果目标信息为空，使用源表/字段自身
                        if not target_table or not target_column:
                            print(f"[DEBUG] 目标信息为空，使用自身作为兜底")
                            target_table = table_name
                            target_column = column_name
                            target_type = source_column_type

                        mapping.target_table = target_table
                        mapping.target_column = target_column
                        mapping.target_type = target_type
                        mapping.mapping_type = mapping_type
                        mapping.confidence = selected.get("confidence", 0.0)
                        mapping.mapping_basis = {
                            "source": selected.get("source"),
                            "source_type": candidate_source_type,
                            "scores": selected.get("scores", {}),
                            "reasoning": selected.get("reasoning", ""),
                            "column_comment": selected.get("column_comment", ""),
                            "is_self_reference": (target_table == table_name and target_column == column_name)
                        }

                    print(f"[字段映射] {table_name}.{column_name} -> {mapping.target_table}.{mapping.target_column} "
                          f"(source_type={mapping.source_type}, target_type={mapping.target_type}, "
                          f"mapping_type={mapping.mapping_type}, candidate_source={candidate_source_type})")

        # 5. 更新数据卡的字段注释
        updated_tables = set()
        for table_name, columns in confirmations.items():
            for column_name, confirmation in columns.items():
                action = confirmation.get("action")

                if action in ["accept", "custom"]:
                    # 获取最终的注释
                    final_comment = ""
                    if action == "custom":
                        final_comment = confirmation.get("custom_comment", "")
                    elif action == "accept":
                        selected = confirmation.get("selected_candidate")
                        if selected:
                            final_comment = selected.get("column_comment", "")

                    if final_comment:
                        # 更新数据卡
                        success = _update_datacard_field_comment(
                            datasource_id, table_name, column_name, final_comment
                        )
                        if success:
                            updated_tables.add(table_name)

        result["updated_datacards"] = len(updated_tables)

        # 6. 提交事务
        db.session.commit()

        result["success"] = True
        print(f"[字段推荐确认] 完成，更新字段: {result['updated_fields']}, "
              f"创建映射: {result['created_mappings']}, 更新数据卡: {result['updated_datacards']}")

    except Exception as e:
        db.session.rollback()
        result["errors"].append(str(e))
        print(f"[字段推荐确认] 失败: {e}")

    return result


def confirm_table_relationships(
    job_id: str,
    datasource_id: str,
    schema_hash: str,
    confirmations: List[Dict[str, Any]],
    datasource_schema_map: Dict[str, str] = None
) -> Dict[str, Any]:
    """
    确认表关系推断结果（支持同源和跨源）

    Args:
        job_id: 任务ID
        datasource_id: 主数据源ID（同源时使用）
        schema_hash: 主数据源的Schema哈希值（同源时使用）
        confirmations: 用户确认的表关系列表
            [
                {
                    "from_table": "target_user_address",
                    "from_column": "user_id",
                    "from_datasource_id": "uuid-xxx",  # 跨源时必填
                    "from_schema_hash": "hash-xxx",    # 跨源时必填
                    "to_table": "users",
                    "to_column": "id",
                    "to_datasource_id": "uuid-yyy",    # 跨源时必填
                    "to_schema_hash": "hash-yyy",      # 跨源时必填
                    "relationship_type": "foreign_key",
                    "confidence": 0.85,
                    "action": "accept" or "reject",
                    "user_notes": "用户备注"
                }
            ]
        datasource_schema_map: 数据源ID到schema_hash的映射（跨源时使用）
            {"datasource_id_1": "schema_hash_1", "datasource_id_2": "schema_hash_2"}

    Returns:
        {
            "success": True,
            "created_relationships": 5,
            "created_cards": 2
        }
    """
    print(f"[表关系确认] 开始处理，任务ID: {job_id}")

    result = {
        "success": False,
        "created_relationships": 0,
        "created_cards": 0,
        "updated_cards": 0,
        "errors": []
    }

    # 初始化 datasource_schema_map
    if datasource_schema_map is None:
        datasource_schema_map = {}
    # 确保主数据源在映射中
    datasource_schema_map[datasource_id] = schema_hash

    try:
        # 1. 获取任务结果
        job_result = TargetInventoryJobResult.query.filter_by(job_id=job_id).first()
        if not job_result:
            result["errors"].append(f"任务结果不存在: {job_id}")
            return result

        # 2. 从任务结果中构建完整关系映射（用于获取增强字段）
        inferred_relationships = job_result.table_relationships_json or {}
        relationships_list = inferred_relationships.get("relationships", [])

        # 构建关系映射：以 (from_table, from_column, to_table, to_column) 为键
        relationship_map = {}
        for rel in relationships_list:
            key = (
                rel.get("from_table", ""),
                rel.get("from_column", ""),
                rel.get("to_table", ""),
                rel.get("to_column", "")
            )
            relationship_map[key] = rel

        # 3. 更新 confirm_json
        if not job_result.confirm_json:
            job_result.confirm_json = {}

        job_result.confirm_json["table_relationships"] = confirmations
        job_result.confirm_json["relationships_confirmed_at"] = datetime.now(tz_cst).isoformat()
        # 标记 JSON 字段已修改，确保 SQLAlchemy 能检测到变化
        flag_modified(job_result, "confirm_json")

        # 4. 过滤出用户接受的关系，并合并增强字段
        accepted_relationships = []
        for rel in confirmations:
            if rel.get("action") == "accept":
                # 尝试从任务结果中获取完整的增强字段
                key = (
                    rel.get("from_table", ""),
                    rel.get("from_column", ""),
                    rel.get("to_table", ""),
                    rel.get("to_column", "")
                )
                full_rel = relationship_map.get(key, {})

                # 合并数据：使用简化的确认数据，覆盖增强字段
                merged_rel = {**rel}
                if full_rel:
                    # 从完整关系中复制增强字段
                    if "business_relation" in full_rel:
                        merged_rel["business_relation"] = full_rel["business_relation"]
                    if "join_suggestion" in full_rel:
                        merged_rel["join_suggestion"] = full_rel["join_suggestion"]
                    if "fusion_suggestion" in full_rel:
                        merged_rel["fusion_suggestion"] = full_rel["fusion_suggestion"]
                    # 如果完整关系中没有基数，尝试从确认数据中获取
                    if not merged_rel.get("cardinality") and full_rel.get("cardinality"):
                        merged_rel["cardinality"] = full_rel["cardinality"]

                accepted_relationships.append(merged_rel)

        # 5. 持久化到 table_relationship 表
        for rel in accepted_relationships:
            from_table = rel.get("from_table")
            to_table = rel.get("to_table")

            # 获取各表的数据源ID和schema_hash
            from_ds_id = rel.get("from_datasource_id") or datasource_id
            to_ds_id = rel.get("to_datasource_id") or datasource_id
            from_schema = rel.get("from_schema_hash") or datasource_schema_map.get(from_ds_id, schema_hash)
            to_schema = rel.get("to_schema_hash") or datasource_schema_map.get(to_ds_id, schema_hash)

            # 判断是否跨源
            is_cross_source = (from_ds_id != to_ds_id)

            # 统一表对的顺序（按 datasource_id + table_name 字典序）
            from_key = f"{from_ds_id}:{from_table}"
            to_key = f"{to_ds_id}:{to_table}"

            if from_key > to_key:
                # 交换顺序，确保 table_a 始终是字典序较小的
                table_a, table_b = to_table, from_table
                table_a_ds_id, table_b_ds_id = to_ds_id, from_ds_id
                table_a_schema, table_b_schema = to_schema, from_schema
            else:
                table_a, table_b = from_table, to_table
                table_a_ds_id, table_b_ds_id = from_ds_id, to_ds_id
                table_a_schema, table_b_schema = from_schema, to_schema

            # 检查是否已存在（增加 source_job_id 条件）
            existing = TableRelationship.query.filter_by(
                table_a_datasource_id=table_a_ds_id,
                table_a_schema_hash=table_a_schema,
                table_a=table_a,
                table_b_datasource_id=table_b_ds_id,
                table_b_schema_hash=table_b_schema,
                table_b=table_b,
                source_job_id=job_id  # ✅ 新增：按任务隔离
            ).first()

            if not existing:
                # 创建新的表关系记录
                relationship = TableRelationship(
                    table_a=table_a,
                    table_a_datasource_id=table_a_ds_id,
                    table_a_schema_hash=table_a_schema,
                    table_b=table_b,
                    table_b_datasource_id=table_b_ds_id,
                    table_b_schema_hash=table_b_schema,
                    is_cross_source=is_cross_source,
                    source_type='target_inventory',  # ✅ 新增：标识来源
                    source_job_id=job_id,            # ✅ 新增：关联任务
                    relationship_type=rel.get("relationship_type", "Semantic"),
                    join_conditions=[{
                        "from_table": rel.get("from_table"),
                        "from_column": rel.get("from_column"),
                        "to_table": rel.get("to_table"),
                        "to_column": rel.get("to_column"),
                        "confidence": rel.get("confidence", 0.0),
                        "reasoning": rel.get("reasoning", "")
                    }],
                    relationship_strength=rel.get("confidence", 0.0),
                    cardinality=_infer_cardinality(rel)
                )
                db.session.add(relationship)
                result["created_relationships"] += 1
            else:
                # 更新已有的关系（添加新的join条件）
                join_conditions = existing.join_conditions or []
                join_conditions.append({
                    "from_table": rel.get("from_table"),
                    "from_column": rel.get("from_column"),
                    "to_table": rel.get("to_table"),
                    "to_column": rel.get("to_column"),
                    "confidence": rel.get("confidence", 0.0),
                    "reasoning": rel.get("reasoning", "")
                })
                existing.join_conditions = join_conditions

                # 更新关系强度（取平均值）
                avg_confidence = sum(jc.get("confidence", 0) for jc in join_conditions) / len(join_conditions)
                existing.relationship_strength = avg_confidence

        # 6. 生成标准格式的关系卡片（复用全域盘点的卡片生成逻辑）
        cards_created, cards_updated = _generate_standard_relationship_cards(
            accepted_relationships=accepted_relationships,
            job_id=job_id,
            datasource_id=datasource_id,
            schema_hash=schema_hash,
            datasource_schema_map=datasource_schema_map
        )
        result["created_cards"] = cards_created
        result["updated_cards"] = cards_updated

        # 7. 提交事务
        db.session.commit()

        result["success"] = True
        print(f"[表关系确认] 完成，创建关系: {result['created_relationships']}, "
              f"创建卡片: {result['created_cards']}, 更新卡片: {result['updated_cards']}")

    except Exception as e:
        db.session.rollback()
        result["errors"].append(str(e))
        print(f"[表关系确认] 失败: {e}")
        import traceback
        traceback.print_exc()

    return result


def _update_datacard_field_comment(
    datasource_id: str,
    table_name: str,
    column_name: str,
    comment: str
) -> bool:
    """
    更新数据卡的字段注释

    Returns:
        True if successful, False otherwise
    """
    try:
        # 查找数据卡
        datacard = DataCardDataSource.query.filter_by(
            datasource_id=datasource_id,
            table_name=table_name
        ).first()

        if not datacard:
            print(f"[更新数据卡] 数据卡不存在: {table_name}")
            return False

        # 更新字段注释
        card_data = datacard.card_data or {}

        # 处理 card_data 可能是 JSON 字符串的情况
        if isinstance(card_data, str):
            try:
                card_data = json.loads(card_data)
            except json.JSONDecodeError:
                print(f"[更新数据卡] 失败: card_data 不是有效的 JSON 字符串")
                return False

        # columns 在 SQLMeta.columns 路径下
        sql_meta = card_data.get("SQLMeta", {})
        if isinstance(sql_meta, str):
            try:
                sql_meta = json.loads(sql_meta)
            except json.JSONDecodeError:
                print(f"[更新数据卡] 失败: SQLMeta 不是有效的 JSON 字符串")
                return False

        columns = sql_meta.get("columns", [])

        # 处理 columns 可能是 JSON 字符串的情况
        if isinstance(columns, str):
            try:
                columns = json.loads(columns)
            except json.JSONDecodeError:
                print(f"[更新数据卡] 失败: columns 不是有效的 JSON 字符串")
                return False

        if not isinstance(columns, list):
            print(f"[更新数据卡] 失败: columns 不是列表类型，实际类型: {type(columns)}")
            return False

        for col in columns:
            if not isinstance(col, dict):
                print(f"[更新数据卡] 跳过非字典类型的列: {type(col)}")
                continue
            if col.get("name") == column_name:
                col["comment"] = comment
                col["comment_updated_at"] = datetime.now(tz_cst).isoformat()
                break

        sql_meta["columns"] = columns
        card_data["SQLMeta"] = sql_meta
        # 保存时需要转回 JSON 字符串
        datacard.card_data = json.dumps(card_data, ensure_ascii=False)

        print(f"[更新数据卡] 更新字段注释: {table_name}.{column_name}")
        return True

    except Exception as e:
        print(f"[更新数据卡] 失败: {e}")
        return False


def _infer_cardinality(relationship: Dict[str, Any]) -> str:
    """
    推断关系的基数

    Returns:
        "one_to_one", "one_to_many", "many_to_one", or "many_to_many"
    """
    # 简化处理：基于外键关系推断
    rel_type = relationship.get("relationship_type", "")

    if rel_type == "foreign_key":
        # 外键关系通常是 many_to_one
        return "many_to_one"

    # 其他关系默认为 many_to_many
    return "many_to_many"


def _infer_entity_name(table_name: str) -> str:
    """
    从表名推断业务实体名称（中文）
    """
    if not table_name:
        return ""

    import re
    # 移空前缀后缀
    core = re.sub(r'^(tbl?|tab_?)?', '', table_name, flags=re.IGNORECASE)
    core = re.sub(r'_?(?:tb|table)$', '', core, flags=re.IGNORECASE)
    core = core.strip('_')

    # 常见实体映射
    entity_map = {
        "user": "用户", "member": "会员", "customer": "客户",
        "order": "订单", "product": "商品", "goods": "商品", "item": "商品项",
        "category": "分类", "address": "地址", "payment": "支付",
        "cart": "购物车", "store": "店铺", "shop": "店铺", "merchant": "商户",
        "inventory": "库存", "stock": "库存", "logistics": "物流", "delivery": "配送",
        "coupon": "优惠券", "promotion": "促销", "comment": "评论", "review": "评价",
        "message": "消息", "notification": "通知", "log": "日志", "record": "记录",
        "config": "配置", "setting": "设置", "department": "部门", "employee": "员工",
        "role": "角色", "permission": "权限", "menu": "菜单", "file": "文件",
        "image": "图片", "attachment": "附件", "role": "角色",
        "sender": "发送者", "receiver": "接收者", "admin": "管理员"
    }

    core_lower = core.lower()
    for key, value in entity_map.items():
        if key in core_lower:
            return value

    return core if core else table_name


def _generate_standard_relationship_cards(
    accepted_relationships: List[Dict[str, Any]],
    job_id: str,
    datasource_id: str,
    schema_hash: str,
    datasource_schema_map: Dict[str, str]
) -> Tuple[int, int]:
    """
    生成标准格式的关系卡片（与全域盘点格式一致）

    Args:
        accepted_relationships: 用户确认的关系列表
        job_id: 任务ID
        datasource_id: 主数据源ID
        schema_hash: Schema哈希
        datasource_schema_map: 数据源到schema_hash的映射

    Returns:
        (created_count, updated_count)
    """
    from models.datacards_datasource import DataCardDataSource

    created_count = 0
    updated_count = 0

    # 按表分组关系
    table_relationships_map = {}  # key: (datasource_id, schema_hash, table_name)

    for rel in accepted_relationships:
        from_table = rel.get("from_table")
        to_table = rel.get("to_table")
        from_ds_id = rel.get("from_datasource_id") or datasource_id
        to_ds_id = rel.get("to_datasource_id") or datasource_id
        from_schema = rel.get("from_schema_hash") or datasource_schema_map.get(from_ds_id, schema_hash)
        to_schema = rel.get("to_schema_hash") or datasource_schema_map.get(to_ds_id, schema_hash)

        # from_table 的卡片
        from_key = (from_ds_id, from_schema, from_table)
        if from_key not in table_relationships_map:
            table_relationships_map[from_key] = {"rels": [], "related_ds_ids": set()}
        table_relationships_map[from_key]["rels"].append(rel)
        if from_ds_id != to_ds_id:
            table_relationships_map[from_key]["related_ds_ids"].add(to_ds_id)

        # to_table 的卡片
        to_key = (to_ds_id, to_schema, to_table)
        if to_key not in table_relationships_map:
            table_relationships_map[to_key] = {"rels": [], "related_ds_ids": set()}
        table_relationships_map[to_key]["rels"].append(rel)
        if from_ds_id != to_ds_id:
            table_relationships_map[to_key]["related_ds_ids"].add(from_ds_id)

    # 为每张表创建标准格式的卡片
    for (ds_id, s_hash, table_name), data in table_relationships_map.items():
        rels = data["rels"]
        related_ds_ids = list(data["related_ds_ids"])
        has_cross_source = len(related_ds_ids) > 0

        # 按关联表分组关系
        related_tables_map = {}
        for rel in rels:
            # 确定对方表
            if rel.get("from_table") == table_name:
                related_table = rel.get("to_table")
            else:
                related_table = rel.get("from_table")

            if related_table not in related_tables_map:
                related_tables_map[related_table] = []
            related_tables_map[related_table].append(rel)

        # 构建 Relationships 列表
        relationships_list = []
        for related_table, table_rels in related_tables_map.items():
            # 计算平均置信度
            avg_confidence = sum(r.get("confidence", 0) for r in table_rels) / len(table_rels)

            # 推断主要基数关系
            cardinalities = [_infer_cardinality(r) for r in table_rels]
            main_cardinality = max(set(cardinalities), key=cardinalities.count)

            # 构建 join_fields
            join_fields = []
            for rel in table_rels:
                if rel.get("from_table") == table_name:
                    join_fields.append({
                        "local_field": rel.get("from_column"),
                        "remote_field": rel.get("to_column"),
                        "confidence": rel.get("confidence", 0),
                        "relationship_type": rel.get("relationship_type", "semantic")
                    })
                else:
                    join_fields.append({
                        "local_field": rel.get("to_column"),
                        "remote_field": rel.get("from_column"),
                        "confidence": rel.get("confidence", 0),
                        "relationship_type": rel.get("relationship_type", "semantic")
                    })

            # 获取跨源信息
            is_cross = any(
                (r.get("from_datasource_id") or datasource_id) != (r.get("to_datasource_id") or datasource_id)
                for r in table_rels
            )
            related_ds_id = None
            if is_cross:
                for r in table_rels:
                    if r.get("from_table") == table_name:
                        related_ds_id = r.get("to_datasource_id")
                    else:
                        related_ds_id = r.get("from_datasource_id")
                    if related_ds_id:
                        break

            # 获取增强字段（从传入的关系对象中提取）
            business_relation = rel.get("business_relation", {})
            join_suggestion = rel.get("join_suggestion", {})
            fusion_suggestion = rel.get("fusion_suggestion", {})

            # 如果没有增强字段，基于规则生成默认值
            if not join_suggestion:
                join_type = "LEFT JOIN" if main_cardinality in ["many_to_one", "one_to_many"] else "INNER JOIN"
                join_suggestion = {
                    "recommended_join_type": join_type,
                    "join_conditions": [
                        {
                            "from_column": rel.get("from_column"),
                            "to_column": rel.get("to_column"),
                            "condition": f"{rel.get('from_table')}.{rel.get('from_column')} = {rel.get('to_table')}.{rel.get('to_column')}",
                            "confidence": rel.get("confidence", 0)
                        }
                    ],
                    "use_cases": []
                }

            if not business_relation:
                # 推断实体名称
                from_entity = _infer_entity_name(rel.get("from_table", ""))
                to_entity = _infer_entity_name(rel.get("to_table", ""))
                business_relation = {
                    "from_entity": from_entity,
                    "to_entity": to_entity,
                    "relation_description": "",
                    "from_role": "detail" if main_cardinality == "many_to_one" else "master",
                    "to_role": "master" if main_cardinality == "many_to_one" else "detail"
                }

            if not fusion_suggestion:
                # 根据基数关系推断主从表
                if main_cardinality == "many_to_one":
                    primary_table = rel.get("to_table")
                    secondary_table = rel.get("from_table")
                elif main_cardinality == "one_to_many":
                    primary_table = rel.get("from_table")
                    secondary_table = rel.get("to_table")
                else:
                    primary_table = rel.get("to_table")
                    secondary_table = rel.get("from_table")

                fusion_suggestion = {
                    "primary_table": primary_table,
                    "secondary_table": secondary_table,
                    "aggregation_hint": "",
                    "fusion_strategy": ""
                }

            relationships_list.append({
                "related_table": related_table,
                "relationship_type": main_cardinality,
                "confidence": round(avg_confidence, 4),
                "join_fields": join_fields,
                "join_suggestion": join_suggestion,
                "business_relation": business_relation,
                "fusion_suggestion": fusion_suggestion,
                "is_cross_source": is_cross,
                "related_datasource_id": str(related_ds_id) if related_ds_id else None,
                "related_datasource_name": ""  # 可以从数据源表查询
            })

        # 按置信度排序
        relationships_list.sort(key=lambda x: x["confidence"], reverse=True)

        # 获取表的字段信息
        fields_count = 0
        primary_key = "id"
        try:
            datacard = DataCardDataSource.query.filter_by(
                datasource_id=ds_id,
                table_name=table_name
            ).first()
            if datacard:
                card_data = datacard.card_data
                if isinstance(card_data, str):
                    card_data = json.loads(card_data)
                sql_meta = card_data.get("SQLMeta", {})
                columns = sql_meta.get("columns", [])
                fields_count = len(columns)
                # 推断主键
                for col in columns:
                    if col.get("name", "").lower() == "id":
                        primary_key = col.get("name", "id")
                        break
        except Exception as e:
            print(f"[卡片生成] 获取表 {table_name} 字段信息失败: {e}")

        # 生成摘要和提示
        join_summary = f"表 {table_name} 与 {len(relationships_list)} 张表存在关联关系"
        if len(relationships_list) > 0:
            top_tables = [r["related_table"] for r in relationships_list[:3]]
            join_summary += f"，主要关联: {', '.join(top_tables)}"
            if len(relationships_list) > 3:
                join_summary += " 等"

        fusion_hints = {
            "as_master": [],
            "as_detail": [],
            "common_joins": []
        }

        # 构建标准格式卡片
        card_data = {
            "DocInfo": {
                "doc_id": f"rel_card_{ds_id}_{table_name}_{job_id}",
                "title": f"关系卡片: {table_name}",
                "source_type": "relationship",
                "datasource_id": str(ds_id),
                "schema_name": datasource_schema_map.get(str(ds_id), {}).get("schema_name", "public") if isinstance(datasource_schema_map.get(str(ds_id)), dict) else "public",
                "table_name": table_name,
                "created_at": datetime.now(tz_cst).isoformat()
            },
            "TableInfo": {
                "table_name": table_name,
                "fields_count": fields_count,
                "primary_key": primary_key
            },
            "Relationships": relationships_list,
            "FusionHints": fusion_hints,
            "JoinSummary": join_summary,
            "Statistics": {
                "related_tables_count": len(relationships_list),
                "total_join_fields": sum(len(r["join_fields"]) for r in relationships_list),
                "avg_confidence": round(
                    sum(r["confidence"] for r in relationships_list) / len(relationships_list), 4
                ) if relationships_list else 0
            }
        }

        # 查询或创建卡片（增加 source_job_id 条件）
        card = TableRelationshipCard.query.filter_by(
            datasource_id=ds_id,
            schema_hash=s_hash,
            table_name=table_name,
            source_job_id=job_id  # ✅ 按任务隔离
        ).first()

        if not card:
            card = TableRelationshipCard(
                datasource_id=ds_id,
                schema_hash=s_hash,
                table_name=table_name,
                source_type='target_inventory',  # ✅ 标识来源
                source_job_id=job_id,            # ✅ 关联任务
                card_data=card_data,
                has_cross_source_relations=has_cross_source,
                related_datasource_ids=related_ds_ids if related_ds_ids else None
            )
            db.session.add(card)
            created_count += 1
        else:
            # 更新卡片
            card.card_data = card_data
            card.has_cross_source_relations = has_cross_source
            if related_ds_ids:
                existing_related = card.related_datasource_ids or []
                card.related_datasource_ids = list(set(existing_related + related_ds_ids))
            card.version = (card.version or 0) + 1
            updated_count += 1

    return created_count, updated_count
