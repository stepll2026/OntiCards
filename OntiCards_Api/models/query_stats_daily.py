"""
 @File: query_stats_daily.py
 @Description: 查询统计表（按天聚合）- 用于监控模块
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-03-30
"""
import uuid
from datetime import datetime, date, timezone, timedelta
from sqlalchemy import Column, Integer, String, Float, Date, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID

from extensions.ext_database import db
from models.utils import format_datetime

# 中国时区 (UTC+8)
tz_cst = timezone(timedelta(hours=8))


class QueryStatsDaily(db.Model):
    """查询统计表（按天聚合）- 用于监控模块"""
    __tablename__ = "query_stats_daily"

    # === 主键 ===
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="主键ID"
    )

    # === 用户和时间 ===
    user_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="用户ID"
    )

    stat_date = Column(
        Date,
        nullable=False,
        index=True,
        comment="统计日期"
    )

    # === 调用次数统计 ===
    total_queries = Column(
        Integer,
        default=0,
        comment="总查询次数"
    )

    success_queries = Column(
        Integer,
        default=0,
        comment="成功次数"
    )

    error_queries = Column(
        Integer,
        default=0,
        comment="失败次数"
    )

    timeout_queries = Column(
        Integer,
        default=0,
        comment="超时次数"
    )

    # === Token消耗统计 ===
    total_embedding_tokens = Column(
        db.BigInteger,
        default=0,
        comment="Embedding总Token"
    )

    total_rerank_tokens = Column(
        db.BigInteger,
        default=0,
        comment="Rerank总Token"
    )

    total_llm_tokens = Column(
        db.BigInteger,
        default=0,
        comment="LLM总Token"
    )

    total_tokens = Column(
        db.BigInteger,
        default=0,
        comment="总Token消耗"
    )

    # === 成本统计（人民币，分，预估仅供参考） ===
    # ⚠️ 重要说明：
    # 1. 成本为预估值，实际费用以云厂商账单为准
    # 2. 实际成本受折扣、套餐、促销活动等影响，可能有偏差
    # 3. cost_version 用于记录价格配置版本，便于追溯
    estimated_cost_cents = Column(
        Integer,
        default=0,
        comment="预估成本(分)，仅供参考，实际费用以账单为准"
    )

    cost_version = Column(
        String(32),
        comment="价格配置版本号，用于追溯当时的价格配置"
    )

    # === 性能统计（毫秒） ===
    avg_duration_ms = Column(
        Integer,
        comment="平均耗时"
    )

    min_duration_ms = Column(
        Integer,
        comment="最小耗时"
    )

    max_duration_ms = Column(
        Integer,
        comment="最大耗时"
    )

    # === 各环节平均耗时 ===
    avg_vector_search_ms = Column(
        Integer,
        comment="向量检索平均耗时"
    )

    avg_rerank_ms = Column(
        Integer,
        comment="重排序平均耗时"
    )

    avg_llm_gen_sql_ms = Column(
        Integer,
        comment="LLM生成SQL平均耗时"
    )

    avg_sql_execution_ms = Column(
        Integer,
        comment="SQL执行平均耗时"
    )

    # === 召回质量统计 ===
    avg_cards_recalled = Column(
        Float,
        comment="平均召回卡片数"
    )

    avg_cards_selected = Column(
        Float,
        comment="平均选择卡片数"
    )

    avg_top1_rerank_score = Column(
        Float,
        comment="平均Top1重排序分数"
    )

    # === 时间戳 ===
    created_at = Column(
        db.TIMESTAMP(timezone=True),
        default=lambda: datetime.now(tz_cst),
        comment="记录创建时间"
    )

    updated_at = Column(
        db.TIMESTAMP(timezone=True),
        default=lambda: datetime.now(tz_cst),
        onupdate=lambda: datetime.now(tz_cst),
        comment="记录更新时间"
    )

    # === 唯一约束 ===
    __table_args__ = (
        UniqueConstraint('user_id', 'stat_date', name='uq_user_stat_date'),
    )

    def __repr__(self):
        return f"<QueryStatsDaily user_id={self.user_id} stat_date={self.stat_date}>"

    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "stat_date": str(self.stat_date),
            "total_queries": self.total_queries,
            "success_queries": self.success_queries,
            "error_queries": self.error_queries,
            "timeout_queries": self.timeout_queries,
            "total_embedding_tokens": self.total_embedding_tokens,
            "total_rerank_tokens": self.total_rerank_tokens,
            "total_llm_tokens": self.total_llm_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_cents": self.estimated_cost_cents,
            "estimated_cost_yuan": self.estimated_cost_cents / 100 if self.estimated_cost_cents else 0,
            "cost_version": self.cost_version,
            "avg_duration_ms": self.avg_duration_ms,
            "min_duration_ms": self.min_duration_ms,
            "max_duration_ms": self.max_duration_ms,
            "avg_vector_search_ms": self.avg_vector_search_ms,
            "avg_rerank_ms": self.avg_rerank_ms,
            "avg_llm_gen_sql_ms": self.avg_llm_gen_sql_ms,
            "avg_sql_execution_ms": self.avg_sql_execution_ms,
            "avg_cards_recalled": self.avg_cards_recalled,
            "avg_cards_selected": self.avg_cards_selected,
            "avg_top1_rerank_score": self.avg_top1_rerank_score,
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }
