import { get, del } from './base'

/**
 * 术语展开详情
 */
export interface TermRewriteInfo {
  enabled: boolean
  matched_count: number
  matched_terms: TermMatchedItem[]
  rewritten_question: string
}

/**
 * 匹配到的术语项
 */
export interface TermMatchedItem {
  term_name: string
  term_definition: string
  matched_name: string
  term_id: string
  library_id: string
  library_name: string
}

/**
 * 聚类 SQL 信息（多数据源查询时各数据源的 SQL）
 */
export interface ClusterSQL {
  cluster_index: number
  datasource_ids: string[]
  datasource_names: string[]
  table_names: string[]
  sql: string
  fusion_strategy: string
}

/**
 * 查询历史列表项
 */
export interface QueryHistoryItem {
  id: string
  question: string
  // 术语展开后的问题（实际用于检索的问题）
  processed_question?: string
  // 术语展开详情
  term_rewrite_info?: TermRewriteInfo
  sql: string
  // 聚类 SQL 信息（多数据源查询时各数据源的 SQL）
  cluster_sqls?: ClusterSQL[]
  datasource_ids: string[]
  datasource_names: string[]
  // 新增：来源数据源（发起查询的数据源）
  source_datasource_ids: string[]
  source_datasource_names: string[]
  total_duration_ms: number
  total_tokens: number
  status: 'success' | 'error' | 'timeout'
  result_count: number
  fusion_strategy: string
  created_at: string
}

/**
 * 查询历史列表响应
 */
export interface QueryHistoryListResponse {
  code: number
  msg?: string
  message?: string
  data: {
    total: number
    page: number
    page_size: number
    total_pages: number
    items: QueryHistoryItem[]
  }
}

/**
 * 查询历史详情响应
 */
export interface QueryHistoryDetailResponse {
  code: number
  msg?: string
  message?: string
  data: QueryHistoryDetailData
}

/**
 * 查询历史详情数据
 */
export interface QueryHistoryDetailData {
  id: string
  user_id: string
  api_key_id: string | null
  question: string
  // 术语展开后的问题（实际用于检索的问题）
  processed_question?: string
  // 术语展开详情
  term_rewrite_info?: TermRewriteInfo
  sql: string
  // 聚类 SQL 信息（多数据源查询时各数据源的 SQL）
  cluster_sqls?: ClusterSQL[]
  datasource_ids: string[]
  datasource_names: string[]
  // 新增：来源数据源（发起查询的数据源）
  source_datasource_ids?: string[]
  source_datasource_names?: string[]
  table_names: string[]
  performance: {
    total_duration_ms: number
    vector_search_ms: number
    rerank_ms: number
    llm_gen_sql_ms: number
    sql_execution_ms: number
    fusion_ms: number | null
  }
  tokens: {
    embedding_tokens: number
    rerank_tokens: number
    llm_prompt_tokens: number
    llm_completion_tokens: number
    total_tokens: number
  }
  result: {
    result_count: number
  }
  quality: {
    cards_recalled: number
    cards_reranked: number
    cards_selected: number
    top1_rerank_score: number | null
    avg_rerank_score: number | null
  }
  status: 'success' | 'error' | 'timeout'
  error_message: string | null
  fusion_strategy: string
  created_at: string
  // 完整响应结果（包含数据卡片和查询结果）
  full_response_result?: FullResponseResult
}

/**
 * 完整响应结果
 */
export interface FullResponseResult {
  clusters: ClusterResult[]
  merge: MergeInfo
  final_rows: Record<string, unknown>[]
  fill_warnings: string[]
  data_cards: DataCardInfo[]
}

/**
 * 簇查询结果
 */
export interface ClusterResult {
  query: string
  datasource_id: string
  datasource_name: string
  rows: Record<string, unknown>[]
  columns: string[]
  error?: string
}

/**
 * 融合信息
 */
export interface MergeInfo {
  strategy: string
  entity_key?: string
  final_entity_ids?: string[]
  fusion_method?: string
}

