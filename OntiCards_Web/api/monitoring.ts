import { get } from './base'

// ==================== 监控总览类型 ====================

export interface Recent24hStats {
  total_queries: number
  success_queries: number
  error_queries: number
  timeout_queries: number
  success_rate: number
  avg_duration_ms: number
  total_tokens: number
  embedding_tokens: number
  rerank_tokens: number
  llm_tokens: number
}

export interface TodayStats {
  total_queries: number
  success_queries: number
  total_tokens: number
}

export interface DailyTrendItem {
  date: string
  total_queries: number
  success_queries: number
  error_queries: number
  success_rate: number
  total_tokens: number
  avg_duration_ms: number
  cost_yuan: number
  cost_version: string
}

export interface Summary30d {
  total_queries: number
  total_tokens: number
  total_cost_yuan: number
}

export interface ComparisonItem {
  queries_change: number
  queries_change_rate: string
  tokens_change: number
  tokens_change_rate: string
  avg_duration_change: number
  avg_duration_change_rate: string
  is_positive: boolean
}

export interface HourlyDistribution {
  peak_hour: number
  peak_hour_label: string
  off_peak_hour: number
  off_peak_hour_label: string
  distribution: Array<{
    hour: number
    label: string
    queries: number
    percentage: number
  }>
}

export interface TopDatasource {
  datasource_name: string
  query_count: number
  percentage: number
  avg_duration_ms: number
}

export interface DatasourceStats {
  total_datasources_used: number
  top_datasources: TopDatasource[]
}

export interface StatusBreakdownItem {
  count: number
  percentage: number
  avg_duration_ms: number
  top_errors?: string[]
}

export interface StatusBreakdown {
  success: StatusBreakdownItem
  error: StatusBreakdownItem
  timeout: StatusBreakdownItem
}

export interface QualityMetrics {
  avg_cards_recalled: number
  avg_cards_selected: number
  avg_top1_score: number
  avg_result_count: number
  zero_result_rate: number
}

export interface MonitoringOverviewData {
  recent_24h: Recent24hStats
  today: TodayStats
  daily_trend: DailyTrendItem[]
  summary_30d: Summary30d
  cost_note: string
  comparison?: {
    vs_yesterday: ComparisonItem
    vs_last_week: ComparisonItem
  }
  hourly_distribution?: HourlyDistribution
  datasource_stats?: DatasourceStats
  status_breakdown?: StatusBreakdown
  quality_metrics?: QualityMetrics
}

export interface MonitoringOverviewResponse {
  code: number
  msg?: string
  message?: string
  data: MonitoringOverviewData
}

export interface MonitoringOverviewParams {
  user_id?: string
  workspace_id?: string
}

// ==================== 趋势分析类型 ====================

export interface TrendDayItem {
  date: string
  total_queries: number
  success_queries: number
  error_queries: number
  timeout_queries: number
  success_rate: number
  tokens: {
    embedding: number
    rerank: number
    llm: number
    total: number
  }
  cost_yuan: number
  cost_version: string
  performance: {
    avg_duration_ms: number
    min_duration_ms: number
    max_duration_ms: number
    avg_vector_search_ms: number
    avg_rerank_ms: number
    avg_llm_gen_sql_ms: number
    avg_sql_execution_ms: number
  }
  quality: {
    avg_cards_recalled: number
    avg_cards_selected: number
    avg_top1_rerank_score: number
  }
}

export interface TrendStatistics {
  total_days: number
  data_days: number
  missing_days: number
  total_queries: number
  total_tokens: number
  total_cost_yuan: number
  avg_daily_queries: number
  avg_daily_tokens: number
  avg_success_rate: number
}

export interface GrowthAnalysisItem {
  queries_change: number
  queries_change_rate: string
  tokens_change: number
  tokens_change_rate: string
  cost_change: number
  cost_change_rate: string
  trend: 'growth' | 'decline' | 'stable'
}

export interface GrowthAnalysis {
  week_over_week: GrowthAnalysisItem
  month_over_month: GrowthAnalysisItem
}

export interface PeakDayInfo {
  date: string
  queries: number
  reason?: string
}

export interface PeakHourInfo {
  hour: number
  label: string
  query_count: number
  avg_duration_ms: number
}

export interface PeakValley {
  peak_day: PeakDayInfo
  valley_day: PeakDayInfo
  peak_hours: PeakHourInfo[]
}

export interface WeeklyPatternItem {
  weekday: number
  label: string
  avg_queries: number
  is_workday: boolean
}

export interface WeeklyPattern {
  pattern: WeeklyPatternItem[]
  workday_avg: number
  weekend_avg: number
  workday_ratio: number
}

export interface MonitoringTrendData {
  days: number
  items: TrendDayItem[]
  statistics?: TrendStatistics
  growth_analysis?: GrowthAnalysis
  peak_valley?: PeakValley
  weekly_pattern?: WeeklyPattern
}

export interface MonitoringTrendResponse {
  code: number
  msg?: string
  message?: string
  data: MonitoringTrendData
}

export interface MonitoringTrendParams {
  user_id?: string
  workspace_id?: string
  days?: number
}

// ==================== 实时监控类型 ====================

export interface RealtimeSummary {
  total_queries: number
  avg_duration_ms: number
  total_tokens: number
}

