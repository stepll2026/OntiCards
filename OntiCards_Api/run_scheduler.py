# -*- coding: utf-8 -*-
"""
 @File: run_scheduler.py
 @Description: 定时任务调度器启动脚本
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-04-08

 使用 APScheduler 实现定时清理任务：
 - 每天凌晨 4:00 执行数据清理（避开业务高峰期）

 使用方式：
 1. 独立运行：python run_scheduler.py
 2. 与 Flask 一起运行：在启动命令后加 & 同时运行

 注意：
 - 这是简化实现，不影响现有业务
 - 调度器可以独立部署，不依赖 Flask 进程
"""

import logging
import sys
import os
import time

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 中国时区
tz_cst = timezone(timedelta(hours=8))


def main():
    """主函数：启动定时任务调度器"""
    logger.info("=" * 60)
    logger.info("[调度器] 数据清理定时任务调度器启动")
    logger.info("=" * 60)

    # 创建调度器
    scheduler = BackgroundScheduler(timezone=str(tz_cst))

    # 注册清理任务
    from task import cleanup_all

    # 定时任务：每天凌晨 4:00 执行
    scheduler.add_job(
        func=cleanup_all,
        trigger=CronTrigger(hour=4, minute=0, timezone=str(tz_cst)),
        id='cleanup_expired_data',
        name='清理过期数据',
        replace_existing=True,
        misfire_grace_time=3600  # 错过1小时内仍执行
    )

    # 启动调度器
    scheduler.start()
    logger.info("[调度器] ✓ 调度器已启动，定时任务已注册")
    logger.info("[调度器]   - 清理任务：每天 04:00 执行")
    logger.info("[调度器]   - 按 Ctrl+C 可以停止调度器")

    # 打印下次执行时间
    try:
        next_run_time = scheduler.get_job('cleanup_expired_data').next_run_time
        if next_run_time:
            logger.info(f"[调度器]   - 下次执行时间：{next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.warning(f"[调度器] 无法获取下次执行时间: {e}")

    logger.info("=" * 60)

    # 保持运行
    try:
        while True:
            time.sleep(60)  # 每分钟检查一次
    except (KeyboardInterrupt, SystemExit):
        logger.info("[调度器] 收到停止信号，正在关闭调度器...")
        scheduler.shutdown()
        logger.info("[调度器] ✓ 调度器已关闭")


if __name__ == '__main__':
    main()
