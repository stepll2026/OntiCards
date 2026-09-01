"""
@File: query_history_api.py
@Description: 查询历史模块 API
@Author: 韩小豪 849631113@qq.com
@Create: 2026-03-30
"""

from datetime import datetime
from uuid import UUID
from typing import Any, Dict, Tuple

from flask import Blueprint, request
from flask_restful import Api, Resource
from sqlalchemy.dialects.postgresql import JSONB

from extensions.ext_database import db
from models.query_logs import QueryLog
from controllers.query_history.query_logger import QueryLogger

query_history_api = Blueprint("query_history_api", __name__)
api = Api(query_history_api)


def resp(code: int = 200, msg: str = "success", data: Any = None,
         http_status: int = 200) -> Tuple[Dict[str, Any], int]:
    return {  # type: ignore[return]
        "code": code,
        "msg": msg,
        "data": data
    }, http_status


def _is_uuid(v: str) -> bool:
    """校验字符串是否为有效的 UUID"""
    try:
        UUID(str(v))
        return True
    except Exception:
        return False


class QueryHistoryListResource(Resource):
    """
    查询历史列表接口
    GET /console/api/query_history/list
    """

    def get(self):
        """
        查询历史列表

        Query参数:
            - page: 页码，默认1
            - page_size: 每页条数，默认20
            - keyword: 搜索关键词（问题/SQL），可选
            - status: 查询状态筛选（success/error/timeout/all），默认all
            - start_date: 开始日期（YYYY-MM-DD），可选
            - end_date: 结束日期（YYYY-MM-DD），可选
            - user_id: 用户ID（UUID），必填
            - source_datasource_id: 查询来源数据源ID（UUID），可选
              - 如果传入，则只返回该数据源发起的查询历史
              - 语义：查询日志的 source_datasource_ids 列表中包含此ID
        """
        try:
            # 获取请求参数
            page = int(request.args.get('page', 1))
            page_size = int(request.args.get('page_size', 20))
            keyword = request.args.get('keyword', '').strip()
            status = request.args.get('status', 'all')
            start_date = request.args.get('start_date', '')
            end_date = request.args.get('end_date', '')
            user_id = request.args.get('user_id', '')
            source_datasource_id = request.args.get('source_datasource_id', '').strip()

            # 参数校验
            if not user_id:
                return resp(400, "user_id 不能为空", None, 400)

            if not _is_uuid(user_id):
                return resp(400, "user_id 格式错误，必须为 UUID", None, 400)

            if page < 1:
                page = 1
            if page_size < 1 or page_size > 100:
                page_size = 20

            # 构建查询
            query = QueryLog.query.filter(QueryLog.user_id == user_id)

            # 来源数据源筛选（JSONB 数组查询）
            # 数据格式可能是：
            # - 单数据源: ["uuid1"]
            # - 多数据源: [["uuid1", "uuid2"]]  嵌套数组格式（已入库规范化为一维数组）
            # 使用 PostgreSQL 的 @> 运算符检查数组中是否包含指定 UUID
            if source_datasource_id and _is_uuid(source_datasource_id):
                from sqlalchemy import text
                # 使用 text() 直接写原生 SQL，jsonb_build_array 将参数包装为 JSONB 数组格式
                # 这样可以避免参数绑定问题
                query = query.filter(
                    text('source_datasource_ids @> jsonb_build_array(:value)')
                ).params(value=source_datasource_id)
                print(f"[历史查询] JSONB 数组包含查询: source_datasource_id={source_datasource_id}")

            # 关键词搜索
            if keyword:
                query = query.filter(
                    db.or_(
                        QueryLog.question.ilike(f'%{keyword}%'),
                        QueryLog.sql.ilike(f'%{keyword}%')
                    )
                )

            # 状态筛选
            if status and status != 'all':
                query = query.filter(QueryLog.status == status)

            # 日期范围筛选
            if start_date:
                try:
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                    query = query.filter(QueryLog.created_at >= start_dt)
                except ValueError:
                    return resp(400, "start_date 格式错误，需为 YYYY-MM-DD", None, 400)

            if end_date:
                try:
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    # 设置为当天结束
                    end_dt = end_dt.replace(hour=23, minute=59, second=59)
                    query = query.filter(QueryLog.created_at <= end_dt)
                except ValueError:
                    return resp(400, "end_date 格式错误，需为 YYYY-MM-DD", None, 400)

            # 统计总数
            total = query.count()

            # 分页查询
            items = query.order_by(
                QueryLog.created_at.desc()
            ).offset((page - 1) * page_size).limit(page_size).all()

            # 格式化返回
            result_items = []
            for item in items:
                result_items.append({
                    "id": str(item.id),
                    "question": item.question,
                    "processed_question": item.processed_question,
                    "term_rewrite_info": item.term_rewrite_info,
                    "sql": item.sql,
                    "cluster_sqls": item.cluster_sqls,
                    "source_datasource_ids": item.source_datasource_ids,
                    "source_datasource_names": item.source_datasource_names,
                    "datasource_ids": item.datasource_ids,
                    "datasource_names": item.datasource_names,
                    "total_duration_ms": item.total_duration_ms,
                    "total_tokens": item.total_tokens,
                    "status": item.status,
                    "result_count": item.result_count,
                    "fusion_strategy": item.fusion_strategy,
                    "has_full_result": item.full_response_result is not None,
                    "created_at": item.created_at.isoformat() if item.created_at else None
                })

            return resp(200, "success", {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
                "items": result_items
            })

        except Exception as e:
            return resp(500, f"查询失败: {str(e)}", None, 500)


