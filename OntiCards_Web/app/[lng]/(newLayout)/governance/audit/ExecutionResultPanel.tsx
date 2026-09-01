'use client'

import React, { useState } from 'react'
import {
  ArrowRight,
  ExternalLink,
  Link2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Target,
  Award,
  ShieldCheck,
  Loader2,
  Clock,
  ChevronDown,
  ChevronRight,
  Copy,
  Terminal,
  Database,
  Table2,
  BarChart3,
  TrendingUp,
  FileText,
  TableProperties,
} from 'lucide-react'
import { Empty, Table, Space, Button, Tag, Tooltip, Progress, message, Collapse } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  BasicAuditData,
  RelationDiscoveryDetail,
  RuleExecutionResultDetail,
  getRuleDisplayName,
  getSeverityDisplayName,
  ruleModeLabels,
  ruleModeColors,
  relationshipTypeLabels,
  relationshipTypeColors,
  cardinalityLabels,
  cardinalityColors,
  executionSourceLabels,
  executionSourceColors,
} from '@/api/governance'

export interface ExecutionResult {
  report_id: string
  quality_score: number
  grade: string
  summary: {
    total_rules: number
    passed_rules: number
    failed_rules: number
    error_rules: number
    quality_score: number
    grade: string
  }
  // 新版新增
  basic_audit?: BasicAuditData
  quality_audit?: {
    rules_count: number
    results: RuleExecutionResultDetail[]
  }
  // 新版新增：基础空值检测详情（execution_source='basic_audit'）
  basic_audit_detail?: {
    tables_count: number
    results: RuleExecutionResultDetail[]
  }
  // 扩展的关系发现
  relation_discovery?: RelationDiscoveryDetail
  // 兼容旧版
  results?: RuleExecutionResultDetail[]
}

interface ExecutionResultPanelProps {
  result: ExecutionResult
  onGenerateReport: () => void
  onDownloadReport: () => void
  onViewDetails: () => void
  reportLoading: boolean
  reportGenerated: boolean
}

const formatNumber = (value?: number | null) => {
  if (value === undefined || value === null) return '-'
  return new Intl.NumberFormat('zh-CN').format(value)
}

const getGradeColor = (grade: string) => {
  switch (grade) {
    case '优秀': return '#52c41a'
    case '良好': return '#1890ff'
    case '一般': return '#faad14'
    case '较差': return '#fa8c16'
    case '差': return '#f5222d'
    default: return '#999'
  }
}

const StatCard = ({
  icon,
  label,
  value,
  color,
  subText,
}: {
  icon: React.ReactNode
  label: string
  value: string | number
  color?: string
  subText?: string
}) => (
  <div
    style={{
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '10px 14px',
      borderRadius: 12,
      border: '1px solid rgb(var(--theme-border))',
      backgroundColor: 'rgb(var(--theme-bg))',
      flex: 1,
      minWidth: 0,
    }}
  >
    <div
      style={{
        width: 32,
        height: 32,
        borderRadius: 8,
        backgroundColor: color ? `${color}18` : 'rgba(var(--theme-primary), 0.08)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: color || 'rgb(var(--theme-primary))',
        flexShrink: 0,
      }}
    >
      {icon}
    </div>
    <div style={{ minWidth: 0, flex: 1 }}>
      <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', lineHeight: 1.2 }}>
        {label}
      </div>
      <div
        style={{
          fontSize: 18,
          fontWeight: 700,
          color: color || 'rgb(var(--theme-text))',
          lineHeight: 1.2,
        }}
      >
        {value}
      </div>
      {subText && (
        <div style={{ fontSize: 10, color: 'rgb(var(--theme-text-muted))', marginTop: 1 }}>{subText}</div>
      )}
    </div>
  </div>
)

