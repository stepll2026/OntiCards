'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next-nprogress-bar'
import {
  Shield,
  Library,
  FileText,
  PlayCircle,
  Plus,
  ChevronRight,
  TrendingUp,
  CheckCircle,
  BarChart3,
  Database,
  Loader2,
  Sparkles,
  RefreshCw,
  AlertTriangle,
  Clock,
  Activity,
  Target,
  PieChart,
} from 'lucide-react'
import { message } from 'antd'
import {
  getGovernanceLibraries,
  getGovernanceReports,
  getQualityOverview,
  GovernanceLibrary,
  GovernanceReport,
  QualityOverview,
  getGradeName,
  getGradeColor,
} from '@/api/governance'
import { CreateLibraryModal } from './CreateLibraryModal'

const dimensionLabels: Record<string, string> = {
  completeness: '完整性',
  uniqueness: '唯一性',
  validity: '有效性',
  consistency: '一致性',
  timeliness: '时效性',
  accuracy: '准确性',
  composite: '复合规则',
}

const dimensionColors: Record<string, string> = {
  completeness: '#1890ff',
  uniqueness: '#722ed1',
  validity: '#fa8c16',
  consistency: '#52c41a',
  timeliness: '#f5222d',
  accuracy: '#faad14',
  composite: '#13c2c2',
}

const ruleTypeColors: Record<string, string> = {
  null_check: '#1890ff',
  unique: '#722ed1',
  format: '#fa8c16',
  threshold: '#52c41a',
  enum: '#f5222d',
  custom_sql: '#faad14',
  composite: '#13c2c2',
  consistency_check: '#2f54eb',
  multi_column_compare: '#722ed1',
}

// 规则类型分布标签组件
const RuleTypeTag = ({ type, count, percentage, color }: { type: string; count: number; percentage?: number; color: string }) => (
  <div
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 8,
      padding: '6px 12px',
      borderRadius: 8,
      backgroundColor: `${color}12`,
      border: `1px solid ${color}30`,
    }}
  >
    <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: color }} />
    <span style={{ fontSize: 12, fontWeight: 500, color: 'rgb(var(--theme-text))' }}>{type}</span>
    <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>{count}</span>
    {typeof percentage === 'number' && (
      <span style={{ fontSize: 11, color: 'rgb(var(--theme-text-muted))' }}>({percentage.toFixed(1)}%)</span>
    )}
  </div>
)

// 质量维度进度条组件
const DimensionProgressBar = ({
  label,
  value,
  color
}: {
  label: string
  value: number
  color: string
}) => (
  <div style={{ marginBottom: 12 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
      <span style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))' }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: 600, color }}>{value.toFixed(1)}</span>
    </div>
    <div style={{
      height: 6,
      borderRadius: 3,
      backgroundColor: 'rgb(var(--theme-bg-secondary))',
      overflow: 'hidden',
    }}>
      <div style={{
        width: `${Math.min(value, 100)}%`,
        height: '100%',
        borderRadius: 3,
        background: `linear-gradient(90deg, ${color}, ${color}cc)`,
        transition: 'width 0.5s ease',
      }} />
    </div>
  </div>
)

// 评分趋势组件
const ScoreTrendChart = ({ data }: { data: QualityOverview['report_trend'] }) => {
  if (!data || data.length === 0) return null

  const maxScore = Math.max(...data.map(d => d.avg_score || 0))
  const minScore = Math.min(...data.map(d => d.avg_score || 0))

  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))', marginBottom: 8 }}>
        评分趋势
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 60 }}>
        {data.slice(-7).map((item, index) => {
          const height = maxScore > 0 ? ((item.avg_score || 0) / maxScore) * 50 : 0
          const isLast = index === data.slice(-7).length - 1
          return (
            <div key={index} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
              <div style={{
                width: '100%',
                height: height + 10,
                borderRadius: '4px 4px 0 0',
                backgroundColor: isLast ? 'rgb(var(--theme-primary))' : 'rgba(var(--theme-primary), 0.3)',
                transition: 'all 0.3s ease',
              }} />
              <span style={{ fontSize: 10, color: 'rgb(var(--theme-text-muted))' }}>
                {item.date?.slice(5) || ''}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// 关键发现条目组件
const CriticalFindingItem = ({
  finding,
  onClick
}: {
  finding: NonNullable<QualityOverview['critical_findings']>[0]
  onClick: () => void
}) => {
  const severityConfig = {
    critical: { color: '#f5222d', bg: 'rgba(245, 34, 45, 0.08)', label: '严重' },
    warning: { color: '#fa8c16', bg: 'rgba(250, 140, 22, 0.08)', label: '警告' },
    info: { color: '#1890ff', bg: 'rgba(24, 144, 255, 0.08)', label: '信息' },
  }
  const config = severityConfig[finding.severity as keyof typeof severityConfig] || severityConfig.info

  // 区分表和列的显示
  const columnNames = finding.column_name ? finding.column_name.split(',').map(c => c.trim()) : []

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 10,
        padding: 10,
        borderRadius: 10,
        backgroundColor: 'rgb(var(--theme-bg-secondary))',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
      }}
    >
      <div style={{
        padding: '3px 6px',
        borderRadius: 4,
        fontSize: 10,
        fontWeight: 600,
        backgroundColor: config.bg,
        color: config.color,
      }}>
        {config.label}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 13,
          fontWeight: 500,
          color: 'rgb(var(--theme-text))',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          {finding.rule_name}
        </div>
        <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-muted))', marginTop: 4, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ color: 'rgb(var(--theme-text-secondary))' }}>
            <Database style={{ width: 10, height: 10, display: 'inline', verticalAlign: 'middle' }} />
            {' '}{finding.table_name}
          </span>
          {columnNames.length > 0 && (
            <span style={{ color: 'rgb(var(--theme-text-secondary))' }}>
              <Library style={{ width: 10, height: 10, display: 'inline', verticalAlign: 'middle' }} />
              {' '}{columnNames.join(', ')}
            </span>
          )}
          <span style={{ color: '#f5222d' }}>
            失败 {finding.failed_count} 条 ({finding.failed_rate?.toFixed(1)}%)
          </span>
        </div>
      </div>
    </div>
  )
}

