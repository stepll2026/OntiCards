// 全域盘点相关接口定义和封装

import { request } from './base'

// ===== 类型定义 =====

// 表清单项
export interface TableListItem {
  table_name: string
  missing_comment_fields: number
  quality_level: 'low' | 'medium' | 'high'
  is_auto_filled?: boolean // 是否有AI自动填充标志（true=部分数据AI补全，false=经过人工增强）
  auto_filled_count?: number // AI填充字段数
}

// 表清单响应
export interface TableListResponse {
  code: number
  msg: string
  data: TableListItem[]
}

// 字段画像
export interface FieldProfile {
  column_name?: string
  column_type?: string
  sample_size?: number
  null_ratio?: number       // API 返回的字段名
  null_rate_est?: number    // 兼容旧字段名
  distinct_ratio?: number   // API 返回的字段名
  distinct_est?: number     // 兼容旧字段名
  top_values?: Array<{ v?: any; cnt?: number; value?: any; count?: number; ratio?: number }>
  type_hint?: 'boolean_flag' | 'datetime' | 'timestamp' | 'enum' | 'amount' | 'identifier' | 'text' | string
  format_hint?: string
  notes?: string
  sample_values?: any[]
}

// 候选字段
export interface CandidateField {
  table_name: string
  column_name: string
  column_comment: string
  column_type?: string
  score: number
  source_type: 'table_ref' | 'dict'
  source_id: string
}

// LLM 候选注释
export interface LLMCandidate {
  comment?: string
  column_comment?: string  // 文档中的字段名
  confidence: number
  source: string
  source_type?: 'llm' | 'table_ref' | 'dict' | string  // 来源类型
  table_name?: string      // 来源表名
  column_name?: string     // 来源字段名
  column_type?: string     // 字段类型
  reasoning?: string
  scores?: {
    name_sim?: number
    type_match?: number
    vector_sim?: number
    profile_match?: number
    semantic_relevance?: number
  }
}

// LLM 裁决结果
export interface LLMJudgeResult {
  profile?: FieldProfile
  candidates: LLMCandidate[]
  need_human_confirm?: boolean
}

// Job 配置选项
export interface JobOptions {
  sample_size?: number
  vector_topn?: number
  topk?: number
  schema_name?: string
}

// 全域盘点任务
export interface GlobalInventoryJob {
  id: string
  user_id: string
  datasource_id: string
  schema_hash: string
  target_tables: string[]
  ref_tables: string[]
  dict_file_id?: string
  options: JobOptions
  status: 'queued' | 'running' | 'completed' | 'failed'
  progress?: any
  error_msg?: string
  created_at: string
  updated_at: string
}

// 全域盘点结果
export interface GlobalInventoryJobResult {
  job_id: string
  field_profiles_json: Record<string, FieldProfile>  // key 格式: "表名.字段名"
  candidates_json: Record<string, Record<string, { topk: CandidateField[] }>>
  llm_json: Record<string, Record<string, LLMJudgeResult>>
  confirm_json?: any
  index_meta_json: any
  created_at: string
  updated_at: string
}

// 启动盘点请求
export interface RunJobRequest {
  datasource_id: string
  target_tables: string[]
  ref_tables: string[]
  dict_file_id?: string
  options?: JobOptions
}

// 启动盘点响应
export interface RunJobResponse {
  code: number
  msg: string
  data: {
    job: GlobalInventoryJob
    result: GlobalInventoryJobResult
  }
}

// 确认回填请求
export interface ConfirmRequest {
  datasource_id: string
  table_name: string
  updates: Array<{
    column: string
    comment: string
  }>
}

// 确认回填响应
export interface ConfirmResponse {
  code: number
  msg: string
  data: {
    doc_id: string
    table_name: string
    _vector_ops: {
      delete_old_ok: boolean
      old_w_uuid: string
      new_w_uuid: string
    }
  }
}

