'use client'

import React, { useEffect, useState, Suspense, useMemo } from 'react'
import { useRouter } from 'next-nprogress-bar'
import { useParams, useSearchParams } from 'next/navigation'
import {
  ArrowLeft,
  Download,
  FileText,
  Loader2,
  Sparkles,
  Database,
  Table2,
  Link2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Shield,
  ShieldCheck,
  ChevronDown,
  ChevronRight,
  Copy,
  Terminal,
  Clock,
  BookOpen,
  Key,
  Hash,
  FileUp,
  RefreshCw,
  Trash2,
} from 'lucide-react'
import { message, Tag, Table, Modal, Tooltip, Button, Radio, Input } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  getGovernanceReportDetail,
  downloadGovernanceReport,
  generateGovernanceReportV2,
  getGovernanceReportStatus,
  GovernanceReportDetail,
  HistoryFile,
  deleteGovernanceReportFile,
  deleteGovernanceReport,
  updateGovernanceReportName,
  ruleModeLabels,
} from '@/api/governance'

// 关系类型标签和颜色
const relationshipTypeLabels: Record<string, string> = {
  'one_to_one': '一对一',
  'one_to_many': '一对多',
  'many_to_one': '多对一',
  'many_to_many': '多对多',
  'shared_field': '共享字段',
  'foreign_key': '外键关联',
}

const relationshipTypeColors: Record<string, string> = {
  'one_to_one': '#1890ff',
  'one_to_many': '#722ed1',
  'many_to_one': '#fa8c16',
  'many_to_many': '#eb2f96',
  'shared_field': '#52c41a',
  'foreign_key': '#f5222d',
}

// 规则类型标签
const ruleTypeLabels: Record<string, string> = {
  'null_check': '空值检测',
  'unique': '唯一性检测',
  'format': '格式检测',
  'threshold': '阈值检测',
  'enum': '枚举检测',
  'custom_sql': '自定义SQL',
  'length_check': '长度检测',
  'range_check': '范围检测',
  'date_check': '日期检测',
  'consistency_check': '一致性检测',
  'freshness_check': '新鲜度检测',
  'value_distribution': '值分布',
  'composite': '复合规则',
  'basic_null_check': '基础质检',
  'table_stats': '表级统计',
}

// 级别标签
const severityLabels: Record<string, string> = {
  'critical': '严重',
  'warning': '警告',
  'info': '信息',
}

// 基数标签
const cardinalityLabels: Record<string, string> = {
  'one_to_one': '一对一',
  'one_to_many': '一对多',
  'many_to_one': '多对一',
  'many_to_many': '多对多',
}

// 格式化工具
const formatNumber = (value?: number | null) => {
  if (value === undefined || value === null) return '-'
  return new Intl.NumberFormat('zh-CN').format(value)
}

const formatExecutionTime = (ms?: number) => {
  if (ms === undefined || ms === null) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

// 使用类型别名，方便后续扩展
export type ExtendedGovernanceReportDetail = GovernanceReportDetail

// 评分环形图 - 优化居中
const ScoreRing = ({ score, size = 70 }: { score: number; size?: number }) => {
  const grade = score >= 90 ? '优秀' : score >= 75 ? '良好' : score >= 60 ? '一般' : score >= 40 ? '较差' : '差'
  const color = score >= 90 ? '#52c41a' : score >= 75 ? '#1890ff' : score >= 60 ? '#faad14' : score >= 40 ? '#fa8c16' : '#f5222d'
  const cx = 35, cy = 35, r = 30, strokeWidth = 6
  const progress = Math.min(score / 100, 1)
  const startAngle = -Math.PI / 2

  // 计算终点角度（当进度为100%时，需要特殊处理绘制完整圆）
  let endAngle: number
  let arcPath: string
  let largeArcFlag: number

  if (progress >= 1) {
    // 100%时，绘制完整圆（使用两个半圆拼接）
    endAngle = startAngle + 2 * Math.PI
    largeArcFlag = 1
    arcPath = `M ${cx + r} ${cy} A ${r} ${r} 0 1 1 ${cx - r - 0.001} ${cy} A ${r} ${r} 0 1 1 ${cx + r} ${cy}`
  } else if (progress <= 0) {
    // 0%时，不绘制弧线
    arcPath = ''
    largeArcFlag = 0
  } else {
    endAngle = startAngle + 2 * Math.PI * progress
    largeArcFlag = progress > 0.5 ? 1 : 0
    const startX = cx + r * Math.cos(startAngle)
    const startY = cy + r * Math.sin(startAngle)
    const endX = cx + r * Math.cos(endAngle)
    const endY = cy + r * Math.sin(endAngle)
    arcPath = `M ${startX} ${startY} A ${r} ${r} 0 ${largeArcFlag} 1 ${endX} ${endY}`
  }

  const startX = cx + r * Math.cos(startAngle)
  const startY = cy + r * Math.sin(startAngle)

  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(0,0,0,0.05)" strokeWidth={strokeWidth} />
        {arcPath && <path d={arcPath} fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="butt" />}
        {progress > 0 && progress < 1 && (
          <circle cx={startX} cy={startY} r={strokeWidth / 2} fill={color} />
        )}
        {progress >= 1 && (
          <>
            <circle cx={cx + r} cy={cy} r={strokeWidth / 2} fill={color} />
            <circle cx={cx - r} cy={cy} r={strokeWidth / 2} fill={color} />
          </>
        )}
      </svg>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontSize: 16, fontWeight: 700, color, lineHeight: 1 }}>{score.toFixed(1)}</span>
      </div>
    </div>
  )
}

