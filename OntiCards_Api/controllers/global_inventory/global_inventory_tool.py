"""
 @File: global_inventory_tool.py
 @Description: 全域盘点 API 定义 - 真正的全域盘点，用户可选择多数据源，对所有数据源中表进行表关系发现和关系卡片生成
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-02-06

 功能说明：
 全域盘点接口，支持单数据源和多数据源
 1. 对数据源中的所有表进行关系发现（支持单数据源和多数据源）
 2. 生成以表为中心的关系卡片
 3. 支持查询单表的关系卡片
 4. 多数据源场景下自动标记跨源关系
"""

from __future__ import annotations
from typing import List, Dict, Any
import json
from flask import Blueprint, request
from flask_restful import Resource, Api
from flask_login import login_required, current_user
from extensions.ext_database import db

from models.datasource_infos import DatasourceInfo
from models.global_inventory import TableRelationship, TableRelationshipCard


# 创建独立的Blueprint
global_inventory_bp = Blueprint("global_inventory_bp", __name__)
api = Api(global_inventory_bp)


def resp(data=None, code=200, msg="操作成功"):
    """统一响应格式"""
    return {"code": code, "msg": msg, "data": data}, code


class DiscoverAPI(Resource):
    """
    表关系发现接口 - 对数据源中的所有表进行关系盘点（支持单源和多源）
    """

    @login_required
    def post(self):
        """
        启动表关系发现任务

        Request Body:
            {
                "datasource_id": "xxx",              # 单数据源ID（与datasource_ids二选一）
                "datasource_ids": ["xxx", "yyy"],   # 多数据源ID列表（与datasource_id二选一）
                "schema_name": "public",             # 可选，Schema名称
                "confidence_threshold": 0.5,         # 可选，置信度阈值（默认0.5）
                "max_workers": 10,                   # 可选，最大并行线程数（默认10）
                "enable_profiling": true             # 可选，是否启用字段画像（默认true，提升准确性）
            }

        Returns:
            {
                "success": true,
                "tables_count": 10,
                "relationships_count": 25,
                "cards_count": 10,
                "relationships": [...],
                "cards": [...],
                "statistics": {...},
                "persist_result": {...},
                "is_multi_source": false,            # 是否多数据源模式
                "datasource_ids": ["xxx"],           # 参与的数据源ID列表
                "cross_source_count": 0              # 跨源关系数量
            }
        """
        from controllers.global_inventory.global_inventory_service import (
            run_global_inventory
        )

        payload = request.get_json(force=True, silent=False) or {}

        # 获取参数 - 支持单个datasource_id或多个datasource_ids
        datasource_id = payload.get("datasource_id")
        datasource_ids = payload.get("datasource_ids")

        # 统一处理为列表
        if datasource_ids and isinstance(datasource_ids, list):
            ds_id_list = [str(ds_id).strip() for ds_id in datasource_ids if ds_id]
        elif datasource_id:
            ds_id_list = [str(datasource_id).strip()]
        else:
            return resp(None, 400, "缺少 datasource_id 或 datasource_ids")

        if not ds_id_list:
            return resp(None, 400, "数据源ID不能为空")

        schema_name = payload.get("schema_name")
        confidence_threshold = float(payload.get("confidence_threshold", 0.5))
        max_workers = int(payload.get("max_workers", 10))
        enable_profiling = payload.get("enable_profiling", True)

        # 校验所有数据源权限
        for ds_id in ds_id_list:
            ds = db.session.query(DatasourceInfo).filter(
                DatasourceInfo.id == ds_id,
                DatasourceInfo.user_id == current_user.id
            ).first()
            if not ds:
                return resp(None, 404, f"数据源 {ds_id} 不存在或无权访问")

        try:
            # 执行全域盘点（传入列表或单个ID）
            result = run_global_inventory(
                datasource_id=ds_id_list if len(ds_id_list) > 1 else ds_id_list[0],
                user_id=str(current_user.id),
                schema_name=schema_name,
                confidence_threshold=confidence_threshold,
                max_workers=max_workers,
                enable_profiling=enable_profiling
            )

            if result.get("success"):
                msg = "全域盘点完成"
                if result.get("is_multi_source"):
                    msg = f"多数据源全域盘点完成（{len(ds_id_list)}个数据源，{result.get('cross_source_count', 0)}个跨源关系）"
                return resp(result, 200, msg)
            else:
                return resp(result, 500, f"全域盘点失败: {result.get('errors')}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            return resp(None, 500, f"全域盘点失败: {str(e)}")


class TableRelationshipCardAPI(Resource):
    """
    单表关系卡片查询接口
    """

    @login_required
    def get(self, datasource_id, table_name):
        """
        获取单表的关系卡片

        Args:
            datasource_id: 数据源ID
            table_name: 表名

        Returns:
            {
                "card": {
                    "DocInfo": {...},
                    "TableInfo": {...},
                    "Relationships": [...],
                    "FusionHints": {...},
                    "JoinSummary": "...",
                    "Statistics": {...}
                }
            }
        """
        # 校验数据源权限
        ds = db.session.query(DatasourceInfo).filter(
            DatasourceInfo.id == datasource_id,
            DatasourceInfo.user_id == current_user.id
        ).first()
        if not ds:
            return resp(None, 404, "数据源不存在或无权访问")

        # 查询关系卡片
        card = db.session.query(TableRelationshipCard).filter(
            TableRelationshipCard.datasource_id == datasource_id,
            TableRelationshipCard.table_name == table_name
        ).first()

        if not card:
            return resp(None, 404, f"表 {table_name} 的关系卡片不存在")

        return resp({
            "card": card.card_data,
            "version": card.version,
            "w_uuid": card.w_uuid,
            "schema_hash": card.schema_hash,
            "related_datasource_ids": card.related_datasource_ids,
            "has_cross_source_relations": card.has_cross_source_relations,
            "created_at": card.created_at.isoformat() if card.created_at else None,
            "updated_at": card.updated_at.isoformat() if card.updated_at else None
        }, 200, "获取关系卡片成功")


class AllRelationshipCardsAPI(Resource):
    """
    数据源所有关系卡片查询接口
    """

    @login_required
    def get(self, datasource_id):
        """
        获取数据源下所有表的关系卡片

        Args:
            datasource_id: 数据源ID

        Query Params:
            with_relationships: 是否只返回有关系的表（默认false）

        Returns:
            {
                "cards": [
                    {
                        "table_name": "users",
                        "card": {...},
                        "version": 1,
                        "related_tables_count": 3
                    }
                ],
                "total": 10,
                "statistics": {
                    "tables_with_relationships": 8,
                    "tables_without_relationships": 2
                }
            }
        """
        # 校验数据源权限
        ds = db.session.query(DatasourceInfo).filter(
            DatasourceInfo.id == datasource_id,
            DatasourceInfo.user_id == current_user.id
        ).first()
        if not ds:
            return resp(None, 404, "数据源不存在或无权访问")

        with_relationships = request.args.get("with_relationships", "false").lower() == "true"

        # 查询所有关系卡片
        cards = db.session.query(TableRelationshipCard).filter(
            TableRelationshipCard.datasource_id == datasource_id
        ).order_by(TableRelationshipCard.table_name).all()

        items = []
        tables_with_rels = 0
        tables_without_rels = 0

        for card in cards:
            card_data = card.card_data or {}
            # 处理 card_data 可能是 JSON 字符串的情况
            if isinstance(card_data, str):
                try:
                    card_data = json.loads(card_data)
                except json.JSONDecodeError:
                    card_data = {}
            relationships = card_data.get("Relationships", [])
            related_tables_count = len(relationships)

            # 统计跨源关系数量
            cross_source_count = sum(1 for r in relationships if r.get("is_cross_source", False))

            if related_tables_count > 0:
                tables_with_rels += 1
            else:
                tables_without_rels += 1
                if with_relationships:
                    continue

            items.append({
                "table_name": card.table_name,
                "card": card_data,
                "version": card.version,
                "w_uuid": card.w_uuid,
                "schema_hash": card.schema_hash,
                "related_datasource_ids": card.related_datasource_ids,
                "has_cross_source_relations": card.has_cross_source_relations,
                "related_tables_count": related_tables_count,
                "cross_source_relations_count": cross_source_count,
                "created_at": card.created_at.isoformat() if card.created_at else None,
                "updated_at": card.updated_at.isoformat() if card.updated_at else None
            })

        return resp({
            "cards": items,
            "total": len(items),
            "statistics": {
                "tables_with_relationships": tables_with_rels,
                "tables_without_relationships": tables_without_rels
            }
        }, 200, "获取关系卡片成功")


class AllRelationshipsAPI(Resource):
    """
    数据源所有表关系查询接口
    """

    @login_required
    def get(self, datasource_id):
        """
        获取数据源下所有表之间的关系

        Args:
            datasource_id: 数据源ID

        Query Params:
            table_name: 筛选包含特定表的关系（可选）
            min_confidence: 最小置信度筛选（可选）

        Returns:
            {
                "relationships": [
                    {
                        "id": "xxx",
                        "table_a": "users",
                        "table_b": "orders",
                        "relationship_type": "FK",
                        "join_conditions": [...],
                        "relationship_strength": 0.95,
                        "cardinality": "one_to_many"
                    }
                ],
                "total": 25,
                "statistics": {...}
            }
        """
        # 校验数据源权限
        ds = db.session.query(DatasourceInfo).filter(
            DatasourceInfo.id == datasource_id,
            DatasourceInfo.user_id == current_user.id
        ).first()
        if not ds:
            return resp(None, 404, "数据源不存在或无权访问")

        # 可选筛选条件
        table_name = request.args.get("table_name")
        min_confidence = request.args.get("min_confidence", type=float)

        # 构建查询 - 查询该数据源相关的所有关系（作为 table_a 或 table_b 的数据源）
        query = db.session.query(TableRelationship).filter(
            db.or_(
                TableRelationship.table_a_datasource_id == datasource_id,
                TableRelationship.table_b_datasource_id == datasource_id
            )
        )

        if table_name:
            query = query.filter(
                db.or_(
                    TableRelationship.table_a == table_name,
                    TableRelationship.table_b == table_name
                )
            )

        if min_confidence:
            query = query.filter(TableRelationship.relationship_strength >= min_confidence)

        relationships = query.order_by(
            TableRelationship.relationship_strength.desc()
        ).all()

        # 统计信息
        type_counts = {}
        cardinality_counts = {}
        total_strength = 0
        cross_source_count = 0

        items = []
        for rel in relationships:
            is_cross = rel.is_cross_source or False
            if is_cross:
                cross_source_count += 1

            items.append({
                "id": str(rel.id),
                "table_a": rel.table_a,
                "table_a_datasource_id": str(rel.table_a_datasource_id) if rel.table_a_datasource_id else None,
                "table_b": rel.table_b,
                "table_b_datasource_id": str(rel.table_b_datasource_id) if rel.table_b_datasource_id else None,
                "is_cross_source": is_cross,
                "relationship_type": rel.relationship_type,
                "join_conditions": rel.join_conditions or [],
                "relationship_strength": float(rel.relationship_strength) if rel.relationship_strength else None,
                "cardinality": rel.cardinality,
                "created_at": rel.created_at.isoformat() if rel.created_at else None
            })

            # 统计
            rel_type = rel.relationship_type or "unknown"
            type_counts[rel_type] = type_counts.get(rel_type, 0) + 1

            cardinality = rel.cardinality or "unknown"
            cardinality_counts[cardinality] = cardinality_counts.get(cardinality, 0) + 1

            if rel.relationship_strength:
                total_strength += float(rel.relationship_strength)

        return resp({
            "relationships": items,
            "total": len(items),
            "statistics": {
                "by_type": type_counts,
                "by_cardinality": cardinality_counts,
                "avg_strength": round(total_strength / len(items), 4) if items else 0,
                "cross_source_count": cross_source_count,
                "intra_source_count": len(items) - cross_source_count
            }
        }, 200, "获取表关系成功")


class RelationshipGraphAPI(Resource):
    """
    关系图谱数据接口（用于可视化）
    """

    @login_required
    def get(self, datasource_id):
        """
        获取关系图谱数据（用于可视化）

        Args:
            datasource_id: 数据源ID

        Returns:
            {
                "nodes": [
                    {
                        "id": "users",
                        "label": "users",
                        "type": "table",
                        "related_count": 3
                    }
                ],
                "edges": [
                    {
                        "id": "xxx",
                        "source": "users",
                        "target": "orders",
                        "label": "FK",
                        "strength": 0.95,
                        "cardinality": "one_to_many"
                    }
                ]
            }
        """
        # 校验数据源权限
        ds = db.session.query(DatasourceInfo).filter(
            DatasourceInfo.id == datasource_id,
            DatasourceInfo.user_id == current_user.id
        ).first()
        if not ds:
            return resp(None, 404, "数据源不存在或无权访问")

        # 查询所有关系 - 查询该数据源相关的所有关系
        relationships = db.session.query(TableRelationship).filter(
            db.or_(
                TableRelationship.table_a_datasource_id == datasource_id,
                TableRelationship.table_b_datasource_id == datasource_id
            )
        ).all()

        # 构建节点和边
        nodes = {}
        edges = []
        cross_source_edge_count = 0

        for rel in relationships:
            is_cross = rel.is_cross_source or False

            # 添加节点
            if rel.table_a not in nodes:
                nodes[rel.table_a] = {
                    "id": rel.table_a,
                    "label": rel.table_a,
                    "type": "table",
                    "datasource_id": str(rel.table_a_datasource_id) if rel.table_a_datasource_id else str(datasource_id),
                    "related_count": 0,
                    "cross_source_count": 0
                }
            nodes[rel.table_a]["related_count"] += 1
            if is_cross:
                nodes[rel.table_a]["cross_source_count"] += 1

            if rel.table_b not in nodes:
                nodes[rel.table_b] = {
                    "id": rel.table_b,
                    "label": rel.table_b,
                    "type": "table",
                    "datasource_id": str(rel.table_b_datasource_id) if rel.table_b_datasource_id else str(datasource_id),
                    "related_count": 0,
                    "cross_source_count": 0
                }
            nodes[rel.table_b]["related_count"] += 1
            if is_cross:
                nodes[rel.table_b]["cross_source_count"] += 1
                cross_source_edge_count += 1

            # 添加边
            edges.append({
                "id": str(rel.id),
                "source": rel.table_a,
                "target": rel.table_b,
                "source_datasource_id": str(rel.table_a_datasource_id) if rel.table_a_datasource_id else None,
                "target_datasource_id": str(rel.table_b_datasource_id) if rel.table_b_datasource_id else None,
                "is_cross_source": is_cross,
                "label": rel.relationship_type,
                "strength": float(rel.relationship_strength) if rel.relationship_strength else None,
                "cardinality": rel.cardinality,
                "join_conditions": rel.join_conditions or []
            })

        return resp({
            "nodes": list(nodes.values()),
            "edges": edges,
            "statistics": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "cross_source_edges": cross_source_edge_count
            }
        }, 200, "获取关系图谱成功")


