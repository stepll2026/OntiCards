'use client';

import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import Link from 'next/link';
import { App } from 'antd';
import {
  Database,
  Plus,
  Server,
  CheckCircle,
  AlertCircle,
  ChevronRight,
  MoreVertical,
  RefreshCw,
  Trash2,
  Edit3,
  Loader2,
  CreditCard,
  Zap,
  X,
  Info,
} from 'lucide-react';
import { DataSourceItem, fullRefreshDataSource, quickRefreshDataSource, deleteDataSource } from '@/api/datasource';
import AddDataSourceModal from '@/components/business/AddDataSourceModal';
import { useDataSources } from '@/hooks/useDataSources';
import { urlPrefix } from '@/api/base';

// 数据库类型图标映射
const getDbTypeIcon = (dbType: string) => {
  const icons: Record<string, string> = {
    mysql: '🐬',
    postgresql: '🐘',
    mssql: '📊',
    oracle: '🔵',
    sqlite: '📁',
    trino: '⚡',
    kingbase: '🛡️',
    oceanbase: '🌊',
    dm: '💠',
  };
  return icons[dbType?.toLowerCase()] || '🗄️';
};

// 数据库类型颜色映射
const getDbTypeColor = (dbType: string) => {
  const colors: Record<string, string> = {
    mysql: 'bg-blue-100 text-blue-600',
    postgresql: 'bg-emerald-100 text-emerald-600',
    mssql: 'bg-purple-100 text-purple-600',
    oracle: 'bg-red-100 text-red-600',
    sqlite: 'bg-yellow-100 text-yellow-600',
    trino: 'bg-orange-100 text-orange-600',
    kingbase: 'bg-cyan-100 text-cyan-600',
    oceanbase: 'bg-sky-100 text-sky-600',
    dm: 'bg-indigo-100 text-indigo-600',
  };
  return colors[dbType?.toLowerCase()] || 'bg-gray-100 text-gray-600';
};

