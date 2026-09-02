'use client'

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  message,
  Button,
  Tag,
  Modal,
  Select,
  Space,
  Empty,
  Card,
  Typography,
  Tooltip,
  Badge,
  Spin,
  Drawer,
  Input,
  Switch,
} from 'antd'
import {
  PlusOutlined,
  DeleteOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SearchOutlined,
  ArrowRightOutlined,
  EyeOutlined,
} from '@ant-design/icons'
import { useRouter, useParams } from 'next/navigation'
import {
  getDataSourceLibraries,
  getAvailableLibraries,
  addDataSourceLibrary,
  updateDataSourceLibrary,
  removeDataSourceLibrary,
  getLibraryDetail,
  type DataSourceTermLibrary,
  type BusinessTermLibrary,
} from '@/api/businessTerms'

const { Text, Title } = Typography

// 动态颜色映射
const DYNAMIC_COLOR_MAP = [
  'blue', 'purple', 'green', 'orange', 'cyan', 'red', 'magenta', 'volcano',
  'gold', 'lime', 'geekblue', 'pink', 'yellow'
]

const getCategoryColor = (category: string): string => {
  let hash = 0
  for (let i = 0; i < category.length; i++) {
    hash = category.charCodeAt(i) + ((hash << 5) - hash)
  }
  return DYNAMIC_COLOR_MAP[Math.abs(hash) % DYNAMIC_COLOR_MAP.length]
}