// 查询 Job 结果响应
export interface JobResultResponse {
  code: number
  msg: string
  data: {
    job: GlobalInventoryJob
    result: GlobalInventoryJobResult
  }
}

// 字典文件上传响应
export interface DictUploadResponse {
  code: number
  message: string
  data: {
    dict_file_id: string
    entry_count: number
    preview: Array<{
      column_name: string
      column_comment: string
      column_type?: string
    }>
    save_path?: string
  }
}

// 表关系
export interface TableRelationship {
  id?: string
  from_table: string
  from_column: string
  to_table: string
  to_column: string
  relationship_type: 'foreign_key' | 'semantic' | 'name_based' | 'synonym'
  confidence: number
  reasoning?: string
  confirmed?: boolean
  cardinality?: 'one_to_one' | 'one_to_many' | 'many_to_one' | 'many_to_many'
}

// 联表查询条件
export interface JoinCondition {
  from_column: string
  to_column: string
  condition: string
  confidence: number
}

// 联表查询建议
export interface JoinSuggestion {
  recommended_join_type: 'INNER JOIN' | 'LEFT JOIN' | 'RIGHT JOIN' | 'FULL JOIN'
  join_conditions: JoinCondition[]
  sample_sql: string
  use_cases: string[]
  // 兼容旧字段名
  join_type?: string
  join_condition?: string
}

// 数据融合建议
export interface FusionSuggestion {
  primary_table: string
  secondary_table: string
  aggregation_hint: string
  fusion_strategy: string
  recommended_aggregations: string[]
}

// 业务关系
export interface BusinessRelation {
  from_role: 'master' | 'detail' | 'dimension' | 'fact'
  to_role: 'master' | 'detail' | 'dimension' | 'fact'
  from_entity?: string
  to_entity?: string
  relation_description?: string
}

// 关系卡片字段
export interface RelationshipCardField {
  from_table?: string
  to_table?: string
  from_column: string
  to_column: string
  confidence: number
  cardinality?: 'one_to_one' | 'one_to_many' | 'many_to_one' | 'many_to_many'
  type?: string
  reasoning?: string
  business_relation?: BusinessRelation
  join_suggestion?: JoinSuggestion
  fusion_suggestion?: FusionSuggestion
}

// 关系卡片
export interface RelationshipCard {
  id?: string
  card_id?: string
  // 主要字段名（API 返回的格式）
  table1: string
  table2: string
  // 兼容旧字段名
  from_table?: string
  to_table?: string
  relationship_type: 'foreign_key' | 'semantic' | 'name_based' | 'synonym' | 'value_overlap' | 'shared_field'
  confidence: number
  direction?: 'one_to_one' | 'one_to_many' | 'many_to_one' | 'many_to_many'
  fields: RelationshipCardField[]
  description?: string
  // 新增字段
  business_relation?: BusinessRelation
  join_suggestion?: JoinSuggestion
  fusion_suggestion?: FusionSuggestion
  // 额外字段
  is_cross_source?: boolean
}

// 图数据节点
export interface GraphNode {
  id: string
  label: string
  type: 'target' | 'ref' | 'table'
  table_name?: string
  field_count?: number
  missing_comment_count?: number
  quality_level?: 'low' | 'medium' | 'high'
  // 新增字段
  role?: 'master' | 'detail' | 'dimension' | 'fact'
  entity_name?: string
  description?: string
  record_count?: number
}

// 图数据边字段映射
export interface GraphEdgeFieldMapping {
  type?: string
  from_table?: string
  from_column: string
  to_table?: string
  to_column: string
  confidence?: number
  reasoning?: string
  cardinality?: 'one_to_one' | 'one_to_many' | 'many_to_one' | 'many_to_many'
  // 兼容旧格式
  field1?: string
  field2?: string
  // 新增字段
  business_relation?: BusinessRelation
  join_suggestion?: JoinSuggestion
  fusion_suggestion?: FusionSuggestion
}