class JoinSuggestionAPI(Resource):
    """
    联表查询建议接口 - 用于NL2SQL
    """

    @login_required
    def post(self):
        """
        根据表名列表获取联表查询建议

        Request Body:
            {
                "datasource_id": "xxx",
                "tables": ["users", "orders", "products"]
            }

        Returns:
            {
                "suggestions": [
                    {
                        "from_table": "orders",
                        "to_table": "users",
                        "join_type": "LEFT JOIN",
                        "join_condition": "orders.user_id = users.id",
                        "confidence": 0.95,
                        "use_cases": [...]
                    }
                ],
                "recommended_join_order": ["users", "orders", "products"],
                "sample_sql": "SELECT * FROM users LEFT JOIN orders ON ..."
            }
        """
        payload = request.get_json(force=True, silent=False) or {}

        datasource_id = str(payload.get("datasource_id") or "").strip()
        tables = payload.get("tables") or []

        if not datasource_id:
            return resp(None, 400, "缺少 datasource_id")
        if not tables or len(tables) < 2:
            return resp(None, 400, "至少需要2张表")

        # 校验数据源权限
        ds = db.session.query(DatasourceInfo).filter(
            DatasourceInfo.id == datasource_id,
            DatasourceInfo.user_id == current_user.id
        ).first()
        if not ds:
            return resp(None, 404, "数据源不存在或无权访问")

        # 查询这些表之间的关系（支持跨源）
        relationships = db.session.query(TableRelationship).filter(
            db.or_(
                TableRelationship.table_a_datasource_id == datasource_id,
                TableRelationship.table_b_datasource_id == datasource_id
            ),
            db.and_(
                TableRelationship.table_a.in_(tables),
                TableRelationship.table_b.in_(tables)
            )
        ).order_by(TableRelationship.relationship_strength.desc()).all()

        suggestions = []
        for rel in relationships:
            join_conditions = rel.join_conditions or []

            for cond in join_conditions:
                suggestion = {
                    "from_table": rel.table_a,
                    "to_table": rel.table_b,
                    "from_column": cond.get("local_field"),
                    "to_column": cond.get("remote_field"),
                    "join_type": self._recommend_join_type(rel.cardinality),
                    "join_condition": f"{rel.table_a}.{cond.get('local_field')} = {rel.table_b}.{cond.get('remote_field')}",
                    "confidence": float(rel.relationship_strength) if rel.relationship_strength else cond.get("confidence", 0),
                    "cardinality": rel.cardinality
                }
                suggestions.append(suggestion)

        # 推荐JOIN顺序（基于关系强度）
        join_order = self._recommend_join_order(tables, suggestions)

        # 生成示例SQL
        sample_sql = self._generate_sample_sql(join_order, suggestions)

        return resp({
            "suggestions": suggestions,
            "recommended_join_order": join_order,
            "sample_sql": sample_sql
        }, 200, "获取联表建议成功")

    def _recommend_join_type(self, cardinality: str) -> str:
        """推荐JOIN类型"""
        join_type_map = {
            "one_to_one": "INNER JOIN",
            "one_to_many": "LEFT JOIN",
            "many_to_one": "LEFT JOIN",
            "many_to_many": "INNER JOIN"
        }
        return join_type_map.get(cardinality, "LEFT JOIN")

    def _recommend_join_order(
        self,
        tables: List[str],
        suggestions: List[Dict[str, Any]]
    ) -> List[str]:
        """
        推荐JOIN顺序

        策略：将关系最多/置信度最高的表作为起点
        """
        # 统计每张表的关系数和总置信度
        table_scores = {t: {"count": 0, "total_confidence": 0} for t in tables}

        for sug in suggestions:
            from_table = sug["from_table"]
            to_table = sug["to_table"]
            confidence = sug.get("confidence", 0)

            if from_table in table_scores:
                table_scores[from_table]["count"] += 1
                table_scores[from_table]["total_confidence"] += confidence
            if to_table in table_scores:
                table_scores[to_table]["count"] += 1
                table_scores[to_table]["total_confidence"] += confidence

        # 按得分排序
        sorted_tables = sorted(
            tables,
            key=lambda t: (
                table_scores[t]["count"],
                table_scores[t]["total_confidence"]
            ),
            reverse=True
        )

        return sorted_tables

    def _generate_sample_sql(
        self,
        join_order: List[str],
        suggestions: List[Dict[str, Any]]
    ) -> str:
        """生成示例SQL"""
        if len(join_order) < 2:
            return f"SELECT * FROM {join_order[0]}" if join_order else ""

        sql_parts = [f"SELECT *\nFROM {join_order[0]}"]

        # 已处理的表
        processed = {join_order[0]}

        for table in join_order[1:]:
            # 找到与已处理表的关系
            best_suggestion = None
            best_confidence = -1

            for sug in suggestions:
                from_t = sug["from_table"]
                to_t = sug["to_table"]

                # 检查是否连接已处理的表和当前表
                if (from_t in processed and to_t == table) or (to_t in processed and from_t == table):
                    if sug.get("confidence", 0) > best_confidence:
                        best_suggestion = sug
                        best_confidence = sug.get("confidence", 0)

            if best_suggestion:
                join_type = best_suggestion.get("join_type", "LEFT JOIN")
                join_condition = best_suggestion.get("join_condition", "")
                sql_parts.append(f"{join_type} {table} ON {join_condition}")
            else:
                # 没有找到关系，使用CROSS JOIN（不推荐）
                sql_parts.append(f"CROSS JOIN {table}")

            processed.add(table)

        return "\n".join(sql_parts)


