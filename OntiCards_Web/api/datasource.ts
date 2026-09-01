// 数据连接器相关接口定义和封装

import { request } from './base'

// ===== 类型定义 =====

// 数据库类型
export type DatabaseType = 'mysql' | 'postgresql' | 'mssql' | 'oracle' | 'sqlite' | 'trino' | 'kingbase' | 'oceanbase' | 'dm'

// 数据源连接配置
export interface DataSourceConfig {
  connect_name: string
  dbType: DatabaseType
  username?: string
  password?: string
  host?: string
  port?: number
  database?: string
  schema?: string
  
  // Trino 特有字段
  catalog?: string
  
  // Oracle 特有字段
  service_name?: string
  sid?: string
  oracle_mode_sysdba?: boolean
  target_schema?: string  // Oracle 的 Schema（不填则默认使用用户名）
  
  // SQL Server 特有字段
  dsn?: string
  
  // SQLite 特有字段
  sqlite_path?: string
  sqlite_memory?: boolean
  
  // 抽取特定表相关字段
  table_names?: string[]  // 要抽取的表名列表
}

// 表列表项
export interface TableListItem {
  name: string
  type: 'TABLE' | 'VIEW'
}

// 表列表响应
export interface TableListResponse {
  tables: TableListItem[]
  total: number
}

// 数据库表结构信息
export interface TableInfo {
  table_name: string
  schema?: string
  description: string
  columns: ColumnInfo[]
  primary_keys: string[]
  foreign_keys: ForeignKeyInfo[]
  indexes: IndexInfo[]
}

// 列信息
export interface ColumnInfo {
  name: string
  type: string
  nullable: boolean
  default?: string
  comment: string
  is_primary: boolean
  is_foreign: boolean
}

// 外键信息
export interface ForeignKeyInfo {
  name: string
  columns: string[]
  referenced_table: string
  referenced_schema?: string
  referenced_columns: string[]
  on_update: string
  on_delete: string
}

// 索引信息
export interface IndexInfo {
  name: string
  columns: string[]
  unique: boolean
  type: string
}

// 数据库结构信息
export interface DatabaseSchema {
  database_type: string
  database_version: string
  generated_at: string
  tables: TableInfo[]
}

// API 响应格式
export interface ApiResponse<T = any> {
  code: number
  msg: string
  result?: T | null
  data?: T | null
}

// 连接测试响应
export interface ConnectionTestResult {
  success: boolean
  database_type?: string
  database_version?: string
  message: string
}

// 快速刷新（测试连接）响应
export interface QuickRefreshResult {
  mode: 'quick'
  id: string
  connect_name: string
  status_before: string
  status_after: string
  database_type: string
  database_name: string
  database_version: string
  connection: string
  error: string | null
}

// 完整刷新响应
export interface FullRefreshResult {
  mode: 'full'
  added_tables: string[]
  removed_tables: string[]
  changed_tables: string[]
  unchanged_tables: string[]
  schemas_deleted: number
  cards_deleted: number
  weaviate_deleted: number
  cards_generated: number
  total_tables: number
}

// 数据源提取响应
export interface ExtractSchemaResult {
  insert_result: {
    message: string
    inserted: number
    skipped: number
    total: number
  }
  generated_cards: Array<{
    DocInfo: {
      doc_id: string
      title: string
      source_type: string
      publish_date: string
      domain: string
      language: string
      author: string
      pages: number
      origin_url: string
      connect_name: string
    }
    Abstract: string
    KeyConcepts: {
      canonical_topic: string
      alias: string[]
      taxonomy_code: string
      key_entities: string[]
      applicable_scenarios: string[]
      tags: string[]
    }
    MongoMap: any[]
    GraphMap: {
      nodes: any[]
      edges: any[]
    }
    SQLMeta: {
      table: string
      pk: string
      pk_value: any
      file_path: string
      checksum: string
      columns: Array<{
        name: string
        type: string
        nullable: boolean
        default: any
        comment: string
        is_primary: boolean
        is_foreign: boolean
      }>
      foreign_keys: any[]
    }
    Tags: string[]
  }>
}

