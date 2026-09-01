"""
 @File: datasource_tool.py
 @Description: 工具类：针对数据库中的数据源信息记录
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-10-22 16:01
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Dict, Optional

from flask import Blueprint, request
from flask_login import login_required, current_user
from flask_restful import Resource, Api
from sqlalchemy import func, inspect, make_url
from sqlalchemy.exc import SQLAlchemyError, NoSuchTableError

from controllers.datasource.database_schema_extractor import insert_table_info_to_db, _extract_table_info, get_tables, \
    _get_database_version, get_db_engine, _resolve_schema_name, _add_schema_filter, _has_schema_dim
from controllers.datacard.datacard_generator import generate_datacards_for_schema
from controllers.weaviate_db_tool.weaviate_api import (
    batch_delete_by_uuids, get_total_count, weaviate_client,
    _require_user_class_name, _require_collection_exists,
    delete_field_index_by_datasource
)
from extensions.ext_database import db
from models.user_datasource_schema import UserDatasourceSchema
from models.datacards_datasource import DataCardDataSource
from models.datasource_infos import DatasourceInfo
from models.datasource_term_library import DatasourceTermLibrary
from models.global_inventory import (
    TableRelationship,
    TableRelationshipCard,
    TargetInventoryJob,
    TargetInventoryJobResult,
    FieldMapping
)

# 导入加密模块
from core.connect_info_encryptor import decrypt_connect_info

# ================== Blueprint & Api ==================
datasource_tool_bp = Blueprint("datasource_tool_bp", __name__)
api = Api(datasource_tool_bp)

# ================== 工具函数（统一响应 & JSON 安全） ==================
def _json_safe(obj):
    from datetime import date, datetime
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if hasattr(obj, "_asdict"):
        return obj._asdict()
    return obj

def _deep_json_safe(data):
    import json
    return json.loads(json.dumps(data, default=_json_safe, ensure_ascii=False))

def format_response(data=None, code: int = 200, msg: str = "操作成功"):
    return {"code": code, "msg": msg, "data": _deep_json_safe(data)}, code

def _canon_col(col: dict) -> dict:
    # 只保留与结构稳定相关的字段，统一大小写与空值
    return {
        "name": str(col.get("name", "")).strip(),
        "type": str(col.get("type", "")).strip().lower(),
        "nullable": bool(col.get("nullable", False)),
        "default": (None if col.get("default") in ("", "null", None) else col.get("default")),
        "is_primary": bool(col.get("is_primary", False)),
        "is_foreign": bool(col.get("is_foreign", False)),
        # comment 不参与签名（很多库不稳定、常改注释会触发重建就很烦），若你希望纳入可放开
    }

def _canon_table(info: dict) -> dict:
    """从 _extract_table_info(...) 结果或 schema_text(JSON) 里抽取稳定子集"""
    name = str(info.get("table_name") or info.get("name") or "").strip()
    # 兼容不同字段名：columns / cols / fields
    cols = info.get("columns") or info.get("cols") or info.get("fields") or []
    cols_canon = sorted([_canon_col(c) for c in cols], key=lambda x: x["name"])
    # 主键、索引、外键如果需要纳入签名，也做排序与格式统一再放进来
    pk = sorted([str(k).strip() for k in info.get("primary_keys") or []])
    # 索引、外键根据你的抽取结果结构决定是否纳入（很多方言里容易不稳定，建议先不纳入）
    return {
        "table_name": name,
        "columns": cols_canon,
        "primary_keys": pk,
    }

def _stable_hash_from_info(table_info: dict) -> str:
    canon = _canon_table(table_info)
    return hashlib.md5(json.dumps(canon, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def _stable_hash_from_schema_text(schema_text: str) -> str:
    try:
        parsed = json.loads(schema_text)
    except Exception:
        # 不是JSON（老数据或异常），退化为原文哈希（仍可能误报，但尽力）
        return hashlib.md5((schema_text or "").encode()).hexdigest()
    canon = _canon_table(parsed)
    return hashlib.md5(json.dumps(canon, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def calculate_schema_hash_from_datasource(
    datasource_id: str,
    schema_name: str = None
) -> str:
    """
    基于数据源的真实表结构计算 schema_hash（改进版）

    核心改进：
    - 旧方法：仅基于 datasource_id + schema_name 计算（结构变化时hash不变）
    - 新方法：基于所有表的真实结构（字段名、类型、主键等）计算

    优势：
    1. 数据库结构变化时，schema_hash自动改变
    2. 避免复用过时的知识资产（字段映射、表关系、向量索引）
    3. 确保知识资产与实际结构一致

    Args:
        datasource_id: 数据源ID
        schema_name: Schema名称（可选，如果为None则从数据源配置中获取）

    Returns:
        32字符的MD5哈希值

    示例：
        # 数据库结构未变
        hash1 = calculate_schema_hash_from_datasource("uuid-123", "public")
        hash2 = calculate_schema_hash_from_datasource("uuid-123", "public")
        assert hash1 == hash2  # 相同

        # 数据库结构变化（新增字段、删除表等）
        # ... 执行 ALTER TABLE ...
        hash3 = calculate_schema_hash_from_datasource("uuid-123", "public")
        assert hash1 != hash3  # 不同！
    """
    # 1. 获取该数据源下的所有数据卡片（包含表结构信息）
    datacards = db.session.query(DataCardDataSource).filter(
        DataCardDataSource.datasource_id == datasource_id
    ).all()

    if not datacards:
        # 回退策略：如果没有数据卡片，使用旧方法（确保功能不中断）
        # 场景：用户刚创建数据源，还没生成数据卡片
        print(f"[SchemaHash] 数据源 {datasource_id} 没有数据卡片，使用旧hash算法（基于datasource_id+schema_name）")
        if not schema_name:
            # 尝试从数据源配置中获取
            ds = db.session.query(DatasourceInfo).filter(DatasourceInfo.id == datasource_id).first()
            schema_name = getattr(ds, 'schema_name', None) or 'public' if ds else 'public'
        schema_str = f"{datasource_id}_{schema_name}"
        return hashlib.md5(schema_str.encode()).hexdigest()

    # 2. 提取所有表的结构信息
    tables_structure = []
    for card in datacards:
        try:
            # 解析卡片数据
            card_data = card.card_data
            if isinstance(card_data, str):
                card_data = json.loads(card_data)

            # 获取表名
            table_name = card.table_name
            if not table_name:
                sql_meta = card_data.get("SQLMeta", {})
                table_name = sql_meta.get("table", "")

            if not table_name:
                continue

            # 获取字段信息
            sql_meta = card_data.get("SQLMeta", {})
            columns = sql_meta.get("columns", [])

            if not columns:
                continue

            # 构建标准化的表结构（只包含影响结构的字段，不包括comment等易变字段）
            table_info = {
                "table_name": table_name,
                "columns": sorted([
                    {
                        "name": col.get("name", "").strip(),
                        "type": str(col.get("type", "")).strip().lower(),
                        "nullable": bool(col.get("nullable", False)),
                        "is_primary": bool(col.get("is_primary", False)),
                        "is_foreign": bool(col.get("is_foreign", False))
                    }
                    for col in columns
                ], key=lambda x: x["name"])
            }
            tables_structure.append(table_info)

        except Exception as e:
            print(f"[SchemaHash] 解析表 {getattr(card, 'table_name', 'unknown')} 结构失败: {e}")
            continue

    # 3. 构建标准化的数据源结构描述
    if not schema_name:
        # 尝试从数据源配置中获取
        ds = db.session.query(DatasourceInfo).filter(DatasourceInfo.id == datasource_id).first()
        schema_name = getattr(ds, 'schema_name', None) or 'public' if ds else 'public'

    canon = {
        "datasource_id": str(datasource_id),
        "schema_name": schema_name,
        "tables": sorted(tables_structure, key=lambda x: x["table_name"])
    }

    # 4. 计算hash
    hash_value = hashlib.md5(
        json.dumps(canon, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()

    print(f"[SchemaHash] datasource={datasource_id}, schema={schema_name}, tables={len(tables_structure)}, hash={hash_value}")
    return hash_value

# ================== 业务辅助 ==================
UPDATE_FIELDS_WHITELIST = {
    "connect_name", "status", "db_type", "database_name", "table_num"
}

def _must_uuid(s: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(s))
    except Exception:
        raise ValueError("ID 格式不正确，必须为 UUID")

def _ensure_owner(record: DatasourceInfo, user_id: uuid.UUID):
    if str(record.user_id) != str(user_id):
        # 仅允许操作本人数据
        raise PermissionError("无权操作该数据源")

# ================== Resource ==================
class DatasourceToolAPI(Resource):
    """
    /datasource_tool
      GET    ?user_id=<uuid>            -> 获取该用户的所有数据源摘要
    /datasource_tool/<id>
      PUT    JSON body(允许字段见白名单)  -> 按 ID 更新数据源摘要
      DELETE                              -> 按 ID 删除数据源摘要
    """

    @login_required
    def get(self):
        """分页：根据用户ID获取数据源信息"""
        # user_id：默认当前登录用户
        user_id = request.args.get("user_id") or str(current_user.id)
        try:
            user_uuid = _must_uuid(user_id)
        except ValueError as e:
            return format_response(None, 400, str(e))

        # 分页参数
        def _as_int(v, default):
            try:
                return int(v)
            except (TypeError, ValueError):
                return default

        page = _as_int(request.args.get("page"), 1)
        page_size = _as_int(request.args.get("page_size"), 10)

        if page < 1:
            page = 1
        # 限制单页上限，避免过大请求
        if page_size < 1:
            page_size = 10
        if page_size > 100:
            page_size = 100

        offset = (page - 1) * page_size

        base_q = (
            db.session.query(DatasourceInfo)
            .filter(DatasourceInfo.user_id == str(user_uuid))
        )

        # 统计总数
        total = db.session.query(func.count(DatasourceInfo.id)).filter(
            DatasourceInfo.user_id == str(user_uuid)
        ).scalar() or 0

        # 当前页数据
        items = (
            base_q.order_by(DatasourceInfo.updated_at.desc())
            .limit(page_size)
            .offset(offset)
            .all()
        )

        # 批量查询数据卡片数量和表信息，避免N+1查询问题
        datacard_counts = {}
        datasource_wuuids = {}  # 存储每个数据源的w_uuid列表（用于向量库统计）
        datasource_schemas = {}  # 存储每个数据源的表信息列表

        if items:
            datasource_ids = [str(it.id) for it in items]

            # 1. 批量查询user_datasource_schemas表信息
            # 匹配策略：
            #   - 有 connect_info_hash: 使用 (connect_info_hash, schema_name) 匹配
            #   - 无 connect_info_hash (历史数据): 使用 (db_type, connect_name, database_name, schema_name) 匹配

            # 构建 datasource 元数据映射
            datasource_meta = {}
            for it in items:
                ds_id = str(it.id)
                datasource_meta[ds_id] = {
                    'connect_info_hash': it.connect_info_hash,
                    'schema_name': it.schema_name,
                    'db_type': it.db_type,
                    'connect_name': it.connect_name,
                    'database_name': it.database_name,
                }

            # 分别查询有哈希值和无哈希值的记录
            from sqlalchemy import or_, and_

            # 查询1: 有哈希值的 user_datasource_schemas
            hashes_with_value = [it.connect_info_hash for it in items if it.connect_info_hash]
            if hashes_with_value:
                all_schemas_with_hash = db.session.query(UserDatasourceSchema).filter(
                    UserDatasourceSchema.user_id == str(user_uuid),
                    UserDatasourceSchema.connect_info_hash.in_(hashes_with_value)
                ).all()
            else:
                all_schemas_with_hash = []

            # 查询2: 无哈希值的 user_datasource_schemas (历史数据)
            # 使用 (db_type, connect_name, database_name, schema_name) 匹配
            legacy_conditions = []
            for ds_id, meta in datasource_meta.items():
                if not meta['connect_info_hash']:  # 没有哈希值
                    legacy_conditions.append(
                        and_(
                            UserDatasourceSchema.db_type == meta['db_type'],
                            UserDatasourceSchema.connect_name == meta['connect_name'],
                            UserDatasourceSchema.database_name == meta['database_name'],
                            UserDatasourceSchema.schema_name == meta['schema_name']
                        )
                    )

            if legacy_conditions:
                all_schemas_without_hash = db.session.query(UserDatasourceSchema).filter(
                    UserDatasourceSchema.user_id == str(user_uuid),
                    or_(*legacy_conditions)
                ).all()
            else:
                all_schemas_without_hash = []

            # 合并结果
            all_schemas = all_schemas_with_hash + all_schemas_without_hash

            # 构建反向查找映射
            ds_lookup = {}
            for ds_id, meta in datasource_meta.items():
                if meta['connect_info_hash']:
                    # 有哈希值：用 (connect_info_hash, schema_name) 作为键
                    key = (meta['connect_info_hash'], meta['schema_name'])
                    ds_lookup[key] = ds_id
                else:
                    # 无哈希值：用 legacy 条件作为键
                    key = ('legacy', meta['db_type'], meta['connect_name'], meta['database_name'], meta['schema_name'])
                    ds_lookup[key] = ds_id

            for schema in all_schemas:
                # 尝试用哈希值匹配
                ds_id = ds_lookup.get((schema.connect_info_hash, schema.schema_name))
                if not ds_id and not schema.connect_info_hash:
                    # 回退：用 legacy 条件匹配
                    ds_id = ds_lookup.get(('legacy', schema.db_type, schema.connect_name, schema.database_name, schema.schema_name))

                if ds_id:
                    if ds_id not in datasource_schemas:
                        datasource_schemas[ds_id] = []

                    # 解析schema_text（可能是JSON字符串）
                    schema_text_parsed = None
                    if schema.schema_text:
                        try:
                            import json
                            if isinstance(schema.schema_text, str):
                                schema_text_parsed = json.loads(schema.schema_text)
                            else:
                                schema_text_parsed = schema.schema_text
                        except Exception as e:
                            print(f"[表结构解析] 解析schema_text失败: schema_id={schema.id}, error={e}")
                            schema_text_parsed = schema.schema_text  # 解析失败则返回原始数据

                    # 解析filled_data（LLM填充结果）
                    filled_data_parsed = None
                    if schema.filled_data:
                        try:
                            import json
                            if isinstance(schema.filled_data, str):
                                filled_data_parsed = json.loads(schema.filled_data)
                            else:
                                filled_data_parsed = schema.filled_data
                        except Exception:
                            filled_data_parsed = schema.filled_data

                    datasource_schemas[ds_id].append({
                        "id": str(schema.id),
                        "table_name": schema.table_name,
                        "db_type": schema.db_type,
                        "database_name": schema.database_name,
                        "db_version": schema.db_version,
                        "is_view": schema.is_view,
                        "view_name": schema.view_name,
                        "is_filled": schema.is_filled,
                        "catalog_type": schema.catalog_type,
                        "schema_text": schema_text_parsed,  # 表结构详情（已解析为JSON对象）
                        "filled_data": filled_data_parsed,  # LLM填充结果
                        "created_at": schema.created_at.isoformat() if schema.created_at else None,
                        "updated_at": schema.updated_at.isoformat() if schema.updated_at else None
                    })

            # 2. 只查询 w_uuid 用于向量库统计（不查询完整 card_data）
            wuuid_query = (
                db.session.query(
                    DataCardDataSource.datasource_id,
                    DataCardDataSource.w_uuid
                )
                .filter(DataCardDataSource.datasource_id.in_(datasource_ids))
                .all()
            )
            for ds_id, w_uuid in wuuid_query:
                ds_id_str = str(ds_id)
                if ds_id_str not in datasource_wuuids:
                    datasource_wuuids[ds_id_str] = []
                datasource_wuuids[ds_id_str].append(w_uuid)

            # 3. 统计每个数据源的数据卡片数量
            for ds_id, wuuids in datasource_wuuids.items():
                datacard_counts[ds_id] = len(wuuids)

        # 获取向量库中的实际UUID集合
        weaviate_uuid_set = None  # None表示查询失败，set()表示查询成功但结果为空
        weaviate_count = 0
        user_class = getattr(current_user, "weaviate_class_name", None)

        if user_class:
            try:
                # 获取向量库总记录数
                weaviate_count = get_total_count(user_class)

                # 批量查询向量库中的所有UUID（用于验证w_uuid的存在性）
                # 为了性能考虑，限制查询数量
                with weaviate_client() as client:
                    target_class = _require_user_class_name(user_class)
                    _require_collection_exists(client, target_class)

                    collection = client.collections.get(target_class)
                    # 分批查询向量库中的所有UUID
                    # 考虑性能，最多查询10000条（如果超过，后续可以优化为分页查询）
                    query_limit = min(10000, weaviate_count) if weaviate_count > 0 else 100
                    response = collection.query.fetch_objects(
                        limit=query_limit,
                        return_properties=[]  # 只需要UUID，不需要properties
                    )
                    # 构建UUID集合（即使为空集合也表示查询成功）
                    weaviate_uuid_set = {str(obj.uuid) for obj in response.objects}
                    print(f"[向量库统计] 用户={user_uuid} class={target_class} 查询到 {len(weaviate_uuid_set)} 个向量对象（总数={weaviate_count}）")

            except Exception as e:
                print(f"[向量库统计] 获取向量库UUID失败: {e}")
                import traceback
                traceback.print_exc()
                weaviate_uuid_set = None  # 显式设置为None表示查询失败

        total_pages = (total + page_size - 1) // page_size if page_size else 0

        # 将数据卡片数量和向量库统计添加到返回结果中
        items_dict = []
        for it in items:
            item_data = it.to_dict()
            ds_id = str(it.id)

            # 统计信息
            item_data["datacard_count"] = datacard_counts.get(ds_id, 0)

            # 统计该数据源在向量库中实际存在的对象数
            ds_wuuids = datasource_wuuids.get(ds_id, [])
            if weaviate_uuid_set is not None:
                # 查询成功（包括向量库为空的情况）
                # 验证每个w_uuid是否在向量库中存在
                weaviate_num = sum(1 for w_uuid in ds_wuuids if w_uuid and w_uuid in weaviate_uuid_set)
            else:
                # 查询失败（异常情况）
                # 如果无法查询向量库，回退到使用datacard_count
                weaviate_num = item_data["datacard_count"]

            item_data["weaviate_num"] = weaviate_num

            # 添加表信息列表
            item_data["schemas"] = datasource_schemas.get(ds_id, [])

            items_dict.append(item_data)

        payload = {
            "items": items_dict,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
            "weaviate_count": weaviate_count  # 用户向量库总记录数
        }
        return format_response(payload, 200, "查询成功")

    @login_required
    def put(self, ds_id: str):
        """按 ID 修改数据源记录（仅白名单字段可改），并同步到 user_datasource_schemas.connect_name 和数据卡片"""
        try:
            _ = _must_uuid(ds_id)
        except ValueError as e:
            return format_response(None, 400, str(e))

        payload: Dict[str, Any] = (request.get_json() or {})
        if not payload:
            return format_response(None, 400, "请求体不能为空")

        updates = {k: v for k, v in payload.items() if k in UPDATE_FIELDS_WHITELIST}
        if not updates:
            return format_response(None, 400, f"无可更新字段，允许字段：{', '.join(sorted(UPDATE_FIELDS_WHITELIST))}")

        record: Optional[DatasourceInfo] = (
            db.session.query(DatasourceInfo).filter(DatasourceInfo.id == ds_id).one_or_none()
        )
        if not record:
            return format_response(None, 404, "记录不存在")

        try:
            _ensure_owner(record, current_user.id)
        except PermissionError as e:
            return format_response(None, 403, str(e))

        # 记录旧值用于判断是否需要同步
        old_connect_name = record.connect_name
        want_connect_name = updates.get("connect_name", old_connect_name)

        # 应用更新到 datasource_info
        for k, v in updates.items():
            setattr(record, k, v)

        # —— 事务开始：datasource_info、user_datasource_schemas 和 datacards_datasource 同步 ——
        try:
            schemas_updated = 0
            cards_updated = 0

            # 只有在 connect_name 真的变化时才同步
            if "connect_name" in updates and (want_connect_name != old_connect_name):
                print(f"[数据源更新] connect_name 变化: {old_connect_name} -> {want_connect_name}")

                # 1. 更新 user_datasource_schemas 表
                # 按 db_type 分支决定是否带 schema_name 过滤（避免同 connect_info 不同 schema 的兄弟数据源被串改）
                # 使用 connect_info_hash 进行稳定匹配
                update_query = db.session.query(UserDatasourceSchema).filter(
                    UserDatasourceSchema.user_id == record.user_id,
                    UserDatasourceSchema.connect_info_hash == record.connect_info_hash,
                )
                update_query = _add_schema_filter(update_query, record.db_type, record.schema_name)
                schemas_updated = update_query.update(
                    {
                        "connect_name": want_connect_name,
                        "updated_at": func.current_timestamp()
                    },
                    synchronize_session=False
                )
                print(f"[数据源更新] 更新了 {schemas_updated} 条 schema 记录")

                # 2. 更新 datacards_datasource 表中的 card_data JSON 字段
                # 先获取所有相关的 schema doc_id（同样按 db_type 分支带 schema_name 过滤）
                # 使用 connect_info_hash 进行稳定匹配
                doc_id_query = db.session.query(UserDatasourceSchema.id).filter(
                    UserDatasourceSchema.user_id == record.user_id,
                    UserDatasourceSchema.connect_info_hash == record.connect_info_hash,
                )
                doc_id_query = _add_schema_filter(doc_id_query, record.db_type, record.schema_name)
                schema_doc_ids = [
                    str(r[0]) for r in doc_id_query.all()
                ]

                # 以下 datacards_datasource 同步逻辑保持不变（已在前面通过 doc_id 精确锁定）
                if schema_doc_ids:
                    # 获取所有需要更新的数据卡片
                    cards_to_update = (
                        db.session.query(DataCardDataSource)
                        .filter(DataCardDataSource.doc_id.in_(schema_doc_ids))
                        .all()
                    )

                    print(f"[数据源更新] 找到 {len(cards_to_update)} 张数据卡片需要更新")

                    # 逐个更新 card_data 中的 connect_name 和 connect_name 表字段
                    for card in cards_to_update:
                        try:
                            card_data = json.loads(card.card_data)
                            updated = False

                            # 更新 card_data JSON 中的 DocInfo.connect_name
                            if "DocInfo" in card_data:
                                old_name_in_card = card_data["DocInfo"].get("connect_name")
                                card_data["DocInfo"]["connect_name"] = want_connect_name
                                card.card_data = json.dumps(card_data, ensure_ascii=False)
                                updated = True

                                print(f"[数据源更新] 更新数据卡片 card_data: doc_id={card.doc_id}, "
                                      f"{old_name_in_card} -> {want_connect_name}")

                            # 更新 datacards_datasource 表的 connect_name 冗余字段
                            if card.connect_name != want_connect_name:
                                old_name_in_field = card.connect_name
                                card.connect_name = want_connect_name
                                updated = True

                                print(f"[数据源更新] 更新数据卡片 connect_name 字段: doc_id={card.doc_id}, "
                                      f"{old_name_in_field} -> {want_connect_name}")

                            if updated:
                                db.session.add(card)
                                cards_updated += 1
                            else:
                                print(f"[数据源更新] 警告: 数据卡片 doc_id={card.doc_id} 缺少 DocInfo 字段且 connect_name 字段无需更新")

                        except json.JSONDecodeError as e:
                            print(f"[数据源更新] 错误: 数据卡片 doc_id={card.doc_id} 的 card_data 不是有效的 JSON: {e}")
                        except Exception as e:
                            print(f"[数据源更新] 错误: 更新数据卡片 doc_id={card.doc_id} 失败: {e}")

            db.session.commit()
            print(f"[数据源更新] [OK] 事务提交成功")

        except SQLAlchemyError as e:
            db.session.rollback()
            print(f"[数据源更新] [FAIL] 事务回滚: {e}")
            return format_response(None, 500, f"更新失败：{e}")

        data = record.to_dict()
        data["schemas_updated"] = int(schemas_updated)
        data["cards_updated"] = int(cards_updated)

        return format_response(data, 200, "更新成功")

    @login_required
    def delete(self, ds_id: str):
        """
        级联删除：
        1) 删除 datasource_info
        2) 删除 datasource_term_library（该数据源关联的术语库绑定记录）
        3) 删除 user_datasource_schemas（同一 user_id + connect_info）
        4) 删除 datacards_datasource（以 doc_id = user_datasource_schemas.id）
        5) 删除盘点相关数据（target_inventory_job、table_relationship、table_relationship_card、field_mapping）
        6) 删除向量库中的对象（datacards_datasource.w_uuid）
        7) 删除字段画像向量索引中该数据源的所有记录
        """
        # 校验 id
        try:
            _ = _must_uuid(ds_id)
        except ValueError as e:
            return format_response(None, 400, str(e))

        # 查询数据源记录
        record: Optional[DatasourceInfo] = (
            db.session.query(DatasourceInfo)
            .filter(DatasourceInfo.id == ds_id)
            .one_or_none()
        )
        if not record:
            return format_response(None, 404, "记录不存在")

        # 权限：仅能删除自己的
        try:
            _ensure_owner(record, current_user.id)
        except PermissionError as e:
            return format_response(None, 403, str(e))

        # ===== 预取依赖数据（在删除前先把“关联ID与向量UUID”查出来）=====
        # 这个数据源对应的所有 schema 行（用 user_id + connect_info + (可选) schema_name 作为关联键）
        schema_id_query = db.session.query(UserDatasourceSchema.id).filter(
            UserDatasourceSchema.user_id == record.user_id,
            UserDatasourceSchema.connect_info_hash == record.connect_info_hash
        )
        schema_id_query = _add_schema_filter(schema_id_query, record.db_type, record.schema_name)
        schema_rows = schema_id_query.all()
        schema_doc_ids = [str(r[0]) for r in schema_rows]  # 转成字符串用于 IN 查询

        # 这些 schema 的卡片里对应的向量 UUID 列表（先拿出来，等 SQL 删除成功后删向量库）
        w_uuids = []
        cards_deleted = 0
        if schema_doc_ids:
            w_uuids = [
                r[0] for r in db.session.query(DataCardDataSource.w_uuid)
                .filter(DataCardDataSource.doc_id.in_(schema_doc_ids))
                .all()
            ]

        # ===== 预取盘点相关数据 =====
        ds_uuid = uuid.UUID(ds_id)

        # 定向盘点任务：查询该数据源的所有 job_id（用于删除关联结果）
        inventory_job_ids = [
            str(r[0]) for r in db.session.query(TargetInventoryJob.id)
            .filter(TargetInventoryJob.datasource_id == ds_uuid)
            .all()
        ]

        # ======= 事务：先删数据源，再删 schema，再删卡片（数据库内原子性）=======
        try:
            # 1) 删除 datasource_info
            db.session.delete(record)

            # 2) 删除 datasource_term_library（该数据源关联的术语库绑定记录）
            term_library_links_deleted = (
                db.session.query(DatasourceTermLibrary)
                .filter(DatasourceTermLibrary.datasource_id == ds_uuid)
                .delete(synchronize_session=False)
            )

            # 3) 删除 user_datasource_schemas
            del_schema_query = db.session.query(UserDatasourceSchema).filter(
                UserDatasourceSchema.user_id == record.user_id,
                UserDatasourceSchema.connect_info_hash == record.connect_info_hash
            )
            del_schema_query = _add_schema_filter(del_schema_query, record.db_type, record.schema_name)
            schemas_deleted = del_schema_query.delete(synchronize_session=False)

            # 4) 删除 datacards_datasource（按 doc_id 批量删）
            if schema_doc_ids:
                cards_deleted = (
                    db.session.query(DataCardDataSource)
                    .filter(DataCardDataSource.doc_id.in_(schema_doc_ids))
                    .delete(synchronize_session=False)
                )
            else:
                cards_deleted = 0

            # 5) 删除盘点相关数据
            # 5.1) TargetInventoryJobResult（通过 job_id）
            inventory_job_results_deleted = 0
            if inventory_job_ids:
                inventory_job_results_deleted = (
                    db.session.query(TargetInventoryJobResult)
                    .filter(TargetInventoryJobResult.job_id.in_([uuid.UUID(jid) for jid in inventory_job_ids]))
                    .delete(synchronize_session=False)
                )

            # 5.2) TargetInventoryJob（通过 datasource_id）
            inventory_jobs_deleted = 0
            if inventory_job_ids:
                inventory_jobs_deleted = (
                    db.session.query(TargetInventoryJob)
                    .filter(TargetInventoryJob.datasource_id == ds_uuid)
                    .delete(synchronize_session=False)
                )

            # 5.3) TableRelationship（涉及该数据源的所有关系：table_a 或 table_b）
            table_relationships_deleted = (
                db.session.query(TableRelationship)
                .filter(
                    (TableRelationship.table_a_datasource_id == ds_uuid) |
                    (TableRelationship.table_b_datasource_id == ds_uuid)
                )
                .delete(synchronize_session=False)
            )

            # 5.4) TableRelationshipCard（datasource_id）
            table_relationship_cards_deleted = (
                db.session.query(TableRelationshipCard)
                .filter(TableRelationshipCard.datasource_id == ds_uuid)
                .delete(synchronize_session=False)
            )

            # 5.5) FieldMapping（datasource_id）
            field_mappings_deleted = (
                db.session.query(FieldMapping)
                .filter(FieldMapping.datasource_id == ds_uuid)
                .delete(synchronize_session=False)
            )

            # 提交数据库事务
            db.session.commit()

        except SQLAlchemyError as e:
            db.session.rollback()
            return format_response(None, 500, f"删除失败：{e}")

        # 6) 删除向量库对象（非数据库资源，放在提交之后；失败也不影响数据库一致性）
        vectors_deleted_ok = True
        vectors_count = len(w_uuids)
        try:
            if w_uuids:
                user_class = getattr(current_user, "weaviate_class_name", None)
                vectors_deleted_ok = bool(batch_delete_by_uuids(w_uuids, class_name=user_class))
        except Exception as _:
            vectors_deleted_ok = False  # 不抛出，避免影响整体

        # 7) 删除字段画像向量索引中该数据源的所有记录
        field_index_deleted_count = 0
        try:
            user_class = getattr(current_user, "weaviate_class_name", None)
            if user_class:
                field_index_deleted_count = delete_field_index_by_datasource(
                    datasource_id=ds_id,
                    user_class=user_class
                )
        except Exception as e:
            print(f"[数据源删除] 删除字段索引失败: {e}")

        # 返回结果
        data = {
            "id": ds_id,
            "schemas_deleted": int(schemas_deleted),
            "cards_deleted": int(cards_deleted),
            "term_library_links_deleted": int(term_library_links_deleted),
            "inventory_jobs_deleted": int(inventory_jobs_deleted),
            "inventory_job_results_deleted": int(inventory_job_results_deleted),
            "table_relationships_deleted": int(table_relationships_deleted),
            "table_relationship_cards_deleted": int(table_relationship_cards_deleted),
            "field_mappings_deleted": int(field_mappings_deleted),
            "weaviate_count": int(vectors_count),
            "weaviate_deleted": bool(vectors_deleted_ok),
            "field_index_deleted": int(field_index_deleted_count),
        }
        return format_response(data, 200, "删除成功")

    @login_required
    def post(self, ds_id: str):
        """
        刷新数据源：
        - quick：仅测试连接并更新状态
        - full：带结构对比，仅刷新有变化的表
        """
        if not request.path.endswith("/refresh"):
            return format_response(None, 404, "未定义的子路径")

        mode = (request.args.get("mode") or "full").lower()
        if mode not in ("quick", "full"):
            return format_response(None, 400, "mode 参数错误，应为 quick 或 full")

        # ===== 1. 查询数据源 =====
        record: Optional[DatasourceInfo] = (
            db.session.query(DatasourceInfo).filter(DatasourceInfo.id == ds_id).one_or_none()
        )
        if not record:
            return format_response(None, 404, "记录不存在")

        try:
            _ensure_owner(record, current_user.id)
        except PermissionError as e:
            return format_response(None, 403, str(e))

        # ===== 2. quick 模式：连接测试 + 刷新状态 =====
        if mode == "quick":
            old_status = record.status
            checked_version = None
            safe_conn = None
            err_msg = None
            engine = None

            try:
                # 从数据源记录中拿连接串（解密后用于连接数据库）
                decrypted_connect_info = decrypt_connect_info(record.connect_info)
                engine = get_db_engine(decrypted_connect_info, db_type=record.db_type)  # 成功即表示连通
                checked_version = _get_database_version(engine)

                # 返回里用脱敏连接串（隐藏密码）
                safe_conn = make_url(decrypted_connect_info).render_as_string(hide_password=True)

                # 连通即设为可用
                record.status = "available"

            except Exception as e:
                # 失败即设为不可用，并记录错误信息（不暴露密码、不回传原串）
                record.status = "unavailable"
                err_msg = str(e)

            finally:
                # 释放数据库连接池
                if engine:
                    try:
                        engine.dispose()
                    except Exception:
                        pass

            # 写回数据库（只更新 status）
            try:
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                return format_response(None, 500, f"状态更新失败：{e}")

            # 组织返回
            return format_response(
                {
                    "mode": "quick",
                    "id": str(record.id),
                    "connect_name": record.connect_name,
                    "status_before": old_status,
                    "status_after": record.status,
                    "database_type": record.db_type,
                    "database_name": record.database_name,
                    "database_version": checked_version,
                    "connection": safe_conn,  # 已脱敏
                    "error": err_msg  # 仅在失败时有值
                },
                200,
                "刷新完成（quick）"
            )

        # ===== 3. full 模式：带结构差异检测 =====
        engine = None
        try:
            try:
                # 解密连接信息后创建数据库引擎
                decrypted_connect_info = decrypt_connect_info(record.connect_info)
                engine = get_db_engine(decrypted_connect_info, db_type=record.db_type)
                inspector = inspect(engine)
            except Exception as e:
                return format_response(None, 500, f"数据库连接失败：{e}")

            print(
                f"[DATASOURCE_REFRESH][START] "
                f"user_id={record.user_id} | "
                f"datasource_id={record.id} | "
                f"db_type={record.db_type} | "
                f"database={record.database_name} | "
                f"schema={record.schema_name or 'N/A'}"
            )

            # Step 1：提取当前表结构（新）
            # 构建 payload 参数
            # 注意：record.connect_info 存储的是加密值，需要解密后再使用
            decrypted_conn = decrypt_connect_info(record.connect_info)
            url = make_url(decrypted_conn)
            payload = {"db_type": record.db_type, "database": record.database_name}

            dbt = (record.db_type or "").lower()
            if dbt in ("postgresql", "kingbase"):
                # KingBase 基于 PostgreSQL 协议，使用相同的 schema 处理逻辑
                payload["schema"] = record.schema_name or "public"
            elif dbt == "mssql":
                payload["schema"] = record.schema_name or "dbo"
            elif dbt == "oracle":
                # 原生 oracle 用 username/owner 控制范围
                # 优先使用 schema_name（可能是 target_schema），否则使用 username
                # schema_name 在添加数据源时已保存为 target_schema 或 username（大写）
                payload["username"] = (record.schema_name or (make_url(decrypted_conn).username or "")).upper()
            elif dbt == "dm":
                # 达梦 DM：与 Oracle 行为一致，username/owner 控制范围
                payload["username"] = (record.schema_name or (make_url(decrypted_conn).username or "")).upper()
            elif dbt == "trino":
                # trino 必须要 schema
                payload["schema"] = record.schema_name
                # catalog 继续按你原来的方式（来自 database_name 或 url.database 的 catalog/schema）
                # 但 schema 不再猜，直接用 record.schema_name
                payload["catalog"] = (record.catalog_type or (
                    record.database_name.split("/", 1)[0] if "/" in record.database_name else record.database_name))
            elif dbt == "mysql":
                # mysql 没 schema，不加 schema 字段
                pass

            if dbt == "trino":
                url = make_url(decrypted_conn)
                path = url.database or ""  # 形如 catalog/schema
                if "/" in path:
                    _catalog, _schema = path.split("/", 1)
                    if record.schema_name and _schema and (record.schema_name != _schema):
                        return format_response(
                            None, 409,
                            f"Trino 数据源不一致：schema_name={record.schema_name} 但 connect_info 的 schema={_schema}。"
                            f"请修正数据源连接信息后再刷新，避免跑偏。"
                        )

            # 根据数据库类型添加特殊参数
            if (record.db_type or "").lower() == "oracle" and not url.drivername.startswith("trino"):
                # 原生 Oracle：需要传 target_schema 或 owner（用户名大写）来限定 ALL_TABLES.OWNER
                # 优先使用 schema_name（可能是 target_schema），否则使用 username
                owner_upper = (record.schema_name or url.username or "").upper()
                if record.schema_name:
                    payload["target_schema"] = record.schema_name.upper()
                payload["username"] = owner_upper  # 关键：用于枚举表
            elif (record.db_type or "").lower() == "dm" and not url.drivername.startswith("trino"):
                # 达梦 DM：与 Oracle 兼容，沿用相同逻辑（ALL_TABLES.OWNER 大写过滤）
                owner_upper = (record.schema_name or url.username or "").upper()
                if record.schema_name:
                    payload["target_schema"] = record.schema_name.upper()
                payload["username"] = owner_upper  # 关键：用于枚举表
            elif (record.db_type or "").lower() == "trino":
                # Trino：只允许补齐 catalog；schema 必须以 record.schema_name 为准（添加数据源时传入）
                # connect_info 格式: trino://user@host:port/catalog/schema?params
                catalog = None
                parsed_schema = None

                # 方法1：从 database_name 解析（如果格式正确）
                if "/" in (record.database_name or ""):
                    catalog, parsed_schema = record.database_name.split("/", 1)
                else:
                    # 方法2：从 connect_info URL 解析
                    try:
                        url_path = url.database or ""  # 例如：postgres/public
                        if "/" in url_path:
                            catalog, parsed_schema = url_path.split("/", 1)
                        else:
                            catalog = url_path or record.database_name
                    except Exception as e:
                        print(f"[WARN] 解析 Trino connect_info 失败: {e}")
                        catalog = record.database_name

                # 只补齐/修正 catalog，不覆盖 schema
                if catalog:
                    payload["catalog"] = catalog

                # schema 必须来自 record.schema_name（你前面已经 payload["schema"] = record.schema_name）
                if not payload.get("schema"):
                    # 如果 record.schema_name 为空，这里才兜底使用解析到的 schema（避免直接跑空导致误删）
                    payload["schema"] = parsed_schema

                print(f"[DEBUG] Trino 刷新 - catalog: {payload.get('catalog')}, schema: {payload.get('schema')}")

            print(
                f"[DATASOURCE_REFRESH][SCOPE] "
                f"db_type={record.db_type} | "
                f"database={payload.get('database')} | "
                f"catalog={payload.get('catalog', 'N/A')} | "
                f"schema={payload.get('schema', payload.get('username', 'N/A'))}"
            )

            new_tables = get_tables(inspector, engine, payload)
            print(f"[DEBUG] get_tables 返回的表名: {new_tables}")

            # —— 防御：若新列表为空但旧数据存在，直接中断，避免误删 ——
            # 按 db_type 分支决定是否带 schema_name 过滤（避免同 connect_info 不同 schema 的兄弟数据源被串改）
            existing_count_query = db.session.query(UserDatasourceSchema.id).filter(
                UserDatasourceSchema.user_id == record.user_id,
                UserDatasourceSchema.connect_info_hash == record.connect_info_hash
            )
            existing_count_query = _add_schema_filter(existing_count_query, record.db_type, record.schema_name)
            existing_count = existing_count_query.count()

            if (not new_tables) and existing_count > 0:
                if (record.db_type or "").lower() == "oracle" and not url.drivername.startswith("trino"):
                    return format_response(
                        None, 409,
                        "Oracle 刷新异常：未枚举到任何表（可能 owner/schema 不匹配或权限不足），为避免误删已中止。"
                    )
                elif (record.db_type or "").lower() == "dm" and not url.drivername.startswith("trino"):
                    # 达梦 DM：与 Oracle 类似的 owner/权限提示
                    return format_response(
                        None, 409,
                        "达梦 DM 刷新异常：未枚举到任何表（可能 owner/schema 不匹配或权限不足），为避免误删已中止。"
                    )
                elif (record.db_type or "").lower() == "trino":
                    catalog = payload.get("catalog", "未知")
                    schema = payload.get("schema", "未知")
                    return format_response(
                        None, 409,
                        f"Trino 刷新异常：未枚举到任何表（catalog: {catalog}, schema: {schema}），"
                        f"请检查 catalog/schema 是否正确或是否有权限访问，为避免误删已中止。"
                    )
                elif (record.db_type or "").lower() in ("postgresql", "kingbase"):
                    schema = payload.get("schema", "未知")
                    return format_response(
                        None, 409,
                        f"PostgreSQL/KingBase 刷新异常：未枚举到任何表（schema: {schema}），"
                        f"请检查 schema 是否正确或是否有权限访问，为避免误删已中止。"
                    )
                elif (record.db_type or "").lower() == "mssql":
                    schema = payload.get("schema", "未知")
                    return format_response(
                        None, 409,
                        f"MSSQL 刷新异常：未枚举到任何表（schema: {schema}），"
                        f"请检查 schema 是否正确或是否有权限访问，为避免误删已中止。"
                    )

            new_struct = {}
            db_type_lower = (record.db_type or "").lower()
            if db_type_lower in ("postgresql", "kingbase"):
                # KingBase 基于 PostgreSQL 协议，使用相同的 schema 处理逻辑
                schema_arg = payload.get("schema")
            elif db_type_lower == "mssql":
                schema_arg = payload.get("schema")
            elif db_type_lower == "oracle" or db_type_lower == "dm":
                # 优先使用 target_schema（用户指定的 schema），其次使用 username
                # 达梦 DM 与 Oracle 兼容，沿用同一逻辑
                schema_arg = (payload.get("target_schema") or payload.get("username") or url.username or "").upper() or None
            elif db_type_lower == "trino":
                schema_arg = payload.get("schema")
            else:
                schema_arg = None

            for tbl_item in new_tables:

                if isinstance(tbl_item, dict):
                    table_name = tbl_item.get("name")
                    object_type = (tbl_item.get("type") or "TABLE").upper()
                else:
                    table_name = tbl_item
                    object_type = "TABLE"

                if not table_name:
                    continue

                table_name = str(table_name)
                is_view = object_type == "VIEW"

                # 保存原始表名（从 get_tables 返回的实际表名）
                original_table_name = table_name

                # Oracle 表名大小写容错处理
                # 策略：先尝试原始表名，失败后再尝试大写表名
                # 达梦 DM 与 Oracle 兼容，也走相同的处理
                info = None
                if db_type_lower == "oracle" or db_type_lower == "dm":
                    try:
                        info = _extract_table_info(inspector, original_table_name, schema=schema_arg, is_view=is_view)
                    except NoSuchTableError:
                        # 如果失败且表名不是全大写，尝试使用大写表名（Oracle/达梦默认行为）
                        if original_table_name != original_table_name.upper():
                            try:
                                info = _extract_table_info(inspector, original_table_name.upper(), schema=schema_arg, is_view=is_view)
                            except NoSuchTableError:
                                # 两种方式都失败，抛出异常
                                raise
                        else:
                            # 表名已经是大写，直接抛出异常
                            raise
                else:
                    # 非 Oracle/达梦 数据库，直接使用原始表名
                    info = _extract_table_info(inspector, original_table_name, schema=schema_arg, is_view=is_view)

                # 关键：确保返回的 info 中的 table_name 是原始表名
                if info:
                    info["table_name"] = original_table_name

                info_hash = _stable_hash_from_info(info)  # 稳定签名

                # 调试：对于 Trino，检查表名存储格式
                if db_type_lower == "trino":
                    print(
                        f"[DEBUG] Trino 表名处理 - 原始: '{table_name}', schema_arg: '{schema_arg}', is_view: {is_view}")

                new_struct[original_table_name] = {"info": info, "hash": info_hash}

            # Step 2：获取旧的表结构（旧）
            # 按 db_type 分支决定是否带 schema_name 过滤（避免同 connect_info 不同 schema 的兄弟数据源被串改）
            old_rows_query = (
                db.session.query(
                    UserDatasourceSchema.table_name,
                    UserDatasourceSchema.schema_text,
                    UserDatasourceSchema.id
                )
                .filter(
                    UserDatasourceSchema.user_id == record.user_id,
                    UserDatasourceSchema.connect_info_hash == record.connect_info_hash
                )
            )
            old_rows_query = _add_schema_filter(old_rows_query, record.db_type, record.schema_name)
            old_rows = old_rows_query.all()
            print(f"[DEBUG] 数据库中的表记录数: {len(old_rows)}")
            if old_rows:
                print(f"[DEBUG] 数据库中的表名: {[row[0] for row in old_rows[:5]]}...")  # 只显示前5个

            # Step 3：对比差异
            old_map = {}
            for name, schema_text, sid in old_rows:
                old_hash = _stable_hash_from_schema_text(schema_text)
                old_map[name] = {"hash": old_hash, "id": str(sid)}

            # Oracle 统一使用大写表名，避免大小写导致的"误删/误变更"
            # 达梦 DM 与 Oracle 兼容，沿用同一逻辑
            if (record.db_type or "").lower() in ("oracle", "dm") and not url.drivername.startswith("trino"):
                old_map = {k.upper(): v for k, v in old_map.items()}
                new_struct = {k.upper(): v for k, v in new_struct.items()}

            # 对于 Trino，可能需要智能表名匹配
            if (record.db_type or "").lower() == "trino" and old_map and new_struct:
                old_keys = list(old_map.keys())
                new_keys = list(new_struct.keys())

                if old_keys and new_keys and "." in old_keys[0] and "." not in new_keys[0]:
                    print(f"[DEBUG] 检测到 Trino 表名格式不匹配，尝试智能匹配...")
                    new_old_map = {}
                    for old_name, old_data in old_map.items():
                        table_name_only = old_name.split(".")[-1] if "." in old_name else old_name
                        new_old_map[table_name_only] = old_data
                    old_map = new_old_map
                    print(f"[DEBUG] 智能匹配后的旧表名: {sorted(old_map.keys())}")

            old_names = set(old_map.keys())
            new_names = set(new_struct.keys())

            print(f"[DEBUG] 刷新对比 - 旧表数量: {len(old_names)}, 新表数量: {len(new_names)}")
            print(f"[DEBUG] 刷新对比 - 旧表名: {sorted(old_names)}")
            print(f"[DEBUG] 刷新对比 - 新表名: {sorted(new_names)}")

            if (record.db_type or "").lower() == "trino":
                print(f"[DEBUG] Trino 表名诊断:")
                print(f"  - database_name: {record.database_name}")
                # 注意：打印调试信息时使用脱敏版本，避免泄漏敏感信息
                print(f"  - connect_info: {record.connect_info_safe}")

                if old_names and new_names:
                    sample_old = list(old_names)[0] if old_names else None
                    sample_new = list(new_names)[0] if new_names else None
                    print(f"  - 示例旧表名: '{sample_old}'")
                    print(f"  - 示例新表名: '{sample_new}'")

                    if sample_old and sample_new and ("." in sample_old or "/" in sample_old):
                        print(f"  - 可能的表名格式不匹配问题！")

            added = new_names - old_names
            removed = old_names - new_names
            common = old_names & new_names

            changed = []
            for n in common:
                old_hash = old_map[n]["hash"]
                new_hash = new_struct[n]["hash"]
                if old_hash != new_hash:
                    changed.append(n)
                    print(f"[DEBUG] 表 {n} 结构变化 - 旧hash: {old_hash[:10]}..., 新hash: {new_hash[:10]}...")

            unchanged = list(common - set(changed))

            print(f"[DEBUG] 刷新结果 - 新增: {list(added)}, 删除: {list(removed)}, 变更: {changed}, 未变: {len(unchanged)}")

            # Step 4：删除 removed + changed
            schemas_deleted = 0
            cards_deleted = 0
            weaviate_deleted = 0
            to_delete_doc_ids = [old_map[n]["id"] for n in (removed | set(changed)) if n in old_map]

            if to_delete_doc_ids:
                w_uuids = [
                    w for (w,) in db.session.query(DataCardDataSource.w_uuid)
                    .filter(DataCardDataSource.doc_id.in_(to_delete_doc_ids))
                    .all()
                ]

                try:
                    schemas_deleted = (
                        db.session.query(UserDatasourceSchema)
                        .filter(UserDatasourceSchema.id.in_(to_delete_doc_ids))
                        .delete(synchronize_session=False)
                    )
                    cards_deleted = (
                        db.session.query(DataCardDataSource)
                        .filter(DataCardDataSource.doc_id.in_(to_delete_doc_ids))
                        .delete(synchronize_session=False)
                    )
                    db.session.commit()
                except SQLAlchemyError:
                    db.session.rollback()

                try:
                    if w_uuids:
                        user_class = getattr(current_user, "weaviate_class_name", None)
                        batch_delete_by_uuids(w_uuids, class_name=user_class)
                        weaviate_deleted = len(w_uuids)
                except Exception:
                    weaviate_deleted = 0

            to_refresh_tables = added | set(changed)

            if not to_refresh_tables and not removed:
                record.table_num = len(new_struct)
                record.status = "available"
                db.session.commit()
                payload = {
                    "mode": "full",
                    "added_tables": [],
                    "removed_tables": [],
                    "changed_tables": [],
                    "unchanged_tables": list(new_names),
                    "schemas_deleted": 0,
                    "cards_deleted": 0,
                    "weaviate_deleted": 0,
                    "cards_generated": 0,
                    "total_tables": len(new_struct),
                }
                return format_response(payload, 200, "刷新完成（full，无变化，跳过重建）")

            # Step 5：新增 + 变更表 重新生成
            to_refresh_tables = added | set(changed)
            generated_cards = []

            if to_refresh_tables:
                db_info = {
                    "database_type": record.db_type,
                    "database_version": _get_database_version(engine),
                    "schema_name": record.schema_name,  # KingBase/PG 需要 schema_name 来过滤
                    "tables": [new_struct[n]["info"] for n in to_refresh_tables],
                }
                # 始终传递 payload（包含 target_schema 等信息），确保各数据库类型的 database_name 正确
                db_connect_info_payload = payload.copy()
                # 注意：record.connect_info 已是加密值，需要解密后再传入
                decrypted_conn = decrypt_connect_info(record.connect_info)
                insert_table_info_to_db(
                    db_info, str(current_user.id), decrypted_conn, record.connect_name,
                    request_id=None,
                    db_connect_info_payload=db_connect_info_payload,
                    schema_name=record.schema_name,
                )
                user_class = getattr(current_user, "weaviate_class_name", None)

                generated_cards = generate_datacards_for_schema(
                    db_info,
                    str(current_user.id),
                    decrypted_conn,
                    record.connect_name,
                    datasource_id=str(record.id),
                    request_id=None,
                    weaviate_class_name=user_class,
                ) or []

            # Step 6：更新数据源状态与统计
            record.table_num = len(new_struct)
            record.status = "available"
            db.session.commit()

            payload = {
                "mode": "full",
                "added_tables": list(added),
                "removed_tables": list(removed),
                "changed_tables": list(changed),
                "unchanged_tables": unchanged,
                "schemas_deleted": int(schemas_deleted),
                "cards_deleted": int(cards_deleted),
                "weaviate_deleted": int(weaviate_deleted),
                "cards_generated": len(generated_cards),
                "total_tables": len(new_struct),
            }

            return format_response(payload, 200, "刷新完成（full）")

        finally:
            # ✅ 关键修复：无论成功/失败/中途 return，都释放 SQLAlchemy Engine 的连接池
            if engine is not None:
                try:
                    engine.dispose()
                except Exception:
                    pass



# 路由注册
api.add_resource(DatasourceToolAPI,
                 "/datasource_tool",
                 "/datasource_tool/<string:ds_id>",
                 "/datasource_tool/<string:ds_id>/refresh")