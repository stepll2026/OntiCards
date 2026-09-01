'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useRouter } from 'next-nprogress-bar';
import { message } from 'antd';
import {
  Database,
  Table,
  CreditCard,
  Search,
  MessageSquare,
  Plus,
  ChevronRight,
  PlayCircle,
  Server,
  FileText,
  CheckCircle,
  X,
  ExternalLink,
  Info,
  RefreshCw,
  Settings,
  ArrowRight,
  Sparkles,
  Code,
  BarChart3,
  Bot,
  Layers,
  Lightbulb,
  FileDown,
  Bell,
  Gauge,
  Share2,
  LayoutDashboard,
  Zap,
  BookOpen,
  ClipboardList,
} from 'lucide-react';

// 检测是否为深色模式
const useDarkMode = () => {
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const checkDark = () => {
      const dark = document.documentElement.getAttribute('data-theme') === 'dark';
      setIsDark(dark);
    };

    checkDark();

    const observer = new MutationObserver(checkDark);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme']
    });

    return () => observer.disconnect();
  }, []);

  return isDark;
};

// 数据库类型对应的图标（与添加数据源弹框保持一致）
const getDbTypeIcon = (dbType: string) => {
  const type = dbType?.toLowerCase() || '';
  if (type.includes('mysql')) {
    return { icon: '🐬', bg: 'from-sky-50 to-sky-100' };
  }
  if (type.includes('postgres')) {
    return { icon: '🐘', bg: 'from-blue-50 to-indigo-50' };
  }
  if (type.includes('oracle')) {
    return { icon: '🔶', bg: 'from-amber-50 to-amber-100' };
  }
  if (type.includes('sql server') || type.includes('mssql')) {
    return { icon: '🏢', bg: 'from-purple-50 to-purple-100' };
  }
  if (type.includes('trino')) {
    return { icon: '🐰', bg: 'from-cyan-50 to-cyan-100' };
  }
  if (type.includes('sqlite')) {
    return { icon: '📄', bg: 'from-slate-50 to-slate-100' };
  }
  if (type.includes('kingbase')) {
    return { icon: '🛡️', bg: 'from-teal-50 to-teal-100' };
  }
  if (type.includes('oceanbase')) {
    return { icon: '🌊', bg: 'from-sky-50 to-sky-100' };
  }
  if (type.includes('dm') || type.includes('达梦')) {
    return { icon: '💠', bg: 'from-indigo-50 to-indigo-100' };
  }
  // 默认
  return { icon: '🗄️', bg: 'from-blue-50 to-indigo-50' };
};

// 解析连接字符串
const parseConnectInfo = (connectInfo: string): {
  username: string;
  password: string;
  host: string;
  port: number;
  database: string;
  serviceName?: string;
} | null => {
  if (!connectInfo) return null;
  try {
    // 支持多种数据库连接字符串格式：
    // 1. mysql+pymysql://user:pass@host:port/db
    // 2. postgresql://user:pass@host:port/db
    // 3. dm+dmPython://user:pass@host:port/db (达梦)
    // 4. 带 service_name 参数的格式
    // 5. 用户名中可能包含 URL 编码的字符（如 OceanBase 的 root%40tenant）
    const match = connectInfo.match(/^(\w+)\+?(\w+)?:\/\/([^:@]+):([^@]+)@([^:]+):(\d+)\/?([^?]*)(?:\?service_name=([^&\s]+))?$/);
    if (match) {
      const [, , , username, password, host, port, database, serviceName] = match;
      return {
        // 对用户名和密码进行 URL 解码
        username: decodeURIComponent(username),
        password: decodeURIComponent(password),
        host,
        port: parseInt(port, 10),
        database: database || '',
        serviceName: serviceName || undefined,
      };
    }
    return null;
  } catch {
    return null;
  }
};

// 密码脱敏
const maskPassword = (password: string) => {
  if (!password) return '';
  return '••••••••';
};

import { Modal } from 'antd';
import AddDataSourceModal from '@/components/business/AddDataSourceModal';
import DataConsumeScenariosModal, { ScenarioType } from '@/components/business/DataConsumeScenariosModal';
import { DataSourceItem, updateDataSourceName } from '@/api/datasource';
import { useDataSources } from '@/hooks/useDataSources';
import { useUserInfo } from '@/hooks';
import { setLoggingOut } from '@/api/base';
import { getUserInfo } from '@/api/user';
import { setUserInfoInitialized, notifySSOTokenStored } from '@/hooks/useUserInfo';
import type { UserInfoType } from '@/context/homeContext';
import { Loader2 } from 'lucide-react';

// SSO回调处理逻辑（适用于Overview页面）
const handleSSOCallback = async (): Promise<boolean> => {
  const params = new URLSearchParams(window.location.search);
  const accessToken = params.get('access_token');

  if (!accessToken) {
    return false;
  }

  // 将SSO返回的access_token存入localStorage
  localStorage.setItem('console_token', accessToken);
  document.cookie = `console_token=${accessToken}; path=/; max-age=${30 * 24 * 60 * 60}`;

  // 通知其他组件 token 已存储（UserInfoProvider 会收到通知）
  notifySSOTokenStored();

  // 重置登录状态
  setLoggingOut(false);

  // 获取用户信息
  try {
    const userInfoRes = await getUserInfo() as { data: UserInfoType };
    if (userInfoRes?.data) {
      window.localStorage.setItem('userInfo', JSON.stringify(userInfoRes.data));
      // 标记用户信息已初始化，避免重复获取
      setUserInfoInitialized(userInfoRes.data);
    }
  } catch (err) {
    console.error('SSO登录获取用户信息失败:', err);
  }

  // 清除URL中的access_token参数
  const cleanUrl = window.location.pathname + window.location.hash;
  window.history.replaceState(null, '', cleanUrl);

  return true;
};