// 图数据边
export interface GraphEdge {
  id?: string
  source: string
  target: string
  label?: string
  direction?: 'one_to_one' | 'one_to_many' | 'many_to_one' | 'many_to_many'
  relationship_type?: 'foreign_key' | 'semantic' | 'name_based' | 'synonym'
  confidence?: number
  fields?: GraphEdgeFieldMapping[]
  field_mappings?: Array<{
    source_field: string
    target_field: string
    confidence: number
  }>
  // 新增字段
  business_relation?: BusinessRelation
  business_description?: string
  join_suggestion?: JoinSuggestion
  fusion_suggestion?: FusionSuggestion
}

// 图数据
export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

// 表关系响应
export interface RelationshipsResponse {
  code: number
  msg: string
  data: {
    relationships: TableRelationship[]
    relationship_cards: RelationshipCard[]
  }
}

// 图数据响应
export interface GraphDataResponse {
  code: number
  msg: string
  data: GraphData
}

// 确认表关系项
export interface TableRelationshipConfirmation {
  from_table: string
  from_column: string
  to_table: string
  to_column: string
  relationship_type: 'foreign_key' | 'semantic' | 'name_based' | 'synonym'
  confidence: number
  action: 'accept' | 'reject' | 'modify'
}

// 确认表关系请求
export interface ConfirmTableRelationshipsRequest {
  job_id: string
  confirmations: TableRelationshipConfirmation[]
}

// 确认表关系响应
export interface ConfirmTableRelationshipsResponse {
  code: number
  msg: string
  data?: {
    success?: boolean
    confirmed_count?: number
    created_relationships?: number
    created_cards?: number
    table_relationship_ids?: string[]
    relationship_card_ids?: string[]
    errors?: string[]
  }
}

// 字段推荐确认项
export interface FieldRecommendationConfirmation {
  action: 'accept' | 'reject' | 'custom'
  selected_candidate?: LLMCandidate
  custom_comment?: string  // 当 action 为 custom 时使用
}

// 字段推荐确认请求
export interface ConfirmFieldRecommendationsRequest {
  job_id: string
  confirmations: Record<string, Record<string, FieldRecommendationConfirmation>>  // table_name -> column_name -> confirmation
}

// 字段推荐确认响应
export interface ConfirmFieldRecommendationsResponse {
  code: number
  msg: string
  data?: {
    confirmed_count: number
    updated_tables: string[]
  }
}

// API 响应格式
export interface ApiResponse<T = any> {
  code: number
  msg: string
  data?: T
  result?: T
}

// ===== API 函数 =====

/**
 * 获取表清单（显示缺失注释字段数）
 * @param datasourceId 数据源ID
 * @returns 表清单
 */
export const getTableList = async (datasourceId: string): Promise<TableListResponse> => {
  try {
    const response = await request<TableListResponse>(
      `/target_inventory/tables?datasource_id=${datasourceId}`,
      {
        method: 'GET',
      }
    )
    return response
  } catch (error) {
    console.error('获取表清单失败:', error)
    return {
      code: 500,
      msg: '获取表清单失败',
      data: []
    }
  }
}

/**
 * 启动全域盘点
 * @param params 盘点参数
 * @returns 盘点结果
 */
export const runGlobalInventory = async (params: RunJobRequest): Promise<RunJobResponse> => {
  try {
    const response = await request<RunJobResponse>(
      '/target_inventory/run',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: params,
      }
    )
    return response
  } catch (error) {
    console.error('启动全域盘点失败:', error)
    throw error
  }
}

/**
 * 查询 Job 结果
 * @param jobId 任务ID
 * @returns Job 结果
 */
export const getJobResult = async (jobId: string): Promise<JobResultResponse> => {
  try {
    const response = await request<JobResultResponse>(
      `/target_inventory/job/${jobId}`,
      {
        method: 'GET',
      }
    )
    return response
  } catch (error) {
    console.error('查询Job结果失败:', error)
    throw error
  }
}