class QueryHistoryDetailResource(Resource):
    """
    查询历史详情接口
    GET /console/api/query_history/<query_id>
    """

    def get(self, query_id):
        """
        查询历史详情

        Path参数:
            - query_id: 查询记录ID（UUID）

        Query参数:
            - user_id: 用户ID（UUID），必填
        """
        try:
            user_id = request.args.get('user_id', '')

            if not user_id:
                return resp(400, "user_id 不能为空", None, 400)

            if not _is_uuid(user_id):
                return resp(400, "user_id 格式错误，必须为 UUID", None, 400)

            if not _is_uuid(query_id):
                return resp(400, "query_id 格式错误，必须为 UUID", None, 400)

            # 查询记录
            query_log = QueryLog.query.filter_by(
                id=query_id,
                user_id=user_id
            ).first()

            if not query_log:
                return resp(404, "查询记录不存在", None, 404)

            # 格式化返回
            return resp(200, "success", {
                "id": str(query_log.id),
                "user_id": str(query_log.user_id),
                "api_key_id": str(query_log.api_key_id) if query_log.api_key_id else None,
                "question": query_log.question,
                "processed_question": query_log.processed_question,
                "term_rewrite_info": query_log.term_rewrite_info,
                "sql": query_log.sql,
                "cluster_sqls": query_log.cluster_sqls,
                "source_datasource_ids": query_log.source_datasource_ids,
                "source_datasource_names": query_log.source_datasource_names,
                "datasource_ids": query_log.datasource_ids,
                "datasource_names": query_log.datasource_names,
                "table_names": query_log.table_names,
                "performance": {
                    "total_duration_ms": query_log.total_duration_ms,
                    "vector_search_ms": query_log.vector_search_ms,
                    "rerank_ms": query_log.rerank_ms,
                    "llm_gen_sql_ms": query_log.llm_gen_sql_ms,
                    "sql_execution_ms": query_log.sql_execution_ms,
                    "fusion_ms": query_log.fusion_ms
                },
                "tokens": {
                    "embedding_tokens": query_log.embedding_tokens,
                    "rerank_tokens": query_log.rerank_tokens,
                    "llm_prompt_tokens": query_log.llm_prompt_tokens,
                    "llm_completion_tokens": query_log.llm_completion_tokens,
                    "total_tokens": query_log.total_tokens
                },
                "result": {
                    "result_count": query_log.result_count
                },
                "quality": {
                    "cards_recalled": query_log.cards_recalled,
                    "cards_reranked": query_log.cards_reranked,
                    "cards_selected": query_log.cards_selected,
                    "top1_rerank_score": query_log.top1_rerank_score,
                    "avg_rerank_score": query_log.avg_rerank_score
                },
                "status": query_log.status,
                "error_message": query_log.error_message,
                "fusion_strategy": query_log.fusion_strategy,
                "full_response_result": query_log.full_response_result,
                "created_at": query_log.created_at.isoformat() if query_log.created_at else None
            })

        except Exception as e:
            return resp(500, f"查询详情失败: {str(e)}", None, 500)


