'use client'

import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next-nprogress-bar'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Database,
  FileText,
  FolderTree,
  HardDrive,
  Loader2,
  RefreshCw,
  Shield,
  ListChecks,
  AlertTriangle,
  ExternalLink,
  Table2,
} from 'lucide-react'
import { message, Checkbox, Input, Modal, Radio } from 'antd'
import {
  getGovernanceLibraries,
  executeGovernanceRules,
  generateGovernanceReportV2,
  getGovernanceReportStatus,
  getGovernanceReports,
  GovernanceLibrary,
  getGradeName,
  getGradeColor,
  getGovernanceReportDetail,
  HistoryFile,
} from '@/api/governance'
import { getUserDataSources } from '@/api/datasource'
import { downloadGovernanceReport, deleteGovernanceReport, deleteGovernanceReportFile } from '@/api/governance'
import ExecutionResultPanel, { ExecutionResult } from '@/app/[lng]/(newLayout)/governance/audit/ExecutionResultPanel'

type StepKey = 'datasource' | 'config' | 'result' | 'report'

interface ReportGenerateResult {
  report_id: string
  exported_file_path: string
  file_name: string
  file_size: number
  format: string
  mode: string
}

const StepCard = ({ active, title, description, icon }: { active: boolean; title: string; description: string; icon: React.ReactNode }) => (
  <div
    style={{
      padding: 16,
      borderRadius: 16,
      border: `1px solid ${active ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-border))'}`,
      backgroundColor: active ? 'rgba(var(--theme-primary), 0.05)' : 'rgb(var(--theme-bg))',
    }}
  >
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: 12,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: active ? 'rgba(var(--theme-primary), 0.12)' : 'rgb(var(--theme-bg-secondary))',
          color: active ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-secondary))',
        }}
      >
        {icon}
      </div>
      <div style={{ fontWeight: 600, color: 'rgb(var(--theme-text))' }}>{title}</div>
    </div>
    <div style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))', lineHeight: 1.6 }}>{description}</div>
  </div>
)

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
  <div style={{ textAlign: 'center', padding: 48 }}>
    <div style={{ color: 'rgb(var(--theme-text-muted))', opacity: 0.4 }}>
      {React.cloneElement(icon as React.ReactElement, { style: { width: 64, height: 64 } })}
    </div>
    <p style={{ fontSize: 18, fontWeight: 600, marginTop: 16, color: 'rgb(var(--theme-text))' }}>{title}</p>
    <p style={{ fontSize: 14, marginTop: 8, color: 'rgb(var(--theme-text-secondary))', maxWidth: 420, lineHeight: 1.6 }}>
      {description}
    </p>
    {buttonText && onButtonClick && (
      <button
        onClick={onButtonClick}
        style={{
          marginTop: 24,
          padding: '10px 20px',
          borderRadius: 12,
          fontSize: 14,
          fontWeight: 500,
          color: 'white',
          backgroundColor: 'rgb(var(--theme-primary))',
          border: 'none',
          cursor: 'pointer',
        }}
      >
        {buttonText}
      </button>
    )}
  </div>
)

