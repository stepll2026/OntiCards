import { get, post, del } from './base'

// ==================== 类型定义 ====================

// 发现关系请求参数
export interface DiscoverRelationshipsParams {
  datasource_ids: string[]           // 数据源ID列表（必填）
  schema_name?: string
  confidence_threshold?: number
  max_workers?: number
}

// 发现关系响应
export interface DiscoverRelationshipsResponse {
  code: number
  msg: string
  data: {
    success: boolean
    datasource_ids: string[]         // 处理的数据源ID列表
    tables_count: number
    relationships_count: number
    cards_count: number
    cross_source_count: number       // 跨源关系数量
    statistics: {
      total_tables: number
      total_relationships: number      // 字段级关系数
      total_table_pairs: number        // 表对级关系数（新增）
      cross_source_table_pairs: number // 跨源表对数（新增）
      tables_with_relationships: number
      tables_without_relationships: number
      relationship_types: {
        FK: number
        Semantic: number
        Value: number
      }
      cardinality_distribution: {
        many_to_one: number
        one_to_many: number
        many_to_many: number
        one_to_one: number
      }
      avg_confidence: number
      high_confidence_count: number
      low_confidence_count: number
      cross_source_count: number     // 跨源关系数量
      intra_source_count: number     // 源内关系数量
    }
    persist_result: {
      relationships_saved: number
      cards_saved: number
    }
  }
}

// JOIN 字段
export interface JoinField {
  local_field: string
  remote_field: string
  confidence: number
  relationship_type: 'foreign_key' | 'semantic' | 'same_name'
}

// JOIN 建议
export interface JoinSuggestion {
  join_type: 'LEFT JOIN' | 'INNER JOIN' | 'RIGHT JOIN'
  join_condition: string
  use_cases: string[]
  sample_sql?: string  // 示例SQL语句
}

// 业务关系
export interface BusinessRelation {
  from_entity: string
  to_entity: string
  relation_description: string
  from_role: 'master' | 'detail' | 'fact' | 'dimension'
  to_role: 'master' | 'detail' | 'fact' | 'dimension'
}

// 融合建议
export interface FusionSuggestion {
  primary_table: string
  secondary_table: string
  aggregation_hint: string
  fusion_strategy: string
}

// 单个关系
export interface Relationship {
  related_table: string
  relationship_type: 'many_to_one' | 'one_to_many' | 'one_to_one' | 'many_to_many'
  confidence: number
  join_fields: JoinField[]
  join_suggestion: JoinSuggestion
  business_relation: BusinessRelation
  fusion_suggestion: FusionSuggestion
  // 跨源关系相关字段
  is_cross_source?: boolean           // 是否跨源关系
  related_datasource_id?: string      // 关联表所属数据源ID
  related_datasource_name?: string    // 关联表所属数据源名称
}

// 文档信息
export interface DocInfo {
  doc_id: string
  title: string
  source_type: 'relationship'
  datasource_id?: string
  schema_name?: string
  table_name: string
  created_at?: string
}

// 表信息
export interface TableInfo {
  table_name: string
  fields_count: number
  primary_key: string
}

// 融合提示
export interface FusionHints {
  as_master: string[]
  as_detail: string[]
  common_joins: string[]
}

// 统计信息
export interface CardStatistics {
  related_tables_count: number
  total_join_fields: number
  avg_confidence: number
}

// 关系卡片
export interface RelationshipCard {
  DocInfo: DocInfo
  TableInfo: TableInfo
  Relationships: Relationship[]
  FusionHints: FusionHints
  JoinSummary: string
  Statistics: CardStatistics
}

// 关系卡片项
export interface RelationshipCardItem {
  table_name: string
  card: RelationshipCard
  version: number
  related_tables_count: number
  created_at: string
  updated_at: string
  // 跨源关系相关字段
  related_datasource_ids?: string[]      // 所有关联数据源ID的汇总数组
  has_cross_source_relations?: boolean   // 是否有跨源关系
}

// 获取所有关系卡片响应
export interface GetCardsResponse {
  code: number
  msg: string
  data: {
    cards: RelationshipCardItem[]
    total: number
    statistics: {
      tables_with_relationships: number
      tables_without_relationships: number
    }
  }
}

// 获取单表关系卡片响应
export interface GetCardResponse {
  code: number
  msg: string
  data: {
    card: RelationshipCard
    version: number
    created_at: string
    updated_at: string
  }
}

// JOIN 条件
export interface JoinCondition {
  local_field: string
  remote_field: string
  confidence: number
  mapping_type: string
}

// 表关系
export interface GlobalInventory {
  id: string
  table_a: string
  table_b: string
  table_a_datasource_id?: string    // 表A所属数据源ID
  table_b_datasource_id?: string    // 表B所属数据源ID
  table_a_datasource_name?: string  // 表A所属数据源名称
  table_b_datasource_name?: string  // 表B所属数据源名称
  is_cross_source?: boolean         // 是否跨源关系
  relationship_type: 'FK' | 'Semantic' | 'Value'
  join_conditions: JoinCondition[]
  relationship_strength: number
  cardinality: 'many_to_one' | 'one_to_many' | 'one_to_one' | 'many_to_many'
  created_at: string
}

