'use client'

import React, { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next-nprogress-bar'
import {
  FileText,
  Search,
  Download,
  Trash2,
  Database,
  CheckCircle,
  Loader2,
  BarChart3,
  ArrowRight,
  ArrowLeft,
  RefreshCw,
  Sparkles,
  Eye,
  Clock,
  Target,
  Layers,
  FileCheck,
  Server,
  HardDrive,
  FolderTree,
  File,
  ChevronDown,
} from 'lucide-react'
import { message, Modal, Select, Input, Tooltip, Dropdown } from 'antd'
import type { MenuProps } from 'antd'
import {
  getGovernanceReports,
  deleteGovernanceReport,
  downloadGovernanceReport,
  GovernanceReport,
  getGradeName,
  getGradeColor,
} from '@/api/governance'

// 统计数据卡片组件（紧凑版）
const StatCard = ({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode
  label: string
  value: string | number
  color: string
}) => (
  <div
    style={{
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '10px 14px',
      borderRadius: 10,
      backgroundColor: 'rgb(var(--theme-bg))',
      border: '1px solid rgb(var(--theme-border))',
      flex: '1 1 auto',
      minWidth: 120,
    }}
  >
    <div
      style={{
        width: 32,
        height: 32,
        borderRadius: 8,
        backgroundColor: `${color}15`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: color,
        flexShrink: 0,
      }}
    >
      {icon}
    </div>
    <div>
      <p style={{ fontSize: 16, fontWeight: 700, color: 'rgb(var(--theme-text))', margin: 0 }}>
        {value}
      </p>
      <p style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', margin: 0 }}>{label}</p>
    </div>
  </div>
)

// 空状态组件
const EmptyStateCard = ({
  icon,
  title,
  description,
  buttonText,
  onButtonClick,
}: {
  icon: React.ReactNode
  title: string
  description: string
  buttonText?: string
  onButtonClick?: () => void
}) => (
  <div
    style={{
      textAlign: 'center',
      padding: 64,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: 400,
    }}
  >
    <div
      style={{
        color: 'rgb(var(--theme-text-muted))',
        opacity: 0.4,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: 16,
      }}
    >
      {React.cloneElement(icon as React.ReactElement, { style: { width: 72, height: 72 } })}
    </div>
    <p style={{ fontSize: 18, fontWeight: 600, marginTop: 16, color: 'rgb(var(--theme-text))' }}>
      {title}
    </p>
    <p
      style={{
        fontSize: 14,
        marginTop: 8,
        color: 'rgb(var(--theme-text-secondary))',
        maxWidth: 420,
        lineHeight: 1.7,
      }}
    >
      {description}
    </p>
    {buttonText && onButtonClick && (
      <button
        onClick={onButtonClick}
        style={{
          marginTop: 24,
          padding: '10px 20px',
          borderRadius: 10,
          fontSize: 14,
          fontWeight: 500,
          color: 'white',
          backgroundColor: 'rgb(var(--theme-primary))',
          border: 'none',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}
      >
        <Sparkles style={{ width: 16, height: 16 }} />
        {buttonText}
      </button>
    )}
  </div>
)

// 状态标签组件
const StatusBadge = ({ status }: { status?: string }) => {
  const config: Record<string, { color: string; bg: string; label: string }> = {
    completed: { color: '#52c41a', bg: '#f6ffed', label: '已导出' },
    generating: { color: '#1890ff', bg: '#e6f7ff', label: '生成中' },
    pending: { color: '#faad14', bg: '#fffbe6', label: '未导出' },
    failed: { color: '#f5222d', bg: '#fff1f0', label: '失败' },
  }

  const current = config[status || ''] || config.pending

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '4px 10px',
        borderRadius: 6,
        fontSize: 12,
        fontWeight: 500,
        color: current.color,
        backgroundColor: current.bg,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          backgroundColor: current.color,
        }}
      />
      {current.label}
    </span>
  )
}

