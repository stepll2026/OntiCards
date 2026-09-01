"""
 @File: target_inventory_service.py
 @Description: 定向盘点服务 - 分离字段推荐和表关系推断两个模块
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-02-02
 @Update: 2026-02-02 - 合并工具函数，移除V2后缀
"""

from __future__ import annotations
import json
import os
import traceback
from typing import Dict, List, Any
from decimal import Decimal
from datetime import datetime
from flask_login import current_user
from sqlalchemy import create_engine

from extensions.ext_database import db
from models.global_inventory import TargetInventoryJob, TargetInventoryJobResult, FieldMapping
from models.datasource_infos import DatasourceInfo
from models.datacards_datasource import DataCardDataSource

from controllers.target_inventory.field_recommendation import recommend_field_annotations
from controllers.target_inventory.table_relationship_inference import infer_table_relationships
from controllers.target_inventory.relationship_card_generator import generate_relationship_cards
from controllers.target_inventory.ref_builder import build_ref_entries_from_datacards, upsert_entries_to_field_index
from controllers.target_inventory.dict_file_api import parse_dict_file, DICT_UPLOAD_FOLDER
from controllers.target_inventory.utils import _safe_load_card, extract_connect_and_table
from controllers.weaviate_db_tool.weaviate_api import delete_by_uuid, add_vector, weaviate_client, _field_index_class_name


# ==================== 工具函数 ====================

def _get_latest_datacard(datasource_id: str, table_name: str) -> DataCardDataSource | None:
    """
    根据 datasource_id 和 table_name 获取最新的数据卡片

    Args:
        datasource_id: 数据源ID（而不是 connect_name）
        table_name: 表名

    Returns:
        最新的数据卡片记录，如果不存在则返回 None
    """
    # 优先使用新字段查询（性能更好）
    result = (
        db.session.query(DataCardDataSource)
        .filter(
            DataCardDataSource.datasource_id == datasource_id,
            DataCardDataSource.table_name == table_name
        )
        .order_by(DataCardDataSource.updated_at.desc())
        .first()
    )

    # 如果新字段查询没有结果，回退到旧的全表扫描方式（向后兼容）
    if not result:
        print(f"[WARN] 使用新字段查询未找到数据卡片，回退到旧方式查询 (datasource_id={datasource_id}, table_name={table_name})")
        # 通过 datasource_id 获取 connect_name
        ds = db.session.query(DatasourceInfo).filter(DatasourceInfo.id == datasource_id).first()
        if not ds:
            return None

        connect_name = ds.connect_name
        rows = (
            db.session.query(DataCardDataSource)
            .order_by(DataCardDataSource.updated_at.desc())
            .all()
        )
        for r in rows:
            card = _safe_load_card(r)
            cn, tn = extract_connect_and_table(card)
            if cn == connect_name and tn == table_name:
                return r
        return None

    return result


def check_and_reuse_field_index(datasource_id: str, schema_hash: str, user_class: str) -> dict:
    """
    检查 FieldIndex 是否已存在且可复用

    返回：
    {
        "exists": true/false,
        "entry_count": 123,
        "can_reuse": true/false
    }
    """
    from weaviate.classes.query import Filter
    idx_class = _field_index_class_name(user_class)

    with weaviate_client() as client:
        if not client.collections.exists(idx_class):
            return {"exists": False, "can_reuse": False, "entry_count": 0}

        collection = client.collections.get(idx_class)

        # 查询该 datasource_id + schema_hash 的条目数
        f = (
            Filter.by_property("object_type").equal("field_entry") &
            Filter.by_property("datasource_id").equal(str(datasource_id)) &
            Filter.by_property("schema_hash").equal(str(schema_hash))
        )

        result = collection.aggregate.over_all(
            filters=f,
            total_count=True
        )

        entry_count = result.total_count or 0

        if entry_count > 0:
            print(f"[FieldIndex] 检测到已有索引，条目数: {entry_count}")
            return {"exists": True, "can_reuse": True, "entry_count": entry_count}
        else:
            return {"exists": True, "can_reuse": False, "entry_count": 0}


