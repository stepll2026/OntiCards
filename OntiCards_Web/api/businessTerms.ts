// 业务术语库相关接口定义

import { request, get, post, put, del } from './base'

// ===== 类型定义 =====

// 术语库
export interface BusinessTermLibrary {
  id: string
  name: string
  description?: string
  category?: string
  status: 'active' | 'inactive'
  term_count: number
  created_by?: string
  created_at: string
  updated_at: string
}

// 术语
export interface BusinessTerm {
  id: string
  library_id: string
  library_name?: string
  term_name: string
  term_alias: string[]
  term_definition: string
  applicable_conditions?: string
  remarks?: string
  related_datacards: Array<{ id: string; name: string }>
  related_fields: Array<{ table: string; field: string }>
  related_terms: Array<{ id: string; name: string }>
  status: 'active' | 'inactive'
  created_by?: string
  created_at: string
  updated_at: string
}

// 数据源-术语库关联
export interface DataSourceTermLibrary {
  id: string
  datasource_id: string
  library_id: string
  library_name: string
  library_category?: string
  library_description?: string
  library_status?: string
  library_term_count: number
  is_enabled: boolean
  added_by?: string
  added_at: string
  updated_at?: string
}

// 模板分类项
export interface TemplateCategory {
  category: string
  templates: Array<{
    template_name: string
    count: number
    preview_terms?: string[]  // 术语预览
  }>
}

// 模板项
export interface TermTemplate {
  id: string
  category: string
  template_name: string
  term_name: string
  term_alias: string[]
  term_definition: string
  applicable_conditions?: string
  remarks?: string
}

// ===== 响应类型 =====

// 通用分页响应
export interface PaginatedResponse<T> {
  code: number
  msg: string
  data: {
    items: T[]
    pagination: {
      page: number
      page_size: number
      total: number
      total_pages: number
    }
  }
}

// 术语库列表响应（带分页）
export interface LibraryListResponse {
  code: number
  msg: string
  data: {
    items: BusinessTermLibrary[]
    pagination: {
      page: number
      page_size: number
      total: number
      total_pages: number
    }
  }
}

// 术语库详情响应
export interface LibraryDetailResponse {
  code: number
  msg: string
  data: BusinessTermLibrary & {
    terms: BusinessTerm[]
    terms_pagination: {
      page: number
      page_size: number
      total: number
      total_pages: number
    }
  }
}

// 术语列表响应
export interface TermListResponse {
  code: number
  msg: string
  data: {
    items: BusinessTerm[]
    pagination: {
      page: number
      page_size: number
      total: number
      total_pages: number
    }
  }
}

// 模板分类响应
export interface TemplateCategoriesResponse {
  code: number
  msg: string
  data: {
    categories: TemplateCategory[]
  }
}

// 模板列表响应
export interface TemplateListResponse {
  code: number
  msg: string
  data: {
    items: TermTemplate[]
    total: number
  }
}

// 导入响应
export interface ImportResponse {
  code: number
  msg: string
  data: {
    imported_count: number
    skipped_count: number
    message: string
  }
}

// 数据源术语库响应
export interface DataSourceLibrariesResponse {
  code: number
  msg: string
  data: {
    items: DataSourceTermLibrary[]
    pagination: {
      page: number
      page_size: number
      total: number
      total_pages: number
    }
  }
}

// 可添加术语库响应
export interface AvailableLibrariesResponse {
  code: number
  msg: string
  data: {
    items: BusinessTermLibrary[]
    total: number
  }
}

// ===== API 请求参数 =====

// 术语库列表请求
export interface LibraryListParams {
  page?: number
  page_size?: number
  search?: string
  category?: string
  status?: 'active' | 'inactive'
}

// 术语列表请求
export interface TermListParams {
  library_id: string
  page?: number
  page_size?: number
  search?: string
  status?: 'active' | 'inactive'
}

// 创建/更新术语库请求
export interface LibraryFormData {
  name: string
  description?: string
  category?: string
  status?: 'active' | 'inactive'
}

// 创建/更新术语请求
export interface TermFormData {
  library_id: string
  term_name: string
  term_alias?: string[]
  term_definition: string
  applicable_conditions?: string
  remarks?: string
  related_datacards?: Array<{ id: string; name: string }>
  related_fields?: Array<{ table: string; field: string }>
  related_terms?: Array<{ id: string; name: string }>
  status?: 'active' | 'inactive'
}

// 模板导入请求
export interface ImportParams {
  library_id: string
  template_ids?: string[]
  category?: string
  template_name?: string
}

// 数据源术语库请求
export interface DataSourceLibraryParams {
  page?: number
  page_size?: number
  is_enabled?: string
}

