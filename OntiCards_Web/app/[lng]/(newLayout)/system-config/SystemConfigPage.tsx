'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Settings,
  Coins,
  Database,
  Loader2,
  Save,
  RefreshCw,
  X,
  Edit3,
  AlertCircle,
  CheckCircle,
} from 'lucide-react';
import {
  getTokenPrices,
  updateTokenPrices,
  getDataRetention,
  updateDataRetention,
  TokenPriceConfig,
  DataRetentionConfig,
  UpdateTokenPricesParams,
  UpdateDataRetentionParams,
} from '@/api/systemConfig';

type TabType = 'token-prices' | 'data-retention';

const tabs = [
  { id: 'token-prices', label: 'Token价格配置', icon: <Coins className="w-4 h-4" /> },
  { id: 'data-retention', label: '数据保留配置', icon: <Database className="w-4 h-4" /> },
];

const SystemConfigPage = () => {
  const [activeTab, setActiveTab] = useState<TabType>('token-prices');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [tokenPrices, setTokenPrices] = useState<TokenPriceConfig | null>(null);
  const [dataRetention, setDataRetention] = useState<DataRetentionConfig | null>(null);

  const [tokenForm, setTokenForm] = useState<UpdateTokenPricesParams>({});
  const [retentionForm, setRetentionForm] = useState<UpdateDataRetentionParams>({});

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

  const fetchDataRetention = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getDataRetention();
      if (res.code === 200 && res.data) {
        setDataRetention(res.data);
        setRetentionForm({
          query_logs_retention_days: parseInt(res.data.query_logs_retention_days.value),
          stats_retention_days: parseInt(res.data.stats_retention_days.value),
        });
      }
    } catch (e) {
      console.error('获取数据保留配置失败', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'token-prices') fetchTokenPrices();
    if (activeTab === 'data-retention') fetchDataRetention();
  }, [activeTab, fetchTokenPrices, fetchDataRetention]);

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

  const handleSaveDataRetention = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const res = await updateDataRetention(retentionForm);
      if (res.code === 200) {
        setMessage({ type: 'success', text: res.data.message || '数据保留配置更新成功' });
        fetchDataRetention();
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <header>
        <h1 style={{ fontSize: '24px', fontWeight: 600, marginBottom: '4px', color: 'rgb(var(--theme-text))' }}>系统配置</h1>
        <p style={{ fontSize: '14px', color: 'rgb(var(--theme-text-muted))' }}>管理系统Token计费规则和数据保留策略</p>
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
            {activeTab === 'data-retention' && dataRetention && (
              <DataRetentionTab
                dataRetention={dataRetention}
                retentionForm={retentionForm}
                setRetentionForm={setRetentionForm}
                saving={saving}
                onSave={handleSaveDataRetention}
              />
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
            <p style={{ fontSize: '12px', color: 'rgb(217, 119, 6)', marginTop: '4px', opacity: 0.8 }}>Token价格将用于计算每次查询的成本预估。修改前请确认价格单位为元/千token</p>
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
          <h4 style={{ fontSize: '14px', fontWeight: 500, color: 'rgb(var(--theme-text-secondary))', marginBottom: '12px' }}>常见Token价格参考</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', fontSize: '12px' }}>
            {[
              { name: 'OpenAI Embedding', price: '$0.0001 / 1K tokens' },
              { name: 'Cohere Rerank', price: '$0.001 / 1K tokens' },
              { name: 'GPT-4 Input', price: '$0.03 / 1K tokens' },
              { name: 'GPT-4 Output', price: '$0.06 / 1K tokens' },
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

function DataRetentionTab({
  dataRetention,
  retentionForm,
  setRetentionForm,
  saving,
  onSave,
}: {
  dataRetention: DataRetentionConfig
  retentionForm: UpdateDataRetentionParams
  setRetentionForm: (form: UpdateDataRetentionParams) => void
  saving: boolean
  onSave: () => void
}) {
  const retentionItems = [
    {
      key: 'query_logs_retention_days' as const,
      label: '查询日志保留天数',
      current: dataRetention.query_logs_retention_days.value,
      description: dataRetention.query_logs_retention_days.description,
      unit: dataRetention.query_logs_retention_days.unit,
      min: 1,
      max: 3650,
    },
    {
      key: 'stats_retention_days' as const,
      label: '聚合统计保留天数',
      current: dataRetention.stats_retention_days.value,
      description: dataRetention.stats_retention_days.description,
      unit: dataRetention.stats_retention_days.unit,
      min: 1,
      max: 3650,
    },
  ];

  const handleChange = (key: keyof UpdateDataRetentionParams, value: string) => {
    const parsed = parseInt(value);
    setRetentionForm({ ...retentionForm, [key]: isNaN(parsed) ? undefined : parsed });
  };

  const hasChanges = retentionItems.some(item => {
    const formValue = retentionForm[item.key];
    const currentValue = parseInt(dataRetention[item.key].value);
    return formValue !== currentValue;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ background: 'rgb(var(--theme-bg))', borderRadius: '20px', border: '1px solid rgb(var(--theme-border))', padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <div>
            <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>数据保留策略</h3>
            <p style={{ fontSize: '14px', color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>配置历史数据的保留天数，超期数据将自动清理</p>
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
            <p style={{ fontSize: '14px', fontWeight: 500, color: 'rgb(217, 119, 6)' }}>重要提示</p>
            <p style={{ fontSize: '12px', color: 'rgb(217, 119, 6)', marginTop: '4px', opacity: 0.8 }}>减少保留天数可能导致历史数据丢失，请谨慎操作。建议保留至少90天以支持趋势分析。</p>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {retentionItems.map(item => (
            <div key={item.key} style={{ background: 'rgb(var(--theme-bg-secondary))', borderRadius: '16px', padding: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <div>
                  <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'rgb(var(--theme-text))' }}>{item.label}</h4>
                  <p style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))', marginTop: '4px' }}>{item.description}</p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>当前: {item.current}{item.unit}</span>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <input
                  type="range"
                  min={item.min}
                  max={item.max}
                  value={retentionForm[item.key] || parseInt(item.current)}
                  onChange={(e) => handleChange(item.key, e.target.value)}
                  style={{
                    flex: 1,
                    height: '8px',
                    background: 'rgb(var(--theme-bg-tertiary))',
                    borderRadius: '4px',
                    appearance: 'none',
                    cursor: 'pointer',
                    accentColor: 'rgb(var(--theme-primary))',
                  }}
                />
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '128px' }}>
                  <input
                    type="number"
                    min={item.min}
                    max={item.max}
                    value={retentionForm[item.key] || parseInt(item.current)}
                    onChange={(e) => handleChange(item.key, e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      border: '1px solid rgb(var(--theme-border))',
                      borderRadius: '10px',
                      fontSize: '14px',
                      textAlign: 'center',
                      outline: 'none',
                      background: 'rgb(var(--theme-bg))',
                      color: 'rgb(var(--theme-text))',
                    }}
                  />
                  <span style={{ fontSize: '14px', color: 'rgb(var(--theme-text-muted))' }}>{item.unit}</span>
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px', fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>
                <span>{item.min}天</span>
                <span>{item.max}天</span>
              </div>
              {/* 快捷选项 */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '16px' }}>
                <span style={{ fontSize: '12px', color: 'rgb(var(--theme-text-muted))' }}>快捷设置:</span>
                {[30, 90, 180, 365, 730].map(days => (
                  <button
                    key={days}
                    onClick={() => handleChange(item.key, String(days))}
                    style={{
                      padding: '4px 8px',
                      borderRadius: '6px',
                      fontSize: '12px',
                      border: (retentionForm[item.key] || parseInt(item.current)) === days ? 'none' : '1px solid rgb(var(--theme-border))',
                      background: (retentionForm[item.key] || parseInt(item.current)) === days ? 'rgba(var(--theme-primary), 0.1)' : 'rgb(var(--theme-bg))',
                      color: (retentionForm[item.key] || parseInt(item.current)) === days ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-muted))',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                    }}
                  >
                    {days}天
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default SystemConfigPage;
