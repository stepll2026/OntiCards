// 业务术语库页面类型定义

import type { BusinessTermLibrary, BusinessTerm } from '@/api/businessTerms'

// Props 类型
export interface Props {
  params: {
    lng: string
  }
}

// 术语库表单数据
export interface LibraryFormValues {
  name: string
  description?: string
  category?: string
}

// 术语表单数据
export interface TermFormValues {
  term_name: string
  term_alias?: string[]
  term_definition: string
  applicable_conditions?: string
  remarks?: string
  related_datacards?: Array<{ id: string; name: string }>
  related_fields?: Array<{ table: string; field: string }>
  related_terms?: Array<{ id: string; name: string }>
}

// 表格列配置类型
export interface LibraryTableColumn {
  key: string
  title: string
  dataIndex?: string
  width?: number | string
  render?: (value: any, record: BusinessTermLibrary, index: number) => React.ReactNode
}

export interface TermTableColumn {
  key: string
  title: string
  dataIndex?: string
  width?: number | string
  render?: (value: any, record: BusinessTerm, index: number) => React.ReactNode
}

// 模板选择项
export interface TemplateSelectItem {
  id: string
  category: string
  template_name: string
  term_name: string
  term_alias: string[]
  term_definition: string
  selected: boolean
}

// 行业分类选项 - 由后端动态提供，这里只提供默认值
export const CATEGORY_OPTIONS: Array<{ label: string; value: string }> = []

// 状态选项
export const STATUS_OPTIONS = [
  { label: '启用', value: 'active' },
  { label: '禁用', value: 'inactive' },
]
