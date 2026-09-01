'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { message } from 'antd';
import {
  Clock,
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  Eye,
  Loader2,
  X,
  Calendar,
  AlertCircle,
  CheckCircle,
  XCircle,
  Timer,
  Hash,
  BarChart3,
  Database,
  ChevronDown,
  ChevronRight as ChevronRightIcon,
  Layers,
  Table,
  Star,
  FileText,
  Copy,
  Check,
  RefreshCw,
  Key,
  Columns,
  Info,
  Tag,
  Trash2,
  Sparkles,
  BookOpen,
  ChevronDown as ChevronDownIcon,
} from 'lucide-react';
import { useUserInfo } from '@/hooks';
import {
  getQueryHistoryList,
  getQueryHistoryDetail,
  getQueryHistoryStats,
  deleteQueryHistory,
  batchDeleteQueryHistory,
  QueryHistoryItem,
  QueryHistoryDetailResponse,
  QueryHistoryDetailData,
  QueryHistoryStatsResponse,
  QueryHistoryListParams,
  QueryHistoryStatsParams,
  FullResponseResult,
  DataCardInfo,
  DataCardContent,
  ClusterSQL,
  TermRewriteInfo,
} from '@/api/queryHistory';

type StatusType = 'all' | 'success' | 'error' | 'timeout';

interface QueryHistoryPageProps {
  /** 工作空间ID，如果提供则按工作空间筛选 */
  workspaceId?: string;
  /** 数据源ID，用于按数据源查看历史筛选（隔离不同数据源的历史查询） */
  sourceDatasourceId?: string;
  /** 是否显示搜索筛选区域，默认为true */
  showFilters?: boolean;
  /** 是否显示统计卡片，默认为true */
  showStats?: boolean;
  /** 是否显示刷新按钮，默认为true */
  showRefresh?: boolean;
  /** 是否显示头部区域，默认为true */
  showHeader?: boolean;
}