// 数据源列表项
export interface DataSourceItem {
  id: string
  user_id: string
  connect_name: string
  db_type: string
  database_name: string
  table_num: number
  status: 'available' | 'unavailable'
  created_at: string
  updated_at: string
  connect_info: string  // 数据源连接信息
  // 新增字段
  datacard_count?: number  // 该数据源在datacards_datasource表中的记录数
  weaviate_num?: number   // 该数据源在向量库中实际存在的对象数
  catalog_type?: string   // 目录类型
  schema_name?: string    // schema名称
  // 新增：表结构列表（包含填充和审计状态）
  schemas?: SchemaItem[]
}

// 表结构项
export interface SchemaItem {
  id: string
  table_name: string
  db_type: string
  database_name: string
  db_version?: string
  is_view: boolean
  view_name?: string
  is_filled: boolean     // 是否已填充字段描述
  catalog_type?: string
  schema_text?: {
    table_name: string
    description?: string // 表描述
    columns: Array<{
      name: string
      type: string
      nullable?: boolean
      default?: any
      is_primary?: boolean
      comment?: string
      business_meaning?: string // 业务含义（LLM填充后）
    }>
    primary_keys?: string[]
    foreign_keys?: any[]
    indexes?: any[]
  }
  // LLM 填充信息数据结构
  filled_data?: {
    table_name?: string
    before?: {
      table_name?: string
      has_table_description?: boolean
      missing_comment_fields?: Array<{
        name: string
        type?: string
        comment?: string
        is_primary?: boolean
        is_foreign?: boolean
      }>
      total_fields?: number
      missing_count?: number
    }
    fill_result?: {
      table_name?: string
      table_description_filled?: boolean
      filled_fields?: Array<{
        name: string
        type?: string
        comment?: string
        is_primary?: boolean
        is_foreign?: boolean
      }>
      still_missing_fields?: Array<{
        name: string
        type?: string
        comment?: string
        is_primary?: boolean
        is_foreign?: boolean
      }>
      filled_count?: number
      still_missing_count?: number
    }
    columns?: Array<{
      name: string
      business_meaning?: string
      value_range?: string
      sample_values?: string[]
    }>
  }
  created_at: string
  updated_at: string
}

// 数据卡片项
export interface DataCardItem {
  id: number
  doc_id: string
  w_uuid: string
  table_name: string
  connect_name: string
  card_data?: {
    DocInfo?: {
      doc_id: string
      table_name: string
      database_name: string
      connect_name: string
    }
    Abstract?: string
    SQLMeta?: {
      table: string
      columns: Array<{
        name: string
        type: string
        comment?: string
        is_primary?: boolean
      }>
    }
    KeyConcepts?: {
      canonical_topic?: string
      alias?: string[]
      key_entities?: string[]
      applicable_scenarios?: string[]
    }
    Tags?: string[]
    SampleQueries?: string[]
  }
  created_at: string
  updated_at: string
}

// 分页响应数据（新增 weaviate_count 字段）
export interface PaginatedResponse<T> {
  items: T[]
  page: number
  page_size: number
  total: number
  total_pages: number
  has_next: boolean
  has_prev: boolean
  // 新增字段：用户所有数据源的向量库总记录数
  weaviate_count?: number
}

// 分页参数
export interface PaginationParams {
  page?: number
  page_size?: number
  user_id?: string
}

// ===== API 函数 =====

/**
 * 获取数据库表列表
 * @param config 数据源配置
 * @returns 表列表
 */
export const listTables = async (config: DataSourceConfig): Promise<ApiResponse<TableListResponse>> => {
  try {
    // 构建请求参数
    const requestBody: any = { ...config }
    
    // 只有Oracle数据库且勾选了SYSDBA模式时才携带oracle_mode_sysdba字段
    if (config.dbType === 'oracle' && config.oracle_mode_sysdba === true) {
      requestBody.oracle_mode_sysdba = true
    } else {
      delete requestBody.oracle_mode_sysdba
    }
    
    // Trino的port需要转换为字符串
    if (config.dbType === 'trino' && config.port !== undefined) {
      requestBody.port = String(config.port)
    }
    
    // DM 的 target_schema 字段（仅 DM 且填写了才传递，不填则默认传用户名大写）
    if (config.dbType === 'dm') {
      // 如果填写了 target_schema，使用填写的值
      if (config.target_schema?.trim()) {
        requestBody.target_schema = config.target_schema.trim().toUpperCase()
      } else if (config.username?.trim()) {
        // 如果没填 target_schema，默认使用用户名大写
        requestBody.target_schema = config.username.trim().toUpperCase()
      }
    } else {
      delete requestBody.target_schema
    }
    
    // Oracle 的 target_schema 字段
    if (config.dbType === 'oracle' && config.target_schema?.trim()) {
      requestBody.target_schema = config.target_schema.trim()
    } else if (config.dbType !== 'dm') {
      delete requestBody.target_schema
    }
    
    const response = await request<ApiResponse<TableListResponse>>('/list_tables', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: requestBody,
    })
    return response
  } catch (error: any) {
    console.error('获取表列表失败:', error)
    const errorMsg = error?.response?.data?.msg || error?.message || '获取表列表失败'
    return {
      code: 500,
      msg: errorMsg,
      result: null
    }
  }
}

