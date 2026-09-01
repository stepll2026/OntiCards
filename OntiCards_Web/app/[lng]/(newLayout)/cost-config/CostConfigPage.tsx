'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Coins,
  Clock,
  Loader2,
  Save,
  X,
  AlertCircle,
  CheckCircle,
  TrendingUp,
  TrendingDown,
  Activity,
  Zap,
  Timer,
  PieChart,
  ArrowUp,
  ArrowDown,
  DollarSign,
  BarChart2,
  Check,
  XCircle,
  AlertTriangle,
} from 'lucide-react';
import {
  getTokenPrices,
  updateTokenPrices,
  TokenPriceConfig,
  UpdateTokenPricesParams,
} from '@/api/systemConfig';
import {
  getMonitoringOverview,
  MonitoringOverviewResponse,
} from '@/api/monitoring';
import { useUserInfo } from '@/hooks';

type TabType = 'token-prices' | 'cost-stats';

const CostConfigPage = () => {
  const { userInfo } = useUserInfo();
  const currentUserId = userInfo?.id || '';
  const isAdmin = userInfo?.role === 'admin';

  const tabs = [
    ...(isAdmin ? [{ id: 'token-prices' as TabType, label: 'Token价格', icon: <Coins className="w-4 h-4" /> }] : []),
    { id: 'cost-stats' as TabType, label: '成本统计', icon: <TrendingUp className="w-4 h-4" /> },
  ];

  const [activeTab, setActiveTab] = useState<TabType>(isAdmin ? 'token-prices' : 'cost-stats');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [tokenPrices, setTokenPrices] = useState<TokenPriceConfig | null>(null);
  const [costOverview, setCostOverview] = useState<MonitoringOverviewResponse['data'] | null>(null);

  const [tokenForm, setTokenForm] = useState<UpdateTokenPricesParams>({});

  const fetchTokenPrices = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getTokenPrices();
      if (res.code === 200 && res.data) {
        setTokenPrices(res.data);
        setTokenForm({
          embedding: parseFloat(res.data.embedding.value),
          rerank: parseFloat(res.data.rerank.value),
          llm_input: parseFloat(res.data.llm_input.value),
          llm_output: parseFloat(res.data.llm_output.value),
        });
      }
    } catch (e) {
      console.error('获取Token价格失败', e);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchCostOverview = useCallback(async () => {
    if (!currentUserId) return;
    setLoading(true);
    try {
      const res = await getMonitoringOverview({ user_id: currentUserId });
      if (res.code === 200 && res.data) {
        setCostOverview(res.data);
      }
    } catch (e) {
      console.error('获取成本统计失败', e);
    } finally {
      setLoading(false);
    }
  }, [currentUserId]);

  useEffect(() => {
    if (activeTab === 'token-prices') fetchTokenPrices();
    if (activeTab === 'cost-stats') fetchCostOverview();
  }, [activeTab, fetchTokenPrices, fetchCostOverview]);

  const handleSaveTokenPrices = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const res = await updateTokenPrices(tokenForm);
      if (res.code === 200) {
        setMessage({ type: 'success', text: res.data.message || 'Token价格配置更新成功' });
        fetchTokenPrices();
      } else {
        setMessage({ type: 'error', text: res.message || '更新失败' });
      }
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.message || '更新失败' });
    } finally {
      setSaving(false);
    }
  };

  const formatPrice = (value: number | undefined) => {
    if (value === undefined) return '';
    return value.toString();
  };

  const parsePrice = (value: string) => {
    const parsed = parseFloat(value);
    return isNaN(parsed) ? undefined : parsed;
  };

  const formatTokens = (n: number) => {
    if (n >= 1000000) return `${(n / 1000000).toFixed(2)}M`;
    if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
    return n.toString();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <header>
        <h1 style={{ fontSize: '24px', fontWeight: 600, marginBottom: '4px', color: 'rgb(var(--theme-text))' }}>成本管理</h1>
        <p style={{ fontSize: '14px', color: 'rgb(var(--theme-text-muted))' }}>管理Token计费规则和成本统计</p>
      </header>

      {/* Tab 导航 */}
      <div style={{ borderBottom: '1px solid rgb(var(--theme-border))' }}>
        <nav style={{ display: 'flex', gap: '4px' }}>
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => { setActiveTab(tab.id as TabType); setMessage(null); }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '12px 16px',
                fontSize: '14px',
                fontWeight: 500,
                border: 'none',
                borderBottom: activeTab === tab.id ? '2px solid rgb(var(--theme-primary))' : '2px solid transparent',
                background: 'transparent',
                color: activeTab === tab.id ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-muted))',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* 消息提示 */}
      {message && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '16px',
          borderRadius: '12px',
          ...(message.type === 'success'
            ? { background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', color: 'rgb(22, 163, 74)' }
            : { background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', color: 'rgb(220, 38, 38)' }
          )
        }}>
          {message.type === 'success' ? <CheckCircle style={{ width: '20px', height: '20px', flexShrink: 0 }} /> : <AlertCircle style={{ width: '20px', height: '20px', flexShrink: 0 }} />}
          <p style={{ fontSize: '14px' }}>{message.text}</p>
          <button onClick={() => setMessage(null)} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer' }}>
            <X style={{ width: '16px', height: '16px' }} />
          </button>
        </div>
      )}

      {/* 内容 */}
      <div style={{ minHeight: '500px' }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', paddingTop: '80px' }}>
            <Loader2 style={{ width: '24px', height: '24px', animation: 'spin 1s linear infinite', color: 'rgb(var(--theme-primary))' }} />
          </div>
        ) : (
          <>
            {activeTab === 'token-prices' && tokenPrices && (
              <TokenPricesTab
                tokenPrices={tokenPrices}
                tokenForm={tokenForm}
                setTokenForm={setTokenForm}
                saving={saving}
                onSave={handleSaveTokenPrices}
                formatPrice={formatPrice}
                parsePrice={parsePrice}
              />
            )}
            {activeTab === 'cost-stats' && (
              <>
                {loading ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', paddingTop: '80px' }}>
                    <Loader2 style={{ width: '24px', height: '24px', animation: 'spin 1s linear infinite', color: 'rgb(var(--theme-primary))' }} />
                  </div>
                ) : costOverview ? (
                  <CostStatsTab costOverview={costOverview} formatTokens={formatTokens} />
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', paddingTop: '80px', textAlign: 'center' }}>
                    <TrendingUp style={{ width: '48px', height: '48px', color: 'rgb(var(--theme-text-muted))', marginBottom: '16px', opacity: 0.5 }} />
                    <h4 style={{ fontSize: '18px', fontWeight: 600, color: 'rgb(var(--theme-text))', marginBottom: '8px' }}>暂无成本数据</h4>
                    <p style={{ fontSize: '14px', color: 'rgb(var(--theme-text-muted))' }}>开始使用智能问数后，这里将显示成本统计</p>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
};

function TokenPricesTab({
  tokenPrices,
  tokenForm,
  setTokenForm,
  saving,
  onSave,
  formatPrice,
  parsePrice,
}: {
  tokenPrices: TokenPriceConfig
  tokenForm: UpdateTokenPricesParams
  setTokenForm: (form: UpdateTokenPricesParams) => void
  saving: boolean
  onSave: () => void
  formatPrice: (value: number | undefined) => string
  parsePrice: (value: string) => number | undefined
}) {
  const priceItems = [
    {
      key: 'embedding' as const,
      label: 'Embedding Token',
      current: tokenPrices.embedding.value,
      description: tokenPrices.embedding.description,
      placeholder: '例如: 0.0007',
    },
    {
      key: 'rerank' as const,
      label: 'Rerank Token',
      current: tokenPrices.rerank.value,
      description: tokenPrices.rerank.description,
      placeholder: '例如: 0.002',
    },
    {
      key: 'llm_input' as const,
      label: 'LLM 输入 Token',
      current: tokenPrices.llm_input.value,
      description: tokenPrices.llm_input.description,
      placeholder: '例如: 0.002',
    },
    {
      key: 'llm_output' as const,
      label: 'LLM 输出 Token',
      current: tokenPrices.llm_output.value,
      description: tokenPrices.llm_output.description,
      placeholder: '例如: 0.006',
    },
  ];

  const handleChange = (key: keyof UpdateTokenPricesParams, value: string) => {
    setTokenForm({ ...tokenForm, [key]: parsePrice(value) });
  };

  const hasChanges = priceItems.some(item => {
    const formValue = tokenForm[item.key];
    const currentValue = parseFloat(tokenPrices[item.key].value);
    return formValue !== currentValue;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ background: 'rgb(var(--theme-bg))', borderRadius: '20px', border: '1px solid rgb(var(--theme-border))', padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <div>
            <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>Token 价格配置</h3>
            <p style={{ fontSize: '14px', color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>设置各类Token的单价，单位为元/千token</p>
          </div>
          <button
            onClick={onSave}
            disabled={saving || !hasChanges}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 16px',
              background: 'rgb(var(--theme-primary))',
              color: '#fff',
              borderRadius: '12px',
              fontSize: '14px',
              fontWeight: 500,
              border: 'none',
              cursor: saving || !hasChanges ? 'not-allowed' : 'pointer',
              opacity: saving || !hasChanges ? 0.5 : 1,
            }}
          >
            {saving ? <Loader2 style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite' }} /> : <Save style={{ width: '16px', height: '16px' }} />}
            保存配置
          </button>
        </div>

        <div style={{ background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.3)', borderRadius: '12px', padding: '16px', display: 'flex', alignItems: 'flex-start', gap: '12px', marginBottom: '24px' }}>
          <AlertCircle style={{ width: '20px', height: '20px', color: 'rgb(245, 158, 11)', flexShrink: 0, marginTop: '2px' }} />
          <div>
            <p style={{ fontSize: '14px', fontWeight: 500, color: 'rgb(217, 119, 6)' }}>计费说明</p>
            <p style={{ fontSize: '12px', color: 'rgb(217, 119, 6)', marginTop: '4px', opacity: 0.8 }}>⚠️ 提供模型服务的云厂商不同则计费规则也不同，请根据实际情况调整价格</p>
            <p style={{ fontSize: '12px', color: 'rgb(217, 119, 6)', marginTop: '4px', opacity: 0.8 }}>⚠️ Token价格将用于预估计算每次查询的算力成本，修改前请确认价格单位为[元/千token]</p>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '24px' }}>
          {priceItems.map(item => (
            <div key={item.key} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <label style={{ fontSize: '14px', fontWeight: 500, color: 'rgb(var(--theme-text-secondary))' }}>{item.label}</label>
                <span style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>当前: {item.current}</span>
              </div>
              <div style={{ position: 'relative' }}>
                <input
                  type="number"
                  step="0.0001"
                  min="0"
                  value={formatPrice(tokenForm[item.key])}
                  onChange={(e) => handleChange(item.key, e.target.value)}
                  placeholder={item.placeholder}
                  style={{
                    width: '100%',
                    padding: '10px 80px 10px 16px',
                    fontSize: '14px',
                    border: '1px solid rgb(var(--theme-border))',
                    borderRadius: '12px',
                    outline: 'none',
                    background: 'rgb(var(--theme-bg-secondary))',
                    color: 'rgb(var(--theme-text))',
                  }}
                />
                <span style={{ position: 'absolute', right: '16px', top: '50%', transform: 'translateY(-50%)', fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>元/千token</span>
              </div>
              <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>{item.description}</p>
            </div>
          ))}
        </div>

        {/* 价格合理性提示 */}
        <div style={{ marginTop: '24px', paddingTop: '24px', borderTop: '1px solid rgb(var(--theme-border))' }}>
          <h4 style={{ fontSize: '14px', fontWeight: 500, color: 'rgb(var(--theme-text-secondary))', marginBottom: '12px' }}>常见 Token 价格参考（阿里千问）</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', fontSize: '12px' }}>
            {[
              { name: '文本向量化 text-embedding-v3', price: '0.0005 元 / 千Token' },
              { name: '重排序 gte-rerank-v2', price: '0.0008 元 / 千Token' },
              { name: '普通对话 qwen-max-latest 输入', price: '0.0024 元 / 千Token' },
              { name: '普通对话 qwen-max-latest 输出', price: '0.0096 元 / 千Token' },
            ].map((item, idx) => (
              <div key={idx} style={{ background: 'rgb(var(--theme-bg-secondary))', borderRadius: '10px', padding: '12px' }}>
                <p style={{ color: 'rgb(var(--theme-text-muted))' }}>{item.name}</p>
                <p style={{ color: 'rgb(var(--theme-text))', fontWeight: 500, marginTop: '4px' }}>{item.price}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function CostStatsTab({
  costOverview,
  formatTokens,
}: {
  costOverview: MonitoringOverviewResponse['data']
  formatTokens: (n: number) => string
}) {
  const dailyTrend = costOverview.daily_trend || [];
  const maxDailyCost = dailyTrend.length > 0 ? Math.max(...dailyTrend.slice(0, 7).map(d => d.cost_yuan), 0.01) : 0.01;
  const maxHourlyQueries = Math.max(...(costOverview.hourly_distribution?.distribution || []).map(h => h.queries), 1);
  const totalDatasourceQueries = (costOverview.datasource_stats?.top_datasources || []).reduce((sum, ds) => sum + ds.query_count, 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* 核心成本概览 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
        <div style={{ background: 'linear-gradient(135deg, rgb(var(--theme-primary)) 0%, rgba(var(--theme-primary), 0.8) 100%)', borderRadius: '20px', padding: '24px', color: '#fff', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <p style={{ color: 'rgba(255,255,255,0.8)', fontSize: '14px' }}>近30天总成本</p>
            <DollarSign style={{ width: '20px', height: '20px', color: 'rgba(255,255,255,0.6)' }} />
          </div>
          <p style={{ fontSize: '30px', fontWeight: 700 }}>¥{costOverview.summary_30d.total_cost_yuan.toFixed(2)}</p>
          <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '12px', marginTop: '8px' }}>{costOverview.summary_30d.total_queries} 次查询</p>
        </div>
        <div style={{ background: 'linear-gradient(135deg, rgb(59, 130, 246) 0%, rgb(37, 99, 235) 100%)', borderRadius: '20px', padding: '24px', color: '#fff', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <p style={{ color: 'rgba(255,255,255,0.8)', fontSize: '14px' }}>30天总Token</p>
            <Zap style={{ width: '20px', height: '20px', color: 'rgba(255,255,255,0.6)' }} />
          </div>
          <p style={{ fontSize: '30px', fontWeight: 700 }}>{formatTokens(costOverview.summary_30d.total_tokens)}</p>
          <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '12px', marginTop: '8px' }}>平均 ¥{(costOverview.summary_30d.total_cost_yuan / Math.max(costOverview.summary_30d.total_tokens, 1) * 1000).toFixed(4)}/K</p>
        </div>
        <div style={{ background: 'linear-gradient(135deg, rgb(16, 185, 129) 0%, rgb(5, 150, 105) 100%)', borderRadius: '20px', padding: '24px', color: '#fff', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <p style={{ color: 'rgba(255,255,255,0.8)', fontSize: '14px' }}>今日成本</p>
            <Activity style={{ width: '20px', height: '20px', color: 'rgba(255,255,255,0.6)' }} />
          </div>
          <p style={{ fontSize: '30px', fontWeight: 700 }}>¥{dailyTrend[0]?.cost_yuan?.toFixed(2) || '0.00'}</p>
          <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '12px', marginTop: '8px' }}>{costOverview.today.total_queries} 次查询 · {formatTokens(costOverview.today.total_tokens)} Token</p>
        </div>
        <div style={{ background: 'linear-gradient(135deg, rgb(245, 158, 11) 0%, rgb(217, 119, 6) 100%)', borderRadius: '20px', padding: '24px', color: '#fff', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <p style={{ color: 'rgba(255,255,255,0.8)', fontSize: '14px' }}>24小时成本</p>
            <Clock style={{ width: '20px', height: '20px', color: 'rgba(255,255,255,0.6)' }} />
          </div>
          <p style={{ fontSize: '30px', fontWeight: 700 }}>¥{(dailyTrend[0]?.cost_yuan || 0).toFixed(2)}</p>
          <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '12px', marginTop: '8px' }}>成功率 {costOverview.recent_24h.success_rate.toFixed(1)}%</p>
        </div>
      </div>

      {/* 成本提示 */}
      <div style={{ background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.3)', borderRadius: '12px', padding: '16px', display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
        <AlertCircle style={{ width: '20px', height: '20px', color: 'rgb(245, 158, 11)', flexShrink: 0, marginTop: '2px' }} />
        <div>
          <p style={{ fontSize: '14px', fontWeight: 500, color: 'rgb(217, 119, 6)' }}>成本说明：{costOverview.cost_note}</p>
        </div>
      </div>

      {/* 与昨日/上周对比 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
        <div style={{ background: 'rgb(var(--theme-bg))', borderRadius: '20px', border: '1px solid rgb(var(--theme-border))', padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <TrendingUp style={{ width: '20px', height: '20px', color: 'rgb(var(--theme-text-muted))' }} />
            <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>环比变化</h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
            <div style={{ textAlign: 'center', padding: '12px', background: 'rgb(var(--theme-bg-secondary))', borderRadius: '12px' }}>
              <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>查询量</p>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                {costOverview.comparison?.vs_yesterday.is_positive ? (
                  <ArrowUp style={{ width: '16px', height: '16px', color: 'rgb(16, 185, 129)' }} />
                ) : (
                  <ArrowDown style={{ width: '16px', height: '16px', color: 'rgb(239, 68, 68)' }} />
                )}
                <span style={{ fontWeight: 700, color: costOverview.comparison?.vs_yesterday.is_positive ? 'rgb(16, 185, 129)' : 'rgb(239, 68, 68)' }}>
                  {Math.abs(costOverview.comparison?.vs_yesterday.queries_change || 0)}
                </span>
              </div>
              <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>{costOverview.comparison?.vs_yesterday.queries_change_rate || 'N/A'}</p>
            </div>
            <div style={{ textAlign: 'center', padding: '12px', background: 'rgb(var(--theme-bg-secondary))', borderRadius: '12px' }}>
              <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>Token</p>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                {(costOverview.comparison?.vs_yesterday.tokens_change || 0) >= 0 ? (
                  <ArrowUp style={{ width: '16px', height: '16px', color: 'rgb(16, 185, 129)' }} />
                ) : (
                  <ArrowDown style={{ width: '16px', height: '16px', color: 'rgb(239, 68, 68)' }} />
                )}
                <span style={{ fontWeight: 700, color: (costOverview.comparison?.vs_yesterday.tokens_change || 0) >= 0 ? 'rgb(16, 185, 129)' : 'rgb(239, 68, 68)' }}>
                  {formatTokens(Math.abs(costOverview.comparison?.vs_yesterday.tokens_change || 0))}
                </span>
              </div>
              <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>{costOverview.comparison?.vs_yesterday.tokens_change_rate || 'N/A'}</p>
            </div>
            <div style={{ textAlign: 'center', padding: '12px', background: 'rgb(var(--theme-bg-secondary))', borderRadius: '12px' }}>
              <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))', marginBottom: '4px' }}>响应时间</p>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                {(costOverview.comparison?.vs_yesterday.avg_duration_change || 0) >= 0 ? (
                  <ArrowUp style={{ width: '16px', height: '16px', color: 'rgb(239, 68, 68)' }} />
                ) : (
                  <ArrowDown style={{ width: '16px', height: '16px', color: 'rgb(16, 185, 129)' }} />
                )}
                <span style={{ fontWeight: 700, color: (costOverview.comparison?.vs_yesterday.avg_duration_change || 0) >= 0 ? 'rgb(239, 68, 68)' : 'rgb(16, 185, 129)' }}>
                  {Math.abs(costOverview.comparison?.vs_yesterday.avg_duration_change || 0).toFixed(0)}ms
                </span>
              </div>
              <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>{costOverview.comparison?.vs_yesterday.avg_duration_change_rate || 'N/A'}</p>
            </div>
          </div>
        </div>
        <div style={{ background: 'rgb(var(--theme-bg))', borderRadius: '20px', border: '1px solid rgb(var(--theme-border))', padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Timer style={{ width: '20px', height: '20px', color: 'rgb(var(--theme-text-muted))' }} />
            <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>查询状态分布</h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
            <div style={{ textAlign: 'center', padding: '12px', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '12px' }}>
              <CheckCircle style={{ width: '24px', height: '24px', color: 'rgb(16, 185, 129)', margin: '0 auto 8px' }} />
              <p style={{ fontSize: '24px', fontWeight: 700, color: 'rgb(16, 185, 129)' }}>{costOverview.status_breakdown?.success.count || 0}</p>
              <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>成功</p>
              <p style={{ fontSize: '12px', color: 'rgb(16, 185, 129)', marginTop: '4px' }}>{costOverview.status_breakdown?.success.percentage.toFixed(1) || '0.0'}%</p>
            </div>
            <div style={{ textAlign: 'center', padding: '12px', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '12px' }}>
              <XCircle style={{ width: '24px', height: '24px', color: 'rgb(239, 68, 68)', margin: '0 auto 8px' }} />
              <p style={{ fontSize: '24px', fontWeight: 700, color: 'rgb(239, 68, 68)' }}>{costOverview.status_breakdown?.error.count || 0}</p>
              <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>失败</p>
              <p style={{ fontSize: '12px', color: 'rgb(239, 68, 68)', marginTop: '4px' }}>{costOverview.status_breakdown?.error.percentage.toFixed(1) || '0.0'}%</p>
            </div>
            <div style={{ textAlign: 'center', padding: '12px', background: 'rgba(245, 158, 11, 0.1)', borderRadius: '12px' }}>
              <AlertTriangle style={{ width: '24px', height: '24px', color: 'rgb(245, 158, 11)', margin: '0 auto 8px' }} />
              <p style={{ fontSize: '24px', fontWeight: 700, color: 'rgb(245, 158, 11)' }}>{costOverview.status_breakdown?.timeout.count || 0}</p>
              <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>超时</p>
              <p style={{ fontSize: '12px', color: 'rgb(245, 158, 11)', marginTop: '4px' }}>{costOverview.status_breakdown?.timeout.percentage.toFixed(1) || '0.0'}%</p>
            </div>
          </div>
        </div>
      </div>

      {/* Token消耗分布 */}
      <div style={{ background: 'rgb(var(--theme-bg))', borderRadius: '20px', border: '1px solid rgb(var(--theme-border))', padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <PieChart style={{ width: '20px', height: '20px', color: 'rgb(var(--theme-text-muted))' }} />
            <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>24小时Token消耗分布</h3>
          </div>
          <span style={{ fontSize: '14px', color: 'rgb(var(--theme-text-muted))' }}>总计 {formatTokens(costOverview.recent_24h.embedding_tokens + costOverview.recent_24h.rerank_tokens + costOverview.recent_24h.llm_tokens)}</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
          {[
            { key: 'embedding', label: 'Embedding', tokens: costOverview.recent_24h.embedding_tokens, color: 'rgb(var(--theme-primary))', bgColor: 'rgba(var(--theme-primary), 0.1)', borderColor: 'rgba(var(--theme-primary), 0.3)' },
            { key: 'rerank', label: 'Rerank', tokens: costOverview.recent_24h.rerank_tokens, color: 'rgb(139, 92, 246)', bgColor: 'rgba(139, 92, 246, 0.1)', borderColor: 'rgba(139, 92, 246, 0.3)' },
            { key: 'llm', label: 'LLM', tokens: costOverview.recent_24h.llm_tokens, color: 'rgb(59, 130, 246)', bgColor: 'rgba(59, 130, 246, 0.1)', borderColor: 'rgba(59, 130, 246, 0.3)' },
          ].map(item => {
            const total = costOverview.recent_24h.embedding_tokens + costOverview.recent_24h.rerank_tokens + costOverview.recent_24h.llm_tokens;
            const percentage = total > 0 ? (item.tokens / total) * 100 : 0;
            return (
              <div key={item.key} style={{ background: item.bgColor, borderRadius: '16px', padding: '20px', border: `1px solid ${item.borderColor}` }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <span style={{ fontSize: '14px', fontWeight: 500, color: item.color }}>{item.label}</span>
                  <span style={{ fontSize: '12px', color: item.color, background: item.bgColor, padding: '2px 8px', borderRadius: '9999px' }}>
                    {percentage.toFixed(1)}%
                  </span>
                </div>
                <p style={{ fontSize: '24px', fontWeight: 700, color: item.color }}>{formatTokens(item.tokens)}</p>
                <div style={{ marginTop: '12px', height: '8px', background: item.borderColor, borderRadius: '12px', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${percentage}%`, background: item.color, borderRadius: '12px' }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 每日成本趋势 */}
      <div style={{ background: 'rgb(var(--theme-bg))', borderRadius: '20px', border: '1px solid rgb(var(--theme-border))', padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <BarChart2 style={{ width: '20px', height: '20px', color: 'rgb(var(--theme-text-muted))' }} />
            <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>每日成本趋势</h3>
          </div>
          <span style={{ fontSize: '14px', color: 'rgb(var(--theme-text-muted))' }}>近7日</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {dailyTrend.slice(0, 7).map(item => {
            const total7dCost = dailyTrend.slice(0, 7).reduce((sum, d) => sum + d.cost_yuan, 0);
            const percentage = total7dCost > 0 ? (item.cost_yuan / total7dCost) * 100 : 0;
            return (
              <div key={item.date} style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <span style={{ width: '96px', fontSize: '14px', color: 'rgb(var(--theme-text-secondary))', fontWeight: 500 }}>{item.date}</span>
                <div style={{ flex: 1, height: '12px', background: 'rgb(var(--theme-bg-secondary))', position: 'relative', borderRadius: '9999px', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${percentage}%`, background: 'linear-gradient(to right, rgb(var(--theme-primary)), rgba(var(--theme-primary), 0.7))', borderRadius: '9999px' }} />
                </div>
                <div style={{ width: '144px', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '12px' }}>
                  <span style={{ fontSize: '14px', fontWeight: 500, color: 'rgb(var(--theme-text-secondary))' }}>{percentage.toFixed(1)}%</span>
                  <span style={{ fontSize: '16px', fontWeight: 700, color: 'rgb(var(--theme-primary))' }}>¥{item.cost_yuan.toFixed(2)}</span>
                </div>
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid rgb(var(--theme-border))', display: 'flex', justifyContent: 'flex-end' }}>
          <div style={{ textAlign: 'right' }}>
            <span style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>7日累计成本</span>
            <p style={{ fontSize: '18px', fontWeight: 700, color: 'rgb(var(--theme-primary))' }}>
              ¥{dailyTrend.slice(0, 7).reduce((sum, d) => sum + d.cost_yuan, 0).toFixed(2)}
            </p>
          </div>
        </div>
      </div>

      {/* 24小时查询分布 */}
      <div style={{ background: 'rgb(var(--theme-bg))', borderRadius: '20px', border: '1px solid rgb(var(--theme-border))', padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity style={{ width: '20px', height: '20px', color: 'rgb(var(--theme-text-muted))' }} />
            <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>24小时查询分布</h3>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '12px' }}>
            <span style={{ color: 'rgb(var(--theme-text-muted))' }}>高峰: <span style={{ fontWeight: 500, color: 'rgb(245, 158, 11)' }}>{costOverview.hourly_distribution?.peak_hour_label || 'N/A'}</span></span>
            <span style={{ color: 'rgb(var(--theme-text-muted))' }}>低谷: <span style={{ fontWeight: 500, color: 'rgb(var(--theme-text-muted))' }}>{costOverview.hourly_distribution?.off_peak_hour_label || 'N/A'}</span></span>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: '4px', height: '160px' }}>
          {costOverview.hourly_distribution?.distribution.map(hour => (
            <div key={hour.hour} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
              <div style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: '128px' }}>
                {hour.queries > 0 && (
                  <span style={{ fontSize: '12px', fontWeight: 500, color: 'rgb(var(--theme-primary))', marginBottom: '4px' }}>{hour.queries}</span>
                )}
                <div
                  style={{
                    width: '100%',
                    borderRadius: '6px',
                    transition: 'all 0.3s',
                    background: hour.hour === costOverview.hourly_distribution?.peak_hour
                      ? 'rgb(245, 158, 11)'
                      : hour.queries > 0
                      ? 'rgb(var(--theme-primary))'
                      : 'rgb(var(--theme-bg-secondary))',
                    height: `${Math.max((hour.queries / maxHourlyQueries) * 100, hour.queries > 0 ? 8 : 4)}%`,
                  }}
                />
              </div>
              <span style={{ fontSize: '10px', color: 'rgb(var(--theme-text-muted))' }}>{hour.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 数据源使用统计 */}
      <div style={{ background: 'rgb(var(--theme-bg))', borderRadius: '20px', border: '1px solid rgb(var(--theme-border))', padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Zap style={{ width: '20px', height: '20px', color: 'rgb(var(--theme-text-muted))' }} />
            <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>数据源使用统计</h3>
          </div>
          <span style={{ fontSize: '14px', color: 'rgb(var(--theme-text-muted))' }}>共 {costOverview.datasource_stats?.total_datasources_used || 0} 个数据源</span>
        </div>
        {costOverview.datasource_stats?.top_datasources && costOverview.datasource_stats.top_datasources.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {costOverview.datasource_stats.top_datasources.map((ds, index) => (
              <div key={ds.datasource_name} style={{ background: 'rgb(var(--theme-bg-secondary))', borderRadius: '12px', padding: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{
                      width: '24px',
                      height: '24px',
                      borderRadius: '50%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '12px',
                      fontWeight: 700,
                      color: '#fff',
                      background: index === 0 ? 'rgb(245, 158, 11)' : index === 1 ? 'rgb(var(--theme-text-muted))' : 'rgb(var(--theme-border))',
                    }}>
                      {index + 1}
                    </span>
                    <span style={{ fontWeight: 500, color: 'rgb(var(--theme-text))' }}>{ds.datasource_name}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '14px' }}>
                    <span style={{ color: 'rgb(var(--theme-text-muted))' }}>{ds.query_count} 次查询</span>
                    <span style={{ color: 'rgb(var(--theme-primary))', fontWeight: 500 }}>{ds.percentage.toFixed(1)}%</span>
                    <span style={{ color: 'rgb(var(--theme-text-muted))' }}>平均 {ds.avg_duration_ms.toFixed(0)}ms</span>
                  </div>
                </div>
                <div style={{ height: '8px', background: 'rgb(var(--theme-bg-tertiary))', borderRadius: '12px', overflow: 'hidden' }}>
                  <div
                    style={{
                      height: '100%',
                      borderRadius: '12px',
                      transition: 'all 0.5s',
                      background: index === 0 ? 'rgb(245, 158, 11)' : 'rgb(var(--theme-primary))',
                      width: `${ds.percentage}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '40px', color: 'rgb(var(--theme-text-muted))' }}>
            <p style={{ fontSize: '14px' }}>暂无数据源使用数据</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default CostConfigPage;
