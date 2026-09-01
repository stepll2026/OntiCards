import { get, put, del } from './base'

/**
 * 系统配置项
 */
export interface SystemConfigItem {
  id: string
  config_key: string
  config_value: string
  description: string
  created_at: string
  updated_at: string
}

/**
 * 获取系统配置响应（单个）
 */
export interface SystemConfigResponse {
  code: number
  msg?: string
  message?: string
  data: SystemConfigItem
}

/**
 * 获取系统配置响应（全部）
 */
export interface SystemConfigListResponse {
  code: number
  msg?: string
  message?: string
  data: {
    configs: SystemConfigItem[]
  }
}

/**
 * 更新系统配置请求
 */
export interface UpdateSystemConfigParams {
  key: string
  value: string
  description?: string
}

/**
 * 更新系统配置响应
 */
export interface UpdateSystemConfigResponse {
  code: number
  msg?: string
  message?: string
  data: {
    config_key: string
    config_value: string
    message: string
  }
}

/**
 * 删除系统配置参数
 */
export interface DeleteSystemConfigParams {
  key: string
}

/**
 * 删除系统配置响应
 */
export interface DeleteSystemConfigResponse {
  code: number
  msg?: string
  message?: string
  data: {
    config_key: string
    message: string
  }
}

/**
 * Token价格配置
 */
export interface TokenPriceConfig {
  embedding: {
    key: string
    value: string
    description: string
  }
  rerank: {
    key: string
    value: string
    description: string
  }
  llm_input: {
    key: string
    value: string
    description: string
  }
  llm_output: {
    key: string
    value: string
    description: string
  }
}

/**
 * 获取Token价格配置响应
 */
export interface TokenPricesResponse {
  code: number
  msg?: string
  message?: string
  data: TokenPriceConfig
}

/**
 * 更新Token价格配置请求
 */
export interface UpdateTokenPricesParams {
  embedding?: number
  rerank?: number
  llm_input?: number
  llm_output?: number
}

/**
 * 更新Token价格配置响应
 */
export interface UpdateTokenPricesResponse {
  code: number
  msg?: string
  message?: string
  data: {
    message: string
    updated: Array<{ key: string; value: string }>
  }
}

/**
 * 数据保留配置
 */
export interface DataRetentionConfig {
  scope?: 'system' | 'user'
  user_id?: string
  query_logs_retention_days: {
    value: string
    description: string
    unit: string
  }
  stats_retention_days: {
    value: string
    description: string
    unit: string
  }
}

/**
 * 获取数据保留配置响应
 */
export interface DataRetentionResponse {
  code: number
  msg?: string
  message?: string
  data: DataRetentionConfig
}

/**
 * 更新数据保留配置请求
 */
export interface UpdateDataRetentionParams {
  query_logs_retention_days?: number
  stats_retention_days?: number
  user_id?: string
}

/**
 * 更新数据保留配置响应
 */
export interface UpdateDataRetentionResponse {
  code: number
  msg?: string
  message?: string
  data: {
    message: string
    scope?: 'system' | 'user'
    user_id?: string
    updated: Array<{ key: string; value: string }>
  }
}

/**
 * 获取系统配置（单个或全部）
 */
export const getSystemConfig = (key?: string) => {
  if (key) {
    return get<SystemConfigResponse>('/system_config/config', { params: { key } })
  }
  return get<SystemConfigListResponse>('/system_config/config')
}

/**
 * 更新系统配置
 */
export const updateSystemConfig = (params: UpdateSystemConfigParams) => {
  return put<UpdateSystemConfigResponse>('/system_config/config', { body: params })
}

/**
 * 删除系统配置
 */
export const deleteSystemConfig = (params: DeleteSystemConfigParams) => {
  return del<DeleteSystemConfigResponse>('/system_config/config', { body: params })
}

/**
 * 获取Token价格配置
 */
export const getTokenPrices = () => {
  return get<TokenPricesResponse>('/system_config/token_prices')
}

/**
 * 更新Token价格配置
 */
export const updateTokenPrices = (params: UpdateTokenPricesParams) => {
  return put<UpdateTokenPricesResponse>('/system_config/token_prices', { body: params })
}

/**
 * 获取数据保留配置
 */
export const getDataRetention = (userId?: string) => {
  return get<DataRetentionResponse>('/system_config/data_retention', {
    params: userId ? { user_id: userId } : undefined
  })
}

/**
 * 更新数据保留配置
 */
export const updateDataRetention = (params: UpdateDataRetentionParams) => {
  const { user_id, ...rest } = params
  return put<UpdateDataRetentionResponse>('/system_config/data_retention', {
    body: user_id ? { ...rest, user_id } : rest
  })
}
