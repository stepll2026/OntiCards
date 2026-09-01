'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  BarChart3,
  Clock,
  Loader2,
  TrendingUp,
  TrendingDown,
  Zap,
  Database,
  Timer,
  AlertTriangle,
  Eye,
  Server,
  CheckCircle,
  XCircle,
  ArrowUp,
  ArrowDown,
  Minus,
  PieChart,
  Flame,
  Target,
  Calendar,
  Users,
  GitBranch,
  Maximize,
  Minimize,
  Gauge,
  Wifi,
  WifiOff,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';
import { useUserInfo } from '@/hooks';
import {
  getMonitoringOverview,
  getMonitoringTrend,
  getMonitoringRealtime,
  getMonitoringPerformance,
  MonitoringOverviewResponse,
  MonitoringTrendResponse,
  MonitoringRealtimeResponse,
  MonitoringPerformanceResponse,
} from '@/api/monitoring';

type TabType = 'overview' | 'trend' | 'realtime' | 'performance';

const tabs = [
  { id: 'overview', label: '监控总览', icon: <Activity size={16} /> },
  { id: 'trend', label: '趋势分析', icon: <TrendingUp size={16} /> },
  { id: 'realtime', label: '实时监控', icon: <Zap size={16} /> },
  { id: 'performance', label: '性能分析', icon: <BarChart3 size={16} /> },
];

const styles = {
  container: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    color: 'rgb(var(--theme-text))',
  } as React.CSSProperties,
  header: {
    marginBottom: '24px',
  } as React.CSSProperties,
  title: {
    fontSize: '24px',
    fontWeight: 600,
    color: 'rgb(var(--theme-text))',
    marginBottom: '4px',
  } as React.CSSProperties,
  subtitle: {
    fontSize: '14px',
    color: 'rgb(var(--theme-text-muted))',
  } as React.CSSProperties,
  tabNav: {
    display: 'flex',
    gap: '8px',
    borderBottom: '1px solid rgb(var(--theme-border))',
    marginBottom: '24px',
  } as React.CSSProperties,
  tabButton: (active: boolean) => ({
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '12px 16px',
    fontSize: '14px',
    fontWeight: 500,
    border: 'none',
    borderBottom: active ? '2px solid rgb(var(--theme-primary))' : '2px solid transparent',
    background: 'transparent',
    color: active ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-muted))',
    cursor: 'pointer',
    transition: 'all 0.2s',
  } as React.CSSProperties),
  loadingContainer: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '400px',
  } as React.CSSProperties,
  loadingSpinner: {
    animation: 'spin 1s linear infinite',
    color: 'rgb(var(--theme-primary))',
  } as React.CSSProperties,
  grid: {
    display: 'grid',
    gap: '20px',
  } as React.CSSProperties,
  grid2: {
    gridTemplateColumns: 'repeat(2, 1fr)',
  } as React.CSSProperties,
  grid3: {
    gridTemplateColumns: 'repeat(3, 1fr)',
  } as React.CSSProperties,
  grid4: {
    gridTemplateColumns: 'repeat(4, 1fr)',
  } as React.CSSProperties,
  grid5: {
    gridTemplateColumns: 'repeat(5, 1fr)',
  } as React.CSSProperties,
  card: {
    background: 'rgb(var(--theme-bg))',
    borderRadius: '16px',
    borderColor: 'rgb(var(--theme-border))',
    padding: '20px',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
  } as React.CSSProperties,
  cardTitle: {
    fontSize: '16px',
    fontWeight: 600,
    color: 'rgb(var(--theme-text))',
    marginBottom: '16px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  } as React.CSSProperties,
  cardTitleIcon: {
    color: 'rgb(var(--theme-primary))',
  } as React.CSSProperties,
  statCard: {
    background: 'rgb(var(--theme-bg))',
    borderRadius: '16px',
    borderColor: 'rgb(var(--theme-border))',
    padding: '20px',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
  } as React.CSSProperties,
  statCardContent: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  } as React.CSSProperties,
  statIcon: (color: string) => ({
    width: '48px',
    height: '48px',
    borderRadius: '12px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'rgba(var(--theme-primary), 0.12)',
    color: 'rgb(var(--theme-primary))',
  } as React.CSSProperties),
  statLabel: {
    fontSize: '12px',
    color: 'rgb(var(--theme-text-muted))',
    marginBottom: '4px',
  } as React.CSSProperties,
  statValue: {
    fontSize: '24px',
    fontWeight: 700,
    color: 'rgb(var(--theme-text))',
  } as React.CSSProperties,
  statSubtext: {
    fontSize: '12px',
    color: 'rgb(var(--theme-text-muted))',
    marginTop: '2px',
  } as React.CSSProperties,
  trendBadge: (positive: boolean) => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: '2px',
    fontSize: '12px',
    fontWeight: 500,
    color: positive ? 'rgb(16, 185, 129)' : 'rgb(239, 68, 68)',
    marginLeft: '8px',
  } as React.CSSProperties),
  progressBar: {
    height: '8px',
    background: 'rgb(var(--theme-bg-tertiary))',
    borderRadius: '4px',
    overflow: 'hidden',
  } as React.CSSProperties,
  progressFill: (percent: number, color: string = 'rgb(var(--theme-primary))') => ({
    height: '100%',
    width: `${percent}%`,
    background: color,
    borderRadius: '4px',
    transition: 'width 0.3s ease',
  } as React.CSSProperties),
  miniProgress: {
    height: '4px',
    background: 'rgb(var(--theme-bg-tertiary))',
    borderRadius: '2px',
    overflow: 'hidden',
  } as React.CSSProperties,
  table: {
    width: '100%',
    borderCollapse: 'collapse' as const,
    fontSize: '14px',
  } as React.CSSProperties,
  tableHeader: {
    textAlign: 'left' as const,
    padding: '12px 16px',
    fontSize: '12px',
    fontWeight: 500,
    color: 'rgb(var(--theme-text-secondary))',
    borderBottom: '1px solid rgb(var(--theme-border))',
  } as React.CSSProperties,
  tableCell: {
    padding: '12px 16px',
    borderBottom: '1px solid rgb(var(--theme-border))',
    color: 'rgb(var(--theme-text))',
  } as React.CSSProperties,
  tableCellRight: {
    padding: '12px 16px',
    borderBottom: '1px solid rgb(var(--theme-border))',
    color: 'rgb(var(--theme-text))',
    textAlign: 'right' as const,
  } as React.CSSProperties,
  badge: (color: string) => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    padding: '4px 10px',
    borderRadius: '9999px',
    fontSize: '12px',
    fontWeight: 500,
    background: 'rgba(var(--theme-primary), 0.12)',
    color: 'rgb(var(--theme-primary))',
  } as React.CSSProperties),
  flex: {
    display: 'flex',
  } as React.CSSProperties,
  flexBetween: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  } as React.CSSProperties,
  gap2: {
    gap: '8px',
  } as React.CSSProperties,
  gap3: {
    gap: '12px',
  } as React.CSSProperties,
  gap4: {
    gap: '16px',
  } as React.CSSProperties,
  textSm: {
    fontSize: '14px',
    color: 'rgb(var(--theme-text))',
  } as React.CSSProperties,
  textXs: {
    fontSize: '12px',
    color: 'rgb(var(--theme-text-muted))',
  } as React.CSSProperties,
  textGray: {
    color: 'rgb(var(--theme-text-muted))',
  } as React.CSSProperties,
  textGreen: {
    color: 'rgb(16, 185, 129)',
  } as React.CSSProperties,
  textRed: {
    color: 'rgb(239, 68, 68)',
  } as React.CSSProperties,
  textAmber: {
    color: 'rgb(245, 158, 11)',
  } as React.CSSProperties,
  textIndigo: {
    color: 'rgb(var(--theme-primary))',
  } as React.CSSProperties,
  bgSlate: {
    background: 'rgb(var(--theme-bg-secondary))',
  } as React.CSSProperties,
  rounded: {
    borderRadius: '12px',
  } as React.CSSProperties,
  p3: {
    padding: '12px',
  } as React.CSSProperties,
  p4: {
    padding: '16px',
  } as React.CSSProperties,
  statusDot: (color: string) => ({
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    background: color,
  } as React.CSSProperties),
  chartContainer: {
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    height: '120px',
    padding: '0 8px',
  } as React.CSSProperties,
  chartBar: (height: number, maxHeight: number, color: string = 'rgb(var(--theme-primary))') => ({
    width: '100%',
    maxWidth: '24px',
    height: `${(height / maxHeight) * 100}%`,
    minHeight: '4px',
    background: `linear-gradient(to top, ${color}, ${color}aa)`,
    borderRadius: '4px 4px 0 0',
    cursor: 'pointer',
    transition: 'all 0.2s',
  } as React.CSSProperties),
  barItem: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    gap: '4px',
  } as React.CSSProperties,
  barLabel: {
    fontSize: '10px',
    color: 'rgb(var(--theme-text-muted))',
  } as React.CSSProperties,
  compareCard: {
    background: 'rgb(var(--theme-bg-secondary))',
    borderRadius: '12px',
    padding: '16px',
  } as React.CSSProperties,
  compareTitle: {
    fontSize: '13px',
    fontWeight: 500,
    color: 'rgb(var(--theme-text-secondary))',
    marginBottom: '12px',
  } as React.CSSProperties,
  compareRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '6px 0',
  } as React.CSSProperties,
  sectionTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: 'rgb(var(--theme-text))',
    marginBottom: '12px',
  } as React.CSSProperties,
  errorAlert: (type: 'error' | 'warning' | 'success') => ({
    background: type === 'error' ? 'rgba(239, 68, 68, 0.1)' : type === 'warning' ? 'rgba(245, 158, 11, 0.1)' : 'rgba(16, 185, 129, 0.1)',
    border: `1px solid ${type === 'error' ? 'rgba(239, 68, 68, 0.3)' : type === 'warning' ? 'rgba(245, 158, 11, 0.3)' : 'rgba(16, 185, 129, 0.3)'}`,
    borderRadius: '10px',
    padding: '12px',
    marginBottom: '8px',
  } as React.CSSProperties),
  alertTitle: (type: 'error' | 'warning' | 'success') => ({
    fontSize: '13px',
    fontWeight: 500,
    color: type === 'error' ? 'rgb(220, 38, 38)' : type === 'warning' ? 'rgb(217, 119, 6)' : 'rgb(5, 150, 105)',
  } as React.CSSProperties),
  alertContent: {
    fontSize: '12px',
    color: 'rgb(var(--theme-text-muted))',
    marginTop: '4px',
  } as React.CSSProperties,
  patternBar: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '8px 0',
  } as React.CSSProperties,
  qualityCard: {
    background: 'rgba(var(--theme-primary), 0.05)',
    borderRadius: '12px',
    padding: '16px',
    border: '1px solid rgba(var(--theme-primary), 0.2)',
  } as React.CSSProperties,
};

const formatDuration = (ms: number) => {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
};