// 关系卡片 - 优化显示更多内容
const RelationCard = ({ card, onClick }: { card: any; onClick: () => void }) => {
  const { DocInfo, TableInfo, Statistics, Relationships } = card
  const confidence = Statistics?.avg_confidence || 0
  const confidenceColor = confidence >= 0.9 ? '#52c41a' : confidence >= 0.7 ? '#faad14' : '#f5222d'

  // 获取关联的表名和关系类型
  const relationSummary = Relationships?.slice(0, 3).map((r: any) => ({
    table: r.related_table,
    type: relationshipTypeLabels[r.relationship_type] || r.relationship_type,
    color: relationshipTypeColors[r.relationship_type] || '#999',
    field: r.join_fields?.[0] ? `${r.join_fields[0].local_field} = ${r.join_fields[0].remote_field}` : ''
  })) || []

  return (
    <div
      onClick={onClick}
      style={{
        padding: '14px 16px',
        borderRadius: 10,
        border: '1px solid rgb(var(--theme-border))',
        backgroundColor: 'rgb(var(--theme-bg))',
        cursor: 'pointer',
        transition: 'all 0.2s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = 'rgb(var(--theme-primary))'
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(var(--theme-primary), 0.15)'
        e.currentTarget.style.transform = 'translateY(-2px)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'rgb(var(--theme-border))'
        e.currentTarget.style.boxShadow = 'none'
        e.currentTarget.style.transform = 'translateY(0)'
      }}
    >
      {/* 表名和主键 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <div style={{ width: 32, height: 32, borderRadius: 8, backgroundColor: 'rgba(var(--theme-primary), 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgb(var(--theme-primary))' }}>
          <Database style={{ width: 16, height: 16 }} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, color: 'rgb(var(--theme-text))', fontSize: 14, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {DocInfo.table_name}
          </div>
          <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-muted))', display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
            <span>{TableInfo.fields_count} 字段</span>
            {TableInfo.primary_key && (
              <>
                <span>·</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Key style={{ width: 10, height: 10 }} />
                  {TableInfo.primary_key}
                </span>
              </>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}>
          <Tag style={{ fontSize: 11, margin: 0, padding: '0 6px', height: 20 }}>{Relationships?.length || 0} 关联</Tag>
          <span style={{ fontSize: 13, fontWeight: 700, color: confidenceColor }}>{(confidence * 100).toFixed(0)}%</span>
        </div>
      </div>

      {/* 关联摘要 */}
      {relationSummary.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {relationSummary.map((rel: any, idx: number) => (
            <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
              <Tag style={{ margin: 0, padding: '0 4px', height: 18, fontSize: 10, backgroundColor: `${rel.color}15`, borderColor: `${rel.color}40`, color: rel.color }}>
                {rel.type}
              </Tag>
              <span style={{ color: 'rgb(var(--theme-text))', fontWeight: 500, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {rel.table}
              </span>
              {rel.field && (
                <span style={{ color: 'rgb(var(--theme-text-muted))', fontFamily: 'monospace', fontSize: 10 }}>
                  {rel.field}
                </span>
              )}
            </div>
          ))}
          {Relationships?.length > 3 && (
            <div style={{ fontSize: 10, color: 'rgb(var(--theme-text-muted))', marginTop: 2 }}>
              还有 {Relationships.length - 3} 个关联...
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// 关系详情弹框 - 每个字段对独立显示，带表名
const RelationDetailModal = ({ card, allRelationships, open, onClose }: { card: any; allRelationships: any[]; open: boolean; onClose: () => void }) => {
  if (!card) return null
  const { DocInfo, TableInfo, Statistics, Relationships, JoinSummary, FusionHints } = card
  const sourceTable = DocInfo.table_name

  // 展开每个 join_field 为独立的卡片，并匹配对应的完整关系信息（包含 reasoning 和 join_suggestion）
  const getFullRelationForField = (localField: string, remoteField: string, targetTable: string) => {
    if (!allRelationships?.length) return null
    return allRelationships.find((r) =>
      r.from_table === sourceTable &&
      r.to_table === targetTable &&
      r.from_column === localField
    )
  }

  // 构建每个字段对的详情 - 按目标表分组
  const groupedFieldPairs = useMemo(() => {
    const groups: Record<string, any[]> = {}
    Relationships?.forEach((rel: any) => {
      const targetTable = rel.related_table
      rel.join_fields?.forEach((jf: any) => {
        const fullRel = getFullRelationForField(jf.local_field, jf.remote_field, targetTable)
        if (!groups[targetTable]) groups[targetTable] = []
        groups[targetTable].push({
          localField: jf.local_field,
          remoteField: jf.remote_field,
          relationshipType: jf.relationship_type || rel.relationship_type,
          confidence: jf.confidence || rel.confidence,
          cardinality: rel.cardinality,
          evidence: rel.evidence,
          businessRelation: rel.business_relation,
          // 优先使用 fullRel 中的 join_suggestion，否则使用 rel 中的
          joinSuggestion: fullRel?.join_suggestion || rel.join_suggestion,
          fusionSuggestion: rel.fusion_suggestion,
          reasoning: fullRel?.reasoning || rel.reasoning,
        })
      })
    })
    return Object.entries(groups).map(([targetTable, pairs]) => ({ targetTable, pairs }))
  }, [Relationships, allRelationships, sourceTable])

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={1000}
      centered
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, backgroundColor: 'rgba(var(--theme-primary), 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgb(var(--theme-primary))' }}>
            <Database style={{ width: 18, height: 18 }} />
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 15 }}>{sourceTable}</div>
            <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-muted))' }}>
              {TableInfo.fields_count} 字段 · 主键: {TableInfo.primary_key || '无'}
            </div>
          </div>
        </div>
      }
      styles={{ body: { padding: '16px 20px', maxHeight: '78vh', overflow: 'auto' } }}
    >
      <div style={{ display: 'grid', gap: 16 }}>
        {/* 统计信息 - 紧凑 */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
          <div style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))', textAlign: 'center' }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: 'rgb(var(--theme-primary))' }}>{Statistics?.related_tables_count || 0}</div>
            <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', marginTop: 2 }}>关联表数</div>
          </div>
          <div style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))', textAlign: 'center' }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: 'rgb(var(--theme-primary))' }}>{Statistics?.total_join_fields || 0}</div>
            <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', marginTop: 2 }}>关联字段数</div>
          </div>
          <div style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))', textAlign: 'center' }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#52c41a' }}>{((Statistics?.avg_confidence || 0) * 100).toFixed(0)}%</div>
            <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', marginTop: 2 }}>平均置信度</div>
          </div>
        </div>

        {/* 关系摘要 */}
        {JoinSummary && (
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
              <BookOpen style={{ width: 14, height: 14, color: 'rgb(var(--theme-primary))' }} />
              关系摘要
            </div>
            <div style={{ padding: '12px 14px', borderRadius: 8, backgroundColor: 'rgb(var(--theme-bg-secondary))', fontSize: 12, color: 'rgb(var(--theme-text))', lineHeight: 1.7 }}>
              {JoinSummary}
            </div>
          </div>
        )}

        {/* 融合建议 */}
        {FusionHints && (FusionHints.as_master?.length || FusionHints.as_detail?.length || FusionHints.common_joins?.length) && (
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Link2 style={{ width: 14, height: 14, color: 'rgb(var(--theme-primary))' }} />
              融合建议
            </div>
            <div style={{ display: 'grid', gap: 8 }}>
              {FusionHints.as_master?.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ width: 5, height: 5, borderRadius: '50%', backgroundColor: '#52c41a' }} />
                    作为主表时
                  </div>
                  {FusionHints.as_master.map((hint, i) => (
                    <div key={i} style={{ padding: '8px 10px', borderRadius: 6, backgroundColor: 'rgba(82, 196, 26, 0.06)', fontSize: 11, color: 'rgb(var(--theme-text-secondary))', marginBottom: 4, lineHeight: 1.5 }}>{hint}</div>
                  ))}
                </div>
              )}
              {FusionHints.as_detail?.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ width: 5, height: 5, borderRadius: '50%', backgroundColor: '#1890ff' }} />
                    作为明细表时
                  </div>
                  {FusionHints.as_detail.map((hint, i) => (
                    <div key={i} style={{ padding: '8px 10px', borderRadius: 6, backgroundColor: 'rgba(24, 144, 255, 0.06)', fontSize: 11, color: 'rgb(var(--theme-text-secondary))', marginBottom: 4, lineHeight: 1.5 }}>{hint}</div>
                  ))}
                </div>
              )}
              {FusionHints.common_joins?.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Hash style={{ width: 11, height: 11, color: 'rgb(var(--theme-primary))' }} />
                    常用查询场景
                  </div>
                  {FusionHints.common_joins.map((hint, i) => (
                    <div key={i} style={{ padding: '8px 10px', borderRadius: 6, backgroundColor: 'rgba(var(--theme-primary), 0.04)', fontSize: 11, color: 'rgb(var(--theme-text-secondary))', marginBottom: 4, lineHeight: 1.5 }}>{hint}</div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* 关系详情列表 - 按目标表分组，表对和字段对在同一区域内显示 */}
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'rgb(var(--theme-text))', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Link2 style={{ width: 14, height: 14, color: 'rgb(var(--theme-primary))' }} />
            关联关系详情 ({groupedFieldPairs.reduce((acc, g) => acc + g.pairs.length, 0)} 个字段对)
          </div>

          {groupedFieldPairs.map(({ targetTable, pairs }) => (
            <div key={targetTable} style={{ marginBottom: 16 }}>
              {/* 表对和字段对的大容器 */}
              <div style={{ border: '1px solid rgba(var(--theme-primary), 0.15)', borderRadius: 10, overflow: 'hidden' }}>
                {/* 表对标题 - 容器顶部标题栏 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', backgroundColor: 'rgba(var(--theme-primary), 0.05)', borderBottom: '1px solid rgba(var(--theme-primary), 0.1)' }}>
                  <Database style={{ width: 14, height: 14, color: 'rgb(var(--theme-primary))' }} />
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>{sourceTable}</span>
                  <Terminal style={{ width: 14, height: 14, color: 'rgb(var(--theme-primary))' }} />
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'rgb(var(--theme-primary))' }}>{targetTable}</span>
                  <Tag style={{ margin: 0, fontSize: 10, marginLeft: 'auto' }}>{pairs.length} 个字段对</Tag>
                </div>

                {/* 字段对卡片列表 */}
                <div style={{ padding: 12 }}>
                  {pairs.map((pair: any, idx: number) => {
                    const relTypeColor = relationshipTypeColors[pair.relationshipType] || '#999'
                    const isLast = idx === pairs.length - 1

                    return (
                      <div key={idx} style={{ padding: '12px 14px', borderRadius: 8, border: `1px solid ${relTypeColor}25`, backgroundColor: 'rgb(var(--theme-bg))', marginBottom: isLast ? 0 : 10 }}>
                        {/* 字段对连接 */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ padding: '3px 10px', borderRadius: 5, backgroundColor: 'rgba(24, 144, 255, 0.1)', fontFamily: 'monospace', fontWeight: 600, fontSize: 12, color: 'rgb(var(--theme-text))' }}>{pair.localField}</span>
                            <Terminal style={{ width: 16, height: 16, color: 'rgb(var(--theme-primary))' }} />
                            <span style={{ padding: '3px 10px', borderRadius: 5, backgroundColor: 'rgba(24, 144, 255, 0.1)', fontFamily: 'monospace', fontWeight: 600, fontSize: 12, color: 'rgb(var(--theme-text))' }}>{pair.remoteField}</span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexWrap: 'wrap' }}>
                            <Tag style={{ margin: 0, fontSize: 10, backgroundColor: `${relTypeColor}15`, borderColor: `${relTypeColor}40`, color: relTypeColor }}>
                              {relationshipTypeLabels[pair.relationshipType] || pair.relationshipType}
                            </Tag>
                            {pair.cardinality && <Tag style={{ margin: 0, fontSize: 9 }}>{cardinalityLabels[pair.cardinality] || pair.cardinality}</Tag>}
                            <Tag color={pair.confidence >= 0.9 ? 'green' : pair.confidence >= 0.7 ? 'orange' : 'default'} style={{ margin: 0, fontSize: 9 }}>{(pair.confidence * 100).toFixed(0)}%</Tag>
                            {pair.evidence && (
                              <>
                                {pair.evidence.name_match >= 0.8 && <Tag style={{ margin: 0, fontSize: 9 }} color="blue">命名</Tag>}
                                {pair.evidence.llm_analyzed && <Tag style={{ margin: 0, fontSize: 9 }} color="purple">LLM</Tag>}
                                {pair.evidence.type_compatible && <Tag style={{ margin: 0, fontSize: 9 }} color="cyan">类型</Tag>}
                              </>
                            )}
                          </div>
                        </div>

                        {/* 推理说明 */}
                        {pair.reasoning && (
                          <div style={{ marginBottom: 10 }}>
                            <div style={{ fontSize: 11, fontWeight: 600, color: 'rgb(var(--theme-text))', marginBottom: 5, display: 'flex', alignItems: 'center', gap: 4 }}>
                              <BookOpen style={{ width: 12, height: 12, color: 'rgb(var(--theme-primary))' }} />
                              推断依据
                            </div>
                            <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', lineHeight: 1.7, padding: '7px 10px', backgroundColor: 'rgb(var(--theme-bg-secondary))', borderRadius: 5, borderLeft: `3px solid ${relTypeColor}` }}>
                              {pair.reasoning}
                            </div>
                          </div>
                        )}

                        {/* 业务关系 */}
                        {pair.businessRelation && (
                          <div style={{ marginBottom: 10, padding: '7px 10px', borderRadius: 6, backgroundColor: 'rgba(var(--theme-primary), 0.04)', border: '1px solid rgba(var(--theme-primary), 0.08)' }}>
                            <div style={{ fontSize: 11, fontWeight: 600, color: 'rgb(var(--theme-text))', marginBottom: 2 }}>业务含义</div>
                            <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', lineHeight: 1.5 }}>
                              {pair.businessRelation.relation_description}
                            </div>
                          </div>
                        )}

                        {/* JOIN 建议 */}
                        {pair.joinSuggestion && (
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
                              <Terminal style={{ width: 12, height: 12, color: 'rgb(var(--theme-primary))' }} />
                              <span style={{ fontSize: 11, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>建议 JOIN</span>
                              <Tag style={{ margin: 0, fontSize: 9 }}>{pair.joinSuggestion.join_type}</Tag>
                              <div style={{ marginLeft: 'auto' }}>
                                <Tooltip title="复制">
                                  <Button type="text" size="small" icon={<Copy style={{ width: 11, height: 11 }} />} onClick={() => { navigator.clipboard.writeText(pair.joinSuggestion.sample_sql || pair.joinSuggestion.join_condition || ''); message.success('已复制') }} />
                                </Tooltip>
                              </div>
                            </div>
                            <div style={{ padding: '6px 8px', borderRadius: 5, backgroundColor: 'rgb(var(--theme-bg-secondary))', border: '1px solid rgb(var(--theme-border))', fontFamily: 'monospace', fontSize: 11, color: 'rgb(var(--theme-text))', lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                              {pair.joinSuggestion.sample_sql || pair.joinSuggestion.join_condition}
                            </div>
                            {pair.joinSuggestion.use_cases && pair.joinSuggestion.use_cases.length > 0 && (
                              <div style={{ marginTop: 6 }}>
                                <div style={{ fontSize: 10, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 3 }}>使用场景：</div>
                                {pair.joinSuggestion.use_cases.map((uc: string, i: number) => (
                                  <div key={i} style={{ fontSize: 10, color: 'rgb(var(--theme-text-secondary))', paddingLeft: 10, position: 'relative', lineHeight: 1.4 }}>
                                    <span style={{ position: 'absolute', left: 0, color: 'rgb(var(--theme-primary)' }}>•</span>
                                    {uc}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Modal>
  )
}

// 展开行详情 - 优化版
const ExpandedRowDetail = ({ record }: { record: any }) => {
  const hasDetail = record.executed_sql_text || record.error_message || record.failed_samples?.length > 0 || record.raw_result

  if (!hasDetail) {
    return <div style={{ textAlign: 'center', padding: 20, color: 'rgb(var(--theme-text-muted))', fontSize: 13 }}>暂无详细信息</div>
  }

  return (
    <div style={{ padding: '16px 20px', backgroundColor: 'rgba(var(--theme-bg-secondary), 0.5)' }}>
      <div style={{ display: 'grid', gap: 16 }}>
        {/* 执行结果 - 表格形式 */}
        {record.raw_result && Object.keys(record.raw_result).length > 0 && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <CheckCircle2 style={{ width: 13, height: 13, color: 'rgb(var(--theme-primary))' }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>执行结果</span>
            </div>
            <div style={{ overflowX: 'auto', borderRadius: 8, border: '1px solid rgb(var(--theme-border))' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ backgroundColor: 'rgba(var(--theme-primary), 0.06)' }}>
                    {Object.keys(record.raw_result).map((key) => (
                      <th key={key} style={{ padding: '8px 14px', textAlign: 'left', fontWeight: 600, color: 'rgb(var(--theme-text))', borderBottom: '1px solid rgb(var(--theme-border))', whiteSpace: 'nowrap' }}>
                        {key === 'total_count' ? '总记录数' : key === 'failed_count' ? '失败数' : key}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    {Object.values(record.raw_result).map((val: any, idx: number) => (
                      <td key={idx} style={{ padding: '8px 14px', color: 'rgb(var(--theme-text))', borderBottom: '1px solid rgb(var(--theme-border))', fontWeight: 500 }}>
                        {typeof val === 'number' ? formatNumber(val) : String(val ?? '-')}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 执行 SQL - 右上角复制按钮 */}
        {record.executed_sql_text && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Terminal style={{ width: 13, height: 13, color: 'rgb(var(--theme-primary))' }} />
                <span style={{ fontSize: 13, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>执行的 SQL</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {record.rule_mode && (
                  <Tag style={{ margin: 0, fontSize: 11, backgroundColor: '#722ed115', borderColor: '#722ed140', color: '#722ed1' }}>
                    {ruleModeLabels[record.rule_mode] || record.rule_mode}
                  </Tag>
                )}
                <Tag style={{ margin: 0, fontSize: 11 }}>{formatExecutionTime(record.execution_time_ms)}</Tag>
                <Tooltip title="复制 SQL">
                  <Button type="text" size="small" icon={<Copy style={{ width: 13, height: 13 }} />} onClick={() => { navigator.clipboard.writeText(record.executed_sql_text); message.success('已复制到剪贴板') }} />
                </Tooltip>
              </div>
            </div>
            <div style={{ padding: '10px 12px', borderRadius: 8, backgroundColor: 'rgb(var(--theme-bg))', border: '1px solid rgb(var(--theme-border))', fontFamily: 'monospace', fontSize: 12, color: 'rgb(var(--theme-text))', lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
              {record.executed_sql_text}
            </div>
          </div>
        )}

        {/* 错误信息 */}
        {record.error_message && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <AlertCircle style={{ width: 13, height: 13, color: '#fa8c16' }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: '#fa8c16' }}>执行错误</span>
            </div>
            <div style={{ padding: '10px 12px', borderRadius: 8, backgroundColor: 'rgba(250, 140, 22, 0.06)', border: '1px solid rgba(250, 140, 22, 0.15)', fontFamily: 'monospace', fontSize: 12, color: '#fa8c16', lineHeight: 1.6 }}>
              {record.error_message}
            </div>
          </div>
        )}

        {/* 失败样例 - 优化美观样式 */}
        {record.failed_samples && record.failed_samples.length > 0 && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28, borderRadius: 8, backgroundColor: 'rgba(245, 34, 45, 0.1)' }}>
                <AlertCircle style={{ width: 14, height: 14, color: '#f5222d' }} />
              </div>
              <span style={{ fontSize: 14, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>失败样例</span>
              <Tag style={{ margin: 0, fontSize: 11 }} color="red">{record.failed_samples.length} 条</Tag>
            </div>
            <div style={{ display: 'grid', gap: 14 }}>
              {record.failed_samples.map((sample: any, idx: number) => (
                <div key={idx} style={{ borderRadius: 12, backgroundColor: 'rgba(245, 34, 45, 0.03)', border: '1px solid rgba(245, 34, 45, 0.1)', overflow: 'hidden' }}>
                  {/* 样例编号和标签 */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', backgroundColor: 'rgba(245, 34, 45, 0.04)', borderBottom: '1px solid rgba(245, 34, 45, 0.08)' }}>
                    <div style={{ width: 24, height: 24, borderRadius: '50%', backgroundColor: 'rgba(245, 34, 45, 0.15)', color: '#f5222d', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700 }}>
                      {idx + 1}
                    </div>
                    {sample.condition_mode && <Tag style={{ margin: 0, fontSize: 10, backgroundColor: 'rgba(245, 34, 45, 0.1)', borderColor: 'rgba(245, 34, 45, 0.2)', color: '#f5222d' }}>条件违反详情</Tag>}
                  </div>

                  {/* 违反条件 - 表格形式展示 */}
                  <div style={{ padding: 14 }}>
                    {sample.violated_conditions && sample.violated_conditions.length > 0 && (
                      <div style={{ marginBottom: 14 }}>
                        <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-muted))', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
                          <AlertCircle style={{ width: 11, height: 11, color: '#f5222d' }} />
                          违反条件
                        </div>
                        <div style={{ overflowX: 'auto', borderRadius: 8, border: '1px solid rgba(245, 34, 45, 0.12)', backgroundColor: 'rgb(var(--theme-bg))' }}>
                          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                            <thead>
                              <tr style={{ backgroundColor: 'rgba(245, 34, 45, 0.05)' }}>
                                <th style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: 'rgb(var(--theme-text))', borderBottom: '1px solid rgba(245, 34, 45, 0.1)', whiteSpace: 'nowrap', width: '40%' }}>字段</th>
                                <th style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: 'rgb(var(--theme-text))', borderBottom: '1px solid rgba(245, 34, 45, 0.1)', whiteSpace: 'nowrap', width: '60%' }}>条件</th>
                              </tr>
                            </thead>
                            <tbody>
                              {sample.violated_conditions.map((vc: any, vcIdx: number) => (
                                <tr key={vcIdx} style={{ backgroundColor: vcIdx % 2 === 0 ? 'transparent' : 'rgba(0,0,0,0.02)' }}>
                                  <td style={{ padding: '8px 12px', borderBottom: '1px solid rgba(245, 34, 45, 0.06)' }}>
                                    <span style={{ fontSize: 12, fontWeight: 600, padding: '3px 10px', backgroundColor: 'rgba(24, 144, 255, 0.08)', borderRadius: 4, fontFamily: 'monospace', color: 'rgb(var(--theme-text))' }}>{vc.column}</span>
                                  </td>
                                  <td style={{ padding: '8px 12px', borderBottom: '1px solid rgba(245, 34, 45, 0.06)' }}>
                                    <span style={{ fontSize: 12, color: '#cf1322', fontFamily: 'monospace', fontWeight: 500, wordBreak: 'break-all' }}>{vc.condition}</span>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* 样例数据 - 表格形式 */}
                    {sample.sample_value && (
                      <div>
                        <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-muted))', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
                          <Database style={{ width: 11, height: 11, color: 'rgb(var(--theme-primary))' }} />
                          样例数据
                        </div>
                        {Array.isArray(sample.sample_value) && sample.sample_value.length > 0 ? (
                          <div style={{ overflowX: 'auto', borderRadius: 8, border: '1px solid rgba(245, 34, 45, 0.12)', backgroundColor: 'rgb(var(--theme-bg))' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                              <thead>
                                <tr style={{ backgroundColor: 'rgba(245, 34, 45, 0.05)' }}>
                                  <th style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: 'rgb(var(--theme-text))', borderBottom: '1px solid rgba(245, 34, 45, 0.1)', whiteSpace: 'nowrap', width: 40 }}>#</th>
                                  {Object.keys(sample.sample_value[0]).map((col) => (
                                    <th key={col} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: 'rgb(var(--theme-text))', borderBottom: '1px solid rgba(245, 34, 45, 0.1)', whiteSpace: 'nowrap' }}>{col}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {sample.sample_value.map((row: any, rowIdx: number) => (
                                  <tr key={rowIdx} style={{ backgroundColor: rowIdx % 2 === 0 ? 'transparent' : 'rgba(0,0,0,0.02)' }}>
                                    <td style={{ padding: '8px 12px', color: 'rgb(var(--theme-text-muted))', borderBottom: '1px solid rgba(245, 34, 45, 0.06)' }}>{rowIdx + 1}</td>
                                    {Object.values(row).map((val: any, colIdx: number) => (
                                      <td key={colIdx} style={{ padding: '8px 12px', color: '#cf1322', borderBottom: '1px solid rgba(245, 34, 45, 0.06)', wordBreak: 'break-all', maxWidth: 150 }}>{typeof val === 'object' ? JSON.stringify(val) : String(val ?? '-')}</td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : typeof sample.sample_value === 'object' ? (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 8 }}>
                            {Object.entries(sample.sample_value).map(([key, value]) => (
                              <div key={key} style={{ padding: '8px 10px', borderRadius: 6, backgroundColor: 'rgb(var(--theme-bg))', border: '1px solid rgba(245, 34, 45, 0.12)' }}>
                                <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-muted))', marginBottom: 4 }}>{key}</div>
                                <div style={{ fontSize: 13, fontWeight: 600, color: '#cf1322', wordBreak: 'break-all' }}>{typeof value === 'object' ? JSON.stringify(value) : String(value ?? '-')}</div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div style={{ fontSize: 13, color: '#cf1322', fontFamily: 'monospace', padding: '8px 10px', backgroundColor: 'rgb(var(--theme-bg))', borderRadius: 6, border: '1px solid rgba(245, 34, 45, 0.12)' }}>{String(sample.sample_value)}</div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function ReportDetailPageContent() {
  const router = useRouter()
  const params = useParams()
  const searchParams = useSearchParams()
  const { lng, id } = params as { lng: string; id: string }

  const [report, setReport] = useState<ExtendedGovernanceReportDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [basicAuditExpanded, setBasicAuditExpanded] = useState(true)
  const [basicAuditDetailExpanded, setBasicAuditDetailExpanded] = useState(true)
  const [qualityAuditExpanded, setQualityAuditExpanded] = useState(true)
  const [relationExpanded, setRelationExpanded] = useState(true)
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())
  const [selectedRelation, setSelectedRelation] = useState<any>(null)
  const [relationModalOpen, setRelationModalOpen] = useState(false)
  const [generatingFile, setGeneratingFile] = useState(false)
  const [fileStatus, setFileStatus] = useState<'pending' | 'generating' | 'completed' | 'failed' | null>(null)
  const [fileErrorMsg, setFileErrorMsg] = useState<string | null>(null)
  const [generateModalOpen, setGenerateModalOpen] = useState(false)
  const [generateReportName, setGenerateReportName] = useState('')
  const [generateFormat, setGenerateFormat] = useState<'docx' | 'pdf' | 'xlsx' | 'md'>('md')
  const [fileNameError, setFileNameError] = useState('')

  // 编辑报告名称相关状态
  const [isEditingReportName, setIsEditingReportName] = useState(false)
  const [editingReportName, setEditingReportName] = useState('')
  const [editingReportNameError, setEditingReportNameError] = useState('')
  const [isUpdatingReportName, setIsUpdatingReportName] = useState(false)

  // 文件名非法字符正则（Windows/通用文件系统不允许的字符）
  const INVALID_FILENAME_CHARS = /[\\/:*?"<>|]/
  const validateFileName = (name: string): string => {
    if (!name.trim()) return ''
    if (INVALID_FILENAME_CHARS.test(name)) {
      return '文件名包含非法字符：\\ / : * ? " < > |'
    }
    if (name.length > 200) {
      return '文件名长度不能超过200个字符'
    }
    return ''
  }

  const [reExportConfirmOpen, setReExportConfirmOpen] = useState(false)
  const [historyFiles, setHistoryFiles] = useState<HistoryFile[]>([])
  const [historyFilesExpanded, setHistoryFilesExpanded] = useState(true)

  const isFromAudit = searchParams.get('from') === 'audit'

  useEffect(() => {
    if (id) fetchReportDetail()
  }, [id])

  const fetchReportDetail = async () => {
    setLoading(true)
    try {
      const res = await getGovernanceReportDetail(id)
      if (res.code === 200) {
        setReport(res.data)
        // 设置文件状态
        // 只有当 has_export 为 true 或有历史文件时才保留 file_status
        // 否则说明从未生成过文件或文件已全部删除，应该重置状态
        if (res.data.has_export || (res.data.history_files && res.data.history_files.length > 0)) {
          setFileStatus(res.data.file_status || null)
          setFileErrorMsg(res.data.file_error_msg || null)
        } else {
          // 从未生成过文件或文件已全部删除，重置所有文件相关状态
          setFileStatus(null)
          setFileErrorMsg(null)
        }
        // 无论是否有文件状态，都重置生成中状态
        setGeneratingFile(false)
        // 设置历史文件列表
        setHistoryFiles(res.data.history_files || [])
      }
      else message.error(res.msg || '获取报告详情失败')
    } catch (error) {
      message.error('获取报告详情失败')
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = async () => {
    try {
      await downloadGovernanceReport(id)
      message.success('下载已完成')
    } catch (error) {
      message.error('下载失败')
    }
  }

  // 下载历史文件
  const handleDownloadHistoryFile = async (fileId: string) => {
    try {
      await downloadGovernanceReport(id, fileId)
      message.success('下载已完成')
    } catch (error) {
      message.error('下载失败')
    }
  }

  // 删除历史导出文件
  const handleDeleteHistoryFile = async (fileId: string, fileName?: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除文件"${fileName || ''}"吗？`,
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      centered: true,
      styles: {
        content: { color: 'rgb(var(--theme-text))' },
      },
      onOk: async () => {
        try {
          await deleteGovernanceReportFile(fileId)
          message.success('删除成功')
          // 刷新历史文件列表
          await fetchReportDetail()
        } catch (err) {
          message.error('删除失败')
        }
      },
    })
  }

  // 删除当前报告
  const handleDeleteReport = async () => {
    if (!report) return
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
          const res = await deleteGovernanceReport(id)
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
            // 删除成功后返回报告列表页面
            router.push(`/${lng}/governance/reports`)
          } else if (res.code === 404) {
            message.error('报告不存在')
            router.push(`/${lng}/governance/reports`)
          } else {
            message.error(res.msg || '删除失败')
          }
        } catch (error) {
          message.error('删除失败')
        }
      },
    })
  }

  // 开始编辑报告名称
  const handleStartEditReportName = () => {
    if (!report) return
    setEditingReportName(report.report_name)
    setEditingReportNameError('')
    setIsEditingReportName(true)
  }

  // 取消编辑报告名称
  const handleCancelEditReportName = () => {
    setIsEditingReportName(false)
    setEditingReportName('')
    setEditingReportNameError('')
  }

  // 确认修改报告名称
  const handleConfirmEditReportName = async () => {
    if (!report) return

    // 校验名称
    const trimmedName = editingReportName.trim()
    if (!trimmedName) {
      setEditingReportNameError('报告名称不能为空')
      return
    }
    if (trimmedName.length > 255) {
      setEditingReportNameError('报告名称不能超过255个字符')
      return
    }
    if (trimmedName === report.report_name) {
      // 名称未变化，直接取消编辑
      handleCancelEditReportName()
      return
    }

    setIsUpdatingReportName(true)
    try {
      const res = await updateGovernanceReportName(id, { report_name: trimmedName })
      if (res.code === 200) {
        message.success('报告名称修改成功')
        // 更新本地状态
        setReport((prev) => prev ? { ...prev, report_name: trimmedName } : null)
        handleCancelEditReportName()
      } else {
        message.error(res.msg || '修改失败')
      }
    } catch (error) {
      message.error('修改报告名称失败')
    } finally {
      setIsUpdatingReportName(false)
    }
  }

  // 生成报告文件
  const handleGenerateFile = () => {
    // 如果已经导出过文件，先弹出确认框
    if (hasExportFile) {
      setReExportConfirmOpen(true)
    } else {
      // 未导出过，直接打开生成弹框
      setGenerateReportName('')
      setFileNameError('')
      setGenerateFormat('md')
      setGenerateModalOpen(true)
    }
  }

  // 确认重新导出
  const handleConfirmReExport = () => {
    setReExportConfirmOpen(false)
    setGenerateReportName('')
    setFileNameError('')
    setGenerateFormat('md')
    setGenerateModalOpen(true)
  }

  // 确认生成报告
  const handleConfirmGenerate = async () => {
    // 校验文件名
    const error = validateFileName(generateReportName)
    if (error) {
      setFileNameError(error)
      return
    }

    setGeneratingFile(true)
    setFileErrorMsg(null)
    setGenerateModalOpen(false)
    // 显示生成中的提示
    const hideLoadingMsg = message.loading('报告文件生成中...', 0)
    try {
      const res = await generateGovernanceReportV2({
        report_id: id,
        file_name: generateReportName.trim() || undefined,
        format: generateFormat,
      })
      if (res.code === 200) {
        hideLoadingMsg()
        message.success('报告文件生成已启动')
        // 轮询文件状态
        pollFileStatus()
      } else {
        hideLoadingMsg()
        message.error(res.msg || '生成文件失败')
        setGeneratingFile(false)
      }
    } catch (error) {
      hideLoadingMsg()
      message.error('生成文件失败')
      setGeneratingFile(false)
    }
  }

  // 轮询文件生成状态
  const pollFileStatus = () => {
    const poll = async () => {
      try {
        const res = await getGovernanceReportStatus(id)
        if (res.code === 200) {
          setFileStatus(res.data.file_status)
          if (res.data.file_error_msg) {
            setFileErrorMsg(res.data.file_error_msg)
          }

          if (res.data.file_status === 'completed') {
            message.success('报告文件生成成功')
            setGeneratingFile(false)
            // 刷新报告详情以获取最新文件信息
            fetchReportDetail()
            return
          } else if (res.data.file_status === 'failed') {
            message.error(res.data.file_error_msg || '文件生成失败')
            setGeneratingFile(false)
            return
          }
          // 继续轮询
          setTimeout(poll, 2000)
        }
      } catch (error) {
        console.error('轮询文件状态失败:', error)
        setGeneratingFile(false)
      }
    }
    poll()
  }

  const toggleExpand = (recordId: string) => {
    setExpandedRows(prev => {
      const newSet = new Set(prev)
      if (newSet.has(recordId)) newSet.delete(recordId)
      else newSet.add(recordId)
      return newSet
    })
  }

  // 计算统计数据 - 使用 summary 字段
  const stats = useMemo(() => {
    if (!report) return null
    const basicAudit = report.basic_audit_result || []
    const tableCount = basicAudit.length
    const summary = report.summary
    const relationCards = report.full_relation_discovery?.cards || []
    return {
      tableCount,
      totalRules: summary?.total_rules || 0,
      passedRules: summary?.passed_rules || 0,
      failedRules: summary?.failed_rules || 0,
      qualityRulesCount: (report.quality_audit_result || []).length,
      basicRulesCount: (report.basic_audit_detail?.results || []).length,
      relationCardsCount: relationCards.length,
    }
  }, [report])

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <Loader2 style={{ width: 48, height: 48, color: 'rgb(var(--theme-primary))', animation: 'spin 1s linear infinite' }} />
        <p style={{ marginTop: 20, color: 'rgb(var(--theme-text-muted))', fontSize: 14 }}>加载报告详情...</p>
      </div>
    )
  }

  if (!report) {
    return (
      <div style={{ padding: 60, borderRadius: 16, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))', textAlign: 'center' }}>
        <FileText style={{ width: 48, height: 48, color: 'rgb(var(--theme-text-muted))', opacity: 0.4, margin: '0 auto' }} />
        <p style={{ marginTop: 16, fontSize: 16, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>报告不存在</p>
      </div>
    )
  }

  const score = report.quality_score || 0
  const grade = score >= 90 ? '优秀' : score >= 75 ? '良好' : score >= 60 ? '一般' : score >= 40 ? '较差' : '差'
  const gradeColor = score >= 90 ? '#52c41a' : score >= 75 ? '#1890ff' : score >= 60 ? '#faad14' : score >= 40 ? '#fa8c16' : '#f5222d'
  const basicAuditData = report.basic_audit_result || []
  const qualityAuditData = report.quality_audit_result || []
  const basicAuditDetailData = report.basic_audit_detail?.results || []
  const relationCards = report.full_relation_discovery?.cards || []
  const allRelationships = report.full_relation_discovery?.relationships || []

  // 判断是否已经有导出文件
  const hasExportFile = report.has_export || report.file_status === 'completed'

  // 判断文件是否正在生成中
  const isFileGenerating = fileStatus === 'generating' || fileStatus === 'pending'

  // 获取文件状态的显示文本
  const getFileStatusText = () => {
    if (generatingFile || fileStatus === 'pending') return '生成中...'
    if (fileStatus === 'generating') return '生成中...'
    if (fileStatus === 'failed') return '生成失败'
    return ''
  }

  // 获取文件状态的显示颜色
  const getFileStatusColor = () => {
    if (generatingFile || fileStatus === 'pending' || fileStatus === 'generating') return 'rgb(var(--theme-text-secondary))'
    if (fileStatus === 'failed') return '#f5222d'
    if (fileStatus === 'completed') return '#52c41a'
    return 'rgb(var(--theme-text-secondary))'
  }

  // 质检规则表格列
  const qualityColumns: ColumnsType<any> = [
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 40,
      align: 'center',
      render: (status) => {
        if (status === 'passed') return <CheckCircle2 style={{ width: 16, height: 16, color: '#52c41a' }} />
        if (status === 'failed') return <XCircle style={{ width: 16, height: 16, color: '#f5222d' }} />
        return <AlertCircle style={{ width: 16, height: 16, color: '#fa8c16' }} />
      },
    },
    { title: '规则名称', dataIndex: 'rule_name', key: 'rule_name', ellipsis: true, width: 180, render: (text) => <Tooltip title={text}><span style={{ fontSize: 12, fontWeight: 500 }}>{text}</span></Tooltip> },
    { title: '类型', dataIndex: 'rule_type', key: 'rule_type', width: 90, render: (type) => <Tag style={{ fontSize: 11, borderRadius: 4, margin: 0 }}>{ruleTypeLabels[type] || type}</Tag> },
    { title: '级别', dataIndex: 'severity', key: 'severity', width: 70, render: (sev) => <Tag color={sev === 'critical' ? 'red' : sev === 'warning' ? 'orange' : 'blue'} style={{ fontSize: 11, borderRadius: 4, margin: 0 }}>{severityLabels[sev] || sev}</Tag> },
    { title: '目标表', dataIndex: 'table_name', key: 'table_name', width: 120, ellipsis: true, render: (t) => <span style={{ fontSize: 12 }}>{t}</span> },
    { title: '列', dataIndex: 'column_name', key: 'column_name', width: 80, ellipsis: true, render: (c) => <span style={{ fontSize: 12, color: c ? undefined : 'rgb(var(--theme-text-muted))' }}>{c || '-'}</span> },
    {
      title: '通过/总数',
      key: 'counts',
      width: 90,
      align: 'right' as const,
      render: (_, r) => <span style={{ fontSize: 12 }}><span style={{ color: '#52c41a', fontWeight: 600 }}>{r.passed_count}</span> / {r.total_count}</span>,
    },
    {
      title: '失败',
      dataIndex: 'failed_count',
      key: 'failed_count',
      width: 50,
      align: 'right' as const,
      render: (v) => <span style={{ fontSize: 12, color: v > 0 ? '#f5222d' : '#52c41a', fontWeight: 600 }}>{v}</span>,
    },
    {
      title: '详情',
      key: 'expand',
      width: 50,
      align: 'center' as const,
      render: (_, record) => {
        const hasDetail = record.executed_sql_text || record.error_message || record.failed_samples?.length > 0 || record.raw_result
        if (!hasDetail) return <span style={{ color: 'rgb(var(--theme-text-muted))', fontSize: 11 }}>无</span>
        return (
          <Button type="text" size="small" icon={expandedRows.has(record.id) ? <ChevronDown style={{ width: 14, height: 14, color: 'rgb(var(--theme-text))' }} /> : <ChevronRight style={{ width: 14, height: 14, color: 'rgb(var(--theme-text))' }} />} onClick={() => toggleExpand(record.id)} style={{ padding: 4 }} />
        )
      },
    },
  ]

  return (
    <div className="space-y-4">
      {/* 顶部导航 */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button onClick={() => router.push(`/${lng}/governance/reports`)} style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '6px 12px', borderRadius: 8, fontSize: 13, color: 'rgb(var(--theme-text-secondary))', backgroundColor: 'transparent', border: 'none', cursor: 'pointer' }}>
          <ArrowLeft style={{ width: 15, height: 15 }} />
          返回报告列表
        </button>
        {isFromAudit && (
          <button onClick={() => router.push(`/${lng}/governance/audit`)} style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '6px 12px', borderRadius: 8, fontSize: 13, color: 'rgb(var(--theme-primary))', backgroundColor: 'rgba(var(--theme-primary), 0.08)', border: '1px solid rgba(var(--theme-primary), 0.2)', cursor: 'pointer' }}>
            <ArrowLeft style={{ width: 15, height: 15 }} />
            返回执行与结果
          </button>
        )}
      </div>

      {/* 报告头部 */}
      <div style={{ padding: 18, borderRadius: 14, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 10px', borderRadius: 9999, backgroundColor: 'rgba(var(--theme-primary), 0.08)', color: 'rgb(var(--theme-primary))', fontSize: 11, fontWeight: 600, marginBottom: 8 }}>
              <Sparkles style={{ width: 11, height: 11 }} />
              质检报告详情
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {isEditingReportName ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Input
                    value={editingReportName}
                    onChange={(e) => {
                      setEditingReportName(e.target.value)
                      const trimmed = e.target.value.trim()
                      if (!trimmed) {
                        setEditingReportNameError('报告名称不能为空')
                      } else if (trimmed.length > 255) {
                        setEditingReportNameError('报告名称不能超过255个字符')
                      } else {
                        setEditingReportNameError('')
                      }
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        handleConfirmEditReportName()
                      } else if (e.key === 'Escape') {
                        handleCancelEditReportName()
                      }
                    }}
                    style={{ width: 300, fontSize: 18, fontWeight: 700 }}
                    status={editingReportNameError ? 'error' : ''}
                    autoFocus
                  />
                  <Button
                    type="primary"
                    size="small"
                    onClick={handleConfirmEditReportName}
                    loading={isUpdatingReportName}
                    disabled={!!editingReportNameError}
                  >
                    保存
                  </Button>
                  <Button
                    size="small"
                    onClick={handleCancelEditReportName}
                    disabled={isUpdatingReportName}
                  >
                    取消
                  </Button>
                  {editingReportNameError && (
                    <span style={{ fontSize: 12, color: '#ff4d4f' }}>{editingReportNameError}</span>
                  )}
                </div>
              ) : (
                <>
                  <h1 style={{ fontSize: 18, fontWeight: 700, color: 'rgb(var(--theme-text))', margin: 0 }}>{report.report_name}</h1>
                  <Tooltip title="编辑报告名称">
                    <button
                      onClick={handleStartEditReportName}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 24,
                        height: 24,
                        borderRadius: 4,
                        backgroundColor: 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                        color: 'rgb(var(--theme-text-secondary))',
                        padding: 0,
                      }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                      </svg>
                    </button>
                  </Tooltip>
                </>
              )}
            </div>
            <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', marginTop: 4 }}>
              {new Date(report.execution_time).toLocaleString('zh-CN')}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', flexWrap: 'wrap', paddingTop: 28 }}>
            {/* 文件状态提示 */}
            {fileStatus && (fileStatus !== 'completed' || fileErrorMsg) && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: getFileStatusColor() }}>
                {fileStatus === 'generating' || fileStatus === 'pending' || generatingFile ? (
                  <Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} />
                ) : fileStatus === 'failed' ? (
                  <AlertCircle style={{ width: 14, height: 14 }} />
                ) : null}
                <span>{getFileStatusText()}</span>
                {fileErrorMsg && (
                  <Tooltip title={fileErrorMsg}>
                    <AlertCircle style={{ width: 12, height: 12, color: '#f5222d' }} />
                  </Tooltip>
                )}
              </div>
            )}
            {/* 生成文件按钮 */}
            <button
              onClick={handleGenerateFile}
              disabled={generatingFile || isFileGenerating}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 16px',
                borderRadius: 8,
                fontSize: 13,
                fontWeight: 500,
                color: 'white',
                backgroundColor: generatingFile || isFileGenerating ? 'rgba(var(--theme-primary), 0.5)' : '#52c41a',
                border: 'none',
                cursor: generatingFile || isFileGenerating ? 'not-allowed' : 'pointer',
              }}
            >
              {generatingFile || isFileGenerating ? (
                <>
                  <Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} />
                  生成中...
                </>
              ) : (
                <>
                  <FileUp style={{ width: 14, height: 14 }} />
                  生成文件
                </>
              )}
            </button>
            {/* 下载报告文件按钮 */}
            {hasExportFile && (
              <button onClick={handleDownload} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500, color: 'white', backgroundColor: 'rgb(var(--theme-primary))', border: 'none', cursor: 'pointer' }}>
                <Download style={{ width: 14, height: 14 }} />
                下载报告文件
              </button>
            )}
            {/* 刷新状态按钮 */}
            <Tooltip title="刷新文件状态">
              <button
                onClick={() => fetchReportDetail()}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 36,
                  height: 36,
                  borderRadius: 8,
                  backgroundColor: 'transparent',
                  border: '1px solid rgb(var(--theme-border))',
                  cursor: 'pointer',
                  color: 'rgb(var(--theme-text-secondary))',
                }}
              >
                <RefreshCw style={{ width: 14, height: 14 }} />
              </button>
            </Tooltip>
            {/* 删除报告按钮 */}
            <Tooltip title="删除报告">
              <button
                onClick={handleDeleteReport}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 36,
                  height: 36,
                  borderRadius: 8,
                  backgroundColor: 'transparent',
                  border: '1px solid rgba(245, 34, 45, 0.3)',
                  cursor: 'pointer',
                  color: '#f5222d',
                }}
              >
                <Trash2 style={{ width: 14, height: 14 }} />
              </button>
            </Tooltip>
          </div>
        </div>
      </div>

      {/* 概览区域 - 紧凑优化 */}
      <div style={{ padding: 14, borderRadius: 12, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))' }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          {/* 评分 - 紧凑 */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '4px 16px' }}>
            <ScoreRing score={score} />
            <div style={{ marginTop: 6, padding: '2px 10px', borderRadius: 9999, fontSize: 11, fontWeight: 600, color: 'white', backgroundColor: gradeColor }}>{grade}</div>
            <div style={{ marginTop: 2, fontSize: 10, color: 'rgb(var(--theme-text-muted))' }}>质量评分</div>
          </div>

          {/* 统计指标 - 紧凑一行 */}
          <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, minWidth: 280 }}>
            <div style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))', textAlign: 'center', position: 'relative', overflow: 'hidden' }}>
              {/* 渐变光晕效果 */}
              <div
                style={{
                  position: 'absolute',
                  top: -15,
                  right: -15,
                  width: 60,
                  height: 60,
                  borderRadius: '50%',
                  opacity: 0.12,
                  background: 'radial-gradient(circle, #13c2c2, transparent 70%)',
                  filter: 'blur(10px)',
                }}
              />
              <div style={{ fontSize: 18, fontWeight: 700, color: '#13c2c2', position: 'relative', zIndex: 1 }}>{stats?.totalRules || 0}</div>
              <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', marginTop: 2, position: 'relative', zIndex: 1 }}>总规则数</div>
            </div>
            <div style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))', textAlign: 'center', position: 'relative', overflow: 'hidden' }}>
              {/* 渐变光晕效果 */}
              <div
                style={{
                  position: 'absolute',
                  top: -15,
                  right: -15,
                  width: 60,
                  height: 60,
                  borderRadius: '50%',
                  opacity: 0.12,
                  background: 'radial-gradient(circle, #52c41a, transparent 70%)',
                  filter: 'blur(10px)',
                }}
              />
              <div style={{ fontSize: 18, fontWeight: 700, color: '#52c41a', position: 'relative', zIndex: 1 }}>{stats?.passedRules || 0}</div>
              <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', marginTop: 2, position: 'relative', zIndex: 1 }}>通过规则</div>
            </div>
            <div style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))', textAlign: 'center', position: 'relative', overflow: 'hidden' }}>
              {/* 渐变光晕效果 */}
              <div
                style={{
                  position: 'absolute',
                  top: -15,
                  right: -15,
                  width: 60,
                  height: 60,
                  borderRadius: '50%',
                  opacity: 0.12,
                  background: 'radial-gradient(circle, #f5222d, transparent 70%)',
                  filter: 'blur(10px)',
                }}
              />
              <div style={{ fontSize: 18, fontWeight: 700, color: '#f5222d', position: 'relative', zIndex: 1 }}>{stats?.failedRules || 0}</div>
              <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', marginTop: 2, position: 'relative', zIndex: 1 }}>失败规则</div>
            </div>
            <div style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))', textAlign: 'center', position: 'relative', overflow: 'hidden' }}>
              {/* 渐变光晕效果 */}
              <div
                style={{
                  position: 'absolute',
                  top: -15,
                  right: -15,
                  width: 60,
                  height: 60,
                  borderRadius: '50%',
                  opacity: 0.12,
                  background: 'radial-gradient(circle, #1890ff, transparent 70%)',
                  filter: 'blur(10px)',
                }}
              />
              <div style={{ fontSize: 18, fontWeight: 700, color: '#1890ff', position: 'relative', zIndex: 1 }}>{stats?.tableCount || 0}</div>
              <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', marginTop: 2, position: 'relative', zIndex: 1 }}>检测表数</div>
            </div>
          </div>
        </div>
      </div>


      {/* 基础审计结果 */}
      {basicAuditData.length > 0 && (
        <div style={{ borderRadius: 12, border: '1px solid rgb(var(--theme-border))', overflow: 'hidden', backgroundColor: 'rgb(var(--theme-bg))' }}>
          <div
            onClick={() => setBasicAuditExpanded(!basicAuditExpanded)}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', cursor: 'pointer', backgroundColor: 'rgba(var(--theme-primary), 0.04)' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 30, height: 30, borderRadius: 8, backgroundColor: 'rgba(var(--theme-primary), 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgb(var(--theme-primary))' }}>
                <Table2 style={{ width: 15, height: 15 }} />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'rgb(var(--theme-text))', display: 'flex', alignItems: 'center', gap: 8 }}>
                  基础质检结果
                  <Tag style={{ margin: 0, fontSize: 11, padding: '0 6px', height: 18 }}>{basicAuditData.length} 张表</Tag>
                </div>
                <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', marginTop: 2 }}>表数据完整性质量概览</div>
              </div>
            </div>
            {basicAuditExpanded ? <ChevronDown style={{ width: 16, height: 16, color: 'rgb(var(--theme-text-secondary))' }} /> : <ChevronRight style={{ width: 16, height: 16, color: 'rgb(var(--theme-text-secondary))' }} />}
          </div>
          {basicAuditExpanded && (
            <div style={{ padding: 12, maxHeight: 500, overflow: 'auto' }}>
              <div style={{ display: 'grid', gap: 10 }}>
                {basicAuditData.map((table, idx) => (
                  <div key={idx} style={{ borderRadius: 8, border: '1px solid rgb(var(--theme-border))', overflow: 'hidden' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', backgroundColor: 'rgba(var(--theme-primary), 0.04)', borderBottom: '1px solid rgb(var(--theme-border))' }}>
                      <Database style={{ width: 12, height: 12, color: 'rgb(var(--theme-primary))' }} />
                      <span style={{ fontWeight: 600, fontSize: 12, color: 'rgb(var(--theme-text))' }}>{table.schema}.{table.table}</span>
                      <Tag style={{ margin: 0, fontSize: 10 }}>{table.db_type}</Tag>
                      <span style={{ fontSize: 11, color: 'rgb(var(--theme-text-muted))', marginLeft: 'auto' }}>{table.database}</span>
                    </div>
                    <div style={{ padding: 8 }}>
                      <Table
                        size="small"
                        pagination={false}
                        dataSource={table.report}
                        rowKey="column_name"
                        columns={[
                          { title: '列名', dataIndex: 'column_name', key: 'column_name', width: 110, render: (c) => <span style={{ fontWeight: 500, fontSize: 12 }}>{c}</span> },
                          { title: '数据类型', dataIndex: 'data_type', key: 'data_type', width: 130, render: (t) => <span style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', fontFamily: 'monospace' }}>{t}</span> },
                          { title: '总行数', dataIndex: 'total_rows', key: 'total_rows', width: 70, align: 'right' as const, render: (v) => <span style={{ fontSize: 12 }}>{formatNumber(v)}</span> },
                          { title: '空值', dataIndex: 'null_count', key: 'null_count', width: 60, align: 'right' as const, render: (v) => <span style={{ fontSize: 12, color: v > 0 ? '#f5222d' : '#52c41a', fontWeight: v > 0 ? 600 : 400 }}>{formatNumber(v)}</span> },
                          { title: '空串', dataIndex: 'empty_str_count', key: 'empty_str_count', width: 60, align: 'right' as const, render: (v) => <span style={{ fontSize: 12, color: v > 0 ? '#fa8c16' : 'rgb(var(--theme-text-secondary))' }}>{formatNumber(v)}</span> },
                          { title: '缺失率', dataIndex: 'missing_pct', key: 'missing_pct', width: 70, align: 'right' as const, render: (p) => { const v = p || 0; const c = v > 20 ? '#f5222d' : v > 5 ? '#faad14' : '#52c41a'; return <span style={{ fontSize: 12, fontWeight: 600, color: c }}>{v.toFixed(1)}%</span> } },
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


      {/* 基础空值检测详情 */}
      {report.basic_audit_detail && report.basic_audit_detail.results && report.basic_audit_detail.results.length > 0 && (
        <div style={{ borderRadius: 12, border: '1px solid #1890ff30', overflow: 'hidden', backgroundColor: 'rgb(var(--theme-bg))' }}>
          <div
            onClick={() => setBasicAuditDetailExpanded(!basicAuditDetailExpanded)}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', cursor: 'pointer', backgroundColor: 'rgba(24, 144, 255, 0.06)' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 30, height: 30, borderRadius: 8, backgroundColor: 'rgba(24, 144, 255, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#1890ff' }}>
                <ShieldCheck style={{ width: 15, height: 15 }} />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'rgb(var(--theme-text))', display: 'flex', alignItems: 'center', gap: 8 }}>
                  基础质检执行明细
                  <Tag style={{ margin: 0, fontSize: 11, padding: '0 6px', height: 18, backgroundColor: '#1890ff15', borderColor: '#1890ff40', color: '#1890ff' }}>{report.basic_audit_detail.results.length} 条检测</Tag>
                </div>
                <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', marginTop: 2 }}>全库表的空值检测详情（NULL、空字符串、缺失率）</div>
              </div>
            </div>
            {basicAuditDetailExpanded ? <ChevronDown style={{ width: 16, height: 16, color: 'rgb(var(--theme-text-secondary))' }} /> : <ChevronRight style={{ width: 16, height: 16, color: 'rgb(var(--theme-text-secondary))' }} />}
          </div>
          {basicAuditDetailExpanded && (
            <div style={{ padding: 12 }}>
              <Table
                size="small"
                pagination={{ pageSize: 10, showSizeChanger: false }}
                dataSource={report.basic_audit_detail.results}
                rowKey="id"
                columns={[
                  {
                    title: '状态',
                    dataIndex: 'status',
                    key: 'status',
                    width: 45,
                    align: 'center',
                    render: (status) => {
                      if (status === 'passed') return <CheckCircle2 style={{ width: 16, height: 16, color: '#52c41a' }} />
                      if (status === 'failed') return <XCircle style={{ width: 16, height: 16, color: '#f5222d' }} />
                      return <AlertCircle style={{ width: 16, height: 16, color: '#fa8c16' }} />
                    },
                  },
                  { title: '规则名称', dataIndex: 'rule_name', key: 'rule_name', width: 180, ellipsis: true, render: (text) => <Tooltip title={text}><span style={{ fontSize: 12, fontWeight: 500 }}>{text}</span></Tooltip> },
                  { title: '类型', dataIndex: 'rule_type', key: 'rule_type', width: 90, render: (type) => <Tag style={{ fontSize: 11, borderRadius: 4, margin: 0 }}>{ruleTypeLabels[type] || type}</Tag> },
                  { title: '目标表', dataIndex: 'table_name', key: 'table_name', width: 120, ellipsis: true, render: (t) => <span style={{ fontSize: 12 }}>{t}</span> },
                  { title: '列', dataIndex: 'column_name', key: 'column_name', width: 80, ellipsis: true, render: (c) => <span style={{ fontSize: 12, color: c ? undefined : 'rgb(var(--theme-text-muted))' }}>{c || '-'}</span> },
                  { title: '级别', dataIndex: 'severity', key: 'severity', width: 70, render: (sev) => <Tag color={sev === 'critical' ? 'red' : sev === 'warning' ? 'orange' : 'blue'} style={{ fontSize: 11, borderRadius: 4, margin: 0 }}>{severityLabels[sev] || sev}</Tag> },
                  {
                    title: '失败/总数',
                    key: 'counts',
                    width: 90,
                    align: 'right' as const,
                    render: (_, r) => <span style={{ fontSize: 12 }}><span style={{ color: '#f5222d', fontWeight: 600 }}>{r.failed_count}</span> / {r.total_count}</span>,
                  },
                  {
                    title: '失败率',
                    key: 'failed_rate',
                    width: 80,
                    align: 'right' as const,
                    render: (_, r) => {
                      const rate = r.failed_rate ?? 0
                      const color = rate > 5 ? '#f5222d' : rate > 2 ? '#faad14' : '#52c41a'
                      return <span style={{ fontSize: 12, fontWeight: 600, color }}>{rate > 0 ? `${rate.toFixed(2)}%` : '0%'}</span>
                    },
                  },
                  {
                    title: '耗时',
                    dataIndex: 'execution_time_ms',
                    key: 'execution_time_ms',
                    width: 70,
                    align: 'right' as const,
                    render: (ms) => <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>{ms ? (ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(2)}s`) : '-'}</span>,
                  },
                  {
                    title: '详情',
                    key: 'expand',
                    width: 50,
                    align: 'center' as const,
                    render: (_, record) => {
                      const hasDetail = record.executed_sql_text || record.error_message || record.raw_result
                      if (!hasDetail) return <span style={{ color: 'rgb(var(--theme-text-muted))', fontSize: 11 }}>无</span>
                      return (
                        <Button type="text" size="small" icon={expandedRows.has(record.id) ? <ChevronDown style={{ width: 14, height: 14, color: 'rgb(var(--theme-text))' }} /> : <ChevronRight style={{ width: 14, height: 14, color: 'rgb(var(--theme-text))' }} />} onClick={() => toggleExpand(record.id)} style={{ padding: 4 }} />
                      )
                    },
                  },
                ]}
                scroll={{ x: 850 }}
                expandable={{
                  expandedRowRender: (record) => <ExpandedRowDetail record={record} />,
                  expandedRowKeys: Array.from(expandedRows),
                  onExpand: (expanded, record) => toggleExpand(record.id),
                  showExpandColumn: false,
                }}
              />
            </div>
          )}
        </div>
      )}

      {/* 质检规则执行结果 */}
      {qualityAuditData.length > 0 && (
        <div style={{ borderRadius: 12, border: '1px solid #722ed140', overflow: 'hidden', backgroundColor: 'rgb(var(--theme-bg))' }}>
          <div
            onClick={() => setQualityAuditExpanded(!qualityAuditExpanded)}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', cursor: 'pointer', backgroundColor: 'rgba(114, 46, 209, 0.06)' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 30, height: 30, borderRadius: 8, backgroundColor: 'rgba(114, 46, 209, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#722ed1' }}>
                <Shield style={{ width: 15, height: 15 }} />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'rgb(var(--theme-text))', display: 'flex', alignItems: 'center', gap: 8 }}>
                  规则库质检执行明细
                  <Tag style={{ margin: 0, fontSize: 11, padding: '0 6px', height: 18, backgroundColor: '#722ed115', borderColor: '#722ed140', color: '#722ed1' }}>{qualityAuditData.length} 条</Tag>
                </div>
                <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', marginTop: 2 }}>基于规则库的自定义规则执行详情</div>
              </div>
            </div>
            {qualityAuditExpanded ? <ChevronDown style={{ width: 16, height: 16, color: 'rgb(var(--theme-text-secondary))' }} /> : <ChevronRight style={{ width: 16, height: 16, color: 'rgb(var(--theme-text-secondary))' }} />}
          </div>
          {qualityAuditExpanded && (
            <div style={{ padding: 12 }}>
              <Table
                size="small"
                pagination={{ pageSize: 8, showSizeChanger: false }}
                dataSource={qualityAuditData}
                rowKey="id"
                columns={qualityColumns}
                scroll={{ x: 750 }}
                expandable={{
                  expandedRowRender: (record) => <ExpandedRowDetail record={record} />,
                  expandedRowKeys: Array.from(expandedRows),
                  onExpand: (expanded, record) => toggleExpand(record.id),
                  showExpandColumn: false,
                }}
              />
            </div>
          )}
        </div>
      )}

      {/* 关系发现 */}
      {relationCards.length > 0 && (
        <div style={{ borderRadius: 12, border: '1px solid rgb(var(--theme-border))', overflow: 'hidden', backgroundColor: 'rgb(var(--theme-bg))' }}>
          <div
            onClick={() => setRelationExpanded(!relationExpanded)}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', cursor: 'pointer', backgroundColor: 'rgba(var(--theme-primary), 0.04)' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 30, height: 30, borderRadius: 8, backgroundColor: 'rgba(var(--theme-primary), 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgb(var(--theme-primary))' }}>
                <Link2 style={{ width: 15, height: 15 }} />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'rgb(var(--theme-text))', display: 'flex', alignItems: 'center', gap: 8 }}>
                  关系发现
                  <Tag style={{ margin: 0, fontSize: 11, padding: '0 6px', height: 18 }}>{relationCards.length} 个卡片</Tag>
                </div>
                <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', marginTop: 2 }}>点击卡片查看详情</div>
              </div>
            </div>
            {relationExpanded ? <ChevronDown style={{ width: 16, height: 16, color: 'rgb(var(--theme-text-secondary))' }} /> : <ChevronRight style={{ width: 16, height: 16, color: 'rgb(var(--theme-text-secondary))' }} />}
          </div>
          {relationExpanded && (
            <div style={{ padding: 12 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
                {relationCards.map((card, idx) => (
                  <RelationCard key={card.DocInfo?.doc_id || idx} card={card} onClick={() => { setSelectedRelation(card); setRelationModalOpen(true) }} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 历史导出文件 */}
      {historyFiles.length > 0 && (
        <div style={{ borderRadius: 12, border: '1px solid rgb(var(--theme-border))', overflow: 'hidden', backgroundColor: 'rgb(var(--theme-bg))' }}>
          <div
            onClick={() => setHistoryFilesExpanded(!historyFilesExpanded)}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', cursor: 'pointer', backgroundColor: 'rgba(var(--theme-primary), 0.04)' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 30, height: 30, borderRadius: 8, backgroundColor: 'rgba(var(--theme-primary), 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgb(var(--theme-primary))' }}>
                <FileText style={{ width: 15, height: 15 }} />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'rgb(var(--theme-text))', display: 'flex', alignItems: 'center', gap: 8 }}>
                  历史导出文件
                  <Tag style={{ margin: 0, fontSize: 11, padding: '0 6px', height: 18 }}>{historyFiles.length} 个文件</Tag>
                </div>
                <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', marginTop: 2 }}>该报告已导出的所有文件版本</div>
              </div>
            </div>
            {historyFilesExpanded ? <ChevronDown style={{ width: 16, height: 16, color: 'rgb(var(--theme-text-secondary))' }} /> : <ChevronRight style={{ width: 16, height: 16, color: 'rgb(var(--theme-text-secondary))' }} />}
          </div>
          {historyFilesExpanded && (
            <div style={{ padding: 12 }}>
              <div style={{ display: 'grid', gap: 10 }}>
                {historyFiles.map((file, idx) => (
                  <div
                    key={file.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '12px 14px',
                      borderRadius: 10,
                      border: '1px solid rgb(var(--theme-border))',
                      backgroundColor: 'rgb(var(--theme-bg))',
                      gap: 16,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1, minWidth: 0 }}>
                      <div style={{ width: 36, height: 36, borderRadius: 8, backgroundColor: 'rgba(var(--theme-primary), 0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <FileText style={{ width: 18, height: 18, color: 'rgb(var(--theme-primary))' }} />
                      </div>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ fontSize: 13, fontWeight: 500, color: 'rgb(var(--theme-text))', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginBottom: 4 }}>
                          {file.file_name}
                        </div>
                        <div style={{ fontSize: 11, color: 'rgb(var(--theme-text-muted))', display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ padding: '1px 6px', borderRadius: 3, backgroundColor: 'rgba(var(--theme-primary), 0.08)', color: 'rgb(var(--theme-primary))', fontWeight: 500 }}>
                            {file.file_type.toUpperCase()}
                          </span>
                          <span>{file.file_size > 1024 * 1024 ? `${(file.file_size / (1024 * 1024)).toFixed(2)} MB` : file.file_size > 1024 ? `${(file.file_size / 1024).toFixed(2)} KB` : `${file.file_size} B`}</span>
                          <span>·</span>
                          <span>{new Date(file.created_at).toLocaleString('zh-CN')}</span>
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                      <button
                        onClick={() => handleDownloadHistoryFile(file.id)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          padding: '6px 12px',
                          borderRadius: 6,
                          fontSize: 12,
                          fontWeight: 500,
                          color: 'white',
                          backgroundColor: 'rgb(var(--theme-primary))',
                          border: 'none',
                          cursor: 'pointer',
                        }}
                      >
                        <Download style={{ width: 12, height: 12 }} />
                        下载
                      </button>
                      <button
                        onClick={() => handleDeleteHistoryFile(file.id, file.file_name)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          padding: '6px 12px',
                          borderRadius: 6,
                          fontSize: 12,
                          fontWeight: 500,
                          color: '#ff4d4f',
                          backgroundColor: 'rgba(255, 77, 79, 0.08)',
                          border: 'none',
                          cursor: 'pointer',
                        }}
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="3 6 5 6 21 6" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                        删除
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 空状态 */}
      {qualityAuditData.length === 0 && basicAuditData.length === 0 && relationCards.length === 0 && basicAuditDetailData.length === 0 && (
        <div style={{ padding: 60, borderRadius: 12, border: '1px dashed rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg-secondary))', textAlign: 'center' }}>
          <BookOpen style={{ width: 48, height: 48, color: 'rgb(var(--theme-text-muted))', opacity: 0.3, margin: '0 auto' }} />
          <p style={{ marginTop: 16, fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text-secondary))' }}>暂无详细数据</p>
        </div>
      )}

      {/* 关系详情弹框 */}
      <RelationDetailModal
        card={selectedRelation}
        allRelationships={allRelationships}
        open={relationModalOpen}
        onClose={() => setRelationModalOpen(false)}
      />

      {/* 重复导出确认弹框 */}
      <Modal
        title="重复导出确认"
        open={reExportConfirmOpen}
        onOk={handleConfirmReExport}
        onCancel={() => setReExportConfirmOpen(false)}
        okText="确认导出"
        cancelText="取消"
        centered
      >
        <div style={{ padding: '8px 0' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '12px 14px', borderRadius: 10, backgroundColor: 'rgba(250, 140, 22, 0.08)', border: '1px solid rgba(250, 140, 22, 0.2)', marginBottom: 16 }}>
            <AlertCircle style={{ width: 20, height: 20, color: '#fa8c16', flexShrink: 0, marginTop: 2 }} />
            <div>
              <div style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 4 }}>
                报告已导出过文件，是否重复导出？
              </div>
              {report.exported_file_name && (
                <div style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))' }}>
                  上次导出: {report.exported_file_name}
                  {report.file_size && ` (${(report.file_size / 1024).toFixed(1)}KB)`}
                </div>
              )}
            </div>
          </div>
          <p style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))', margin: 0 }}>
            点击"确认导出"将重新生成报告文件，确认后可修改报告名称和文件格式。
          </p>
        </div>
      </Modal>

      {/* 生成报告弹框 */}
      <Modal
        title="生成报告"
        open={generateModalOpen}
        onOk={handleConfirmGenerate}
        onCancel={() => setGenerateModalOpen(false)}
        confirmLoading={generatingFile}
        okText={generatingFile ? '生成中...' : '确认生成'}
        cancelText="取消"
        centered
        styles={{ body: { paddingTop: 16 } }}
        okButtonProps={{ disabled: !!fileNameError }}
      >
        <div style={{ display: 'grid', gap: 16 }}>
          <div>
            <label style={{ fontSize: 14, color: 'rgb(var(--theme-text-secondary))', marginBottom: 6, display: 'block' }}>
              文件名称（选填）
            </label>
            <Input
              value={generateReportName}
              onChange={(e) => {
                setGenerateReportName(e.target.value)
                setFileNameError(validateFileName(e.target.value))
              }}
              placeholder="留空则使用系统默认名称"
              status={fileNameError ? 'error' : ''}
            />
            {fileNameError && (
              <p style={{ fontSize: 12, color: '#ff4d4f', margin: '4px 0 0' }}>
                {fileNameError}
              </p>
            )}
          </div>
          <div>
            <label style={{ fontSize: 14, color: 'rgb(var(--theme-text-secondary))', marginBottom: 6, display: 'block' }}>
              文件类型
            </label>
            <Radio.Group
              value={generateFormat}
              onChange={(e) => setGenerateFormat(e.target.value)}
              style={{ width: '100%' }}
            >
              <Radio value="md">Markdown (.md)</Radio>
            </Radio.Group>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default function ReportDetailPage() {
  return (
    <Suspense fallback={
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <Loader2 style={{ width: 48, height: 48, color: 'rgb(var(--theme-primary))', animation: 'spin 1s linear infinite' }} />
        <p style={{ marginTop: 20, color: 'rgb(var(--theme-text-muted))', fontSize: 14 }}>加载中...</p>
      </div>
    }>
      <ReportDetailPageContent />
    </Suspense>
  )
}
