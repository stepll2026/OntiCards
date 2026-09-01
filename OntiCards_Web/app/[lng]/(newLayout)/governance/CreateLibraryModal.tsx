'use client'

import React, { useState, useEffect } from 'react'
import { Modal, Input, Select, message } from 'antd'
import { Loader2, Database } from 'lucide-react'
import {
  createGovernanceLibrary,
  updateGovernanceLibrary,
  GovernanceLibrary,
} from '@/api/governance'
import { getUserDataSources, DataSourceItem } from '@/api/datasource'

export interface CreateLibraryModalProps {
  visible: boolean
  editingLibrary?: GovernanceLibrary | null
  onClose: () => void
  onSuccess?: (newLibraryId?: string) => void
  initialDatasourceId?: string
  title?: string
  onGoToDatasourceManagement?: () => void
}

export function CreateLibraryModal({
  visible,
  editingLibrary,
  onClose,
  onSuccess,
  initialDatasourceId,
  title,
  onGoToDatasourceManagement,
}: CreateLibraryModalProps) {
  const [loading, setLoading] = useState(false)
  const [dataSources, setDataSources] = useState<DataSourceItem[]>([])
  const [dataSourcesLoading, setDataSourcesLoading] = useState(true)
  const [form, setForm] = useState({
    name: '',
    description: '',
    datasource_id: '',
  })

  useEffect(() => {
    if (visible) {
      fetchDataSources()
    }
  }, [visible])

  useEffect(() => {
    if (visible) {
      if (editingLibrary) {
        setForm({
          name: editingLibrary.name,
          description: editingLibrary.description || '',
          datasource_id: editingLibrary.datasource_id || '',
        })
      } else {
        setForm({
          name: '',
          description: '',
          datasource_id: initialDatasourceId || '',
        })
      }
    }
  }, [visible, editingLibrary, initialDatasourceId])

  const fetchDataSources = async () => {
    setDataSourcesLoading(true)
    try {
      const res = await getUserDataSources({ page_size: 100 })
      if (res.code === 200 && res.data) {
        setDataSources(res.data.items || [])
        if (!editingLibrary && !initialDatasourceId && !form.datasource_id) {
          const firstAvailable = (res.data.items || []).find(
            (item: DataSourceItem) => item.status === 'available'
          )
          if (firstAvailable) {
            setForm(prev => ({ ...prev, datasource_id: firstAvailable.id }))
          }
        }
      }
    } catch {
      message.error('获取数据源失败')
    } finally {
      setDataSourcesLoading(false)
    }
  }

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      message.warning('请输入规则库名称')
      return
    }

    const datasourceId =
      form.datasource_id ||
      initialDatasourceId ||
      dataSources.find((item) => item.status === 'available')?.id

    if (!editingLibrary && !datasourceId) {
      message.warning('请选择绑定的数据源')
      return
    }

    setLoading(true)
    try {
      const res = editingLibrary
        ? await updateGovernanceLibrary(editingLibrary.id, form)
        : await createGovernanceLibrary({
            ...form,
            datasource_id: datasourceId as string,
          })

      if (res.code === 200) {
        message.success(editingLibrary ? '更新成功' : '创建成功')
        onSuccess?.(res.data?.id)
        onClose()
        setForm({ name: '', description: '', datasource_id: '' })
      } else {
        message.error(res.msg || '操作失败')
      }
    } catch {
      message.error('操作失败')
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => {
    onClose()
    setForm({ name: '', description: '', datasource_id: '' })
  }

  const availableDataSources = dataSources.filter((item) => item.status === 'available')
  const hasAvailableDataSources = availableDataSources.length > 0
  const shouldShowCreateForm = editingLibrary || !dataSourcesLoading
  const showEmptyDataSourceState = !editingLibrary && !dataSourcesLoading && !hasAvailableDataSources

  return (
    <Modal
      title={
        <span style={{ fontWeight: 600, fontSize: 16 }}>
          {title || (editingLibrary ? '编辑规则库' : '创建规则库')}
        </span>
      }
      open={visible}
      onCancel={handleClose}
      footer={null}
      width={420}
      centered
      destroyOnClose
      className="create-library-modal-dark"
      styles={{
        body: { padding: '16px 20px 20px' },
        header: { borderBottom: 'none', padding: '16px 20px 0', marginBottom: 0 },
      }}
    >
      <div style={{ minHeight: 220, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {!shouldShowCreateForm ? (
          <Loader2 style={{ width: 34, height: 34, color: 'rgb(var(--theme-primary))', animation: 'spin 1s linear infinite' }} />
        ) : showEmptyDataSourceState ? (
          <div style={{ textAlign: 'center', padding: '12px 4px', width: '100%' }}>
            <Database style={{ width: 44, height: 44, color: 'rgb(var(--theme-text-muted))', opacity: 0.45 }} />
            <div style={{ marginTop: 12, fontSize: 15, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>暂无可绑定的数据源</div>
            <div style={{ marginTop: 6, fontSize: 13, lineHeight: 1.7, color: 'rgb(var(--theme-text-secondary))' }}>
              请先创建一个可用的数据源，再继续创建规则库。
            </div>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 18 }}>
              <button
                onClick={handleClose}
                style={{
                  padding: '8px 16px',
                  borderRadius: 8,
                  fontSize: 14,
                  fontWeight: 500,
                  color: 'rgb(var(--theme-text))',
                  backgroundColor: 'transparent',
                  border: '1px solid rgb(var(--theme-border))',
                  cursor: 'pointer',
                }}
              >
                取消
              </button>
              <button
                onClick={onGoToDatasourceManagement}
                style={{
                  padding: '8px 16px',
                  borderRadius: 8,
                  fontSize: 14,
                  fontWeight: 500,
                  color: 'white',
                  backgroundColor: 'rgb(var(--theme-primary))',
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                去添加数据源
              </button>
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, width: '100%' }}>
            {!editingLibrary && (
              <div>
                <label
                  style={{
                    fontSize: 14,
                    fontWeight: 500,
                    color: 'rgb(var(--theme-text))',
                    marginBottom: 8,
                    display: 'block',
                  }}
                >
                  绑定数据源 *
                </label>
                <Select
                  value={form.datasource_id || undefined}
                  onChange={(value) => setForm({ ...form, datasource_id: value })}
                  placeholder="请选择数据源"
                  loading={dataSourcesLoading}
                  options={availableDataSources.map((item) => ({
                    value: item.id,
                    label: item.connect_name || item.database_name || item.id,
                  }))}
                  style={{ width: '100%' }}
                />
              </div>
            )}
            <div>
              <label
                style={{
                  fontSize: 14,
                  fontWeight: 500,
                  color: 'rgb(var(--theme-text))',
                  marginBottom: 8,
                  display: 'block',
                }}
              >
                规则库名称 *
              </label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="请输入规则库名称"
              />
            </div>
            <div>
              <label
                style={{
                  fontSize: 14,
                  fontWeight: 500,
                  color: 'rgb(var(--theme-text))',
                  marginBottom: 8,
                  display: 'block',
                }}
              >
                描述
              </label>
              <Input.TextArea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="请输入规则库描述（可选）"
                rows={3}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
              <button
                onClick={handleClose}
                style={{
                  padding: '8px 16px',
                  borderRadius: 8,
                  fontSize: 14,
                  fontWeight: 500,
                  color: 'rgb(var(--theme-text))',
                  backgroundColor: 'transparent',
                  border: '1px solid rgb(var(--theme-border))',
                  cursor: 'pointer',
                }}
              >
                取消
              </button>
              <button
                onClick={handleSubmit}
                disabled={loading}
                style={{
                  padding: '8px 16px',
                  borderRadius: 8,
                  fontSize: 14,
                  fontWeight: 500,
                  color: 'white',
                  backgroundColor: 'rgb(var(--theme-primary))',
                  border: 'none',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  opacity: loading ? 0.6 : 1,
                }}
              >
                {loading ? '提交中...' : editingLibrary ? '保存' : '创建'}
              </button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}