const formatTokens = (n: number) => {
  if (n >= 1000000) return `${(n / 1000000).toFixed(2)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
};

// 格式化变化率，处理 N/A 情况
const formatChangeRate = (rate: string | null | undefined, context?: string) => {
  if (rate === 'N/A' || rate === null || rate === undefined) {
    return { value: 'N/A', tooltip: context || '前期无数据，无法计算', isNA: true };
  }
  return { value: rate, tooltip: '', isNA: false };
};

// 根据变化率字符串获取颜色
const getChangeRateColor = (rate: string | null | undefined) => {
  if (rate === 'N/A' || rate === null || rate === undefined) {
    return 'rgb(var(--theme-text-muted))';
  }
  // 去掉符号后判断正负
  const numRate = parseFloat(rate.replace('%', '').replace('+', ''));
  if (numRate >= 0) return 'rgb(16, 185, 129)'; // 绿色表示增长/改善
  return 'rgb(239, 68, 68)'; // 红色表示下降/恶化
};

// 对于耗时类指标，数值下降是好的
const getDurationChangeColor = (rate: string | null | undefined) => {
  if (rate === 'N/A' || rate === null || rate === undefined) {
    return 'rgb(var(--theme-text-muted))';
  }
  const numRate = parseFloat(rate.replace('%', '').replace('+', ''));
  if (numRate <= 0) return 'rgb(16, 185, 129)'; // 耗时下降是好的
  return 'rgb(239, 68, 68)'; // 耗时上升是不好的
};

// N/A 提示图标组件
const NADot = ({ title }: { title?: string }) => (
  <span
    title={title || '前期无数据，无法计算'}
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: '16px',
      height: '16px',
      borderRadius: '50%',
      background: 'rgba(245, 158, 11, 0.2)',
      color: 'rgb(var(--theme-text-muted))',
      fontSize: '11px',
      fontWeight: 600,
      marginLeft: '4px',
    }}
  >
    ?
  </span>
);

const getStatusColor = (status: string) => {
  switch (status) {
    case 'healthy':
    case 'success':
      return { bg: 'rgba(22, 163, 74, 0.15)', text: 'rgb(22, 163, 74)', dot: 'rgb(34, 197, 94)' };
    case 'warning':
    case 'degraded':
      return { bg: 'rgba(245, 158, 11, 0.15)', text: 'rgb(217, 119, 6)', dot: 'rgb(245, 158, 11)' };
    case 'critical':
    case 'error':
      return { bg: 'rgba(220, 38, 38, 0.15)', text: 'rgb(220, 38, 38)', dot: 'rgb(239, 68, 68)' };
    default:
      return { bg: 'rgb(var(--theme-bg-tertiary))', text: 'rgb(var(--theme-text-muted))', dot: 'rgb(var(--theme-text-muted))' };
  }
};

const getTrendIcon = (trend: string, isPositive: boolean = true) => {
  if (trend === 'stable') return <Minus size={14} />;
  if ((trend === 'growth' || trend === 'decreasing') && isPositive) return <ArrowUp size={14} />;
  if ((trend === 'growth' || trend === 'decreasing') && !isPositive) return <ArrowDown size={14} />;
  if (trend === 'increasing') return <ArrowUp size={14} />;
  if (trend === 'decline') return <ArrowDown size={14} />;
  return <Minus size={14} />;
};

interface MonitoringPageProps {
  workspaceId?: string;
  title?: string;
}

const MonitoringPage = ({ workspaceId, title = '监控中心' }: MonitoringPageProps) => {
  const { userInfo } = useUserInfo();
  const currentUserId = userInfo?.id || '';

  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [loading, setLoading] = useState(false);

  const [overview, setOverview] = useState<MonitoringOverviewResponse['data'] | null>(null);
  const [trend, setTrend] = useState<MonitoringTrendResponse['data'] | null>(null);
  const [realtime, setRealtime] = useState<MonitoringRealtimeResponse['data'] | null>(null);
  const [performance, setPerformance] = useState<MonitoringPerformanceResponse['data'] | null>(null);

  const [trendDays, setTrendDays] = useState(30);
  const [perfDays, setPerfDays] = useState(7);

  const fetchOverview = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (workspaceId) params.workspace_id = workspaceId;
      else if (currentUserId) params.user_id = currentUserId;

      const res = await getMonitoringOverview(params);
      if (res.code === 200 && res.data) {
        setOverview(res.data);
      }
    } catch (e) {
      console.error('获取监控总览失败', e);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, currentUserId]);

  const fetchTrend = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { days: trendDays };
      if (workspaceId) params.workspace_id = workspaceId;
      else if (currentUserId) params.user_id = currentUserId;

      const res = await getMonitoringTrend(params);
      if (res.code === 200 && res.data) {
        setTrend(res.data);
      }
    } catch (e) {
      console.error('获取监控趋势失败', e);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, currentUserId, trendDays]);

  const fetchRealtime = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (workspaceId) params.workspace_id = workspaceId;
      else if (currentUserId) params.user_id = currentUserId;

      const res = await getMonitoringRealtime(params);
      if (res.code === 200 && res.data) {
        setRealtime(res.data);
      }
    } catch (e) {
      console.error('获取实时监控失败', e);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, currentUserId]);

  const fetchPerformance = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { days: perfDays };
      if (workspaceId) params.workspace_id = workspaceId;
      else if (currentUserId) params.user_id = currentUserId;

      const res = await getMonitoringPerformance(params);
      if (res.code === 200 && res.data) {
        setPerformance(res.data);
      }
    } catch (e) {
      console.error('获取性能分析失败', e);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, currentUserId, perfDays]);

  useEffect(() => {
    if (!currentUserId) return;
    if (activeTab === 'overview') fetchOverview();
    if (activeTab === 'trend') fetchTrend();
    if (activeTab === 'realtime') fetchRealtime();
    if (activeTab === 'performance') fetchPerformance();
  }, [activeTab, currentUserId, fetchOverview, fetchTrend, fetchRealtime, fetchPerformance]);

  return (
    <div style={styles.container}>
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .hover-bg:hover {
          background: rgb(var(--theme-bg-secondary));
        }
        .chart-bar:hover {
          opacity: 0.8;
          transform: scaleY(1.05);
        }
      `}</style>

      <header style={styles.header}>
        <h1 style={styles.title}>{title}</h1>
        <p style={styles.subtitle}>系统运行监控、数据分析和性能监控</p>
      </header>

      <nav style={styles.tabNav}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as TabType)}
            style={styles.tabButton(activeTab === tab.id)}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </nav>

      <div style={{ minHeight: '500px' }}>
        {loading ? (
          <div style={styles.loadingContainer}>
            <Loader2 size={32} style={styles.loadingSpinner} />
          </div>
        ) : (
          <>
            {activeTab === 'overview' && <OverviewTab overview={overview} />}
            {activeTab === 'trend' && <TrendTab trend={trend} days={trendDays} setDays={setTrendDays} />}
            {activeTab === 'realtime' && <RealtimeTab realtime={realtime} />}
            {activeTab === 'performance' && <PerformanceTab performance={performance} days={perfDays} setDays={setPerfDays} />}
          </>
        )}
      </div>
    </div>
  );
};

// ==================== 监控总览 ====================