// 术语项组件
const TermItem: React.FC<{
  term: {
    id: string
    term_name: string
    term_alias?: string[]
    term_definition: string
    applicable_conditions?: string
    status: string
  }
  onPreview: () => void
}> = ({ term, onPreview }) => {
  const [expanded, setExpanded] = useState(false)
  const canExpand = term.term_definition.length > 50 || (term.applicable_conditions && term.applicable_conditions.length > 0)

  const handleToggle = () => {
    if (canExpand) {
      setExpanded(!expanded)
    }
  }

  return (
    <div
      className="term-item-component"
      style={{
        padding: '16px',
        borderRadius: '12px',
        margin: '4px 8px',
        cursor: canExpand ? 'pointer' : 'default',
        backgroundColor: 'transparent',
        transition: 'all 0.2s',
      }}
      onClick={handleToggle}
      onMouseEnter={(e) => {
        if (canExpand) {
          e.currentTarget.style.backgroundColor = 'rgba(var(--theme-bg-secondary), 0.5)'
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = 'transparent'
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span
              className="font-semibold text-sm"
              style={{ color: 'rgb(var(--theme-primary))' }}
            >
              {term.term_name}
            </span>
            {term.term_alias && term.term_alias.length > 0 && (
              <span className="text-xs" style={{ color: 'rgb(var(--theme-text-muted))', maxWidth: '200px' }}>
                ({term.term_alias.slice(0, 3).join(', ')})
              </span>
            )}
            <Tag
              color={term.status === 'active' ? 'success' : 'default'}
              style={{ borderRadius: '4px', fontSize: '10px', padding: '0 4px', margin: 0 }}
            >
              {term.status === 'active' ? '启用' : '禁用'}
            </Tag>
          </div>
          <Text
            className="text-xs block"
            style={{
              color: 'rgb(var(--theme-text-secondary))',
              display: '-webkit-box',
              WebkitLineClamp: expanded ? 'unset' : 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              wordBreak: 'break-all',
            }}
          >
            {term.term_definition}
          </Text>
        </div>
        <Button
          type="text"
          size="small"
          icon={<EyeOutlined style={{ color: 'rgb(var(--theme-text-secondary))' }} />}
          onClick={(e) => {
            e.stopPropagation()
            onPreview()
          }}
          className="shrink-0"
        />
      </div>

      {expanded && term.applicable_conditions && (
        <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid rgb(var(--theme-border))' }}>
          <Text strong className="text-xs" style={{ color: 'rgb(var(--theme-text-secondary))' }}>适用条件：</Text>
          <Text className="text-xs" style={{ color: 'rgb(var(--theme-text))', marginLeft: '8px' }}>{term.applicable_conditions}</Text>
        </div>
      )}
    </div>
  )
}

// 术语预览抽屉组件
const TermPreviewDrawer: React.FC<{
  libraryId: string
  libraryName: string
  visible: boolean
  onClose: () => void
}> = ({ libraryId, libraryName, visible, onClose }) => {
  const [terms, setTerms] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedTerm, setSelectedTerm] = useState<any>(null)

  useEffect(() => {
    if (visible && libraryId) {
      loadTerms()
    }
  }, [visible, libraryId])

  useEffect(() => {
    if (!visible) {
      setTerms([])
      setSelectedTerm(null)
    }
  }, [visible])

  const loadTerms = async () => {
    setLoading(true)
    try {
      const response = await getLibraryDetail(libraryId, {
        terms_page: 1,
        terms_page_size: 100,
      })
      if (response.code === 200) {
        setTerms(response.data.terms || [])
      }
    } catch (error) {
      console.error('获取术语列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Drawer
      className="term-preview-drawer knowledge-term-preview-drawer"
      title={
        <div className="flex items-center gap-2">
          <span className="text-lg">📚</span>
          <div>
            <Text strong className="text-base" style={{ color: 'rgb(var(--theme-text))' }}>{libraryName}</Text>
            <Text type="secondary" className="text-xs block" style={{ color: 'rgb(var(--theme-text-secondary))' }}>{terms.length} 个术语</Text>
          </div>
        </div>
      }
      placement="right"
      width={520}
      open={visible}
      onClose={onClose}
      footer={
        <div className="flex justify-end" style={{ backgroundColor: 'rgb(var(--theme-bg))', padding: '12px 20px' }}>
          <Button onClick={onClose}>关闭</Button>
        </div>
      }
      styles={{
        body: { padding: 0, backgroundColor: 'rgb(var(--theme-bg))' },
        header: { backgroundColor: 'rgb(var(--theme-bg))', borderBottom: '1px solid rgb(var(--theme-border))', padding: '16px 24px' },
        footer: { backgroundColor: 'rgb(var(--theme-bg))', borderTop: '1px solid rgb(var(--theme-border))', padding: 0 },
        wrapper: { backgroundColor: 'rgb(var(--theme-bg))' },
      }}
    >
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Spin size="large" />
        </div>
      ) : terms.length === 0 ? (
        <Empty
          description={<span style={{ color: 'rgb(var(--theme-text-secondary))' }}>该术语库暂无术语</span>}
          className="py-20"
        />
      ) : (
        <div>
          {terms.map((term, index) => (
            <div
              key={term.id}
              className="term-preview-drawer-item"
              style={{
                borderBottom: index < terms.length - 1 ? '1px solid rgb(var(--theme-border))' : 'none'
              }}
            >
              <TermItem
                term={term}
                onPreview={() => setSelectedTerm(term)}
              />
            </div>
          ))}
        </div>
      )}

      {/* 术语详情弹窗 */}
      <Modal
        className="term-detail-modal"
        title={
          <div className="flex items-center gap-2">
            <span
              className="font-bold text-lg"
              style={{ color: 'rgb(var(--theme-primary))' }}
            >
              {selectedTerm?.term_name}
            </span>
            <Tag
              color={selectedTerm?.status === 'active' ? 'success' : 'default'}
            >
              {selectedTerm?.status === 'active' ? '已启用' : '已禁用'}
            </Tag>
          </div>
        }
        open={!!selectedTerm}
        onCancel={() => setSelectedTerm(null)}
        footer={
          <div className="flex justify-end gap-2">
            <Button onClick={() => setSelectedTerm(null)}>关闭</Button>
          </div>
        }
        width={560}
        centered
      >
        {selectedTerm && (
          <div className="space-y-4 py-4">
            {selectedTerm.term_alias && selectedTerm.term_alias.length > 0 && (
              <div>
                <Text type="secondary" className="text-sm block mb-1" style={{ color: 'rgb(var(--theme-text-secondary))' }}>别名：</Text>
                <div className="flex flex-wrap gap-1 mt-1">
                  {selectedTerm.term_alias.map((alias: string, idx: number) => (
                    <Tag key={idx} style={{ borderRadius: '6px' }}>{alias}</Tag>
                  ))}
                </div>
              </div>
            )}

            <div>
              <Text type="secondary" className="text-sm block mb-1" style={{ color: 'rgb(var(--theme-text-secondary))' }}>定义</Text>
              <div
                className="p-3 rounded-xl text-sm leading-relaxed"
                style={{
                  backgroundColor: 'rgb(var(--theme-bg-secondary))',
                  whiteSpace: 'pre-wrap',
                  color: 'rgb(var(--theme-text))'
                }}
              >
                {selectedTerm.term_definition}
              </div>
            </div>

            {selectedTerm.applicable_conditions && (
              <div>
                <Text type="secondary" className="text-sm block mb-1" style={{ color: 'rgb(var(--theme-text-secondary))' }}>适用条件</Text>
                <div
                  className="p-3 rounded-xl text-sm"
                  style={{ backgroundColor: 'rgb(var(--theme-bg-secondary))', color: 'rgb(var(--theme-text))' }}
                >
                  {selectedTerm.applicable_conditions}
                </div>
              </div>
            )}

            {selectedTerm.remarks && (
              <div>
                <Text type="secondary" className="text-sm block mb-1" style={{ color: 'rgb(var(--theme-text-secondary))' }}>备注</Text>
                <div
                  className="p-3 rounded-xl text-sm"
                  style={{ backgroundColor: 'rgb(var(--theme-bg-secondary))', color: 'rgb(var(--theme-text))' }}
                >
                  {selectedTerm.remarks}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </Drawer>
  )
}

// 扩展的数据源术语库类型（包含预加载的术语数据）
interface DataSourceTermLibraryWithTerms extends DataSourceTermLibrary {
  _terms?: any[]
}

// 术语库卡片组件
const LibraryCard: React.FC<{
  lib: DataSourceTermLibraryWithTerms
  onToggle: () => void
  onRemove: (lib: DataSourceTermLibrary) => void
  onPreview: () => void
}> = ({ lib, onToggle, onRemove, onPreview }) => {
  const [expanded, setExpanded] = useState(false)

  // 直接使用从父组件传入的术语数据（已预先加载）
  const terms = lib._terms || []

  // 计算预览术语标签
  const previewTerms = useMemo(() => {
    if (terms.length === 0) return { shown: [] as any[], remaining: 0 }
    const maxShow = 15
    const shown = terms.slice(0, maxShow)
    const remaining = Math.max(0, lib.library_term_count - maxShow)
    return { shown, remaining }
  }, [terms, lib.library_term_count])

  // 移除确认弹框
  const handleRemoveClick = () => {
    Modal.confirm({
      className: 'remove-confirm-modal',
      title: <span style={{ fontSize: '16px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>确认移除</span>,
      icon: <DeleteOutlined style={{ color: '#ff4d4f', fontSize: '20px' }} />,
      content: (
        <div style={{ fontSize: '14px', color: 'rgb(var(--theme-text-secondary))', marginTop: '12px' }}>
          <p style={{ margin: '0 0 8px' }}>要从该数据源移除术语库 <strong style={{ color: 'rgb(var(--theme-text))' }}>「{lib.library_name}」</strong> 吗？</p>
          <p style={{ margin: 0, fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>移除后，大模型将无法使用该术语库理解业务语义。</p>
        </div>
      ),
      okText: '确认移除',
      cancelText: '取消',
      okButtonProps: { danger: true, size: 'large' },
      cancelButtonProps: { size: 'large' },
      width: 420,
      centered: true,
      maskClosable: true,
      onOk: () => onRemove(lib),
    })
  }

  return (
    <div
      className="border library-card-component transition-all duration-200 overflow-hidden"
      style={{
        backgroundColor: 'rgb(var(--theme-bg))',
        borderColor: 'rgb(var(--theme-border))',
        borderRadius: '12px',
      }}
    >
      {/* 主区域 */}
      <div className="p-4">
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: 0 }}>
            {/* 图标 - 移除背景 */}
            <span className="text-2xl">📚</span>

            {/* 信息 */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '4px' }}>
                <span className="font-semibold text-base truncate" style={{ color: 'rgb(var(--theme-text))' }}>
                  {lib.library_name}
                </span>
                {lib.library_category && (
                  <Tag
                    color={getCategoryColor(lib.library_category)}
                    style={{ borderRadius: '8px', fontSize: '11px', margin: 0 }}
                  >
                    {lib.library_category}
                  </Tag>
                )}
              </div>
              <Text type="secondary" className="text-sm" style={{ display: 'block', color: 'rgb(var(--theme-text-secondary))' }}>
                包含 {lib.library_term_count} 个术语
              </Text>
              {/* 预览术语标签 - 始终显示 */}
              {terms.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '8px', flexWrap: 'wrap' }}>
                  {previewTerms.shown.map(term => (
                    <Tag
                      key={term.id}
                      className="term-alias-tag"
                      style={{
                        borderRadius: '6px',
                        fontSize: '11px',
                        backgroundColor: 'rgba(var(--theme-primary), 0.1)',
                        border: 'none',
                        color: 'rgb(var(--theme-primary))',
                        margin: 0,
                      }}
                    >
                      {term.term_name}
                    </Tag>
                  ))}
                  {previewTerms.remaining > 0 && (
                    <Tag
                      style={{
                        borderRadius: '6px',
                        fontSize: '11px',
                        backgroundColor: 'rgb(var(--theme-bg-secondary))',
                        border: 'none',
                        color: 'rgb(var(--theme-text-secondary))',
                        margin: 0,
                      }}
                    >
                      +{previewTerms.remaining}
                    </Tag>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* 操作按钮 - 垂直居中靠右 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0 }}>
            {/* 预览详情 */}
            {lib.library_term_count > 0 && (
              <Tooltip title="查看详情">
                <Button
                  type="text"
                  size="small"
                  icon={<EyeOutlined style={{ color: 'rgb(var(--theme-text-secondary))' }} />}
                  onClick={onPreview}
                  style={{ width: '32px', height: '32px', padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                />
              </Tooltip>
            )}

            {/* 启用/禁用开关 */}
            <Tooltip title={lib.is_enabled ? '已启用' : '已禁用'}>
              <Switch
                size="small"
                checked={lib.is_enabled}
                onChange={onToggle}
              />
            </Tooltip>

            {/* 移除按钮 */}
            <Button
              type="text"
              danger
              size="small"
              icon={<DeleteOutlined />}
              onClick={handleRemoveClick}
              style={{ width: '32px', height: '32px', padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

// 知识Tab主组件
interface KnowledgeTabProps {
  workspaceId: string
  workspaceName: string
}

const KnowledgeTab: React.FC<KnowledgeTabProps> = ({ workspaceId, workspaceName }) => {
  const router = useRouter()
  const params = useParams<{ lng?: string }>()
  const lng = params?.lng ?? 'zh-CN'

  const [dsLibraries, setDsLibraries] = useState<DataSourceTermLibraryWithTerms[]>([])
  const [loadingDsLibraries, setLoadingDsLibraries] = useState(false)
  const [showAddLibraryModal, setShowAddLibraryModal] = useState(false)
  const [availableLibraries, setAvailableLibraries] = useState<BusinessTermLibrary[]>([])
  const [selectedLibraryId, setSelectedLibraryId] = useState<string>('')
  const [showDropdown, setShowDropdown] = useState(false)
  const [loadingAvailable, setLoadingAvailable] = useState(false)
  const [addingLibrary, setAddingLibrary] = useState(false)

  // 术语预览抽屉
  const [previewDrawerVisible, setPreviewDrawerVisible] = useState(false)
  const [previewLibraryId, setPreviewLibraryId] = useState('')
  const [previewLibraryName, setPreviewLibraryName] = useState('')

  // 搜索
  const [searchKeyword, setSearchKeyword] = useState('')

  // 加载数据源的术语库（包含术语详情用于预览）
  const loadDataSourceLibraries = useCallback(async () => {
    setLoadingDsLibraries(true)
    try {
      const response = await getDataSourceLibraries(workspaceId, {
        page: 1,
        page_size: 100,
      })
      if (response.code === 200) {
        const libraries = response.data.items || []
        setDsLibraries(libraries)

        // 同步加载每个术语库的术语详情用于预览
        const librariesWithTerms = await Promise.all(
          libraries.map(async (lib) => {
            if (lib.library_term_count === 0) return { ...lib, _terms: [] }
            try {
              const detailRes = await getLibraryDetail(lib.library_id, {
                terms_page: 1,
                terms_page_size: 999,
              })
              if (detailRes.code === 200) {
                return { ...lib, _terms: detailRes.data.terms || [] }
              }
            } catch (e) {
              console.error('加载术语详情失败:', e)
            }
            return { ...lib, _terms: [] }
          })
        )
        setDsLibraries(librariesWithTerms)
      }
    } catch (error) {
      console.error('加载数据源术语库失败:', error)
    } finally {
      setLoadingDsLibraries(false)
    }
  }, [workspaceId])

  useEffect(() => {
    loadDataSourceLibraries()
  }, [loadDataSourceLibraries])

  // 加载可添加的术语库
  const loadAvailableLibraries = async () => {
    setLoadingAvailable(true)
    try {
      const response = await getAvailableLibraries(workspaceId)
      if (response.code === 200) {
        setAvailableLibraries(response.data.items || [])
      }
    } catch (error) {
      console.error('加载可添加术语库失败:', error)
    } finally {
      setLoadingAvailable(false)
    }
  }

  // 打开添加术语库弹窗
  const handleOpenAddLibraryModal = async () => {
    setShowAddLibraryModal(true)
    setSelectedLibraryId('')
    await loadAvailableLibraries()
  }

  // 添加术语库到数据源
  const handleAddLibrary = async () => {
    if (!selectedLibraryId) {
      message.warning('请选择一个术语库')
      return
    }
    setAddingLibrary(true)
    try {
      const response = await addDataSourceLibrary(workspaceId, {
        library_id: selectedLibraryId,
        is_enabled: true,
      })
      if (response.code === 200) {
        message.success(response.msg || '添加成功')
        setShowAddLibraryModal(false)
        loadDataSourceLibraries()
      }
    } catch (error) {
      console.error('添加术语库失败:', error)
    } finally {
      setAddingLibrary(false)
    }
  }

  // 切换术语库启用状态
  const handleToggleLibraryEnabled = async (lib: DataSourceTermLibrary) => {
    try {
      const response = await updateDataSourceLibrary(workspaceId, lib.id, {
        is_enabled: !lib.is_enabled,
      })
      if (response.code === 200) {
        message.success(response.data.message || '状态更新成功')
        loadDataSourceLibraries()
      }
    } catch (error) {
      console.error('更新术语库状态失败:', error)
    }
  }

  // 移除术语库
  const handleRemoveLibrary = async (lib: DataSourceTermLibrary) => {
    try {
      const response = await removeDataSourceLibrary(workspaceId, lib.id)
      if (response.code === 200) {
        message.success(response.data.message || '移除成功')
        loadDataSourceLibraries()
      }
    } catch (error) {
      console.error('移除术语库失败:', error)
    }
  }

  // 打开术语预览抽屉
  const handleOpenPreview = (lib: DataSourceTermLibrary) => {
    setPreviewLibraryId(lib.library_id)
    setPreviewLibraryName(lib.library_name)
    setPreviewDrawerVisible(true)
  }

  // 跳转到术语库管理
  const handleGoToLibraryManagement = () => {
    router.push(`/${lng}/business-terms`)
  }

  // 过滤术语库
  const filteredLibraries = useMemo(() => {
    if (!searchKeyword) return dsLibraries
    const keyword = searchKeyword.toLowerCase()
    return dsLibraries.filter(lib =>
      lib.library_name.toLowerCase().includes(keyword) ||
      lib.library_category?.toLowerCase().includes(keyword)
    )
  }, [dsLibraries, searchKeyword])

  const enabledCount = dsLibraries.filter(l => l.is_enabled).length

  return (
    <div
      className="rounded-[28px] overflow-hidden shadow-sm knowledge-tab-container"
      style={{
        backgroundColor: 'rgb(var(--theme-bg))',
        borderColor: 'rgb(var(--theme-border))',
        border: '1px solid rgb(var(--theme-border))',
      }}
    >
      {/* 头部 */}
      <div
        className="px-5 py-4 flex items-center justify-between knowledge-tab-header"
        style={{
          background: 'linear-gradient(135deg, rgba(var(--theme-bg-secondary), 0.8) 0%, rgb(var(--theme-bg)) 50%, rgba(var(--theme-bg-secondary), 0.6) 100%)',
          borderBottom: '1px solid rgb(var(--theme-border))',
        }}
      >
        <div className="flex items-center gap-4">
          {/* 图标 - 圆角矩形背景 */}
          <div className="knowledge-tab-icon-bg" style={{
            width: '2.5rem',
            height: '2.5rem',
            borderRadius: '16px',
            background: 'linear-gradient(135deg, rgb(34,197,94), rgb(5,150,105))',
            color: '#fff',
            boxShadow: '0 8px 16px -4px rgba(34,197,94,0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <span className="text-lg">📖</span>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold" style={{ color: 'rgb(var(--theme-text))' }}>
                知识
              </h3>
              {enabledCount > 0 && (
                <Badge
                  count={enabledCount}
                  style={{
                    backgroundColor: 'rgb(var(--theme-primary))',
                    fontSize: '10px',
                    fontWeight: 600,
                  }}
                />
              )}
            </div>
            <p className="text-sm" style={{ color: 'rgb(var(--theme-text-secondary))' }}>
              管理业务术语与数据关联
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleOpenAddLibraryModal}
            style={{ borderRadius: '10px' }}
          >
            添加术语库
          </Button>
          <Button
            icon={<ArrowRightOutlined />}
            onClick={handleGoToLibraryManagement}
            style={{ borderRadius: '10px' }}
          >
            创建术语库
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => loadDataSourceLibraries()}
            loading={loadingDsLibraries}
            style={{ borderRadius: '10px' }}
          >
            刷新
          </Button>
        </div>
      </div>

      {/* 内容区 */}
      <div className="p-6">
        {/* 搜索框 */}
        {dsLibraries.length > 0 && (
          <div className="mb-5">
            <Input
              className="knowledge-tab-search"
              placeholder="搜索已关联的术语库..."
              prefix={<SearchOutlined style={{ color: 'rgb(var(--theme-text-muted))' }} />}
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              allowClear
              style={{ borderRadius: '12px', maxWidth: '320px' }}
            />
          </div>
        )}

        {/* 加载状态 */}
        {loadingDsLibraries ? (
          <div className="flex items-center justify-center py-16">
            <Spin size="large" />
          </div>
        ) : dsLibraries.length === 0 ? (
          /* 空状态 */
          <div className="py-16 text-center">
            <div className="mb-4">
              <span className="text-4xl knowledge-tab-empty-icon">📚</span>
            </div>
            <Title level={4} className="mb-2" style={{ color: 'rgb(var(--theme-text))' }}>
              暂无关联的术语库
            </Title>
            <Text type="secondary" className="text-sm block mb-6 max-w-sm mx-auto" style={{ whiteSpace: 'nowrap' }}>
              添加术语库后，大模型将理解业务术语与指标口径，提升 NL2SQL 查询准确率
            </Text>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleOpenAddLibraryModal}
              style={{ borderRadius: '10px' }}
            >
              添加术语库
            </Button>
          </div>
        ) : filteredLibraries.length === 0 ? (
          /* 搜索无结果 */
          <div className="py-12 text-center">
            <Empty
              description={
                <div>
                  <Text type="secondary">没有找到匹配的术语库</Text>
                </div>
              }
            >
              <Button onClick={() => setSearchKeyword('')} style={{ borderRadius: '12px' }}>
                清除搜索
              </Button>
            </Empty>
          </div>
        ) : (
          /* 术语库列表 */
          <div className="space-y-4">
            {filteredLibraries.map(lib => (
              <LibraryCard
                key={lib.id}
                lib={lib}
                onToggle={() => handleToggleLibraryEnabled(lib)}
                onRemove={handleRemoveLibrary}
                onPreview={() => handleOpenPreview(lib)}
              />
            ))}
          </div>
        )}
      </div>

      {/* 添加术语库弹窗 */}
      <Modal
        className="add-library-modal"
        title={
          <div className="flex items-center gap-3">
            <span className="text-xl">📚</span>
            <div>
              <Text strong className="text-base" style={{ color: 'rgb(var(--theme-text))' }}>添加术语库</Text>
              <Text type="secondary" className="text-xs block" style={{ whiteSpace: 'nowrap' }}>
                关联到「{workspaceName}」
              </Text>
            </div>
          </div>
        }
        open={showAddLibraryModal}
        onOk={handleAddLibrary}
        onCancel={() => setShowAddLibraryModal(false)}
        confirmLoading={addingLibrary}
        okText="添加"
        cancelText="取消"
        destroyOnClose
        centered
        width={480}
      >
        <div className="py-4">
          <Text type="secondary" className="text-sm block mb-4" style={{ whiteSpace: 'nowrap' }}>
            关联术语库后，大模型将在查询中启用术语展开功能
          </Text>

          <Select
            style={{ width: '100%' }}
            placeholder="请选择术语库"
            value={selectedLibraryId || undefined}
            onChange={(value) => {
              setSelectedLibraryId(value)
              setShowDropdown(false)
            }}
            loading={loadingAvailable}
            open={showDropdown}
            onDropdownVisibleChange={setShowDropdown}
            dropdownStyle={{ padding: '4px 0' }}
            notFoundContent={null}
            suffixIcon={<SearchOutlined style={{ color: 'rgb(var(--theme-text-muted))' }} />}
          >
            {availableLibraries.map(lib => (
              <Select.Option key={lib.id} value={lib.id} label={lib.name}>
                <div className="flex items-center justify-between py-1.5 px-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm" style={{ color: 'rgb(var(--theme-text))' }}>{lib.name}</span>
                    {lib.category && (
                      <Tag color={getCategoryColor(lib.category)} style={{ borderRadius: '6px', fontSize: '10px', margin: 0 }}>
                        {lib.category}
                      </Tag>
                    )}
                  </div>
                  <Text className="text-xs" style={{ color: 'rgb(var(--theme-text-secondary))' }}>
                    {lib.term_count} 个术语
                  </Text>
                </div>
              </Select.Option>
            ))}
          </Select>

          {availableLibraries.length === 0 && !loadingAvailable && (
            <div className="py-6 text-center">
              <Empty
                description={
                  <div>
                    <Text type="secondary" className="text-sm">暂无可添加的术语库</Text>
                    <div className="mt-2">
                      <Button
                        type="link"
                        size="small"
                        icon={<ArrowRightOutlined />}
                        onClick={handleGoToLibraryManagement}
                      >
                        去创建术语库
                      </Button>
                    </div>
                  </div>
                }
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            </div>
          )}
        </div>
      </Modal>

      {/* 术语预览抽屉 */}
      <TermPreviewDrawer
        libraryId={previewLibraryId}
        libraryName={previewLibraryName}
        visible={previewDrawerVisible}
        onClose={() => setPreviewDrawerVisible(false)}
      />
    </div>
  )
}

export default KnowledgeTab
