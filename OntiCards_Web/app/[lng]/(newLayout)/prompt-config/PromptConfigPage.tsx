'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  FileText,
  Plus,
  Search,
  Loader2,
  Edit3,
  Trash2,
  X,
  AlertCircle,
  RefreshCw,
  Filter,
  Eye,
  Edit2,
} from 'lucide-react';
import {
  getPromptList,
  getPromptDetail,
  createPrompt,
  updatePrompt,
  deletePrompt,
  syncPrompt,
  getCategories,
  PromptListItem,
  PromptConfig,
  CategoryInfo,
} from '@/api/promptConfig';
import { Modal, Select, message } from 'antd';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import gfm from 'remark-gfm';
import math from 'remark-math';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';
import 'github-markdown-css/github-markdown.css';

const PromptConfigPage = () => {
  const [loading, setLoading] = useState(false);
  const [promptList, setPromptList] = useState<PromptListItem[]>([]);
  const [allPromptList, setAllPromptList] = useState<PromptListItem[]>([]);
  const [pagination, setPagination] = useState({ page: 1, page_size: 20, total: 0, total_pages: 0 });
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<string>('');
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [dbTypes, setDbTypes] = useState<string[]>([]);

  const formatDateTime = (dateStr?: string) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editModalMode, setEditModalMode] = useState<'create' | 'edit'>('create');
  const [editingPrompt, setEditingPrompt] = useState<PromptConfig | null>(null);
  const [editForm, setEditForm] = useState({ file_name: '', prompt: '', description: '' });
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [isPreviewMode, setIsPreviewMode] = useState(false);

  const [deleteModalVisible, setDeleteModalVisible] = useState(false);
  const [deletingPrompt, setDeletingPrompt] = useState<PromptListItem | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const [syncLoading, setSyncLoading] = useState(false);

  const fetchCategories = useCallback(async () => {
    try {
      const res = await getCategories();
      if (res.code === 200 && res.data) {
        setCategories(res.data.categories || []);
        setDbTypes(res.data.db_types || []);
      }
    } catch (e) {
      console.error('获取分类失败', e);
    }
  }, []);

  const fetchPromptList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getPromptList({
        page: 1,
        page_size: 1000,
        search: undefined,
        category: undefined,
        include_prompt: false,
      });
      if (res.code === 200 && res.data) {
        setAllPromptList(res.data.items || []);
      }
    } catch (e) {
      console.error('获取提示词列表失败', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCategories();
    fetchPromptList();
  }, [fetchCategories, fetchPromptList]);

  useEffect(() => {
    let filtered = [...allPromptList];

    if (search) {
      const searchLower = search.toLowerCase();
      filtered = filtered.filter(item =>
        item.file_name.toLowerCase().includes(searchLower) ||
        item.description?.toLowerCase().includes(searchLower) ||
        item.category?.toLowerCase().includes(searchLower)
      );
    }

    if (category) {
      filtered = filtered.filter(item => item.category === category);
    }

    const total = filtered.length;
    const page_size = pagination.page_size;
    const total_pages = Math.ceil(total / page_size);
    const start = (pagination.page - 1) * page_size;
    const end = start + page_size;
    const items = filtered.slice(start, end);

    setPromptList(items);
    setPagination(prev => ({ ...prev, total, total_pages }));
  }, [allPromptList, search, category, pagination.page, pagination.page_size]);

  const handleSearch = (value: string) => {
    setSearch(value);
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const handleCategoryChange = (value: string) => {
    setCategory(value);
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const handlePageChange = (page: number) => {
    setPagination(prev => ({ ...prev, page }));
  };

  const openCreateModal = () => {
    setEditModalMode('create');
    setEditingPrompt(null);
    setEditForm({ file_name: '', prompt: '', description: '' });
    setEditError(null);
    setIsPreviewMode(false);
    setEditModalVisible(true);
  };

  const openEditModal = async (item: PromptListItem) => {
    setEditLoading(true);
    setEditError(null);
    setIsPreviewMode(false);
    try {
      const res = await getPromptDetail(item.id);
      if (res.code === 200 && res.data) {
        setEditModalMode('edit');
        setEditingPrompt(res.data);
        setEditForm({
          file_name: res.data.file_name,
          prompt: res.data.prompt || '',
          description: res.data.description || '',
        });
        setEditModalVisible(true);
      }
    } catch (e) {
      console.error('获取详情失败', e);
    } finally {
      setEditLoading(false);
    }
  };

  const handleEditSubmit = async () => {
    if (!editForm.file_name && editModalMode === 'create') {
      setEditError('文件名不能为空');
      return;
    }
    if (!editForm.prompt) {
      setEditError('提示词内容不能为空');
      return;
    }

    setEditLoading(true);
    setEditError(null);

    try {
      if (editModalMode === 'create') {
        const res = await createPrompt({
          file_name: editForm.file_name,
          prompt: editForm.prompt,
          description: editForm.description,
        });
        if (res.code === 200) {
          message.success('创建成功');
          setEditModalVisible(false);
          fetchPromptList();
          fetchCategories();
        } else {
          setEditError(res.msg || '创建失败');
        }
      } else if (editingPrompt) {
        const res = await updatePrompt(editingPrompt.id, {
          prompt: editForm.prompt,
          description: editForm.description,
        });
        if (res.code === 200) {
          message.success('更新成功');
          setEditModalVisible(false);
          fetchPromptList();
        } else {
          setEditError(res.msg || '更新失败');
        }
      }
    } catch (e: any) {
      setEditError(e?.message || '操作失败');
    } finally {
      setEditLoading(false);
    }
  };

  const openDeleteModal = (item: PromptListItem) => {
    setDeletingPrompt(item);
    setDeleteModalVisible(true);
  };

  const handleDelete = async () => {
    if (!deletingPrompt) return;
    setDeleteLoading(true);
    try {
      const res = await deletePrompt(deletingPrompt.id);
      if (res.code === 200) {
        message.success('删除成功');
        setDeleteModalVisible(false);
        setDeletingPrompt(null);
        fetchPromptList();
        fetchCategories();
      }
    } catch (e) {
      console.error('删除失败', e);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleSync = async (fileName?: string) => {
    setSyncLoading(true);
    try {
      const res = await syncPrompt(fileName ? { file_name: fileName } : {});
      if (res.code === 200) {
        message.success('同步成功');
        fetchPromptList();
        fetchCategories();
      }
    } catch (e) {
      console.error('同步失败', e);
    } finally {
      setSyncLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      <header>
        <h1 style={{ fontSize: '24px', fontWeight: 600, marginBottom: '4px', color: 'rgb(var(--theme-text))' }}>提示词配置</h1>
        <p style={{ fontSize: '14px', color: 'rgb(var(--theme-text-muted))' }}>管理提示词模板的创建、编辑和删除</p>
      </header>

      {/* 工具栏 */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: '400px' }}>
          <div style={{ position: 'relative', flex: 1, maxWidth: '400px' }}>
            <Search style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', width: '16px', height: '16px', color: 'rgb(var(--theme-text-muted))' }} />
            <input
              type="text"
              placeholder="搜索文件名或描述..."
              value={search}
              onChange={(e) => handleSearch(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 12px 10px 40px',
                fontSize: '14px',
                border: '1px solid rgb(var(--theme-border))',
                borderRadius: '10px',
                outline: 'none',
                background: 'rgb(var(--theme-bg))',
                color: 'rgb(var(--theme-text))',
              }}
            />
          </div>

          <Select
            placeholder="选择分类"
            allowClear
            style={{ width: '160px' }}
            value={category || undefined}
            onChange={handleCategoryChange}
            options={categories.map(c => ({ label: `${c.name} (${c.count})`, value: c.name }))}
          />

          <button
            onClick={() => fetchPromptList()}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '10px 16px',
              fontSize: '14px',
              border: '1px solid rgb(var(--theme-border))',
              borderRadius: '10px',
              background: 'rgb(var(--theme-bg))',
              color: 'rgb(var(--theme-text-secondary))',
              cursor: 'pointer',
            }}
          >
            <RefreshCw style={{ width: '14px', height: '14px' }} />
            刷新
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={() => handleSync()}
            disabled={syncLoading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '10px 16px',
              fontSize: '14px',
              border: '1px solid rgb(var(--theme-border))',
              borderRadius: '10px',
              background: 'rgb(var(--theme-bg))',
              color: 'rgb(var(--theme-text-secondary))',
              cursor: syncLoading ? 'not-allowed' : 'pointer',
              opacity: syncLoading ? 0.6 : 1,
            }}
          >
            {syncLoading ? <Loader2 style={{ width: '14px', height: '14px', animation: 'spin 1s linear infinite' }} /> : <RefreshCw style={{ width: '14px', height: '14px' }} />}
            同步文件
          </button>

          {/* <button */}
          {/*   onClick={openCreateModal} */}
          {/*   style={{ */}
          {/*     display: 'flex', */}
          {/*     alignItems: 'center', */}
          {/*     gap: '6px', */}
          {/*     padding: '10px 16px', */}
          {/*     fontSize: '14px', */}
          {/*     fontWeight: 500, */}
          {/*     border: 'none', */}
          {/*     borderRadius: '10px', */}
          {/*     background: 'rgb(var(--theme-primary))', */}
          {/*     color: '#fff', */}
          {/*     cursor: 'pointer', */}
          {/*   }} */}
          {/* > */}
          {/*   <Plus style={{ width: '14px', height: '14px' }} /> */}
          {/*   新建提示词 */}
          {/* </button> */}
        </div>
      </div>

      {/* 提示信息 */}
      {category && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '12px 16px', background: 'rgba(var(--theme-primary), 0.1)', borderRadius: '10px', border: '1px solid rgba(var(--theme-primary), 0.2)' }}>
          <Filter style={{ width: '14px', height: '14px', color: 'rgb(var(--theme-primary))' }} />
          <span style={{ fontSize: '14px', color: 'rgb(var(--theme-text-secondary))' }}>
            当前筛选: <strong style={{ color: 'rgb(var(--theme-primary))' }}>{category}</strong>
          </span>
          <button
            onClick={() => handleCategoryChange('')}
            style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', padding: '4px' }}
          >
            <X style={{ width: '14px', height: '14px', color: 'rgb(var(--theme-text-muted))' }} />
          </button>
        </div>
      )}

      {/* 列表 */}
      <div style={{ background: 'rgb(var(--theme-bg))', borderRadius: '16px', border: '1px solid rgb(var(--theme-border))', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '80px' }}>
            <Loader2 style={{ width: '24px', height: '24px', animation: 'spin 1s linear infinite', color: 'rgb(var(--theme-primary))' }} />
          </div>
        ) : promptList.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '80px', textAlign: 'center' }}>
            <FileText style={{ width: '48px', height: '48px', color: 'rgb(var(--theme-text-muted))', marginBottom: '16px', opacity: 0.5 }} />
            <h4 style={{ fontSize: '18px', fontWeight: 600, color: 'rgb(var(--theme-text))', marginBottom: '8px' }}>暂无提示词</h4>
            <p style={{ fontSize: '14px', color: 'rgb(var(--theme-text-muted))', marginBottom: '24px' }}>点击上方"新建提示词"开始创建</p>
          </div>
        ) : (
          <>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'rgb(var(--theme-bg-secondary))' }}>
                  <th style={{ padding: '14px 16px', textAlign: 'left', fontSize: '13px', fontWeight: 500, color: 'rgb(var(--theme-text-secondary))', borderBottom: '1px solid rgb(var(--theme-border))' }}>文件名</th>
                  <th style={{ padding: '14px 16px', textAlign: 'left', fontSize: '13px', fontWeight: 500, color: 'rgb(var(--theme-text-secondary))', borderBottom: '1px solid rgb(var(--theme-border))' }}>描述</th>
                  <th style={{ padding: '14px 16px', textAlign: 'left', fontSize: '13px', fontWeight: 500, color: 'rgb(var(--theme-text-secondary))', borderBottom: '1px solid rgb(var(--theme-border))' }}>分类</th>
                  <th style={{ padding: '14px 16px', textAlign: 'left', fontSize: '13px', fontWeight: 500, color: 'rgb(var(--theme-text-secondary))', borderBottom: '1px solid rgb(var(--theme-border))' }}>数据库类型</th>
                  <th style={{ padding: '14px 16px', textAlign: 'left', fontSize: '13px', fontWeight: 500, color: 'rgb(var(--theme-text-secondary))', borderBottom: '1px solid rgb(var(--theme-border))' }}>创建时间</th>
                  <th style={{ padding: '14px 16px', textAlign: 'left', fontSize: '13px', fontWeight: 500, color: 'rgb(var(--theme-text-secondary))', borderBottom: '1px solid rgb(var(--theme-border))' }}>更新时间</th>
                  <th style={{ padding: '14px 16px', textAlign: 'right', fontSize: '13px', fontWeight: 500, color: 'rgb(var(--theme-text-secondary))', borderBottom: '1px solid rgb(var(--theme-border))' }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {promptList.map((item) => (
                  <tr key={item.id} style={{ borderBottom: '1px solid rgb(var(--theme-border))' }}>
                    <td style={{ padding: '14px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <FileText style={{ width: '16px', height: '16px', color: 'rgb(var(--theme-primary))', flexShrink: 0 }} />
                        <span style={{ fontSize: '14px', color: 'rgb(var(--theme-text))', fontWeight: 500 }}>{item.file_name}</span>
                      </div>
                      {item.prompt_length && (
                        <span style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))', marginLeft: '24px' }}>
                          {item.prompt_length.toLocaleString()} 字符
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <span style={{ fontSize: '14px', color: 'rgb(var(--theme-text-secondary))' }}>
                        {item.description || '-'}
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <span style={{ fontSize: '13px', color: 'rgb(var(--theme-text-secondary))', background: 'rgb(var(--theme-bg-secondary))', padding: '4px 10px', borderRadius: '6px' }}>
                        {item.category || '-'}
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <span style={{ fontSize: '13px', color: 'rgb(var(--theme-text-secondary))' }}>
                        {item.db_type || '-'}
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <span style={{ fontSize: '13px', color: 'rgb(var(--theme-text-muted))' }}>
                        {formatDateTime(item.created_at)}
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <span style={{ fontSize: '13px', color: 'rgb(var(--theme-text-muted))' }}>
                        {formatDateTime(item.updated_at)}
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px' }}>
                        <button
                          onClick={() => openEditModal(item)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '6px 12px',
                            fontSize: '13px',
                            border: '1px solid rgb(var(--theme-border))',
                            borderRadius: '8px',
                            background: 'transparent',
                            color: 'rgb(var(--theme-text-secondary))',
                            cursor: 'pointer',
                          }}
                        >
                          <Edit3 style={{ width: '12px', height: '12px' }} />
                          编辑
                        </button>
                        <button
                          onClick={() => openDeleteModal(item)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '6px 12px',
                            fontSize: '13px',
                            border: '1px solid rgba(239, 68, 68, 0.3)',
                            borderRadius: '8px',
                            background: 'transparent',
                            color: 'rgb(239, 68, 68)',
                            cursor: 'pointer',
                          }}
                        >
                          <Trash2 style={{ width: '12px', height: '12px' }} />
                          删除
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* 分页 */}
            {pagination.total_pages > 1 && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px', borderTop: '1px solid rgb(var(--theme-border))' }}>
                <span style={{ fontSize: '14px', color: 'rgb(var(--theme-text-muted))' }}>
                  共 {pagination.total} 条记录，第 {pagination.page}/{pagination.total_pages} 页
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button
                    onClick={() => handlePageChange(pagination.page - 1)}
                    disabled={pagination.page <= 1}
                    style={{
                      padding: '8px 12px',
                      fontSize: '13px',
                      border: '1px solid rgb(var(--theme-border))',
                      borderRadius: '8px',
                      background: 'transparent',
                      color: pagination.page <= 1 ? 'rgb(var(--theme-text-muted))' : 'rgb(var(--theme-text))',
                      cursor: pagination.page <= 1 ? 'not-allowed' : 'pointer',
                    }}
                  >
                    上一页
                  </button>
                  <button
                    onClick={() => handlePageChange(pagination.page + 1)}
                    disabled={pagination.page >= pagination.total_pages}
                    style={{
                      padding: '8px 12px',
                      fontSize: '13px',
                      border: '1px solid rgb(var(--theme-border))',
                      borderRadius: '8px',
                      background: 'transparent',
                      color: pagination.page >= pagination.total_pages ? 'rgb(var(--theme-text-muted))' : 'rgb(var(--theme-text))',
                      cursor: pagination.page >= pagination.total_pages ? 'not-allowed' : 'pointer',
                    }}
                  >
                    下一页
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* 创建/编辑弹窗 */}
      <Modal
        title={editModalMode === 'create' ? '新建提示词' : '编辑提示词'}
        open={editModalVisible}
        onCancel={() => setEditModalVisible(false)}
        footer={null}
        width={1200}
        centered
        destroyOnClose
        styles={{ body: { padding: '0 24px 24px' } }}
      >
        <div style={{ padding: '16px 0' }}>
          {editModalMode === 'create' && (
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: '8px' }}>
                文件名 <span style={{ color: 'rgb(239, 68, 68)' }}>*</span>
              </label>
              <input
                type="text"
                value={editForm.file_name}
                onChange={(e) => setEditForm({ ...editForm, file_name: e.target.value })}
                placeholder="请输入文件名（必须以 .txt 结尾）"
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  fontSize: '14px',
                  border: '1px solid rgb(var(--theme-border))',
                  borderRadius: '10px',
                  outline: 'none',
                  background: 'rgb(var(--theme-bg))',
                  color: 'rgb(var(--theme-text))',
                  boxSizing: 'border-box',
                }}
              />
            </div>
          )}

          <div style={{ marginBottom: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <label style={{ fontSize: '14px', fontWeight: 500, color: 'rgb(var(--theme-text))' }}>
                提示词内容 <span style={{ color: 'rgb(239, 68, 68)' }}>*</span>
              </label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => setIsPreviewMode(false)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '6px 12px',
                    fontSize: '13px',
                    border: !isPreviewMode ? '1px solid rgb(var(--theme-primary))' : '1px solid rgb(var(--theme-border))',
                    borderRadius: '6px',
                    background: !isPreviewMode ? 'rgba(var(--theme-primary), 0.1)' : 'transparent',
                    color: !isPreviewMode ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-secondary))',
                    cursor: 'pointer',
                  }}
                >
                  <Edit2 style={{ width: '12px', height: '12px' }} />
                  编辑
                </button>
                <button
                  onClick={() => setIsPreviewMode(true)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '6px 12px',
                    fontSize: '13px',
                    border: isPreviewMode ? '1px solid rgb(var(--theme-primary))' : '1px solid rgb(var(--theme-border))',
                    borderRadius: '6px',
                    background: isPreviewMode ? 'rgba(var(--theme-primary), 0.1)' : 'transparent',
                    color: isPreviewMode ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-secondary))',
                    cursor: 'pointer',
                  }}
                >
                  <Eye style={{ width: '12px', height: '12px' }} />
                  预览
                </button>
              </div>
            </div>

            {isPreviewMode ? (
              <div
                className="markdown-preview"
                style={{
                  height: '560px',
                  overflow: 'auto',
                  border: '1px solid rgb(var(--theme-border))',
                  borderRadius: '10px',
                  background: 'rgb(var(--theme-bg))',
                }}
              >
                <style>{`
                  .markdown-preview .markdown-body {
                    font-size: 14px;
                    line-height: 1.6;
                    padding: 16px;
                    color: rgb(var(--theme-text));
                  }
                  .markdown-preview .markdown-body h1,
                  .markdown-preview .markdown-body h2,
                  .markdown-preview .markdown-body h3,
                  .markdown-preview .markdown-body h4,
                  .markdown-preview .markdown-body h5,
                  .markdown-preview .markdown-body h6 {
                    margin-top: 16px;
                    margin-bottom: 8px;
                    font-weight: 600;
                    color: rgb(var(--theme-text));
                  }
                  .markdown-preview .markdown-body h1 { font-size: 20px; }
                  .markdown-preview .markdown-body h2 { font-size: 18px; }
                  .markdown-preview .markdown-body h3 { font-size: 16px; }
                  .markdown-preview .markdown-body p {
                    margin-bottom: 12px;
                    color: rgb(var(--theme-text-secondary));
                  }
                  .markdown-preview .markdown-body ul,
                  .markdown-preview .markdown-body ol {
                    padding-left: 24px;
                    margin-bottom: 12px;
                    color: rgb(var(--theme-text-secondary));
                  }
                  .markdown-preview .markdown-body li {
                    margin-bottom: 4px;
                  }
                  .markdown-preview .markdown-body ul li {
                    list-style-type: disc;
                  }
                  .markdown-preview .markdown-body ol li {
                    list-style-type: decimal;
                  }
                  .markdown-preview .markdown-body code {
                    padding: 2px 6px;
                    background: rgb(var(--theme-bg-secondary));
                    border-radius: 4px;
                    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
                    font-size: 13px;
                    color: rgb(var(--theme-primary));
                  }
                  .markdown-preview .markdown-body pre {
                    margin: 12px 0;
                    border-radius: 8px;
                    overflow: hidden;
                  }
                  .markdown-preview .markdown-body pre code {
                    padding: 0;
                    background: transparent;
                    color: inherit;
                  }
                  .markdown-preview .markdown-body blockquote {
                    border-left: 3px solid rgb(var(--theme-primary));
                    padding-left: 12px;
                    margin: 12px 0;
                    color: rgb(var(--theme-text-muted));
                  }
                  .markdown-preview .markdown-body table {
                    border-collapse: collapse;
                    width: 100%;
                    margin: 12px 0;
                  }
                  .markdown-preview .markdown-body th,
                  .markdown-preview .markdown-body td {
                    border: 1px solid rgb(var(--theme-border));
                    padding: 8px 12px;
                    text-align: left;
                  }
                  .markdown-preview .markdown-body th {
                    background: rgb(var(--theme-bg-secondary));
                    font-weight: 600;
                  }
                  .markdown-preview .markdown-body hr {
                    border: none;
                    border-top: 1px solid rgb(var(--theme-border));
                    margin: 16px 0;
                  }
                  .markdown-preview .markdown-body a {
                    color: rgb(var(--theme-primary));
                    text-decoration: none;
                  }
                  .markdown-preview .markdown-body a:hover {
                    text-decoration: underline;
                  }
                `}</style>
                {editForm.prompt ? (
                  <ReactMarkdown
                    className="markdown-body"
                    remarkPlugins={[gfm, math]}
                    components={{
                      code({ node, className, children, ...props }) {
                        const match = /language-(\w+)/.exec(className || '')
                        return match ? (
                          <SyntaxHighlighter
                            style={tomorrow as { [key: string]: React.CSSProperties }}
                            language={match[1]}
                            PreTag="div"
                            {...props}
                          >
                            {String(children).replace(/\n$/, '')}
                          </SyntaxHighlighter>
                        ) : (
                          <code className={className} {...props}>
                            {children}
                          </code>
                        )
                      },
                    }}
                  >
                    {editForm.prompt}
                  </ReactMarkdown>
                ) : (
                  <div style={{ color: 'rgb(var(--theme-text-muted))', textAlign: 'center', paddingTop: '100px' }}>
                    暂无内容
                  </div>
                )}
              </div>
            ) : (
              <textarea
                value={editForm.prompt}
                onChange={(e) => setEditForm({ ...editForm, prompt: e.target.value })}
                placeholder="请输入提示词内容..."
                rows={40}
                style={{
                  height: '560px',
                  width: '100%',
                  padding: '10px 14px',
                  fontSize: '14px',
                  border: '1px solid rgb(var(--theme-border))',
                  borderRadius: '10px',
                  outline: 'none',
                  background: 'rgb(var(--theme-bg))',
                  color: 'rgb(var(--theme-text))',
                  resize: 'vertical',
                  fontFamily: 'monospace',
                  boxSizing: 'border-box',
                }}
              />
            )}
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: '8px' }}>
              描述
            </label>
            <input
              type="text"
              value={editForm.description}
              onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
              placeholder="请输入描述信息（可选）"
              style={{
                width: '100%',
                padding: '10px 14px',
                fontSize: '14px',
                border: '1px solid rgb(var(--theme-border))',
                borderRadius: '10px',
                outline: 'none',
                background: 'rgb(var(--theme-bg))',
                color: 'rgb(var(--theme-text))',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {editError && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '12px', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '10px', marginBottom: '16px', color: 'rgb(239, 68, 68)', fontSize: '14px' }}>
              <AlertCircle style={{ width: '16px', height: '16px', flexShrink: 0 }} />
              {editError}
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
            <button
              onClick={() => setEditModalVisible(false)}
              style={{
                padding: '10px 20px',
                fontSize: '14px',
                border: '1px solid rgb(var(--theme-border))',
                borderRadius: '10px',
                background: 'transparent',
                color: 'rgb(var(--theme-text))',
                cursor: 'pointer',
              }}
            >
              取消
            </button>
            <button
              onClick={handleEditSubmit}
              disabled={editLoading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '10px 20px',
                fontSize: '14px',
                fontWeight: 500,
                border: 'none',
                borderRadius: '10px',
                background: 'rgb(var(--theme-primary))',
                color: '#fff',
                cursor: editLoading ? 'not-allowed' : 'pointer',
                opacity: editLoading ? 0.7 : 1,
              }}
            >
              {editLoading && <Loader2 style={{ width: '14px', height: '14px', animation: 'spin 1s linear infinite' }} />}
              {editModalMode === 'create' ? '创建' : '保存'}
            </button>
          </div>
        </div>
      </Modal>

      {/* 删除确认弹窗 */}
      <Modal
        title="确认删除"
        open={deleteModalVisible}
        onCancel={() => setDeleteModalVisible(false)}
        footer={null}
        width={400}
        centered
      >
        <div style={{ padding: '16px 0' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', marginBottom: '24px' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'rgba(239, 68, 68, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <AlertCircle style={{ width: '20px', height: '20px', color: 'rgb(239, 68, 68)' }} />
            </div>
            <div>
              <p style={{ fontSize: '15px', color: 'rgb(var(--theme-text))', marginBottom: '8px' }}>
                删除提示词 <strong>"{deletingPrompt?.file_name}"</strong>
              </p>
              <p style={{ fontSize: '13px', color: 'rgb(var(--theme-text-muted))' }}>
                此操作不可恢复，请谨慎操作。
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '12px' }}>
            <button
              onClick={() => setDeleteModalVisible(false)}
              style={{
                padding: '10px 20px',
                fontSize: '14px',
                border: '1px solid rgb(var(--theme-border))',
                borderRadius: '10px',
                background: 'transparent',
                color: 'rgb(var(--theme-text))',
                cursor: 'pointer',
              }}
            >
              取消
            </button>
            <button
              onClick={handleDelete}
              disabled={deleteLoading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '10px 20px',
                fontSize: '14px',
                fontWeight: 500,
                border: 'none',
                borderRadius: '10px',
                background: 'rgb(239, 68, 68)',
                color: '#fff',
                cursor: deleteLoading ? 'not-allowed' : 'pointer',
                opacity: deleteLoading ? 0.7 : 1,
              }}
            >
              {deleteLoading && <Loader2 style={{ width: '14px', height: '14px', animation: 'spin 1s linear infinite' }} />}
              确认删除
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default PromptConfigPage;