class QueryHistoryDeleteResource(Resource):
    """
    删除查询历史记录接口
    DELETE /console/api/query_history/<query_id>
    """

    def delete(self, query_id):
        """
        删除单条查询历史记录

        Path参数:
            - query_id: 查询记录ID（UUID）

        Query参数:
            - user_id: 用户ID（UUID），必填

        说明：
            删除时会级联更新 query_stats_daily 聚合表，确保数据一致性。
        """
        try:
            user_id = request.args.get('user_id', '')

            if not user_id:
                return resp(400, "user_id 不能为空", None, 400)

            if not _is_uuid(user_id):
                return resp(400, "user_id 格式错误，必须为 UUID", None, 400)

            if not _is_uuid(query_id):
                return resp(400, "query_id 格式错误，必须为 UUID", None, 400)

            # 查询记录
            query_log = QueryLog.query.filter_by(
                id=query_id,
                user_id=user_id
            ).first()

            if not query_log:
                return resp(404, "查询记录不存在", None, 404)

            # 使用级联删除方法
            success = QueryLogger.delete_with_cascade(query_log)

            if success:
                return resp(200, "删除成功", {"deleted_id": str(query_id)})
            else:
                return resp(500, "删除失败", None, 500)

        except Exception as e:
            return resp(500, f"删除失败: {str(e)}", None, 500)


class QueryHistoryBatchDeleteResource(Resource):
    """
    批量删除查询历史记录接口
    DELETE /console/api/query_history/batch
    """

    def delete(self):
        """
        批量删除查询历史记录

        Query参数:
            - user_id: 用户ID（UUID），必填
            - query_ids: 要删除的查询记录ID列表，逗号分隔（可选）
            - before_date: 删除此日期之前的所有记录（可选），格式 YYYY-MM-DD
            - keep_days: 保留最近多少天的记录（可选），与 before_date 二选一

        说明：
            - query_ids、before_date、keep_days 三个条件至少要传一个
            - 删除时会级联更新 query_stats_daily 聚合表
        """
        try:
            user_id = request.args.get('user_id', '')
            query_ids_str = request.args.get('query_ids', '')
            before_date_str = request.args.get('before_date', '')
            keep_days_str = request.args.get('keep_days', '')

            if not user_id:
                return resp(400, "user_id 不能为空", None, 400)

            if not _is_uuid(user_id):
                return resp(400, "user_id 格式错误，必须为 UUID", None, 400)

            # 解析删除条件
            query_ids = []
            if query_ids_str:
                for qid in query_ids_str.split(','):
                    qid = qid.strip()
                    if qid and _is_uuid(qid):
                        query_ids.append(qid)

            # 计算 before_date
            before_date = None
            if before_date_str:
                try:
                    before_date = datetime.strptime(before_date_str, '%Y-%m-%d')
                except ValueError:
                    return resp(400, "before_date 格式错误，需为 YYYY-MM-DD", None, 400)

            # 计算 keep_days
            keep_days = None
            if keep_days_str:
                try:
                    keep_days = int(keep_days_str)
                    if keep_days < 0:
                        return resp(400, "keep_days 必须为正整数", None, 400)
                except ValueError:
                    return resp(400, "keep_days 格式错误，需为正整数", None, 400)

            # 至少要有一个删除条件
            if not query_ids and not before_date and not keep_days:
                return resp(400, "query_ids、before_date、keep_days 至少要传一个", None, 400)

            # 构建查询条件
            base_query = QueryLog.query.filter(QueryLog.user_id == user_id)

            if query_ids:
                base_query = base_query.filter(QueryLog.id.in_(query_ids))

            if before_date:
                base_query = base_query.filter(QueryLog.created_at < before_date)

            if keep_days:
                from datetime import timedelta
                cutoff_date = datetime.utcnow() - timedelta(days=keep_days)
                base_query = base_query.filter(QueryLog.created_at < cutoff_date)

            # 先查询要删除的记录
            records_to_delete = base_query.all()
            total_to_delete = len(records_to_delete)

            if total_to_delete == 0:
                return resp(200, "没有需要删除的记录", {"deleted_count": 0})

            # 逐条删除（确保级联更新）
            deleted_count = 0
            for query_log in records_to_delete:
                if QueryLogger.delete_with_cascade(query_log):
                    deleted_count += 1

            return resp(200, f"成功删除 {deleted_count} 条记录", {
                "deleted_count": deleted_count,
                "total_found": total_to_delete
            })

        except Exception as e:
            return resp(500, f"批量删除失败: {str(e)}", None, 500)


