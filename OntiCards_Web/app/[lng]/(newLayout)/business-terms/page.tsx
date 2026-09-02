'use client'

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import Link from 'next/link'
import {
  message, Button, Tag, Modal, Form, Input, Select, Space, Spin, Drawer,
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, EditOutlined, SearchOutlined, ReloadOutlined,
  CheckCircleOutlined, CloseCircleOutlined, RocketOutlined, ArrowRightOutlined,
} from '@ant-design/icons'
import { ChevronRight, Loader2 } from 'lucide-react'
import { useRouter } from 'next-nprogress-bar'
import { useParams } from 'next/navigation'
import {
  getLibraryList, createLibrary, updateLibrary, deleteLibrary,
  getTemplateCategories, getTemplateList, importFromTemplate,
  type BusinessTermLibrary, type LibraryFormData, type TemplateCategory,
} from '@/api/businessTerms'

const { TextArea } = Input

// 动态颜色
const COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#06b6d4', '#ef4444', '#ec4899', '#6366f1', '#84cc16', '#f97316']
const getColor = (str: string) => {
  let hash = 0
  for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash)
  return COLORS[Math.abs(hash) % COLORS.length]
}

// 术语库卡片
const LibraryCard: React.FC<{
  lib: BusinessTermLibrary
  onEdit: () => void
  onDelete: (id: string) => void
  onEnter: () => void
}> = ({ lib, onEdit, onDelete, onEnter }) => {
  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    Modal.confirm({
      className: 'library-delete-confirm',
      title: <span style={{ fontSize: '16px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>确认删除</span>,
      icon: <DeleteOutlined style={{ color: '#ff4d4f', fontSize: '20px' }} />,
      content: (
        <div style={{ fontSize: '14px', color: 'rgb(var(--theme-text-secondary))', marginTop: '12px' }}>
          <p style={{ margin: '0 0 8px' }}>确定要删除术语库 <strong style={{ color: 'rgb(var(--theme-text))' }}>「{lib.name}」</strong> 吗？</p>
          <p style={{ margin: 0, fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>删除后无法恢复，术语库中的所有术语将被一并删除。</p>
        </div>
      ),
      okText: '确认删除',
      cancelText: '取消',
      okButtonProps: { danger: true, size: 'large' },
      cancelButtonProps: { size: 'large' },
      width: 420,
      centered: true,
      maskClosable: true,
      onOk: () => onDelete(lib.id),
    })
  }

  return (
    <div style={{
      background: 'rgb(var(--theme-bg))', borderRadius: '16px',
      border: '1px solid rgb(var(--theme-border))', overflow: 'hidden', transition: 'all 0.25s',
      cursor: 'pointer',
    }}
         onClick={onEnter}
         onMouseEnter={(e) => {
           e.currentTarget.style.transform = 'translateY(-2px)'
           e.currentTarget.style.boxShadow = '0 8px 20px rgba(0,0,0,0.08)'
         }}
         onMouseLeave={(e) => {
           e.currentTarget.style.transform = 'translateY(0)'
           e.currentTarget.style.boxShadow = 'none'
         }}
    >
      <div style={{ padding: '20px' }}>
        {/* 顶部：图标 + 信息区 */}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px', marginBottom: '12px' }}>
          {/* 左侧图标 */}
          <div style={{
            width: '48px', height: '48px', borderRadius: '14px', flexShrink: 0,
            background: `linear-gradient(135deg, ${getColor(lib.category || '默认')}20, ${getColor(lib.category || '默认')}10)`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '22px'
          }}>📚</div>

          {/* 右侧信息区 */}
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {/* 第一行：名称 + 状态 + 操作按钮 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontWeight: 600, fontSize: '16px', color: 'rgb(var(--theme-text))', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{lib.name}</span>
              <Tag
                color={lib.status === 'active' ? 'success' : 'default'}
                icon={lib.status === 'active' ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                style={{ borderRadius: '6px', fontSize: '11px', flexShrink: 0 }}
              >
                {lib.status === 'active' ? '已启用' : '已禁用'}
              </Tag>
              {/* 操作按钮 */}
              <div style={{ display: 'flex', gap: '2px', flexShrink: 0 }}>
                <Button
                  type="text" size="small" icon={<EditOutlined />}
                  onClick={(e) => { e.stopPropagation(); onEdit() }}
                  style={{ width: 28, height: 28, padding: 0, color: 'rgb(var(--theme-text-secondary))' }}
                />
                <Button
                  type="text" size="small" danger icon={<DeleteOutlined />}
                  onClick={handleDeleteClick}
                  style={{ width: 28, height: 28, padding: 0 }}
                />
              </div>
            </div>
            {/* 第二行：行业分类 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {lib.category && (
                <Tag style={{ borderRadius: '6px', fontSize: '11px', margin: 0, background: `${getColor(lib.category)}15`, border: 'none', color: getColor(lib.category) }}>
                  {lib.category}
                </Tag>
              )}
            </div>
          </div>
        </div>

        {/* 描述 */}
        {lib.description && (
          <p style={{
            margin: '0 0 14px', paddingLeft: '62px', fontSize: '13px', color: 'rgb(var(--theme-text-secondary))',
            lineHeight: 1.6, overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box',
            WebkitLineClamp: 2, WebkitBoxOrient: 'vertical'
          }}>
            {lib.description}
          </p>
        )}

        {/* 底部信息 */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          paddingTop: '14px', borderTop: '1px solid rgb(var(--theme-border))'
        }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: 'rgb(var(--theme-text-secondary))' }}>
            <span style={{ fontWeight: 600, color: 'rgb(var(--theme-text))' }}>{lib.term_count}</span> 个术语
          </span>
          <span style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>
            {lib.created_at ? new Date(lib.created_at).toLocaleDateString('zh-CN') : '-'}
          </span>
        </div>
      </div>
    </div>
  )
}

// 主页面
const LibrariesListPage: React.FC = () => {
  const router = useRouter()
  const params = useParams<{ lng?: string }>()
  const lng = (params?.lng as string) || 'zh-CN'
  const [libraries, setLibraries] = useState<BusinessTermLibrary[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>(undefined)
  const [tab, setTab] = useState<'all' | 'active' | 'inactive'>('all')

  const [guideVisible, setGuideVisible] = useState(false)
  const [step, setStep] = useState<'choose' | 'template'>('choose')
  const [templates, setTemplates] = useState<TemplateCategory[]>([])
  const [templateLoading, setTemplateLoading] = useState(false)
  const [selectedCat, setSelectedCat] = useState('')
  const [creating, setCreating] = useState(false)

  // 术语预览抽屉
  const [termPreviewVisible, setTermPreviewVisible] = useState(false)
  const [previewTemplate, setPreviewTemplate] = useState<{ template_name: string; count: number; category: string } | null>(null)
  const [previewTerms, setPreviewTerms] = useState<Array<{ id: string; term_name: string; term_alias: string[]; term_definition: string }>>([])
  const [previewLoading, setPreviewLoading] = useState(false)

  const [formVisible, setFormVisible] = useState(false)
  const [formLoading, setFormLoading] = useState(false)
  const [editing, setEditing] = useState<BusinessTermLibrary | null>(null)
  const [form] = Form.useForm()

  const existingCats = useMemo(() => {
    const s = new Set<string>()
    libraries.forEach(l => l.category && s.add(l.category))
    return Array.from(s).sort()
  }, [libraries])

  const filtered = useMemo(() => {
    return libraries.filter(l => {
      if (search) {
        const k = search.toLowerCase()
        if (!l.name.toLowerCase().includes(k) && !l.description?.toLowerCase().includes(k)) return false
      }
      if (categoryFilter && l.category !== categoryFilter) return false
      if (tab === 'active' && l.status !== 'active') return false
      if (tab === 'inactive' && l.status !== 'inactive') return false
      return true
    })
  }, [libraries, search, categoryFilter, tab])

  const stats = useMemo(() => ({
    total: libraries.length,
    terms: libraries.reduce((s, l) => s + l.term_count, 0),
    active: libraries.filter(l => l.status === 'active').length,
  }), [libraries])

  const fetchLibraries = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getLibraryList({ page: 1, page_size: 100 })
      if (res.code === 200) setLibraries(res.data.items)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchLibraries() }, [fetchLibraries])

  const openGuide = () => { setStep('choose'); setSelectedCat(''); setGuideVisible(true) }
  const openForm = () => { setEditing(null); form.resetFields(); setFormVisible(true) }
  const openEdit = (lib: BusinessTermLibrary) => {
    setEditing(lib)
    form.setFieldsValue({ name: lib.name, description: lib.description, category: lib.category })
    setFormVisible(true)
  }

  const handleCreate = async () => {
    if (!selectedCat) { message.warning('请选择模板'); return }
    setCreating(true)
    try {
      const name = `${selectedCat}术语库`
      const cr = await createLibrary({ name, description: `基于${selectedCat}行业模板创建`, category: selectedCat })
      if (cr.code === 200) {
        await importFromTemplate({ library_id: cr.data.id, category: selectedCat })
        message.success(`已创建「${name}」`)
        setGuideVisible(false)
        fetchLibraries()
      } else {
        message.error(cr.msg || '创建术语库失败')
      }
    } catch (e) { console.error(e); message.error('创建术语库失败，请重试') }
    finally { setCreating(false) }
  }

  const handleSave = async () => {
    try {
      const v = await form.validateFields()
      setFormLoading(true)
      const data: LibraryFormData = { name: v.name, description: v.description, category: v.category || undefined }
      const res = editing ? await updateLibrary(editing.id, data) : await createLibrary(data)
      if (res.code === 200) {
        message.success(res.msg)
        setFormVisible(false)
        setGuideVisible(false)
        fetchLibraries()
      } else {
        message.error(res.msg || '操作失败')
      }
    } catch (e) { console.error(e); message.error('保存失败，请重试') }
    finally { setFormLoading(false) }
  }

  const handleDelete = async (id: string) => {
    const res = await deleteLibrary(id)
    if (res.code === 200) { message.success('删除成功'); fetchLibraries() }
  }

  // 打开术语预览抽屉
  const openTermPreview = async (template: { template_name: string; count: number; category: string }) => {
    setPreviewTemplate(template)
    setTermPreviewVisible(true)
    setPreviewLoading(true)
    setPreviewTerms([])
    try {
      const res = await getTemplateList({ category: template.category, template_name: template.template_name })
      if (res.code === 200) {
        setPreviewTerms(res.data.items.map(item => ({
          id: item.id,
          term_name: item.term_name,
          term_alias: item.term_alias || [],
          term_definition: item.term_definition,
        })))
      }
    } catch (e) { console.error(e) }
    finally { setPreviewLoading(false) }
  }

  return (
    <div className="space-y-6 libraries-list-page">
      {/* 标题区 */}
      <header>
        <h1 className="text-2xl font-semibold mb-1" style={{ color: 'rgb(var(--theme-text))' }}>
          业务术语库
        </h1>
        <p style={{ margin: '6px 0 0', fontSize: '14px', color: 'rgb(var(--theme-text-secondary))' }}>
          统一管理业务术语，提升查询准确率
        </p>
      </header>

      {/* 统计卡片 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
        {loading ? (
          [1, 2, 3].map(i => (
            <div key={i} className="business-terms-card" style={{
              padding: '16px', borderRadius: '16px',
              background: 'rgb(var(--theme-bg))', border: '1px solid rgb(var(--theme-border))'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: 'rgba(var(--theme-bg-secondary))' }} />
                <div>
                  <div style={{ height: '10px', width: '50px', borderRadius: '4px', background: 'rgba(var(--theme-bg-secondary))', marginBottom: '6px' }} />
                  <div style={{ height: '20px', width: '36px', borderRadius: '4px', background: 'rgba(var(--theme-bg-secondary))' }} />
                </div>
              </div>
            </div>
          ))
        ) : [
          { label: '术语库', value: stats.total, icon: '📚', color: 'rgb(var(--theme-primary))', bg: 'rgba(var(--theme-primary), 0.08)' },
          { label: '术语', value: stats.terms, icon: '📝', color: 'rgb(var(--theme-primary))', bg: 'rgba(var(--theme-primary), 0.08)' },
          { label: '已启用', value: stats.active, icon: <CheckCircleOutlined style={{ color: '#4ade80', fontSize: '18px' }} />, color: '#4ade80', bg: 'rgba(34, 197, 94, 0.08)', isGreen: true },
        ].map((s: any, i) => (
          <div key={i} className="business-terms-card" style={{
            padding: '16px', borderRadius: '16px', background: 'rgb(var(--theme-bg))',
            border: '1px solid rgb(var(--theme-border))', transition: 'all 0.2s',
            position: 'relative', overflow: 'hidden',
          }}>
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
                background: `radial-gradient(circle, ${s.color}, transparent 70%)`,
                filter: 'blur(15px)',
              }}
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', position: 'relative', zIndex: 1 }}>
              <div style={{
                width: '40px', height: '40px', borderRadius: '12px',
                background: s.bg, display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                {typeof s.icon === 'string' ? (
                  <span style={{ fontSize: '20px' }}>{s.icon}</span>
                ) : s.icon}
              </div>
              <div>
                <p style={{ margin: 0, fontSize: '11px', color: 'rgb(var(--theme-text-secondary))', fontWeight: 500 }}>{s.label}</p>
                <p style={{ margin: '2px 0 0', fontSize: '22px', fontWeight: 700, color: s.color }}>{s.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 操作栏 */}
      <div className="business-terms-card" style={{
        display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap',
        padding: '16px 20px', borderRadius: '16px',
        background: 'rgb(var(--theme-bg))', border: '1px solid rgb(var(--theme-border))'
      }}>
        <Input
          className="search-input"
          placeholder="搜索术语库..."
          prefix={<SearchOutlined style={{ color: 'rgb(var(--theme-text-muted))' }} />}
          value={search}
          onChange={e => setSearch(e.target.value)}
          allowClear
          style={{ width: 200, borderRadius: '10px' }}
        />
        <Select
          placeholder="行业分类"
          style={{ width: 140, borderRadius: '10px' }}
          allowClear showSearch
          value={categoryFilter}
          onChange={setCategoryFilter}
          options={existingCats.map(c => ({ label: c, value: c }))}
        />
        <div className="business-terms-tab-switch" style={{ display: 'flex', gap: '4px', padding: '4px', background: 'rgba(0,0,0,0.04)', borderRadius: '10px' }}>
          {[{ k: 'all', l: '全部' }, { k: 'active', l: '已启用' }, { k: 'inactive', l: '已禁用' }].map(t => (
            <button key={t.k} onClick={() => setTab(t.k as any)} className={tab === t.k ? 'active' : ''} style={{
              padding: '6px 14px', fontSize: '12px', fontWeight: 500, borderRadius: '8px',
              border: 'none', cursor: 'pointer', transition: 'all 0.2s',
              background: tab === t.k ? 'rgb(var(--theme-bg))' : 'transparent',
              color: tab === t.k ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-secondary))',
              boxShadow: tab === t.k ? '0 1px 4px rgba(0,0,0,0.08)' : 'none'
            }}>{t.l}</button>
          ))}
        </div>
        <span style={{ fontSize: '13px', color: 'rgb(var(--theme-text-secondary))' }}>共 {filtered.length} 个</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '10px' }}>
          <Button icon={loading ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <ReloadOutlined />} onClick={fetchLibraries} style={{ borderRadius: '10px' }}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openGuide} style={{ borderRadius: '10px' }}>
            新建术语库
          </Button>
        </div>
      </div>

      {/* 列表 */}
      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: '16px' }}>
          {[1, 2, 3].map(i => (
            <div key={i} className="business-terms-card" style={{
              padding: '20px', borderRadius: '16px',
              background: 'rgb(var(--theme-bg))', border: '1px solid rgb(var(--theme-border))'
            }}>
              <div style={{ display: 'flex', gap: '14px', marginBottom: '14px' }}>
                <div style={{ width: '48px', height: '48px', borderRadius: '14px', background: 'rgba(var(--theme-bg-secondary))' }} />
                <div style={{ flex: 1 }}>
                  <div style={{ height: '16px', width: '60%', borderRadius: '4px', background: 'rgba(var(--theme-bg-secondary))', marginBottom: '10px' }} />
                  <div style={{ height: '12px', width: '40%', borderRadius: '4px', background: 'rgba(var(--theme-bg-secondary))' }} />
                </div>
              </div>
              <div style={{ height: '12px', width: '80%', borderRadius: '4px', background: 'rgba(var(--theme-bg-secondary))', marginBottom: '8px' }} />
              <div style={{ height: '12px', width: '60%', borderRadius: '4px', background: 'rgba(var(--theme-bg-secondary))' }} />
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="business-terms-card" style={{
          textAlign: 'center', padding: '80px 20px', borderRadius: '20px',
          background: 'rgb(var(--theme-bg))', border: '2px dashed rgb(var(--theme-border))'
        }}>
          <div style={{
            width: '80px', height: '80px', borderRadius: '50%',
            background: 'rgba(var(--theme-primary), 0.08)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 20px', fontSize: '36px'
          }}>📚</div>
          <h3 style={{ margin: '0 0 8px', color: 'rgb(var(--theme-text))', fontSize: '18px', fontWeight: 600 }}>
            {libraries.length === 0 ? '还没有术语库' : '没有找到匹配的术语库'}
          </h3>
          <p style={{ margin: '0 0 20px', color: 'rgb(var(--theme-text-secondary))', fontSize: '14px' }}>
            {libraries.length === 0 ? '创建术语库来统一管理您的业务术语' : '尝试调整搜索条件'}
          </p>
          {libraries.length === 0 ? (
            <Space size="middle">
              <Button icon={<RocketOutlined />} onClick={openGuide} size="large" style={{ borderRadius: '12px' }}>
                快速创建
              </Button>
              <Button icon={<PlusOutlined />} onClick={openForm} size="large" style={{ borderRadius: '12px' }}>
                从零创建
              </Button>
            </Space>
          ) : (
            <Button onClick={() => { setSearch(''); setTab('all') }} size="large" style={{ borderRadius: '12px' }}>
              清除筛选
            </Button>
          )}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: '16px' }}>
          {filtered.map(lib => (
            <LibraryCard
              key={lib.id}
              lib={lib}
              onEdit={() => openEdit(lib)}
              onDelete={handleDelete}
              onEnter={() => router.push(`/${lng}/business-terms/${lib.id}`)}
            />
          ))}
        </div>
      )}

      {/* 新建引导 */}
      <Modal
        title={<span style={{ fontSize: '16px', fontWeight: 600 }}>🚀 新建术语库</span>}
        open={guideVisible}
        onCancel={() => setGuideVisible(false)}
        footer={null}
        width={600}
        centered
      >
        <div style={{ padding: '16px 0' }}>
          {step === 'choose' ? (
            <>
              <div style={{
                padding: '14px', borderRadius: '12px',
                background: 'rgb(var(--theme-bg-secondary))', marginBottom: '20px',
                display: 'flex', gap: '10px', alignItems: 'flex-start'
              }}>
                <span style={{ fontSize: '18px' }}>💡</span>
                <div>
                  <strong style={{ fontSize: '13px' }}>选择创建方式</strong>
                  <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'rgb(var(--theme-text-secondary))' }}>从模板创建可快速导入预置术语</p>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="business-terms-guide-option" onClick={async () => {
                  setStep('template')
                  setTemplateLoading(true)
                  try {
                    const r = await getTemplateCategories()
                    if (r.code === 200) setTemplates(r.data.categories || [])
                  } catch (e) {
                    console.error(e)
                  } finally {
                    setTemplateLoading(false)
                  }
                }}
                     style={{
                       padding: '20px', borderRadius: '14px',
                       border: '2px solid rgba(var(--theme-primary), 0.3)',
                       background: 'rgba(var(--theme-primary), 0.05)', cursor: 'pointer', textAlign: 'center'
                     }}>
                  <div style={{
                    width: '52px', height: '52px', borderRadius: '14px',
                    background: 'rgba(var(--theme-primary), 0.15)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    margin: '0 auto 12px', fontSize: '22px'
                  }}>
                    <RocketOutlined style={{ color: 'rgb(var(--theme-primary))', fontSize: '22px' }} />
                  </div>
                  <p style={{ margin: 0, fontWeight: 600, fontSize: '14px', color: 'rgb(var(--theme-text))' }}>从模板创建</p>
                  <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'rgb(var(--theme-text-secondary))' }}>基于行业预置模板</p>
                  <div style={{ marginTop: '10px' }}><Tag color="blue">推荐</Tag></div>
                </div>
                <div className="business-terms-guide-option" onClick={openForm} style={{
                  padding: '20px', borderRadius: '14px',
                  border: '1px solid rgb(var(--theme-border))', cursor: 'pointer', textAlign: 'center'
                }}>
                  <div style={{
                    width: '52px', height: '52px', borderRadius: '14px',
                    background: 'rgba(var(--theme-bg-secondary))',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    margin: '0 auto 12px', fontSize: '22px'
                  }}>
                    <PlusOutlined style={{ color: 'rgb(var(--theme-text-secondary))', fontSize: '20px' }} />
                  </div>
                  <p style={{ margin: 0, fontWeight: 600, fontSize: '14px', color: 'rgb(var(--theme-text))' }}>从零创建</p>
                  <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'rgb(var(--theme-text-secondary))' }}>手动添加术语</p>
                </div>
              </div>
            </>
          ) : (
            <>
              <div onClick={() => setStep('choose')} style={{
                color: 'rgb(var(--theme-primary))', fontSize: '13px', cursor: 'pointer',
                marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '4px'
              }}>
                <ArrowRightOutlined style={{ transform: 'rotate(180deg)' }} /> 返回选择
              </div>
              <div style={{
                padding: '12px 14px', borderRadius: '10px',
                background: 'rgba(59,130,246,0.06)', marginBottom: '14px',
                border: '1px solid rgba(59,130,246,0.15)'
              }}>
                <p style={{ margin: 0, fontSize: '12px', color: 'rgb(var(--theme-text-secondary))', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <RocketOutlined style={{ color: '#3b82f6' }} />
                  点击分类展开查看模板详情，选择后自动导入全部术语
                </p>
              </div>
              <div style={{ maxHeight: '420px', overflowY: 'auto' }}>
                {templateLoading ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px 20px', gap: '16px' }}>
                    <Spin size="large" />
                    <p style={{ margin: 0, fontSize: '13px', color: 'rgb(var(--theme-text-secondary))' }}>正在加载模板...</p>
                  </div>
                ) : templates.length === 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px 20px', gap: '12px' }}>
                    <span style={{ fontSize: '48px' }}>📋</span>
                    <p style={{ margin: 0, fontSize: '13px', color: 'rgb(var(--theme-text-secondary))' }}>暂无可用模板</p>
                  </div>
                ) : (
                  templates.map(t => {
                    const isSelected = selectedCat === t.category
                    const totalTerms = t.templates.reduce((s, x) => s + x.count, 0)
                    return (
                      <div key={t.category} style={{
                        borderRadius: '12px', marginBottom: '10px',
                        border: `2px solid ${isSelected ? '#3b82f6' : 'rgb(var(--theme-border))'}`,
                        background: 'rgb(var(--theme-bg))',
                        overflow: 'hidden',
                        transition: 'all 0.2s'
                      }}>
                        {/* 分类头部 - 可点击展开 */}
                        <div onClick={() => setSelectedCat(isSelected ? '' : t.category)}
                             style={{
                               padding: '14px 16px', cursor: 'pointer',
                               background: isSelected ? 'rgba(59,130,246,0.06)' : 'transparent',
                               display: 'flex', alignItems: 'center', gap: '12px'
                             }}>
                          <ChevronRight size={16} style={{
                            color: 'rgb(var(--theme-text-secondary))',
                            transform: isSelected ? 'rotate(90deg)' : 'rotate(0deg)',
                            transition: 'transform 0.2s'
                          }} />
                          <Tag color={getColor(t.category)} style={{ borderRadius: '6px', fontSize: '11px', margin: 0 }}>{t.category}</Tag>
                          <span style={{ fontSize: '12px', color: 'rgb(var(--theme-text-secondary))', flex: 1 }}>
                          {t.templates.length} 个模板 · 共 {totalTerms} 个术语
                        </span>
                          {isSelected && (
                            <CheckCircleOutlined style={{ color: '#3b82f6' }} />
                          )}
                        </div>
                        {/* 展开的模板列表 */}
                        {isSelected && (
                          <div style={{
                            borderTop: '1px solid rgb(var(--theme-border))',
                            padding: '12px 16px',
                            background: 'rgb(var(--theme-bg-secondary))'
                          }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                              {t.templates.map(x => (
                                <div key={x.template_name} style={{
                                  display: 'flex', alignItems: 'center', gap: '10px',
                                  padding: '10px 12px', borderRadius: '8px',
                                  background: 'rgb(var(--theme-bg))',
                                  border: '1px solid rgb(var(--theme-border))',
                                  transition: 'all 0.2s'
                                }}>
                                  <div style={{
                                    width: '32px', height: '32px', borderRadius: '8px', flexShrink: 0,
                                    background: `${getColor(t.category)}20`,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    fontSize: '14px'
                                  }}>📋</div>
                                  <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ fontSize: '13px', fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: '4px' }}>
                                      {x.template_name}
                                    </div>
                                    <div style={{ fontSize: '11px', color: 'rgb(var(--theme-text-secondary))' }}>
                                      包含 <span style={{ color: 'rgb(var(--theme-primary))', fontWeight: 600 }}>{x.count}</span> 个术语
                                    </div>
                                  </div>
                                  <Button
                                    type="text" size="small"
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      openTermPreview({ ...x, category: t.category })
                                    }}
                                    style={{ fontSize: '12px', color: 'rgb(var(--theme-primary))', flexShrink: 0 }}
                                  >
                                    查看术语
                                  </Button>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })
                )}
              </div>
              <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <Button onClick={() => setGuideVisible(false)}>取消</Button>
                <Button type="primary" icon={<RocketOutlined />} loading={creating} onClick={handleCreate} disabled={!selectedCat}>
                  创建并导入
                </Button>
              </div>
            </>
          )}
        </div>
      </Modal>

      {/* 术语预览抽屉 */}
      <Drawer
        className="term-preview-drawer libraries-list-term-preview-drawer"
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{
              padding: '4px 10px', borderRadius: '6px', fontSize: '11px',
              background: `${getColor(previewTemplate?.category || '')}20`,
              color: getColor(previewTemplate?.category || '')
            }}>
              {previewTemplate?.category}
            </span>
            <span style={{ fontSize: '15px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>{previewTemplate?.template_name}</span>
          </div>
        }
        open={termPreviewVisible}
        onClose={() => setTermPreviewVisible(false)}
        width={560}
        styles={{
          body: { padding: '16px', backgroundColor: 'rgb(var(--theme-bg))' },
          header: { backgroundColor: 'rgb(var(--theme-bg))', borderBottom: '1px solid rgb(var(--theme-border))' },
        }}
      >
        {previewTemplate && (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {/* 术语数量提示 */}
            <div style={{
              padding: '10px 14px', borderRadius: '10px',
              background: `${getColor(previewTemplate.category)}10`,
              border: `1px solid ${getColor(previewTemplate.category)}30`,
              marginBottom: '14px', flexShrink: 0
            }}>
              <span style={{ fontSize: '13px', color: 'rgb(var(--theme-text-secondary))' }}>
                该模板共包含 <span style={{ color: 'rgb(var(--theme-primary))', fontWeight: 600 }}>{previewTemplate.count}</span> 个术语
              </span>
            </div>

            {/* 术语列表 */}
            {previewLoading ? (
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{ textAlign: 'center' }}>
                  <Spin size="large" />
                  <p style={{ margin: '16px 0 0', color: 'rgb(var(--theme-text-secondary))', fontSize: '13px' }}>正在加载术语...</p>
                </div>
              </div>
            ) : previewTerms.length === 0 ? (
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgb(var(--theme-text-secondary))' }}>
                暂无术语数据
              </div>
            ) : (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '12px',
                overflowY: 'auto',
                flex: 1,
                alignContent: 'start'
              }}>
                {previewTerms.map(term => (
                  <div key={term.id} className="term-preview-card" style={{
                    padding: '14px', borderRadius: '12px',
                    background: 'rgb(var(--theme-bg))',
                    border: '1px solid rgb(var(--theme-border))',
                    transition: 'all 0.2s'
                  }}>
                    {/* 术语名称 */}
                    <div style={{
                      fontSize: '14px', fontWeight: 600, color: 'rgb(var(--theme-text))',
                      marginBottom: '8px', paddingBottom: '8px',
                      borderBottom: '1px solid rgb(var(--theme-border))'
                    }}>
                      {term.term_name}
                    </div>

                    {/* 别名标签 */}
                    {term.term_alias && term.term_alias.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '8px' }}>
                        {term.term_alias.map((alias, idx) => (
                          <span key={idx} className="term-alias-tag" style={{
                            padding: '2px 8px', borderRadius: '4px', fontSize: '10px',
                            background: 'rgba(var(--theme-primary), 0.1)',
                            color: 'rgb(var(--theme-primary))', fontWeight: 500
                          }}>
                            {alias}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* 术语定义 */}
                    <div style={{
                      fontSize: '12px', color: 'rgb(var(--theme-text-secondary))',
                      lineHeight: 1.6,
                      display: '-webkit-box',
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden'
                    }}>
                      {term.term_definition}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </Drawer>

      {/* 表单 */}
      <Modal
        className="libraries-list-page-modal"
        title={<span style={{ fontSize: '16px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>📚 {editing ? '编辑术语库' : '新建术语库'}</span>}
        open={formVisible}
        onOk={handleSave}
        onCancel={() => setFormVisible(false)}
        confirmLoading={formLoading}
        okText="保存"
        cancelText="取消"
        centered
        width={440}
        zIndex={1001}
      >
        <Form form={form} layout="vertical" style={{ marginTop: '18px' }}>
          <Form.Item name="name" label={<strong style={{ color: 'rgb(var(--theme-text))' }}>名称 <span style={{ color: '#ef4444' }}>*</span></strong>} rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：电商业务术语库" maxLength={100} style={{ borderRadius: '10px' }} />
          </Form.Item>
          <Form.Item name="description" label={<strong style={{ color: 'rgb(var(--theme-text))' }}>描述</strong>}>
            <TextArea rows={3} placeholder="描述术语库的用途..." style={{ borderRadius: '10px' }} />
          </Form.Item>
          <Form.Item name="category" label={<strong style={{ color: 'rgb(var(--theme-text))' }}>行业分类</strong>}>
            <Input placeholder="例如：电商、财务" maxLength={100} style={{ borderRadius: '10px' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default LibrariesListPage