// 报告卡片组件
const ReportCard = ({
  report,
  onClick,
  onDelete,
  onDownload,
}: {
  report: GovernanceReport
  onClick: () => void
  onDelete: () => void
  onDownload: () => void
}) => {
  const gradeColor = getGradeColor(getGradeName(report.quality_score))

  return (
    <div
      onClick={onClick}
      style={{
        padding: 16,
        borderRadius: 14,
        border: '1px solid rgb(var(--theme-border))',
        backgroundColor: 'rgb(var(--theme-bg))',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        boxShadow: '0 4px 16px rgba(15, 23, 42, 0.04)',
        position: 'relative',
        overflow: 'hidden',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = '0 8px 24px rgba(15, 23, 42, 0.08)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = '0 4px 16px rgba(15, 23, 42, 0.04)'
      }}
    >
      {/* 顶部区域：评分 + 状态 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          marginBottom: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 46,
              height: 46,
              borderRadius: 10,
              backgroundColor: `${gradeColor}15`,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              border: `2px solid ${gradeColor}30`,
            }}
          >
            <span style={{ fontSize: 15, fontWeight: 800, color: gradeColor, lineHeight: 1 }}>
              {report.quality_score?.toFixed(1) || '-'}
            </span>
          </div>
          <div>
            <p
              style={{
                fontSize: 11,
                color: 'rgb(var(--theme-text-muted))',
                margin: 0,
                marginBottom: 1,
              }}
            >
              质量评分
            </p>
            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: gradeColor,
              }}
            >
              {getGradeName(report.quality_score)}
            </span>
          </div>
        </div>
        <StatusBadge status={report.file_status} />
      </div>

      {/* 文件名称 */}
      <h3
        style={{
          fontWeight: 600,
          fontSize: 13,
          color: 'rgb(var(--theme-text))',
          margin: 0,
          marginBottom: 8,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {report.report_name}
      </h3>

      {/* 数据源信息 */}
      {(report.datasource_name || report.database_name || report.schema_name) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            marginBottom: 8,
            padding: '6px 8px',
            borderRadius: 6,
            backgroundColor: 'rgb(var(--theme-bg-secondary))',
            flexWrap: 'wrap',
          }}
        >
          <Server style={{ width: 11, height: 11, color: 'rgb(var(--theme-text-muted))' }} />
          {report.datasource_name && (
            <Tooltip title={`数据源：${report.datasource_name}`}>
              <span
                style={{
                  fontSize: 12,
                  color: 'rgb(var(--theme-text))',
                  fontWeight: 500,
                  maxWidth: 120,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {report.datasource_name}
              </span>
            </Tooltip>
          )}
          {report.datasource_name && (report.database_name || report.schema_name) && (
            <span style={{ color: 'rgb(var(--theme-border))', fontSize: 10 }}>/</span>
          )}
          {report.database_name && (
            <Tooltip title={`数据库：${report.database_name}`}>
              <span
                style={{
                  fontSize: 12,
                  color: 'rgb(var(--theme-text-secondary))',
                  maxWidth: 140,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {report.database_name}
              </span>
            </Tooltip>
          )}
          {report.schema_name && (
            <>
              <span style={{ color: 'rgb(var(--theme-border))', fontSize: 10 }}>/</span>
              <Tooltip title={`Schema：${report.schema_name}`}>
                <span
                  style={{
                    fontSize: 12,
                    color: 'rgb(var(--theme-text-secondary))',
                    maxWidth: 80,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {report.schema_name}
                </span>
              </Tooltip>
            </>
          )}
        </div>
      )}

      {/* 报告模块标签 */}
      <div style={{ display: 'flex', gap: 5, marginBottom: 8, flexWrap: 'wrap' }}>
        {report.include_basic_audit && (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 3,
              padding: '2px 7px',
              borderRadius: 4,
              fontSize: 11,
              fontWeight: 500,
              backgroundColor: '#f6ffed',
              color: '#52c41a',
            }}
          >
            <FileCheck style={{ width: 10, height: 10 }} />
            基础审计
          </span>
        )}
        {/* [暂时屏蔽关系发现功能] */}
        {/*
        {report.include_relationship && (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 3,
              padding: '2px 7px',
              borderRadius: 4,
              fontSize: 11,
              fontWeight: 500,
              backgroundColor: '#f9f0ff',
              color: '#722ed1',
            }}
          >
            <Layers style={{ width: 10, height: 10 }} />
            关系发现
          </span>
        )}
        */}
        {report.include_quality && (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 3,
              padding: '2px 7px',
              borderRadius: 4,
              fontSize: 11,
              fontWeight: 500,
              backgroundColor: '#e6f7ff',
              color: '#1890ff',
            }}
          >
            <BarChart3 style={{ width: 10, height: 10 }} />
            规则库质检
          </span>
        )}
      </div>

      {/* 导出文件信息 */}
      {report.has_export && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            marginBottom: 8,
            fontSize: 11,
            color: 'rgb(var(--theme-text-secondary))',
          }}
        >
          <File style={{ width: 11, height: 11 }} />
          <span>已导出文件：{report.exported_file_name || '未知文件'}</span>
          {report.exported_file_type && (
            <span
              style={{
                padding: '1px 4px',
                borderRadius: 3,
                backgroundColor: 'rgb(var(--theme-bg-secondary))',
                fontSize: 10,
                fontWeight: 500,
              }}
            >
              {report.exported_file_type.toUpperCase()}
            </span>
          )}
        </div>
      )}

      {/* 统计信息栏 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '8px 0',
          borderTop: '1px solid rgb(var(--theme-border))',
          marginBottom: 10,
        }}
      >
        <Tooltip title="应用的规则数">
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Target style={{ width: 11, height: 11, color: 'rgb(var(--theme-text-muted))' }} />
            <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>
              {report.rules_applied} 条规则
            </span>
          </div>
        </Tooltip>
        <Tooltip title="执行时间">
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Clock style={{ width: 11, height: 11, color: 'rgb(var(--theme-text-muted))' }} />
            <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>
              {new Date(report.execution_time).toLocaleString('zh-CN', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          </div>
        </Tooltip>
      </div>

      {/* 操作按钮 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <button
          onClick={(e) => {
            e.stopPropagation()
            onClick()
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            padding: '6px 12px',
            borderRadius: 7,
            fontSize: 12,
            fontWeight: 500,
            color: 'white',
            backgroundColor: 'rgb(var(--theme-primary))',
            border: 'none',
            cursor: 'pointer',
          }}
        >
          <Eye style={{ width: 13, height: 13 }} />
          查看详情
        </button>
        <div style={{ display: 'flex', gap: 5 }}>
          {report.has_export && (
            <Tooltip title="下载报告">
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onDownload()
                }}
                style={{
                  padding: 6,
                  borderRadius: 7,
                  backgroundColor: 'transparent',
                  border: '1px solid rgb(var(--theme-border))',
                  cursor: 'pointer',
                  color: 'rgb(var(--theme-text-secondary))',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Download style={{ width: 14, height: 14 }} />
              </button>
            </Tooltip>
          )}
          <Tooltip title="删除报告">
            <button
              onClick={(e) => {
                e.stopPropagation()
                onDelete()
              }}
              style={{
                padding: 6,
                borderRadius: 7,
                backgroundColor: 'transparent',
                border: '1px solid rgb(var(--theme-border))',
                cursor: 'pointer',
                color: '#f5222d',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Trash2 style={{ width: 14, height: 14 }} />
            </button>
          </Tooltip>
        </div>
      </div>
    </div>
  )
}

export default function ReportsPage({ params }: { params: { lng: string } }) {
  const { lng } = params
  const router = useRouter()
  const [reports, setReports] = useState<GovernanceReport[]>([])
  const [loading, setLoading] = useState(true)
  const [searchKeyword, setSearchKeyword] = useState('')
  const [datasourceFilter, setDatasourceFilter] = useState<string | undefined>()

  useEffect(() => {
    fetchReports()
  }, [datasourceFilter])

  const fetchReports = async () => {
    setLoading(true)
    try {
      const res = await getGovernanceReports({ page_size: 100, datasource_id: datasourceFilter })
      if (res.code === 200) setReports(res.data.items)
    } catch (error) {
      message.error('获取报告列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (report: GovernanceReport) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定删除 "${report.report_name}" 吗？操作不可逆`,
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      centered: true,
      styles: {
        content: { color: 'rgb(var(--theme-text))' },
      },
      onOk: async () => {
        try {
          const res = await deleteGovernanceReport(report.id)
          // 成功状态码支持 0 和 200
          if ((res.code === 0 || res.code === 200) && res.data) {
            const { table_relationships_deleted, table_relationship_cards_deleted } = res.data
            // 根据删除的数据量构建友好的提示信息
            const deletedParts: string[] = []
            if (table_relationships_deleted > 0) {
              deletedParts.push(`${table_relationships_deleted} 条关系记录`)
            }
            if (table_relationship_cards_deleted > 0) {
              deletedParts.push(`${table_relationship_cards_deleted} 张表关系卡片`)
            }
            if (deletedParts.length > 0) {
              message.success(`删除成功！已同时清理 ${deletedParts.join('和')}。`)
            } else {
              message.success('删除成功')
            }
            fetchReports()
          } else if (res.code === 404) {
            message.error('报告不存在')
            fetchReports()
          } else {
            message.error(res.msg || '删除失败')
          }
        } catch (error) {
          message.error('删除失败')
        }
      },
    })
  }

  const handleDownload = async (report: GovernanceReport) => {
    try {
      await downloadGovernanceReport(report.id)
      message.success('下载已完成')
    } catch (error) {
      message.error('下载失败')
    }
  }

  // 从报告列表中提取唯一的数据源选项（基于接口返回的 datasource_name）
  const datasourceOptions = useMemo(() => {
    const map = new Map<string, { label: string; value: string }>()
    reports.forEach((report) => {
      if (report.datasource_id && report.datasource_name) {
        map.set(report.datasource_id, {
          label: report.datasource_name,
          value: report.datasource_id,
        })
      }
    })
    return Array.from(map.values())
  }, [reports])

  const filteredReports = reports.filter((report) =>
    report.report_name.toLowerCase().includes(searchKeyword.toLowerCase())
  )

  // 计算统计数据
  const stats = useMemo(() => {
    const totalReports = reports.length
    const avgScore = reports.length
      ? reports.reduce((sum, r) => sum + (r.quality_score || 0), 0) / reports.length
      : 0
    const completedCount = reports.filter((r) => r.file_status === 'completed').length
    const qualityReports = reports.filter((r) => r.include_quality).length

    return { totalReports, avgScore, completedCount, qualityReports }
  }, [reports])

  return (
    <div className="reports-page space-y-5">
      {/* 返回按钮 */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button
          onClick={() => router.push(`/${lng}/governance`)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            padding: '6px 10px',
            borderRadius: 6,
            fontSize: 13,
            color: 'rgb(var(--theme-text-secondary))',
            backgroundColor: 'transparent',
            border: 'none',
            cursor: 'pointer',
          }}
        >
          <ArrowLeft style={{ width: 16, height: 16 }} />
          返回质检中心
        </button>
      </div>

      {/* 页面标题区域 */}
      <div
        style={{
          borderRadius: 16,
          border: '1px solid rgb(var(--theme-border))',
          backgroundColor: 'rgb(var(--theme-bg))',
          padding: 20,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: 16,
            flexWrap: 'wrap',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 10,
                  backgroundColor: 'rgb(var(--theme-primary))15',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'rgb(var(--theme-primary))',
                }}
              >
                <FileText style={{ width: 18, height: 18 }} />
              </div>
              <h1 style={{ fontSize: 20, fontWeight: 700, color: 'rgb(var(--theme-text))', margin: 0 }}>
                质检报告
              </h1>
            </div>
            <p style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))', margin: 0 }}>
              查看和下载所有已生成的质检质量报告，支持质量检测和基础审计结果。
            </p>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Input
              prefix={<Search style={{ width: 14, height: 14, color: 'rgb(var(--theme-text-muted))' }} />}
              placeholder="搜索报告名称..."
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              style={{ borderRadius: 8, width: 180, fontSize: 13 }}
              allowClear
            />
            <Select
              placeholder="筛选数据源"
              allowClear
              value={datasourceFilter}
              onChange={setDatasourceFilter}
              style={{ width: 160, fontSize: 13 }}
              options={datasourceOptions}
              suffixIcon={<ChevronDown style={{ width: 14, height: 14 }} />}
            />
            <Tooltip title="刷新">
              <button
                onClick={fetchReports}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 36,
                  height: 36,
                  borderRadius: 8,
                  color: 'rgb(var(--theme-text-secondary))',
                  backgroundColor: 'transparent',
                  border: '1px solid rgb(var(--theme-border))',
                  cursor: 'pointer',
                }}
              >
                <RefreshCw style={{ width: 14, height: 14 }} />
              </button>
            </Tooltip>
          </div>
        </div>
      </div>

      {/* 统计卡片区域（独立区块） */}
      {!loading && reports.length > 0 && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: 12,
          }}
        >
          <StatCard
            icon={<FileText style={{ width: 16, height: 16 }} />}
            label="报告总数"
            value={stats.totalReports}
            color="#1890ff"
          />
          <StatCard
            icon={<Target style={{ width: 16, height: 16 }} />}
            label="平均评分"
            value={stats.avgScore.toFixed(1)}
            color="#722ed1"
          />
          <StatCard
            icon={<FileCheck style={{ width: 16, height: 16 }} />}
            label="已完成"
            value={stats.completedCount}
            color="#52c41a"
          />
          <StatCard
            icon={<BarChart3 style={{ width: 16, height: 16 }} />}
            label="质量检测"
            value={stats.qualityReports}
            color="#13c2c2"
          />
        </div>
      )}

      {/* 报告列表区域 */}
      {loading ? (
        <div
          style={{
            borderRadius: 16,
            border: '1px solid rgb(var(--theme-border))',
            backgroundColor: 'rgb(var(--theme-bg))',
            minHeight: 400,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div style={{ textAlign: 'center' }}>
            <Loader2
              style={{
                width: 40,
                height: 40,
                color: 'rgb(var(--theme-primary))',
                animation: 'spin 1s linear infinite',
                margin: '0 auto',
              }}
            />
            <p style={{ marginTop: 14, color: 'rgb(var(--theme-text-muted))' }}>正在加载报告列表...</p>
          </div>
        </div>
      ) : filteredReports.length === 0 ? (
        <div
          style={{
            borderRadius: 16,
            border: '1px solid rgb(var(--theme-border))',
            backgroundColor: 'rgb(var(--theme-bg))',
            minHeight: 400,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <EmptyStateCard
            icon={<FileText />}
            title={searchKeyword || datasourceFilter ? '未找到匹配的报告' : '暂无质检报告'}
            description={
              searchKeyword || datasourceFilter
                ? `没有找到符合条件的报告，请尝试其他筛选条件。`
                : '开始执行数据质检后，这里会展示生成的质检质量报告。报告包含质量检测和基础审计等模块。'
            }
            buttonText={searchKeyword || datasourceFilter ? undefined : '开始质检'}
            onButtonClick={searchKeyword || datasourceFilter ? undefined : () => router.push(`/${lng}/governance/audit`)}
          />
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
            gap: 16,
          }}
        >
          {filteredReports.map((report) => (
            <ReportCard
              key={report.id}
              report={report}
              onClick={() => router.push(`/${lng}/governance/reports/${report.id}`)}
              onDelete={() => handleDelete(report)}
              onDownload={() => handleDownload(report)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
