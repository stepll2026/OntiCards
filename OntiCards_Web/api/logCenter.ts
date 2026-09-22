import { get } from './base'

export type SystemLogLevel = 'all' | 'INFO' | 'WARNING' | 'ERROR'

export type SystemLogItem = {
  id: string
  created_at: string
  level: string
  event: string
  message: string
  request_id?: string | null
  method?: string | null
  path?: string | null
  status_code?: number | null
  duration_ms?: number | null
}

export type SystemLogParams = {
  page: number
  page_size: number
  level: SystemLogLevel
  keyword?: string
  start_date?: string
  end_date?: string
}

export type SystemLogResponse = {
  code: number
  msg?: string
  message?: string
  data: {
    items: SystemLogItem[]
    total: number
    page: number
    page_size: number
    total_pages: number
    truncated: boolean
  }
}

export const getSystemLogs = (params: SystemLogParams) =>
  get<SystemLogResponse>('/log_center/system', { params })