/**
 * 确认并回填注释
 * @param params 确认参数
 * @returns 回填结果
 */
export const confirmAndFill = async (params: ConfirmRequest): Promise<ConfirmResponse> => {
  try {
    const response = await request<ConfirmResponse>(
      '/target_inventory/confirm',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: params,
      }
    )
    return response
  } catch (error) {
    console.error('确认回填失败:', error)
    throw error
  }
}

/**
 * 上传字典文件
 * @param file 字典文件
 * @returns 上传结果
 */
export const uploadDictFile = async (file: File): Promise<DictUploadResponse> => {
  try {
    const formData = new FormData()
    formData.append('file', file)

    const response = await request<DictUploadResponse>(
      '/target_inventory/dict/upload',
      {
        method: 'POST',
        body: formData,
      },
      {
        deleteContentType: true,
        bodyStringify: false,
      }
    )
    return response
  } catch (error) {
    console.error('上传字典文件失败:', error)
    throw error
  }
}

/**
 * 查询表关系
 * @param jobId 任务ID
 * @returns 表关系和关系卡片
 */
export const getRelationships = async (jobId: string): Promise<RelationshipsResponse> => {
  try {
    const response = await request<RelationshipsResponse>(
      `/target_inventory/job/${jobId}/relationships`,
      {
        method: 'GET',
      }
    )
    return response
  } catch (error) {
    console.error('查询表关系失败:', error)
    throw error
  }
}

/**
 * 获取关系图数据
 * @param jobId 任务ID
 * @returns 图数据（nodes + edges）
 */
export const getGraphData = async (jobId: string): Promise<GraphDataResponse> => {
  try {
    const response = await request<GraphDataResponse>(
      `/target_inventory/job/${jobId}/graph`,
      {
        method: 'GET',
      }
    )
    return response
  } catch (error) {
    console.error('获取关系图数据失败:', error)
    throw error
  }
}

/**
 * 确认表关系
 * @param params 确认参数
 * @returns 确认结果
 */
export const confirmTableRelationships = async (params: ConfirmTableRelationshipsRequest): Promise<ConfirmTableRelationshipsResponse> => {
  try {
    const response = await request<ConfirmTableRelationshipsResponse>(
      '/target_inventory/confirm_table_relationships',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: params,
      }
    )
    return response
  } catch (error) {
    console.error('确认表关系失败:', error)
    throw error
  }
}

/**
 * 确认字段推荐注释
 * @param params 确认参数
 * @returns 确认结果
 */
export const confirmFieldRecommendations = async (params: ConfirmFieldRecommendationsRequest): Promise<ConfirmFieldRecommendationsResponse> => {
  try {
    const response = await request<ConfirmFieldRecommendationsResponse>(
      '/target_inventory/confirm_field_recommendations',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: params,
      }
    )
    return response
  } catch (error) {
    console.error('确认字段推荐失败:', error)
    throw error
  }
}

// ==================== 历史盘点结果查看相关类型 ====================

// 历史任务列表项
export interface HistoryJobItem {
  job_id: string
  user_id: string
  datasource_id: string
  datasource_name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  target_tables: string[]
  ref_tables: string[]
  schema_name?: string
  created_at: string
  completed_at?: string
  progress?: {
    phase: string
    field_recommendations?: number
    table_relationships?: number
    relationship_cards?: number
  }
}

// 历史任务列表响应
export interface HistoryJobsResponse {
  code: number
  msg: string
  data: {
    total: number
    page: number
    page_size: number
    items: HistoryJobItem[]
  }
}

// 历史任务详情响应
export interface HistoryJobDetailResponse {
  code: number
  msg: string
  data: {
    job: HistoryJobItem & {
      schema_hash?: string
    }
    result?: {
      field_recommendations?: any
      field_profiles?: any
      candidates?: any
      field_mappings?: any
      table_relationships?: any
      relationship_cards?: any
      confirmations?: any
      index_meta?: any
    }
  }
}