class QueryHistoryStatsResource(Resource):
    """
    查询历史统计接口
    GET /console/api/query_history/stats
    """

    def get(self):
        """
        查询历史统计

        Query参数:
            - user_id: 用户ID（UUID），必填
            - source_datasource_id: 查询来源数据源ID（UUID），可选
              - 如果传入，则只统计该数据源发起的查询
            - start_date: 开始日期（YYYY-MM-DD），可选，不传则查询最早记录
            - end_date: 结束日期（YYYY-MM-DD），可选，不传则查询至今
            - workspace_id: 工作区ID（UUID），可选，仅作兼容
        """
        try:
            user_id = request.args.get('user_id', '')
            source_datasource_id = request.args.get('source_datasource_id', '').strip()
            start_date = request.args.get('start_date', '')
            end_date = request.args.get('end_date', '')

            if not user_id:
                return resp(400, "user_id 不能为空", None, 400)

            if not _is_uuid(user_id):
                return resp(400, "user_id 格式错误，必须为 UUID", None, 400)

            # 日期范围处理 - 不传时查询所有时间
            if start_date:
                try:
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                except ValueError:
                    return resp(400, "start_date 格式错误，需为 YYYY-MM-DD", None, 400)
            else:
                start_dt = None

            if end_date:
                try:
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    end_dt = end_dt.replace(hour=23, minute=59, second=59)
                except ValueError:
                    return resp(400, "end_date 格式错误，需为 YYYY-MM-DD", None, 400)
            else:
                end_dt = None

            # 构建过滤条件
            base_filters = [QueryLog.user_id == user_id]
            extra_filters = []  # 需要特殊处理的 filter

            # 来源数据源筛选（JSONB 数组查询）
            # 使用 PostgreSQL 的 @> 运算符检查数组中是否包含指定 UUID
            if source_datasource_id and _is_uuid(source_datasource_id):
                from sqlalchemy import text
                # 使用 text() 直接写原生 SQL，jsonb_build_array 将参数包装为 JSONB 数组格式
                text_filter = text('source_datasource_ids @> jsonb_build_array(:value)')
                text_filter = text_filter.params(value=source_datasource_id)
                extra_filters.append(text_filter)
                print(f"[统计] JSONB 数组包含查询: source_datasource_id={source_datasource_id}")

            if start_dt:
                base_filters.append(QueryLog.created_at >= start_dt)
            if end_dt:
                base_filters.append(QueryLog.created_at <= end_dt)

            # 统计查询
            from sqlalchemy import func, case

            all_filters = base_filters + extra_filters
            stats = db.session.query(
                func.count(QueryLog.id).label('total_queries'),
                func.sum(case((QueryLog.status == 'success', 1), else_=0)).label('success_queries'),
                func.sum(case((QueryLog.status == 'error', 1), else_=0)).label('error_queries'),
                func.sum(case((QueryLog.status == 'timeout', 1), else_=0)).label('timeout_queries'),
                func.sum(QueryLog.total_tokens).label('total_tokens'),
                func.avg(QueryLog.total_duration_ms).label('avg_duration_ms'),
                func.min(QueryLog.total_duration_ms).label('min_duration_ms'),
                func.max(QueryLog.total_duration_ms).label('max_duration_ms')
            ).filter(*all_filters).first()

            total = stats.total_queries or 0
            success = stats.success_queries or 0

            # 构建返回的日期范围
            if start_date and end_date:
                period = {"start_date": start_date, "end_date": end_date}
            elif start_date:
                period = {"start_date": start_date, "end_date": "至今"}
            elif end_date:
                period = {"start_date": "最早记录", "end_date": end_date}
            else:
                period = {"start_date": "最早记录", "end_date": "至今"}

            return resp(200, "success", {
                "period": period,
                "total_queries": total,
                "success_queries": success,
                "error_queries": stats.error_queries or 0,
                "timeout_queries": stats.timeout_queries or 0,
                "success_rate": round(success / total * 100, 2) if total > 0 else 0,
                "total_tokens": stats.total_tokens or 0,
                "avg_duration_ms": int(stats.avg_duration_ms) if stats.avg_duration_ms else 0,
                "min_duration_ms": stats.min_duration_ms or 0,
                "max_duration_ms": stats.max_duration_ms or 0
            })

        except Exception as e:
            return resp(500, f"查询统计失败: {str(e)}", None, 500)


# 路由注册
api.add_resource(QueryHistoryListResource, '/list')
api.add_resource(QueryHistoryDetailResource, '/<query_id>')
api.add_resource(QueryHistoryStatsResource, '/stats')
api.add_resource(QueryHistoryDeleteResource, '/<query_id>/delete')
api.add_resource(QueryHistoryBatchDeleteResource, '/batch/delete')