// 统计卡片组件（恢复原始样式）
const AnimatedStatCard = ({
  icon,
  value,
  label,
  color,
}: {
  icon: React.ReactNode
  value: number | string
  label: string
  color: string
}) => (
  <div
    style={{
      position: 'relative',
      overflow: 'hidden',
      padding: 16,
      borderRadius: 16,
      border: '1px solid rgb(var(--theme-border))',
      backgroundColor: 'rgb(var(--theme-bg))',
      boxShadow: '0 10px 30px rgba(15, 23, 42, 0.04)',
    }}
  >
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
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, position: 'relative', zIndex: 1 }}>
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: 14,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: `linear-gradient(135deg, ${color}18, ${color}08)`,
        }}
      >
        <div style={{ color }}>{icon}</div>
      </div>
      <div>
        <p
          style={{
            fontSize: 24,
            fontWeight: 700,
            color: 'rgb(var(--theme-text))',
            lineHeight: 1,
          }}
        >
          {value}
        </p>
        <p style={{ fontSize: 13, marginTop: 4, color: 'rgb(var(--theme-text-muted))' }}>{label}</p>
      </div>
    </div>
  </div>
)

// 规则库卡片
const LibraryCard = ({
  library,
  onClick,
}: {
  library: GovernanceLibrary
  onClick: () => void
}) => (
  <div
    onClick={onClick}
    style={{
      padding: 14,
      borderRadius: 14,
      border: '1px solid rgb(var(--theme-border))',
      backgroundColor: 'rgb(var(--theme-bg))',
      cursor: 'pointer',
      transition: 'all 0.2s ease',
      boxShadow: '0 4px 12px rgba(15, 23, 42, 0.03)',
    }}
  >
    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <h3
            style={{
              fontWeight: 600,
              fontSize: 14,
              color: 'rgb(var(--theme-text))',
              margin: 0,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {library.name}
          </h3>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '2px 6px',
              borderRadius: 4,
              fontSize: 10,
              fontWeight: 500,
              backgroundColor: 'rgba(var(--theme-primary), 0.1)',
              color: 'rgb(var(--theme-primary))',
            }}
          >
            {library.rule_count || 0} 规则
          </span>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 3,
              padding: '2px 6px',
              borderRadius: 4,
              fontSize: 10,
              backgroundColor: library.status === 'active' ? 'rgba(82, 196, 26, 0.1)' : 'rgba(var(--theme-bg-secondary), 0.8)',
              color: library.status === 'active' ? '#52c41a' : 'rgb(var(--theme-text-muted))',
            }}
          >
            {library.status === 'active' ? '●' : '○'}
            {library.status === 'active' ? '启用' : '停用'}
          </span>
        </div>
        {(library.connect_name || library.database_name || library.datasource_db_type || library.datasource?.connect_name || library.datasource?.database_name || library.datasource?.db_type) && (
          <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {(library.connect_name || library.datasource?.connect_name) && (
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '1px 6px',
                borderRadius: 4,
                fontSize: 11,
                backgroundColor: 'rgba(24, 144, 255, 0.08)',
                color: '#1677ff',
              }}>
                <Database style={{ width: 9, height: 9, marginRight: 3 }} />
                {library.connect_name || library.datasource?.connect_name}
              </span>
            )}
            {(library.database_name || library.datasource?.database_name) && (
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '1px 6px',
                borderRadius: 4,
                fontSize: 11,
                backgroundColor: 'rgba(82, 196, 26, 0.08)',
                color: '#389e0d',
              }}>
                {library.database_name || library.datasource?.database_name}
              </span>
            )}
            {(library.datasource_db_type || library.datasource?.db_type) && (
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '1px 6px',
                borderRadius: 4,
                fontSize: 11,
                backgroundColor: 'rgba(250, 173, 20, 0.1)',
                color: '#d48806',
                textTransform: 'uppercase',
              }}>
                {library.datasource_db_type || library.datasource?.db_type}
              </span>
            )}
          </div>
        )}
        {library.description && library.description !== library.name && (
          <p
            style={{
              fontSize: 11,
              marginTop: 4,
              color: 'rgb(var(--theme-text-muted))',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {library.description}
          </p>
        )}
      </div>
      <ChevronRight style={{ width: 14, height: 14, color: 'rgb(var(--theme-text-muted))', flexShrink: 0, marginTop: 2 }} />
    </div>
  </div>
)

// 报告卡片
const ReportCard = ({
  report,
  onClick,
  compact = false,
}: {
  report: GovernanceReport
  onClick: () => void
  compact?: boolean
}) => {
  const gradeColor = getGradeColor(getGradeName(report.quality_score))

  return (
    <div
      onClick={onClick}
      style={{
        padding: 14,
        borderRadius: 12,
        border: '1px solid rgb(var(--theme-border))',
        backgroundColor: 'rgb(var(--theme-bg))',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        boxShadow: '0 2px 8px rgba(15, 23, 42, 0.03)',
        height: '100%',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* 头部：得分 + 评级标签 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <div
              style={{
                padding: '2px 8px',
                borderRadius: 5,
                fontSize: 12,
                fontWeight: 700,
                color: 'white',
                backgroundColor: gradeColor,
                minWidth: 36,
                textAlign: 'center',
              }}
            >
              {report.quality_score?.toFixed(1) || '-'}
            </div>
            <span
              style={{
                padding: '2px 6px',
                borderRadius: 4,
                fontSize: 11,
                fontWeight: 500,
                backgroundColor: `${gradeColor}15`,
                color: gradeColor,
              }}
            >
              {getGradeName(report.quality_score)}
            </span>
          </div>

          {/* 文件名称 */}
          <h3
            style={{
              fontWeight: 600,
              fontSize: 14,
              color: 'rgb(var(--theme-text))',
              margin: 0,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {report.report_name}
          </h3>

          {/* 报告类型标签 */}
          <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
            {report.include_basic_audit && (
              <span style={{ fontSize: 10, color: '#faad14', padding: '2px 6px', backgroundColor: 'rgba(250,173,20,0.1)', borderRadius: 4 }}>基础审计</span>
            )}
            {report.include_quality && (
              <span style={{ fontSize: 10, color: '#52c41a', padding: '2px 6px', backgroundColor: 'rgba(82,196,26,0.1)', borderRadius: 4 }}>规则库质检</span>
            )}
            {report.include_relationship && (
              <span style={{ fontSize: 10, color: '#1890ff', padding: '2px 6px', backgroundColor: 'rgba(24,144,255,0.1)', borderRadius: 4 }}>关系发现</span>
            )}
          </div>

          {/* 数据源信息 */}
          <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <Database style={{ width: 11, height: 11, color: 'rgb(var(--theme-text-secondary))' }} />
            <span style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))' }}>
              {report.datasource_name && <span>{report.datasource_name}</span>}
              {report.datasource_name && report.database_name && <span style={{ margin: '0 4px', opacity: 0.5 }}>/</span>}
              {report.database_name && <span>{report.database_name}</span>}
              {report.schema_name && (
                <>
                  <span style={{ margin: '0 4px', opacity: 0.5 }}>/</span>
                  <span>{report.schema_name}</span>
                </>
              )}
            </span>
          </div>

          {/* 底部：时间 + 表数量 + 规则数 */}
          <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: 'rgb(var(--theme-text-muted))', flexWrap: 'wrap' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <Clock style={{ width: 11, height: 11 }} />
              {new Date(report.execution_time).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}
            </span>
            {report.scope_tables && report.scope_tables.length > 0 && (
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <Database style={{ width: 11, height: 11 }} />
                {report.scope_tables.length} 表
              </span>
            )}
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <CheckCircle style={{ width: 11, height: 11 }} />
              {report.rules_applied} 规则
            </span>
          </div>
        </div>
        <ChevronRight style={{ width: 14, height: 14, color: 'rgb(var(--theme-text-muted))', flexShrink: 0, marginTop: 4 }} />
      </div>
    </div>
  )
}

// 增强版空状态卡片
const EnhancedEmptyStateCard = ({
  icon,
  title,
  description,
  buttonText,
  onButtonClick,
  actionType,
}: {
  icon: React.ReactNode
  title: string
  description: string
  buttonText?: string
  onButtonClick?: () => void
  actionType?: 'create' | 'execute' | 'view'
}) => {
  const actionConfig = {
    create: { color: 'rgb(var(--theme-primary))', bg: 'rgba(var(--theme-primary), 0.1)' },
    execute: { color: '#52c41a', bg: 'rgba(82, 196, 26, 0.1)' },
    view: { color: '#faad14', bg: 'rgba(250, 173, 20, 0.1)' },
  }
  const config = actionType ? actionConfig[actionType] : actionConfig.view

  return (
    <div
      style={{
        textAlign: 'center',
        padding: 32,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 200,
      }}
    >
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: 16,
          backgroundColor: 'rgb(var(--theme-bg-secondary))',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 16,
        }}
      >
        <div style={{ color: 'rgb(var(--theme-text-muted))', opacity: 0.5 }}>
          {React.cloneElement(icon as React.ReactElement, { style: { width: 28, height: 28 } })}
        </div>
      </div>
      <p style={{ fontSize: 14, fontWeight: 600, color: 'rgb(var(--theme-text))', margin: 0 }}>{title}</p>
      <p style={{ fontSize: 12, marginTop: 6, color: 'rgb(var(--theme-text-secondary))', maxWidth: 280, lineHeight: 1.6 }}>
        {description}
      </p>
      {buttonText && onButtonClick && (
        <button
          onClick={onButtonClick}
          style={{
            marginTop: 16,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '8px 14px',
            borderRadius: 10,
            fontSize: 13,
            fontWeight: 500,
            color: config.color,
            backgroundColor: config.bg,
            border: 'none',
            cursor: 'pointer',
          }}
        >
          <Plus style={{ width: 13, height: 13 }} />
          {buttonText}
        </button>
      )}
    </div>
  )
}

export default function GovernancePage({ params }: { params: { lng: string } }) {
  const { lng } = params
  const router = useRouter()

  const [libraries, setLibraries] = useState<GovernanceLibrary[]>([])
  const [reports, setReports] = useState<GovernanceReport[]>([])
  const [overview, setOverview] = useState<QualityOverview | null>(null)
  const [librariesLoading, setLibrariesLoading] = useState(true)
  const [reportsLoading, setReportsLoading] = useState(true)
  const [overviewLoading, setOverviewLoading] = useState(true)
  const [libraryModalVisible, setLibraryModalVisible] = useState(false)
  const [pendingLibraryId, setPendingLibraryId] = useState<string | null>(null)

  const [stats, setStats] = useState({
    libraryCount: 0,
    ruleCount: 0,
    reportCount: 0,
    avgScore: 0,
  })

  useEffect(() => {
    fetchData()
  }, [])

  // 创建规则库成功后，跳转到规则库详情页面
  useEffect(() => {
    if (pendingLibraryId) {
      const targetId = pendingLibraryId
      setPendingLibraryId(null)
      router.push(`/${lng}/governance/libraries?id=${targetId}`)
    }
  }, [pendingLibraryId, router, lng])

  const fetchData = async () => {
    setLibrariesLoading(true)
    setReportsLoading(true)
    setOverviewLoading(true)
    try {
      // 并行请求：移除冗余的 rules 接口调用
      const [libRes, repRes, overviewRes] = await Promise.all([
        getGovernanceLibraries({ page_size: 100 }),
        getGovernanceReports({ page_size: 5 }),
        getQualityOverview(),
      ])

      if (libRes.code === 200) setLibraries(libRes.data.items)
      if (repRes.code === 200) setReports(repRes.data.items)
      if (overviewRes.code === 200) setOverview(overviewRes.data)

      const libData = libRes.code === 200 ? libRes.data : { items: [], total: 0 }
      const repData = repRes.code === 200 ? repRes.data : { items: [], total: 0 }
      const overviewData = overviewRes.code === 200 ? overviewRes.data : null

      // 计算平均分
      const scores = repData.items
        .filter((r: GovernanceReport) => r.quality_score !== undefined)
        .map((r: GovernanceReport) => r.quality_score as number)
      const avgScore = scores.length > 0 ? scores.reduce((a: number, b: number) => a + b, 0) / scores.length : 0

      setStats({
        libraryCount: overviewData?.library_count ?? libData.total,
        ruleCount: overviewData?.rule_count ?? 0,
        reportCount: overviewData?.report_count ?? repData.total,
        avgScore: overviewData?.quality_score ?? avgScore,
      })
    } catch (error) {
      console.error('获取质检数据失败:', error)
      message.error('获取质检总览失败')
    } finally {
      setLibrariesLoading(false)
      setReportsLoading(false)
      setOverviewLoading(false)
    }
  }

  const fetchLibrariesOnly = async () => {
    setLibrariesLoading(true)
    try {
      const libRes = await getGovernanceLibraries({ page_size: 100 })
      if (libRes.code === 200) {
        setLibraries(libRes.data.items)
        setStats(prev => ({ ...prev, libraryCount: libRes.data.total }))
      }
    } catch (error) {
      message.error('获取规则库失败')
    } finally {
      setLibrariesLoading(false)
    }
  }

  const openLibraryCreateModal = () => {
    setPendingLibraryId(null)
    setLibraryModalVisible(true)
  }

  const handleLibraryCreateSuccess = (newLibraryId?: string) => {
    fetchLibrariesOnly()
    if (newLibraryId) {
      setPendingLibraryId(newLibraryId)
    }
  }

  const fetchReportsOnly = async () => {
    setReportsLoading(true)
    try {
      const repRes = await getGovernanceReports({ page_size: 5 })
      if (repRes.code === 200) {
        setReports(repRes.data.items)
        const scores = repRes.data.items
          .filter((r: GovernanceReport) => r.quality_score !== undefined)
          .map((r: GovernanceReport) => r.quality_score as number)
        const avgScore = scores.length > 0 ? scores.reduce((a: number, b: number) => a + b, 0) / scores.length : 0
        setStats(prev => ({ ...prev, reportCount: repRes.data.total, avgScore }))
      }
    } catch (error) {
      message.error('获取报告失败')
    } finally {
      setReportsLoading(false)
    }
  }

  const recentReports = reports.slice(0, 6)
  const activeLibraries = libraries.filter(item => item.status === 'active')
  const qualityScore = overview?.quality_score ?? stats.avgScore
  const qualityGrade = qualityScore > 0 ? getGradeName(qualityScore) : '0'
  const qualityScoreDisplay = typeof qualityScore === 'number' && qualityScore > 0 ? qualityScore.toFixed(1) : '-'
  const reportTrend = overview?.report_trend || []
  const criticalFindings = overview?.critical_findings || []
  const ruleTypeStats = overview?.rule_type_stats || []

  return (
    <div className="space-y-6">
      {/* 页面标题区域 */}
      <header>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ maxWidth: 720 }}>
            <h1 className="text-2xl font-semibold mb-2" style={{ color: 'rgb(var(--theme-text))' }}>
              数据质检
            </h1>
            <p style={{ fontSize: 14, lineHeight: 1.7, color: 'rgb(var(--theme-text-secondary))', marginTop: 6 }}>
              统一管理基础质量检测、规则库质检，围绕规则库、报告与执行结果构建可配置、可追踪、可复用的质检链路闭环。
            </p>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', paddingTop: 30 }}>
            <button
              onClick={() => router.push(`/${lng}/governance/libraries`)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '10px 14px',
                borderRadius: 12,
                fontSize: 14,
                fontWeight: 500,
                color: 'rgb(var(--theme-text))',
                backgroundColor: 'transparent',
                border: '1px solid rgb(var(--theme-border))',
                cursor: 'pointer',
              }}
            >
              <Library style={{ width: 16, height: 16 }} />
              管理规则库
            </button>
            <button
              onClick={() => router.push(`/${lng}/governance/audit`)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '10px 16px',
                borderRadius: 12,
                fontSize: 14,
                fontWeight: 600,
                color: 'white',
                backgroundColor: 'rgb(var(--theme-primary))',
                border: 'none',
                cursor: 'pointer',
                boxShadow: '0 10px 24px rgba(var(--theme-primary), 0.18)',
              }}
            >
              <PlayCircle style={{ width: 16, height: 16 }} />
              开始质检
            </button>
          </div>
        </div>
      </header>

      {/* 统计概览卡片行 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 16 }}>
        <AnimatedStatCard
          icon={<Library style={{ width: 22, height: 22 }} />}
          value={stats.libraryCount}
          label="规则库总数"
          color="rgb(var(--theme-primary))"
        />
        <AnimatedStatCard
          icon={<Shield style={{ width: 22, height: 22 }} />}
          value={stats.ruleCount}
          label="质检规则总数"
          color="#52c41a"
        />
        <AnimatedStatCard
          icon={<FileText style={{ width: 22, height: 22 }} />}
          value={stats.reportCount}
          label="质检报告总数"
          color="#faad14"
        />
        <AnimatedStatCard
          icon={<TrendingUp style={{ width: 22, height: 22 }} />}
          value={qualityScoreDisplay}
          label={`当前质量评级：${qualityGrade}`}
          color="rgb(var(--theme-primary))"
        />
      </div>

      {/* 主内容区域：左侧质检总览 + 右侧快捷入口/规则库预览 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* 质检总览 */}
        <div style={{ borderRadius: 20, border: '1px solid rgb(var(--theme-border))', padding: 20, backgroundColor: 'rgb(var(--theme-bg))' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 600, color: 'rgb(var(--theme-text))', margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Sparkles style={{ width: 16, height: 16, color: '#faad14' }} />
                质检总览
              </h2>
              <p style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', marginTop: 4 }}>
                质检数据库表统计与质量评分概览
              </p>
            </div>
            <button
              onClick={fetchData}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '7px 10px',
                borderRadius: 8,
                fontSize: 12,
                fontWeight: 500,
                color: 'rgb(var(--theme-text))',
                backgroundColor: 'transparent',
                border: '1px solid rgb(var(--theme-border))',
                cursor: 'pointer',
              }}
            >
              <RefreshCw style={{ width: 12, height: 12 }} />
              刷新
            </button>
          </div>

          {overviewLoading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200 }}>
              <Loader2 style={{ width: 32, height: 32, color: 'rgb(var(--theme-primary))', animation: 'spin 1s linear infinite' }} />
            </div>
          ) : (
            <>
          {/* 质量评分环形图 + 关键指标 */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: 16, alignItems: 'center' }}>
            {/* 评分环形 */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 16 }}>
              <div style={{ position: 'relative', width: 100, height: 100 }}>
                <svg width="100" height="100" viewBox="0 0 100 100">
                  <circle cx="50" cy="50" r="42" fill="none" stroke="rgb(var(--theme-bg-secondary))" strokeWidth="8" />
                  <circle
                    cx="50" cy="50" r="42" fill="none"
                    stroke={getGradeColor(qualityGrade)}
                    strokeWidth="8"
                    strokeDasharray={`${(qualityScore / 100) * 264} 264`}
                    strokeLinecap="round"
                    transform="rotate(-90 50 50)"
                    style={{ transition: 'stroke-dasharray 0.5s ease' }}
                  />
                </svg>
                <div style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                  <div style={{ fontSize: 22, fontWeight: 700, color: 'rgb(var(--theme-text))', lineHeight: 1 }}>
                    {qualityScoreDisplay}
                  </div>
                  <div style={{ fontSize: 10, color: 'rgb(var(--theme-text-muted))', marginTop: 2 }}>
                    {qualityGrade}
                  </div>
                </div>
              </div>
            </div>

            {/* 关键指标 */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 8, backgroundColor: 'rgb(var(--theme-bg-secondary))' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#52c41a' }} />
                <span style={{ flex: 1, fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>活跃规则库</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>{activeLibraries.length}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 8, backgroundColor: 'rgb(var(--theme-bg-secondary))' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#1890ff' }} />
                <span style={{ flex: 1, fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>启用规则</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>{overview?.enabled_rule_count ?? 0}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 8, backgroundColor: 'rgb(var(--theme-bg-secondary))' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#faad14' }} />
                <span style={{ flex: 1, fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>总规则数</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>{overview?.rule_count ?? 0}</span>
              </div>
            </div>
          </div>

          {/* 质量维度评估 */}
          <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid rgb(var(--theme-border))' }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: 'rgb(var(--theme-text-secondary))', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Target style={{ width: 12, height: 12 }} />
              质量维度评估（数据通过率）
            </div>
            {overview && overview.dimensions && Object.keys(overview.dimensions).filter((key) => (overview.dimensions[key] as number) > 0).length > 0 ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 24px' }}>
                {Object.entries(overview.dimensions)
                  .filter(([_, value]) => (value as number) > 0)
                  .slice(0, 5)
                  .map(([key, value]) => (
                    <DimensionProgressBar
                      key={key}
                      label={dimensionLabels[key] || key}
                      value={Number(value)}
                      color={dimensionColors[key] || '#999'}
                    />
                  ))}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))', textAlign: 'center', padding: '12px 0' }}>
                暂无数据
              </div>
            )}
          </div>

          {/* 规则类型分布 */}
          {ruleTypeStats.length > 0 && (
            <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid rgb(var(--theme-border))' }}>
              <div style={{ fontSize: 12, fontWeight: 500, color: 'rgb(var(--theme-text-secondary))', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                <PieChart style={{ width: 12, height: 12 }} />
                规则类型分布
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {ruleTypeStats.map((item) => (
                  <RuleTypeTag
                    key={item.type}
                    type={item.type_name || item.type}
                    count={item.count}
                    percentage={item.percentage}
                    color={ruleTypeColors[item.type] || '#999'}
                  />
                ))}
              </div>
            </div>
          )}

          {/* 关键发现 */}
          <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid rgb(var(--theme-border))' }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: 'rgb(var(--theme-text-secondary))', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
              <AlertTriangle style={{ width: 12, height: 12, color: '#fa8c16' }} />
              关键发现 {criticalFindings.length > 0 && `(${criticalFindings.length})`}
            </div>
            {criticalFindings.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: criticalFindings.length > 2 ? 160 : 'none', overflowY: criticalFindings.length > 2 ? 'auto' : 'visible' }}>
                {criticalFindings.slice(0, 2).map((finding, index) => (
                  <CriticalFindingItem
                    key={`finding-${index}-${finding.table_name}`}
                    finding={finding}
                    onClick={() => {
                      if (finding.report_id) {
                        router.push(`/${lng}/governance/reports/${finding.report_id}`)
                      }
                    }}
                  />
                ))}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))', textAlign: 'center', padding: '12px 0' }}>
                暂无数据
              </div>
            )}
          </div>
          </>
          )}
        </div>

        {/* 右侧：快捷入口 + 规则库预览 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* 快捷入口 */}
          <div style={{ borderRadius: 20, border: '1px solid rgb(var(--theme-border))', padding: 20, backgroundColor: 'rgb(var(--theme-bg))' }}>
            <h2 style={{ fontSize: 15, fontWeight: 600, color: 'rgb(var(--theme-text))', margin: '0 0 14px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Activity style={{ width: 14, height: 14 }} />
              快捷入口
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <button
                onClick={() => router.push(`/${lng}/governance/audit`)}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: 12,
                  borderRadius: 12,
                  border: '1px solid rgb(var(--theme-border))',
                  backgroundColor: 'rgba(var(--theme-primary), 0.04)',
                  cursor: 'pointer',
                  color: 'rgb(var(--theme-text))',
                }}
              >
                <div style={{ width: 32, height: 32, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(var(--theme-primary), 0.12)', color: 'rgb(var(--theme-primary))' }}>
                  <PlayCircle style={{ width: 16, height: 16 }} />
                </div>
                <div style={{ textAlign: 'left', minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>发起质检</div>
                  <div style={{ fontSize: 10, color: 'rgb(var(--theme-text-muted))', marginTop: 1 }}>执行检测</div>
                </div>
              </button>
              <button
                onClick={openLibraryCreateModal}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: 12,
                  borderRadius: 12,
                  border: '1px solid rgb(var(--theme-border))',
                  backgroundColor: 'rgba(82, 196, 26, 0.04)',
                  cursor: 'pointer',
                  color: 'rgb(var(--theme-text))',
                }}
              >
                <div style={{ width: 32, height: 32, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(82, 196, 26, 0.12)', color: '#52c41a' }}>
                  <Plus style={{ width: 16, height: 16 }} />
                </div>
                <div style={{ textAlign: 'left', minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>新建规则库</div>
                  <div style={{ fontSize: 10, color: 'rgb(var(--theme-text-muted))', marginTop: 1 }}>创建模板</div>
                </div>
              </button>
              <button
                onClick={() => router.push(`/${lng}/governance/reports`)}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: 12,
                  borderRadius: 12,
                  border: '1px solid rgb(var(--theme-border))',
                  backgroundColor: 'rgba(250, 173, 20, 0.04)',
                  cursor: 'pointer',
                  color: 'rgb(var(--theme-text))',
                }}
              >
                <div style={{ width: 32, height: 32, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(250, 173, 20, 0.12)', color: '#faad14' }}>
                  <FileText style={{ width: 16, height: 16 }} />
                </div>
                <div style={{ textAlign: 'left', minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>查看报告</div>
                  <div style={{ fontSize: 10, color: 'rgb(var(--theme-text-muted))', marginTop: 1 }}>历史记录</div>
                </div>
              </button>
              <button
                onClick={() => router.push(`/${lng}/governance/reports/${reports[0]?.id}`)}
                disabled={reports.length === 0}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: 12,
                  borderRadius: 12,
                  border: '1px solid rgb(var(--theme-border))',
                  backgroundColor: 'rgba(24, 144, 255, 0.04)',
                  cursor: reports.length === 0 ? 'not-allowed' : 'pointer',
                  color: reports.length === 0 ? 'rgb(var(--theme-text-muted))' : 'rgb(var(--theme-text))',
                  opacity: reports.length === 0 ? 0.5 : 1,
                }}
              >
                <div style={{ width: 32, height: 32, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(24, 144, 255, 0.12)', color: '#1890ff' }}>
                  <BarChart3 style={{ width: 16, height: 16 }} />
                </div>
                <div style={{ textAlign: 'left', minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>最新报告</div>
                  <div style={{ fontSize: 10, color: 'rgb(var(--theme-text-muted))', marginTop: 1 }}>查看详情</div>
                </div>
              </button>
            </div>
          </div>

          {/* 规则库预览 */}
          <div style={{ borderRadius: 20, border: '1px solid rgb(var(--theme-border))', padding: 20, backgroundColor: 'rgb(var(--theme-bg))', flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16, gap: 12 }}>
              <div>
                <h2 style={{ fontSize: 16, fontWeight: 600, color: 'rgb(var(--theme-text))', margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Library style={{ width: 16, height: 16 }} />
                  规则库预览
                </h2>
                <p style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', marginTop: 4 }}>
                  管理规则库，创建和维护质检规则
                </p>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {libraries.length > 4 && (
                  <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))' }}>
                    +{libraries.length - 4}
                  </span>
                )}
                <button
                  onClick={() => router.push(`/${lng}/governance/libraries`)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    padding: '7px 10px',
                    borderRadius: 8,
                    fontSize: 12,
                    fontWeight: 500,
                    color: 'rgb(var(--theme-primary))',
                    backgroundColor: 'rgba(var(--theme-primary), 0.08)',
                    border: 'none',
                    cursor: 'pointer',
                  }}
                >
                  查看全部
                  <ChevronRight style={{ width: 12, height: 12 }} />
                </button>
              </div>
            </div>

            {librariesLoading ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 160 }}>
                <Loader2 style={{ width: 24, height: 24, color: 'rgb(var(--theme-primary))', animation: 'spin 1s linear infinite' }} />
              </div>
            ) : libraries.length === 0 ? (
              <EnhancedEmptyStateCard
                icon={<Library />}
                title="暂无规则库"
                description="创建规则库并绑定数据源后，即可开始维护质检规则"
                buttonText="创建规则库"
                onButtonClick={openLibraryCreateModal}
                actionType="create"
              />
            ) : libraries.length === 1 ? (
              /* 只有1个规则库时，展示卡片 + 添加新规则库提示 */
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {libraries.slice(0, 1).map((lib) => (
                  <LibraryCard
                    key={lib.id}
                    library={lib}
                    onClick={() => router.push(`/${lng}/governance/libraries?id=${lib.id}`)}
                  />
                ))}
                {/* 添加新规则库提示 */}
                <button
                  onClick={openLibraryCreateModal}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    padding: 14,
                    borderRadius: 10,
                    backgroundColor: 'rgba(82, 196, 26, 0.04)',
                    border: '1px dashed rgba(82, 196, 26, 0.3)',
                    cursor: 'pointer',
                    color: 'rgb(var(--theme-text-secondary))',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(82, 196, 26, 0.08)'
                    e.currentTarget.style.borderColor = 'rgba(82, 196, 26, 0.5)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(82, 196, 26, 0.04)'
                    e.currentTarget.style.borderColor = 'rgba(82, 196, 26, 0.3)'
                  }}
                >
                  <div style={{ width: 36, height: 36, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(82, 196, 26, 0.1)', color: '#52c41a' }}>
                    <Plus style={{ width: 18, height: 18 }} />
                  </div>
                  <div style={{ textAlign: 'left' }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: '#52c41a' }}>添加新的规则库</div>
                    <div style={{ fontSize: 11, marginTop: 2 }}>绑定数据源，创建更多质检规则</div>
                  </div>
                </button>
              </div>
            ) : (
              /* 2个及以上规则库时正常展示 */
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {libraries.slice(0, 4).map((lib) => (
                  <LibraryCard
                    key={lib.id}
                    library={lib}
                    onClick={() => router.push(`/${lng}/governance/libraries?id=${lib.id}`)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 最近报告区域 */}
      <div style={{ borderRadius: 20, border: '1px solid rgb(var(--theme-border))', padding: 20, backgroundColor: 'rgb(var(--theme-bg))' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16, gap: 12 }}>
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 600, color: 'rgb(var(--theme-text))', margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
              <FileText style={{ width: 16, height: 16 }} />
              最近报告
            </h2>
            <p style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', marginTop: 4 }}>
              最新的质检执行结果与质量评分
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={fetchReportsOnly}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '7px 10px',
                borderRadius: 8,
                fontSize: 12,
                fontWeight: 500,
                color: 'rgb(var(--theme-text))',
                backgroundColor: 'transparent',
                border: '1px solid rgb(var(--theme-border))',
                cursor: 'pointer',
              }}
            >
              <RefreshCw style={{ width: 12, height: 12 }} />
              刷新
            </button>
            <button
              onClick={() => router.push(`/${lng}/governance/reports`)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '7px 10px',
                borderRadius: 8,
                fontSize: 12,
                fontWeight: 500,
                color: 'rgb(var(--theme-primary))',
                backgroundColor: 'rgba(var(--theme-primary), 0.08)',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              查看全部
              <ChevronRight style={{ width: 12, height: 12 }} />
            </button>
          </div>
        </div>

        {reportsLoading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 180 }}>
            <Loader2 style={{ width: 24, height: 24, color: 'rgb(var(--theme-primary))', animation: 'spin 1s linear infinite' }} />
          </div>
        ) : recentReports.length === 0 ? (
          <EnhancedEmptyStateCard
            icon={<FileText />}
            title="暂无报告"
            description="开始一次质检执行后，可以在这里查看最新质检结果"
            buttonText="开始质检"
            onButtonClick={() => router.push(`/${lng}/governance/audit`)}
            actionType="execute"
          />
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(320px, 1fr))', gap: 14 }}>
            {recentReports.map((report) => (
              <ReportCard
                key={report.id}
                report={report}
                onClick={() => router.push(`/${lng}/governance/reports/${report.id}`)}
              />
            ))}
          </div>
        )}
      </div>

      <CreateLibraryModal
        visible={libraryModalVisible}
        onClose={() => setLibraryModalVisible(false)}
        onSuccess={handleLibraryCreateSuccess}
        title="创建规则库"
        onGoToDatasourceManagement={() => router.push(`/${lng}/workspaces`)}
      />
    </div>
  )
}
