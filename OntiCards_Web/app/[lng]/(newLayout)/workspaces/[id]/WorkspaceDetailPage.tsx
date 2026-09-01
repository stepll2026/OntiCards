'use client'

import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { createPortal } from 'react-dom'
import Link from 'next/link'
import { useParams, useSearchParams } from 'next/navigation'
import {
  message,
  Modal,
  Select,
  Spin,
  Button,
  Empty,
  Tabs,
  Card,
  Tooltip,
  Checkbox,
  Progress,
  Input,
  Popconfirm,
  Switch,
} from 'antd'
import type { UploadFile } from 'antd/es/upload/interface'
import type { ColumnsType } from 'antd/es/table'
import {
  Database,
  Table,
  CreditCard,
  Sparkles,
  MessageSquare,
  PlayCircle,
  CheckCircle,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Clock,
  BarChart3,
  Layers,
  FileText,
  Settings,
  Loader2,
  RefreshCw,
  X,
  Tag,
  Link2,
  Key,
  Upload,
  FileSpreadsheet,
  ArrowRight,
  Table2,
  FileCheck,
  FileX,
  Eye,
  EyeOff,
  AlertTriangle,
  Zap,
  Copy,
  Code,
  Search,
  Info,
  CheckCircle2,
  Target,
  Globe,
  Aperture,
  BookOpen,
  LayoutDashboard,
} from 'lucide-react'
import {
  PlusOutlined,
  DeleteOutlined,
  BookOutlined,
} from '@ant-design/icons'
import { getUserDataSources, updateDataSourceName, uploadExcelFieldData } from '@/api/datasource'
import type { DataSourceItem, SchemaItem } from '@/api/datasource'
import { getDataCards, getAllDataCards, updateDataCard } from '@/api/datacard'
import type { DataCard, DataCardData, DataSource } from '@/api/datacard'
import { queryByDatacardsAgg, type QueryRequest } from '@/api/query'
import { runGlobalInventory, getTableList, type TableListItem, type RunJobRequest } from '@/api/targetInventory'
import {
  discoverRelationships,
  getRelationshipCards,
  getTableRelationships,
  getRelationshipGraph,
  deleteRelationships,
  type RelationshipCardItem,
  type GlobalInventory,
  type GraphNode,
  type GraphEdge,
} from '@/api/globalInventory'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import TargetInventory from '@/app/[lng]/(newLayout)/target-inventory/TargetInventory'
import InventoryTypeModal, { type InventoryType } from '@/components/business/InventoryTypeModal'
import TargetInventoryModal from '@/components/business/TargetInventoryModal'
import GlobalInventoryModal from '@/components/business/GlobalInventoryModal'
import WorkspaceGlobalInventoryTabs from '@/components/business/WorkspaceGlobalInventoryTabs'
import KnowledgeTab from '@/components/business/KnowledgeTab'
import { useDataSources } from '@/hooks/useDataSources'
import QueryHistoryPage from '@/app/[lng]/(newLayout)/query-history/QueryHistoryPage'

// 全局统一的数据源缓存 key
const GLOBAL_DATA_SOURCE_CACHE_KEY = 'globalDataSources'

// 全局加载状态跟踪器（页面刷新时会重置，SPA 导航时保持）
let globalHasLoadedData = false

// 清除全局加载状态（供页面刷新时使用）
export const resetGlobalDataSourceLoaded = () => {
  globalHasLoadedData = false
}

// 清除全局数据源缓存（供其他页面调用）
export const clearGlobalDataSourceCache = () => {
  if (typeof window === 'undefined') return
  window.sessionStorage.removeItem(GLOBAL_DATA_SOURCE_CACHE_KEY)
}

// 通知数据源已变更（供其他页面调用）
export const notifyDataSourceChanged = () => {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('datasource-changed'))
  }
}

const tabs = [
  {
    id: 'overview',
    label: '概览',
    icon: <FileText className="w-4 h-4" />,
  },
  {
    id: 'assets',
    label: '库表',
    icon: <Layers className="w-4 h-4" />,
  },
  {
    id: 'cards',
    label: '卡片',
    icon: <CreditCard className="w-4 h-4" />,
  },
  {
    id: 'enhance',
    label: '增强',
    icon: <Sparkles className="w-4 h-4" />,
  },
  {
    id: 'ask',
    label: '问数',
    icon: <MessageSquare className="w-4 h-4" />,
  },
  {
    id: 'knowledge',
    label: '知识',
    icon: <BookOpen className="w-4 h-4" />,
  },
  {
    id: 'history',
    label: '历史',
    icon: <Clock className="w-4 h-4" />,
  },
  {
    id: 'jobs',
    label: '任务',
    icon: <BarChart3 className="w-4 h-4" />,
  },
]

const getDbTypeIcon = (dbType: string) => {
  const icons: Record<string, string> = {
    mysql: '🐬',
    postgresql: '🐘',
    mssql: '📊',
    oracle: '🔵',
    sqlite: '📁',
    trino: '⚡',
    kingbase: '🛡️',
    oceanbase: '🌊',
    dm: '💠',
  }
  return icons[dbType?.toLowerCase()] || '🗄️'
}

// 数据库类型标签浅色背景（用于卡片等）
const getDbTypeTagClass = (dbType: string) => {
  const map: Record<string, string> = {
    mysql: 'bg-blue-50 text-blue-600 border-blue-100',
    postgresql: 'bg-emerald-50 text-emerald-600 border-emerald-100',
    mssql: 'bg-purple-50 text-purple-600 border-purple-100',
    oracle: 'bg-red-50 text-red-600 border-red-100',
    sqlite: 'bg-amber-50 text-amber-600 border-amber-100',
    trino: 'bg-orange-50 text-orange-600 border-orange-100',
    kingbase: 'bg-cyan-50 text-cyan-600 border-cyan-100',
    oceanbase: 'bg-sky-50 text-sky-600 border-sky-100',
    dm: 'bg-indigo-50 text-indigo-600 border-indigo-100',
  }
  return map[dbType?.toLowerCase()] || 'bg-slate-50 text-slate-600 border-slate-100'
}

function formatRelativeTime(dateString: string): string {
  if (!dateString) return '-'
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffMins < 60) return `${diffMins} 分钟前`
  if (diffHours < 24) return `${diffHours} 小时前`
  if (diffDays < 7) return `${diffDays} 天前`
  return date.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

// 解析连接字符串，返回各项属性
function parseConnectInfo(connectInfo: string): {
  username: string;
  password: string;
  host: string;
  port: number;
  database: string;
  dbType: string;
  serviceName?: string;
} | null {
  if (!connectInfo) return null

  try {
    // 支持多种数据库连接字符串格式：
    // 1. mysql+pymysql://user:pass@host:port/db
    // 2. postgresql://user:pass@host:port/db
    // 3. dm+dmPython://user:pass@host:port/db (达梦)
    // 4. oracle://user:pass@host:port?service_name=XXX
    // 5. 用户名中可能包含 URL 编码的字符（如 OceanBase 的 root%40tenant）
    // 第一个 \w+ 是数据库类型，第二个（可选）是驱动名
    const match = connectInfo.match(/^(\w+)\+?(\w+)?:\/\/([^:@]+):([^@]+)@([^:]+):(\d+)\/?([^?]*)(?:\?service_name=([^&\s]+))?$/)

    if (match) {
      const [, dbType, , username, password, host, port, database, serviceName] = match
      return {
        // 对用户名和密码进行 URL 解码
        username: decodeURIComponent(username),
        password: decodeURIComponent(password),
        host,
        port: parseInt(port, 10),
        database: database || '',
        dbType,
        serviceName: serviceName || undefined,
      }
    }
    return null
  } catch {
    return null
  }
}

// 加密密码显示
function maskPassword(password: string): string {
  if (!password) return ''
  return '*'.repeat(Math.min(password.length, 12))
}

const StatCard = ({
                    icon,
                    label,
                    value,
                    color = '#3b82f6',
                  }: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  color?: string;
}) => (
  <div
    className="bg-white p-3 rounded-[16px] border border-slate-200 flex items-center gap-3 hover:shadow-sm transition-shadow relative overflow-hidden"
    style={{ position: 'relative' }}
  >
    {/* 渐变光晕效果 */}
    <div
      style={{
        position: 'absolute',
        top: -20,
        right: -20,
        width: 88,
        height: 88,
        borderRadius: '50%',
        opacity: 0.12,
        background: `radial-gradient(circle, ${color}, transparent 70%)`,
        filter: 'blur(15px)',
      }}
    />
    <div className="p-2 bg-gradient-to-br from-slate-50 to-slate-100/50 rounded-[12px]" style={{ position: 'relative', zIndex: 1 }}>
      {icon}
    </div>
    <div style={{ position: 'relative', zIndex: 1 }}>
      <p className="text-slate-500 text-[10px] mb-0.5">{label}</p>
      <p className="text-lg font-semibold text-slate-900">{value}</p>
    </div>
  </div>
)

// 解析卡片数据
function parseCardData(cardData: string | DataCardData | undefined): DataCardData | null {
  if (!cardData) return null
  if (typeof cardData === 'string') {
    try {
      return JSON.parse(cardData) as DataCardData
    } catch {
      return null
    }
  }
  return cardData
}

