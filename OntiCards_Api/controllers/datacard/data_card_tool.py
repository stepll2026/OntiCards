"""
 @File: data_card_tool.py
 @Description: 工具类接口：获取当前用户各数据源中的数据卡片（RESTful GET）
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-10-24 10:20
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import flask_login
from flask import Blueprint, request
from flask_login import login_required, current_user
from flask_restful import Resource, Api
from sqlalchemy.engine import make_url
from sqlalchemy import and_, or_, func, cast
from sqlalchemy.dialects.postgresql import JSONB

from controllers.weaviate_db_tool.weaviate_api import add_vector, delete_by_uuid
from extensions.ext_database import db
from models.datasource_infos import DatasourceInfo
from models.user_datasource_schema import UserDatasourceSchema
from models.datacards_datasource import DataCardDataSource
from core.connect_info_encryptor import decrypt_connect_info

# -----------------------------
# Blueprint & API
# -----------------------------
datacard_tool_bp = Blueprint("datacard_tool", __name__)
api = Api(datacard_tool_bp)

# -----------------------------
# 通用响应封装（与项目其它接口保持一致：code/msg/data）
# -----------------------------
def _json_safe(obj):
    if hasattr(obj, "isoformat"):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)
    return obj

def _deep_json_safe(data):
    return json.loads(json.dumps(data, default=_json_safe, ensure_ascii=False))

def format_response(data=None, code=200, msg="操作成功"):
    return {"code": code, "msg": msg, "data": _deep_json_safe(data)}, code

def _escape_like(keyword: str) -> str:
    """
    转义 SQL LIKE/ILIKE 中的特殊字符：`%`、`_`、`\\`，
    避免用户输入的关键词被当作通配符。
    """
    if not keyword:
        return keyword
    return (
        keyword
        .replace('\\', '\\\\')   # 先转义反斜杠（顺序敏感：必须在 %/_ 之前）
        .replace('%', '\\%')
        .replace('_', '\\_')
    )

# -----------------------------
# GET /datacard_tool
# -----------------------------
class DataCardToolAPI(Resource):
    """
    获取当前用户的所有数据卡片（可筛选、可分页）

    Query 参数：
      - datasource_id: str    （可选）按数据源 ID 精确筛选（推荐）
      - connect_name: str     （可选）按数据源名称筛选（已废弃，仅用于兼容）
      - q: str                （可选）关键字检索（在 card_data JSON 文本中模糊匹配）
      - page: int             （可选，默认 1）
      - page_size: int        （可选，默认 50，最大 200）
      - group_by: str         （可选，默认 "datasource"，可选值：datasource / flat）
      - parse_json: bool      （可选，默认 false；true 时把 card_data 解析成对象返回）

    注意：datasource_id 与 connect_name 互斥，若同时传入，优先使用 datasource_id。
          connect_name 筛选在同一用户下可能存在同名数据源，建议使用 datasource_id。
    """

    @login_required
    def get(self):
        user_id = str(flask_login.current_user.id)

        # ---- 读取查询参数 ----
        datasource_id = (request.args.get("datasource_id") or "").strip()
        connect_name = (request.args.get("connect_name") or "").strip()
        keyword = (request.args.get("q") or "").strip()

        try:
            page = max(int(request.args.get("page", 1)), 1)
        except Exception:
            page = 1

        try:
            page_size = int(request.args.get("page_size", 50))
        except Exception:
            page_size = 50
        page_size = max(1, min(page_size, 200))

        group_by = (request.args.get("group_by") or "datasource").lower()
        parse_json = (request.args.get("parse_json") or "false").lower() in ("1", "true", "yes")

        # ---- 1) 找到当前用户的数据源（优先按 datasource_id，否则按 connect_name）----
        ds_query = db.session.query(DatasourceInfo).filter(
            DatasourceInfo.user_id == user_id
        )
        if datasource_id:
            ds_query = ds_query.filter(DatasourceInfo.id == datasource_id)
        elif connect_name:
            ds_query = ds_query.filter(DatasourceInfo.connect_name == connect_name)

        ds_rows: List[DatasourceInfo] = ds_query.order_by(DatasourceInfo.created_at.desc()).all()
        if not ds_rows:
            return format_response(
                {
                    "total_cards": 0,
                    "total_datasources": 0,
                    "items": [] if group_by == "datasource" else []
                },
                200,
                "未找到任何数据源或不满足筛选条件"
            )

        # 建立 (connect_info_hash, schema_name) -> datasource_info 映射（复合键用于区分同 hash 不同 schema）
        ds_map: Dict[str, Dict[str, Any]] = {}
        for r in ds_rows:
            # 某些历史记录可能存了"原始串"，这里统一做脱敏输出
            masked = None
            try:
                # 注意：数据库中存储的是加密后的 connect_info，需要先解密再脱敏
                connect_info_decrypted = decrypt_connect_info(r.connect_info)
                masked = make_url(connect_info_decrypted).render_as_string(hide_password=True)
            except Exception:
                masked = r.connect_info  # 兜底

            # 防御：connect_info_hash 在迁移完成前缺失，避免 KeyError
            ds_hash = getattr(r, "connect_info_hash", None)
            schema_name_key = r.schema_name if r.schema_name is not None else "__NONE__"
            composite_key = (ds_hash, schema_name_key)

            ds_map[composite_key] = {
                "datasource_id": str(r.id),
                "connect_info_hash": ds_hash,
                "connect_name": r.connect_name,
                "db_type": r.db_type,
                "database_name": r.database_name,
                "schema_name": r.schema_name,
                "table_num": r.table_num,
                "status": r.status,
                "connect_info_masked": masked,
            }

        # ---- 2) 在 user_datasource_schemas 中查出这些数据源下的表 ----
        # 重要：必须按 (connect_info_hash, schema_name) 过滤
        # 使用 connect_info_hash 进行稳定匹配
        target_composite_keys: List[tuple] = []
        for r in ds_rows:
            # 防御：兼容迁移未跑的老库，缺字段时按 None 处理
            ds_hash = getattr(r, "connect_info_hash", None)
            target_composite_keys.append((ds_hash, r.schema_name))

        schema_filter_conditions = []
        for hash_val, sn in target_composite_keys:
            if not hash_val:
                continue
            if sn is not None:
                schema_filter_conditions.append(
                    and_(
                        UserDatasourceSchema.connect_info_hash == hash_val,
                        UserDatasourceSchema.schema_name == sn
                    )
                )
            else:
                schema_filter_conditions.append(
                    and_(
                        UserDatasourceSchema.connect_info_hash == hash_val,
                        UserDatasourceSchema.schema_name.is_(None)
                    )
                )

        if not schema_filter_conditions:
            schema_iter = iter([])
        else:
            # PR-G 优化：yield_per(1000) 让 SQLAlchemy 分批从数据库游标拉取，
            # 避免 ORM identity map 一次性缓存全部 row。对于 10万+ 表的盘点场景，
            # 这是核心 OOM 防护点。返回值/契约零变化。
            schema_iter = (
                db.session.query(
                    UserDatasourceSchema.id.label("doc_id"),
                    UserDatasourceSchema.table_name,
                    UserDatasourceSchema.connect_info_hash,
                    UserDatasourceSchema.connect_name,
                    UserDatasourceSchema.schema_name,
                    UserDatasourceSchema.is_filled,
                    UserDatasourceSchema.filled_data,
                    UserDatasourceSchema.is_view,
                    UserDatasourceSchema.view_name
                )
                .filter(
                    UserDatasourceSchema.user_id == user_id,
                    or_(*schema_filter_conditions)
                )
                .yield_per(1000)
            )

        # doc_id（字符串）列表与映射
        # PR-G 优化：直接对 schema_iter 迭代构造 dict（不再先 .all() 装入列表），
        # session 按 1000 条分批从游标读取，identity map 不再爆炸式增长。
        # 契约零变化：返回值结构与原始逻辑完全一致。
        # 复合键统一用 (connect_info_hash, schema_name)，稳定且不含敏感信息。
        doc_id_to_tbl: Dict[str, Dict[str, Any]] = {}
        all_doc_ids: List[str] = []
        # 关键词搜索（q）的转义处理：%/_/\\ 都被 \\ 转义，避免 LIKE 通配符注入。
        escaped_keyword: str = _escape_like(keyword) if keyword else ""
        for row in schema_iter:
            doc_id = str(row.doc_id)
            all_doc_ids.append(doc_id)
            schema_name_key = row.schema_name if row.schema_name is not None else "__NONE__"
            doc_id_to_tbl[doc_id] = {
                "table_name": row.table_name,
                "connect_info_hash": row.connect_info_hash,
                "schema_name": row.schema_name,
                "schema_name_key": schema_name_key,
                "connect_name": row.connect_name,
                "is_filled": row.is_filled,
                "filled_data": row.filled_data,
                "is_view": row.is_view,
                "view_name": row.view_name
            }

        if not doc_id_to_tbl:
            # 没有表结构，直接返回
            return format_response(
                {
                    "total_cards": 0,
                    "total_datasources": len(ds_rows),
                    "items": [] if group_by == "datasource" else []
                },
                200,
                "没有找到任何表结构/数据卡片"
            )

        # 迭代结束后，主动释放 session 对 row 对象的引用，为后续 card_query 让出内存
        db.session.expire_all()

        # ---- 3) 在 datacards_datasource 中查卡片（支持关键词检索 + 分页）----
        # PR-G 优化：
        #   - 先构建 base_query（含 doc_id.in_ 过滤和 keyword 条件）
        #   - count() 使用 func.count(id) 只 count id 列，不扫描 Text 类型的 card_data 列
        #     （极端情况：id 是主键，count 走主键索引快 10x+）
        #   - 分页 query 使用 yield_per(page_size) 流式取出 ORM 对象，内存峰值下降
        # 契约零变化：返回值结构与原始逻辑完全一致。
        base_card_query = db.session.query(DataCardDataSource).filter(
            DataCardDataSource.doc_id.in_(all_doc_ids)
        )
        # 关键词检索逻辑：
        #   搜索字段严格限定为两个——table_name + card_data.Abstract 字段值。
        #   关键修复：旧 LIKE 模式 '%"Abstract":%keyword%' 的 % 通配符贪婪匹配
        #   跨过 Abstract JSON 字段边界，命中 Abstract 之后的字段（如
        #   SQLMeta.foreign_keys.referenced_table、Tags 数组里的关联表名等）。
        #   真实案例：搜 'shop_order' 误返回 refund_case（因为 refund_case.foreign_keys
        #   .referenced_table 包含 "shop_order"）。
        #   修正：用 card_data::jsonb->>'Abstract' 精确提取 Abstract JSON 字段值，
        #   再做 ILIKE。JSONB 路径只在 Abstract 字符串值内匹配，不会跨字段边界。
        #   风险：card_data 必须是合法 JSON 字符串；本系统 card_data 始终由
        #   json.dumps(...) 写入，格式 100% 合法，无需 try/catch 兜底。
        if keyword:
            # 走 PostgreSQL JSONB 路径访问器：cast(card_data AS JSONB)->>'Abstract'
            abstract_text = cast(DataCardDataSource.card_data, JSONB)['Abstract'].astext
            base_card_query = base_card_query.filter(
                or_(
                    # table_name 字段在 datacards_datasource 上有索引，ILIKE 大小写不敏感
                    DataCardDataSource.table_name.ilike(f"%{escaped_keyword}%"),
                    # 精确只对 Abstract 字段值做匹配，杜绝跨 JSON 字段误命中
                    abstract_text.ilike(f"%{escaped_keyword}%")
                )
            )

        # 统计总量（用于分页）—— func.count(id) 走主键索引，不扫描 Text 列
        total_cards = (
            base_card_query.with_entities(func.count(DataCardDataSource.id)).scalar()
        ) or 0

        # 分页查询（yield_per 流式取出，内存峰值 = page_size × ORM 单对象大小）
        cards = (
            base_card_query
            .order_by(DataCardDataSource.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .yield_per(page_size)
            .all()
        )

        # ---- 4) 组装返回体 ----
        if group_by == "flat":
            # 扁平列表
            items: List[Dict[str, Any]] = []
            for c in cards:
                info = doc_id_to_tbl.get(str(c.doc_id), {})
                # 修复：统一用 (connect_info_hash, schema_name) 做复合键，稳定且不含敏感信息
                schema_name_key = info.get("schema_name_key", "__NONE__")
                composite_key = (info.get("connect_info_hash"), schema_name_key)
                ds_info = ds_map.get(composite_key, {})
                # 处理 filled_data：如果是 JSON 字符串，根据 parse_json 决定是否解析
                filled_data_value = info.get("filled_data")
                if filled_data_value and parse_json:
                    try:
                        filled_data_value = json.loads(filled_data_value)
                    except Exception:
                        pass  # 解析失败则保持原字符串
                
                item = {
                    "doc_id": str(c.doc_id),
                    "datasource_id": ds_info.get("datasource_id"),
                    "table_name": info.get("table_name"),
                    "connect_name": ds_info.get("connect_name") or info.get("connect_name"),
                    "connect_info_masked": ds_info.get("connect_info_masked"),
                    "db_type": ds_info.get("db_type"),
                    "database_name": ds_info.get("database_name"),
                    "w_uuid": c.w_uuid,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                    "card_data": json.loads(c.card_data) if parse_json else c.card_data,
                    "is_filled": info.get("is_filled"),
                    "filled_data": filled_data_value,
                    "is_view": info.get("is_view"),
                    "view_name": info.get("view_name")
                }
                items.append(item)

            data = {
                "total_cards": total_cards,
                "total_datasources": len(ds_rows),
                "page": page,
                "page_size": page_size,
                "items": items,
            }
            # PR-G 优化：组装完 items 后立即释放 ORM 对象引用
            # items 是纯 dict，对返回体的字段值已全部快照，ORM 实例不再需要驻留
            del cards
            db.session.expire_all()
            return format_response(data, 200, "获取成功")

        # 默认：按数据源分组返回
        # 修复：统一用 (connect_info_hash, schema_name) 做复合键
        grouped: Dict[tuple, List[Dict[str, Any]]] = {}
        for c in cards:
            tb_info = doc_id_to_tbl.get(str(c.doc_id), {})
            schema_name_key = tb_info.get("schema_name_key", "__NONE__")
            composite_key = (tb_info.get("connect_info_hash"), schema_name_key)
            grouped.setdefault(composite_key, [])
            # 处理 filled_data：如果是 JSON 字符串，根据 parse_json 决定是否解析
            filled_data_value = tb_info.get("filled_data")
            if filled_data_value and parse_json:
                try:
                    filled_data_value = json.loads(filled_data_value)
                except Exception:
                    pass  # 解析失败则保持原字符串
            
            ds_info = ds_map.get(composite_key, {})
            grouped[composite_key].append({
                "doc_id": str(c.doc_id),
                "datasource_id": ds_info.get("datasource_id"),
                "table_name": tb_info.get("table_name"),
                "connect_name": tb_info.get("connect_name"),
                "connect_info_masked": ds_info.get("connect_info_masked"),
                "w_uuid": c.w_uuid,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                "card_data": json.loads(c.card_data) if parse_json else c.card_data,
                "is_filled": tb_info.get("is_filled"),
                "filled_data": filled_data_value,
                "is_view": tb_info.get("is_view"),
                "view_name": tb_info.get("view_name")
            })

        items_grouped: List[Dict[str, Any]] = []
        for composite_key, cards_in_ds in grouped.items():
            ds_info = ds_map.get(composite_key, {})
            items_grouped.append({
                "datasource": {
                    "datasource_id": ds_info.get("datasource_id"),
                    "connect_name": ds_info.get("connect_name"),
                    "db_type": ds_info.get("db_type"),
                    "database_name": ds_info.get("database_name"),
                    "schema_name": ds_info.get("schema_name"),
                    "table_num": ds_info.get("table_num"),
                    "status": ds_info.get("status"),
                    "connect_info_masked": ds_info.get("connect_info_masked")
                },
                "cards": cards_in_ds
            })

        data = {
            "total_cards": total_cards,
            "total_datasources": len(ds_rows),
            "page": page,
            "page_size": page_size,
            "items": items_grouped
        }
        # PR-G 优化：组装完 items_grouped 后立即释放 ORM 对象引用
        del cards
        db.session.expire_all()
        return format_response(data, 200, "获取成功")

    @login_required
    def put(self):
        """
        更新数据卡片：
        Request JSON 示例（与提案一致）：
        {
            "doc_id": "...",
            "table_name": "user_sqlserver",
            "connect_name": "数据源_MSSQL",
            "connect_info_masked": "...",
            "w_uuid": "旧向量UUID（可选，若传则更精准定位记录）",
            "card_data": { ... }   # 必填，新的卡片JSON对象
        }

        流程：
          1) 根据 doc_id（若给了 w_uuid 则优先以 w_uuid）查找 datacards_datasource 当前记录；
          2) 用旧 w_uuid 删除向量库对象（忽略删除失败但记录日志）；
          3) 使用新的 card_data 生成并写入向量库，获得新的 w_uuid；
          4) 更新数据库该条记录的 card_data 与 w_uuid；
          5) 返回更新后的记录。
        """
        try:
            payload = request.get_json(force=True, silent=False) or {}
        except Exception:
            return format_response(None, 400, "请求体不是有效的 JSON")

        doc_id = str(payload.get("doc_id") or "").strip()
        new_card_obj = payload.get("card_data")
        prefer_old_wuuid = str(payload.get("w_uuid") or "").strip()

        # 基础校验
        if not doc_id:
            return format_response(None, 400, "缺少必填字段：doc_id")
        if not isinstance(new_card_obj, dict):
            return format_response(None, 400, "card_data 必须为对象（JSON）")

        # 一致性校验：card_data.DocInfo.doc_id（若存在）应与 doc_id 一致
        inner_doc_id = (
            (new_card_obj.get("DocInfo") or {}).get("doc_id") if isinstance(new_card_obj.get("DocInfo"), dict) else None
        )
        if inner_doc_id and str(inner_doc_id) != doc_id:
            return format_response(None, 400, "card_data.DocInfo.doc_id 与 doc_id 不一致")

        # 精确定位待更新记录
        q = db.session.query(DataCardDataSource).filter(DataCardDataSource.doc_id == doc_id)
        record = None
        if prefer_old_wuuid:
            record = q.filter(DataCardDataSource.w_uuid == prefer_old_wuuid).first()
        if not record:
            # 若未传 w_uuid 或未命中，就按 doc_id 拿“最近更新”的一条
            record = q.order_by(DataCardDataSource.updated_at.desc()).first()

        if not record:
            return format_response(None, 404, "未找到要更新的数据卡片记录")

        old_wuuid = record.w_uuid
        user_class = getattr(current_user, "weaviate_class_name", None)

        # 修复版：先添加新向量，再更新数据库，最后删除旧向量
        # 这样即使删除旧向量失败，数据也是完整的

        # 步骤1：添加新向量
        try:
            # 若 card_data 中 DocInfo.doc_id 缺失，则补齐，避免向量入库缺 doc_id
            if not inner_doc_id:
                new_card_obj.setdefault("DocInfo", {})
                if isinstance(new_card_obj["DocInfo"], dict):
                    new_card_obj["DocInfo"]["doc_id"] = doc_id

            new_wuuid = add_vector(new_card_obj, class_name=user_class)
            new_wuuid = str(new_wuuid)
        except Exception as e:
            # 新向量添加失败，终止更新
            return format_response(None, 500, f"向量入库失败：{e}")

        # 步骤2：更新数据库记录
        try:
            record.card_data = json.dumps(new_card_obj, ensure_ascii=False)
            record.w_uuid = new_wuuid
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # 数据库更新失败，回滚删除新向量
            try:
                delete_by_uuid(new_wuuid, class_name=user_class)
            except Exception:
                pass
            return format_response(None, 500, f"数据库更新失败：{e}")

        # 步骤3：删除旧向量（如果存在）
        # 注意：即使删除失败也不影响整体流程，因为新向量已经生效
        _del_ok = False
        if old_wuuid:
            try:
                _del_ok = delete_by_uuid(old_wuuid, class_name=user_class)
            except Exception:
                _del_ok = False

        # 4) 组装返回
        resp = record.to_dict()
        # 附带一点过程信息便于前端提示（可选）
        resp["_vector_ops"] = {
            "delete_old_ok": _del_ok,
            "old_w_uuid": old_wuuid,
            "new_w_uuid": new_wuuid
        }
        # 兼容你 GET 的 parse_json 语义：PUT 默认返回对象形式的 card_data
        try:
            resp["card_data"] = new_card_obj
        except Exception:
            pass

        return format_response(resp, 200, "更新成功")


# -----------------------------
# GET /datacard_tool/all
# -----------------------------
class DataCardToolAllAPI(Resource):
    """
    获取当前用户的所有数据卡片（不分页，一次性返回全部）

    Query 参数：
      - datasource_id: str    （可选）按数据源 ID 精确筛选（推荐）
      - connect_name: str     （可选）按数据源名称筛选（已废弃，仅用于兼容）
      - q: str                （可选）关键字检索（在 card_data JSON 文本中模糊匹配）
      - group_by: str         （可选，默认 "datasource"，可选值：datasource / flat）
      - parse_json: bool      （可选，默认 false；true 时把 card_data 解析成对象返回）

    返回结构（与 /datacard_tool 分页接口结构一致）：
    {
      "code": 200,
      "msg": "操作成功",
      "data": {
        "total_cards": 12,
        "total_datasources": 2,
        "items": [...]  # 与 /datacard_tool 一致（flat 或 datasource 分组）
      }
    }

    注意：datasource_id 与 connect_name 互斥，若同时传入，优先使用 datasource_id。
          connect_name 筛选在同一用户下可能存在同名数据源，建议使用 datasource_id。
    """

    @login_required
    def get(self):
        user_id = str(flask_login.current_user.id)

        # ---- 读取查询参数 ----
        datasource_id = (request.args.get("datasource_id") or "").strip()
        connect_name = (request.args.get("connect_name") or "").strip()
        keyword = (request.args.get("q") or "").strip()
        group_by = (request.args.get("group_by") or "datasource").lower()
        parse_json = (request.args.get("parse_json") or "false").lower() in ("1", "true", "yes")

        # ---- 1) 找到当前用户的数据源（优先按 datasource_id，否则按 connect_name）----
        ds_query = db.session.query(DatasourceInfo).filter(
            DatasourceInfo.user_id == user_id
        )
        if datasource_id:
            ds_query = ds_query.filter(DatasourceInfo.id == datasource_id)
        elif connect_name:
            ds_query = ds_query.filter(DatasourceInfo.connect_name == connect_name)

        ds_rows: List[DatasourceInfo] = ds_query.order_by(DatasourceInfo.created_at.desc()).all()
        if not ds_rows:
            return format_response(
                {
                    "total_cards": 0,
                    "total_datasources": 0,
                    "items": [] if group_by == "datasource" else [],
                },
                200,
                "未找到任何数据源或不满足筛选条件"
            )

        # 建立 (connect_info_hash, schema_name) -> datasource_info 映射（复合键用于区分同 hash 不同 schema）
        ds_map: Dict[str, Dict[str, Any]] = {}

        for r in ds_rows:
            masked = None
            try:
                # 注意：数据库中存储的是加密后的 connect_info，需要先解密再脱敏
                connect_info_decrypted = decrypt_connect_info(r.connect_info)
                masked = make_url(connect_info_decrypted).render_as_string(hide_password=True)
            except Exception:
                masked = r.connect_info

            # 使用复合键：(connect_info_hash, schema_name) 来区分同一用户下同 connect_info 不同 schema 的数据源
            schema_name_key = r.schema_name if r.schema_name is not None else "__NONE__"
            composite_key = (r.connect_info_hash, schema_name_key)

            ds_map[composite_key] = {
                "datasource_id": str(r.id),
                "connect_info_hash": r.connect_info_hash,
                "connect_name": r.connect_name,
                "db_type": r.db_type,
                "database_name": r.database_name,
                "schema_name": r.schema_name,
                "table_num": r.table_num,
                "status": r.status,
                "connect_info_masked": masked,
            }

        # ---- 2) 在 user_datasource_schemas 中查出这些数据源下的表 ----
        # 重要：必须按 (connect_info_hash, schema_name) 过滤，避免返回同 connect_info 不同 schema 的表
        # 使用 connect_info_hash 进行稳定匹配
        # 构建 (connect_info_hash, schema_name) 的目标列表
        target_composite_keys: List[tuple] = []
        for r in ds_rows:
            schema_name_key = r.schema_name if r.schema_name is not None else "__NONE__"
            target_composite_keys.append((r.connect_info_hash, r.schema_name))  # 使用原始 schema_name (可为 None)

        # 查询时按 composite key 过滤
        schema_filter_conditions = []
        for hash_val, sn in target_composite_keys:
            if not hash_val:
                continue
            if sn is not None:
                schema_filter_conditions.append(
                    and_(
                        UserDatasourceSchema.connect_info_hash == hash_val,
                        UserDatasourceSchema.schema_name == sn
                    )
                )
            else:
                schema_filter_conditions.append(
                    and_(
                        UserDatasourceSchema.connect_info_hash == hash_val,
                        UserDatasourceSchema.schema_name.is_(None)
                    )
                )

        if not schema_filter_conditions:
            schema_rows = []
        else:
            schema_rows = (
            db.session.query(
                UserDatasourceSchema.id.label("doc_id"),
                UserDatasourceSchema.table_name,
                UserDatasourceSchema.connect_info_hash,
                UserDatasourceSchema.connect_name,
                UserDatasourceSchema.schema_name,
                UserDatasourceSchema.is_filled,
                UserDatasourceSchema.filled_data,
                UserDatasourceSchema.is_view,
                UserDatasourceSchema.view_name
            )
            .filter(
                UserDatasourceSchema.user_id == user_id,
                or_(*schema_filter_conditions)
            )
            .all()
        )

        if not schema_rows:
            return format_response(
                {
                    "total_cards": 0,
                    "total_datasources": len(ds_rows),
                    "items": [] if group_by == "datasource" else [],
                },
                200,
                "没有找到任何表结构/数据卡片"
            )

        # doc_id（字符串）列表与映射
        # 复合键统一用 (connect_info_hash, schema_name)，稳定且不含敏感信息。
        doc_id_to_tbl: Dict[str, Dict[str, Any]] = {}
        all_doc_ids: List[str] = []
        # 关键词搜索（q）的转义处理：%/_/\\ 都被 \\ 转义，避免 LIKE 通配符注入。
        escaped_keyword: str = _escape_like(keyword) if keyword else ""
        for row in schema_rows:
            doc_id = str(row.doc_id)
            all_doc_ids.append(doc_id)
            schema_name_key = row.schema_name if row.schema_name is not None else "__NONE__"
            doc_id_to_tbl[doc_id] = {
                "table_name": row.table_name,
                "connect_info_hash": row.connect_info_hash,
                "schema_name": row.schema_name,
                "schema_name_key": schema_name_key,
                "connect_name": row.connect_name,
                "is_filled": row.is_filled,
                "filled_data": row.filled_data,
                "is_view": row.is_view,
                "view_name": row.view_name
            }

        # ---- 3) 在 datacards_datasource 中查卡片（不分页）----
        card_query = (
            db.session.query(DataCardDataSource)
            .filter(DataCardDataSource.doc_id.in_(all_doc_ids))
        )
        # 关键词检索逻辑：与分页端点一致——单表 OR 查询，走索引列 + JSONB 精确路径。
        # Abstract 必须从 card_data JSON 中精确提取，杜绝 LIKE 模式跨字段误命中
        # （如 foreign_keys.referenced_table、Tags 数组里的关联表名）。
        if keyword:
            abstract_text = cast(DataCardDataSource.card_data, JSONB)['Abstract'].astext
            card_query = card_query.filter(
                or_(
                    DataCardDataSource.table_name.ilike(f"%{escaped_keyword}%"),
                    abstract_text.ilike(f"%{escaped_keyword}%")
                )
            )

        total_cards = card_query.count()

        # /all 一次性返回所有卡片（不分页、不截断），
        # 但走流式响应（PR-A/B），内存峰值从 ~90MB 降到几百 KB，
        # 避免单 worker 被 gunicorn worker_memory_limit SIGKILL。
        # 大数据量场景建议前端改用 /datacard_tool 分页接口。
        cards: List[DataCardDataSource] = list(
            card_query.order_by(DataCardDataSource.updated_at.desc()).all()
        )

        # ============================================================
        # PR-A/B: 流式 Response 防 OOM
        #
        # 历史：旧版走 format_response(data)，会先把整个 dict 一次性
        # 序列化成 bytes 再交给 Flask。30MB 响应 → Python 进程里
        # 同时驻留 ~60MB 的 dict + ~30MB 的 bytes → 内存峰值 90MB+，
        # 在 worker_memory_limit=1500MB 下不会立刻挂，但碰上盘点/查询
        # 等其他重任务同时跑 → worker 被 SIGKILL → 前端看到 404。
        #
        # 修复：返回 Response(generator)，边读卡片边序列化边写入 socket。
        # 内存峰值 ≈ 单条卡片大小（约几百 KB）。
        # 前端零改动（浏览器/axios 自动处理 chunked）。
        # ============================================================
        from flask import Response

        if group_by == "flat":
            def _gen_flat():
                # 头部（一次性写出固定前缀）
                yield (
                    b'{"code":200,"msg":"\xe6\x93\x8d\xe4\xbd\x9c\xe6\x88\x90\xe5\x8a\x9f",'
                    b'"data":{"total_cards":' + str(total_cards).encode() +
                    b',"total_datasources":' + str(len(ds_rows)).encode() +
                    b',"items":['
                )
                first = True
                for c in cards:
                    info = doc_id_to_tbl.get(str(c.doc_id), {})
                    # 修复：统一用 (connect_info_hash, schema_name) 做复合键，稳定且不含敏感信息
                    schema_name_key = info.get("schema_name_key", "__NONE__")
                    composite_key = (info.get("connect_info_hash"), schema_name_key)
                    ds_info = ds_map.get(composite_key, {})
                    filled_data_value = info.get("filled_data")
                    if filled_data_value and parse_json:
                        try:
                            filled_data_value = json.loads(filled_data_value)
                        except Exception:
                            pass

                    item = {
                        "doc_id": str(c.doc_id),
                        "datasource_id": ds_info.get("datasource_id"),
                        "table_name": info.get("table_name"),
                        "connect_name": ds_info.get("connect_name") or info.get("connect_name"),
                        "connect_info_masked": ds_info.get("connect_info_masked"),
                        "db_type": ds_info.get("db_type"),
                        "database_name": ds_info.get("database_name"),
                        "w_uuid": c.w_uuid,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                        "card_data": json.loads(c.card_data) if parse_json else c.card_data,
                        "is_filled": info.get("is_filled"),
                        "filled_data": filled_data_value,
                        "is_view": info.get("is_view"),
                        "view_name": info.get("view_name"),
                    }
                    chunk = json.dumps(item, ensure_ascii=False, default=_json_safe)
                    if first:
                        yield chunk.encode("utf-8")
                        first = False
                    else:
                        yield b"," + chunk.encode("utf-8")
                yield b"]}}"

            resp = Response(_gen_flat(), mimetype="application/json; charset=utf-8")
            # PR-B: 元数据响应头（前端无需解析完整个 body 才能知道总数）
            resp.headers["X-Response-Mode"] = "streaming"
            resp.headers["X-Total-Cards"] = str(total_cards)
            resp.headers["X-Response-Datasources"] = str(len(ds_rows))
            resp.headers["X-Group-By"] = "flat"
            return resp

        # 默认：按数据源分组返回（流式版）
        # 必须在内存中聚合到 grouped，因为 JSON 顶层 items 元素形状是
        #   {datasource: {...}, cards: [...]}
        # 如果按单卡流式输出，每张卡前都要重复 datasource 块，破坏结构。
        # 单条 dict ≈ 1KB（不解析时），300 张 ≈ 300KB，远低于 worker 内存阈值。
        # 流式 Response 仍消除了 format_response 时代 dict+bytes 双倍驻留的峰值。
        # 修复：统一用 (connect_info_hash, schema_name) 做复合键。
        grouped: Dict[tuple, List[Dict[str, Any]]] = {}
        for c in cards:
            tb_info = doc_id_to_tbl.get(str(c.doc_id), {})
            schema_name_key = tb_info.get("schema_name_key", "__NONE__")
            composite_key = (tb_info.get("connect_info_hash"), schema_name_key)
            grouped.setdefault(composite_key, [])
            filled_data_value = tb_info.get("filled_data")
            if filled_data_value and parse_json:
                try:
                    filled_data_value = json.loads(filled_data_value)
                except Exception:
                    pass

            ds_info = ds_map.get(composite_key, {})
            grouped[composite_key].append({
                "doc_id": str(c.doc_id),
                "datasource_id": ds_info.get("datasource_id"),
                "table_name": tb_info.get("table_name"),
                "connect_name": tb_info.get("connect_name"),
                "connect_info_masked": ds_info.get("connect_info_masked"),
                "w_uuid": c.w_uuid,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                "card_data": json.loads(c.card_data) if parse_json else c.card_data,
                "is_filled": tb_info.get("is_filled"),
                "filled_data": filled_data_value,
                "is_view": tb_info.get("is_view"),
                "view_name": tb_info.get("view_name"),
            })

        def _gen_grouped():
            yield (
                b'{"code":200,"msg":"\xe6\x93\x8d\xe4\xbd\x9c\xe6\x88\x90\xe5\x8a\x9f",'
                b'"data":{"total_cards":' + str(total_cards).encode() +
                b',"total_datasources":' + str(len(ds_rows)).encode() +
                b',"items":['
            )
            first = True
            # 按 connect_name 排序输出（保持稳定顺序，便于前端 key）
            sorted_keys = sorted(
                grouped.keys(),
                key=lambda k: (ds_map.get(k, {}).get("connect_name") or "")
            )
            for composite_key in sorted_keys:
                cards_in_ds = grouped[composite_key]
                ds_info = ds_map.get(composite_key, {})
                block = {
                    "datasource": {
                        "datasource_id": ds_info.get("datasource_id"),
                        "connect_name": ds_info.get("connect_name"),
                        "db_type": ds_info.get("db_type"),
                        "database_name": ds_info.get("database_name"),
                        "schema_name": ds_info.get("schema_name"),
                        "table_num": ds_info.get("table_num"),
                        "status": ds_info.get("status"),
                        "connect_info_masked": ds_info.get("connect_info_masked"),
                    },
                    "cards": cards_in_ds,
                }
                chunk = json.dumps(block, ensure_ascii=False, default=_json_safe)
                if first:
                    yield chunk.encode("utf-8")
                    first = False
                else:
                    yield b"," + chunk.encode("utf-8")
            yield b"]}}"

        resp = Response(_gen_grouped(), mimetype="application/json; charset=utf-8")
        # PR-B: 元数据响应头
        resp.headers["X-Response-Mode"] = "streaming"
        resp.headers["X-Total-Cards"] = str(total_cards)
        resp.headers["X-Response-Datasources"] = str(len(ds_rows))
        resp.headers["X-Group-By"] = "datasource"
        return resp


# 路由注册
api.add_resource(DataCardToolAPI, "/datacard_tool")
api.add_resource(DataCardToolAllAPI, "/datacard_tool/all")