def build_query_text(table_name: str, column_name: str, column_type: str, profile: dict) -> str:
    """
    构造规范的 query_text，包含完整画像信息
    """
    type_hint = profile.get("type_hint", "unknown")
    format_hint = profile.get("format_hint", "")
    top_values = profile.get("top_values", [])

    # 格式化 top_values
    top_str = ", ".join([f"{v.get('v')}({v.get('cnt')}次)" for v in top_values[:3]])

    parts = [
        f"表 {table_name}",
        f"字段 {column_name}",
        f"类型 {column_type}",
        f"画像类型 {type_hint}"
    ]

    if format_hint:
        parts.append(f"格式 {format_hint}")

    if top_str:
        parts.append(f"高频值 {top_str}")

    parts.append("目标：匹配语义相近的字段注释")

    return "。".join(parts) + "。"


# ==================== 确认服务 ====================

def confirm_field_mappings(
    datasource_id: str,
    schema_hash: str,
    confirmed_mappings: list,
    job_id: str = None
) -> dict:
    """
    用户确认字段映射后，将最终结果保存到 FieldMapping 表

    Args:
        datasource_id: 数据源ID
        schema_hash: Schema哈希值
        confirmed_mappings: 用户确认的映射列表
        job_id: 任务ID（可选，用于记录）

    Returns:
        {"deleted": N, "inserted": M, "status": "success"}
    """
    try:
        # 步骤1: 删除旧的字段映射数据（按 job_id 删除，避免误删其他任务的数据）
        if job_id:
            deleted_count = FieldMapping.query.filter(
                FieldMapping.datasource_id == datasource_id,
                FieldMapping.schema_hash == schema_hash,
                FieldMapping.source_job_id == job_id
            ).delete()
        else:
            # 如果没有 job_id，按 datasource_id + schema_hash 删除（兼容旧逻辑）
            deleted_count = FieldMapping.query.filter(
                FieldMapping.datasource_id == datasource_id,
                FieldMapping.schema_hash == schema_hash
            ).delete()

        print(f"[ConfirmFieldMapping] 删除旧数据: {deleted_count} 条")

        # 步骤2: 构建新的映射记录
        field_mapping_records = []

        for mapping in confirmed_mappings:
            try:
                # 验证必填字段
                required_fields = ["source_table", "source_column", "target_table", "target_column"]
                for field in required_fields:
                    if not mapping.get(field):
                        print(f"[ConfirmFieldMapping] 警告: 映射记录缺少必填字段 {field}，跳过")
                        continue

                # 创建记录
                record = FieldMapping(
                    datasource_id=datasource_id,
                    schema_hash=schema_hash,
                    source_job_id=job_id,  # 添加 job_id
                    source_table=mapping["source_table"],
                    source_column=mapping["source_column"],
                    source_type=mapping.get("source_type"),
                    target_table=mapping["target_table"],
                    target_column=mapping["target_column"],
                    target_type=mapping.get("target_type"),
                    mapping_type=mapping.get("mapping_type", "semantic_match"),
                    confidence=Decimal(str(mapping.get("confidence", 0.0))),
                    mapping_basis=mapping.get("mapping_basis", {})
                )

                field_mapping_records.append(record)

            except Exception as e:
                print(f"[ConfirmFieldMapping] 处理映射记录时出错: {e}")
                continue

        # 步骤3: 批量插入
        if field_mapping_records:
            db.session.bulk_save_objects(field_mapping_records)

        db.session.commit()

        inserted_count = len(field_mapping_records)
        print(f"[ConfirmFieldMapping] 插入新数据: {inserted_count} 条")

        # 步骤4: 更新 job_result 的元数据（如果提供了 job_id）
        if job_id:
            result = db.session.query(TargetInventoryJobResult).filter(
                TargetInventoryJobResult.job_id == job_id
            ).first()

            if result:
                if not result.index_meta_json:
                    result.index_meta_json = {}
                result.index_meta_json["field_mapping_confirmed"] = {
                    "confirmed_at": datetime.now().isoformat(),
                    "deleted": deleted_count,
                    "inserted": inserted_count
                }
                db.session.commit()

        return {
            "deleted": deleted_count,
            "inserted": inserted_count,
            "status": "success"
        }

    except Exception as e:
        db.session.rollback()
        print(f"[ConfirmFieldMapping] 确认失败: {e}")
        traceback.print_exc()
        raise e


