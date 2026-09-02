'use client'

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import Link from 'next/link'
import {
  message, Button, Tag, Modal, Form, Input, Select, Space, Popconfirm, Spin, Drawer,
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, EditOutlined, ReloadOutlined, ArrowLeftOutlined,
  ImportOutlined, InfoCircleOutlined, SearchOutlined, CheckCircleOutlined, CloseCircleOutlined,
} from '@ant-design/icons'
import { ChevronLeft } from 'lucide-react'
import { useParams } from 'next/navigation'
import { useRouter } from 'next-nprogress-bar'
import {
  getLibraryDetail, createTerm, updateTerm, deleteTerm,
  getTemplateCategories, getTemplateList, importFromTemplate,
  type BusinessTermLibrary, type BusinessTerm,
} from '@/api/businessTerms'

const { TextArea } = Input

// 动态颜色
const COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#06b6d4', '#ef4444', '#ec4899', '#6366f1', '#84cc16', '#f97316']
const getColor = (str: string) => {
  let hash = 0
  for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash)
  return COLORS[Math.abs(hash) % COLORS.length]
}

// 术语详情抽屉
const TermDetailDrawer: React.FC<{
  termId: string | null
  visible: boolean
  onClose: () => void
  onEdit: (term: BusinessTerm) => void
  onDelete: (termId: string) => void
}> = ({ termId, visible, onClose, onEdit, onDelete }) => {
  const [term, setTerm] = useState<BusinessTerm | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (termId && visible) {
      setLoading(true)
      import('@/api/businessTerms').then(async ({ getTermDetail }) => {
        try {
          const res = await getTermDetail(termId)
          if (res.code === 200) setTerm(res.data)
        } catch (e) { console.error(e) }
        finally { setLoading(false) }
      })
    } else {
      setTerm(null)
    }
  }, [termId, visible])

  return (
    <Drawer
      className="library-detail-drawer term-preview-drawer library-detail-page-drawer"
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '18px' }}>📝</span>
          <span style={{ fontWeight: 600, fontSize: '15px', color: 'rgb(var(--theme-text))' }}>术语详情</span>
        </div>
      }
      placement="right"
      width={480}
      open={visible}
      onClose={onClose}
      styles={{
        body: { padding: '0', backgroundColor: 'rgb(var(--theme-bg))' },
        header: { backgroundColor: 'rgb(var(--theme-bg))', borderBottom: '1px solid rgb(var(--theme-border))', padding: '16px 24px' },
        footer: { backgroundColor: 'rgb(var(--theme-bg))', borderTop: '1px solid rgb(var(--theme-border))', padding: '12px 24px' }
      }}
      footer={
        term ? (
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <Button danger icon={<DeleteOutlined />} onClick={() => { onDelete(term.id); onClose() }}>删除</Button>
            <Space>
              <Button onClick={onClose}>关闭</Button>
              <Button type="primary" icon={<EditOutlined />} onClick={() => { onClose(); onEdit(term) }}>编辑</Button>
            </Space>
          </div>
        ) : null
      }
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px' }}><Spin size="large" /></div>
      ) : term ? (
        <div style={{ padding: '20px' }}>
          <div style={{ marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span style={{ fontSize: '18px', fontWeight: 700, color: 'rgb(var(--theme-primary))' }}>{term.term_name}</span>
              <Tag color={term.status === 'active' ? 'success' : 'default'} style={{ borderRadius: '5px' }}>
                {term.status === 'active' ? '已启用' : '已禁用'}
              </Tag>
            </div>
            {term.term_alias && term.term_alias.length > 0 && (
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                {term.term_alias.map((a, i) => <Tag key={i} style={{ borderRadius: '4px' }}>{a}</Tag>)}
              </div>
            )}
          </div>

          <div style={{ marginBottom: '14px' }}>
            <p style={{ margin: '0 0 6px', fontSize: '11px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))' }}>定义</p>
            <div className="term-definition-box" style={{ padding: '12px', borderRadius: '10px', background: 'rgb(var(--theme-bg-secondary))', fontSize: '12px', lineHeight: 1.7, whiteSpace: 'pre-wrap', color: 'rgb(var(--theme-text))' }}>
              {term.term_definition}
            </div>
          </div>

          {term.applicable_conditions && (
            <div style={{ marginBottom: '14px' }}>
              <p style={{ margin: '0 0 6px', fontSize: '11px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))' }}>适用条件</p>
              <div className="term-conditions-box" style={{ padding: '10px', borderRadius: '10px', background: 'rgb(var(--theme-bg-secondary))', fontSize: '12px', color: 'rgb(var(--theme-text))' }}>
                {term.applicable_conditions}
              </div>
            </div>
          )}

          {term.remarks && (
            <div style={{ marginBottom: '14px' }}>
              <p style={{ margin: '0 0 6px', fontSize: '11px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))' }}>备注</p>
              <div className="term-remarks-box" style={{ padding: '10px', borderRadius: '10px', background: 'rgb(var(--theme-bg-secondary))', fontSize: '12px', color: 'rgb(var(--theme-text))' }}>
                {term.remarks}
              </div>
            </div>
          )}

          <div>
            <p style={{ margin: '0 0 10px', fontSize: '11px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))' }}>关联信息</p>
            {term.related_datacards?.length ? (
              <div style={{ marginBottom: '8px' }}>
                <div style={{ fontSize: '11px', color: 'rgb(var(--theme-text-secondary))', marginBottom: '4px' }}>📋 数据卡片</div>
                <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                  {term.related_datacards.map((d, i) => <Tag key={i} color="blue" style={{ borderRadius: '4px' }}>{d.name}</Tag>)}
                </div>
              </div>
            ) : null}
            {term.related_fields?.length ? (
              <div style={{ marginBottom: '8px' }}>
                <div style={{ fontSize: '11px', color: 'rgb(var(--theme-text-secondary))', marginBottom: '4px' }}>🔗 关联字段</div>
                <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                  {term.related_fields.map((f, i) => <Tag key={i} color="purple" style={{ borderRadius: '4px' }}>{f.table}.{f.field}</Tag>)}
                </div>
              </div>
            ) : null}
            {term.related_terms?.length ? (
              <div>
                <div style={{ fontSize: '11px', color: 'rgb(var(--theme-text-secondary))', marginBottom: '4px' }}>🔄 关联术语</div>
                <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                  {term.related_terms.map((t, i) => <Tag key={i} color="green" style={{ borderRadius: '4px' }}>{t.name}</Tag>)}
                </div>
              </div>
            ) : null}
            {!term.related_datacards?.length && !term.related_fields?.length && !term.related_terms?.length && (
              <p style={{ margin: 0, fontSize: '12px', color: 'rgb(var(--theme-text-secondary))' }}>暂无关联信息</p>
            )}
          </div>
        </div>
      ) : null}
    </Drawer>
  )
}