const AuditPage = ({ params }: { params: { lng: string } }) => {
  const { lng } = params
  const router = useRouter()

  const [currentStep, setCurrentStep] = useState<StepKey>('datasource')
  const [dataSources, setDataSources] = useState<any[]>([])
  const [selectedDatasourceId, setSelectedDatasourceId] = useState<string | null>(null)
  const [libraries, setLibraries] = useState<GovernanceLibrary[]>([])
  const [selectedLibraryIds, setSelectedLibraryIds] = useState<string[]>([])
  const [libraryLoading, setLibraryLoading] = useState(false)
  const [includeBasicAudit, setIncludeBasicAudit] = useState(true)
  const [executionLoading, setExecutionLoading] = useState(false)
  const [reportLoading, setReportLoading] = useState(false)
  const [dsLoading, setDsLoading] = useState(true)
  const [executionResult, setExecutionResult] = useState<ExecutionResult | null>(null)
  const [reportResult, setReportResult] = useState<ReportGenerateResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [reports, setReports] = useState<any[]>([])
  const [reportListLoading, setReportListLoading] = useState(false)
  const [reportName, setReportName] = useState('')
  const [historyFiles, setHistoryFiles] = useState<HistoryFile[]>([])
  const [historyFilesLoading, setHistoryFilesLoading] = useState(false)

  const [generateModalOpen, setGenerateModalOpen] = useState(false)
  const [generateReportName, setGenerateReportName] = useState('')
  const [generateFormat, setGenerateFormat] = useState<'docx' | 'pdf' | 'xlsx' | 'md'>('md')
  const [fileNameError, setFileNameError] = useState('')

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

  // 规则库选择弹框
  const [libraryModalOpen, setLibraryModalOpen] = useState(false)

  const selectedDatasource = useMemo(
    () => dataSources.find((ds) => ds.id === selectedDatasourceId),
    [dataSources, selectedDatasourceId],
  )

  const fetchDataSources = useCallback(async () => {
    setDsLoading(true)
    try {
      const res = await getUserDataSources({ page_size: 100 })
      if (res.code === 200 && res.data) {
        setDataSources(res.data.items || [])
        const firstAvailable = (res.data.items || []).find((item: any) => item.status === 'available')
        setSelectedDatasourceId(firstAvailable?.id || null)
      }
    } catch (err) {
      message.error('获取数据源失败')
    } finally {
      setDsLoading(false)
    }
  }, [])

  const fetchLibraries = useCallback(async (datasourceId: string) => {
    setLibraryLoading(true)
    try {
      const res = await getGovernanceLibraries({ page_size: 100, datasource_id: datasourceId })
      if (res.code === 200) {
        setLibraries(res.data.items.filter((l) => l.status === 'active'))
      }
    } catch (err) {
      console.error('获取规则库失败', err)
    } finally {
      setLibraryLoading(false)
    }
  }, [])

  const fetchReportList = useCallback(async () => {
    setReportListLoading(true)
    try {
      const res = await getGovernanceReports({ page_size: 20, datasource_id: selectedDatasourceId || undefined })
      if (res.code === 200) setReports(res.data.items)
    } catch (err) {
      console.error('获取报告列表失败', err)
    } finally {
      setReportListLoading(false)
    }
  }, [selectedDatasourceId])

  // 获取报告的历史文件列表
  const fetchHistoryFiles = useCallback(async () => {
    if (!executionResult?.report_id) return
    setHistoryFilesLoading(true)
    try {
      // 调用报告详情接口，include_details=true 会返回 history_files
      const res = await getGovernanceReportDetail(executionResult.report_id)
      if (res.code === 200 && res.data) {
        setHistoryFiles(res.data.history_files || [])
      }
    } catch (err) {
      console.error('获取历史文件列表失败', err)
    } finally {
      setHistoryFilesLoading(false)
    }
  }, [executionResult?.report_id])

  useEffect(() => {
    fetchDataSources()
  }, [fetchDataSources])

  // 打开规则库选择弹框时加载规则库数据
  useEffect(() => {
    if (libraryModalOpen && selectedDatasourceId && libraries.length === 0) {
      fetchLibraries(selectedDatasourceId)
    }
  }, [libraryModalOpen, selectedDatasourceId, libraries.length, fetchLibraries])

  const handleNext = () => {
    if (currentStep === 'datasource' && !selectedDatasourceId) {
      message.warning('请选择数据源')
      return
    }
    if (currentStep === 'config' && selectedLibraryIds.length === 0 && !includeBasicAudit) {
      message.warning('请至少选择一个规则库或勾选基础检测')
      return
    }

    if (currentStep === 'datasource') {
      fetchLibraries(selectedDatasourceId!)
      setCurrentStep('config')
      return
    }

    if (currentStep === 'config') {
      setCurrentStep('result')
      handleExecute()
      return
    }

    setCurrentStep((step) => {
      const order: StepKey[] = ['datasource', 'config', 'result', 'report']
      const index = order.indexOf(step)
      return order[Math.min(index + 1, order.length - 1)]
    })
  }

  const handleExecute = async () => {
    if (!selectedDatasourceId) {
      message.warning('请选择数据源')
      return
    }
    if (selectedLibraryIds.length === 0 && !includeBasicAudit) {
      message.warning('请至少选择一个规则库或勾选基础检测')
      return
    }

    setExecutionLoading(true)
    setError(null)
    setExecutionResult(null)
    setReportResult(null)

    try {
      const res = await executeGovernanceRules({
        datasource_id: selectedDatasourceId,
        library_ids: selectedLibraryIds.length > 0 ? selectedLibraryIds : undefined,
        include_basic_audit: includeBasicAudit,
        // [暂时屏蔽关系发现功能] 此处写死为 false
        include_relation_discovery: false,
      })

      if (res.code === 200 && res.data) {
        setExecutionResult(res.data)
        setCurrentStep('result')
        await fetchReportList()
      } else {
        setError(res.msg || '执行失败')
      }
    } catch (err: any) {
      setError(err?.message || '执行失败，请稍后重试')
    } finally {
      setExecutionLoading(false)
    }
  }

  const handleOpenGenerateModal = () => {
    if (!executionResult?.report_id) {
      message.warning('请先执行规则')
      return
    }
    setGenerateReportName('')
    setFileNameError('')
    setGenerateFormat('md')
    setGenerateModalOpen(true)
  }

  const handleConfirmGenerate = async () => {
    if (!executionResult?.report_id) {
      message.warning('请先执行规则')
      return
    }

    // 校验文件名
    const error = validateFileName(generateReportName)
    if (error) {
      setFileNameError(error)
      return
    }

    setReportLoading(true)
    setError(null)
    setGenerateModalOpen(false)
    // 显示生成中的提示
    const hideLoadingMsg = message.loading('报告文件生成中...', 0)
    try {
      const res = await generateGovernanceReportV2({
        report_id: executionResult.report_id,
        file_name: generateReportName.trim() || undefined,
        format: generateFormat,
      })
      if (res.code === 200 && res.data) {
        setReportResult(res.data)
        setCurrentStep('report')
        await fetchReportList()
        // 获取历史文件列表
        await fetchHistoryFiles()
        hideLoadingMsg()
        message.success('报告文件生成成功')
      } else {
        hideLoadingMsg()
        setError(res.msg || '生成报告失败')
      }
    } catch (err: any) {
      hideLoadingMsg()
      setError(err?.message || '生成报告失败，请稍后重试')
    } finally {
      setReportLoading(false)
    }
  }

  const handleViewDetails = () => {
    if (executionResult?.report_id) {
      router.push(`/${lng}/governance/reports/${executionResult.report_id}`)
    }
  }

  const handleReset = () => {
    setCurrentStep('datasource')
    setSelectedLibraryIds([])
    setIncludeBasicAudit(true)
    setExecutionResult(null)
    setReportResult(null)
    setReportName('')
    setGenerateModalOpen(false)
    setGenerateReportName('')
    setGenerateFormat('md')
    setError(null)
  }

  const handleDownloadReport = async (reportId?: string, fileId?: string) => {
    const target = typeof reportId === 'string' ? reportId : executionResult?.report_id
    if (!target) {
      message.warning('暂无可下载报告')
      return
    }
    try {
      await downloadGovernanceReport(target, fileId)
      message.success('下载已完成')
    } catch (err) {
      message.error('下载失败')
    }
  }

  const handleDeleteReport = async (reportId: string, reportName?: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除报告"${reportName || ''}"吗？`,
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      centered: true,
      onOk: async () => {
        try {
          await deleteGovernanceReport(reportId)
          message.success('删除成功')
          await fetchReportList()
        } catch (err) {
          message.error('删除失败')
        }
      },
    })
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
      onOk: async () => {
        try {
          await deleteGovernanceReportFile(fileId)
          message.success('删除成功')
          // 刷新历史文件列表
          await fetchHistoryFiles()
        } catch (err) {
          message.error('删除失败')
        }
      },
    })
  }

  return (
    <div className="space-y-6">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
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
          返回
        </button>
      </div>

      <div
        style={{
          padding: 20,
          borderRadius: 20,
          border: '1px solid rgb(var(--theme-border))',
          backgroundColor: 'rgb(var(--theme-bg))',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ maxWidth: 720 }}>
            <h1 style={{ fontSize: 24, fontWeight: 700, color: 'rgb(var(--theme-text))', margin: 0 }}>质检执行</h1>
            <p style={{ fontSize: 14, color: 'rgb(var(--theme-text-secondary))', marginTop: 8, lineHeight: 1.7 }}>
              选择数据源、配置检测范围，执行规则后可立即查看质检结果，并支持生成报告文档。
            </p>
          </div>
          {currentStep !== 'result' && currentStep !== 'config' && (
            <button
              onClick={() => {
                // 在报告步骤时刷新历史文件列表，否则刷新数据源
                if (currentStep === 'report') {
                  fetchHistoryFiles()
                } else {
                  fetchDataSources()
                }
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 12px',
                borderRadius: 10,
                fontSize: 13,
                fontWeight: 500,
                color: 'rgb(var(--theme-text))',
                backgroundColor: 'transparent',
                border: '1px solid rgb(var(--theme-border))',
                cursor: 'pointer',
              }}
            >
              <RefreshCw style={{ width: 14, height: 14 }} />
              刷新
            </button>
          )}
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
            gap: 12,
            marginTop: 20,
          }}
        >
          <StepCard
            active={currentStep === 'datasource'}
            title="选择数据源"
            description="选择要执行质检的数据源"
            icon={<Database style={{ width: 18, height: 18 }} />}
          />
          <StepCard
            active={currentStep === 'config'}
            title="配置质检"
            description="勾选检测类型与规则库"
            icon={<ListChecks style={{ width: 18, height: 18 }} />}
          />
          <StepCard
            active={currentStep === 'result'}
            title="执行与结果"
            description="执行规则并查看明细"
            icon={<Shield style={{ width: 18, height: 18 }} />}
          />
          <StepCard
            active={currentStep === 'report'}
            title="生成报告"
            description="导出质检报告结果"
            icon={<FileText style={{ width: 18, height: 18 }} />}
          />
        </div>
      </div>

      <div
        style={{
          borderRadius: 20,
          border: '1px solid rgb(var(--theme-border))',
          padding: 24,
          backgroundColor: 'rgb(var(--theme-bg))',
        }}
      >
        {currentStep === 'datasource' && (
          <div>
            <h3 style={{ fontSize: 18, fontWeight: 600, color: 'rgb(var(--theme-text))', marginBottom: 8 }}>选择数据源</h3>
            <p style={{ fontSize: 14, color: 'rgb(var(--theme-text-secondary))', marginBottom: 24 }}>请选择要执行质检的数据源</p>
            {dsLoading ? (
              <div style={{ textAlign: 'center', padding: 48 }}>
                <Loader2 style={{ width: 40, height: 40, color: 'rgb(var(--theme-primary))', animation: 'spin 1s linear infinite', margin: '0 auto' }} />
                <p style={{ marginTop: 16, color: 'rgb(var(--theme-text-muted))' }}>加载数据源中...</p>
              </div>
            ) : dataSources.length === 0 ? (
              <EmptyStateCard
                icon={<Database />}
                title="暂无数据源"
                description="请先添加数据源后再执行质检。"
                buttonText="添加数据源"
                onButtonClick={() => router.push(`/${lng}/workspaces`)}
              />
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 16 }}>
                {dataSources.map((ds) => (
                  <div
                    key={ds.id}
                    onClick={() => setSelectedDatasourceId(ds.id)}
                    style={{
                      padding: 14,
                      borderRadius: 14,
                      border: `2px solid ${selectedDatasourceId === ds.id ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-border))'}`,
                      backgroundColor: selectedDatasourceId === ds.id ? 'rgba(var(--theme-primary), 0.04)' : 'rgb(var(--theme-bg))',
                      cursor: 'pointer',
                      transition: 'all 0.25s ease',
                      position: 'relative',
                      overflow: 'hidden',
                    }}
                  >
                    {/* 选中状态角标 */}
                    {selectedDatasourceId === ds.id && (
                      <div
                        style={{
                          position: 'absolute',
                          top: 8,
                          right: 8,
                          width: 20,
                          height: 20,
                          borderRadius: '50%',
                          backgroundColor: 'rgb(var(--theme-primary))',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        <Check style={{ width: 11, height: 11, color: 'white' }} />
                      </div>
                    )}

                    {/* 数据源名称 */}
                    <div style={{ marginBottom: 10 }}>
                      <h4 style={{ fontWeight: 600, fontSize: 14, color: 'rgb(var(--theme-text))', margin: 0, marginBottom: 6, paddingRight: 26 }}>
                        {ds.connect_name}
                      </h4>

                      {/* 数据库信息 */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {/* 数据库名称 */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <Database style={{ width: 12, height: 12, color: 'rgb(var(--theme-text-muted))', flexShrink: 0 }} />
                          <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            数据库: {ds.database_name || '未指定'}
                          </span>
                        </div>

                        {/* Schema 信息 */}
                        {ds.schema_name && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <FolderTree style={{ width: 12, height: 12, color: 'rgb(var(--theme-text-muted))', flexShrink: 0 }} />
                            <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              Schema: {ds.schema_name}
                            </span>
                          </div>
                        )}

                        {/* 数据库类型 */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <HardDrive style={{ width: 12, height: 12, color: 'rgb(var(--theme-text-muted))', flexShrink: 0 }} />
                          <span style={{ fontSize: 11, padding: '1px 5px', borderRadius: 3, backgroundColor: 'rgba(var(--theme-primary), 0.08)', color: 'rgb(var(--theme-primary))', fontWeight: 500 }}>
                            {ds.db_type?.toUpperCase() || 'Unknown'}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* 统计信息 */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        paddingTop: 8,
                        borderTop: '1px solid rgb(var(--theme-border))',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                        <Table2 style={{ width: 11, height: 11, color: 'rgb(var(--theme-text-muted))' }} />
                        <span style={{ fontSize: 11, color: 'rgb(var(--theme-text-muted))' }}>
                          {ds.table_num || 0} 张表
                        </span>
                      </div>

                      {/* 状态标签 */}
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 4,
                        }}
                      >
                        <span
                          style={{
                            width: 5,
                            height: 5,
                            borderRadius: '50%',
                            backgroundColor: ds.status === 'available' ? '#52c41a' : '#faad14',
                          }}
                        />
                        <span style={{ fontSize: 10, color: ds.status === 'available' ? '#52c41a' : '#faad14', fontWeight: 500 }}>
                          {ds.status === 'available' ? '可用' : '不可用'}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {currentStep === 'config' && (
          <div>

            <div style={{ display: 'grid', gap: 20 }}>
              {/* 页面标题 */}
              <div>
                <h3 style={{ fontSize: 18, fontWeight: 600, color: 'rgb(var(--theme-text))', margin: 0, marginBottom: 4 }}>选择质检模式</h3>
                <p style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))', margin: 0 }}>
                  选择一种或多种质检检测方式，快速发现数据质量问题
                  {selectedDatasource && (
                    <span style={{ marginLeft: 8, color: 'rgb(var(--theme-primary))' }}>
                      · 当前数据源：{selectedDatasource.connect_name}
                    </span>
                  )}
                </p>
              </div>

              {/* 两种质检模式卡片 */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>

                {/* 基础质量检测模式卡片 */}
                <div
                  onClick={() => setIncludeBasicAudit(!includeBasicAudit)}
                  style={{
                    padding: 20,
                    borderRadius: 16,
                    border: `2px solid ${includeBasicAudit ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-border))'}`,
                    backgroundColor: includeBasicAudit ? 'rgba(var(--theme-primary), 0.04)' : 'rgb(var(--theme-bg))',
                    cursor: 'pointer',
                    transition: 'all 0.25s ease',
                    position: 'relative',
                    overflow: 'hidden',
                  }}
                  onMouseEnter={(e) => {
                    if (!includeBasicAudit) {
                      e.currentTarget.style.borderColor = 'rgba(var(--theme-primary), 0.4)'
                      e.currentTarget.style.backgroundColor = 'rgba(var(--theme-primary), 0.02)'
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!includeBasicAudit) {
                      e.currentTarget.style.borderColor = 'rgb(var(--theme-border))'
                      e.currentTarget.style.backgroundColor = 'rgb(var(--theme-bg))'
                    }
                  }}
                >
                  {/* 选中状态角标 */}
                  {includeBasicAudit && (
                    <div style={{
                      position: 'absolute',
                      top: 12,
                      right: 12,
                      width: 24,
                      height: 24,
                      borderRadius: '50%',
                      backgroundColor: 'rgb(var(--theme-primary))',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                      <Check style={{ width: 14, height: 14, color: 'white' }} />
                    </div>
                  )}

                  {/* 模式标识 */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
                    <div style={{
                      width: 48,
                      height: 48,
                      borderRadius: 12,
                      backgroundColor: includeBasicAudit ? 'rgba(var(--theme-primary), 0.12)' : 'rgba(var(--theme-primary), 0.06)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: 'all 0.25s ease',
                    }}>
                      <Shield style={{ width: 24, height: 24, color: 'rgb(var(--theme-primary))' }} />
                    </div>
                    <div>
                      <h4 style={{ fontWeight: 600, fontSize: 15, color: 'rgb(var(--theme-text))', margin: 0 }}>基础质量检测</h4>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
                        <span style={{
                          fontSize: 11,
                          padding: '2px 8px',
                          borderRadius: 4,
                          backgroundColor: includeBasicAudit ? 'rgba(var(--theme-primary), 0.1)' : 'rgba(var(--theme-text-muted), 0.1)',
                          color: includeBasicAudit ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-muted))',
                          fontWeight: 500,
                        }}>
                          快速检测
                        </span>
                        <span style={{
                          fontSize: 11,
                          padding: '2px 8px',
                          borderRadius: 4,
                          backgroundColor: 'rgba(82, 196, 26, 0.1)',
                          color: '#52c41a',
                          fontWeight: 500,
                        }}>
                          默认
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* 功能描述 */}
                  <div style={{ display: 'grid', gap: 8, marginBottom: 16 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CheckCircle2 style={{ width: 14, height: 14, color: '#52c41a', flexShrink: 0 }} />
                      <span style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))' }}>自动检测空值、缺失、重复等基础问题</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CheckCircle2 style={{ width: 14, height: 14, color: '#52c41a', flexShrink: 0 }} />
                      <span style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))' }}>覆盖所有数据表，无需额外配置</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CheckCircle2 style={{ width: 14, height: 14, color: '#52c41a', flexShrink: 0 }} />
                      <span style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))' }}>作为质检报告的核心组成</span>
                    </div>
                  </div>

                  {/* 状态指示 */}
                  <div style={{
                    padding: '10px 14px',
                    borderRadius: 10,
                    backgroundColor: includeBasicAudit ? 'rgba(var(--theme-primary), 0.08)' : 'rgba(var(--theme-text-muted), 0.06)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                  }}>
                    <Checkbox checked={includeBasicAudit} onChange={(e) => setIncludeBasicAudit(e.target.checked)} />
                    <span style={{ fontSize: 13, fontWeight: 500, color: includeBasicAudit ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-muted))' }}>
                      {includeBasicAudit ? '已启用' : '点击启用'}
                    </span>
                  </div>
                </div>

                {/* 质检规则库模式卡片 */}
                <div
                  onClick={() => {
                    // 点击卡片时打开规则库选择弹框
                    setLibraryModalOpen(true)
                  }}
                  style={{
                    padding: 20,
                    borderRadius: 16,
                    border: `2px solid ${selectedLibraryIds.length > 0 ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-border))'}`,
                    backgroundColor: selectedLibraryIds.length > 0 ? 'rgba(var(--theme-primary), 0.04)' : 'rgb(var(--theme-bg))',
                    cursor: 'pointer',
                    transition: 'all 0.25s ease',
                    position: 'relative',
                    overflow: 'hidden',
                  }}
                  onMouseEnter={(e) => {
                    if (selectedLibraryIds.length === 0) {
                      e.currentTarget.style.borderColor = 'rgba(var(--theme-primary), 0.4)'
                      e.currentTarget.style.backgroundColor = 'rgba(var(--theme-primary), 0.02)'
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (selectedLibraryIds.length === 0) {
                      e.currentTarget.style.borderColor = 'rgb(var(--theme-border))'
                      e.currentTarget.style.backgroundColor = 'rgb(var(--theme-bg))'
                    }
                  }}
                >
                  {/* 选中状态角标 */}
                  {selectedLibraryIds.length > 0 && (
                    <div style={{
                      position: 'absolute',
                      top: 12,
                      right: 12,
                      width: 24,
                      height: 24,
                      borderRadius: '50%',
                      backgroundColor: 'rgb(var(--theme-primary))',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                      <Check style={{ width: 14, height: 14, color: 'white' }} />
                    </div>
                  )}

                  {/* 模式标识 */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
                    <div style={{
                      width: 48,
                      height: 48,
                      borderRadius: 12,
                      backgroundColor: selectedLibraryIds.length > 0 ? 'rgba(var(--theme-primary), 0.12)' : 'rgba(var(--theme-primary), 0.06)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: 'all 0.25s ease',
                    }}>
                      <ListChecks style={{ width: 24, height: 24, color: 'rgb(var(--theme-primary))' }} />
                    </div>
                    <div>
                      <h4 style={{ fontWeight: 600, fontSize: 15, color: 'rgb(var(--theme-text))', margin: 0 }}>质检规则库</h4>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
                        <span style={{
                          fontSize: 11,
                          padding: '2px 8px',
                          borderRadius: 4,
                          backgroundColor: selectedLibraryIds.length > 0 ? 'rgba(var(--theme-primary), 0.1)' : 'rgba(var(--theme-text-muted), 0.1)',
                          color: selectedLibraryIds.length > 0 ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-muted))',
                          fontWeight: 500,
                        }}>
                          自定义规则
                        </span>
                        <span style={{
                          fontSize: 11,
                          padding: '2px 8px',
                          borderRadius: 4,
                          backgroundColor: 'rgba(24, 144, 255, 0.1)',
                          color: '#1890ff',
                          fontWeight: 500,
                        }}>
                          可选
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* 功能描述 */}
                  <div style={{ display: 'grid', gap: 8, marginBottom: 16 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CheckCircle2 style={{ width: 14, height: 14, color: '#1890ff', flexShrink: 0 }} />
                      <span style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))' }}>基于业务场景的自定义质量规则</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CheckCircle2 style={{ width: 14, height: 14, color: '#1890ff', flexShrink: 0 }} />
                      <span style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))' }}>支持多规则库组合使用</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CheckCircle2 style={{ width: 14, height: 14, color: '#1890ff', flexShrink: 0 }} />
                      <span style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))' }}>灵活配置，精准检测特定问题</span>
                    </div>
                  </div>

                  {/* 配置按钮 */}
                  <div style={{
                    padding: '10px 14px',
                    borderRadius: 10,
                    backgroundColor: selectedLibraryIds.length > 0 ? 'rgba(var(--theme-primary), 0.08)' : 'rgba(var(--theme-text-muted), 0.06)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    transition: 'all 0.25s ease',
                  }}>
                    <ListChecks style={{ width: 14, height: 14, color: selectedLibraryIds.length > 0 ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-muted))' }} />
                    <span style={{ fontSize: 13, fontWeight: 500, color: selectedLibraryIds.length > 0 ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-muted))' }}>
                      {selectedLibraryIds.length > 0 ? `已选择 ${selectedLibraryIds.length} 个规则库` : '配置规则库'}
                    </span>
                  </div>
                </div>
              </div>

              {/* 选择提示 */}
              <div style={{
                padding: '12px 16px',
                borderRadius: 10,
                backgroundColor: 'rgba(var(--theme-primary), 0.04)',
                border: '1px solid rgba(var(--theme-primary), 0.1)',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
              }}>
                <AlertTriangle style={{ width: 16, height: 16, color: 'rgb(var(--theme-primary))', flexShrink: 0 }} />
                <span style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))' }}>
                  提示：建议同时启用基础质量检测和选择质检规则库，以获得更全面的数据质量分析结果
                </span>
              </div>
            </div>
          </div>
        )}

        {currentStep === 'result' && (
          executionLoading ? (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '80px 24px',
                gap: 16,
              }}
            >
              <Loader2
                style={{
                  width: 40,
                  height: 40,
                  color: 'rgb(var(--theme-primary))',
                  animation: 'spin 1s linear infinite',
                }}
              />
              <div style={{ textAlign: 'center' }}>
                <p
                  style={{
                    fontSize: 15,
                    fontWeight: 600,
                    color: 'rgb(var(--theme-text))',
                    margin: '0 0 6px',
                  }}
                >
                  规则执行中，请稍候...
                </p>
                <p
                  style={{
                    fontSize: 13,
                    color: 'rgb(var(--theme-text-secondary))',
                    margin: 0,
                  }}
                >
                  正在对数据源进行质量检测与分析
                </p>
              </div>
            </div>
          ) : executionResult && !error ? (
            <ExecutionResultPanel
              result={executionResult}
              onGenerateReport={handleOpenGenerateModal}
              onDownloadReport={() => handleDownloadReport()}
              onViewDetails={handleViewDetails}
              reportLoading={reportLoading}
              reportGenerated={!!reportResult}
            />
          ) : null
        )}

        {currentStep === 'report' && (
          <div style={{ display: 'grid', gap: 24 }}>
            {/* 报告生成区域 */}
            <div
              style={{
                padding: 20,
                borderRadius: 16,
                border: '1px solid rgb(var(--theme-border))',
                background: 'linear-gradient(135deg, rgba(var(--theme-primary), 0.03) 0%, transparent 100%)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: 12,
                      backgroundColor: 'rgba(var(--theme-primary), 0.1)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <FileText style={{ width: 20, height: 20, color: 'rgb(var(--theme-primary))' }} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: 15, fontWeight: 600, color: 'rgb(var(--theme-text))', margin: 0 }}>生成新报告</h3>
                    <p style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))', margin: 0 }}>基于当前执行结果重新生成报告文档</p>
                  </div>
                </div>
                <button
                  onClick={handleOpenGenerateModal}
                  disabled={reportLoading}
                  style={{
                    padding: '0 20px',
                    height: 38,
                    borderRadius: 10,
                    border: 'none',
                    background: reportLoading ? 'rgba(var(--theme-primary), 0.7)' : 'rgb(var(--theme-primary))',
                    color: 'white',
                    cursor: reportLoading ? 'not-allowed' : 'pointer',
                    fontSize: 14,
                    fontWeight: 500,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                    transition: 'all 0.2s',
                  }}
                >
                  {reportLoading && <Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} />}
                  {reportLoading ? '重新生成中...' : '重新生成报告'}
                  {!reportLoading && <ArrowRight style={{ width: 14, height: 14 }} />}
                </button>
              </div>
            </div>

            {/* 最新报告区域 */}
            {reportResult ? (
              <div
                style={{
                  padding: 24,
                  borderRadius: 16,
                  border: '1px solid rgb(var(--theme-primary))',
                  backgroundColor: 'rgba(var(--theme-primary), 0.03)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: 10,
                        backgroundColor: 'rgb(var(--theme-primary))',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <FileText style={{ width: 18, height: 18, color: 'white' }} />
                    </div>
                    <div>
                      <h4 style={{ fontSize: 15, fontWeight: 600, color: 'rgb(var(--theme-text))', margin: 0 }}>最新生成的报告</h4>
                      <p style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', margin: 0 }}>刚刚生成 · 可立即下载查看</p>
                    </div>
                  </div>
                  <div
                    style={{
                      padding: '4px 12px',
                      borderRadius: 20,
                      backgroundColor: 'rgba(var(--theme-primary), 0.1)',
                      color: 'rgb(var(--theme-primary))',
                      fontSize: 12,
                      fontWeight: 600,
                    }}
                  >
                    {reportResult.format.toUpperCase()}
                  </div>
                </div>

                <div
                  style={{
                    padding: 16,
                    borderRadius: 12,
                    backgroundColor: 'rgb(var(--theme-bg))',
                    border: '1px solid rgb(var(--theme-border))',
                    marginBottom: 16,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: 200 }}>
                      <p style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))', margin: '0 0 4px' }}>文件名</p>
                      <p style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', margin: 0, wordBreak: 'break-all' }}>
                        {reportResult.file_name}
                      </p>
                    </div>
                    <div style={{ padding: '0 16px', borderLeft: '1px solid rgb(var(--theme-border))' }}>
                      <p style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))', margin: '0 0 4px' }}>文件大小</p>
                      <p style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', margin: 0 }}>
                        {reportResult.file_size > 1024 * 1024
                          ? `${(reportResult.file_size / (1024 * 1024)).toFixed(2)} MB`
                          : reportResult.file_size > 1024
                          ? `${(reportResult.file_size / 1024).toFixed(2)} KB`
                          : `${reportResult.file_size} B`}
                      </p>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  <button
                    onClick={() => handleDownloadReport(executionResult?.report_id)}
                    style={{
                      padding: '10px 18px',
                      borderRadius: 10,
                      border: 'none',
                      backgroundColor: 'rgb(var(--theme-primary))',
                      color: 'white',
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      fontSize: 14,
                      fontWeight: 500,
                      transition: 'all 0.2s',
                    }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="7 10 12 15 17 10" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    下载报告
                  </button>
                  <button
                    onClick={handleViewDetails}
                    style={{
                      padding: '10px 18px',
                      borderRadius: 10,
                      border: '1px solid rgb(var(--theme-border))',
                      backgroundColor: 'transparent',
                      color: 'rgb(var(--theme-text))',
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      fontSize: 14,
                      fontWeight: 500,
                      transition: 'all 0.2s',
                    }}
                  >
                    <ExternalLink style={{ width: 14, height: 14 }} />
                    查看报告详情
                  </button>
                </div>
              </div>
            ) : (
              <div
                style={{
                  textAlign: 'center',
                  padding: 48,
                  borderRadius: 16,
                  border: '1px dashed rgb(var(--theme-border))',
                  backgroundColor: 'rgb(var(--theme-bg-secondary))',
                }}
              >
                <div style={{ marginBottom: 16 }}>
                  <FileText style={{ width: 48, height: 48, color: 'rgb(var(--theme-text-muted))', opacity: 0.3, margin: '0 auto' }} />
                </div>
                <p style={{ fontSize: 15, fontWeight: 500, color: 'rgb(var(--theme-text-secondary))', marginBottom: 6 }}>暂无已生成的报告</p>
                <p style={{ fontSize: 13, color: 'rgb(var(--theme-text-muted))' }}>请在上方输入文件名称并点击"生成报告"</p>
              </div>
            )}

            {/* 历史报告区域 */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, color: 'rgb(var(--theme-text))', margin: 0 }}>历史报告</h3>
                <span style={{ fontSize: 13, color: 'rgb(var(--theme-text-muted))' }}>共 {historyFiles.length} 份报告</span>
              </div>
              {historyFilesLoading ? (
                <div style={{ textAlign: 'center', padding: 48 }}>
                  <Loader2 style={{ width: 32, height: 32, color: 'rgb(var(--theme-primary))', animation: 'spin 1s linear infinite', margin: '0 auto' }} />
                  <p style={{ marginTop: 12, color: 'rgb(var(--theme-text-muted))' }}>加载中...</p>
                </div>
              ) : historyFiles.length === 0 ? (
                <div
                  style={{
                    textAlign: 'center',
                    padding: 40,
                    borderRadius: 16,
                    border: '1px dashed rgb(var(--theme-border))',
                    backgroundColor: 'rgb(var(--theme-bg-secondary))',
                  }}
                >
                  <p style={{ color: 'rgb(var(--theme-text-muted))', fontSize: 14 }}>暂无历史报告</p>
                </div>
              ) : (
                <div style={{ display: 'grid', gap: 12 }}>
                  {historyFiles.map((file) => (
                    <div
                      key={file.id}
                      style={{
                        padding: 16,
                        borderRadius: 14,
                        border: '1px solid rgb(var(--theme-border))',
                        backgroundColor: 'rgb(var(--theme-bg))',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: 16,
                        transition: 'all 0.2s',
                        cursor: 'default',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = 'rgb(var(--theme-primary))'
                        e.currentTarget.style.boxShadow = '0 2px 8px rgba(var(--theme-primary), 0.1)'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = 'rgb(var(--theme-border))'
                        e.currentTarget.style.boxShadow = 'none'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0, flex: 1 }}>
                        <div
                          style={{
                            width: 40,
                            height: 40,
                            borderRadius: 10,
                            backgroundColor: 'rgba(var(--theme-primary), 0.08)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                          }}
                        >
                          <FileText style={{ width: 18, height: 18, color: 'rgb(var(--theme-primary))' }} />
                        </div>
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div
                            style={{
                              fontWeight: 500,
                              color: 'rgb(var(--theme-text))',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              marginBottom: 4,
                            }}
                          >
                            {file.file_name}
                          </div>
                          <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))', display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span>{file.file_type.toUpperCase()}</span>
                            <span>·</span>
                            <span>{file.file_size > 1024 * 1024 ? `${(file.file_size / (1024 * 1024)).toFixed(2)} MB` : file.file_size > 1024 ? `${(file.file_size / 1024).toFixed(2)} KB` : `${file.file_size} B`}</span>
                            <span>·</span>
                            <span>{new Date(file.created_at).toLocaleString('zh-CN')}</span>
                          </div>
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: 8, flexShrink: 0, flexWrap: 'wrap' }}>
                        <button
                          onClick={() => handleDownloadReport(reportResult?.report_id, file.id)}
                          style={{
                            padding: '8px 14px',
                            borderRadius: 8,
                            border: 'none',
                            backgroundColor: 'rgb(var(--theme-primary))',
                            color: 'white',
                            cursor: 'pointer',
                            fontSize: 13,
                            fontWeight: 500,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                            transition: 'all 0.2s',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.opacity = '0.9'
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.opacity = '1'
                          }}
                        >
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                            <polyline points="7 10 12 15 17 10" />
                            <line x1="12" y1="15" x2="12" y2="3" />
                          </svg>
                          下载
                        </button>
                        <button
                          onClick={() => handleDeleteHistoryFile(file.id, file.file_name)}
                          style={{
                            padding: '8px 14px',
                            borderRadius: 8,
                            border: 'none',
                            backgroundColor: 'rgba(255, 77, 79, 0.08)',
                            color: '#ff4d4f',
                            cursor: 'pointer',
                            fontSize: 13,
                            fontWeight: 500,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                            transition: 'all 0.2s',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = 'rgba(255, 77, 79, 0.15)'
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'rgba(255, 77, 79, 0.08)'
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
              )}
            </div>
          </div>
        )}

        {error && (
          <div
            style={{
              padding: 24,
              borderRadius: 16,
              backgroundColor: 'rgba(245, 34, 45, 0.06)',
              border: '1px solid rgba(245, 34, 45, 0.2)',
            }}
          >
            <div
              style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#f5222d', fontWeight: 600, marginBottom: 8 }}
            >
              <AlertTriangle style={{ width: 16, height: 16 }} />
              执行失败
            </div>
            <p style={{ color: 'rgb(var(--theme-text-secondary))' }}>{error}</p>
            <button
              onClick={() => setError(null)}
              style={{
                marginTop: 12,
                padding: '6px 12px',
                borderRadius: 8,
                border: 'none',
                backgroundColor: 'rgba(245, 34, 45, 0.12)',
                color: '#f5222d',
                cursor: 'pointer',
              }}
            >
              关闭
            </button>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
        {currentStep === 'datasource' && (
          <button
            onClick={handleNext}
            style={{
              padding: '10px 18px',
              borderRadius: 12,
              border: 'none',
              backgroundColor: 'rgb(var(--theme-primary))',
              color: 'white',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            下一步
            <ArrowRight style={{ width: 16, height: 16 }} />
          </button>
        )}

        {currentStep === 'config' && (
          <button
            onClick={() => setCurrentStep('datasource')}
            disabled={executionLoading}
            style={{
              padding: '10px 14px',
              borderRadius: 12,
              border: '1px solid rgb(var(--theme-border))',
              backgroundColor: 'transparent',
              color: executionLoading ? 'rgb(var(--theme-text-muted))' : 'rgb(var(--theme-text))',
              cursor: executionLoading ? 'not-allowed' : 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              opacity: executionLoading ? 0.6 : 1,
            }}
          >
            <ArrowLeft style={{ width: 14, height: 14 }} />
            返回上一步
          </button>
        )}

        {currentStep === 'config' && (
          <button
            onClick={handleNext}
            disabled={executionLoading}
            style={{
              padding: '10px 18px',
              borderRadius: 12,
              border: 'none',
              backgroundColor: executionLoading ? 'rgba(var(--theme-primary), 0.7)' : 'rgb(var(--theme-primary))',
              color: 'white',
              cursor: executionLoading ? 'not-allowed' : 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            {executionLoading && <Loader2 style={{ width: 16, height: 16, animation: 'spin 1s linear infinite' }} />}
            {executionLoading ? '执行中...' : '开始执行'}
            {!executionLoading && <ArrowRight style={{ width: 16, height: 16 }} />}
          </button>
        )}

        {currentStep === 'result' && (
          <button
            onClick={() => setCurrentStep('config')}
            disabled={executionLoading || reportLoading}
            style={{
              padding: '10px 14px',
              borderRadius: 12,
              border: '1px solid rgb(var(--theme-border))',
              backgroundColor: 'transparent',
              color: (executionLoading || reportLoading) ? 'rgb(var(--theme-text-muted))' : 'rgb(var(--theme-text))',
              cursor: (executionLoading || reportLoading) ? 'not-allowed' : 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              opacity: (executionLoading || reportLoading) ? 0.6 : 1,
            }}
          >
            <ArrowLeft style={{ width: 16, height: 16 }} />
            返回上一步
          </button>
        )}

        {currentStep === 'result' && (
          <button
            onClick={handleOpenGenerateModal}
            disabled={reportLoading}
            style={{
              padding: '10px 18px',
              borderRadius: 12,
              border: 'none',
              backgroundColor: reportLoading ? 'rgba(var(--theme-primary), 0.7)' : 'rgb(var(--theme-primary))',
              color: 'white',
              cursor: reportLoading ? 'not-allowed' : 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            {reportLoading && <Loader2 style={{ width: 16, height: 16, animation: 'spin 1s linear infinite' }} />}
            {reportLoading ? '生成中...' : '生成报告'}
            {!reportLoading && <ArrowRight style={{ width: 16, height: 16 }} />}
          </button>
        )}

        {currentStep === 'report' && (
          <button
            onClick={() => setCurrentStep('result')}
            disabled={reportLoading}
            style={{
              padding: '10px 14px',
              borderRadius: 12,
              border: '1px solid rgb(var(--theme-border))',
              backgroundColor: 'transparent',
              color: reportLoading ? 'rgb(var(--theme-text-muted))' : 'rgb(var(--theme-text))',
              cursor: reportLoading ? 'not-allowed' : 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              opacity: reportLoading ? 0.6 : 1,
            }}
          >
            <ArrowLeft style={{ width: 14, height: 14 }} />
            返回上一步
          </button>
        )}

        {currentStep === 'report' && (
          <button
            onClick={handleReset}
            disabled={reportLoading}
            style={{
              padding: '10px 14px',
              borderRadius: 12,
              border: '1px solid rgb(var(--theme-border))',
              backgroundColor: 'transparent',
              color: reportLoading ? 'rgb(var(--theme-text-muted))' : 'rgb(var(--theme-text))',
              cursor: reportLoading ? 'not-allowed' : 'pointer',
              opacity: reportLoading ? 0.6 : 1,
            }}
          >
            再次执行
          </button>
        )}
      </div>

      {/* 规则库选择弹框 */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <ListChecks style={{ width: 18, height: 18, color: 'rgb(var(--theme-primary))' }} />
            <span>选择规则库</span>
          </div>
        }
        open={libraryModalOpen}
        onCancel={() => setLibraryModalOpen(false)}
        footer={
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
            <button
              onClick={() => setLibraryModalOpen(false)}
              style={{
                padding: '8px 16px',
                borderRadius: 8,
                border: '1px solid rgb(var(--theme-border))',
                backgroundColor: 'transparent',
                color: 'rgb(var(--theme-text))',
                cursor: 'pointer',
                fontSize: 13,
              }}
            >
              取消
            </button>
            <button
              onClick={() => setLibraryModalOpen(false)}
              style={{
                padding: '8px 16px',
                borderRadius: 8,
                border: 'none',
                backgroundColor: 'rgb(var(--theme-primary))',
                color: 'white',
                cursor: 'pointer',
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              确定 {selectedLibraryIds.length > 0 && `(${selectedLibraryIds.length} 个)`}
            </button>
          </div>
        }
        width={560}
        centered
      >
        <div style={{ padding: '8px 0' }}>
          {libraryLoading ? (
            <div style={{ textAlign: 'center', padding: 48 }}>
              <Loader2 style={{ width: 32, height: 32, color: 'rgb(var(--theme-primary))', animation: 'spin 1s linear infinite', margin: '0 auto 12px' }} />
              <p style={{ fontSize: 14, color: 'rgb(var(--theme-text-muted))', margin: 0 }}>正在加载规则库数据...</p>
            </div>
          ) : libraries.length === 0 ? (
            <div style={{
              textAlign: 'center',
              padding: 48,
              borderRadius: 12,
              backgroundColor: 'rgb(var(--theme-bg-secondary))',
            }}>
              <FileText style={{ width: 48, height: 48, color: 'rgb(var(--theme-text-muted))', margin: '0 auto 16px', opacity: 0.4 }} />
              <p style={{ fontSize: 14, color: 'rgb(var(--theme-text-secondary))', margin: 0 }}>暂无可用的规则库</p>
              <p style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))', margin: '8px 0 0' }}>请先创建规则库后再进行选择</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gap: 10, maxHeight: 400, overflowY: 'auto' }}>
              {libraries.map((lib) => {
                const checked = selectedLibraryIds.includes(lib.id)
                return (
                  <div
                    key={lib.id}
                    onClick={() => {
                      setSelectedLibraryIds((prev) =>
                        prev.includes(lib.id) ? prev.filter((id) => id !== lib.id) : [...prev, lib.id],
                      )
                    }}
                    style={{
                      padding: '14px 16px',
                      borderRadius: 12,
                      border: `2px solid ${checked ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-border))'}`,
                      backgroundColor: checked ? 'rgba(var(--theme-primary), 0.04)' : 'rgb(var(--theme-bg))',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <Checkbox checked={checked} onChange={() => void 0} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, fontSize: 14, color: 'rgb(var(--theme-text))', marginBottom: 4 }}>
                          {lib.name}
                        </div>
                        <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))', display: 'flex', alignItems: 'center', gap: 12 }}>
                          <span>{lib.rule_count || 0} 个规则</span>
                          {lib.description && (
                            <>
                              <span>·</span>
                              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 280 }}>
                                {lib.description}
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                      {checked && (
                        <div style={{
                          width: 24,
                          height: 24,
                          borderRadius: '50%',
                          backgroundColor: 'rgb(var(--theme-primary))',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}>
                          <Check style={{ width: 14, height: 14, color: 'white' }} />
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </Modal>

      <Modal
        title="生成报告"
        open={generateModalOpen}
        onOk={handleConfirmGenerate}
        onCancel={() => setGenerateModalOpen(false)}
        confirmLoading={reportLoading}
        okText={reportLoading ? '生成中...' : '确认生成'}
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
              {/*
              <Radio value="docx">DOCX</Radio>
              <Radio value="pdf">PDF</Radio>
              <Radio value="xlsx">XLSX</Radio>
              */}
            </Radio.Group>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default AuditPage
