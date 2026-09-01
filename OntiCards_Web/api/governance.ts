// 数据治理模块 API

import { del, get, post, put, request, urlPrefix } from './base'

// ==================== 类型定义 ====================

export interface GovernanceDatasourceSummary {
  id: string
  name?: string
  connect_name?: string
  database_name?: string
  db_type?: string
}

export interface GovernanceLibrary {
  id: string
  name: string
  description?: string
  status: 'active' | 'inactive'
  datasource_id?: string
  datasource_name?: string
  connect_name?: string
  database_name?: string
  datasource_db_type?: string
  datasource?: GovernanceDatasourceSummary
  created_by: string
  created_at: string
  updated_at: string
  rule_count?: number
  rules?: GovernanceRule[]
}

export type RuleType =
  | 'null_check'
  | 'unique'
  | 'format'
  | 'threshold'
  | 'enum'
  | 'custom_sql'
  | 'length_check'
  | 'range_check'
  | 'date_check'
  | 'consistency_check'
  | 'freshness_check'
  | 'value_distribution'
  | 'composite'
  | 'table_stats'
  | 'basic_null_check'
  | 'multi_column_compare'

export type SeverityLevel = 'critical' | 'warning' | 'info'

export type RuleCreateSource = 'manual' | 'template' | 'ai'

export interface GovernanceRuleConditionsConfig {
  conditions?: GovernanceRuleCondition[]
  condition_mode?: 'AND' | 'OR'
  [key: string]: any
}

export interface GovernanceRule {
  id: string
  library_id?: string
  rule_name: string
  rule_type: RuleType
  rule_type_name?: string
  target_table?: string
  target_column?: string | null
  condition_expr?: string | null
  conditions_config?: string | GovernanceRuleConditionsConfig | Array<Record<string, any>> | null
  severity: SeverityLevel
  severity_name?: string
  create_source?: RuleCreateSource
  create_source_name?: string
  description?: string
  enabled: boolean
  is_global?: boolean
  scope_description?: string
  datasource_id?: string
  connect_name?: string
  datasource_name?: string
  datasource_db_type?: string
  sql_text?: string
  created_at: string
  updated_at: string
  template_id?: string
}

export interface GovernanceRuleTemplate {
  id: string
  name: string
  template_name?: string
  rule_type: RuleType | string
  rule_type_name?: string
  description?: string
  default_condition?: string
  params?: Array<{
    name: string
    description?: string
    required?: boolean
  }>
  applicable_columns?: string
  applicable_columns_list?: string[]
  default_severity?: SeverityLevel | string
  severity_name?: string
  condition_placeholder_hint?: string | null
  category?: string | null
  has_placeholder?: boolean
  related_rules_count?: number
  created_at?: string
}

export interface RuleTemplate extends GovernanceRuleTemplate {}

export interface RuleExecutionResult {
  id: string
  rule_id?: string
  rule_name: string
  table_name: string
  column_name?: string
  total_count: number
  passed_count: number
  failed_count: number
  failed_rate: number
  failed_samples?: Array<{
    sample_value?: Array<Record<string, any>>
    condition_expr?: string
    violated_conditions?: Array<{
      column: string
      condition: string
      negated_condition: string
    }>
    condition_mode?: 'AND' | 'OR'
    rule_type?: string
    [key: string]: any
  }>
  status: 'passed' | 'failed' | 'error'
  created_at: string
}

export interface ReportSummary {
  total_rules: number
  passed_rules: number
  failed_rules: number
  error_rules?: number
  pass_rate: number
  fail_rate: number
  total_affected_rows: number
}

export interface RelationshipSummary {
  total_relationships: number
  total_tables: number
  cross_source_relationships: number
  high_confidence_relationships: number
  medium_confidence_relationships?: number
  relationship_coverage: number
  relationship_types: {
    one_to_many: number
    many_to_one: number
    [key: string]: number
  }
}

export interface QualityDimension {
  score: number
  name: string
  trend?: 'up' | 'down' | 'stable'
}

export interface CriticalFinding {
  rule_name: string
  table_name: string
  column_name?: string
  severity: SeverityLevel
  failed_count: number
  failed_rate: number
  description?: string
  recommendation?: string
  rule_id?: string
  report_id?: string
  status?: string
}

export interface Dimensions {
  completeness?: number
  uniqueness?: number
  consistency?: number
  accuracy?: number
  timeliness?: number
  validity?: number
  composite?: number  // 复合规则通过率
  [key: string]: number | undefined
}

export interface RuleResult {
  rule_name: string
  rule_type: string
  severity: string
  table_name?: string
  column_name?: string
  passed_count?: number
  failed_count?: number
  status: 'passed' | 'failed' | 'error'
}