/**
 * 数据卡片信息
 */
export interface DataCardInfo {
  id?: string
  doc_id: string
  card_name?: string
  card_content?: DataCardContent
  datasource_name?: string
  datasource_id?: string
  table_name: string
  column_names?: string[]
  description?: string
  score?: number
  content_preview?: string
}

/**
 * 数据卡片内容
 */
export interface DataCardContent {
  Tags?: string[]
  Abstract?: string
  DocInfo?: {
    title?: string
    author?: string
    doc_id?: string
    domain?: string
    language?: string
    connect_name?: string
    datasource_id?: string
    abstract?: string
  }
  SQLMeta?: {
    pk?: string
    table?: string
    columns?: Array<{
      name: string
      type: string
      comment?: string
      nullable?: boolean
      is_primary?: boolean
      is_foreign?: boolean
    }>
    foreign_keys?: Array<{
      name: string
      columns: string[]
      referenced_table: string
    }>
  }
}

/**
 * 查询历史统计响应
 */
export interface QueryHistoryStatsResponse {
  code: number
  msg?: string
  message?: string
  data: {
    period: {
      start_date: string
      end_date: string
    }
    total_queries: number
    success_queries: number
    error_queries: number
    timeout_queries: number
    success_rate: number
    total_tokens: number
    avg_duration_ms: number
    min_duration_ms: number
    max_duration_ms: number
  }
}

/**
 * 查询历史列表参数
 */
export interface QueryHistoryListParams {
  user_id?: string
  workspace_id?: string
  // 按查询来源数据源筛选，用于按数据源查看历史
  source_datasource_id?: string
  page?: number
  page_size?: number
  keyword?: string
  status?: 'success' | 'error' | 'timeout' | 'all'
  start_date?: string
  end_date?: string
}

/**
 * 查询历史统计参数
 */
export interface QueryHistoryStatsParams {
  user_id?: string
  workspace_id?: string
  // 按查询来源数据源筛选
  source_datasource_id?: string
  start_date?: string
  end_date?: string
}

/**
 * 获取查询历史列表
 */
export const getQueryHistoryList = (params: QueryHistoryListParams) => {
  return get<QueryHistoryListResponse>('/query_history/list', { params })
}

/**
 * 获取查询历史详情
 */
export const getQueryHistoryDetail = (query_id: string, user_id: string) => {
  return get<QueryHistoryDetailResponse>(`/query_history/${query_id}`, {
    params: { user_id },
  })
}

/**
 * 获取查询历史统计
 */
export const getQueryHistoryStats = (params: QueryHistoryStatsParams) => {
  return get<QueryHistoryStatsResponse>('/query_history/stats', { params })
}

/**
 * 删除单条查询历史响应
 */
export interface DeleteQueryHistoryResponse {
  code: number
  msg?: string
  data?: {
    deleted_id: string
  }
}

/**
 * 批量删除查询历史响应
 */
export interface BatchDeleteQueryHistoryResponse {
  code: number
  msg?: string
  data?: {
    deleted_count: number
    total_found?: number
  }
}

/**
 * 删除单条查询历史
 */
export const deleteQueryHistory = (query_id: string, user_id: string) => {
  return del<DeleteQueryHistoryResponse>(`/query_history/${query_id}/delete?user_id=${user_id}`)
}

/**
 * 批量删除查询历史
 */
export interface BatchDeleteParams {
  user_id: string
  query_ids?: string
  before_date?: string
  keep_days?: number
}

export const batchDeleteQueryHistory = (params: BatchDeleteParams) => {
  const queryParts: string[] = [`user_id=${params.user_id}`]
  if (params.query_ids) queryParts.push(`query_ids=${params.query_ids}`)
  if (params.before_date) queryParts.push(`before_date=${params.before_date}`)
  if (params.keep_days) queryParts.push(`keep_days=${params.keep_days}`)
  return del<BatchDeleteQueryHistoryResponse>(`/query_history/batch/delete?${queryParts.join('&')}`)
}