/**
 * 测试数据库连接
 * @param config 数据源配置
 * @returns 连接测试结果
 */
export const testConnection = async (config: DataSourceConfig): Promise<ApiResponse<ConnectionTestResult>> => {
  try {
    // 构建请求参数，处理Oracle SYSDBA模式和Trino的port字段
    const requestBody: any = { ...config }
    
    // 只有Oracle数据库且勾选了SYSDBA模式时才携带oracle_mode_sysdba字段
    if (config.dbType === 'oracle' && config.oracle_mode_sysdba === true) {
      requestBody.oracle_mode_sysdba = true
    } else {
      // 确保不携带oracle_mode_sysdba字段
      delete requestBody.oracle_mode_sysdba
    }
    
    // Trino的port需要转换为字符串
    if (config.dbType === 'trino' && config.port !== undefined) {
      requestBody.port = String(config.port)
    }
    
    // DM 的 target_schema 字段（仅 DM 且填写了才传递，不填则默认传用户名大写）
    if (config.dbType === 'dm') {
      // 如果填写了 target_schema，使用填写的值
      if (config.target_schema?.trim()) {
        requestBody.target_schema = config.target_schema.trim().toUpperCase()
      } else if (config.username?.trim()) {
        // 如果没填 target_schema，默认使用用户名大写
        requestBody.target_schema = config.username.trim().toUpperCase()
      }
    } else {
      delete requestBody.target_schema
    }
    
    // Oracle 的 target_schema 字段（仅 Oracle 且填写了才传递）
    if (config.dbType === 'oracle' && config.target_schema?.trim()) {
      requestBody.target_schema = config.target_schema.trim()
    } else if (config.dbType !== 'dm') {
      delete requestBody.target_schema
    }
    
    const response = await request<ApiResponse<ConnectionTestResult>>('/connect_test', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: requestBody,
    })
    return response
  } catch (error: any) {
    console.error('连接测试失败:', error)
    // 优先使用接口返回的错误信息，其次使用 Error 对象的 message，最后使用默认提示
    const errorMsg = error?.response?.data?.msg || error?.message || '连接失败，请检查网络和配置'
    return {
      code: 500,
      msg: errorMsg,
      result: null
    }
  }
}

/**
 * 提取数据库结构
 * @param config 数据源配置
 * @param getAbortController 可选的获取AbortController回调函数，用于取消请求
 * @returns 提取结果
 */