// 字段推荐结果响应
export interface FieldRecommendationsResponse {
  code: number
  msg: string
  data: {
    recommendations: Record<string, Record<string, {
      candidates: Array<{
        table_name: string
        column_name: string
        column_comment: string
        score: number
        match_type: string
      }>
      profile?: {
        sample_values?: any[]
        distinct_count?: number
      }
    }>>
    profiles?: any
    candidates?: any
    confirmed?: Record<string, Record<string, {
      selected_ref: string
      action: string
    }>>
    confirmed_at?: string
  }
}

// 表关系推断结果响应
export interface TableRelationshipsHistoryResponse {
  code: number
  msg: string
  data: {
    relationships: Array<{
      from_table: string
      from_column: string
      to_table: string
      to_column: string
      relationship_type: string
      confidence: number
      reasoning?: string
      cardinality?: string
      business_relation?: {
        from_entity?: string
        to_entity?: string
        relation_description?: string
        from_role?: string
        to_role?: string
      }
      join_suggestion?: {
        join_type?: string
        join_condition?: string
        sample_sql?: string
        use_cases?: string[]
      }
      fusion_suggestion?: {
        primary_table?: string
        secondary_table?: string
        aggregation_hint?: string
        fusion_strategy?: string
      }
    }>
    confirmed?: Array<{
      from_table: string
      from_column: string
      to_table: string
      to_column: string
      action: string
    }>
    confirmed_at?: string
  }
}

// 关系卡片历史响应
export interface RelationshipCardsHistoryResponse {
  code: number
  msg: string
  data: {
    cards: RelationshipCard[]
  }
}

// 关系图谱历史响应
export interface GraphHistoryResponse {
  code: number
  msg: string
  data: GraphData
}

// 用户确认记录响应
export interface ConfirmationsHistoryResponse {
  code: number
  msg: string
  data: {
    field_recommendations?: {
      confirmed_at?: string
      confirmations?: Record<string, Record<string, {
        selected_ref: string
        action: string
      }>>
    }
    table_relationships?: {
      confirmed_at?: string
      confirmations?: Array<{
        from_table: string
        from_column: string
        to_table: string
        to_column: string
        action: string
      }>
    }
    field_mappings?: any
  }
}

// 字段映射项
export interface FieldMappingItem {
  id: string
  source_table: string
  source_column: string
  source_type: string
  target_table: string
  target_column: string
  target_type: string
  mapping_type: 'exact_match' | 'semantic_match' | 'user_defined' | string
  confidence: number
  mapping_basis?: {
    source?: string
    scores?: Record<string, number>
  }
  schema_hash?: string
  created_at: string
  updated_at: string
}

// 字段映射确认结果响应
export interface FieldMappingsConfirmedResponse {
  code: number
  msg: string
  data: {
    field_mappings: FieldMappingItem[]
    total: number
    by_table: Record<string, FieldMappingItem[]>
  }
}

// 数据源字段映射响应
export interface DatasourceFieldMappingsResponse {
  code: number
  msg: string
  data: {
    field_mappings: FieldMappingItem[]
    total: number
    by_table: Record<string, FieldMappingItem[]>
    statistics?: {
      total_mappings: number
      [key: string]: any
    }
  }
}

// ==================== 历史盘点结果查看相关 API ====================

/**
 * 获取历史盘点任务列表
 */
export const getHistoryJobs = async (params?: {
  datasource_id?: string
  status?: string
  page?: number
  page_size?: number
}): Promise<HistoryJobsResponse> => {
  try {
    const queryParams = new URLSearchParams()
    if (params?.datasource_id) queryParams.append('datasource_id', params.datasource_id)
    if (params?.status) queryParams.append('status', params.status)
    if (params?.page) queryParams.append('page', params.page.toString())
    if (params?.page_size) queryParams.append('page_size', params.page_size.toString())

    const queryString = queryParams.toString()
    const url = `/target_inventory/history/jobs${queryString ? `?${queryString}` : ''}`

    const response = await request<HistoryJobsResponse>(url, { method: 'GET' })
    return response
  } catch (error) {
    console.error('获取历史盘点任务列表失败:', error)
    throw error
  }
}