// 术语卡片
const TermCard: React.FC<{
  term: BusinessTerm
  onView: () => void
  onEdit: () => void
  onDelete: () => void
}> = ({ term, onView, onEdit, onDelete }) => (
  <div className="term-card business-terms-card" style={{
    background: 'rgb(var(--theme-bg))', borderRadius: '14px',
    border: '1px solid rgb(var(--theme-border))', overflow: 'hidden',
    transition: 'all 0.2s', cursor: 'pointer',
  }}
       onClick={onView}
       onMouseEnter={(e) => {
         e.currentTarget.style.transform = 'translateY(-2px)'
         e.currentTarget.style.boxShadow = '0 6px 16px rgba(0,0,0,0.12)'
       }}
       onMouseLeave={(e) => {
         e.currentTarget.style.transform = 'translateY(0)'
         e.currentTarget.style.boxShadow = 'none'
       }}
  >
    <div style={{ padding: '14px 14px 12px' }}>
      {/* 第一行：名称 + 状态 + 操作按钮 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
        <span style={{ fontWeight: 600, fontSize: '15px', color: 'rgb(var(--theme-primary))', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{term.term_name}</span>
        <Tag color={term.status === 'active' ? 'success' : 'default'} style={{ borderRadius: '5px', fontSize: '11px', flexShrink: 0 }}>
          {term.status === 'active' ? '已启用' : '已禁用'}
        </Tag>
        {/* 操作按钮 */}
        <div style={{ display: 'flex', gap: '2px', flexShrink: 0 }}>
          <Button
            type="text" size="small" icon={<EditOutlined />}
            onClick={(e) => { e.stopPropagation(); onEdit() }}
            style={{ width: 26, height: 26, padding: 0, color: 'rgb(var(--theme-text-secondary))' }}
          />
          <Popconfirm
            className="term-delete-confirm"
            title={<span style={{ color: 'rgb(var(--theme-text))' }}>确认删除？</span>}
            onConfirm={(e) => { e?.stopPropagation(); onDelete() }}
            okText="确认"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button
              type="text" size="small" danger icon={<DeleteOutlined />}
              onClick={(e) => e?.stopPropagation()}
              style={{ width: 26, height: 26, padding: 0 }}
            />
          </Popconfirm>
        </div>
      </div>
      {/* 第二行：别名 */}
      {term.term_alias && term.term_alias.length > 0 && (
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '6px' }}>
          {term.term_alias.map((a, i) => (
            <Tag key={i} style={{ borderRadius: '5px', fontSize: '10px', margin: 0 }}>{a}</Tag>
          ))}
        </div>
      )}
      {/* 第三行：术语定义 */}
      <p style={{ margin: 0, fontSize: '12px', color: 'rgb(var(--theme-text-secondary))', lineHeight: 1.6, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical' }}>
        {term.term_definition}
      </p>
      {/* 第四行：关联信息 */}
      {(term.related_datacards?.length || term.related_fields?.length || term.related_terms?.length) ? (
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '8px', fontSize: '10px', color: 'rgb(var(--theme-text-secondary))' }}>
          {term.related_datacards?.length > 0 && <span>📋 {term.related_datacards.length}</span>}
          {term.related_fields?.length > 0 && <span>🔗 {term.related_fields.length}</span>}
          {term.related_terms?.length > 0 && <span>🔄 {term.related_terms.length}</span>}
        </div>
      ) : null}
    </div>
  </div>
)