export interface GovernanceReport {
  id: string
  datasource_id?: string
  datasource_name?: string
  database_name?: string
  schema_name?: string
  report_name: string
  execution_time: string
  rules_applied: number
  quality_score?: number
  grade?: string
  include_quality?: boolean
  include_basic_audit?: boolean
  include_relationship?: boolean
  file_status?: 'pending' | 'generating' | 'completed' | 'failed'
  has_export?: boolean
  exported_file_name?: string
  exported_file_type?: string
  file_error_msg?: string | null
  created_at: string
  // 兼容旧版字段
  scope_tables?: string[]
  summary?: ReportSummary
  dimensions?: Dimensions
  critical_findings?: CriticalFinding[]
  relationship_summary?: RelationshipSummary
  rule_results?: RuleResult[]
  recommendations?: string[]
  exported_file_path?: string
  exported_file_type_old?: 'pdf' | 'excel'
  file_size?: number
  file_created_at?: string
  execution_results?: RuleExecutionResult[]
}

export interface GovernanceReportDetail extends GovernanceReport {
  dimensions?: Dimensions
  critical_findings?: CriticalFinding[]
  rule_results?: RuleResult[]
  recommendations?: string[]
  file_error_msg?: string | null
  // 历史文件列表
  history_files?: HistoryFile[]
  // 扩展字段：质检报告详情
  basic_audit_result?: Array<{
    table: string
    schema: string
    db_type: string
    database: string
    report: Array<{
      column_name: string
      data_type: string
      total_rows: number
      null_count: number
      missing_count: number
      missing_pct: number
      empty_str_count: number
    }>
  }>
  // 扩展字段：基础空值检测详情
  basic_audit_detail?: {
    rules_count: number
    results: Array<{
      id: string
      status: 'passed' | 'failed' | 'error'
      rule_id: string | null
      severity: string
      report_id: string
      rule_mode: string
      rule_name: string
      rule_type: string
      created_at: string
      library_id: string | null
      raw_result?: Record<string, any>
      table_name: string
      column_name: string
      failed_rate: number | null
      total_count: number
      failed_count: number
      passed_count: number
      error_message: string | null
      failed_samples: any | null
      execution_source: string
      executed_sql_text: string
      execution_time_ms: number
    }>
  }
  quality_audit_result?: Array<{
    id: string
    status: 'passed' | 'failed' | 'error'
    rule_name: string
    rule_type: string
    rule_mode?: string
    severity: string
    table_name: string
    column_name?: string
    total_count: number
    passed_count: number
    failed_count: number
    failed_rate: number | null
    executed_sql_text?: string
    execution_time_ms?: number
    error_message?: string
    failed_samples?: Array<{
      sample_value?: any
      violated_conditions?: Array<{ column: string; condition: string }>
      condition_mode?: string
    }>
    raw_result?: Record<string, any>
  }>
  full_relation_discovery?: {
    cards?: Array<{
      DocInfo: { doc_id: string; title: string; table_name: string; schema_name: string }
      TableInfo: { table_name: string; fields_count: number; primary_key?: string }
      Statistics: { related_tables_count: number; total_join_fields: number; avg_confidence: number }
      Relationships: Array<{
        related_table: string
        relationship_type: string
        confidence: number
        cardinality?: string
        join_fields?: Array<{ local_field: string; remote_field: string; confidence: number; relationship_type: string }>
        join_suggestion?: { join_type: string; sample_sql?: string; join_condition?: string; use_cases?: string[] }
        business_relation?: { from_entity?: string; to_entity?: string; from_role?: string; to_role?: string; relation_description?: string }
        reasoning?: string
        evidence?: { name_match: number; llm_analyzed: boolean; type_compatible: boolean }
        fusion_suggestion?: { primary_table?: string; secondary_table?: string; fusion_strategy?: string; aggregation_hint?: string }
      }>
      JoinSummary?: string
      FusionHints?: { as_master?: string[]; as_detail?: string[]; common_joins?: string[] }
    }>
    statistics?: {
      total_tables: number
      total_relationships: number
      avg_confidence: number
      high_confidence_count: number
      relationship_types?: Record<string, number>
      cardinality_distribution?: Record<string, number>
    }
    relationships?: Array<{
      from_table: string
      from_column: string
      to_table: string
      to_column: string
      confidence: number
      cardinality?: string
      relationship_type: string
      reasoning?: string
      evidence?: { name_match: number; llm_analyzed: boolean; type_compatible: boolean }
      business_relation?: { from_entity?: string; to_entity?: string; from_role?: string; to_role?: string; relation_description?: string }
      join_suggestion?: { join_type: string; sample_sql?: string; join_condition?: string; use_cases?: string[] }
      fusion_suggestion?: { primary_table?: string; secondary_table?: string; fusion_strategy?: string; aggregation_hint?: string }
    }>
  }
  include_basic_audit?: boolean
  include_relationship?: boolean
}

