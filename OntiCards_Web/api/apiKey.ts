import { get, post, put, del } from './base'

/**
 * API Key 状态类型
 */
export type ApiKeyStatus = 'active' | 'disabled'

/**
 * API Key 数据项
 */
export interface ApiKeyItem {
  id: string
  user_id: string
  name: string
  api_key: string
  status: ApiKeyStatus
  expires_at: string | null
  last_used_at: string | null
  created_at: string | null
  updated_at: string | null
}

/**
 * 查询 API Key 响应
 */
export interface ApiKeyListResponse {
  code: number
  msg?: string
  message?: string
  data: ApiKeyItem[] | ApiKeyItem
}

/**
 * 创建 API Key 响应
 */
export interface ApiKeyCreateResponse {
  code: number
  msg?: string
  message?: string
  data: {
    id: string
    api_key: string
  }
}

/**
 * 修改/删除 API Key 响应
 */
export interface ApiKeyMutationResponse {
  code: number
  msg?: string
  message?: string
  data?: {
    id: string
  }
}

/**
 * 创建 API Key 参数
 */
export interface CreateApiKeyParams {
  user_id: string
  name: string
  api_key?: string
  expires_at?: string | null
}

/**
 * 修改 API Key 参数
 */
export interface UpdateApiKeyParams {
  id: string
  name?: string
  status?: ApiKeyStatus
  expires_at?: string | null
}

/**
 * 删除 API Key 参数
 */
export interface DeleteApiKeyParams {
  id: string
}

/**
 * 按 id 查询单条 API Key
 */
export const getApiKeyById = (id: string) => {
  return get<ApiKeyListResponse>('/api_keys', {
    params: { id },
  })
}

/**
 * 按 user_id 查询该用户下的所有 API Keys
 */
export const getApiKeysByUserId = (user_id: string) => {
  return get<ApiKeyListResponse>('/api_keys', {
    params: { user_id },
  })
}

/**
 * 创建 API Key
 */
export const createApiKey = (body: CreateApiKeyParams) => {
  return post<ApiKeyCreateResponse>('/api_keys', {
    body,
  })
}

/**
 * 修改 API Key
 */
export const updateApiKey = (body: UpdateApiKeyParams) => {
  return put<ApiKeyMutationResponse>('/api_keys', {
    body,
  })
}

/**
 * 删除 API Key
 */
export const deleteApiKey = (body: DeleteApiKeyParams) => {
  return del<ApiKeyMutationResponse>('/api_keys', {
    body,
  })
}