// 添加术语库到数据源请求
export interface AddDataSourceLibraryParams {
  library_id: string
  is_enabled?: boolean
}

// 更新数据源术语库状态请求
export interface UpdateDataSourceLibraryParams {
  is_enabled: boolean
}

// ===== API 接口 =====

/**
 * 获取术语库列表
 */
export const getLibraryList = (params?: LibraryListParams) => {
  return get<LibraryListResponse>('/business_term/libraries', { params })
}

/**
 * 获取术语库详情
 */
export const getLibraryDetail = (libraryId: string, params?: { terms_page?: number; terms_page_size?: number; terms_search?: string; terms_status?: string }) => {
  return get<LibraryDetailResponse>(`/business_term/libraries/${libraryId}`, { params })
}

/**
 * 创建术语库
 */
export const createLibrary = (data: LibraryFormData) => {
  return post<{ code: number; msg: string; data: { id: string; name: string; message: string } }>('/business_term/libraries', { body: data })
}

/**
 * 更新术语库
 */
export const updateLibrary = (libraryId: string, data: Partial<LibraryFormData>) => {
  return put<{ code: number; msg: string; data: { id: string; updated_fields: string[]; message: string } }>(`/business_term/libraries/${libraryId}`, { body: data })
}

/**
 * 删除术语库
 */
export const deleteLibrary = (libraryId: string) => {
  return del<{ code: number; msg: string; data: { id: string; message: string } }>(`/business_term/libraries/${libraryId}`)
}

/**
 * 获取术语列表
 */
export const getTermList = (params: TermListParams) => {
  return get<TermListResponse>('/business_term/list', { params })
}

/**
 * 获取术语详情
 */
export const getTermDetail = (termId: string) => {
  return get<{ code: number; msg: string; data: BusinessTerm }>(`/business_term/${termId}`)
}

/**
 * 创建术语
 */
export const createTerm = (data: TermFormData) => {
  return post<{ code: number; msg: string; data: { id: string; term_name: string; message: string } }>('/business_term/list', { body: data })
}

/**
 * 更新术语
 */
export const updateTerm = (termId: string, data: Partial<TermFormData>) => {
  return put<{ code: number; msg: string; data: { id: string; updated_fields: string[]; message: string } }>(`/business_term/${termId}`, { body: data })
}

/**
 * 删除术语
 */
export const deleteTerm = (termId: string) => {
  return del<{ code: number; msg: string; data: { id: string; message: string } }>(`/business_term/${termId}`)
}

/**
 * 获取模板分类列表
 */
export const getTemplateCategories = () => {
  return get<TemplateCategoriesResponse>('/business_term/templates/categories')
}

/**
 * 获取模板列表
 */
export const getTemplateList = (params?: { category?: string; template_name?: string }) => {
  return get<TemplateListResponse>('/business_term/templates', { params })
}

/**
 * 从模板导入术语
 */
export const importFromTemplate = (data: ImportParams) => {
  return post<ImportResponse>('/business_term/templates/import', { body: data })
}

/**
 * 获取数据源已添加的术语库
 */
export const getDataSourceLibraries = (datasourceId: string, params?: DataSourceLibraryParams) => {
  return get<DataSourceLibrariesResponse>(`/business_term/datasource/${datasourceId}/libraries`, { params })
}

/**
 * 获取数据源可添加的术语库（未添加的）
 */
export const getAvailableLibraries = (datasourceId: string, params?: { search?: string; category?: string; status?: string }) => {
  return get<AvailableLibrariesResponse>(`/business_term/datasource/${datasourceId}/available`, { params })
}

/**
 * 为数据源添加术语库
 */
export const addDataSourceLibrary = (datasourceId: string, data: AddDataSourceLibraryParams) => {
  return post<{ code: number; msg: string; data: DataSourceTermLibrary & { message: string } }>(`/business_term/datasource/${datasourceId}/libraries`, { body: data })
}

/**
 * 更新数据源术语库状态
 */
export const updateDataSourceLibrary = (datasourceId: string, dsLibraryId: string, data: UpdateDataSourceLibraryParams) => {
  return put<{ code: number; msg: string; data: { id: string; is_enabled: boolean; message: string } }>(`/business_term/datasource/${datasourceId}/libraries/${dsLibraryId}`, { body: data })
}

/**
 * 从数据源移除术语库
 */
export const removeDataSourceLibrary = (datasourceId: string, dsLibraryId: string) => {
  return del<{ code: number; msg: string; data: { id: string; message: string } }>(`/business_term/datasource/${datasourceId}/libraries/${dsLibraryId}`)
}