// 获取所有表关系响应
export interface GetRelationshipsResponse {
  code: number
  msg: string
  data: {
    relationships: GlobalInventory[]
    total: number
    statistics: {
      by_type: {
        FK: number
        Semantic: number
        Value: number
      }
      by_cardinality: {
        many_to_one: number
        one_to_many: number
        many_to_many: number
      }
      avg_strength: number
      cross_source_count?: number    // 跨源关系数量
      intra_source_count?: number    // 源内关系数量
    }
  }
}

// 图谱节点
export interface GraphNode {
  id: string
  label: string
  type: string
  related_count: number
  datasource_id?: string           // 所属数据源ID
  datasource_name?: string         // 所属数据源名称
  cross_source_count?: number      // 跨源关系数量
}

// 图谱边
export interface GraphEdge {
  id: string
  source: string
  target: string
  label: string
  strength: number
  cardinality: string
  source_datasource_id?: string    // 源节点数据源ID
  target_datasource_id?: string    // 目标节点数据源ID
  source_datasource_name?: string  // 源节点数据源名称
  target_datasource_name?: string  // 目标节点数据源名称
  is_cross_source?: boolean        // 是否跨源关系
  join_conditions: Array<{
    local_field: string
    remote_field: string
    confidence: number
    mapping_type?: string          // 映射类型（foreign_key, semantic, same_name）
  }>
  // 扩展字段（用于详情展示）
  join_sql?: string                // JOIN SQL 示例
  join_type?: string               // 推荐的 JOIN 类型（LEFT JOIN, INNER JOIN 等）
  join_condition?: string          // JOIN 条件表达式
  use_cases?: string[]             // 使用场景
  created_at?: string              // 创建时间
  // 业务关系信息
  business_relation?: {
    from_entity?: string           // 源实体名称
    to_entity?: string             // 目标实体名称
    relation_description?: string  // 关系描述
    from_role?: 'master' | 'detail' | 'fact' | 'dimension'  // 源表角色
    to_role?: 'master' | 'detail' | 'fact' | 'dimension'    // 目标表角色
  }
  // 融合建议
  fusion_suggestion?: {
    primary_table?: string         // 主表
    secondary_table?: string       // 从表
    aggregation_hint?: string      // 聚合提示
    fusion_strategy?: string       // 融合策略
  }
}

// 获取关系图谱响应
export interface GetGraphResponse {
  code: number
  msg: string
  data: {
    nodes: GraphNode[]
    edges: GraphEdge[]
  }
}

// 联表建议请求参数
export interface JoinSuggestionParams {
  datasource_id: string
  tables: string[]
}

// 联表建议项
export interface JoinSuggestionItem {
  from_table: string
  to_table: string
  from_column: string
  to_column: string
  join_type: string
  join_condition: string
  confidence: number
  cardinality: string
}

// 联表建议响应
export interface JoinSuggestionResponse {
  code: number
  msg: string
  data: {
    suggestions: JoinSuggestionItem[]
    recommended_join_order: string[]
    sample_sql: string
  }
}

// 批量获取关系卡片请求参数
export interface BatchCardsParams {
  datasource_id: string
  table_names: string[]
}

// 批量获取关系卡片响应
export interface BatchCardsResponse {
  code: number
  msg: string
  data: {
    cards: Record<string, {
      table_name: string
      relationships: Array<{
        related_table: string
        relationship_type: string
        confidence: number
        join_fields: JoinField[]
        join_suggestion: JoinSuggestion
      }>
      all_relationships: Relationship[]
      join_summary: string
      fusion_hints: FusionHints
    }>
    join_suggestions: JoinSuggestionItem[]
    missing_tables: string[]
    found_count: number
    requested_count: number
  }
}

// 删除关系数据响应
export interface DeleteRelationshipsResponse {
  code: number
  msg: string
  data: {
    deleted_relationships: number
    deleted_cards: number
  }
}

// ==================== API 函数 ====================

const BASE_PATH = '/global_inventory'

/**
 * 发现关系
 * 启动表关系发现任务，对数据源中的所有表进行关系分析
 */
export const discoverRelationships = (params: DiscoverRelationshipsParams) => {
  return post<DiscoverRelationshipsResponse>(`${BASE_PATH}/discover`, { body: params })
}

/**
 * 获取所有关系卡片
 * @param datasource_id 数据源ID
 * @param with_relationships 是否只返回有关系的表，默认false
 */
export const getRelationshipCards = (datasource_id: string, with_relationships?: boolean) => {
  const params: Record<string, any> = {}
  if (with_relationships !== undefined) {
    params.with_relationships = with_relationships
  }
  return get<GetCardsResponse>(`${BASE_PATH}/cards/${datasource_id}`, { params })
}

/**
 * 获取单表关系卡片
 * @param datasource_id 数据源ID
 * @param table_name 表名
 */
export const getRelationshipCard = (datasource_id: string, table_name: string) => {
  return get<GetCardResponse>(`${BASE_PATH}/card/${datasource_id}/${table_name}`)
}