class DeleteRelationshipsAPI(Resource):
    """
    删除数据源的关系数据
    """

    @login_required
    def delete(self, datasource_id):
        """
        删除数据源的所有关系数据（用于重新发现）

        Args:
            datasource_id: 数据源ID

        Returns:
            {
                "deleted_relationships": 25,
                "deleted_cards": 10
            }
        """
        # 校验数据源权限
        ds = db.session.query(DatasourceInfo).filter(
            DatasourceInfo.id == datasource_id,
            DatasourceInfo.user_id == current_user.id
        ).first()
        if not ds:
            return resp(None, 404, "数据源不存在或无权访问")

        try:
            # 删除关系（该数据源作为 table_a 或 table_b 的数据源）
            deleted_rels = db.session.query(TableRelationship).filter(
                db.or_(
                    TableRelationship.table_a_datasource_id == datasource_id,
                    TableRelationship.table_b_datasource_id == datasource_id
                )
            ).delete(synchronize_session=False)

            # 删除卡片
            deleted_cards = db.session.query(TableRelationshipCard).filter(
                TableRelationshipCard.datasource_id == datasource_id
            ).delete(synchronize_session=False)

            db.session.commit()

            # TODO: 同时删除向量库中的数据（关系卡片暂时无需入向量库做召回检索）

            return resp({
                "deleted_relationships": deleted_rels,
                "deleted_cards": deleted_cards
            }, 200, "删除成功")

        except Exception as e:
            db.session.rollback()
            return resp(None, 500, f"删除失败: {str(e)}")