const ExecutionResultPanel = ({
  result,
  onGenerateReport,
  onDownloadReport,
  onViewDetails,
  reportLoading,
  reportGenerated,
}: ExecutionResultPanelProps) => {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())
  const [basicAuditExpanded, setBasicAuditExpanded] = useState(false)
  const [basicAuditDetailExpanded, setBasicAuditDetailExpanded] = useState(false)
  const [relationDetailExpanded, setRelationDetailExpanded] = useState(false)
  const [ruleLibraryExpanded, setRuleLibraryExpanded] = useState(true)

  // 兼容新版 quality_audit.results 和旧版 results
  const executionResults = result.quality_audit?.results || result.results || []

  const toggleExpand = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      message.success('已复制到剪贴板')
    })
  }

  const formatExecutionTime = (ms?: number) => {
    if (ms === undefined || ms === null) return '-'
    if (ms < 1000) return `${ms}ms`
    if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`
    return `${(ms / 1000).toFixed(1)}s`
  }

  // 格式化值显示
  const formatValue = (value: any): string => {
    if (value === null || value === undefined) return '-'
    if (typeof value === 'boolean') return value ? '是' : '否'
    if (typeof value === 'object') {
      if (value instanceof Date) return value.toLocaleString('zh-CN')
      return JSON.stringify(value)
    }
    if (typeof value === 'number') {
      // 如果是时间戳（较大的数字），尝试转换
      if (value > 1000000000000 && value < 2000000000000) {
        return new Date(value).toLocaleString('zh-CN')
      }
      return value.toString()
    }
    return String(value)
  }

  const resultColumns = React.useMemo<ColumnsType<RuleExecutionResultDetail>>(
    () => [
      {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        width: 45,
        align: 'center',
        render: (status) => {
          if (status === 'passed')
            return (
              <CheckCircle2 style={{ width: 16, height: 16, color: '#52c41a' }} />
            )
          if (status === 'failed')
            return (
              <XCircle style={{ width: 16, height: 16, color: '#f5222d' }} />
            )
          return (
            <AlertCircle style={{ width: 16, height: 16, color: '#fa8c16' }} />
          )
        },
      },
      {
        title: '规则名称',
        dataIndex: 'rule_name',
        key: 'rule_name',
        width: 160,
        minWidth: 120,
        ellipsis: { showTitle: false },
        render: (text) => (
          <Tooltip title={text} placement="topLeft">
            <span style={{ fontWeight: 500, fontSize: 12, whiteSpace: 'nowrap' }}>{text}</span>
          </Tooltip>
        ),
      },
      {
        title: '类型',
        dataIndex: 'rule_type',
        key: 'rule_type',
        width: 80,
        render: (ruleType) => (
          <Tag style={{ borderRadius: 6, margin: 0 }}>{getRuleDisplayName({ rule_type: ruleType })}</Tag>
        ),
      },
      {
        title: '目标表',
        dataIndex: 'table_name',
        key: 'table_name',
        width: 140,
        ellipsis: { showTitle: false },
        render: (text) => (
          <Tooltip title={text} placement="topLeft">
            <span>{text}</span>
          </Tooltip>
        ),
      },
      {
        title: '目标列',
        dataIndex: 'column_name',
        key: 'column_name',
        width: 110,
        ellipsis: { showTitle: false },
        render: (value: string | null) =>
          value ? (
            <Tooltip title={value} placement="topLeft">
              <span>{value}</span>
            </Tooltip>
          ) : (
            <span style={{ color: 'rgb(var(--theme-text-muted))' }}>-</span>
          ),
      },
      {
        title: '失败率',
        key: 'failed_rate',
        width: 75,
        align: 'right',
        render: (_, record) => {
          const rate = record.failed_rate ?? 0
          const color = rate > 5 ? '#f5222d' : rate > 2 ? '#faad14' : '#52c41a'
          return (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-end' }}>
              <Progress
                percent={Math.min(rate, 100)}
                size="small"
                strokeColor={color}
                trailColor="rgba(0,0,0,0.06)"
                showInfo={false}
                style={{ width: 40, marginBottom: 0 }}
              />
              <span style={{ color, fontWeight: 600, minWidth: 42, textAlign: 'right', fontSize: 12 }}>
                {rate.toFixed(2)}%
              </span>
            </div>
          )
        },
      },
      {
        title: '失败/总数',
        key: 'detail',
        width: 80,
        align: 'right',
        render: (_, record) => (
          <span style={{ color: 'rgb(var(--theme-text-secondary))', fontSize: 12 }}>
            <span style={{ color: '#f5222d', fontWeight: 600 }}>{formatNumber(record.failed_count)}</span>
            {' / '}
            {formatNumber(record.total_count)}
          </span>
        ),
      },
      {
        title: '执行耗时',
        dataIndex: 'execution_time_ms',
        key: 'execution_time_ms',
        width: 80,
        align: 'right',
        render: (ms?: number) => {
          if (ms === undefined || ms === null) {
            return <span style={{ color: 'rgb(var(--theme-text-muted))', fontSize: 12 }}>无</span>
          }
          return (
            <Tooltip title={`实际执行时间: ${ms}ms`}>
              <span
                style={{
                  color: 'rgb(var(--theme-text-secondary))',
                  fontSize: 12,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                <Clock style={{ width: 11, height: 11 }} />
                {formatExecutionTime(ms)}
              </span>
            </Tooltip>
          )
        },
      },
      {
        title: '级别',
        dataIndex: 'severity',
        key: 'severity',
        width: 70,
        align: 'center',
        render: (severity) => (
          <Tag
            color={severity === 'critical' ? 'red' : severity === 'warning' ? 'orange' : 'blue'}
            style={{ borderRadius: 6, fontSize: 11, margin: 0 }}
          >
            {getSeverityDisplayName({ severity })}
          </Tag>
        ),
      },
      {
        title: '详情',
        key: 'expand',
        width: 50,
        align: 'center',
        render: (_, record) => {
          const hasDetail = record.executed_sql_text || record.error_message || (record.raw_result && Object.keys(record.raw_result).length > 0)
          if (!hasDetail) {
            return <span style={{ color: 'rgb(var(--theme-text-muted))', fontSize: 12 }}>无</span>
          }
          return (
            <Button
              type="text"
              size="small"
              icon={expandedRows.has(record.id) ? <ChevronDown style={{ width: 14, height: 14, color: 'rgb(var(--theme-text))' }} /> : <ChevronRight style={{ width: 14, height: 14, color: 'rgb(var(--theme-text))' }} />}
              onClick={() => toggleExpand(record.id)}
              style={{ padding: 4 }}
            />
          )
        },
      },
    ],
    [expandedRows],
  )

  const gradeColor = getGradeColor(result.grade)
  const passRate =
    result.summary.total_rules > 0
      ? ((result.summary.passed_rules / result.summary.total_rules) * 100).toFixed(1)
      : '0'

  return (
    <div style={{ display: 'grid', gap: 20 }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div>
          <h3
            style={{
              fontSize: 17,
              fontWeight: 700,
              color: 'rgb(var(--theme-text))',
              margin: 0,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <ShieldCheck style={{ width: 20, height: 20, color: gradeColor }} />
            执行结果
          </h3>
          <p style={{ color: 'rgb(var(--theme-text-secondary))', marginTop: 4, fontSize: 13 }}>
            规则执行已完成，{result.summary.total_rules} 条规则中 {result.summary.passed_rules} 条通过
          </p>
        </div>
        <Space>
          <Button type="primary" onClick={onGenerateReport} loading={reportLoading}>
            生成报告
            <ArrowRight style={{ width: 14, height: 14 }} />
          </Button>
          {reportGenerated ? (
            <Button onClick={onDownloadReport}>
              下载报告
              <ExternalLink style={{ width: 14, height: 14 }} />
            </Button>
          ) : (
            <Button disabled>
              下载报告
              <ExternalLink style={{ width: 14, height: 14 }} />
            </Button>
          )}
        </Space>
      </div>

      {/* Score + Stats Row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'stretch',
          gap: 20,
          backgroundColor: 'rgb(var(--theme-bg))',
          borderRadius: 18,
          border: '1px solid rgb(var(--theme-border))',
          padding: 24,
          overflow: 'hidden',
        }}
      >
        {/* 4 Stat Cards */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 12,
            flex: 1,
            alignContent: 'center',
          }}
        >
          <StatCard
            icon={<Target style={{ width: 16, height: 16 }} />}
            label="总规则"
            value={result.summary.total_rules}
            color="rgb(var(--theme-primary))"
          />
          <StatCard
            icon={<Award style={{ width: 16, height: 16 }} />}
            label="评级"
            value={result.grade}
            color={gradeColor}
          />
          <StatCard
            icon={<CheckCircle2 style={{ width: 16, height: 16 }} />}
            label="通过规则"
            value={result.summary.passed_rules}
            color="#52c41a"
            subText={`通过率 ${passRate}%`}
          />
          <StatCard
            icon={<XCircle style={{ width: 16, height: 16 }} />}
            label="失败规则"
            value={result.summary.failed_rules}
            color="#f5222d"
          />
        </div>

        {/* Score Circle */}
        {(() => {
          const cx = 60, cy = 60, r = 54, strokeWidth = 12;
          const progress = Math.min(result.quality_score / 100, 1);
          const startAngle = -Math.PI / 2; // 从12点钟方向开始

          // 计算终点角度（当进度为100%时，需要特殊处理绘制完整圆）
          let endAngle: number;
          let arcPath: string;
          let largeArcFlag: number;

          if (progress >= 1) {
            // 100%时，绘制完整圆（使用两个半圆拼接）
            endAngle = startAngle + 2 * Math.PI;
            largeArcFlag = 1;
            arcPath = `M ${cx + r} ${cy} A ${r} ${r} 0 1 1 ${cx - r - 0.001} ${cy} A ${r} ${r} 0 1 1 ${cx + r} ${cy}`;
          } else if (progress <= 0) {
            // 0%时，不绘制弧线
            arcPath = '';
            largeArcFlag = 0;
          } else {
            endAngle = startAngle + 2 * Math.PI * progress;
            largeArcFlag = progress > 0.5 ? 1 : 0;
            const startX = cx + r * Math.cos(startAngle);
            const startY = cy + r * Math.sin(startAngle);
            const endX = cx + r * Math.cos(endAngle);
            const endY = cy + r * Math.sin(endAngle);
            arcPath = `M ${startX} ${startY} A ${r} ${r} 0 ${largeArcFlag} 1 ${endX} ${endY}`;
          }

          const startX = cx + r * Math.cos(startAngle);
          const startY = cy + r * Math.sin(startAngle);

          return (
            <div
              style={{
                width: 120,
                height: 120,
                borderRadius: '50%',
                backgroundColor: 'rgb(var(--theme-bg))',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                alignSelf: 'center',
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              <svg
                width="120"
                height="120"
                style={{ position: 'absolute', top: 0, left: 0 }}
              >
                {/* 背景圆环 */}
                <circle
                  cx={cx}
                  cy={cy}
                  r={r}
                  fill="none"
                  stroke="rgba(0,0,0,0.06)"
                  strokeWidth={strokeWidth}
                />
                {/* 前景进度（开口圆弧，不包含端点） */}
                {arcPath && (
                  <path
                    d={arcPath}
                    fill="none"
                    stroke={gradeColor}
                    strokeWidth={strokeWidth}
                    strokeLinecap="butt"
                  />
                )}
                {/* 起点圆角 */}
                {progress > 0 && progress < 1 && (
                  <circle
                    cx={startX}
                    cy={startY}
                    r={strokeWidth / 2}
                    fill={gradeColor}
                  />
                )}
                {/* 终点圆角 */}
                {progress > 0 && progress < 1 && (
                  <circle
                    cx={cx + r * Math.cos(startAngle + 2 * Math.PI * progress)}
                    cy={cy + r * Math.sin(startAngle + 2 * Math.PI * progress)}
                    r={strokeWidth / 2}
                    fill={gradeColor}
                  />
                )}
                {/* 100%时显示两个端点 */}
                {progress >= 1 && (
                  <>
                    <circle cx={cx + r} cy={cy} r={strokeWidth / 2} fill={gradeColor} />
                    <circle cx={cx - r} cy={cy} r={strokeWidth / 2} fill={gradeColor} />
                  </>
                )}
              </svg>
              <div
                style={{
                  width: 96,
                  height: 96,
                  borderRadius: '50%',
                  backgroundColor: 'rgb(var(--theme-bg))',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  position: 'relative',
                  zIndex: 1,
                }}
              >
                <span
                  style={{ fontSize: 24, fontWeight: 800, color: gradeColor, lineHeight: 1 }}
                >
                  {result.quality_score.toFixed(1)}
                </span>
                <span style={{ fontSize: 11, color: 'rgb(var(--theme-text-muted))', marginTop: 2 }}>
                  质量分
                </span>
              </div>
            </div>
          );
        })()}
      </div>

      {/* Error rules row */}
      {result.summary.error_rules > 0 && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 16px',
            borderRadius: 12,
            backgroundColor: 'rgba(250, 173, 20, 0.08)',
            border: '1px solid rgba(250, 173, 20, 0.2)',
            fontSize: 13,
            color: '#faad14',
          }}
        >
          <AlertCircle style={{ width: 16, height: 16 }} />
          <span>
            有 <strong>{result.summary.error_rules}</strong> 条规则执行出错，请检查规则配置或目标表是否存在
          </span>
        </div>
      )}

      {/* Basic Audit - 基础质检概览 */}
      {result.basic_audit && (
        <div
          style={{
            borderRadius: 16,
            border: '1px solid rgb(var(--theme-border))',
            overflow: 'hidden',
            backgroundColor: 'rgb(var(--theme-bg))',
          }}
        >
          {/* Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '14px 18px',
              cursor: 'pointer',
              backgroundColor: 'rgba(var(--theme-primary), 0.04)',
            }}
            onClick={() => setBasicAuditExpanded(!basicAuditExpanded)}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <TableProperties style={{ width: 16, height: 16, color: 'rgb(var(--theme-primary))' }} />
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'rgb(var(--theme-text))', display: 'flex', alignItems: 'center', gap: 8 }}>
                  基础质检概览
                  <Tag style={{ margin: 0, fontSize: 11, padding: '0 6px', height: 20, lineHeight: '18px' }}>
                    {result.basic_audit.tables_count} 张表
                  </Tag>
                </div>
                <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', marginTop: 2 }}>
                  表级统计-数据完整性及质量概览
                </div>
              </div>
            </div>
            {basicAuditExpanded ? (
              <ChevronDown style={{ width: 18, height: 18, color: 'rgb(var(--theme-text-secondary))' }} />
            ) : (
              <ChevronRight style={{ width: 18, height: 18, color: 'rgb(var(--theme-text-secondary))' }} />
            )}
          </div>

          {/* Tables Detail */}
          {basicAuditExpanded && (
            <div style={{ padding: 16, maxHeight: 500, overflow: 'auto' }}>
              <div style={{ display: 'grid', gap: 12 }}>
                {result.basic_audit.tables.map((table, idx) => (
                  <div
                    key={idx}
                    style={{
                      borderRadius: 12,
                      border: '1px solid rgb(var(--theme-border))',
                      overflow: 'hidden',
                    }}
                  >
                    {/* Table Header */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        padding: '10px 14px',
                        backgroundColor: 'rgba(var(--theme-primary), 0.04)',
                        borderBottom: '1px solid rgb(var(--theme-border))',
                      }}
                    >
                      <Table2 style={{ width: 14, height: 14, color: 'rgb(var(--theme-primary))' }} />
                      <span style={{ fontWeight: 600, fontSize: 13, color: 'rgb(var(--theme-text))' }}>
                        {table.schema}.{table.table}
                      </span>
                      <Tag style={{ margin: 0, fontSize: 10 }}>{table.db_type}</Tag>
                      <span style={{ fontSize: 11, color: 'rgb(var(--theme-text-muted))', marginLeft: 'auto' }}>
                        {table.database}
                      </span>
                    </div>

                    {/* Column Reports */}
                    <div style={{ padding: 10 }}>
                      <Table
                        size="small"
                        pagination={false}
                        dataSource={table.report}
                        rowKey="column_name"
                        columns={[
                          {
                            title: '列名',
                            dataIndex: 'column_name',
                            key: 'column_name',
                            width: 120,
                            render: (col) => <span style={{ fontWeight: 500, fontSize: 12 }}>{col}</span>,
                          },
                          {
                            title: '数据类型',
                            dataIndex: 'data_type',
                            key: 'data_type',
                            width: 150,
                            render: (type) => <span style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))' }}>{type}</span>,
                          },
                          {
                            title: '总行数',
                            dataIndex: 'total_rows',
                            key: 'total_rows',
                            width: 80,
                            align: 'right',
                            render: (val) => <span style={{ fontSize: 12 }}>{formatNumber(val)}</span>,
                          },
                          {
                            title: '空值',
                            dataIndex: 'null_count',
                            key: 'null_count',
                            width: 70,
                            align: 'right',
                            render: (val, record) => (
                              <span style={{ fontSize: 12, color: val > 0 ? '#f5222d' : '#52c41a' }}>
                                {formatNumber(val)}
                              </span>
                            ),
                          },
                          {
                            title: '空串',
                            dataIndex: 'empty_str_count',
                            key: 'empty_str_count',
                            width: 70,
                            align: 'right',
                            render: (val) => (
                              <span style={{ fontSize: 12, color: val > 0 ? '#fa8c16' : 'rgb(var(--theme-text-secondary))' }}>
                                {formatNumber(val)}
                              </span>
                            ),
                          },
                          {
                            title: '缺失率',
                            dataIndex: 'missing_pct',
                            key: 'missing_pct',
                            width: 100,
                            align: 'right',
                            render: (pct) => {
                              const val = pct || 0
                              const color = val > 20 ? '#f5222d' : val > 5 ? '#faad14' : '#52c41a'
                              return (
                                <span style={{ fontSize: 12, fontWeight: 600, color }}>
                                  {val.toFixed(1)}%
                                </span>
                              )
                            },
                          },
                        ]}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Basic Audit Detail - 基础质检详情 */}
      {result.basic_audit_detail && result.basic_audit_detail.results && result.basic_audit_detail.results.length > 0 && (
        <div
          style={{
            borderRadius: 16,
            border: '1px solid #1890ff30',
            overflow: 'hidden',
            backgroundColor: 'rgb(var(--theme-bg))',
          }}
        >
          {/* Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '14px 18px',
              cursor: 'pointer',
              backgroundColor: 'rgba(24, 144, 255, 0.06)',
            }}
            onClick={() => setBasicAuditDetailExpanded(!basicAuditDetailExpanded)}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <Table2 style={{ width: 16, height: 16, color: '#1890ff' }} />
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'rgb(var(--theme-text))', display: 'flex', alignItems: 'center', gap: 8 }}>
                  基础质检执行明细
                  <Tag style={{ margin: 0, fontSize: 11, padding: '0 6px', height: 20, lineHeight: '18px', backgroundColor: '#1890ff15', borderColor: '#1890ff40', color: '#1890ff' }}>
                    {result.basic_audit_detail.results.length} 条检测
                  </Tag>
                </div>
                <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', marginTop: 2 }}>
                  全库表的空值检测详情（NULL、空字符串、缺失率）
                </div>
              </div>
            </div>
            {basicAuditDetailExpanded ? (
              <ChevronDown style={{ width: 18, height: 18, color: 'rgb(var(--theme-text-secondary))' }} />
            ) : (
              <ChevronRight style={{ width: 18, height: 18, color: 'rgb(var(--theme-text-secondary))' }} />
            )}
          </div>

          {/* Detail Content */}
          {basicAuditDetailExpanded && (
            <div style={{ padding: 16 }}>
              <div style={{ overflowX: 'auto', borderRadius: 14, border: '1px solid rgb(var(--theme-border))' }}>
                <Table
                  rowKey="id"
                  size="small"
                  pagination={{ pageSize: 10, showSizeChanger: false }}
                  scroll={{ x: 'max-content' }}
                  dataSource={result.basic_audit_detail.results}
                  columns={[
                  {
                    title: '状态',
                    dataIndex: 'status',
                    key: 'status',
                    width: 45,
                    align: 'center',
                    render: (status) => {
                      if (status === 'passed')
                        return (
                          <CheckCircle2 style={{ width: 16, height: 16, color: '#52c41a' }} />
                        )
                      if (status === 'failed')
                        return (
                          <XCircle style={{ width: 16, height: 16, color: '#f5222d' }} />
                        )
                      return (
                        <AlertCircle style={{ width: 16, height: 16, color: '#fa8c16' }} />
                      )
                    },
                  },
                  {
                    title: '规则名称',
                    dataIndex: 'rule_name',
                    key: 'rule_name',
                    width: 160,
                    minWidth: 120,
                    ellipsis: { showTitle: false },
                    render: (text) => (
                      <Tooltip title={text} placement="topLeft">
                        <span style={{ fontWeight: 500, fontSize: 12, whiteSpace: 'nowrap' }}>{text}</span>
                      </Tooltip>
                    ),
                  },
                  {
                    title: '类型',
                    dataIndex: 'rule_type',
                    key: 'rule_type',
                    width: 80,
                    render: (ruleType) => (
                      <Tag style={{ borderRadius: 6, margin: 0 }}>{getRuleDisplayName({ rule_type: ruleType })}</Tag>
                    ),
                  },
                  {
                    title: '目标表',
                    dataIndex: 'table_name',
                    key: 'table_name',
                    width: 140,
                    ellipsis: { showTitle: false },
                    render: (text) => (
                      <Tooltip title={text} placement="topLeft">
                        <span>{text}</span>
                      </Tooltip>
                    ),
                  },
                  {
                    title: '目标列',
                    dataIndex: 'column_name',
                    key: 'column_name',
                    width: 110,
                    ellipsis: { showTitle: false },
                    render: (value: string | null | undefined) =>
                      value ? (
                        <Tooltip title={value} placement="topLeft">
                          <span>{value}</span>
                        </Tooltip>
                      ) : (
                        <span style={{ color: 'rgb(var(--theme-text-muted))' }}>-</span>
                      ),
                  },
                  {
                    title: '失败率',
                    key: 'failed_rate',
                    width: 75,
                    align: 'right',
                    render: (_, record) => {
                      const rate = record.failed_rate ?? 0
                      const color = rate > 5 ? '#f5222d' : rate > 2 ? '#faad14' : '#52c41a'
                      return (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-end' }}>
                          <Progress
                            percent={Math.min(rate, 100)}
                            size="small"
                            strokeColor={color}
                            trailColor="rgba(0,0,0,0.06)"
                            showInfo={false}
                            style={{ width: 40, marginBottom: 0 }}
                          />
                          <span style={{ color, fontWeight: 600, minWidth: 42, textAlign: 'right', fontSize: 12 }}>
                            {rate.toFixed(2)}%
                          </span>
                        </div>
                      )
                    },
                  },
                  {
                    title: '失败/总数',
                    key: 'detail',
                    width: 80,
                    align: 'right',
                    render: (_, record) => (
                      <span style={{ color: 'rgb(var(--theme-text-secondary))', fontSize: 12 }}>
                        <span style={{ color: '#f5222d', fontWeight: 600 }}>{formatNumber(record.failed_count)}</span>
                        {' / '}
                        {formatNumber(record.total_count)}
                      </span>
                    ),
                  },
                  {
                    title: '执行耗时',
                    dataIndex: 'execution_time_ms',
                    key: 'execution_time_ms',
                    width: 80,
                    align: 'right',
                    render: (ms?: number) => {
                      if (ms === undefined || ms === null) {
                        return <span style={{ color: 'rgb(var(--theme-text-muted))', fontSize: 12 }}>-</span>
                      }
                      return (
                        <Tooltip title={`实际执行时间: ${ms}ms`}>
                          <span
                            style={{
                              color: 'rgb(var(--theme-text-secondary))',
                              fontSize: 12,
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 4,
                            }}
                          >
                            <Clock style={{ width: 11, height: 11 }} />
                            {formatExecutionTime(ms)}
                          </span>
                        </Tooltip>
                      )
                    },
                  },
                  {
                    title: '级别',
                    dataIndex: 'severity',
                    key: 'severity',
                    width: 70,
                    align: 'center',
                    render: (severity) => (
                      <Tag
                        color={severity === 'critical' ? 'red' : severity === 'warning' ? 'orange' : 'blue'}
                        style={{ borderRadius: 6, fontSize: 11, margin: 0 }}
                      >
                        {getSeverityDisplayName({ severity })}
                      </Tag>
                    ),
                  },
                  {
                    title: '详情',
                    key: 'expand',
                    width: 50,
                    align: 'center',
                    render: (_, record) => {
                      const hasDetail = record.executed_sql_text || record.error_message || (record.raw_result && Object.keys(record.raw_result).length > 0)
                      if (!hasDetail) {
                        return <span style={{ color: 'rgb(var(--theme-text-muted))', fontSize: 12 }}>无</span>
                      }
                      return (
                        <Button
                          type="text"
                          size="small"
                          icon={expandedRows.has(record.id) ? <ChevronDown style={{ width: 14, height: 14, color: 'rgb(var(--theme-text))' }} /> : <ChevronRight style={{ width: 14, height: 14, color: 'rgb(var(--theme-text))' }} />}
                          onClick={() => toggleExpand(record.id)}
                          style={{ padding: 4 }}
                        />
                      )
                    },
                  },
                ]}
                expandable={{
                  expandedRowKeys: Array.from(expandedRows),
                  expandRowByClick: false,
                  showExpandColumn: false,
                  expandedRowRender: (record) => {
                    return (
                      <div style={{ padding: '16px 20px', backgroundColor: 'rgba(var(--theme-bg-secondary), 0.5)' }}>
                        <div style={{ display: 'grid', gap: 16 }}>
                          {/* 执行耗时和执行模式信息 */}
                          {record.execution_time_ms !== undefined && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                              {record.rule_mode && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                  <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))' }}>执行模式：</span>
                                  <Tag
                                    style={{
                                      borderRadius: 6,
                                      margin: 0,
                                      backgroundColor: `${ruleModeColors[record.rule_mode] || '#999'}15`,
                                      borderColor: `${ruleModeColors[record.rule_mode] || '#999'}40`,
                                      color: ruleModeColors[record.rule_mode] || '#999',
                                      fontSize: 11,
                                    }}
                                  >
                                    {ruleModeLabels[record.rule_mode] || record.rule_mode}
                                  </Tag>
                                </div>
                              )}
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))' }}>执行耗时：</span>
                                <span style={{ fontSize: 13, color: 'rgb(var(--theme-text))', fontWeight: 500 }}>
                                  <Clock style={{ width: 12, height: 12, display: 'inline', marginRight: 4 }} />
                                  {formatExecutionTime(record.execution_time_ms)}
                                </span>
                              </div>
                            </div>
                          )}

                          {/* 执行SQL */}
                          {record.executed_sql_text && (
                            <div>
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                  <Terminal style={{ width: 14, height: 14, color: '#722ed1' }} />
                                  <span style={{ fontSize: 13, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>
                                    执行的 SQL
                                  </span>
                                </div>
                                <Button
                                  type="text"
                                  size="small"
                                  icon={<Copy style={{ width: 12, height: 12 }} />}
                                  onClick={() => copyToClipboard(record.executed_sql_text!)}
                                  style={{ fontSize: 12 }}
                                >
                                  复制
                                </Button>
                              </div>
                              <div
                                style={{
                                  padding: '12px 14px',
                                  borderRadius: 10,
                                  backgroundColor: 'rgb(var(--theme-bg))',
                                  border: '1px solid rgb(var(--theme-border))',
                                  fontFamily: 'Monaco, Consolas, "Courier New", monospace',
                                  fontSize: 12,
                                  color: 'rgb(var(--theme-text))',
                                  lineHeight: 1.6,
                                  maxHeight: 120,
                                  overflow: 'auto',
                                  whiteSpace: 'pre-wrap',
                                  wordBreak: 'break-all',
                                }}
                              >
                                {record.executed_sql_text}
                              </div>
                            </div>
                          )}

                          {/* 错误信息 */}
                          {record.status === 'error' && record.error_message && (
                            <div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                                <AlertCircle style={{ width: 14, height: 14, color: '#fa8c16' }} />
                                <span style={{ fontSize: 13, fontWeight: 600, color: '#fa8c16' }}>
                                  执行错误
                                </span>
                              </div>
                              <div
                                style={{
                                  padding: '12px 14px',
                                  borderRadius: 10,
                                  backgroundColor: 'rgba(250, 140, 22, 0.08)',
                                  border: '1px solid rgba(250, 140, 22, 0.2)',
                                  fontFamily: 'Monaco, Consolas, "Courier New", monospace',
                                  fontSize: 12,
                                  color: '#fa8c16',
                                  lineHeight: 1.6,
                                  maxHeight: 120,
                                  overflow: 'auto',
                                  whiteSpace: 'pre-wrap',
                                  wordBreak: 'break-all',
                                }}
                              >
                                {record.error_message}
                              </div>
                            </div>
                          )}

                          {/* 原始结果 */}
                          {record.raw_result && Object.keys(record.raw_result).length > 0 && (
                            <div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                                <Database style={{ width: 14, height: 14, color: '#722ed1' }} />
                                <span style={{ fontSize: 13, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>
                                  原始结果
                                </span>
                              </div>
                              <div
                                style={{
                                  padding: '12px 14px',
                                  borderRadius: 10,
                                  backgroundColor: 'rgb(var(--theme-bg))',
                                  border: '1px solid rgb(var(--theme-border))',
                                  fontFamily: 'Monaco, Consolas, "Courier New", monospace',
                                  fontSize: 12,
                                  color: 'rgb(var(--theme-text))',
                                  lineHeight: 1.6,
                                  maxHeight: 160,
                                  overflow: 'auto',
                                }}
                              >
                                <div style={{ display: 'grid', gap: 6 }}>
                                  {Object.entries(record.raw_result).map(([key, value]) => (
                                    <div key={key} style={{ display: 'flex', gap: 12 }}>
                                      <span style={{ color: '#722ed1', minWidth: 120, fontWeight: 500 }}>
                                        {key}:
                                      </span>
                                      <span style={{ color: 'rgb(var(--theme-text))', wordBreak: 'break-all' }}>
                                        {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value ?? '')}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  },
                  rowExpandable: (record) => !!(record.executed_sql_text || record.error_message || (record.raw_result && Object.keys(record.raw_result).length > 0) || record.execution_time_ms !== undefined),
                  onExpand: (expanded, record) => {
                    if (expanded) {
                      setExpandedRows((prev) => new Set(prev).add(record.id))
                    } else {
                      setExpandedRows((prev) => {
                        const next = new Set(prev)
                        next.delete(record.id)
                        return next
                      })
                    }
                  },
                }}
              />
            </div>
            </div>
          )}
        </div>
      )}

      {/* Relation discovery - 增强版 */}
      {result.relation_discovery && (
        <div
          style={{
            borderRadius: 16,
            border: '1px solid rgb(var(--theme-border))',
            overflow: 'hidden',
            backgroundColor: 'rgb(var(--theme-bg))',
          }}
        >
          {/* Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '14px 18px',
              cursor: 'pointer',
              backgroundColor: 'rgba(var(--theme-primary), 0.04)',
            }}
            onClick={() => setRelationDetailExpanded(!relationDetailExpanded)}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <Link2 style={{ width: 16, height: 16, color: 'rgb(var(--theme-primary))' }} />
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'rgb(var(--theme-text))', display: 'flex', alignItems: 'center', gap: 8 }}>
                  关系发现
                  <Tag style={{ margin: 0, fontSize: 11, padding: '0 6px', height: 20, lineHeight: '18px' }}>
                    {result.relation_discovery.relationships_count} 个关系
                  </Tag>
                </div>
                <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', marginTop: 2 }}>
                  覆盖 {result.relation_discovery.tables_count} 张表，生成 {result.relation_discovery.cards_count} 个卡片
                </div>
              </div>
            </div>
            {relationDetailExpanded ? (
              <ChevronDown style={{ width: 18, height: 18, color: 'rgb(var(--theme-text-secondary))' }} />
            ) : (
              <ChevronRight style={{ width: 18, height: 18, color: 'rgb(var(--theme-text-secondary))' }} />
            )}
          </div>

          {/* Detail Content */}
          {relationDetailExpanded && (
            <div style={{ padding: 16 }}>
              {/* Statistics */}
              {result.relation_discovery.statistics && (
                <div style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
                    <BarChart3 style={{ width: 14, height: 14, color: 'rgb(var(--theme-primary))' }} />
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>统计概览</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10 }}>
                    <StatCard icon={<Table2 style={{ width: 14, height: 14 }} />} label="总表数" value={result.relation_discovery.statistics.total_tables} color="#1890ff" />
                    <StatCard icon={<Link2 style={{ width: 14, height: 14 }} />} label="总关系数" value={result.relation_discovery.statistics.total_relationships} color="#722ed1" />
                    <StatCard icon={<TrendingUp style={{ width: 14, height: 14 }} />} label="平均置信度" value={result.relation_discovery.statistics.avg_confidence ? `${(result.relation_discovery.statistics.avg_confidence * 100).toFixed(1)}%` : '-'} color="#52c41a" />
                    <StatCard icon={<CheckCircle2 style={{ width: 14, height: 14 }} />} label="高置信关系" value={result.relation_discovery.statistics.high_confidence_count || 0} color="#52c41a" />
                  </div>

                  {/* Relationship Types */}
                  {result.relation_discovery.statistics.relationship_types && (
                    <div style={{ marginTop: 12 }}>
                      <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', marginRight: 12 }}>关系类型：</span>
                      {Object.entries(result.relation_discovery.statistics.relationship_types).map(([type, count]) => (
                        <Tag key={type} style={{ marginRight: 6, marginBottom: 4, fontSize: 11 }} color={relationshipTypeColors[type] ? undefined : 'default'}>
                          {relationshipTypeLabels[type] || type}: {count}
                        </Tag>
                      ))}
                    </div>
                  )}

                  {/* Cardinality Distribution */}
                  {result.relation_discovery.statistics.cardinality_distribution && (
                    <div style={{ marginTop: 10, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>基数分布：</span>
                      {result.relation_discovery.statistics.cardinality_distribution.many_to_one !== undefined && (
                        <span style={{ fontSize: 12 }}>
                          <strong style={{ color: cardinalityColors.many_to_one }}>{result.relation_discovery.statistics.cardinality_distribution.many_to_one}</strong> 多对一
                        </span>
                      )}
                      {result.relation_discovery.statistics.cardinality_distribution.one_to_many !== undefined && (
                        <span style={{ fontSize: 12 }}>
                          <strong style={{ color: cardinalityColors.one_to_many }}>{result.relation_discovery.statistics.cardinality_distribution.one_to_many}</strong> 一对多
                        </span>
                      )}
                      {result.relation_discovery.statistics.cardinality_distribution.one_to_one !== undefined && (
                        <span style={{ fontSize: 12 }}>
                          <strong style={{ color: cardinalityColors.one_to_one }}>{result.relation_discovery.statistics.cardinality_distribution.one_to_one}</strong> 一对一
                        </span>
                      )}
                      {result.relation_discovery.statistics.cardinality_distribution.many_to_many !== undefined && (
                        <span style={{ fontSize: 12 }}>
                          <strong style={{ color: cardinalityColors.many_to_many }}>{result.relation_discovery.statistics.cardinality_distribution.many_to_many}</strong> 多对多
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Relationships List */}
              {result.relation_discovery.relationships && result.relation_discovery.relationships.length > 0 && (
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
                    <Link2 style={{ width: 14, height: 14, color: 'rgb(var(--theme-primary))' }} />
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>关系详情</span>
                  </div>
                  <div style={{ display: 'grid', gap: 12, maxHeight: 500, overflow: 'auto' }}>
                    {result.relation_discovery.relationships.slice(0, 10).map((rel, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: '14px 16px',
                          borderRadius: 12,
                          backgroundColor: 'rgb(var(--theme-bg))',
                          border: '1px solid rgb(var(--theme-border))',
                        }}
                      >
                        {/* Header: 表名和关系类型 */}
                        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                            <Tag style={{ margin: 0, fontSize: 12, padding: '2px 10px', borderRadius: 4, backgroundColor: `${relationshipTypeColors[rel.relationship_type] || '#999'}15`, borderColor: `${relationshipTypeColors[rel.relationship_type] || '#999'}40`, color: relationshipTypeColors[rel.relationship_type] || '#999' }}>
                              {relationshipTypeLabels[rel.relationship_type] || rel.relationship_type}
                            </Tag>
                            <Tag style={{ margin: 0, fontSize: 11, padding: '2px 8px', borderRadius: 4 }} color={cardinalityColors[rel.cardinality] ? undefined : 'default'}>
                              {cardinalityLabels[rel.cardinality] || rel.cardinality}
                            </Tag>
                            <Tag color={rel.confidence >= 0.9 ? 'green' : rel.confidence >= 0.7 ? 'orange' : 'default'} style={{ margin: 0, fontSize: 11, padding: '2px 8px' }}>
                              置信度 {(rel.confidence * 100).toFixed(0)}%
                            </Tag>
                          </div>
                        </div>

                        {/* 表关系 */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10, flexWrap: 'wrap' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            <span style={{ fontSize: 11, color: 'rgb(var(--theme-text-muted))' }}>
                              {rel.from_datasource_name || '源表'}
                            </span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ fontSize: 14, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>
                                {rel.from_table}
                              </span>
                              <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>
                                {rel.from_column}
                              </span>
                            </div>
                          </div>
                          <ArrowRight style={{ width: 20, height: 20, color: 'rgb(var(--theme-text-muted))', flexShrink: 0 }} />
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            <span style={{ fontSize: 11, color: 'rgb(var(--theme-text-muted))' }}>
                              {rel.to_datasource_name || '目标表'}
                            </span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ fontSize: 14, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>
                                {rel.to_table}
                              </span>
                              <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>
                                {rel.to_column}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* 业务关系说明 */}
                        {rel.business_relation && (
                          <div style={{ marginBottom: 10, padding: '8px 12px', borderRadius: 8, backgroundColor: 'rgba(var(--theme-primary), 0.04)', border: '1px solid rgba(var(--theme-primary), 0.08)' }}>
                            <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', display: 'flex', alignItems: 'center', gap: 8 }}>
                              {rel.business_relation.from_entity && (
                                <span><strong style={{ color: 'rgb(var(--theme-text))' }}>{rel.business_relation.from_entity}</strong> ({rel.business_relation.from_role || 'detail'})</span>
                              )}
                              <span style={{ color: 'rgb(var(--theme-text-muted))' }}>→</span>
                              {rel.business_relation.to_entity && (
                                <span><strong style={{ color: 'rgb(var(--theme-text))' }}>{rel.business_relation.to_entity}</strong> ({rel.business_relation.to_role || 'master'})</span>
                              )}
                            </div>
                            {rel.business_relation.relation_description && (
                              <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', marginTop: 4 }}>
                                {rel.business_relation.relation_description}
                              </div>
                            )}
                          </div>
                        )}

                        {/* 推理说明 */}
                        {rel.reasoning && (
                          <div style={{ marginBottom: 10 }}>
                            <div style={{ fontSize: 12, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                              <FileText style={{ width: 12, height: 12 }} />
                              推理说明
                            </div>
                            <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', lineHeight: 1.6, maxHeight: 60, overflow: 'hidden' }}>
                              {rel.reasoning}
                            </div>
                          </div>
                        )}

                        {/* JOIN 建议 */}
                        {rel.join_suggestion && (
                          <div style={{ marginBottom: 10 }}>
                            <div style={{ fontSize: 12, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                              <Terminal style={{ width: 12, height: 12 }} />
                              建议 JOIN
                              {rel.join_suggestion.join_type && (
                                <Tag style={{ margin: 0, fontSize: 10, padding: '0 6px' }}>{rel.join_suggestion.join_type}</Tag>
                              )}
                            </div>
                            <div style={{ padding: '8px 12px', borderRadius: 8, backgroundColor: 'rgb(var(--theme-bg))', border: '1px solid rgb(var(--theme-border))', fontFamily: 'Monaco, Consolas, "Courier New", monospace', fontSize: 11, color: 'rgb(var(--theme-text))', lineHeight: 1.6, overflow: 'auto', maxHeight: 80, whiteSpace: 'pre-wrap' }}>
                              {rel.join_suggestion.sample_sql || rel.join_suggestion.join_condition}
                            </div>
                            {rel.join_suggestion.use_cases && rel.join_suggestion.use_cases.length > 0 && (
                              <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                                {rel.join_suggestion.use_cases.slice(0, 3).map((useCase, i) => (
                                  <span key={i} style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, backgroundColor: 'rgba(var(--theme-primary), 0.06)', color: 'rgb(var(--theme-text-secondary))' }}>
                                    {useCase}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        )}

                        {/* 融合建议 */}
                        {rel.fusion_suggestion && (rel.fusion_suggestion.aggregation_hint || rel.fusion_suggestion.fusion_strategy) && (
                          <div>
                            <div style={{ fontSize: 12, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                              <Database style={{ width: 12, height: 12 }} />
                              数据融合建议
                            </div>
                            <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', lineHeight: 1.6 }}>
                              {rel.fusion_suggestion.aggregation_hint && <div>{rel.fusion_suggestion.aggregation_hint}</div>}
                              {rel.fusion_suggestion.fusion_strategy && (
                                <div style={{ marginTop: 4, color: 'rgb(var(--theme-text-muted))' }}>
                                  {rel.fusion_suggestion.fusion_strategy}
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                    {result.relation_discovery.relationships.length > 10 && (
                      <div style={{ textAlign: 'center', padding: 12, color: 'rgb(var(--theme-text-muted))', fontSize: 12 }}>
                        还有 {result.relation_discovery.relationships.length - 10} 个关系...
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Execution Details Table - 基于规则库的质检执行明细 */}
      {(() => {
        // 只显示规则库质检的结果（排除基础空值检测）
        const ruleLibraryResults = executionResults.filter(r => r.execution_source !== 'basic_audit')

        if (ruleLibraryResults.length === 0) {
          return null
        }

        return (
          <div
            style={{
              borderRadius: 16,
              border: '1px solid #722ed140',
              overflow: 'hidden',
              backgroundColor: 'rgb(var(--theme-bg))',
            }}
          >
            {/* Header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '14px 18px',
                cursor: 'pointer',
                backgroundColor: 'rgba(114, 46, 209, 0.06)',
              }}
              onClick={() => setRuleLibraryExpanded(!ruleLibraryExpanded)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <ShieldCheck style={{ width: 16, height: 16, color: '#722ed1' }} />
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'rgb(var(--theme-text))', display: 'flex', alignItems: 'center', gap: 8 }}>
                    规则库质检执行明细
                    <Tag style={{ margin: 0, fontSize: 11, padding: '0 6px', height: 20, lineHeight: '18px', backgroundColor: '#722ed115', borderColor: '#722ed140', color: '#722ed1' }}>
                      {ruleLibraryResults.length} 条规则
                    </Tag>
                  </div>
                  <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', marginTop: 2 }}>
                    基于质检规则库的规则执行明细
                  </div>
                </div>
              </div>
              {ruleLibraryExpanded ? (
                <ChevronDown style={{ width: 18, height: 18, color: 'rgb(var(--theme-text-secondary))' }} />
              ) : (
                <ChevronRight style={{ width: 18, height: 18, color: 'rgb(var(--theme-text-secondary))' }} />
              )}
            </div>

            {/* Detail Content */}
            {ruleLibraryExpanded && (
              <div style={{ padding: 16 }}>
                <div style={{ overflowX: 'auto', borderRadius: 14, border: '1px solid rgb(var(--theme-border))' }}>
                  <Table<RuleExecutionResultDetail>
                    rowKey="id"
                    size="small"
                    columns={resultColumns}
                    dataSource={ruleLibraryResults}
                    pagination={ruleLibraryResults.length > 8 ? { pageSize: 8, showSizeChanger: false } : false}
                    scroll={{ x: 'max-content' }}
                    expandable={{
                      expandedRowKeys: Array.from(expandedRows),
                      expandRowByClick: false,
                      showExpandColumn: false,
                      expandedRowRender: (record) => {
                        return (
                          <div style={{ padding: '16px 20px', backgroundColor: 'rgba(var(--theme-bg-secondary), 0.5)' }}>
                    <div style={{ display: 'grid', gap: 16 }}>
                      {/* 执行耗时和执行模式信息 */}
                      {record.execution_time_ms !== undefined && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          {record.rule_mode && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginRight: 8 }}>
                              <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))' }}>执行模式：</span>
                              <Tag
                                style={{
                                  borderRadius: 6,
                                  margin: 0,
                                  backgroundColor: `${ruleModeColors[record.rule_mode] || '#999'}15`,
                                  borderColor: `${ruleModeColors[record.rule_mode] || '#999'}40`,
                                  color: ruleModeColors[record.rule_mode] || '#999',
                                  fontSize: 11,
                                }}
                              >
                                {ruleModeLabels[record.rule_mode] || record.rule_mode}
                              </Tag>
                            </div>
                          )}
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))' }}>执行耗时：</span>
                            <span style={{ fontSize: 13, color: 'rgb(var(--theme-text))', fontWeight: 500 }}>
                              <Clock style={{ width: 12, height: 12, display: 'inline', marginRight: 4 }} />
                              {formatExecutionTime(record.execution_time_ms)}
                            </span>
                          </div>
                        </div>
                      )}

                      {/* 执行SQL */}
                      {record.executed_sql_text && (
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                              <Terminal style={{ width: 14, height: 14, color: 'rgb(var(--theme-primary))' }} />
                              <span style={{ fontSize: 13, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>
                                执行的 SQL
                              </span>
                            </div>
                            <Button
                              type="text"
                              size="small"
                              icon={<Copy style={{ width: 12, height: 12 }} />}
                              onClick={() => copyToClipboard(record.executed_sql_text!)}
                              style={{ fontSize: 12 }}
                            >
                              复制
                            </Button>
                          </div>
                          <div
                            style={{
                              padding: '12px 14px',
                              borderRadius: 10,
                              backgroundColor: 'rgb(var(--theme-bg))',
                              border: '1px solid rgb(var(--theme-border))',
                              fontFamily: 'Monaco, Consolas, "Courier New", monospace',
                              fontSize: 12,
                              color: 'rgb(var(--theme-text))',
                              lineHeight: 1.6,
                              maxHeight: 120,
                              overflow: 'auto',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-all',
                            }}
                          >
                            {record.executed_sql_text}
                          </div>
                        </div>
                      )}

                      {/* 错误信息 */}
                      {record.status === 'error' && record.error_message && (
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                            <AlertCircle style={{ width: 14, height: 14, color: '#fa8c16' }} />
                            <span style={{ fontSize: 13, fontWeight: 600, color: '#fa8c16' }}>
                              执行错误
                            </span>
                          </div>
                          <div
                            style={{
                              padding: '12px 14px',
                              borderRadius: 10,
                              backgroundColor: 'rgba(250, 140, 22, 0.08)',
                              border: '1px solid rgba(250, 140, 22, 0.2)',
                              fontFamily: 'Monaco, Consolas, "Courier New", monospace',
                              fontSize: 12,
                              color: '#fa8c16',
                              lineHeight: 1.6,
                              maxHeight: 120,
                              overflow: 'auto',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-all',
                            }}
                          >
                            {record.error_message}
                          </div>
                        </div>
                      )}

                      {/* 原始结果 */}
                      {record.raw_result && Object.keys(record.raw_result).length > 0 && (
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                            <Database style={{ width: 14, height: 14, color: 'rgb(var(--theme-primary))' }} />
                            <span style={{ fontSize: 13, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>
                              原始结果
                            </span>
                          </div>
                          <div
                            style={{
                              padding: '12px 14px',
                              borderRadius: 10,
                              backgroundColor: 'rgb(var(--theme-bg))',
                              border: '1px solid rgb(var(--theme-border))',
                              fontFamily: 'Monaco, Consolas, "Courier New", monospace',
                              fontSize: 12,
                              color: 'rgb(var(--theme-text))',
                              lineHeight: 1.6,
                              maxHeight: 160,
                              overflow: 'auto',
                            }}
                          >
                            <div style={{ display: 'grid', gap: 6 }}>
                              {Object.entries(record.raw_result).map(([key, value]) => (
                                <div key={key} style={{ display: 'flex', gap: 12 }}>
                                  <span style={{ color: 'rgb(var(--theme-primary))', minWidth: 120, fontWeight: 500 }}>
                                    {key}:
                                  </span>
                                  <span style={{ color: 'rgb(var(--theme-text))', wordBreak: 'break-all' }}>
                                    {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value ?? '')}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* 失败样例 */}
                      {record.failed_samples && record.failed_samples.length > 0 && (
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
                            <XCircle style={{ width: 14, height: 14, color: '#f5222d' }} />
                            <span style={{ fontSize: 13, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>
                              失败样例
                            </span>
                            <Tag style={{ margin: 0, fontSize: 11, padding: '0 6px', height: 20, lineHeight: '18px' }} color="red">
                              {record.failed_samples.length} 条
                            </Tag>
                          </div>
                          <div style={{ display: 'grid', gap: 10, maxHeight: 400, overflow: 'auto' }}>
                            {record.failed_samples.map((sample, idx) => (
                              <div
                                key={idx}
                                style={{
                                  padding: '12px 14px',
                                  borderRadius: 10,
                                  backgroundColor: 'rgba(245, 34, 45, 0.04)',
                                  border: '1px solid rgba(245, 34, 45, 0.15)',
                                }}
                              >
                                {/* 样例标题 */}
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                    <span style={{
                                      width: 24,
                                      height: 24,
                                      borderRadius: '50%',
                                      backgroundColor: 'rgba(245, 34, 45, 0.1)',
                                      color: '#f5222d',
                                      display: 'flex',
                                      alignItems: 'center',
                                      justifyContent: 'center',
                                      fontSize: 12,
                                      fontWeight: 600,
                                    }}>
                                      {idx + 1}
                                    </span>
                                    {sample.condition_mode && (
                                      <Tag style={{ margin: 0, fontSize: 10 }} color="red">
                                        条件违反详情
                                      </Tag>
                                    )}
                                  </div>
                                </div>

                                {/* 违反的条件列表 */}
                                {sample.violated_conditions && sample.violated_conditions.length > 0 && (
                                  <div style={{ marginBottom: 10 }}>
                                    <div style={{ display: 'grid', gap: 8 }}>
                                      {sample.violated_conditions.map((vc, vcIdx) => (
                                        <div
                                          key={vcIdx}
                                          style={{
                                            padding: '10px 12px',
                                            borderRadius: 8,
                                            backgroundColor: 'rgba(245, 34, 45, 0.06)',
                                            border: '1px solid rgba(245, 34, 45, 0.12)',
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 16,
                                          }}
                                        >
                                          <div style={{ display: 'flex', alignItems: 'center', gap: 4, width: 160, flexShrink: 0 }}>
                                            <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))', flexShrink: 0 }}>字段/列名：</span>
                                            <span style={{
                                              fontSize: 12,
                                              flexShrink: 0,
                                              padding: '2px 8px',
                                              backgroundColor: 'rgba(24, 144, 255, 0.08)',
                                              color: 'rgb(var(--theme-color))',
                                              borderRadius: 4,
                                              border: '1px solid rgba(24, 144, 255, 0.2)',
                                              fontFamily: 'Monaco, Consolas, "Courier New", monospace',
                                            }}>
                                              {vc.column}
                                            </span>
                                          </div>
                                          <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1 }}>
                                            <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))', flexShrink: 0 }}>违反条件：</span>
                                            <div
                                              style={{
                                                fontFamily: 'Monaco, Consolas, "Courier New", monospace',
                                                fontSize: 12,
                                                color: '#cf1322',
                                                lineHeight: 1.5,
                                                wordBreak: 'break-all',
                                              }}
                                            >
                                              {vc.condition}
                                            </div>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}

                                {/* 样例数据（表格形式） */}
                                {sample.sample_value && Array.isArray(sample.sample_value) && sample.sample_value.length > 0 && (
                                  <div>
                                    <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-muted))', marginBottom: 8 }}>
                                      样例数据
                                    </div>
                                    <div style={{ overflowX: 'auto', borderRadius: 8, border: '1px solid rgb(var(--theme-border))' }}>
                                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                                        <thead>
                                          <tr style={{ backgroundColor: 'rgba(245, 34, 45, 0.08)' }}>
                                            <th style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: 'rgb(var(--theme-text))', borderBottom: '1px solid rgb(var(--theme-border))', whiteSpace: 'nowrap' }}>
                                              #
                                            </th>
                                            {Object.keys(sample.sample_value[0]).map((col) => (
                                              <th key={col} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: 'rgb(var(--theme-text))', borderBottom: '1px solid rgb(var(--theme-border))', whiteSpace: 'nowrap' }}>
                                                {col}
                                              </th>
                                            ))}
                                          </tr>
                                        </thead>
                                        <tbody>
                                          {sample.sample_value.map((row, rowIdx) => (
                                            <tr key={rowIdx} style={{ backgroundColor: rowIdx % 2 === 0 ? 'transparent' : 'rgba(0, 0, 0, 0.02)' }}>
                                              <td style={{ padding: '8px 12px', color: 'rgb(var(--theme-text-muted))', borderBottom: '1px solid rgb(var(--theme-border))' }}>
                                                {rowIdx + 1}
                                              </td>
                                              {Object.values(row).map((val, colIdx) => (
                                                <td key={colIdx} style={{ padding: '8px 12px', color: 'rgb(var(--theme-text))', borderBottom: '1px solid rgb(var(--theme-border))', wordBreak: 'break-all', maxWidth: 200 }}>
                                                  {formatValue(val)}
                                                </td>
                                              ))}
                                            </tr>
                                          ))}
                                        </tbody>
                                      </table>
                                    </div>
                                  </div>
                                )}

                                {/* 样例数据（非数组，兼容旧格式） */}
                                {sample.sample_value && !Array.isArray(sample.sample_value) && typeof sample.sample_value === 'object' && (
                                  <div>
                                    <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-muted))', marginBottom: 6 }}>
                                      样例数据
                                    </div>
                                    <div
                                      style={{
                                        display: 'grid',
                                        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                                        gap: 8,
                                      }}
                                    >
                                      {Object.entries(sample.sample_value).map(([key, value]) => (
                                        <div
                                          key={key}
                                          style={{
                                            padding: '8px 10px',
                                            borderRadius: 6,
                                            backgroundColor: 'rgb(var(--theme-bg))',
                                            border: '1px solid rgb(var(--theme-border))',
                                          }}
                                        >
                                          <div style={{ fontSize: 10, color: 'rgb(var(--theme-text-muted))', marginBottom: 2 }}>
                                            {key}
                                          </div>
                                          <div style={{ fontSize: 13, fontWeight: 500, color: 'rgb(var(--theme-text))', wordBreak: 'break-all' }}>
                                            {formatValue(value)}
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )
              },
              rowExpandable: (record) => {
                return !!(record.executed_sql_text || record.error_message || (record.raw_result && Object.keys(record.raw_result).length > 0) || (record.failed_samples && record.failed_samples.length > 0))
              },
            }}
            />
            </div>
          </div>
        )}
      </div>
    )
  })()}

</div>
)
}

export default ExecutionResultPanel
