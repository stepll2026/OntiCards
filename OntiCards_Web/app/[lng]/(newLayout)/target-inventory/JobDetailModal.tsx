'use client'

import React, { useState, useEffect } from 'react'
import { Modal, Tabs, Spin, message, Table, Tag, Card, Descriptions, Empty, Progress, Collapse, Button, Popconfirm } from 'antd'
import {
  DatabaseOutlined,
  LinkOutlined,
  ApartmentOutlined,
  CheckCircleOutlined,
  MergeCellsOutlined,
  HistoryOutlined,
  DeleteOutlined,
  ReloadOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import {
  getHistoryJobDetail,
  getHistoryFieldRecommendations,
  getHistoryTableRelationships,
  getHistoryRelationshipCards,
  getHistoryGraph,
  getHistoryConfirmations,
  getHistoryFieldMappingsConfirmed,
  deleteTargetInventoryRelationships,
  type HistoryJobItem,
  type RelationshipCard,
  type GraphData,
  type FieldMappingItem
} from '@/api/targetInventory'
import dynamic from 'next/dynamic'

// 动态导入定向盘点的关系图谱组件
const TargetInventoryRelationshipGraph = dynamic(
  () => import('./TargetInventoryRelationshipGraph'),
  {
    ssr: false,
    loading: () => <div className="flex items-center justify-center h-96"><Spin size="large" tip="加载图谱组件..." /></div>
  }
)

const { TabPane } = Tabs
const { Panel } = Collapse

interface JobDetailModalProps {
  visible: boolean
  job: HistoryJobItem | null
  onClose: () => void
}

// 关系方向映射
const DIRECTION_LABELS: Record<string, string> = {
  'one_to_one': '1:1',
  'one_to_many': '1:N',
  'many_to_one': 'N:1',
  'many_to_many': 'N:N',
}

const JobDetailModal: React.FC<JobDetailModalProps> = ({ visible, job, onClose }) => {
  const [activeTab, setActiveTab] = useState('field-recommendations')
  const [loading, setLoading] = useState(false)

  // 各Tab数据
  const [fieldRecommendations, setFieldRecommendations] = useState<any>(null)
  const [tableRelationships, setTableRelationships] = useState<any[]>([])
  const [relationshipCards, setRelationshipCards] = useState<RelationshipCard[]>([])
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [confirmations, setConfirmations] = useState<any>(null)
  const [fieldMappingsConfirmed, setFieldMappingsConfirmed] = useState<{
    field_mappings: FieldMappingItem[]
    total: number
    by_table: Record<string, FieldMappingItem[]>
  } | null>(null)

  // 加载状态
  const [loadingField, setLoadingField] = useState(false)
  const [loadingRelations, setLoadingRelations] = useState(false)
  const [loadingCards, setLoadingCards] = useState(false)
  const [loadingGraph, setLoadingGraph] = useState(false)
  const [loadingFieldMappings, setLoadingFieldMappings] = useState(false)
  const [deleting, setDeleting] = useState(false)

  // 深色模式检测
  const [isDark, setIsDark] = useState(false)

  useEffect(() => {
    const checkDark = () => {
      const dark = document.documentElement.getAttribute('data-theme') === 'dark'
      setIsDark(dark)
    }

    checkDark()

    const observer = new MutationObserver(checkDark)
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme']
    })

    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (visible && job) {
      setActiveTab('field-recommendations')
      loadFieldRecommendations()
    }
  }, [visible, job])

  useEffect(() => {
    if (visible && job) {
      switch (activeTab) {
        case 'field-recommendations':
          if (!fieldRecommendations) loadFieldRecommendations()
          break
        case 'table-relationships':
          if (tableRelationships.length === 0) loadTableRelationships()
          break
        case 'relationship-cards':
          if (relationshipCards.length === 0) loadRelationshipCards()
          break
        case 'relationship-graph':
          if (!graphData) loadGraphData()
          break
        case 'field-mappings-confirmed':
          if (!fieldMappingsConfirmed) loadFieldMappingsConfirmed()
          break
      }
    }
  }, [activeTab])

  const loadFieldRecommendations = async () => {
    if (!job) return
    setLoadingField(true)
    try {
      const response = await getHistoryFieldRecommendations(job.job_id)
      if (response.code === 200 && response.data) {
        setFieldRecommendations(response.data)
      }
    } catch (error) {
      console.error('加载字段推荐失败:', error)
    } finally {
      setLoadingField(false)
    }
  }

  const loadTableRelationships = async () => {
    if (!job) return
    setLoadingRelations(true)
    try {
      const response = await getHistoryTableRelationships(job.job_id)
      if (response.code === 200 && response.data) {
        setTableRelationships(response.data.relationships || [])
        // 同时加载确认记录
        const confirmRes = await getHistoryConfirmations(job.job_id)
        if (confirmRes.code === 200 && confirmRes.data) {
          setConfirmations(confirmRes.data)
        }
        // 同时加载关系卡片数据（用于辅助判断确认状态）
        const cardsRes = await getHistoryRelationshipCards(job.job_id)
        if (cardsRes.code === 200 && cardsRes.data) {
          setRelationshipCards(cardsRes.data.cards || [])
        }
      }
    } catch (error) {
      console.error('加载表关系失败:', error)
    } finally {
      setLoadingRelations(false)
    }
  }

  const loadRelationshipCards = async () => {
    if (!job) return
    setLoadingCards(true)
    try {
      const response = await getHistoryRelationshipCards(job.job_id)
      if (response.code === 200 && response.data) {
        setRelationshipCards(response.data.cards || [])
      }
    } catch (error) {
      console.error('加载关系卡片失败:', error)
    } finally {
      setLoadingCards(false)
    }
  }

  const loadGraphData = async () => {
    if (!job) return
    setLoadingGraph(true)

    try {
      // 如果关系卡片还没加载，一起加载；否则只加载图谱数据
      if (relationshipCards.length === 0) {
        setLoadingCards(true)
        const [graphRes, cardsRes] = await Promise.all([
          getHistoryGraph(job.job_id),
          getHistoryRelationshipCards(job.job_id)
        ])

        if (graphRes.code === 200 && graphRes.data) {
          setGraphData(graphRes.data)
        }

        if (cardsRes.code === 200 && cardsRes.data && cardsRes.data.cards) {
          setRelationshipCards(cardsRes.data.cards || [])
        }
        setLoadingCards(false)
      } else {
        // 关系卡片已加载，只加载图谱数据
        const graphRes = await getHistoryGraph(job.job_id)
        if (graphRes.code === 200 && graphRes.data) {
          setGraphData(graphRes.data)
        }
      }
    } catch (error) {
      console.error('加载关系图谱失败:', error)
      setLoadingCards(false)
    } finally {
      setLoadingGraph(false)
    }
  }

  const loadFieldMappingsConfirmed = async () => {
    if (!job) return
    setLoadingFieldMappings(true)
    try {
      const response = await getHistoryFieldMappingsConfirmed(job.job_id)
      if (response.code === 200 && response.data) {
        setFieldMappingsConfirmed(response.data)
      }
    } catch (error) {
      console.error('加载字段映射确认结果失败:', error)
    } finally {
      setLoadingFieldMappings(false)
    }
  }

  // 删除关系数据
  const handleDeleteRelationships = async () => {
    if (!job?.job_id) {
      message.warning('无法获取任务信息')
      return
    }

    setDeleting(true)
    try {
      const response = await deleteTargetInventoryRelationships(job.job_id)

      if (response.code === 200) {
        message.success(`已删除 ${response.data.deleted_relationships} 个关系和 ${response.data.deleted_cards} 个卡片`)
        // 清空关系相关数据
        setRelationshipCards([])
        setTableRelationships([])
        setGraphData(null)
        // 重新加载关系图谱数据
        loadGraphData()
      } else {
        message.error(response.msg || '删除失败')
      }
    } catch (error: any) {
      console.error('删除关系数据失败:', error)
      message.error(error?.message || '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  const handleClose = () => {
    // 重置状态
    setFieldRecommendations(null)
    setTableRelationships([])
    setRelationshipCards([])
    setGraphData(null)
    setConfirmations(null)
    setFieldMappingsConfirmed(null)
    onClose()
  }

  // 表关系列表列定义
  const relationshipColumns: ColumnsType<any> = [
    {
      title: '源表',
      dataIndex: 'from_table',
      key: 'from_table',
      width: 150,
      render: (text) => <Tag color="blue">{text}</Tag>
    },
    {
      title: '源字段',
      dataIndex: 'from_column',
      key: 'from_column',
      width: 120,
      render: (text) => <span className="font-mono text-blue-600">{text}</span>
    },
    {
      title: '目标表',
      dataIndex: 'to_table',
      key: 'to_table',
      width: 150,
      render: (text) => <Tag color="green">{text}</Tag>
    },
    {
      title: '目标字段',
      dataIndex: 'to_column',
      key: 'to_column',
      width: 120,
      render: (text) => <span className="font-mono text-green-600">{text}</span>
    },
    {
      title: '关系类型',
      dataIndex: 'relationship_type',
      key: 'relationship_type',
      width: 100,
      render: (type) => {
        const typeMap: Record<string, { label: string; color: string }> = {
          'foreign_key': { label: '外键', color: 'red' },
          'semantic': { label: '语义', color: 'purple' },
          'synonym': { label: '同义', color: 'blue' },
          'name_based': { label: '命名', color: 'cyan' },
          'shared_field': { label: '共享字段', color: 'orange' },
          'value_overlap': { label: '值域重叠', color: 'default' }
        }
        const config = typeMap[type] || { label: type, color: 'default' }
        return <Tag color={config.color}>{config.label}</Tag>
      }
    },
    {
      title: '基数',
      dataIndex: 'cardinality',
      key: 'cardinality',
      width: 80,
      render: (cardinality) => cardinality ? (
        <Tag>{DIRECTION_LABELS[cardinality] || cardinality}</Tag>
      ) : '-'
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 120,
      render: (confidence) => (
        <Progress
          percent={Math.round((confidence || 0) * 100)}
          size="small"
          strokeColor={confidence >= 0.8 ? '#52c41a' : confidence >= 0.6 ? '#faad14' : '#ff4d4f'}
          style={{ width: 80 }}
        />
      )
    },
    {
      title: '确认状态',
      key: 'confirmed',
      width: 100,
      render: (_, record) => {
        // 首先检查记录本身是否有确认状态字段
        if (record.is_confirmed || record.confirmed) {
          return <Tag icon={<CheckCircleOutlined />} color="success">已确认</Tag>
        }

        // 检查 confirmations 数据中的嵌套结构
        const tableRelConfirmations = confirmations?.table_relationships?.confirmations
        if (Array.isArray(tableRelConfirmations)) {
          const isConfirmed = tableRelConfirmations.some(
            (c: any) =>
              c.from_table === record.from_table &&
              c.from_column === record.from_column &&
              c.to_table === record.to_table &&
              c.to_column === record.to_column
          )
          if (isConfirmed) {
            return <Tag icon={<CheckCircleOutlined />} color="success">已确认</Tag>
          }
        }

        // 检查 confirmations 本身是否是数组（直接返回确认列表的情况）
        if (Array.isArray(confirmations)) {
          const isConfirmed = confirmations.some(
            (c: any) =>
              c.from_table === record.from_table &&
              c.from_column === record.from_column &&
              c.to_table === record.to_table &&
              c.to_column === record.to_column
          )
          if (isConfirmed) {
            return <Tag icon={<CheckCircleOutlined />} color="success">已确认</Tag>
          }
        }

        // 检查 confirmations.confirmations 路径（另一种可能的结构）
        if (Array.isArray(confirmations?.confirmations)) {
          const isConfirmed = confirmations.confirmations.some(
            (c: any) =>
              c.from_table === record.from_table &&
              c.from_column === record.from_column &&
              c.to_table === record.to_table &&
              c.to_column === record.to_column
          )
          if (isConfirmed) {
            return <Tag icon={<CheckCircleOutlined />} color="success">已确认</Tag>
          }
        }

        // 检查 relationshipCards 数据（通过已创建的卡片判断确认状态）
        if (relationshipCards && relationshipCards.length > 0) {
          const cardExists = relationshipCards.some((card: any) => {
            // 检查卡片的表是否匹配
            const tablesMatch =
              (card.from_table === record.from_table && card.to_table === record.to_table) ||
              (card.table1 === record.from_table && card.table2 === record.to_table) ||
              (card.from_table === record.to_table && card.to_table === record.from_table) ||
              (card.table1 === record.to_table && card.table2 === record.from_table)

            if (!tablesMatch) return false

            // 进一步检查字段是否匹配
            if (card.fields && Array.isArray(card.fields)) {
              return card.fields.some((f: any) =>
                (f.from_column === record.from_column && f.to_column === record.to_column) ||
                (f.from_column === record.to_column && f.to_column === record.from_column)
              )
            }

            // 如果没有 fields 信息，只要表匹配就认为已确认
            return true
          })
          if (cardExists) {
            return <Tag icon={<CheckCircleOutlined />} color="success">已确认</Tag>
          }
        }

        return <Tag color="default">未确认</Tag>
      }
    }
  ]

  // 格式化分数显示 - 兼容多种字段名和直接传入数值
  const formatScore = (candidate: any): string => {
    let score: number | undefined | null

    // 如果直接传入的是数字，直接使用
    if (typeof candidate === 'number') {
      score = candidate
    } else {
      // 尝试多种可能的字段名
      score = candidate?.score ?? candidate?.confidence ?? candidate?.similarity ?? candidate?.match_score
    }

    if (score === undefined || score === null || isNaN(Number(score))) {
      return '-'
    }
    const numScore = Number(score)
    // 如果分数大于1，说明已经是百分比形式
    if (numScore > 1) {
      return `${Math.round(numScore)}%`
    }
    return `${Math.round(numScore * 100)}%`
  }

  // 获取分数的数值（用于颜色判断）
  const getScoreValue = (candidate: any): number => {
    let score: number | undefined | null

    // 如果直接传入的是数字，直接使用
    if (typeof candidate === 'number') {
      score = candidate
    } else {
      score = candidate?.score ?? candidate?.confidence ?? candidate?.similarity ?? candidate?.match_score
    }

    if (score === undefined || score === null || isNaN(Number(score))) {
      return 0
    }
    const numScore = Number(score)
    // 如果分数大于1，说明已经是百分比形式，转换为0-1
    return numScore > 1 ? numScore / 100 : numScore
  }

  // 渲染字段推荐内容
  const renderFieldRecommendations = () => {
    if (loadingField) {
      return <div className="flex justify-center py-12"><Spin size="large" /></div>
    }

    if (!fieldRecommendations || !fieldRecommendations.recommendations || Object.keys(fieldRecommendations.recommendations).length === 0) {
      return (
        <div className="flex flex-col items-center justify-center py-16" style={{ minHeight: 'calc(100vh - 420px)' }}>
          <Empty description="暂无字段推荐数据" style={{ color: isDark ? '#94a3b8' : '#6b7280' }} />
        </div>
      )
    }

    const recommendations = fieldRecommendations.recommendations
    const confirmed = fieldRecommendations.confirmed || {}

    return (
      <div className="space-y-4">
        {fieldRecommendations.confirmed_at && (
          <div className="text-sm mb-4" style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>
            确认时间：{new Date(fieldRecommendations.confirmed_at).toLocaleString('zh-CN')}
          </div>
        )}

        <Collapse
          defaultActiveKey={Object.keys(recommendations).slice(0, 1)}
          style={{ background: isDark ? '#0f172a' : '#ffffff' }}
        >
          {Object.entries(recommendations).map(([tableName, fields]: [string, any]) => (
            <Panel
              header={
                <div className="flex items-center gap-2">
                  <DatabaseOutlined style={{ color: isDark ? '#60a5fa' : '#3b82f6' }} />
                  <span className="font-medium" style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>{tableName}</span>
                  <Tag style={{ background: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', color: isDark ? '#93c5fd' : '#1d4ed8', borderColor: 'transparent' }}>{Object.keys(fields).length} 个字段</Tag>
                </div>
              }
              key={tableName}
              style={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb' }}
            >
              <div className="space-y-3" style={{ background: isDark ? '#0f172a' : '#ffffff' }}>
                {Object.entries(fields).map(([fieldName, fieldData]: [string, any]) => {
                  const confirmedField = confirmed[tableName]?.[fieldName]
                  return (
                    <Card
                      key={fieldName}
                      size="small"
                      style={{ background: isDark ? '#1e293b' : '#f9fafc', borderColor: isDark ? '#334155' : '#e5e7eb' }}
                      headStyle={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb', color: isDark ? '#f1f5f9' : '#1e293b' }}
                      bodyStyle={{ background: isDark ? '#1e293b' : '#ffffff', color: isDark ? '#f1f5f9' : '#1e293b' }}
                    >
                      <div className="flex flex-col">
                        <div className="flex items-center gap-2 mb-3 pb-2" style={{ borderBottom: `1px solid ${isDark ? '#334155' : '#e5e7eb'}` }}>
                          <span className="font-semibold text-base" style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>{fieldName}</span>
                          {confirmedField && (
                            <Tag icon={<CheckCircleOutlined />} style={{ background: isDark ? 'rgba(34, 197, 94, 0.2)' : '#dcfce7', color: isDark ? '#4ade80' : '#16a34a', borderColor: 'transparent' }}>
                              已确认
                            </Tag>
                          )}
                        </div>
                        {fieldData.profile && (
                          <div className="text-xs mb-3 p-2 rounded" style={{ background: isDark ? 'rgba(59, 130, 246, 0.1)' : '#eff6ff', color: isDark ? '#94a3b8' : '#6b7280' }}>
                            {fieldData.profile.sample_values && fieldData.profile.sample_values.length > 0 && (
                              <div className="flex items-start gap-2">
                                <span className="font-medium whitespace-nowrap" style={{ color: isDark ? '#64748b' : '#4b5563' }}>样本值:</span>
                                <span style={{ color: isDark ? '#e2e8f0' : '#374151' }}>
                                  {fieldData.profile.sample_values.slice(0, 5).join(', ')}
                                </span>
                              </div>
                            )}
                            {fieldData.profile.distinct_count !== undefined && (
                              <div className="mt-1">
                                <span className="font-medium" style={{ color: isDark ? '#64748b' : '#4b5563' }}>去重数量:</span>
                                <span className="ml-1" style={{ color: isDark ? '#e2e8f0' : '#374151' }}>{fieldData.profile.distinct_count}</span>
                              </div>
                            )}
                          </div>
                        )}
                        <div className="space-y-2">
                          <div className="text-xs font-medium" style={{ color: isDark ? '#64748b' : '#6b7280' }}>推荐候选:</div>
                          {fieldData.candidates?.slice(0, 5).map((candidate: any, idx: number) => {
                            const scoreValue = getScoreValue(candidate)
                            const scoreDisplay = formatScore(candidate)
                            return (
                              <div
                                key={idx}
                                className="flex items-center gap-2 text-sm p-2.5 rounded border transition-colors"
                                style={{
                                  background: confirmedField?.selected_ref === `${candidate.table_name}.${candidate.column_name}`
                                    ? (isDark ? 'rgba(34, 197, 94, 0.1)' : '#f0fdf4')
                                    : (isDark ? '#1e293b' : '#ffffff'),
                                  borderColor: confirmedField?.selected_ref === `${candidate.table_name}.${candidate.column_name}`
                                    ? (isDark ? 'rgba(34, 197, 94, 0.5)' : '#bbf7d0')
                                    : (isDark ? '#334155' : '#e5e7eb')
                                }}
                              >
                                {/* 来源标识：LLM推断、字典文件或参考表 */}
                                {candidate.source_type === 'llm' ? (
                                  <Tag style={{ background: isDark ? 'rgba(139, 92, 246, 0.3)' : '#ede9fe', color: isDark ? '#c084fc' : '#7c3aed', borderColor: 'transparent' }} className="shrink-0">LLM推断</Tag>
                                ) : candidate.source_type === 'dict' || !candidate.table_name ? (
                                  <Tag style={{ background: isDark ? 'rgba(34, 197, 94, 0.2)' : '#dcfce7', color: isDark ? '#4ade80' : '#16a34a', borderColor: 'transparent' }} className="shrink-0">字典文件</Tag>
                                ) : (
                                  <Tag style={{ background: isDark ? 'rgba(6, 182, 212, 0.2)' : '#cffafe', color: isDark ? '#67e8f9' : '#0891b2', borderColor: 'transparent' }} className="shrink-0">{candidate.table_name}</Tag>
                                )}
                                <span className="font-mono font-medium" style={{ color: isDark ? '#60a5fa' : '#2563eb' }}>{candidate.column_name}</span>
                                {candidate.column_comment && (
                                  <span className="text-xs" style={{ color: isDark ? '#64748b' : '#9ca3af' }}>({candidate.column_comment})</span>
                                )}
                                <div className="ml-auto flex items-center gap-2 shrink-0">
                                  {scoreDisplay !== '-' && (
                                    <Tag style={{
                                      background: scoreValue >= 0.8 ? (isDark ? 'rgba(34, 197, 94, 0.2)' : '#dcfce7') : scoreValue >= 0.6 ? (isDark ? 'rgba(251, 191, 36, 0.3)' : '#fef3c7') : (isDark ? 'rgba(148, 163, 184, 0.2)' : '#f3f4f6'),
                                      color: scoreValue >= 0.8 ? (isDark ? '#4ade80' : '#16a34a') : scoreValue >= 0.6 ? (isDark ? '#fbbf24' : '#ca8a04') : (isDark ? '#94a3b8' : '#6b7280'),
                                      borderColor: 'transparent'
                                    }}>
                                      {scoreDisplay}
                                    </Tag>
                                  )}
                                  {candidate.match_type && (
                                    <Tag style={{ background: isDark ? 'rgba(139, 92, 246, 0.2)' : '#ede9fe', color: isDark ? '#a5b4fc' : '#7c3aed', borderColor: 'transparent' }}>{candidate.match_type}</Tag>
                                  )}
                                </div>
                              </div>
                            )
                          })}
                          {(!fieldData.candidates || fieldData.candidates.length === 0) && (
                            <div className="text-sm p-2" style={{ color: isDark ? '#64748b' : '#9ca3af' }}>暂无推荐候选</div>
                          )}
                        </div>
                      </div>
                    </Card>
                  )
                })}
              </div>
            </Panel>
          ))}
        </Collapse>
      </div>
    )
  }

  // 渲染关系卡片内容
  const renderRelationshipCards = () => {
    if (loadingCards) {
      return <div className="flex justify-center py-12"><Spin size="large" /></div>
    }

    // 防御性检查：确保 relationshipCards 是数组
    if (!Array.isArray(relationshipCards) || relationshipCards.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center py-16" style={{ minHeight: 'calc(100vh - 420px)' }}>
          <Empty description="暂无关系卡片数据" style={{ color: isDark ? '#94a3b8' : '#6b7280' }} />
        </div>
      )
    }

    return (
      <div className="grid grid-cols-1 gap-4">
        {relationshipCards.map((card, index) => (
          <Card
            key={index}
            size="small"
            title={
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Tag style={{ background: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', color: isDark ? '#93c5fd' : '#1d4ed8', borderColor: 'transparent' }}>{card.from_table || card.table1}</Tag>
                  <span style={{ color: isDark ? '#64748b' : '#9ca3af' }}>↔</span>
                  <Tag style={{ background: isDark ? 'rgba(34, 197, 94, 0.2)' : '#dcfce7', color: isDark ? '#4ade80' : '#16a34a', borderColor: 'transparent' }}>{card.to_table || card.table2}</Tag>
                </div>
                <div className="flex items-center gap-2">
                  {card.direction && (
                    <Tag style={{ background: isDark ? 'rgba(139, 92, 246, 0.3)' : '#ede9fe', color: isDark ? '#a5b4fc' : '#7c3aed', borderColor: 'transparent' }}>
                      {DIRECTION_LABELS[card.direction] || card.direction}
                    </Tag>
                  )}
                  {card.is_cross_source && (
                    <Tag style={{ background: isDark ? 'rgba(251, 191, 36, 0.3)' : '#fef3c7', color: isDark ? '#fbbf24' : '#92400e', borderColor: 'transparent' }}>跨数据源</Tag>
                  )}
                </div>
              </div>
            }
            style={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb' }}
            headStyle={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb', color: isDark ? '#f1f5f9' : '#1e293b' }}
            bodyStyle={{ background: isDark ? '#1e293b' : '#ffffff' }}
          >
            <div className="space-y-4">
              {/* 简洁的关系概览 */}
              <div className="flex items-center justify-between text-sm rounded p-2" style={{ background: isDark ? '#0f172a' : '#f9fafb' }}>
                <div className="flex items-center gap-3">
                  <span style={{ color: isDark ? '#64748b' : '#6b7280' }}>关联字段:</span>
                  <span className="font-semibold" style={{ color: isDark ? '#f1f5f9' : '#374151' }}>{card.fields?.length || 0} 个</span>
                </div>
                <div className="flex items-center gap-3">
                  <span style={{ color: isDark ? '#64748b' : '#6b7280' }}>整体置信度:</span>
                  <span className="font-semibold" style={{
                    color: (card.confidence || 0) >= 0.8 ? (isDark ? '#4ade80' : '#16a34a') :
                           (card.confidence || 0) >= 0.6 ? (isDark ? '#fbbf24' : '#ca8a04') : (isDark ? '#64748b' : '#6b7280')
                  }}>
                    {((card.confidence || 0) * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* 业务角色 */}
              {card.business_relation && (
                <div className="rounded-lg p-3" style={{ background: isDark ? 'rgba(99, 102, 241, 0.1)' : '#eef2ff' }}>
                  <div className="flex items-center gap-4">
                    <span className="text-sm font-medium" style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>业务角色：</span>
                    <div className="flex items-center gap-2">
                      <Tag style={{
                        background: card.business_relation.from_role === 'master' ? (isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe') :
                                   card.business_relation.from_role === 'detail' ? (isDark ? 'rgba(34, 197, 94, 0.2)' : '#dcfce7') :
                                   card.business_relation.from_role === 'dimension' ? (isDark ? 'rgba(139, 92, 246, 0.3)' : '#ede9fe') : (isDark ? 'rgba(251, 191, 36, 0.3)' : '#fef3c7'),
                        color: card.business_relation.from_role === 'master' ? (isDark ? '#93c5fd' : '#1d4ed8') :
                               card.business_relation.from_role === 'detail' ? (isDark ? '#4ade80' : '#16a34a') :
                               card.business_relation.from_role === 'dimension' ? (isDark ? '#a5b4fc' : '#7c3aed') : (isDark ? '#fbbf24' : '#92400e'),
                        borderColor: 'transparent'
                      }}>
                        {card.business_relation.from_role === 'master' ? '主表' :
                         card.business_relation.from_role === 'detail' ? '明细表' :
                         card.business_relation.from_role === 'dimension' ? '维度表' : '事实表'}
                      </Tag>
                      {card.business_relation.from_entity && (
                        <span className="text-xs" style={{ color: isDark ? '#64748b' : '#9ca3af' }}>({card.business_relation.from_entity})</span>
                      )}
                    </div>
                    <span style={{ color: isDark ? '#475569' : '#d1d5db' }}>→</span>
                    <div className="flex items-center gap-2">
                      <Tag style={{
                        background: card.business_relation.to_role === 'master' ? (isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe') :
                                   card.business_relation.to_role === 'detail' ? (isDark ? 'rgba(34, 197, 94, 0.2)' : '#dcfce7') :
                                   card.business_relation.to_role === 'dimension' ? (isDark ? 'rgba(139, 92, 246, 0.3)' : '#ede9fe') : (isDark ? 'rgba(251, 191, 36, 0.3)' : '#fef3c7'),
                        color: card.business_relation.to_role === 'master' ? (isDark ? '#93c5fd' : '#1d4ed8') :
                               card.business_relation.to_role === 'detail' ? (isDark ? '#4ade80' : '#16a34a') :
                               card.business_relation.to_role === 'dimension' ? (isDark ? '#a5b4fc' : '#7c3aed') : (isDark ? '#fbbf24' : '#92400e'),
                        borderColor: 'transparent'
                      }}>
                        {card.business_relation.to_role === 'master' ? '主表' :
                         card.business_relation.to_role === 'detail' ? '明细表' :
                         card.business_relation.to_role === 'dimension' ? '维度表' : '事实表'}
                      </Tag>
                      {card.business_relation.to_entity && (
                        <span className="text-xs" style={{ color: isDark ? '#64748b' : '#9ca3af' }}>({card.business_relation.to_entity})</span>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* 关联字段详情 */}
              <div>
                <div className="text-sm font-medium mb-3 flex items-center gap-2" style={{ color: isDark ? '#f1f5f9' : '#374151' }}>
                  <LinkOutlined style={{ color: isDark ? '#60a5fa' : '#3b82f6' }} />
                  关联字段详情
                  <span style={{ color: isDark ? '#64748b' : '#9ca3af', fontWeight: 'normal' }}>({card.fields?.length || 0} 个)</span>
                </div>
                <div className="space-y-2">
                  {card.fields && card.fields.length > 0 ? (
                    card.fields.map((field, fidx) => (
                      <Card key={fidx} size="small" style={{ background: isDark ? '#0f172a' : '#f9fafb', borderColor: isDark ? '#334155' : '#e5e7eb' }} bodyStyle={{ background: isDark ? '#0f172a' : '#f9fafb' }}>
                        <div className="space-y-2">
                          {/* 字段映射 */}
                          <div className="flex items-center gap-2">
                            <div className="flex items-baseline gap-1">
                              <span className="font-mono font-semibold" style={{ color: isDark ? '#60a5fa' : '#2563eb' }}>{field.from_column}</span>
                              <span className="text-xs" style={{ color: isDark ? '#64748b' : '#9ca3af' }}>({field.from_table})</span>
                            </div>
                            <span className="mx-1" style={{ color: isDark ? '#475569' : '#d1d5db' }}>→</span>
                            {field.cardinality && (
                              <Tag style={{ background: isDark ? 'rgba(148, 163, 184, 0.2)' : '#f3f4f6', color: isDark ? '#94a3b8' : '#6b7280', borderColor: 'transparent' }} className="mx-0">
                                {DIRECTION_LABELS[field.cardinality] || field.cardinality}
                              </Tag>
                            )}
                            <span className="mx-1" style={{ color: isDark ? '#475569' : '#d1d5db' }}>→</span>
                            <div className="flex items-baseline gap-1">
                              <span className="text-xs" style={{ color: isDark ? '#64748b' : '#9ca3af' }}>({field.to_table})</span>
                              <span className="font-mono font-semibold" style={{ color: isDark ? '#4ade80' : '#16a34a' }}>{field.to_column}</span>
                            </div>
                          </div>

                          {/* 关系类型和置信度 */}
                          <div className="flex items-center justify-between pt-2" style={{ borderTop: `1px solid ${isDark ? '#334155' : '#e5e7eb'}` }}>
                            <div className="flex items-center gap-2">
                              <Tag style={{
                                background: field.type === 'foreign_key' ? (isDark ? 'rgba(34, 197, 94, 0.2)' : '#dcfce7') :
                                           field.type === 'semantic' ? (isDark ? 'rgba(59, 130, 246, 0.2)' : '#dbeafe') :
                                           field.type === 'synonym' ? (isDark ? 'rgba(59, 130, 246, 0.3)' : '#bfdbfe') :
                                           field.type === 'shared_field' ? (isDark ? 'rgba(168, 85, 247, 0.2)' : '#f3e8ff') :
                                           field.type === 'value_overlap' ? (isDark ? 'rgba(249, 115, 22, 0.2)' : '#ffedd5') : (isDark ? 'rgba(6, 182, 212, 0.2)' : '#cffafe'),
                                color: field.type === 'foreign_key' ? (isDark ? '#4ade80' : '#16a34a') :
                                       field.type === 'semantic' ? (isDark ? '#60a5fa' : '#2563eb') :
                                       field.type === 'synonym' ? (isDark ? '#93c5fd' : '#1d4ed8') :
                                       field.type === 'shared_field' ? (isDark ? '#c084fc' : '#9333ea') :
                                       field.type === 'value_overlap' ? (isDark ? '#fb923c' : '#ea580c') : (isDark ? '#67e8f9' : '#0891b2'),
                                borderColor: 'transparent'
                              }}>
                                {field.type === 'foreign_key' ? '外键' :
                                 field.type === 'semantic' ? '语义' :
                                 field.type === 'synonym' ? '同义' :
                                 field.type === 'shared_field' ? '共享字段' :
                                 field.type === 'value_overlap' ? '值域重叠' : field.type}
                              </Tag>
                              <Progress
                                percent={Math.round((field.confidence || 0) * 100)}
                                size="small"
                                strokeColor={(field.confidence || 0) >= 0.85 ? '#52c41a' : (field.confidence || 0) >= 0.7 ? '#faad14' : '#ff4d4f'}
                                style={{ width: 100 }}
                              />
                            </div>
                          </div>

                          {/* 推理依据 */}
                          {field.reasoning && (
                            <div className="text-xs p-2 rounded border" style={{ background: isDark ? '#1e293b' : '#ffffff', color: isDark ? '#94a3b8' : '#6b7280', borderColor: isDark ? '#334155' : '#e5e7eb' }}>
                              <span className="font-medium">推理依据：</span>{field.reasoning}
                            </div>
                          )}

                          {/* 字段级别的业务关系 */}
                          {field.business_relation && field.business_relation.relation_description && (
                            <div className="text-xs p-2 rounded border-l-2" style={{ background: isDark ? 'rgba(99, 102, 241, 0.1)' : '#eef2ff', borderColor: isDark ? '#a5b4fc' : '#6366f1' }}>
                              <span className="font-medium" style={{ color: isDark ? '#a5b4fc' : '#6366f1' }}>业务关系：</span>
                              <span style={{ color: isDark ? '#f1f5f9' : '#374151' }}>{field.business_relation.relation_description}</span>
                            </div>
                          )}

                          {/* 字段级别的连接建议 */}
                          {field.join_suggestion && (
                            <div className="p-2 rounded space-y-1" style={{ background: isDark ? 'rgba(59, 130, 246, 0.1)' : '#eff6ff' }}>
                              <div className="flex items-center gap-2">
                                <span className="text-xs" style={{ color: isDark ? '#64748b' : '#6b7280' }}>推荐连接：</span>
                                <Tag style={{ background: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', color: isDark ? '#93c5fd' : '#1d4ed8', borderColor: 'transparent' }}>{field.join_suggestion.join_type}</Tag>
                              </div>
                              {field.join_suggestion.join_condition && (
                                <div className="text-xs font-mono p-1 rounded" style={{ background: isDark ? '#0f172a' : '#ffffff', color: isDark ? '#e2e8f0' : '#374151' }}>
                                  {field.join_suggestion.join_condition}
                                </div>
                              )}
                              {field.join_suggestion.use_cases && field.join_suggestion.use_cases.length > 0 && (
                                <div className="text-xs" style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>
                                  <span className="font-medium">适用场景：</span>
                                  {field.join_suggestion.use_cases.join('、')}
                                </div>
                              )}
                            </div>
                          )}

                          {/* 字段级别的融合建议 */}
                          {field.fusion_suggestion && (
                            <div className="p-2 rounded space-y-1" style={{ background: isDark ? 'rgba(139, 92, 246, 0.1)' : '#f5f3ff' }}>
                              <div className="text-xs" style={{ color: isDark ? '#c4b5fd' : '#7c3aed' }}>
                                <span className="font-medium" style={{ color: isDark ? '#c4b5fd' : '#7c3aed' }}>融合策略：</span>
                                {field.fusion_suggestion.fusion_strategy}
                              </div>
                              {field.fusion_suggestion.aggregation_hint && (
                                <div className="text-xs" style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>
                                  💡 {field.fusion_suggestion.aggregation_hint}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </Card>
                    ))
                  ) : (
                    <span className="text-gray-400 text-sm">暂无字段信息</span>
                  )}
                </div>
              </div>

              {/* 关系信息 */}
              <Descriptions size="small" column={2} bordered>
                <Descriptions.Item label="关系类型">
                  <Tag color={
                    card.relationship_type === 'foreign_key' ? 'success' :
                    card.relationship_type === 'semantic' ? 'processing' :
                    card.relationship_type === 'synonym' ? 'blue' :
                    card.relationship_type === 'value_overlap' ? 'default' :
                    card.relationship_type === 'shared_field' ? 'orange' :
                    'default'
                  }>
                    {card.relationship_type === 'foreign_key' ? '外键关联' :
                     card.relationship_type === 'semantic' ? '语义关系' :
                     card.relationship_type === 'synonym' ? '同义关系' :
                     card.relationship_type === 'value_overlap' ? '值域重叠' :
                     card.relationship_type === 'shared_field' ? '共享字段' : '命名关系'}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="整体置信度">
                  <Progress
                    percent={Math.round((Number(card.confidence) || 0) * 100)}
                    size="small"
                    strokeColor={(Number(card.confidence) || 0) >= 0.8 ? '#52c41a' : (Number(card.confidence) || 0) >= 0.6 ? '#faad14' : '#ff4d4f'}
                    style={{ width: 120 }}
                  />
                </Descriptions.Item>
              </Descriptions>

              {/* 联表查询建议 */}
              {card.join_suggestion && (
                <div className="border-t pt-3">
                  <div className="flex items-center gap-2 mb-2">
                    <DatabaseOutlined className="text-blue-500" />
                    <span className="text-sm font-medium text-gray-700">联表查询建议</span>
                  </div>
                  <div className="bg-blue-50 rounded p-3 space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-500">推荐连接：</span>
                      <Tag color="blue">{card.join_suggestion.recommended_join_type}</Tag>
                    </div>
                    {card.join_suggestion.join_conditions && card.join_suggestion.join_conditions.length > 0 && (
                      <div>
                        <span className="text-sm text-gray-500">连接条件：</span>
                        <div className="mt-1 space-y-1">
                          {card.join_suggestion.join_conditions.map((jc: any, jcIdx: number) => (
                            <div key={jcIdx} className="flex items-center gap-2 text-xs bg-white p-2 rounded">
                              <span className="font-mono text-blue-600">{jc.from_column}</span>
                              <span className="text-gray-400">=</span>
                              <span className="font-mono text-green-600">{jc.to_column}</span>
                              <Tag color="blue" className="ml-auto">
                                {Math.round((jc.confidence || 0) * 100)}%
                              </Tag>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {card.join_suggestion.use_cases && card.join_suggestion.use_cases.length > 0 && (
                      <div>
                        <span className="text-sm text-gray-500">适用场景：</span>
                        <ul className="list-disc list-inside text-sm text-gray-600 mt-1">
                          {card.join_suggestion.use_cases.map((uc, ucIdx) => (
                            <li key={ucIdx}>{uc}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {card.join_suggestion.sample_sql && (
                      <div>
                        <span className="text-sm text-gray-500">示例 SQL：</span>
                        <pre className="mt-1 bg-gray-800 text-green-400 p-2 rounded text-xs overflow-x-auto">
                          {card.join_suggestion.sample_sql}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* 数据融合建议 */}
              {card.fusion_suggestion && (
                <div className="border-t pt-3">
                  <div className="flex items-center gap-2 mb-2">
                    <MergeCellsOutlined className="text-purple-500" />
                    <span className="text-sm font-medium text-gray-700">数据融合建议</span>
                  </div>
                  <div className="bg-purple-50 rounded p-3 space-y-2">
                    <div>
                      <span className="text-sm text-gray-500">融合策略：</span>
                      <span className="text-sm text-gray-700 ml-2">{card.fusion_suggestion.fusion_strategy}</span>
                    </div>
                    {card.fusion_suggestion.aggregation_hint && (
                      <div>
                        <span className="text-sm text-gray-500">聚合提示：</span>
                        <span className="text-sm text-gray-700 ml-2">{card.fusion_suggestion.aggregation_hint}</span>
                      </div>
                    )}
                    {card.fusion_suggestion.primary_table && card.fusion_suggestion.secondary_table && (
                      <div className="flex items-center gap-2 text-sm">
                        <span className="text-gray-500">主表:</span>
                        <Tag color="blue">{card.fusion_suggestion.primary_table}</Tag>
                        <span className="text-gray-500">从表:</span>
                        <Tag color="green">{card.fusion_suggestion.secondary_table}</Tag>
                      </div>
                    )}
                    {card.fusion_suggestion.recommended_aggregations && card.fusion_suggestion.recommended_aggregations.length > 0 && (
                      <div>
                        <span className="text-sm text-gray-500">推荐聚合：</span>
                        <ul className="list-disc list-inside text-sm text-gray-600 mt-1 font-mono">
                          {card.fusion_suggestion.recommended_aggregations.map((agg, aggIdx) => (
                            <li key={aggIdx}>{agg}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>
    )
  }

  // 字段映射确认结果列定义
  const fieldMappingColumns: ColumnsType<FieldMappingItem> = [
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>源表</span>,
      dataIndex: 'source_table',
      key: 'source_table',
      width: 140,
      render: (text) => <Tag style={{ background: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', color: isDark ? '#93c5fd' : '#1d4ed8', borderColor: 'transparent' }}>{text}</Tag>
    },
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>源字段</span>,
      dataIndex: 'source_column',
      key: 'source_column',
      width: 120,
      render: (text, record) => (
        <div>
          <span className="font-mono font-medium" style={{ color: isDark ? '#60a5fa' : '#2563eb' }}>{text}</span>
          {record.source_type && (
            <div className="text-xs" style={{ color: isDark ? '#64748b' : '#9ca3af' }}>{record.source_type}</div>
          )}
        </div>
      )
    },
    {
      title: '',
      key: 'arrow',
      width: 40,
      render: () => <span style={{ color: isDark ? '#475569' : '#d1d5db' }}>→</span>
    },
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>目标表</span>,
      dataIndex: 'target_table',
      key: 'target_table',
      width: 140,
      render: (text) => <Tag style={{ background: isDark ? 'rgba(34, 197, 94, 0.2)' : '#dcfce7', color: isDark ? '#4ade80' : '#16a34a', borderColor: 'transparent' }}>{text}</Tag>
    },
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>目标字段</span>,
      dataIndex: 'target_column',
      key: 'target_column',
      width: 120,
      render: (text, record) => (
        <div>
          <span className="font-mono font-medium" style={{ color: isDark ? '#4ade80' : '#16a34a' }}>{text}</span>
          {record.target_type && (
            <div className="text-xs" style={{ color: isDark ? '#64748b' : '#9ca3af' }}>{record.target_type}</div>
          )}
        </div>
      )
    },
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>映射类型</span>,
      dataIndex: 'mapping_type',
      key: 'mapping_type',
      width: 100,
      render: (type) => {
        const typeMap: Record<string, { label: string; bgColor: string; textColor: string }> = {
          'exact_match': { label: '精确匹配', bgColor: isDark ? 'rgba(34, 197, 94, 0.2)' : '#dcfce7', textColor: isDark ? '#4ade80' : '#16a34a' },
          'semantic_match': { label: '语义匹配', bgColor: isDark ? 'rgba(139, 92, 246, 0.3)' : '#ede9fe', textColor: isDark ? '#a5b4fc' : '#7c3aed' },
          'user_defined': { label: '用户定义', bgColor: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', textColor: isDark ? '#93c5fd' : '#1d4ed8' },
          'name_similarity': { label: '名称相似', bgColor: isDark ? 'rgba(6, 182, 212, 0.2)' : '#cffafe', textColor: isDark ? '#67e8f9' : '#0891b2' },
          'llm_generated': { label:'LLM自动填充', bgColor: isDark ? 'rgba(139, 92, 246, 0.3)' : '#ede9fe', textColor: isDark ? '#a5b4fc' : '#7c3aed' },
        }
        const config = typeMap[type] || { label: type, bgColor: isDark ? 'rgba(148, 163, 184, 0.2)' : '#f3f4f6', textColor: isDark ? '#94a3b8' : '#6b7280' }
        return <Tag style={{ background: config.bgColor, color: config.textColor, borderColor: 'transparent' }}>{config.label}</Tag>
      }
    },
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>置信度</span>,
      dataIndex: 'confidence',
      key: 'confidence',
      width: 120,
      render: (confidence) => (
        <Progress
          percent={Math.round((confidence || 0) * 100)}
          size="small"
          strokeColor={confidence >= 0.8 ? '#52c41a' : confidence >= 0.6 ? '#faad14' : '#ff4d4f'}
          style={{ width: 80 }}
        />
      )
    },
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>映射依据</span>,
      dataIndex: 'mapping_basis',
      key: 'mapping_basis',
      width: 150,
      render: (basis) => {
        if (!basis) return '-'
        return (
          <div className="text-xs">
            {basis.source && <div style={{ color: isDark ? '#64748b' : '#4b5563' }}>来源: {basis.source}</div>}
            {basis.scores && Object.entries(basis.scores).map(([key, value]) => (
              <div style={{ color: isDark ? '#64748b' : '#6b7280' }}>
                {key}: {typeof value === 'number' ? `${Math.round(value * 100)}%` : String(value)}
              </div>
            ))}
          </div>
        )
      }
    },
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>确认时间</span>,
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (time) => time ? new Date(time).toLocaleString('zh-CN') : '-'
    }
  ]

  // 渲染字段映射确认结果
  const renderFieldMappingsConfirmed = () => {
    if (loadingFieldMappings) {
      return <div className="flex justify-center py-12"><Spin size="large" /></div>
    }

    if (!fieldMappingsConfirmed || fieldMappingsConfirmed.field_mappings.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center py-16" style={{ minHeight: 'calc(100vh - 420px)' }}>
          <Empty description="暂无字段映射确认记录" style={{ color: isDark ? '#94a3b8' : '#6b7280' }} />
        </div>
      )
    }

    const { field_mappings, total, by_table } = fieldMappingsConfirmed

    return (
      <div className="space-y-4">
        {/* 统计信息 */}
        <Card
          size="small"
          style={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb' }}
          bodyStyle={{ background: isDark ? '#1e293b' : '#ffffff' }}
        >
          <div className="flex items-center gap-8">
            <div>
              <div className="text-2xl font-bold" style={{ color: isDark ? '#a5b4fc' : '#6366f1' }}>{total}</div>
              <div className="text-sm" style={{ color: isDark ? '#64748b' : '#6b7280' }}>已确认映射</div>
            </div>
            <div>
              <div className="text-2xl font-bold" style={{ color: isDark ? '#60a5fa' : '#3b82f6' }}>{Object.keys(by_table).length}</div>
              <div className="text-sm" style={{ color: isDark ? '#64748b' : '#6b7280' }}>涉及表数</div>
            </div>
            <div>
              <div className="text-2xl font-bold" style={{ color: isDark ? '#4ade80' : '#16a34a' }}>
                {field_mappings.filter(m => m.mapping_type === 'exact_match').length}
              </div>
              <div className="text-sm" style={{ color: isDark ? '#64748b' : '#6b7280' }}>精确匹配</div>
            </div>
            <div>
              <div className="text-2xl font-bold" style={{ color: isDark ? '#a78bfa' : '#8b5cf6' }}>
                {field_mappings.filter(m => m.mapping_type === 'semantic_match').length}
              </div>
              <div className="text-sm" style={{ color: isDark ? '#64748b' : '#6b7280' }}>语义匹配</div>
            </div>
          </div>
        </Card>

        {/* 按表分组展示 */}
        <Collapse
          defaultActiveKey={Object.keys(by_table).slice(0, 2)}
          style={{ background: isDark ? '#0f172a' : '#ffffff' }}
        >
          {Object.entries(by_table).map(([tableName, mappings]) => (
            <Panel
              header={
                <div className="flex items-center gap-2">
                  <DatabaseOutlined style={{ color: isDark ? '#60a5fa' : '#3b82f6' }} />
                  <span className="font-medium" style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>{tableName}</span>
                  <Tag style={{ background: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', color: isDark ? '#93c5fd' : '#1d4ed8', borderColor: 'transparent' }}>{(mappings as FieldMappingItem[]).length} 个映射</Tag>
                </div>
              }
              key={tableName}
              style={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb' }}
            >
              <Table
                columns={fieldMappingColumns}
                dataSource={mappings as FieldMappingItem[]}
                rowKey="id"
                size="small"
                pagination={false}
                scroll={{ x: 1100 }}
                style={{ background: isDark ? '#1e293b' : '#ffffff' }}
                className={isDark ? 'dark-table' : ''}
              />
            </Panel>
          ))}
        </Collapse>
      </div>
    )
  }

  return (
    <Modal
      title={
        <div className="flex items-center gap-2">
          <HistoryOutlined style={{ color: isDark ? '#60a5fa' : '#6366f1' }} />
          <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>盘点任务详情</span>
          {job && (
            <Tag style={{ background: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', color: isDark ? '#93c5fd' : '#1d4ed8', borderColor: 'transparent' }} className="ml-2">{job.datasource_name}</Tag>
          )}
        </div>
      }
      open={visible}
      onCancel={handleClose}
      footer={null}
      width={1200}
      style={{ top: 40 }}
      className="job-detail-modal"
      styles={{
        body: { padding: '12px 24px 16px', background: isDark ? '#0f172a' : '#ffffff', color: isDark ? '#f1f5f9' : '#1e293b' },
        content: { background: isDark ? '#1e293b' : '#ffffff' },
        header: { background: isDark ? '#1e293b' : '#ffffff', borderBottom: isDark ? '1px solid #334155' : '#e5e7eb' }
      }}
    >
      {job && (
        <div>
          {/* 任务基本信息 */}
          <Card
            size="small"
            className="mb-3"
            style={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb' }}
            headStyle={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb', color: isDark ? '#f1f5f9' : '#1e293b' }}
            bodyStyle={{ background: isDark ? '#1e293b' : '#ffffff' }}
          >
            <Descriptions size="small" column={3}>
              <Descriptions.Item label={<span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>任务ID</span>}>
                <span className="font-mono text-xs" style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>{job.job_id}</span>
              </Descriptions.Item>
              <Descriptions.Item label={<span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>数据源</span>}>
                <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>{job.datasource_name}</span>
              </Descriptions.Item>
              <Descriptions.Item label={<span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>创建时间</span>}>
                <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>{job.created_at ? new Date(job.created_at).toLocaleString('zh-CN') : '-'}</span>
              </Descriptions.Item>
              <Descriptions.Item label={<span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>目标表</span>}>
                <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>{job.target_tables?.join(', ') || '-'}</span>
              </Descriptions.Item>
              <Descriptions.Item label={<span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>参考表</span>}>
                <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>{job.ref_tables?.join(', ') || '-'}</span>
              </Descriptions.Item>
            </Descriptions>
          </Card>

          {/* Tab 内容 */}
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            className={isDark ? 'dark-tabs' : ''}
          >
            <TabPane
              tab={
                <span className="flex items-center gap-1" style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>
                  <DatabaseOutlined style={{ color: isDark ? '#60a5fa' : '#6366f1' }} />
                  字段推荐
                </span>
              }
              key="field-recommendations"
            >
              <div style={{ height: 'calc(100vh - 320px)', overflow: 'auto' }}>
                {renderFieldRecommendations()}
              </div>
            </TabPane>

            <TabPane
              tab={
                <span className="flex items-center gap-1" style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>
                  <LinkOutlined style={{ color: isDark ? '#60a5fa' : '#6366f1' }} />
                  表关系
                </span>
              }
              key="table-relationships"
            >
              <div style={{ height: 'calc(100vh - 320px)', overflow: 'auto' }}>
                <Spin spinning={loadingRelations}>
                  {tableRelationships.length === 0 && !loadingRelations ? (
                    <div className="flex flex-col items-center justify-center" style={{ height: 'calc(100vh - 400px)' }}>
                      <Empty description="暂无表关系数据" style={{ color: isDark ? '#94a3b8' : '#6b7280' }} />
                    </div>
                  ) : (
                    <>
                      {confirmations?.table_relationships?.confirmed_at && (
                        <div className="text-sm text-gray-500 mb-4">
                          确认时间：{new Date(confirmations.table_relationships.confirmed_at).toLocaleString('zh-CN')}
                        </div>
                      )}
                      <Table
                        columns={relationshipColumns}
                        dataSource={tableRelationships}
                        rowKey={(record) => `${record.from_table}-${record.from_column}-${record.to_table}-${record.to_column}`}
                        scroll={{ x: 1100 }}
                        pagination={{ pageSize: 10 }}
                      />
                    </>
                  )}
                </Spin>
              </div>
            </TabPane>

            <TabPane
              tab={
                <span className="flex items-center gap-1" style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>
                  <MergeCellsOutlined style={{ color: isDark ? '#a78bfa' : '#8b5cf6' }} />
                  关系卡片
                </span>
              }
              key="relationship-cards"
            >
              <div style={{ height: 'calc(100vh - 320px)', overflow: 'auto' }}>
                {/* 操作栏 */}
                {(relationshipCards.length > 0 || tableRelationships.length > 0) && (
                  <div className="flex justify-end mb-3 px-1">
                    <Button
                      danger
                      icon={<DeleteOutlined />}
                      size="small"
                      loading={deleting}
                      onClick={() => {
                        Modal.confirm({
                          title: '确认删除',
                          content: '删除后将清除该任务的所有关系数据，操作不可逆',
                          okText: '确认删除',
                          cancelText: '取消',
                          okButtonProps: { danger: true },
                          centered: true,
                          onOk: handleDeleteRelationships
                        })
                      }}
                    >
                      清除关系数据
                    </Button>
                  </div>
                )}
                {renderRelationshipCards()}
              </div>
            </TabPane>

            <TabPane
              tab={
                <span className="flex items-center gap-1" style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>
                  <ApartmentOutlined style={{ color: isDark ? '#f472b6' : '#ec4899' }} />
                  关系图谱
                </span>
              }
              key="relationship-graph"
            >
              <div style={{ height: 'calc(100vh - 320px)' }}>
                {/* 操作栏 */}
                {graphData && (
                  <div className="flex justify-end mb-2 px-1">
                    {/* <Button
                      danger
                      icon={<DeleteOutlined />}
                      size="small"
                      loading={deleting}
                      onClick={() => {
                        Modal.confirm({
                          title: '确认删除',
                          content: '删除后将清除该数据源的所有关系数据，此操作不可恢复',
                          okText: '确认删除',
                          cancelText: '取消',
                          okButtonProps: { danger: true },
                          centered: true,
                          onOk: handleDeleteRelationships
                        })
                      }}
                    >
                      清除关系数据
                    </Button> */}
                  </div>
                )}
                <Spin spinning={loadingGraph}>
                  {graphData ? (
                    <TargetInventoryRelationshipGraph
                      data={graphData}
                      loading={loadingGraph}
                      relationshipCards={relationshipCards}
                      height="calc(100vh - 360px)"
                    />
                  ) : (
                    !loadingGraph && (
                      <div className="flex flex-col items-center justify-center" style={{ height: 'calc(100vh - 420px)' }}>
                        <Empty description="暂无关系图谱数据" style={{ color: isDark ? '#94a3b8' : '#6b7280' }} />
                      </div>
                    )
                  )}
                </Spin>
              </div>
            </TabPane>

            <TabPane
              tab={
                <span className="flex items-center gap-1" style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>
                  <CheckCircleOutlined style={{ color: isDark ? '#4ade80' : '#16a34a' }} />
                  注释确认结果
                </span>
              }
              key="field-mappings-confirmed"
            >
              <div style={{ height: 'calc(100vh - 320px)', overflow: 'auto' }}>
                {renderFieldMappingsConfirmed()}
              </div>
            </TabPane>
          </Tabs>
        </div>
      )}
    </Modal>
  )
}

export default JobDetailModal