def apply_confirm(datasource_id: str, table_name: str, doc_id: str, old_wuuid: str, new_card_obj: dict):
    """
    应用字段注释确认（更新数据卡片和向量索引）

    操作顺序（修复版）：
    1. 先添加新向量
    2. 更新数据库记录
    3. 删除旧向量

    这样即使删除旧向量失败，数据也是完整的（新向量已存在）

    Args:
        datasource_id: 数据源ID
        table_name: 表名
        doc_id: 文档ID
        old_wuuid: 旧的向量UUID
        new_card_obj: 新的卡片对象
    """
    user_class = getattr(current_user, "weaviate_class_name", None)

    # 确保DocInfo.doc_id存在
    if not ((new_card_obj.get("DocInfo") or {}).get("doc_id")):
        new_card_obj.setdefault("DocInfo", {})
        if isinstance(new_card_obj["DocInfo"], dict):
            new_card_obj["DocInfo"]["doc_id"] = doc_id

    new_wuuid = None
    _del_ok = False

    try:
        # 步骤1：先添加新向量
        new_wuuid = str(add_vector(new_card_obj, class_name=user_class))
        print(f"[ApplyConfirm] 新向量已添加: doc_id={doc_id}, new_wuuid={new_wuuid}")

        # 步骤2：更新数据库记录
        record = (
            db.session.query(DataCardDataSource)
            .filter(DataCardDataSource.doc_id == str(doc_id))
            .order_by(DataCardDataSource.updated_at.desc())
            .first()
        )
        if not record:
            # 数据库记录不存在，回滚新向量
            try:
                delete_by_uuid(new_wuuid, class_name=user_class)
                print(f"[ApplyConfirm] 数据库记录不存在，已回滚新向量: {new_wuuid}")
            except Exception:
                pass
            raise ValueError("datacard record not found")

        record.card_data = json.dumps(new_card_obj, ensure_ascii=False)
        record.w_uuid = new_wuuid

        # 更新冗余字段（如果存在的话）
        if hasattr(record, 'table_name') and table_name:
            record.table_name = table_name
        if hasattr(record, 'datasource_id') and datasource_id:
            record.datasource_id = datasource_id

        db.session.commit()
        print(f"[ApplyConfirm] 数据库已更新: doc_id={doc_id}")

        # 步骤3：删除旧向量（如果存在）
        # 注意：即使删除失败也不影响整体流程，因为新向量已经生效
        if old_wuuid:
            try:
                _del_ok = delete_by_uuid(old_wuuid, class_name=user_class)
                if _del_ok:
                    print(f"[ApplyConfirm] 旧向量已删除: old_wuuid={old_wuuid}")
                else:
                    print(f"[ApplyConfirm] 旧向量删除失败: old_wuuid={old_wuuid}")
            except Exception as e:
                _del_ok = False
                print(f"[ApplyConfirm] 删除旧向量异常: old_wuuid={old_wuuid}, error={e}")

        return {"delete_old_ok": _del_ok, "old_w_uuid": old_wuuid, "new_w_uuid": new_wuuid}

    except Exception as e:
        # 如果是在添加新向量后、提交数据库前发生异常，需要回滚新向量
        if new_wuuid:
            try:
                delete_by_uuid(new_wuuid, class_name=user_class)
                print(f"[ApplyConfirm] 异常回滚：已删除新向量 {new_wuuid}")
            except Exception as rollback_err:
                print(f"[ApplyConfirm] 回滚失败：无法删除新向量 {new_wuuid}, error={rollback_err}")

        # 确保数据库回滚
        db.session.rollback()
        print(f"[ApplyConfirm] 应用确认失败: {e}")
        raise e


# ==================== 主流程 ====================