// 主页面
const LibraryDetailPage: React.FC = () => {
  const params = useParams()
  const router = useRouter()
  const lng = (params?.lng as string) || 'zh-CN'
  const libId = params.id as string

  const [lib, setLib] = useState<BusinessTermLibrary | null>(null)
  const [allTerms, setAllTerms] = useState<BusinessTerm[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')

  const [formVisible, setFormVisible] = useState(false)
  const [formLoading, setFormLoading] = useState(false)
  const [editing, setEditing] = useState<BusinessTerm | null>(null)
  const [form] = Form.useForm()

  const [detailVisible, setDetailVisible] = useState(false)
  const [detailId, setDetailId] = useState<string | null>(null)

  const [tplVisible, setTplVisible] = useState(false)
  const [tplCats, setTplCats] = useState<any[]>([])
  const [tplList, setTplList] = useState<any[]>([])
  const [selectedTpl, setSelectedTpl] = useState<string[]>([])
  const [tplLoading, setTplLoading] = useState(false)
  const [importing, setImporting] = useState(false)

  const filtered = useMemo(() => {
    return allTerms.filter(t => {
      if (search) {
        const k = search.toLowerCase()
        if (!t.term_name.toLowerCase().includes(k) &&
          !t.term_alias?.some(a => a.toLowerCase().includes(k)) &&
          !t.term_definition.toLowerCase().includes(k)) return false
      }
      if (status && t.status !== status) return false
      return true
    })
  }, [allTerms, search, status])

  const stats = useMemo(() => ({
    total: allTerms.length,
    active: allTerms.filter(t => t.status === 'active').length,
  }), [allTerms])

  const fetchDetail = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getLibraryDetail(libId, { terms_page: 1, terms_page_size: 500 })
      if (res.code === 200) {
        setLib(res.data)
        setAllTerms(res.data.terms || [])
      }
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [libId])

  useEffect(() => { fetchDetail() }, [fetchDetail])

  const openCreate = () => { setEditing(null); form.resetFields(); setFormVisible(true) }
  const openEdit = (term: BusinessTerm) => {
    setEditing(term)
    form.setFieldsValue({
      term_name: term.term_name,
      term_alias: term.term_alias || [],
      term_definition: term.term_definition,
      applicable_conditions: term.applicable_conditions,
      remarks: term.remarks,
      status: term.status,
    })
    setFormVisible(true)
  }

  const handleSave = async () => {
    try {
      const v = await form.validateFields()
      setFormLoading(true)
      const data = {
        library_id: libId,
        term_name: v.term_name,
        term_alias: v.term_alias || [],
        term_definition: v.term_definition,
        applicable_conditions: v.applicable_conditions,
        remarks: v.remarks,
        status: v.status || 'active',
      }
      const res = editing ? await updateTerm(editing.id, data) : await createTerm(data)
      if (res.code === 200) {
        message.success(res.msg)
        setFormVisible(false)
        fetchDetail()
      } else {
        message.error(res.msg || '操作失败')
      }
    } catch (e) { console.error(e); message.error('保存失败，请重试') }
    finally { setFormLoading(false) }
  }

  const handleDelete = async (id: string) => {
    const res = await deleteTerm(id)
    if (res.code === 200) { message.success('删除成功'); fetchDetail() }
  }

  const openTpl = async () => {
    setTplVisible(true)
    setTplLoading(true)
    setSelectedTpl([])
    try {
      const [cr, lr] = await Promise.all([getTemplateCategories(), getTemplateList()])
      if (cr.code === 200) setTplCats(cr.data.categories || [])
      if (lr.code === 200) setTplList(lr.data.items || [])
    } catch (e) { console.error(e) }
    finally { setTplLoading(false) }
  }

  const handleImport = async () => {
    if (selectedTpl.length === 0) { message.warning('请选择模板'); return }
    setImporting(true)
    try {
      const res = await importFromTemplate({ library_id: libId, template_ids: selectedTpl })
      if (res.code === 200) { message.success(res.data.message); setTplVisible(false); fetchDetail() }
    } catch (e) { console.error(e) }
    finally { setImporting(false) }
  }

  return (
    <div className="space-y-6 library-detail-page">
      {/* 返回 + 标题区 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '4px' }}>
        <Link
          href={`/${lng}/business-terms`}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: '4px',
            color: 'rgb(var(--theme-text-secondary))', textDecoration: 'none', fontSize: '14px',
            transition: 'all 0.2s'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = 'rgb(var(--theme-primary))'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = 'rgb(var(--theme-text-secondary))'
          }}
        >
          <ChevronLeft size={16} />
          返回
        </Link>
      </div>

      {/* 标题区 */}
      <header>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ width: '48px', height: '48px', borderRadius: '14px', background: 'rgba(var(--theme-bg-secondary))', animation: 'pulse 1.5s ease-in-out infinite' }} />
            <div style={{ height: '28px', width: '200px', background: 'rgba(var(--theme-bg-secondary))', borderRadius: '6px', animation: 'pulse 1.5s ease-in-out infinite' }} />
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '40px', height: '40px', borderRadius: '12px', flexShrink: 0,
              background: `linear-gradient(135deg, ${getColor(lib?.category || '默认')}20, ${getColor(lib?.category || '默认')}10)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '20px'
            }}>📚</div>
            <h1 style={{ margin: 0, fontSize: '20px', fontWeight: 700, color: 'rgb(var(--theme-text))', letterSpacing: '-0.02em', flex: 1, minWidth: 0 }}>
              {lib?.name}
            </h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
              {lib?.category && (
                <Tag style={{ borderRadius: '6px', fontSize: '12px', background: `${getColor(lib.category)}15`, border: 'none', color: getColor(lib.category) }}>
                  {lib.category}
                </Tag>
              )}
              <Tag
                color={lib?.status === 'active' ? 'success' : 'default'}
                icon={lib?.status === 'active' ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                style={{ borderRadius: '6px', fontSize: '12px' }}
              >
                {lib?.status === 'active' ? '已启用' : '已禁用'}
              </Tag>
              <span style={{ fontSize: '14px', color: 'rgb(var(--theme-text-secondary))' }}>
                共 <span style={{ fontWeight: 600, color: 'rgb(var(--theme-text))' }}>{lib?.term_count}</span> 个术语
              </span>
            </div>
          </div>
        )}
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
                <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: 'rgba(var(--theme-bg-secondary))', animation: 'pulse 1.5s ease-in-out infinite' }} />
                <div>
                  <div style={{ height: '10px', width: '50px', borderRadius: '4px', background: 'rgba(var(--theme-bg-secondary))', marginBottom: '6px', animation: 'pulse 1.5s ease-in-out infinite' }} />
                  <div style={{ height: '20px', width: '36px', borderRadius: '4px', background: 'rgba(var(--theme-bg-secondary))', animation: 'pulse 1.5s ease-in-out infinite' }} />
                </div>
              </div>
            </div>
          ))
        ) : [
          { label: '术语总数', value: stats.total, icon: '📝', color: 'rgb(var(--theme-primary))', bg: 'rgba(var(--theme-primary), 0.08)' },
          { label: '已启用', value: stats.active, icon: <CheckCircleOutlined style={{ color: '#4ade80', fontSize: '18px' }} />, color: '#4ade80', bg: 'rgba(34, 197, 94, 0.08)', isGreen: true },
          { label: '已禁用', value: stats.total - stats.active, icon: '🚫', color: 'rgb(var(--theme-text-muted))', bg: 'rgba(var(--theme-text-muted), 0.08)' },
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
                background: `radial-gradient(circle, ${s.color === 'rgb(var(--theme-text-secondary))' ? '#64748b' : s.color}, transparent 70%)`,
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
      <div className="business-terms-card library-detail-page" style={{
        display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap',
        padding: '16px 20px', borderRadius: '16px',
        background: 'rgb(var(--theme-bg))', border: '1px solid rgb(var(--theme-border))'
      }}>
        <Input
          className="search-input library-detail-search-input"
          placeholder="搜索术语名称、别名或定义..."
          prefix={<SearchOutlined style={{ color: 'rgb(var(--theme-text-muted))' }} />}
          value={search}
          onChange={e => setSearch(e.target.value)}
          allowClear
          style={{ width: 260, borderRadius: '10px' }}
        />
        <Select
          value={status}
          onChange={v => setStatus(v)}
          allowClear
          style={{ width: 120, borderRadius: '10px' }}
          options={[
            { label: '全部', value: '' },
            { label: '已启用', value: 'active' },
            { label: '已禁用', value: 'inactive' },
          ]}
        />
        <span style={{ fontSize: '13px', color: 'rgb(var(--theme-text-secondary))', marginLeft: 'auto' }}>
          共 {filtered.length} 个术语{filtered.length !== allTerms.length && `（筛选自 ${allTerms.length}）`}
        </span>
        <div style={{ display: 'flex', gap: '10px' }}>
          <Button icon={<ReloadOutlined />} onClick={fetchDetail} loading={loading} style={{ borderRadius: '10px' }}>刷新</Button>
          <Button icon={<ImportOutlined />} onClick={openTpl} style={{ borderRadius: '10px' }}>从模板导入</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate} style={{ borderRadius: '10px' }}>新建术语</Button>
        </div>
      </div>

      {/* 列表 */}
      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '12px' }}>
          {[1, 2, 3, 4, 5, 6].map(i => (
            <div key={i} className="term-card business-terms-card" style={{ padding: '14px', borderRadius: '14px', background: 'rgb(var(--theme-bg))', border: '1px solid rgb(var(--theme-border))' }}>
              <div style={{ height: '14px', width: '60%', borderRadius: '4px', background: 'rgba(var(--theme-bg-secondary))', marginBottom: '8px' }} />
              <div style={{ height: '10px', width: '90%', borderRadius: '4px', background: 'rgba(var(--theme-bg-secondary))', marginBottom: '6px' }} />
              <div style={{ height: '10px', width: '70%', borderRadius: '4px', background: 'rgba(var(--theme-bg-secondary))' }} />
            </div>
          ))}
        </div>
      ) : allTerms.length === 0 ? (
        <div className="business-terms-card" style={{ textAlign: 'center', padding: '60px 20px', borderRadius: '14px', background: 'rgb(var(--theme-bg))', border: '2px dashed rgb(var(--theme-border))' }}>
          <div style={{ width: '60px', height: '60px', borderRadius: '50%', background: 'rgba(var(--theme-primary), 0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px', fontSize: '28px' }}>📝</div>
          <h3 style={{ margin: '0 0 6px', color: 'rgb(var(--theme-text))' }}>该术语库暂无术语</h3>
          <p style={{ margin: '0 0 16px', color: 'rgb(var(--theme-text-secondary))', fontSize: '13px' }}>可以从模板导入，或手动新建术语</p>
          <Space>
            <Button icon={<ImportOutlined />} onClick={openTpl}>从模板导入</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建术语</Button>
          </Space>
        </div>
      ) : filtered.length === 0 ? (
        <div className="business-terms-card" style={{ textAlign: 'center', padding: '60px', borderRadius: '14px', background: 'rgb(var(--theme-bg))', border: '1px solid rgb(var(--theme-border))' }}>
          <p style={{ margin: '0 0 14px', color: 'rgb(var(--theme-text-secondary))' }}>没有匹配的术语</p>
          <Button onClick={() => { setSearch(''); setStatus('') }} style={{ borderRadius: '10px' }}>清除筛选</Button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '12px' }}>
          {filtered.map(term => (
            <TermCard
              key={term.id}
              term={term}
              onView={() => { setDetailId(term.id); setDetailVisible(true) }}
              onEdit={() => openEdit(term)}
              onDelete={() => handleDelete(term.id)}
            />
          ))}
        </div>
      )}

      {/* 术语详情 */}
      <TermDetailDrawer
        termId={detailId}
        visible={detailVisible}
        onClose={() => setDetailVisible(false)}
        onEdit={openEdit}
        onDelete={handleDelete}
      />

      {/* 术语表单 */}
      <Modal
        className="library-detail-page-modal term-form-modal"
        title={<span style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>📝 {editing ? '编辑术语' : '新建术语'}</span>}
        open={formVisible}
        onOk={handleSave}
        onCancel={() => setFormVisible(false)}
        confirmLoading={formLoading}
        okText="保存"
        cancelText="取消"
        centered
        width={540}
      >
        <Form form={form} layout="vertical" style={{ marginTop: '14px' }}>
          <Form.Item name="term_name" label={<strong style={{ color: 'rgb(var(--theme-text))' }}>术语名称 <span style={{ color: '#ef4444' }}>*</span></strong>} rules={[{ required: true, message: '请输入术语名称' }]}>
            <Input placeholder="例如：GMV、客单价" maxLength={255} style={{ borderRadius: '10px' }} />
          </Form.Item>
          <Form.Item name="term_alias" label={<strong style={{ color: 'rgb(var(--theme-text))' }}>术语别名</strong>} extra={<span style={{ color: 'rgb(var(--theme-text-muted))' }}>输入后按回车添加</span>}>
            <Select mode="tags" placeholder="例如：成交金额、商品成交总额" style={{ width: '100%', borderRadius: '10px' }} tokenSeparators={[',', '，']} />
          </Form.Item>
          <Form.Item name="term_definition" label={<strong style={{ color: 'rgb(var(--theme-text))' }}>术语定义 <span style={{ color: '#ef4444' }}>*</span></strong>} rules={[{ required: true, message: '请输入术语定义' }]} extra={<span style={{ color: 'rgb(var(--theme-text-muted))' }}>详细描述该术语的业务含义和计算口径</span>}>
            <TextArea rows={3} placeholder="例如：GMV（商品成交总额=已完成订单金额-已退款金额，不含未支付订单" style={{ borderRadius: '10px' }} />
          </Form.Item>
          <Form.Item name="applicable_conditions" label={<strong style={{ color: 'rgb(var(--theme-text))' }}>适用条件</strong>}>
            <Input placeholder="例如：仅统计已完成的订单" style={{ borderRadius: '10px' }} />
          </Form.Item>
          <Form.Item name="remarks" label={<strong style={{ color: 'rgb(var(--theme-text))' }}>备注</strong>}>
            <TextArea rows={2} placeholder="其他补充说明（可选）" style={{ borderRadius: '10px' }} />
          </Form.Item>
          {editing && (
            <Form.Item name="status" label={<strong style={{ color: 'rgb(var(--theme-text))' }}>状态</strong>}>
              <Select
                style={{ width: '100%' }}
                options={[
                  { label: '启用', value: 'active' },
                  { label: '禁用', value: 'inactive' },
                ]}
              />
            </Form.Item>
          )}
        </Form>
      </Modal>

      {/* 模板导入 */}
      <Modal
        className="library-detail-page-import-modal"
        title={<span style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>📦 从模板导入术语</span>}
        open={tplVisible}
        onOk={handleImport}
        onCancel={() => setTplVisible(false)}
        confirmLoading={importing}
        okText={`导入 (${selectedTpl.length})`}
        cancelText="取消"
        centered
        width={560}
      >
        <div style={{ marginTop: '14px' }}>
          <div className="term-definition-box" style={{ padding: '10px', borderRadius: '10px', background: 'rgb(var(--theme-bg-secondary))', marginBottom: '14px', fontSize: '12px', color: 'rgb(var(--theme-text-secondary))' }}>
            <InfoCircleOutlined /> 选择模板导入到「{lib?.name}」，导入后可自行修改
          </div>
          {tplLoading ? <div style={{ textAlign: 'center', padding: '40px' }}><Spin /></div> : (
            <div style={{ maxHeight: '380px', overflowY: 'auto' }}>
              {tplCats.map(cat => (
                <div key={cat.category} style={{ marginBottom: '14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <Tag style={{ borderRadius: '5px', fontSize: '11px', background: `${getColor(cat.category)}15`, border: 'none', color: getColor(cat.category) }}>{cat.category}</Tag>
                    <Button type="link" size="small" onClick={() => {
                      const ids = tplList.filter((t: any) => t.category === cat.category).map((t: any) => t.id)
                      setSelectedTpl(prev => ids.every((id: string) => prev.includes(id)) ? prev.filter(id => !ids.includes(id)) : [...new Set([...prev, ...ids])])
                    }}>全选</Button>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                    {tplList.filter((t: any) => t.category === cat.category).map((t: any) => (
                      <Tag
                        key={t.id}
                        onClick={() => setSelectedTpl(prev => prev.includes(t.id) ? prev.filter(x => x !== t.id) : [...prev, t.id])}
                        className={selectedTpl.includes(t.id) ? 'term-template-tag-selected' : 'term-template-tag'}
                        style={{ cursor: 'pointer', borderRadius: '5px', padding: '3px 8px', fontSize: '11px', border: selectedTpl.includes(t.id) ? '1px solid rgb(var(--theme-primary))' : '1px solid rgb(var(--theme-border))', background: selectedTpl.includes(t.id) ? 'rgba(var(--theme-primary), 0.2)' : 'rgb(var(--theme-bg-secondary))', color: selectedTpl.includes(t.id) ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text))' }}>
                        {t.term_name}
                      </Tag>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </Modal>
    </div>
  )
}

export default LibraryDetailPage