export interface PaginatedResponse<T> {
  items: T[]
  page: number
  page_size: number
  total: number
  pages: number
}

export interface QualityOverview {
  quality_score?: number
  grade?: string
  report_count?: number
  library_count?: number
  rule_count?: number
  enabled_rule_count?: number
  dimensions?: Dimensions
  critical_findings?: CriticalFinding[]
  report_trend?: Array<{
    date: string
    count?: number
    score?: number
    avg_score?: number
  }>
  rule_type_stats?: Array<{
    type: string
    type_name?: string
    count: number
    percentage?: number
  }>
  date_range?: {
    start?: string
    end?: string
    range?: string
  }
}

// 历史文件类型
export interface HistoryFile {
  id: string
  report_id: string
  file_name: string
  file_type: string
  file_size: number
  created_at: string
}

// 报告删除返回数据
export interface GovernanceReportDeleteResponse {
  report_id: string
  rule_execution_results_cleared: string
  table_relationships_deleted: number
  table_relationship_cards_deleted: number
}

export interface GovernanceReportDeleteResult {
  code: number
  msg: string
  data: GovernanceReportDeleteResponse | null
  http_status?: number
}

export interface GovernanceReportGenerateResponse {
  report_id: string
  report_name: string
  quality_score: number
  grade: string
  summary: ReportSummary
  relationship_summary?: RelationshipSummary
}

export interface GovernanceLibraryCreatePayload {
  name: string
  description?: string
  datasource_id: string
}

export interface GovernanceLibraryUpdatePayload {
  name?: string
  description?: string
  status?: 'active' | 'inactive'
}

export interface GovernanceRuleCreatePayload {
  library_id?: string
  rule_name: string
  rule_type?: RuleType  // AI模式可为空，由rule_config提供
  target_table?: string | null
  target_column?: string | null
  condition_expr?: string
  conditions_config?: string | Record<string, any> | Array<Record<string, any>>
  conditions?: GovernanceRuleCondition[]
  condition_mode?: 'AND' | 'OR'
  severity?: SeverityLevel
  description?: string
  create_source?: RuleCreateSource
  enabled?: boolean
  sql_text?: string  // 用于存储原始SQL语句
  // Template mode specific fields
  template_id?: string
  // AI模式专用
  sql_preview?: string
  rule_config?: {
    rule_type: string
    target_table?: string | null
    target_column?: string | null
    condition_expr?: string
    severity?: SeverityLevel | string
    conditions?: GovernanceRuleCondition[]
    condition_mode?: 'AND' | 'OR'
  }
}

export interface GovernanceRuleUpdatePayload extends GovernanceRuleCreatePayload {}

export interface GovernanceReportGeneratePayload {
  datasource_id: string
  library_ids?: string[]
  rule_ids?: string[]
  tables?: string[]
  include_basic_audit?: boolean
  include_relationship?: boolean
  report_name?: string
}

export interface GovernanceRuleCondition {
  column: string
  rule_type?: RuleType | string
  condition: string
  description?: string
}

export interface GovernanceExecuteRequest {
  datasource_id: string
  library_ids?: string[]
  rule_ids?: string[]
  include_basic_audit?: boolean
  include_relation_discovery?: boolean
}

export interface RelationDiscoverySummary {
  relationships_count: number
  tables_count: number
  cards_count: number
  cross_source_count: number
  is_multi_source: boolean
  statistics?: {
    relationship_types?: Record<string, number>
    avg_confidence?: number
    high_confidence_count?: number
  }
}

export interface RuleExecutionResultDetail {
  id: string
  library_id?: string
  rule_id?: string
  rule_name: string
  rule_type: string
  severity: SeverityLevel
  table_name: string
  column_name?: string | null
  total_count: number
  passed_count: number
  failed_count: number
  failed_rate: number
  status: 'passed' | 'failed' | 'error'
  created_at?: string
  failed_samples?: Array<{
    sample_value?: Array<Record<string, any>>
    condition_expr?: string
    violated_conditions?: Array<{
      column: string
      condition: string
      negated_condition: string
    }>
    condition_mode?: 'AND' | 'OR'
    rule_type?: string
    [key: string]: any
  } | null>
  // 新增字段
  rule_mode?: 'scoped_single' | 'scoped_multi_cond' | 'unscoped'
  executed_sql_text?: string
  execution_time_ms?: number
  raw_result?: Record<string, any>
  error_message?: string
  // execution_source: 标识结果来源 (rule_library: 规则库质检, basic_audit: 基础空值检测)
  execution_source?: 'rule_library' | 'basic_audit'
}