export const extractSchema = async (
  config: DataSourceConfig, 
  getAbortController?: (abortController: AbortController) => void
): Promise<ApiResponse<ExtractSchemaResult>> => {
  // 生成唯一的请求ID，用于后端识别和清理
  const requestId = `extract_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  
  try {
    // 构建请求参数，处理Oracle SYSDBA模式和Trino的port字段
    const requestBody: any = { 
      ...config,
      request_id: requestId  // 添加请求ID
    }
    
    // 只有Oracle数据库且勾选了SYSDBA模式时才携带oracle_mode_sysdba字段
    if (config.dbType === 'oracle' && config.oracle_mode_sysdba === true) {
      requestBody.oracle_mode_sysdba = true
    } else {
      // 确保不携带oracle_mode_sysdba字段
      delete requestBody.oracle_mode_sysdba
    }
    
    // Trino的port需要转换为字符串
    if (config.dbType === 'trino' && config.port !== undefined) {
      requestBody.port = String(config.port)
    }
    
    // DM 的 target_schema 字段（仅 DM 且填写了才传递，不填则默认传用户名大写）
    if (config.dbType === 'dm') {
      // 如果填写了 target_schema，使用填写的值
      if (config.target_schema?.trim()) {
        requestBody.target_schema = config.target_schema.trim().toUpperCase()
      } else if (config.username?.trim()) {
        // 如果没填 target_schema，默认使用用户名大写
        requestBody.target_schema = config.username.trim().toUpperCase()
      }
    } else {
      delete requestBody.target_schema
    }
    
    // Oracle 的 target_schema 字段（仅 Oracle 且填写了才传递）
    if (config.dbType === 'oracle' && config.target_schema?.trim()) {
      requestBody.target_schema = config.target_schema.trim()
    } else if (config.dbType !== 'dm') {
      delete requestBody.target_schema
    }
    
    // 只有当选择了特定表时才添加table_names参数
    if (config.table_names && config.table_names.length > 0) {
      requestBody.table_names = config.table_names
    } else {
      delete requestBody.table_names
    }
    
    const response = await request<ApiResponse<ExtractSchemaResult>>('/extract_schema', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: requestBody,
    }, {
      getAbortController
    })
    return response
  } catch (error: any) {
    // 如果是用户主动取消请求，通知后端清理
    if (error?.name === 'AbortError') {
      console.log('请求已被取消，通知后端清理数据')
      
      // 异步调用后端清理接口，传递完整配置用于构建连接字符串
      cancelExtractSchema(requestId, config).catch(err => {
        console.error('清理请求失败:', err)
      })
      
      return {
        code: 499,
        msg: '请求已取消',
        result: null
      }
    }
    console.error('结构提取失败:', error)
    return {
      code: 500,
      msg: error?.message || '结构提取失败',
      result: null
    }
  }
}

/**
 * 取消数据源提取并清理后端数据
 * @param requestId 请求ID
 * @param config 数据源配置（用于后端构建连接字符串并清理数据）
 */
export const cancelExtractSchema = async (requestId: string, config?: DataSourceConfig): Promise<ApiResponse<any>> => {
  try {
    const response = await request<ApiResponse<any>>('/cancel_extract_schema', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: {
        request_id: requestId,
        // 传递完整配置，让后端构建连接字符串
        ...(config ? { config } : {})
      },
    })
    return response
  } catch (error) {
    console.error('取消请求失败:', error)
    return {
      code: 500,
      msg: '取消请求失败',
      result: null
    }
  }
}

/**
 * 获取数据源列表
 * @returns 数据源列表
 */
export const getDataSources = async (): Promise<ApiResponse<any[]>> => {
  try {
    const response = await request<ApiResponse<any[]>>('/datasources', {
      method: 'GET',
    })
    return response
  } catch (error) {
    console.error('获取数据源列表失败:', error)
    return {
      code: 500,
      msg: '获取数据源列表失败',
      result: null
    }
  }
}

/**
 * 获取用户数据源列表（分页）
 * @param params 分页参数
 * @returns 用户数据源列表（分页）
 */
export const getUserDataSources = async (params: PaginationParams = {}): Promise<ApiResponse<PaginatedResponse<DataSourceItem>>> => {
  try {
    const { page = 1, page_size = 8, user_id } = params
    
    // 构建查询参数
    const queryParams = new URLSearchParams({
      page: page.toString(),
      page_size: page_size.toString()
    })
    
    // 如果提供了user_id，添加到查询参数中
    if (user_id) {
      queryParams.append('user_id', user_id)
    }
    
    const response = await request<ApiResponse<PaginatedResponse<DataSourceItem>>>(`/datasource_tool?${queryParams.toString()}`, {
      method: 'GET',
    })
    return response
  } catch (error) {
    console.error('获取用户数据源列表失败:', error)
    return {
      code: 500,
      msg: '获取用户数据源列表失败',
      result: null
    }
  }
}

/**
 * 根据 ID 获取单个数据源详情（含 schemas 等）
 * @param id 数据源 ID
 * @returns 数据源详情
 */
export const getDataSourceById = async (id: string): Promise<ApiResponse<DataSourceItem>> => {
  try {
    const response = await request<ApiResponse<DataSourceItem>>(`/datasource_tool/${id}`, {
      method: 'GET',
    })
    return response
  } catch (error) {
    console.error('获取数据源详情失败:', error)
    return {
      code: 500,
      msg: '获取数据源详情失败',
      result: null
    }
  }
}

/**
 * 删除数据源
 * @param id 数据源ID
 * @returns 删除结果
 */
export const deleteDataSource = async (id: string): Promise<ApiResponse<any>> => {
  try {
    const response = await request<ApiResponse<any>>(`/datasource_tool/${id}`, {
      method: 'DELETE',
    })
    return response
  } catch (error) {
    console.error('删除数据源失败:', error)
    return {
      code: 500,
      msg: '删除数据源失败',
      result: null
    }
  }
}

/**
 * 更新数据源名称
 * @param id 数据源ID
 * @param newName 新的数据源名称
 * @returns 更新结果
 */
export const updateDataSourceName = async (id: string, newName: string): Promise<ApiResponse<any>> => {
  try {
    console.log('更新数据源API调用:', { id, newName }) // 调试日志
    const response = await request<ApiResponse<any>>(`/datasource_tool/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: {
        connect_name: newName
      }
    })
    console.log('更新数据源API响应:', response) // 调试日志
    return response
  } catch (error) {
    console.error('更新数据源名称失败:', error)
    return {
      code: 500,
      msg: '更新数据源名称失败',
      result: null
    }
  }
}

