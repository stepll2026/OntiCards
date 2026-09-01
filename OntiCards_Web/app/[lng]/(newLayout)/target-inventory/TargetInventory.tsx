'use client'

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { message, Spin, Button, Table, Tag, Select, Card, Empty, Modal, Input, Tabs, Progress, Tooltip, Upload, Checkbox, Collapse, Popconfirm } from 'antd'
import {
  DatabaseOutlined,
  SearchOutlined,
  ReloadOutlined,
  TableOutlined,
  UploadOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  FileTextOutlined,
  ApartmentOutlined,
  HistoryOutlined,
  EyeOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  PlusOutlined,
  DeleteOutlined,
  ClearOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { UploadFile } from 'antd/es/upload/interface'
import UserMenu from '@/components/userMenu/UserMenu'
import { getUserDataSources } from '@/api/datasource'
import type { DataSourceItem } from '@/api/datasource'
import {
  getTableList,
  runGlobalInventory,
  getJobResult,
  uploadDictFile,
  getHistoryJobs,
  getHistoryFieldRecommendations,
  getHistoryTableRelationships,
  confirmFieldRecommendations,
  confirmTableRelationships,
  deleteHistoryJob,
  deleteHistoryJobs,
  clearHistoryJobs,
  type TableListItem,
  type RunJobRequest,
  type GlobalInventoryJob,
  type GlobalInventoryJobResult,
  type LLMJudgeResult,
  type HistoryJobItem,
  type FieldRecommendationConfirmation,
  type TableRelationshipConfirmation,
  type ClearHistoryJobsResponse
} from '@/api/targetInventory'
import { deleteRelationships } from '@/api/globalInventory'
import JobDetailModal from '../target-inventory/JobDetailModal'

const { TabPane } = Tabs

// 质量等级配置
const QUALITY_LEVEL_CONFIG: Record<string, { color: string; text: string }> = {
  'high': { color: 'success', text: '高' },
  'medium': { color: 'warning', text: '中' },
  'low': { color: 'error', text: '低' }
}

export interface TargetInventoryProps {
  /** 嵌入到工作空间详情时传入，预选数据源名称 */
  defaultConnectName?: string
  /** 嵌入到工作空间详情时传入，预选数据源ID */
  defaultDataSourceId?: string
  /** 嵌入模式：不显示左侧导航和顶部用户栏 */
  embedded?: boolean
}

const TargetInventory: React.FC<TargetInventoryProps> = ({ defaultConnectName, defaultDataSourceId, embedded = false }) => {
  // 状态管理
  const [loading, setLoading] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [dataSources, setDataSources] = useState<DataSourceItem[]>([])
  const [selectedDataSource, setSelectedDataSource] = useState<string>(defaultConnectName ?? '')
  const [userInfo, setUserInfo] = useState<any>(null)

  // 表列表状态
  const [tableList, setTableList] = useState<TableListItem[]>([])
  const [loadingTables, setLoadingTables] = useState(false)

  // 盘点配置状态
  const [targetTables, setTargetTables] = useState<string[]>([])
  const [refTables, setRefTables] = useState<string[]>([])
  const [dictFileId, setDictFileId] = useState<string>('')
  const [dictFileList, setDictFileList] = useState<UploadFile[]>([])
  const [uploadingDict, setUploadingDict] = useState(false)

  // 盘点结果状态
  const [currentJob, setCurrentJob] = useState<GlobalInventoryJob | null>(null)
  const [jobResult, setJobResult] = useState<GlobalInventoryJobResult | null>(null)
  const [activeTab, setActiveTab] = useState('config')

  // 历史记录状态
  const [historyJobs, setHistoryJobs] = useState<HistoryJobItem[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [historyDatasource, setHistoryDatasource] = useState<string>('')
  const [historyStatus, setHistoryStatus] = useState<string>('')
  const [selectedJob, setSelectedJob] = useState<HistoryJobItem | null>(null)
  const [detailModalVisible, setDetailModalVisible] = useState(false)

  // 确认功能状态
  const [resultActiveTab, setResultActiveTab] = useState('field')
  const [fieldRecommendations, setFieldRecommendations] = useState<any>(null)
  const [tableRelationships, setTableRelationships] = useState<any[]>([])
  const [loadingRecommendations, setLoadingRecommendations] = useState(false)
  const [fieldConfirmations, setFieldConfirmations] = useState<Record<string, Record<string, FieldRecommendationConfirmation>>>({})
  const [relationConfirmations, setRelationConfirmations] = useState<Record<string, TableRelationshipConfirmation>>({})
  const [submittingField, setSubmittingField] = useState(false)
  const [submittingRelation, setSubmittingRelation] = useState(false)

  // 嵌入模式下折叠面板由外部弹框替代，非嵌入模式保留原有折叠行为
  const [configPanelOpen, setConfigPanelOpen] = useState(false)

  // 删除相关状态
  const [selectedJobIds, setSelectedJobIds] = useState<string[]>([])
  const [deletingJob, setDeletingJob] = useState(false)
  const [clearingJobs, setClearingJobs] = useState(false)

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

  // 获取用户信息
  useEffect(() => {
    const storedUserInfo = window.localStorage.getItem('userInfo')
    if (storedUserInfo) {
      try {
        const parsedUserInfo = JSON.parse(storedUserInfo)
        setUserInfo(parsedUserInfo)
      } catch (error) {
        console.error('解析用户信息失败:', error)
      }
    }
  }, [])

  // 获取数据源列表
  useEffect(() => {
    fetchDataSources()
    loadHistoryJobs()
    // 嵌入模式下，用 defaultDataSourceId 初始化历史筛选
    if (embedded && defaultDataSourceId) {
      setHistoryDatasource(defaultDataSourceId)
    }
  }, [])

  // 嵌入模式下同步默认数据源（列表加载后选中）
  useEffect(() => {
    if (embedded && defaultConnectName && dataSources.length > 0 && !selectedDataSource) {
      const exists = dataSources.some((ds) => ds.connect_name === defaultConnectName)
      if (exists) setSelectedDataSource(defaultConnectName)
    }
  }, [embedded, defaultConnectName, dataSources, selectedDataSource])

  // 监听外部刷新事件（定向盘点弹框确认完成后触发）
  useEffect(() => {
    if (!embedded) return

    const handleRefresh = () => {
      loadHistoryJobs()
    }
    window.addEventListener('refresh-target-inventory-history', handleRefresh)
    return () => {
      window.removeEventListener('refresh-target-inventory-history', handleRefresh)
    }
  }, [embedded])

  const fetchDataSources = async () => {
    try {
      setLoading(true)
      const response = await getUserDataSources({ page: 1, page_size: 100 })
      if (response.code === 200 && response.data) {
        setDataSources(response.data.items || [])
      } else {
        message.error('获取数据源列表失败')
      }
    } catch (error) {
      console.error('获取数据源列表失败:', error)
      message.error('获取数据源列表失败')
    } finally {
      setLoading(false)
    }
  }

  // 加载历史任务列表
  const loadHistoryJobs = async () => {
    setLoadingHistory(true)
    try {
      // 如果传入了 defaultDataSourceId，则只加载该数据源的任务
      const params: {
        page: number
        page_size: number
        datasource_id?: string
        status?: string
      } = { page: 1, page_size: 1000 }
      if (defaultDataSourceId) {
        params.datasource_id = defaultDataSourceId
      }
      const response = await getHistoryJobs(params)
      if (response.code === 200 && response.data) {
        setHistoryJobs(response.data.items || [])
      } else {
        message.error(response.msg || '获取历史任务列表失败')
      }
    } catch (error: any) {
      console.error('获取历史任务列表失败:', error)
      message.error('获取历史任务列表失败')
    } finally {
      setLoadingHistory(false)
    }
  }

  // 当 defaultDataSourceId 变化时，重新加载任务列表
  useEffect(() => {
    if (defaultDataSourceId) {
      // 同步更新历史筛选数据源
      setHistoryDatasource(defaultDataSourceId)
      loadHistoryJobs()
    }
  }, [defaultDataSourceId])

  // 从历史任务中提取数据源列表
  const historyDataSourceOptions = useMemo(() => {
    const dsMap = new Map<string, string>()
    historyJobs.forEach(job => {
      if (job.datasource_id && job.datasource_name) {
        dsMap.set(job.datasource_id, job.datasource_name)
      }
    })
    return Array.from(dsMap.entries()).map(([id, name]) => ({ id, name }))
  }, [historyJobs])

  // 前端筛选后的历史任务
  const filteredHistoryJobs = useMemo(() => {
    let result = historyJobs
    if (historyDatasource) {
      result = result.filter(job => job.datasource_id === historyDatasource)
    }
    if (historyStatus) {
      result = result.filter(job => job.status === historyStatus)
    }
    return result
  }, [historyJobs, historyDatasource, historyStatus])

  // 查看历史任务详情
  const handleViewDetail = (job: HistoryJobItem) => {
    setSelectedJob(job)
    setDetailModalVisible(true)
  }

  // 删除单条历史任务
  const handleDeleteJob = async (jobId: string) => {
    setDeletingJob(true)
    try {
      const response = await deleteHistoryJob(jobId)
      if (response.code === 200) {
        message.success('删除成功')
        loadHistoryJobs() // 刷新列表
        setSelectedJobIds(prev => prev.filter(id => id !== jobId))
      } else {
        message.error(response.msg || '删除失败')
      }
    } catch (error: any) {
      console.error('删除历史任务失败:', error)
      message.error(error?.message || '删除失败')
    } finally {
      setDeletingJob(false)
    }
  }

  // 批量删除历史任务
  const handleBatchDelete = async () => {
    if (selectedJobIds.length === 0) {
      message.warning('请先选择要删除的任务')
      return
    }

    setDeletingJob(true)
    try {
      const response = await deleteHistoryJobs(selectedJobIds)
      if (response.code === 200) {
        message.success(`成功删除 ${response.data?.deleted_count || selectedJobIds.length} 条记录`)
        loadHistoryJobs() // 刷新列表
        setSelectedJobIds([])
      } else {
        message.error(response.msg || '删除失败')
      }
    } catch (error: any) {
      console.error('批量删除历史任务失败:', error)
      message.error(error?.message || '删除失败')
    } finally {
      setDeletingJob(false)
    }
  }

  // 清空历史任务
  const handleClearHistory = async () => {
    setClearingJobs(true)
    try {
      // 如果选择了特定数据源，只清空该数据源的任务
      const response = await clearHistoryJobs(historyDatasource || undefined)
      if (response.code === 200) {
        const data = response.data as ClearHistoryJobsResponse['data']
        const totalDeleted = (data?.deleted_jobs || 0) + (data?.deleted_rels || 0) + (data?.deleted_cards || 0) + (data?.deleted_mappings || 0)
        const detailParts: string[] = []
        if (data?.deleted_jobs) detailParts.push(`${data.deleted_jobs}个任务`)
        if (data?.deleted_rels) detailParts.push(`${data.deleted_rels}个关系`)
        if (data?.deleted_cards) detailParts.push(`${data.deleted_cards}个卡片`)
        if (data?.deleted_mappings) detailParts.push(`${data.deleted_mappings}个映射`)
        const detailStr = detailParts.length > 0 ? `（${detailParts.join('、')}）` : ''
        message.success(`清空成功，共删除${totalDeleted}条记录${detailStr}`)
        loadHistoryJobs() // 刷新列表
        setSelectedJobIds([])
      } else {
        message.error(response.msg || '清空失败')
      }
    } catch (error: any) {
      console.error('清空历史任务失败:', error)
      message.error(error?.message || '清空失败')
    } finally {
      setClearingJobs(false)
    }
  }

  // 删除指定数据源的关系数据
  const handleDeleteRelationships = async (datasourceId: string, datasourceName: string) => {
    setDeletingJob(true)
    try {
      const response = await deleteRelationships(datasourceId)
      if (response.code === 200) {
        message.success(`已清除 ${datasourceName} 的 ${response.data.deleted_relationships} 个关系和 ${response.data.deleted_cards} 个卡片`)
      } else {
        message.error(response.msg || '清除关系数据失败')
      }
    } catch (error: any) {
      console.error('清除关系数据失败:', error)
      message.error(error?.message || '清除关系数据失败')
    } finally {
      setDeletingJob(false)
    }
  }

  // 获取状态标签
  const getStatusTag = (status: string) => {
    switch (status) {
      case 'completed':
        return <Tag icon={<CheckCircleOutlined />} color="success">已完成</Tag>
      case 'running':
        return <Tag icon={<SyncOutlined spin />} color="processing">运行中</Tag>
      case 'pending':
        return <Tag icon={<ClockCircleOutlined />} color="default">等待中</Tag>
      case 'failed':
        return <Tag icon={<CloseCircleOutlined />} color="error">失败</Tag>
      default:
        return <Tag>{status}</Tag>
    }
  }

  // 渲染表名列表
  const renderTableList = (tables: string[], maxShow: number = 2) => {
    if (!tables || tables.length === 0) return <span className="text-gray-400">-</span>

    const displayTables = tables.slice(0, maxShow)
    const remaining = tables.length - maxShow

    return (
      <Tooltip
        title={
          <div className="max-w-xs">
            {tables.map((t, i) => (
              <div key={i} className="py-0.5">{t}</div>
            ))}
          </div>
        }
        placement="topLeft"
      >
        <div className="space-y-1">
          {displayTables.map((table, idx) => (
            <Tag key={idx} color="blue" className="mr-0 mb-1 text-xs">
              {table.length > 20 ? table.substring(0, 18) + '...' : table}
            </Tag>
          ))}
          {remaining > 0 && (
            <Tag color="default" className="mr-0 mb-1 text-xs">+{remaining}</Tag>
          )}
        </div>
      </Tooltip>
    )
  }

  // 历史任务表格列定义（嵌入模式下隐藏数据源列，列宽紧凑以避免滚动）
  const historyColumns: ColumnsType<HistoryJobItem> = [
    {
      title: '任务ID',
      dataIndex: 'job_id',
      key: 'job_id',
      width: embedded ? 200 : 180,
      render: (text) => (
        <span className="font-mono text-xs text-gray-600">{text}</span>
      )
    },
    ...(embedded ? [] : [{
      title: '数据源',
      dataIndex: 'datasource_name',
      key: 'datasource_name',
      width: 160,
      ellipsis: true,
      render: (text) => (
        <Tooltip title={text}>
          <div className="flex items-center gap-1.5">
            <DatabaseOutlined className="text-blue-500 shrink-0" />
            <span className="truncate">{text || '-'}</span>
          </div>
        </Tooltip>
      )
    }] as ColumnsType<HistoryJobItem>),
    {
      title: '目标表',
      dataIndex: 'target_tables',
      key: 'target_tables',
      width: 160,
      render: (tables: string[]) => renderTableList(tables, 2)
    },
    {
      title: '参考表',
      dataIndex: 'ref_tables',
      key: 'ref_tables',
      width: embedded ? 150 : 180,
      render: (tables: string[]) => renderTableList(tables, embedded ? 2 : 3)
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      align: 'center' as const,
      render: (status) => getStatusTag(status)
    },
    {
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      width: embedded ? 100 : 120,
      render: (progress) => {
        if (!progress) return <span className="text-gray-400">-</span>
        return (
          <div className="text-xs space-y-0.5">
            {progress.phase && (
              <div className="text-gray-500 truncate">{progress.phase}</div>
            )}
            {progress.field_recommendations !== undefined && (
              <div>字段: <span className="text-blue-600 font-medium">{progress.field_recommendations}</span></div>
            )}
            {progress.table_relationships !== undefined && (
              <div>关系: <span className="text-green-600 font-medium">{progress.table_relationships}</span></div>
            )}
          </div>
        )
      }
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: embedded ? 130 : 150,
      render: (text) => (
        <span className="text-xs text-gray-600">
          {text ? new Date(text).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-'}
        </span>
      )
    },
    {
      title: '操作',
      key: 'action',
      width: embedded ? 110 : 130,
      fixed: 'right' as const,
      align: 'center' as const,
      render: (_, record) => (
        <div className="flex items-center gap-1 justify-center">
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(record)}
            disabled={record.status !== 'completed'}
            className="text-xs px-1"
          >
            查看
          </Button>
          <Popconfirm
            title="确认删除"
            description="删除后将无法恢复此任务记录"
            okText="确认"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onOpenChange={(open) => { if (!open) setDeletingJob(false) }}
            onConfirm={() => handleDeleteJob(record.job_id)}
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
              loading={deletingJob}
              className="text-xs px-1"
            >
              删除
            </Button>
          </Popconfirm>
        </div>
      )
    }
  ]

  // 选择数据源后加载表列表
  const handleSelectDataSource = async (datasourceId: string) => {
    setSelectedDataSource(datasourceId)
    setTargetTables([])
    setRefTables([])
    setTableList([])
    setCurrentJob(null)
    setJobResult(null)

    if (!datasourceId) return

    try {
      setLoadingTables(true)
      const response = await getTableList(datasourceId)
      if (response.code === 200 && response.data) {
        setTableList(response.data)
      } else {
        message.error(response.msg || '获取表列表失败')
      }
    } catch (error: any) {
      console.error('获取表列表失败:', error)
      message.error(error?.message || '获取表列表失败')
    } finally {
      setLoadingTables(false)
    }
  }

  // 上传字典文件
  const handleUploadDict = async (file: File) => {
    try {
      setUploadingDict(true)
      const response = await uploadDictFile(file)

      // 处理标准响应格式 {code, msg, data}
      if (response.code === 200 && response.data) {
        setDictFileId(response.data.dict_file_id)
        message.success(`字典文件上传成功，包含 ${response.data.entry_count} 条记录`)
        return true
      }
      // 处理后端直接返回数据对象的情况 {dict_file_id, entry_count, ...}
      else if ((response as any).dict_file_id) {
        const data = response as any
        setDictFileId(data.dict_file_id)
        message.success(`字典文件上传成功，包含 ${data.entry_count} 条记录`)
        return true
      }
      // 其他情况视为失败
      else {
        message.error((response as any).msg || (response as any).message || '上传失败')
        return false
      }
    } catch (error: any) {
      console.error('上传字典文件失败:', error)
      message.error(error?.message || '上传失败')
      return false
    } finally {
      setUploadingDict(false)
    }
  }

  // 执行盘点
  const handleExecute = async () => {
    if (!selectedDataSource) {
      message.warning('请先选择数据源')
      return
    }
    if (targetTables.length === 0) {
      message.warning('请选择至少一个目标表')
      return
    }
    if (refTables.length === 0) {
      message.warning('请选择至少一个参考表')
      return
    }

    const hideLoading = message.loading('正在执行定向盘点，可能需要1-5分钟，请耐心等待...', 0)

    try {
      setExecuting(true)

      const params: RunJobRequest = {
        datasource_id: selectedDataSource,
        target_tables: targetTables,
        ref_tables: refTables,
        dict_file_id: dictFileId || undefined
      }

      const response = await runGlobalInventory(params)

      if (response.code === 200 && response.data) {
        setCurrentJob(response.data.job)
        setJobResult(response.data.result)
        setActiveTab('result')
        message.success('盘点完成！')
      } else {
        message.error(response.msg || '盘点执行失败')
      }
    } catch (error: any) {
      console.error('盘点执行失败:', error)
      message.error(error?.message || '盘点执行失败')
    } finally {
      hideLoading()
      setExecuting(false)
    }
  }

  // 加载字段推荐和表关系数据 - 直接从 jobResult 解析
  const parseRecommendationData = (result: GlobalInventoryJobResult) => {
    setLoadingRecommendations(true)
    try {
      // 解析字段推荐数据 (llm_json)
      if (result.llm_json) {
        setFieldRecommendations(result.llm_json)

        // 初始化字段确认状态 - 默认选择第一个候选
        const initialConfirmations: Record<string, Record<string, FieldRecommendationConfirmation>> = {}
        Object.entries(result.llm_json).forEach(([tableName, columns]: [string, any]) => {
          initialConfirmations[tableName] = {}
          Object.entries(columns).forEach(([columnName, data]: [string, any]) => {
            if (data.candidates && data.candidates.length > 0) {
              initialConfirmations[tableName][columnName] = {
                action: 'accept',
                selected_candidate: data.candidates[0]
              }
            }
          })
        })
        setFieldConfirmations(initialConfirmations)
      }

      // 解析表关系数据 (table_relationships_json)
      const resultAny = result as any
      if (resultAny.table_relationships_json) {
        const relationships = resultAny.table_relationships_json.relationships || []
        setTableRelationships(relationships)

        // 初始化关系确认状态
        const initialRelationConfirmations: Record<string, TableRelationshipConfirmation> = {}
        relationships.forEach((rel: any) => {
          const key = `${rel.from_table}.${rel.from_column}-${rel.to_table}.${rel.to_column}`
          initialRelationConfirmations[key] = {
            from_table: rel.from_table,
            from_column: rel.from_column,
            to_table: rel.to_table,
            to_column: rel.to_column,
            relationship_type: rel.relationship_type || 'semantic',
            confidence: rel.confidence || 0,
            action: 'accept'
          }
        })
        setRelationConfirmations(initialRelationConfirmations)
      }
    } catch (error) {
      console.error('解析推荐数据失败:', error)
      message.error('解析推荐数据失败')
    } finally {
      setLoadingRecommendations(false)
    }
  }

  // 当盘点完成后自动解析推荐数据
  useEffect(() => {
    if (jobResult) {
      parseRecommendationData(jobResult)
    }
  }, [jobResult])

  // 更新字段确认状态
  const handleFieldConfirmationChange = (tableName: string, columnName: string, confirmation: FieldRecommendationConfirmation) => {
    setFieldConfirmations(prev => ({
      ...prev,
      [tableName]: {
        ...prev[tableName],
        [columnName]: confirmation
      }
    }))
  }

  // 更新关系确认状态
  const handleRelationConfirmationChange = (key: string, action: 'accept' | 'reject') => {
    setRelationConfirmations(prev => ({
      ...prev,
      [key]: {
        ...prev[key],
        action
      }
    }))
  }

  // 提交字段推荐确认
  const handleSubmitFieldConfirmations = async () => {
    // 优先使用 jobResult.job_id，其次使用 currentJob.id
    const jobId = jobResult?.job_id || currentJob?.id
    if (!jobId) {
      message.warning('没有可确认的任务')
      return
    }

    setSubmittingField(true)
    try {
      const response = await confirmFieldRecommendations({
        job_id: jobId,
        confirmations: fieldConfirmations
      })

      if (response.code === 200) {
        const data = response.data as any
        message.success(`字段注释确认成功，已更新 ${data?.updated_fields || data?.confirmed_count || 0} 个字段，创建 ${data?.created_mappings || 0} 个映射`)
        loadHistoryJobs() // 刷新历史记录
      } else {
        message.error(response.msg || '确认失败')
      }
    } catch (error: any) {
      console.error('字段确认失败:', error)
      message.error(error?.message || '字段确认失败')
    } finally {
      setSubmittingField(false)
    }
  }

  // 提交表关系确认
  const handleSubmitRelationConfirmations = async () => {
    // 优先使用 jobResult.job_id，其次使用 currentJob.id
    const jobId = jobResult?.job_id || currentJob?.id
    if (!jobId) {
      message.warning('没有可确认的任务')
      return
    }

    // 只提交选中的关系（action === 'accept'）
    const selectedConfirmations = Object.values(relationConfirmations).filter(r => r.action === 'accept')
    if (selectedConfirmations.length === 0) {
      message.warning('请至少选择一个表关系')
      return
    }

    setSubmittingRelation(true)
    try {
      const response = await confirmTableRelationships({
        job_id: jobId,
        confirmations: selectedConfirmations
      })

      if (response.code === 200) {
        message.success(`表关系确认成功，已创建 ${response.data?.created_relationships || 0} 个关系，${response.data?.created_cards || 0} 张卡片`)
        loadHistoryJobs() // 刷新历史记录
        // 清空确认数据
        setRelationConfirmations({})
        setTableRelationships([])
        setJobResult(null)
        setCurrentJob(null)
        setFieldConfirmations({})
      } else {
        message.error(response.msg || '确认失败')
      }
    } catch (error: any) {
      console.error('表关系确认失败:', error)
      message.error(error?.message || '表关系确认失败')
    } finally {
      setSubmittingRelation(false)
    }
  }

  // 目标表列定义
  const targetTableColumns: ColumnsType<TableListItem> = [
    {
      title: '表名',
      dataIndex: 'table_name',
      key: 'table_name',
      render: (text) => <span className="font-medium text-blue-600">{text}</span>
    },
    {
      title: 'AI填充字段数',
      dataIndex: 'auto_filled_count',
      key: 'auto_filled_count',
      width: 120,
      align: 'center',
      sorter: (a, b) => (a.auto_filled_count || 0) - (b.auto_filled_count || 0),
      render: (count) => (
        <Tag color="orange">
          {count || 0}
        </Tag>
      )
    },
    {
      title: '缺失注释字段数',
      dataIndex: 'missing_comment_fields',
      key: 'missing_comment_fields',
      width: 130,
      align: 'center',
      sorter: (a, b) => a.missing_comment_fields - b.missing_comment_fields,
      render: (count) => (
        <Tag color={count > 0 ? 'red' : 'green'}>
          {count}
        </Tag>
      )
    },
    {
      title: '质量等级',
      dataIndex: 'quality_level',
      key: 'quality_level',
      width: 100,
      align: 'center',
      filters: [
        { text: '高', value: 'high' },
        { text: '中', value: 'medium' },
        { text: '低', value: 'low' }
      ],
      onFilter: (value, record) => record.quality_level === value,
      render: (level) => {
        const config = QUALITY_LEVEL_CONFIG[level]
        return config ? (
          <Tag color={config.color}>{config.text}</Tag>
        ) : (
          <Tag>{level}</Tag>
        )
      }
    }
  ]

  // 参考表列定义
  const refTableColumns: ColumnsType<TableListItem> = [
    {
      title: '表名',
      dataIndex: 'table_name',
      key: 'table_name',
      render: (text) => <span className="font-medium text-blue-600">{text}</span>
    },
    {
      title: '缺失注释字段数',
      dataIndex: 'missing_comment_fields',
      key: 'missing_comment_fields',
      width: 130,
      align: 'center',
      sorter: (a, b) => a.missing_comment_fields - b.missing_comment_fields,
      render: (count) => (
        <Tag color={count > 0 ? 'red' : 'green'}>
          {count}
        </Tag>
      )
    },
    {
      title: '质量等级',
      dataIndex: 'quality_level',
      key: 'quality_level',
      width: 100,
      align: 'center',
      filters: [
        { text: '高', value: 'high' },
        { text: '中', value: 'medium' },
        { text: '低', value: 'low' }
      ],
      onFilter: (value, record) => record.quality_level === value,
      render: (level) => {
        const config = QUALITY_LEVEL_CONFIG[level]
        return config ? (
          <Tag color={config.color}>{config.text}</Tag>
        ) : (
          <Tag>{level}</Tag>
        )
      }
    }
  ]

  // 计算结果统计
  const resultStats = jobResult ? {
    fieldRecommendations: Object.keys(jobResult.llm_json || {}).reduce((sum, table) => {
      return sum + Object.keys(jobResult.llm_json[table] || {}).length
    }, 0),
    tableRelationships: Object.keys(jobResult.candidates_json || {}).length
  } : null

  return (
    <div className={embedded ? 'flex flex-col min-h-0' : 'flex h-screen bg-gray-100'}>
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* 顶部导航栏（嵌入时不显示） */}
        {!embedded && (
          <header className="bg-white shadow-sm px-6 h-[64px] flex items-center justify-end border-b">
            <UserMenu userInfo={userInfo || {}} />
          </header>
        )}

        {/* 主内容区 */}
        <main className="flex-1 p-6 overflow-auto">
          <div className="space-y-6">

            {/* 新建盘点入口：嵌入模式下用简洁按钮，非嵌入模式用折叠面板 */}
            {embedded ? (
              /* 嵌入模式：简洁入口按钮 */
              <div className="bg-white border border-indigo-100 flex items-center gap-4 px-5 py-3" style={{ borderRadius: 12 }}>
                <div className="flex items-center gap-2">
                  <Tag color="blue" icon={<DatabaseOutlined />}>{defaultConnectName || '当前数据源'}</Tag>
                  <span className="text-sm text-gray-500">选择目标表和参考表进行定向盘点</span>
                </div>
                <div className="ml-auto">
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={() => {
                      window.dispatchEvent(new CustomEvent('open-target-inventory-modal'))
                    }}
                  >
                    创建盘点任务
                  </Button>
                </div>
              </div>
            ) : (
              /* 非嵌入模式：原有折叠面板 */
              <Collapse
                activeKey={configPanelOpen ? ['config'] : []}
                onChange={(keys) => setConfigPanelOpen(keys.includes('config'))}
                className="bg-white"
              >
                <Collapse.Panel
                  key="config"
                  header={
                    <div className="flex items-center gap-2">
                      <PlusOutlined className="text-indigo-600" />
                      <span className="font-medium">新建盘点任务</span>
                      {selectedDataSource && (
                        <Tag color="blue" className="ml-2">
                          已选数据源
                        </Tag>
                      )}
                    </div>
                  }
                >
                <div className="space-y-6">
                  {/* 数据源选择 */}
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <DatabaseOutlined className="text-indigo-600" />
                      <span className="font-medium">选择数据源：</span>
                    </div>
                    <Select
                      style={{ width: 300 }}
                      placeholder="请选择数据源"
                      value={selectedDataSource || undefined}
                      onChange={handleSelectDataSource}
                      loading={loading}
                    >
                      {dataSources.filter(ds => ds.status === 'available').map(ds => (
                        <Select.Option key={ds.id} value={ds.id}>
                          {ds.connect_name} ({ds.database_name})
                        </Select.Option>
                      ))}
                    </Select>
                    {selectedDataSource && (
                      <Button
                        icon={<ReloadOutlined />}
                        onClick={() => handleSelectDataSource(selectedDataSource)}
                        loading={loadingTables}
                      >
                        刷新表列表
                      </Button>
                    )}
                  </div>

                  {/* 配置盘点区域 */}
                  {selectedDataSource && (
                    <Tabs activeKey={activeTab} onChange={setActiveTab}>
                      <TabPane
                        tab={
                          <span>
                            <SearchOutlined />
                            配置盘点
                          </span>
                        }
                        key="config"
                      >
                        <div className="space-y-6">
                          {/* 提示信息 */}
                          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                            <div className="flex items-start gap-3">
                              <InfoCircleOutlined className="text-blue-500 text-lg mt-0.5" />
                              <div>
                                <h3 className="font-medium text-blue-900 mb-1">定向盘点说明</h3>
                                <p className="text-sm text-blue-800">
                                  选择需要推荐注释的<strong>目标表</strong>，以及提供参考注释的<strong>参考表</strong>。
                                  系统将基于参考表中的字段注释，为目标表中缺失注释的字段推荐合适的注释并进行关系发现。
                                </p>
                              </div>
                            </div>
                          </div>

                          <div className="grid grid-cols-2 gap-6">
                            {/* 目标表选择 */}
                            <Card
                              title={
                                <div className="flex items-center justify-between">
                                  <span>
                                    <ExclamationCircleOutlined className="text-orange-500 mr-2" />
                                    目标表（需要推荐注释）
                                    <Tooltip title="目标表是指字段注释由AI自动填充的表，这些表的注释需要人工确认和校验。系统将为这些表的字段推荐更准确的注释。">
                                      <InfoCircleOutlined className="ml-2 text-gray-400" />
                                    </Tooltip>
                                  </span>
                                  <span className="text-sm font-normal text-gray-500">
                                    已选 {targetTables.length} 个
                                  </span>
                                </div>
                              }
                              size="small"
                            >
                              <Spin spinning={loadingTables}>
                                {tableList.length === 0 ? (
                                  <Empty description="暂无表数据" />
                                ) : (
                                  <Table
                                    columns={targetTableColumns}
                                    dataSource={tableList.filter(t => t.is_auto_filled === true)}
                                    rowKey="table_name"
                                    size="small"
                                    pagination={{ pageSize: 8, hideOnSinglePage: true }}
                                    rowSelection={{
                                      selectedRowKeys: targetTables,
                                      onChange: (keys) => setTargetTables(keys as string[])
                                    }}
                                  />
                                )}
                              </Spin>
                            </Card>

                            {/* 参考表选择 */}
                            <Card
                              title={
                                <div className="flex items-center justify-between">
                                  <span>
                                    <CheckCircleOutlined className="text-green-500 mr-2" />
                                    参考表（提供参考注释）
                                    <Tooltip title="参考表是指字段注释完整且经过人工增强的表，无需AI填充。系统将参考这些表的字段注释来为目标表推荐合适的注释。">
                                      <InfoCircleOutlined className="ml-2 text-gray-400" />
                                    </Tooltip>
                                  </span>
                                  <span className="text-sm font-normal text-gray-500">
                                    已选 {refTables.length} 个
                                  </span>
                                </div>
                              }
                              size="small"
                            >
                              <Spin spinning={loadingTables}>
                                {tableList.length === 0 ? (
                                  <Empty description="暂无表数据" />
                                ) : (
                                  <Table
                                    columns={refTableColumns}
                                    dataSource={tableList.filter(t => !t.is_auto_filled)}
                                    rowKey="table_name"
                                    size="small"
                                    pagination={{ pageSize: 8, hideOnSinglePage: true }}
                                    rowSelection={{
                                      selectedRowKeys: refTables,
                                      onChange: (keys) => setRefTables(keys as string[])
                                    }}
                                  />
                                )}
                              </Spin>
                            </Card>
                          </div>

                          {/* 字典文件上传 */}
                          <Card
                            title={
                              <span>
                                <FileTextOutlined className="text-purple-500 mr-2" />
                                字典文件（可选）
                              </span>
                            }
                            size="small"
                          >
                            <div className="flex items-center gap-4">
                              <Upload
                                accept=".csv,.xlsx,.xls"
                                maxCount={1}
                                fileList={dictFileList}
                                beforeUpload={async (file) => {
                                  const success = await handleUploadDict(file)
                                  if (success) {
                                    setDictFileList([{
                                      uid: '-1',
                                      name: file.name,
                                      status: 'done'
                                    }])
                                  }
                                  return false
                                }}
                                onRemove={() => {
                                  setDictFileList([])
                                  setDictFileId('')
                                }}
                              >
                                <Button icon={<UploadOutlined />} loading={uploadingDict}>
                                  上传字典文件
                                </Button>
                              </Upload>
                              <span className="text-gray-400 text-sm">
                                支持 CSV、Excel 格式，包含 column_name 和 column_comment 列
                              </span>
                              {dictFileId && (
                                <Tag color="success" icon={<CheckCircleOutlined />}>
                                  已上传
                                </Tag>
                              )}
                            </div>
                          </Card>

                          {/* 执行按钮 */}
                          <div className="flex justify-center pt-4">
                            <Button
                              type="primary"
                              size="large"
                              icon={<SearchOutlined />}
                              loading={executing}
                              disabled={targetTables.length === 0 || refTables.length === 0}
                              onClick={handleExecute}
                            >
                              {executing ? '盘点中...' : '执行定向盘点'}
                            </Button>
                          </div>
                        </div>
                      </TabPane>

                      <TabPane
                        tab={
                          <span>
                            <ApartmentOutlined />
                            盘点结果
                            {resultStats && (
                              <Tag color="blue" className="ml-2">
                                {resultStats.fieldRecommendations} 个推荐
                              </Tag>
                            )}
                          </span>
                        }
                        key="result"
                        disabled={!jobResult}
                      >
                        {jobResult ? (
                          <div className="space-y-4">
                            {/* 结果统计 */}
                            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                              <div className="flex items-center gap-2 mb-2">
                                <CheckCircleOutlined className="text-green-600" />
                                <span className="font-medium text-green-800">盘点完成</span>
                              </div>
                              <div className="flex gap-6 text-sm">
                                <div>
                                  <span className="text-gray-500">字段推荐数：</span>
                                  <span className="font-medium text-blue-600">{resultStats?.fieldRecommendations || 0}</span>
                                </div>
                                <div>
                                  <span className="text-gray-500">表关系数：</span>
                                  <span className="font-medium text-purple-600">{tableRelationships.length}</span>
                                </div>
                                <div>
                                  <span className="text-gray-500">任务状态：</span>
                                  <Tag color="success">{currentJob?.status}</Tag>
                                </div>
                              </div>
                            </div>

                            {/* 确认功能 Tabs */}
                            <Spin spinning={loadingRecommendations}>
                              <Tabs activeKey={resultActiveTab} onChange={setResultActiveTab} type="card">
                                {/* 字段注释推荐确认 */}
                                <TabPane
                                  tab={<span><FileTextOutlined /> 字段注释确认</span>}
                                  key="field"
                                >
                                  <div className="space-y-6">
                                    {fieldRecommendations && Object.keys(fieldRecommendations).length > 0 ? (
                                      <>
                                        {Object.entries(fieldRecommendations).map(([tableName, columns]: [string, any]) => {
                                          const tableData = Object.entries(columns).map(([colName, data]: [string, any]) => ({
                                            key: `${tableName}.${colName}`,
                                            table_name: tableName,
                                            column_name: colName,
                                            original_comment: data.original_comment || '',
                                            llm_comment: data.llm_comment || '',
                                            candidates: data.candidates || []
                                          }))

                                          return (
                                            <Card
                                              key={tableName}
                                              title={
                                                <span className="text-blue-600">
                                                  <TableOutlined className="mr-2" />{tableName}
                                                  <span className="text-sm font-normal text-gray-500 ml-3">
                                                    共 {tableData.length} 个字段
                                                  </span>
                                                </span>
                                              }
                                              size="small"
                                              className="shadow-sm"
                                            >
                                              <Table
                                                dataSource={tableData}
                                                columns={[
                                                  {
                                                    title: '字段名',
                                                    dataIndex: 'column_name',
                                                    key: 'column_name',
                                                    width: 150,
                                                    render: (text: string) => (
                                                      <span className="font-mono text-sm text-gray-800 font-medium">{text}</span>
                                                    )
                                                  },
                                                  {
                                                    title: '原始注释',
                                                    dataIndex: 'original_comment',
                                                    key: 'original_comment',
                                                    width: 200,
                                                    render: (text: string) => (
                                                      <div className="py-1">
                                                        <span className={text ? 'text-gray-600' : 'text-gray-400 italic text-sm'}>
                                                          {text || '暂无注释'}
                                                        </span>
                                                      </div>
                                                    )
                                                  },
                                                  {
                                                    title: '选择推荐注释',
                                                    key: 'recommended',
                                                    width: 280,
                                                    render: (_: any, record: any) => {
                                                      const currentSelection = fieldConfirmations[tableName]?.[record.column_name]?.selected_candidate
                                                      const selectedComment = currentSelection?.column_comment || ''

                                                      if (record.candidates.length === 0) {
                                                        return <span className="text-gray-400 italic text-sm">无推荐</span>
                                                      }

                                                      return (
                                                        <Select
                                                          size="middle"
                                                          style={{ width: '100%' }}
                                                          value={selectedComment}
                                                          onChange={(value) => {
                                                            const selected = record.candidates.find((c: any) => c.column_comment === value)
                                                            if (selected) {
                                                              handleFieldConfirmationChange(tableName, record.column_name, {
                                                                action: 'accept',
                                                                selected_candidate: selected
                                                              })
                                                            }
                                                          }}
                                                          placeholder="选择推荐注释"
                                                          dropdownStyle={{ minWidth: 400 }}
                                                          optionLabelProp="label"
                                                        >
                                                          {record.candidates.map((candidate: any, idx: number) => {
                                                            const sourceMap: Record<string, { color: string; text: string }> = {
                                                              'reference_table': { color: 'blue', text: '参考表' },
                                                              'llm': { color: 'purple', text: 'LLM' },
                                                              'dictionary': { color: 'green', text: '字典' }
                                                            }
                                                            const sourceConfig = sourceMap[candidate.source] || { color: 'default', text: candidate.source || '-' }
                                                            const confidence = candidate.confidence

                                                            return (
                                                              <Select.Option
                                                                key={idx}
                                                                value={candidate.column_comment}
                                                                label={candidate.column_comment}
                                                              >
                                                                <div className="py-1">
                                                                  <div className="font-medium text-gray-800">{candidate.column_comment}</div>
                                                                  <div className="flex items-center gap-3 mt-1">
                                                                    <span className="text-xs text-gray-500">
                                                                      来源: <Tag color={sourceConfig.color} className="ml-1">{sourceConfig.text}</Tag>
                                                                    </span>
                                                                    <span className="text-xs text-gray-500">
                                                                      置信度:
                                                                      <Tag
                                                                        color={confidence >= 0.8 ? 'green' : confidence >= 0.5 ? 'orange' : 'red'}
                                                                        className="ml-1"
                                                                      >
                                                                        {(confidence * 100).toFixed(0)}%
                                                                      </Tag>
                                                                    </span>
                                                                  </div>
                                                                </div>
                                                              </Select.Option>
                                                            )
                                                          })}
                                                        </Select>
                                                      )
                                                    }
                                                  },
                                                  {
                                                    title: '来源',
                                                    key: 'source',
                                                    width: 100,
                                                    align: 'center' as const,
                                                    render: (_: any, record: any) => {
                                                      const currentSelection = fieldConfirmations[tableName]?.[record.column_name]?.selected_candidate
                                                      const source = currentSelection?.source || ''
                                                      const sourceMap: Record<string, { color: string; text: string }> = {
                                                        'reference_table': { color: 'blue', text: '参考表' },
                                                        'llm': { color: 'purple', text: 'LLM' },
                                                        'dictionary': { color: 'green', text: '字典' }
                                                      }
                                                      const config = sourceMap[source] || { color: 'default', text: source || '-' }
                                                      return source ? <Tag color={config.color}>{config.text}</Tag> : <span className="text-gray-400">-</span>
                                                    }
                                                  },
                                                  {
                                                    title: '置信度',
                                                    key: 'confidence',
                                                    width: 90,
                                                    align: 'center' as const,
                                                    render: (_: any, record: any) => {
                                                      const currentSelection = fieldConfirmations[tableName]?.[record.column_name]?.selected_candidate
                                                      const confidence = currentSelection?.confidence
                                                      if (confidence === undefined || confidence === null) return <span className="text-gray-400">-</span>
                                                      return (
                                                        <Tag color={confidence >= 0.8 ? 'green' : confidence >= 0.5 ? 'orange' : 'red'}>
                                                          {(confidence * 100).toFixed(0)}%
                                                        </Tag>
                                                      )
                                                    }
                                                  },
                                                  {
                                                    title: '推荐原因',
                                                    key: 'reasoning',
                                                    render: (_: any, record: any) => {
                                                      const currentSelection = fieldConfirmations[tableName]?.[record.column_name]?.selected_candidate
                                                      const reasoning = currentSelection?.reasoning || ''
                                                      return reasoning ? (
                                                        <Tooltip title={reasoning} placement="topLeft">
                                                          <div className="text-xs text-gray-500 line-clamp-2 ">
                                                            {reasoning}
                                                          </div>
                                                        </Tooltip>
                                                      ) : <span className="text-gray-400">-</span>
                                                    }
                                                  }
                                                ]}
                                                pagination={false}
                                                size="middle"
                                                className="field-confirm-table"
                                              />
                                            </Card>
                                          )
                                        })}

                                        <div className="flex justify-center gap-4 pt-2 pb-2">
                                          <Button
                                            type="primary"
                                            size="large"
                                            icon={<CheckCircleOutlined />}
                                            loading={submittingField}
                                            onClick={handleSubmitFieldConfirmations}
                                          >
                                            确认字段注释
                                          </Button>
                                        </div>
                                      </>
                                    ) : (
                                      <Empty description="暂无字段推荐数据" />
                                    )}
                                  </div>
                                </TabPane>

                                {/* 表关系确认 */}
                                <TabPane
                                  tab={<span><ApartmentOutlined /> 表关系确认</span>}
                                  key="relation"
                                >
                                  <div className="space-y-4">
                                    {tableRelationships.length > 0 ? (
                                      <>
                                        {/* 选择统计 */}
                                        <div className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-2">
                                          <span className="text-gray-600">
                                            已选择 <span className="text-blue-600 font-medium">
                                              {Object.values(relationConfirmations).filter(r => r.action === 'accept').length}
                                            </span> / {tableRelationships.length} 个关系
                                          </span>
                                          <div className="flex gap-2">
                                            <Button
                                              size="small"
                                              onClick={() => {
                                                // 全选
                                                const newConfirmations: Record<string, TableRelationshipConfirmation> = {}
                                                tableRelationships.forEach((rel: any, idx: number) => {
                                                  const key = `${rel.from_table}.${rel.from_column}-${rel.to_table}.${rel.to_column}-${idx}`
                                                  newConfirmations[key] = {
                                                    from_table: rel.from_table,
                                                    from_column: rel.from_column,
                                                    to_table: rel.to_table,
                                                    to_column: rel.to_column,
                                                    relationship_type: rel.relationship_type || 'semantic',
                                                    confidence: rel.confidence || 0,
                                                    action: 'accept'
                                                  }
                                                })
                                                setRelationConfirmations(newConfirmations)
                                              }}
                                            >
                                              全选
                                            </Button>
                                            <Button
                                              size="small"
                                              onClick={() => {
                                                // 取消全选
                                                const newConfirmations: Record<string, TableRelationshipConfirmation> = {}
                                                tableRelationships.forEach((rel: any, idx: number) => {
                                                  const key = `${rel.from_table}.${rel.from_column}-${rel.to_table}.${rel.to_column}-${idx}`
                                                  newConfirmations[key] = {
                                                    from_table: rel.from_table,
                                                    from_column: rel.from_column,
                                                    to_table: rel.to_table,
                                                    to_column: rel.to_column,
                                                    relationship_type: rel.relationship_type || 'semantic',
                                                    confidence: rel.confidence || 0,
                                                    action: 'reject'
                                                  }
                                                })
                                                setRelationConfirmations(newConfirmations)
                                              }}
                                            >
                                              取消全选
                                            </Button>
                                          </div>
                                        </div>

                                        <Card size="small" className="shadow-sm">
                                          <Table
                                            dataSource={tableRelationships.map((rel: any, idx: number) => ({
                                              key: `${rel.from_table}.${rel.from_column}-${rel.to_table}.${rel.to_column}-${idx}`,
                                              ...rel
                                            }))}
                                            rowSelection={{
                                              selectedRowKeys: Object.entries(relationConfirmations)
                                                .filter(([_, v]) => v.action === 'accept')
                                                .map(([k, _]) => k),
                                              onChange: (selectedKeys) => {
                                                const newConfirmations: Record<string, TableRelationshipConfirmation> = {}
                                                tableRelationships.forEach((rel: any, idx: number) => {
                                                  const key = `${rel.from_table}.${rel.from_column}-${rel.to_table}.${rel.to_column}-${idx}`
                                                  newConfirmations[key] = {
                                                    from_table: rel.from_table,
                                                    from_column: rel.from_column,
                                                    to_table: rel.to_table,
                                                    to_column: rel.to_column,
                                                    relationship_type: rel.relationship_type || 'semantic',
                                                    confidence: rel.confidence || 0,
                                                    action: selectedKeys.includes(key) ? 'accept' : 'reject'
                                                  }
                                                })
                                                setRelationConfirmations(newConfirmations)
                                              }
                                            }}
                                            columns={[
                                              {
                                                title: '源表',
                                                key: 'from_table',
                                                width: 140,
                                                render: (_: any, record: any) => (
                                                  <span className="text-blue-600 font-medium">{record.from_table}</span>
                                                )
                                              },
                                              {
                                                title: '源字段',
                                                key: 'from_column',
                                                width: 130,
                                                render: (_: any, record: any) => (
                                                  <span className="font-mono text-sm bg-gray-100 px-2 py-0.5 rounded">{record.from_column}</span>
                                                )
                                              },
                                              {
                                                title: '',
                                                key: 'arrow',
                                                width: 60,
                                                align: 'center' as const,
                                                render: () => (
                                                  <span className="text-blue-400 text-xl font-bold">→</span>
                                                )
                                              },
                                              {
                                                title: '目标表',
                                                key: 'to_table',
                                                width: 140,
                                                render: (_: any, record: any) => (
                                                  <span className="text-green-600 font-medium">{record.to_table}</span>
                                                )
                                              },
                                              {
                                                title: '目标字段',
                                                key: 'to_column',
                                                width: 130,
                                                render: (_: any, record: any) => (
                                                  <span className="font-mono text-sm bg-gray-100 px-2 py-0.5 rounded">{record.to_column}</span>
                                                )
                                              },
                                              {
                                                title: '关系类型',
                                                dataIndex: 'relationship_type',
                                                key: 'relationship_type',
                                                width: 100,
                                                align: 'center' as const,
                                                render: (type: string) => {
                                                  const typeMap: Record<string, { color: string; text: string }> = {
                                                    'foreign_key': { color: 'blue', text: '外键' },
                                                    'semantic': { color: 'purple', text: '语义' },
                                                    'name_based': { color: 'cyan', text: '命名' },
                                                    'synonym': { color: 'orange', text: '同义' },
                                                    'value_overlap': { color: 'default', text: '值域重叠' },
                                                    'shared_field': { color: 'orange', text: '共享字段' },
                                                  }
                                                  const config = typeMap[type] || { color: 'default', text: type || '未知' }
                                                  return <Tag color={config.color}>{config.text}</Tag>
                                                }
                                              },
                                              {
                                                title: '基数',
                                                dataIndex: 'cardinality',
                                                key: 'cardinality',
                                                width: 90,
                                                align: 'center' as const,
                                                render: (text: string) => text ? (
                                                  <Tag color="geekblue">{text}</Tag>
                                                ) : <span className="text-gray-400">-</span>
                                              },
                                              {
                                                title: '置信度',
                                                dataIndex: 'confidence',
                                                key: 'confidence',
                                                width: 90,
                                                align: 'center' as const,
                                                render: (conf: number) => (
                                                  <Tag color={conf >= 0.8 ? 'green' : conf >= 0.5 ? 'orange' : 'red'}>
                                                    {((conf || 0) * 100).toFixed(0)}%
                                                  </Tag>
                                                )
                                              },
                                              {
                                                title: '推荐原因',
                                                dataIndex: 'reasoning',
                                                key: 'reasoning',
                                                render: (text: string) => (
                                                  <Tooltip title={text} placement="topLeft">
                                                    <div className="text-xs text-gray-500 line-clamp-2 ">
                                                      {text || '-'}
                                                    </div>
                                                  </Tooltip>
                                                )
                                              }
                                            ]}
                                            pagination={{
                                              pageSize: 10,
                                              hideOnSinglePage: true,
                                              showTotal: (total) => `共 ${total} 条关系`
                                            }}
                                            size="middle"
                                          />
                                        </Card>

                                        <div className="flex justify-center pt-2 pb-2">
                                          <Button
                                            type="primary"
                                            size="large"
                                            icon={<CheckCircleOutlined />}
                                            loading={submittingRelation}
                                            onClick={handleSubmitRelationConfirmations}
                                          >
                                            确认表关系
                                          </Button>
                                        </div>
                                      </>
                                    ) : (
                                      <Empty description="暂无表关系数据" />
                                    )}
                                  </div>
                                </TabPane>
                              </Tabs>
                            </Spin>
                          </div>
                        ) : (
                          <Empty description="请先执行盘点任务" />
                        )}
                      </TabPane>
                    </Tabs>
                  )}

                  {/* 未选择数据源时的提示 */}
                  {!selectedDataSource && (
                    <Empty
                      image={<DatabaseOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />}
                      description={
                        <span className="text-gray-400">请先选择数据源，然后配置并执行定向盘点任务</span>
                      }
                    />
                  )}
                </div>
              </Collapse.Panel>
            </Collapse>
            )}

            {/* 历史记录列表 - 直接显示 */}
            <Card className={`target-inventory-history ${isDark ? '' : ''}`}>
              {/* 筛选区域 */}
              <div className="flex items-center gap-4 mb-4 flex-wrap">
                {/* 嵌入模式下隐藏数据源筛选（始终只看当前数据源的任务） */}
                {!embedded && (
                  <div className="flex items-center gap-2">
                    <span className="text-gray-500 text-sm">数据源：</span>
                    <Select
                      style={{ width: 200 }}
                      placeholder="全部数据源"
                      allowClear
                      value={historyDatasource || undefined}
                      onChange={(value) => setHistoryDatasource(value || '')}
                    >
                      {historyDataSourceOptions.map(ds => (
                        <Select.Option key={ds.id} value={ds.id}>
                          {ds.name}
                        </Select.Option>
                      ))}
                    </Select>
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <span className={isDark ? 'text-gray-400' : 'text-gray-500'} style={{ color: isDark ? 'rgb(var(--theme-text-muted))' : undefined }}>状态：</span>
                  <Select
                    style={{
                      width: 120,
                      ...(isDark ? {
                        backgroundColor: 'rgb(var(--theme-bg-secondary))',
                        borderColor: 'rgb(var(--theme-border))',
                        color: 'rgb(var(--theme-text))',
                      } : {})
                    }}
                    placeholder="全部状态"
                    allowClear
                    value={historyStatus || undefined}
                    onChange={(value) => setHistoryStatus(value || '')}
                    className={isDark ? 'dark-mode-select' : ''}
                    popupClassName={isDark ? 'dark-mode-select-dropdown' : ''}
                    dropdownStyle={isDark ? { backgroundColor: 'rgb(var(--theme-bg))' } : {}}
                  >
                    <Select.Option value="completed">已完成</Select.Option>
                    <Select.Option value="running">运行中</Select.Option>
                    <Select.Option value="pending">等待中</Select.Option>
                    <Select.Option value="failed">失败</Select.Option>
                  </Select>
                </div>

                <Button
                  icon={<ReloadOutlined />}
                  onClick={loadHistoryJobs}
                  loading={loadingHistory}
                  className={isDark ? 'dark-mode-btn' : ''}
                  style={isDark ? {
                    backgroundColor: 'rgb(var(--theme-bg-secondary))',
                    borderColor: 'rgb(var(--theme-border))',
                    color: 'rgb(var(--theme-text))'
                  } : {}}
                >
                  刷新
                </Button>

                {/* 批量操作按钮 */}
                <div className="flex items-center gap-2 ml-auto">
                  {selectedJobIds.length > 0 && (
                    <Popconfirm
                      title="确认批量删除"
                      description={`确定要删除选中的 ${selectedJobIds.length} 条记录吗？`}
                      onConfirm={handleBatchDelete}
                      okText="确认删除"
                      cancelText="取消"
                      okButtonProps={{ danger: true, loading: deletingJob }}
                    >
                      <Button
                        danger
                        icon={<DeleteOutlined />}
                        loading={deletingJob}
                      >
                        删除选中 ({selectedJobIds.length})
                      </Button>
                    </Popconfirm>
                  )}

                  <Button
                    danger
                    icon={<ClearOutlined />}
                    loading={clearingJobs}
                    disabled={filteredHistoryJobs.length === 0}
                    onClick={() => {
                      Modal.confirm({
                        title: '确认清空历史记录',
                        content: historyDatasource
                          ? '将清空该数据源的所有定向盘点记录，操作不可逆！'
                          : '将清空所有历史记录，此操作不可恢复！',
                        okText: '确认清空',
                        cancelText: '取消',
                        okButtonProps: { danger: true },
                        centered: true,
                        onOk: handleClearHistory
                      })
                    }}
                    className={isDark ? 'dark-mode-btn-danger' : ''}
                  >
                    清空记录
                  </Button>

                  <span className="text-gray-400 text-sm">
                    共 {filteredHistoryJobs.length} 条记录
                  </span>
                </div>
              </div>

              {/* 任务列表 */}
              <Spin spinning={loadingHistory}>
                {filteredHistoryJobs.length === 0 && !loadingHistory ? (
                  <Empty description="暂无历史盘点任务" />
                ) : (
                  <Table
                    columns={historyColumns}
                    dataSource={filteredHistoryJobs}
                    rowKey="job_id"
                    scroll={{ x: embedded ? 900 : 1300 }}
                    size="middle"
                    rowSelection={{
                      selectedRowKeys: selectedJobIds,
                      onChange: (selectedKeys) => setSelectedJobIds(selectedKeys as string[]),
                      preserveSelectedRowKeys: true,
                    }}
                    pagination={{
                      pageSize: 10,
                      showSizeChanger: true,
                      showQuickJumper: true,
                      pageSizeOptions: ['10', '20', '50'],
                      showTotal: (total) => `共 ${total} 条记录`
                    }}
                  />
                )}
              </Spin>
            </Card>
          </div>
        </main>
      </div>

      {/* 任务详情弹窗 */}
      <JobDetailModal
        visible={detailModalVisible}
        job={selectedJob}
        onClose={() => {
          setDetailModalVisible(false)
          setSelectedJob(null)
        }}
      />
    </div>
  )
}

export default TargetInventory