export interface GovernanceExecuteResponse {
  code: number
  msg: string
  data: {
    report_id: string
    quality_score: number
    grade: string
    summary: {
      total_rules: number
      passed_rules: number
      failed_rules: number
      error_rules: number
      quality_score: number
      grade: string
    }
    // 新版新增：基础审计信息（表级汇总）
    basic_audit?: BasicAuditData
    // 新版新增：质量审计结果（替代原来的 results 顶层字段）
    quality_audit?: {
      rules_count: number
      results: RuleExecutionResultDetail[]
    }
    // 新版新增：基础空值检测详情（execution_source='basic_audit'）
    basic_audit_detail?: {
      tables_count: number
      results: RuleExecutionResultDetail[]
    }
    // 保留旧版 results 字段以兼容
    results?: RuleExecutionResultDetail[]
    // 扩展的关系发现数据
    relation_discovery?: RelationDiscoveryDetail
  }
}

// 新增：基础审计数据结构
export interface BasicAuditData {
  tables_count: number
  tables: Array<{
    db_type: string
    database: string
    schema: string
    table: string
    report: Array<{
      column_name: string
      data_type: string
      total_rows: number
      null_count: number
      empty_str_count: number
      missing_count: number
      missing_pct: number
    }>
  }>
}

// 新增：扩展的关系发现详情
export interface RelationDiscoveryDetail {
  tables_count: number
  relationships_count: number
  cards_count: number
  statistics?: {
    total_tables: number
    total_relationships: number
    total_table_pairs: number
    cross_source_table_pairs: number
    tables_with_relationships: number
    tables_without_relationships: number
    relationship_types?: Record<string, number>
    cardinality_distribution?: {
      one_to_many: number
      many_to_one: number
      one_to_one: number
      many_to_many?: number
    }
    avg_confidence?: number
    high_confidence_count?: number
    low_confidence_count?: number
  }
  relationships?: Array<{
    from_table: string
    from_column: string
    to_table: string
    to_column: string
    confidence: number
    cardinality: string
    relationship_type: string
    reasoning?: string  // 推理过程说明
    evidence?: {
      llm_analyzed?: boolean
      name_match?: number
      type_compatible?: boolean
    }
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
    is_cross_source?: boolean
    from_datasource_id?: string
    to_datasource_id?: string
    from_datasource_name?: string
    to_datasource_name?: string
    from_schema_hash?: string
    to_schema_hash?: string
  }>
  cards?: Array<{
    DocInfo: {
      doc_id: string
      title: string
      source_type: string
      datasource_id: string
      schema_name: string
      table_name: string
    }
    TableInfo: {
      table_name: string
      fields_count: number
      primary_key?: string
    }
    Relationships: Array<{
      related_table: string
      relationship_type: string
      confidence: number
      join_fields: Array<{
        local_field: string
        remote_field: string
        confidence: number
      }>
    }>
    Statistics: {
      related_tables_count: number
      total_join_fields: number
      avg_confidence: number
    }
  }>
}

// 保留旧版 RelationDiscoverySummary 用于兼容
// 注意：此接口已在 459-470 行定义，此处保留仅为兼容旧代码
// 如有需要使用，请引用上方的 RelationDiscoveryDetail 接口中的 statistics 字段

export interface GovernanceReportGenerateRequest {
  report_id: string
  file_name?: string
  format?: 'docx' | 'pdf' | 'xlsx' | 'md'
}

export interface GovernanceReportGenerateResponseV2 {
  report_id: string
  exported_file_path: string
  file_name: string
  file_size: number
  format: string
  mode: string
}

export interface GovernanceReportStatusResponse {
  code: number
  data: {
    report_id: string
    file_status: 'pending' | 'generating' | 'completed' | 'failed'
    file_error_msg?: string | null
    exported_file_name?: string | null
    file_size?: number | null
    exported_file_path?: string | null
  }
}

export interface GovernanceRuleParsePayload {
  user_input: string
  datasource_id: string
  target_table?: string
  target_column?: string
  selected_table?: string
  selected_column?: string
  inferred_columns?: Array<{ column: string; reason?: string }>
  target_columns?: string  // 多列参数（逗号分隔），触发 multi_preview
  mode?: 'auto' | 'llm' | 'pattern'
  db_type?: string
}