export interface RealtimeMinuteData {
  time: string
  count: number
  avg_duration_ms: number
}

export interface CurrentStatus {
  overall: 'healthy' | 'warning' | 'critical'
  status_text: string
  status_color: string
  uptime_seconds?: number
  last_query_time?: string
  consecutive_success: number
  consecutive_errors: number
}

export interface QpsStats {
  current_qps: number
  avg_qps_1m: number
  avg_qps_5m: number
  avg_qps_15m?: number
  max_qps: number
  min_qps?: number
}

export interface RecentError {
  time: string
  type: 'error' | 'timeout'
  datasource?: string
  message: string
  count: number
}

export interface TopErrorType {
  type: string
  count: number
  percentage: number
}

export interface ErrorAlerts {
  total_errors_1h: number
  error_rate: number
  timeout_rate?: number
  recent_errors: RecentError[]
  top_error_types: TopErrorType[]
}

export interface QuerySample {
  id: string
  question: string
  duration_ms: number
  tokens: number
  datasources?: string[]
  status?: 'success' | 'error'
  error_type?: string
  error_message?: string
  time: string
}

export interface RecentQueries {
  success_samples: QuerySample[]
  error_samples: QuerySample[]
}

export interface DatasourceHealthItem {
  name: string
  status: 'healthy' | 'degraded' | 'critical'
  queries_1h: number
  avg_latency_ms: number
  error_count: number
  error_rate: number
  reason?: string
}

export interface DatasourceHealth {
  datasources: DatasourceHealthItem[]
}

export interface MonitoringRealtimeData {
  summary: RealtimeSummary
  minute_data: RealtimeMinuteData[]
  current_status?: CurrentStatus
  qps_stats?: QpsStats
  error_alerts?: ErrorAlerts
  recent_queries?: RecentQueries
  datasource_health?: DatasourceHealth
}

export interface MonitoringRealtimeResponse {
  code: number
  msg?: string
  message?: string
  data: MonitoringRealtimeData
}

export interface MonitoringRealtimeParams {
  user_id?: string
  workspace_id?: string
}

// ==================== 性能分析类型 ====================

export interface StageAverages {
  vector_search_ms: number
  rerank_ms: number
  llm_gen_sql_ms: number
  sql_execution_ms: number
  total_avg_ms: number
}

export interface SlowQueryItem {
  id: string
  question: string
  duration_ms: number
  tokens: number
  created_at: string
}

export interface LatencyDistributionItem {
  range: string
  count: number
  percentage: number
}

export interface LatencyDistribution {
  distribution: LatencyDistributionItem[]
}

export interface StageBreakdownItem {
  name: string
  label: string
  avg_ms: number
  percentage: number
  trend: 'increasing' | 'stable' | 'decreasing'
  trend_rate?: string
}

export interface StageBreakdown {
  total_avg_ms: number
  stages: StageBreakdownItem[]
}

export interface DatasourcePerformanceItem {
  name: string
  query_count: number
  avg_duration_ms: number
  min_duration_ms: number
  max_duration_ms: number
  avg_sql_execution_ms: number
  usage_rank: number
}

export interface DatasourcePerformance {
  datasources: DatasourcePerformanceItem[]
}

export interface PerformanceTrendComparison {
  vector_search_change: string
  rerank_change: string
  llm_gen_sql_change: string
  sql_execution_change: string
  overall_change: string
  trend: 'increasing' | 'stable' | 'decreasing'
}

export interface DailyPerformanceTrend {
  date: string
  avg_duration_ms: number
}

export interface PerformanceTrend {
  vs_last_period: PerformanceTrendComparison
  daily_trend: DailyPerformanceTrend[]
}

export interface ComplexityDistributionItem {
  type: string
  label: string
  count: number
  percentage: number
  avg_duration_ms: number
}

export interface QueryPatterns {
  fast_queries_pct: number
  slow_queries_pct: number
  complexity_distribution: ComplexityDistributionItem[]
}

export interface MonitoringPerformanceData {
  period_days: number
  stage_averages: StageAverages
  slow_queries_top10: SlowQueryItem[]
  latency_distribution?: LatencyDistribution
  stage_breakdown?: StageBreakdown
  datasource_performance?: DatasourcePerformance
  performance_trend?: PerformanceTrend
  query_patterns?: QueryPatterns
}

export interface MonitoringPerformanceResponse {
  code: number
  msg?: string
  message?: string
  data: MonitoringPerformanceData
}

export interface MonitoringPerformanceParams {
  user_id?: string
  workspace_id?: string
  days?: number
}

// ==================== API 函数 ====================

export const getMonitoringOverview = (params: MonitoringOverviewParams) => {
  return get<MonitoringOverviewResponse>('/monitoring/overview', { params })
}

export const getMonitoringTrend = (params: MonitoringTrendParams) => {
  return get<MonitoringTrendResponse>('/monitoring/trend', { params })
}

export const getMonitoringRealtime = (params: MonitoringRealtimeParams) => {
  return get<MonitoringRealtimeResponse>('/monitoring/realtime', { params })
}

export const getMonitoringPerformance = (params: MonitoringPerformanceParams) => {
  return get<MonitoringPerformanceResponse>('/monitoring/performance', { params })
}