/**
 * 获取盘点任务详情
 */
export const getHistoryJobDetail = async (jobId: string): Promise<HistoryJobDetailResponse> => {
  try {
    const response = await request<HistoryJobDetailResponse>(
      `/target_inventory/history/job/${jobId}`,
      { method: 'GET' }
    )
    return response
  } catch (error) {
    console.error('获取盘点任务详情失败:', error)
    throw error
  }
}

/**
 * 获取字段推荐结果
 */
export const getHistoryFieldRecommendations = async (jobId: string): Promise<FieldRecommendationsResponse> => {
  try {
    const response = await request<FieldRecommendationsResponse>(
      `/target_inventory/history/job/${jobId}/field_recommendations`,
      { method: 'GET' }
    )
    return response
  } catch (error) {
    console.error('获取字段推荐结果失败:', error)
    throw error
  }
}

/**
 * 获取表关系推断结果
 */
export const getHistoryTableRelationships = async (jobId: string): Promise<TableRelationshipsHistoryResponse> => {
  try {
    const response = await request<TableRelationshipsHistoryResponse>(
      `/target_inventory/history/job/${jobId}/table_relationships`,
      { method: 'GET' }
    )
    return response
  } catch (error) {
    console.error('获取表关系推断结果失败:', error)
    throw error
  }
}

/**
 * 获取关系卡片
 */
export const getHistoryRelationshipCards = async (jobId: string): Promise<RelationshipCardsHistoryResponse> => {
  try {
    const response = await request<RelationshipCardsHistoryResponse>(
      `/target_inventory/history/job/${jobId}/relationship_cards`,
      { method: 'GET' }
    )
    return response
  } catch (error) {
    console.error('获取关系卡片失败:', error)
    throw error
  }
}

/**
 * 获取关系图谱数据
 */
export const getHistoryGraph = async (jobId: string): Promise<GraphHistoryResponse> => {
  try {
    const response = await request<GraphHistoryResponse>(
      `/target_inventory/history/job/${jobId}/graph`,
      { method: 'GET' }
    )
    return response
  } catch (error) {
    console.error('获取关系图谱数据失败:', error)
    throw error
  }
}

/**
 * 获取用户确认记录
 */
export const getHistoryConfirmations = async (jobId: string): Promise<ConfirmationsHistoryResponse> => {
  try {
    const response = await request<ConfirmationsHistoryResponse>(
      `/target_inventory/history/job/${jobId}/confirmations`,
      { method: 'GET' }
    )
    return response
  } catch (error) {
    console.error('获取用户确认记录失败:', error)
    throw error
  }
}

/**
 * 获取数据源下所有已确认的表关系
 */
export const getDatasourceRelationships = async (datasourceId: string): Promise<any> => {
  try {
    const response = await request<any>(
      `/target_inventory/datasource/${datasourceId}/relationships`,
      { method: 'GET' }
    )
    return response
  } catch (error) {
    console.error('获取数据源表关系失败:', error)
    throw error
  }
}

/**
 * 获取数据源下所有关系卡片
 */
export const getDatasourceRelationshipCards = async (datasourceId: string): Promise<any> => {
  try {
    const response = await request<any>(
      `/target_inventory/datasource/${datasourceId}/relationship_cards`,
      { method: 'GET' }
    )
    return response
  } catch (error) {
    console.error('获取数据源关系卡片失败:', error)
    throw error
  }
}

/**
 * 获取任务的字段映射确认结果
 * @param jobId 任务ID
 * @returns 字段映射确认结果
 */