export interface GovernanceRuleParsePrimaryResult {
  rule_type: string
  target_table?: string | null
  target_column?: string | null
  condition_expr?: string
  severity?: SeverityLevel | string
  confidence?: number
  needs_confirmation?: boolean
  reasoning?: string
  conditions?: GovernanceRuleCondition[]
  condition_mode?: 'AND' | 'OR'
}

export interface GovernanceRuleParseInferredColumn {
  column: string
  reason?: string
  data_type?: string
  comment?: string
}

export interface GovernanceRuleParseCandidateItem {
  name: string
  score: number
  reason: string
  description?: string
  data_type?: string
  comment?: string
  inferred_column?: string | null  // 旧版字符串格式
  inferred_columns?: string[] | GovernanceRuleParseInferredColumn[]  // 兼容字符串数组或对象数组
  inferred_column_names?: string | null  // 新版逗号分隔格式
  inferred_columns_detail?: GovernanceRuleParseInferredColumn[]  // 新版详细数组
  column_reasoning?: string | null
  from_card?: boolean
  is_view?: boolean
  // multi_column 场景新增字段
  rule_type?: string  // 推测的规则类型，如 "null_check"
  condition_hint?: string  // 原始自然语言描述
}

export interface GovernanceRuleParseCandidates {
  type: 'table' | 'column' | 'multi_column'  // multi_column: 多列候选
  items: GovernanceRuleParseCandidateItem[]
}

// 多条规则预览配置（multi_preview 阶段使用）
export interface GovernanceRuleParseMultiConfig {
  target_column: string
  rule_type: string
  condition_expr: string
  severity: string
  confidence: number
  reasoning: string
  sql_preview: string
}

export type ParseStage = 'table_selection' | 'column_selection' | 'multi_column_selection' | 'rule_preview' | 'multi_preview'

export interface GovernanceRuleParseResponseData {
  success: boolean
  needs_confirmation: boolean
  stage?: ParseStage  // 新版阶段标识
  scope_type?: string  // 保留兼容旧版
  confidence?: number
  rule_config?: GovernanceRuleParsePrimaryResult | null
  rule_configs?: GovernanceRuleParseMultiConfig[] | null  // 新增：multi_preview 阶段的多规则配置
  candidates?: GovernanceRuleParseCandidates | null
  sql_preview?: string | null
  reasoning?: string
  target_table?: string | null
  target_column?: string | null
}

export interface GovernanceRulePreviewPayload {
  library_id?: string
  rule_type: RuleType | string
  target_table?: string
  target_column?: string
  condition_expr?: string
  conditions?: Array<{
    column: string
    condition: string
  }>
  condition_mode?: 'AND' | 'OR'
  db_type?: string
  // Template mode specific fields
  template_id?: string
}

export interface GovernanceRulePreviewResponseData {
  success: boolean
  sql: string
}

// 新版规则建议接口类型 (LLM 模式)
export interface GovernanceRuleSuggestionItemV2 {
  table: string
  column: string
  column_comment: string
  data_type: string
  rule_type: string
  rule_name: string
  rule_description: string
  confidence: number
  reasoning: string
}

export interface GovernanceRuleSuggestResponseDataV2 {
  success: boolean
  source: string  // 'llm' | 'pattern' 等
  suggestions: GovernanceRuleSuggestionItemV2[]
}

// 旧版规则建议接口类型（保留以备兼容）
export interface GovernanceRuleSuggestionItem {
  type: string
  name: string
}

export interface GovernanceRuleSuggestion {
  table: string
  column_pattern: string
  suggested_rules: GovernanceRuleSuggestionItem[]
}

export interface GovernanceRuleSuggestResponseData {
  success: boolean
  suggestions: GovernanceRuleSuggestion[]
}

export interface GovernanceDatasourceTable {
  name?: string
  table_name?: string
  type: 'TABLE' | 'VIEW' | string
  description?: string
  column_count?: number
  columns?: string[]
}

export interface GovernanceDatasourceColumn {
  name?: string
  column_name?: string
  type?: string
  data_type?: string
  nullable?: boolean
  is_nullable?: boolean
  default?: string | null
  default_value?: string | null
  comment?: string | null
  description?: string | null
  is_primary?: boolean
  is_primary_key?: boolean
}

export interface GovernanceDatasourceTablesResponseData {
  tables: GovernanceDatasourceTable[]
  total: number
}

export interface GovernanceDatasourceColumnsResponseData {
  table_name: string
  columns: GovernanceDatasourceColumn[]
  total: number
}

const BASE_PATH = '/governance'

