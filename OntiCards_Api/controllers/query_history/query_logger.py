"""
 @File: query_logger.py
 @Description: 查询日志记录工具类
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-03-30

 统一处理 query_logs 写入和 query_stats_daily 增量更新
"""

from datetime import date
from sqlalchemy.dialects.postgresql import insert
from extensions.ext_database import db
from models.query_logs import QueryLog
from models.query_stats_daily import QueryStatsDaily


class QueryLogger:
    """查询日志记录器"""

    @staticmethod
    def _normalize_jsonb_list(value: list) -> list:
        """
        规范化 JSONB 列表字段，确保存储为一维数组
        处理嵌套数组情况：[["uuid1", "uuid2"]] -> ["uuid1", "uuid2"]
        """
        if not value:
            return []
        # 如果是嵌套数组，展平为一维数组
        if value and isinstance(value, list) and value and isinstance(value[0], list):
            # 展平嵌套数组
            flattened = []
            for item in value:
                if isinstance(item, list):
                    flattened.extend(item)
                else:
                    flattened.append(item)
            return flattened
        return value if isinstance(value, list) else []

    @staticmethod
    def log_success(
        user_id: str,
        question: str,
        sql: str = None,
        source_datasource_ids: list = None,
        source_datasource_names: list = None,
        datasource_ids: list = None,
        datasource_names: list = None,
        table_names: list = None,
        performance: dict = None,
        tokens: dict = None,
        result_count: int = 0,
        cards_recalled: int = 0,
        cards_reranked: int = 0,
        cards_selected: int = 0,
        top1_rerank_score: float = None,
        avg_rerank_score: float = None,
        fusion_strategy: str = None,
        api_key_id: str = None,
        full_response_result: dict = None,
        cluster_sqls: list = None,
        # === 新增参数 ===
        processed_question: str = None,
        term_rewrite_info: dict = None
    ):
        """
        记录成功查询

        Args:
            user_id: 用户ID
            question: 用户原始问题（术语展开前）
            sql: 生成的SQL
            source_datasource_ids: 查询来源数据源ID列表（用户发起查询时选中的数据源）
            source_datasource_names: 查询来源数据源名称列表
            datasource_ids: 涉及的数据源ID列表（查询过程中涉及到的所有数据源）
            datasource_names: 涉及的数据源名称列表
            table_names: 表名列表
            performance: 性能指标 dict，含 total_duration_ms, vector_search_ms 等
            tokens: Token消耗 dict，含 embedding_tokens, rerank_tokens 等
            result_count: 返回行数
            cards_recalled: 向量召回卡片数
            cards_reranked: 重排序后卡片数
            cards_selected: 最终选择卡片数
            top1_rerank_score: Top1重排序分数
            avg_rerank_score: 平均重排序分数
            fusion_strategy: 融合策略
            api_key_id: API Key ID（如果通过API调用）
            full_response_result: 完整接口返回结果（用于回放/分析）
            cluster_sqls: 各数据源/簇的SQL数组（用于多数据源查询时记录各簇SQL）
            processed_question: 实际用于检索的问题（术语展开后）
            term_rewrite_info: 术语展开详情，包含匹配的术语列表等信息
        """
        # 1. 创建明细记录
        query_log = QueryLog(
            user_id=user_id,
            question=question,
            sql=sql,
            # 规范化 JSONB 字段，确保存储为一维数组
            source_datasource_ids=QueryLogger._normalize_jsonb_list(source_datasource_ids),
            source_datasource_names=QueryLogger._normalize_jsonb_list(source_datasource_names),
            datasource_ids=QueryLogger._normalize_jsonb_list(datasource_ids),
            datasource_names=QueryLogger._normalize_jsonb_list(datasource_names),
            table_names=QueryLogger._normalize_jsonb_list(table_names),
            total_duration_ms=performance.get('total_duration_ms') if performance else None,
            vector_search_ms=performance.get('vector_search_ms') if performance else None,
            rerank_ms=performance.get('rerank_ms') if performance else None,
            llm_gen_sql_ms=performance.get('llm_gen_sql_ms') if performance else None,
            sql_execution_ms=performance.get('sql_execution_ms') if performance else None,
            fusion_ms=performance.get('llm_fusion_ms', 0) if performance else None,
            embedding_tokens=tokens.get('embedding_tokens', 0) if tokens else 0,
            rerank_tokens=tokens.get('rerank_tokens', 0) if tokens else 0,
            llm_prompt_tokens=tokens.get('llm_prompt_tokens', 0) if tokens else 0,
            llm_completion_tokens=tokens.get('llm_completion_tokens', 0) if tokens else 0,
            total_tokens=tokens.get('total_tokens', 0) if tokens else 0,
            result_count=result_count,
            status='success',
            cards_recalled=cards_recalled,
            cards_reranked=cards_reranked,
            cards_selected=cards_selected,
            top1_rerank_score=top1_rerank_score,
            avg_rerank_score=avg_rerank_score,
            full_response_result=full_response_result,
            fusion_strategy=fusion_strategy,
            api_key_id=api_key_id,
            cluster_sqls=cluster_sqls,
            # === 新增字段 ===
            processed_question=processed_question if processed_question else None,
            term_rewrite_info=term_rewrite_info if term_rewrite_info else {}
        )
        db.session.add(query_log)

        # 2. 幂等更新聚合表
        QueryLogger._increment_daily_stats(
            user_id=user_id,
            is_success=True,
            tokens=tokens or {},
            duration_ms=performance.get('total_duration_ms') if performance else 0,
            vector_search_ms=performance.get('vector_search_ms') if performance else 0,
            rerank_ms=performance.get('rerank_ms') if performance else 0,
            llm_gen_sql_ms=performance.get('llm_gen_sql_ms') if performance else 0,
            sql_execution_ms=performance.get('sql_execution_ms') if performance else 0,
            cards_recalled=cards_recalled,
            cards_selected=cards_selected,
            top1_rerank_score=top1_rerank_score
        )

        return query_log

    @staticmethod
    def log_error(
        user_id: str,
        question: str,
        error_message: str,
        total_duration_ms: int = 0,
        source_datasource_ids: list = None,
        source_datasource_names: list = None,
        datasource_ids: list = None,
        datasource_names: list = None,
        api_key_id: str = None
    ):
        """
        记录失败查询

        Args:
            user_id: 用户ID
            question: 用户问题
            error_message: 错误信息
            total_duration_ms: 总耗时
            source_datasource_ids: 查询来源数据源ID列表
            source_datasource_names: 查询来源数据源名称列表
            datasource_ids: 数据源ID列表
            datasource_names: 数据源名称列表
            api_key_id: API Key ID（如果通过API调用）
        """
        query_log = QueryLog(
            user_id=user_id,
            question=question,
            total_duration_ms=total_duration_ms,
            status='error',
            error_message=error_message,
            # 规范化 JSONB 字段，确保存储为一维数组
            source_datasource_ids=QueryLogger._normalize_jsonb_list(source_datasource_ids),
            source_datasource_names=QueryLogger._normalize_jsonb_list(source_datasource_names),
            datasource_ids=QueryLogger._normalize_jsonb_list(datasource_ids),
            datasource_names=QueryLogger._normalize_jsonb_list(datasource_names),
            api_key_id=api_key_id
        )
        db.session.add(query_log)

        # 失败也要更新聚合表
        QueryLogger._increment_daily_stats(
            user_id=user_id,
            is_success=False,
            tokens={},
            duration_ms=total_duration_ms
        )

        return query_log

    @staticmethod
    def log_timeout(
        user_id: str,
        question: str,
        total_duration_ms: int = 0,
        source_datasource_ids: list = None,
        source_datasource_names: list = None,
        datasource_ids: list = None,
        datasource_names: list = None,
        api_key_id: str = None
    ):
        """
        记录超时查询

        Args:
            user_id: 用户ID
            question: 用户问题
            total_duration_ms: 总耗时
            source_datasource_ids: 查询来源数据源ID列表
            source_datasource_names: 查询来源数据源名称列表
            datasource_ids: 数据源ID列表
            datasource_names: 数据源名称列表
            api_key_id: API Key ID（如果通过API调用）
        """
        query_log = QueryLog(
            user_id=user_id,
            question=question,
            total_duration_ms=total_duration_ms,
            status='timeout',
            error_message='Query timeout',
            # 规范化 JSONB 字段，确保存储为一维数组
            source_datasource_ids=QueryLogger._normalize_jsonb_list(source_datasource_ids),
            source_datasource_names=QueryLogger._normalize_jsonb_list(source_datasource_names),
            datasource_ids=QueryLogger._normalize_jsonb_list(datasource_ids),
            datasource_names=QueryLogger._normalize_jsonb_list(datasource_names),
            api_key_id=api_key_id
        )
        db.session.add(query_log)

        QueryLogger._increment_daily_stats(
            user_id=user_id,
            is_success=False,
            is_timeout=True,
            tokens={},
            duration_ms=total_duration_ms
        )

        return query_log

    @staticmethod
    def _increment_daily_stats(
        user_id: str,
        is_success: bool,
        tokens: dict,
        duration_ms: int = 0,
        vector_search_ms: int = 0,
        rerank_ms: int = 0,
        llm_gen_sql_ms: int = 0,
        sql_execution_ms: int = 0,
        cards_recalled: int = 0,
        cards_selected: int = 0,
        top1_rerank_score: float = None,
        is_timeout: bool = False
    ):
        """
        幂等更新聚合表

        使用 PostgreSQL 的 INSERT ... ON CONFLICT DO UPDATE 实现原子累加，
        解决高并发场景下的竞态问题。
        """
        today = date.today()

        embedding_tokens = tokens.get('embedding_tokens', 0)
        rerank_tokens = tokens.get('rerank_tokens', 0)
        llm_prompt_tokens = tokens.get('llm_prompt_tokens', 0)
        llm_completion_tokens = tokens.get('llm_completion_tokens', 0)
        total_tokens = tokens.get('total_tokens', embedding_tokens + rerank_tokens + llm_prompt_tokens + llm_completion_tokens)

        # 计算成本
        estimated_cost_cents, cost_version = QueryLogger._calculate_cost(
            embedding_tokens,
            rerank_tokens,
            llm_prompt_tokens,
            llm_completion_tokens
        )

        # 构建 upsert 语句
        stmt = insert(QueryStatsDaily).values(
            user_id=user_id,
            stat_date=today,
            total_queries=1,
            success_queries=1 if is_success else 0,
            error_queries=0 if is_success else (1 if not is_timeout else 0),
            timeout_queries=1 if is_timeout else 0,
            total_embedding_tokens=embedding_tokens,
            total_rerank_tokens=rerank_tokens,
            total_llm_tokens=llm_prompt_tokens + llm_completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_cents=estimated_cost_cents,
            cost_version=cost_version,
            avg_duration_ms=duration_ms,
            min_duration_ms=duration_ms if duration_ms else None,
            max_duration_ms=duration_ms if duration_ms else None,
            avg_vector_search_ms=vector_search_ms,
            avg_rerank_ms=rerank_ms,
            avg_llm_gen_sql_ms=llm_gen_sql_ms,
            avg_sql_execution_ms=sql_execution_ms,
            avg_cards_recalled=cards_recalled,
            avg_cards_selected=cards_selected,
            avg_top1_rerank_score=top1_rerank_score
        )

        # 冲突时累加更新
        stmt = stmt.on_conflict_do_update(
            constraint='uq_user_stat_date',
            set_={
                'total_queries': QueryStatsDaily.total_queries + 1,
                'success_queries': QueryStatsDaily.success_queries + (1 if is_success else 0),
                'error_queries': QueryStatsDaily.error_queries + (0 if is_success else (1 if not is_timeout else 0)),
                'timeout_queries': QueryStatsDaily.timeout_queries + (1 if is_timeout else 0),
                'total_embedding_tokens': QueryStatsDaily.total_embedding_tokens + embedding_tokens,
                'total_rerank_tokens': QueryStatsDaily.total_rerank_tokens + rerank_tokens,
                'total_llm_tokens': QueryStatsDaily.total_llm_tokens + (llm_prompt_tokens + llm_completion_tokens),
                'total_tokens': QueryStatsDaily.total_tokens + total_tokens,
                'estimated_cost_cents': QueryStatsDaily.estimated_cost_cents + estimated_cost_cents,
                'avg_duration_ms': duration_ms,
                'min_duration_ms': db.func.least(
                    db.func.coalesce(QueryStatsDaily.min_duration_ms, 999999999),
                    duration_ms
                ) if duration_ms else QueryStatsDaily.min_duration_ms,
                'max_duration_ms': db.func.greatest(
                    db.func.coalesce(QueryStatsDaily.max_duration_ms, 0),
                    duration_ms
                ) if duration_ms else QueryStatsDaily.max_duration_ms,
                'updated_at': db.func.now()
            }
        )

        try:
            db.session.execute(stmt)
            print(f"[_increment_daily_stats] 执行成功: user_id={user_id}, date={today}")
        except Exception as e:
            print(f"[_increment_daily_stats] 执行失败: {str(e)}")
            import traceback
            print(f"[_increment_daily_stats] 详细错误: {traceback.format_exc()}")
            raise

    @staticmethod
    def _calculate_cost(embedding_tokens, rerank_tokens, llm_prompt_tokens, llm_completion_tokens):
        """
        计算Token成本（人民币分）

        ⚠️ 注意：此为预估值，实际费用以云厂商账单为准
        """
        from models.system_configs import get_config_as_float
        import hashlib

        # 从配置表读取价格（仅查询系统级配置，user_id 传 None）
        embedding_price = get_config_as_float('token_price_embedding', user_id=None, default=0.0007)
        rerank_price = get_config_as_float('token_price_rerank', user_id=None, default=0.002)
        llm_input_price = get_config_as_float('token_price_llm_input', user_id=None, default=0.002)
        llm_output_price = get_config_as_float('token_price_llm_output', user_id=None, default=0.006)

        # 计算各部分成本
        embedding_cost = (embedding_tokens or 0) / 1000 * embedding_price
        rerank_cost = (rerank_tokens or 0) / 1000 * rerank_price
        llm_input_cost = (llm_prompt_tokens or 0) / 1000 * llm_input_price
        llm_output_cost = (llm_completion_tokens or 0) / 1000 * llm_output_price

        total_cost_yuan = embedding_cost + rerank_cost + llm_input_cost + llm_output_cost

        # 生成配置版本号
        version_str = f"{embedding_price}:{rerank_price}:{llm_input_price}:{llm_output_price}"
        cost_version = hashlib.md5(version_str.encode()).hexdigest()[:8]

        return int(total_cost_yuan * 100), cost_version

    @staticmethod
    def decrement_daily_stats(query_log):
        """
        递减聚合表统计值（用于删除查询日志时的级联更新）

        当删除一条 query_logs 记录时，需要同步减少 query_stats_daily 中
        对应用户当天日期的统计值，确保两张表的数据一致性。

        Args:
            query_log: QueryLog 实例，要删除的查询日志记录
        """
        if not query_log or not query_log.user_id or not query_log.created_at:
            return

        # 获取该记录所属的日期
        stat_date = query_log.created_at.date() if query_log.created_at else date.today()

        # 查询对应的聚合记录
        daily_stat = QueryStatsDaily.query.filter_by(
            user_id=str(query_log.user_id),
            stat_date=stat_date
        ).first()

        if not daily_stat:
            return

        # 判断要删除的记录类型
        is_success = query_log.status == 'success'
        is_timeout = query_log.status == 'timeout'

        # 获取 token 消耗
        embedding_tokens = query_log.embedding_tokens or 0
        rerank_tokens = query_log.rerank_tokens or 0
        llm_prompt_tokens = query_log.llm_prompt_tokens or 0
        llm_completion_tokens = query_log.llm_completion_tokens or 0
        total_tokens = query_log.total_tokens or 0

        # 重新计算要删除的这条记录的成本
        estimated_cost_cents, _ = QueryLogger._calculate_cost(
            embedding_tokens,
            rerank_tokens,
            llm_prompt_tokens,
            llm_completion_tokens
        )

        # 判断是否需要删除整条聚合记录
        # 如果 total_queries <= 1，则直接删除聚合记录
        if daily_stat.total_queries <= 1:
            db.session.delete(daily_stat)
            return

        # 否则递减各项统计值（确保不会变成负数）
        daily_stat.total_queries = max(0, daily_stat.total_queries - 1)
        daily_stat.success_queries = max(0, daily_stat.success_queries - (1 if is_success else 0))
        daily_stat.error_queries = max(0, daily_stat.error_queries - (1 if (query_log.status == 'error') else 0))
        daily_stat.timeout_queries = max(0, daily_stat.timeout_queries - (1 if is_timeout else 0))
        daily_stat.total_embedding_tokens = max(0, daily_stat.total_embedding_tokens - embedding_tokens)
        daily_stat.total_rerank_tokens = max(0, daily_stat.total_rerank_tokens - rerank_tokens)
        daily_stat.total_llm_tokens = max(0, daily_stat.total_llm_tokens - (llm_prompt_tokens + llm_completion_tokens))
        daily_stat.total_tokens = max(0, daily_stat.total_tokens - total_tokens)
        daily_stat.estimated_cost_cents = max(0, daily_stat.estimated_cost_cents - estimated_cost_cents)

        # 注意：avg_duration_ms, min_duration_ms, max_duration_ms 等聚合值
        # 在删除单条记录后无法精确更新，需要依赖定时任务重新计算
        # 这里只做简单的递减处理

        daily_stat.updated_at = db.func.now()

    @staticmethod
    def delete_with_cascade(query_log):
        """
        删除查询日志并级联更新聚合表

        这是删除 query_logs 的推荐方式，确保数据一致性。

        Args:
            query_log: QueryLog 实例

        Returns:
            bool: 是否删除成功
        """
        try:
            # 1. 先递减聚合表
            QueryLogger.decrement_daily_stats(query_log)

            # 2. 删除明细记录
            db.session.delete(query_log)

            # 3. 提交事务
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"删除查询日志失败: {e}")
            return False
