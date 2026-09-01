import { get, post, put, del } from '@/api/base'

/**
 * 版本更新日志数据结构
 */
export interface ChangelogItem {
  id: number
  version: string
  title: string
  content_md: string
  status: 'public' | 'hidden'
  created_at: string
  updated_at: string
}

/**
 * 版本更新日志响应数据结构
 */
export interface ChangelogResponse {
  code: number
  msg: string
  data: ChangelogItem[]
}

/**
 * 单条日志响应数据结构
 */
export interface SingleChangelogResponse {
  code: number
  msg: string
  data: ChangelogItem
}

/**
 * 操作响应数据结构
 */
export interface OperationResponse {
  code: number
  msg: string
  data?: { id: number }
}

/**
 * 创建/更新日志的参数类型
 */
export interface CreateChangelogParams {
  version: string
  title: string
  content_md: string
  status?: 'public' | 'hidden'
}

export interface UpdateChangelogParams {
  version?: string
  title?: string
  content_md?: string
  status?: 'public' | 'hidden'
}

/**
 * 获取所有版本更新日志
 * @export
 */
export function getChangelog(): Promise<ChangelogResponse> {
  return get<ChangelogResponse>('/changelog')
}

/**
 * 获取单条版本更新日志
 * @param id 日志ID
 * @export
 */
export function getChangelogById(id: number): Promise<SingleChangelogResponse> {
  return get<SingleChangelogResponse>(`/changelog/${id}`)
}

/**
 * 创建版本更新日志
 * @param params 创建参数
 * @export
 */
export function createChangelog(params: CreateChangelogParams): Promise<OperationResponse> {
  return post<OperationResponse>('/changelog', { body: params })
}

/**
 * 更新版本更新日志
 * @param id 日志ID
 * @param params 更新参数
 * @export
 */
export function updateChangelog(id: number, params: UpdateChangelogParams): Promise<OperationResponse> {
  return put<OperationResponse>(`/changelog/${id}`, { body: params })
}

/**
 * 删除版本更新日志
 * @param id 日志ID
 * @export
 */
export function deleteChangelog(id: number): Promise<OperationResponse> {
  return del<OperationResponse>(`/changelog/${id}`)
}