class SingleRelationshipDeleteAPI(Resource):
    """
    删除单条关系记录接口
    """

    @login_required
    def delete(self, relationship_id):
        """
        根据关系ID删除单条关系记录

        Args:
            relationship_id: 关系记录ID (UUID)

        Returns:
            {
                "deleted": true,
                "relationship_id": "xxx"
            }
        """
        try:
            # 查询该关系是否存在
            relationship = db.session.query(TableRelationship).filter(
                TableRelationship.id == relationship_id
            ).first()

            if not relationship:
                return resp(None, 404, "关系记录不存在")

            # 校验数据源权限（用户需要拥有该关系关联的数据源权限）
            datasource_ids = []
            if relationship.table_a_datasource_id:
                datasource_ids.append(str(relationship.table_a_datasource_id))
            if relationship.table_b_datasource_id:
                datasource_ids.append(str(relationship.table_b_datasource_id))

            for ds_id in datasource_ids:
                ds = db.session.query(DatasourceInfo).filter(
                    DatasourceInfo.id == ds_id,
                    DatasourceInfo.user_id == current_user.id
                ).first()
                if not ds:
                    return resp(None, 403, f"无权删除该关系记录")

            # 删除关系
            db.session.delete(relationship)
            db.session.commit()

            return resp({
                "deleted": True,
                "relationship_id": str(relationship_id)
            }, 200, "删除成功")

        except Exception as e:
            db.session.rollback()
            return resp(None, 500, f"删除失败: {str(e)}")