/**
 * 获取所有表关系
 * @param datasource_id 数据源ID（单数据源）
 * @param options 可选参数
 * @param options.datasource_ids 多数据源ID列表
 * @param options.table_name 筛选包含特定表的关系
 * @param options.min_confidence 最小置信度筛选
 */
export const getTableRelationships = (
  datasource_id?: string,
  options?: {
    datasource_ids?: string[]
    table_name?: string
    min_confidence?: number
  }
) => {
  const params: Record<string, any> = {}
  if (options?.datasource_ids && options.datasource_ids.length > 0) {
    params.datasource_ids = options.datasource_ids.join(',')
  }
  if (options?.table_name) {
    params.table_name = options.table_name
  }
  if (options?.min_confidence !== undefined) {
    params.min_confidence = options.min_confidence
  }
  // 如果有多数据源，使用多数据源接口；否则使用单数据源接口
  if (options?.datasource_ids && options.datasource_ids.length > 0) {
    return get<GetRelationshipsResponse>(`${BASE_PATH}/relationships`, { params })
  }
  return get<GetRelationshipsResponse>(`${BASE_PATH}/relationships/${datasource_id}`, { params })
}

/**
 * 获取关系图谱数据
 * @param datasource_id 数据源ID（单数据源）
 * @param datasource_ids 多数据源ID列表
 */
export const getRelationshipGraph = (datasource_id?: string, datasource_ids?: string[]) => {
  // 如果有多数据源，使用多数据源接口
  if (datasource_ids && datasource_ids.length > 0) {
    const params = { datasource_ids: datasource_ids.join(',') }
    return get<GetGraphResponse>(`${BASE_PATH}/graph`, { params })
  }
  return get<GetGraphResponse>(`${BASE_PATH}/graph/${datasource_id}`)
}

/**
 * 联表建议
 * 根据表名列表获取JOIN建议和示例SQL
 */
export const getJoinSuggestion = (params: JoinSuggestionParams) => {
  return post<JoinSuggestionResponse>(`${BASE_PATH}/join_suggestion`, { body: params })
}

/**
 * 批量获取关系卡片
 * 根据表名列表批量获取关系卡片，主要供NL2SQL模块调用
 */
export const getBatchCards = (params: BatchCardsParams) => {
  return post<BatchCardsResponse>(`${BASE_PATH}/batch_cards`, { body: params })
}

/**
 * 删除关系数据
 * 删除数据源的所有关系数据，用于重新发现
 * @param datasource_id 数据源ID
 */
export const deleteRelationships = (datasource_id: string) => {
  return del<DeleteRelationshipsResponse>(`${BASE_PATH}/delete/${datasource_id}`)
}

// ==================== 全域盘点任务历史相关类型 ====================

// 全域盘点任务项
export interface GlobalInventoryJobItem {
  job_id: string
  user_id: string
  datasource_ids: string[]
  datasource_names?: string[]
  schema_name?: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  confidence_threshold?: number
  created_at: string
  completed_at?: string
  statistics?: {
    tables_count: number
    relationships_count: number
    cards_count: number
    cross_source_count: number
    avg_confidence: number
  }
}

// 全域盘点任务历史响应
export interface GlobalInventoryHistoryResponse {
  code: number
  msg: string
  data: {
    total: number
    page: number
    page_size: number
    items: GlobalInventoryJobItem[]
  }
}

// 全域盘点任务详情响应
export interface GlobalInventoryJobDetailResponse {
  code: number
  msg: string
  data: {
    job: GlobalInventoryJobItem
    cards_count: number
    relationships_count: number
  }
}

// ==================== 全域盘点任务历史相关 API ====================

/**
 * 获取全域盘点任务历史列表
 * @param datasource_id 可选，按数据源ID筛选
 * @param page 页码
 * @param page_size 每页数量
 */
export const getGlobalInventoryHistory = (
  datasource_id?: string,
  page: number = 1,
  page_size: number = 20
) => {
  const params: Record<string, string | number> = { page, page_size }
  if (datasource_id) {
    params.datasource_id = datasource_id
  }
  return get<GlobalInventoryHistoryResponse>(`${BASE_PATH}/history/jobs`, { params })
}

/**
 * 获取全域盘点任务详情
 * @param job_id 任务ID
 */
export const getGlobalInventoryJobDetail = (job_id: string) => {
  return get<GlobalInventoryJobDetailResponse>(`${BASE_PATH}/history/job/${job_id}`)
}

/**
 * 删除全域盘点任务
 * @param job_id 任务ID
 */
export const deleteGlobalInventoryJob = (job_id: string) => {
  return del<{ code: number; msg: string; data?: { deleted: boolean } }>(`${BASE_PATH}/history/job/${job_id}`)
}

/**
 * 清除数据源的关系数据
 * @param datasource_id 数据源ID
 */
export const deleteRelationshipsByDatasourceId = (datasource_id: string) => {
  return del<{ code: number; msg: string; data?: { deleted: boolean } }>(`${BASE_PATH}/delete/${datasource_id}`)
}