export const getGovernanceLibraries = (params?: { page?: number; page_size?: number; search?: string; datasource_id?: string }) =>
  get<{ code: number; msg: string; data: PaginatedResponse<GovernanceLibrary> }>(`${BASE_PATH}/libraries`, { params })

export const getGovernanceLibrary = (libraryId: string) =>
  get<{ code: number; msg: string; data: GovernanceLibrary }>(`${BASE_PATH}/libraries/${libraryId}`)

export const createGovernanceLibrary = (data: GovernanceLibraryCreatePayload) =>
  post<{ code: number; msg: string; data: GovernanceLibrary }>(`${BASE_PATH}/libraries`, { body: data })

export const updateGovernanceLibrary = (libraryId: string, data: GovernanceLibraryUpdatePayload) =>
  put<{ code: number; msg: string; data: GovernanceLibrary }>(`${BASE_PATH}/libraries/${libraryId}`, { body: data })

export const deleteGovernanceLibrary = (libraryId: string) =>
  del<{ code: number; msg: string; data?: null }>(`${BASE_PATH}/libraries/${libraryId}`)

export const getGovernanceRules = (params?: { page?: number; page_size?: number; library_id?: string; rule_type?: RuleType; enabled?: boolean; search?: string; create_source?: RuleCreateSource }) =>
  get<{ code: number; msg: string; data: PaginatedResponse<GovernanceRule> }>(`${BASE_PATH}/rules`, { params })

export const getGovernanceRule = (ruleId: string) =>
  get<{ code: number; msg: string; data: GovernanceRule }>(`${BASE_PATH}/rules/${ruleId}`)

export const createGovernanceRule = (data: GovernanceRuleCreatePayload) =>
  post<{ code: number; msg: string; data: GovernanceRule }>(`${BASE_PATH}/rules`, { body: data })

export const updateGovernanceRule = (ruleId: string, data: GovernanceRuleUpdatePayload) =>
  put<{ code: number; msg: string; data: GovernanceRule }>(`${BASE_PATH}/rules/${ruleId}`, { body: data })

export const deleteGovernanceRule = (ruleId: string) =>
  del<{ code: number; msg: string; data?: null }>(`${BASE_PATH}/rules/${ruleId}`)

export const toggleGovernanceRule = (ruleId: string) =>
  put<{ code: number; msg: string; data: { id: string; enabled: boolean } }>(`${BASE_PATH}/rules/${ruleId}/toggle`)

export const executeGovernanceRule = (data: { datasource_id: string; rule_id: string }) =>
  post<{ code: number; msg: string; data: RuleExecutionResult }>(`${BASE_PATH}/rules/execute`, { body: data })

export const getRuleTemplates = (params?: { rule_type?: RuleType | string }) =>
  get<{ code: number; msg: string; data: GovernanceRuleTemplate[] }>(`${BASE_PATH}/templates`, { params })

// Get template details by ID
export const getTemplateDetail = (templateId: string) =>
  get<{ code: number; msg: string; data: GovernanceRuleTemplate }>(`${BASE_PATH}/templates/${templateId}`)

// Get templates grouped by rule type (for template mode selection)
export interface GovernanceTemplateGroup {
  rule_type: string
  rule_type_name: string
  templates: GovernanceRuleTemplate[]
}

export interface GovernanceTemplatesGroupedResponse {
  groups: GovernanceTemplateGroup[]
  total: number
}

export const getRuleTemplatesGrouped = (params?: { keyword?: string }) =>
  get<{ code: number; msg: string; data: GovernanceTemplatesGroupedResponse }>(`${BASE_PATH}/templates`, { params: { group_by: 'rule_type', ...params } })

export interface GovernanceRuleImportPayload {
  library_id: string
  template_ids: string[]
  target_table?: string
  target_column?: string
  override_name?: boolean
}

export const importRulesFromTemplate = (data: GovernanceRuleImportPayload) =>
  post<{ code: number; msg: string; data: { imported_count: number; rules: GovernanceRule[] } }>(`${BASE_PATH}/templates/import`, { body: data })

export const generateGovernanceReport = (data: GovernanceReportGeneratePayload) =>
  post<{ code: number; msg: string; data: GovernanceReportGenerateResponse }>(`${BASE_PATH}/report`, { body: data })

export const executeGovernanceRules = (data: GovernanceExecuteRequest) =>
  post<{ code: number; msg: string; data: GovernanceExecuteResponse['data'] }>(`${BASE_PATH}/execute`, { body: data })

export const generateGovernanceReportV2 = (data: GovernanceReportGenerateRequest) =>
  post<{ code: number; msg: string; data: GovernanceReportGenerateResponseV2 }>(`${BASE_PATH}/report`, { body: data })

