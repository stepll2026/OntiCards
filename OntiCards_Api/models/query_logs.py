"""
 @File: query_logs.py
 @Description: 查询日志表 - 记录每次查询的完整信息
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-03-30
"""
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, Integer, String, Text, Float, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSON, JSONB

from extensions.ext_database import db
from models.utils import format_datetime

# 中国时区 (UTC+8)
tz_cst = timezone(timedelta(hours=8))


class QueryLog(db.Model):
    """查询日志表 - 记录每次查询的完整信息"""
    __tablename__ = "query_logs"

    # === 主键 ===
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="主键ID"
    )

    # === 用户信息 ===
    user_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="用户ID"
    )

    api_key_id = Column(
        UUID(as_uuid=True),
        comment="API Key ID（如果通过API调用）"
    )

    # === 查询内容 ===
    question = Column(
        Text,
        nullable=False,
        comment="用户原始问题（术语展开前）"
    )

    # === 术语展开后的查询内容（新增） ===
    processed_question = Column(
        Text,
        comment="实际用于检索/生成SQL的问题（术语展开后）"
    )

    # === 术语展开详情（新增） ===
    term_rewrite_info = Column(
        JSONB,
        comment="术语展开详情，包含匹配的术语列表等信息"
    )

    sql = Column(
        Text,
        comment="生成的SQL语句"
    )

    # === 来源数据源（用户发起查询时选中的数据源）===
    # 注意：这是查询的"来源"，用于按数据源筛选历史查询
    # 例如：用户从数据源A发起查询，找到A和B的数据，则 source_datasource_ids=['A的id']，datasource_ids=['A的id', 'B的id']
    # 如果用户选中多个数据源查询，则 source_datasource_ids 包含这几个数据源ID
    source_datasource_ids = Column(
        JSONB,
        comment="查询来源数据源ID列表 ['uuid1', 'uuid2']，表示用户发起查询时选中的数据源"
    )

    source_datasource_names = Column(
        JSONB,
        comment="查询来源数据源名称列表（冗余，便于展示）['生产库', '测试库']"
    )

    # === 涉及数据源（查询过程中涉及到的所有数据源）===
    datasource_ids = Column(
        JSONB,
        comment="涉及的数据源ID列表 ['uuid1', 'uuid2']"
    )

    datasource_names = Column(
        JSONB,
        comment="数据源名称列表（冗余，便于展示）['生产库', '测试库']"
    )

    table_names = Column(
        JSONB,
        comment="涉及的表名列表 ['orders', 'users']"
    )

    # === 性能指标（毫秒） ===
    total_duration_ms = Column(
        Integer,
        comment="总耗时(ms)"
    )

    vector_search_ms = Column(
        Integer,
        comment="向量检索耗时(ms)"
    )

    rerank_ms = Column(
        Integer,
        comment="重排序耗时(ms)"
    )

    llm_gen_sql_ms = Column(
        Integer,
        comment="LLM生成SQL耗时(ms)"
    )

    sql_execution_ms = Column(
        Integer,
        comment="SQL执行耗时(ms)"
    )

    fusion_ms = Column(
        Integer,
        comment="跨库融合耗时(ms)"
    )

    # === Token消耗 ===
    embedding_tokens = Column(
        Integer,
        default=0,
        comment="Embedding Token数"
    )

    rerank_tokens = Column(
        Integer,
        default=0,
        comment="Rerank Token数"
    )

    llm_prompt_tokens = Column(
        Integer,
        default=0,
        comment="LLM Prompt Token数（输入）"
    )

    llm_completion_tokens = Column(
        Integer,
        default=0,
        comment="LLM Completion Token数（输出）"
    )

    total_tokens = Column(
        Integer,
        default=0,
        comment="总Token数"
    )

    # === 结果信息 ===
    result_count = Column(
        Integer,
        comment="返回行数"
    )

    status = Column(
        String(32),
        nullable=False,
        default='success',
        comment="查询状态：success/error/timeout"
    )

    error_message = Column(
        Text,
        comment="错误信息（如果失败）"
    )

    fusion_strategy = Column(
        String(32),
        comment="融合策略：AND/OR/UNION/PRIORITY/NONE"
    )

    # === 召回质量指标 ===
    cards_recalled = Column(
        Integer,
        default=0,
        comment="向量召回卡片数"
    )

    cards_reranked = Column(
        Integer,
        default=0,
        comment="重排序后卡片数"
    )

    cards_selected = Column(
        Integer,
        default=0,
        comment="最终选择卡片数"
    )

    top1_rerank_score = Column(
        Float,
        comment="Top1卡片的重排序分数"
    )

    avg_rerank_score = Column(
        Float,
        comment="选中卡片的平均重排序分数"
    )

    # === 完整响应结果（JSON） ===
    full_response_result = Column(
        JSONB,
        comment="完整接口返回结果（用于回放/分析）"
    )

    # === 多数据源 SQL 数组（新增） ===
    # 用于记录多数据源查询时各簇/各数据源的 SQL
    cluster_sqls = Column(
        JSONB,
        nullable=True,
        comment="各数据源/簇的SQL数组 [{'datasource_ids': ['xxx'], 'datasource_names': ['xxx'], 'table_names': ['xxx'], 'sql': 'SELECT ...'}], 用于多数据源查询时记录各簇SQL"
    )

    # === 时间戳 ===
    created_at = Column(
        db.TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(tz_cst),
        index=True,
        comment="查询发起时间"
    )

    # === 索引策略 ===
    __table_args__ = (
        Index('idx_query_logs_user_created', 'user_id', 'created_at'),
        Index('idx_query_logs_user_status', 'user_id', 'status'),
    )

    def __repr__(self):
        return f"<QueryLog id={self.id} user_id={self.user_id} question={self.question[:20] if self.question else ''}...>"

    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "api_key_id": str(self.api_key_id) if self.api_key_id else None,
            "question": self.question,
            "processed_question": self.processed_question,
            "term_rewrite_info": self.term_rewrite_info,
            "sql": self.sql,
            "source_datasource_ids": self.source_datasource_ids,
            "source_datasource_names": self.source_datasource_names,
            "datasource_ids": self.datasource_ids,
            "datasource_names": self.datasource_names,
            "table_names": self.table_names,
            "total_duration_ms": self.total_duration_ms,
            "vector_search_ms": self.vector_search_ms,
            "rerank_ms": self.rerank_ms,
            "llm_gen_sql_ms": self.llm_gen_sql_ms,
            "sql_execution_ms": self.sql_execution_ms,
            "fusion_ms": self.fusion_ms,
            "embedding_tokens": self.embedding_tokens,
            "rerank_tokens": self.rerank_tokens,
            "llm_prompt_tokens": self.llm_prompt_tokens,
            "llm_completion_tokens": self.llm_completion_tokens,
            "total_tokens": self.total_tokens,
            "result_count": self.result_count,
            "status": self.status,
            "error_message": self.error_message,
            "fusion_strategy": self.fusion_strategy,
            "cards_recalled": self.cards_recalled,
            "cards_reranked": self.cards_reranked,
            "cards_selected": self.cards_selected,
            "top1_rerank_score": self.top1_rerank_score,
            "avg_rerank_score": self.avg_rerank_score,
            "full_response_result": self.full_response_result,
            "cluster_sqls": self.cluster_sqls,
            "created_at": format_datetime(self.created_at),
        }