const WorkspacesPage = () => {
  const { message } = App.useApp();

  // 使用统一的数据源 hook 管理数据源状态
  const { dataSources, weaviateCount, loading, fetchDataSources, refreshDataSources } = useDataSources();

  const [refreshing, setRefreshing] = useState<string | null>(null);
  const [testingConnection, setTestingConnection] = useState<string | null>(null);

  // 操作菜单状态
  const [actionMenuVisible, setActionMenuVisible] = useState(false);
  const [actionMenuWorkspaceId, setActionMenuWorkspaceId] = useState<string | null>(null);

  // 删除确认弹框状态
  const [deleteConfirmVisible, setDeleteConfirmVisible] = useState(false);
  const [deleteTargetWorkspaceId, setDeleteTargetWorkspaceId] = useState<string | null>(null);
  // 标记是否正在进行删除操作，防止重复刷新
  const [isDeleting, setIsDeleting] = useState(false);

  // 添加数据源弹框状态
  const [addDataSourceModalOpen, setAddDataSourceModalOpen] = useState(false);

  // 首次加载时获取数据源
  useEffect(() => {
    fetchDataSources();
  }, [fetchDataSources]);

  // 从 dataSources 派生统计数据
  const totalTables = dataSources.reduce((acc, ws) => acc + (ws.table_num || 0), 0);
  const totalCards = dataSources.reduce((acc, ws) => acc + (ws.datacard_count || 0), 0);
  const workspaces = dataSources;

  // 点击外部关闭操作菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      const isMenuClick = target.closest('[data-action-menu]');
      if (!isMenuClick && actionMenuVisible) {
        setActionMenuVisible(false);
        setActionMenuWorkspaceId(null);
      }
    };

    if (actionMenuVisible) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [actionMenuVisible]);

  // 处理点击操作菜单按钮
  const handleActionMenuClick = (e: React.MouseEvent, workspaceId: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (actionMenuWorkspaceId === workspaceId && actionMenuVisible) {
      setActionMenuVisible(false);
      setActionMenuWorkspaceId(null);
    } else {
      setActionMenuWorkspaceId(workspaceId);
      setActionMenuVisible(true);
    }
  };

  // 处理测试连接
  const handleTestConnection = async (workspaceId: string) => {
    setActionMenuVisible(false);
    setActionMenuWorkspaceId(null);
    setTestingConnection(workspaceId);

    const loadingMessage = message.loading('正在测试连接...', 0);

    try {
      const token = localStorage.getItem('console_token') || '';
      const response = await fetch(
        `${urlPrefix}/datasource_tool/${workspaceId}/refresh?mode=quick`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': token
          }
        }
      );
      const data = await response.json();
      loadingMessage();

      if (data.code === 200) {
        message.success('连接测试成功');
      } else {
        message.error(data.msg || '连接测试失败');
      }
    } catch (error) {
      loadingMessage();
      console.error('测试连接失败:', error);
      message.error('连接测试失败，请稍后重试');
    } finally {
      setTestingConnection(null);
    }
  };

  // 处理删除数据源 - 显示确认弹框
  const handleDeleteDataSource = (workspaceId: string) => {
    setActionMenuVisible(false);
    setActionMenuWorkspaceId(null);
    setDeleteTargetWorkspaceId(workspaceId);
    setDeleteConfirmVisible(true);
  };

  // 确认删除数据源
  const confirmDeleteDataSource = async () => {
    if (!deleteTargetWorkspaceId || isDeleting) return;

    const workspaceId = deleteTargetWorkspaceId;
    setDeleteConfirmVisible(false);
    setDeleteTargetWorkspaceId(null);
    setIsDeleting(true);

    const loadingMessage = message.loading('正在删除数据源...', 0);

    try {
      const token = localStorage.getItem('console_token') || '';
      const response = await fetch(
        `${urlPrefix}/datasource_tool/${workspaceId}`,
        {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': token
          }
        }
      );
      const data = await response.json();
      loadingMessage();

      if (data.code === 200) {
        message.success('数据源删除成功');
        // 刷新数据源列表
        refreshDataSources();
      } else {
        message.error(data.msg || '删除失败');
      }
    } catch (error) {
      loadingMessage();
      console.error('删除数据源失败:', error);
      message.error('删除失败，请稍后重试');
    } finally {
      // 延迟重置删除状态，确保页面刷新完成
      setTimeout(() => setIsDeleting(false), 500);
    }
  };

  // 取消删除
  const cancelDelete = () => {
    setDeleteConfirmVisible(false);
    setDeleteTargetWorkspaceId(null);
  };

  const handleRefresh = async (id: string) => {
    // 先设置刷新状态，显示加载图标
    setRefreshing(id);

    // 显示正在刷新的提示
    const loadingMessage = message.loading('正在增量更新数据源...', 0);

    try {
      const token = localStorage.getItem('console_token') || '';
      const response = await fetch(
        `${urlPrefix}/datasource_tool/${id}/refresh?mode=full`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': token
          }
        }
      );
      const data = await response.json();

      // 关闭加载提示
      loadingMessage();

      if (data.code === 200) {
        // 根据返回数据生成友好的提示信息
        const { added_tables = [], removed_tables = [], changed_tables = [], unchanged_tables = [] } = data.data || {};
        const totalChanges = added_tables.length + removed_tables.length + changed_tables.length;

        let successMsg = '';
        if (totalChanges === 0) {
          successMsg = '数据源已是最新状态，无需更新';
        } else {
          const parts = [];
          if (added_tables.length > 0) parts.push(`新增 ${added_tables.length} 个表`);
          if (removed_tables.length > 0) parts.push(`删除 ${removed_tables.length} 个表`);
          if (changed_tables.length > 0) parts.push(`更新 ${changed_tables.length} 个表`);
          successMsg = parts.join('， ') + `，共 ${totalChanges} 个变化`;
        }

        message.success(successMsg);

        await refreshDataSources();
      } else {
        message.error(data.msg || '刷新失败');
      }
    } catch (error) {
      // 关闭加载提示
      loadingMessage();
      console.error('刷新数据源失败:', error);
      message.error('刷新失败，请稍后重试');
    } finally {
      setRefreshing(null);
    }
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className="space-y-6">
      {/* Header Section */}
      <header>
        <h1 className="text-2xl font-semibold mb-1 text-slate-900">
          工作空间
        </h1>
        <p className="text-sm text-slate-500">
          管理您的数据源与连接
        </p>
      </header>

      {/* Stats Overview */}
      <div className="grid grid-cols-5 gap-4">
        <div className="bg-white p-5 rounded-[20px] border border-slate-200 hover:shadow-sm transition-shadow relative overflow-hidden" style={{ position: 'relative' }}>
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
              background: 'radial-gradient(circle, #64748b, transparent 70%)',
              filter: 'blur(15px)',
            }}
          />
          <div className="flex items-center gap-3" style={{ position: 'relative', zIndex: 1 }}>
            <div className="p-3 bg-gradient-to-br from-slate-50 to-slate-100/50 rounded-[16px]">
              <Server className="w-5 h-5 text-slate-600" strokeWidth={2} />
            </div>
            <div>
              <p className="text-slate-500 text-xs mb-0.5">
                工作空间总数
              </p>
              <p className="text-2xl font-semibold text-slate-900">
                {loading ? '-' : workspaces.length}
              </p>
            </div>
          </div>
        </div>
        <div className="bg-white p-5 rounded-[20px] border border-slate-200 hover:shadow-sm transition-shadow relative overflow-hidden" style={{ position: 'relative' }}>
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
              background: 'radial-gradient(circle, #22c55e, transparent 70%)',
              filter: 'blur(15px)',
            }}
          />
          <div className="flex items-center gap-3" style={{ position: 'relative', zIndex: 1 }}>
            <div className="p-3 bg-gradient-to-br from-green-50 to-emerald-50 rounded-[16px]">
              <CheckCircle
                className="w-5 h-5 text-green-600"
                strokeWidth={2}
              />
            </div>
            <div>
              <p className="text-slate-500 text-xs mb-0.5">可用</p>
              <p className="text-2xl font-semibold text-slate-900">
                {loading
                  ? '-'
                  : workspaces.filter((w) => w.status === 'available').length}
              </p>
            </div>
          </div>
        </div>
        <div className="bg-white p-5 rounded-[20px] border border-slate-200 hover:shadow-sm transition-shadow relative overflow-hidden" style={{ position: 'relative' }}>
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
              background: 'radial-gradient(circle, #3b82f6, transparent 70%)',
              filter: 'blur(15px)',
            }}
          />
          <div className="flex items-center gap-3" style={{ position: 'relative', zIndex: 1 }}>
            <div className="p-3 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-[16px]">
              <Database
                className="w-5 h-5 text-blue-600"
                strokeWidth={2}
              />
            </div>
            <div>
              <p className="text-slate-500 text-xs mb-0.5">数据表总数</p>
              <p className="text-2xl font-semibold text-slate-900">
                {loading ? '-' : totalTables}
              </p>
            </div>
          </div>
        </div>
        <div className="bg-white p-5 rounded-[20px] border border-slate-200 hover:shadow-sm transition-shadow relative overflow-hidden" style={{ position: 'relative' }}>
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
              background: 'radial-gradient(circle, #f97316, transparent 70%)',
              filter: 'blur(15px)',
            }}
          />
          <div className="flex items-center gap-3" style={{ position: 'relative', zIndex: 1 }}>
            <div className="p-3 bg-gradient-to-br from-orange-50 to-amber-50 rounded-[16px]">
              <CreditCard
                className="w-5 h-5 text-orange-600"
                strokeWidth={2}
              />
            </div>
            <div>
              <p className="text-slate-500 text-xs mb-0.5">数据卡片</p>
              <p className="text-2xl font-semibold text-slate-900">
                {loading ? '-' : totalCards}
              </p>
            </div>
          </div>
        </div>
        <div className="bg-white p-5 rounded-[20px] border border-slate-200 hover:shadow-sm transition-shadow relative overflow-hidden" style={{ position: 'relative' }}>
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
              background: 'radial-gradient(circle, #a855f7, transparent 70%)',
              filter: 'blur(15px)',
            }}
          />
          <div className="flex items-center gap-3" style={{ position: 'relative', zIndex: 1 }}>
            <div className="p-3 bg-gradient-to-br from-purple-50 to-pink-50 rounded-[16px]">
              <Database
                className="w-5 h-5 text-purple-600"
                strokeWidth={2}
              />
            </div>
            <div>
              <p className="text-slate-500 text-xs mb-0.5">向量库索引</p>
              <p className="text-2xl font-semibold text-slate-900">
                {loading ? '-' : weaviateCount}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Workspaces List */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-1.5 relative z-20">
            <h3 className="text-sm font-semibold text-slate-900">全部工作空间</h3>
              <div className="group relative inline-flex">
                <Info className="w-4 h-4 text-slate-400 flex-shrink-0" />
                <div className="absolute left-0 top-full mt-1.5 px-3 py-2 bg-white border border-slate-200 text-slate-600 text-xs rounded-xl shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-30 whitespace-nowrap">
                  当前支持数据源：PostgreSQL、MySQL、Oracle、SQL Server、Trino、SQLite、电科金仓(原人大金仓)KingBase、OceanBase(MySQL模式)、DMBase(达梦)
                </div>
              </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => refreshDataSources()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[10px] text-sm font-medium text-slate-500 hover:text-indigo-600 hover:bg-indigo-50/50 transition-colors"
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              <span>{loading ? '刷新中' : '刷新'}</span>
            </button>
            <button
              onClick={() => setAddDataSourceModalOpen(true)}
              className="flex items-center gap-1.5 bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-4 py-1.5 rounded-[10px] text-sm font-medium hover:from-blue-700 hover:to-indigo-700 transition-all shadow-sm hover:shadow-md"
            >
              <Plus className="w-4 h-4" />
              添加工作空间
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center min-h-[300px]">
            <div className="flex flex-col items-center">
              <Loader2 className="w-10 h-10 animate-spin text-indigo-600" />
              <p className="text-slate-500 font-medium mt-4">正在加载工作空间...</p>
            </div>
          </div>
        ) : workspaces.length === 0 ? (
          <div className="bg-white rounded-[20px] border border-slate-200 p-12 text-center">
            <div
              className="w-16 h-16 bg-slate-100 flex items-center justify-center mx-auto mb-4"
              style={{ borderRadius: '50%' }}
            >
              <Database className="w-8 h-8 text-slate-400" />
            </div>
            <h4 className="text-lg font-semibold text-slate-900 mb-2">暂无工作空间</h4>
            <p className="text-sm text-slate-500 mb-6">
              创建您的第一个工作空间以开始管理数据源
            </p>
            <button
              onClick={() => setAddDataSourceModalOpen(true)}
              className="inline-flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-5 py-2.5 rounded-[12px] text-sm font-medium hover:from-blue-700 hover:to-indigo-700 transition-all"
            >
              <Plus className="w-4 h-4" />
              添加工作空间
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            {workspaces.map((workspace) => (
              <div
                key={workspace.id}
                className="group bg-white p-6 rounded-[20px] border border-slate-200 hover:shadow-lg hover:border-indigo-200 transition-all"
              >
                <div className="flex items-start justify-between">
                  <Link
                    href={`/workspaces/${workspace.id}`}
                    className="flex-1"
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-2xl">
                        {getDbTypeIcon(workspace.db_type)}
                      </span>
                      <h4 className="font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors">
                        {workspace.connect_name}
                      </h4>
                      {workspace.status === 'available' ? (
                        <CheckCircle className="w-4 h-4 text-green-500" />
                      ) : (
                        <AlertCircle className="w-4 h-4 text-red-500" />
                      )}
                    </div>
                    <p className="text-xs text-slate-500 mb-3">
                      {workspace.database_name}
                    </p>
                    <div className="flex items-center gap-3">
                      <span
                        className={`px-2.5 py-1 rounded-full text-xs font-medium ${getDbTypeColor(workspace.db_type)}`}
                        style={{ borderRadius: '9999px' }}
                      >
                        {workspace.db_type?.toUpperCase() || 'DB'}
                      </span>
                      <span
                        className="text-xs text-slate-400"
                        style={{ backgroundColor: '#f1f5f9', padding: '2px 8px', borderRadius: '9999px' }}
                      >
                        {workspace.table_num || 0} tables
                      </span>
                      {workspace.datacard_count !== undefined && workspace.datacard_count > 0 && (
                        <span
                          className="text-xs text-orange-500 bg-orange-50 px-2 py-0.5 rounded-full"
                          style={{ borderRadius: '9999px' }}
                        >
                          {workspace.datacard_count} 卡片
                        </span>
                      )}
                      {workspace.weaviate_num !== undefined && workspace.weaviate_num > 0 && (
                        <span
                          className="text-xs text-purple-500 bg-purple-50 px-2 py-0.5 rounded-full"
                          style={{ borderRadius: '9999px' }}
                        >
                          {workspace.weaviate_num} 向量
                        </span>
                      )}
                    </div>
                  </Link>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        handleRefresh(workspace.id);
                      }}
                      className="p-2 rounded-lg text-slate-400 hover:text-indigo-600 transition-colors"
                      title="刷新"
                    >
                      {refreshing === workspace.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <RefreshCw className="w-4 h-4" />
                      )}
                    </button>
                    <Link
                      href={`/workspaces/${workspace.id}`}
                      className="p-2"
                    >
                      <ChevronRight className="w-5 h-5 text-slate-300 group-hover:text-indigo-500 transition-colors" />
                    </Link>
                  </div>
                </div>
                <div className="mt-4 pt-4 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-xs text-slate-400">
                    更新于 {formatDate(workspace.updated_at)}
                  </span>
                  <div data-action-menu className="relative">
                    <button
                      onClick={(e) => handleActionMenuClick(e, workspace.id)}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 transition-colors"
                    >
                      <MoreVertical className="w-4 h-4" />
                    </button>
                    {/* 操作菜单 */}
                    {actionMenuVisible && actionMenuWorkspaceId === workspace.id && (
                      <div className="absolute left-0 top-full mt-2 w-36 bg-white rounded-[12px] shadow-lg border border-slate-200 py-1 z-10">
                        <button
                          onClick={() => handleTestConnection(workspace.id)}
                          disabled={testingConnection === workspace.id}
                          className="w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2 transition-colors disabled:opacity-50"
                        >
                          {testingConnection === workspace.id ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Zap className="w-4 h-4" />
                          )}
                          测试连接
                        </button>
                        <button
                          onClick={() => handleDeleteDataSource(workspace.id)}
                          className="w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                          删除数据源
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 添加数据源弹框 */}
      <AddDataSourceModal
        isOpen={addDataSourceModalOpen}
        onClose={() => setAddDataSourceModalOpen(false)}
        onSuccess={() => {
          setAddDataSourceModalOpen(false);
          message.success('数据源添加成功');
          // 刷新数据源列表
          refreshDataSources();
        }}
      />

      {/* 删除确认弹框：Portal 到 body 避免布局内定位导致顶部白边 */}
      {deleteConfirmVisible && typeof document !== 'undefined' && createPortal(
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center p-4"
          style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9999 }}
        >
          <div className="bg-white rounded-xl w-full max-w-sm p-5 shadow-xl" style={{ borderRadius: '16px' }}>
            <div className="flex justify-center mb-4">
              <AlertCircle className="w-10 h-10 text-red-500" />
            </div>
            <h3 className="text-base font-semibold text-slate-900 text-center mb-2">
              确定要删除该数据源吗？
            </h3>
            <p className="text-xs text-slate-500 text-center mb-5">
              此操作不可恢复，删除后该数据源的所有数据将被永久删除。
            </p>
            <div className="flex gap-2">
              <button
                onClick={cancelDelete}
                className="flex-1 px-4 py-2 border border-slate-200 text-slate-700 text-sm font-medium hover:bg-slate-50 transition-colors"
                style={{ borderRadius: '12px' }}
              >
                取消
              </button>
              <button
                onClick={confirmDeleteDataSource}
                className="flex-1 px-4 py-2 bg-red-600 text-white text-sm font-medium hover:bg-red-700 transition-colors"
                style={{ borderRadius: '12px' }}
              >
                确认删除
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};

export default WorkspacesPage;

