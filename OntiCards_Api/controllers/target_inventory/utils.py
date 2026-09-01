"""
 @File: utils.py
 @Description: 全域盘点模块的共享工具函数
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-01-21
"""

from __future__ import annotations
import json
from models.datacards_datasource import DataCardDataSource


def _safe_load_card(rec: DataCardDataSource) -> dict:
    """
    安全加载 DataCard 的 card_data 字段

    Args:
        rec: DataCardDataSource 记录

    Returns:
        解析后的字典，失败时返回空字典
    """
    try:
        return json.loads(rec.card_data) if isinstance(rec.card_data, str) else (rec.card_data or {})
    except Exception:
        return {}


def extract_connect_and_table(card: dict) -> tuple[str, str]:
    """
    从 DataCard 中提取连接名和表名

    Args:
        card: DataCard 字典

    Returns:
        (connect_name, table_name) 元组
    """
    doc = card.get("DocInfo") or {}
    sqlm = card.get("SQLMeta") or {}
    connect_name = (doc.get("connect_name") or "").strip()
    table_name = (sqlm.get("table") or "").strip()
    return connect_name, table_name