export const getGovernanceReportStatus = (reportId: string) =>
  get<{ code: number; data: GovernanceReportStatusResponse['data'] }>(`${BASE_PATH}/report/${reportId}`)

export const parseGovernanceRule = (data: GovernanceRuleParsePayload) =>
  post<{ code: number; msg: string; data: GovernanceRuleParseResponseData }>(`${BASE_PATH}/rules/parse`, { body: data })

export const previewGovernanceRule = (data: GovernanceRulePreviewPayload) =>
  post<{ code: number; msg: string; data: GovernanceRulePreviewResponseData }>(`${BASE_PATH}/rules/preview`, { body: data })

export const getDatasourceTables = (datasourceId: string) =>
  get<{ code: number; msg: string; data: GovernanceDatasourceTablesResponseData }>(`${BASE_PATH}/datasources/${datasourceId}/tables`)

export const getDatasourceTableColumns = (datasourceId: string, tableName: string) =>
  get<{ code: number; msg: string; data: GovernanceDatasourceColumnsResponseData }>(`${BASE_PATH}/datasources/${datasourceId}/tables/${encodeURIComponent(tableName)}/columns`)

export const suggestGovernanceRules = (data: { datasource_id: string }) =>
  post<{ code: number; msg: string; data: GovernanceRuleSuggestResponseDataV2 }>(`${BASE_PATH}/rules/suggest`, { body: data })

export const getGovernanceReports = (params?: { page?: number; page_size?: number; datasource_id?: string }) =>
  get<{ code: number; msg: string; data: PaginatedResponse<GovernanceReport> }>(`${BASE_PATH}/reports`, { params })

export const getGovernanceReportDetail = (reportId: string) =>
  get<{ code: number; msg: string; data: GovernanceReportDetail }>(`${BASE_PATH}/reports/${reportId}`)

export const deleteGovernanceReport = (reportId: string) =>
  del<GovernanceReportDeleteResult>(`${BASE_PATH}/reports/${reportId}`)

// 修改报告名称
export interface GovernanceReportUpdateNamePayload {
  report_name: string
}

export interface GovernanceReportUpdateNameResponse {
  code: number
  msg: string
  data?: {
    report_id: string
    report_name: string
    files_updated?: number  // 本次同步更新的历史文件数
    updated_at: string
  }
}

export const updateGovernanceReportName = (reportId: string, data: GovernanceReportUpdateNamePayload) =>
  put<GovernanceReportUpdateNameResponse>(`${BASE_PATH}/reports/${reportId}`, { body: data })

// 删除单个历史导出文件记录
export const deleteGovernanceReportFile = (fileId: string) =>
  del<{ code: number; msg: string }>(`${BASE_PATH}/files/${fileId}`)

export const getQualityOverview = (params?: { datasource_id?: string; date_range?: string }) =>
  get<{ code: number; msg: string; data: QualityOverview }>(`${BASE_PATH}/quality/overview`, { params })

export const getRuleExecutionHistory = (params?: { rule_id?: string; datasource_id?: string; page?: number; page_size?: number }) =>
  get<{ code: number; msg: string; data: PaginatedResponse<RuleExecutionResult> }>(`${BASE_PATH}/quality/execution-history`, { params })

export const ruleTypeLabels: Record<string, string> = {
  null_check: '空值检测',
  unique: '唯一性检测',
  format: '格式检测',
  threshold: '阈值检测',
  enum: '枚举检测',
  custom_sql: '自定义SQL',
  length_check: '长度检测',
  range_check: '范围检测',
  date_check: '日期检测',
  consistency_check: '一致性检测',
  freshness_check: '新鲜度检测',
  value_distribution: '值分布检测',
  composite: '复合规则',
  table_stats: '表级统计',
  basic_null_check: '基础质检',
  multi_column_compare: '多列比对',
  uniqueness: '唯一性',
  completeness: '完整性',
  consistency: '一致性',
  accuracy: '准确性',
  timeliness: '时效性',
  validity: '有效性',
}

export const severityLabels: Record<string, string> = {
  critical: '严重',
  warning: '警告',
  info: '信息',
}

export const severityColors: Record<string, string> = {
  critical: '#f5222d',
  warning: '#faad14',
  info: '#1890ff',
}

export const getGradeName = (score: number | undefined): string => {
  if (score === undefined || score === null) return '暂无评估'
  if (score >= 90) return '优秀'
  if (score >= 80) return '良好'
  if (score >= 60) return '一般'
  if (score >= 40) return '较差'
  return '差'
}