function OverviewTab({ overview }: { overview: MonitoringOverviewResponse['data'] | null }) {
  if (!overview) return null;

  const comparison = overview.comparison;
  const hourlyDist = overview.hourly_distribution;
  const datasourceStats = overview.datasource_stats;
  const statusBreakdown = overview.status_breakdown;
  const qualityMetrics = overview.quality_metrics;

  const distribution = hourlyDist?.distribution || [];
  const maxQueries = Math.max(...distribution.map(d => d.queries), 1);
  const topDatasources = (datasourceStats?.top_datasources || []).slice(0, 3);

  return (
    <div style={{ ...styles.grid, gap: '20px' }}>
      {/* 核心指标卡片 */}
      <div style={{ ...styles.grid, ...styles.grid4, gap: '16px' }}>
        <div style={styles.statCard}>
            <div style={styles.statCardContent}>
            <div style={{ ...styles.statIcon('indigo'), background: 'rgba(var(--theme-primary), 0.12)', color: 'rgb(var(--theme-primary))' }}>
              <Activity size={24} />
            </div>
            <div>
              <div style={styles.statLabel}>24小时查询</div>
              <div style={styles.flex}>
                <span style={styles.statValue}>{overview.recent_24h.total_queries.toLocaleString()}</span>
                {comparison?.vs_yesterday && (
                  <span style={styles.trendBadge(comparison.vs_yesterday.is_positive)}>
                    {getTrendIcon(comparison.vs_yesterday.is_positive ? 'growth' : 'decline')}
                    {comparison.vs_yesterday.queries_change_rate}
                  </span>
                )}
              </div>
              <div style={styles.statSubtext}>成功率 {overview.recent_24h.success_rate.toFixed(1)}%</div>
            </div>
          </div>
        </div>

        <div style={styles.statCard}>
          <div style={styles.statCardContent}>
            <div style={{ ...styles.statIcon('green'), background: 'rgba(16, 185, 129, 0.12)', color: 'rgb(16, 185, 129)' }}>
              <Clock size={24} />
            </div>
            <div>
              <div style={styles.statLabel}>今日查询</div>
              <span style={styles.statValue}>{overview.today.total_queries.toLocaleString()}</span>
              <div style={styles.statSubtext}>成功 {overview.today.success_queries}</div>
            </div>
          </div>
        </div>

        <div style={styles.statCard}>
          <div style={styles.statCardContent}>
            <div style={{ ...styles.statIcon('blue'), background: 'rgba(59, 130, 246, 0.12)', color: 'rgb(59, 130, 246)' }}>
              <Database size={24} />
            </div>
            <div>
              <div style={styles.statLabel}>24小时Token</div>
              <span style={styles.statValue}>{formatTokens(overview.recent_24h.total_tokens)}</span>
              <div style={styles.statSubtext}>LLM: {formatTokens(overview.recent_24h.llm_tokens)}</div>
            </div>
          </div>
        </div>

        <div style={styles.statCard}>
          <div style={styles.statCardContent}>
            <div style={{ ...styles.statIcon('amber'), background: 'rgba(245, 158, 11, 0.12)', color: 'rgb(245, 158, 11)' }}>
              <TrendingUp size={24} />
            </div>
            <div>
              <div style={styles.statLabel}>近30天总成本估算</div>
              <span style={styles.statValue}>¥{overview.summary_30d.total_cost_yuan.toFixed(2)}</span>
              <div style={styles.statSubtext}>Token: {formatTokens(overview.summary_30d.total_tokens)}</div>
            </div>
          </div>
        </div>
      </div>

      {/* 对比分析 + 24小时分布 */}
      <div style={{ ...styles.grid, ...styles.grid2, gap: '20px' }}>
        {/* 历史对比 */}
        {comparison && (
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>
              <GitBranch size={18} style={styles.cardTitleIcon} />
              历史对比分析
            </h3>
            <div style={{ ...styles.grid, ...styles.grid2, gap: '16px' }}>
              <div style={styles.compareCard}>
                <div style={styles.compareTitle}>vs 昨日 增长率</div>
                <div style={styles.compareRow}>
                  <span style={styles.textGray}>查询量</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ fontWeight: 500, color: getChangeRateColor(comparison.vs_yesterday.queries_change_rate) }}>
                      {formatChangeRate(comparison.vs_yesterday.queries_change_rate, '昨日无数据').value}
                    </span>
                    {formatChangeRate(comparison.vs_yesterday.queries_change_rate).isNA && (
                      <NADot title="昨日无数据，无法计算增长率" />
                    )}
                  </span>
                </div>
                <div style={styles.compareRow}>
                  <span style={styles.textGray}>Token</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ fontWeight: 500, color: getChangeRateColor(comparison.vs_yesterday.tokens_change_rate) }}>
                      {formatChangeRate(comparison.vs_yesterday.tokens_change_rate).value}
                    </span>
                    {formatChangeRate(comparison.vs_yesterday.tokens_change_rate).isNA && (
                      <NADot title="昨日无数据" />
                    )}
                  </span>
                </div>
                <div style={styles.compareRow}>
                  <span style={styles.textGray}>平均耗时</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ fontWeight: 500, color: getDurationChangeColor(comparison.vs_yesterday.avg_duration_change_rate) }}>
                      {formatChangeRate(comparison.vs_yesterday.avg_duration_change_rate).value}
                    </span>
                    {formatChangeRate(comparison.vs_yesterday.avg_duration_change_rate).isNA && (
                      <NADot title="昨日无数据" />
                    )}
                  </span>
                </div>
              </div>
              <div style={styles.compareCard}>
                <div style={styles.compareTitle}>vs 上周同期 增长率</div>
                <div style={styles.compareRow}>
                  <span style={styles.textGray}>查询量</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ fontWeight: 500, color: getChangeRateColor(comparison.vs_last_week.queries_change_rate) }}>
                      {formatChangeRate(comparison.vs_last_week.queries_change_rate, '上周同期无数据').value}
                    </span>
                    {formatChangeRate(comparison.vs_last_week.queries_change_rate).isNA && (
                      <NADot title="上周同期无数据" />
                    )}
                  </span>
                </div>
                <div style={styles.compareRow}>
                  <span style={styles.textGray}>Token</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ fontWeight: 500, color: getChangeRateColor(comparison.vs_last_week.tokens_change_rate) }}>
                      {formatChangeRate(comparison.vs_last_week.tokens_change_rate).value}
                    </span>
                    {formatChangeRate(comparison.vs_last_week.tokens_change_rate).isNA && (
                      <NADot title="上周同期无数据" />
                    )}
                  </span>
                </div>
                <div style={styles.compareRow}>
                  <span style={styles.textGray}>平均耗时</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ fontWeight: 500, color: getDurationChangeColor(comparison.vs_last_week.avg_duration_change_rate) }}>
                      {formatChangeRate(comparison.vs_last_week.avg_duration_change_rate).value}
                    </span>
                    {formatChangeRate(comparison.vs_last_week.avg_duration_change_rate).isNA && (
                      <NADot title="上周同期无数据" />
                    )}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 24小时分布 */}
        {distribution.length > 0 && (
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>
              <Flame size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(249, 115, 22)' }} />
              24小时访问热度
              <span style={{ fontSize: '12px', fontWeight: 400, color: 'rgb(var(--theme-text-muted))' }}>
                峰值: {hourlyDist?.peak_hour_label}
              </span>
            </h3>
            <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', height: '100px', padding: '0 4px' }}>
              {distribution.map((item) => (
                <div key={item.hour} style={styles.barItem} className="bar-item">
                  <div
                    className="chart-bar"
                    style={{
                      ...styles.chartBar(item.queries, maxQueries, '#6366f1'),
                      height: `${Math.max(4, (item.queries / maxQueries) * 80)}px`,
                    }}
                  />
                  <span style={styles.barLabel}>{item.hour}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 性能 + 状态分布 */}
      <div style={{ ...styles.grid, ...styles.grid2, gap: '20px' }}>
        {/* 性能指标 */}
        <div style={styles.card}>
          <h3 style={styles.cardTitle}>
            <Gauge size={18} style={styles.cardTitleIcon} />
            性能指标
          </h3>
          <div style={{ ...styles.grid, ...styles.grid4, gap: '12px' }}>
            <div style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p3, textAlign: 'center' }}>
              <div style={styles.textGray}>平均耗时</div>
              <div style={{ ...styles.textIndigo, fontSize: '18px', fontWeight: 600, marginTop: '4px' }}>
                {formatDuration(overview.recent_24h.avg_duration_ms)}
              </div>
            </div>
            <div style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p3, textAlign: 'center' }}>
              <div style={styles.textGray}>成功数</div>
              <div style={{ ...styles.textGreen, fontSize: '18px', fontWeight: 600, marginTop: '4px' }}>
                {overview.recent_24h.success_queries}
              </div>
            </div>
            <div style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p3, textAlign: 'center' }}>
              <div style={styles.textGray}>错误数</div>
              <div style={{ ...styles.textRed, fontSize: '18px', fontWeight: 600, marginTop: '4px' }}>
                {overview.recent_24h.error_queries}
              </div>
            </div>
            <div style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p3, textAlign: 'center' }}>
              <div style={styles.textGray}>超时数</div>
              <div style={{ ...styles.textAmber, fontSize: '18px', fontWeight: 600, marginTop: '4px' }}>
                {overview.recent_24h.timeout_queries}
              </div>
            </div>
          </div>
        </div>

        {/* 状态分布 */}
        {statusBreakdown && (
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>
              <PieChart size={18} style={styles.cardTitleIcon} />
              查询状态分布
            </h3>
            <div style={{ ...styles.grid, ...styles.grid3, gap: '12px' }}>
              <div>
                <div style={{ ...styles.flex, ...styles.gap2, marginBottom: '8px', alignItems: 'center' }}>
                  <CheckCircle size={16} style={{ color: 'rgb(34, 197, 94)' }} />
                  <span style={styles.textSm}>成功</span>
                </div>
                <div style={styles.progressBar}>
                  <div style={styles.progressFill(statusBreakdown.success.percentage, '#22c55e')} />
                </div>
                <div style={{ ...styles.flex, ...styles.gap2, marginTop: '6px', justifyContent: 'space-between' }}>
                  <span style={styles.textXs}>{statusBreakdown.success.count}次</span>
                  <span style={{ ...styles.textXs, ...styles.textGreen }}>{statusBreakdown.success.percentage.toFixed(1)}%</span>
                </div>
              </div>
              <div>
                <div style={{ ...styles.flex, ...styles.gap2, marginBottom: '8px', alignItems: 'center' }}>
                  <XCircle size={16} style={{ color: 'rgb(239, 68, 68)' }} />
                  <span style={styles.textSm}>错误</span>
                </div>
                <div style={styles.progressBar}>
                  <div style={styles.progressFill(statusBreakdown.error.percentage, '#ef4444')} />
                </div>
                <div style={{ ...styles.flex, ...styles.gap2, marginTop: '6px', justifyContent: 'space-between' }}>
                  <span style={styles.textXs}>{statusBreakdown.error.count}次</span>
                  <span style={{ ...styles.textXs, ...styles.textRed }}>{statusBreakdown.error.percentage.toFixed(1)}%</span>
                </div>
              </div>
              <div>
                <div style={{ ...styles.flex, ...styles.gap2, marginBottom: '8px', alignItems: 'center' }}>
                  <Timer size={16} style={{ color: 'rgb(245, 158, 11)' }} />
                  <span style={styles.textSm}>超时</span>
                </div>
                <div style={styles.progressBar}>
                  <div style={styles.progressFill(statusBreakdown.timeout.percentage, '#f59e0b')} />
                </div>
                <div style={{ ...styles.flex, ...styles.gap2, marginTop: '6px', justifyContent: 'space-between' }}>
                  <span style={styles.textXs}>{statusBreakdown.timeout.count}次</span>
                  <span style={{ ...styles.textXs, ...styles.textAmber }}>{statusBreakdown.timeout.percentage.toFixed(1)}%</span>
                </div>
              </div>
            </div>
            {statusBreakdown.error.top_errors && statusBreakdown.error.top_errors.length > 0 && (
              <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid #e5e7eb' }}>
                <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))', marginBottom: '6px' }}>TOP 错误类型</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {statusBreakdown.error.top_errors.map((err, idx) => (
                    <span key={idx} style={{
                      fontSize: '11px',
                      padding: '2px 8px',
                      background: '#fef2f2',
                      color: 'rgb(220, 38, 38)',
                      borderRadius: '4px',
                    }}>
                      {err}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 数据源排行 */}
      {topDatasources.length > 0 && (
        <div style={styles.card}>
          <h3 style={styles.cardTitle}>
            <Server size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(59, 130, 246)' }} />
            数据源使用排行 TOP {topDatasources.length}
            <span style={{ fontSize: '12px', fontWeight: 400, color: 'rgb(var(--theme-text-muted))' }}>
              共 {datasourceStats?.total_datasources_used || topDatasources.length} 个数据源
            </span>
          </h3>
          <div style={{ ...styles.grid, gap: '12px' }}>
            {topDatasources.map((ds, idx) => (
              <div key={ds.datasource_name} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  background: idx === 0 ? '#6366f1' : idx === 1 ? '#8b5cf6' : '#a855f7',
                  color: '#fff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '12px',
                  fontWeight: 600,
                  flexShrink: 0,
                }}>
                  {idx + 1}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ ...styles.flexBetween, marginBottom: '6px' }}>
                    <span style={{ fontSize: '14px', fontWeight: 500, color: 'rgb(var(--theme-text))' }}>{ds.datasource_name}</span>
                    <span style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>{ds.query_count} 次 ({ds.percentage.toFixed(1)}%)</span>
                  </div>
                  <div style={styles.miniProgress}>
                    <div style={{ ...styles.progressFill(ds.percentage, '#6366f1') }} />
                  </div>
                </div>
                <span style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))', minWidth: '60px', textAlign: 'right' }}>
                  {formatDuration(ds.avg_duration_ms)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 质量指标 */}
      {qualityMetrics && (
        <div style={styles.qualityCard}>
          <h3 style={styles.cardTitle}>
            <Target size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(139, 92, 246)' }} />
            查询质量指标
          </h3>
          <div style={{ ...styles.grid, ...styles.grid5, gap: '16px' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 700, color: 'rgb(var(--theme-primary))' }}>{qualityMetrics.avg_cards_recalled.toFixed(1)}</div>
              <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>平均召回卡片</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 700, color: 'rgb(139, 92, 246)' }}>{qualityMetrics.avg_cards_selected.toFixed(1)}</div>
              <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>平均精选卡片</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 700, color: 'rgb(59, 130, 246)' }}>{qualityMetrics.avg_top1_score.toFixed(3)}</div>
              <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>Top1分数</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 700, color: 'rgb(22, 163, 74)' }}>{qualityMetrics.avg_result_count.toFixed(0)}</div>
              <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>平均结果数</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 700, color: qualityMetrics.zero_result_rate > 5 ? '#ef4444' : '#10b981' }}>
                {qualityMetrics.zero_result_rate.toFixed(1)}%
              </div>
              <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>零结果率</div>
            </div>
          </div>
        </div>
      )}

      {/* 查询次数趋势曲线图 */}
      {overview.daily_trend && overview.daily_trend.length > 0 && (
        <div style={styles.card}>
          <h3 style={styles.cardTitle}>
            <TrendingUp size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(var(--theme-primary))' }} />
            查询次数趋势
          </h3>
          <div style={{ width: '100%', height: '200px' }}>
            <ResponsiveContainer>
              <AreaChart data={overview.daily_trend.slice().sort((a, b) => a.date.localeCompare(b.date))} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorQueries" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--theme-border))" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 12, fill: 'rgb(var(--theme-text-muted))' }}
                  tickLine={false}
                  axisLine={{ stroke: 'rgb(var(--theme-border))' }}
                />
                <YAxis
                  tick={{ fontSize: 12, fill: 'rgb(var(--theme-text-muted))' }}
                  tickLine={false}
                  axisLine={{ stroke: 'rgb(var(--theme-border))' }}
                  width={45}
                />
                <Tooltip
                  contentStyle={{
                    background: 'rgb(var(--theme-bg))',
                    borderColor: 'rgb(var(--theme-border))',
                    borderRadius: '8px',
                    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                    color: 'rgb(var(--theme-text))',
                  }}
                  labelStyle={{ color: 'rgb(var(--theme-text))', fontWeight: 500 }}
                  itemStyle={{ color: 'rgb(var(--theme-primary))' }}
                  formatter={(value: number) => [value.toLocaleString(), '查询次数']}
                />
                <Area
                  type="monotone"
                  dataKey="total_queries"
                  stroke="#6366f1"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorQueries)"
                  name="查询次数"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* 近7日趋势 */}
      <div style={styles.card}>
        <h3 style={styles.cardTitle}>近7日趋势</h3>
        {overview.daily_trend && overview.daily_trend.length > 0 ? (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.tableHeader}>日期</th>
                <th style={{ ...styles.tableHeader, textAlign: 'right' }}>查询量</th>
                <th style={{ ...styles.tableHeader, textAlign: 'right' }}>成功率</th>
                <th style={{ ...styles.tableHeader, textAlign: 'right' }}>Token</th>
                <th style={{ ...styles.tableHeader, textAlign: 'right' }}>成本</th>
              </tr>
            </thead>
            <tbody>
              {overview.daily_trend.slice(0, 7).map(item => (
                <tr key={item.date} style={{ cursor: 'pointer' }} className="hover-bg">
                  <td style={styles.tableCell}>{item.date}</td>
                  <td style={{ ...styles.tableCellRight, fontWeight: 500 }}>{item.total_queries.toLocaleString()}</td>
                  <td style={{ ...styles.tableCellRight, ...styles.textGreen }}>{item.success_rate.toFixed(1)}%</td>
                  <td style={{ ...styles.tableCellRight }}>{formatTokens(item.total_tokens)}</td>
                  <td style={{ ...styles.tableCellRight }}>¥{item.cost_yuan.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div style={{ textAlign: 'center', padding: '40px', color: 'rgb(var(--theme-text-muted))' }}>
            <p style={{ fontSize: '14px' }}>近七日暂无查询数据</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== 趋势分析 ====================

function TrendTab({ trend, days, setDays }: {
  trend: MonitoringTrendResponse['data'] | null
  days: number
  setDays: (d: number) => void
}) {
  if (!trend) return null;

  const statistics = trend.statistics;
  const growthAnalysis = trend.growth_analysis;
  const peakValley = trend.peak_valley;
  const weeklyPattern = trend.weekly_pattern;

  const dayOptions = [7, 14, 30, 90];

  return (
    <div style={{ ...styles.grid, gap: '20px' }}>
      {/* 时间选择器 */}
      <div style={styles.flexBetween}>
        <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>趋势分析</h3>
        <div style={{ ...styles.flex, ...styles.gap2 }}>
          {dayOptions.map(d => (
            <button
              key={d}
              onClick={() => setDays(d)}
              style={{
                padding: '6px 14px',
                fontSize: '13px',
                fontWeight: 500,
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                background: days === d ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-bg-secondary))',
                color: days === d ? '#fff' : 'rgb(var(--theme-text-muted))',
                transition: 'all 0.2s',
              }}
            >
              {d}天
            </button>
          ))}
        </div>
      </div>

      {/* 统计概览 */}
      {statistics && (
        <div style={{ background: 'rgba(var(--theme-primary), 0.05)', borderRadius: '16px', border: '1px solid rgba(var(--theme-primary), 0.2)', padding: '20px' }}>
          <h3 style={styles.cardTitle}>
            <Activity size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(var(--theme-primary))' }} />
            数据概览
            <span style={{ fontSize: '12px', fontWeight: 400, color: 'rgb(var(--theme-text-muted))' }}>
              ({statistics.data_days}/{statistics.total_days}天有数据)
            </span>
          </h3>
          <div style={{ ...styles.grid, ...styles.grid4, gap: '16px' }}>
            <div style={{ background: 'rgb(var(--theme-bg))', borderRadius: '12px', padding: '16px', textAlign: 'center', borderColor: 'rgb(var(--theme-border))' }}>
              <div style={{ fontSize: '28px', fontWeight: 700, color: 'rgb(var(--theme-primary))' }}>{statistics.total_queries.toLocaleString()}</div>
              <div style={{ ...styles.textXs }}>总查询数</div>
            </div>
            <div style={{ background: 'rgb(var(--theme-bg))', borderRadius: '12px', padding: '16px', textAlign: 'center', borderColor: 'rgb(var(--theme-border))' }}>
              <div style={{ fontSize: '28px', fontWeight: 700, color: 'rgb(59, 130, 246)' }}>{formatTokens(statistics.total_tokens)}</div>
              <div style={{ ...styles.textXs }}>总Token</div>
            </div>
            <div style={{ background: 'rgb(var(--theme-bg))', borderRadius: '12px', padding: '16px', textAlign: 'center', borderColor: 'rgb(var(--theme-border))' }}>
              <div style={{ fontSize: '28px', fontWeight: 700, color: 'rgb(245, 158, 11)' }}>¥{statistics.total_cost_yuan.toFixed(2)}</div>
              <div style={{ ...styles.textXs }}>总成本</div>
            </div>
            <div style={{ background: 'rgb(var(--theme-bg))', borderRadius: '12px', padding: '16px', textAlign: 'center', borderColor: 'rgb(var(--theme-border))' }}>
              <div style={{ fontSize: '28px', fontWeight: 700, color: 'rgb(16, 185, 129)' }}>{statistics.avg_success_rate.toFixed(1)}%</div>
              <div style={{ ...styles.textXs }}>平均成功率</div>
            </div>
          </div>
          <div style={{ ...styles.grid, ...styles.grid3, gap: '16px', marginTop: '16px' }}>
            <div style={{ background: 'rgb(var(--theme-bg))', borderRadius: '12px', padding: '12px', textAlign: 'center', borderColor: 'rgb(var(--theme-border))' }}>
              <div style={{ fontSize: '20px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>{formatTokens(statistics.avg_daily_queries)}</div>
              <div style={{ ...styles.textXs }}>日均查询</div>
            </div>
            <div style={{ background: 'rgb(var(--theme-bg))', borderRadius: '12px', padding: '12px', textAlign: 'center', borderColor: 'rgb(var(--theme-border))' }}>
              <div style={{ fontSize: '20px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>{formatTokens(statistics.avg_daily_tokens)}</div>
              <div style={{ ...styles.textXs }}>日均Token</div>
            </div>
            <div style={{ background: 'rgb(var(--theme-bg))', borderRadius: '12px', padding: '12px', textAlign: 'center', borderColor: 'rgb(var(--theme-border))' }}>
              <div style={{ fontSize: '20px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>{statistics.missing_days}</div>
              <div style={{ ...styles.textXs }}>缺失天数</div>
            </div>
          </div>
        </div>
      )}

      {/* 增长分析 */}
      {growthAnalysis && (
        <div style={{ ...styles.grid, ...styles.grid2, gap: '20px' }}>
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>
              <TrendingUp size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(16, 185, 129)' }} />
              周环比分析
            </h3>
            <div style={styles.compareCard}>
              <div style={{ ...styles.flexBetween, padding: '8px 0', borderBottom: '1px solid rgb(var(--theme-border))' }}>
                <span style={styles.textGray}>查询量</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ fontWeight: 500, color: getChangeRateColor(growthAnalysis.week_over_week.queries_change_rate) }}>
                    {formatChangeRate(growthAnalysis.week_over_week.queries_change_rate).value}
                  </span>
                  {formatChangeRate(growthAnalysis.week_over_week.queries_change_rate).isNA && (
                    <NADot title="上周无数据，无法计算" />
                  )}
                </span>
              </div>
              <div style={{ ...styles.flexBetween, padding: '8px 0', borderBottom: '1px solid rgb(var(--theme-border))' }}>
                <span style={styles.textGray}>Token</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ fontWeight: 500, color: getChangeRateColor(growthAnalysis.week_over_week.tokens_change_rate) }}>
                    {formatChangeRate(growthAnalysis.week_over_week.tokens_change_rate).value}
                  </span>
                  {formatChangeRate(growthAnalysis.week_over_week.tokens_change_rate).isNA && (
                    <NADot title="上周无数据" />
                  )}
                </span>
              </div>
              <div style={{ ...styles.flexBetween, padding: '8px 0' }}>
                <span style={styles.textGray}>成本</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ fontWeight: 500, color: getChangeRateColor(growthAnalysis.week_over_week.cost_change_rate) }}>
                    {formatChangeRate(growthAnalysis.week_over_week.cost_change_rate).value}
                  </span>
                  {formatChangeRate(growthAnalysis.week_over_week.cost_change_rate).isNA && (
                    <NADot title="上周无数据" />
                  )}
                </span>
              </div>
            </div>
          </div>
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>
              <Users size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(139, 92, 246)' }} />
              月环比分析
            </h3>
            <div style={styles.compareCard}>
              <div style={{ ...styles.flexBetween, padding: '8px 0', borderBottom: '1px solid rgb(var(--theme-border))' }}>
                <span style={styles.textGray}>查询量</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ fontWeight: 500, color: getChangeRateColor(growthAnalysis.month_over_month.queries_change_rate) }}>
                    {formatChangeRate(growthAnalysis.month_over_month.queries_change_rate).value}
                  </span>
                  {formatChangeRate(growthAnalysis.month_over_month.queries_change_rate).isNA && (
                    <NADot title="上月无数据，无法计算" />
                  )}
                </span>
              </div>
              <div style={{ ...styles.flexBetween, padding: '8px 0', borderBottom: '1px solid rgb(var(--theme-border))' }}>
                <span style={styles.textGray}>Token</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ fontWeight: 500, color: getChangeRateColor(growthAnalysis.month_over_month.tokens_change_rate) }}>
                    {formatChangeRate(growthAnalysis.month_over_month.tokens_change_rate).value}
                  </span>
                  {formatChangeRate(growthAnalysis.month_over_month.tokens_change_rate).isNA && (
                    <NADot title="上月无数据" />
                  )}
                </span>
              </div>
              <div style={{ ...styles.flexBetween, padding: '8px 0' }}>
                <span style={styles.textGray}>成本</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ fontWeight: 500, color: getChangeRateColor(growthAnalysis.month_over_month.cost_change_rate) }}>
                    {formatChangeRate(growthAnalysis.month_over_month.cost_change_rate).value}
                  </span>
                  {formatChangeRate(growthAnalysis.month_over_month.cost_change_rate).isNA && (
                    <NADot title="上月无数据" />
                  )}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 峰值谷值 + 周规律 */}
      <div style={{ ...styles.grid, ...styles.grid2, gap: '20px' }}>
        {/* 峰值谷值 */}
        {peakValley && (
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>
              <Maximize size={18} style={styles.cardTitleIcon} />
              峰值谷值分析
            </h3>
            {(peakValley.peak_day || peakValley.valley_day || (peakValley.peak_hours && peakValley.peak_hours.length > 0)) ? (
              <>
                <div style={{ ...styles.grid, ...styles.grid2, gap: '16px' }}>
                  {peakValley.peak_day ? (
                    <div style={{ background: 'rgba(16, 185, 129, 0.1)', borderRadius: '12px', padding: '16px', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                      <div style={{ ...styles.flex, ...styles.gap2, marginBottom: '8px' }}>
                        <Maximize size={16} style={{ color: 'rgb(16, 185, 129)' }} />
                        <span style={{ fontSize: '13px', fontWeight: 500, color: 'rgb(5, 150, 105)' }}>峰值</span>
                      </div>
                      <div style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>{peakValley.peak_day.date}</div>
                      <div style={{ fontSize: '20px', fontWeight: 700, color: 'rgb(16, 185, 129)' }}>{peakValley.peak_day.queries}</div>
                      {peakValley.peak_day.reason && (
                        <div style={{ ...styles.textXs, marginTop: '4px' }}>{peakValley.peak_day.reason}</div>
                      )}
                    </div>
                  ) : (
                    <div style={{ background: 'rgba(16, 185, 129, 0.1)', borderRadius: '12px', padding: '16px', border: '1px solid rgba(16, 185, 129, 0.3)', textAlign: 'center' }}>
                      <div style={{ ...styles.flex, ...styles.gap2, marginBottom: '8px', justifyContent: 'center' }}>
                        <Maximize size={16} style={{ color: 'rgb(16, 185, 129)' }} />
                        <span style={{ fontSize: '13px', fontWeight: 500, color: 'rgb(5, 150, 105)' }}>峰值</span>
                      </div>
                      <div style={{ fontSize: '14px', color: 'rgb(var(--theme-text-muted))' }}>暂无数据</div>
                    </div>
                  )}
                  {peakValley.valley_day ? (
                    <div style={{ background: 'rgba(239, 68, 68, 0.1)', borderRadius: '12px', padding: '16px', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
                      <div style={{ ...styles.flex, ...styles.gap2, marginBottom: '8px' }}>
                        <Minimize size={16} style={{ color: 'rgb(239, 68, 68)' }} />
                        <span style={{ fontSize: '13px', fontWeight: 500, color: 'rgb(220, 38, 38)' }}>谷值</span>
                      </div>
                      <div style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>{peakValley.valley_day.date}</div>
                      <div style={{ fontSize: '20px', fontWeight: 700, color: 'rgb(239, 68, 68)' }}>{peakValley.valley_day.queries}</div>
                      {peakValley.valley_day.reason && (
                        <div style={{ ...styles.textXs, marginTop: '4px' }}>{peakValley.valley_day.reason}</div>
                      )}
                    </div>
                  ) : (
                    <div style={{ background: 'rgba(239, 68, 68, 0.1)', borderRadius: '12px', padding: '16px', border: '1px solid rgba(239, 68, 68, 0.3)', textAlign: 'center' }}>
                      <div style={{ ...styles.flex, ...styles.gap2, marginBottom: '8px', justifyContent: 'center' }}>
                        <Minimize size={16} style={{ color: 'rgb(239, 68, 68)' }} />
                        <span style={{ fontSize: '13px', fontWeight: 500, color: 'rgb(220, 38, 38)' }}>谷值</span>
                      </div>
                      <div style={{ fontSize: '14px', color: 'rgb(var(--theme-text-muted))' }}>暂无数据</div>
                    </div>
                  )}
                </div>
                {peakValley.peak_hours && peakValley.peak_hours.length > 0 && (
                  <div style={{ marginTop: '16px' }}>
                    <div style={styles.sectionTitle}>高峰时段 TOP {peakValley.peak_hours.length}</div>
                    {peakValley.peak_hours.map((ph, idx) => (
                      <div key={idx} style={{ ...styles.flexBetween, padding: '8px 0', borderBottom: '1px solid rgb(var(--theme-border))' }}>
                        <span style={styles.textGray}>{ph.label}</span>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <span style={{ fontWeight: 500, color: 'rgb(var(--theme-primary))' }}>{ph.query_count} 次</span>
                          <span style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>均 {formatDuration(ph.avg_duration_ms)}</span>
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
          <div style={{ textAlign: 'center', padding: '24px', color: 'rgb(var(--theme-text-muted))' }}>
            <p style={{ fontSize: '14px' }}>近期暂无查询记录数据</p>
          </div>
            )}
          </div>
        )}

        {/* 周规律 */}
        {weeklyPattern && weeklyPattern.pattern && (
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>
              <Calendar size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(139, 92, 246)' }} />
              周规律分布
            </h3>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', marginBottom: '16px' }}>
              {weeklyPattern.pattern.map(item => (
                <div key={item.weekday} style={{
                  flex: 1,
                  background: item.is_workday ? 'rgb(var(--theme-bg-secondary))' : 'rgba(245, 158, 11, 0.1)',
                  borderRadius: '10px',
                  padding: '12px 8px',
                  textAlign: 'center',
                }}>
                  <div style={{ ...styles.textXs, marginBottom: '6px' }}>{item.label}</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: item.is_workday ? 'rgb(var(--theme-primary))' : 'rgb(245, 158, 11)' }}>
                    {item.avg_queries.toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
            <div style={{ ...styles.grid, ...styles.grid2, gap: '12px', marginBottom: '12px' }}>
              <div style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p3, textAlign: 'center' }}>
                <div style={{ fontSize: '18px', fontWeight: 600, color: 'rgb(var(--theme-primary))' }}>{weeklyPattern.workday_avg.toLocaleString()}</div>
                <div style={{ ...styles.textXs }}>工作日平均</div>
              </div>
              <div style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p3, textAlign: 'center' }}>
                <div style={{ fontSize: '18px', fontWeight: 600, color: 'rgb(245, 158, 11)' }}>{weeklyPattern.weekend_avg.toLocaleString()}</div>
                <div style={{ ...styles.textXs }}>周末平均</div>
              </div>
            </div>
            {(() => {
              const workdayHigher = weeklyPattern.workday_avg > weeklyPattern.weekend_avg;
              const weekendHigher = weeklyPattern.weekend_avg > weeklyPattern.workday_avg;
              const equal = weeklyPattern.workday_avg === weeklyPattern.weekend_avg;
              const workdayZero = weeklyPattern.workday_avg === 0;
              const weekendZero = weeklyPattern.weekend_avg === 0;
              const workdayDays = weeklyPattern.pattern.filter(p => p.is_workday).length || 5;
              const weekendDays = weeklyPattern.pattern.filter(p => !p.is_workday).length || 2;
              const workdayTotal = weeklyPattern.workday_avg * workdayDays;
              const weekendTotal = weeklyPattern.weekend_avg * weekendDays;

              if (equal || (workdayZero && weekendZero)) {
                return (
                  <div style={{ background: 'rgb(var(--theme-bg-secondary))', borderRadius: '8px', padding: '16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '12px' }}>
                      <Minus size={16} style={{ color: 'rgb(var(--theme-text-muted))' }} />
                      <span style={{ color: 'rgb(var(--theme-text-muted))', fontWeight: 500 }}>工作日与周末查询量持平</span>
                    </div>
                    <div style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))', textAlign: 'center' }}>
                      各 {workdayDays} 个工作日 / {weekendDays} 个周末 · 总计 {workdayTotal.toLocaleString()} / {weekendTotal.toLocaleString()} 次查询
                    </div>
                  </div>
                );
              } else if (workdayHigher) {
                const ratio = weekendZero ? null : Math.round((weeklyPattern.workday_avg / weeklyPattern.weekend_avg - 1) * 100);
                return (
                  <div style={{ background: 'rgba(16, 185, 129, 0.1)', borderRadius: '8px', padding: '16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '12px' }}>
                      <TrendingUp size={16} style={{ color: 'rgb(16, 185, 129)' }} />
                      <span style={{ color: 'rgb(5, 150, 105)', fontWeight: 500 }}>
                        {weekendZero ? '工作日有查询量，周末无数据（无法计算差异）' : `工作日查询量比周末高 ${ratio}%`}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: 'rgb(var(--theme-text-muted))', padding: '0 8px' }}>
                      <span>工作日共 {workdayDays} 天</span>
                      <span>周末共 {weekendDays} 天</span>
                    </div>
                    <div style={{ display: 'flex', gap: '4px', marginTop: '8px' }}>
                      <div style={{ flex: workdayDays, background: 'rgb(var(--theme-primary))', height: '6px', borderRadius: '3px' }} />
                      <div style={{ flex: weekendDays, background: 'rgb(245, 158, 11)', height: '6px', borderRadius: '3px' }} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'rgb(var(--theme-text-muted))', padding: '4px 8px 0' }}>
                      <span>总查询 {workdayTotal.toLocaleString()}</span>
                      <span>总查询 {weekendTotal.toLocaleString()}</span>
                    </div>
                  </div>
                );
              } else if (weekendHigher) {
                const ratio = workdayZero ? null : Math.round((weeklyPattern.weekend_avg / weeklyPattern.workday_avg - 1) * 100);
                return (
                  <div style={{ background: 'rgba(245, 158, 11, 0.1)', borderRadius: '8px', padding: '16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '12px' }}>
                      <TrendingDown size={16} style={{ color: 'rgb(245, 158, 11)' }} />
                      <span style={{ color: 'rgb(217, 119, 6)', fontWeight: 500 }}>
                        {workdayZero ? '周末有查询量，工作日无数据（无法计算差异）' : `周末查询量比工作日高 ${ratio}%`}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: 'rgb(var(--theme-text-muted))', padding: '0 8px' }}>
                      <span>工作日共 {workdayDays} 天</span>
                      <span>周末共 {weekendDays} 天</span>
                    </div>
                    <div style={{ display: 'flex', gap: '4px', marginTop: '8px' }}>
                      <div style={{ flex: workdayDays, background: 'rgb(var(--theme-primary))', height: '6px', borderRadius: '3px' }} />
                      <div style={{ flex: weekendDays, height: '6px', background: 'rgb(245, 158, 11)', borderRadius: '3px' }} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'rgb(var(--theme-text-muted))', padding: '4px 8px 0' }}>
                      <span>总查询 {workdayTotal.toLocaleString()}</span>
                      <span>总查询 {weekendTotal.toLocaleString()}</span>
                    </div>
                  </div>
                );
              }
              return null;
            })()}
          </div>
        )}
      </div>

      {/* 趋势图表 */}
      <div style={styles.card}>
        <h4 style={styles.sectionTitle}>查询量趋势</h4>
        {trend.items && trend.items.length > 0 ? (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {trend.items.map(item => (
                <div key={item.date} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{ width: '80px', fontSize: '13px', color: 'rgb(var(--theme-text-muted))' }}>{item.date}</span>
                  <div style={{ flex: 1, display: 'flex', height: '24px', borderRadius: '6px', overflow: 'hidden' }}>
                    <div style={{
                      width: `${(item.success_queries / Math.max(item.total_queries, 1)) * 100}%`,
                      minWidth: '2px',
                      background: '#22c55e',
                    }} />
                    <div style={{
                      width: `${(item.error_queries / Math.max(item.total_queries, 1)) * 100}%`,
                      minWidth: '2px',
                      background: '#ef4444',
                    }} />
                    <div style={{
                      width: `${(item.timeout_queries / Math.max(item.total_queries, 1)) * 100}%`,
                      minWidth: '2px',
                      background: '#f59e0b',
                    }} />
                  </div>
                  <span style={{ width: '60px', fontSize: '13px', textAlign: 'right', fontWeight: 500 }}>
                    {item.total_queries}
                  </span>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: '16px', marginTop: '12px', fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: '12px', height: '12px', background: '#22c55e', borderRadius: '2px' }} />成功
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: '12px', height: '12px', background: '#ef4444', borderRadius: '2px' }} />失败
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: '12px', height: '12px', background: '#f59e0b', borderRadius: '2px' }} />超时
              </span>
            </div>
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: '40px', color: 'rgb(var(--theme-text-muted))' }}>
            <p>暂无趋势数据</p>
          </div>
        )}
      </div>

      {/* Token消耗趋势曲线图 */}
      {trend.items && trend.items.length > 0 && (
        <div style={styles.card}>
          <h4 style={styles.sectionTitle}>Token消耗趋势</h4>
          <div style={{ width: '100%', height: '200px' }}>
            <ResponsiveContainer>
              <AreaChart data={trend.items.slice().sort((a, b) => a.date.localeCompare(b.date))} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorTokens" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorLLM" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--theme-border))" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                  tickLine={false}
                  axisLine={{ stroke: '#e5e7eb' }}
                />
                <YAxis
                  tick={{ fontSize: 12, fill: 'rgb(var(--theme-text-muted))' }}
                  tickLine={false}
                  axisLine={{ stroke: 'rgb(var(--theme-border))' }}
                  width={60}
                  tickFormatter={(value) => formatTokens(value)}
                />
                <Tooltip
                  contentStyle={{
                    background: 'rgb(var(--theme-bg))',
                    borderColor: 'rgb(var(--theme-border))',
                    borderRadius: '8px',
                    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                    color: 'rgb(var(--theme-text))',
                  }}
                  labelStyle={{ color: 'rgb(var(--theme-text))', fontWeight: 500 }}
                  formatter={(value: number, name: string) => {
                    if (name === 'total') return [formatTokens(value), '总Token'];
                    if (name === 'llm') return [formatTokens(value), 'LLM'];
                    return [formatTokens(value), name];
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="tokens.total"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorTokens)"
                  name="total"
                />
                <Area
                  type="monotone"
                  dataKey="tokens.llm"
                  stroke="#10b981"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorLLM)"
                  name="llm"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: 'flex', gap: '16px', marginTop: '12px', fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '12px', height: '3px', background: '#3b82f6', borderRadius: '2px' }} />总Token
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '12px', height: '3px', background: '#10b981', borderRadius: '2px' }} />LLM
            </span>
          </div>
        </div>
      )}

      {/* 详细数据 */}
      <div style={styles.card}>
        <h4 style={styles.sectionTitle}>详细数据</h4>
        {trend.items && trend.items.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.tableHeader}>日期</th>
                  <th style={{ ...styles.tableHeader, textAlign: 'right' }}>查询数</th>
                  <th style={{ ...styles.tableHeader, textAlign: 'right' }}>成功率</th>
                  <th style={{ ...styles.tableHeader, textAlign: 'right' }}>Token</th>
                  <th style={{ ...styles.tableHeader, textAlign: 'right' }}>成本</th>
                  <th style={{ ...styles.tableHeader, textAlign: 'right' }}>平均耗时</th>
                </tr>
              </thead>
              <tbody>
                {trend.items.map(item => (
                  <tr key={item.date} style={{ cursor: 'pointer' }} className="hover-bg">
                    <td style={styles.tableCell}>{item.date}</td>
                    <td style={{ ...styles.tableCellRight, fontWeight: 500 }}>{item.total_queries.toLocaleString()}</td>
                    <td style={{ ...styles.tableCellRight, ...styles.textGreen }}>{item.success_rate.toFixed(1)}%</td>
                    <td style={{ ...styles.tableCellRight }}>{formatTokens(item.tokens.total)}</td>
                    <td style={{ ...styles.tableCellRight }}>¥{item.cost_yuan.toFixed(2)}</td>
                    <td style={{ ...styles.tableCellRight }}>{formatDuration(item.performance.avg_duration_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '40px', color: 'rgb(var(--theme-text-muted))' }}>
            <p style={{ fontSize: '14px' }}>近七日暂无查询数据</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== 实时监控 ====================

function RealtimeTab({ realtime }: { realtime: MonitoringRealtimeResponse['data'] | null }) {
  if (!realtime) return null;

  const currentStatus = realtime.current_status;
  const qpsStats = realtime.qps_stats;
  const errorAlerts = realtime.error_alerts;
  const recentQueries = realtime.recent_queries;
  const datasourceHealth = realtime.datasource_health;

  return (
    <div style={{ ...styles.grid, gap: '20px' }}>
      {/* 概览 */}
      <div style={{ ...styles.grid, ...styles.grid3, gap: '16px' }}>
        <div style={styles.statCard}>
          <div style={styles.statLabel}>最近1小时查询数</div>
          <div style={{ fontSize: '32px', fontWeight: 700, color: 'rgb(var(--theme-primary))', marginTop: '8px' }}>
            {realtime.summary.total_queries}
          </div>
        </div>
        <div style={styles.statCard}>
          <div style={styles.statLabel}>平均耗时</div>
          <div style={{ fontSize: '32px', fontWeight: 700, color: 'rgb(22, 163, 74)', marginTop: '8px' }}>
            {formatDuration(realtime.summary.avg_duration_ms)}
          </div>
        </div>
        <div style={styles.statCard}>
          <div style={styles.statLabel}>Token消耗</div>
          <div style={{ fontSize: '32px', fontWeight: 700, color: 'rgb(59, 130, 246)', marginTop: '8px' }}>
            {realtime.summary.total_tokens.toLocaleString()}
          </div>
        </div>
      </div>

      {/* 系统状态 + QPS */}
      <div style={{ ...styles.grid, ...styles.grid2, gap: '20px' }}>
        {/* 系统状态 */}
        {currentStatus && (
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>
              <Server size={18} style={styles.cardTitleIcon} />
              当前系统状态
              <span style={{
                marginLeft: 'auto',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 12px',
                borderRadius: '9999px',
                fontSize: '12px',
                fontWeight: 500,
                background: getStatusColor(currentStatus.overall).bg,
                color: getStatusColor(currentStatus.overall).text,
              }}>
                <span style={{ ...styles.statusDot(getStatusColor(currentStatus.overall).dot) }} />
                {currentStatus.status_text}
              </span>
            </h3>
            <div style={{ ...styles.grid, ...styles.grid2, gap: '16px' }}>
              <div style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p3 }}>
                <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>连续成功</div>
                <div style={{ fontSize: '24px', fontWeight: 700, color: 'rgb(22, 163, 74)' }}>{currentStatus.consecutive_success}</div>
              </div>
              <div style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p3 }}>
                <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>连续失败</div>
                <div style={{ fontSize: '24px', fontWeight: 700, color: currentStatus.consecutive_errors > 0 ? '#ef4444' : '#10b981' }}>
                  {currentStatus.consecutive_errors}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* QPS统计 */}
        {qpsStats && (
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>
              <Activity size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(22, 163, 74)' }} />
              QPS 吞吐量监控
            </h3>
            <div style={{ ...styles.grid, ...styles.grid5, gap: '8px' }}>
              <div style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p3, textAlign: 'center' }}>
                <div style={{ fontSize: '20px', fontWeight: 700, color: 'rgb(var(--theme-primary))' }}>{qpsStats.current_qps.toFixed(2)}</div>
                <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>当前</div>
              </div>
              <div style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p3, textAlign: 'center' }}>
                <div style={{ fontSize: '20px', fontWeight: 700, color: 'rgb(59, 130, 246)' }}>{qpsStats.avg_qps_1m.toFixed(2)}</div>
                <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>1分钟均</div>
              </div>
              <div style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p3, textAlign: 'center' }}>
                <div style={{ fontSize: '20px', fontWeight: 700, color: 'rgb(22, 163, 74)' }}>{qpsStats.avg_qps_5m.toFixed(2)}</div>
                <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>5分钟均</div>
              </div>
              {qpsStats.avg_qps_15m != null && (
                <div style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p3, textAlign: 'center' }}>
                  <div style={{ fontSize: '20px', fontWeight: 700, color: 'rgb(139, 92, 246)' }}>{qpsStats.avg_qps_15m.toFixed(2)}</div>
                  <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>15分钟均</div>
                </div>
              )}
              <div style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p3, textAlign: 'center' }}>
                <div style={{ fontSize: '20px', fontWeight: 700, color: 'rgb(245, 158, 11)' }}>{qpsStats.max_qps.toFixed(2)}</div>
                <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>峰值</div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 分钟数据 */}
      <div style={styles.card}>
        <h3 style={styles.cardTitle}>每分钟查询量</h3>
        {realtime.minute_data && realtime.minute_data.length > 0 ? (
          <div style={{ ...styles.grid, gridTemplateColumns: 'repeat(6, 1fr)', gap: '8px' }}>
            {realtime.minute_data.map((item, idx) => (
              <div key={idx} style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p3, textAlign: 'center' }}>
                <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))' }}>{item.time}</div>
                <div style={{ fontSize: '18px', fontWeight: 600, color: 'rgb(var(--theme-primary))', marginTop: '4px' }}>{item.count}</div>
                <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))', marginTop: '2px' }}>{formatDuration(item.avg_duration_ms)}</div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '40px 20px',
            color: 'rgb(var(--theme-text-muted))',
            textAlign: 'center',
          }}>
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              background: 'rgb(var(--theme-bg-secondary))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '12px',
            }}>
              <Clock size={24} style={{ color: 'rgb(var(--theme-text-muted))' }} />
            </div>
            <div style={{ fontSize: '14px', fontWeight: 500, marginBottom: '4px' }}>暂无数据</div>
            <div style={{ fontSize: '12px' }}>当前暂无每分钟查询记录</div>
          </div>
        )}
      </div>

      {/* 错误告警 + 数据源健康 */}
      <div style={{ ...styles.grid, ...styles.grid2, gap: '20px' }}>
        {/* 错误告警 */}
        {errorAlerts && (
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>
              <AlertTriangle size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(239, 68, 68)' }} />
              错误告警
              <span style={{
                marginLeft: '8px',
                padding: '2px 8px',
                borderRadius: '9999px',
                fontSize: '11px',
                fontWeight: 500,
                background: '#fef2f2',
                color: 'rgb(220, 38, 38)',
              }}>
                {errorAlerts.total_errors_1h} / 1小时
              </span>
            </h3>
            <div style={{ ...styles.flex, ...styles.gap3, marginBottom: '16px' }}>
              <div style={{ flex: 1, ...styles.bgSlate, ...styles.rounded, ...styles.p3, textAlign: 'center' }}>
                <div style={{ fontSize: '20px', fontWeight: 700, color: 'rgb(239, 68, 68)' }}>{errorAlerts.error_rate.toFixed(1)}%</div>
                <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>错误率</div>
              </div>
              {errorAlerts.timeout_rate != null && (
                <div style={{ flex: 1, ...styles.bgSlate, ...styles.rounded, ...styles.p3, textAlign: 'center' }}>
                  <div style={{ fontSize: '20px', fontWeight: 700, color: 'rgb(245, 158, 11)' }}>{errorAlerts.timeout_rate.toFixed(1)}%</div>
                  <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>超时率</div>
                </div>
              )}
            </div>
            {errorAlerts.recent_errors && errorAlerts.recent_errors.length > 0 && (
              <div>
                <div style={styles.sectionTitle}>最近错误</div>
                {errorAlerts.recent_errors.slice(0, 5).map((err, idx) => (
                  <div key={idx} style={styles.errorAlert('error')}>
                    <div style={{ ...styles.alertTitle('error'), display: 'flex', justifyContent: 'space-between' }}>
                      <span>{err.message}</span>
                      <span style={{ fontWeight: 400 }}>{err.count}次</span>
                    </div>
                    <div style={styles.alertContent}>
                      {err.time} {err.datasource && `· ${err.datasource}`}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {errorAlerts.top_error_types && errorAlerts.top_error_types.length > 0 && (
              <div style={{ marginTop: '16px' }}>
                <div style={styles.sectionTitle}>错误类型排行</div>
                {errorAlerts.top_error_types.map((err, idx) => (
                  <div key={idx} style={{ ...styles.flexBetween, padding: '8px 0', borderBottom: '1px solid #f3f4f6' }}>
                    <span style={{ fontSize: '13px', color: 'rgb(var(--theme-text))' }}>{err.type}</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{ width: '60px', ...styles.miniProgress }}>
                        <div style={{ ...styles.progressFill(err.percentage, '#ef4444') }} />
                      </div>
                      <span style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))', minWidth: '40px', textAlign: 'right' }}>
                        {err.count} ({err.percentage.toFixed(1)}%)
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {!errorAlerts.recent_errors?.length && !errorAlerts.top_error_types?.length && (
              <div style={{
                textAlign: 'center',
                padding: '20px 16px',
                marginTop: '16px',
                background: 'rgba(16, 185, 129, 0.1)',
                borderRadius: '8px',
                border: '1px solid rgba(16, 185, 129, 0.3)',
              }}>
                <div style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  background: 'rgb(16, 185, 129)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 12px',
                }}>
                  <CheckCircle size={20} color="#fff" />
                </div>
                <div style={{ fontSize: '14px', fontWeight: 500, color: 'rgb(16, 185, 129)', marginBottom: '4px' }}>运行状态良好</div>
                <div style={{ fontSize: '12px', color: 'rgb(16, 185, 129)', opacity: 0.7 }}>近1小时内无错误和超时</div>
              </div>
            )}
          </div>
        )}

        {/* 数据源健康 */}
        {datasourceHealth && (
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>
              <Database size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(59, 130, 246)' }} />
              数据源健康状态
            </h3>
            {datasourceHealth.datasources && datasourceHealth.datasources.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {datasourceHealth.datasources.map((ds, idx) => {
                  const statusColors = getStatusColor(ds.status);
                  return (
                    <div key={idx} style={{
                      ...styles.bgSlate,
                      ...styles.rounded,
                      padding: '16px',
                      borderLeft: `4px solid ${statusColors.dot}`,
                    }}>
                      <div style={{ ...styles.flexBetween, marginBottom: '12px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={styles.statusDot(statusColors.dot)} />
                          <span style={{ fontSize: '14px', fontWeight: 500, color: 'rgb(var(--theme-text))' }}>{ds.name}</span>
                          <span style={{
                            fontSize: '11px',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            background: statusColors.bg,
                            color: statusColors.text,
                          }}>
                            {ds.status === 'healthy' ? '健康' : ds.status === 'degraded' ? '降级' : '异常'}
                          </span>
                        </div>
                        {ds.reason && (
                          <span style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>{ds.reason}</span>
                        )}
                      </div>
                      <div style={{ ...styles.grid, ...styles.grid4, gap: '8px' }}>
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>{ds.queries_1h}</div>
                          <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))' }}>1小时查询</div>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(var(--theme-primary))' }}>{formatDuration(ds.avg_latency_ms)}</div>
                          <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))' }}>平均延迟</div>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(239, 68, 68)' }}>{ds.error_count}</div>
                          <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))' }}>错误数</div>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ fontSize: '14px', fontWeight: 600, color: ds.error_rate > 5 ? '#ef4444' : '#10b981' }}>
                            {ds.error_rate.toFixed(2)}%
                          </div>
                          <div style={{ ...styles.textXs, color: 'rgb(var(--theme-text-muted))' }}>错误率</div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '60px 20px',
                background: 'rgb(var(--theme-bg-secondary))',
                borderRadius: '10px',
                border: '1px dashed rgb(var(--theme-border))',
                minHeight: '200px',
              }}>
                <Database size={48} style={{ color: 'rgb(var(--theme-text-muted))', marginBottom: '16px', opacity: 0.5 }} />
                <div style={{ fontSize: '16px', fontWeight: 500, color: 'rgb(var(--theme-text-secondary))', marginBottom: '8px' }}>近期暂无数据源使用情况</div>
                <div style={{ fontSize: '13px', color: 'rgb(var(--theme-text-muted))' }}>近1小时内未产生数据源查询请求</div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 最近查询 */}
      {recentQueries && (
        <div style={styles.card}>
          <h3 style={styles.cardTitle}>
            <Eye size={18} style={styles.cardTitleIcon} />
            最近查询样例
          </h3>
          {(!recentQueries.success_samples?.length && !recentQueries.error_samples?.length) ? (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '48px 20px',
              background: 'rgb(var(--theme-bg-secondary))',
              borderRadius: '10px',
              border: '1px dashed rgb(var(--theme-border))',
              minHeight: '180px',
            }}>
              <Eye size={40} style={{ color: 'rgb(var(--theme-text-muted))', marginBottom: '12px', opacity: 0.5 }} />
              <div style={{ fontSize: '14px', fontWeight: 500, color: 'rgb(var(--theme-text-secondary))', marginBottom: '4px' }}>近期暂无查询任务</div>
              <div style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>此处显示近1小时的查询请求记录</div>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.tableHeader}>问题</th>
                    <th style={{ ...styles.tableHeader, textAlign: 'center' }}>状态</th>
                    <th style={{ ...styles.tableHeader, textAlign: 'right' }}>耗时</th>
                    <th style={{ ...styles.tableHeader, textAlign: 'right' }}>Token</th>
                    <th style={{ ...styles.tableHeader, textAlign: 'right' }}>时间</th>
                  </tr>
                </thead>
                <tbody>
                  {recentQueries.success_samples?.slice(0, 5).map(item => (
                    <tr key={item.id} style={{ cursor: 'pointer' }} className="hover-bg">
                      <td style={{ ...styles.tableCell, maxWidth: '400px' }}>
                        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {item.question}
                        </div>
                        {item.datasources && (
                          <div style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', marginTop: '2px' }}>
                            {item.datasources.join(', ')}
                          </div>
                        )}
                      </td>
                      <td style={{ ...styles.tableCell, textAlign: 'center' }}>
                        <span style={{ ...styles.badge('green'), background: 'rgba(34, 197, 94, 0.15)', color: 'rgb(34, 197, 94)' }}>
                          <CheckCircle size={12} /> 成功
                        </span>
                      </td>
                      <td style={{ ...styles.tableCellRight, color: 'rgb(22, 163, 74)', fontWeight: 500 }}>
                        {formatDuration(item.duration_ms)}
                      </td>
                      <td style={{ ...styles.tableCellRight }}>{item.tokens.toLocaleString()}</td>
                      <td style={{ ...styles.tableCellRight, color: 'rgb(var(--theme-text-muted))' }}>{item.time}</td>
                    </tr>
                  ))}
                  {recentQueries.error_samples?.slice(0, 3).map(item => (
                    <tr key={item.id} style={{ cursor: 'pointer' }} className="hover-bg">
                      <td style={{ ...styles.tableCell, maxWidth: '400px' }}>
                        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {item.question}
                        </div>
                        <div style={{ fontSize: '11px', color: 'rgb(239, 68, 68)', marginTop: '2px' }}>{item.error_message}</div>
                      </td>
                      <td style={{ ...styles.tableCell, textAlign: 'center' }}>
                        <span style={{ ...styles.badge('red'), background: '#fef2f2', color: 'rgb(220, 38, 38)' }}>
                          <XCircle size={12} /> {item.error_type}
                        </span>
                      </td>
                      <td style={{ ...styles.tableCellRight, color: 'rgb(239, 68, 68)', fontWeight: 500 }}>
                        {formatDuration(item.duration_ms)}
                      </td>
                      <td style={{ ...styles.tableCellRight }}>{item.tokens.toLocaleString()}</td>
                      <td style={{ ...styles.tableCellRight, color: 'rgb(var(--theme-text-muted))' }}>{item.time}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ==================== 性能分析 ====================

function PerformanceTab({ performance, days, setDays }: {
  performance: MonitoringPerformanceResponse['data'] | null
  days: number
  setDays: (d: number) => void
}) {
  if (!performance) return null;

  const latencyDist = performance.latency_distribution;
  const stageBreakdown = performance.stage_breakdown;
  const datasourcePerf = performance.datasource_performance;
  const perfTrend = performance.performance_trend;
  const queryPatterns = performance.query_patterns;

  const dayOptions = [7, 14, 30];
  const stageColors: Record<string, string> = {
    vector_search: 'rgb(var(--theme-primary))',
    rerank: 'rgb(139, 92, 246)',
    llm_gen_sql: 'rgb(59, 130, 246)',
    sql_execution: 'rgb(16, 185, 129)',
  };

  return (
    <div style={{ ...styles.grid, gap: '20px' }}>
      {/* 时间选择器 */}
      <div style={styles.flexBetween}>
        <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>性能分析</h3>
        <div style={{ ...styles.flex, ...styles.gap2 }}>
          {dayOptions.map(d => (
            <button
              key={d}
              onClick={() => setDays(d)}
              style={{
                padding: '6px 14px',
                fontSize: '13px',
                fontWeight: 500,
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                background: days === d ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-bg-secondary))',
                color: days === d ? '#fff' : 'rgb(var(--theme-text-muted))',
                transition: 'all 0.2s',
              }}
            >
              {d}天
            </button>
          ))}
        </div>
      </div>

      {/* 阶段耗时 */}
      <div style={styles.card}>
        <h3 style={styles.cardTitle}>
          <Timer size={18} style={styles.cardTitleIcon} />
          各阶段平均耗时
          <span style={{ fontSize: '12px', fontWeight: 400, color: 'rgb(var(--theme-text-muted))', marginLeft: 'auto' }}>
            总计: {formatDuration(performance.stage_averages.total_avg_ms)}
          </span>
        </h3>
        <div style={{ ...styles.grid, ...styles.grid5, gap: '16px' }}>
          {[
            { label: '向量检索', value: performance.stage_averages.vector_search_ms, color: 'rgb(var(--theme-primary))' },
            { label: '重排序', value: performance.stage_averages.rerank_ms, color: 'rgb(139, 92, 246)' },
            { label: 'LLM生成SQL', value: performance.stage_averages.llm_gen_sql_ms, color: 'rgb(59, 130, 246)' },
            { label: 'SQL执行', value: performance.stage_averages.sql_execution_ms, color: 'rgb(16, 185, 129)' },
            { label: '总计', value: performance.stage_averages.total_avg_ms, color: 'rgb(var(--theme-text))' },
          ].map(item => (
            <div key={item.label} style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p4, textAlign: 'center' }}>
              <div style={{ fontSize: '18px', fontWeight: 700, color: item.color }}>{formatDuration(item.value)}</div>
              <div style={{ ...styles.textXs, marginTop: '6px' }}>{item.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 延迟分布 + 环节占比 */}
      <div style={{ ...styles.grid, ...styles.grid2, gap: '20px' }}>
        {/* 延迟分布 */}
        {latencyDist && latencyDist.distribution && (
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>
              <BarChart3 size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(var(--theme-primary))' }} />
              延迟时间分布
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {latencyDist.distribution.map((item, idx) => (
                <div key={idx} style={styles.patternBar}>
                  <span style={{ width: '70px', fontSize: '13px', color: 'rgb(var(--theme-text-muted))' }}>{item.range}</span>
                  <div style={{ flex: 1, ...styles.progressBar }}>
                    <div style={{ ...styles.progressFill(item.percentage, 'rgb(var(--theme-primary))') }} />
                  </div>
                  <span style={{ width: '50px', fontSize: '13px', textAlign: 'right', color: 'rgb(var(--theme-text))' }}>{item.count}</span>
                  <span style={{ width: '50px', fontSize: '13px', textAlign: 'right', color: 'rgb(var(--theme-text-muted))' }}>{item.percentage.toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 环节占比 */}
        {stageBreakdown && (
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>
              <PieChart size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(139, 92, 246)' }} />
              各环节耗时占比
            </h3>
            <div style={{ marginBottom: '16px', padding: '12px', background: 'rgb(var(--theme-bg-secondary))', borderRadius: '10px', textAlign: 'center' }}>
              <span style={{ fontSize: '14px', color: 'rgb(var(--theme-text-muted))' }}>总平均耗时 </span>
              <span style={{ fontSize: '20px', fontWeight: 700, color: 'rgb(var(--theme-text))' }}>{formatDuration(stageBreakdown.total_avg_ms)}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {stageBreakdown.stages.map((stage, idx) => (
                <div key={idx} style={styles.patternBar}>
                  <span style={{ width: '80px', fontSize: '13px', color: 'rgb(var(--theme-text-muted))' }}>{stage.label}</span>
                  <div style={{ flex: 1, ...styles.progressBar }}>
                    <div style={{ ...styles.progressFill(stage.percentage, stageColors[stage.name] || 'rgb(var(--theme-primary))') }} />
                  </div>
                  <span style={{ width: '50px', fontSize: '13px', textAlign: 'right', color: 'rgb(var(--theme-text))' }}>{stage.percentage.toFixed(1)}%</span>
                  <span style={{ width: '70px', fontSize: '13px', textAlign: 'right', color: 'rgb(var(--theme-text-muted))' }}>{formatDuration(stage.avg_ms)}</span>
                  {stage.trend_rate && (
                    <span style={{
                      width: '60px',
                      fontSize: '11px',
                      color: stage.trend_rate === 'N/A' ? 'rgb(var(--theme-text-muted))' : stage.trend === 'decreasing' ? 'rgb(16, 185, 129)' : stage.trend === 'increasing' ? 'rgb(239, 68, 68)' : 'rgb(var(--theme-text-muted))',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '2px',
                    }}>
                      {stage.trend_rate === 'N/A' ? (
                        <NADot title="数据不足(<2天)，无法计算趋势" />
                      ) : (
                        <>
                          {stage.trend === 'decreasing' ? '↓' : stage.trend === 'increasing' ? '↑' : '→'}
                          {stage.trend_rate}
                        </>
                      )}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 查询复杂度 + 性能趋势 */}
      <div style={{ ...styles.grid, ...styles.grid2, gap: '20px' }}>
        {/* 查询复杂度 */}
        {queryPatterns && queryPatterns.complexity_distribution && queryPatterns.complexity_distribution.length > 0 ? (
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>
              <Gauge size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(245, 158, 11)' }} />
              查询复杂度分布
            </h3>
            <div style={{ ...styles.grid, ...styles.grid2, gap: '12px', marginBottom: '16px' }}>
              <div style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p3, textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 700, color: 'rgb(16, 185, 129)' }}>{queryPatterns.fast_queries_pct?.toFixed(1) || '0.0'}%</div>
                <div style={{ ...styles.textXs }}>快速查询占比</div>
              </div>
              <div style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p3, textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 700, color: 'rgb(239, 68, 68)' }}>{queryPatterns.slow_queries_pct?.toFixed(1) || '0.0'}%</div>
                <div style={{ ...styles.textXs }}>慢查询占比</div>
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {queryPatterns.complexity_distribution.map((item, idx) => {
                const colors = ['rgb(16, 185, 129)', 'rgb(245, 158, 11)', 'rgb(239, 68, 68)'];
                return (
                  <div key={idx} style={styles.patternBar}>
                    <span style={{ width: '90px', fontSize: '13px', color: 'rgb(var(--theme-text-muted))', whiteSpace: 'nowrap' }}>{item.label}</span>
                    <div style={{ flex: 1, ...styles.progressBar }}>
                      <div style={{ ...styles.progressFill(item.percentage, colors[idx] || 'rgb(var(--theme-primary))') }} />
                    </div>
                    <span style={{ width: '40px', fontSize: '13px', textAlign: 'right', color: 'rgb(var(--theme-text))' }}>{item.count}</span>
                    <span style={{ width: '60px', fontSize: '13px', textAlign: 'right', color: 'rgb(var(--theme-text-muted))' }}>{formatDuration(item.avg_duration_ms)}</span>
                  </div>
                );
              })}
            </div>
            {/* 复杂度分布柱状图 */}
            <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid rgb(var(--theme-border))' }}>
              <div style={{ fontSize: '13px', fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: '12px' }}>查询复杂度分布</div>
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: '16px', height: '100px' }}>
                {queryPatterns.complexity_distribution.map((item, idx) => {
                  const colors = ['rgb(16, 185, 129)', 'rgb(245, 158, 11)', 'rgb(239, 68, 68)'];
                  const maxCount = Math.max(...queryPatterns.complexity_distribution.map(d => d.count), 1);
                  const barHeight = Math.max((item.count / maxCount) * 80, item.count > 0 ? 20 : 4);
                  const label = item.label.split('(')[0];
                  return (
                    <div key={idx} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                      <div style={{
                        width: '100%',
                        height: `${barHeight}px`,
                        backgroundColor: colors[idx],
                        borderRadius: '4px 4px 0 0',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#fff',
                        fontSize: '12px',
                        fontWeight: 600,
                        minHeight: '20px',
                      }}>
                        {item.count}
                      </div>
                      <span style={{ fontSize: '11px', color: 'rgb(var(--theme-text-muted))', textAlign: 'center' }}>{label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ) : (
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>
              <Gauge size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(245, 158, 11)' }} />
              查询复杂度分布
            </h3>
            <div style={{ textAlign: 'center', padding: '40px', color: 'rgb(var(--theme-text-muted))' }}>
              <p style={{ fontSize: '14px' }}>暂无复杂度数据</p>
            </div>
          </div>
        )}

        {/* 性能趋势对比 */}
        {perfTrend && (
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>
              <TrendingUp size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(16, 185, 129)' }} />
              性能趋势对比
            </h3>
            <div style={{ ...styles.bgSlate, ...styles.rounded, ...styles.p3, marginBottom: '16px', textAlign: 'center' }}>
              <span style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>较上周期 </span>
              <span style={{
                fontSize: '18px',
                fontWeight: 700,
                color: perfTrend.vs_last_period.overall_change === 'N/A' ? 'rgb(var(--theme-text-muted))' : perfTrend.vs_last_period.trend === 'decreasing' ? 'rgb(16, 185, 129)' : perfTrend.vs_last_period.trend === 'increasing' ? 'rgb(239, 68, 68)' : 'rgb(var(--theme-text-muted))',
              }}>
                {perfTrend.vs_last_period.overall_change}
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {[
                { label: '向量检索', value: perfTrend.vs_last_period.vector_search_change },
                { label: '重排序', value: perfTrend.vs_last_period.rerank_change },
                { label: 'LLM生成', value: perfTrend.vs_last_period.llm_gen_sql_change },
                { label: 'SQL执行', value: perfTrend.vs_last_period.sql_execution_change },
              ].map((item, idx) => (
                <div key={idx} style={{ ...styles.flexBetween, padding: '8px 0', borderBottom: '1px solid rgb(var(--theme-border))' }}>
                  <span style={styles.textGray}>{item.label}</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{
                      fontWeight: 500,
                      color: item.value === 'N/A' ? 'rgb(var(--theme-text-muted))' : item.value.startsWith('-') ? 'rgb(16, 185, 129)' : item.value.startsWith('+') ? 'rgb(239, 68, 68)' : 'rgb(var(--theme-text-muted))',
                    }}>
                      {item.value}
                    </span>
                    {item.value === 'N/A' && (
                      <NADot title="数据不足(<2天)，无法计算趋势" />
                    )}
                  </span>
                </div>
              ))}
            </div>
            {perfTrend.daily_trend && perfTrend.daily_trend.length > 0 && (
              <div style={{ marginTop: '16px' }}>
                <div style={styles.sectionTitle}>每日趋势</div>
                <div style={{ overflowX: 'auto' }}>
                  <table style={styles.table}>
                    <thead>
                      <tr>
                        <th style={styles.tableHeader}>日期</th>
                        <th style={{ ...styles.tableHeader, textAlign: 'right' }}>平均耗时</th>
                      </tr>
                    </thead>
                    <tbody>
                      {perfTrend.daily_trend.map((item, idx) => (
                        <tr key={idx} style={{ cursor: 'pointer' }} className="hover-bg">
                          <td style={styles.tableCell}>{item.date}</td>
                          <td style={{ ...styles.tableCellRight, fontWeight: 500, color: 'rgb(var(--theme-primary))' }}>
                            {formatDuration(item.avg_duration_ms)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 数据源性能对比 */}
      {datasourcePerf && datasourcePerf.datasources && datasourcePerf.datasources.length > 0 ? (
        <div style={styles.card}>
          <h3 style={styles.cardTitle}>
            <Database size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(59, 130, 246)' }} />
            数据源性能对比
          </h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.tableHeader}>数据源</th>
                  <th style={{ ...styles.tableHeader, textAlign: 'right' }}>查询数</th>
                  <th style={{ ...styles.tableHeader, textAlign: 'right' }}>平均</th>
                  <th style={{ ...styles.tableHeader, textAlign: 'right' }}>最小</th>
                  <th style={{ ...styles.tableHeader, textAlign: 'right' }}>最大</th>
                  <th style={{ ...styles.tableHeader, textAlign: 'right' }}>SQL执行</th>
                </tr>
              </thead>
              <tbody>
                {datasourcePerf.datasources.map((ds, idx) => (
                  <tr key={ds.name} style={{ cursor: 'pointer' }} className="hover-bg">
                    <td style={styles.tableCell}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{
                          width: '20px',
                          height: '20px',
                          borderRadius: '50%',
                          background: idx === 0 ? '#6366f1' : idx === 1 ? '#8b5cf6' : idx === 2 ? '#a855f7' : '#d946ef',
                          color: '#fff',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '10px',
                          fontWeight: 600,
                        }}>
                          {ds.usage_rank}
                        </span>
                        <span style={{ fontWeight: 500 }}>{ds.name}</span>
                      </div>
                    </td>
                    <td style={{ ...styles.tableCellRight }}>{ds.query_count.toLocaleString()}</td>
                    <td style={{ ...styles.tableCellRight, color: 'rgb(var(--theme-primary))', fontWeight: 600 }}>{formatDuration(ds.avg_duration_ms)}</td>
                    <td style={{ ...styles.tableCellRight, color: 'rgb(22, 163, 74)' }}>{formatDuration(ds.min_duration_ms)}</td>
                    <td style={{ ...styles.tableCellRight, color: 'rgb(239, 68, 68)' }}>{formatDuration(ds.max_duration_ms)}</td>
                    <td style={{ ...styles.tableCellRight }}>{formatDuration(ds.avg_sql_execution_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div style={styles.card}>
          <h3 style={styles.cardTitle}>
            <Database size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(59, 130, 246)' }} />
            数据源性能对比
          </h3>
            <div style={{ textAlign: 'center', padding: '40px', color: 'rgb(var(--theme-text-muted))' }}>
              <p style={{ fontSize: '14px' }}>暂无数据源性能数据</p>
            </div>
        </div>
      )}

      {/* 查询耗时 TOP 10 */}
      {performance.slow_queries_top10 && performance.slow_queries_top10.length > 0 ? (
        <div style={styles.card}>
          <h3 style={styles.cardTitle}>
            <Timer size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(239, 68, 68)' }} />
            查询耗时 TOP 10
          </h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={{ ...styles.tableHeader, width: '40px' }}>#</th>
                  <th style={styles.tableHeader}>问题</th>
                  <th style={{ ...styles.tableHeader, textAlign: 'right' }}>耗时</th>
                  <th style={{ ...styles.tableHeader, textAlign: 'right' }}>Token</th>
                  <th style={{ ...styles.tableHeader, textAlign: 'right' }}>时间</th>
                </tr>
              </thead>
              <tbody>
                {performance.slow_queries_top10.map((item, idx) => (
                  <tr key={item.id} style={{ cursor: 'pointer' }} className="hover-bg">
                    <td style={{ ...styles.tableCell, color: 'rgb(var(--theme-text-muted))' }}>{idx + 1}</td>
                    <td style={{ ...styles.tableCell, maxWidth: '500px' }}>
                      <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {item.question}
                      </div>
                    </td>
                    <td style={{ ...styles.tableCellRight, color: 'rgb(239, 68, 68)', fontWeight: 600 }}>
                      <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '4px' }}>
                        <Timer size={14} /> {formatDuration(item.duration_ms)}
                      </span>
                    </td>
                    <td style={{ ...styles.tableCellRight }}>{item.tokens.toLocaleString()}</td>
                    <td style={{ ...styles.tableCellRight, color: 'rgb(var(--theme-text-muted))' }}>
                      {new Date(item.created_at).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div style={styles.card}>
          <h3 style={styles.cardTitle}>
            <Timer size={18} style={{ ...styles.cardTitleIcon, color: 'rgb(239, 68, 68)' }} />
            查询耗时 TOP 10
          </h3>
            <div style={{ textAlign: 'center', padding: '40px', color: 'rgb(var(--theme-text-muted))' }}>
              <p style={{ fontSize: '14px' }}>暂无慢查询数据</p>
            </div>
        </div>
      )}
    </div>
  );
}

export default MonitoringPage;
