# -*- coding: utf-8 -*-
"""
 @File: cleanup_tasks.py
 @Description: 数据清理定时任务
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-04-08

 提供定时清理功能：
 1. query_logs 表过期数据清理
 2. query_stats_daily 表过期数据清理
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from extensions.ext_database import db
from models.query_logs import QueryLog
from models.query_stats_daily import QueryStatsDaily
from models.system_configs import get_config_as_int

# 中国时区 (UTC+8)
tz_cst = timezone(timedelta(hours=8))

# 日志记录器
logger = logging.getLogger(__name__)


def cleanup_expired_logs():
    """
    清理过期的查询日志

    根据 system_configs 表中的 query_logs_retention_days 配置，
    删除超过保留期限的历史记录。

    Returns:
        dict: 包含删除数量的字典 {"deleted": 0}
    """
    try:
        # 获取保留天数配置（默认 180 天）
        retention_days = get_config_as_int('query_logs_retention_days', None, default=180)

        # 计算截止日期
        cutoff_date = datetime.now(tz_cst) - timedelta(days=retention_days)

        logger.info(f"[数据清理] 开始清理 {retention_days} 天前的查询日志（截止日期：{cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}）")

        # 统计待删除数量
        count_before = db.session.query(func.count(QueryLog.id)).filter(
            QueryLog.created_at < cutoff_date
        ).scalar() or 0

        if count_before == 0:
            logger.info("[数据清理] 没有需要清理的查询日志")
            return {"deleted": 0}

        # 执行删除（分批删除以避免锁表）
        batch_size = 1000
        total_deleted = 0

        while True:
            # 每次删除一批
            deleted = db.session.query(QueryLog).filter(
                QueryLog.created_at < cutoff_date
            ).limit(batch_size).delete(synchronize_session=False)

            db.session.commit()
            total_deleted += deleted

            logger.debug(f"[数据清理] 本批删除了 {deleted} 条记录")

            # 如果删除数量少于批次大小，说明已经删完了
            if deleted < batch_size:
                break

            # 安全检查：防止无限循环
            if total_deleted >= count_before:
                break

        logger.info(f"[数据清理] ✓ 查询日志清理完成，共删除 {total_deleted} 条记录")

        return {"deleted": total_deleted}

    except Exception as e:
        db.session.rollback()
        logger.error(f"[数据清理] 清理查询日志失败: {e}", exc_info=True)
        return {"deleted": 0, "error": str(e)}


def cleanup_expired_stats():
    """
    清理过期的聚合统计记录

    根据 system_configs 表中的 stats_retention_days 配置，
    删除超过保留期限的日聚合统计数据。

    注意：日聚合数据通常保留更长时间（默认 365 天），
    因为它们是重要的统计指标来源。

    Returns:
        dict: 包含删除数量的字典 {"deleted": 0}
    """
    try:
        # 获取保留天数配置（默认 365 天）
        retention_days = get_config_as_int('stats_retention_days', None, default=365)

        # 计算截止日期（使用日期类型比较）
        cutoff_date = (datetime.now(tz_cst) - timedelta(days=retention_days)).date()

        logger.info(f"[数据清理] 开始清理 {retention_days} 天前的聚合统计（截止日期：{cutoff_date}）")

        # 统计待删除数量
        count_before = db.session.query(func.count(QueryStatsDaily.id)).filter(
            QueryStatsDaily.stat_date < cutoff_date
        ).scalar() or 0

        if count_before == 0:
            logger.info("[数据清理] 没有需要清理的聚合统计数据")
            return {"deleted": 0}

        # 执行删除
        deleted = db.session.query(QueryStatsDaily).filter(
            QueryStatsDaily.stat_date < cutoff_date
        ).delete(synchronize_session=False)

        db.session.commit()

        logger.info(f"[数据清理] ✓ 聚合统计清理完成，共删除 {deleted} 条记录")

        return {"deleted": deleted}

    except Exception as e:
        db.session.rollback()
        logger.error(f"[数据清理] 清理聚合统计数据失败: {e}", exc_info=True)
        return {"deleted": 0, "error": str(e)}


def cleanup_all():
    """
    执行所有清理任务

    按顺序执行：
    1. 清理过期查询日志
    2. 清理过期聚合统计

    Returns:
        dict: 包含各项清理结果的字典
    """
    logger.info("=" * 50)
    logger.info("[数据清理] ========== 开始执行定时清理任务 ==========")

    results = {}

    # 1. 清理查询日志
    log_result = cleanup_expired_logs()
    results["query_logs"] = log_result

    # 2. 清理聚合统计
    stats_result = cleanup_expired_stats()
    results["query_stats_daily"] = stats_result

    total_deleted = log_result.get("deleted", 0) + stats_result.get("deleted", 0)
    logger.info(f"[数据清理] ========== 清理任务完成，共删除 {total_deleted} 条记录 ==========")
    logger.info("=" * 50)

    return results