def run_target_inventory(
    job_id: str,
    datasource_id: str,
    target_tables: List[str],
    ref_tables: List[str],
    dict_file_id: str = None,
    schema_name: str = None,
    sample_size: int = 100,
    topk: int = 10,
    vector_topn: int = 20
) -> tuple[TargetInventoryJob, TargetInventoryJobResult]:
    """
    定向盘点主流程 - 用户手动选择数据源中的表进行字段注释推荐和表关系确认

    核心改进：
    1. 字段推荐模块：为目标表字段推荐注释（包括LLM注释作为候选）
    2. 表关系推断模块：独立分析所有字段对，不依赖字段推荐结果

    Args:
        job_id: 任务ID
        datasource_id: 数据源ID
        target_tables: 目标表列表
        ref_tables: 参考表列表
        dict_file_id: 字典文件ID
        schema_name: Schema名称
        sample_size: 采样大小
        topk: 返回前K个候选
        vector_topn: 向量召回数量

    Returns:
        (job, job_result)
    """
    print(f"[定向盘点] 开始执行，任务ID: {job_id}")

    # 获取任务和结果记录
    job = TargetInventoryJob.query.filter_by(id=job_id).first()
    if not job:
        raise ValueError(f"任务不存在: {job_id}")

    res = TargetInventoryJobResult.query.filter_by(job_id=job_id).first()
    if not res:
        res = TargetInventoryJobResult(job_id=job_id)
        db.session.add(res)
        db.session.commit()

    # 获取数据源信息
    ds = DatasourceInfo.query.filter_by(id=datasource_id).first()
    if not ds:
        raise ValueError(f"数据源不存在: {datasource_id}")

    schema_hash = job.schema_hash
    user_class = getattr(current_user, "weaviate_class_name", None)

    # ===== Phase 1: 构建参考索引 =====
    print(f"[全域盘点V2] Phase 1: 构建参考索引")

    # 检查是否可以复用已有索引
    cache_info = check_and_reuse_field_index(datasource_id, schema_hash, user_class)

    ref_entries = []
    if cache_info["can_reuse"]:
        print(f"[FieldIndex] 复用已有索引，条目数：{cache_info['entry_count']}")
        # 重新构建 ref_entries 用于规则召回
        ref_datacards = []
        for t in ref_tables:
            r = _get_latest_datacard(datasource_id, t)
            if r:
                ref_datacards.append(r)
        ref_entries = build_ref_entries_from_datacards(ref_datacards, datasource_id=datasource_id, schema_hash=schema_hash)
    else:
        print(f"[FieldIndex] 构建新索引")
        # 构建参考条目
        ref_datacards = []
        for t in ref_tables:
            r = _get_latest_datacard(datasource_id, t)
            if r:
                ref_datacards.append(r)

        ref_entries = build_ref_entries_from_datacards(ref_datacards, datasource_id=datasource_id, schema_hash=schema_hash)

        # 插入向量索引
        inserted = upsert_entries_to_field_index(
            entries=ref_entries,
            user_class=user_class
        )
        print(f"[FieldIndex] 插入 {inserted} 条记录")

    # 加载字典文件条目
    if dict_file_id:
        dict_path = os.path.join(DICT_UPLOAD_FOLDER, dict_file_id)
        if os.path.exists(dict_path):
            try:
                dict_entries = parse_dict_file(dict_path)
                for e in dict_entries:
                    ref_entries.append({
                        "datasource_id": datasource_id,
                        "schema_hash": schema_hash,
                        "source_type": "dict",
                        "table_name": "",
                        "column_name": e["column_name"],
                        "column_type": e.get("column_type", ""),
                        "column_comment": e["column_comment"]
                    })
                print(f"[字典文件] 加载 {len(dict_entries)} 条记录")
            except Exception as e:
                print(f"[字典文件] 加载失败: {e}")

    res.index_meta_json = {
        "reused": cache_info["can_reuse"],
        "entry_count": len(ref_entries),
        "datasource_id": datasource_id,
        "schema_hash": schema_hash
    }
    db.session.commit()

    # ===== Phase 2: 字段推荐模块 =====
    print(f"[全域盘点V2] Phase 2: 字段推荐")

    # 获取目标表的字段信息（包含数据库采样）
    target_fields = _get_target_fields_info(
        datasource_id=datasource_id,
        target_tables=target_tables,
        schema_name=schema_name,
        sample_size=sample_size
    )

    # 获取LLM填充的注释
    llm_annotations = _get_llm_annotations(
        datasource_id=datasource_id,
        target_tables=target_tables
    )

    # 执行字段推荐
    recommendations = recommend_field_annotations(
        target_fields=target_fields,
        ref_entries=ref_entries,
        llm_annotations=llm_annotations,
        topk=topk,
        datasource_id=datasource_id,
        schema_hash=schema_hash,
        vector_topn=vector_topn,
        max_workers=4  # 启用多线程并发优化
    )

    # 从推荐结果中提取字段画像和候选列表
    field_profiles = {}
    candidates_by_field = {}
    for table_name, fields in recommendations.items():
        for column_name, field_data in fields.items():
            key = f"{table_name}.{column_name}"
            # 提取字段画像
            field_profiles[key] = field_data.get("profile", {})
            # 提取候选列表
            candidates_by_field[key] = field_data.get("candidates", [])

    # 保存推荐结果
    res.llm_json = recommendations
    res.field_profiles_json = field_profiles  # 填充字段画像
    res.candidates_json = candidates_by_field  # 填充候选列表
    res.field_mappings_json = {}  # 初始为空，用户确认后才填充
    db.session.commit()

    print(f"[字段推荐] 完成，共推荐 {sum(len(fields) for fields in recommendations.values())} 个字段")

    # ===== Phase 3: 表关系推断模块（独立于字段推荐）=====
    print(f"[全域盘点V2] Phase 3: 表关系推断")

    # 获取目标表和参考表的完整字段信息
    target_tables_info = _get_tables_full_info(datasource_id, target_tables)
    ref_tables_info = _get_tables_full_info(datasource_id, ref_tables)

    # 执行表关系推断（增强版：传递字段画像和缓存配置）
    relationships = infer_table_relationships(
        target_tables_info=target_tables_info,
        ref_tables_info=ref_tables_info,
        confidence_threshold=0.5,
        field_profiles=field_profiles,          # 传递字段画像信息
        schema_hash=schema_hash,                # 传递schema哈希用于缓存
        use_prefilter=True,                     # 启用预筛选
        similarity_threshold=0.1,               # 预筛选相似度阈值（更宽松，减少误过滤）
        max_pairs=100,                          # 最大分析表对数
        use_cache=True,                         # 启用缓存
        parallel=True,                          # 启用多线程并发优化
        max_workers=4                           # 并发工作线程数
    )

    res.table_relationships_json = {"relationships": relationships}
    db.session.commit()

    print(f"[表关系推断] 完成，发现 {len(relationships)} 个关系")

    # ===== Phase 4: 关系卡片生成 =====
    print(f"[全域盘点V2] Phase 4: 关系卡片生成")

    try:
        cards = generate_relationship_cards(
            relationships=relationships,
            datasource_id=datasource_id,
            schema_name=schema_name
        )
        res.relationship_cards_json = {"cards": cards}
        print(f"[关系卡片] 生成 {len(cards)} 个关系卡片")
    except Exception as e:
        print(f"[关系卡片] 生成失败: {e}")
        res.relationship_cards_json = {"cards": [], "error": str(e)}

    db.session.commit()

    # 更新任务状态
    job.status = "completed"
    job.progress = {
        "phase": "completed",
        "field_recommendations": sum(len(fields) for fields in recommendations.values()),
        "table_relationships": len(relationships),
        "relationship_cards": len(cards) if 'cards' in locals() else 0
    }
    db.session.commit()

    print(f"[全域盘点V2] 完成")

    return job, res


