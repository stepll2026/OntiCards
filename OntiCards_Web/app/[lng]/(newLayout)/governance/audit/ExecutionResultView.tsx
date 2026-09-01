'use client'

import React, { useState } from 'react'
import { ArrowRight, ExternalLink, Link2, Table2 } from 'lucide-react'
import { Empty, Statistic, Row, Col, Card, Table, Space, Button, Tag, Tooltip } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  BasicAuditData,
  RelationDiscoveryDetail,
  RuleExecutionResultDetail,
  getGradeName,
  getGradeColor,
  getRuleDisplayName,
  getSeverityDisplayName,
  severityColors,
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
  basic_audit?: BasicAuditData
  quality_audit?: {
    rules_count: number
    results: RuleExecutionResultDetail[]
  }
  basic_audit_detail?: {
    tables_count: number
    results: RuleExecutionResultDetail[]
  }
  relation_discovery?: RelationDiscoveryDetail
  results?: RuleExecutionResultDetail[]
}

interface ExecutionResultViewProps {
  result: ExecutionResult
  onGenerateReport: () => void
  onDownloadReport: () => void
  onViewDetails: () => void
  reportLoading: boolean
}

const formatNumber = (value?: number | null) => {
  if (value === undefined || value === null) return '-'
  return new Intl.NumberFormat('zh-CN').format(value)
}