const QueryHistoryPage = ({
  workspaceId,
  sourceDatasourceId,
  showFilters = true,
  showStats = true,
  showRefresh = true,
  showHeader = true,
}: QueryHistoryPageProps) => {
  const { userInfo } = useUserInfo();
  const currentUserId = userInfo?.id || '';

  const [list, setList] = useState<QueryHistoryItem[]>([]);
  const [allList, setAllList] = useState<QueryHistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState<StatusType>('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [showFiltersPanel, setShowFiltersPanel] = useState(false);

  const [stats, setStats] = useState<QueryHistoryStatsResponse['data'] | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  const [detailModal, setDetailModal] = useState<QueryHistoryDetailData | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['data-cards', 'query-results']));
  const [selectedCardDetail, setSelectedCardDetail] = useState<DataCardInfo | null>(null);

  // 删除相关状态
  const [deleteModalVisible, setDeleteModalVisible] = useState(false);
  const [deleteType, setDeleteType] = useState<'single' | 'batch'>('single');
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchDeleteModalVisible, setBatchDeleteModalVisible] = useState(false);
  const [currentDeleteId, setCurrentDeleteId] = useState<string>('');
  const [batchDeleteOption, setBatchDeleteOption] = useState<'before_date' | 'keep_days'>('before_date');
  const [batchDeleteDate, setBatchDeleteDate] = useState('');
  const [batchDeleteDays, setBatchDeleteDays] = useState(30);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // 删除单条查询历史
  const handleDeleteSingle = async (queryId: string) => {
    if (!currentUserId) {
      console.error('用户ID为空，无法删除');
      return;
    }
    setDeleteLoading(true);
    try {
      const res = await deleteQueryHistory(queryId, currentUserId);
      if (res.code === 200) {
        message.success('删除成功');
        // 刷新列表和统计数据
        fetchList();
        fetchAllList();
        fetchStats();
        // 清除选择状态
        setSelectedIds(prev => {
          const newSet = new Set(prev);
          newSet.delete(queryId);
          return newSet;
        });
      }
    } catch (error) {
      console.error('删除失败:', error);
      message.error('删除失败，请重试');
    } finally {
      setDeleteLoading(false);
    }
  };

  // 批量删除查询历史
  const handleBatchDelete = async () => {
    if (!currentUserId) return;
    setDeleteLoading(true);
    try {
      const params: { user_id: string; query_ids?: string; before_date?: string; keep_days?: number } = {
        user_id: currentUserId,
      };

      if (batchDeleteOption === 'before_date' && batchDeleteDate) {
        params.before_date = batchDeleteDate;
      } else if (batchDeleteOption === 'keep_days') {
        params.keep_days = batchDeleteDays;
      }

      const res = await batchDeleteQueryHistory(params);
      if (res.code === 200) {
        const deletedCount = res.data?.deleted_count || 0;
        message.success(`成功删除 ${deletedCount} 条记录`);
        // 重新获取列表
        fetchList();
        fetchAllList();
        // 重新获取统计数据
        fetchStats();
        setBatchDeleteModalVisible(false);
      }
    } catch (error) {
      console.error('批量删除失败:', error);
    } finally {
      setDeleteLoading(false);
    }
  };

  // 切换选择状态
  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  };

  // 全选/取消全选
  const toggleSelectAll = () => {
    if (selectedIds.size === displayList.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(displayList.map(item => item.id)));
    }
  };

  // 批量删除选中项
  const handleBatchDeleteSelected = async () => {
    if (!currentUserId || selectedIds.size === 0) return;
    setDeleteLoading(true);
    try {
      const res = await batchDeleteQueryHistory({
        user_id: currentUserId,
        query_ids: Array.from(selectedIds).join(','),
      });
      if (res.code === 200) {
        message.success(`成功删除 ${selectedIds.size} 条记录`);
        // 重新获取列表
        fetchList();
        fetchAllList();
        // 重新获取统计数据
        fetchStats();
        setSelectedIds(new Set());
      }
    } catch (error) {
      console.error('批量删除失败:', error);
      message.error('批量删除失败，请重试');
    } finally {
      setDeleteLoading(false);
    }
  };

  const fetchAllList = useCallback(async (showSuccess?: boolean) => {
    if (!currentUserId) return;
    setLoading(true);
    try {
      const params: QueryHistoryListParams = {
        user_id: currentUserId,
        page: 1,
        page_size: 1000,
      };
      if (workspaceId) {
        params.workspace_id = workspaceId;
      }
      if (sourceDatasourceId) {
        params.source_datasource_id = sourceDatasourceId;
      }
      if (status !== 'all') params.status = status;
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;

      const res = await getQueryHistoryList(params);
      if (res.code === 200 && res.data) {
        setAllList(res.data.items || []);
        if (showSuccess) {
          message.success(`刷新成功，共 ${res.data.items?.length || 0} 条记录`);
        }
      } else if (showSuccess) {
        message.success('刷新成功');
      }
    } catch (e) {
      console.error('获取查询历史失败', e);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, sourceDatasourceId, currentUserId, status, startDate, endDate]);

  const fetchList = useCallback(async (showSuccess?: boolean) => {
    if (!currentUserId) return;
    setLoading(true);
    try {
      const params: QueryHistoryListParams = {
        user_id: currentUserId,
        page,
        page_size: pageSize,
      };
      if (workspaceId) {
        params.workspace_id = workspaceId;
      }
      if (sourceDatasourceId) {
        params.source_datasource_id = sourceDatasourceId;
      }
      if (status !== 'all') params.status = status;
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;

      const res = await getQueryHistoryList(params);
      if (res.code === 200 && res.data) {
        setList(res.data.items || []);
        const totalCount = res.data.total ?? res.data.items?.length ?? 0;
        setTotal(totalCount);
        if (showSuccess) {
          message.success(`刷新成功，共 ${totalCount} 条记录`);
        }
      } else if (showSuccess) {
        message.success('刷新成功');
      }
    } catch (e) {
      console.error('获取查询历史失败', e);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, sourceDatasourceId, currentUserId, page, pageSize, status, startDate, endDate]);

  const fetchStats = useCallback(async () => {
    if (!currentUserId) return;
    setStatsLoading(true);
    try {
      const params: QueryHistoryStatsParams = {
        user_id: currentUserId,
      };
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      if (workspaceId) {
        params.workspace_id = workspaceId;
      }
      if (sourceDatasourceId) {
        params.source_datasource_id = sourceDatasourceId;
      }

      const res = await getQueryHistoryStats(params);
      if (res.code === 200 && res.data) {
        setStats(res.data);
      }
    } catch (e) {
      console.error('获取统计失败', e);
    } finally {
      setStatsLoading(false);
    }
  }, [workspaceId, sourceDatasourceId, currentUserId, startDate, endDate]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  useEffect(() => {
    fetchAllList();
  }, [fetchAllList]);

  useEffect(() => {
    if (showStats) {
      fetchStats();
    }
  }, [fetchStats, showStats]);

  const handleViewDetail = async (item: QueryHistoryItem) => {
    if (!workspaceId && !currentUserId) return;
    setDetailLoading(true);
    setDetailModal(null);
    setSelectedCardDetail(null);
    setExpandedSections(new Set(['data-cards', 'query-results'])); // 默认全部展开
    try {
      const res = await getQueryHistoryDetail(item.id, currentUserId);
      if (res.code === 200 && res.data) {
        setDetailModal(res.data);
      }
    } catch (e) {
      console.error('获取详情失败', e);
    } finally {
      setDetailLoading(false);
    }
  };

  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const newSet = new Set(prev);
      if (newSet.has(section)) {
        newSet.delete(section);
      } else {
        newSet.add(section);
      }
      return newSet;
    });
  };

  const isSectionExpanded = (section: string) => expandedSections.has(section);

  // 从 data_card 中提取卡片名称
  const getCardName = (card: DataCardInfo): string => {
    if (card.card_name) return card.card_name;
    if (card.card_content?.DocInfo?.title) return card.card_content.DocInfo.title;
    if (card.card_content?.SQLMeta?.table) return `数据表: ${card.card_content.SQLMeta.table}`;
    return card.table_name || '未命名卡片';
  };

  // 从 data_card 中提取数据源名称
  const getCardDatasource = (card: DataCardInfo): string => {
    if (card.datasource_name) return card.datasource_name;
    if (card.card_content?.DocInfo?.connect_name) return card.card_content.DocInfo.connect_name;
    return '未知数据源';
  };

  // 从 data_card 中提取字段列表
  const getCardColumns = (card: DataCardInfo): string[] => {
    if (card.column_names && card.column_names.length > 0) return card.column_names;
    if (card.card_content?.SQLMeta?.columns) {
      return card.card_content.SQLMeta.columns.map(col => col.name);
    }
    return [];
  };

  // 从 data_card 中提取内容预览
  const getCardPreview = (card: DataCardInfo): string | undefined => {
    if (card.content_preview) return card.content_preview;
    if (card.card_content?.Tags && card.card_content.Tags.length > 0) {
      // 取前几个 Tags 作为预览
      const tags = card.card_content.Tags.filter(t => !t.includes('_id') || t === 'course_id');
      return tags.slice(0, 8).join(' / ');
    }
    if (card.description) return card.description;
    return undefined;
  };

  // 格式化 SQL 提高可读性
  const formatSQL = (sql: string): string => {
    if (!sql) return '';

    const mainKeywords = [
      'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN', 'OUTER JOIN', 'JOIN',
      'SELECT', 'FROM', 'WHERE',
      'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT', 'OFFSET', 'UNION',
      'INSERT INTO', 'UPDATE', 'DELETE FROM',
    ];

    let formatted = sql.replace(/\s+/g, ' ').trim();
    const sortedKeywords = [...mainKeywords].sort((a, b) => b.length - a.length);

    sortedKeywords.forEach(keyword => {
      const escapedKeyword = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(`\\b${escapedKeyword}\\b`, 'gi');
      formatted = formatted.replace(regex, `\n${keyword}`);
    });

    formatted = formatted.split('\n').map(line => {
      const trimmed = line.trim();
      if (!trimmed) return '';
      return trimmed;
    }).filter(line => line.trim() !== '').join('\n');

    return formatted.trim();
  };

  const handleSearch = () => {
    setPage(1);
    if (keyword.trim()) {
      fetchAllList();
    } else {
      fetchList();
    }
    if (showStats) fetchStats();
  };

  const handleReset = () => {
    setKeyword('');
    setStatus('all');
    setStartDate('');
    setEndDate('');
    setPage(1);
    fetchAllList();
    if (showStats) fetchStats();
  };

  // 前端过滤列表
  const displayList = React.useMemo(() => {
    if (!keyword.trim()) {
      return list;
    }
    const searchLower = keyword.toLowerCase();
    return allList.filter(item =>
      item.question.toLowerCase().includes(searchLower) ||
      (item.sql && item.sql.toLowerCase().includes(searchLower))
    );
  }, [keyword, list, allList]);

  const totalPages = Math.ceil(total / pageSize);

  const getStatusBadge = (status: string) => {
    const config: Record<string, { icon: React.ReactNode; label: string; style: React.CSSProperties }> = {
      success: { 
        icon: <CheckCircle className="w-3 h-3" style={{ flexShrink: 0 }} />, 
        label: '成功', 
        style: { 
          backgroundColor: 'rgba(22, 163, 74, 0.12)', 
          color: 'rgb(22, 163, 74)', 
          borderColor: 'rgba(22, 163, 74, 0.3)',
          borderRadius: '6px',
          padding: '2px 8px',
          fontSize: '12px',
          fontWeight: 500,
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          whiteSpace: 'nowrap',
          border: '1px solid',
        } 
      },
      error: { 
        icon: <XCircle className="w-3 h-3" style={{ flexShrink: 0 }} />, 
        label: '失败', 
        style: { 
          backgroundColor: 'rgba(220, 38, 38, 0.12)', 
          color: 'rgb(220, 38, 38)', 
          borderColor: 'rgba(220, 38, 38, 0.3)',
          borderRadius: '6px',
          padding: '2px 8px',
          fontSize: '12px',
          fontWeight: 500,
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          whiteSpace: 'nowrap',
          border: '1px solid',
        } 
      },
      timeout: { 
        icon: <Timer className="w-3 h-3" style={{ flexShrink: 0 }} />, 
        label: '超时', 
        style: { 
          backgroundColor: 'rgba(217, 119, 6, 0.12)', 
          color: 'rgb(217, 119, 6)', 
          borderColor: 'rgba(217, 119, 6, 0.3)',
          borderRadius: '6px',
          padding: '2px 8px',
          fontSize: '12px',
          fontWeight: 500,
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          whiteSpace: 'nowrap',
          border: '1px solid',
        } 
      },
    };
    const item = config[status] || config.error;
    return (
      <span style={item.style}>
        {item.icon}
        {item.label}
      </span>
    );
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      console.error('复制失败:', err);
    }
  };

  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined) return 'null';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  };

  /**
   * 获取查询类型（单数据源/多数据源）
   */
  const getQueryType = (item: QueryHistoryItem): { type: string; isMulti: boolean } => {
    const sourceCount = item.source_datasource_ids?.length || 0;
    if (sourceCount === 0) return { type: '未知', isMulti: false };
    if (sourceCount === 1) return { type: '单数据源', isMulti: false };
    return { type: '多数据源', isMulti: true };
  };

  // 刷新数据
  const handleRefresh = async () => {
    console.log('handleRefresh called, currentUserId:', currentUserId);
    if (!currentUserId) return;
    setIsRefreshing(true);
    try {
      const params: QueryHistoryListParams = {
        user_id: currentUserId,
        page,
        page_size: pageSize,
      };
      if (workspaceId) {
        params.workspace_id = workspaceId;
      }
      if (sourceDatasourceId) {
        params.source_datasource_id = sourceDatasourceId;
      }
      if (keyword) params.keyword = keyword;
      if (status !== 'all') params.status = status;
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;

      const res = await getQueryHistoryList(params);
      console.log('handleRefresh getQueryHistoryList result:', res);
      if (res.code === 200 && res.data) {
        setList(res.data.items || []);
        const totalCount = res.data.total ?? res.data.items?.length ?? 0;
        setTotal(totalCount);
        message.success(`刷新成功，共 ${totalCount} 条记录`);
      } else {
        message.success('刷新成功');
      }
      if (showStats) fetchStats();
    } catch (e) {
      console.error('刷新失败', e);
      message.error('刷新失败，请重试');
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* 历史查询 Tab 头部 - 仅当 showHeader 为 true 时显示 */}
      {showHeader && (
        <div
          style={{
            padding: '1.25rem',
            borderBottom: '1px solid rgb(var(--theme-border))',
            background: 'linear-gradient(135deg, rgba(var(--theme-bg-tertiary), 0.6) 0%, rgb(var(--theme-bg)) 50%, rgba(var(--theme-bg-tertiary), 0.4) 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div className="flex items-center gap-4">
            <div style={{
              width: '2.5rem',
              height: '2.5rem',
              borderRadius: '16px',
              background: 'linear-gradient(135deg, rgb(6,182,212), rgb(37,99,235))',
              color: '#fff',
              boxShadow: '0 10px 15px -3px rgba(6,182,212,0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            >
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold" style={{ color: 'rgb(var(--theme-text))' }}>历史查询</h3>
              <p className="text-sm" style={{ color: 'rgb(var(--theme-text-muted))' }}>查看和管理历史查询记录及统计</p>
            </div>
          </div>
          {showRefresh && (
            <button
              onClick={handleRefresh}
              disabled={loading || statsLoading || isRefreshing}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 14px',
                fontSize: '13px',
                color: 'rgb(var(--theme-text-secondary))',
                backgroundColor: 'transparent',
                border: '1px solid rgb(var(--theme-border))',
                borderRadius: '8px',
                cursor: loading || statsLoading ? 'not-allowed' : 'pointer',
                opacity: loading || statsLoading ? 0.6 : 1,
                transition: 'all 0.2s ease',
              }}
              onMouseEnter={(e) => {
                if (!loading && !statsLoading) {
                  e.currentTarget.style.backgroundColor = 'rgb(var(--theme-bg-tertiary))';
                  e.currentTarget.style.borderColor = 'rgb(var(--theme-border-hover))';
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent';
                e.currentTarget.style.borderColor = 'rgb(var(--theme-border))';
              }}
            >
              <RefreshCw className={`w-4 h-4 ${loading || statsLoading ? 'animate-spin' : ''}`} style={{ transition: 'transform 0.2s' }} />
              刷新
            </button>
          )}
        </div>
      )}

      {/* 内容区域 */}
      <div className="p-5">
        {/* 统计卡片 - 加载时不显示旧数据 */}
        {showStats && !statsLoading && stats && (
          <div className="grid grid-cols-4 gap-3 mb-4">
            <StatCard title="总查询数" value={stats.total_queries} icon={<Hash className="w-4 h-4" />} color="indigo" />
            <StatCard title="成功数" value={stats.success_queries} icon={<CheckCircle className="w-4 h-4" />} color="green" suffix={`成功率 ${stats.success_rate.toFixed(1)}%`} />
            <StatCard title="失败数" value={stats.error_queries + stats.timeout_queries} icon={<AlertCircle className="w-4 h-4" />} color="red" />
            <StatCard title="平均耗时" value={formatDuration(stats.avg_duration_ms)} icon={<Timer className="w-4 h-4" />} color="blue" />
          </div>
        )}
        {showStats && statsLoading && (
          <div className="grid grid-cols-4 gap-4 mb-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="rounded-[16px] border p-5 h-28 animate-pulse" style={{
                backgroundColor: 'rgb(var(--theme-bg-secondary))',
                borderColor: 'rgb(var(--theme-border))'
              }} />
            ))}
          </div>
        )}

        {/* 搜索和筛选区域 - 始终可用 */}
        {showFilters && (
          <div className="rounded-[16px] border p-4 mb-4" style={{
            backgroundColor: 'rgb(var(--theme-bg-secondary))',
            borderColor: 'rgb(var(--theme-border))'
          }}>
            <div className="flex items-center gap-3 mb-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'rgb(var(--theme-text-muted))' }} />
                <input
                  type="text"
                  placeholder="搜索问题或SQL..."
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  style={{
                    width: '100%',
                    paddingLeft: '2.5rem',
                    paddingRight: '1rem',
                    paddingTop: '0.625rem',
                    paddingBottom: '0.625rem',
                    border: '1px solid rgb(var(--theme-border))',
                    borderRadius: '12px',
                    fontSize: '14px',
                    outline: 'none',
                    backgroundColor: 'rgb(var(--theme-bg))',
                    color: 'rgb(var(--theme-text))',
                  }}
                  className="focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
              </div>
              <button
                onClick={() => setShowFiltersPanel(!showFiltersPanel)}
                className="flex items-center gap-2 px-4 py-2.5 border rounded-[12px] text-sm font-medium transition-colors"
                style={{
                  borderColor: showFiltersPanel ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-border))',
                  color: showFiltersPanel ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-secondary))',
                  backgroundColor: showFiltersPanel ? 'rgba(var(--theme-primary), 0.08)' : 'rgb(var(--theme-bg))',
                }}
              >
                <Filter className="w-4 h-4" />
                筛选
              </button>
              <button
                onClick={handleSearch}
                className="flex items-center gap-2 px-4 py-2.5 rounded-[12px] text-sm font-medium hover:opacity-90"
                style={{
                  backgroundColor: 'rgb(var(--theme-primary))',
                  color: '#fff',
                }}
              >
                <Search className="w-4 h-4" />
                搜索
              </button>
              {/* 刷新按钮 - 仅当 showHeader 为 false 时显示 */}
              {!showHeader && showRefresh && (
                <button
                  onClick={handleRefresh}
                  disabled={loading || statsLoading || isRefreshing}
                  className="flex items-center gap-2 px-3 py-2 border rounded-[12px] text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{
                    borderColor: 'rgb(var(--theme-border))',
                    color: 'rgb(var(--theme-text-secondary))',
                    backgroundColor: 'rgb(var(--theme-bg))',
                  }}
                >
                  <RefreshCw className={`w-4 h-4 ${(loading || statsLoading || isRefreshing) ? 'animate-spin' : ''}`} />
                </button>
              )}
            </div>

            {showFiltersPanel && (
              <div className="flex items-center gap-4 pt-4 border-t" style={{ borderTopColor: 'rgb(var(--theme-border))' }}>
                <div className="flex items-center gap-2">
                  <Calendar className="w-4 h-4" style={{ color: 'rgb(var(--theme-text-muted))' }} />
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="px-3 py-2 border rounded-[10px] text-sm"
                    style={{
                      backgroundColor: 'rgb(var(--theme-bg))',
                      borderColor: 'rgb(var(--theme-border))',
                      color: 'rgb(var(--theme-text))',
                    }}
                  />
                  <span style={{ color: 'rgb(var(--theme-text-muted))' }}>至</span>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="px-3 py-2 border rounded-[10px] text-sm"
                    style={{
                      backgroundColor: 'rgb(var(--theme-bg))',
                      borderColor: 'rgb(var(--theme-border))',
                      color: 'rgb(var(--theme-text))',
                    }}
                  />
                </div>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value as StatusType)}
                  className="px-3 py-2 border rounded-[10px] text-sm"
                  style={{
                    backgroundColor: 'rgb(var(--theme-bg))',
                    borderColor: 'rgb(var(--theme-border))',
                    color: 'rgb(var(--theme-text))',
                  }}
                >
                  <option value="all">全部状态</option>
                  <option value="success">成功</option>
                  <option value="error">失败</option>
                  <option value="timeout">超时</option>
                </select>
                <button
                  onClick={handleReset}
                  className="text-sm transition-colors hover:opacity-80"
                  style={{ color: 'rgb(var(--theme-text-muted))' }}
                >
                  重置
                </button>
              </div>
            )}
          </div>
        )}

        {/* 列表区域 */}
        <div className="rounded-[16px] border overflow-hidden" style={{
          backgroundColor: 'rgb(var(--theme-bg))',
          borderColor: 'rgb(var(--theme-border))'
        }}>
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
            </div>
          ) : displayList.length === 0 ? (
            <div className="py-20 text-center">
              <Clock className="w-12 h-12 mx-auto mb-4" style={{ color: 'rgb(var(--theme-text-muted))', opacity: 0.5 }} />
              <h4 className="text-lg font-semibold mb-2" style={{ color: 'rgb(var(--theme-text))' }}>暂无查询记录</h4>
              <p className="text-sm" style={{ color: 'rgb(var(--theme-text-muted))' }}>开始使用智能问数来创建查询记录</p>
            </div>
          ) : (
          <>
            <table className="w-full" style={{ tableLayout: 'fixed', display: 'table', width: '100%' }}>
              <colgroup>
                <col style={{ width: '40px' }} />
                <col style={{ width: '40px' }} />
                <col style={{ width: '38%' }} />
                <col style={{ width: '12%' }} />
                <col style={{ width: '8%' }} />
                <col style={{ width: '8%' }} />
                <col style={{ width: '6%' }} />
                <col style={{ width: '12%' }} />
                <col style={{ width: '14%', minWidth: '120px' }} />
              </colgroup>
              <thead style={{ backgroundColor: 'rgb(var(--theme-bg-tertiary))', borderBottom: '1px solid rgb(var(--theme-border))' }}>
                <tr>
                  <th style={{ textAlign: 'center', padding: '12px 8px 12px 16px', width: '40px' }}>
                    <input
                      type="checkbox"
                      checked={displayList.length > 0 && selectedIds.size === displayList.length}
                      onChange={toggleSelectAll}
                      style={{ width: '16px', height: '16px', cursor: 'pointer', accentColor: 'rgb(var(--theme-primary))' }}
                    />
                  </th>
                  <th style={{ width: '40px' }}></th>
                  <th style={{ textAlign: 'center', padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))', width: '38%' }}>问题</th>
                  <th style={{ textAlign: 'left', padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))', width: '12%' }}>数据源</th>
                  <th style={{ textAlign: 'left', padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))', width: '8%' }}>耗时</th>
                  <th style={{ textAlign: 'left', padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))', width: '8%' }}>Token</th>
                  <th style={{ textAlign: 'center', padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))', width: '6%' }}>状态</th>
                  <th style={{ textAlign: 'center', padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))', width: '12%' }}>时间</th>
                  <th style={{ textAlign: 'center', padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))', width: '14%', minWidth: '120px' }}>操作</th>
                </tr>
              </thead>
              <tbody style={{ borderColor: 'rgb(var(--theme-border))' }}>
                {displayList.map(item => (
                  <tr key={item.id} className="transition-colors" style={{ borderBottom: '1px solid rgb(var(--theme-border))' }} onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(var(--theme-primary), 0.04)'; }} onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}>
                    <td style={{ textAlign: 'center', padding: '12px 8px 12px 16px', width: '40px' }}>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(item.id)}
                        onChange={() => toggleSelect(item.id)}
                        style={{ width: '16px', height: '16px', cursor: 'pointer', accentColor: 'rgb(var(--theme-primary))' }}
                      />
                    </td>
                    <td style={{ width: '40px' }}></td>
                    <td style={{ padding: '12px 16px', maxWidth: '450px' }}>
                      <p style={{ fontSize: '14px', color: 'rgb(var(--theme-text))', overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', lineHeight: '1.5', maxHeight: '3em' }}>{item.question}</p>
                      {/* 术语展开提示 */}
                      {item.term_rewrite_info?.enabled && (
                        <div
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            marginTop: '4px',
                            padding: '2px 8px',
                            fontSize: '11px',
                            color: 'rgb(139, 92, 246)',
                            backgroundColor: 'rgba(139, 92, 246, 0.1)',
                            borderRadius: '4px',
                            cursor: 'pointer',
                          }}
                          onClick={() => handleViewDetail(item)}
                          title="点击查看术语展开详情"
                        >
                          <Sparkles className="w-3 h-3" />
                          <span>术语展开 · 匹配 {item.term_rewrite_info.matched_count} 个</span>
                        </div>
                      )}
                      {item.sql && (
                        <div
                          title={item.sql}
                          style={{
                            fontSize: '12px',
                            color: 'rgb(var(--theme-text-muted))',
                            marginTop: '4px',
                            fontFamily: 'monospace',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            maxWidth: '420px',
                            cursor: 'default',
                          }}
                        >
                          {item.sql}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <Database className="w-3 h-3" style={{ color: 'rgb(var(--theme-text-muted))', flexShrink: 0 }} />
                          <span style={{ fontSize: '13px', color: 'rgb(var(--theme-text-secondary))', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.datasource_names.join(', ')}</span>
                        </div>
                        {item.source_datasource_ids && item.source_datasource_ids.length > 0 && (
                          <span
                            style={{
                              fontSize: '10px',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              fontWeight: 500,
                              display: 'inline-block',
                              width: 'fit-content',
                              backgroundColor: item.source_datasource_ids.length > 1 ? 'rgba(59, 130, 246, 0.15)' : 'rgba(22, 163, 74, 0.15)',
                              color: item.source_datasource_ids.length > 1 ? 'rgb(96, 165, 250)' : 'rgb(74, 222, 128)',
                            }}
                          >
                            {item.source_datasource_ids.length > 1 ? `多数据源 (${item.source_datasource_ids.length})` : '单数据源'}
                          </span>
                        )}
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px', fontSize: '13px', color: 'rgb(var(--theme-text-secondary))', whiteSpace: 'nowrap' }}>{formatDuration(item.total_duration_ms)}</td>
                    <td style={{ padding: '12px 16px', fontSize: '13px', color: 'rgb(var(--theme-text-secondary))', whiteSpace: 'nowrap' }}>{item.total_tokens.toLocaleString()}</td>
                    <td style={{ padding: '12px 16px' }}>{getStatusBadge(item.status)}</td>
                    <td style={{ padding: '12px 16px', fontSize: '13px', color: 'rgb(var(--theme-text-muted))', whiteSpace: 'nowrap' }}>{formatDate(item.created_at)}</td>
                    <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <button
                          onClick={() => handleViewDetail(item)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '6px 10px',
                            fontSize: '12px',
                            color: 'rgb(var(--theme-primary))',
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            borderRadius: '6px',
                            transition: 'all 0.15s ease',
                            whiteSpace: 'nowrap',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = 'rgba(var(--theme-primary), 0.1)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'transparent';
                          }}
                          title="查看详情"
                        >
                          <Eye className="w-4 h-4" style={{ flexShrink: 0 }} />
                          <span>详情</span>
                        </button>
                        <button
                          onClick={() => {
                            setCurrentDeleteId(item.id);
                            setDeleteType('single');
                            setDeleteModalVisible(true);
                          }}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '6px 10px',
                            fontSize: '12px',
                            color: '#ef4444',
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            borderRadius: '6px',
                            transition: 'all 0.15s ease',
                            whiteSpace: 'nowrap',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'transparent';
                          }}
                          title="删除"
                        >
                          <Trash2 className="w-4 h-4" style={{ flexShrink: 0 }} />
                          <span>删除</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* 批量操作栏 */}
            {selectedIds.size > 0 && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 16px',
                backgroundColor: 'rgb(var(--theme-bg-secondary))',
                borderTop: '1px solid rgb(var(--theme-border))',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '13px', color: 'rgb(var(--theme-text-secondary))' }}>
                    已选择 <strong style={{ color: 'rgb(var(--theme-primary))' }}>{selectedIds.size}</strong> 项
                  </span>
                  <button
                    onClick={() => setSelectedIds(new Set())}
                    style={{
                      fontSize: '12px',
                      color: 'rgb(var(--theme-text-muted))',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      textDecoration: 'underline',
                    }}
                  >
                    取消选择
                  </button>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button
                    onClick={() => {
                      setDeleteType('batch');
                      setDeleteModalVisible(true);
                    }}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '8px 14px',
                      fontSize: '13px',
                      color: '#ef4444',
                      backgroundColor: 'rgba(239, 68, 68, 0.1)',
                      border: '1px solid rgba(239, 68, 68, 0.3)',
                      borderRadius: '8px',
                      cursor: 'pointer',
                    }}
                  >
                    <Trash2 className="w-4 h-4" />
                    批量删除选中项
                  </button>
                </div>
              </div>
            )}

            {/* 批量清理工具栏 - 始终显示 */}
            {!loading && displayList.length > 0 && selectedIds.size === 0 && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                padding: '8px 16px',
                borderBottom: '1px solid rgb(var(--theme-border))',
              }}>
                <button
                  onClick={() => setBatchDeleteModalVisible(true)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '6px 12px',
                    fontSize: '12px',
                    color: 'rgb(var(--theme-text-secondary))',
                    backgroundColor: 'rgb(var(--theme-bg-secondary))',
                    border: '1px solid rgb(var(--theme-border))',
                    borderRadius: '6px',
                    cursor: 'pointer',
                  }}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  批量清理
                </button>
              </div>
            )}

            {/* 分页 */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-6 py-4 border-t" style={{ borderTopColor: 'rgb(var(--theme-border))' }}>
                <p className="text-sm" style={{ color: 'rgb(var(--theme-text-muted))' }}>共 {total} 条记录</p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: '8px',
                      border: '1px solid rgb(var(--theme-border))',
                      borderRadius: '8px',
                      color: 'rgb(var(--theme-text-secondary))',
                      backgroundColor: 'rgb(var(--theme-bg))',
                      cursor: page === 1 ? 'not-allowed' : 'pointer',
                      opacity: page === 1 ? 0.5 : 1,
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="px-3 py-1 text-sm" style={{ color: 'rgb(var(--theme-text)' }}>第 {page} / {totalPages} 页</span>
                  <button
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: '8px',
                      border: '1px solid rgb(var(--theme-border))',
                      borderRadius: '8px',
                      color: 'rgb(var(--theme-text-secondary))',
                      backgroundColor: 'rgb(var(--theme-bg))',
                      cursor: page === totalPages ? 'not-allowed' : 'pointer',
                      opacity: page === totalPages ? 0.5 : 1,
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
        </div>
      </div>

      {/* 详情弹窗 */}
      {detailModal && (
        <div
          style={{
            position: 'fixed',
            top: '0px',
            left: '0px',
            right: '0px',
            bottom: '0px',
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 99999,
            padding: '0px',
            margin: '0px',
            boxSizing: 'border-box',
            width: '100vw',
            height: '100vh',
            overflow: 'hidden',
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setDetailModal(null);
          }}
        >
          <div
            style={{
              backgroundColor: 'rgb(var(--theme-bg))',
              borderRadius: '16px',
              width: '100%',
              maxWidth: '950px',
              maxHeight: '90vh',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
              position: 'relative',
              zIndex: 100000,
              margin: '16px',
            }}
          >
            {/* 头部 */}
            <div 
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '16px 24px',
                borderBottom: '1px solid rgb(var(--theme-border))',
              }}
            >
              <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>查询详情</h3>
              <button 
                onClick={() => setDetailModal(null)} 
                style={{
                  padding: '8px',
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  borderRadius: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgb(var(--theme-bg-tertiary))'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              >
                <X className="w-5 h-5" style={{ color: 'rgb(var(--theme-text-muted))' }} />
              </button>
            </div>

            {/* 内容 */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
              {/* 基本信息 */}
              <section style={{ marginBottom: '24px' }}>
                <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(var(--theme-text))', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '4px', height: '16px', backgroundColor: 'rgb(var(--theme-primary))', borderRadius: '2px' }}></span>
                  基本信息
                </h4>
                <div style={{ backgroundColor: 'rgb(var(--theme-bg-secondary))', borderRadius: '12px', padding: '16px', border: '1px solid rgb(var(--theme-border))' }}>
                  {/* 问题 */}
                  <div style={{ marginBottom: '14px' }}>
                    <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))', marginBottom: '6px' }}>问题</p>
                    <p style={{ fontSize: '14px', color: 'rgb(var(--theme-text))', lineHeight: 1.6 }}>{detailModal.question}</p>
                  </div>

                  {/* 术语展开信息 */}
                  {detailModal.term_rewrite_info?.enabled && (
                    <div style={{ marginBottom: '14px' }}>
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '8px 12px',
                        backgroundColor: 'rgba(139, 92, 246, 0.1)',
                        borderRadius: '8px',
                        marginBottom: detailModal.term_rewrite_info.rewritten_question ? '8px' : 0,
                      }}>
                        <Sparkles className="w-4 h-4" style={{ color: 'rgb(139, 92, 246)' }} />
                        <span style={{ fontSize: '12px', fontWeight: 600, color: 'rgb(139, 92, 246)' }}>术语展开</span>
                        <span style={{ fontSize: '11px', color: 'rgb(139, 92, 246)', opacity: 0.8 }}>
                          匹配到 {detailModal.term_rewrite_info.matched_count} 个术语
                        </span>
                      </div>

                      {/* 展开后的问题 */}
                      {detailModal.term_rewrite_info.rewritten_question && (
                        <div style={{ marginBottom: '8px' }}>
                          <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>展开后的问题</p>
                          <p style={{ fontSize: '14px', color: 'rgb(var(--theme-text))', lineHeight: 1.6, padding: '8px 12px', backgroundColor: 'rgb(var(--theme-bg))', borderRadius: '6px', border: '1px solid rgb(var(--theme-border))' }}>
                            {detailModal.term_rewrite_info.rewritten_question}
                          </p>
                        </div>
                      )}

                      {/* 匹配的术语列表 */}
                      {detailModal.term_rewrite_info.matched_terms && detailModal.term_rewrite_info.matched_terms.length > 0 && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '200px', overflowY: 'auto' }}>
                          {detailModal.term_rewrite_info.matched_terms.map((term, index) => (
                            <div key={index} style={{
                              display: 'flex',
                              alignItems: 'flex-start',
                              gap: '8px',
                              padding: '8px 10px',
                              backgroundColor: 'rgb(var(--theme-bg))',
                              borderRadius: '6px',
                              border: '1px solid rgb(var(--theme-border))',
                            }}>
                              <BookOpen className="w-4 h-4" style={{ color: 'rgb(139, 92, 246)', marginTop: '2px', flexShrink: 0 }} />
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', marginBottom: '2px' }}>
                                  <span style={{ fontSize: '13px', fontWeight: 600, color: 'rgb(139, 92, 246)' }}>
                                    {term.term_name}
                                  </span>
                                  <span style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))' }}>
                                    ({term.matched_name})
                                  </span>
                                  <span style={{
                                    fontSize: '10px',
                                    padding: '2px 6px',
                                    backgroundColor: 'rgb(var(--theme-bg-secondary))',
                                    color: 'rgb(var(--theme-text-muted))',
                                    borderRadius: '4px',
                                  }}>
                                    {term.library_name}
                                  </span>
                                </div>
                                <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text-secondary))', margin: 0, lineHeight: 1.5 }}>
                                  {term.term_definition}
                                </p>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* SQL */}
                  <div style={{ marginBottom: '14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                      <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))', margin: 0 }}>
                        {detailModal.cluster_sqls && detailModal.cluster_sqls.length > 0 ? '各数据源 SQL' : 'SQL'}
                      </p>
                    </div>
                    {/* 如果有 cluster_sqls，展示每个数据源的 SQL */}
                    {detailModal.cluster_sqls && detailModal.cluster_sqls.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {detailModal.cluster_sqls.map((cluster, index) => (
                          <div key={index} style={{
                            backgroundColor: 'rgb(var(--theme-bg))',
                            borderRadius: '8px',
                            border: '1px solid rgb(var(--theme-border))',
                            overflow: 'hidden',
                          }}>
                            <div style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '8px 12px',
                              backgroundColor: 'rgb(var(--theme-bg-secondary))',
                              borderBottom: '1px solid rgb(var(--theme-border))',
                            }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <Database className="w-3.5 h-3.5" style={{ color: 'rgb(var(--theme-text-muted))' }} />
                                <span style={{ fontSize: '11px', fontWeight: 500, color: 'rgb(var(--theme-text-secondary))' }}>
                                  {cluster.datasource_names && cluster.datasource_names.length > 0
                                    ? cluster.datasource_names.join(', ')
                                    : cluster.datasource_ids && cluster.datasource_ids.length > 0
                                      ? `数据源 ${index + 1}`
                                      : (() => {
                                          const totalClusters = (detailModal.cluster_sqls?.length || 0) > 0
                                            ? detailModal.cluster_sqls!.length
                                            : 1;
                                          const sourceName = detailModal.source_datasource_names?.[index] 
                                            || detailModal.source_datasource_names?.[0] 
                                            || '未知数据源';
                                          return totalClusters > 1 ? `${sourceName} (${index + 1})` : sourceName;
                                        })()}
                                </span>
                                {cluster.table_names && cluster.table_names.length > 0 && (
                                  <span style={{ fontSize: '10px', color: 'rgb(var(--theme-text-muted))' }}>
                                    表: {cluster.table_names.join(', ')}
                                  </span>
                                )}
                              </div>
                              <button
                                onClick={() => handleCopy(cluster.sql, `cluster-sql-${index}`)}
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                  padding: '4px 8px',
                                  fontSize: '11px',
                                  color: copiedId === `cluster-sql-${index}` ? 'rgb(22, 163, 74)' : 'rgb(var(--theme-primary))',
                                  border: '1px solid',
                                  borderColor: copiedId === `cluster-sql-${index}` ? 'rgba(22, 163, 74, 0.3)' : 'rgba(var(--theme-primary), 0.3)',
                                  backgroundColor: copiedId === `cluster-sql-${index}` ? 'rgba(22, 163, 74, 0.1)' : 'rgba(var(--theme-primary), 0.08)',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                }}
                              >
                                {copiedId === `cluster-sql-${index}` ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                                {copiedId === `cluster-sql-${index}` ? '已复制' : '复制'}
                              </button>
                            </div>
                            <pre style={{
                              fontSize: '12px',
                              color: 'rgb(var(--theme-text))',
                              fontFamily: 'Monaco, Consolas, monospace',
                              padding: '10px 12px',
                              margin: 0,
                              lineHeight: 1.6,
                              maxHeight: '150px',
                              overflowY: 'auto',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-word',
                            }}>{formatSQL(cluster.sql)}</pre>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <pre style={{
                        fontSize: '12px',
                        color: 'rgb(var(--theme-text))',
                        fontFamily: 'Monaco, Consolas, monospace',
                        backgroundColor: 'rgb(var(--theme-bg))',
                        padding: '12px',
                        borderRadius: '8px',
                        border: '1px solid rgb(var(--theme-border))',
                        lineHeight: 1.8,
                        margin: 0,
                        maxHeight: '250px',
                        overflowY: 'auto',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                      }}>{formatSQL(detailModal.sql)}</pre>
                    )}
                  </div>

                  {/* 数据源、表、融合策略 - 卡片样式 */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px' }}>
                    <div style={{
                      backgroundColor: 'rgb(var(--theme-bg))',
                      borderRadius: '8px',
                      padding: '12px',
                      border: '1px solid rgb(var(--theme-border))'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                        <Layers className="w-3.5 h-3.5" style={{ color: 'rgb(var(--theme-text-muted))' }} />
                        <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', margin: 0 }}>来源数据源</p>
                      </div>
                      <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text))', fontWeight: 500, wordBreak: 'break-all', lineHeight: 1.4 }}>
                        {detailModal.source_datasource_names?.join(', ') || detailModal.datasource_names?.join(', ') || '-'}
                      </p>
                      {detailModal.source_datasource_ids && detailModal.source_datasource_ids.length > 1 && (
                        <span style={{
                          fontSize: '10px',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          fontWeight: 500,
                          display: 'inline-block',
                          marginTop: '4px',
                          backgroundColor: 'rgba(59, 130, 246, 0.15)',
                          color: 'rgb(96, 165, 250)',
                        }}>
                          多数据源 ({detailModal.source_datasource_ids.length})
                        </span>
                      )}
                    </div>
                    <div style={{
                      backgroundColor: 'rgb(var(--theme-bg))',
                      borderRadius: '8px',
                      padding: '12px',
                      border: '1px solid rgb(var(--theme-border))'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                        <Database className="w-3.5 h-3.5" style={{ color: 'rgb(var(--theme-text-muted))' }} />
                        <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', margin: 0 }}>涉及的数据源</p>
                      </div>
                      <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text))', fontWeight: 500, wordBreak: 'break-all', lineHeight: 1.4 }}>{detailModal.datasource_names.join(', ')}</p>
                    </div>
                    <div style={{
                      backgroundColor: 'rgb(var(--theme-bg))',
                      borderRadius: '8px',
                      padding: '12px',
                      border: '1px solid rgb(var(--theme-border))'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                        <Table className="w-3.5 h-3.5" style={{ color: 'rgb(var(--theme-text-muted))' }} />
                        <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', margin: 0 }}>涉及的表</p>
                      </div>
                      <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text))', fontWeight: 500, wordBreak: 'break-all', lineHeight: 1.4 }}>{detailModal.table_names.join(', ')}</p>
                    </div>
                    <div style={{
                      backgroundColor: 'rgb(var(--theme-bg))',
                      borderRadius: '8px',
                      padding: '12px',
                      border: '1px solid rgb(var(--theme-border))'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                        <Layers className="w-3.5 h-3.5" style={{ color: 'rgb(var(--theme-text-muted))' }} />
                        <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', margin: 0 }}>融合策略</p>
                      </div>
                      <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text))', fontWeight: 500, wordBreak: 'break-all', lineHeight: 1.4 }}>{detailModal.fusion_strategy}</p>
                    </div>
                  </div>
                </div>
              </section>

              {/* 性能 */}
              <section style={{ marginBottom: '24px' }}>
                <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(var(--theme-text))', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '4px', height: '16px', backgroundColor: '#10b981', borderRadius: '2px' }}></span>
                  性能指标
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '8px' }}>
                  {[
                    { label: '总耗时', value: detailModal.performance.total_duration_ms, color: 'rgb(16, 185, 129)', bg: 'rgba(16, 185, 129, 0.12)', border: 'rgba(16, 185, 129, 0.3)' },
                    { label: '向量检索', value: detailModal.performance.vector_search_ms, color: 'rgb(139, 92, 246)', bg: 'rgba(139, 92, 246, 0.12)', border: 'rgba(139, 92, 246, 0.3)' },
                    { label: '重排序', value: detailModal.performance.rerank_ms, color: 'rgb(236, 72, 153)', bg: 'rgba(236, 72, 153, 0.12)', border: 'rgba(236, 72, 153, 0.3)' },
                    { label: 'SQL生成', value: detailModal.performance.llm_gen_sql_ms, color: 'rgb(var(--theme-primary))', bg: 'rgba(var(--theme-primary), 0.12)', border: 'rgba(var(--theme-primary), 0.3)' },
                    { label: 'SQL执行', value: detailModal.performance.sql_execution_ms, color: 'rgb(59, 130, 246)', bg: 'rgba(59, 130, 246, 0.12)', border: 'rgba(59, 130, 246, 0.3)' },
                    { label: '融合', value: detailModal.performance.fusion_ms, color: 'rgb(14, 165, 233)', bg: 'rgba(14, 165, 233, 0.12)', border: 'rgba(14, 165, 233, 0.3)' },
                  ].map(item => (
                    <div key={item.label} style={{ backgroundColor: item.bg, borderRadius: '10px', padding: '10px 12px', border: `1px solid ${item.border}`, textAlign: 'center' }}>
                      <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>{item.label}</p>
                      <p style={{ fontSize: '13px', fontWeight: 700, color: item.color }}>{formatDuration(item.value)}</p>
                    </div>
                  ))}
                </div>
              </section>

              {/* Token */}
              <section style={{ marginBottom: '24px' }}>
                <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(var(--theme-text))', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '4px', height: '16px', backgroundColor: '#f59e0b', borderRadius: '2px' }}></span>
                  Token 消耗
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                  <div style={{ backgroundColor: 'rgb(var(--theme-bg-secondary))', borderRadius: '10px', padding: '12px', textAlign: 'center', border: '1px solid rgb(var(--theme-border))' }}>
                    <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>LLM输入</p>
                    <p style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))' }}>{detailModal.tokens.llm_prompt_tokens.toLocaleString()}</p>
                  </div>
                  <div style={{ backgroundColor: 'rgb(var(--theme-bg-secondary))', borderRadius: '10px', padding: '12px', textAlign: 'center', border: '1px solid rgb(var(--theme-border))' }}>
                    <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>LLM输出</p>
                    <p style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))' }}>{detailModal.tokens.llm_completion_tokens.toLocaleString()}</p>
                  </div>
                  <div style={{ backgroundColor: 'rgba(var(--theme-primary), 0.12)', borderRadius: '10px', padding: '12px', textAlign: 'center', border: '1px solid rgba(var(--theme-primary), 0.3)' }}>
                    <p style={{ fontSize: '11px', color: 'rgb(var(--theme-primary))', marginBottom: '4px', fontWeight: 600 }}>总计</p>
                    <p style={{ fontSize: '14px', fontWeight: 700, color: 'rgb(var(--theme-primary))' }}>{detailModal.tokens.total_tokens.toLocaleString()}</p>
                  </div>
                </div>
              </section>

              {/* 质量 */}
              <section style={{ marginBottom: '24px' }}>
                <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(var(--theme-text))', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '4px', height: '16px', backgroundColor: '#ec4899', borderRadius: '2px' }}></span>
                  召回质量
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '8px' }}>
                  <div style={{ backgroundColor: 'rgba(236, 72, 153, 0.12)', borderRadius: '10px', padding: '12px', textAlign: 'center', border: '1px solid rgba(236, 72, 153, 0.3)' }}>
                    <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>召回卡片</p>
                    <p style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(236, 72, 153)' }}>{detailModal.quality.cards_recalled}</p>
                  </div>
                  <div style={{ backgroundColor: 'rgba(236, 72, 153, 0.12)', borderRadius: '10px', padding: '12px', textAlign: 'center', border: '1px solid rgba(236, 72, 153, 0.3)' }}>
                    <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>重排卡片</p>
                    <p style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(236, 72, 153)' }}>{detailModal.quality.cards_reranked}</p>
                  </div>
                  <div style={{ backgroundColor: 'rgba(236, 72, 153, 0.12)', borderRadius: '10px', padding: '12px', textAlign: 'center', border: '1px solid rgba(236, 72, 153, 0.3)' }}>
                    <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>选中卡片</p>
                    <p style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(236, 72, 153)' }}>{detailModal.quality.cards_selected}</p>
                  </div>
                  <div style={{ backgroundColor: 'rgba(236, 72, 153, 0.12)', borderRadius: '10px', padding: '12px', textAlign: 'center', border: '1px solid rgba(236, 72, 153, 0.3)' }}>
                    <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>Top1得分</p>
                    <p style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(236, 72, 153)' }}>{detailModal.quality.top1_rerank_score?.toFixed(3) ?? '-'}</p>
                  </div>
                  <div style={{ backgroundColor: 'rgba(236, 72, 153, 0.12)', borderRadius: '10px', padding: '12px', textAlign: 'center', border: '1px solid rgba(236, 72, 153, 0.3)' }}>
                    <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>平均得分</p>
                    <p style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(236, 72, 153)' }}>{detailModal.quality.avg_rerank_score?.toFixed(3) ?? '-'}</p>
                  </div>
                </div>
              </section>

              {/* 数据卡片 */}
              <section style={{ marginBottom: '24px' }}>
                <div
                  onClick={() => toggleSection('data-cards')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    marginBottom: isSectionExpanded('data-cards') ? '12px' : 0,
                    padding: '10px 12px',
                    backgroundColor: isSectionExpanded('data-cards') ? 'rgb(var(--theme-bg-secondary))' : 'transparent',
                    borderRadius: isSectionExpanded('data-cards') ? '8px' : '0px',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(var(--theme-text))', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ width: '4px', height: '16px', backgroundColor: '#8b5cf6', borderRadius: '2px' }}></span>
                    数据卡片
                    {detailModal.full_response_result?.data_cards && detailModal.full_response_result.data_cards.length > 0 ? (
                      <span style={{
                        fontSize: '12px',
                        fontWeight: 500,
                        color: 'rgb(139, 92, 246)',
                        backgroundColor: 'rgba(139, 92, 246, 0.15)',
                        padding: '2px 8px',
                        borderRadius: '10px',
                        marginLeft: '8px',
                      }}>
                        {detailModal.full_response_result.data_cards.length} 个卡片
                      </span>
                    ) : (
                      <span style={{
                        fontSize: '12px',
                        fontWeight: 500,
                        color: 'rgb(var(--theme-text-muted))',
                        backgroundColor: 'rgb(var(--theme-bg-tertiary))',
                        padding: '2px 8px',
                        borderRadius: '10px',
                        marginLeft: '8px',
                      }}>
                        暂无数据
                      </span>
                    )}
                  </h4>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    color: 'rgb(var(--theme-text-muted))',
                    fontSize: '12px',
                  }}>
                    <span style={{ fontSize: '11px' }}>{isSectionExpanded('data-cards') ? '收起' : '展开'}</span>
                    <ChevronDown
                      className="w-4 h-4"
                      style={{
                        transform: isSectionExpanded('data-cards') ? 'rotate(180deg)' : 'rotate(0deg)',
                        transition: 'transform 0.2s ease',
                      }}
                    />
                  </div>
                </div>

                {isSectionExpanded('data-cards') && (
                  <>
                    {detailModal.full_response_result?.data_cards && detailModal.full_response_result.data_cards.length > 0 ? (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '12px' }}>
                        {detailModal.full_response_result.data_cards.map((card, index) => (
                          <div
                            key={card.doc_id || index}
                            style={{
                              backgroundColor: 'rgb(var(--theme-bg))',
                              border: '1px solid rgb(var(--theme-border))',
                              borderRadius: '12px',
                              padding: '16px',
                              transition: 'all 0.2s ease',
                              cursor: 'pointer',
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.borderColor = 'rgba(139, 92, 246, 0.5)';
                              e.currentTarget.style.boxShadow = '0 4px 12px rgba(139, 92, 246, 0.15)';
                              e.currentTarget.style.transform = 'translateY(-2px)';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.borderColor = 'rgb(var(--theme-border))';
                              e.currentTarget.style.boxShadow = 'none';
                              e.currentTarget.style.transform = 'translateY(0)';
                            }}
                            onClick={() => setSelectedCardDetail(card)}
                          >
                            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '10px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                <div style={{
                                  width: '32px',
                                  height: '32px',
                                  borderRadius: '8px',
                                  backgroundColor: 'rgba(139, 92, 246, 0.15)',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                }}>
                                  <FileText className="w-5 h-5" style={{ color: 'rgb(139, 92, 246)' }} />
                                </div>
                                <div style={{ minWidth: 0 }}>
                                  <p style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(var(--theme-text))', margin: 0, lineHeight: 1.3 }}>{getCardName(card)}</p>
                                </div>
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                {card.score !== undefined && (
                                  <div style={{
                                    fontSize: '11px',
                                    fontWeight: 600,
                                    color: 'rgb(139, 92, 246)',
                                    backgroundColor: 'rgba(139, 92, 246, 0.15)',
                                    padding: '2px 6px',
                                    borderRadius: '4px',
                                  }}>
                                    {card.score.toFixed(2)}
                                  </div>
                                )}
                                <div style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '2px',
                                  fontSize: '11px',
                                  color: 'rgb(var(--theme-text-muted))',
                                }}>
                                  <Info className="w-3 h-3" />
                                  <span>详情</span>
                                </div>
                              </div>
                            </div>

                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '10px' }}>
                              <span style={{
                                fontSize: '11px',
                                color: 'rgb(var(--theme-text-secondary))',
                                backgroundColor: 'rgb(var(--theme-bg-tertiary))',
                                padding: '3px 8px',
                                borderRadius: '4px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                              }}>
                                <Database className="w-3 h-3" />
                                {getCardDatasource(card)}
                              </span>
                              {card.table_name && (
                                <span style={{
                                  fontSize: '11px',
                                  color: 'rgb(var(--theme-text-secondary))',
                                  backgroundColor: 'rgb(var(--theme-bg-tertiary))',
                                  padding: '3px 8px',
                                  borderRadius: '4px',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                }}>
                                  <Table className="w-3 h-3" />
                                  {card.table_name}
                                </span>
                              )}
                            </div>

                            {getCardColumns(card).length > 0 && (
                              <div style={{ marginBottom: '8px' }}>
                                <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>字段：</p>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                  {getCardColumns(card).slice(0, 6).map((col, i) => (
                                    <span key={i} style={{
                                      fontSize: '11px',
                                      color: 'rgb(var(--theme-text-secondary))',
                                      backgroundColor: 'rgb(var(--theme-bg-secondary))',
                                      padding: '2px 6px',
                                      borderRadius: '4px',
                                      fontFamily: 'Monaco, Consolas, monospace',
                                    }}>
                                      {col}
                                    </span>
                                  ))}
                                  {getCardColumns(card).length > 6 && (
                                    <span style={{
                                      fontSize: '11px',
                                      color: 'rgb(var(--theme-text-muted))',
                                      padding: '2px 4px',
                                    }}>
                                      +{getCardColumns(card).length - 6}
                                    </span>
                                  )}
                                </div>
                              </div>
                            )}

                            {getCardPreview(card) && (
                              <p style={{
                                fontSize: '12px',
                                color: 'rgb(var(--theme-text-muted))',
                                lineHeight: 1.5,
                                margin: 0,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                              }}>
                                {getCardPreview(card)}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{
                        backgroundColor: 'rgb(var(--theme-bg-secondary))',
                        borderRadius: '12px',
                        padding: '24px',
                        border: '1px dashed rgb(var(--theme-border))',
                        textAlign: 'center',
                      }}>
                        <FileText className="w-8 h-8" style={{ color: 'rgb(var(--theme-text-muted))', margin: '0 auto 8px', opacity: 0.5 }} />
                        <p style={{ fontSize: '13px', color: 'rgb(var(--theme-text-muted))', margin: 0 }}>
                          {detailModal.full_response_result ? '该查询未检索到相关数据卡片' : '数据卡片信息暂不可用'}
                        </p>
                      </div>
                    )}
                  </>
                )}
              </section>

              {/* 查询结果 */}
              <section style={{ marginBottom: '24px' }}>
                <div
                  onClick={() => toggleSection('query-results')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    marginBottom: isSectionExpanded('query-results') ? '12px' : 0,
                    padding: '10px 12px',
                    backgroundColor: isSectionExpanded('query-results') ? 'rgb(var(--theme-bg-secondary))' : 'transparent',
                    borderRadius: isSectionExpanded('query-results') ? '8px' : '0px',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(var(--theme-text))', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ width: '4px', height: '16px', backgroundColor: '#06b6d4', borderRadius: '2px' }}></span>
                    查询结果
                    {detailModal.result.result_count > 0 ? (
                      <span style={{
                        fontSize: '12px',
                        fontWeight: 500,
                        color: 'rgb(14, 165, 233)',
                        backgroundColor: 'rgba(14, 165, 233, 0.15)',
                        padding: '2px 8px',
                        borderRadius: '10px',
                        marginLeft: '8px',
                      }}>
                        {detailModal.result.result_count} 条结果
                      </span>
                    ) : (
                      <span style={{
                        fontSize: '12px',
                        fontWeight: 500,
                        color: 'rgb(var(--theme-text-muted))',
                        backgroundColor: 'rgb(var(--theme-bg-tertiary))',
                        padding: '2px 8px',
                        borderRadius: '10px',
                        marginLeft: '8px',
                      }}>
                        暂无结果
                      </span>
                    )}
                  </h4>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    color: 'rgb(var(--theme-text-muted))',
                    fontSize: '12px',
                  }}>
                    <span style={{ fontSize: '11px' }}>{isSectionExpanded('query-results') ? '收起' : '展开'}</span>
                    <ChevronDown
                      className="w-4 h-4"
                      style={{
                        transform: isSectionExpanded('query-results') ? 'rotate(180deg)' : 'rotate(0deg)',
                        transition: 'transform 0.2s ease',
                      }}
                    />
                  </div>
                </div>

                {isSectionExpanded('query-results') && (
                  <>
                    {detailModal.full_response_result?.final_rows && detailModal.full_response_result.final_rows.length > 0 ? (
                      <div>
                        {/* 融合信息 */}
                        {detailModal.full_response_result.merge && (
                          <div style={{
                            backgroundColor: 'rgba(22, 163, 74, 0.12)',
                            border: '1px solid rgba(22, 163, 74, 0.3)',
                            borderRadius: '10px',
                            padding: '12px 14px',
                            marginBottom: '12px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '12px',
                            flexWrap: 'wrap',
                          }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <Layers className="w-4 h-4" style={{ color: 'rgb(22, 163, 74)' }} />
                              <span style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>融合策略：</span>
                              <span style={{ fontSize: '12px', fontWeight: 600, color: 'rgb(22, 163, 74)' }}>
                                {detailModal.full_response_result.merge.strategy || detailModal.fusion_strategy}
                              </span>
                            </div>
                            {detailModal.full_response_result.merge.fusion_method && (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>融合方式：</span>
                                <span style={{ fontSize: '12px', fontWeight: 500, color: 'rgb(22, 163, 74)' }}>
                                  {detailModal.full_response_result.merge.fusion_method}
                                </span>
                              </div>
                            )}
                            {detailModal.full_response_result.merge.entity_key && (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>实体字段：</span>
                                <code style={{ fontSize: '11px', fontFamily: 'Monaco, Consolas, monospace', backgroundColor: 'rgba(22, 163, 74, 0.15)', padding: '2px 6px', borderRadius: '4px', color: 'rgb(22, 163, 74)' }}>
                                  {detailModal.full_response_result.merge.entity_key}
                                </code>
                              </div>
                            )}
                          </div>
                        )}

                        {/* 结果表格 */}
                        <div style={{ overflowX: 'auto', border: '1px solid rgb(var(--theme-border))', borderRadius: '12px' }}>
                          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                            <thead>
                              <tr style={{ backgroundColor: 'rgb(var(--theme-bg-tertiary))' }}>
                                {Object.keys(detailModal.full_response_result.final_rows[0] || {}).map((key, index) => (
                                  <th
                                    key={key}
                                    style={{
                                      padding: '10px 12px',
                                      textAlign: 'left',
                                      fontWeight: 600,
                                      color: 'rgb(var(--theme-text-secondary))',
                                      borderBottom: '1px solid rgb(var(--theme-border))',
                                      whiteSpace: 'nowrap',
                                      backgroundColor: index === 0 ? 'rgb(var(--theme-bg-secondary))' : 'rgb(var(--theme-bg-tertiary))',
                                    }}
                                  >
                                    {key}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {detailModal.full_response_result.final_rows.slice(0, 30).map((row, rowIndex) => (
                                <tr
                                  key={rowIndex}
                                  style={{
                                    backgroundColor: rowIndex % 2 === 0 ? 'rgb(var(--theme-bg))' : 'rgb(var(--theme-bg-secondary))',
                                  }}
                                  onMouseEnter={(e) => {
                                    e.currentTarget.style.backgroundColor = 'rgba(22, 163, 74, 0.08)';
                                  }}
                                  onMouseLeave={(e) => {
                                    e.currentTarget.style.backgroundColor = rowIndex % 2 === 0 ? 'rgb(var(--theme-bg))' : 'rgb(var(--theme-bg-secondary))';
                                  }}
                                >
                                  {Object.entries(row).map(([key, value], colIndex) => (
                                    <td
                                      key={key}
                                      style={{
                                        padding: '8px 12px',
                                        color: 'rgb(var(--theme-text))',
                                        borderBottom: '1px solid rgb(var(--theme-border))',
                                        maxWidth: '200px',
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        whiteSpace: 'nowrap',
                                        backgroundColor: colIndex === 0 ? 'rgb(var(--theme-bg-secondary))' : 'transparent',
                                      }}
                                      title={String(value ?? '')}
                                    >
                                      {value === null || value === undefined ? (
                                        <span style={{ color: 'rgb(var(--theme-text-muted))', fontStyle: 'italic' }}>null</span>
                                      ) : typeof value === 'object' ? (
                                        <span 
                                          style={{ 
                                            color: 'rgb(var(--theme-text-muted))',
                                            fontFamily: 'Monaco, Consolas, monospace',
                                            fontSize: '12px',
                                          }} 
                                          title={JSON.stringify(value, null, 2)}
                                        >
                                          {JSON.stringify(value)}
                                        </span>
                                      ) : (
                                        String(value)
                                      )}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {detailModal.full_response_result.final_rows.length > 10 && (
                            <div style={{
                              padding: '10px',
                              textAlign: 'center',
                              borderTop: '1px solid rgb(var(--theme-border))',
                              backgroundColor: 'rgb(var(--theme-bg-secondary))',
                            }}>
                              <span style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>
                                仅显示前 30 条结果，共 {detailModal.full_response_result.final_rows.length} 条
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div style={{
                        backgroundColor: 'rgb(var(--theme-bg-secondary))',
                        borderRadius: '12px',
                        padding: '24px',
                        border: '1px dashed rgb(var(--theme-border))',
                        textAlign: 'center',
                      }}>
                        <Table className="w-8 h-8" style={{ color: 'rgb(var(--theme-text-muted))', margin: '0 auto 8px', opacity: 0.5 }} />
                        <p style={{ fontSize: '13px', color: 'rgb(var(--theme-text-muted))', margin: 0 }}>
                          {detailModal.full_response_result ? '该查询未返回结果数据' : '结果数据暂不可用'}
                        </p>
                      </div>
                    )}
                  </>
                )}
              </section>

              {/* 错误信息 */}
              {detailModal.error_message && (
                <section style={{
                  backgroundColor: 'rgba(220, 38, 38, 0.12)',
                  borderRadius: '12px',
                  padding: '16px',
                  border: '1px solid rgba(220, 38, 38, 0.3)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'rgb(220, 38, 38)', fontWeight: 600, marginBottom: '8px' }}>
                    <AlertCircle className="w-4 h-4" />
                    错误信息
                  </div>
                  <p style={{ fontSize: '14px', color: 'rgb(220, 38, 38)', lineHeight: 1.6 }}>{detailModal.error_message}</p>
                </section>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 数据卡片详情弹窗 */}
      {selectedCardDetail && (
          <div
            style={{
              position: 'fixed',
              top: '0px',
              left: '0px',
              right: '0px',
              bottom: '0px',
              backgroundColor: 'rgba(0, 0, 0, 0.6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 100001,
              padding: '0px',
              margin: '0px',
              boxSizing: 'border-box',
              width: '100vw',
              height: '100vh',
              overflow: 'hidden',
            }}
            onClick={(e) => {
              if (e.target === e.currentTarget) setSelectedCardDetail(null);
            }}
          >
            <div
              style={{
                backgroundColor: 'rgb(var(--theme-bg))',
                borderRadius: '16px',
                width: '100%',
                maxWidth: '700px',
                maxHeight: '85vh',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
                position: 'relative',
                zIndex: 100002,
                margin: '16px',
              }}
            >
              {/* 头部 */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '16px 24px',
                  borderBottom: '1px solid rgb(var(--theme-border))',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: '8px',
                    backgroundColor: 'rgba(139, 92, 246, 0.15)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}>
                    <FileText className="w-5 h-5" style={{ color: 'rgb(139, 92, 246)' }} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'rgb(var(--theme-text))', margin: 0 }}>{getCardName(selectedCardDetail)}</h3>
                    <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))', margin: 0 }}>数据卡片详情</p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedCardDetail(null)}
                  style={{
                    padding: '8px',
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    borderRadius: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgb(var(--theme-bg-tertiary))'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                  <X className="w-5 h-5" style={{ color: 'rgb(var(--theme-text-muted))' }} />
                </button>
              </div>

              {/* 内容 */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
                {/* 基本信息 */}
                <section style={{ marginBottom: '20px' }}>
                  <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Info className="w-4 h-4" />
                    基本信息
                  </h4>
                  <div style={{ backgroundColor: 'rgb(var(--theme-bg-secondary))', borderRadius: '10px', padding: '14px', border: '1px solid rgb(var(--theme-border))' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
                      <div>
                        <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>数据源</p>
                        <p style={{ fontSize: '13px', color: 'rgb(var(--theme-text))', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <Database className="w-3.5 h-3.5" style={{ color: 'rgb(var(--theme-text-muted))' }} />
                          {getCardDatasource(selectedCardDetail)}
                        </p>
                      </div>
                      <div>
                        <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>表名</p>
                        <p style={{ fontSize: '13px', color: 'rgb(var(--theme-text))', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <Table className="w-3.5 h-3.5" style={{ color: 'rgb(var(--theme-text-muted))' }} />
                          {selectedCardDetail.table_name}
                        </p>
                      </div>
                      {selectedCardDetail.doc_id && (
                        <div>
                          <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>文档ID</p>
                          <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))', fontFamily: 'Monaco, Consolas, monospace', wordBreak: 'break-all' }}>
                            {selectedCardDetail.doc_id}
                          </p>
                        </div>
                      )}
                      {selectedCardDetail.card_content?.DocInfo?.domain && (
                        <div>
                          <p style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>领域</p>
                          <p style={{ fontSize: '13px', color: 'rgb(var(--theme-text))', fontWeight: 500 }}>
                            {selectedCardDetail.card_content.DocInfo.domain}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </section>

                {/* 摘要描述 */}
                {(selectedCardDetail.card_content?.Abstract || selectedCardDetail.card_content?.DocInfo?.abstract || selectedCardDetail.description) && (
                  <section style={{ marginBottom: '20px' }}>
                    <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <FileText className="w-4 h-4" />
                      摘要描述
                    </h4>
                    <div style={{
                      backgroundColor: 'rgba(234, 179, 8, 0.1)',
                      borderRadius: '10px',
                      padding: '14px',
                      border: '1px solid rgba(234, 179, 8, 0.3)',
                    }}>
                      <p style={{
                        fontSize: '13px',
                        color: 'rgb(var(--theme-text))',
                        lineHeight: 1.7,
                        margin: 0,
                        textIndent: '2em'
                      }}>
                        {selectedCardDetail.card_content?.Abstract || selectedCardDetail.card_content?.DocInfo?.abstract || selectedCardDetail.description}
                      </p>
                    </div>
                  </section>
                )}

                {/* 字段信息 */}
                {selectedCardDetail.card_content?.SQLMeta?.columns && selectedCardDetail.card_content.SQLMeta.columns.length > 0 && (
                  <section style={{ marginBottom: '20px' }}>
                    <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Columns className="w-4 h-4" />
                      字段列表
                    </h4>
                    <div style={{ overflowX: 'auto', border: '1px solid rgb(var(--theme-border))', borderRadius: '10px' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr style={{ backgroundColor: 'rgb(var(--theme-bg-tertiary))' }}>
                            <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: '11px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))', borderBottom: '1px solid rgb(var(--theme-border))', whiteSpace: 'nowrap' }}>字段名</th>
                            <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: '11px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))', borderBottom: '1px solid rgb(var(--theme-border))', whiteSpace: 'nowrap' }}>类型</th>
                            <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: '11px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))', borderBottom: '1px solid rgb(var(--theme-border))' }}>注释</th>
                            <th style={{ padding: '10px 12px', textAlign: 'center', fontSize: '11px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))', borderBottom: '1px solid rgb(var(--theme-border))', whiteSpace: 'nowrap' }}>主键</th>
                            <th style={{ padding: '10px 12px', textAlign: 'center', fontSize: '11px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))', borderBottom: '1px solid rgb(var(--theme-border))', whiteSpace: 'nowrap' }}>外键</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedCardDetail.card_content.SQLMeta.columns.map((col, index) => (
                            <tr key={index} style={{ backgroundColor: index % 2 === 0 ? 'rgb(var(--theme-bg))' : 'rgb(var(--theme-bg-secondary))' }}>
                              <td style={{ padding: '8px 12px', fontSize: '12px', color: 'rgb(var(--theme-text))', fontFamily: 'Monaco, Consolas, monospace', borderBottom: '1px solid rgb(var(--theme-border))', whiteSpace: 'nowrap' }}>
                                {col.is_primary && <Key className="w-3 h-3 inline mr-1" style={{ color: 'rgb(245, 158, 11)' }} />}
                                {col.name}
                              </td>
                              <td style={{ padding: '8px 12px', fontSize: '12px', color: 'rgb(var(--theme-text-secondary))', fontFamily: 'Monaco, Consolas, monospace', borderBottom: '1px solid rgb(var(--theme-border))', whiteSpace: 'nowrap' }}>{col.type}</td>
                              <td style={{ padding: '8px 12px', fontSize: '12px', color: 'rgb(var(--theme-text-secondary))', borderBottom: '1px solid rgb(var(--theme-border))' }}>{col.comment || '-'}</td>
                              <td style={{ padding: '8px 12px', fontSize: '12px', textAlign: 'center', borderBottom: '1px solid rgb(var(--theme-border))' }}>
                                {col.is_primary ? <CheckCircle className="w-4 h-4" style={{ color: 'rgb(22, 163, 74)', margin: '0 auto' }} /> : <span style={{ color: 'rgb(var(--theme-text-muted))' }}>-</span>}
                              </td>
                              <td style={{ padding: '8px 12px', fontSize: '12px', textAlign: 'center', borderBottom: '1px solid rgb(var(--theme-border))' }}>
                                {col.is_foreign ? <CheckCircle className="w-4 h-4" style={{ color: 'rgb(var(--theme-primary))', margin: '0 auto' }} /> : <span style={{ color: 'rgb(var(--theme-text-muted))' }}>-</span>}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                )}

                {/* Tags */}
                {selectedCardDetail.card_content?.Tags && selectedCardDetail.card_content.Tags.length > 0 && (
                  <section>
                    <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'rgb(var(--theme-text-secondary))', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Tag className="w-4 h-4" />
                      标签
                    </h4>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                      {selectedCardDetail.card_content.Tags.map((tag, index) => (
                        <span
                          key={index}
                          style={{
                            fontSize: '12px',
                            color: 'rgb(var(--theme-text-secondary))',
                            backgroundColor: 'rgb(var(--theme-bg-tertiary))',
                            padding: '4px 10px',
                            borderRadius: '6px',
                          }}
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </section>
                )}
              </div>
            </div>
          </div>
        )}

      {/* 单条删除确认弹窗 */}
      {deleteModalVisible && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div style={{
            backgroundColor: 'rgb(var(--theme-bg))',
            borderRadius: '16px',
            padding: '24px',
            maxWidth: '400px',
            width: '90%',
            border: '1px solid rgb(var(--theme-border))'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
              <div style={{
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                backgroundColor: 'rgba(239, 68, 68, 0.12)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <Trash2 className="w-5 h-5" style={{ color: 'rgb(220, 38, 38)' }} />
              </div>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'rgb(var(--theme-text))', margin: 0 }}>
                {deleteType === 'single' ? '确认删除' : '确认批量删除'}
              </h3>
            </div>
            <p style={{ fontSize: '14px', color: 'rgb(var(--theme-text-muted))', marginBottom: '24px', lineHeight: 1.6 }}>
              {deleteType === 'single'
                ? '确定要删除这条查询记录吗？删除后无法恢复。'
                : `确定要删除选中的 ${selectedIds.size} 条查询记录吗？删除后无法恢复。`
              }
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                onClick={() => setDeleteModalVisible(false)}
                disabled={deleteLoading}
                style={{
                  padding: '10px 20px',
                  fontSize: '14px',
                  color: 'rgb(var(--theme-text-secondary))',
                  backgroundColor: 'rgb(var(--theme-bg-secondary))',
                  border: '1px solid rgb(var(--theme-border))',
                  borderRadius: '8px',
                  cursor: deleteLoading ? 'not-allowed' : 'pointer',
                  opacity: deleteLoading ? 0.6 : 1,
                }}
              >
                取消
              </button>
              <button
                onClick={async () => {
                  if (deleteType === 'single') {
                    await handleDeleteSingle(currentDeleteId);
                  } else {
                    await handleBatchDeleteSelected();
                  }
                  setDeleteModalVisible(false);
                }}
                disabled={deleteLoading}
                style={{
                  padding: '10px 20px',
                  fontSize: '14px',
                  color: '#ffffff',
                  backgroundColor: 'rgb(220, 38, 38)',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: deleteLoading ? 'not-allowed' : 'pointer',
                  opacity: deleteLoading ? 0.6 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                {deleteLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                确定删除
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 批量删除弹窗 */}
      {batchDeleteModalVisible && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div style={{
            backgroundColor: 'rgb(var(--theme-bg))',
            borderRadius: '16px',
            padding: '24px',
            maxWidth: '450px',
            width: '90%',
            border: '1px solid rgb(var(--theme-border))'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
              <div style={{
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                backgroundColor: 'rgba(239, 68, 68, 0.12)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <Trash2 className="w-5 h-5" style={{ color: 'rgb(220, 38, 38)' }} />
              </div>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'rgb(var(--theme-text))', margin: 0 }}>批量删除</h3>
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ fontSize: '13px', color: 'rgb(var(--theme-text-secondary))', marginBottom: '8px', display: 'block' }}>删除方式</label>
              <div style={{ display: 'flex', gap: '12px', marginBottom: '16px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                  <input
                    type="radio"
                    name="deleteOption"
                    checked={batchDeleteOption === 'before_date'}
                    onChange={() => setBatchDeleteOption('before_date')}
                    style={{ accentColor: 'rgb(var(--theme-primary))' }}
                  />
                  <span style={{ fontSize: '13px', color: 'rgb(var(--theme-text))' }}>指定日期之前</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                  <input
                    type="radio"
                    name="deleteOption"
                    checked={batchDeleteOption === 'keep_days'}
                    onChange={() => setBatchDeleteOption('keep_days')}
                    style={{ accentColor: 'rgb(var(--theme-primary))' }}
                  />
                  <span style={{ fontSize: '13px', color: 'rgb(var(--theme-text))' }}>保留最近N天</span>
                </label>
              </div>

              {batchDeleteOption === 'before_date' ? (
                <input
                  type="date"
                  value={batchDeleteDate}
                  onChange={(e) => setBatchDeleteDate(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    fontSize: '14px',
                    border: '1px solid rgb(var(--theme-border))',
                    borderRadius: '8px',
                    outline: 'none',
                    backgroundColor: 'rgb(var(--theme-bg-secondary))',
                    color: 'rgb(var(--theme-text))',
                  }}
                />
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '13px', color: 'rgb(var(--theme-text-muted))' }}>保留最近</span>
                  <input
                    type="number"
                    value={batchDeleteDays}
                    onChange={(e) => setBatchDeleteDays(parseInt(e.target.value) || 30)}
                    min="1"
                    style={{
                      width: '80px',
                      padding: '8px 12px',
                      fontSize: '14px',
                      border: '1px solid rgb(var(--theme-border))',
                      borderRadius: '8px',
                      outline: 'none',
                      textAlign: 'center',
                      backgroundColor: 'rgb(var(--theme-bg-secondary))',
                      color: 'rgb(var(--theme-text))',
                    }}
                  />
                  <span style={{ fontSize: '13px', color: 'rgb(var(--theme-text-muted))' }}>天的记录</span>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                onClick={() => setBatchDeleteModalVisible(false)}
                disabled={deleteLoading}
                style={{
                  padding: '10px 20px',
                  fontSize: '14px',
                  color: 'rgb(var(--theme-text-secondary))',
                  backgroundColor: 'rgb(var(--theme-bg-secondary))',
                  border: '1px solid rgb(var(--theme-border))',
                  borderRadius: '8px',
                  cursor: deleteLoading ? 'not-allowed' : 'pointer',
                  opacity: deleteLoading ? 0.6 : 1,
                }}
              >
                取消
              </button>
              <button
                onClick={handleBatchDelete}
                disabled={deleteLoading || (batchDeleteOption === 'before_date' && !batchDeleteDate)}
                style={{
                  padding: '10px 20px',
                  fontSize: '14px',
                  color: '#ffffff',
                  backgroundColor: 'rgb(220, 38, 38)',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: (deleteLoading || (batchDeleteOption === 'before_date' && !batchDeleteDate)) ? 'not-allowed' : 'pointer',
                  opacity: (deleteLoading || (batchDeleteOption === 'before_date' && !batchDeleteDate)) ? 0.6 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                {deleteLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 加载详情 */}
      {detailLoading && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="rounded-[20px] p-8" style={{ backgroundColor: 'rgb(var(--theme-bg))' }}>
            <Loader2 className="w-8 h-8 animate-spin" style={{ color: 'rgb(var(--theme-primary))' }} />
          </div>
        </div>
      )}
    </div>
  );
};

function StatCard({ title, value, icon, color, suffix }: {
  title: string
  value: string | number
  icon: React.ReactNode
  color: 'indigo' | 'green' | 'red' | 'blue'
  suffix?: string
}) {
  const colors = {
    indigo: { bg: 'rgba(var(--theme-primary), 0.12)', color: 'rgb(var(--theme-primary))' },
    green: { bg: 'rgba(22, 163, 74, 0.12)', color: 'rgb(22, 163, 74)' },
    red: { bg: 'rgba(220, 38, 38, 0.12)', color: 'rgb(220, 38, 38)' },
    blue: { bg: 'rgba(59, 130, 246, 0.12)', color: 'rgb(59, 130, 246)' },
  };
  return (
    <div className="rounded-[12px] border p-3" style={{
      backgroundColor: 'rgb(var(--theme-bg))',
      borderColor: 'rgb(var(--theme-border))'
    }}>
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-[8px] flex items-center justify-center" style={{
          backgroundColor: colors[color].bg,
          color: colors[color].color
        }}>
          {icon}
        </div>
        <div>
          <p className="text-[11px]" style={{ color: 'rgb(var(--theme-text-muted))' }}>{title}</p>
          <div className="flex items-baseline gap-2">
            <p className="text-base font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>{value}</p>
            {suffix && <p className="text-[11px] font-medium" style={{ color: 'rgb(22, 163, 74)' }}>{suffix}</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

export default QueryHistoryPage;
