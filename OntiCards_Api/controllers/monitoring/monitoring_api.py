"""
 @File: monitoring_api.py
 @Description: 监控模块 API
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-03-30
 @Update: 2026-04-07 - 扩展接口返回值，丰富监控数据展示
"""

from datetime import datetime, timedelta, date, timezone, timedelta as td
from uuid import UUID
from typing import Any, Dict, Tuple
from collections import defaultdict

from flask import Blueprint, request
from flask_restful import Api, Resource
from sqlalchemy import func, case, extract, text

from extensions.ext_database import db
from models.query_logs import QueryLog
from models.query_stats_daily import QueryStatsDaily
from models.users import User

# 中国时区 (UTC+8)
tz_cst = timezone(td(hours=8))

monitoring_api = Blueprint("monitoring_api", __name__)
api = Api(monitoring_api)


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


class MonitoringOverviewResource(Resource):
    """
    监控总览接口
    GET /console/api/monitoring/overview
    """

    def get(self):
        """
        监控总览数据

        Query参数:
            - user_id: 用户ID（UUID），必填
        """
        try:
            user_id = request.args.get('user_id', '')

            if not user_id:
                return resp(400, "user_id 不能为空", None, 400)

            if not _is_uuid(user_id):
                return resp(400, "user_id 格式错误，必须为 UUID", None, 400)

            # 验证 user_id 是否存在于数据库中
            user_exists = db.session.query(User.id).filter(User.id == user_id).first()
            if not user_exists:
                return resp(404, "用户不存在", None, 404)

            # 实时数据（最近24小时）
            recent_stats = db.session.query(
                func.count(QueryLog.id).label('total_queries'),
                func.sum(case((QueryLog.status == 'success', 1), else_=0)).label('success_queries'),
                func.sum(case((QueryLog.status == 'error', 1), else_=0)).label('error_queries'),
                func.sum(case((QueryLog.status == 'timeout', 1), else_=0)).label('timeout_queries'),
                func.avg(QueryLog.total_duration_ms).label('avg_duration_ms'),
                func.sum(QueryLog.total_tokens).label('total_tokens'),
                func.sum(QueryLog.embedding_tokens).label('total_embedding_tokens'),
                func.sum(QueryLog.rerank_tokens).label('total_rerank_tokens'),
                func.sum(QueryLog.llm_prompt_tokens + QueryLog.llm_completion_tokens).label('total_llm_tokens')
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= datetime.now(tz_cst) - timedelta(hours=24)
            ).first()

            total_24h = recent_stats.total_queries or 0
            success_24h = recent_stats.success_queries or 0

            # 今日数据
            today_start = datetime.now(tz_cst).replace(hour=0, minute=0, second=0, microsecond=0)
            today_stats = db.session.query(
                func.count(QueryLog.id).label('total_queries'),
                func.sum(case((QueryLog.status == 'success', 1), else_=0)).label('success_queries'),
                func.sum(QueryLog.total_tokens).label('total_tokens')
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= today_start
            ).first()

            # 趋势数据（最近30天）
            daily_trend = QueryStatsDaily.query.filter(
                QueryStatsDaily.user_id == user_id,
                QueryStatsDaily.stat_date >= date.today() - timedelta(days=30)
            ).order_by(QueryStatsDaily.stat_date.asc()).all()

            # 格式化趋势数据
            trend_items = []
            total_cost_cents = 0
            for day in daily_trend:
                cost_yuan = day.estimated_cost_cents / 100 if day.estimated_cost_cents else 0
                total_cost_cents += day.estimated_cost_cents or 0
                trend_items.append({
                    "date": str(day.stat_date),
                    "total_queries": day.total_queries,
                    "success_queries": day.success_queries,
                    "error_queries": day.error_queries,
                    "success_rate": round(day.success_queries / day.total_queries * 100, 2) if day.total_queries else 0,
                    "total_tokens": day.total_tokens,
                    "avg_duration_ms": day.avg_duration_ms,
                    "cost_yuan": round(cost_yuan, 4),
                    "cost_version": day.cost_version
                })

            # ====== 新增扩展数据 ======

            # 1. 与历史同期对比数据 (comparison)
            comparison_data = self._get_comparison_data(user_id, total_24h, recent_stats)

            # 2. 24小时各时段查询分布 (hourly_distribution)
            hourly_distribution_data = self._get_hourly_distribution(user_id)

            # 3. 数据源使用统计 (datasource_stats)
            datasource_stats_data = self._get_datasource_stats(user_id)

            # 4. 查询状态详细分布 (status_breakdown)
            status_breakdown_data = self._get_status_breakdown(user_id, recent_stats)

            # 5. 查询质量指标 (quality_metrics)
            quality_metrics_data = self._get_quality_metrics(user_id)

            return resp(200, "success", {
                "recent_24h": {
                    "total_queries": total_24h,
                    "success_queries": success_24h,
                    "error_queries": recent_stats.error_queries or 0,
                    "timeout_queries": recent_stats.timeout_queries or 0,
                    "success_rate": round(success_24h / total_24h * 100, 2) if total_24h > 0 else 0,
                    "avg_duration_ms": int(recent_stats.avg_duration_ms) if recent_stats.avg_duration_ms else 0,
                    "total_tokens": recent_stats.total_tokens or 0,
                    "embedding_tokens": recent_stats.total_embedding_tokens or 0,
                    "rerank_tokens": recent_stats.total_rerank_tokens or 0,
                    "llm_tokens": recent_stats.total_llm_tokens or 0
                },
                "today": {
                    "total_queries": today_stats.total_queries or 0,
                    "success_queries": today_stats.success_queries or 0,
                    "total_tokens": today_stats.total_tokens or 0
                },
                "daily_trend": trend_items,
                "summary_30d": {
                    "total_queries": sum(d.total_queries for d in daily_trend) if daily_trend else 0,
                    "total_tokens": sum(d.total_tokens or 0 for d in daily_trend) if daily_trend else 0,
                    "total_cost_yuan": round(total_cost_cents / 100, 4)
                },
                "cost_note": "⚠️ 成本为预估值，仅供参考，实际费用以云厂商账单为准",
                # ====== 新增扩展字段 ======
                "comparison": comparison_data,
                "hourly_distribution": hourly_distribution_data,
                "datasource_stats": datasource_stats_data,
                "status_breakdown": status_breakdown_data,
                "quality_metrics": quality_metrics_data
            })

        except Exception as e:
            return resp(500, f"查询监控数据失败: {str(e)}", None, 500)

    def _get_comparison_data(self, user_id, total_24h, recent_stats):
        """获取与历史同期对比数据"""
        try:
            now = datetime.now(tz_cst)
            yesterday_same_time = now - timedelta(days=1)
            last_week_same_time = now - timedelta(days=7)

            # 昨日同期统计
            yesterday_stats = db.session.query(
                func.count(QueryLog.id).label('total_queries'),
                func.sum(QueryLog.total_tokens).label('total_tokens'),
                func.avg(QueryLog.total_duration_ms).label('avg_duration_ms')
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= yesterday_same_time - timedelta(hours=24),
                QueryLog.created_at < yesterday_same_time
            ).first()

            # 上周同期统计
            last_week_stats = db.session.query(
                func.count(QueryLog.id).label('total_queries'),
                func.sum(QueryLog.total_tokens).label('total_tokens'),
                func.avg(QueryLog.total_duration_ms).label('avg_duration_ms')
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= last_week_same_time - timedelta(hours=24),
                QueryLog.created_at < last_week_same_time
            ).first()

            def calc_change_rate(current, previous):
                """计算变化率
                - 如果 current = 0 且 previous = 0，返回 0（都为零，无增长）
                - 如果 current > 0 且 previous = 0，返回 None（分母为0，无法计算）
                - 否则正常计算变化率
                """
                if current == 0 and previous == 0:
                    return 0.0
                if previous == 0:
                    return None
                return round((current - previous) / previous * 100, 1)

            def format_rate(rate):
                """格式化变化率，None时返回N/A"""
                if rate is None:
                    return "N/A"
                return f"+{rate}%" if rate >= 0 else f"{rate}%"

            yesterday_queries = yesterday_stats.total_queries or 0
            last_week_queries = last_week_stats.total_queries or 0
            yesterday_tokens = yesterday_stats.total_tokens or 0
            last_week_tokens = last_week_stats.total_tokens or 0
            yesterday_duration = yesterday_stats.avg_duration_ms or 0
            last_week_duration = last_week_stats.avg_duration_ms or 0

            # 计算变化率
            queries_change_rate_y = calc_change_rate(total_24h, yesterday_queries)
            tokens_change_rate_y = calc_change_rate((recent_stats.total_tokens or 0), yesterday_tokens)
            duration_change_rate_y = calc_change_rate((recent_stats.avg_duration_ms or 0), yesterday_duration)

            queries_change_rate_lw = calc_change_rate(total_24h, last_week_queries)
            tokens_change_rate_lw = calc_change_rate((recent_stats.total_tokens or 0), last_week_tokens)
            duration_change_rate_lw = calc_change_rate((recent_stats.avg_duration_ms or 0), last_week_duration)

            return {
                "vs_yesterday": {
                    "queries_change": round(total_24h - yesterday_queries, 1),
                    "queries_change_rate": format_rate(queries_change_rate_y),
                    "tokens_change": round((recent_stats.total_tokens or 0) - yesterday_tokens, 1),
                    "tokens_change_rate": format_rate(tokens_change_rate_y),
                    "avg_duration_change": round((recent_stats.avg_duration_ms or 0) - yesterday_duration, 1),
                    "avg_duration_change_rate": format_rate(duration_change_rate_y),
                    "is_positive": total_24h >= yesterday_queries
                },
                "vs_last_week": {
                    "queries_change": round(total_24h - last_week_queries, 1),
                    "queries_change_rate": format_rate(queries_change_rate_lw),
                    "tokens_change": round((recent_stats.total_tokens or 0) - last_week_tokens, 1),
                    "tokens_change_rate": format_rate(tokens_change_rate_lw),
                    "avg_duration_change": round((recent_stats.avg_duration_ms or 0) - last_week_duration, 1),
                    "avg_duration_change_rate": format_rate(duration_change_rate_lw),
                    "is_positive": total_24h >= last_week_queries
                }
            }
        except Exception:
            return {"vs_yesterday": {}, "vs_last_week": {}}

    def _get_hourly_distribution(self, user_id):
        """获取24小时各时段查询分布"""
        try:
            now = datetime.now(tz_cst)
            yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

            hourly_stats = db.session.query(
                extract('hour', QueryLog.created_at).label('hour'),
                func.count(QueryLog.id).label('count')
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= yesterday_start
            ).group_by('hour').all()

            hourly_dict = {int(stat.hour): stat.count for stat in hourly_stats}
            total_hourly = sum(hourly_dict.values()) or 1

            distribution = []
            peak_hour = 0
            peak_count = 0
            off_peak_hour = 0
            off_peak_count = float('inf')

            for hour in range(24):
                count = hourly_dict.get(hour, 0)
                percentage = round(count / total_hourly * 100, 1) if total_hourly > 0 else 0
                distribution.append({
                    "hour": hour,
                    "label": f"{hour:02d}:00",
                    "queries": count,
                    "percentage": percentage
                })
                if count > peak_count:
                    peak_count = count
                    peak_hour = hour
                if count < off_peak_count:
                    off_peak_count = count
                    off_peak_hour = hour

            return {
                "peak_hour": peak_hour,
                "peak_hour_label": f"{peak_hour:02d}:00-{(peak_hour + 1) % 24:02d}:00",
                "off_peak_hour": off_peak_hour,
                "off_peak_hour_label": f"{off_peak_hour:02d}:00-{(off_peak_hour + 1) % 24:02d}:00",
                "distribution": distribution
            }
        except Exception:
            return {"peak_hour": 0, "peak_hour_label": "00:00-01:00", "off_peak_hour": 0, "off_peak_hour_label": "00:00-01:00", "distribution": []}

    def _get_datasource_stats(self, user_id):
        """获取数据源使用统计"""
        try:
            now = datetime.now(tz_cst)
            yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

            # 查询涉及的数据源统计
            datasource_stats = db.session.query(
                QueryLog.source_datasource_names,
                func.count(QueryLog.id).label('count'),
                func.avg(QueryLog.total_duration_ms).label('avg_duration')
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= yesterday_start,
                QueryLog.source_datasource_names.isnot(None)
            ).group_by('source_datasource_names').all()

            datasource_list = []
            total_datasource_queries = 0
            for stat in datasource_stats:
                names = stat.source_datasource_names
                if names and isinstance(names, list):
                    for name in names:
                        if name:
                            datasource_list.append({
                                "datasource_name": name,
                                "query_count": stat.count // len([n for n in names if n]),
                                "avg_duration_ms": int(stat.avg_duration) if stat.avg_duration else 0
                            })
                            total_datasource_queries += stat.count // len([n for n in names if n])

            # 合并同名数据源
            merged = defaultdict(lambda: {"query_count": 0, "avg_duration_ms": 0})
            for ds in datasource_list:
                merged[ds["datasource_name"]]["query_count"] += ds["query_count"]
                merged[ds["datasource_name"]]["avg_duration_ms"] = max(merged[ds["datasource_name"]]["avg_duration_ms"], ds["avg_duration_ms"])

            total = sum(d["query_count"] for d in merged.values()) or 1
            top_datasources = []
            for i, (name, data) in enumerate(sorted(merged.items(), key=lambda x: x[1]["query_count"], reverse=True)[:5]):
                top_datasources.append({
                    "datasource_name": name,
                    "query_count": data["query_count"],
                    "percentage": round(data["query_count"] / total * 100, 1),
                    "avg_duration_ms": data["avg_duration_ms"]
                })

            return {
                "total_datasources_used": len(merged),
                "top_datasources": top_datasources
            }
        except Exception:
            return {"total_datasources_used": 0, "top_datasources": []}

    def _get_status_breakdown(self, user_id, recent_stats):
        """获取查询状态详细分布"""
        try:
            now = datetime.now(tz_cst)
            yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

            total_queries = recent_stats.total_queries or 0

            # 获取错误类型分布
            error_stats = db.session.query(
                QueryLog.error_message,
                func.count(QueryLog.id).label('count')
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= yesterday_start,
                QueryLog.status == 'error',
                QueryLog.error_message.isnot(None)
            ).group_by('error_message').order_by(func.count(QueryLog.id).desc()).limit(3).all()

            top_errors = [stat.error_message[:20] + "..." if len(stat.error_message) > 20 else stat.error_message
                         for stat in error_stats if stat.error_message]

            success_count = recent_stats.success_queries or 0
            error_count = recent_stats.error_queries or 0
            timeout_count = recent_stats.timeout_queries or 0

            return {
                "success": {
                    "count": success_count,
                    "percentage": round(success_count / total_queries * 100, 1) if total_queries > 0 else 0,
                    "avg_duration_ms": int(recent_stats.avg_duration_ms) if recent_stats.avg_duration_ms else 0
                },
                "error": {
                    "count": error_count,
                    "percentage": round(error_count / total_queries * 100, 1) if total_queries > 0 else 0,
                    "avg_duration_ms": 0,
                    "top_errors": top_errors
                },
                "timeout": {
                    "count": timeout_count,
                    "percentage": round(timeout_count / total_queries * 100, 1) if total_queries > 0 else 0,
                    "avg_duration_ms": 30000
                }
            }
        except Exception:
            return {"success": {"count": 0, "percentage": 0, "avg_duration_ms": 0},
                    "error": {"count": 0, "percentage": 0, "avg_duration_ms": 0, "top_errors": []},
                    "timeout": {"count": 0, "percentage": 0, "avg_duration_ms": 0}}

    def _get_quality_metrics(self, user_id):
        """获取查询质量指标"""
        try:
            now = datetime.now(tz_cst)
            yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

            quality_stats = db.session.query(
                func.avg(QueryLog.cards_recalled).label('avg_cards_recalled'),
                func.avg(QueryLog.cards_selected).label('avg_cards_selected'),
                func.avg(QueryLog.top1_rerank_score).label('avg_top1_score'),
                func.avg(QueryLog.result_count).label('avg_result_count'),
                func.sum(case((QueryLog.result_count == 0, 1), else_=0)).label('zero_count'),
                func.count(QueryLog.id).label('total_count')
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= yesterday_start,
                QueryLog.status == 'success'
            ).first()

            total_count = quality_stats.total_count or 0
            zero_count = quality_stats.zero_count or 0

            return {
                "avg_cards_recalled": round(quality_stats.avg_cards_recalled, 1) if quality_stats.avg_cards_recalled else 0,
                "avg_cards_selected": round(quality_stats.avg_cards_selected, 1) if quality_stats.avg_cards_selected else 0,
                "avg_top1_score": round(quality_stats.avg_top1_score, 2) if quality_stats.avg_top1_score else 0,
                "avg_result_count": int(quality_stats.avg_result_count) if quality_stats.avg_result_count else 0,
                "zero_result_rate": round(zero_count / total_count * 100, 1) if total_count > 0 else 0
            }
        except Exception:
            return {
                "avg_cards_recalled": 0,
                "avg_cards_selected": 0,
                "avg_top1_score": 0,
                "avg_result_count": 0,
                "zero_result_rate": 0
            }