export const getGradeColor = (grade: string): string => {
  switch (grade) {
    case '优秀': return '#52c41a'
    case '良好': return '#1890ff'
    case '一般': return '#faad14'
    case '较差': return '#fa8c16'
    case '差': return '#f5222d'
    default: return '#999'
  }
}

// 报告下载函数
export const downloadGovernanceReport = async (reportId: string, fileId?: string) => {
  // 如果有 file_id，添加到查询参数中
  const queryParams = fileId ? `?file_id=${encodeURIComponent(fileId)}` : ''
  const url = `${urlPrefix}/governance/reports/${reportId}/download${queryParams}`
  const token = localStorage.getItem('console_token') || ''

  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': token,
      },
      credentials: 'include',
    })

    if (!response.ok) {
      throw new Error('Download failed')
    }

    // 调试日志：输出所有响应头
    console.log('📥 下载响应 Headers:', {
      status: response.status,
      contentType: response.headers.get('content-type'),
      contentDisposition: response.headers.get('content-disposition'),
      contentDisposition2: response.headers.get('Content-Disposition'),
      allHeaders: Object.fromEntries(response.headers.entries()),
    })

    // 同时检查原始 Headers 对象
    console.log('🔍 Headers 对象原始值:', response.headers.get('content-disposition'))

    const contentDisposition = response.headers.get('content-disposition')
    let filename = `report_${reportId}.md`  // 默认文件名

    if (contentDisposition) {
      // 调试日志：输出原始 Content-Disposition
      console.log('📋 Content-Disposition 原始值:', contentDisposition)

      const filenameMatch = contentDisposition.match(/filename\*?=['"]?(?:UTF-8'')?([^;\n"']+)/i)
      console.log('🔍 正则匹配结果:', filenameMatch)

      if (filenameMatch) {
        const decodedFilename = decodeURIComponent(filenameMatch[1])
        console.log('✅ 解析后的文件名:', decodedFilename)
        filename = decodedFilename
      }
    } else {
      console.warn('⚠️ 未找到 Content-Disposition header，使用默认文件名:', filename)
    }

    const blob = await response.blob()
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)
  } catch (error) {
    console.error('Download failed:', error)
    throw error
  }
}

export const getRuleDisplayName = (rule: { rule_type: string; rule_type_name?: string }) => rule.rule_type_name || ruleTypeLabels[rule.rule_type] || rule.rule_type
export const getSeverityDisplayName = (rule: { severity: string; severity_name?: string }) => rule.severity_name || severityLabels[rule.severity] || rule.severity

export const ruleModeLabels: Record<string, string> = {
  scoped_single: '单列规则',
  scoped_multi_cond: '多条件规则',
  unscoped: '全局规则',
}

export const ruleModeColors: Record<string, string> = {
  scoped_single: '#1890ff',
  scoped_multi_cond: '#722ed1',
  unscoped: '#fa8c16',
}

export const ruleModeDescriptions: Record<string, string> = {
  scoped_single: '单列/单条件规则',
  scoped_multi_cond: '多条件规则',
  unscoped: '全局规则，批量执行',
}

export const triggerTypeLabels: Record<string, string> = {
  manual: '手动触发',
  scheduled: '定时触发',
  realtime: '实时触发',
}

// 关系类型中文映射
export const relationshipTypeLabels: Record<string, string> = {
  foreign_key: '外键关联',
  FK: '外键关联',
  semantic: '语义关系',
  Semantic: '语义关系',
  shared_field: '共享字段',
  same_name: '同名关联',
  value_overlap: '值域重叠',
  Value: '值域关联',
}

// 基数类型中文映射
export const cardinalityLabels: Record<string, string> = {
  one_to_one: '一对一',
  one_to_many: '一对多',
  many_to_one: '多对一',
  many_to_many: '多对多',
}

export const executionSourceLabels: Record<string, string> = {
  rule_library: '规则库质检',
  basic_audit: '基础质检',
}

export const executionSourceColors: Record<string, string> = {
  rule_library: '#1890ff',
  basic_audit: '#722ed1',
}

// 关系类型颜色配置
export const relationshipTypeColors: Record<string, string> = {
  foreign_key: '#52c41a',
  FK: '#52c41a',
  semantic: '#722ed1',
  Semantic: '#722ed1',
  shared_field: '#1890ff',
  same_name: '#fa8c16',
  value_overlap: '#faad14',
  Value: '#faad14',
}

// 基数类型颜色配置
export const cardinalityColors: Record<string, string> = {
  one_to_one: '#52c41a',
  one_to_many: '#1890ff',
  many_to_one: '#722ed1',
  many_to_many: '#fa8c16',
}
