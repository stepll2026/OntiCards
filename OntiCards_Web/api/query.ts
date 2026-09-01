import { post, type IOtherOptions } from './base'

// 查询请求参数类型
export interface QueryRequest {
  query: string
  enable_rerank?: boolean
  datasource_id?: string  // 单个数据源ID（可选）
  datasource_ids?: string[]  // 多个数据源ID（可选）
}

// ========== 术语展开相关类型定义 ==========

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
 * 术语展开详情
 */
export interface TermRewrite {
  enabled: boolean
  matched_count: number
  matched_terms: TermMatchedItem[]
  rewritten_question: string
}

// 数据库列信息
export interface ColumnInfo {
  name: string
  type: string
  nullable: boolean
  default: any
  comment: string | null
  is_primary: boolean
  is_foreign: boolean
}

// SQL元数据
export interface SQLMeta {
  table: string
  pk: string
  pk_value: any
  file_path: string
  checksum: string
  columns: ColumnInfo[]
  foreign_keys: any[]
}

// 文档信息
export interface DocInfo {
  doc_id: string
  title: string
  source_type: string
  publish_date: string
  domain: string
  language: string
  author: string
  pages: number
  origin_url: string
  connect_name?: string
}

// 关键概念
export interface KeyConcepts {
  canonical_topic: string
  alias: string[]
  taxonomy_code: string
  key_entities: string[]
  applicable_scenarios: string[]
  tags: string[]
}

// 图谱映射
export interface GraphMap {
  nodes: any[]
  edges: any[]
}

// 数据卡片信息
export interface CardData {
  DocInfo: DocInfo
  Abstract: string
  KeyConcepts: KeyConcepts
  MongoMap: any[]
  GraphMap: GraphMap
  SQLMeta: SQLMeta
  Tags: string[]
}

// 查询结果项
export interface QueryResultItem {
  db_type: string
  connect_info: string
  database_name: string
  table_name: string
  target_sql: string
  sql_result: Record<string, any>[]
  warnings: string[]
  note: string
  schema_id: string
  doc_id: string
  card_data: CardData | null
}

// API响应类型
export interface QueryResponse {
  code: number
  msg: string
  results: QueryResultItem[]
}

// 查询数据卡片接口
export const queryByDatacards = async (params: QueryRequest): Promise<QueryResponse> => {
  try {
    const response = await post<QueryResponse>('/query_by_datacards', { body: params })
    return response
  } catch (error) {
    console.error('查询数据卡片失败:', error)
    throw error
  }
}

// ============= 聚合检索相关类型定义 =============

// 列信息
export interface AggColumnInfo {
  name: string
  type: string
}

// 表信息
export interface AggTableInfo {
  table_name: string
  alias: string | null
}

// 簇表信息
export interface ClusterTable {
  table_name: string
  columns: AggColumnInfo[]
}

// 连接信息
export interface ConnectInfoSafe {
  type: string
  database: string | null
}

// 数据簇
export interface DataCluster {
  db_type: string
  connect_info_safe: ConnectInfoSafe
  tables: AggTableInfo[]
  cluster_tables: ClusterTable[]
  target_sql: string
  rows: Record<string, any>[]
  entity_ids: any[]
  note: string
  warnings: string[]
  error?: string  // 新增：失败时的技术错误详情
}

// 融合策略
export interface MergeStrategy {
  strategy: string
  entity_key: string
  final_entity_ids: any[]
}

// 数据卡片
export interface DataCardItem {
  doc_id: string
  table_name: string
  database_name: string
  connect_name: string
  card_content: CardData
}

// 聚合查询数据
export interface AggQueryData {
  clusters: DataCluster[]
  merge: MergeStrategy
  final_rows: Record<string, any>[]
  fill_warnings: string[]
  data_cards: DataCardItem[]
  // 术语展开详情
  term_rewrite?: TermRewrite
}

// 聚合查询响应
export interface AggQueryResponse {
  code: number
  msg: string
  data: AggQueryData
}

// 聚合检索接口
export const queryByDatacardsAgg = async (
  params: QueryRequest,
  otherOptions?: IOtherOptions
): Promise<AggQueryResponse> => {
  try {
    const response = await post<AggQueryResponse>('/query_by_datacards_agg', { body: params }, otherOptions)
    return response
  } catch (error) {
    console.error('聚合查询失败:', error)
    throw error
  }
}