class MonitoringTrendResource(Resource):
    """
    监控趋势数据接口
    GET /console/api/monitoring/trend
    """

    def get(self):
        """
        查询监控趋势数据

        Query参数:
            - user_id: 用户ID（UUID），必填
            - days: 天数，默认30，最大365
        """
        try:
            user_id = request.args.get('user_id', '')
            days = int(request.args.get('days', 30))

            if not user_id:
                return resp(400, "user_id 不能为空", None, 400)

            if not _is_uuid(user_id):
                return resp(400, "user_id 格式错误，必须为 UUID", None, 400)

            # 验证 user_id 是否存在于数据库中
            user_exists = db.session.query(User.id).filter(User.id == user_id).first()
            if not user_exists:
                return resp(404, "用户不存在", None, 404)

            if days < 1 or days > 365:
                days = 30

            # 查询趋势数据
            daily_data = QueryStatsDaily.query.filter(
                QueryStatsDaily.user_id == user_id,
                QueryStatsDaily.stat_date >= date.today() - timedelta(days=days)
            ).order_by(QueryStatsDaily.stat_date.asc()).all()

            items = []
            total_queries = 0
            total_tokens = 0
            total_cost_cents = 0
            total_success_rate = 0
            data_days = 0

            for day in daily_data:
                total_queries += day.total_queries
                total_tokens += day.total_tokens or 0
                total_cost_cents += day.estimated_cost_cents or 0
                if day.total_queries > 0:
                    total_success_rate += day.success_queries / day.total_queries * 100
                    data_days += 1
                items.append({
                    "date": str(day.stat_date),
                    "total_queries": day.total_queries,
                    "success_queries": day.success_queries,
                    "error_queries": day.error_queries,
                    "timeout_queries": day.timeout_queries,
                    "success_rate": round(day.success_queries / day.total_queries * 100, 2) if day.total_queries else 0,
                    "tokens": {
                        "embedding": day.total_embedding_tokens or 0,
                        "rerank": day.total_rerank_tokens or 0,
                        "llm": day.total_llm_tokens or 0,
                        "total": day.total_tokens or 0
                    },
                    "cost_yuan": round((day.estimated_cost_cents or 0) / 100, 4),
                    "cost_version": day.cost_version,
                    "performance": {
                        "avg_duration_ms": day.avg_duration_ms,
                        "min_duration_ms": day.min_duration_ms,
                        "max_duration_ms": day.max_duration_ms,
                        "avg_vector_search_ms": day.avg_vector_search_ms,
                        "avg_rerank_ms": day.avg_rerank_ms,
                        "avg_llm_gen_sql_ms": day.avg_llm_gen_sql_ms,
                        "avg_sql_execution_ms": day.avg_sql_execution_ms
                    },
                    "quality": {
                        "avg_cards_recalled": day.avg_cards_recalled,
                        "avg_cards_selected": day.avg_cards_selected,
                        "avg_top1_rerank_score": day.avg_top1_rerank_score
                    }
                })

            # ====== 新增扩展数据 ======

            # 1. 统计汇总 (statistics)
            statistics_data = self._get_statistics(user_id, days, items, total_queries, total_tokens, total_cost_cents, total_success_rate, data_days)

            # 2. 增长分析 (growth_analysis)
            growth_analysis_data = self._get_growth_analysis(user_id, days, daily_data)

            # 3. 峰值谷值分析 (peak_valley)
            peak_valley_data = self._get_peak_valley(items, user_id)

            # 4. 周规律分析 (weekly_pattern)
            weekly_pattern_data = self._get_weekly_pattern(items)

            return resp(200, "success", {
                "days": days,
                "items": items,
                # ====== 新增扩展字段 ======
                "statistics": statistics_data,
                "growth_analysis": growth_analysis_data,
                "peak_valley": peak_valley_data,
                "weekly_pattern": weekly_pattern_data
            })

        except Exception as e:
            return resp(500, f"查询趋势数据失败: {str(e)}", None, 500)

    def _get_statistics(self, user_id, days, items, total_queries, total_tokens, total_cost_cents, total_success_rate, data_days):
        """获取统计汇总数据"""
        try:
            missing_days = days - data_days
            avg_daily_queries = round(total_queries / data_days) if data_days > 0 else 0
            avg_daily_tokens = round(total_tokens / data_days) if data_days > 0 else 0
            avg_success_rate = round(total_success_rate / data_days, 1) if data_days > 0 else 0

            return {
                "total_days": days,
                "data_days": data_days,
                "missing_days": missing_days,
                "total_queries": total_queries,
                "total_tokens": total_tokens,
                "total_cost_yuan": round(total_cost_cents / 100, 2),
                "avg_daily_queries": avg_daily_queries,
                "avg_daily_tokens": avg_daily_tokens,
                "avg_success_rate": avg_success_rate
            }
        except Exception:
            return {
                "total_days": days,
                "data_days": 0,
                "missing_days": days,
                "total_queries": 0,
                "total_tokens": 0,
                "total_cost_yuan": 0,
                "avg_daily_queries": 0,
                "avg_daily_tokens": 0,
                "avg_success_rate": 0
            }

    def _get_growth_analysis(self, user_id, days, daily_data):
        """获取增长分析数据"""
        try:
            now = datetime.now(tz_cst)

            # 计算周环比 (当前7天 vs 上一个7天)
            # 获取当前7天数据
            current_7d_start = date.today() - timedelta(days=7)
            current_7d_data = [d for d in daily_data if d.stat_date >= current_7d_start]
            current_7d_queries = sum(d.total_queries for d in current_7d_data)
            current_7d_tokens = sum(d.total_tokens or 0 for d in current_7d_data)
            current_7d_cost = sum(d.estimated_cost_cents or 0 for d in current_7d_data)

            # 获取上一个7天数据
            prev_7d_start = date.today() - timedelta(days=14)
            prev_7d_end = date.today() - timedelta(days=7)
            prev_7d_data = [d for d in daily_data if prev_7d_start <= d.stat_date < prev_7d_end]
            prev_7d_queries = sum(d.total_queries for d in prev_7d_data)
            prev_7d_tokens = sum(d.total_tokens or 0 for d in prev_7d_data)
            prev_7d_cost = sum(d.estimated_cost_cents or 0 for d in prev_7d_data)

            # 计算月环比 (当前30天 vs 上一个30天)
            # 获取上一个30天数据
            prev_30d_start = date.today() - timedelta(days=days * 2)
            prev_30d_end = date.today() - timedelta(days=days)
            prev_30d_data = [d for d in daily_data if prev_30d_start <= d.stat_date < prev_30d_end]
            prev_30d_queries = sum(d.total_queries for d in prev_30d_data)
            prev_30d_tokens = sum(d.total_tokens or 0 for d in prev_30d_data)
            prev_30d_cost = sum(d.estimated_cost_cents or 0 for d in prev_30d_data)

            # 当前周期数据
            curr_queries = sum(d.total_queries for d in daily_data)
            curr_tokens = sum(d.total_tokens or 0 for d in daily_data)
            curr_cost = sum(d.estimated_cost_cents or 0 for d in daily_data)

            def calc_growth_rate(current, previous):
                """计算增长率
                - 如果 current = 0 且 previous = 0，返回 0（都为零，无增长）
                - 如果 current > 0 且 previous = 0，返回 None（分母为0，无法计算）
                - 否则正常计算变化率
                """
                if current == 0 and previous == 0:
                    return 0.0
                if previous == 0:
                    return None
                return round((current - previous) / previous * 100, 1)

            def format_rate(rate):
                """格式化变化率，None时返回N/A"""
                if rate is None:
                    return "N/A"
                return f"+{rate}%" if rate >= 0 else f"{rate}%"

            def get_trend(rate):
                """判断趋势，None时返回stable"""
                if rate is None:
                    return "stable"
                if rate > 5:
                    return "growth"
                elif rate < -5:
                    return "decline"
                return "stable"

            week_growth_queries = calc_growth_rate(current_7d_queries, prev_7d_queries)
            week_growth_tokens = calc_growth_rate(current_7d_tokens, prev_7d_tokens)
            week_growth_cost = calc_growth_rate(current_7d_cost, prev_7d_cost)

            month_growth_queries = calc_growth_rate(curr_queries, prev_30d_queries)
            month_growth_tokens = calc_growth_rate(curr_tokens, prev_30d_tokens)
            month_growth_cost = calc_growth_rate(curr_cost, prev_30d_cost)

            return {
                "week_over_week": {
                    "queries_change": current_7d_queries - prev_7d_queries,
                    "queries_change_rate": format_rate(week_growth_queries),
                    "tokens_change": current_7d_tokens - prev_7d_tokens,
                    "tokens_change_rate": format_rate(week_growth_tokens),
                    "cost_change": round((current_7d_cost - prev_7d_cost) / 100, 2),
                    "cost_change_rate": format_rate(week_growth_cost),
                    "trend": get_trend(week_growth_queries)
                },
                "month_over_month": {
                    "queries_change": curr_queries - prev_30d_queries,
                    "queries_change_rate": format_rate(month_growth_queries),
                    "tokens_change": curr_tokens - prev_30d_tokens,
                    "tokens_change_rate": format_rate(month_growth_tokens),
                    "cost_change": round((curr_cost - prev_30d_cost) / 100, 2),
                    "cost_change_rate": format_rate(month_growth_cost),
                    "trend": get_trend(month_growth_queries)
                }
            }
        except Exception:
            return {
                "week_over_week": {
                    "queries_change": 0, "queries_change_rate": "N/A",
                    "tokens_change": 0, "tokens_change_rate": "N/A",
                    "cost_change": 0, "cost_change_rate": "N/A",
                    "trend": "stable"
                },
                "month_over_month": {
                    "queries_change": 0, "queries_change_rate": "N/A",
                    "tokens_change": 0, "tokens_change_rate": "N/A",
                    "cost_change": 0, "cost_change_rate": "N/A",
                    "trend": "stable"
                }
            }

    def _get_peak_valley(self, items, user_id):
        """获取峰值谷值分析"""
        try:
            if not items:
                return {"peak_day": None, "valley_day": None, "peak_hours": []}

            # 找出峰值和谷值日期
            peak_day = max(items, key=lambda x: x["total_queries"]) if items else None
            valley_day = min(items, key=lambda x: x["total_queries"]) if items else None

            peak_reason = "工作高峰" if peak_day and date.today().weekday() in [0, 1, 2, 3, 4] else "周末高峰"
            valley_reason = "周末最低" if valley_day and date.today().weekday() in [5, 6] else "活动较少"

            # 获取高峰时段分析 (基于最近24小时)
            peak_hours = []
            try:
                now = datetime.now(tz_cst)
                hourly_stats = db.session.query(
                    extract('hour', QueryLog.created_at).label('hour'),
                    func.count(QueryLog.id).label('query_count'),
                    func.avg(QueryLog.total_duration_ms).label('avg_duration_ms')
                ).filter(
                    QueryLog.user_id == user_id,
                    QueryLog.created_at >= now - timedelta(hours=24)
                ).group_by('hour').order_by(func.count(QueryLog.id).desc()).limit(3).all()

                for stat in hourly_stats:
                    hour = int(stat.hour)
                    peak_hours.append({
                        "hour": hour,
                        "label": f"{hour:02d}:00-{(hour + 1) % 24:02d}:00",
                        "query_count": stat.query_count or 0,
                        "avg_duration_ms": int(stat.avg_duration_ms) if stat.avg_duration_ms else 0
                    })
            except Exception:
                pass

            return {
                "peak_day": {
                    "date": peak_day["date"] if peak_day else None,
                    "queries": peak_day["total_queries"] if peak_day else 0,
                    "reason": peak_reason
                },
                "valley_day": {
                    "date": valley_day["date"] if valley_day else None,
                    "queries": valley_day["total_queries"] if valley_day else 0,
                    "reason": valley_reason
                },
                "peak_hours": peak_hours
            }
        except Exception:
            return {"peak_day": None, "valley_day": None, "peak_hours": []}

    def _get_weekly_pattern(self, items):
        """获取周规律分析"""
        try:
            if not items:
                return {"pattern": [], "workday_avg": 0, "weekend_avg": 0, "workday_ratio": 0}

            # 按星期几分组
            weekday_totals = defaultdict(lambda: {"total": 0, "count": 0})
            weekday_labels = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]

            for item in items:
                try:
                    item_date = datetime.strptime(item["date"], "%Y-%m-%d")
                    weekday = item_date.weekday()
                    weekday_totals[weekday]["total"] += item["total_queries"]
                    weekday_totals[weekday]["count"] += 1
                except Exception:
                    continue

            pattern = []
            workday_totals = []
            weekend_totals = []

            for weekday in range(7):
                data = weekday_totals[weekday]
                avg_queries = round(data["total"] / data["count"]) if data["count"] > 0 else 0
                is_workday = weekday in [0, 1, 2, 3, 4]

                pattern.append({
                    "weekday": weekday,
                    "label": weekday_labels[weekday],
                    "avg_queries": avg_queries,
                    "is_workday": is_workday
                })

                if is_workday:
                    workday_totals.append(avg_queries)
                else:
                    weekend_totals.append(avg_queries)

            workday_avg = round(sum(workday_totals) / len(workday_totals)) if workday_totals else 0
            weekend_avg = round(sum(weekend_totals) / len(weekend_totals)) if weekend_totals else 0
            total_avg = workday_avg + weekend_avg
            workday_ratio = round(workday_avg / total_avg, 2) if total_avg > 0 else 0

            return {
                "pattern": pattern,
                "workday_avg": workday_avg,
                "weekend_avg": weekend_avg,
                "workday_ratio": workday_ratio
            }
        except Exception:
            return {"pattern": [], "workday_avg": 0, "weekend_avg": 0, "workday_ratio": 0}


