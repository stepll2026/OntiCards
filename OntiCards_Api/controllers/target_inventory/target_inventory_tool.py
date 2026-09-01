"""
 @File: target_inventory_tool.py
 @Description: 定向盘点 API 定义 - 用户手动选择数据源中的表进行字段注释推荐和表关系确认
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-01-21 14:45
"""

from __future__ import annotations
import json
import uuid
from datetime import datetime

from flask import Blueprint, request
from flask_restful import Resource, Api
from flask_login import login_required, current_user
from extensions.ext_database import db

from models.datasource_infos import DatasourceInfo
from models.datacards_datasource import DataCardDataSource

from controllers.datasource.database_schema_extractor import get_db_engine
from controllers.target_inventory.utils import _safe_load_card, extract_connect_and_table

# 提供 3 个 API：tables/run/confirm（最小闭环）

# 新增的两个模型（按实际路径改）
from models.global_inventory import (
    TargetInventoryJob,
    TargetInventoryJobResult,
    TableRelationship,
    TableRelationshipCard,
    FieldMapping
)
from sqlalchemy.orm.attributes import flag_modified

target_inventory_bp = Blueprint("target_inventory_bp", __name__)
api = Api(target_inventory_bp)

def resp(data=None, code=200, msg="操作成功"):
    return {"code": code, "msg": msg, "data": data}, code