export const getHistoryFieldMappingsConfirmed = async (jobId: string): Promise<FieldMappingsConfirmedResponse> => {
  try {
    const response = await request<FieldMappingsConfirmedResponse>(
      `/target_inventory/history/job/${jobId}/field_mappings_confirmed`,
      { method: 'GET' }
    )
    return response
  } catch (error) {
    console.error('获取字段映射确认结果失败:', error)
    throw error
  }
}

/**
 * 获取数据源的所有字段映射
 * @param datasourceId 数据源ID
 * @param params 可选查询参数
 * @returns 字段映射列表
 */
export const getDatasourceFieldMappings = async (
  datasourceId: string,
  params?: {
    source_table?: string
    target_table?: string
    mapping_type?: string
  }
): Promise<DatasourceFieldMappingsResponse> => {
  try {
    const queryParams = new URLSearchParams()
    if (params?.source_table) queryParams.append('source_table', params.source_table)
    if (params?.target_table) queryParams.append('target_table', params.target_table)
    if (params?.mapping_type) queryParams.append('mapping_type', params.mapping_type)

    const queryString = queryParams.toString()
    const url = `/target_inventory/datasource/${datasourceId}/field_mappings${queryString ? `?${queryString}` : ''}`

    const response = await request<DatasourceFieldMappingsResponse>(url, { method: 'GET' })
    return response
  } catch (error) {
    console.error('获取数据源字段映射失败:', error)
    throw error
  }
}

// 删除历史任务响应（单个删除）
export interface DeleteHistoryJobResponse {
  code: number
  msg: string
  data?: {
    deleted_count: number
  }
}

// 清空历史任务响应（包含详细统计）
export interface ClearHistoryJobsResponse {
  code: number
  msg: string
  data?: {
    deleted_jobs: number
    deleted_rels: number
    deleted_cards: number
    deleted_mappings: number
  }
}

/**
 * 删除单个历史盘点任务
 * @param jobId 任务ID
 * @returns 删除结果
 */
export const deleteHistoryJob = async (jobId: string): Promise<DeleteHistoryJobResponse> => {
  try {
    const response = await request<DeleteHistoryJobResponse>(
      `/target_inventory/history/job/${jobId}`,
      { method: 'DELETE' }
    )
    return response
  } catch (error) {
    console.error('删除历史任务失败:', error)
    throw error
  }
}

/**
 * 批量删除历史盘点任务
 * @param jobIds 任务ID列表
 * @returns 删除结果
 */
export const deleteHistoryJobs = async (jobIds: string[]): Promise<DeleteHistoryJobResponse> => {
  try {
    const response = await request<DeleteHistoryJobResponse>(
      '/target_inventory/history/jobs/batch_delete',
      {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: { job_ids: jobIds },
      }
    )
    return response
  } catch (error) {
    console.error('批量删除历史任务失败:', error)
    throw error
  }
}

/**
 * 清空所有历史盘点任务
 * @param datasourceId 可选，指定数据源ID，不传则清空所有
 * @returns 删除结果
 */
export const clearHistoryJobs = async (datasourceId?: string): Promise<ClearHistoryJobsResponse> => {
  try {
    const url = datasourceId
      ? `/target_inventory/history/jobs/clear?datasource_id=${datasourceId}`
      : '/target_inventory/history/jobs/clear'

    const response = await request<ClearHistoryJobsResponse>(url, { method: 'DELETE' })
    return response
  } catch (error) {
    console.error('清空历史任务失败:', error)
    throw error
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

/**
 * 删除指定定向盘点任务的关系数据
 * @param jobId 任务ID
 * @returns 删除结果
 */
export const deleteTargetInventoryRelationships = async (jobId: string): Promise<DeleteRelationshipsResponse> => {
  try {
    const response = await request<DeleteRelationshipsResponse>(
      `/target_inventory/job/${jobId}/relationships`,
      { method: 'DELETE' }
    )
    return response
  } catch (error) {
    console.error('删除定向盘点关系数据失败:', error)
    throw error
  }
}