def _get_target_fields_info(
    datasource_id: str,
    target_tables: List[str],
    schema_name: str = None,
    sample_size: int = 100
) -> List[Dict[str, Any]]:
    """
    获取目标表的字段信息（包含数据库采样）

    Returns:
        [
            {
                "table_name": "target_user_address",
                "column_name": "user_id",
                "column_type": "bigint",
                "column_comment": "用户ID",
                "sample_values": [...]
            }
        ]
    """
    from controllers.target_inventory.value_profiling import profile_columns

    fields = []

    # 获取数据源连接信息
    ds = DatasourceInfo.query.filter_by(id=datasource_id).first()
    if not ds:
        return fields

    # 创建数据库引擎，配置连接池和超时参数
    engine = create_engine(
        ds.connect_info,
        pool_pre_ping=True,  # 每次使用前检查连接是否有效
        pool_recycle=3600   # 1小时后回收连接
    )

    for table_name in target_tables:
        card_row = _get_latest_datacard(datasource_id, table_name)
        if not card_row:
            continue

        card = json.loads(card_row.card_data) if isinstance(card_row.card_data, str) else (card_row.card_data or {})
        cols = ((card.get("SQLMeta") or {}).get("columns") or [])

        # 获取所有字段名用于采样
        col_names = [col.get("name") for col in cols if col.get("name")]

        # 构建完整表名（带schema）
        if schema_name:
            table_full_name = f'"{schema_name}"."{table_name}"'
        else:
            table_full_name = f'"{table_name}"'

        # 从数据库采样获取字段画像
        profiles = {}
        if col_names:
            try:
                profiles = profile_columns(engine, table_full_name, col_names, sample_size=sample_size)
            except Exception as e:
                print(f"[字段采样] 表 {table_name} 采样失败: {e}")

        for col in cols:
            col_name = col.get("name")
            if not col_name:
                continue

            # 从采样结果中获取样例值
            col_profile = profiles.get(col_name, {})
            sample_values = col_profile.get("sample_values", [])

            fields.append({
                "table_name": table_name,
                "column_name": col_name,
                "column_type": col.get("type", ""),
                "column_comment": col.get("comment", ""),
                "sample_values": sample_values,
                "profile": col_profile  # 附带完整画像信息
            })

    # 关闭数据库连接
    engine.dispose()

    return fields