class MonitoringRealtimeResource(Resource):
    """
    实时监控接口
    GET /console/api/monitoring/realtime
    """

    def get(self):
        """
        查询实时监控数据（最近1小时）

        Query参数:
            - user_id: 用户ID（UUID），必填
        """
        try:
            user_id = request.args.get('user_id', '')

            if not user_id:
                return resp(400, "user_id 不能为空", None, 400)

            if not _is_uuid(user_id):
                return resp(400, "user_id 格式错误，必须为 UUID", None, 400)

            # 验证 user_id 是否存在于数据库中
            user_exists = db.session.query(User.id).filter(User.id == user_id).first()
            if not user_exists:
                return resp(404, "用户不存在", None, 404)

            # 最近1小时数据
            one_hour_ago = datetime.now(tz_cst) - timedelta(hours=1)

            # 每分钟统计
            stats = db.session.query(
                func.date_trunc('minute', QueryLog.created_at).label('minute'),
                func.count(QueryLog.id).label('count'),
                func.avg(QueryLog.total_duration_ms).label('avg_duration')
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= one_hour_ago
            ).group_by(
                func.date_trunc('minute', QueryLog.created_at)
            ).order_by('minute').all()

            minute_items = []
            for stat in stats:
                minute_items.append({
                    "time": stat.minute.strftime('%H:%M') if stat.minute else "",
                    "count": stat.count,
                    "avg_duration_ms": int(stat.avg_duration) if stat.avg_duration else 0
                })

            # 最近1小时汇总
            summary = db.session.query(
                func.count(QueryLog.id).label('total'),
                func.avg(QueryLog.total_duration_ms).label('avg_duration'),
                func.sum(QueryLog.total_tokens).label('total_tokens')
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= one_hour_ago
            ).first()

            # ====== 新增扩展数据 ======

            # 1. 当前系统状态 (current_status)
            current_status_data = self._get_current_status(user_id, one_hour_ago, summary)

            # 2. QPS统计 (qps_stats)
            qps_stats_data = self._get_qps_stats(user_id, one_hour_ago)

            # 3. 错误告警 (error_alerts)
            error_alerts_data = self._get_error_alerts(user_id, one_hour_ago)

            # 4. 最近查询样例 (recent_queries)
            recent_queries_data = self._get_recent_queries(user_id, one_hour_ago)

            # 5. 数据源健康状态 (datasource_health)
            datasource_health_data = self._get_datasource_health(user_id, one_hour_ago)

            return resp(200, "success", {
                "summary": {
                    "total_queries": summary.total or 0,
                    "avg_duration_ms": int(summary.avg_duration) if summary.avg_duration else 0,
                    "total_tokens": summary.total_tokens or 0
                },
                "minute_data": minute_items,
                # ====== 新增扩展字段 ======
                "current_status": current_status_data,
                "qps_stats": qps_stats_data,
                "error_alerts": error_alerts_data,
                "recent_queries": recent_queries_data,
                "datasource_health": datasource_health_data
            })

        except Exception as e:
            return resp(500, f"查询实时数据失败: {str(e)}", None, 500)

    def _get_current_status(self, user_id, one_hour_ago, summary):
        """获取当前系统状态"""
        try:
            # 获取最新一条记录
            latest_query = QueryLog.query.filter(
                QueryLog.user_id == user_id
            ).order_by(QueryLog.created_at.desc()).first()

            # 获取连续成功/失败数
            consecutive_stats = db.session.query(
                func.count(QueryLog.id).label('consecutive_success')
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.status == 'success',
                QueryLog.created_at >= datetime.now(tz_cst) - timedelta(hours=1)
            ).scalar() or 0

            consecutive_errors = db.session.query(
                func.count(QueryLog.id).label('consecutive_errors')
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.status == 'error',
                QueryLog.created_at >= datetime.now(tz_cst) - timedelta(hours=1)
            ).scalar() or 0

            total_queries = summary.total or 0
            error_count = db.session.query(
                func.count(QueryLog.id)
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= one_hour_ago,
                QueryLog.status.in_(['error', 'timeout'])
            ).scalar() or 0

            error_rate = (error_count / total_queries * 100) if total_queries > 0 else 0
            success_rate = 100 - error_rate

            # 判断状态
            if success_rate >= 95 and error_rate < 5:
                overall = "healthy"
                status_text = "运行正常"
                status_color = "#52c41a"
            elif success_rate >= 85:
                overall = "warning"
                status_text = "轻微异常"
                status_color = "#faad14"
            else:
                overall = "critical"
                status_text = "需要关注"
                status_color = "#ff4d4f"

            return {
                "overall": overall,
                "status_text": status_text,
                "status_color": status_color,
                "uptime_seconds": 3600,
                "last_query_time": latest_query.created_at.isoformat() if latest_query and latest_query.created_at else None,
                "consecutive_success": consecutive_stats,
                "consecutive_errors": consecutive_errors
            }
        except Exception:
            return {
                "overall": "unknown",
                "status_text": "状态未知",
                "status_color": "#d9d9d9",
                "uptime_seconds": 0,
                "last_query_time": None,
                "consecutive_success": 0,
                "consecutive_errors": 0
            }

    def _get_qps_stats(self, user_id, one_hour_ago):
        """获取QPS统计"""
        try:
            now = datetime.now(tz_cst)

            # 当前QPS (最近5分钟)
            five_min_ago = now - timedelta(minutes=5)
            count_5m = db.session.query(
                func.count(QueryLog.id)
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= five_min_ago
            ).scalar() or 0

            # 15分钟QPS
            fifteen_min_ago = now - timedelta(minutes=15)
            count_15m = db.session.query(
                func.count(QueryLog.id)
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= fifteen_min_ago
            ).scalar() or 0

            # 获取每分钟统计数据计算最大最小值
            minute_stats = db.session.query(
                func.count(QueryLog.id).label('count')
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= one_hour_ago
            ).group_by(
                func.date_trunc('minute', QueryLog.created_at)
            ).all()

            counts = [s.count for s in minute_stats] if minute_stats else [0]
            current_qps = round(counts[-1] / 60, 2) if counts else 0.0
            avg_qps_1m = round(count_5m / 300, 2) if count_5m else 0.0
            avg_qps_5m = avg_qps_1m
            avg_qps_15m = round(count_15m / 900, 2) if count_15m else 0.0
            max_qps = round(max(counts) / 60, 2) if counts else 0.0
            min_qps = round(min(counts) / 60, 2) if counts else 0.0

            return {
                "current_qps": current_qps,
                "avg_qps_1m": avg_qps_1m,
                "avg_qps_5m": avg_qps_5m,
                "avg_qps_15m": avg_qps_15m,
                "max_qps": max_qps,
                "min_qps": min_qps
            }
        except Exception:
            return {
                "current_qps": 0,
                "avg_qps_1m": 0,
                "avg_qps_5m": 0,
                "avg_qps_15m": 0,
                "max_qps": 0,
                "min_qps": 0
            }

    def _get_error_alerts(self, user_id, one_hour_ago):
        """获取错误告警"""
        try:
            # 最近1小时错误统计
            total_errors = db.session.query(
                func.count(QueryLog.id)
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= one_hour_ago,
                QueryLog.status == 'error'
            ).scalar() or 0

            total_timeout = db.session.query(
                func.count(QueryLog.id)
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= one_hour_ago,
                QueryLog.status == 'timeout'
            ).scalar() or 0

            total_queries = db.session.query(
                func.count(QueryLog.id)
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= one_hour_ago
            ).scalar() or 0

            error_rate = round(total_errors / total_queries * 100, 1) if total_queries > 0 else 0
            timeout_rate = round(total_timeout / total_queries * 100, 1) if total_queries > 0 else 0

            # 获取最近错误样例
            error_samples = QueryLog.query.filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= one_hour_ago,
                QueryLog.status.in_(['error', 'timeout'])
            ).order_by(QueryLog.created_at.desc()).limit(5).all()

            recent_errors = []
            for err in error_samples:
                recent_errors.append({
                    "time": err.created_at.strftime('%H:%M:%S') if err.created_at else "",
                    "type": err.status,
                    "datasource": err.source_datasource_names[0] if err.source_datasource_names and len(err.source_datasource_names) > 0 else "未知",
                    "message": (err.error_message[:30] + "..." if err.error_message and len(err.error_message) > 30 else err.error_message) if err.error_message else err.status,
                    "count": 1
                })

            # 获取错误类型分布
            error_types = db.session.query(
                QueryLog.status,
                QueryLog.error_message,
                func.count(QueryLog.id).label('count')
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= one_hour_ago,
                QueryLog.status.in_(['error', 'timeout'])
            ).group_by('status', 'error_message').order_by(func.count(QueryLog.id).desc()).limit(5).all()

            total_error_count = sum(e.count for e in error_types) or 1
            top_error_types = []
            for et in error_types:
                error_type = et.status if et.status != 'timeout' else 'connection_timeout'
                top_error_types.append({
                    "type": error_type,
                    "count": et.count,
                    "percentage": round(et.count / total_error_count * 100, 1)
                })

            return {
                "total_errors_1h": total_errors + total_timeout,
                "error_rate": error_rate,
                "timeout_rate": timeout_rate,
                "recent_errors": recent_errors,
                "top_error_types": top_error_types
            }
        except Exception:
            return {
                "total_errors_1h": 0,
                "error_rate": 0,
                "timeout_rate": 0,
                "recent_errors": [],
                "top_error_types": []
            }

    def _get_recent_queries(self, user_id, one_hour_ago):
        """获取最近查询样例"""
        try:
            # 成功的查询样例
            success_samples = QueryLog.query.filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= one_hour_ago,
                QueryLog.status == 'success'
            ).order_by(QueryLog.created_at.desc()).limit(5).all()

            success_list = []
            for q in success_samples:
                success_list.append({
                    "id": str(q.id),
                    "question": q.question[:50] + "..." if q.question and len(q.question) > 50 else q.question,
                    "duration_ms": q.total_duration_ms,
                    "tokens": q.total_tokens,
                    "datasources": q.source_datasource_names if q.source_datasource_names else [],
                    "status": "success",
                    "time": q.created_at.strftime('%H:%M:%S') if q.created_at else ""
                })

            # 失败的查询样例
            error_samples = QueryLog.query.filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= one_hour_ago,
                QueryLog.status.in_(['error', 'timeout'])
            ).order_by(QueryLog.created_at.desc()).limit(3).all()

            error_list = []
            for q in error_samples:
                error_list.append({
                    "id": str(q.id),
                    "question": q.question[:50] + "..." if q.question and len(q.question) > 50 else q.question,
                    "duration_ms": q.total_duration_ms,
                    "error_type": q.status,
                    "error_message": q.error_message[:30] + "..." if q.error_message and len(q.error_message) > 30 else q.error_message,
                    "datasources": q.source_datasource_names if q.source_datasource_names else [],
                    "time": q.created_at.strftime('%H:%M:%S') if q.created_at else ""
                })

            return {
                "success_samples": success_list,
                "error_samples": error_list
            }
        except Exception:
            return {"success_samples": [], "error_samples": []}

    def _get_datasource_health(self, user_id, one_hour_ago):
        """获取数据源健康状态"""
        try:
            # 获取各数据源统计
            ds_stats = db.session.query(
                QueryLog.source_datasource_names,
                func.count(QueryLog.id).label('count'),
                func.avg(QueryLog.total_duration_ms).label('avg_duration'),
                func.sum(case((QueryLog.status == 'error', 1), else_=0)).label('error_count'),
                func.sum(case((QueryLog.status == 'timeout', 1), else_=0)).label('timeout_count')
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= one_hour_ago,
                QueryLog.source_datasource_names.isnot(None)
            ).group_by('source_datasource_names').all()

            datasources = []
            for stat in ds_stats:
                names = stat.source_datasource_names
                if names and isinstance(names, list):
                    for name in names:
                        if name:
                            total_count = stat.count or 0
                            error_count = (stat.error_count or 0) + (stat.timeout_count or 0)
                            error_rate = round(error_count / total_count * 100, 2) if total_count > 0 else 0
                            avg_duration = int(stat.avg_duration) if stat.avg_duration else 0

                            # 判断数据源状态
                            if error_rate < 1 and avg_duration < 2000:
                                status = "healthy"
                                reason = ""
                            elif error_rate < 5:
                                status = "degraded"
                                reason = "错误率略高" if error_rate >= 1 else "响应时间较长"
                            else:
                                status = "critical"
                                reason = "错误率过高" if error_rate >= 5 else "响应超时严重"

                            datasources.append({
                                "name": name,
                                "status": status,
                                "queries_1h": total_count,
                                "avg_latency_ms": avg_duration,
                                "error_count": error_count,
                                "error_rate": error_rate,
                                "reason": reason
                            })

            # 合并同名数据源
            merged = {}
            for ds in datasources:
                name = ds["name"]
                if name not in merged:
                    merged[name] = ds
                else:
                    merged[name]["queries_1h"] += ds["queries_1h"]
                    merged[name]["error_count"] += ds["error_count"]

            # 重新计算错误率
            for name, ds in merged.items():
                ds["error_rate"] = round(ds["error_count"] / ds["queries_1h"] * 100, 2) if ds["queries_1h"] > 0 else 0

            return {
                "datasources": list(merged.values())[:10]
            }
        except Exception:
            return {"datasources": []}