// 表结构详情弹窗
function SchemaDetailModal({
                             schema,
                             onClose,
                           }: {
  schema: SchemaItem;
  onClose: () => void;
}) {
  const schemaText = schema.schema_text
  const columns = schemaText?.columns ?? []
  const primaryKeys = schemaText?.primary_keys ?? []
  const foreignKeys = schemaText?.foreign_keys ?? []
  const indexes = schemaText?.indexes ?? []
  const filledData = schema.filled_data

  const content = (
    <div
      className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 9999,
      }}
    >
      <div className="w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col shadow-2xl"
           style={{ borderRadius: '28px', backgroundColor: 'rgb(var(--theme-bg))' }}
      >

        {/* 头部 */}
        <div
          className="flex items-center justify-between px-6 py-5 border-b"
          style={{ borderColor: 'rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))' }}
        >
          <div className="flex items-center gap-3">
            <div
              className="w-11 h-11 flex items-center justify-center"
              style={{ borderRadius: '14px', backgroundColor: 'rgba(var(--theme-primary), 0.1)' }}
            >
              <Table className="w-5 h-5" style={{ color: 'rgb(var(--theme-primary))' }} />
            </div>
            <div>
              <h3 className="text-lg font-bold flex items-center gap-2" style={{ color: 'rgb(var(--theme-text))' }}>
                {schema.table_name}
                {schema.is_view && (
                  <span className="text-xs px-2.5 py-0.5 font-medium"
                        style={{ borderRadius: '9999px', backgroundColor: 'rgba(245, 158, 11, 0.1)', color: 'rgb(217, 119, 6)', border: '1px solid rgba(245, 158, 11, 0.2)' }}
                  >视图</span>
                )}
              </h3>
              <p className="text-sm mt-0.5" style={{ color: 'rgb(var(--theme-text-muted))' }}>{schema.database_name}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 transition-colors"
                  style={{ borderRadius: '12px', color: 'rgb(var(--theme-text-muted))' }}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 内容区域 */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">

          {/* 基本信息 + 表描述 紧凑一行 */}
          <div
            className="flex items-start gap-x-5 gap-y-2 flex-wrap px-5 py-3.5 text-sm"
            style={{ borderRadius: '16px', backgroundColor: 'rgb(var(--theme-bg-secondary))', border: '1px solid rgb(var(--theme-border))' }}
          >
            <span className="flex items-center gap-1.5 whitespace-nowrap">
              <span className="text-xs font-medium" style={{ color: 'rgb(var(--theme-text-muted))' }}>字段数</span>
              <span className="text-xs" style={{ color: 'rgb(var(--theme-border))' }}>:</span>
              <span className="font-bold" style={{ color: 'rgb(var(--theme-primary))' }}>{columns.length}</span>
            </span>
            <span className="text-xs self-center" style={{ color: 'rgb(var(--theme-border))' }}>|</span>
            <span className="flex items-center gap-1.5 whitespace-nowrap">
              <span className="text-xs font-medium" style={{ color: 'rgb(var(--theme-text-muted))' }}>主键</span>
              <span className="text-xs" style={{ color: 'rgb(var(--theme-border))' }}>:</span>
              <span className="font-mono font-semibold text-xs" style={{ color: 'rgb(var(--theme-text))' }}>{primaryKeys.join(', ') ||
                <span style={{ color: 'rgb(var(--theme-text-muted))' }}>-</span>}</span>
            </span>
            <span className="text-xs self-center" style={{ color: 'rgb(var(--theme-border))' }}>|</span>
            <span
              className="flex items-center gap-1.5 whitespace-nowrap text-xs font-semibold"
              style={{ color: schema.is_filled ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-muted))' }}
            >
              {schema.is_filled ? '✨ 部分数据AI填充' : '未填充'}
            </span>
            {schemaText?.description && (
              <>
                <span className="text-xs self-center" style={{ color: 'rgb(var(--theme-border))' }}>|</span>
                <span className="flex items-center gap-1.5 min-w-0">
                  <span className="text-xs font-medium whitespace-nowrap" style={{ color: 'rgb(var(--theme-text-muted))' }}>表描述</span>
                  <span className="text-xs" style={{ color: 'rgb(var(--theme-border))' }}>:</span>
                  <span className="text-xs leading-relaxed" style={{ color: 'rgb(var(--theme-text))' }}>{schemaText.description}</span>
                </span>
              </>
            )}
          </div>

          {/* 字段详情 */}
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-widest mb-3" style={{ color: 'rgb(var(--theme-text-muted))' }}>字段详情</p>
            <div className="overflow-hidden border" style={{ borderRadius: '16px', borderColor: 'rgb(var(--theme-border))' }}>
              <table className="w-full text-sm">
                <thead>
                <tr className="border-b text-left" style={{ backgroundColor: 'rgb(var(--theme-bg-secondary))', borderColor: 'rgb(var(--theme-border))' }}>
                  <th className="px-3 py-3 w-10 font-semibold text-xs">#</th>
                  <th className="px-3 py-3 font-semibold text-xs min-w-[120px]" style={{ color: 'rgb(var(--theme-text-muted))' }}>字段名</th>
                  <th className="px-3 py-3 font-semibold text-xs w-[140px]" style={{ color: 'rgb(var(--theme-text-muted))' }}>类型</th>
                  <th className="px-3 py-3 font-semibold text-xs w-[70px]" style={{ color: 'rgb(var(--theme-text-muted))' }}>可空</th>
                  <th className="px-3 py-3 font-semibold text-xs w-20" style={{ color: 'rgb(var(--theme-text-muted))' }}>默认值</th>
                  <th className="px-3 py-3 font-semibold text-xs" style={{ color: 'rgb(var(--theme-text-muted))' }}>注释</th>
                </tr>
                </thead>
                <tbody>
                {columns.map((col, idx) => (
                  <tr key={idx}
                      className="border-b transition-colors last:border-0"
                      style={{ borderColor: 'rgb(var(--theme-border))' }}
                  >
                    <td className="px-3 py-3 text-xs font-mono" style={{ color: 'rgb(var(--theme-text-muted))' }}>{idx + 1}</td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono font-semibold text-sm" style={{ color: 'rgb(var(--theme-text))' }}>{col.name}</span>
                        {primaryKeys.includes(col.name) && (
                          <span className="text-[10px] text-white px-1.5 py-0.5 font-semibold"
                                style={{ borderRadius: '9999px', backgroundColor: 'rgb(59, 130, 246)' }}
                          >PK</span>
                        )}
                        {foreignKeys.some((fk: any) => fk.columns?.includes(col.name)) && (
                          <span className="text-[10px] text-white px-1.5 py-0.5 font-semibold"
                                style={{ borderRadius: '9999px', backgroundColor: 'rgb(245, 158, 11)' }}
                          >FK</span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <span
                        className="font-mono text-xs px-2 py-1 inline-block max-w-[130px] overflow-hidden text-ellipsis"
                        style={{ borderRadius: '8px', backgroundColor: 'rgb(var(--theme-bg-secondary))', color: 'rgb(var(--theme-text-muted))' }} title={col.type}
                      >{col.type}</span>
                    </td>
                    <td className="px-3 py-3">
                      {col.nullable
                        ? <span className="text-xs" style={{ color: 'rgb(var(--theme-text-muted))' }}>✓</span>
                        : <span className="text-xs" style={{ color: 'rgb(var(--theme-text-muted))' }}>✗</span>}
                    </td>
                    <td className="px-3 py-3">
                      <span className="font-mono text-xs" style={{ color: 'rgb(var(--theme-text-muted))' }}>{col.default ?? '-'}</span>
                    </td>
                    <td className="px-3 py-3">
                      <span className="text-xs" style={{ color: 'rgb(var(--theme-text-muted))' }}>{col.comment || '-'}</span>
                    </td>
                  </tr>
                ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 索引信息 */}
          {indexes && indexes.length > 0 && (
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-widest mb-3" style={{ color: 'rgb(var(--theme-text-muted))' }}>索引</p>
              <div className="space-y-2">
                {indexes.map((idx: any, i: number) => (
                  <div key={i}
                       className="flex items-center gap-2.5 text-xs px-4 py-2.5"
                       style={{ borderRadius: '12px', backgroundColor: 'rgb(var(--theme-bg-secondary))', border: '1px solid rgb(var(--theme-border))' }}
                  >
                    <span className="font-semibold font-mono" style={{ color: 'rgb(var(--theme-primary))' }}>{idx.name}</span>
                    <span style={{ color: 'rgb(var(--theme-border))' }}>·</span>
                    <span style={{ color: 'rgb(var(--theme-text-muted))' }}>{idx.columns?.join(', ')}</span>
                    {idx.unique && (
                      <span
                        className="ml-auto px-2 py-0.5 text-[10px] font-semibold"
                        style={{ borderRadius: '9999px', backgroundColor: 'rgba(249, 115, 22, 0.1)', color: 'rgb(249, 115, 22)', border: '1px solid rgba(249, 115, 22, 0.2)' }}
                      >Unique</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 外键关系 */}
          {foreignKeys && foreignKeys.length > 0 && (
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-widest mb-3" style={{ color: 'rgb(var(--theme-text-muted))' }}>外键关系</p>
              <div className="space-y-2">
                {foreignKeys.map((fk: any, i: number) => (
                  <div key={i}
                       className="flex items-center gap-2.5 text-xs px-4 py-2.5"
                       style={{ borderRadius: '12px', backgroundColor: 'rgb(var(--theme-bg-secondary))', border: '1px solid rgb(var(--theme-border))' }}
                  >
                    <span className="font-mono font-semibold px-2 py-1"
                          style={{ borderRadius: '8px', backgroundColor: 'rgb(var(--theme-bg))', color: 'rgb(var(--theme-text))', border: '1px solid rgb(var(--theme-border))' }}
                    >{fk.columns?.join(', ')}</span>
                    <span className="font-bold" style={{ color: 'rgb(var(--theme-text-muted))' }}>→</span>
                    <span className="font-mono font-semibold" style={{ color: 'rgb(var(--theme-primary))' }}>{fk.referenced_table}</span>
                    <span style={{ color: 'rgb(var(--theme-text-muted))' }}>({fk.referenced_columns?.join(', ')})</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* LLM 填充信息 - 资产tab栏从 schema.filled_data 获取数据 */}
          {filledData && (
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-widest mb-3" style={{ color: 'rgb(var(--theme-text-muted))' }}>LLM
                自动填充信息</p>
              <div className="border overflow-hidden" style={{ borderRadius: '16px', borderColor: 'rgb(var(--theme-border))' }}>
                {filledData.before && (
                  <div className="p-5 border-b" style={{ borderColor: 'rgb(var(--theme-border))' }}>
                    <p className="text-xs font-bold uppercase tracking-wider mb-3" style={{ color: 'rgb(var(--theme-text-muted))' }}>填充前状态</p>
                    <div
                      className="flex items-center justify-between px-4 py-3 mb-3"
                      style={{ borderRadius: '12px', backgroundColor: 'rgb(var(--theme-bg-secondary))', border: '1px solid rgb(var(--theme-border))' }}
                    >
                      <span className="text-sm font-medium" style={{ color: 'rgb(var(--theme-text))' }}>缺失注释字段</span>
                      <span className="font-bold text-lg" style={{ color: 'rgb(249, 115, 22)' }}>
                      {filledData.before.missing_count} / {filledData.before.total_fields}</span>
                    </div>
                    {filledData.before.missing_comment_fields?.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {filledData.before.missing_comment_fields.map((f: any, i: number) => (
                          <span key={i}
                                className="text-xs px-2.5 py-1 font-medium"
                                style={{ borderRadius: '9999px', backgroundColor: 'rgba(249, 115, 22, 0.1)', color: 'rgb(249, 115, 22)', border: '1px solid rgba(249, 115, 22, 0.2)' }}
                          >{f.name}</span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                {filledData.fill_result && (
                  <div className="p-5">
                    <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">填充结果</p>
                    <div className="grid grid-cols-2 gap-3 mb-4">
                      <div className="flex items-center justify-between bg-slate-50 border border-slate-100 px-4 py-3"
                           style={{ borderRadius: '12px' }}
                      >
                        <span className="text-slate-600 text-sm font-medium">已填充字段</span>
                        <span className="font-bold text-teal-600 text-lg">{filledData.fill_result.filled_count}</span>
                      </div>
                      <div className="flex items-center justify-between bg-slate-50 border border-slate-100 px-4 py-3"
                           style={{ borderRadius: '12px' }}
                      >
                        <span className="text-slate-600 text-sm font-medium">仍缺失字段</span>
                        <span className="font-bold text-red-500 text-lg"
                        >{filledData.fill_result.still_missing_count}</span>
                      </div>
                    </div>
                    {filledData.fill_result.filled_fields?.length > 0 && (
                      <div>
                        <p className="text-xs text-slate-400 mb-2">字段注释填充结果：</p>
                        <div className="space-y-1.5">
                          {filledData.fill_result.filled_fields.map((f: any, i: number) => (
                            <div key={i}
                                 className="flex flex-col sm:flex-row sm:items-start gap-20 bg-teal-50 border border-teal-100 px-3 py-2 text-xs"
                                 style={{ borderRadius: '10px' }}
                            >
                              <span className="font-mono font-semibold text-teal-800 shrink-0">{f.name}</span>
                              <span className="text-teal-700 break-words leading-relaxed">{f.comment}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
  return typeof document !== 'undefined' ? createPortal(content, document.body) : null
}

// 数据卡片详情弹窗
function DataCardDetailModal({
                               card,
                               datasource,
                               onClose,
                               onSaveSuccess,
                               loadWorkspace,
                               onDataSourcesRefresh,
                             }: {
  card: DataCard;
  datasource: DataSource;
  onClose: () => void;
  onSaveSuccess?: (updatedCard: DataCard) => void;
  loadWorkspace?: (forceRefresh?: boolean) => Promise<void>;
  onDataSourcesRefresh?: () => void;
}) {
  const [activeSection, setActiveSection] = useState<'detail' | 'json'>('detail')
  const [jsonCopied, setJsonCopied] = useState(false)
  // 编辑状态
  const [isEditing, setIsEditing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [editedCardData, setEditedCardData] = useState<any>(null)

  const cardData = parseCardData(card.card_data)
  const rawCardData = typeof card.card_data === 'string' ? JSON.parse(card.card_data) : card.card_data
  const jsonString = JSON.stringify(rawCardData, null, 2)

  // 初始化编辑数据
  const initEditData = useCallback(() => {
    if (cardData) {
      setEditedCardData(JSON.parse(JSON.stringify(cardData)))
    }
  }, [cardData])

  // 开始编辑
  const handleStartEdit = () => {
    initEditData()
    setIsEditing(true)
  }

  // 取消编辑
  const handleCancelEdit = () => {
    setIsEditing(false)
    setEditedCardData(null)
  }

  // 保存编辑
  const handleSaveEdit = async () => {
    if (!editedCardData) return

    setIsSaving(true)
    try {
      const updatedCard: DataCard = {
        ...card,
        card_data: editedCardData as DataCardData,
      }
      const res = await updateDataCard(updatedCard)
      if (res.code === 200) {
        message.success('保存成功')
        setIsEditing(false)
        setEditedCardData(null)
        // 通知父组件卡片已更新
        if (onSaveSuccess) {
          onSaveSuccess(updatedCard)
        }
        onClose()
        // 刷新数据源信息
        loadWorkspace(true)
        onDataSourcesRefresh?.()
      } else {
        message.error(res.msg || '保存失败')
      }
    } catch (error) {
      console.error('保存失败:', error)
      message.error('保存失败，请重试')
    } finally {
      setIsSaving(false)
    }
  }

  // 更新编辑数据
  const updateEditedData = (path: string, value: any) => {
    if (!editedCardData) return
    const newData = JSON.parse(JSON.stringify(editedCardData))
    const keys = path.split('.')
    let obj: any = newData
    for (let i = 0; i < keys.length - 1; i++) {
      obj = obj[keys[i]]
    }
    obj[keys[keys.length - 1]] = value
    setEditedCardData(newData)
  }

  // 当前使用的数据（编辑时使用 editedCardData，否则使用原始数据）
  const currentCardData = isEditing ? editedCardData : cardData

  const handleCopyJson = () => {
    navigator.clipboard.writeText(jsonString).then(() => {
      setJsonCopied(true)
      setTimeout(() => setJsonCopied(false), 2000)
    })
  }

  if (!cardData) {
    const fallbackContent = (
      <div
        className="fixed inset-0 bg-black/50 flex items-center justify-center p-4"
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          zIndex: 9999,
        }}
      >
        <div className="bg-white p-8 shadow-2xl" style={{ borderRadius: '28px' }}>
          <p className="text-slate-500">无法解析卡片数据</p>
          <button onClick={onClose}
                  className="mt-4 px-4 py-2 bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors"
                  style={{ borderRadius: '12px' }}
          >关闭
          </button>
        </div>
      </div>
    )
    return typeof document !== 'undefined' ? createPortal(fallbackContent, document.body) : null
  }

  const sqlMeta = (currentCardData as any).SQLMeta
  const keyConcepts = (currentCardData as any).KeyConcepts
  const abstract = (currentCardData as any).Abstract ?? ''
  const tags = (currentCardData as any).Tags ?? []
  const columns = sqlMeta?.columns ?? []
  const filledData = card.filled_data ?? (rawCardData as any).filled_data

  const cardModalContent = (
    <div
      className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 9999,
      }}
    >
      <div className="bg-white w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col shadow-2xl"
           style={{ borderRadius: '28px' }}
      >

        {/* 头部 */}
        <div
          className="flex items-center justify-between px-6 py-5 border-b flex-shrink-0"
          style={{ borderColor: 'rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))' }}
        >
          <div className="flex items-center gap-3 min-w-0">
            <div
              className="w-11 h-11 flex-shrink-0 flex items-center justify-center"
              style={{ borderRadius: '14px', backgroundColor: 'rgba(var(--theme-primary), 0.1)' }}
            >
              <CreditCard className="w-5 h-5" style={{ color: 'rgb(var(--theme-primary))' }} />
            </div>
            <div className="min-w-0">
              <h3 className="text-lg font-bold flex items-center gap-2 flex-wrap" style={{ color: 'rgb(var(--theme-text))' }}>
                {card.table_name}
                {card.is_view && <span
                  className="text-xs px-2.5 py-0.5 font-medium whitespace-nowrap"
                  style={{ borderRadius: '9999px', backgroundColor: 'rgba(245, 158, 11, 0.1)', color: 'rgb(217, 119, 6)', border: '1px solid rgba(245, 158, 11, 0.2)' }}
                >👁️ 视图</span>}
                {card.is_filled && <span
                  className="text-xs px-2.5 py-0.5 font-medium whitespace-nowrap"
                  style={{ borderRadius: '9999px', backgroundColor: 'rgba(var(--theme-primary), 0.1)', color: 'rgb(var(--theme-primary))', border: '1px solid rgba(var(--theme-primary), 0.2)' }}
                >✨ LLM填充</span>}
              </h3>
              <p className="text-sm mt-0.5" style={{ color: 'rgb(var(--theme-text-muted))' }}>{card.connect_name}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {/* 编辑按钮 - 仅在详情视图且非编辑状态下显示 */}
            {activeSection === 'detail' && !isEditing ? (
              <button
                onClick={handleStartEdit}
                className="flex items-center gap-2 px-4 py-2 text-white text-sm font-medium transition-colors"
                style={{ borderRadius: '12px', backgroundColor: 'rgb(var(--theme-primary))' }}
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"
                  />
                </svg>
                编辑
              </button>
            ) : activeSection === 'detail' ? (
              <>
                <button
                  onClick={handleSaveEdit}
                  disabled={isSaving}
                  className="flex items-center gap-2 px-4 py-2 text-white text-sm font-medium disabled:opacity-50 transition-colors"
                  style={{ borderRadius: '12px', backgroundColor: 'rgb(34, 197, 94)' }}
                >
                  {isSaving ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd"
                            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                            clipRule="evenodd"
                      />
                    </svg>
                  )}
                  {isSaving ? '保存中' : '保存'}
                </button>
                <button
                  onClick={handleCancelEdit}
                  disabled={isSaving}
                  className="flex items-center gap-2 px-4 py-2 text-white text-sm font-medium disabled:opacity-50 transition-colors"
                  style={{ borderRadius: '12px', backgroundColor: 'rgb(var(--theme-border))', color: 'rgb(var(--theme-text-muted))' }}
                >
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd"
                          d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                          clipRule="evenodd"
                    />
                  </svg>
                  取消
                </button>
              </>
            ) : null}
            {/* 详情 / JSON 切换 */}
            <div className="flex items-center p-1 gap-0.5" style={{ borderRadius: '12px', backgroundColor: 'rgb(var(--theme-bg-secondary))' }}>
              <button
                onClick={() => setActiveSection('detail')}
                className={`px-3.5 py-1.5 text-xs font-semibold transition-all whitespace-nowrap ${activeSection === 'detail' ? 'shadow-sm' : ''}`}
                style={{ borderRadius: '9px', backgroundColor: activeSection === 'detail' ? 'rgb(var(--theme-bg))' : 'transparent', color: activeSection === 'detail' ? 'rgb(var(--theme-text))' : 'rgb(var(--theme-text-muted))' }}
              >
                详情
              </button>
              <button
                onClick={() => setActiveSection('json')}
                className={`px-3.5 py-1.5 text-xs font-semibold transition-all whitespace-nowrap ${activeSection === 'json' ? 'shadow-sm' : ''}`}
                style={{ borderRadius: '9px', backgroundColor: activeSection === 'json' ? 'rgb(var(--theme-bg))' : 'transparent', color: activeSection === 'json' ? 'rgb(var(--theme-text))' : 'rgb(var(--theme-text-muted))' }}
              >
                JSON
              </button>
            </div>
            <button onClick={onClose} className="p-2 transition-colors flex-shrink-0"
                    style={{ borderRadius: '12px', color: 'rgb(var(--theme-text-muted))' }}
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {activeSection === 'detail' ? (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">

            {/* 基本信息紧凑条 */}
            <div className="flex items-center gap-x-5 gap-y-2 flex-wrap bg-slate-50 border border-slate-100 px-5 py-3.5"
                 style={{ borderRadius: '16px' }}
            >
              <span className="flex items-center gap-1.5 whitespace-nowrap">
                <span className="text-slate-400 text-xs font-medium">数据库</span>
                <span className="text-slate-200 text-xs">:</span>
                <span className="font-bold text-slate-700 uppercase text-xs">{datasource?.db_type ?? '-'}</span>
              </span>
              <span className="text-slate-200 text-xs self-center">|</span>
              <span className="flex items-center gap-1.5 whitespace-nowrap">
                <span className="text-slate-400 text-xs font-medium">字段数</span>
                <span className="text-slate-200 text-xs">:</span>
                <span className="font-bold text-blue-600">{columns.length}</span>
              </span>
              <span className="text-slate-200 text-xs self-center">|</span>
              <span className="flex items-center gap-1.5 whitespace-nowrap">
                <span className="text-slate-400 text-xs font-medium">主键</span>
                <span className="text-slate-200 text-xs">:</span>
                <span className="font-mono font-semibold text-slate-700 text-xs">{sqlMeta?.pk ||
                  <span className="text-slate-300">-</span>}</span>
              </span>
              <span className="text-slate-200 text-xs self-center">|</span>
              <span className="flex items-center gap-1.5 whitespace-nowrap">
                <span className="text-slate-400 text-xs font-medium">更新</span>
                <span className="text-slate-200 text-xs">:</span>
                <span className="text-slate-600 text-xs">{new Date(card.updated_at).toLocaleString('zh-CN')}</span>
              </span>
            </div>

            {/* 描述 */}
            {(abstract || isEditing) && (
              <div className="bg-slate-50 border border-slate-100 px-5 py-4" style={{ borderRadius: '16px' }}>
                <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest mb-2">描述
                  (Abstract)</p>
                {isEditing ? (
                  <textarea
                    value={abstract}
                    onChange={(e) => updateEditedData('Abstract', e.target.value)}
                    className="w-full p-3 border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm leading-relaxed bg-white"
                    style={{ borderRadius: '8px' }}
                    rows={3}
                    placeholder="请输入描述..."
                  />
                ) : (
                  <p className="text-sm text-slate-700 leading-relaxed indent-4">{abstract ||
                    <span className="italic text-slate-400">暂无描述</span>}</p>
                )}
              </div>
            )}

            {/* 标签 */}
            {(tags.length > 0 || isEditing) && (
              <div>
                <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest mb-3">标签 (Tags)</p>
                {isEditing ? (
                  <input
                    type="text"
                    value={tags.join(', ')}
                    onChange={(e) => updateEditedData('Tags', e.target.value.split(',').map((t: string) => t.trim()).filter(Boolean))}
                    className="w-full p-3 border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm bg-white"
                    style={{ borderRadius: '8px' }}
                    placeholder="请输入标签，用逗号分隔..."
                  />
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {tags.length > 0 ? (
                      tags.map((t: string, i: number) => (
                        <span key={i}
                              className="px-3 py-1.5 bg-slate-100 text-slate-700 text-xs font-medium border border-slate-200"
                              style={{ borderRadius: '9999px' }}
                        >{t}</span>
                      ))
                    ) : (
                      <span className="text-slate-400 text-xs italic">暂无标签</span>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* 关键概念 */}
            {(keyConcepts || isEditing) && (
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-widest mb-3" style={{ color: 'rgb(var(--theme-text-muted))' }}>关键概念 (Key
                  Concepts)</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {/* 主题 */}
                  <div className="border px-4 py-3" style={{ borderRadius: '14px', borderColor: 'rgba(124, 58, 237, 0.3)', backgroundColor: 'rgba(124, 58, 237, 0.05)' }}>
                    <span className="text-[10px] font-bold uppercase tracking-widest block mb-1.5" style={{ color: 'rgb(124, 58, 237)' }}>主题 (Canonical Topic)</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={keyConcepts?.canonical_topic || ''}
                        onChange={(e) => updateEditedData('KeyConcepts.canonical_topic', e.target.value)}
                        className="w-full p-2 border focus:outline-none focus:ring-2 text-sm font-bold"
                        style={{ borderRadius: '8px', borderColor: 'rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))', color: 'rgb(var(--theme-text))' }}
                        placeholder="请输入主题..."
                      />
                    ) : (
                      <p className="font-bold text-sm" style={{ color: 'rgb(217, 119, 6)' }}>{keyConcepts?.canonical_topic || '-'}</p>
                    )}
                  </div>
                  {/* 别名 */}
                  <div className="border px-4 py-3" style={{ borderRadius: '14px', borderColor: 'rgb(var(--theme-border))', backgroundColor: 'rgba(var(--theme-bg-secondary), 0.5)' }}>
                    <span className="text-[10px] font-bold uppercase tracking-widest block mb-1.5" style={{ color: 'rgb(var(--theme-text-muted))' }}>别名 (Alias)</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={(keyConcepts?.alias ?? []).join(', ')}
                        onChange={(e) => updateEditedData('KeyConcepts.alias', e.target.value.split(',').map((t: string) => t.trim()).filter(Boolean))}
                        className="w-full p-2 border focus:outline-none focus:ring-2 text-sm"
                        style={{ borderRadius: '8px', borderColor: 'rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))', color: 'rgb(var(--theme-text))' }}
                        placeholder="请输入别名，用逗号分隔..."
                      />
                    ) : (
                      <div className="flex flex-wrap gap-1.5 mt-1">
                        {(keyConcepts?.alias ?? []).map((a: string, i: number) => (
                          <span key={i}
                                className="text-xs border px-2 py-0.5 font-medium"
                                style={{ borderRadius: '9999px', backgroundColor: 'rgb(var(--theme-bg))', borderColor: 'rgb(var(--theme-border))', color: 'rgb(var(--theme-text))' }}
                          >{a}</span>
                        ))}
                        {(!keyConcepts?.alias || keyConcepts?.alias.length === 0) &&
                          <span className="text-xs" style={{ color: 'rgb(var(--theme-text-muted))' }}>-</span>}
                      </div>
                    )}
                  </div>
                  {/* 关键实体 */}
                  <div className="border px-4 py-3" style={{ borderRadius: '14px', borderColor: 'rgba(59, 130, 246, 0.3)', backgroundColor: 'rgba(59, 130, 246, 0.05)' }}>
                    <span className="text-[10px] font-bold uppercase tracking-widest block mb-1.5" style={{ color: 'rgb(59, 130, 246)' }}>关键实体 (Key Entities)</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={(keyConcepts?.key_entities ?? []).join(', ')}
                        onChange={(e) => updateEditedData('KeyConcepts.key_entities', e.target.value.split(',').map((t: string) => t.trim()).filter(Boolean))}
                        className="w-full p-2 border focus:outline-none focus:ring-2 text-sm"
                        style={{ borderRadius: '8px', borderColor: 'rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))', color: 'rgb(var(--theme-text))' }}
                        placeholder="请输入关键实体，用逗号分隔..."
                      />
                    ) : (
                      <div className="flex flex-wrap gap-1.5 mt-1">
                        {(keyConcepts?.key_entities ?? []).map((e: string, i: number) => (
                          <span key={i}
                                className="text-xs border px-2 py-0.5 font-medium"
                                style={{ borderRadius: '9999px', backgroundColor: 'rgba(59, 130, 246, 0.1)', borderColor: 'rgba(59, 130, 246, 0.3)', color: 'rgb(59, 130, 246)' }}
                          >{e}</span>
                        ))}
                        {(!keyConcepts?.key_entities || keyConcepts?.key_entities.length === 0) &&
                          <span className="text-xs" style={{ color: 'rgb(var(--theme-text-muted))' }}>-</span>}
                      </div>
                    )}
                  </div>
                  {/* 适用场景 */}
                  <div className="border px-4 py-3" style={{ borderRadius: '14px', borderColor: 'rgba(168, 85, 247, 0.3)', backgroundColor: 'rgba(168, 85, 247, 0.05)' }}>
                    <span className="text-[10px] font-bold uppercase tracking-widest block mb-1.5" style={{ color: 'rgb(168, 85, 247)' }}>适用场景 (Applicable Scenarios)</span>
                    {isEditing ? (
                      <input
                        type="text"
                        value={(keyConcepts?.applicable_scenarios ?? []).join(', ')}
                        onChange={(e) => updateEditedData('KeyConcepts.applicable_scenarios', e.target.value.split(',').map((t: string) => t.trim()).filter(Boolean))}
                        className="w-full p-2 border focus:outline-none focus:ring-2 text-sm"
                        style={{ borderRadius: '8px', borderColor: 'rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))', color: 'rgb(var(--theme-text))' }}
                        placeholder="请输入适用场景，用逗号分隔..."
                      />
                    ) : (
                      <div className="flex flex-wrap gap-1.5 mt-1">
                        {(keyConcepts?.applicable_scenarios ?? []).map((s: string, i: number) => (
                          <span key={i}
                                className="text-xs border px-2 py-0.5 font-medium"
                                style={{ borderRadius: '9999px', backgroundColor: 'rgba(168, 85, 247, 0.1)', borderColor: 'rgba(168, 85, 247, 0.3)', color: 'rgb(168, 85, 247)' }}
                          >{s}</span>
                        ))}
                        {(!keyConcepts?.applicable_scenarios || keyConcepts?.applicable_scenarios.length === 0) &&
                          <span className="text-xs" style={{ color: 'rgb(var(--theme-text-muted))' }}>-</span>}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* 字段信息 */}
            {columns.length > 0 && (() => {
              const filledFieldNames = new Set<string>((filledData?.fill_result?.filled_fields ?? []).map((f: any) => f.name))
              return (
                <div>
                  <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest mb-3">字段信息 (SQL
                    Meta)</p>
                  <div className="overflow-hidden border border-slate-100" style={{ borderRadius: '16px' }}>
                    <table className="w-full text-sm">
                      <thead>
                      <tr className="bg-slate-50/80 border-b border-slate-100 text-left">
                        <th className="px-4 py-3 w-10 font-semibold text-slate-300 text-xs">#</th>
                        <th className="px-4 py-3 font-semibold text-slate-500 text-xs">字段名</th>
                        <th className="px-4 py-3 font-semibold text-slate-500 text-xs">类型</th>
                        <th className="px-4 py-3 font-semibold text-slate-500 text-xs min-w-[200px]">注释</th>
                      </tr>
                      </thead>
                      <tbody>
                      {columns.map((col: {
                        name: string;
                        type: string;
                        comment?: string;
                        is_primary?: boolean;
                        is_foreign?: boolean
                      }, i: number) => {
                        const isAiFilled = filledFieldNames.has(col.name)
                        return (
                          <tr key={i}
                              className={`border-b border-slate-50 transition-colors last:border-0 ${isAiFilled ? 'hover:bg-purple-50/30' : 'hover:bg-indigo-50/20'}`}
                          >
                            <td className="px-4 py-3 text-slate-200 text-xs font-mono">{i + 1}</td>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-mono font-semibold text-slate-800 text-sm">{col.name}</span>
                                {col.is_primary &&
                                  <span className="text-[10px] bg-blue-500 text-white px-1.5 py-0.5 font-semibold"
                                        style={{ borderRadius: '9999px' }}
                                  >PK</span>}
                                {col.is_foreign &&
                                  <span className="text-[10px] bg-amber-500 text-white px-1.5 py-0.5 font-semibold"
                                        style={{ borderRadius: '9999px' }}
                                  >FK</span>}
                                {isAiFilled && <span
                                  className="text-[10px] bg-purple-100 text-purple-600 border border-purple-200 px-1.5 py-0.5 font-semibold"
                                  style={{ borderRadius: '9999px' }}
                                >✨ AI</span>}
                              </div>
                            </td>
                            <td className="px-4 py-3">
                              <span className="font-mono text-xs text-slate-600 bg-slate-100 px-2 py-1"
                                    style={{ borderRadius: '8px' }}
                              >{col.type}</span>
                            </td>
                            <td className="px-4 py-3 text-xs">
                              {isEditing ? (
                                <input
                                  type="text"
                                  value={col.comment || ''}
                                  onChange={(e) => {
                                    const newColumns = [...columns]
                                    newColumns[i] = {
                                      ...newColumns[i],
                                      comment: e.target.value,
                                    }
                                    updateEditedData('SQLMeta.columns', newColumns)
                                  }}
                                  className="w-full p-2 border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-xs bg-white"
                                  style={{ borderRadius: '8px' }}
                                  placeholder="请输入注释..."
                                />
                              ) : (
                                col.comment
                                  ? <span className={isAiFilled ? 'text-purple-700' : 'text-slate-600'}
                                  >{col.comment}</span>
                                  : <span className="text-slate-300 italic">暂无注释</span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )
            })()}

            {/* 外键关联关系 */}
            {(sqlMeta?.foreign_keys ?? []).length > 0 && (
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-widest mb-3" style={{ color: 'rgb(var(--theme-text-muted))' }}>外键关联关系</p>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {(sqlMeta?.foreign_keys ?? []).map((fk: any, idx: number) => (
                    <div key={idx} className="border p-4"
                         style={{ borderRadius: '14px', borderColor: 'rgba(245, 158, 11, 0.3)', backgroundColor: 'rgba(245, 158, 11, 0.05)' }}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <Link2 className="w-4 h-4" style={{ color: 'rgb(245, 158, 11)' }} />
                        <span className="font-semibold text-sm" style={{ color: 'rgb(217, 119, 6)' }}>{fk.name || '外键'}</span>
                      </div>
                      <div className="space-y-2 text-xs">
                        {/* 关联关系展示 */}
                        <div className="flex items-center justify-between p-2 border"
                             style={{ borderRadius: '8px', borderColor: 'rgba(245, 158, 11, 0.3)', backgroundColor: 'rgb(var(--theme-bg))' }}
                        >
                          <span className="font-mono text-xs" style={{ color: 'rgb(var(--theme-text))' }}>{(fk.columns ?? []).join(', ')}</span>
                          <ArrowRight className="w-3 h-3 mx-1" style={{ color: 'rgb(245, 158, 11)' }} />
                          <span className="font-mono font-semibold text-xs" style={{ color: 'rgb(217, 119, 6)' }}>{fk.referenced_table}.{(fk.referenced_columns ?? []).join(', ')}</span>
                        </div>
                        {/* 详细信息 */}
                        <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] pt-1" style={{ color: 'rgb(var(--theme-text-muted))' }}>
                          <span>源字段: <span className="font-mono" style={{ color: 'rgb(var(--theme-text))' }}>{(fk.columns ?? []).join(', ')}</span></span>
                          <span>目标: <span className="font-mono" style={{ color: 'rgb(217, 119, 6)' }}>{fk.referenced_table}</span></span>
                          <span>目标字段: <span className="font-mono" style={{ color: 'rgb(var(--theme-text))' }}>{(fk.referenced_columns ?? []).join(', ')}</span></span>
                        </div>
                        {(fk.on_update || fk.on_delete) && (
                          <div
                            className="flex items-center gap-2 pt-1 mt-1 text-[10px]"
                            style={{ borderTop: '1px solid rgba(245, 158, 11, 0.2)', color: 'rgb(var(--theme-text-muted))' }}
                          >
                            <span>操作:</span>
                            {fk.on_update && <span>更新: {fk.on_update}</span>}
                            {fk.on_delete && <span>删除: {fk.on_delete}</span>}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          /* JSON 视图 */
          <div className="flex-1 flex flex-col overflow-hidden">
            <div
              className="flex items-center justify-between px-5 py-3 border-b border-slate-100 bg-slate-50/60 flex-shrink-0"
            >
              <p className="text-xs font-semibold text-slate-500">完整 JSON 数据 · {card.table_name}</p>
              <button
                onClick={handleCopyJson}
                className={`flex items-center gap-1.5 text-xs font-semibold px-3.5 py-1.5 transition-all ${jsonCopied ? 'bg-teal-50 text-teal-600 border border-teal-200' : 'bg-white text-slate-600 border border-slate-200 hover:border-indigo-300 hover:text-indigo-600'}`}
                style={{ borderRadius: '9999px' }}
              >
                {jsonCopied ? '✓ 已复制' : '复制 JSON'}
              </button>
            </div>
            <div className="flex-1 overflow-auto p-5">
              <pre
                className="text-xs text-slate-700 font-mono leading-relaxed whitespace-pre-wrap break-all bg-slate-50 p-5 border border-slate-100"
                style={{ borderRadius: '14px' }}
              >
                {jsonString}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  )
  return typeof document !== 'undefined' ? createPortal(cardModalContent, document.body) : null
}

const WorkspaceDetailPage = () => {
  const params = useParams()
  const searchParams = useSearchParams()
  const { refreshDataSources } = useDataSources()
  const [activeTab, setActiveTab] = useState('overview')
  const [loading, setLoading] = useState(true)
  const [workspace, setWorkspace] = useState<DataSourceItem | null>(null)
  const [error, setError] = useState<string | null>(null)
  const workspaceId = typeof params?.id === 'string' ? params.id : undefined

  // 深色模式检测
  const [isDark, setIsDark] = useState(false)
  useEffect(() => {
    const checkDark = () => setIsDark(document.documentElement.getAttribute('data-theme') === 'dark')
    checkDark()
    const observer = new MutationObserver(checkDark)
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])

  // 从 URL 参数初始化 activeTab
  useEffect(() => {
    const tabParam = searchParams.get('tab')
    const validTabs = ['overview', 'assets', 'cards', 'enhance', 'ask', 'jobs', 'knowledge']
    if (tabParam && validTabs.includes(tabParam)) {
      setActiveTab(tabParam)
    }
  }, [searchParams])

  // 资产 tab: 选中的表
  const [selectedSchema, setSelectedSchema] = useState<SchemaItem | null>(null)

  // 卡片 tab 状态
  const [cardsLoading, setCardsLoading] = useState(false)
  const [allCards, setAllCards] = useState<DataCard[]>([])
  const [cardsPage, setCardsPage] = useState(1)
  const [selectedCard, setSelectedCard] = useState<{ card: DataCard; datasource: DataSource } | null>(null)

  // 资产（表信息）分页状态
  const SCHEMAS_PAGE_SIZE = 20
  const [schemasPage, setSchemasPage] = useState(1)

  // 资产搜索状态
  const [assetsSearch, setAssetsSearch] = useState('')
  // 资产类型筛选状态: 'all' | 'table' | 'view'
  const [assetsTypeFilter, setAssetsTypeFilter] = useState<'all' | 'table' | 'view'>('all')

  // 卡片搜索状态
  const [cardsSearch, setCardsSearch] = useState('')
  // 卡片搜索防抖句柄
  const [cardsSearchDebounce, setCardsSearchDebounce] = useState<number | null>(null)
  // fetchCards 请求令牌：用于防抖场景下丢弃过期响应
  const fetchCardsReqTokenRef = useRef(0)
  // 标记本次 loading 的来源类型：'search' = 用户输入搜索词；'page' = 切 tab / 刷新 / 翻页
  // 用 ref 而非 state：cardsLoading 这个 state 已会触发 re-render，无须再多一个 state
  // 内容区是否需要显示 loading 蒙层由此判断（搜索时只走顶部 message，不在内容区覆盖）
  const cardsLoadingKindRef = useRef<'search' | 'page' | null>(null)
  // 搜索提示消息生命周期状态：用于避免连续搜索时 message 反复弹/关造成的视觉跳动
  // open: 当前是否正在显示 "搜索中..."
  // closeTimer: 延迟关闭的定时器句柄（搜索完成后不会立刻关闭，等待 grace 期间是否继续输入）
  const searchMsgStateRef = useRef<{ open: boolean; closeTimer: number | null }>({
    open: false,
    closeTimer: null,
  })
  // 搜索消息的固定 key（antd message 标识）
  const SEARCH_MSG_KEY = 'cards-search-loading'
  // 搜索完成到真正关闭 message 的缓冲时间（期间如有新搜索则取消关闭）
  const SEARCH_CLOSE_GRACE_MS = 800
  // 卡片类型筛选状态: 'all' | 'table' | 'view'
  const [cardsTypeFilter, setCardsTypeFilter] = useState<'all' | 'table' | 'view'>('all')

  // 资产数据（派生变量）
  const schemas = workspace?.schemas ?? []

  // 卡片分页状态
  const CARDS_PAGE_SIZE = 21
  const [showSettings, setShowSettings] = useState(false)
  const [editingName, setEditingName] = useState(false)
  const [connectName, setConnectName] = useState('')
  const [savingName, setSavingName] = useState(false)

  // 增强 tab 状态
  const [enhanceFile, setEnhanceFile] = useState<File | null>(null)
  const [enhanceSheetName, setEnhanceSheetName] = useState('')
  const [enhanceIsUploading, setEnhanceIsUploading] = useState(false)
  const [enhanceFieldMapping, setEnhanceFieldMapping] = useState({
    has_title: '1' as '0' | '1',
    tb_name_index: 'A',
    tb_desc_index: 'B',
    field_name_index: 'B',
    field_desc_index: 'E',
    field_value_desc_index: 'F',
  })
  const [enhanceResult, setEnhanceResult] = useState<any>(null)
  const [enhanceDragOver, setEnhanceDragOver] = useState(false)

  // ========== 问数 Tab 相关状态 ==========
  const [askQuestion, setAskQuestion] = useState('')
  const [askQueryStatus, setAskQueryStatus] = useState<'idle' | 'analyzing' | 'error'>('idle')
  const [askQueryResult, setAskQueryResult] = useState<any>(null)
  const [askError, setAskError] = useState<string | null>(null)
  const [askQueryStep, setAskQueryStep] = useState(0)
  const [askProgressPercent, setAskProgressPercent] = useState(0)
  const [selectedDataSourceIds, setSelectedDataSourceIds] = useState<string[]>([])
  const [isMultiSelectMode, setIsMultiSelectMode] = useState(false)

  // 预设问题
  const [presetQuestions] = useState<string[]>([
    '列出2026年5月份销量排行前10的产品信息',
    '统计今年3月份的网购订单总量',
    '查询库存不足的商品有哪些',
    '去年12月什么商品卖的最好',
  ])

  // 数据卡片详情弹框状态
  const [selectedDataCards, setSelectedDataCards] = useState<any[]>([])
  const [isCardDetailOpen, setIsCardDetailOpen] = useState(false)
  const [activeCardIndex, setActiveCardIndex] = useState(0)

  // 复制成功提示状态
  const [copiedClusterIndex, setCopiedClusterIndex] = useState<number | null>(null)

  // ========== 盘点相关状态 ==========
  const [showInventoryTypeModal, setShowInventoryTypeModal] = useState(false)
  const [showTargetInventoryModal, setShowTargetInventoryModal] = useState(false)
  const [showGlobalInventoryModal, setShowGlobalInventoryModal] = useState(false)
  const [inventoryJobType, setInventoryJobType] = useState<'target' | 'global'>('target')

  // 全域盘点任务列表状态
  // 全域盘点结果状态
  const [relationshipCards, setRelationshipCards] = useState<RelationshipCardItem[]>([])
  const [tableRelationships, setTableRelationships] = useState<GlobalInventory[]>([])
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[], edges: GraphEdge[] }>({
    nodes: [],
    edges: [],
  })
  const [loadingGlobalResult, setLoadingGlobalResult] = useState(false)

  // 问数查询进度步骤（用户友好文案）
  const askQuerySteps = [
    {
      id: 1,
      name: '向量检索',
      description: '正在基于向量检索召回数据卡片...',
    },
    {
      id: 2,
      name: '回查数据库',
      description: '正在回查数据库获取完整卡片内容...',
    },
    {
      id: 3,
      name: 'AI 分析生成 SQL',
      description: '正在基于大模型对用户提问做语义分析并生成查询SQL语句...',
    },
    {
      id: 4,
      name: '执行 SQL 查询',
      description: '正在连接数据源执行SQL获取结果...',
    },
    {
      id: 5,
      name: '结果合并',
      description: '正在进行查询结果融合...',
    },
  ]

  // 问数查询进度条动画时间配置（单位：毫秒，可根据需要调整各阶段进度条停留时间）
  const askProgressStepConfig = [
    { step: 1, percent: 12, ms: 2400 },
    { step: 2, percent: 25, ms: 900 },
    { step: 3, percent: 75, ms: 5000 },
    { step: 4, percent: 80, ms: 900 },
    { step: 5, percent: 92, ms: 2100 },
  ]

  // 问数查询的 AbortController
  const askAbortControllerRef = useRef<AbortController | null>(null)
  const askProgressIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const askCancelFlagRef = useRef(false)
  const askTimeoutIdsRef = useRef<NodeJS.Timeout[]>([])
  const askProgressRef = useRef(0)

  // 获取数据源列表
  const {
    dataSources: allDataSources,
    loading: dataSourcesLoading,
    fetchDataSources,
  } = useDataSources()

  // 当切换到多数据源模式时，确保数据源已加载
  useEffect(() => {
    if (isMultiSelectMode && (allDataSources || []).length === 0 && !dataSourcesLoading) {
      fetchDataSources()
    }
  }, [isMultiSelectMode, (allDataSources || []).length, dataSourcesLoading, fetchDataSources])

  // 全域盘点：数据源 id -> 名称（跨源关联展示，与 GlobalInventory 一致）
  const globalInventoryDsNameMap = useMemo(() => {
    const map = new Map<string, string>()
    ;(allDataSources || []).forEach((ds) => map.set(ds.id, ds.connect_name))
    return map
  }, [allDataSources])

  /** 当前工作空间数据源曾参与跨源关系发现的其他数据源 */
  const globalInventoryRelatedDatasources = useMemo(() => {
    if (!workspace?.id) return []
    const currentId = workspace.id
    const relatedDsMap = new Map<string, string>()

    tableRelationships.forEach((rel) => {
      if (rel.is_cross_source) {
        if (rel.table_a_datasource_id === currentId && rel.table_b_datasource_id && rel.table_b_datasource_name) {
          relatedDsMap.set(rel.table_b_datasource_id, rel.table_b_datasource_name)
        }
        if (rel.table_b_datasource_id === currentId && rel.table_a_datasource_id && rel.table_a_datasource_name) {
          relatedDsMap.set(rel.table_a_datasource_id, rel.table_a_datasource_name)
        }
      }
    })

    relationshipCards.forEach((card) => {
      if (card.related_datasource_ids?.length) {
        card.related_datasource_ids.forEach((dsId) => {
          if (dsId !== currentId) {
            const dsName = globalInventoryDsNameMap.get(dsId)
            if (dsName) relatedDsMap.set(dsId, dsName)
          }
        })
      }
      if (card.card?.Relationships) {
        card.card.Relationships.forEach((rel: {
          is_cross_source?: boolean;
          related_datasource_id?: string;
          related_datasource_name?: string
        }) => {
          if (rel.is_cross_source && rel.related_datasource_id && rel.related_datasource_name && rel.related_datasource_id !== currentId) {
            relatedDsMap.set(rel.related_datasource_id, rel.related_datasource_name)
          }
        })
      }
    })

    return Array.from(relatedDsMap.entries()).map(([id, name]) => ({
      id,
      name,
    }))
  }, [workspace?.id, tableRelationships, relationshipCards, globalInventoryDsNameMap])

  /** 关系图谱图例：合并所有可出现的数据源 id→名称，避免只显示 UUID */
  const workspaceRelationshipGraphDatasourceNameMap = useMemo(() => {
    const m = new Map<string, string>()
    if (workspace?.id && workspace.connect_name) {
      m.set(workspace.id, workspace.connect_name)
    }
    ;(allDataSources || []).forEach((ds) => m.set(ds.id, ds.connect_name))
    graphData.nodes.forEach((n) => {
      if (n.datasource_id) {
        const label = n.datasource_name || m.get(n.datasource_id)
        if (label) m.set(n.datasource_id, label)
      }
    })
    tableRelationships.forEach((rel) => {
      if (rel.table_a_datasource_id && rel.table_a_datasource_name) {
        m.set(rel.table_a_datasource_id, rel.table_a_datasource_name)
      }
      if (rel.table_b_datasource_id && rel.table_b_datasource_name) {
        m.set(rel.table_b_datasource_id, rel.table_b_datasource_name)
      }
    })
    relationshipCards.forEach((card) => {
      card.related_datasource_ids?.forEach((id) => {
        const name = globalInventoryDsNameMap.get(id)
        if (name) m.set(id, name)
      })
      card.card?.Relationships?.forEach((rel: { related_datasource_id?: string; related_datasource_name?: string }) => {
        if (rel.related_datasource_id && rel.related_datasource_name) {
          m.set(rel.related_datasource_id, rel.related_datasource_name)
        }
      })
    })
    return m
  }, [workspace?.id, workspace?.connect_name, allDataSources, graphData.nodes, tableRelationships, relationshipCards, globalInventoryDsNameMap])

  // 资产搜索过滤
  const filteredSchemas = useMemo(() => {
    let result = schemas
    // 按类型筛选
    if (assetsTypeFilter === 'table') {
      result = result.filter((s: SchemaItem) => !s.is_view)
    } else if (assetsTypeFilter === 'view') {
      result = result.filter((s: SchemaItem) => s.is_view)
    }
    // 按关键词搜索
    if (assetsSearch.trim()) {
      const search = assetsSearch.toLowerCase()
      result = result.filter((s: SchemaItem) =>
        s.table_name.toLowerCase().includes(search) ||
        (s.schema_text?.description?.toLowerCase() || '').includes(search)
      )
    }
    return result
  }, [schemas, assetsSearch, assetsTypeFilter])

  // 卡片类型筛选（搜索由后端 q 参数完成，前端只按 view/table 过滤）
  const filteredCards = useMemo(() => {
    let result = allCards
    // 按类型筛选
    if (cardsTypeFilter === 'table') {
      result = result.filter((card: DataCard) => !card.is_view)
    } else if (cardsTypeFilter === 'view') {
      result = result.filter((card: DataCard) => card.is_view)
    }
    return result
  }, [allCards, cardsTypeFilter])

  // 初始化选中当前工作区；单数据源模式下强制使用当前工作区
  useEffect(() => {
    if (workspace?.id && selectedDataSourceIds.length === 0) {
      setSelectedDataSourceIds([workspace.id])
    }
  }, [workspace?.id])

  // 问数 tab：单数据源模式下强制使用当前工作区，不展示其他可选
  useEffect(() => {
    if (activeTab === 'ask' && !isMultiSelectMode && workspace?.id) {
      setSelectedDataSourceIds(prev => (prev.length === 1 && prev[0] === workspace.id ? prev : [workspace.id]))
    }
  }, [activeTab, isMultiSelectMode, workspace?.id])

  // 切换离开问数 tab 时清空本次查询结果，避免切回其他 tab 仍看到上次结果
  const prevActiveTabRef = useRef(activeTab)
  useEffect(() => {
    if (prevActiveTabRef.current === 'ask' && activeTab !== 'ask') {
      setAskQueryResult(null)
      setAskError(null)
      setAskQueryStep(0)
      setAskProgressPercent(0)
      askProgressRef.current = 0
      if (askProgressIntervalRef.current) {
        clearInterval(askProgressIntervalRef.current)
        askProgressIntervalRef.current = null
      }
    }
    prevActiveTabRef.current = activeTab
  }, [activeTab])

  // 更新进度（存整数，避免 63.9999999% 等显示）
  const updateAskProgress = (value: number) => {
    const clamped = Math.min(100, Math.max(0, value))
    const rounded = Math.round(clamped)
    askProgressRef.current = rounded
    setAskProgressPercent(rounded)
  }

  // SQL格式化函数
  const formatAskSQL = (sql: string): string => {
    const mainKeywords = ['SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT', 'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN']
    let formatted = sql.trim()
    mainKeywords.forEach(keyword => {
      const regex = new RegExp(`\\s+(${keyword})\\s+`, 'gi')
      formatted = formatted.replace(regex, '\n$1 ')
    })
    formatted = formatted.replace(/\s+(AND|OR)\s+/gi, '\n  $1 ')
    formatted = formatted.replace(/\n{3,}/g, '\n\n')
    return formatted.trim()
  }

  // 智能格式化单元格数据
  const formatAskCellValue = (cell: any): React.ReactNode => {
    if (cell === null || cell === undefined) {
      return <span className="text-gray-400 italic">N/A</span>
    }
    if (typeof cell === 'object') {
      if (cell.type && cell.value !== undefined) {
        const value = String(cell.value)
        if (cell.type.toUpperCase() === 'UUID') {
          return <span className="font-mono text-xs text-blue-600">{value}</span>
        }
        return <span className="text-gray-700">{value}</span>
      }
      if (cell instanceof Date) {
        return <span className="text-gray-700">{cell.toLocaleString('zh-CN')}</span>
      }
      try {
        return <span className="text-gray-600 text-xs font-mono">{JSON.stringify(cell)}</span>
      } catch {
        return <span className="text-gray-400 italic">[对象]</span>
      }
    }
    const strValue = String(cell)
    if (strValue.trim() === '') {
      return <span className="text-gray-400 italic">（空）</span>
    }
    const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
    if (uuidPattern.test(strValue)) {
      return <span className="font-mono text-xs text-blue-600" title={strValue}>{strValue}</span>
    }
    const timePattern = /^\d{2}:\d{2}:\d{2}(\.\d+)?$/
    if (timePattern.test(strValue)) {
      return <span className="text-gray-700">{strValue}</span>
    }
    const datePattern = /^\d{4}-\d{2}-\d{2}(T|\s)\d{2}:\d{2}:\d{2}/
    if (datePattern.test(strValue)) {
      try {
        const date = new Date(strValue)
        if (!isNaN(date.getTime())) {
          return <span className="text-gray-700">{date.toLocaleString('zh-CN')}</span>
        }
      } catch { /* ignore */
      }
    }
    if (typeof cell === 'number' || !isNaN(Number(strValue))) {
      const num = typeof cell === 'number' ? cell : Number(strValue)
      if (Math.abs(num) >= 1000) {
        return <span className="text-gray-700 font-medium">{num.toLocaleString('zh-CN')}</span>
      }
      return <span className="text-gray-700">{strValue}</span>
    }
    if (typeof cell === 'boolean') {
      return (
        <span
          className={`px-2 py-0.5 text-xs rounded ${cell ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}
        >
          {cell ? '是' : '否'}
        </span>
      )
    }
    if (strValue.length > 100) {
      return (
        <span className="text-gray-700" title={strValue}>
          {strValue.substring(0, 100)}...
        </span>
      )
    }
    return <span className="text-gray-700">{strValue}</span>
  }

  // 处理复制SQL
  const handleCopyAskSQL = (sql: string, clusterIndex: number) => {
    navigator.clipboard.writeText(sql)
    setCopiedClusterIndex(clusterIndex)
    setTimeout(() => {
      setCopiedClusterIndex(null)
    }, 2000)
  }

  // 根据表名查找对应的数据卡片
  const findDataCardByTableName = (tableName: string): any | null => {
    if (!askQueryResult?.data?.data_cards) return null
    return askQueryResult.data.data_cards.find((card: any) => card.table_name === tableName) || null
  }

  // 根据多个表名查找对应的数据卡片
  const findDataCardsByTableNames = (tableNames: string[]): any[] => {
    if (!askQueryResult?.data?.data_cards) return []
    return tableNames
      .map(tableName => findDataCardByTableName(tableName))
      .filter((card): card is any => card !== null)
  }

  // 打开数据卡片详情：支持传入表名数组或卡片对象数组（与接口 data_cards 一致）
  const handleOpenAskCardDetail = (tableNamesOrCards: string[] | any[]) => {
    if (!Array.isArray(tableNamesOrCards) || tableNamesOrCards.length === 0) return
    const cards = typeof tableNamesOrCards[0] === 'string'
      ? findDataCardsByTableNames(tableNamesOrCards as string[])
      : tableNamesOrCards
    if (cards.length > 0) {
      setSelectedDataCards(cards)
      setActiveCardIndex(0)
      setIsCardDetailOpen(true)
    }
  }

  // 关闭数据卡片详情
  const handleCloseAskCardDetail = () => {
    setIsCardDetailOpen(false)
    setSelectedDataCards([])
    setActiveCardIndex(0)
  }

  // 可取消的延迟函数
  const askCancelableDelay = (ms: number): Promise<void> => {
    return new Promise((resolve) => {
      const timeoutId = setTimeout(() => {
        askTimeoutIdsRef.current = askTimeoutIdsRef.current.filter(id => id !== timeoutId)
        resolve()
      }, ms)
      askTimeoutIdsRef.current.push(timeoutId)
    })
  }

  // 平滑更新进度条
  const askSmoothProgressTo = (targetPercent: number, duration: number) => {
    if (askProgressIntervalRef.current) {
      clearInterval(askProgressIntervalRef.current)
      askProgressIntervalRef.current = null
    }

    return new Promise<void>((resolve) => {
      if (duration <= 0) {
        updateAskProgress(targetPercent)
        resolve()
        return
      }

      const startPercent = askProgressRef.current
      const difference = targetPercent - startPercent
      const steps = Math.max(20, Math.floor(duration / 50))
      const stepSize = difference / steps
      let currentStep = 0
      const stepDuration = duration / steps

      askProgressIntervalRef.current = setInterval(() => {
        if (askCancelFlagRef.current) {
          if (askProgressIntervalRef.current) {
            clearInterval(askProgressIntervalRef.current)
            askProgressIntervalRef.current = null
          }
          resolve()
          return
        }

        currentStep++
        if (currentStep >= steps) {
          updateAskProgress(targetPercent)
          if (askProgressIntervalRef.current) {
            clearInterval(askProgressIntervalRef.current)
            askProgressIntervalRef.current = null
          }
          resolve()
        } else {
          updateAskProgress(startPercent + stepSize * currentStep)
        }
      }, stepDuration)
    })
  }

  // 执行问数查询：立即调接口，进度条与请求并行、顺滑动画
  const handleAskQuery = async () => {
    if (!askQuestion.trim()) return

    askCancelFlagRef.current = false
    askTimeoutIdsRef.current.forEach(id => clearTimeout(id))
    askTimeoutIdsRef.current = []

    setAskQueryStatus('analyzing')
    setAskQueryStep(1)
    updateAskProgress(5)
    setAskQueryResult(null)
    setAskError(null)

    let controller: AbortController | null = null

    const requestParams: QueryRequest = {
      query: askQuestion,
      enable_rerank: true,
    }
    if (selectedDataSourceIds.length > 0) {
      if (selectedDataSourceIds.length === 1) {
        requestParams.datasource_id = selectedDataSourceIds[0]
      } else {
        requestParams.datasource_ids = selectedDataSourceIds
      }
    }

    const apiPromise = queryByDatacardsAgg(requestParams, {
      getAbortController: (ac) => {
        controller = ac
        askAbortControllerRef.current = ac
      },
    })

    // 进度条顺滑动画：与接口并行，该停顿和慢的地方（如 AI 分析、执行 SQL）更慢
    const runProgressAnimation = async () => {
      // 使用可配置的进度条时间设置
      const steps = askProgressStepConfig
      for (const {
        step,
        percent,
        ms
      } of steps) {
        if (askCancelFlagRef.current) return
        setAskQueryStep(step)
        await askSmoothProgressTo(percent, ms)
      }
    }
    runProgressAnimation()

    try {
      const response = await apiPromise
      if (askCancelFlagRef.current) throw new Error('QueryCancelled')

      await askSmoothProgressTo(100, 400)
      if (askCancelFlagRef.current) throw new Error('QueryCancelled')

      if (response.code === 200) {
        setAskQueryResult(response)
        setAskQueryStatus('idle')
        setAskQueryStep(0)
        updateAskProgress(0)
        askAbortControllerRef.current = null
        if (askProgressIntervalRef.current) {
          clearInterval(askProgressIntervalRef.current)
          askProgressIntervalRef.current = null
        }
      } else {
        setAskQueryStatus('error')
        setAskError(response.msg || '查询失败')
        setAskQueryStep(0)
        updateAskProgress(0)
        askAbortControllerRef.current = null
      }
    } catch (error: any) {
      console.error('查询失败:', error)
      if (error.name === 'AbortError' || error.message === 'QueryCancelled') {
        setAskQueryStatus('idle')
        setAskError(null)
      } else {
        setAskQueryStatus('error')
        setAskError(error instanceof Error ? error.message : '网络请求失败')
      }
      setAskQueryStep(0)
      updateAskProgress(0)
      askAbortControllerRef.current = null
      askTimeoutIdsRef.current.forEach(id => clearTimeout(id))
      askTimeoutIdsRef.current = []
      if (askProgressIntervalRef.current) {
        clearInterval(askProgressIntervalRef.current)
        askProgressIntervalRef.current = null
      }
    }
  }

  // 取消问数查询
  const handleCancelAskQuery = () => {
    askCancelFlagRef.current = true
    askTimeoutIdsRef.current.forEach(id => clearTimeout(id))
    askTimeoutIdsRef.current = []

    if (askAbortControllerRef.current) {
      askAbortControllerRef.current.abort()
      askAbortControllerRef.current = null
    }

    setAskQueryStep(0)
    setAskQueryStatus('idle')
    setAskError(null)
  }

  // SQL格式化函数
  const formatSQL = (sql: string): string => {
    const mainKeywords = ['SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT', 'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN']
    let formatted = sql.trim()
    mainKeywords.forEach(keyword => {
      const regex = new RegExp(`\\s+(${keyword})\\s+`, 'gi')
      formatted = formatted.replace(regex, '\n$1 ')
    })
    formatted = formatted.replace(/\s+(AND|OR)\s+/gi, '\n  $1 ')
    formatted = formatted.replace(/\n{3,}/g, '\n\n')
    return formatted.trim()
  }

  // 切换数据源选中状态（多数据源模式下当前工作区必须选中，不可取消）
  const toggleDataSourceSelection = (id: string) => {
    setSelectedDataSourceIds(prev => {
      if (prev.includes(id)) {
        // 当前工作区不允许取消选中
        if (id === workspace?.id) return prev
        // 如果是最后一个，不能取消选中（至少保留一个）
        if (prev.length === 1) return prev
        return prev.filter(dsId => dsId !== id)
      } else {
        return [...prev, id]
      }
    })
  }

  // ========== 防止弹框打开时页面滚动 ==========
  useEffect(() => {
    const anyModalOpen = showSettings || selectedSchema !== null || selectedCard !== null || isCardDetailOpen

    if (anyModalOpen) {
      const originalHtmlOverflow = document.documentElement.style.overflow
      const originalBodyOverflow = document.body.style.overflow

      document.documentElement.style.overflow = 'hidden'
      document.body.style.overflow = 'hidden'

      return () => {
        document.documentElement.style.overflow = originalHtmlOverflow
        document.body.style.overflow = originalBodyOverflow
      }
    }
  }, [showSettings, selectedSchema, selectedCard, isCardDetailOpen])

  // 使用 ref 跟踪是否已经加载过数据（页面刷新时会重置，SPA 导航时保持）
  const hasLoadedRef = useRef(false)

  const loadWorkspace = useCallback(async (forceRefresh = false) => {
    if (!workspaceId) return
    setLoading(true)
    setError(null)

    // 优先使用 useDataSources hook 已缓存的数据，避免重复调用 API
    if (allDataSources && allDataSources.length > 0) {
      const found = allDataSources.find((w) => w.id === workspaceId)
      if (found) {
        setWorkspace(found)
        setLoading(false)
        return
      }
    }

    // 检查是否是页面刷新（通过 performance API 检测）
    const isPageRefresh = typeof window !== 'undefined' &&
      window.performance &&
      (window.performance.navigation.type === 1 || // TYPE_REFRESH
        (window.performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming)?.type === 'reload')

    // 检查是否是新的会话（首次加载或重新登录）
    const SESSION_ID_KEY = 'datasource_session_id'
    const currentSessionId = typeof window !== 'undefined' ? window.sessionStorage.getItem(SESSION_ID_KEY) : null
    const isNewSession = !currentSessionId

    // 如果是新会话或页面刷新，重置加载状态
    if (isNewSession || isPageRefresh) {
      forceRefresh = true
      globalHasLoadedData = false
      // 创建新会话 ID（如果是新会话）
      if (isNewSession && typeof window !== 'undefined') {
        window.sessionStorage.setItem(SESSION_ID_KEY, Date.now().toString())
      }
    }

    // 强制刷新时清除缓存
    if (forceRefresh && typeof window !== 'undefined') {
      window.sessionStorage.removeItem(GLOBAL_DATA_SOURCE_CACHE_KEY)
    }

    // 如果不是强制刷新，且已经加载过数据，使用缓存
    if (!forceRefresh && globalHasLoadedData) {
      try {
        // 1. 尝试从全局缓存读取
        const cached = typeof window !== 'undefined' ? window.sessionStorage.getItem(GLOBAL_DATA_SOURCE_CACHE_KEY) : null
        if (cached) {
          const parsed = JSON.parse(cached)
          // 支持新旧两种缓存格式：数组格式 或 {items, weaviate_count} 格式
          let items: DataSourceItem[] = []
          if (Array.isArray(parsed)) {
            items = parsed
          } else if (parsed && parsed.items) {
            items = parsed.items
          }
          const found = items.find((w) => w.id === workspaceId)
          if (found) {
            setWorkspace(found)
            setLoading(false)
            return
          }
        }
      } catch {
        // ignore
      }
    }

    // 标记为已加载
    globalHasLoadedData = true

    // useDataSources 缓存中没有找到，调用列表接口获取所有数据源详情
    try {
      const listRes = await getUserDataSources({
        page: 1,
        page_size: 100,
      })
      if (listRes.code === 200 && listRes.data?.items) {
        const found = listRes.data.items.find((w) => w.id === workspaceId)
        if (found) {
          setWorkspace(found)
          // 更新全局缓存以供后续使用（同时保存 weaviate_count 和时间戳）
          try {
            const cacheData = {
              items: listRes.data.items,
              weaviate_count: listRes.data.weaviate_count || 0,
              timestamp: Date.now(),
            }
            window.sessionStorage.setItem(GLOBAL_DATA_SOURCE_CACHE_KEY, JSON.stringify(cacheData))
          } catch { /* ignore */
          }
        } else {
          setError('未找到该工作空间')
        }
      } else {
        setError('加载工作空间列表失败')
      }
    } catch (e) {
      console.error(e)
      setError('加载失败')
    } finally {
      setLoading(false)
    }
  }, [workspaceId, allDataSources])

  useEffect(() => {
    if (workspaceId) {
      loadWorkspace(false) // 首次加载尝试使用缓存
    }
  }, [workspaceId])

  // 切换到资产 tab 时重置分页
  useEffect(() => {
    if (activeTab === 'assets') {
      setSchemasPage(1)
    }
  }, [activeTab])

  // 监听其他页面触发的数据源变更事件
  useEffect(() => {
    const handleDataSourceChanged = () => {
      // 收到其他页面变更通知后，强制刷新获取最新数据
      loadWorkspace(true)
    }

    window.addEventListener('datasource-changed', handleDataSourceChanged)
    return () => {
      window.removeEventListener('datasource-changed', handleDataSourceChanged)
    }
  }, [loadWorkspace])

  // 监听卡片数据更新事件，刷新卡片列表
  useEffect(() => {
    const handleCardUpdated = () => {
      // 刷新卡片列表数据
      console.log('[datacard-updated] 收到卡片更新事件，刷新卡片列表')
      if (workspace?.id) {
        // 走分页接口，复用 fetchCards 逻辑（保持与手动刷新一致）
        fetchCards(cardsPage, false)
      }
    }

    window.addEventListener('datacard-updated', handleCardUpdated)
    return () => {
      window.removeEventListener('datacard-updated', handleCardUpdated)
    }
  }, [workspace, cardsPage, CARDS_PAGE_SIZE])

  // 监听 TargetInventory 组件发出的新建定向盘点事件
  useEffect(() => {
    const handleOpenTargetInventoryModal = () => {
      setInventoryJobType('target')
      setShowTargetInventoryModal(true)
    }
    window.addEventListener('open-target-inventory-modal', handleOpenTargetInventoryModal)
    return () => {
      window.removeEventListener('open-target-inventory-modal', handleOpenTargetInventoryModal)
    }
  }, [])

  // 加载当前页的扁平卡片（来自后端分页接口），同时记录总数 / 最后一页
  const [pageMeta, setPageMeta] = useState<{
    total_cards: number
    total_datasources: number
    total_pages: number
  } | null>(null)

  // 组件卸载时清理搜索提示 message 的延迟关闭定时器，避免内存泄漏
  useEffect(() => {
    return () => {
      const state = searchMsgStateRef.current
      if (state.closeTimer !== null) {
        window.clearTimeout(state.closeTimer)
        state.closeTimer = null
      }
      if (state.open) {
        state.open = false
        message.destroy(SEARCH_MSG_KEY)
      }
    }
  }, [])

  const fetchCards = async (_page = 1, isManualRefresh = false, q?: string) => {
    if (!workspace?.id) return
    setCardsLoading(true)
    // 用递增请求令牌避免慢响应覆盖新请求（搜索防抖场景）
    const reqToken = ++fetchCardsReqTokenRef.current
    // 是否搜索调用：用户输入了非空关键词（q 为 undefined 表示非搜索场景：分页/刷新/切 tab）
    // q === '' 表示清除搜索（用户点 X 或空状态清除），也不应弹 message
    const isSearchCall = q !== undefined && q.trim() !== ''
    // 标记本次 loading 的来源类型，供内容区判断是否显示 loading 蒙层
    // - 'search': 搜索时只走顶部 message，不在内容区覆盖旧数据
    // - 'page'  : 切 tab / 刷新 / 翻页等场景，需要在内容区提示"数据卡片信息获取中..."
    cardsLoadingKindRef.current = isSearchCall ? 'search' : 'page'
    // 仅搜索调用才显示顶部 loading 提示，避免与"刷新中"反馈叠加
    if (isSearchCall) {
      const state = searchMsgStateRef.current
      // 若已有待执行的关闭任务，先取消（说明用户还在持续输入）
      if (state.closeTimer !== null) {
        window.clearTimeout(state.closeTimer)
        state.closeTimer = null
      }
      // 若消息当前未显示，则弹出
      if (!state.open) {
        state.open = true
        message.loading({ content: '搜索中...', duration: 0, key: SEARCH_MSG_KEY })
      }
    }
    try {
      // 使用后端分页接口 /datacard_tool，搜索关键词 q 也透传给后端
      const res = await getDataCards({
        datasource_id: workspace.id,
        parse_json: true,
        page: _page,
        page_size: CARDS_PAGE_SIZE,
        q: q && q.trim() ? q.trim() : undefined,
      })
      // 已被更新的请求跳过 setState，避免旧搜索结果覆盖新搜索
      if (reqToken !== fetchCardsReqTokenRef.current) return
      if (res.code === 200 && res.data) {
        const items = Array.isArray(res.data.items) ? res.data.items : []
        // 将分组结构扁平化为卡片数组
        const flatCards: DataCard[] = items.flatMap(item =>
          item.cards.map(card => ({
            ...card,
            datasource: item.datasource,
          }))
        )
        setAllCards(flatCards)
        // 记录后端返回的分页元数据，供上下页按钮 disabled 判定
        const total = res.data.total_cards ?? flatCards.length
        const serverPageSize = res.data.page_size || CARDS_PAGE_SIZE
        const totalPages = Math.max(1, Math.ceil(total / serverPageSize))
        setPageMeta({
          total_cards: total,
          total_datasources: res.data.total_datasources ?? 0,
          total_pages: totalPages,
        })
        setCardsPage(res.data.page || _page)
        if (isManualRefresh) {
          message.success(`刷新成功，共 ${total} 张数据卡片`)
        }
      }
    } catch (e) {
      if (reqToken !== fetchCardsReqTokenRef.current) return
      console.error('获取数据卡片失败', e)
    } finally {
      if (reqToken === fetchCardsReqTokenRef.current) {
        setCardsLoading(false)
        // 清除本次 loading 来源标记（蒙层会随之消失）
        cardsLoadingKindRef.current = null
        // 关闭本次搜索对应的顶部 loading 提示
        if (isSearchCall) {
          const state = searchMsgStateRef.current
          // 先取消旧定时器，确保只有一个延迟关闭任务在调度
          if (state.closeTimer !== null) {
            window.clearTimeout(state.closeTimer)
          }
          // 延迟关闭：期间如有新搜索进来，会取消此定时器并保持 message 显示，
          // 避免连续搜索时 message 反复弹/关造成视觉跳动
          state.closeTimer = window.setTimeout(() => {
            state.closeTimer = null
            state.open = false
            message.destroy(SEARCH_MSG_KEY)
          }, SEARCH_CLOSE_GRACE_MS)
        } else if (q === '') {
          // 清除搜索（用户点 X 或空状态清除）：需要立刻关掉之前残留的搜索 message
          const state = searchMsgStateRef.current
          if (state.closeTimer !== null) {
            window.clearTimeout(state.closeTimer)
            state.closeTimer = null
          }
          if (state.open) {
            state.open = false
            message.destroy(SEARCH_MSG_KEY)
          }
        }
      }
    }
  }

  // 切换到卡片tab时，总是优先从 API 获取最新数据
  useEffect(() => {
    if (activeTab === 'cards' && workspace?.connect_name) {
      // 总是从 API 刷新最新数据（不是手动刷新，不显示提示）
      fetchCards(1, false)
    }
  }, [activeTab, workspace?.connect_name])

  // 切换到知识tab时不再需要加载术语库（由 KnowledgeTab 组件自行加载）

  const vectorIndexCount = workspace?.weaviate_num ?? 0

  const handleSelectInventoryType = (type: InventoryType) => {
    setShowInventoryTypeModal(false)
    if (type === 'target') {
      setInventoryJobType('target')
      setShowTargetInventoryModal(true)
    } else {
      setInventoryJobType('global')
      setShowGlobalInventoryModal(true)
    }
  }

  const handleTargetInventorySuccess = (job: any) => {
    setActiveTab('jobs')
  }

  const handleGlobalInventorySuccess = (result: any) => {
    setActiveTab('jobs')
    // 刷新全域盘点结果
    if (workspace?.id) {
      loadGlobalInventoryResult(workspace.id)
    }
  }

  // 术语库相关逻辑已移至 KnowledgeTab 组件

  // 加载全域盘点结果（关系卡片、表关系、图谱数据）
  const loadGlobalInventoryResult = async (datasourceId: string) => {
    setLoadingGlobalResult(true)
    try {
      // 并行加载关系卡片、表关系和图谱数据
      const [cardsRes, relationshipsRes, graphRes] = await Promise.all([
        getRelationshipCards(datasourceId),
        getTableRelationships(datasourceId),
        getRelationshipGraph(datasourceId),
      ])

      if (cardsRes.code === 200 && cardsRes.data) {
        setRelationshipCards(cardsRes.data.cards || [])
      }

      if (relationshipsRes.code === 200 && relationshipsRes.data) {
        setTableRelationships(relationshipsRes.data.relationships || [])
      }

      if (graphRes.code === 200 && graphRes.data) {
        setGraphData(graphRes.data)
      }
    } catch (error) {
      console.error('加载全域盘点结果失败:', error)
      // 404 表示该数据源还没有关系数据
      setRelationshipCards([])
      setTableRelationships([])
      setGraphData({
        nodes: [],
        edges: [],
      })
    } finally {
      setLoadingGlobalResult(false)
    }
  }

  // 当切换到全域盘点Tab时，加载全域盘点结果
  useEffect(() => {
    if (inventoryJobType === 'global' && workspace?.id) {
      loadGlobalInventoryResult(workspace.id)
    }
  }, [inventoryJobType, workspace?.id])

  // 删除全域盘点结果（关系数据）
  const handleDeleteGlobalInventoryResult = async () => {
    if (!workspace?.id) return
    try {
      const response = await deleteRelationships(workspace.id)
      if (response.code === 200) {
        message.success(`已清除 ${response.data.deleted_relationships} 个关系和 ${response.data.deleted_cards} 个卡片`)
        // 刷新结果
        loadGlobalInventoryResult(workspace.id)
      } else {
        message.error(response.msg || '删除失败')
      }
    } catch (error) {
      console.error('删除全域盘点结果失败:', error)
      message.error('删除失败')
    }
  }

  if (loading && !workspace) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 bg-slate-200 rounded w-48" />
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 bg-slate-200 rounded-[20px]" />
          ))}
        </div>
      </div>
    )
  }

  if (error || !workspace) {
    return (
      <div className="space-y-4">
        <Link href="/workspaces"
              className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-indigo-600"
        >
          <ChevronLeft className="w-4 h-4" /> 工作空间
        </Link>
        <div className="bg-white rounded-[20px] border border-slate-200 p-12 text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <p className="text-slate-700">{error || '未找到该工作空间'}</p>
          <Link href="/workspaces" className="mt-4 inline-block text-indigo-600 hover:underline">返回列表</Link>
        </div>
      </div>
    )
  }

  return (
    <>
      <div className="workspace-detail-root space-y-6" style={{ minHeight: 0, flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2 text-sm">
          <Link
            href="/workspaces"
            className="text-slate-500 hover:text-indigo-600 transition-colors flex items-center gap-1"
          >
            <ChevronLeft className="w-4 h-4" />
            工作空间
          </Link>
          <ChevronRight className="w-4 h-4 text-slate-300" />
          <span className="text-slate-900 font-medium">{workspace.connect_name}</span>
        </nav>

        {/* Header */}
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div
              className="w-12 h-12 rounded-[16px] bg-gradient-to-br from-emerald-100 to-emerald-50 flex items-center justify-center text-2xl"
            >
              {getDbTypeIcon(workspace.db_type)}
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-slate-900 flex items-center gap-2">
                {workspace.connect_name}
                {workspace.status === 'available' ? (
                  <CheckCircle className="w-5 h-5 text-green-500" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-red-500" />
                )}
              </h1>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowSettings(true)}
              className="flex items-center gap-2 px-4 py-2 bg-white text-slate-700 rounded-[12px] text-sm font-medium border border-slate-200 hover:bg-slate-50 transition-colors"
            >
              <Settings className="w-4 h-4" />
              设置
            </button>
            <button
              onClick={() => {
                if (!workspace) {
                  message.loading('数据源加载中...', 1)
                  return
                }
                setShowInventoryTypeModal(true)
              }}
              className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-5 py-2.5 rounded-[12px] text-sm font-medium hover:from-blue-700 hover:to-indigo-700 transition-all shadow-md hover:shadow-lg"
            >
              <PlayCircle className="w-4 h-4" />
              执行盘点
            </button>
          </div>
        </header>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4">
          <StatCard
            icon={<Table className="text-blue-500" strokeWidth={2} />}
            label="数据表"
            value={workspace.table_num ?? 0}
            color="#3b82f6"
          />
          <StatCard
            icon={<CreditCard className="text-purple-500" strokeWidth={2} />}
            label="数据卡片"
            value={workspace.datacard_count ?? 0}
            color="#a855f7"
          />
          <StatCard
            icon={<Sparkles className="text-violet-500" strokeWidth={2} />}
            label="向量索引"
            value={vectorIndexCount}
            color="#8b5cf6"
          />
          <StatCard
            icon={<Clock className="text-orange-500" strokeWidth={2} />}
            label="最近同步"
            value={formatRelativeTime(workspace.updated_at)}
            color="#f97316"
          />
        </div>

        {/* Tabs */}
        <div className="border-b border-slate-200">
          <nav className="flex gap-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-indigo-500 text-indigo-600'
                    : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="min-h-[400px]">
          {activeTab === 'overview' && (
            <div className="workspace-tab workspace-tab-overview space-y-6">
              {/* 连接信息卡片 */}
              <div className="bg-white rounded-[20px] border border-slate-200 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-slate-900">连接信息</h3>
                  <span
                    className={`px-3 py-1.5 text-xs font-medium ${workspace.status === 'available' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`}
                    style={{
                      borderRadius: '9999px',
                      display: 'inline-block',
                    }}
                  >
                  {workspace.status === 'available' ? '已连接' : '未连接'}
                </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <div className="flex items-center gap-2 p-2 bg-slate-50 rounded-[8px]">
                    <span className="text-lg">{getDbTypeIcon(workspace.db_type)}</span>
                    <div className="min-w-0">
                      <p className="text-xs text-slate-500">类型</p>
                      <p className="text-sm font-semibold text-slate-800 truncate"
                      >{String(workspace.db_type || '').toUpperCase()}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 p-2 bg-slate-50 rounded-[8px] min-w-0">
                    <Database className="w-4 h-4 text-blue-500" />
                    <div className="min-w-0">
                      <p className="text-xs text-slate-500">数据库名</p>
                      <p className="text-sm font-semibold text-slate-800 truncate" title={workspace.database_name}
                      >{workspace.database_name}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 p-2 bg-slate-50 rounded-[8px]">
                    <Layers className="w-4 h-4 text-purple-500" />
                    <div>
                      <p className="text-xs text-slate-500">Schema</p>
                      <p className="text-sm font-semibold text-slate-800">{workspace.schema_name || 'default'}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 p-2 bg-slate-50 rounded-[8px] min-w-0 flex-shrink">
                    <Tag className="w-4 h-4 text-orange-500 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs text-slate-500">版本</p>
                      <p className="text-sm font-semibold text-slate-800 break-words" title={schemas[0]?.db_version}>
                        {schemas[0]?.db_version || '-'}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* 表信息预览 */}
              <div className="bg-white dark:bg-slate-800 rounded-[20px] border border-slate-200 dark:border-slate-700 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">表信息预览</h3>
                  <button onClick={() => setActiveTab('assets')}
                          className="text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 font-medium"
                  >
                    查看全部 →
                  </button>
                </div>
                <div className="space-y-2">
                  {schemas.length === 0 ? (
                    <div className="text-center py-8 text-slate-400 dark:text-slate-500">
                      <Table className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p className="text-sm">暂无表结构数据</p>
                    </div>
                  ) : (
                    schemas.slice(0, 5).map((schema: SchemaItem) => (
                      <div key={schema.id}
                           className="p-3 bg-slate-50 dark:bg-slate-700/50 rounded-[10px] hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors border border-slate-100 dark:border-slate-600"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-3 min-w-0">
                            {schema.is_view ? (
                              <span className="text-xs bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400 px-2 py-0.5"
                                    style={{ borderRadius: '9999px' }}
                              >视图</span>
                            ) : (
                              <span className="text-xs bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-400 px-2 py-0.5"
                                    style={{ borderRadius: '9999px' }}
                              >表</span>
                            )}
                            <p className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">{schema.table_name}</p>
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            {schema.is_filled && (
                              <span
                                className="text-xs bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-400 px-2 py-0.5 flex items-center gap-1"
                                style={{ borderRadius: '9999px' }}
                              >
                              <Tag className="w-3 h-3" />部分数据AI填充
                            </span>
                            )}
                          </div>
                        </div>
                        <p className="text-xs text-slate-400 dark:text-slate-500 truncate mb-2">{schema.schema_text?.description || '-'}</p>
                        <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
                        <span className="flex items-center gap-1">
                          <Layers className="w-3 h-3 text-blue-500" />
                          <span className="text-slate-600 dark:text-slate-300">{schema.schema_text?.columns?.length || 0}</span> 字段
                        </span>
                          <span className="flex items-center gap-1">
                          <Key className="w-3 h-3 text-yellow-500" />
                          <span className="text-slate-600 dark:text-slate-300">{schema.schema_text?.primary_keys?.length || 0}</span> 主键
                        </span>
                          <span className="flex items-center gap-1">
                          <Link2 className="w-3 h-3 text-green-500" />
                          <span className="text-slate-600 dark:text-slate-300">{schema.schema_text?.foreign_keys?.length || 0}</span> 外键
                        </span>
                          <span className="flex items-center gap-1">
                          <BarChart3 className="w-3 h-3 text-purple-500" />
                          <span className="text-slate-600 dark:text-slate-300">{schema.schema_text?.indexes?.length || 0}</span> 索引
                        </span>
                        </div>
                      </div>
                    ))
                  )}
                  {schemas.length > 5 && (
                    <div className="text-center pt-2">
                      <span className="text-xs text-slate-400 dark:text-slate-500">还有 {schemas.length - 5} 个表...</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'assets' && (
            <div
              className="workspace-tab workspace-tab-assets bg-white dark:bg-slate-800 rounded-[28px] border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden"
            >
              {/* 资产 Tab 头部 - 使用主题变量以适配深色模式 */}
              <div
                className="workspace-tab-header"
                style={{
                  padding: '1.25rem',
                  borderBottom: '1px solid rgb(var(--theme-border))',
                  background: 'linear-gradient(135deg, rgba(var(--theme-bg-tertiary), 0.6) 0%, rgb(var(--theme-bg)) 50%, rgba(var(--theme-bg-tertiary), 0.4) 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div className="flex items-center gap-4">
                  <div style={{
                    width: '2.5rem',
                    height: '2.5rem',
                    borderRadius: '16px',
                    background: 'linear-gradient(135deg, rgb(59,130,246), rgb(79,70,229))',
                    color: '#fff',
                    boxShadow: '0 10px 15px -3px rgba(59,130,246,0.4)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                  >
                    <Layers className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">库表信息</h3>
                    <p className="text-sm text-slate-500">该数据源下的表与视图</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {/* 资产搜索框 */}
                  <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                    <Search
                      className="w-4 h-4"
                      style={{
                        position: 'absolute',
                        left: '12px',
                        color: 'rgb(var(--theme-text-muted))',
                        pointerEvents: 'none',
                        zIndex: 1,
                      }}
                    />
                    <input
                      type="text"
                      placeholder="搜索表名/描述..."
                      value={assetsSearch}
                      onChange={(e) => {
                        setAssetsSearch(e.target.value)
                        setSchemasPage(1)
                      }}
                      style={{
                        width: '200px',
                        height: '36px',
                        paddingLeft: '36px',
                        paddingRight: '12px',
                        borderRadius: '18px',
                        border: '1px solid rgb(var(--theme-border))',
                        backgroundColor: 'rgb(var(--theme-bg-secondary))',
                        color: 'rgb(var(--theme-text))',
                        fontSize: '13px',
                        outline: 'none',
                        transition: 'all 0.2s ease',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                      }}
                      onFocus={(e) => {
                        e.target.style.borderColor = 'rgb(var(--theme-primary))'
                        e.target.style.boxShadow = '0 0 0 3px rgba(var(--theme-primary), 0.1)'
                      }}
                      onBlur={(e) => {
                        e.target.style.borderColor = 'rgb(var(--theme-border))'
                        e.target.style.boxShadow = '0 1px 3px rgba(0,0,0,0.05)'
                      }}
                    />
                    {assetsSearch && (
                      <button
                        onClick={() => setAssetsSearch('')}
                        style={{
                          position: 'absolute',
                          right: '8px',
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          padding: '4px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: 'rgb(var(--theme-text-muted))',
                          borderRadius: '50%',
                        }}
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                  {/* 资产类型筛选按钮 */}
                  <div className="relative" style={{ zIndex: 10 }}>
                    <button
                      onClick={() => {
                        const next = assetsTypeFilter === 'all' ? 'table' : assetsTypeFilter === 'table' ? 'view' : 'all'
                        setAssetsTypeFilter(next)
                        setSchemasPage(1)
                      }}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-all"
                      style={{
                        borderRadius: '12px',
                        border: '1px solid rgb(var(--theme-border))',
                        backgroundColor: assetsTypeFilter !== 'all' ? 'rgba(var(--theme-primary), 0.15)' : 'rgb(var(--theme-bg-secondary))',
                        color: assetsTypeFilter !== 'all' ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-muted))',
                      }}
                    >
                      <LayoutDashboard className="w-3.5 h-3.5" />
                      <span>
                        {assetsTypeFilter === 'all' ? '全部' : assetsTypeFilter === 'table' ? '表' : '视图'}
                      </span>
                    </button>
                  </div>
                  <span
                    className="text-sm font-medium px-5 py-2 shadow-sm"
                    style={{ borderRadius: '9999px' }}
                  >{filteredSchemas.length} 项</span>
                </div>
              </div>
              {schemas.length === 0 ? (
                <div className="p-20 text-center">
                  <Layers className="w-12 h-12 mx-auto mb-5" style={{ color: 'rgb(var(--theme-text-muted))' }} />
                  <h4 className="text-lg font-semibold mb-2" style={{ color: 'rgb(var(--theme-text))' }}>暂无表信息</h4>
                  <p className="max-w-sm mx-auto" style={{ color: 'rgb(var(--theme-text-muted))' }}>请先执行同步或从列表页进入以加载完整数据</p>
                </div>
              ) : filteredSchemas.length === 0 && (assetsSearch || assetsTypeFilter !== 'all') ? (
                <div className="p-20 text-center">
                  <Search className="w-12 h-12 mx-auto mb-5" style={{ color: 'rgb(var(--theme-text-muted))' }} />
                  <h4 className="text-lg font-semibold mb-2" style={{ color: 'rgb(var(--theme-text))' }}>未找到匹配的表</h4>
                  <p className="max-w-sm mx-auto" style={{ color: 'rgb(var(--theme-text-muted))' }}>
                    {assetsTypeFilter !== 'all'
                      ? `当前筛选类型为"${assetsTypeFilter === 'table' ? '表' : '视图'}"，没有找到匹配的${assetsTypeFilter === 'table' ? '表' : '视图'}`
                      : `未找到包含"${assetsSearch}"的表，请尝试其他关键词`
                    }
                  </p>
                  <button
                    onClick={() => {
                      setAssetsSearch('')
                      setAssetsTypeFilter('all')
                    }}
                    className="mt-4 px-5 py-2 text-sm font-medium"
                    style={{
                      borderRadius: '9999px',
                      backgroundColor: 'rgb(var(--theme-primary))',
                      color: '#fff',
                      border: 'none',
                      cursor: 'pointer',
                    }}
                  >
                    清除筛选
                  </button>
                </div>
              ) : (
                <>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm table-fixed">
                    <thead>
                    <tr
                      className="bg-slate-50 dark:bg-slate-700/80 border-b border-slate-100 dark:border-slate-600 text-left"
                    >
                      <th className="p-4 font-semibold text-slate-500 dark:text-slate-300 w-[50px]">#</th>
                      <th className="p-4 font-semibold text-slate-500 dark:text-slate-300 w-[200px]">表名</th>
                      <th className="p-4 font-semibold text-slate-500 dark:text-slate-300 w-[80px]">类型</th>
                      <th className="p-4 font-semibold text-slate-500 dark:text-slate-300 w-[90px]">字段数</th>
                      <th className="p-4 font-semibold text-slate-500 dark:text-slate-300">描述</th>
                      <th className="p-4 font-semibold text-slate-500 dark:text-slate-300 w-[160px]">状态</th>
                      <th className="p-4 font-semibold text-slate-500 dark:text-slate-300 text-right w-[110px]">操作</th>
                    </tr>
                    </thead>
                    <tbody>
                    {filteredSchemas.slice((schemasPage - 1) * SCHEMAS_PAGE_SIZE, schemasPage * SCHEMAS_PAGE_SIZE).map((s: SchemaItem, idx: number) => (
                      <tr key={s.id}
                          className="border-b border-slate-100 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors group"
                      >
                        <td className="p-4 text-slate-400 dark:text-slate-500 font-mono text-xs">{(schemasPage - 1) * SCHEMAS_PAGE_SIZE + idx + 1}</td>
                        <td className="p-4">
                          <div className="flex items-center gap-2">
                            <div
                              className="p-1.5 bg-slate-100 dark:bg-slate-600 group-hover:bg-indigo-100 dark:group-hover:bg-indigo-900/40 transition-colors flex-shrink-0"
                              style={{ borderRadius: '50%' }}
                            >
                              <Table className="w-4 h-4 text-slate-400 dark:text-slate-500 group-hover:text-indigo-500 dark:group-hover:text-indigo-400 transition-colors" />
                            </div>
                            <span
                              className="font-mono font-semibold text-slate-700 dark:text-slate-200 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors"
                            >{s.table_name}</span>
                          </div>
                        </td>
                        <td className="p-4">
                          <span
                            className={`inline-flex items-center px-3 py-1.5 text-xs font-medium ${s.is_view ? 'bg-orange-100 dark:bg-orange-900/40 text-orange-600 dark:text-orange-400' : 'bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400'}`}
                            style={{ borderRadius: '9999px' }}
                          >
                            {s.is_view ? '视图' : '表'}
                          </span>
                        </td>
                        <td className="p-4">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-slate-700 dark:text-slate-200">{s.schema_text?.columns?.length ?? 0}</span>
                            <span className="text-xs text-slate-400 dark:text-slate-500">字段</span>
                          </div>
                        </td>
                        <td className="p-4">
                          {s.schema_text?.description ? (
                            <span
                              className="text-sm text-slate-600 dark:text-slate-300 line-clamp-2 leading-relaxed"
                              title={s.schema_text.description}
                            >
                              {s.schema_text.description}
                            </span>
                          ) : (
                            <span className="text-slate-300 dark:text-slate-600 italic text-sm">暂无描述</span>
                          )}
                        </td>
                        <td className="p-4">
                          <div className="flex items-center gap-2">
                            <span
                              className={`inline-flex items-center px-2.5 py-1 text-xs font-medium ${s.is_filled ? 'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-400' : 'bg-slate-100 dark:bg-slate-700 text-slate-400 dark:text-slate-500'}`}
                              style={{ borderRadius: '9999px' }}
                            >
                              {s.is_filled ? '部分数据AI填充' : '未填充'}
                            </span>
                          </div>
                        </td>
                        <td className="p-4 text-right">
                          <button
                            onClick={() => setSelectedSchema(s)}
                            className="text-sm font-medium px-4 py-2 bg-indigo-50 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-600 dark:hover:bg-indigo-600 hover:text-white dark:hover:text-white transition-all duration-200 whitespace-nowrap"
                            style={{ borderRadius: '20px' }}
                          >
                            查看详情
                          </button>
                        </td>
                      </tr>
                    ))}
                    </tbody>
                  </table>
                </div>
                {filteredSchemas.length > SCHEMAS_PAGE_SIZE && (
                  <div className="flex justify-center pt-2 pb-5 px-5 border-t" style={{ borderColor: 'rgb(var(--theme-border))' }}>
                    <div className="flex items-center gap-3 px-2">
                      <button
                        type="button"
                        disabled={schemasPage <= 1}
                        onClick={() => setSchemasPage(p => p - 1)}
                        className="flex items-center gap-1.5 px-5 py-2 text-sm font-medium transition-all hover:opacity-80 active:scale-95"
                        style={{
                          color: schemasPage <= 1 ? 'rgb(var(--theme-text-disabled))' : 'rgb(var(--theme-text-primary))',
                          backgroundColor: schemasPage <= 1 ? 'transparent' : 'rgb(var(--theme-bg-secondary))',
                          borderRadius: '9999px',
                          border: 'none'
                        }}
                      >
                        <ChevronLeft className="w-4 h-4" />
                        <span>上一页</span>
                      </button>
                      <span
                        className="text-sm font-bold px-4 py-2"
                        style={{
                          color: 'rgb(var(--theme-text))',
                          backgroundColor: 'rgb(var(--theme-bg-secondary))',
                          borderRadius: '9999px',
                          border: '1px solid rgb(var(--theme-border))'
                        }}
                      >
                        {schemasPage} / {Math.ceil(filteredSchemas.length / SCHEMAS_PAGE_SIZE)}
                      </span>
                      <button
                        type="button"
                        disabled={schemasPage >= Math.ceil(filteredSchemas.length / SCHEMAS_PAGE_SIZE)}
                        onClick={() => setSchemasPage(p => p + 1)}
                        className="flex items-center gap-1.5 px-5 py-2 text-sm font-medium transition-all hover:opacity-80 active:scale-95"
                        style={{
                          color: schemasPage >= Math.ceil(filteredSchemas.length / SCHEMAS_PAGE_SIZE) ? 'rgb(var(--theme-text-disabled))' : 'rgb(var(--theme-text-primary))',
                          backgroundColor: schemasPage >= Math.ceil(filteredSchemas.length / SCHEMAS_PAGE_SIZE) ? 'transparent' : 'rgb(var(--theme-bg-secondary))',
                          borderRadius: '9999px',
                          border: 'none'
                        }}
                      >
                        <span>下一页</span>
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}
                </>
              )}
            </div>
          )}

          {activeTab === 'cards' && (
            <div
              className="workspace-tab workspace-tab-cards shadow-sm overflow-hidden"
              style={{
                borderRadius: '28px',
                border: '1px solid rgb(var(--theme-border))',
                backgroundColor: 'rgb(var(--theme-bg))'
              }}
            >
              {/* 卡片 Tab 头部：与资产 tab 一致，与下方内容同属一个容器，底部分隔线衔接 */}
              <div
                className="workspace-tab-header"
                style={{
                  padding: '1.25rem',
                  borderBottom: '1px solid rgb(var(--theme-border))',
                  background: 'linear-gradient(135deg, rgba(var(--theme-bg-tertiary), 0.6) 0%, rgb(var(--theme-bg)) 50%, rgba(var(--theme-bg-tertiary), 0.4) 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div className="flex items-center gap-4">
                  <div style={{
                    width: '2.5rem',
                    height: '2.5rem',
                    borderRadius: '16px',
                    background: 'linear-gradient(135deg, rgb(168,85,247), rgb(219,39,119))',
                    color: '#fff',
                    boxShadow: '0 10px 15px -3px rgba(168,85,247,0.4)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                  >
                    <CreditCard className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold" style={{ color: 'rgb(var(--theme-text))' }}>数据卡片</h3>
                    <p className="text-sm" style={{ color: 'rgb(var(--theme-text-muted))' }}>该数据源下的库表对应的数据卡片</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {/* 卡片搜索框 */}
                  <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                    <Search
                      className="w-4 h-4"
                      style={{
                        position: 'absolute',
                        left: '12px',
                        color: 'rgb(var(--theme-text-muted))',
                        pointerEvents: 'none',
                        zIndex: 1,
                      }}
                    />
                    <input
                      type="text"
                      placeholder="搜索卡片名称/摘要..."
                      value={cardsSearch}
                      onChange={(e) => {
                        const v = e.target.value
                        setCardsSearch(v)
                        setCardsPage(1)
                        // 防抖调用后端搜索接口：覆盖全量而非仅当前页
                        // 500ms 防抖：稍长一些的等待能合并用户连续输入，避免短时间内重复触发搜索
                        const handle = window.setTimeout(() => {
                          fetchCards(1, false, v)
                        }, 500)
                        setCardsSearchDebounce(handle)
                      }}
                      style={{
                        width: '200px',
                        height: '36px',
                        paddingLeft: '36px',
                        paddingRight: '36px',
                        borderRadius: '18px',
                        border: '1px solid rgb(var(--theme-border))',
                        backgroundColor: 'rgb(var(--theme-bg-secondary))',
                        color: 'rgb(var(--theme-text))',
                        fontSize: '13px',
                        outline: 'none',
                        transition: 'all 0.2s ease',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                      }}
                      onFocus={(e) => {
                        e.target.style.borderColor = 'rgb(var(--theme-primary))'
                        e.target.style.boxShadow = '0 0 0 3px rgba(var(--theme-primary), 0.1)'
                      }}
                      onBlur={(e) => {
                        e.target.style.borderColor = 'rgb(var(--theme-border))'
                        e.target.style.boxShadow = '0 1px 3px rgba(0,0,0,0.05)'
                      }}
                    />
                    {cardsSearch && (
                      <button
                        onClick={() => {
                          // 清空搜索词并重拉后端（用空 q 恢复全量）
                          setCardsSearch('')
                          setCardsPage(1)
                          if (cardsSearchDebounce !== null) {
                            window.clearTimeout(cardsSearchDebounce)
                            setCardsSearchDebounce(null)
                          }
                          fetchCards(1, false, '')
                        }}
                        style={{
                          position: 'absolute',
                          right: '8px',
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          padding: '4px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: 'rgb(var(--theme-text-muted))',
                          borderRadius: '50%',
                        }}
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                  {/* 卡片类型筛选按钮 */}
                  <div className="relative" style={{ zIndex: 10 }}>
                    <button
                      onClick={() => {
                        const next = cardsTypeFilter === 'all' ? 'table' : cardsTypeFilter === 'table' ? 'view' : 'all'
                        setCardsTypeFilter(next)
                        // 切类型筛选时清掉搜索防抖，避免旧搜索请求覆盖当前页
                        if (cardsSearchDebounce !== null) {
                          window.clearTimeout(cardsSearchDebounce)
                          setCardsSearchDebounce(null)
                        }
                      }}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-all"
                      style={{
                        borderRadius: '12px',
                        border: '1px solid rgb(var(--theme-border))',
                        backgroundColor: cardsTypeFilter !== 'all' ? 'rgba(var(--theme-primary), 0.15)' : 'rgb(var(--theme-bg-secondary))',
                        color: cardsTypeFilter !== 'all' ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-muted))',
                      }}
                    >
                      <LayoutDashboard className="w-3.5 h-3.5" />
                      <span>
                        {cardsTypeFilter === 'all' ? '全部' : cardsTypeFilter === 'table' ? '表' : '视图'}
                      </span>
                    </button>
                  </div>
                  <button
                    onClick={() => fetchCards(1, true)}
                    disabled={cardsLoading}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-all"
                    style={{ borderRadius: '12px', color: cardsLoading ? 'rgb(var(--theme-text-muted))' : 'rgb(var(--theme-text-muted))' }}
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${cardsLoading ? 'animate-spin' : ''}`} />
                    {cardsLoading ? '刷新中' : '刷新'}
                  </button>
                  <span
                    className="text-sm font-medium px-5 py-2 shadow-sm"
                    style={{ borderRadius: '9999px', color: 'rgb(var(--theme-text))', backgroundColor: 'rgba(var(--theme-bg-secondary), 0.8)' }}
                  >{filteredCards.length} 张</span>
                </div>
              </div>

              {cardsLoading && cardsLoadingKindRef.current === 'page' ? (
                <div className="flex flex-col items-center justify-center py-20 px-5">
                  <div className="animate-spin" style={{
                    width: '40px',
                    height: '40px',
                    border: '2px solid rgba(var(--theme-border))',
                    borderTop: '2px solid rgb(var(--theme-primary))',
                    borderRadius: '50%',
                  }}
                  ></div>
                  <p className="font-medium mt-4" style={{ color: 'rgb(var(--theme-text-muted))' }}>数据卡片信息获取中...</p>
                </div>
              ) : filteredCards.length === 0 ? (
                <div className="p-20 text-center">
                  <div className="flex items-center justify-center mx-auto mb-6">
                    {cardsSearch ? (
                      <Search className="w-16 h-16" style={{ color: 'rgb(var(--theme-text-muted))' }} />
                    ) : (
                      <CreditCard className="w-16 h-16" style={{ color: 'rgb(var(--theme-text-muted))' }} />
                    )}
                  </div>
                  <h4 className="text-xl font-bold mb-3" style={{ color: 'rgb(var(--theme-text))' }}>
                    {cardsSearch ? '未找到匹配的卡片' : '暂无数据卡片'}
                  </h4>
                  <p className="max-w-md mx-auto"
                     style={{ color: 'rgb(var(--theme-text-muted))' }}
                  >
                    {cardsSearch
                      ? `未找到包含"${cardsSearch}"的数据卡片，请尝试其他关键词`
                      : '该数据源下暂无生成的数据卡片，请尝试执行数据同步或生成卡片'
                    }
                  </p>
                  {cardsSearch && (
                    <button
                      onClick={() => {
                        setCardsSearch('')
                        setCardsPage(1)
                        if (cardsSearchDebounce !== null) {
                          window.clearTimeout(cardsSearchDebounce)
                          setCardsSearchDebounce(null)
                        }
                        fetchCards(1, false, '')
                      }}
                      className="mt-4 px-5 py-2 text-sm font-medium"
                      style={{
                        borderRadius: '9999px',
                        backgroundColor: 'rgb(var(--theme-primary))',
                        color: '#fff',
                        border: 'none',
                        cursor: 'pointer',
                      }}
                    >
                      清除搜索
                    </button>
                  )}
                </div>
              ) : (
                <div className="p-5">
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredCards.slice((cardsPage - 1) * CARDS_PAGE_SIZE, cardsPage * CARDS_PAGE_SIZE).map((card) => {
                      const datasource = workspace as DataSource
                      const cardData = parseCardData(card.card_data)
                      const abstract = (cardData as any)?.Abstract ?? ''
                      const cols = (cardData as any)?.SQLMeta?.columns ?? []
                      const keyConcepts = (cardData as any)?.KeyConcepts
                      const tags = (cardData as any)?.Tags ?? []
                      return (
                        <div
                          key={card.doc_id}
                          className="border p-5 hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 cursor-pointer group flex flex-col"
                          style={{ borderRadius: '20px', backgroundColor: 'rgb(var(--theme-bg))', borderColor: 'rgb(var(--theme-border))' }}
                          onClick={() => {
                            setSelectedCard({
                              card,
                              datasource: workspace as DataSource,
                            })
                          }}
                        >
                          {/* 卡片顶部：类型标签 + 状态角标 */}
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-1.5">
                              <span
                                className={`text-[11px] font-semibold px-2 py-0.5 border uppercase ${getDbTypeTagClass(datasource?.db_type || '')}`}
                                style={{ borderRadius: '9999px' }}
                              >{datasource?.db_type}</span>
                              <span
                                className="text-[11px] font-semibold px-2 py-0.5"
                                style={{ borderRadius: '9999px', border: '1px solid', borderColor: card.is_view ? 'rgba(245, 158, 11, 0.3)' : 'rgba(34, 197, 94, 0.3)', color: card.is_view ? 'rgb(217, 119, 6)' : 'rgb(34, 197, 94)', backgroundColor: card.is_view ? 'rgba(245, 158, 11, 0.1)' : 'rgba(34, 197, 94, 0.1)' }}
                              >
                            {card.is_view ? '视图' : '表'}
                          </span>
                            </div>
                            <div className="flex items-center gap-1">
                              {card.is_filled && (
                                <span
                                  className="text-[10px] px-1.5 py-0.5 font-semibold"
                                  style={{ borderRadius: '9999px', color: 'rgb(124, 58, 237)', backgroundColor: 'rgba(124, 58, 237, 0.1)' }}
                                >✨部分数据AI填充</span>
                              )}
                            </div>
                          </div>

                          {/* 表名 + 主题标签 */}
                          <div className="flex flex-wrap items-center gap-2 mb-2">
                            <h4
                              className="font-bold group-hover:text-indigo-600 transition-colors text-sm leading-snug font-mono"
                              style={{ color: 'rgb(var(--theme-text))' }}
                            >{card.table_name}</h4>
                            {keyConcepts?.canonical_topic && (
                              <span
                                className="text-[11px] px-2.5 py-1 font-medium"
                                style={{ borderRadius: '9999px', backgroundColor: 'rgba(var(--theme-primary), 0.1)', color: 'rgb(var(--theme-primary))', border: '1px solid rgba(var(--theme-primary), 0.2)' }}
                              >
                            {keyConcepts.canonical_topic}
                          </span>
                            )}
                          </div>

                          {/* 描述 */}
                          <p className="text-xs line-clamp-2 mb-3 leading-relaxed flex-1" style={{ color: 'rgb(var(--theme-text-muted))' }}>{abstract ||
                            <span className="italic" style={{ color: 'rgb(var(--theme-text-muted))' }}>暂无描述</span>}</p>

                          {/* 字段注释标签（最多 3 个 + more） */}
                          {(() => {
                            const withComment = (cols as {
                              comment?: string
                            }[]).filter(c => c.comment && String(c.comment).trim())
                            const showComments = withComment.slice(0, 3).map(c => String(c.comment).trim())
                            const moreCount = withComment.length - 3
                            if (showComments.length === 0) return null
                            return (
                              <div className="flex flex-wrap items-center gap-1.5 mb-3">
                                {showComments.map((txt, i) => (
                                  <span key={i}
                                        className="text-[11px] px-2 py-0.5 font-medium max-w-[120px] truncate"
                                        style={{ borderRadius: '9999px', backgroundColor: 'rgb(var(--theme-bg-secondary))', color: 'rgb(var(--theme-text-muted))', border: '1px solid rgb(var(--theme-border))' }} title={txt}
                                  >{txt}</span>
                                ))}
                                {moreCount > 0 && (
                                  <span className="text-[11px] font-medium" style={{ color: 'rgb(var(--theme-text-muted))' }}>+{moreCount} more</span>
                                )}
                              </div>
                            )
                          })()}

                          {/* 底部：字段数 + 更新时间 + 查看 */}
                          <div className="flex items-center justify-between pt-3 mt-auto" style={{ borderTop: '1px solid rgb(var(--theme-border))' }}>
                            <div className="flex items-center gap-3 text-[11px]" style={{ color: 'rgb(var(--theme-text-muted))' }}>
                              <span>{cols.length} 字段</span>
                              {tags.length > 0 && <span>{tags.length} 标签</span>}
                            </div>
                            <span
                              className="text-xs font-semibold transition-all flex items-center gap-0.5"
                              style={{ color: 'rgb(var(--theme-primary))' }}
                            >
                          查看 <ChevronRight className="w-3.5 h-3.5" />
                        </span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
              {filteredCards.length > 0 && !(cardsLoading && cardsLoadingKindRef.current === 'page') && (
                <div className="flex justify-center pt-2 pb-5 px-5 border-t" style={{ borderColor: 'rgb(var(--theme-border))' }}>
                  <div className="flex items-center gap-3 px-2">
                    <button
                      type="button"
                      disabled={cardsPage <= 1 || cardsLoading}
                      onClick={() => fetchCards(cardsPage - 1, false)}
                      className="flex items-center gap-1.5 px-5 py-2 text-sm font-medium transition-all hover:opacity-80 active:scale-95"
                      style={{
                        color: cardsPage <= 1 ? 'rgb(var(--theme-text-disabled))' : 'rgb(var(--theme-text-primary))',
                        backgroundColor: cardsPage <= 1 || cardsLoading ? 'transparent' : 'rgb(var(--theme-bg-secondary))',
                        borderRadius: '9999px',
                        border: 'none'
                      }}
                    >
                      <ChevronLeft className="w-4 h-4" />
                      <span>上一页</span>
                    </button>
                    <span
                      className="text-sm font-bold px-4 py-2"
                      style={{
                        color: 'rgb(var(--theme-text))',
                        backgroundColor: 'rgb(var(--theme-bg-secondary))',
                        borderRadius: '9999px',
                        border: '1px solid rgb(var(--theme-border))'
                      }}
                    >
                      {cardsPage} / {pageMeta?.total_pages ?? Math.max(1, Math.ceil(filteredCards.length / CARDS_PAGE_SIZE))}
                    </span>
                    <button
                      type="button"
                      disabled={cardsPage >= (pageMeta?.total_pages ?? Math.ceil(filteredCards.length / CARDS_PAGE_SIZE)) || cardsLoading}
                      onClick={() => fetchCards(cardsPage + 1, false)}
                      className="flex items-center gap-1.5 px-5 py-2 text-sm font-medium transition-all hover:opacity-80 active:scale-95"
                      style={{
                        color: cardsPage >= (pageMeta?.total_pages ?? Math.ceil(filteredCards.length / CARDS_PAGE_SIZE)) ? 'rgb(var(--theme-text-disabled))' : 'rgb(var(--theme-text-primary))',
                        backgroundColor: cardsPage >= (pageMeta?.total_pages ?? Math.ceil(filteredCards.length / CARDS_PAGE_SIZE)) || cardsLoading ? 'transparent' : 'rgb(var(--theme-bg-secondary))',
                        borderRadius: '9999px',
                        border: 'none'
                      }}
                    >
                      <span>下一页</span>
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'enhance' && (
            <div className="workspace-tab workspace-tab-enhance" style={{
              borderRadius: '28px',
              border: '1px solid rgb(var(--theme-border))',
              boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
              overflow: 'hidden',
              backgroundColor: 'rgb(var(--theme-bg))',
            }}
            >
              {/* 头部 - 使用主题变量以适配深色模式 */}
              <div
                className="enhance-tab-header"
                style={{
                  padding: '1.25rem',
                  borderBottom: '1px solid rgb(var(--theme-border))',
                  background: 'linear-gradient(135deg, rgba(var(--theme-bg-tertiary), 0.6) 0%, rgb(var(--theme-bg)) 50%, rgba(var(--theme-bg-tertiary), 0.4) 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  borderRadius: '28px 28px 0 0',
                }}
              >
                <div className="flex items-center gap-4">
                  <div style={{
                    width: '2.5rem',
                    height: '2.5rem',
                    borderRadius: '16px',
                    background: 'linear-gradient(135deg, rgba(var(--theme-primary), 0.9), rgba(var(--theme-primary-hover), 0.9))',
                    color: '#fff',
                    boxShadow: '0 10px 15px -3px rgba(var(--theme-primary), 0.4)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                  >
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">字段注释增强</h3>
                    <p className="text-sm text-slate-500 mt-0.5">通过 Excel 字典文件补充字段描述信息</p>
                  </div>
                </div>
                {enhanceResult && (
                  <button
                    onClick={() => {
                      setEnhanceFile(null)
                      setEnhanceResult(null)
                      setEnhanceSheetName('')
                    }}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      padding: '0.625rem 1.25rem',
                      fontSize: '0.875rem',
                      fontWeight: 500,
                      color: 'rgb(var(--theme-text))',
                      backgroundColor: 'rgba(var(--theme-bg-secondary), 0.9)',
                      borderRadius: '16px',
                      border: '1px solid rgba(var(--theme-border), 0.9)',
                      cursor: 'pointer',
                    }}
                    className="hover:bg-amber-100 transition-colors"
                  >
                    <RefreshCw className="w-4 h-4" />
                    重新上传
                  </button>
                )}
              </div>

              <div className="p-4 md:p-6">
                {/* 上传区域 */}
                {!enhanceResult && (
                  <div className="space-y-4">
                    {/* 上传 + 配置（更自然的纵向信息架构） */}
                    <div className="space-y-4">
                      {/* 文件上传 */}
                      <div>
                        <label className="block text-xs font-medium text-slate-600 mb-1.5">
                          上传 Excel 字典文件 <span style={{ color: '#e11d48' }}>*</span>
                        </label>
                        <div
                          style={{
                            borderRadius: '16px',
                            border: '2px dashed',
                            padding: '1.5rem 1.5rem',
                            minHeight: '120px',
                            textAlign: 'center',
                            transition: 'all 0.2s ease',
                            borderColor: enhanceDragOver ? 'rgba(248,250,252,0.7)' : 'rgba(var(--theme-border),0.7)',
                            backgroundColor: enhanceDragOver ? 'rgba(var(--theme-primary),0.15)' : 'rgba(var(--theme-bg-secondary),0.8)',
                          }}
                          className="hover:border-indigo-300"
                          onDragOver={(e) => {
                            e.preventDefault()
                            setEnhanceDragOver(true)
                          }}
                          onDragLeave={() => setEnhanceDragOver(false)}
                          onDrop={(e) => {
                            e.preventDefault()
                            setEnhanceDragOver(false)
                            const files = e.dataTransfer.files
                            if (files.length > 0) {
                              const file = files[0]
                              if (file.name.endsWith('.xlsx') || file.name.endsWith('.xls')) {
                                setEnhanceFile(file)
                              }
                            }
                            // 手动清空 dataTransfer，否则拖拽相同文件时 onDrop 可能不会再次触发
                            e.dataTransfer.clearData()
                          }}
                        >
                          <input
                            type="file"
                            accept=".xlsx,.xls"
                            onChange={(e) => {
                              const file = e.target.files?.[0]
                              if (file) setEnhanceFile(file)
                              // 手动清空 value，否则选择相同文件时 onChange 不会再次触发
                              e.target.value = ''
                            }}
                            className="hidden"
                            id="enhance-excel-input"
                          />
                          <label htmlFor="enhance-excel-input" className="cursor-pointer block h-full">
                            {enhanceFile ? (
                              <div className="flex items-center justify-center gap-3 h-full min-h-[80px]">
                                <FileCheck className="w-5 h-5 text-emerald-500" />
                                <div className="min-w-0 max-w-[200px]">
                                  <p className="text-sm font-semibold text-emerald-700 truncate">{enhanceFile.name}</p>
                                  <p className="text-xs text-slate-500"
                                  >{(enhanceFile.size / 1024 / 1024).toFixed(2)} MB</p>
                                </div>
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.preventDefault()
                                    e.stopPropagation()
                                    setEnhanceFile(null)
                                  }}
                                  style={{
                                    fontSize: '0.75rem',
                                    color: '#e11d48',
                                    fontWeight: 500,
                                    borderRadius: '9999px',
                                    padding: '0.25rem 0.5rem',
                                    backgroundColor: 'rgba(var(--theme-bg-secondary),0.85)',
                                    border: 'none',
                                    cursor: 'pointer',
                                    flexShrink: 0,
                                  }}
                                  className="hover:bg-rose-100"
                                >
                                  移除
                                </button>
                              </div>
                            ) : (
                              <div className="flex flex-col items-center justify-center gap-2">
                                <Upload className="w-5 h-5 text-slate-400" />
                                <div className="text-center">
                                  <p className="text-sm font-medium text-slate-600">
                                    {enhanceDragOver ? '松开上传' : '点击或拖拽 Excel 到此处'}
                                  </p>
                                  <p className="text-xs text-slate-400">.xlsx / .xls，最大 20MB</p>
                                </div>
                              </div>
                            )}
                          </label>
                        </div>
                      </div>
                      {/* 右侧配置栏 */}
                      <div
                        className="space-y-4"
                        style={{
                          borderRadius: '18px',
                          background: 'linear-gradient(135deg, rgba(var(--theme-bg-secondary),0.95) 0%, rgba(var(--theme-bg),0.95) 65%, rgba(var(--theme-bg-tertiary),0.6) 100%)',
                          border: '1px solid rgba(var(--theme-border),0.9)',
                          padding: '1rem',
                          boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                        }}
                      >
                        {/* 工作表名称 */}
                        <div>
                          <label
                            className="flex items-center justify-between gap-2 text-xs font-medium text-slate-600 mb-1.5"
                          >
                          <span>
                            工作表名称 <span className="text-slate-400 font-normal">(可选)</span>
                          </span>
                            <span className="text-xs text-slate-400 font-normal whitespace-nowrap"
                            >多工作表时可指定工作表名称</span>
                          </label>
                          <input
                            type="text"
                            value={enhanceSheetName}
                            onChange={(e) => setEnhanceSheetName(e.target.value)}
                            placeholder="留空则默认使用第一个工作表"
                            className="enhance-field-input"
                            style={{
                              width: '100%',
                              padding: '0.5rem 0.75rem',
                              borderRadius: '12px',
                              border: '1px solid rgba(var(--theme-border),0.7)',
                              outline: 'none',
                              fontSize: '0.875rem',
                            }}
                            onFocus={(e) => {
                              e.target.style.boxShadow = '0 0 0 2px rgba(59,130,246,0.4)'
                              e.target.style.borderColor = '#2563eb'
                            }}
                            onBlur={(e) => {
                              e.target.style.boxShadow = 'none'
                              e.target.style.borderColor = 'rgba(var(--theme-border),0.7)'
                            }}
                          />
                        </div>

                        {/* 字段映射配置 - 使用主题变量以适配深色模式 */}
                        <div
                          className="enhance-field-mapping-panel"
                          style={{
                            borderRadius: '14px',
                            backgroundColor: 'rgba(var(--theme-bg-secondary), 0.9)',
                            border: '1px solid rgb(var(--theme-border))',
                            padding: '0.875rem',
                          }}
                        >
                          <h4 className="text-xs font-semibold text-slate-700 mb-3 flex items-center gap-2">
                            <div
                              style={{
                                width: '1.5rem',
                                height: '1.5rem',
                                borderRadius: '8px',
                                backgroundColor: 'rgb(var(--theme-bg-tertiary))',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                              }}
                            >
                              <Table2 className="w-3 h-3 text-slate-600" />
                            </div>
                            字段映射配置
                          </h4>
                          <div className="flex flex-wrap gap-x-4 gap-y-2 items-center">
                            <div className="flex items-center gap-1.5">
                              <label className="text-xs text-slate-500 whitespace-nowrap">含表头</label>
                              <select
                                value={enhanceFieldMapping.has_title}
                                onChange={(e) => setEnhanceFieldMapping(prev => ({
                                  ...prev,
                                  has_title: e.target.value as '0' | '1',
                                }))}
                                className="enhance-field-input"
                                style={{
                                  width: '7.5rem',
                                  padding: '0.2rem 0.3rem',
                                  borderRadius: '6px',
                                  border: '1px solid rgba(var(--theme-border),0.7)',
                                  outline: 'none',
                                  fontSize: '0.75rem',
                                }}
                                onFocus={(e) => {
                                  e.target.style.boxShadow = '0 0 0 2px rgba(59,130,246,0.4)'
                                  e.target.style.borderColor = '#2563eb'
                                }}
                                onBlur={(e) => {
                                  e.target.style.boxShadow = 'none'
                                  e.target.style.borderColor = 'rgba(var(--theme-border),0.7)'
                                }}
                              >
                                <option value="1">是</option>
                                <option value="0">否</option>
                              </select>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <label className="text-xs text-slate-500 whitespace-nowrap">表名列</label>
                              <input
                                type="text"
                                value={enhanceFieldMapping.tb_name_index}
                                onChange={(e) => setEnhanceFieldMapping(prev => ({
                                  ...prev,
                                  tb_name_index: e.target.value,
                                }))}
                                placeholder="A"
                                className="font-mono text-sm enhance-field-input"
                                style={{
                                  width: '7.5rem',
                                  padding: '0.2rem 0.3rem',
                                  borderRadius: '6px',
                                  border: '1px solid rgba(var(--theme-border),0.7)',
                                  outline: 'none',
                                }}
                                onFocus={(e) => {
                                  e.target.style.boxShadow = '0 0 0 2px rgba(59,130,246,0.4)'
                                  e.target.style.borderColor = '#2563eb'
                                }}
                                onBlur={(e) => {
                                  e.target.style.boxShadow = 'none'
                                  e.target.style.borderColor = 'rgba(var(--theme-border),0.7)'
                                }}
                              />
                            </div>
                            <div className="flex items-center gap-1.5">
                              <label className="text-xs text-slate-500 whitespace-nowrap">表描述</label>
                              <input
                                type="text"
                                value={enhanceFieldMapping.tb_desc_index}
                                onChange={(e) => setEnhanceFieldMapping(prev => ({
                                  ...prev,
                                  tb_desc_index: e.target.value,
                                }))}
                                placeholder="B"
                                className="font-mono text-sm enhance-field-input"
                                style={{
                                  width: '7.5rem',
                                  padding: '0.2rem 0.3rem',
                                  borderRadius: '6px',
                                  border: '1px solid rgba(var(--theme-border),0.7)',
                                  outline: 'none',
                                }}
                                onFocus={(e) => {
                                  e.target.style.boxShadow = '0 0 0 2px rgba(59,130,246,0.4)'
                                  e.target.style.borderColor = '#2563eb'
                                }}
                                onBlur={(e) => {
                                  e.target.style.boxShadow = 'none'
                                  e.target.style.borderColor = 'rgba(var(--theme-border),0.7)'
                                }}
                              />
                            </div>
                            <div className="flex items-center gap-1.5">
                              <label className="text-xs text-slate-500 whitespace-nowrap">字段列</label>
                              <input
                                type="text"
                                value={enhanceFieldMapping.field_name_index}
                                onChange={(e) => setEnhanceFieldMapping(prev => ({
                                  ...prev,
                                  field_name_index: e.target.value,
                                }))}
                                placeholder="C"
                                className="font-mono text-sm enhance-field-input"
                                style={{
                                  width: '7.5rem',
                                  padding: '0.2rem 0.3rem',
                                  borderRadius: '6px',
                                  border: '1px solid rgba(var(--theme-border),0.7)',
                                  outline: 'none',
                                }}
                                onFocus={(e) => {
                                  e.target.style.boxShadow = '0 0 0 2px rgba(59,130,246,0.4)'
                                  e.target.style.borderColor = '#2563eb'
                                }}
                                onBlur={(e) => {
                                  e.target.style.boxShadow = 'none'
                                  e.target.style.borderColor = 'rgba(var(--theme-border),0.7)'
                                }}
                              />
                            </div>
                            <div className="flex items-center gap-1.5">
                              <label className="text-xs text-slate-500 whitespace-nowrap">描述列</label>
                              <input
                                type="text"
                                value={enhanceFieldMapping.field_desc_index}
                                onChange={(e) => setEnhanceFieldMapping(prev => ({
                                  ...prev,
                                  field_desc_index: e.target.value,
                                }))}
                                placeholder="D"
                                className="font-mono text-sm enhance-field-input"
                                style={{
                                  width: '7.5rem',
                                  padding: '0.2rem 0.3rem',
                                  borderRadius: '6px',
                                  border: '1px solid rgba(var(--theme-border),0.7)',
                                  outline: 'none',
                                }}
                                onFocus={(e) => {
                                  e.target.style.boxShadow = '0 0 0 2px rgba(59,130,246,0.4)'
                                  e.target.style.borderColor = '#2563eb'
                                }}
                                onBlur={(e) => {
                                  e.target.style.boxShadow = 'none'
                                  e.target.style.borderColor = 'rgba(var(--theme-border),0.7)'
                                }}
                              />
                            </div>
                            <div className="flex items-center gap-1.5">
                              <label className="text-xs text-slate-500 whitespace-nowrap">取值</label>
                              <input
                                type="text"
                                value={enhanceFieldMapping.field_value_desc_index}
                                onChange={(e) => setEnhanceFieldMapping(prev => ({
                                  ...prev,
                                  field_value_desc_index: e.target.value,
                                }))}
                                placeholder="E"
                                className="font-mono text-sm enhance-field-input"
                                style={{
                                  width: '7.5rem',
                                  padding: '0.2rem 0.3rem',
                                  borderRadius: '6px',
                                  border: '1px solid rgba(var(--theme-border),0.7)',
                                  outline: 'none',
                                }}
                                onFocus={(e) => {
                                  e.target.style.boxShadow = '0 0 0 2px rgba(59,130,246,0.4)'
                                  e.target.style.borderColor = '#2563eb'
                                }}
                                onBlur={(e) => {
                                  e.target.style.boxShadow = 'none'
                                  e.target.style.borderColor = 'rgba(var(--theme-border),0.7)'
                                }}
                              />
                            </div>
                          </div>
                          {/* 配置说明 - 使用主题变量以适配深色模式 */}
                          <div
                            className="enhance-mapping-hint"
                            style={{
                              marginTop: '0.5rem',
                              padding: '0.4rem 0.6rem',
                              borderRadius: '8px',
                              backgroundColor: 'rgba(var(--theme-bg-tertiary), 0.8)',
                              border: '1px solid rgb(var(--theme-border))',
                            }}
                          >
                            <p className="text-xs text-slate-500">列标识
                              A/B/C…Z/AA/AB:表名列→表名称、表描述列→表描述、字段名列→字段名、字段描述列→字段注释、取值描述列→取值范围或其他补充（相关信息所在列按实际表格填写）</p>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* 提交按钮 */}
                    <div className="flex justify-end pt-1">
                      <button
                        onClick={async () => {
                          if (!enhanceFile || !workspace.connect_info) return
                          setEnhanceIsUploading(true)
                          try {
                            const res = await uploadExcelFieldData({
                              file: enhanceFile,
                              connect_info: workspace.connect_info,
                              sheet_name: enhanceSheetName || undefined,
                              field_data: enhanceFieldMapping,
                            })
                            if (res.code === 200 && res.data) {
                              setEnhanceResult(res.data)
                              // 刷新卡片数据，确保返回卡片 tab 时显示最新数据
                              fetchCards()
                              // 强制刷新数据源信息（等待完成后使用最新数据更新 workspace 状态）
                              await refreshDataSources()
                              // 手动清除 sessionStorage 缓存后重新加载，确保获取最新数据
                              if (typeof window !== 'undefined') {
                                window.sessionStorage.removeItem('globalDataSourceCache')
                                window.sessionStorage.removeItem(GLOBAL_DATA_SOURCE_CACHE_KEY)
                              }
                              // 强制从 API 重新获取工作空间数据
                              const listRes = await getUserDataSources({
                                page: 1,
                                page_size: 100,
                              })
                              if (listRes.code === 200 && listRes.data?.items) {
                                const found = listRes.data.items.find((w: any) => w.id === workspaceId)
                                if (found) {
                                  setWorkspace(found)
                                }
                              }
                            } else {
                              message.error(res.msg || '上传失败')
                            }
                          } catch (error) {
                            console.error('上传失败:', error)
                            message.error('上传失败，请重试')
                          } finally {
                            setEnhanceIsUploading(false)
                          }
                        }}
                        disabled={!enhanceFile || enhanceIsUploading}
                        style={{
                          borderRadius: '18px',
                          padding: '0.875rem 1.75rem',
                          background: 'linear-gradient(to right, #f59e0b, #f97316)',
                          color: '#fff',
                          fontWeight: 500,
                          boxShadow: '0 10px 15px -3px rgba(251,191,36,0.25)',
                          border: 'none',
                          cursor: enhanceFile && !enhanceIsUploading ? 'pointer' : 'not-allowed',
                          opacity: enhanceFile && !enhanceIsUploading ? 1 : 0.5,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.625rem',
                        }}
                        className="hover:opacity-90 transition-opacity"
                      >
                        {enhanceIsUploading ? (
                          <>
                            <Loader2 className="w-5 h-5 animate-spin" />
                            处理中...
                          </>
                        ) : (
                          <>
                            <Sparkles className="w-5 h-5" />
                            开始处理
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                )}

                {/* 结果展示区域 - 内联圆角保证样式不丢失 */}
                {enhanceResult && (
                  <div className="space-y-6">
                    {/* 统计摘要 */}
                    {enhanceResult.summary && (
                      <div
                        style={{
                          borderRadius: '20px',
                          background: 'linear-gradient(135deg, rgba(255,251,235,0.9) 0%, rgba(255,237,213,0.7) 100%)',
                          border: '1px solid rgba(253,230,138,0.5)',
                          padding: '1.5rem',
                          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                        }}
                      >
                        <h4 className="text-base font-bold text-amber-900 mb-4 flex items-center gap-2">
                          <div style={{
                            width: '2rem',
                            height: '2rem',
                            borderRadius: '12px',
                            backgroundColor: 'rgba(253,230,138,0.5)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                          >
                            <FileCheck className="w-4 h-4 text-amber-700" />
                          </div>
                          处理结果摘要
                        </h4>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          <div style={{
                            backgroundColor: 'rgba(255,255,255,0.85)',
                            borderRadius: '16px',
                            padding: '1rem',
                            border: '1px solid rgba(253,230,138,0.4)',
                            boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                          }}
                          >
                            <div className="text-2xl font-bold text-amber-600"
                            >{enhanceResult.summary.total_tables_in_excel}</div>
                            <div className="text-xs text-slate-500 mt-1">Excel 表总数</div>
                          </div>
                          <div style={{
                            backgroundColor: 'rgba(255,255,255,0.85)',
                            borderRadius: '16px',
                            padding: '1rem',
                            border: '1px solid rgba(167,243,208,0.5)',
                            boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                          }}
                          >
                            <div className="text-2xl font-bold text-emerald-600"
                            >{enhanceResult.summary.matched_tables}</div>
                            <div className="text-xs text-slate-500 mt-1">匹配成功</div>
                          </div>
                          <div style={{
                            backgroundColor: 'rgba(255,255,255,0.85)',
                            borderRadius: '16px',
                            padding: '1rem',
                            border: '1px solid rgba(191,219,254,0.5)',
                            boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                          }}
                          >
                            <div className="text-2xl font-bold text-blue-600"
                            >{enhanceResult.summary.total_fields_updated}</div>
                            <div className="text-xs text-slate-500 mt-1">字段更新总数</div>
                          </div>
                          <div style={{
                            backgroundColor: 'rgba(255,255,255,0.85)',
                            borderRadius: '16px',
                            padding: '1rem',
                            border: '1px solid rgba(221,214,254,0.5)',
                            boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                          }}
                          >
                            <div className="text-2xl font-bold text-violet-600"
                            >{enhanceResult.summary.total_fields_from_excel}</div>
                            <div className="text-xs text-slate-500 mt-1">Excel 填充</div>
                          </div>
                        </div>
                        <div className="mt-4 flex flex-wrap gap-2">
                          {enhanceResult.summary.total_fields_from_llm > 0 && (
                            <span
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-violet-100/80 text-violet-700 text-sm font-medium"
                              style={{ borderRadius: '9999px' }}
                            >
                            <Sparkles className="w-3.5 h-3.5" />
                            LLM 补全: {enhanceResult.summary.total_fields_from_llm}
                          </span>
                          )}
                          {enhanceResult.summary.datacards_deleted > 0 && (
                            <span
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-rose-100/80 text-rose-700 text-sm font-medium"
                              style={{ borderRadius: '9999px' }}
                            >
                            <FileX className="w-3.5 h-3.5" />
                            删除卡片: {enhanceResult.summary.datacards_deleted}
                          </span>
                          )}
                          {enhanceResult.summary.datacards_generated > 0 && (
                            <span
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-100/80 text-emerald-700 text-sm font-medium"
                              style={{ borderRadius: '9999px' }}
                            >
                            <FileCheck className="w-3.5 h-3.5" />
                            生成卡片: {enhanceResult.summary.datacards_generated}
                          </span>
                          )}
                        </div>
                      </div>
                    )}

                    {/* 未匹配表提示 */}
                    {enhanceResult.unmatched_tables_detail && enhanceResult.unmatched_tables_detail.length > 0 && (
                      <div
                        style={{
                          borderRadius: '20px',
                          backgroundColor: 'rgba(255,241,242,0.9)',
                          border: '1px solid rgba(254,202,202,0.6)',
                          padding: '1.25rem',
                          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                        }}
                      >
                        <h4 className="text-sm font-bold text-rose-800 mb-3 flex items-center gap-2">
                          <div style={{
                            width: '1.75rem',
                            height: '1.75rem',
                            borderRadius: '10px',
                            backgroundColor: 'rgba(254,202,202,0.6)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                          >
                            <AlertTriangle className="w-3.5 h-3.5 text-rose-700" />
                          </div>
                          未匹配的表 ({enhanceResult.unmatched_tables_detail.length})
                        </h4>
                        <div className="space-y-2">
                          {enhanceResult.unmatched_tables_detail.map((item: any, idx: number) => (
                            <div key={idx}
                                 className="flex items-center gap-2 bg-white/80 px-4 py-2.5 border border-rose-100"
                                 style={{ borderRadius: '14px' }}
                            >
                              <span className="font-mono text-sm text-rose-700">{item.table_name}</span>
                              <span className="text-slate-300">·</span>
                              <span className="text-sm text-slate-600">{item.reason}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 表级详情 */}
                    {enhanceResult.table_details && enhanceResult.table_details.length > 0 && (
                      <div className="space-y-4">
                        <h4 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                          <div style={{
                            width: '2rem',
                            height: '2rem',
                            borderRadius: '12px',
                            backgroundColor: 'rgba(226,232,240,0.8)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                          >
                            <Table2 className="w-4 h-4 text-slate-600" />
                          </div>
                          表级变更详情
                        </h4>
                        {enhanceResult.table_details.map((table: any, tableIdx: number) => (
                          <div key={tableIdx} style={{
                            borderRadius: '20px',
                            border: '1px solid #e2e8f0',
                            overflow: 'hidden',
                            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                          }}
                          >
                            <div
                              className="bg-gradient-to-r from-slate-50 to-slate-50/80 px-5 py-3.5 border-b border-slate-100 flex items-center justify-between flex-wrap gap-2"
                            >
                              <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-xl bg-blue-100/80 flex items-center justify-center">
                                  <Table className="w-4 h-4 text-blue-600" />
                                </div>
                                <span className="font-semibold text-slate-800">{table.table_name}</span>
                                {table.table_description_updated && (
                                  <span
                                    className="text-xs bg-emerald-100 text-emerald-700 px-2.5 py-1 rounded-full font-medium"
                                  >
                                  表描述已更新
                                </span>
                                )}
                              </div>
                              <div className="flex items-center gap-3 text-xs text-slate-500">
                                <span>字段总数 <strong className="text-slate-700">{table.total_fields}</strong></span>
                                <span>更新 <strong className="text-blue-600">{table.updated_fields}</strong></span>
                                {table.excel_filled_fields > 0 && (
                                  <span className="text-amber-600">Excel {table.excel_filled_fields}</span>
                                )}
                                {table.llm_filled_fields > 0 && (
                                  <span className="text-violet-600">LLM {table.llm_filled_fields}</span>
                                )}
                                {table.still_missing_fields > 0 && (
                                  <span className="text-rose-500">缺失 {table.still_missing_fields}</span>
                                )}
                              </div>
                            </div>
                            {table.field_changes && table.field_changes.length > 0 && (
                              <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                  <thead>
                                  <tr className="bg-white border-b border-slate-100 text-left">
                                    <th className="px-4 py-3 font-semibold text-slate-500 text-xs">字段名</th>
                                    <th className="px-4 py-3 font-semibold text-slate-500 text-xs">更新前</th>
                                    <th className="px-4 py-3 font-semibold text-slate-500 text-xs">更新后</th>
                                    <th className="px-4 py-3 font-semibold text-slate-500 text-xs">来源</th>
                                    <th className="px-4 py-3 font-semibold text-slate-500 text-xs">状态</th>
                                  </tr>
                                  </thead>
                                  <tbody>
                                  {table.field_changes.map((field: any, fieldIdx: number) => (
                                    <tr key={fieldIdx}
                                        className="border-b border-slate-50 hover:bg-slate-50/50 transition-colors"
                                    >
                                      <td className="px-4 py-2.5">
                                        <span className="font-mono font-medium text-slate-700">{field.field_name}</span>
                                      </td>
                                      <td className="px-4 py-2.5 text-slate-500 text-xs max-w-[150px] truncate"
                                          title={field.before_comment}
                                      >
                                        {field.before_comment || <span className="text-slate-300 italic">空</span>}
                                      </td>
                                      <td className="px-4 py-2.5 text-slate-700 text-xs max-w-[150px] truncate"
                                          title={field.after_comment}
                                      >
                                        {field.after_comment || <span className="text-slate-300 italic">空</span>}
                                      </td>
                                      <td className="px-4 py-2.5">
                                        {field.source === 'excel' && (
                                          <span
                                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-amber-100 text-amber-700 text-xs font-medium rounded-full"
                                          >
                                            Excel
                                          </span>
                                        )}
                                        {field.source === 'llm' && (
                                          <span
                                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-violet-100 text-violet-700 text-xs font-medium rounded-full"
                                          >
                                            <Sparkles className="w-3 h-3" /> LLM
                                          </span>
                                        )}
                                        {field.source === 'unchanged' && (
                                          <span
                                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-100 text-slate-500 text-xs font-medium rounded-full"
                                          >
                                            保持
                                          </span>
                                        )}
                                        {field.source === 'missing' && (
                                          <span
                                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-rose-100 text-rose-700 text-xs font-medium rounded-full"
                                          >
                                            缺失
                                          </span>
                                        )}
                                      </td>
                                      <td className="px-4 py-2.5">
                                        {field.changed ? (
                                          <span
                                            className="text-emerald-600 flex items-center gap-1 text-xs font-medium"
                                          >
                                            <ArrowRight className="w-3 h-3" /> 已更新
                                          </span>
                                        ) : (
                                          <span className="text-slate-400 text-xs">—</span>
                                        )}
                                      </td>
                                    </tr>
                                  ))}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'ask' && (
            <div
              className="workspace-tab workspace-tab-ask bg-white dark:bg-slate-800 rounded-[28px] border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden"
            >
              {/* 问数 Tab 头部：与资产 tab 一致，与下方内容同属一个容器 */}
              <div
                className="workspace-tab-header"
                style={{
                  padding: '1.25rem',
                  borderBottom: '1px solid rgb(var(--theme-border))',
                  background: 'linear-gradient(135deg, rgba(var(--theme-bg-tertiary), 0.6) 0%, rgb(var(--theme-bg)) 50%, rgba(var(--theme-bg-tertiary), 0.4) 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div className="flex items-center gap-4">
                  <div style={{
                    width: '2.5rem',
                    height: '2.5rem',
                    borderRadius: '16px',
                    background: 'linear-gradient(135deg, rgb(6,182,212), rgb(37,99,235))',
                    color: '#fff',
                    boxShadow: '0 10px 15px -3px rgba(6,182,212,0.4)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                  >
                    <MessageSquare className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">智能问数</h3>
                    <p className="text-sm text-slate-500">输入自然语言问题，获取 SQL 查询结果</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {/* 数据源选择模式切换：更直观的交互 */}
                  <div className="flex items-center gap-1.5 bg-slate-100 p-1" style={{ borderRadius: '12px' }}>
                    <button
                      onClick={() => setIsMultiSelectMode(false)}
                      className={`text-xs font-medium px-3 py-1.5 transition-all ${
                        !isMultiSelectMode
                          ? 'bg-white text-cyan-700 shadow-sm'
                          : 'text-slate-500 hover:text-slate-700'
                      }`}
                      style={{ borderRadius: '10px' }}
                    >
                      单数据源
                    </button>
                    <button
                      onClick={() => setIsMultiSelectMode(true)}
                      className={`text-xs font-medium px-3 py-1.5 transition-all ${
                        isMultiSelectMode
                          ? 'bg-white text-cyan-700 shadow-sm'
                          : 'text-slate-500 hover:text-slate-700'
                      }`}
                      style={{ borderRadius: '10px' }}
                    >
                      多数据源
                    </button>
                  </div>
                </div>
              </div>

              <div className="p-5 space-y-5">
                {/* 数据源选择：单数据源仅展示当前，多数据源展示可选列表 */}
                <div className="bg-slate-50/80 dark:bg-slate-800/80 border border-slate-100 dark:border-slate-700 p-5 shadow-sm" style={{ borderRadius: '20px' }}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Layers className="w-4 h-4 text-slate-400 dark:text-slate-500" />
                      <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                    {isMultiSelectMode ? '可选数据源（可多选）' : '当前数据源'}
                  </span>
                      {isMultiSelectMode && (
                        <span className="text-xs text-slate-400 dark:text-slate-500">已选 {selectedDataSourceIds.length} 个</span>
                      )}
                    </div>
                    {!isMultiSelectMode && (
                      <span className="text-xs text-slate-500 dark:text-slate-400">将使用当前工作区数据源进行查询</span>
                    )}
                  </div>
                  {!isMultiSelectMode ? (
                    /* 单数据源：不展示其他可选，仅显示当前工作区对应数据源 */
                    (() => {
                      const currentDs = allDataSources.find(d => d.id === workspace?.id)
                      return (
                        <div
                          className="flex items-center gap-2 py-2 px-3 bg-slate-50 dark:bg-slate-700 border border-slate-100 dark:border-slate-600 text-slate-700 dark:text-slate-200 text-sm"
                          style={{ borderRadius: '12px' }}
                        >
                          <span>{currentDs ? getDbTypeIcon(currentDs.db_type) : null}</span>
                          <span className="font-medium"
                          >{currentDs?.connect_name ?? (workspace as any)?.name ?? '当前工作区'}</span>
                        </div>
                      )
                    })()
                  ) : dataSourcesLoading ? (
                    <div className="flex items-center justify-center py-6">
                      <div className="animate-spin" style={{
                        width: '20px',
                        height: '20px',
                        border: '2px solid #e9d5ff',
                        borderTop: '2px solid #9333ea',
                        borderRadius: '50%',
                      }}
                      ></div>
                      <span className="ml-2 text-sm text-slate-500 dark:text-slate-400">加载中...</span>
                    </div>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {/* 数据源排序：当前工作区对应的数据源排在最前面 */}
                      {[...allDataSources].sort((a, b) => {
                        if (a.id === workspace?.id) return -1
                        if (b.id === workspace?.id) return 1
                        return 0
                      }).map((ds) => {
                        const isSelected = selectedDataSourceIds.includes(ds.id)
                        const isCurrent = ds.id === workspace?.id
                        return (
                          <button
                            key={ds.id}
                            onClick={() => toggleDataSourceSelection(ds.id)}
                            title={isCurrent && isSelected ? '当前数据源不可取消' : undefined}
                            className="text-sm flex items-center gap-2 transition-colors px-3 py-2 border"
                            style={{
                              borderRadius: '12px',
                              backgroundColor: isSelected
                                ? (document.documentElement.getAttribute('data-theme') === 'dark' ? 'rgba(14, 165, 233, 0.2)' : '#f0f9ff')
                                : (document.documentElement.getAttribute('data-theme') === 'dark' ? '#1e293b' : '#f8fafc'),
                              color: isSelected
                                ? (document.documentElement.getAttribute('data-theme') === 'dark' ? '#38bdf8' : '#0369a1')
                                : (document.documentElement.getAttribute('data-theme') === 'dark' ? '#e2e8f0' : '#475569'),
                              borderColor: isSelected
                                ? (document.documentElement.getAttribute('data-theme') === 'dark' ? 'rgba(14, 165, 233, 0.6)' : '#0ea5e9')
                                : (document.documentElement.getAttribute('data-theme') === 'dark' ? '#475259' : '#e2e8f0'),
                            }}
                          >
                            {isMultiSelectMode && (
                              <span
                                className="w-4 h-4 flex items-center justify-center shrink-0"
                                style={{
                                  borderRadius: '4px',
                                  backgroundColor: isSelected
                                    ? (document.documentElement.getAttribute('data-theme') === 'dark' ? 'rgba(14, 165, 233, 0.9)' : '#0ea5e9')
                                    : 'transparent',
                                  border: `1.5px solid ${isSelected
                                    ? (document.documentElement.getAttribute('data-theme') === 'dark' ? 'rgba(14, 165, 233, 0.9)' : '#0ea5e9')
                                    : (document.documentElement.getAttribute('data-theme') === 'dark' ? '#475259' : '#cbd5e1')}`,
                                }}
                              >
                            {isSelected && (
                              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"
                                   style={{ color: '#fff' }}
                              >
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                              </svg>
                            )}
                          </span>
                            )}
                            <span>{getDbTypeIcon(ds.db_type)}</span>
                            <span style={{
                              maxWidth: '220px',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }} title={ds.connect_name}
                            >{ds.connect_name}</span>
                            {isCurrent && (
                              <span className="text-[10px] px-1.5 py-0.5 shrink-0" style={{
                                borderRadius: '9999px',
                                backgroundColor: isSelected
                                  ? (document.documentElement.getAttribute('data-theme') === 'dark' ? 'rgba(56, 189, 248, 0.2)' : '#e0f2fe')
                                  : (document.documentElement.getAttribute('data-theme') === 'dark' ? 'rgba(167, 139, 250, 0.2)' : '#ede9fe'),
                                color: isSelected
                                  ? (document.documentElement.getAttribute('data-theme') === 'dark' ? '#38bdf8' : '#0369a1')
                                  : (document.documentElement.getAttribute('data-theme') === 'dark' ? '#c084fc' : '#6b21a8'),
                              }}
                              >当前</span>
                            )}
                          </button>
                        )
                      })}
                    </div>
                  )}
                </div>

                {/* 输入区域 */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                  {/* 问题输入 */}
                  <div className="lg:col-span-2 border p-5 shadow-sm"
                       style={{ borderRadius: '28px', backgroundColor: 'rgb(var(--theme-bg))', borderColor: 'rgb(var(--theme-border))' }}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <Sparkles className="w-4 h-4" style={{ color: 'rgb(var(--theme-primary))' }} />
                        <span className="text-sm font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>问题输入</span>
                      </div>
                      <span className="text-xs" style={{ color: 'rgb(var(--theme-text-muted))' }}>{askQuestion.length} 字符</span>
                    </div>
                    <textarea
                      value={askQuestion}
                      onChange={(e) => setAskQuestion(e.target.value)}
                      placeholder="选择数据源，输入您的自然语言问题，系统将自动生成 SQL 并执行聚合查询"
                      className="w-full px-4 py-3 border-2 focus:outline-none focus:ring-4 text-sm transition-all resize-none"
                      style={{
                        borderRadius: '16px',
                        minHeight: '100px',
                        borderColor: 'rgb(var(--theme-border))',
                        backgroundColor: 'rgb(var(--theme-bg))',
                        color: 'rgb(var(--theme-text))',
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                          handleAskQuery()
                        }
                      }}
                    />
                    <div className="flex items-center justify-between mt-3">
                      <span className="text-xs" style={{ color: 'rgb(var(--theme-text-muted))' }}>Ctrl + Enter 执行查询</span>
                      <button
                        onClick={handleAskQuery}
                        disabled={!askQuestion.trim() || askQueryStatus === 'analyzing'}
                        className="px-6 py-2 text-white text-sm font-semibold transition-all"
                        style={{ borderRadius: '9999px', background: askQueryStatus === 'analyzing' ? 'rgb(var(--theme-border))' : 'linear-gradient(135deg, rgb(var(--theme-primary)), rgb(219, 39, 119))', color: askQueryStatus === 'analyzing' ? 'rgb(var(--theme-text-muted))' : '#fff', cursor: askQueryStatus === 'analyzing' ? 'not-allowed' : 'pointer' }}
                      >
                        {askQueryStatus === 'idle' ? '执行查询' : askQueryStatus === 'error' ? '重新查询' : '查询中...'}
                      </button>
                    </div>
                  </div>

                  {/* 快捷问题 */}
                  <div className="border p-5 shadow-sm" style={{ borderRadius: '28px', backgroundColor: 'rgb(var(--theme-bg))', borderColor: 'rgb(var(--theme-border))' }}>
                    <div className="flex items-center gap-2 mb-3">
                      <Zap className="w-4 h-4" style={{ color: 'rgb(245, 158, 11)' }} />
                      <span className="text-sm font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>示例提问方式</span>
                    </div>
                    <div className="space-y-2">
                      {presetQuestions.map((q, i) => (
                        <div
                          key={i}
                          className="w-full text-left px-3 py-2.5 text-xs border transition-all cursor-default"
                          style={{ borderRadius: '12px', borderColor: 'transparent', backgroundColor: 'transparent', color: 'rgb(var(--theme-text-muted))' }}
                        >
                          {q}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* 查询进度：to-list、圆角、无步骤背景、顺滑节奏 */}
                {askQueryStep > 0 && (
                  <div className="border p-5 shadow-sm" style={{ borderRadius: '20px', backgroundColor: 'rgb(var(--theme-bg))', borderColor: 'rgb(var(--theme-border))' }}>
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2">
                        <Loader2 className="w-5 h-5 animate-spin" style={{ color: 'rgb(var(--theme-primary))' }} />
                        <span className="text-sm font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>查询进度</span>
                      </div>
                      <span className="text-sm font-bold" style={{ color: 'rgb(var(--theme-primary))' }}>{Math.round(askProgressPercent)}%</span>
                    </div>
                    <div className="h-2.5 overflow-hidden mb-5" style={{ borderRadius: '999px', backgroundColor: 'rgb(var(--theme-bg-secondary))' }}>
                      <div
                        className="h-full transition-all duration-500 ease-out"
                        style={{
                          width: `${Math.min(100, Math.round(askProgressPercent))}%`,
                          borderRadius: '999px',
                          background: 'linear-gradient(135deg, rgb(var(--theme-primary)), rgb(219, 39, 119))',
                        }}
                      />
                    </div>
                    <ul className="space-y-1.5">
                      {askQuerySteps.map((step, i) => (
                        <li
                          key={step.id}
                          className="flex flex-col py-2 px-3 text-sm transition-colors border border-transparent"
                          style={{
                            borderRadius: '12px',
                            backgroundColor: askQueryStep === i + 1 ? 'rgba(var(--theme-primary), 0.08)' : 'transparent',
                          }}
                        >
                          <div className="flex items-center gap-3">
                            <span
                              className="w-6 h-6 flex items-center justify-center text-xs font-bold shrink-0"
                              style={{
                                borderRadius: '50%',
                                backgroundColor: askQueryStep > i + 1 ? 'rgba(var(--theme-primary), 0.2)' : askQueryStep === i + 1 ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-bg-secondary))',
                                color: askQueryStep > i + 1 ? 'rgb(var(--theme-primary))' : askQueryStep === i + 1 ? '#fff' : 'rgb(var(--theme-text-muted))',
                              }}
                            >
                              {askQueryStep > i + 1 ? '✓' : i + 1}
                            </span>
                            <span
                              className="font-medium"
                              style={{
                                color: askQueryStep > i + 1 ? 'rgb(var(--theme-primary))' : askQueryStep === i + 1 ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-muted))',
                              }}
                            >
                              {step.name}
                            </span>
                          </div>
                          {askQueryStep === i + 1 && step.description && (
                            <div
                              className="mt-1.5 text-xs"
                              style={{
                                color: 'rgb(var(--theme-text-muted))',
                                marginLeft: '2.25rem',
                              }}
                            >
                              {step.description}
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* 错误提示 */}
                {askError && (
                  <div className="border p-5 shadow-sm" style={{ borderRadius: '16px', backgroundColor: 'rgba(239, 68, 68, 0.05)', borderColor: 'rgba(239, 68, 68, 0.2)' }}>
                    <div className="flex items-center gap-2" style={{ color: 'rgb(239, 68, 68)' }}>
                      <AlertCircle className="w-5 h-5" />
                      <span className="text-sm font-semibold">查询失败</span>
                    </div>
                    <p className="text-sm mt-2" style={{ color: 'rgb(239, 68, 68)' }}>{askError}</p>
                  </div>
                )}

                {/* 查询结果 */}
                {askQueryResult && askQueryResult.code === 200 && askQueryResult.data && (
                  <div className="space-y-5">
                    {/* 检索结果概览：一个组件内展示 */}
                    <div
                      className="border shadow-sm p-4 flex flex-wrap items-center gap-x-6 gap-y-3"
                      style={{ borderRadius: '16px', backgroundColor: 'rgb(var(--theme-bg))', borderColor: 'rgb(var(--theme-border))' }}
                    >
                      <div className="flex items-center gap-2">
                        <FileCheck className="w-4 h-4" style={{ color: 'rgb(var(--theme-primary))' }} />
                        <span className="text-sm font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>检索结果概览</span>
                      </div>
                      <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
                        <span className="text-sm" style={{ color: 'rgb(var(--theme-text-muted))' }}>涉及数据源： <strong style={{ color: 'rgb(var(--theme-primary))' }}>{askQueryResult.data.clusters?.length || 0}</strong> 个</span>
                        <span className="text-sm" style={{ color: 'rgb(var(--theme-text-muted))' }}>结果： <strong style={{ color: 'rgb(34, 197, 94)' }}>{askQueryResult.data.final_rows?.length || askQueryResult.data.clusters?.reduce((s: number, c: any) => s + (c.rows?.length || 0), 0) || 0}</strong> 条</span>
                        {askQueryResult.data.merge?.strategy && (
                          <span className="text-sm" style={{ color: 'rgb(var(--theme-text-muted))' }}>合并方式： <strong style={{ color: 'rgb(59, 130, 246)' }}>{askQueryResult.data.merge.strategy}</strong></span>
                        )}
                        {askQueryResult.data.merge?.entity_key && (
                          <span className="text-slate-500 text-sm">关联字段： <strong className="text-orange-600"
                          >{askQueryResult.data.merge.entity_key}</strong></span>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setAskQueryResult(null)
                          setAskError(null)
                          setAskQuestion('')
                        }}
                        className="ml-auto text-xs text-slate-500 hover:text-red-600 transition-colors px-3 py-1.5"
                      >
                        清空结果
                      </button>
                    </div>

                    {/* 术语展开信息 - 有匹配时显示完整面板 */}
                    {askQueryResult.data.term_rewrite?.enabled && askQueryResult.data.term_rewrite.matched_count > 0 && (
                      <div
                        className="border shadow-sm overflow-hidden"
                        style={{ borderRadius: '16px', backgroundColor: 'rgb(var(--theme-bg))', borderColor: 'rgb(var(--theme-border))' }}
                      >
                        <div
                          className="px-4 py-3 flex items-center gap-2 border-b"
                          style={{ backgroundColor: 'rgba(139, 92, 246, 0.1)', borderColor: 'rgb(var(--theme-border))' }}
                        >
                          <Sparkles className="w-4 h-4" style={{ color: 'rgb(var(--theme-primary))' }} />
                          <span className="text-sm font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>术语展开</span>
                          <span className="text-xs" style={{ color: 'rgb(var(--theme-text-muted))' }}>
                            匹配到 {askQueryResult.data.term_rewrite.matched_count} 个术语
                          </span>
                        </div>
                        {askQueryResult.data.term_rewrite.rewritten_question && (
                          <div className="px-4 py-3 border-b" style={{ borderColor: 'rgb(var(--theme-border))' }}>
                            <div className="text-xs mb-1" style={{ color: 'rgb(var(--theme-text-muted))' }}>展开后的问题</div>
                            <div className="text-sm" style={{ color: 'rgb(var(--theme-text))' }}>
                              {askQueryResult.data.term_rewrite.rewritten_question}
                            </div>
                          </div>
                        )}
                        {askQueryResult.data.term_rewrite.matched_terms && askQueryResult.data.term_rewrite.matched_terms.length > 0 && (
                          <div style={{ padding: '16px', maxHeight: '192px', overflowY: 'auto' }}>
                            <div style={{ display: 'grid', gap: '12px' }}>
                              {askQueryResult.data.term_rewrite.matched_terms.map((term: any, index: number) => (
                                <div
                                  key={index}
                                  className="term-match-item"
                                  style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', padding: '12px', backgroundColor: 'rgb(var(--theme-bg))', borderWidth: '1px', borderStyle: 'solid', borderColor: 'rgb(var(--theme-border))', borderRadius: '12px', boxSizing: 'border-box' }}
                                >
                                  <span style={{ display: 'inline-flex', width: '16px', height: '16px', marginTop: '2px', flexShrink: 0, backgroundColor: 'transparent' }}>
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--theme-primary))" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ backgroundColor: 'transparent' }}>
                                      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
                                      <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
                                    </svg>
                                  </span>
                                  <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                      <span className="text-sm font-medium" style={{ color: 'rgb(var(--theme-primary))' }}>
                                        {term.term_name}
                                      </span>
                                      <span className="text-xs" style={{ color: 'rgb(var(--theme-text-muted))' }}>
                                        ({term.matched_name})
                                      </span>
                                      <span
                                        style={{ padding: '2px 8px', backgroundColor: 'rgb(var(--theme-bg-secondary))', borderRadius: '6px', fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}
                                      >
                                        {term.library_name}
                                      </span>
                                    </div>
                                    <div className="text-xs mt-1" style={{ color: 'rgb(var(--theme-text-muted))' }}>
                                      {term.term_definition}
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* 术语展开未匹配时的友好提示 */}
                    {askQueryResult.data.term_rewrite?.enabled && askQueryResult.data.term_rewrite.matched_count === 0 && (
                      <div style={{ display: 'flex', justifyContent: 'center' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '8px 16px', backgroundColor: '#fef3c7', border: '1px solid #fcd34d', borderRadius: '8px' }}>
                          <Sparkles className="w-4 h-4" style={{ color: '#d97706' }} />
                          <span style={{ fontSize: '13px', color: '#92400e' }}>
                            暂未匹配到相关术语，或术语库功能未启用
                          </span>
                        </div>
                      </div>
                    )}

                    {/* 各数据源结果详情（每个数据源块内展示该数据源涉及的数据卡片） */}
                    {askQueryResult.data.clusters?.map((cluster: any, idx: number) => {
                      const hasError = !!cluster.error
                      const dataCards = Array.isArray(askQueryResult.data.data_cards) && Array.isArray(cluster.tables)
                        ? cluster.tables
                          .map((t: any) => {
                            const tableName = t?.table_name
                            if (!tableName) return null
                            const card = askQueryResult.data.data_cards.find((c: any) =>
                              c.table_name === tableName || (typeof tableName === 'string' && tableName.endsWith('.' + c.table_name)),
                            )
                            return card
                          })
                          .filter(Boolean)
                        : []
                      return (
                        <div key={idx} className="bg-white border border-slate-100 overflow-hidden shadow-sm"
                             style={{ borderRadius: '20px' }}
                        >
                          <div
                            className={`px-5 py-4 border-b ${hasError ? 'bg-red-50 border-red-100' : 'bg-slate-50 border-slate-100'}`}
                            style={{
                              borderTopLeftRadius: '20px',
                              borderTopRightRadius: '20px',
                            }}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3">
                                <div
                                  className="w-8 h-8 flex items-center justify-center text-white font-bold"
                                  style={{
                                    borderRadius: '12px',
                                    background: hasError ? '#ef4444' : 'linear-gradient(to bottom right, #8b5cf6, #db2777)',
                                  }}
                                >
                                  {idx + 1}
                                </div>
                                <div>
                                  <h5 className="text-sm font-semibold text-slate-900">数据源 {idx + 1}</h5>
                                  <p className="text-xs text-slate-500"
                                  >{cluster.db_type} · {cluster.tables?.[0]?.table_name}</p>
                                </div>
                              </div>
                              <span
                                className={`text-xs font-medium px-3 py-1 ${hasError ? 'bg-red-100 text-red-600' : 'bg-purple-100 text-purple-600'}`}
                                style={{ borderRadius: '9999px' }}
                              >
                            {cluster.rows?.length || 0} 条
                          </span>
                            </div>
                          </div>
                          <div className="p-5 space-y-4">
                            {dataCards.length > 0 && (
                              <div>
                                <span className="text-xs font-semibold text-slate-600 block mb-2"
                                >涉及的数据卡片（点击可查看详情）</span>
                                <div className="flex flex-wrap gap-2">
                                  {dataCards.map((card: any, i: number) => (
                                    <button
                                      key={i}
                                      type="button"
                                      onClick={() => handleOpenAskCardDetail([card])}
                                      className="px-3 py-2 text-sm font-medium text-purple-700 transition-colors border border-purple-100 hover:bg-purple-100"
                                      style={{ borderRadius: '12px' }}
                                    >
                                      {card.table_name || card.name || `卡片 ${i + 1}`}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            )}
                            {hasError && (
                              <div className="p-3 bg-red-50 border border-red-100 text-red-600 text-sm"
                                   style={{ borderRadius: '12px' }}
                              >
                                {cluster.note || cluster.error}
                              </div>
                            )}
                            {!hasError && cluster.target_sql && (
                              <div>
                                <div className="flex items-center justify-between mb-2">
                                  <span className="text-xs font-semibold text-slate-600">生成的SQL</span>
                                  <button
                                    onClick={() => handleCopyAskSQL(cluster.target_sql, idx)}
                                    className="text-xs text-slate-400 hover:text-slate-600"
                                  >
                                    {copiedClusterIndex === idx ? '已复制' : '复制'}
                                  </button>
                                </div>
                                <div className="border border-slate-200 overflow-hidden"
                                     style={{ borderRadius: '12px' }}
                                >
                                  <SyntaxHighlighter
                                    language="sql"
                                    style={vscDarkPlus}
                                    customStyle={{
                                      margin: 0,
                                      fontSize: '0.75rem',
                                      borderRadius: '12px',
                                    }}
                                    wrapLines
                                  >
                                    {formatAskSQL(cluster.target_sql)}
                                  </SyntaxHighlighter>
                                </div>
                              </div>
                            )}
                            {!hasError && cluster.rows?.length > 0 && (
                              <div>
                                <div className="flex items-center justify-between mb-2">
                                  <span className="text-xs font-semibold text-slate-600">查询结果</span>
                                  <span className="text-xs text-slate-400">{cluster.rows.length} 条</span>
                                </div>
                                <div className="border border-slate-200 overflow-auto" style={{
                                  borderRadius: '12px',
                                  maxHeight: '300px',
                                }}
                                >
                                  <table className="w-full text-xs">
                                    <thead className="bg-slate-50 sticky top-0">
                                    <tr>
                                      {Object.keys(cluster.rows[0]).map(col => (
                                        <th key={col}
                                            className="px-3 py-2 text-left font-semibold text-slate-600 border-b"
                                        >{col}</th>
                                      ))}
                                    </tr>
                                    </thead>
                                    <tbody>
                                    {cluster.rows.slice(0, 50).map((row: any, ri: number) => (
                                      <tr key={ri} className="border-t border-slate-50">
                                        {Object.values(row).map((cell: any, ci: number) => (
                                          <td key={ci} className="px-3 py-2 text-slate-600">{String(cell ?? '-')}</td>
                                        ))}
                                      </tr>
                                    ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      )
                    })}

                    {/* 合并结果：圆角 */}
                    {askQueryResult.data.final_rows?.length > 0 && (
                      <div className="bg-white border-2 border-purple-200 overflow-hidden shadow-lg"
                           style={{ borderRadius: '20px' }}
                      >
                        <div className="bg-gradient-to-r from-purple-500 to-pink-500 px-5 py-4" style={{
                          borderTopLeftRadius: '18px',
                          borderTopRightRadius: '18px',
                        }}
                        >
                          <div className="flex items-center gap-3">
                            <Sparkles className="w-5 h-5 text-white" />
                            <span className="text-base font-bold text-white">合并结果</span>
                            <span className="ml-auto text-sm text-white/80"
                            >{askQueryResult.data.final_rows.length} 条</span>
                          </div>
                        </div>
                        <div className="p-5">
                          <div className="border border-purple-100 overflow-auto" style={{
                            borderRadius: '14px',
                            maxHeight: '400px',
                          }}
                          >
                            <table className="w-full text-xs">
                              <thead className="bg-purple-50 sticky top-0">
                              <tr>
                                {Object.keys(askQueryResult.data.final_rows[0]).map(col => (
                                  <th key={col}
                                      className="px-3 py-2.5 text-left font-bold text-purple-700 border-b border-purple-100"
                                  >{col}</th>
                                ))}
                              </tr>
                              </thead>
                              <tbody>
                              {askQueryResult.data.final_rows.map((row: any, ri: number) => (
                                <tr key={ri} className="border-t border-purple-50">
                                  {Object.values(row).map((cell: any, ci: number) => (
                                    <td key={ci} className="px-3 py-2.5 text-slate-600">{String(cell ?? '-')}</td>
                                  ))}
                                </tr>
                              ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* 空状态 */}
                {!askQueryResult && !askError && askQueryStatus === 'idle' && (
                  <div
                    className="py-16 px-4 text-center"
                    style={{
                      borderRadius: '24px',
                      border: '2px dashed rgb(var(--theme-border))',
                      backgroundColor: 'rgba(var(--theme-bg-secondary), 0.5)',
                    }}
                  >
                    <div
                      className="w-24 h-24 rounded-full flex items-center justify-center mx-auto mb-6"
                      style={{ color: 'rgb(var(--theme-text-muted))' }}
                    >
                      <MessageSquare className="w-12 h-12" />
                    </div>
                    <h4 className="text-xl font-bold mb-3" style={{ color: 'rgb(var(--theme-text))' }}>开始您的问数</h4>
                    <p className="max-w-md mx-auto" style={{ color: 'rgb(var(--theme-text-muted))' }}>在此处查看聚合检索相关结果（目标数据表、检索SQL语句和最终结果）</p>
                  </div>
                )}

                {/* 取消按钮 */}
                {askQueryStatus === 'analyzing' && (
                  <div className="flex justify-center">
                    <button
                      onClick={handleCancelAskQuery}
                      className="px-6 py-2.5 bg-red-500 hover:bg-red-600 text-white text-sm font-medium transition-all shadow-lg"
                      style={{ borderRadius: '9999px' }}
                    >
                      取消查询
                    </button>
                  </div>
                )}
              </div>

              {/* 数据卡片详情弹框 */}
              {isCardDetailOpen && selectedDataCards.length > 0 && (
                <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
                     onClick={handleCloseAskCardDetail}
                >
                  <div className="shadow-xl max-w-5xl w-full max-h-[90vh] overflow-hidden"
                       style={{ borderRadius: '24px', backgroundColor: 'rgb(var(--theme-bg))' }}
                       onClick={(e) => e.stopPropagation()}
                  >
                    <div className="border-b px-6 py-5 flex justify-between items-start"
                         style={{ borderColor: 'rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))', borderRadius: '24px 24px 0 0' }}
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <FileText className="w-5 h-5" style={{ color: 'rgb(var(--theme-primary))' }} />
                          <span className="text-xs uppercase tracking-wide" style={{ color: 'rgb(var(--theme-text-muted))' }}>数据卡片</span>
                          {selectedDataCards.length > 1 && (
                            <span className="text-xs" style={{ color: 'rgb(var(--theme-text-muted))' }}>({selectedDataCards.length} 张)</span>
                          )}
                        </div>
                        <h3 className="text-xl font-semibold"
                            style={{ color: 'rgb(var(--theme-text))' }}
                        >{selectedDataCards[activeCardIndex].table_name}</h3>
                      </div>
                      <button
                        onClick={handleCloseAskCardDetail}
                        className="p-1.5 transition-colors"
                        style={{ borderRadius: '12px', color: 'rgb(var(--theme-text-muted))' }}
                      >
                        <X className="w-5 h-5" />
                      </button>
                    </div>

                    {selectedDataCards.length > 1 && (
                      <div className="border-b px-6" style={{ backgroundColor: 'rgb(var(--theme-bg-secondary))', borderColor: 'rgb(var(--theme-border))' }}>
                        <div className="flex gap-2 overflow-x-auto py-1">
                          {selectedDataCards.map((card, index) => (
                            <button
                              key={index}
                              onClick={() => setActiveCardIndex(index)}
                              className="px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-all"
                              style={{
                                borderRadius: '10px',
                                backgroundColor: activeCardIndex === index ? '#7c3aed' : 'transparent',
                                color: activeCardIndex === index ? '#fff' : 'rgb(var(--theme-text-muted))',
                                border: activeCardIndex === index ? 'none' : '1px solid rgb(var(--theme-border))',
                              }}
                            >
                              {card.table_name}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="overflow-y-auto max-h-[calc(90vh-88px)] p-6">
                      <div className="space-y-5">
                        {/* 基本信息区域 */}
                        <div
                          className="p-5"
                          style={{
                            borderRadius: '16px',
                            backgroundColor: 'rgba(var(--theme-bg-secondary), 0.5)',
                            border: '1px solid rgb(var(--theme-border))',
                          }}
                        >
                          <h4 className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'rgb(var(--theme-text))' }}>
                            <span style={{ width: '4px', height: '16px', backgroundColor: '#8b5cf6', borderRadius: '2px' }}></span>
                            基本信息
                          </h4>
                          <div className="grid grid-cols-2 gap-4">
                            <div className="flex items-center gap-3 p-3" style={{ borderRadius: '12px', border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))' }}>
                              <div className="w-8 h-8 flex items-center justify-center" style={{ borderRadius: '8px', backgroundColor: 'rgba(59, 130, 246, 0.15)' }}>
                                <span className="text-blue-500 text-xs font-bold">表</span>
                              </div>
                              <div className="flex-1 min-w-0">
                                <span className="text-xs block" style={{ color: 'rgb(var(--theme-text-muted))' }}>表名</span>
                                <span className="text-sm font-medium truncate" style={{ color: 'rgb(var(--theme-text))' }}>{selectedDataCards[activeCardIndex].table_name}</span>
                              </div>
                            </div>
                            <div className="flex items-center gap-3 p-3" style={{ borderRadius: '12px', border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))' }}>
                              <div className="w-8 h-8 flex items-center justify-center" style={{ borderRadius: '8px', backgroundColor: 'rgba(34, 197, 94, 0.15)' }}>
                                <span className="text-green-500 text-xs font-bold">库</span>
                              </div>
                              <div className="flex-1 min-w-0">
                                <span className="text-xs block" style={{ color: 'rgb(var(--theme-text-muted))' }}>数据库</span>
                                <span className="text-sm font-medium truncate" style={{ color: 'rgb(var(--theme-text))' }}>{selectedDataCards[activeCardIndex].database_name}</span>
                              </div>
                            </div>
                            <div className="flex items-center gap-3 p-3" style={{ borderRadius: '12px', border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))' }}>
                              <div className="w-8 h-8 flex items-center justify-center" style={{ borderRadius: '8px', backgroundColor: 'rgba(249, 115, 22, 0.15)' }}>
                                <span className="text-orange-500 text-xs font-bold">连</span>
                              </div>
                              <div className="flex-1 min-w-0">
                                <span className="text-xs block" style={{ color: 'rgb(var(--theme-text-muted))' }}>连接</span>
                                <span className="text-sm font-medium truncate" style={{ color: 'rgb(var(--theme-text))' }}>{selectedDataCards[activeCardIndex].connect_name}</span>
                              </div>
                            </div>
                            <div className="flex items-center gap-3 p-3" style={{ borderRadius: '12px', border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(--theme-bg))' }}>
                              <div className="w-8 h-8 flex items-center justify-center" style={{ borderRadius: '8px', backgroundColor: 'rgba(168, 85, 247, 0.15)' }}>
                                <span className="text-purple-500 text-xs font-bold">域</span>
                              </div>
                              <div className="flex-1 min-w-0">
                                <span className="text-xs block" style={{ color: 'rgb(var(--theme-text-muted))' }}>领域</span>
                                <span className="text-sm font-medium truncate" style={{ color: 'rgb(var(--theme-text))' }}>{selectedDataCards[activeCardIndex].card_content?.DocInfo?.domain || '-'}</span>
                              </div>
                            </div>
                          </div>
                        </div>

                        {selectedDataCards[activeCardIndex].card_content?.Abstract && (
                          <div
                            className="p-5"
                            style={{
                              borderRadius: '16px',
                              backgroundColor: 'rgba(var(--theme-bg-secondary), 0.5)',
                              border: '1px solid rgb(var(--theme-border))',
                            }}
                          >
                            <h4 className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'rgb(var(--theme-text))' }}>
                              <span style={{ width: '4px', height: '16px', backgroundColor: '#10b981', borderRadius: '2px' }}></span>
                              表摘要
                            </h4>
                            <div className="p-4" style={{ borderRadius: '12px', border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))' }}>
                              <p className="text-sm leading-relaxed" style={{ textIndent: '2em', color: 'rgb(var(--theme-text))' }}>
                                {selectedDataCards[activeCardIndex].card_content.Abstract}
                              </p>
                            </div>
                          </div>
                        )}

                        {selectedDataCards[activeCardIndex].card_content?.SQLMeta?.columns && (
                          <div
                            className="p-5"
                            style={{
                              borderRadius: '16px',
                              backgroundColor: 'rgba(var(--theme-bg-secondary), 0.5)',
                              border: '1px solid rgb(var(--theme-border))',
                            }}
                          >
                            <h4 className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'rgb(var(--theme-text))' }}>
                              <span style={{ width: '4px', height: '16px', backgroundColor: '#3b82f6', borderRadius: '2px' }}></span>
                              字段信息
                            </h4>
                            <div className="overflow-x-auto" style={{
                              borderRadius: '12px',
                              border: '1px solid rgb(var(--theme-border))',
                            }}
                            >
                              <table className="w-full text-sm">
                                <thead>
                                <tr style={{ backgroundColor: 'rgb(var(--theme-bg-secondary))' }}>
                                  <th className="text-left px-4 py-3 font-semibold border-b"
                                  >字段名
                                  </th>
                                  <th className="text-left px-4 py-3 font-semibold border-b">类型</th>
                                  <th className="text-left px-4 py-3 font-semibold border-b"
                                  >描述
                                  </th>
                                </tr>
                                </thead>
                                <tbody>
                                {selectedDataCards[activeCardIndex].card_content.SQLMeta.columns.map((col: any, idx: number) => (
                                  <tr key={idx} className="border-t" style={{ borderColor: 'rgb(var(--theme-border))' }}>
                                    <td className="px-4 py-2.5 font-medium">
                                      {col.name}
                                      {col.is_primary && (
                                        <span className="ml-2 text-[10px] px-1.5 py-0.5 font-semibold"
                                              style={{ borderRadius: '4px', backgroundColor: 'rgba(245, 158, 11, 0.2)', color: 'rgb(217, 119, 6)' }}
                                        >PK</span>
                                      )}
                                      {col.is_foreign && (
                                        <span className="ml-2 text-[10px] px-1.5 py-0.5 font-semibold"
                                              style={{ borderRadius: '4px', backgroundColor: 'rgba(59, 130, 246, 0.2)', color: 'rgb(59, 130, 246)' }}
                                        >FK</span>
                                      )}
                                    </td>
                                    <td className="px-4 py-2.5">
                                      <span className="text-xs px-2 py-1 font-semibold"
                                            style={{ borderRadius: '6px', backgroundColor: 'rgb(var(--theme-bg-secondary))', color: 'rgb(var(--theme-text-muted))' }}
                                      >{col.type}</span>
                                    </td>
                                    <td className="px-4 py-2.5" style={{ color: 'rgb(var(--theme-text-muted))' }}>{col.comment || '-'}</td>
                                  </tr>
                                ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}

                        {selectedDataCards[activeCardIndex].card_content?.KeyConcepts && (() => {
                          const KC = selectedDataCards[activeCardIndex].card_content.KeyConcepts as any
                          const hasTopic = KC.canonical_topic
                          const aliasList = Array.isArray(KC.alias) ? KC.alias : []
                          const keyEntities = Array.isArray(KC.key_entities) ? KC.key_entities : []
                          if (!hasTopic && aliasList.length === 0 && keyEntities.length === 0) return null
                          return (
                            <div
                              className="p-5"
                              style={{
                                borderRadius: '16px',
                                backgroundColor: 'rgba(var(--theme-bg-secondary), 0.5)',
                                border: '1px solid rgb(var(--theme-border))',
                              }}
                            >
                              <h4 className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'rgb(var(--theme-text))' }}>
                                <span style={{ width: '4px', height: '16px', backgroundColor: '#f59e0b', borderRadius: '2px' }}></span>
                                关键概念
                              </h4>
                              <div className="space-y-3">
                                {hasTopic && (
                                  <div>
                                    <span className="text-xs block mb-2" style={{ color: 'rgb(var(--theme-text-muted))' }}>主题</span>
                                    <span className="text-sm px-4 py-2 font-medium"
                                          style={{ borderRadius: '8px', backgroundColor: 'rgba(245, 158, 11, 0.15)', color: 'rgb(217, 119, 6)', display: 'inline-block' }}
                                    >{KC.canonical_topic}</span>
                                  </div>
                                )}
                                {aliasList.length > 0 && (
                                  <div>
                                    <span className="text-xs block mb-2" style={{ color: 'rgb(var(--theme-text-muted))' }}>别名</span>
                                    <div className="flex flex-wrap gap-2">
                                      {aliasList.map((a: string, idx: number) => (
                                        <span key={idx} className="text-sm px-3 py-1.5 font-medium"
                                              style={{ borderRadius: '6px', backgroundColor: 'rgba(3, 105, 161, 0.15)', color: 'rgb(59, 130, 246)', display: 'inline-block' }}
                                        >{a}</span>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {keyEntities.length > 0 && (
                                  <div>
                                    <span className="text-xs block mb-2" style={{ color: 'rgb(var(--theme-text-muted))' }}>关键实体</span>
                                    <div className="flex flex-wrap gap-2">
                                      {keyEntities.map((e: string, idx: number) => (
                                        <span key={idx} className="text-sm px-3 py-1.5 font-medium"
                                              style={{ borderRadius: '6px', backgroundColor: 'rgba(124, 58, 237, 0.15)', color: 'rgb(124, 58, 237)', display: 'inline-block' }}
                                        >{e}</span>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          )
                        })()}

                        {Array.isArray((selectedDataCards[activeCardIndex].card_content?.KeyConcepts as any)?.applicable_scenarios) && (selectedDataCards[activeCardIndex].card_content.KeyConcepts as any).applicable_scenarios.length > 0 && (
                          <div
                            className="p-5"
                            style={{
                              borderRadius: '16px',
                              backgroundColor: 'rgba(var(--theme-bg-secondary), 0.5)',
                              border: '1px solid rgb(var(--theme-border))',
                            }}
                          >
                            <h4 className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'rgb(var(--theme-text))' }}>
                              <span style={{ width: '4px', height: '16px', backgroundColor: '#06b6d4', borderRadius: '2px' }}></span>
                              适用场景
                            </h4>
                            <div className="flex flex-wrap gap-2">
                              {((selectedDataCards[activeCardIndex].card_content.KeyConcepts as any).applicable_scenarios as string[]).map((s: string, idx: number) => (
                                <span key={idx} className="text-sm px-4 py-2 font-medium"
                                      style={{ borderRadius: '8px', backgroundColor: 'rgba(6, 182, 212, 0.15)', color: 'rgb(6, 182, 212)' }}
                                >{s}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {Array.isArray(selectedDataCards[activeCardIndex].card_content?.Tags) && selectedDataCards[activeCardIndex].card_content.Tags.length > 0 && (
                          <div
                            className="p-5"
                            style={{
                              borderRadius: '16px',
                              backgroundColor: 'rgba(var(--theme-bg-secondary), 0.5)',
                              border: '1px solid rgb(var(--theme-border))',
                            }}
                          >
                            <h4 className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'rgb(var(--theme-text))' }}>
                              <span style={{ width: '4px', height: '16px', backgroundColor: '#ef4444', borderRadius: '2px' }}></span>
                              标签
                            </h4>
                            <div className="flex flex-wrap gap-2">
                              {selectedDataCards[activeCardIndex].card_content.Tags.map((tag: string, idx: number) => (
                                <span key={idx} className="text-sm px-4 py-2 font-medium"
                                      style={{ borderRadius: '8px', backgroundColor: 'rgba(239, 68, 68, 0.15)', color: 'rgb(239, 68, 68)' }}
                                >{tag}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {selectedDataCards[activeCardIndex].card_content?.SampleData && (
                          <div
                            className="p-5"
                            style={{
                              borderRadius: '16px',
                              backgroundColor: 'rgba(var(--theme-bg-secondary), 0.5)',
                              border: '1px solid rgb(var(--theme-border))',
                            }}
                          >
                            <h4 className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'rgb(var(--theme-text))' }}>
                              <span style={{ width: '4px', height: '16px', backgroundColor: '#6366f1', borderRadius: '2px' }}></span>
                              示例数据
                            </h4>
                            <div className="p-4 overflow-x-auto"
                                 style={{
                                   borderRadius: '12px',
                                   backgroundColor: '#0f172a',
                                 }}
                            >
                              <pre className="text-xs font-mono text-green-400 whitespace-pre-wrap">
                                {JSON.stringify(selectedDataCards[activeCardIndex].card_content.SampleData, null, 2)}
                              </pre>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'history' && (
            <div className="bg-white dark:bg-slate-800 rounded-[28px] border border-slate-200 dark:border-slate-700 overflow-hidden min-h-[400px] shadow-sm">
              {/* 历史查询 Tab 头部 */}
              <div
                className="workspace-tab-header"
                style={{
                  padding: '1.25rem',
                  borderBottom: '1px solid rgb(var(--theme-border))',
                  background: 'linear-gradient(135deg, rgba(var(--theme-bg-tertiary), 0.6) 0%, rgb(var(--theme-bg)) 50%, rgba(var(--theme-bg-tertiary), 0.4) 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div className="flex items-center gap-4">
                  <div style={{
                    width: '2.5rem',
                    height: '2.5rem',
                    borderRadius: '16px',
                    background: 'linear-gradient(135deg, rgb(6,182,212), rgb(37,99,235))',
                    color: '#fff',
                    boxShadow: '0 10px 15px -3px rgba(6,182,212,0.4)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                  >
                    <Clock className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">历史查询</h3>
                    <p className="text-sm text-slate-500">查看和管理历史查询记录及统计</p>
                  </div>
                </div>
              </div>

              {/* 历史查询内容区域 */}
              <div>
                <QueryHistoryPage
                  sourceDatasourceId={workspace?.id}
                  showStats={true}
                  showFilters={true}
                  showHeader={false}
                />
              </div>
            </div>
          )}

          {activeTab === 'jobs' && (
            <div className="bg-white dark:bg-slate-800 rounded-[28px] border border-slate-200 dark:border-slate-700 overflow-hidden min-h-[400px] shadow-sm">
              {/* 任务 Tab 头部 - 使用主题变量以适配深色模式 */}
              <div
                className="workspace-tab-header"
                style={{
                  padding: '1.25rem',
                  borderBottom: '1px solid rgb(var(--theme-border))',
                  background: 'linear-gradient(135deg, rgba(var(--theme-bg-tertiary), 0.6) 0%, rgb(var(--theme-bg)) 50%, rgba(var(--theme-bg-tertiary), 0.4) 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div className="flex items-center gap-4">
                  <div style={{
                    width: '2.5rem',
                    height: '2.5rem',
                    borderRadius: '16px',
                    background: 'linear-gradient(135deg, rgb(34,197,94), rgb(5,150,105))',
                    color: '#fff',
                    boxShadow: '0 10px 15px -3px rgba(34,197,94,0.4)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                  >
                    <BarChart3 className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">任务</h3>
                    <p className="text-sm text-slate-500">管理盘点任务与查看结果</p>
                  </div>
                </div>
              </div>

              {/* 子Tab切换：定向盘点 / 全域盘点 */}
              <div className="border-b border-slate-200 px-4">
                <div className="flex gap-1">
                  <button
                    onClick={() => setInventoryJobType('target')}
                    className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                      inventoryJobType === 'target'
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                    }`}
                  >
                    <Search className="w-4 h-4" />
                    定向盘点
                  </button>
                  <button
                    onClick={() => setInventoryJobType('global')}
                    className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                      inventoryJobType === 'global'
                        ? 'border-purple-500 text-purple-600'
                        : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                    }`}
                  >
                    <Aperture className="w-4 h-4" />
                    全域盘点
                  </button>
                </div>
              </div>

              <div className="min-h-[360px] p-4">
                {inventoryJobType === 'target' ? (
                  <TargetInventory defaultConnectName={workspace.connect_name} defaultDataSourceId={workspace.id}
                                   embedded key={`target-${workspace.id}`}
                  />
                ) : (
                  <div className="space-y-4">

                    {/* 统计卡片 + 操作按钮同一行（略增宽与字号） */}
                    <div className="flex flex-wrap items-center gap-2 mb-3">
                      <div className="flex flex-1 min-w-0 flex-wrap items-stretch gap-2">
                        <div
                          className="flex items-center gap-2.5 shrink-0 min-w-[118px]"
                          style={{
                            borderRadius: '10px',
                            padding: '8px 14px',
                            background: isDark ? 'rgba(168, 85, 247, 0.15)' : 'linear-gradient(135deg, rgba(168, 85, 247, 0.08) 0%, rgba(236, 72, 153, 0.08) 100%)',
                            border: `1px solid ${isDark ? 'rgba(168, 85, 247, 0.3)' : 'rgba(168, 85, 247, 0.2)'}`,
                          }}
                        >
                          <div
                            className="flex items-center justify-center shrink-0"
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius: '8px',
                              background: isDark ? 'linear-gradient(135deg, #9333ea 0%, #db2777 100%)' : 'linear-gradient(135deg, #9333ea 0%, #db2777 100%)',
                            }}
                          >
                            <Aperture className="w-4 h-4 text-white" />
                          </div>
                          <div className="min-w-0">
                            <p className="text-xs leading-none mb-0.5" style={{ color: isDark ? '#94a3b8' : '#64748b' }}>关系卡片</p>
                            <p className="text-lg font-bold leading-tight tabular-nums"
                            style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}
                            >{relationshipCards.length}</p>
                          </div>
                        </div>
                        <div
                          className="flex items-center gap-2.5 shrink-0 min-w-[118px]"
                          style={{
                            borderRadius: '10px',
                            padding: '8px 14px',
                            background: isDark ? 'rgba(59, 130, 246, 0.15)' : 'linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(6, 182, 212, 0.08) 100%)',
                            border: `1px solid ${isDark ? 'rgba(59, 130, 246, 0.3)' : 'rgba(59, 130, 246, 0.2)'}`,
                          }}
                        >
                          <div
                            className="flex items-center justify-center shrink-0"
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius: '8px',
                              background: isDark ? 'linear-gradient(135deg, #2563eb 0%, #0891b2 100%)' : 'linear-gradient(135deg, #2563eb 0%, #0891b2 100%)',
                            }}
                          >
                            <Link2 className="w-4 h-4 text-white" />
                          </div>
                          <div className="min-w-0">
                            <p className="text-xs leading-none mb-0.5" style={{ color: isDark ? '#94a3b8' : '#64748b' }}>表关系</p>
                            <p className="text-lg font-bold leading-tight tabular-nums"
                            style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}
                            >{tableRelationships.length}</p>
                          </div>
                        </div>
                        <div
                          className="flex items-center gap-2.5 shrink-0 min-w-[118px]"
                          style={{
                            borderRadius: '10px',
                            padding: '8px 14px',
                            background: isDark ? 'rgba(34, 197, 94, 0.15)' : 'linear-gradient(135deg, rgba(34, 197, 94, 0.08) 0%, rgba(16, 185, 129, 0.08) 100%)',
                            border: `1px solid ${isDark ? 'rgba(34, 197, 94, 0.3)' : 'rgba(34, 197, 94, 0.2)'}`,
                          }}
                        >
                          <div
                            className="flex items-center justify-center shrink-0"
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius: '8px',
                              background: isDark ? 'linear-gradient(135deg, #16a34a 0%, #059669 100%)' : 'linear-gradient(135deg, #16a34a 0%, #059669 100%)',
                            }}
                          >
                            <Layers className="w-4 h-4 text-white" />
                          </div>
                          <div className="min-w-0">
                            <p className="text-xs leading-none mb-0.5" style={{ color: isDark ? '#94a3b8' : '#64748b' }}>图谱节点</p>
                            <p className="text-lg font-bold leading-tight tabular-nums"
                            style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}
                            >{graphData.nodes.length}</p>
                          </div>
                        </div>
                        <div
                          className="flex items-center gap-2.5 shrink-0 min-w-[118px]"
                          style={{
                            borderRadius: '10px',
                            padding: '8px 14px',
                            background: isDark ? 'rgba(249, 115, 22, 0.15)' : 'linear-gradient(135deg, rgba(249, 115, 22, 0.08) 0%, rgba(245, 158, 11, 0.08) 100%)',
                            border: `1px solid ${isDark ? 'rgba(249, 115, 22, 0.3)' : 'rgba(249, 115, 22, 0.2)'}`,
                          }}
                        >
                          <div
                            className="flex items-center justify-center shrink-0"
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius: '8px',
                              background: isDark ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)' : 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)',
                            }}
                          >
                            <Key className="w-4 h-4 text-white" />
                          </div>
                          <div className="min-w-0">
                            <p className="text-xs leading-none mb-0.5" style={{ color: isDark ? '#94a3b8' : '#64748b' }}>图谱边</p>
                            <p className="text-lg font-bold leading-tight tabular-nums"
                            style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}
                            >{graphData.edges.length}</p>
                          </div>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2 ml-auto">
                        <button
                          type="button"
                          onClick={() => workspace?.id && loadGlobalInventoryResult(workspace.id)}
                          disabled={loadingGlobalResult}
                          className="flex items-center gap-2 px-3 py-1.5 text-sm border border-slate-300 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors disabled:opacity-50"
                          style={{ borderRadius: '10px' }}
                        >
                          <RefreshCw className={`w-4 h-4 ${loadingGlobalResult ? 'animate-spin' : ''}`} />
                          刷新
                        </button>
                        <button
                          type="button"
                          onClick={() => setShowGlobalInventoryModal(true)}
                          className="flex items-center gap-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white px-3 py-1.5 text-sm font-medium hover:from-purple-700 hover:to-pink-700 transition-all shadow-sm whitespace-nowrap"
                          style={{ borderRadius: '10px' }}
                        >
                          <Search className="w-4 h-4" />
                          重新执行全域盘点
                        </button>
                      </div>
                    </div>

                    {/* 曾与哪些数据源做过跨源关系发现（与 GlobalInventory 一致） */}
                    {globalInventoryRelatedDatasources.length > 0 && (
                      <div className="mb-3 p-3 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700" style={{ borderRadius: '10px' }}>
                        <div className="flex items-start gap-2">
                          <div
                            className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300 text-xs font-medium whitespace-nowrap shrink-0"
                          >
                            <Link2 className="w-3.5 h-3.5" />
                            <span>曾与以下数据源进行过跨源关系发现：</span>
                          </div>
                          <div className="flex flex-wrap gap-1.5 flex-1 min-w-0">
                            {globalInventoryRelatedDatasources.map((ds) => (
                              <span
                                key={ds.id}
                                className="inline-flex items-center gap-1 rounded-md border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/30 px-2 py-0.5 text-xs font-medium text-blue-700 dark:text-blue-400"
                              >
                              <Database className="w-3 h-3 shrink-0" />
                                {ds.name}
                            </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* 结果：三 Tab（关系图谱 / 关系卡片 / 关系列表），与 /global-inventory 查看关系数据一致 */}
                    {loadingGlobalResult ? (
                      <div className="flex items-center justify-center py-12">
                        <RefreshCw className="animate-spin text-purple-600 text-xl" />
                        <span className="ml-2 text-slate-500">加载中...</span>
                      </div>
                    ) : relationshipCards.length === 0 && tableRelationships.length === 0 ? (
                      <div className="flex flex-col items-center justify-center py-12 text-center">
                        <div
                          className="w-16 h-16 bg-gradient-to-br from-purple-100 to-pink-100 flex items-center justify-center mb-4"
                          style={{ borderRadius: '16px' }}
                        >
                          <Aperture className="w-8 h-8 text-purple-500" />
                        </div>
                        <h4 className="text-base font-medium text-slate-700 mb-1">暂无全域盘点结果</h4>
                        <p className="text-sm text-slate-500 mb-4">执行全域盘点以发现表关系</p>
                        <button
                          onClick={() => setShowGlobalInventoryModal(true)}
                          className="flex items-center gap-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white px-4 py-2 text-sm font-medium hover:from-purple-700 hover:to-pink-700 transition-all"
                          style={{ borderRadius: '12px' }}
                        >
                          <Search className="w-4 h-4" />
                          执行全域盘点
                        </button>
                      </div>
                    ) : workspace?.id ? (
                      <WorkspaceGlobalInventoryTabs
                        datasourceId={workspace.id}
                        datasourceName={workspace.connect_name ?? ''}
                        datasourceNameMap={workspaceRelationshipGraphDatasourceNameMap}
                        relationshipCards={relationshipCards}
                        tableRelationships={tableRelationships}
                        graphData={graphData}
                        loading={loadingGlobalResult}
                        onRefresh={() => workspace?.id && loadGlobalInventoryResult(workspace.id)}
                      />
                    ) : null}
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'knowledge' && workspace && (
            <KnowledgeTab
              workspaceId={workspace.id}
              workspaceName={workspace.connect_name || ''}
            />
          )}
        </div>

        {selectedCard && (
          <DataCardDetailModal
            card={selectedCard.card}
            datasource={selectedCard.datasource}
            onClose={() => setSelectedCard(null)}
            loadWorkspace={loadWorkspace}
            onDataSourcesRefresh={refreshDataSources}
            onSaveSuccess={(updatedCard) => {
              // 更新 allCards 中的对应卡片数据
              setAllCards(prevCards =>
                prevCards.map(c =>
                  c.doc_id === updatedCard.doc_id ? updatedCard : c
                )
              )
            }}
          />
        )}

        {selectedSchema && (
          <SchemaDetailModal
            schema={selectedSchema}
            onClose={() => setSelectedSchema(null)}
          />
        )}

        {/* 设置弹窗：Portal 到 body 避免顶部白边 */}
        {showSettings && workspace && typeof document !== 'undefined' && createPortal(
          <div
            className="fixed inset-0 backdrop-blur-sm flex items-center justify-center p-4"
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              zIndex: 9999,
              backgroundColor: 'rgba(0, 0, 0, 0.5)',
            }}
          >
            <div className="bg-white dark:bg-slate-800 w-full max-w-lg shadow-2xl overflow-hidden" style={{ borderRadius: '16px' }}>
              {/* 头部 */}
              <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-700 flex items-center gap-3"
                   style={{ borderRadius: '16px 16px 0 0' }}
              >
                <div
                  className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center"
                  style={{ borderRadius: '12px' }}
                >
                  <span className="text-xl">{getDbTypeIcon(workspace.db_type)}</span>
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-bold text-slate-800 dark:text-slate-100">{workspace.connect_name}</h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400"
                  >{workspace.db_type?.toUpperCase()}{workspace.database_name ? ` / ${workspace.database_name}` : ''}</p>
                </div>
                <button
                  onClick={() => {
                    setShowSettings(false)
                    setEditingName(false)
                  }}
                  className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                  style={{ borderRadius: '12px' }}
                >
                  <X className="w-5 h-5 text-slate-400 dark:text-slate-500" />
                </button>
              </div>

              <div className="p-6">
                {/* 连接名称编辑 */}
                {editingName ? (
                  <div className="flex gap-2 mb-4">
                    <input
                      type="text"
                      value={connectName}
                      onChange={(e) => setConnectName(e.target.value)}
                      className="flex-1 px-3 py-2 bg-slate-50 dark:bg-slate-700 border-0 text-base focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700 dark:text-slate-200"
                      placeholder="请输入连接名称"
                      style={{ borderRadius: '12px' }}
                    />
                    <button
                      onClick={async () => {
                        if (!connectName.trim()) return
                        setSavingName(true)
                        const res = await updateDataSourceName(workspace.id, connectName.trim())
                        if (res.code === 200) {
                          const newName = connectName.trim()

                          // 1. 立即更新本地状态，确保 UI 立即显示最新数据
                          setWorkspace(prev => prev ? {
                            ...prev,
                            connect_name: newName,
                          } : null)

                          // 2. 手动清除 sessionStorage 缓存并获取最新数据
                          if (typeof window !== 'undefined') {
                            window.sessionStorage.removeItem('globalDataSourceCache')
                            window.sessionStorage.removeItem(GLOBAL_DATA_SOURCE_CACHE_KEY)
                          }

                          // 3. 直接调用 API 获取最新数据，确保显示最新值
                          try {
                            const listRes = await getUserDataSources({
                              page: 1,
                              page_size: 100,
                            })
                            if (listRes.code === 200 && listRes.data?.items) {
                              const found = listRes.data.items.find((w: any) => w.id === workspace.id)
                              if (found) {
                                setWorkspace(found)
                              }
                            }
                          } catch (e) {
                            console.error('刷新数据失败', e)
                          }

                          // 4. 通知其他组件刷新数据源列表
                          refreshDataSources()

                          setEditingName(false)
                          message.success('保存成功')
                        }
                        setSavingName(false)
                      }}
                      disabled={savingName || !connectName.trim()}
                      className="px-4 py-2 bg-indigo-500 text-white text-sm font-medium hover:bg-indigo-600 transition-colors disabled:opacity-50"
                      style={{ borderRadius: '12px' }}
                    >
                      {savingName ? '保存中' : '保存'}
                    </button>
                    <button
                      onClick={() => {
                        setEditingName(false)
                        setConnectName(workspace.connect_name)
                      }}
                      className="px-4 py-2 bg-slate-100 text-slate-600 text-sm font-medium hover:bg-slate-200 transition-colors"
                      style={{ borderRadius: '12px' }}
                    >
                      取消
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center justify-between mb-4 p-3 bg-slate-50 dark:bg-slate-700"
                       style={{ borderRadius: '12px' }}
                  >
                    <span className="text-sm text-slate-600 dark:text-slate-300">连接名称</span>
                    <button
                      onClick={() => {
                        setConnectName(workspace.connect_name)
                        setEditingName(true)
                      }}
                      className="text-sm text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 font-medium"
                    >
                      {workspace.connect_name} ✏️
                    </button>
                  </div>
                )}

                {/* 创建时间 */}
                <div className="mb-4">
                <span className="text-xs text-slate-400 dark:text-slate-500"
                >创建于 {workspace.created_at ? new Date(workspace.created_at).toLocaleString('zh-CN', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                }) : '-'}</span>
                </div>

                {/* 连接信息 */}
                <div className="p-4 border border-slate-200 dark:border-slate-700" style={{ borderRadius: '12px' }}>
                  <div className="space-y-3">
                    {(() => {
                      const parsed = parseConnectInfo(workspace.connect_info)
                      if (!parsed) {
                        return (
                          <div className="text-center py-4 text-sm text-slate-500 dark:text-slate-400">
                            <p>无法解析连接信息</p>
                            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1 font-mono break-all">{workspace.connect_info}</p>
                          </div>
                        )
                      }

                      return (
                        <>
                          <div className="flex justify-between items-center py-2 border-b border-slate-100 dark:border-slate-700">
                            <span className="text-sm text-slate-500 dark:text-slate-400">用户名</span>
                            <span className="text-sm text-slate-700 dark:text-slate-200 font-mono">{parsed.username}</span>
                          </div>
                          <div className="flex justify-between items-center py-2 border-b border-slate-100 dark:border-slate-700">
                            <span className="text-sm text-slate-500 dark:text-slate-400">密码</span>
                            <span className="text-sm text-slate-700 dark:text-slate-200 font-mono">{maskPassword(parsed.password)}</span>
                          </div>
                          <div className="flex justify-between items-center py-2 border-b border-slate-100 dark:border-slate-700">
                            <span className="text-sm text-slate-500 dark:text-slate-400">IP 地址</span>
                            <span className="text-sm text-slate-700 dark:text-slate-200 font-mono">{parsed.host}</span>
                          </div>
                          <div className="flex justify-between items-center py-2 border-b border-slate-100 dark:border-slate-700">
                            <span className="text-sm text-slate-500 dark:text-slate-400">端口</span>
                            <span className="text-sm text-slate-700 dark:text-slate-200 font-mono">{parsed.port}</span>
                          </div>
                          {parsed.database && (
                            <div className="flex justify-between items-center py-2 border-b border-slate-100 dark:border-slate-700">
                              <span className="text-sm text-slate-500 dark:text-slate-400">数据库</span>
                              <span className="text-sm text-slate-700 dark:text-slate-200 font-mono">{parsed.database}</span>
                            </div>
                          )}
                          {parsed.serviceName && (
                            <div className="flex justify-between items-center py-2 border-b border-slate-100 dark:border-slate-700">
                              <span className="text-sm text-slate-500 dark:text-slate-400">Service</span>
                              <span className="text-sm text-slate-700 dark:text-slate-200 font-mono">{parsed.serviceName}</span>
                            </div>
                          )}
                          {workspace.schema_name && (
                            <div className="flex justify-between items-center py-2">
                              <span className="text-sm text-slate-500 dark:text-slate-400">Schema</span>
                              <span className="text-sm text-slate-700 dark:text-slate-200 font-mono">{workspace.schema_name}</span>
                            </div>
                          )}
                        </>
                      )
                    })()}
                  </div>
                </div>
              </div>
            </div>
          </div>,
          document.body,
        )}

        {/* 盘点类型选择弹框 */}
        {workspace && (
          <InventoryTypeModal
            visible={showInventoryTypeModal}
            onClose={() => setShowInventoryTypeModal(false)}
            onSelectType={handleSelectInventoryType}
            currentDataSourceName={workspace.connect_name}
          />
        )}

        {/* 定向盘点配置弹框 */}
        {workspace && (
          <TargetInventoryModal
            visible={showTargetInventoryModal}
            onClose={() => setShowTargetInventoryModal(false)}
            onBack={() => {
              setShowTargetInventoryModal(false)
              setShowInventoryTypeModal(true)
            }}
            dataSourceId={workspace.id}
            dataSourceName={workspace.connect_name}
            onExecuteSuccess={handleTargetInventorySuccess}
          />
        )}

        {/* 全域盘点配置弹框 */}
        {workspace && (
          <GlobalInventoryModal
            visible={showGlobalInventoryModal}
            onClose={() => setShowGlobalInventoryModal(false)}
            onBack={() => {
              setShowGlobalInventoryModal(false)
              setShowInventoryTypeModal(true)
            }}
            defaultDataSourceId={workspace.id}
            defaultDataSourceName={workspace.connect_name}
            onExecuteSuccess={handleGlobalInventorySuccess}
          />
        )}

        {/* 术语库管理已移至 KnowledgeTab 组件 */}
      </div>
    </>
  )
}

export default WorkspaceDetailPage