def _get_llm_annotations(
    datasource_id: str,
    target_tables: List[str]
) -> Dict[str, str]:
    """
    获取LLM填充的注释

    Returns:
        {
            "table_name.column_name": "LLM填充的注释"
        }
    """
    from models.user_datasource_schema import UserDatasourceSchema
    from models.datasource_infos import DatasourceInfo

    # 获取数据源信息
    ds = DatasourceInfo.query.filter_by(id=datasource_id).first()
    if not ds:
        return {}

    llm_annotations = {}

    # 查询 user_datasource_schema 获取 filled_data
    schema_records = (
        db.session.query(UserDatasourceSchema)
        .filter(
            UserDatasourceSchema.user_id == current_user.id,
            UserDatasourceSchema.connect_name == ds.connect_name,
            UserDatasourceSchema.table_name.in_(target_tables)
        )
        .all()
    )

    for rec in schema_records:
        if rec.is_filled and rec.filled_data:
            try:
                filled_data = json.loads(rec.filled_data) if isinstance(rec.filled_data, str) else rec.filled_data
                detailed_fill = filled_data.get("detailed_fill", {})
                filled_map = detailed_fill.get("filled_map", {})

                # filled_map 格式: {field_name: comment}
                for field_name, comment in filled_map.items():
                    key = f"{rec.table_name}.{field_name}"
                    llm_annotations[key] = comment

            except Exception as e:
                print(f"[LLM注释] 解析 filled_data 失败: {e}")

    return llm_annotations


def _get_tables_full_info(
    datasource_id: str,
    tables: List[str]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    获取表的完整字段信息（用于表关系推断）

    Returns:
        {
            "table_name": [
                {
                    "column_name": "user_id",
                    "column_type": "bigint",
                    "column_comment": "用户ID"
                }
            ]
        }
    """
    tables_info = {}

    for table_name in tables:
        card_row = _get_latest_datacard(datasource_id, table_name)
        if not card_row:
            continue

        card = json.loads(card_row.card_data) if isinstance(card_row.card_data, str) else (card_row.card_data or {})
        cols = ((card.get("SQLMeta") or {}).get("columns") or [])

        fields = []
        for col in cols:
            col_name = col.get("name")
            if not col_name:
                continue

            fields.append({
                "column_name": col_name,
                "column_type": col.get("type", ""),
                "column_comment": col.get("comment", "")
            })

        tables_info[table_name] = fields

    return tables_info