const OverviewPage = ({ lng }: { lng: string }) => {
  const router = useRouter();
  const { userInfo } = useUserInfo();
  const isDark = useDarkMode();

  // SSO加载状态 - 初始化为false，只有检测到access_token时才显示加载
  const [isSSOLoading, setIsSSOLoading] = useState(false);

  // 使用统一的数据源 hook 管理数据源状态
  const { dataSources, loading, fetchDataSources, refreshDataSources } = useDataSources();

  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedDS, setSelectedDS] = useState<DataSourceItem | null>(null);
  const [showDSModal, setShowDSModal] = useState(false);
  const [recentActivities, setRecentActivities] = useState<Array<{ title: string; status: string; ts: number }>>([]);

  // 设置弹窗相关状态
  const [showSettings, setShowSettings] = useState(false);
  const [settingDS, setSettingDS] = useState<DataSourceItem | null>(null);
  const [editingName, setEditingName] = useState(false);
  const [connectName, setConnectName] = useState('');
  const [savingName, setSavingName] = useState(false);

  // 数据源选择弹框相关状态
  const [showDSSelector, setShowDSSelector] = useState(false);
  const [pendingTab, setPendingTab] = useState<string | null>(null);

  // 数据消费场景弹框相关状态
  const [showScenarioModal, setShowScenarioModal] = useState(false);
  const [activeScenario, setActiveScenario] = useState<ScenarioType | null>(null);

  // SSO回调处理：检查URL中是否有access_token
  useEffect(() => {
    const handleSSOLoading = async () => {
      const params = new URLSearchParams(window.location.search);
      const accessToken = params.get('access_token');

      if (accessToken) {
        // 这是SSO回调，需要处理token
        setIsSSOLoading(true);
        const isSSOCallback = await handleSSOCallback();
        setIsSSOLoading(false);
        if (isSSOCallback) {
          // 刷新数据源
          fetchDataSources(true);
        }
      } else {
        // 普通页面加载，不需要显示SSO加载状态
        setIsSSOLoading(false);
      }
    };
    handleSSOLoading();
  }, [fetchDataSources]);

  // 首次加载时获取数据源
  useEffect(() => {
    fetchDataSources();
  }, [fetchDataSources]);

  // 监听用户信息变化，初始化最近动态
  useEffect(() => {
    if (userInfo?.id) {
      // 从 sessionStorage 读取当前用户的最近动态
      const key = `recentActivities_${userInfo.id}`;
      try {
        const raw = window.sessionStorage.getItem(key);
        if (raw) {
          const arr = JSON.parse(raw);
          if (Array.isArray(arr)) {
            setRecentActivities(arr.slice(0, 3));
          }
        }
      } catch {
        // ignore
      }
    }
  }, [userInfo?.id]);

  // 当选中数据源时，自动打开弹框
  useEffect(() => {
    if (selectedDS) {
      setShowDSModal(true);
    }
  }, [selectedDS]);

  const getRecentKey = (userId: string) => `recentActivities_${userId}`;

  const readRecentActivities = (userId: string | null) => {
    if (!userId) return [];
    try {
      const raw = window.sessionStorage.getItem(getRecentKey(userId));
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch {
      return [];
    }
  };

  const writeRecentActivities = (userId: string | null, next: Array<{ title: string; status: string; ts: number }>) => {
    if (!userId) return;
    try {
      window.sessionStorage.setItem(getRecentKey(userId), JSON.stringify(next.slice(0, 3)));
    } catch {
      // ignore
    }
  };

  const logActivity = (title: string, status = '操作') => {
    const uid = userInfo?.id;
    if (!uid) return;
    const next = [{ title, status, ts: Date.now() }, ...readRecentActivities(uid)]
      .slice(0, 3);
    writeRecentActivities(uid, next);
    setRecentActivities(next);
  };

  const formatTimeAgo = (ts: number) => {
    const diff = Date.now() - ts;
    const m = Math.floor(diff / 60000);
    if (m <= 0) return '刚刚';
    if (m < 60) return `${m} 分钟前`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h} 小时前`;
    const d = Math.floor(h / 24);
    return `${d} 天前`;
  };

const hasDataSources = (dataSources?.length ?? 0) > 0;

// 派生出的整体统计信息
const totalSources = dataSources?.length ?? 0;
  const totalTables = (dataSources ?? []).reduce(
    (sum, ds) => sum + (ds.table_num || 0),
    0,
  );
  const totalCards = (dataSources ?? []).reduce(
    (sum, ds) => sum + (ds.datacard_count || 0),
    0,
  );
  const totalWeaviate = (dataSources ?? []).reduce(
    (sum, ds) => sum + (ds.weaviate_num || 0),
    0,
  );

  // 智能路由跳转函数
  const navigateToWorkspaceTab = (tab: string) => {
    if ((dataSources?.length ?? 0) === 0) {
      // 没有数据源，提示并打开添加弹框
      message.info('请先添加数据源');
      setShowAddModal(true);
    } else if ((dataSources?.length ?? 0) === 1) {
      // 只有一个数据源，直接跳转
      logActivity(`访问${getTabName(tab)}`, '访问');
      router.push(`/${lng}/workspaces/${dataSources?.[0].id}?tab=${tab}`);
    } else {
      // 多个数据源，弹出选择框
      setPendingTab(tab);
      setShowDSSelector(true);
    }
  };

  // 获取Tab名称用于日志
  const getTabName = (tab: string) => {
    const names: Record<string, string> = {
      assets: '数据库表',
      cards: '数据卡片',
      enhance: '数据增强',
      ask: '智能问数',
      jobs: '盘点任务',
      overview: '概览',
      knowledge: '知识',
    };
    return names[tab] || tab;
  };

  // 选择数据源后跳转
  const handleSelectDS = (ds: DataSourceItem) => {
    setShowDSSelector(false);
    logActivity(`访问${getTabName(pendingTab || 'tab')}`, '访问');
    router.push(`/${lng}/workspaces/${ds.id}?tab=${pendingTab || 'assets'}`);
    setPendingTab(null);
  };

  const goWorkspaces = () => router.push(`/${lng}/workspaces`);
  const goAsk = () => router.push(`/${lng}/ask`);
  const goExplore = () => router.push(`/${lng}/explore`);
  const openAddModal = () => {
    logActivity('打开添加数据源', '操作');
    setShowAddModal(true);
  };
  const handleViewDetails = (ds: DataSourceItem) => {
    logActivity(`查看数据源：${ds.connect_name}`, '查看');
    setSelectedDS(ds);
  };

  // SSO加载状态
  if (isSSOLoading) {
    return (
      <div className="min-h-full p-3 pt-4 pb-8 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-indigo-600 mx-auto" />
          <p className="mt-4 text-slate-600">SSO登录处理中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-full p-3 pt-4 pb-8">
      <div className="max-w-7xl mx-auto space-y-5">
        {/* Header Section */}
        <header className="mb-2">
          <h1 className="text-2xl font-semibold mb-1.5 text-slate-900">欢迎使用 OntiCards</h1>
          <p className="text-sm text-slate-500">管理并探索您的数据源，理解数据，并进行智能问数。</p>
        </header>

        <div className="grid grid-cols-12 gap-6">
          {/* Main Content (Left 9 Columns) */}
          <div className="col-span-12 lg:col-span-9 space-y-6">

            {/* Add Data Source Hero - 始终显示 */}
            <section
              onClick={openAddModal}
              className="relative overflow-hidden bg-gradient-to-r from-blue-50 to-pink-50 border-2 border-dashed border-slate-300/60 rounded-[20px] p-8 text-center flex flex-col items-center cursor-pointer hover:border-indigo-400/80 transition-all group"
            >
              {/* Decorative gradient orbs */}
              <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-blue-200/20 to-purple-200/20 rounded-full blur-3xl"></div>
              <div className="absolute bottom-0 left-0 w-24 h-24 bg-gradient-to-tr from-indigo-200/20 to-pink-200/20 rounded-full blur-2xl"></div>

              <div className="relative bg-white p-3 rounded-[16px] shadow-sm mb-4 group-hover:scale-110 transition-transform">
                <Plus className="w-6 h-6 text-indigo-500" strokeWidth={2.5} />
              </div>
              <h2 className="relative text-lg font-semibold mb-5 text-slate-900">
                {hasDataSources ? '添加新的数据源' : '添加您的第一个数据源'}
              </h2>
              <div className="relative flex flex-wrap justify-center gap-2 mb-6">
                {[
                  { name: 'PostgreSQL', type: 'postgresql' },
                  { name: 'MySQL', type: 'mysql' },
                  { name: 'Oracle', type: 'oracle' },
                  { name: 'SQL Server', type: 'sql server' },
                  { name: 'Trino', type: 'trino' },
                  { name: 'SQLite', type: 'sqlite' },
                  { name: 'KingBase', type: 'kingbase' },
                  { name: 'OceanBase(MySQL)', type: 'oceanbase' },
                  { name: 'DMBase(达梦)', type: 'dm' }
                ].map((db) => {
                  const dbInfo = getDbTypeIcon(db.type);
                  return (
                  <div
                    key={db.name}
                    className="db-type-pill px-3 py-1.5 bg-white border border-slate-200 text-xs flex items-center gap-1.5"
                    style={{ borderRadius: 9999 }}
                  >
                    <span className="text-base leading-none">{dbInfo.icon}</span> {db.name}
                  </div>
                );
                })}
              </div>
              <button
                className="relative bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-6 py-2.5 rounded-[12px] text-sm font-medium hover:from-blue-700 hover:to-indigo-700 transition-all shadow-md hover:shadow-lg"
                onClick={(e) => {
                  e.stopPropagation();
                  openAddModal();
                }}
              >
                连接
              </button>
            </section>

            {/* Platform Summary - 汇总 + 数据源卡片 */}
            <section>
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-slate-900">数据源概览</h3>
                <button
                  type="button"
                  onClick={() => {
                    logActivity('刷新数据源概览', '操作');
                    fetchDataSources(true);
                  }}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded-[8px] text-xs font-medium text-slate-500 hover:text-indigo-600 hover:bg-indigo-50/50 transition-colors"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                  <span>{loading ? '刷新中' : '刷新'}</span>
                </button>
              </div>

              {/* 汇总统计（芯片形式） */}
              <div className="mb-4">
                <div className="flex flex-wrap gap-2 text-xs">
                  <SummaryPill
                    icon={<Database className="w-3 h-3 text-blue-500" />}
                    label="数据源"
                    value={loading ? '-' : totalSources.toString()}
                  />
                  <SummaryPill
                    icon={<Table className="w-3 h-3 text-green-500" />}
                    label="数据表"
                    value={loading ? '-' : totalTables.toString()}
                  />
                  <SummaryPill
                    icon={<CreditCard className="w-3 h-3 text-orange-500" />}
                    label="数据卡片"
                    value={loading ? '-' : totalCards.toString()}
                  />
                  <SummaryPill
                    icon={<CreditCard className="w-3 h-3 text-purple-500" />}
                    label="向量索引"
                    value={loading ? '-' : totalWeaviate.toString()}
                  />
                  {/* 超过2个数据源时，显示提示在右侧 */}
                  {!loading && totalSources > 2 && (
                    <button
                      onClick={() => { logActivity('访问工作空间列表', '访问'); router.push(`/${lng}/workspaces`); }}
                      className="flex items-center gap-1 px-2.5 py-1 text-[11px] text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-[8px] transition-colors whitespace-nowrap ml-auto"
                    >
                      <span className="font-medium text-indigo-500">+{totalSources - 2}</span>
                      <span>查看全部</span>
                      <ChevronRight className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </div>

              {/* 数据源卡片列表 - 改用列表形式，更清晰展示 */}
              {loading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map(i => (
                    <div key={i} className="bg-white p-5 rounded-[16px] border border-slate-200 animate-pulse">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 bg-slate-100 rounded-[14px]"></div>
                        <div className="flex-1">
                          <div className="h-5 bg-slate-100 rounded w-48 mb-2"></div>
                          <div className="h-4 bg-slate-50 rounded w-32"></div>
                        </div>
                        <div className="flex gap-3">
                          <div className="h-8 bg-slate-50 rounded-lg w-16"></div>
                          <div className="h-8 bg-slate-50 rounded-lg w-16"></div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (dataSources?.length ?? 0) === 0 ? (
                <div className="bg-white rounded-[20px] border border-slate-200 p-12 text-center">
                  <Database className="w-12 h-12 text-slate-200 mx-auto mb-3" />
                  <p className="text-sm text-slate-400">暂无数据源</p>
                  <p className="text-xs text-slate-300 mt-1">点击上方"添加数据源"开始使用</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {(dataSources ?? [])
                    .sort((a, b) => {
                      const timeA = new Date(a.updated_at || 0).getTime();
                      const timeB = new Date(b.updated_at || 0).getTime();
                      return timeB - timeA;
                    })
                    .slice(0, 2)
                    .map((ds) => (
                      <DataSourceCard
                        key={ds.id}
                        ds={ds}
                        lng={lng}
                        onViewDetails={handleViewDetails}
                        onSettings={(ds) => { setSettingDS(ds); setShowSettings(true); }}
                      />
                    ))}
                </div>
              )}
            </section>

            {/* 新手指南 / 使用流程 */}
            <section>
              <div className="flex items-center gap-2 mb-4">
                <Lightbulb className="w-4 h-4 text-amber-500" />
                <h3 className="text-sm font-semibold" style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>使用流程</h3>
              </div>
              <div
                className="rounded-[20px] p-6"
                style={{
                  backgroundColor: isDark ? '#1e293b' : '#ffffff',
                  border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
                }}
              >
                <p className="text-xs mb-5 leading-relaxed" style={{ color: isDark ? '#94a3b8' : '#64748b' }}>
                  了解如何使用 OntiCards 将原始数据转化为可消费的数据资产，实现数据价值的最大化。
                </p>
                <div className="relative">
                  {/* 流程步骤 */}
                  <div className="flex flex-col sm:flex-row sm:items-start gap-5 sm:gap-0">
                    {guideSteps.map((step, index) => (
                      <div key={step.id} className="flex-1 relative">
                        {/* 连接线 */}
                        {index < guideSteps.length - 1 && (
                          <div
                            className="hidden sm:block absolute top-5 left-1/2 w-full h-0.5 z-0"
                            style={{
                              background: isDark
                                ? 'linear-gradient(to right, rgba(99, 102, 241, 0.4), rgba(99, 102, 241, 0.2))'
                                : 'linear-gradient(to right, #c7d2fe, #e0e7ff)',
                            }}
                          />
                        )}
                        <div className="relative z-10 flex flex-col items-center gap-1.5 text-center">
                          <div
                            className="w-10 h-10 flex items-center justify-center flex-shrink-0"
                            style={{
                              borderRadius: '9999px',
                              backgroundColor: step.optional
                                ? isDark ? 'rgba(56, 189, 248, 0.15)' : '#F0F9FF'
                                : isDark ? 'rgba(99, 102, 241, 0.2)' : '#EEF2FF',
                              border: step.optional ? '2px dashed' : 'none',
                              borderColor: step.optional
                                ? isDark ? 'rgba(56, 189, 248, 0.5)' : '#7DD3FC'
                                : 'none',
                              boxShadow: step.optional ? 'none' : isDark
                                ? '0 2px 4px rgba(0, 0, 0, 0.2)'
                                : '0 2px 4px rgba(79, 70, 229, 0.1)'
                            }}
                          >
                            <span
                              className="text-sm font-semibold"
                              style={{ color: step.optional
                                ? isDark ? '#38bdf8' : '#0284C7'
                                : isDark ? '#a5b4fc' : '#4F46E5'
                              }}
                            >
                              {index + 1}
                            </span>
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center justify-center gap-1.5">
                              <h4 className="text-xs font-medium" style={{ color: isDark ? '#f1f5f9' : '#475569' }}>
                                {step.title}
                              </h4>
                              {step.optional && step.tag && (
                                <span
                                  className="text-[9px] px-1.5 py-0.5 font-medium"
                                  style={{
                                    borderRadius: '9999px',
                                    backgroundColor: isDark ? 'rgba(56, 189, 248, 0.15)' : '#E0F2FE',
                                    color: isDark ? '#38bdf8' : '#0284C7'
                                  }}
                                >
                                  {step.tag}
                                </span>
                              )}
                            </div>
                            <p className="text-[10px] mt-0.5" style={{ color: isDark ? '#94a3b8' : '#64748B' }}>
                              {step.desc}
                            </p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* 底部消费场景 */}
                  <div className="mt-6 pt-5 border-t" style={{ borderColor: isDark ? 'rgba(71, 85, 105, 0.5)' : '#e2e7eb' }}>
                    <p
                      className="text-[11px] mb-3 font-medium"
                      style={{ color: isDark ? '#94a3b8' : '#64748b' }}
                    >
                      数据消费场景
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => { setActiveScenario('bi'); setShowScenarioModal(true); }}
                        className="inline-flex items-center gap-1.5 px-2.5 py-2 text-[11px] cursor-pointer transition-colors"
                        style={{
                          borderRadius: '12px',
                          backgroundColor: isDark ? 'rgba(30, 41, 59, 0.8)' : '#f8fafc',
                          color: isDark ? '#cbd5e1' : '#475569',
                          border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
                        }}
                      >
                        <BarChart3 className="w-3.5 h-3.5" />
                        <span>BI 系统对接</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => { setActiveScenario('ai-agent'); setShowScenarioModal(true); }}
                        className="inline-flex items-center gap-1.5 px-2.5 py-2 text-[11px] cursor-pointer transition-colors"
                        style={{
                          borderRadius: '12px',
                          backgroundColor: isDark ? 'rgba(30, 41, 59, 0.8)' : '#f8fafc',
                          color: isDark ? '#cbd5e1' : '#475569',
                          border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
                        }}
                      >
                        <Bot className="w-3.5 h-3.5" />
                        <span>AI 智能体集成</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => { setActiveScenario('api'); setShowScenarioModal(true); }}
                        className="inline-flex items-center gap-1.5 px-2.5 py-2 text-[11px] cursor-pointer transition-colors"
                        style={{
                          borderRadius: '12px',
                          backgroundColor: isDark ? 'rgba(30, 41, 59, 0.8)' : '#f8fafc',
                          color: isDark ? '#cbd5e1' : '#475569',
                          border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
                        }}
                      >
                        <Code className="w-3.5 h-3.5" />
                        <span>API 取数</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => { setActiveScenario('export'); setShowScenarioModal(true); }}
                        className="inline-flex items-center gap-1.5 px-2.5 py-2 text-[11px] cursor-pointer transition-colors"
                        style={{
                          borderRadius: '12px',
                          backgroundColor: isDark ? 'rgba(30, 41, 59, 0.8)' : '#f8fafc',
                          color: isDark ? '#cbd5e1' : '#475569',
                          border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
                        }}
                      >
                        <FileDown className="w-3.5 h-3.5" />
                        <span>数据导出</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => { setActiveScenario('subscription'); setShowScenarioModal(true); }}
                        className="inline-flex items-center gap-1.5 px-2.5 py-2 text-[11px] cursor-pointer transition-colors"
                        style={{
                          borderRadius: '12px',
                          backgroundColor: isDark ? 'rgba(30, 41, 59, 0.8)' : '#f8fafc',
                          color: isDark ? '#cbd5e1' : '#475569',
                          border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
                        }}
                      >
                        <Bell className="w-3.5 h-3.5" />
                        <span>数据订阅推送</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => { setActiveScenario('quality'); setShowScenarioModal(true); }}
                        className="inline-flex items-center gap-1.5 px-2.5 py-2 text-[11px] cursor-pointer transition-colors"
                        style={{
                          borderRadius: '12px',
                          backgroundColor: isDark ? 'rgba(30, 41, 59, 0.8)' : '#f8fafc',
                          color: isDark ? '#cbd5e1' : '#475569',
                          border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
                        }}
                      >
                        <Gauge className="w-3.5 h-3.5" />
                        <span>数据质量监控</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => { setActiveScenario('metrics'); setShowScenarioModal(true); }}
                        className="inline-flex items-center gap-1.5 px-2.5 py-2 text-[11px] cursor-pointer transition-colors"
                        style={{
                          borderRadius: '12px',
                          backgroundColor: isDark ? 'rgba(30, 41, 59, 0.8)' : '#f8fafc',
                          color: isDark ? '#cbd5e1' : '#475569',
                          border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
                        }}
                      >
                        <Zap className="w-3.5 h-3.5" />
                        <span>指标中心</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => { setActiveScenario('prediction'); setShowScenarioModal(true); }}
                        className="inline-flex items-center gap-1.5 px-2.5 py-2 text-[11px] cursor-pointer transition-colors"
                        style={{
                          borderRadius: '12px',
                          backgroundColor: isDark ? 'rgba(30, 41, 59, 0.8)' : '#f8fafc',
                          color: isDark ? '#cbd5e1' : '#475569',
                          border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
                        }}
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>数据预测分析</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => { setActiveScenario('report'); setShowScenarioModal(true); }}
                        className="inline-flex items-center gap-1.5 px-2.5 py-2 text-[11px] cursor-pointer transition-colors"
                        style={{
                          borderRadius: '12px',
                          backgroundColor: isDark ? 'rgba(30, 41, 59, 0.8)' : '#f8fafc',
                          color: isDark ? '#cbd5e1' : '#475569',
                          border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
                        }}
                      >
                        <LayoutDashboard className="w-3.5 h-3.5" />
                        <span>自动化报表</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => { setActiveScenario('quality-report'); setShowScenarioModal(true); }}
                        className="inline-flex items-center gap-1.5 px-2.5 py-2 text-[11px] cursor-pointer transition-colors"
                        style={{
                          borderRadius: '12px',
                          backgroundColor: isDark ? 'rgba(30, 41, 59, 0.8)' : '#f8fafc',
                          color: isDark ? '#cbd5e1' : '#475569',
                          border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
                        }}
                      >
                        <ClipboardList className="w-3.5 h-3.5" />
                        <span>数据质检报告</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => { setActiveScenario('quality-fix'); setShowScenarioModal(true); }}
                        className="inline-flex items-center gap-1.5 px-2.5 py-2 text-[11px] cursor-pointer transition-colors"
                        style={{
                          borderRadius: '12px',
                          backgroundColor: isDark ? 'rgba(30, 41, 59, 0.8)' : '#f8fafc',
                          color: isDark ? '#cbd5e1' : '#475569',
                          border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
                        }}
                      >
                        <Settings className="w-3.5 h-3.5" />
                        <span>数据修复建议</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => { setActiveScenario('sharing'); setShowScenarioModal(true); }}
                        className="inline-flex items-center gap-1.5 px-2.5 py-2 text-[11px] cursor-pointer transition-colors"
                        style={{
                          borderRadius: '12px',
                          backgroundColor: isDark ? 'rgba(30, 41, 59, 0.8)' : '#f8fafc',
                          color: isDark ? '#cbd5e1' : '#475569',
                          border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
                        }}
                      >
                        <Share2 className="w-3.5 h-3.5" />
                        <span>数据市场共享</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => { setActiveScenario('docs'); setShowScenarioModal(true); }}
                        className="inline-flex items-center gap-1.5 px-2.5 py-2 text-[11px] cursor-pointer transition-colors"
                        style={{
                          borderRadius: '12px',
                          backgroundColor: isDark ? 'rgba(30, 41, 59, 0.8)' : '#f8fafc',
                          color: isDark ? '#cbd5e1' : '#475569',
                          border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
                        }}
                      >
                        <BookOpen className="w-3.5 h-3.5" />
                        <span>数据文档中心</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </section>
          </div>

          {/* 数据消费场景演示弹框 */}
          <DataConsumeScenariosModal
            isOpen={showScenarioModal}
            onClose={() => { setShowScenarioModal(false); setActiveScenario(null); }}
            scenarioType={activeScenario}
          />

          {/* Sidebar (Right 3 Columns) */}
          <div className="col-span-12 lg:col-span-3">
            <aside className="space-y-5">
              <div>
                <h4 className="text-sm font-semibold mb-2.5 text-slate-900">快捷操作</h4>
                <div className="space-y-2">
                  <QuickActionItem label="系统设置" onClick={() => { logActivity('进入系统与账户', '访问'); router.push(`/${lng}/settings`); }} />
                  <QuickActionItem label="工作空间列表" onClick={() => { logActivity('访问工作空间列表', '访问'); router.push(`/${lng}/workspaces`); }} />
                </div>
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-2.5 text-slate-900">查看 API 密钥</h4>
                <div
                  onClick={() => { logActivity('查看API密钥', '访问'); router.push(`/${lng}/settings?tab=api-keys`); }}
                  className="bg-white p-3 rounded-[16px] border border-slate-200 flex items-center justify-between cursor-pointer hover:shadow-sm hover:border-indigo-300 hover:bg-indigo-50/30 group transition-all"
                >
                  <code className="text-xs text-slate-400">ak_*****************</code>
                  <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-indigo-500 transition-colors" strokeWidth={2} />
                </div>
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-2.5 text-slate-900">最近动态</h4>
                <div className="bg-white rounded-[16px] border border-slate-200 overflow-hidden">
                  {recentActivities.length === 0 ? (
                    <div className="px-3 py-3 text-xs text-slate-400">暂无动态</div>
                  ) : (
                    recentActivities.map((a) => (
                      <ActivityItem key={`${a.ts}-${a.title}`} title={a.title} status={a.status} timeLabel={formatTimeAgo(a.ts)} />
                    ))
                  )}
                </div>
              </div>

              {/* 快速入口 - 竖向排列 */}
              <div>
                <h4 className="text-sm font-semibold mb-2.5 text-slate-900">快速入口</h4>
                <div className="space-y-2">
                  <ExploreCard
                    title="数据库表"
                    desc="浏览表结构、字段注释"
                    btnText="查看库表"
                    icon={<Database className="w-4 h-4" strokeWidth={2} />}
                    onClick={() => navigateToWorkspaceTab('assets')}
                  />
                  <ExploreCard
                    title="数据增强"
                    desc="上传Excel填充业务含义"
                    btnText="开始增强"
                    icon={<FileText className="w-4 h-4" strokeWidth={2} />}
                    onClick={() => navigateToWorkspaceTab('enhance')}
                  />
                  <ExploreCard
                    title="关联业务术语库"
                    desc="构建并关联术语，精准理解数据"
                    btnText="去关联"
                    icon={<BookOpen className="w-4 h-4" strokeWidth={2} />}
                    onClick={() => navigateToWorkspaceTab('knowledge')}
                  />
                  <ExploreCard
                    title="智能问数"
                    desc="自然语言转SQL查询"
                    btnText="开始问数"
                    icon={<MessageSquare className="w-4 h-4" strokeWidth={2} />}
                    onClick={() => navigateToWorkspaceTab('ask')}
                  />
                </div>
              </div>
            </aside>
          </div>
        </div>
      </div>

      {/* 添加数据源弹窗 */}
      <AddDataSourceModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onSuccess={() => {
          message.success('数据源添加成功');
          // 刷新数据源列表
          refreshDataSources();
        }}
      />

      {/* 数据源选择弹框 */}
      <Modal
        open={showDSSelector}
        onCancel={() => {
          setShowDSSelector(false);
          setPendingTab(null);
        }}
        footer={null}
        width={480}
        centered
        title={
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-indigo-500" />
            <span>选择数据源</span>
          </div>
        }
      >
        <div className="py-2">
          <p className="text-sm text-slate-500 mb-4 px-1">
            选择要进入 <span className="font-medium text-indigo-600">{getTabName(pendingTab || 'tab')}</span> 的数据源
          </p>
          <div className="space-y-2 max-h-[320px] overflow-y-auto">
            {(dataSources ?? []).map((ds) => {
              const dbInfo = getDbTypeIcon(ds.db_type || '');
              return (
                <div
                  key={ds.id}
                  onClick={() => handleSelectDS(ds)}
                  className="flex items-center gap-3 p-3 rounded-[12px] border border-slate-200 bg-white hover:border-indigo-300 hover:bg-indigo-50/30 cursor-pointer transition-all group"
                >
                  <div className={`w-10 h-10 rounded-[10px] bg-gradient-to-br ${dbInfo.bg} flex items-center justify-center shadow-sm`}>
                    <span className="text-xl leading-none">{dbInfo.icon}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-900 truncate">{ds.connect_name}</span>
                      <span
                        className="px-1.5 py-0.5 text-[10px] font-medium flex-shrink-0"
                        style={{
                          borderRadius: '9999px',
                          ...(ds.status === 'available'
                            ? { backgroundColor: 'rgba(16, 185, 129, 0.15)', color: 'rgb(5, 150, 105)' }
                            : { backgroundColor: 'rgba(239, 68, 68, 0.15)', color: 'rgb(185, 28, 28)' })
                        }}
                      >
                        {ds.status === 'available' ? '可用' : '不可用'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5 text-xs text-slate-500">
                      <span className="truncate">{ds.database_name || ds.db_type}</span>
                      <span>·</span>
                      <span>{ds.table_num || 0} 张表</span>
                      <span>·</span>
                      <span>{ds.datacard_count || 0} 张卡片</span>
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-slate-300 group-hover:text-indigo-500 transition-colors flex-shrink-0" strokeWidth={2} />
                </div>
              );
            })}
          </div>
        </div>
      </Modal>

      {/* 数据源详情弹框 */}
      <Modal
        open={showDSModal}
        onCancel={() => {
          setShowDSModal(false);
          setSelectedDS(null);
        }}
        footer={null}
        width={760}
        centered
        title={
          selectedDS && (() => {
            const dbInfo = getDbTypeIcon(selectedDS.db_type || '');
            return (
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-[12px] bg-gradient-to-br ${dbInfo.bg} flex items-center justify-center`}>
                  <span className="text-lg leading-none">{dbInfo.icon}</span>
                </div>
                <div className="space-y-1">
                  <div className="text-base font-semibold text-slate-900">{selectedDS.connect_name}</div>
                  <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-slate-500">
                    <span>数据库：{selectedDS.database_name}</span>
                    <span>类型：{selectedDS.db_type}</span>
                    {selectedDS.schema_name && <span>Schema：{selectedDS.schema_name}</span>}
                    {selectedDS.schemas?.[0]?.db_version && (
                      <span>版本：{selectedDS.schemas[0].db_version}</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })()
        }
      >
        {selectedDS && (
          <div className="space-y-4">
            {/* 统计信息网格：四个精简指标（居中、紧凑） */}
            <div className="grid grid-cols-4 gap-3">
              <div className="rounded-[12px] bg-slate-50 px-2.5 py-2 text-center flex flex-col items-center justify-center">
                <div className="text-[11px] text-slate-500 mb-0.5">数据表</div>
                <div className="text-sm font-semibold text-slate-900 leading-none">
                  {selectedDS.table_num || 0}
                </div>
              </div>
              <div className="rounded-[12px] bg-green-50/80 px-2.5 py-2 text-center flex flex-col items-center justify-center">
                <div className="text-[11px] text-green-600 mb-0.5">部分数据AI填充</div>
                <div className="text-sm font-semibold text-green-600 leading-none">
                  {selectedDS.schemas?.filter(s => s.is_filled).length || 0}
                </div>
              </div>
              <div className="rounded-[12px] bg-orange-50/80 px-2.5 py-2 text-center flex flex-col items-center justify-center">
                <div className="text-[11px] text-orange-600 mb-0.5">数据卡片</div>
                <div className="text-sm font-semibold text-orange-600 leading-none">
                  {selectedDS.datacard_count || 0}
                </div>
              </div>
              <div className="rounded-[12px] bg-purple-50/80 px-2.5 py-2 text-center flex flex-col items-center justify-center">
                <div className="text-[11px] text-purple-600 mb-0.5">向量索引</div>
                <div className="text-sm font-semibold text-purple-600 leading-none">
                  {selectedDS.weaviate_num || 0}
                </div>
              </div>
            </div>

            {/* 表结构列表（含字段信息、主外键、审计） */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-slate-700">表结构详情</span>
                <span className="text-xs text-slate-400">共 {selectedDS.schemas?.length || 0} 张表</span>
              </div>

              <div className="max-h-[480px] overflow-y-auto space-y-4 pr-1">
                {selectedDS.schemas && selectedDS.schemas.length > 0 ? (
                  selectedDS.schemas.map((schema, idx) => {
                    const tableDesc = schema.schema_text?.description || '暂无描述';
                    const columns = schema.schema_text?.columns || [];
                    const filledCols = schema.filled_data?.columns || [];
                    const primaryKeys = schema.schema_text?.primary_keys || [];
                    const foreignKeys = schema.schema_text?.foreign_keys || [];

                    return (
                      <div
                        key={schema.id || `${schema.table_name}-${idx}`}
                        className="rounded-[12px] border border-slate-200 bg-white overflow-hidden hover:shadow-sm transition-shadow"
                      >
                        {/* 表头 */}
                        <div className="flex items-center justify-between p-4 pb-2 flex-wrap gap-2">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Table className="w-4 h-4 text-slate-400 flex-shrink-0" />
                            <span className="text-sm font-medium text-slate-800 dark:text-slate-100">{schema.table_name}</span>
                            {schema.is_view && (
                              <span
                                className="px-2 py-0.5 text-[10px] font-medium"
                                style={{ borderRadius: '9999px', backgroundColor: 'rgba(251, 191, 36, 0.2)', color: 'rgb(217, 119, 6)' }}
                              >
                                视图
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-1.5 flex-wrap">
                            {schema.is_filled && (
                              <span
                                className="px-2 py-0.5 text-[10px] font-medium"
                                style={{ borderRadius: '9999px', backgroundColor: 'rgba(34, 197, 94, 0.15)', color: 'rgb(22, 163, 74)' }}
                              >
                                部分字段注释AI填充
                              </span>
                            )}
                          </div>
                        </div>
                        <p className="px-4 pb-3 text-xs text-slate-500 dark:text-slate-400 leading-relaxed indent-4">
                          {tableDesc}
                        </p>

                        {/* 字段列表：包含主外键信息 */}
                        {(() => {
                          const rows = columns.length > 0
                            ? columns.map((c) => ({
                                name: c.name,
                                type: c.type,
                                comment: c.comment ?? '-',
                                isPrimary: c.is_primary ?? false
                              }))
                            : filledCols.map((fc) => ({
                                name: fc.name,
                                type: '-',
                                comment: fc.business_meaning || fc.value_range || '-',
                                isPrimary: false
                              }));
                          if (rows.length === 0) return null;
                          return (
                            <div className="px-4 pb-3">
                              <div className="flex items-center justify-between mb-2">
                                <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">字段（{rows.length}个）</div>
                                {primaryKeys.length > 0 && (
                                  <div className="text-[10px] text-rose-600 dark:text-rose-400">
                                    主键：{primaryKeys.join('、')}
                                  </div>
                                )}
                              </div>
                              <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50 overflow-hidden">
                                <table className="w-full text-[11px]">
                                  <thead>
                                    <tr className="bg-slate-100/80 dark:bg-slate-700/80 text-slate-600 dark:text-slate-300 text-left">
                                      <th className="py-1.5 px-2 font-medium w-10">#</th>
                                      <th className="py-1.5 px-2 font-medium">字段名</th>
                                      <th className="py-1.5 px-2 font-medium">类型</th>
                                      <th className="py-1.5 px-2 font-medium">说明</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {rows.map((row, i) => (
                                      <tr key={i} className="border-t border-slate-100 dark:border-slate-700">
                                        <td className="py-1.5 px-2 text-slate-400 dark:text-slate-500">{i + 1}</td>
                                        <td className="py-1.5 px-2 text-slate-800 dark:text-slate-200 font-medium">
                                          {row.isPrimary && <span className="inline-block w-1.5 h-1.5 rounded-full bg-rose-500 dark:bg-rose-400 mr-1.5 align-middle"></span>}
                                          {row.name}
                                        </td>
                                        <td className="py-1.5 px-2 text-slate-600 dark:text-slate-400">{row.type}</td>
                                        <td className="py-1.5 px-2 text-slate-500 dark:text-slate-400">{row.comment}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                              {/* 外键信息 */}
                              {foreignKeys.length > 0 && (
                                <div className="mt-2 text-[10px] text-slate-500 dark:text-slate-400">
                                  <span className="font-medium">外键：</span>
                                  {foreignKeys.map((fk: any, i: number) => (
                                    <span key={i} className="mr-2">
                                      {fk.columns?.[0]} → {fk.referenced_table}.{fk.referenced_columns?.[0]}
                                    </span>
                                  ))}
                                </div>
                              )}
                              {/* 示例值 */}
                              {filledCols.length > 0 && filledCols.some((c) => c.sample_values?.length) && (
                                <div className="mt-2 text-[10px] text-slate-400 dark:text-slate-500">
                                  示例值：{filledCols.flatMap((c) => c.sample_values || []).slice(0, 6).join('、')}
                                </div>
                              )}
                            </div>
                          );
                        })()}

                      </div>
                    );
                  })
                ) : (
                  <div className="text-center py-8 text-slate-400 text-sm">暂无表信息</div>
                )}
              </div>
            </div>

            {/* 底部按钮 */}
            <div className="flex justify-end pt-2">
              <button
                onClick={() => router.push(`/${lng}/workspaces`)}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-50 text-indigo-600 rounded-[10px] text-sm font-medium hover:bg-indigo-100 transition-colors"
              >
                <ExternalLink className="w-4 h-4" />
                前往工作空间
              </button>
            </div>
          </div>
        )}
      </Modal>

      {/* 设置弹窗：Portal 到 body 避免顶部白边 */}
      {showSettings && settingDS && typeof document !== 'undefined' && createPortal(
        <div
          className="fixed inset-0 bg-slate-900/20 backdrop-blur-sm flex items-center justify-center p-4"
          style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9999 }}
        >
          <div className="bg-white w-full max-w-lg shadow-2xl overflow-hidden" style={{ borderRadius: '16px' }}>
            {/* 头部 */}
            <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-3" style={{ borderRadius: '16px 16px 0 0' }}>
              <div className={`w-10 h-10 flex items-center justify-center`} style={{ borderRadius: '12px', background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)' }}>
                <span className="text-xl">{getDbTypeIcon(settingDS.db_type).icon}</span>
              </div>
              <div className="flex-1">
                <h2 className="text-lg font-bold text-slate-800">数据源设置</h2>
                <p className="text-sm text-slate-500">{settingDS.db_type?.toUpperCase()}{settingDS.database_name ? ` / ${settingDS.database_name}` : ''}</p>
              </div>
              <button
                onClick={() => {
                  setShowSettings(false);
                  setSettingDS(null);
                  setEditingName(false);
                }}
                className="p-2 hover:bg-slate-100 transition-colors"
                style={{ borderRadius: '12px' }}
              >
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>

            <div className="p-6">
              {/* 连接名称编辑 */}
              {editingName ? (
                <div className="flex gap-2 mb-4">
                  <input
                    type="text"
                    value={connectName}
                    onChange={(e) => setConnectName(e.target.value)}
                    className="flex-1 px-3 py-2 bg-slate-50 border-0 text-base focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700"
                    placeholder="请输入连接名称"
                    style={{ borderRadius: '12px' }}
                  />
                  <button
                    onClick={async () => {
                      if (!connectName.trim()) return;
                      setSavingName(true);
                      const res = await updateDataSourceName(settingDS.id, connectName.trim());
                      if (res.code === 200) {
                        setSettingDS({ ...settingDS, connect_name: connectName.trim() });
                        setEditingName(false);
                        message.success('保存成功');
                        // 刷新数据源列表
                        refreshDataSources();
                      }
                      setSavingName(false);
                    }}
                    disabled={savingName || !connectName.trim()}
                    className="px-4 py-2 bg-indigo-500 text-white text-sm font-medium hover:bg-indigo-600 transition-colors disabled:opacity-50"
                    style={{ borderRadius: '12px' }}
                  >
                    {savingName ? '保存中' : '保存'}
                  </button>
                  <button
                    onClick={() => {
                      setEditingName(false);
                      setConnectName(settingDS.connect_name);
                    }}
                    className="px-4 py-2 bg-slate-100 text-slate-600 text-sm font-medium hover:bg-slate-200 transition-colors"
                    style={{ borderRadius: '12px' }}
                  >
                    取消
                  </button>
                </div>
              ) : (
                <div className="flex items-center justify-between mb-4 p-3 bg-slate-50" style={{ borderRadius: '12px' }}>
                  <span className="text-sm text-slate-600">连接名称</span>
                  <button
                    onClick={() => {
                      setConnectName(settingDS.connect_name);
                      setEditingName(true);
                    }}
                    className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
                  >
                    {settingDS.connect_name} ✏️
                  </button>
                </div>
              )}

              {/* 创建时间 */}
              <div className="mb-4">
                <span className="text-xs text-slate-400">创建于 {settingDS.created_at ? new Date(settingDS.created_at).toLocaleString('zh-CN', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit'
                }) : '-'}</span>
              </div>

              {/* 连接信息 */}
              <div className="p-4 border border-slate-200" style={{ borderRadius: '12px' }}>
                <div className="space-y-3">
                  {(() => {
                    const parsed = parseConnectInfo(settingDS.connect_info);
                    if (!parsed) {
                      return (
                        <div className="text-center py-4 text-sm text-slate-500">
                          <p>无法解析连接信息</p>
                          <p className="text-xs text-slate-400 mt-1 font-mono break-all">{settingDS.connect_info}</p>
                        </div>
                      );
                    }

                    return (
                      <>
                        <div className="flex justify-between items-center py-2 border-b border-slate-100">
                          <span className="text-sm text-slate-500">用户名</span>
                          <span className="text-sm text-slate-700 font-mono">{parsed.username}</span>
                        </div>
                        <div className="flex justify-between items-center py-2 border-b border-slate-100">
                          <span className="text-sm text-slate-500">密码</span>
                          <span className="text-sm text-slate-700 font-mono">{maskPassword(parsed.password)}</span>
                        </div>
                        <div className="flex justify-between items-center py-2 border-b border-slate-100">
                          <span className="text-sm text-slate-500">IP 地址</span>
                          <span className="text-sm text-slate-700 font-mono">{parsed.host}</span>
                        </div>
                        <div className="flex justify-between items-center py-2 border-b border-slate-100">
                          <span className="text-sm text-slate-500">端口</span>
                          <span className="text-sm text-slate-700 font-mono">{parsed.port}</span>
                        </div>
                        {parsed.database && (
                          <div className="flex justify-between items-center py-2 border-b border-slate-100">
                            <span className="text-sm text-slate-500">数据库</span>
                            <span className="text-sm text-slate-700 font-mono">{parsed.database}</span>
                          </div>
                        )}
                        {parsed.serviceName && (
                          <div className="flex justify-between items-center py-2 border-b border-slate-100">
                            <span className="text-sm text-slate-500">Service</span>
                            <span className="text-sm text-slate-700 font-mono">{parsed.serviceName}</span>
                          </div>
                        )}
                        {settingDS.schema_name && (
                          <div className="flex justify-between items-center py-2">
                            <span className="text-sm text-slate-500">Schema</span>
                            <span className="text-sm text-slate-700 font-mono">{settingDS.schema_name}</span>
                          </div>
                        )}
                      </>
                    );
                  })()}
                </div>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};

// --- Sub-components ---

// 数据源卡片组件 - 改用横向列表布局，清晰展示数据源信息
const DataSourceCard = ({ ds, lng, onViewDetails, onSettings }: { ds: DataSourceItem; lng: string; onViewDetails: (ds: DataSourceItem) => void; onSettings: (ds: DataSourceItem) => void }) => {
  const router = useRouter();
  const filledCount = ds.schemas?.filter(s => s.is_filled).length || 0;
  const totalTables = ds.table_num || 0;

  const goWorkspaces = () => router.push(`/${lng}/workspaces`);

  return (
    <div
      className="bg-white rounded-[16px] border border-slate-200 p-4 transition-all duration-200 hover:shadow-md hover:border-indigo-200 group"
      style={{ boxSizing: 'border-box' }}
    >
      <div
        className="flex flex-col lg:flex-row lg:items-center gap-3 lg:gap-4"
        style={{ boxSizing: 'border-box' }}
      >
        {/* 左侧：图标 + 名称信息 */}
        <div
          className="flex items-center gap-3 min-w-0 flex-1"
          style={{ boxSizing: 'border-box' }}
        >
          {(() => {
            const dbInfo = getDbTypeIcon(ds.db_type || '');
            return (
              <div
                className={`w-10 h-10 rounded-[10px] bg-gradient-to-br ${dbInfo.bg} flex items-center justify-center flex-shrink-0 shadow-sm`}
                style={{ boxSizing: 'border-box' }}
              >
                <span className="text-xl leading-none">{dbInfo.icon}</span>
              </div>
            );
          })()}
          <div className="min-w-0 flex-1" style={{ boxSizing: 'border-box' }}>
            <div className="flex items-center gap-2 flex-wrap">
              <h4
                className="text-sm font-medium text-slate-900 truncate"
                title={ds.connect_name}
                style={{ boxSizing: 'border-box' }}
              >
                {ds.connect_name}
              </h4>
              <span
                className="px-2 py-0.5 text-[10px] font-medium flex-shrink-0"
                style={{
                  borderRadius: '9999px',
                  ...(ds.status === 'available'
                    ? { backgroundColor: 'rgba(16, 185, 129, 0.15)', color: 'rgb(5, 150, 105)' }
                    : { backgroundColor: 'rgba(239, 68, 68, 0.15)', color: 'rgb(185, 28, 28)' })
                }}
              >
                {ds.status === 'available' ? '可用' : '不可用'}
              </span>
            </div>
            <p
              className="text-xs text-slate-500 truncate mt-0.5"
              title={ds.database_name ? `${ds.database_name} · ${ds.db_type}` : ds.db_type}
              style={{ boxSizing: 'border-box' }}
            >
              {ds.database_name ? `${ds.database_name} · ${ds.db_type}` : ds.db_type}
            </p>
          </div>
        </div>

        {/* 中间：统计数据 - 小屏幕隐藏 */}
        <div
          className="hidden xl:flex items-center gap-2 flex-shrink-0"
          style={{ boxSizing: 'border-box' }}
        >
          <div
            className="flex items-center gap-1 px-2"
            style={{ boxSizing: 'border-box' }}
          >
            <span className="text-sm font-semibold text-slate-700" style={{ lineHeight: '1.2' }}>{totalTables}</span>
            <span className="text-[11px] text-slate-400 whitespace-nowrap" style={{ lineHeight: '1.2' }}>数据表</span>
          </div>
          <div className="w-px h-5 bg-slate-100"></div>
          <div
            className="flex items-center gap-1 px-2"
            style={{ boxSizing: 'border-box' }}
          >
            <span className="text-sm font-semibold text-green-600" style={{ lineHeight: '1.2' }}>{filledCount}</span>
            <span className="text-[11px] text-slate-400 whitespace-nowrap" style={{ lineHeight: '1.2' }}>部分数据AI填充</span>
          </div>
          <div className="w-px h-5 bg-slate-100"></div>
          <div
            className="flex items-center gap-1 px-2"
            style={{ boxSizing: 'border-box' }}
          >
            <span className="text-sm font-semibold text-orange-500" style={{ lineHeight: '1.2' }}>{ds.datacard_count || 0}</span>
            <span className="text-[11px] text-slate-400 whitespace-nowrap" style={{ lineHeight: '1.2' }}>数据卡片</span>
          </div>
          {(ds.weaviate_num || 0) > 0 && (
            <>
              <div className="w-px h-5 bg-slate-100"></div>
              <div
                className="flex items-center gap-1 px-2"
                style={{ boxSizing: 'border-box' }}
              >
                <span className="text-sm font-semibold text-purple-500" style={{ lineHeight: '1.2' }}>{ds.weaviate_num}</span>
                <span className="text-[11px] text-slate-400 whitespace-nowrap" style={{ lineHeight: '1.2' }}>向量索引</span>
              </div>
            </>
          )}
        </div>

        {/* 右侧：操作按钮 */}
        <div className="flex items-center gap-2 flex-shrink-0 lg:ml-auto">
          <button
            onClick={() => onSettings(ds)}
            className="flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-indigo-600 transition-colors"
          >
            <Settings className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">设置</span>
          </button>
          <button
            onClick={() => onViewDetails(ds)}
            className="flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700 transition-colors"
          >
            <Info className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">详情</span>
          </button>
        </div>
      </div>

      {/* 移动端统计信息 - 小屏幕显示 */}
      <div
        className="xl:hidden mt-3 pt-3 border-t border-slate-100 flex items-center gap-3 text-xs"
        style={{ boxSizing: 'border-box' }}
      >
        <div className="flex items-center gap-1 text-slate-600">
          <Table className="w-3.5 h-3.5" />
          <span><strong>{totalTables}</strong> 表</span>
        </div>
        <div className="flex items-center gap-1 text-green-600">
          <CheckCircle className="w-3.5 h-3.5" />
          <span><strong>{filledCount}</strong> 部分数据AI填充</span>
        </div>
        <div className="flex items-center gap-1 text-orange-500">
          <CreditCard className="w-3.5 h-3.5" />
          <span><strong>{ds.datacard_count || 0}</strong> 卡片</span>
        </div>
        {(ds.weaviate_num || 0) > 0 && (
          <div className="flex items-center gap-1 text-purple-500">
            <CreditCard className="w-3.5 h-3.5" />
            <span><strong>{ds.weaviate_num}</strong> 索引</span>
          </div>
        )}
      </div>
    </div>
  );
};

// 顶部汇总用的小芯片
const SummaryPill = ({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) => (
  <div
    className="inline-flex items-center gap-1.5 bg-white border border-slate-200 px-3 py-1.5 shadow-sm"
    style={{ borderRadius: 9999 }}
  >
    {icon}
    <span className="text-[11px] text-slate-500">{label}</span>
    <span className="text-xs font-semibold text-slate-900">{value}</span>
  </div>
);

const ExploreCard = ({
  title,
  desc,
  btnText,
  icon,
  onClick,
}: {
  title: string;
  desc: string;
  btnText: string;
  icon: React.ReactNode;
  onClick?: () => void;
}) => (
  <div className="bg-white p-3.5 rounded-[17px] border border-slate-200 flex flex-col hover:shadow-md transition-all hover:border-slate-300">
    <div className="flex items-center gap-2 mb-1.5 font-medium text-xs text-slate-900">
      <div className="text-indigo-500">{icon}</div> {title}
    </div>
    <p className="text-[11px] text-slate-500 mb-3 flex-grow leading-relaxed">{desc}</p>
    <button
      className="w-full py-1.5 bg-gradient-to-r from-slate-50 to-slate-100/50 text-slate-700 rounded-[11px] text-[11px] font-medium hover:from-slate-100 hover:to-slate-200/50 transition-all"
      onClick={onClick}
    >
      {btnText}
    </button>
  </div>
);

const QuickActionItem = ({ label, onClick, icon }: { label: string; onClick?: () => void; icon?: React.ReactNode }) => (
  <div
    onClick={onClick}
    className="bg-white p-3 rounded-[16px] border border-slate-200 flex items-center justify-between cursor-pointer hover:border-indigo-300 hover:bg-indigo-50/30 group transition-all"
  >
    <span className="flex items-center gap-2 text-sm font-medium text-slate-700">
      {icon && <span className="text-indigo-500 group-hover:text-indigo-600">{icon}</span>}
      {label}
    </span>
    <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-indigo-500 transition-colors" strokeWidth={2} />
  </div>
);

const ActivityItem = ({ title, status, timeLabel }: { title: string; status: string; timeLabel?: string }) => {
  const getStatusStyle = () => {
    switch (status) {
      case 'Success':
        return { backgroundColor: '#f0fdf4', color: '#16a34a', border: '1px solid #bbf7d0' };
      case 'In Progress':
        return { backgroundColor: '#fefce8', color: '#ca8a04', border: '1px solid #fef08a' };
      default:
        return { backgroundColor: '#eff6ff', color: '#2563eb', border: '1px solid #bfdbfe' };
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'Success': return '成功';
      case 'In Progress': return '进行中';
      case 'New Card': return '新卡片';
      default: return status;
    }
  };

  return (
    <div className="px-3 py-2.5 text-xs hover:bg-slate-50/70 transition-colors border-b last:border-b-0 border-slate-100 flex items-start justify-between gap-2">
      <div className="flex flex-col min-w-0 flex-1">
        <span className="font-medium text-slate-900 truncate" title={title}>{title}</span>
        <span className="text-[10px] text-slate-400 mt-0.5">{timeLabel || '刚刚'}</span>
      </div>
      <span
        style={{
          ...getStatusStyle(),
          padding: '2px 6px',
          borderRadius: '6px',
          fontSize: '10px',
          fontWeight: 500,
          whiteSpace: 'nowrap',
          flexShrink: 0,
        }}
      >
        {getStatusText()}
      </span>
    </div>
  );
};

// 使用流程步骤数据
const guideSteps = [
  {
    id: 'connect',
    title: '连数据源',
    desc: '接入并读取元数据',
  },
  {
    id: 'process',
    title: '自动解析',
    desc: '解析表结构与关系',
    optional: true,
    tag: '可选',
  },
  {
    id: 'quality-check',
    title: '数据质检',
    desc: '自定义规则检测',
    optional: true,
    tag: '推荐',
  },
  {
    id: 'quality-fix',
    title: '问题修复',
    desc: '基于质检结果治理',
    optional: true,
    tag: '可选',
  },
  {
    id: 'enhance',
    title: '数据增强',
    desc: '字典提升卡片质量',
    optional: true,
    tag: '可选',
  },
  {
    id: 'glossary',
    title: '建术语库',
    desc: '提升业务数据理解',
    optional: true,
    tag: '可选',
  },
  {
    id: 'query',
    title: '智能取数',
    desc: '自然语言转 SQL 查询',
  },
  {
    id: 'consume',
    title: '数据消费',
    desc: 'BI/智能体 等对接',
  },
];

// 数据消费场景 - 定义在组件内部以便访问 router
// const consumptionScenarios = [
//   { title: 'BI 系统对接', icon: <BarChart3 className="w-3 h-3" />, type: 'external', url: 'https://onticards.com/docs/bi-integration' },
//   { title: '智能体集成', icon: <Bot className="w-3 h-3" />, type: 'external', url: 'https://onticards.com/docs/agent-integration' },
//   { title: 'API 取数', icon: <Code className="w-3 h-3" />, type: 'internal', path: '/settings', params: { tab: 'api-keys' } },
//   { title: '数据预测分析', icon: <Sparkles className="w-3 h-3" />, type: 'external', url: 'https://onticards.com/docs/analytics' },
// ];

// 流程步骤组件
const GuideStepItem = ({
  step,
  index,
  isLast,
  isDark,
}: {
  step: typeof guideSteps[0];
  index: number;
  isLast: boolean;
  isDark: boolean;
}) => (
  <div className="flex items-start gap-3">
    <div className="flex flex-col items-center">
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center"
        style={{
          backgroundColor: isDark ? 'rgba(99, 102, 241, 0.2)' : '#eef2ff',
        }}
      >
        <span
          className="text-xs font-semibold"
          style={{ color: isDark ? '#a5b4fc' : '#4f46e5' }}
        >
          {index + 1}
        </span>
      </div>
      {!isLast && (
        <div
          className="w-0.5 flex-1 my-1"
          style={{
            background: isDark
              ? 'linear-gradient(to bottom, rgba(99, 102, 241, 0.4), transparent)'
              : 'linear-gradient(to bottom, #c7d2fe, transparent)',
          }}
        />
      )}
    </div>
    <div className="pb-4">
      <span
        className="text-xs font-medium"
        style={{ color: isDark ? '#f1f5f9' : '#374151' }}
      >
        {step.title}
      </span>
    </div>
  </div>
);

export default OverviewPage;