const ExecutionResultPanel = ({ result, onGenerateReport, onDownloadReport, onViewDetails, reportLoading }: ExecutionResultViewProps) => {
  // 兼容新版 quality_audit.results 和旧版 results
  const executionResults = result.quality_audit?.results || result.results || []

  const resultColumns: ColumnsType<RuleExecutionResultDetail> = [
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 70,
      render: (status) => {
        const label = status === 'passed' ? '通过' : status === 'failed' ? '失败' : '错误'
        return <span style={{ color: status === 'passed' ? '#52c41a' : status === 'failed' ? '#f5222d' : '#999', fontSize: 12 }}>{label}</span>
      },
    },
    {
      title: '规则',
      dataIndex: 'rule_name',
      key: 'rule_name',
      ellipsis: true,
    },
    {
      title: '类型',
      dataIndex: 'rule_type',
      key: 'rule_type',
      width: 90,
      render: (ruleType) => <span style={{ fontSize: 12 }}>{getRuleDisplayName({ rule_type: ruleType })}</span>,
    },
    {
      title: '来源',
      dataIndex: 'execution_source',
      key: 'execution_source',
      width: 90,
      render: (source) => {
        if (!source) return <span style={{ color: 'rgb(var(--theme-text-muted))', fontSize: 12 }}>-</span>
        return (
          <Tag style={{ margin: 0, borderRadius: 6, backgroundColor: `${executionSourceColors[source]}15`, borderColor: `${executionSourceColors[source]}40`, color: executionSourceColors[source], fontSize: 10 }}>
            {executionSourceLabels[source] || source}
          </Tag>
        )
      },
    },
    {
      title: '目标表',
      dataIndex: 'table_name',
      key: 'table_name',
      width: 100,
      ellipsis: true,
    },
    {
      title: '目标列',
      dataIndex: 'column_name',
      key: 'column_name',
      width: 80,
      ellipsis: true,
      render: (value: string | null) => (value ? value : '-'),
    },
    {
      title: '失败率',
      dataIndex: 'failed_rate',
      key: 'failed_rate',
      width: 80,
      align: 'right',
      render: (value: number) => <span style={{ color: value > 5 ? '#f5222d' : 'rgb(var(--theme-text))', fontSize: 12 }}>{value.toFixed(2)}%</span>,
    },
    {
      title: '失败/总数',
      key: 'ratio',
      width: 100,
      align: 'right',
      render: (_, record) => (
        <span style={{ fontSize: 12 }}>
          {formatNumber(record.failed_count)} / {formatNumber(record.total_count)}
        </span>
      ),
    },
    {
      title: '严重级别',
      dataIndex: 'severity',
      key: 'severity',
      width: 70,
      render: (severity) => (
        <span style={{ color: severityColors[severity] || '#999', fontSize: 12 }}>{getSeverityDisplayName({ severity })}</span>
      ),
    },
  ]

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h3 style={{ fontSize: 18, fontWeight: 600, color: 'rgb(var(--theme-text))', margin: 0 }}>执行结果</h3>
          <p style={{ color: 'rgb(var(--theme-text-secondary))', marginTop: 4, fontSize: 14 }}>
            执行完成后结果已呈现，您可继续生成报告或下载。
          </p>
        </div>
        <Space>
          <Button
            type="primary"
            onClick={onGenerateReport}
            loading={reportLoading}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            生成报告
            <ArrowRight style={{ width: 16, height: 16 }} />
          </Button>
          <Button
            onClick={onDownloadReport}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            下载报告
            <ExternalLink style={{ width: 16, height: 16 }} />
          </Button>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        <Col span={8}>
          <Card size="small">
            <Statistic title="质量评分" value={result.quality_score} precision={1} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="总规则" value={result.summary.total_rules} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="失败规则" value={result.summary.failed_rules} valueStyle={{ color: '#f5222d' }} />
          </Card>
        </Col>
      </Row>

      {result.relation_discovery && (
        <Card
          size="small"
          title={
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <Link2 style={{ width: 16, height: 16 }} />
              关系发现汇总
            </span>
          }
        >
          <Row gutter={[16, 8]}>
            <Col span={8}>
              <Statistic title="总关系" value={result.relation_discovery.relationships_count} />
            </Col>
            <Col span={8}>
              <Statistic title="总表" value={result.relation_discovery.tables_count} />
            </Col>
            <Col span={8}>
              <Statistic title="卡片数" value={result.relation_discovery.cards_count} />
            </Col>
          </Row>
        </Card>
      )}

      {/* 基础空值检测详情 */}
      {result.basic_audit_detail && result.basic_audit_detail.results && result.basic_audit_detail.results.length > 0 && (
        <Card
          size="small"
          title={
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <Table2 style={{ width: 16, height: 16, color: '#722ed1' }} />
              基础质检执行明细
              <Tag style={{ margin: 0, fontSize: 11, backgroundColor: '#722ed115', borderColor: '#722ed140', color: '#722ed1' }}>
                {result.basic_audit_detail.results.length} 条检测
              </Tag>
            </span>
          }
          style={{ borderColor: '#722ed140' }}
        >
          <Table<RuleExecutionResultDetail>
            rowKey="id"
            size="small"
            dataSource={result.basic_audit_detail.results}
            pagination={{ pageSize: 5, showSizeChanger: false }}
            scroll={{ x: 950 }}
            columns={[
              {
                title: '状态',
                dataIndex: 'status',
                key: 'status',
                width: 80,
                render: (status) => {
                  const label = status === 'passed' ? '通过' : status === 'failed' ? '失败' : '错误'
                  return <span style={{ color: status === 'passed' ? '#52c41a' : status === 'failed' ? '#f5222d' : '#999', fontSize: 14 }}>{label}</span>
                },
              },
              {
                title: '规则名称',
                dataIndex: 'rule_name',
                key: 'rule_name',
                ellipsis: true,
                render: (text) => <Tooltip title={text}><span style={{ fontSize: 14 }}>{text}</span></Tooltip>,
              },
              {
                title: '目标表',
                dataIndex: 'table_name',
                key: 'table_name',
                width: 130,
                ellipsis: true,
              },
              {
                title: '目标列',
                dataIndex: 'column_name',
                key: 'column_name',
                width: 100,
                ellipsis: true,
                render: (value: string | null) => value || '-',
              },
              {
                title: '失败率',
                dataIndex: 'failed_rate',
                key: 'failed_rate',
                width: 80,
                align: 'right',
                render: (value: number) => <span style={{ color: value > 5 ? '#f5222d' : 'rgb(var(--theme-text))', fontSize: 14 }}>{value.toFixed(2)}%</span>,
              },
              {
                title: '失败/总数',
                key: 'ratio',
                width: 100,
                align: 'right',
                render: (_, record) => (
                  <span style={{ fontSize: 12 }}>
                    <span style={{ color: '#f5222d', fontWeight: 600 }}>{formatNumber(record.failed_count)}</span> / {formatNumber(record.total_count)}
                  </span>
                ),
              },
              {
                title: '耗时',
                dataIndex: 'execution_time_ms',
                key: 'execution_time_ms',
                width: 70,
                align: 'right',
                render: (ms?: number) => {
                  if (ms === undefined || ms === null) return <span style={{ color: 'rgb(var(--theme-text-muted))', fontSize: 12 }}>-</span>
                  if (ms < 1000) return <span style={{ fontSize: 12 }}>{ms}ms</span>
                  return <span style={{ fontSize: 12 }}>{(ms / 1000).toFixed(2)}s</span>
                },
              },
              {
                title: '级别',
                dataIndex: 'severity',
                key: 'severity',
                width: 70,
                render: (severity) => (
                  <Tag color={severity === 'critical' ? 'red' : severity === 'warning' ? 'orange' : 'blue'} style={{ margin: 0, fontSize: 11 }}>
                    {getSeverityDisplayName({ severity })}
                  </Tag>
                ),
              },
            ]}
          />
        </Card>
      )}

      <Card size="small" title={
        <span>基于规则库的质检执行明细</span>
      }>
        {(() => {
          const ruleLibraryResults = executionResults.filter(r => r.execution_source !== 'basic_audit')
          if (ruleLibraryResults.length === 0) {
            return <Empty description="暂无规则库质检结果" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          }
          return (
            <div style={{ overflowX: 'auto' }}>
        <Table<RuleExecutionResultDetail>
          rowKey="id"
          size="small"
          columns={resultColumns}
          dataSource={ruleLibraryResults}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          scroll={{ x: 850 }}
          expandable={{
            expandedRowRender: (record) => {
              if (!record.failed_samples || record.failed_samples.length === 0) {
                return <Empty description="暂无失败样本" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              }
              return (
                <div style={{ padding: '12px 24px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                    <span style={{ fontWeight: 600, color: 'rgb(var(--theme-text))' }}>失败样例</span>
                    <Tag style={{ margin: 0, fontSize: 11 }} color="red">{record.failed_samples.length} 条</Tag>
                  </div>
                  {record.failed_samples.map((sample, index) => (
                    <div
                      key={index}
                      style={{
                        padding: '12px 14px',
                        borderRadius: 10,
                        backgroundColor: 'rgba(245, 34, 45, 0.04)',
                        border: '1px solid rgba(245, 34, 45, 0.15)',
                        marginBottom: 10,
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
                            {index + 1}
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
                                        {typeof val === 'object' ? JSON.stringify(val) : String(val ?? '-')}
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
                                  {typeof value === 'object' ? JSON.stringify(value) : String(value ?? '-')}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )
            },
            rowExpandable: (record) => record.status !== 'passed' && record.failed_samples && record.failed_samples.length > 0,
          }}
        />
            </div>
          )
        })()}
      </Card>
    </div>
  )
}

export default ExecutionResultPanel