def _get_latest_datacard(datasource_id: str, table_name: str):
    """
    根据 datasource_id 和 table_name 获取最新数据卡片

    Args:
        datasource_id: 数据源ID
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
        from models.datasource_infos import DatasourceInfo
        ds = db.session.query(DatasourceInfo).filter(DatasourceInfo.id == datasource_id).first()
        if not ds:
            return None

        connect_name = ds.connect_name
        rows = db.session.query(DataCardDataSource).order_by(DataCardDataSource.updated_at.desc()).all()
        for r in rows:
            card = _safe_load_card(r)
            cn, tn = extract_connect_and_table(card)
            if cn == connect_name and tn == table_name:
                return r
        return None

    return result

class TablesAPI(Resource):
    @login_required
    def get(self):
        # 改用 datasource_id 而不是 connect_name
        datasource_id = (request.args.get("datasource_id") or "").strip()
        if not datasource_id:
            return resp(None, 400, "缺少 datasource_id")

        # 直接通过索引字段查询，无需全表扫描
        rows = (
            db.session.query(DataCardDataSource)
            .filter(DataCardDataSource.datasource_id == datasource_id)
            .order_by(DataCardDataSource.updated_at.desc())
            .all()
        )

        # 按表名分组，取每个表的最新记录
        latest_by_table = {}
        for r in rows:
            # 优先使用新字段
            tn = r.table_name if hasattr(r, 'table_name') and r.table_name else None
            # 如果新字段为空，回退到解析 card_data
            if not tn:
                card = _safe_load_card(r)
                _, tn = extract_connect_and_table(card)

            if not tn:
                continue
            if tn not in latest_by_table:
                latest_by_table[tn] = r

        # 查询 user_datasource_schema 获取 is_filled 信息
        from models.user_datasource_schema import UserDatasourceSchema
        ds = db.session.query(DatasourceInfo).filter(DatasourceInfo.id == datasource_id).first()
        if not ds:
            return resp(None, 404, "数据源不存在")

        connect_name = ds.connect_name
        schema_records = (
            db.session.query(UserDatasourceSchema)
            .filter(
                UserDatasourceSchema.user_id == current_user.id,
                UserDatasourceSchema.connect_name == connect_name
            )
            .all()
        )

        # 构建表名 -> is_filled 的映射
        is_filled_map = {rec.table_name: rec.is_filled for rec in schema_records}

        # 构建表名 -> filled_data 的映射（用于计算AI填充字段数）
        filled_data_map = {}
        for rec in schema_records:
            if rec.is_filled and rec.filled_data:
                try:
                    filled_data_map[rec.table_name] = json.loads(rec.filled_data)
                except Exception:
                    filled_data_map[rec.table_name] = {}

        out = []
        for tn, rec in latest_by_table.items():
            card = _safe_load_card(rec)
            cols = ((card.get("SQLMeta") or {}).get("columns") or [])
            missing = sum(1 for c in cols if not (c.get("comment") or "").strip())

            # 判断是否经过LLM填充
            is_auto_filled = is_filled_map.get(tn, False)

            # 计算质量等级
            if missing > 0:
                quality_level = "low"  # 有缺失字段 -> 低质量（目标表）
            elif is_auto_filled:
                quality_level = "medium"  # 无缺失但LLM填充 -> 中等质量（可选参考表）
            else:
                quality_level = "high"  # 无缺失且非LLM填充 -> 高质量（优质参考表）

            item = {
                "table_name": tn,
                "missing_comment_fields": missing,
                "is_auto_filled": is_auto_filled,
                "quality_level": quality_level
            }

            # 目标表（is_auto_filled=True）时，从 filled_data 中获取AI自动填充的字段数量
            if is_auto_filled:
                filled_data = filled_data_map.get(tn) or {}
                detailed_fill = filled_data.get("detailed_fill") or {}
                filled_map = detailed_fill.get("filled_map") or {}
                item["auto_filled_count"] = len(filled_map)

            out.append(item)

        # 按质量等级和缺失字段数排序：low -> medium -> high，同级别按缺失数降序
        quality_order = {"low": 0, "medium": 1, "high": 2}
        out.sort(key=lambda x: (quality_order[x["quality_level"]], -x["missing_comment_fields"]))
        return resp(out)

class RunAPI(Resource):
    @login_required
    def post(self):
        # 延迟导入，避免循环依赖
        from controllers.target_inventory.target_inventory_service import run_target_inventory
        import hashlib

        payload = request.get_json(force=True, silent=False) or {}

        # 获取参数
        datasource_id = str(payload.get("datasource_id") or "").strip()
        target_tables = payload.get("target_tables") or []
        ref_tables = payload.get("ref_tables") or []
        dict_file_id = payload.get("dict_file_id")
        options = payload.get("options") or {}

        if not datasource_id:
            return resp(None, 400, "缺少 datasource_id")
        if not target_tables:
            return resp(None, 400, "缺少 target_tables")

        # 查询数据源
        ds = db.session.query(DatasourceInfo).filter(DatasourceInfo.id == datasource_id).first()
        if not ds:
            return resp(None, 404, "数据源不存在")

        # 计算 schema_hash（改进版：基于真实表结构）
        from controllers.datasource.datasource_tool import calculate_schema_hash_from_datasource
        schema_name = options.get("schema_name") or getattr(ds, "schema_name", None) or "public"
        schema_hash = calculate_schema_hash_from_datasource(
            datasource_id=datasource_id,
            schema_name=schema_name
        )

        # 创建 Job
        job = TargetInventoryJob(
            user_id=current_user.id,
            datasource_id=datasource_id,
            schema_hash=schema_hash,
            target_tables=target_tables,
            ref_tables=ref_tables,
            dict_file_id=dict_file_id,
            options=options,
            status="running"
        )
        db.session.add(job)
        db.session.commit()

        job_id = str(job.id)

        # 执行任务
        try:
            sample_size = int(options.get("sample_size", 100))
            topk = int(options.get("topk", 10))
            vector_topn = int(options.get("vector_topn", 20))

            job_obj, res_obj = run_target_inventory(
                job_id=job_id,
                datasource_id=datasource_id,
                target_tables=target_tables,
                ref_tables=ref_tables,
                dict_file_id=dict_file_id,
                schema_name=schema_name,
                sample_size=sample_size,
                topk=topk,
                vector_topn=vector_topn
            )

            job.status = "completed"
            db.session.commit()

            return resp({"job": job_obj.to_dict(), "result": res_obj.to_dict()}, 200, "定向盘点完成")
        except Exception as e:
            job.status = "failed"
            job.error_msg = str(e)
            db.session.commit()
            return resp(None, 500, f"定向盘点失败: {str(e)}")

class ConfirmAPI(Resource):
    @login_required
    def post(self):
        # 延迟导入，避免循环依赖
        from controllers.target_inventory.target_inventory_service import apply_confirm

        payload = request.get_json(force=True, silent=False) or {}
        datasource_id = (payload.get("datasource_id") or "").strip()  # 改用 datasource_id
        table_name = (payload.get("table_name") or "").strip()
        updates = payload.get("updates") or []  # [{"column":"deleted","comment":"删除标志(0否1是)"}]

        if not datasource_id or not table_name or not updates:
            return resp(None, 400, "datasource_id/table_name/updates 必填")

        # 1) 取最新 datacard（使用新的查询方式）
        rec = _get_latest_datacard(datasource_id, table_name)
        if not rec:
            return resp(None, 404, "datacard not found")

        doc_id = str(rec.doc_id)
        old_wuuid = rec.w_uuid
        card = json.loads(rec.card_data) if isinstance(rec.card_data, str) else (rec.card_data or {})

        # 2) 修改 SQLMeta.columns[].comment
        cols = ((card.get("SQLMeta") or {}).get("columns") or [])
        upd_map = {u["column"]: u["comment"] for u in updates if u.get("column") and u.get("comment")}
        for c in cols:
            name = c.get("name")
            if name in upd_map:
                c["comment"] = upd_map[name]
        card.setdefault("SQLMeta", {})["columns"] = cols

        # 3) 按 DataCardTool.put 的同款流程回填（DB+向量）
        ops = apply_confirm(datasource_id, table_name, doc_id, old_wuuid, card)

        return resp({"doc_id": doc_id, "table_name": table_name, "_vector_ops": ops}, 200, "回填成功")

class JobResultAPI(Resource):
    @login_required
    def get(self, job_id):
        """
        查询盘点任务结果

        Args:
            job_id: 任务ID

        Returns:
            {
                "job": {...},
                "result": {...}
            }
        """
        # 查询任务
        job = db.session.query(TargetInventoryJob).filter(
            TargetInventoryJob.id == job_id
        ).first()

        if not job:
            return resp(None, 404, "任务不存在")

        # 查询结果
        result = db.session.query(TargetInventoryJobResult).filter(
            TargetInventoryJobResult.job_id == job_id
        ).first()

        return resp({
            "job": job.to_dict(),
            "result": result.to_dict() if result else None
        })

class RelationshipsAPI(Resource):
    @login_required
    def get(self, job_id):
        """
        查询表关系结果

        Args:
            job_id: 任务ID

        Returns:
            {
                "relationships": [...],
                "cards": [...]
            }
        """
        # 查询结果
        result = db.session.query(TargetInventoryJobResult).filter(
            TargetInventoryJobResult.job_id == job_id
        ).first()

        if not result:
            return resp(None, 404, "任务结果不存在")

        relationships_data = result.table_relationships_json or {}
        cards_data = result.relationship_cards_json or {}

        return resp({
            "relationships": relationships_data.get("relationships", []),
            "cards": cards_data.get("cards", [])
        })

class RelationshipGraphAPI(Resource):
    @login_required
    def get(self, job_id):
        """
        获取关系图数据（用于可视化）

        Args:
            job_id: 任务ID

        Returns:
            {
                "nodes": [...],
                "edges": [...]
            }
        """
        from controllers.target_inventory.relationship_card_generator import export_cards_to_graph_format

        # 查询结果
        result = db.session.query(TargetInventoryJobResult).filter(
            TargetInventoryJobResult.job_id == job_id
        ).first()

        if not result:
            return resp(None, 404, "任务结果不存在")

        cards_data = result.relationship_cards_json or {}
        cards = cards_data.get("cards", [])

        if not cards:
            return resp({"nodes": [], "edges": []})

        graph_data = export_cards_to_graph_format(cards)
        return resp(graph_data)

class FieldMappingsAPI(Resource):
    @login_required
    def get(self, job_id):
        """
        查询字段映射结果

        Args:
            job_id: 任务ID

        Returns:
            {
                "table_name": {
                    "column_name": {
                        "candidates": [...],
                        "need_human_confirm": true/false
                    }
                }
            }
        """
        # 查询结果
        result = db.session.query(TargetInventoryJobResult).filter(
            TargetInventoryJobResult.job_id == job_id
        ).first()

        if not result:
            return resp(None, 404, "任务结果不存在")

        field_mappings = result.field_mappings_json or {}
        return resp(field_mappings)

class ConfirmFieldMappingsAPI(Resource):
    @login_required
    def post(self):
        """
        用户确认字段映射后，将最终结果写入 field_mapping 表

        Args:
            job_id: 任务ID
            confirmed_mappings: 用户确认的字段映射列表
                [
                    {
                        "source_table": "table1",
                        "source_column": "col1",
                        "target_table": "table2",
                        "target_column": "col2",
                        "mapping_type": "exact_match",
                        "confidence": 0.95,
                        "mapping_basis": "name_similarity"
                    },
                    ...
                ]

        Returns:
            {
                "deleted": 删除的旧记录数,
                "inserted": 插入的新记录数
            }
        """
        from controllers.target_inventory.target_inventory_service import confirm_field_mappings

        payload = request.get_json(force=True, silent=False) or {}
        job_id = payload.get("job_id")
        confirmed_mappings = payload.get("confirmed_mappings") or []

        if not job_id:
            return resp(None, 400, "缺少 job_id")
        if not confirmed_mappings:
            return resp(None, 400, "缺少 confirmed_mappings")

        # 查询任务
        job = db.session.query(TargetInventoryJob).filter(
            TargetInventoryJob.id == job_id
        ).first()

        if not job:
            return resp(None, 404, "任务不存在")

        # 调用确认函数
        try:
            result = confirm_field_mappings(
                datasource_id=job.datasource_id,
                schema_hash=job.schema_hash,
                confirmed_mappings=confirmed_mappings,
                job_id=job_id
            )
            return resp(result, 200, "字段映射确认成功")
        except Exception as e:
            return resp(None, 500, f"字段映射确认失败: {str(e)}")

class ConfirmFieldRecommendationsAPI(Resource):
    @login_required
    def post(self):
        """
        确认字段推荐结果（V2版本）

        Args:
            job_id: 任务ID
            confirmations: 用户确认的字段推荐
                {
                    "table_name": {
                        "column_name": {
                            "action": "accept" or "reject" or "custom",
                            "selected_candidate": {...},
                            "custom_comment": "自定义注释"
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
        from controllers.target_inventory.confirmation_service import confirm_field_recommendations

        payload = request.get_json(force=True, silent=False) or {}
        job_id = payload.get("job_id")
        confirmations = payload.get("confirmations") or {}

        if not job_id:
            return resp(None, 400, "缺少 job_id")
        if not confirmations:
            return resp(None, 400, "缺少 confirmations")

        # 查询任务
        job = db.session.query(TargetInventoryJob).filter(
            TargetInventoryJob.id == job_id
        ).first()

        if not job:
            return resp(None, 404, "任务不存在")

        # 调用确认函数
        try:
            result = confirm_field_recommendations(
                job_id=job_id,
                datasource_id=str(job.datasource_id),
                schema_hash=job.schema_hash,
                confirmations=confirmations
            )

            if result.get("success"):
                return resp(result, 200, "字段推荐确认成功")
            else:
                return resp(result, 500, f"字段推荐确认失败: {result.get('errors')}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            return resp(None, 500, f"字段推荐确认失败: {str(e)}")


class ConfirmTableRelationshipsAPI(Resource):
    @login_required
    def post(self):
        """
        确认表关系推断结果（支持同源和跨源）

        Args:
            job_id: 任务ID
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
            datasource_schema_map: 数据源ID到schema_hash的映射（跨源时使用，可选）
                {"datasource_id_1": "schema_hash_1", "datasource_id_2": "schema_hash_2"}

        Returns:
            {
                "success": True,
                "created_relationships": 5,
                "created_cards": 2
            }
        """
        from controllers.target_inventory.confirmation_service import confirm_table_relationships

        payload = request.get_json(force=True, silent=False) or {}
        job_id = payload.get("job_id")
        confirmations = payload.get("confirmations") or []
        datasource_schema_map = payload.get("datasource_schema_map") or {}

        if not job_id:
            return resp(None, 400, "缺少 job_id")
        if not confirmations:
            return resp(None, 400, "缺少 confirmations")

        # 查询任务
        job = db.session.query(TargetInventoryJob).filter(
            TargetInventoryJob.id == job_id
        ).first()

        if not job:
            return resp(None, 404, "任务不存在")

        # 调用确认函数
        try:
            result = confirm_table_relationships(
                job_id=job_id,
                datasource_id=str(job.datasource_id),
                schema_hash=job.schema_hash,
                confirmations=confirmations,
                datasource_schema_map=datasource_schema_map
            )

            if result.get("success"):
                return resp(result, 200, "表关系确认成功")
            else:
                return resp(result, 500, f"表关系确认失败: {result.get('errors')}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            return resp(None, 500, f"表关系确认失败: {str(e)}")


api.add_resource(TablesAPI, "/tables")
api.add_resource(RunAPI, "/run")
api.add_resource(ConfirmAPI, "/confirm")
api.add_resource(JobResultAPI, "/job/<job_id>")
api.add_resource(RelationshipsAPI, "/job/<job_id>/relationships")
api.add_resource(RelationshipGraphAPI, "/job/<job_id>/graph")
api.add_resource(FieldMappingsAPI, "/job/<job_id>/field_mappings")
api.add_resource(ConfirmFieldMappingsAPI, "/confirm_field_mappings")
api.add_resource(ConfirmFieldRecommendationsAPI, "/confirm_field_recommendations")
api.add_resource(ConfirmTableRelationshipsAPI, "/confirm_table_relationships")


# ==================== 历史盘点结果查询接口 ====================

def _get_user_job(job_id):
    """
    获取当前用户的任务（权限校验）
    """
    return TargetInventoryJob.query.filter_by(
        id=job_id,
        user_id=current_user.id
    ).first()


def _get_user_job_result(job_id):
    """
    获取当前用户的任务结果（权限校验）
    """
    job = _get_user_job(job_id)
    if not job:
        return None, None
    job_result = TargetInventoryJobResult.query.filter_by(job_id=job_id).first()
    return job, job_result


class HistoryJobListAPI(Resource):
    @login_required
    def get(self):
        """
        获取历史盘点任务列表（当前用户）

        Query Params:
            datasource_id: 数据源ID（可选，筛选特定数据源）
            status: 任务状态（可选，pending/running/completed/failed）
            page: 页码（默认1）
            page_size: 每页数量（默认20）

        Returns:
            {
                "total": 100,
                "page": 1,
                "page_size": 20,
                "items": [
                    {
                        "job_id": "xxx",
                        "datasource_id": "xxx",
                        "datasource_name": "测试数据源",
                        "status": "completed",
                        "target_tables": ["table1", "table2"],
                        "ref_tables": ["ref1", "ref2"],
                        "created_at": "2026-02-05T10:00:00",
                        "completed_at": "2026-02-05T10:05:00",
                        "progress": {...}
                    }
                ]
            }
        """
        datasource_id = request.args.get("datasource_id")
        status = request.args.get("status")
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))

        # 构建查询 - 只查询当前用户的任务
        query = db.session.query(TargetInventoryJob).filter(
            TargetInventoryJob.user_id == current_user.id
        )

        if datasource_id:
            query = query.filter(TargetInventoryJob.datasource_id == datasource_id)
        if status:
            query = query.filter(TargetInventoryJob.status == status)

        # 按创建时间倒序
        query = query.order_by(TargetInventoryJob.created_at.desc())

        # 分页
        total = query.count()
        jobs = query.offset((page - 1) * page_size).limit(page_size).all()

        # 获取数据源名称映射
        datasource_ids = list(set(str(job.datasource_id) for job in jobs))
        datasources = {}
        if datasource_ids:
            ds_list = DatasourceInfo.query.filter(DatasourceInfo.id.in_(datasource_ids)).all()
            datasources = {str(ds.id): ds.connect_name for ds in ds_list}

        # 批量取出关联的 job_result，避免循环 N+1
        job_ids = [job.id for job in jobs]
        job_results = {}
        if job_ids:
            results = (
                db.session.query(TargetInventoryJobResult)
                .filter(TargetInventoryJobResult.job_id.in_(job_ids))
                .all()
            )
            job_results = {r.job_id: r for r in results}

        items = []
        for job in jobs:
            # 从 options 中获取 schema_name
            options = job.options or {}
            schema_name = options.get("schema_name", "")

            # 重算 progress：基于 confirm_json 中的"已确认数量"覆盖原推断数量
            # 保留原始 progress 的其它字段（如 phase）
            base_progress = dict(job.progress or {})
            job_result = job_results.get(job.id)
            confirm_json = (job_result.confirm_json or {}) if job_result else {}

            # 已确认的字段注释数：action in {"accept", "custom"}
            field_confirmations = confirm_json.get("field_recommendations") or {}
            confirmed_field_count = 0
            for _table, columns in field_confirmations.items():
                if not isinstance(columns, dict):
                    continue
                for _col, conf in columns.items():
                    if not isinstance(conf, dict):
                        continue
                    action = conf.get("action")
                    if action in ("accept", "custom"):
                        confirmed_field_count += 1

            # 已确认的表关系数：action == "accept"
            relationship_confirmations = confirm_json.get("table_relationships") or []
            confirmed_relationships = [
                rel for rel in relationship_confirmations
                if isinstance(rel, dict) and rel.get("action") == "accept"
            ]
            confirmed_relationships_count = len(confirmed_relationships)

            # 已确认的关系卡片数：与 _generate_standard_relationship_cards 一致，
            # 每个已确认关系涉及的 from_table 与 to_table 各产生一张卡片，
            # 去重 key 为 (datasource_id, schema_hash, table_name) 三元组，
            # 避免跨源场景下同名表被错误合并。
            confirmed_card_keys = set()
            for rel in confirmed_relationships:
                from_ds = rel.get("from_datasource_id") or job.datasource_id
                to_ds = rel.get("to_datasource_id") or job.datasource_id
                from_schema = rel.get("from_schema_hash") or ""
                to_schema = rel.get("to_schema_hash") or ""
                from_table = rel.get("from_table", "")
                to_table = rel.get("to_table", "")
                if not from_table or not to_table:
                    continue
                confirmed_card_keys.add((str(from_ds), from_schema, from_table))
                confirmed_card_keys.add((str(to_ds), to_schema, to_table))
            confirmed_cards_count = len(confirmed_card_keys)

            # 仅当 confirm_json 中存在对应键时，才覆盖原推断数量
            # （避免污染 phase 等其它字段）
            if "field_recommendations" in confirm_json:
                base_progress["field_recommendations"] = confirmed_field_count
            if "table_relationships" in confirm_json:
                base_progress["table_relationships"] = confirmed_relationships_count
                base_progress["relationship_cards"] = confirmed_cards_count

            items.append({
                "job_id": str(job.id),
                "datasource_id": str(job.datasource_id),
                "datasource_name": datasources.get(str(job.datasource_id), "未知数据源"),
                "status": job.status,
                "target_tables": job.target_tables or [],
                "ref_tables": job.ref_tables or [],
                "schema_name": schema_name,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                "progress": base_progress
            })

        return resp({
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items
        }, 200, "获取成功")


class HistoryJobDetailAPI(Resource):
    @login_required
    def get(self, job_id):
        """
        获取盘点任务详情（包含完整结果）

        Returns:
            {
                "job": {
                    "job_id": "xxx",
                    "datasource_id": "xxx",
                    "datasource_name": "测试数据源",
                    "status": "completed",
                    "target_tables": [...],
                    "ref_tables": [...],
                    "created_at": "...",
                    "completed_at": "...",
                    "progress": {...}
                },
                "result": {
                    "field_recommendations": {...},
                    "field_profiles": {...},
                    "candidates": {...},
                    "field_mappings": {...},
                    "table_relationships": {...},
                    "relationship_cards": {...},
                    "confirmations": {...}
                }
            }
        """
        # 只能查看自己的任务
        job = TargetInventoryJob.query.filter_by(
            id=job_id,
            user_id=current_user.id
        ).first()
        if not job:
            return resp(None, 404, "任务不存在或无权访问")

        # 获取数据源名称
        ds = DatasourceInfo.query.filter_by(id=job.datasource_id).first()
        datasource_name = ds.connect_name if ds else "未知数据源"

        # 获取任务结果
        job_result = TargetInventoryJobResult.query.filter_by(job_id=job_id).first()

        result_data = None
        if job_result:
            result_data = {
                "field_recommendations": job_result.llm_json or {},
                "field_profiles": job_result.field_profiles_json or {},
                "candidates": job_result.candidates_json or {},
                "field_mappings": job_result.field_mappings_json or {},
                "table_relationships": job_result.table_relationships_json or {},
                "relationship_cards": job_result.relationship_cards_json or {},
                "confirmations": job_result.confirm_json or {},
                "index_meta": job_result.index_meta_json or {}
            }

        # 从 options 中获取 schema_name
        options = job.options or {}
        schema_name = options.get("schema_name", "")

        return resp({
            "job": {
                "job_id": str(job.id),
                "datasource_id": str(job.datasource_id),
                "datasource_name": datasource_name,
                "status": job.status,
                "target_tables": job.target_tables or [],
                "ref_tables": job.ref_tables or [],
                "schema_name": schema_name,
                "schema_hash": job.schema_hash,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                "progress": job.progress or {}
            },
            "result": result_data
        }, 200, "获取成功")

    @login_required
    def delete(self, job_id):
        """
        删除定向盘点任务及其执行结果

        删除策略：
        - 删除任务执行层数据（临时数据）：
          1. target_inventory_job 表中的任务记录
          2. target_inventory_job_result 表中的任务结果（通过数据库级联删除自动处理）
          3. field_mapping 表中该任务确认的字段映射关系
          4. table_relationship 表中该任务确认的表关系（source_type='target_inventory' + source_job_id）
          5. table_relationship_card 表中该任务的关系卡片（source_type='target_inventory' + source_job_id）

        设计理由：
        - 删除单个任务时，应该删除该任务产生的所有数据，包括字段映射
        - 保持与批量删除、清空接口的行为一致

        Returns:
            {
                "job_id": "xxx",
                "deleted": true,
                "deleted_mappings": N,
                "deleted_relationships": M,
                "deleted_cards": K,
                "message": "任务及相关数据已删除"
            }
        """
        # 权限校验：只能删除自己的任务
        job = TargetInventoryJob.query.filter_by(
            id=job_id,
            user_id=current_user.id
        ).first()
        if not job:
            return resp(None, 404, "任务不存在或无权访问")

        try:
            # 步骤1: 删除 FieldMapping（按 source_job_id 精确删除）
            deleted_mappings = db.session.query(FieldMapping).filter(
                FieldMapping.source_job_id == job_id
            ).delete(synchronize_session=False)

            # 步骤2: 删除 TableRelationship（source_type='target_inventory' + source_job_id）
            deleted_rels = db.session.query(TableRelationship).filter(
                TableRelationship.source_type == 'target_inventory',
                TableRelationship.source_job_id == job_id
            ).delete(synchronize_session=False)

            # 步骤3: 删除 TableRelationshipCard（source_type='target_inventory' + source_job_id）
            deleted_cards = db.session.query(TableRelationshipCard).filter(
                TableRelationshipCard.source_type == 'target_inventory',
                TableRelationshipCard.source_job_id == job_id
            ).delete(synchronize_session=False)

            # 步骤4: 删除任务（job_result 会通过外键级联删除 ondelete="CASCADE"）
            db.session.delete(job)
            db.session.commit()

            return resp({
                "job_id": job_id,
                "deleted": True,
                "deleted_mappings": deleted_mappings,
                "deleted_relationships": deleted_rels,
                "deleted_cards": deleted_cards,
                "message": "任务及相关数据已删除"
            }, 200, "删除成功")

        except Exception as e:
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return resp(None, 500, f"删除失败: {str(e)}")


class ClearTargetInventoryJobsAPI(Resource):
    """
    清空指定数据源下的所有定向盘点任务及其相关数据

    删除范围：
    - TargetInventoryJob: 该数据源下的所有定向盘点任务
    - TargetInventoryJobResult: 通过外键级联删除
    - TableRelationship: source_type='target_inventory' 的记录
    - TableRelationshipCard: source_type='target_inventory' 的记录
    - FieldMapping: 该数据源下按 schema_hash 删除（谨慎：会删除所有来源的映射）

    保留数据：
    - source_type='global_inventory' 的 TableRelationship 和 TableRelationshipCard（全域盘点结果）
    """

    @login_required
    def delete(self):
        """
        清空指定数据源的定向盘点任务

        Query参数:
            datasource_id: 数据源ID（必填）

        Returns:
            {
                "deleted_jobs": N,       # 删除的任务数
                "deleted_rels": M,       # 删除的表关系数
                "deleted_cards": K,      # 删除的关系卡片数
                "deleted_mappings": L,   # 删除的字段映射数
                "schema_hashes": [...]   # 涉及的 schema_hash 列表
            }
        """
        from models.global_inventory import (
            TargetInventoryJob, TargetInventoryJobResult,
            TableRelationship, TableRelationshipCard, FieldMapping
        )

        # 获取 datasource_id 参数
        datasource_id = request.args.get("datasource_id")
        if not datasource_id:
            return resp(None, 400, "datasource_id 参数必填")

        # 转换为 UUID
        try:
            datasource_uuid = uuid.UUID(datasource_id)
        except ValueError:
            return resp(None, 400, "datasource_id 格式无效")

        # 校验数据源权限
        ds = db.session.query(DatasourceInfo).filter(
            DatasourceInfo.id == datasource_uuid,
            DatasourceInfo.user_id == current_user.id
        ).first()
        if not ds:
            return resp(None, 404, "数据源不存在或无权访问")

        try:
            # 步骤1: 查找该数据源下所有的定向盘点任务
            jobs = db.session.query(TargetInventoryJob).filter(
                TargetInventoryJob.datasource_id == datasource_uuid
            ).all()

            job_ids = [job.id for job in jobs]
            schema_hashes = list(set(job.schema_hash for job in jobs))
            deleted_jobs = len(jobs)

            # 步骤2: 删除 TargetInventoryJob（job_result 会通过外键级联删除）
            for job in jobs:
                db.session.delete(job)

            # 步骤3: 删除 TableRelationship（只删 source_type='target_inventory'）
            rel_query = db.session.query(TableRelationship).filter(
                TableRelationship.source_type == 'target_inventory',
                db.or_(
                    TableRelationship.table_a_datasource_id == datasource_uuid,
                    TableRelationship.table_b_datasource_id == datasource_uuid
                )
            )
            deleted_rels = rel_query.delete(synchronize_session=False)

            # 步骤4: 删除 TableRelationshipCard（只删 source_type='target_inventory'）
            card_query = db.session.query(TableRelationshipCard).filter(
                TableRelationshipCard.source_type == 'target_inventory',
                TableRelationshipCard.datasource_id == datasource_uuid
            )
            deleted_cards = card_query.delete(synchronize_session=False)

            # 步骤5: 删除 FieldMapping（按 source_job_id 精确删除）
            mapping_query = db.session.query(FieldMapping).filter(
                FieldMapping.source_job_id.in_(job_ids)
            )
            deleted_mappings = mapping_query.delete(synchronize_session=False)

            db.session.commit()

            return resp({
                "deleted_jobs": deleted_jobs,
                "deleted_rels": deleted_rels,
                "deleted_cards": deleted_cards,
                "deleted_mappings": deleted_mappings,
                "schema_hashes": schema_hashes
            }, 200, "清空成功，定向盘点任务及相关数据已删除")

        except Exception as e:
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return resp(None, 500, f"清空失败: {str(e)}")


class BatchDeleteJobsAPI(Resource):
    """
    批量删除指定的定向盘点任务及其相关数据

    删除范围：
    - TargetInventoryJob: 根据 job_id 删除
    - TargetInventoryJobResult: 通过外键级联删除
    - TableRelationship: source_type='target_inventory' + source_job_id 在待删除列表中
    - TableRelationshipCard: source_type='target_inventory' + source_job_id 在待删除列表中
    - FieldMapping: 根据 datasource_id + schema_hash 删除
    """

    @login_required
    def delete(self):
        """
        批量删除指定的定向盘点任务

        Request Body:
            {
                "job_ids": ["uuid1", "uuid2", ...]  # 必填，任务ID列表
            }

        Returns:
            {
                "deleted_jobs": N,       # 删除的任务数
                "deleted_rels": M,       # 删除的表关系数
                "deleted_cards": K,      # 删除的关系卡片数
                "deleted_mappings": L,   # 删除的字段映射数
                "not_found_jobs": [...]  # 不存在的任务ID列表
            }
        """
        from models.global_inventory import (
            TargetInventoryJob, TargetInventoryJobResult,
            TableRelationship, TableRelationshipCard, FieldMapping
        )

        payload = request.get_json(force=True, silent=False) or {}
        job_ids = payload.get("job_ids", [])

        if not job_ids:
            return resp(None, 400, "job_ids 参数必填，且不能为空")

        # 转换为 UUID 列表，并去重
        try:
            job_uuid_list = list(set(uuid.UUID(jid) for jid in job_ids))
        except ValueError:
            return resp(None, 400, "job_ids 格式无效，请提供有效的 UUID")

        try:
            # 步骤1: 查询要删除的 jobs，并校验权限
            valid_jobs = []
            not_found_jobs = []

            for job_uuid in job_uuid_list:
                job = db.session.query(TargetInventoryJob).filter(
                    TargetInventoryJob.id == job_uuid
                ).first()

                if not job:
                    not_found_jobs.append(str(job_uuid))
                    continue

                # 校验数据源权限
                ds = db.session.query(DatasourceInfo).filter(
                    DatasourceInfo.id == job.datasource_id,
                    DatasourceInfo.user_id == current_user.id
                ).first()
                if not ds:
                    not_found_jobs.append(str(job_uuid))
                    continue

                valid_jobs.append(job)

            deleted_jobs = len(valid_jobs)

            # 收集 schema_hashes 和 job_ids
            schema_hashes = list(set(job.schema_hash for job in valid_jobs))
            valid_job_ids = [job.id for job in valid_jobs]

            # 步骤2: 删除 TargetInventoryJob（job_result 会通过外键级联删除）
            for job in valid_jobs:
                db.session.delete(job)

            # 步骤3: 删除 TableRelationship（source_type='target_inventory' + source_job_id 在列表中）
            rel_query = db.session.query(TableRelationship).filter(
                TableRelationship.source_type == 'target_inventory',
                TableRelationship.source_job_id.in_(valid_job_ids)
            )
            deleted_rels = rel_query.delete(synchronize_session=False)

            # 步骤4: 删除 TableRelationshipCard（source_type='target_inventory' + source_job_id 在列表中）
            card_query = db.session.query(TableRelationshipCard).filter(
                TableRelationshipCard.source_type == 'target_inventory',
                TableRelationshipCard.source_job_id.in_(valid_job_ids)
            )
            deleted_cards = card_query.delete(synchronize_session=False)

            # 步骤5: 删除 FieldMapping（按 source_job_id 精确删除）
            mapping_query = db.session.query(FieldMapping).filter(
                FieldMapping.source_job_id.in_(valid_job_ids)
            )
            deleted_mappings = mapping_query.delete(synchronize_session=False)

            db.session.commit()

            return resp({
                "deleted_jobs": deleted_jobs,
                "deleted_rels": deleted_rels,
                "deleted_cards": deleted_cards,
                "deleted_mappings": deleted_mappings,
                "not_found_jobs": not_found_jobs
            }, 200, f"批量删除成功，已删除 {deleted_jobs} 个任务")

        except Exception as e:
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return resp(None, 500, f"批量删除失败: {str(e)}")


class HistoryFieldRecommendationsAPI(Resource):
    @login_required
    def get(self, job_id):
        """
        获取字段推荐结果

        Returns:
            {
                "recommendations": {
                    "table_name": {
                        "column_name": {
                            "candidates": [...],
                            "profile": {...}
                        }
                    }
                },
                "confirmed": {...}
            }
        """
        job, job_result = _get_user_job_result(job_id)
        if not job:
            return resp(None, 404, "任务不存在或无权访问")
        if not job_result:
            return resp(None, 404, "任务结果不存在")

        # 获取确认信息
        confirm_json = job_result.confirm_json or {}
        field_confirmations = confirm_json.get("field_recommendations", {})

        return resp({
            "recommendations": job_result.llm_json or {},
            "profiles": job_result.field_profiles_json or {},
            "candidates": job_result.candidates_json or {},
            "confirmed": field_confirmations,
            "confirmed_at": confirm_json.get("fields_confirmed_at")
        }, 200, "获取成功")


class HistoryTableRelationshipsAPI(Resource):
    @login_required
    def get(self, job_id):
        """
        获取表关系推断结果

        Returns:
            {
                "relationships": [...],
                "confirmed": [...],
                "confirmed_at": "..."
            }
        """
        job, job_result = _get_user_job_result(job_id)
        if not job:
            return resp(None, 404, "任务不存在或无权访问")
        if not job_result:
            return resp(None, 404, "任务结果不存在")

        # 获取确认信息
        confirm_json = job_result.confirm_json or {}
        relationship_confirmations = confirm_json.get("table_relationships", [])

        # 构建已确认关系的 key 集合，用于过滤未确认的关系
        confirmed_keys = set()
        for rel in relationship_confirmations:
            if rel.get("action") == "accept":
                confirmed_keys.add((
                    rel.get("from_table", ""),
                    rel.get("from_column", ""),
                    rel.get("to_table", ""),
                    rel.get("to_column", "")
                ))

        relationships_data = job_result.table_relationships_json or {}
        all_relationships = relationships_data.get("relationships", [])

        # 仅返回已确认的关系，若无确认记录则返回空列表
        if confirmed_keys:
            filtered_relationships = [
                rel for rel in all_relationships
                if (
                    rel.get("from_table", ""),
                    rel.get("from_column", ""),
                    rel.get("to_table", ""),
                    rel.get("to_column", "")
                ) in confirmed_keys
            ]
        else:
            filtered_relationships = []

        return resp({
            "relationships": filtered_relationships,
            "confirmed": relationship_confirmations,
            "confirmed_at": confirm_json.get("relationships_confirmed_at")
        }, 200, "获取成功")


class HistoryRelationshipCardsAPI(Resource):
    @login_required
    def get(self, job_id):
        """
        获取关系卡片

        Returns:
            {
                "cards": [
                    {
                        "card_id": "...",
                        "table1": "...",
                        "table2": "...",
                        "relationship_type": "...",
                        "direction": "many_to_one",
                        "confidence": 0.9,
                        "business_description": "...",
                        "business_relation": {...},
                        "join_suggestion": {...},
                        "fusion_suggestion": {...},
                        "fields": [...]
                    }
                ]
            }
        """
        job, job_result = _get_user_job_result(job_id)
        if not job:
            return resp(None, 404, "任务不存在或无权访问")
        if not job_result:
            return resp(None, 404, "任务结果不存在")

        # 从 relationship_cards_json 读取全量卡片（任务运行时的推断结果）
        cards_data = job_result.relationship_cards_json or {}
        all_cards = cards_data.get("cards", [])

        # 根据 confirm_json 过滤：只返回已确认关系对应的卡片
        confirm_json = job_result.confirm_json or {}
        relationship_confirmations = confirm_json.get("table_relationships", [])

        confirmed_keys = set()
        for rel in relationship_confirmations:
            if rel.get("action") == "accept":
                confirmed_keys.add((
                    rel.get("from_table", ""),
                    rel.get("from_column", ""),
                    rel.get("to_table", ""),
                    rel.get("to_column", "")
                ))

        # 过滤逻辑：
        # 1) 只保留"至少有一个已确认字段对儿"的卡片；
        # 2) 同时过滤卡片内部的 fields 数组，只保留与已确认关系对应的字段对儿，
        #    否则前端 fields.length 会展示全量推断字段数（包含未确认的）；
        # 3) 同步重建衍生字段（join_suggestion.join_conditions、description、metadata、
        #    confidence），避免未确认关系在其它字段中残留。
        # 兼容双向匹配：confirmed_keys 以 (from, to) 形式存储，但 fields 中可能方向相反。
        confirmed_keys_set = confirmed_keys
        confirmed_keys_reversed = {(t, c, f, col) for (f, c, t, col) in confirmed_keys}

        def _field_key(f: dict) -> tuple:
            return (
                f.get("from_table", ""),
                f.get("from_column", ""),
                f.get("to_table", ""),
                f.get("to_column", "")
            )

        def _is_confirmed_field(f: dict) -> bool:
            return _field_key(f) in confirmed_keys_set or _field_key(f) in confirmed_keys_reversed

        def _rebuild_card(card: dict, filtered_fields: list) -> dict:
            """基于已确认的 fields 重建衍生字段，避免未确认信息残留。"""
            new_card = {**card, "fields": filtered_fields}

            # 1) join_suggestion.join_conditions：按 (from_column, to_column) 过滤
            js = new_card.get("join_suggestion") or {}
            jc_list = js.get("join_conditions") or []
            jc_kept = []
            for jc in jc_list:
                fc = jc.get("from_column", "")
                tc = jc.get("to_column", "")
                # join_conditions 不带 from_table/to_table，使用 column 对照 confirmed_keys
                # 兼容双向
                if any(
                    (f.get("from_column") == fc and f.get("to_column") == tc) or
                    (f.get("from_column") == tc and f.get("to_column") == fc)
                    for f in filtered_fields
                ):
                    jc_kept.append(jc)
            new_card["join_suggestion"] = {**js, "join_conditions": jc_kept}

            # 2) description：基于确认后的 fields 重新生成
            field_pairs = [f"{f.get('from_column')} -> {f.get('to_column')}" for f in filtered_fields]
            fields_str = "、".join(field_pairs[:3])
            if len(field_pairs) > 3:
                fields_str += f" 等{len(field_pairs)}个字段"
            t1 = new_card.get("table1", "")
            t2 = new_card.get("table2", "")
            direction = new_card.get("direction", "")
            direction_map = {
                "one_to_many": "一对多",
                "many_to_one": "多对一",
                "many_to_many": "多对多",
                "one_to_one": "一对一"
            }
            direction_text = direction_map.get(direction, "关联")
            if field_pairs:
                new_card["description"] = (
                    f"表 {t1} 与表 {t2} 存在{direction_text}关系，通过字段 {fields_str} 关联"
                )
            # 否则保留原始 description

            # 3) metadata.relationship_count / *_count 重新统计
            md = dict(new_card.get("metadata") or {})
            md["relationship_count"] = len(filtered_fields)
            type_counter = {
                "foreign_key": 0, "semantic": 0, "name_based": 0, "same_name": 0
            }
            for f in filtered_fields:
                rt = f.get("type", "")
                if rt in type_counter:
                    type_counter[rt] += 1
                else:
                    # 兼容未列出的类型
                    md[f"{rt}_count"] = md.get(f"{rt}_count", 0) + 1
            md["foreign_key_count"] = type_counter["foreign_key"]
            md["semantic_count"] = type_counter["semantic"]
            md["name_based_count"] = type_counter["name_based"]
            md["same_name_count"] = type_counter["same_name"]
            new_card["metadata"] = md

            # 4) confidence：按已确认 fields 重新计算平均值
            if filtered_fields:
                avg = sum(f.get("confidence", 0) for f in filtered_fields) / len(filtered_fields)
                new_card["confidence"] = round(avg, 3)

            return new_card

        if confirmed_keys:
            filtered_cards = []
            for card in all_cards:
                filtered_fields = [f for f in card.get("fields", []) if _is_confirmed_field(f)]
                if not filtered_fields:
                    continue
                filtered_cards.append(_rebuild_card(card, filtered_fields))
        else:
            filtered_cards = []

        return resp({
            "cards": filtered_cards
        }, 200, "获取成功")


class HistoryRelationshipGraphAPI(Resource):
    @login_required
    def get(self, job_id):
        """
        获取关系图谱数据（从表关系表读取，降级到JSON字段）
        返回格式对齐全域盘点

        Returns:
            {
                "nodes": [...],
                "edges": [...],
                "statistics": {...}
            }
        """
        from controllers.target_inventory.relationship_card_generator import export_cards_to_graph_format

        job, job_result = _get_user_job_result(job_id)
        if not job:
            return resp(None, 404, "任务不存在或无权访问")

        # ✅ 优先从 table_relationship_card 表读取（新数据）
        cards_from_db = db.session.query(TableRelationshipCard).filter(
            TableRelationshipCard.source_job_id == job_id
        ).all()

        if cards_from_db:
            # 从表关系卡片表读取
            cards = [card.card_data for card in cards_from_db]
            print(f"[关系图谱] 从表关系卡片表读取到 {len(cards)} 张卡片 (job_id={job_id})")
        elif job_result and job_result.relationship_cards_json:
            # ❌ 降级：从任务结果JSON读取（兼容旧数据）
            cards_data = job_result.relationship_cards_json or {}
            cards = cards_data.get("cards", [])
            print(f"[关系图谱] 降级从任务结果JSON读取到 {len(cards)} 张卡片 (job_id={job_id})")
        else:
            return resp({
                "nodes": [],
                "edges": [],
                "statistics": {
                    "total_nodes": 0,
                    "total_edges": 0,
                    "cross_source_edges": 0
                }
            }, 200, "暂无关系数据")

        if not cards:
            return resp({
                "nodes": [],
                "edges": [],
                "statistics": {
                    "total_nodes": 0,
                    "total_edges": 0,
                    "cross_source_edges": 0
                }
            }, 200, "获取成功")

        # 转换为图数据格式
        graph_data = export_cards_to_graph_format(cards)

        # 添加统计信息（对齐全域盘点）
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        cross_source_count = sum(1 for edge in edges if edge.get("is_cross_source", False))

        graph_data["statistics"] = {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "cross_source_edges": cross_source_count
        }

        return resp(graph_data, 200, "获取成功")


class DeleteJobRelationshipsAPI(Resource):
    @login_required
    def delete(self, job_id):
        """
        删除定向盘点任务的关系数据

        Args:
            job_id: 任务ID

        Returns:
            {
                "deleted_relationships": 5,
                "deleted_cards": 2
            }
        """
        job = _get_user_job(job_id)
        if not job:
            return resp(None, 404, "任务不存在或无权访问")

        try:
            # 删除该任务的表关系数据
            deleted_rels = db.session.query(TableRelationship).filter(
                TableRelationship.source_job_id == job_id
            ).delete(synchronize_session=False)

            # 删除该任务的关系卡片
            deleted_cards = db.session.query(TableRelationshipCard).filter(
                TableRelationshipCard.source_job_id == job_id
            ).delete(synchronize_session=False)

            # 可选：清空任务结果中的JSON字段（兼容旧数据）
            job_result = TargetInventoryJobResult.query.filter_by(job_id=job_id).first()
            if job_result:
                if job_result.relationship_cards_json:
                    job_result.relationship_cards_json = {"cards": []}
                if job_result.table_relationships_json:
                    job_result.table_relationships_json = {"relationships": []}
                flag_modified(job_result, "relationship_cards_json")
                flag_modified(job_result, "table_relationships_json")

            db.session.commit()

            print(f"[删除关系数据] 任务 {job_id}: 删除 {deleted_rels} 条关系, {deleted_cards} 张卡片")

            return resp({
                "deleted_relationships": deleted_rels,
                "deleted_cards": deleted_cards
            }, 200, "删除成功")

        except Exception as e:
            db.session.rollback()
            print(f"[删除关系数据] 失败: {e}")
            import traceback
            traceback.print_exc()
            return resp(None, 500, f"删除失败: {str(e)}")


class HistoryConfirmationsAPI(Resource):
    @login_required
    def get(self, job_id):
        """
        获取用户确认记录

        Returns:
            {
                "field_recommendations": {
                    "confirmed_at": "...",
                    "confirmations": {...}
                },
                "table_relationships": {
                    "confirmed_at": "...",
                    "confirmations": [...]
                }
            }
        """
        job, job_result = _get_user_job_result(job_id)
        if not job:
            return resp(None, 404, "任务不存在或无权访问")
        if not job_result:
            return resp(None, 404, "任务结果不存在")

        confirm_json = job_result.confirm_json or {}

        return resp({
            "field_recommendations": {
                "confirmed_at": confirm_json.get("fields_confirmed_at"),
                "confirmations": confirm_json.get("field_recommendations", {})
            },
            "table_relationships": {
                "confirmed_at": confirm_json.get("relationships_confirmed_at"),
                "confirmations": confirm_json.get("table_relationships", [])
            },
            "field_mappings": job_result.field_mappings_json or {}
        }, 200, "获取成功")


class DatasourceRelationshipsAPI(Resource):
    @login_required
    def get(self, datasource_id):
        """
        获取数据源下所有已确认的表关系（跨任务聚合，包含跨源关系）

        查询逻辑：返回 table_a_datasource_id 或 table_b_datasource_id 等于该数据源的所有关系

        Returns:
            {
                "relationships": [
                    {
                        "id": "...",
                        "table_a": "...",
                        "table_a_datasource_id": "...",
                        "table_b": "...",
                        "table_b_datasource_id": "...",
                        "is_cross_source": false,
                        "relationship_type": "...",
                        "join_conditions": [...],
                        "relationship_strength": 0.9,
                        "cardinality": "many_to_one",
                        "created_at": "..."
                    }
                ],
                "total": 10,
                "cross_source_count": 2
            }
        """
        from models.global_inventory import TableRelationship
        from sqlalchemy import or_

        # 校验数据源属于当前用户
        ds = DatasourceInfo.query.filter_by(
            id=datasource_id,
            user_id=current_user.id
        ).first()
        if not ds:
            return resp(None, 404, "数据源不存在或无权访问")

        # 查询该数据源相关的所有关系（作为 table_a 或 table_b 的数据源）
        relationships = TableRelationship.query.filter(
            or_(
                TableRelationship.table_a_datasource_id == datasource_id,
                TableRelationship.table_b_datasource_id == datasource_id
            )
        ).order_by(TableRelationship.created_at.desc()).all()

        items = []
        cross_source_count = 0
        for rel in relationships:
            if rel.is_cross_source:
                cross_source_count += 1
            items.append({
                "id": str(rel.id),
                "table_a": rel.table_a,
                "table_a_datasource_id": str(rel.table_a_datasource_id),
                "table_a_schema_hash": rel.table_a_schema_hash,
                "table_b": rel.table_b,
                "table_b_datasource_id": str(rel.table_b_datasource_id),
                "table_b_schema_hash": rel.table_b_schema_hash,
                "is_cross_source": rel.is_cross_source,
                "relationship_type": rel.relationship_type,
                "join_conditions": rel.join_conditions or [],
                "relationship_strength": float(rel.relationship_strength) if rel.relationship_strength else None,
                "cardinality": rel.cardinality,
                "created_at": rel.created_at.isoformat() if rel.created_at else None
            })

        return resp({
            "relationships": items,
            "total": len(items),
            "cross_source_count": cross_source_count
        }, 200, "获取成功")


class DatasourceRelationshipCardsAPI(Resource):
    @login_required
    def get(self, datasource_id):
        """
        获取数据源下所有关系卡片（跨任务聚合）

        每张表在其所属数据源下有自己的关系卡片，卡片中记录该表与其他表的所有关系（包含跨源关系）

        Returns:
            {
                "cards": [
                    {
                        "id": "...",
                        "table_name": "...",
                        "schema_hash": "...",
                        "card_data": {...},
                        "has_cross_source_relations": false,
                        "related_datasource_ids": [],
                        "version": 1,
                        "created_at": "..."
                    }
                ],
                "total": 10,
                "cross_source_card_count": 2
            }
        """
        from models.global_inventory import TableRelationshipCard

        # 校验数据源属于当前用户
        ds = DatasourceInfo.query.filter_by(
            id=datasource_id,
            user_id=current_user.id
        ).first()
        if not ds:
            return resp(None, 404, "数据源不存在或无权访问")

        cards = TableRelationshipCard.query.filter_by(
            datasource_id=datasource_id
        ).order_by(TableRelationshipCard.created_at.desc()).all()

        items = []
        cross_source_card_count = 0
        for card in cards:
            if card.has_cross_source_relations:
                cross_source_card_count += 1
            items.append({
                "id": str(card.id),
                "table_name": card.table_name,
                "schema_hash": card.schema_hash,
                "card_data": card.card_data or {},
                "has_cross_source_relations": card.has_cross_source_relations,
                "related_datasource_ids": card.related_datasource_ids or [],
                "version": card.version or 1,
                "created_at": card.created_at.isoformat() if card.created_at else None,
                "updated_at": card.updated_at.isoformat() if card.updated_at else None
            })

        return resp({
            "cards": items,
            "total": len(items),
            "cross_source_card_count": cross_source_card_count
        }, 200, "获取成功")


class HistoryFieldMappingsConfirmedAPI(Resource):
    @login_required
    def get(self, job_id):
        """
        获取任务的字段映射确认结果（从 field_mapping 表查询）

        Returns:
            {
                "field_mappings": [
                    {
                        "id": "...",
                        "source_table": "target_table",
                        "source_column": "user_id",
                        "source_type": "bigint",
                        "target_table": "ref_users",
                        "target_column": "id",
                        "target_type": "bigint",
                        "mapping_type": "exact_match",
                        "confidence": 0.95,
                        "mapping_basis": {...},
                        "created_at": "..."
                    }
                ],
                "total": 10,
                "by_table": {
                    "target_table": [
                        {...}
                    ]
                }
            }
        """
        from models.global_inventory import FieldMapping

        # 校验任务权限
        job = _get_user_job(job_id)
        if not job:
            return resp(None, 404, "任务不存在或无权访问")

        # 通过 source_job_id 查询该任务的字段映射
        mappings = FieldMapping.query.filter_by(
            source_job_id=job_id
        ).order_by(FieldMapping.source_table, FieldMapping.source_column).all()

        items = []
        by_table = {}

        for m in mappings:
            item = {
                "id": str(m.id),
                "source_table": m.source_table,
                "source_column": m.source_column,
                "source_type": m.source_type,
                "target_table": m.target_table,
                "target_column": m.target_column,
                "target_type": m.target_type,
                "mapping_type": m.mapping_type,
                "confidence": float(m.confidence) if m.confidence else None,
                "mapping_basis": m.mapping_basis or {},
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None
            }
            items.append(item)

            # 按源表分组
            if m.source_table not in by_table:
                by_table[m.source_table] = []
            by_table[m.source_table].append(item)

        return resp({
            "field_mappings": items,
            "total": len(items),
            "by_table": by_table
        }, 200, "获取成功")


class DatasourceFieldMappingsAPI(Resource):
    @login_required
    def get(self, datasource_id):
        """
        获取数据源下所有已确认的字段映射（跨任务聚合）

        Query Params:
            source_table: 筛选指定源表（可选）
            target_table: 筛选指定目标表（可选）
            mapping_type: 筛选映射类型（可选）

        Returns:
            {
                "field_mappings": [
                    {
                        "id": "...",
                        "source_table": "target_table",
                        "source_column": "user_id",
                        "source_type": "bigint",
                        "target_table": "ref_users",
                        "target_column": "id",
                        "target_type": "bigint",
                        "mapping_type": "exact_match",
                        "confidence": 0.95,
                        "mapping_basis": {...},
                        "schema_hash": "...",
                        "created_at": "..."
                    }
                ],
                "total": 50,
                "by_table": {
                    "table_name": [...]
                },
                "statistics": {
                    "total_mappings": 50,
                    "by_mapping_type": {
                        "exact_match": 20,
                        "semantic_match": 25,
                        "user_defined": 5
                    },
                    "avg_confidence": 0.85
                }
            }
        """
        from models.global_inventory import FieldMapping

        # 校验数据源属于当前用户
        ds = DatasourceInfo.query.filter_by(
            id=datasource_id,
            user_id=current_user.id
        ).first()
        if not ds:
            return resp(None, 404, "数据源不存在或无权访问")

        # 构建查询
        query = FieldMapping.query.filter_by(datasource_id=datasource_id)

        # 可选筛选条件
        source_table = request.args.get("source_table")
        target_table = request.args.get("target_table")
        mapping_type = request.args.get("mapping_type")

        if source_table:
            query = query.filter(FieldMapping.source_table == source_table)
        if target_table:
            query = query.filter(FieldMapping.target_table == target_table)
        if mapping_type:
            query = query.filter(FieldMapping.mapping_type == mapping_type)

        mappings = query.order_by(
            FieldMapping.source_table,
            FieldMapping.source_column
        ).all()

        items = []
        by_table = {}
        type_counts = {}
        total_confidence = 0.0

        for m in mappings:
            item = {
                "id": str(m.id),
                "source_table": m.source_table,
                "source_column": m.source_column,
                "source_type": m.source_type,
                "target_table": m.target_table,
                "target_column": m.target_column,
                "target_type": m.target_type,
                "mapping_type": m.mapping_type,
                "confidence": float(m.confidence) if m.confidence else None,
                "mapping_basis": m.mapping_basis or {},
                "schema_hash": m.schema_hash,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None
            }
            items.append(item)

            # 按源表分组
            if m.source_table not in by_table:
                by_table[m.source_table] = []
            by_table[m.source_table].append(item)

            # 统计映射类型
            mt = m.mapping_type or "unknown"
            type_counts[mt] = type_counts.get(mt, 0) + 1

            # 累计置信度
            if m.confidence:
                total_confidence += float(m.confidence)

        # 计算平均置信度
        avg_confidence = total_confidence / len(items) if items else 0.0

        return resp({
            "field_mappings": items,
            "total": len(items),
            "by_table": by_table,
            "statistics": {
                "total_mappings": len(items),
                "by_mapping_type": type_counts,
                "avg_confidence": round(avg_confidence, 4)
            }
        }, 200, "获取成功")


# 注册历史查询接口
api.add_resource(HistoryJobListAPI, "/history/jobs")
api.add_resource(HistoryJobDetailAPI, "/history/job/<job_id>")
api.add_resource(ClearTargetInventoryJobsAPI, "/history/jobs/clear")
api.add_resource(BatchDeleteJobsAPI, "/history/jobs/batch_delete")
api.add_resource(HistoryFieldRecommendationsAPI, "/history/job/<job_id>/field_recommendations")
api.add_resource(HistoryTableRelationshipsAPI, "/history/job/<job_id>/table_relationships")
api.add_resource(HistoryRelationshipCardsAPI, "/history/job/<job_id>/relationship_cards")
api.add_resource(HistoryRelationshipGraphAPI, "/history/job/<job_id>/graph")
api.add_resource(DeleteJobRelationshipsAPI, "/job/<job_id>/relationships")  # ✅ 新增删除接口
api.add_resource(HistoryConfirmationsAPI, "/history/job/<job_id>/confirmations")
api.add_resource(HistoryFieldMappingsConfirmedAPI, "/history/job/<job_id>/field_mappings_confirmed")
api.add_resource(DatasourceRelationshipsAPI, "/datasource/<datasource_id>/relationships")
api.add_resource(DatasourceRelationshipCardsAPI, "/datasource/<datasource_id>/relationship_cards")
api.add_resource(DatasourceFieldMappingsAPI, "/datasource/<datasource_id>/field_mappings")