/**
 * 快速刷新数据源（测试连接）
 * @param id 数据源ID
 * @returns 刷新结果
 */
export const quickRefreshDataSource = async (id: string): Promise<ApiResponse<QuickRefreshResult>> => {
  try {
    const response = await request<ApiResponse<QuickRefreshResult>>(`/datasource_tool/${id}/refresh?mode=quick`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      }
    })
    return response
  } catch (error) {
    console.error('快速刷新数据源失败:', error)
    return {
      code: 500,
      msg: '快速刷新数据源失败',
      result: null
    }
  }
}

/**
 * 完整刷新数据源
 * @param id 数据源ID
 * @returns 刷新结果
 */
export const fullRefreshDataSource = async (id: string): Promise<ApiResponse<FullRefreshResult>> => {
  try {
    const response = await request<ApiResponse<FullRefreshResult>>(`/datasource_tool/${id}/refresh?mode=full`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      }
    })
    return response
  } catch (error) {
    console.error('完整刷新数据源失败:', error)
    return {
      code: 500,
      msg: '完整刷新数据源失败',
      result: null
    }
  }
}

// Excel文件上传补充字段描述相关类型
export interface ExcelFieldMapping {
  has_title: '0' | '1'  // 是否包含表头
  tb_name_index: string  // 表名所在列
  tb_desc_index: string  // 表描述所在列
  field_name_index: string  // 字段名所在列
  field_desc_index: string  // 字段描述所在列
  field_value_desc_index: string  // 字段取值附加描述所在列
}

export interface ExcelUploadParams {
  file: File
  connect_info: string
  sheet_name?: string
  field_data: ExcelFieldMapping
}

export interface ExcelFieldData {
  table_name: string
  description: string
  [fieldName: string]: string  // 动态字段名和描述
}

export interface ExcelUploadResult {
  excel_filed_datas: ExcelFieldData[]
}

/**
 * 上传Excel文件补充数据源字段描述
 * @param params 上传参数
 * @returns 上传结果
 */
export const uploadExcelFieldData = async (params: ExcelUploadParams): Promise<ApiResponse<ExcelUploadResult>> => {
  try {
    const formData = new FormData()
    formData.append('file', params.file)
    formData.append('connect_info', params.connect_info)
    if (params.sheet_name) {
      formData.append('sheet_name', params.sheet_name)
    }
    formData.append('field_data', JSON.stringify(params.field_data))

    const response = await request<ApiResponse<ExcelUploadResult>>('/extract_field_data_excel', {
      method: 'POST',
      body: formData,
      // 不设置 Content-Type，让浏览器自动设置 multipart/form-data
    }, {
      deleteContentType: true,  // 删除默认的Content-Type，让浏览器自动设置
      bodyStringify: false      // 不对FormData进行JSON.stringify
    })
    return response
  } catch (error) {
    console.error('Excel文件上传失败:', error)
    return {
      code: 500,
      msg: 'Excel文件上传失败',
      result: null
    }
  }
}