class MonitoringPerformanceResource(Resource):
    """
    性能分析接口
    GET /console/api/monitoring/performance
    """

    def get(self):
        """
        查询性能分析数据

        Query参数:
            - user_id: 用户ID（UUID），必填
            - days: 天数，默认7
        """
        try:
            user_id = request.args.get('user_id', '')
            days = int(request.args.get('days', 7))

            if not user_id:
                return resp(400, "user_id 不能为空", None, 400)

            if not _is_uuid(user_id):
                return resp(400, "user_id 格式错误，必须为 UUID", None, 400)

            # 验证 user_id 是否存在于数据库中
            user_exists = db.session.query(User.id).filter(User.id == user_id).first()
            if not user_exists:
                return resp(404, "用户不存在", None, 404)

            if days < 1 or days > 30:
                days = 7

            # 查询性能数据
            stats = QueryStatsDaily.query.filter(
                QueryStatsDaily.user_id == user_id,
                QueryStatsDaily.stat_date >= date.today() - timedelta(days=days)
            ).order_by(QueryStatsDaily.stat_date.desc()).all()

            # 计算各环节平均耗时
            total_days = len(stats)
            avg_vector_search = sum(s.avg_vector_search_ms or 0 for s in stats) / total_days if total_days > 0 else 0
            avg_rerank = sum(s.avg_rerank_ms or 0 for s in stats) / total_days if total_days > 0 else 0
            avg_llm = sum(s.avg_llm_gen_sql_ms or 0 for s in stats) / total_days if total_days > 0 else 0
            avg_sql = sum(s.avg_sql_execution_ms or 0 for s in stats) / total_days if total_days > 0 else 0
            avg_total = avg_vector_search + avg_rerank + avg_llm + avg_sql

            # 查询慢查询TOP N
            slow_queries = QueryLog.query.filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= datetime.now(tz_cst) - timedelta(days=days),
                QueryLog.status == 'success'
            ).order_by(
                QueryLog.total_duration_ms.desc()
            ).limit(10).all()

            slow_query_items = []
            for q in slow_queries:
                slow_query_items.append({
                    "id": str(q.id),
                    "question": q.question[:50] + "..." if len(q.question) > 50 else q.question,
                    "duration_ms": q.total_duration_ms,
                    "tokens": q.total_tokens,
                    "created_at": q.created_at.isoformat() if q.created_at else None
                })

            # ====== 新增扩展数据 ======

            # 1. 延迟时间分布 (latency_distribution)
            latency_distribution_data = self._get_latency_distribution(user_id, days)

            # 2. 各环节耗时占比 (stage_breakdown)
            stage_breakdown_data = self._get_stage_breakdown(avg_vector_search, avg_rerank, avg_llm, avg_sql, avg_total, stats)

            # 3. 数据源性能对比 (datasource_performance)
            datasource_performance_data = self._get_datasource_performance(user_id, days)

            # 4. 性能趋势对比 (performance_trend)
            performance_trend_data = self._get_performance_trend(user_id, days, stats, avg_total)

            # 5. 查询模式分析 (query_patterns)
            query_patterns_data = self._get_query_patterns(user_id, days)

            return resp(200, "success", {
                "period_days": days,
                "stage_averages": {
                    "vector_search_ms": int(avg_vector_search),
                    "rerank_ms": int(avg_rerank),
                    "llm_gen_sql_ms": int(avg_llm),
                    "sql_execution_ms": int(avg_sql),
                    "total_avg_ms": int(avg_total)
                },
                "slow_queries_top10": slow_query_items,
                # ====== 新增扩展字段 ======
                "latency_distribution": latency_distribution_data,
                "stage_breakdown": stage_breakdown_data,
                "datasource_performance": datasource_performance_data,
                "performance_trend": performance_trend_data,
                "query_patterns": query_patterns_data
            })

        except Exception as e:
            return resp(500, f"查询性能数据失败: {str(e)}", None, 500)

    def _get_latency_distribution(self, user_id, days):
        """获取延迟时间分布"""
        try:
            now = datetime.now(tz_cst)
            start_date = now - timedelta(days=days)

            # 查询各时间段分布
            distribution = [
                {"range": "0-500ms", "count": 0, "percentage": 0},
                {"range": "500ms-1s", "count": 0, "percentage": 0},
                {"range": "1s-2s", "count": 0, "percentage": 0},
                {"range": "2s-5s", "count": 0, "percentage": 0},
                {"range": "5s-10s", "count": 0, "percentage": 0},
                {"range": ">10s", "count": 0, "percentage": 0}
            ]

            # 0-500ms
            count_0_500 = QueryLog.query.filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= start_date,
                QueryLog.total_duration_ms < 500
            ).count()

            # 500ms-1s
            count_500_1s = QueryLog.query.filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= start_date,
                QueryLog.total_duration_ms >= 500,
                QueryLog.total_duration_ms < 1000
            ).count()

            # 1s-2s
            count_1_2s = QueryLog.query.filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= start_date,
                QueryLog.total_duration_ms >= 1000,
                QueryLog.total_duration_ms < 2000
            ).count()

            # 2s-5s
            count_2_5s = QueryLog.query.filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= start_date,
                QueryLog.total_duration_ms >= 2000,
                QueryLog.total_duration_ms < 5000
            ).count()

            # 5s-10s
            count_5_10s = QueryLog.query.filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= start_date,
                QueryLog.total_duration_ms >= 5000,
                QueryLog.total_duration_ms < 10000
            ).count()

            # >10s
            count_over_10s = QueryLog.query.filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= start_date,
                QueryLog.total_duration_ms >= 10000
            ).count()

            counts = [count_0_500, count_500_1s, count_1_2s, count_2_5s, count_5_10s, count_over_10s]
            total = sum(counts) or 1

            for i, count in enumerate(counts):
                distribution[i]["count"] = count
                distribution[i]["percentage"] = round(count / total * 100, 1)

            return {
                "distribution": distribution
            }
        except Exception:
            return {"distribution": []}

    def _get_stage_breakdown(self, avg_vector_search, avg_rerank, avg_llm, avg_sql, avg_total, stats):
        """获取各环节耗时占比"""
        try:
            if avg_total == 0:
                return {"total_avg_ms": 0, "stages": []}

            def get_trend(stage_data, current_value):
                """计算趋势变化，当数据不足时返回N/A"""
                if not stage_data or len(stage_data) < 2:
                    return "stable", "N/A"
                prev_avg = sum(s for s in stage_data[:-1]) / len(stage_data[:-1]) if len(stage_data[:-1]) > 0 else current_value
                if prev_avg == 0:
                    return "stable", "N/A"
                change = ((current_value - prev_avg) / prev_avg) * 100
                trend = "increasing" if change > 2 else ("decreasing" if change < -2 else "stable")
                return trend, f"+{round(change, 1)}%" if change >= 0 else f"{round(change, 1)}%"

            # 获取历史数据计算趋势
            vector_search_history = [s.avg_vector_search_ms or 0 for s in stats]
            rerank_history = [s.avg_rerank_ms or 0 for s in stats]
            llm_history = [s.avg_llm_gen_sql_ms or 0 for s in stats]
            sql_history = [s.avg_sql_execution_ms or 0 for s in stats]

            vs_trend, vs_rate = get_trend(vector_search_history, avg_vector_search)
            rr_trend, rr_rate = get_trend(rerank_history, avg_rerank)
            llm_trend, llm_rate = get_trend(llm_history, avg_llm)
            sql_trend, sql_rate = get_trend(sql_history, avg_sql)

            return {
                "total_avg_ms": int(avg_total),
                "stages": [
                    {
                        "name": "vector_search",
                        "label": "向量检索",
                        "avg_ms": int(avg_vector_search),
                        "percentage": round(avg_vector_search / avg_total * 100, 1),
                        "trend": vs_trend,
                        "trend_rate": vs_rate
                    },
                    {
                        "name": "rerank",
                        "label": "重排序",
                        "avg_ms": int(avg_rerank),
                        "percentage": round(avg_rerank / avg_total * 100, 1),
                        "trend": rr_trend,
                        "trend_rate": rr_rate
                    },
                    {
                        "name": "llm_gen_sql",
                        "label": "LLM生成SQL",
                        "avg_ms": int(avg_llm),
                        "percentage": round(avg_llm / avg_total * 100, 1),
                        "trend": llm_trend,
                        "trend_rate": llm_rate
                    },
                    {
                        "name": "sql_execution",
                        "label": "SQL执行",
                        "avg_ms": int(avg_sql),
                        "percentage": round(avg_sql / avg_total * 100, 1),
                        "trend": sql_trend,
                        "trend_rate": sql_rate
                    }
                ]
            }
        except Exception:
            return {"total_avg_ms": 0, "stages": []}

    def _get_datasource_performance(self, user_id, days):
        """获取数据源性能对比"""
        try:
            now = datetime.now(tz_cst)
            start_date = now - timedelta(days=days)

            ds_stats = db.session.query(
                QueryLog.source_datasource_names,
                func.count(QueryLog.id).label('count'),
                func.avg(QueryLog.total_duration_ms).label('avg_duration'),
                func.min(QueryLog.total_duration_ms).label('min_duration'),
                func.max(QueryLog.total_duration_ms).label('max_duration'),
                func.avg(QueryLog.sql_execution_ms).label('avg_sql_execution')
            ).filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= start_date,
                QueryLog.status == 'success',
                QueryLog.source_datasource_names.isnot(None)
            ).group_by('source_datasource_names').order_by(func.count(QueryLog.id).desc()).all()

            datasources = []
            for i, stat in enumerate(ds_stats[:10]):
                names = stat.source_datasource_names
                if names and isinstance(names, list) and names[0]:
                    datasources.append({
                        "name": names[0],
                        "query_count": stat.count,
                        "avg_duration_ms": int(stat.avg_duration) if stat.avg_duration else 0,
                        "min_duration_ms": int(stat.min_duration) if stat.min_duration else 0,
                        "max_duration_ms": int(stat.max_duration) if stat.max_duration else 0,
                        "avg_sql_execution_ms": int(stat.avg_sql_execution) if stat.avg_sql_execution else 0,
                        "usage_rank": i + 1
                    })

            return {"datasources": datasources}
        except Exception:
            return {"datasources": []}

    def _get_performance_trend(self, user_id, days, stats, avg_total):
        """获取性能趋势对比"""
        try:
            # 获取上个周期的数据进行对比
            prev_start = date.today() - timedelta(days=days * 2)
            prev_end = date.today() - timedelta(days=days)

            prev_stats = QueryStatsDaily.query.filter(
                QueryStatsDaily.user_id == user_id,
                QueryStatsDaily.stat_date >= prev_start,
                QueryStatsDaily.stat_date < prev_end
            ).all()

            # 计算上周期平均值
            prev_total = 0
            prev_count = 0
            prev_vector_search = 0
            prev_rerank = 0
            prev_llm = 0
            prev_sql = 0

            if prev_stats:
                prev_count = len(prev_stats)
                prev_vector_search = sum(s.avg_vector_search_ms or 0 for s in prev_stats) / prev_count
                prev_rerank = sum(s.avg_rerank_ms or 0 for s in prev_stats) / prev_count
                prev_llm = sum(s.avg_llm_gen_sql_ms or 0 for s in prev_stats) / prev_count
                prev_sql = sum(s.avg_sql_execution_ms or 0 for s in prev_stats) / prev_count
                prev_total = prev_vector_search + prev_rerank + prev_llm + prev_sql

            # 当前周期平均值
            current_total = avg_total
            current_vector_search = sum(s.avg_vector_search_ms or 0 for s in stats) / len(stats) if stats else 0
            current_rerank = sum(s.avg_rerank_ms or 0 for s in stats) / len(stats) if stats else 0
            current_llm = sum(s.avg_llm_gen_sql_ms or 0 for s in stats) / len(stats) if stats else 0
            current_sql = sum(s.avg_sql_execution_ms or 0 for s in stats) / len(stats) if stats else 0

            def calc_change(current, previous):
                """计算变化率
                - 如果 current = 0 且 previous = 0，返回 0（都为零，无增长）
                - 如果 current > 0 且 previous = 0，返回 None（分母为0，无法计算）
                - 否则正常计算变化率
                """
                if current == 0 and previous == 0:
                    return 0.0
                if previous == 0:
                    return None
                return round((current - previous) / previous * 100, 1)

            def format_rate(rate):
                """格式化变化率，None时返回N/A"""
                if rate is None:
                    return "N/A"
                return f"+{rate}%" if rate >= 0 else f"{rate}%"

            vs_change = calc_change(current_vector_search, prev_vector_search)
            rr_change = calc_change(current_rerank, prev_rerank)
            llm_change = calc_change(current_llm, prev_llm)
            sql_change = calc_change(current_sql, prev_sql)
            overall_change = calc_change(current_total, prev_total)

            # 判断趋势
            if overall_change is None:
                trend = "stable"
            elif overall_change > 5:
                trend = "worse"
            elif overall_change < -5:
                trend = "better"
            else:
                trend = "stable"

            # 获取每日趋势
            daily_trend = []
            for s in reversed(stats[:7]):
                daily_trend.append({
                    "date": s.stat_date.strftime('%m-%d') if s.stat_date else "",
                    "avg_duration_ms": s.avg_duration_ms or 0
                })

            return {
                "vs_last_period": {
                    "vector_search_change": format_rate(vs_change),
                    "rerank_change": format_rate(rr_change),
                    "llm_gen_sql_change": format_rate(llm_change),
                    "sql_execution_change": format_rate(sql_change),
                    "overall_change": format_rate(overall_change),
                    "trend": trend
                },
                "daily_trend": daily_trend
            }
        except Exception:
            return {
                "vs_last_period": {
                    "vector_search_change": "0%",
                    "rerank_change": "0%",
                    "llm_gen_sql_change": "0%",
                    "sql_execution_change": "0%",
                    "overall_change": "0%",
                    "trend": "stable"
                },
                "daily_trend": []
            }

    def _get_query_patterns(self, user_id, days):
        """获取查询模式分析"""
        try:
            now = datetime.now(tz_cst)
            start_date = now - timedelta(days=days)

            # 统计不同复杂度的查询
            # 简单查询：单表查询 (table_names 长度 <= 1)
            # 中等查询：多表查询 (table_names 长度 2-3)
            # 复杂查询：跨库查询 (datasource_ids 包含多个)

            simple_count = 0
            moderate_count = 0
            complex_count = 0
            simple_duration = 0
            moderate_duration = 0
            complex_duration = 0

            # 获取样本数据
            sample_queries = QueryLog.query.filter(
                QueryLog.user_id == user_id,
                QueryLog.created_at >= start_date,
                QueryLog.status == 'success'
            ).limit(1000).all()

            total_count = len(sample_queries)
            if total_count == 0:
                return {"fast_queries_pct": 0, "slow_queries_pct": 0, "complexity_distribution": []}

            for q in sample_queries:
                duration = q.total_duration_ms or 0
                table_count = len(q.table_names) if q.table_names else 0
                ds_count = len(q.datasource_ids) if q.datasource_ids else 1

                if ds_count > 1:
                    complex_count += 1
                    complex_duration += duration
                elif table_count > 1:
                    moderate_count += 1
                    moderate_duration += duration
                else:
                    simple_count += 1
                    simple_duration += duration

            def calc_avg(duration, count):
                return int(duration / count) if count > 0 else 0

            fast_count = sum(1 for q in sample_queries if (q.total_duration_ms or 0) < 1000)
            slow_count = sum(1 for q in sample_queries if (q.total_duration_ms or 0) > 5000)

            return {
                "fast_queries_pct": round(fast_count / total_count * 100, 1),
                "slow_queries_pct": round(slow_count / total_count * 100, 1),
                "complexity_distribution": [
                    {
                        "type": "simple",
                        "label": "简单查询(单表)",
                        "count": simple_count,
                        "percentage": round(simple_count / total_count * 100, 1),
                        "avg_duration_ms": calc_avg(simple_duration, simple_count)
                    },
                    {
                        "type": "moderate",
                        "label": "中等查询(多表)",
                        "count": moderate_count,
                        "percentage": round(moderate_count / total_count * 100, 1),
                        "avg_duration_ms": calc_avg(moderate_duration, moderate_count)
                    },
                    {
                        "type": "complex",
                        "label": "复杂查询(跨库)",
                        "count": complex_count,
                        "percentage": round(complex_count / total_count * 100, 1),
                        "avg_duration_ms": calc_avg(complex_duration, complex_count)
                    }
                ]
            }
        except Exception:
            return {"fast_queries_pct": 0, "slow_queries_pct": 0, "complexity_distribution": []}


# 路由注册
api.add_resource(MonitoringOverviewResource, '/overview')
api.add_resource(MonitoringTrendResource, '/trend')
api.add_resource(MonitoringRealtimeResource, '/realtime')
api.add_resource(MonitoringPerformanceResource, '/performance')
