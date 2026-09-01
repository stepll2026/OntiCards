import { request } from './base'

// 数据卡片相关类型定义
export interface DataCardColumn {
  name: string
  type: string
  nullable: boolean
  default: any
  comment: string
  is_primary: boolean
  is_foreign: boolean
}

export interface DataCardSQLMeta {
  table: string
  pk: string
  pk_value: any
  file_path: string
  checksum: string
  columns: DataCardColumn[]
  foreign_keys: any[]
}

export interface DataCardDocInfo {
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

export interface DataCardKeyConcepts {
  canonical_topic: string
  alias: string[]
  taxonomy_code: string
  key_entities: string[]
  applicable_scenarios: string[]
  tags: string[]
}

export interface DataCardData {
  DocInfo: DataCardDocInfo
  Abstract: string
  KeyConcepts: DataCardKeyConcepts
  MongoMap: any[]
  GraphMap: {
    nodes: any[]
    edges: any[]
  }
  SQLMeta: DataCardSQLMeta
  Tags: string[]
}

// 填充数据相关类型定义
export interface FilledField {
  name: string
  type: string
  comment?: string
  is_primary: boolean
  is_foreign: boolean
}

export interface FillBefore {
  table_name: string
  has_table_description: boolean
  missing_comment_fields: FilledField[]
  total_fields: number
  missing_count: number
}

export interface FillResult {
  table_name: string
  table_description_filled: boolean
  filled_fields: FilledField[]
  still_missing_fields: FilledField[]
  filled_count: number
  still_missing_count: number
}

export interface DetailedFill {
  table_name: string
  filled_map: Record<string, string>
  still_missing_fields: FilledField[]
  filled_table_description: string
}

export interface FilledData {
  table_name: string
  before: FillBefore
  fill_result: FillResult
  detailed_fill: DetailedFill
}

// 审计相关类型定义已移除

export interface DataCard {
  doc_id: string
  table_name: string
  connect_name: string
  connect_info_masked: string
  w_uuid: string
  created_at: string
  updated_at: string
  card_data: string | DataCardData
  is_filled?: boolean
  filled_data?: FilledData
  is_view?: boolean
  view_name?: string
}

export interface DataSource {
  id?: string
  connect_name: string
  db_type: string
  database_name: string
  table_num: number
  status: string
  connect_info?: string
  connect_info_masked?: string
}

export interface DataCardItem {
  datasource: DataSource
  cards: DataCard[]
}

export interface DataCardResponse {
  code: number
  msg: string
  data: {
    total_cards: number
    total_datasources: number
    page: number
    page_size: number
    items: DataCardItem[]
  }
}

// 获取数据卡片列表的参数
export interface GetDataCardsParams {
  datasource_id?: string
  connect_name?: string
  q?: string
  page?: number
  page_size?: number
  group_by?: 'datasource' | 'flat'
  parse_json?: boolean
}

// 获取数据卡片列表（分页）
export const getDataCards = async (params: GetDataCardsParams = {}): Promise<DataCardResponse> => {
  const queryParams = new URLSearchParams()
  
  if (params.datasource_id) queryParams.append('datasource_id', params.datasource_id)
  if (params.connect_name) queryParams.append('connect_name', params.connect_name)
  if (params.q) queryParams.append('q', params.q)
  if (params.page) queryParams.append('page', params.page.toString())
  if (params.page_size) queryParams.append('page_size', params.page_size.toString())
  if (params.group_by) queryParams.append('group_by', params.group_by)
  if (params.parse_json !== undefined) queryParams.append('parse_json', params.parse_json.toString())

  const url = `/datacard_tool${queryParams.toString() ? `?${queryParams.toString()}` : ''}`
  
  return request(url, {
    method: 'GET'
  })
}

// 获取所有数据卡片（不分页）
// 注意：/datacard_tool/all 仅返回 { total_cards, total_datasources, items }，
// **不包含** page / page_size 等分页字段。
export const getAllDataCards = async (params: { datasource_id?: string; connect_name?: string; parse_json?: boolean } = {}): Promise<{
  code: number
  msg: string
  data: {
    total_cards: number
    total_datasources: number
    items: DataCardItem[]
  }
}> => {
  const queryParams = new URLSearchParams()

  if (params.datasource_id) queryParams.append('datasource_id', params.datasource_id)
  if (params.connect_name) queryParams.append('connect_name', params.connect_name)
  if (params.parse_json !== undefined) queryParams.append('parse_json', params.parse_json.toString())

  const url = `/datacard_tool/all${queryParams.toString() ? `?${queryParams.toString()}` : ''}`

  return request(url, {
    method: 'GET'
  })
}

// 更新数据卡片的响应类型
export interface UpdateDataCardResponse {
  code: number
  msg: string
  data: {
    id: number
    doc_id: string
    w_uuid: string
    card_data: DataCardData
    created_at: string
    updated_at: string
    is_filled?: boolean
    filled_data?: FilledData
    _vector_ops: {
      delete_old_ok: boolean
      old_w_uuid: string
      new_w_uuid: string
    }
  }
}

// 更新数据卡片
export const updateDataCard = async (card: DataCard): Promise<UpdateDataCardResponse> => {
  return request('/datacard_tool', {
    method: 'PUT',
    body: card,
    headers: {
      'Content-Type': 'application/json'
    }
  })
}