class BatchRelationshipCardsAPI(Resource):
    """
    批量查询关系卡片接口 - 供NL2SQL模块调用

    使用场景：
    1. 向量检索召回了若干张数据卡片（如: orders, users, products）
    2. 调用此接口获取这些表的关系卡片
    3. 将数据卡片 + 关系卡片一起提供给LLM生成SQL
    """

    @login_required
    def post(self):
        """
        根据表名列表批量获取关系卡片

        Request Body:
            {
                "datasource_id": "xxx",
                "table_names": ["orders", "users", "products"]
            }

        Returns:
            {
                "cards": {
                    "orders": {
                        "table_name": "orders",
                        "relationships": [...],
                        "join_summary": "...",
                        "fusion_hints": {...}
                    },
                    "users": {...}
                },
                "join_suggestions": [
                    {
                        "from_table": "orders",
                        "to_table": "users",
                        "join_condition": "orders.user_id = users.id",
                        "join_type": "LEFT JOIN"
                    }
                ],
                "missing_tables": ["products"]
            }
        """
        payload = request.get_json(force=True, silent=False) or {}

        datasource_id = str(payload.get("datasource_id") or "").strip()
        table_names = payload.get("table_names") or []

        if not datasource_id:
            return resp(None, 400, "缺少 datasource_id")
        if not table_names:
            return resp(None, 400, "缺少 table_names")

        # 校验数据源权限
        ds = db.session.query(DatasourceInfo).filter(
            DatasourceInfo.id == datasource_id,
            DatasourceInfo.user_id == current_user.id
        ).first()
        if not ds:
            return resp(None, 404, "数据源不存在或无权访问")

        # 批量查询关系卡片
        cards = db.session.query(TableRelationshipCard).filter(
            TableRelationshipCard.datasource_id == datasource_id,
            TableRelationshipCard.table_name.in_(table_names)
        ).all()

        # 构建结果
        cards_dict = {}
        found_tables = set()
        all_join_suggestions = []

        for card in cards:
            table_name = card.table_name
            found_tables.add(table_name)

            card_data = card.card_data or {}
            # 处理 card_data 可能是 JSON 字符串的情况
            if isinstance(card_data, str):
                try:
                    card_data = json.loads(card_data)
                except json.JSONDecodeError:
                    card_data = {}

            # 提取关系信息
            relationships = card_data.get("Relationships", [])

            # 只保留与查询表相关的关系
            relevant_relationships = []
            for rel in relationships:
                related_table = rel.get("related_table", "")
                if related_table in table_names:
                    relevant_relationships.append(rel)

                    # 提取JOIN建议
                    join_suggestion = rel.get("join_suggestion", {})
                    for field in rel.get("join_fields", []):
                        all_join_suggestions.append({
                            "from_table": table_name,
                            "to_table": related_table,
                            "from_column": field.get("local_field"),
                            "to_column": field.get("remote_field"),
                            "join_type": join_suggestion.get("join_type", "LEFT JOIN"),
                            "join_condition": f"{table_name}.{field.get('local_field')} = {related_table}.{field.get('remote_field')}",
                            "confidence": field.get("confidence", 0)
                        })

            cards_dict[table_name] = {
                "table_name": table_name,
                "relationships": relevant_relationships,
                "all_relationships": relationships,  # 完整的关系列表
                "join_summary": card_data.get("JoinSummary", ""),
                "fusion_hints": card_data.get("FusionHints", {})
            }

        # 去重JOIN建议（同一对表只保留置信度最高的）
        unique_joins = {}
        for sug in all_join_suggestions:
            key = tuple(sorted([sug["from_table"], sug["to_table"]]))
            if key not in unique_joins or sug["confidence"] > unique_joins[key]["confidence"]:
                unique_joins[key] = sug

        # 缺失的表
        missing_tables = list(set(table_names) - found_tables)

        return resp({
            "cards": cards_dict,
            "join_suggestions": list(unique_joins.values()),
            "missing_tables": missing_tables,
            "found_count": len(found_tables),
            "requested_count": len(table_names)
        }, 200, "批量获取关系卡片成功")


# 注册路由
api.add_resource(DiscoverAPI, "/discover")
api.add_resource(TableRelationshipCardAPI, "/card/<datasource_id>/<table_name>")
api.add_resource(AllRelationshipCardsAPI, "/cards/<datasource_id>")
api.add_resource(AllRelationshipsAPI, "/relationships/<datasource_id>")
api.add_resource(RelationshipGraphAPI, "/graph/<datasource_id>")
api.add_resource(JoinSuggestionAPI, "/join_suggestion")
api.add_resource(DeleteRelationshipsAPI, "/delete/<datasource_id>")
api.add_resource(SingleRelationshipDeleteAPI, "/relationship/<relationship_id>")
api.add_resource(BatchRelationshipCardsAPI, "/batch_cards")  # 供NL2SQL调用
