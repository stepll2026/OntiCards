'use client';

/**
 * OrcaRouter provider fields for the model-config form.
 *
 * Renders the two explicit authentication choices side by side:
 *   - `OrcaRouter - API`  — paste an existing `sk-orca-…` key
 *   - `OrcaRouter - Auth` — sign in with an OrcaRouter account (OAuth 2.0 + PKCE, out-of-band code)
 *
 * The model name is always a capability-filtered dropdown sourced from the live catalog; it is
 * never a free-text field, so an unsupported model cannot be entered by hand.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Select } from 'antd';
import { AlertCircle, Check, Copy, ExternalLink, Loader2, RefreshCw } from 'lucide-react';

import {
  ORCAROUTER_AUTH_METHODS,
  ORCAROUTER_KEY_DASHBOARD_URL,
  ORCAROUTER_LOGO_PATH,
  createConnectController,
  filterCatalog,
  type AuthMethodId,
  type CatalogModel,
  type ConnectPhase,
  type ConnectViewState,
  type ModelClass,
} from '@/utils/orcarouter';
import {
  cancelOrcaRouterConnect,
  clearOrcaRouterApiKey,
  getOrcaRouterModels,
  getOrcaRouterStatus,
  saveOrcaRouterApiKey,
  startOrcaRouterConnect,
  submitOrcaRouterCode,
  type OrcaRouterStatus,
} from '@/api/orcarouter';

interface Props {
  modelClass: ModelClass;
  modelName: string;
  onModelNameChange: (value: string) => void;
  apiKey: string;
  onApiKeyChange: (value: string) => void;
  showApiKey: boolean;
  onToggleShowApiKey: () => void;
  notify: (type: 'success' | 'error', text: string) => void;
}

const IDLE_CONNECT_STATE: ConnectViewState = {
  phase: 'idle',
  busy: false,
  hint: null,
  error: null,
  sessionId: null,
  authorizeUrl: null,
  generation: 0,
  maskedKey: null,
};

export default function OrcaRouterProviderFields({
  modelClass,
  modelName,
  onModelNameChange,
  apiKey,
  onApiKeyChange,
  showApiKey,
  onToggleShowApiKey,
  notify,
}: Props) {
  const [authMethod, setAuthMethod] = useState<AuthMethodId>('api_key');
  const [status, setStatus] = useState<OrcaRouterStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [savingKey, setSavingKey] = useState(false);

  const [catalog, setCatalog] = useState<CatalogModel[]>([]);
  const [catalogSource, setCatalogSource] = useState<'live' | 'seed'>('live');
  const [catalogDegraded, setCatalogDegraded] = useState(false);
  const [catalogReason, setCatalogReason] = useState<string | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  // Only clear a stale selection once the catalog has actually been fetched; otherwise the very
  // first render (empty catalog, still loading) would wipe the saved model.
  const [catalogReady, setCatalogReady] = useState(false);
  const [catalogReloadToken, setCatalogReloadToken] = useState(0);

  const [connectState, setConnectState] = useState<ConnectViewState>(IDLE_CONNECT_STATE);
  const [code, setCode] = useState('');

  const refreshStatus = useCallback(async () => {
    setStatusLoading(true);
    try {
      const res = await getOrcaRouterStatus();
      if (res.code === 200) setStatus(res.data);
    } catch (error) {
      console.error('读取 OrcaRouter 状态失败', error);
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  // The model dropdown is recomputed whenever the provider, model class or required modality
  // changes. Today OntiCards has no multimodal entry point, so no modality is requested.
  useEffect(() => {
    let cancelled = false;
    setCatalogLoading(true);
    setCatalogError(null);
    setCatalogReady(false);
    getOrcaRouterModels({ modelClass })
      .then((res) => {
        if (cancelled) return;
        if (res.code === 200) {
          setCatalog(res.data.models || []);
          setCatalogSource(res.data.source);
          setCatalogDegraded(res.data.degraded);
          setCatalogReason(res.data.reason);
          setCatalogReady(true);
        } else {
          setCatalogError(res.msg || res.message || '获取模型目录失败');
        }
      })
      .catch(() => {
        if (!cancelled) setCatalogError('无法获取 OrcaRouter 模型目录');
      })
      .finally(() => {
        if (!cancelled) setCatalogLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [modelClass, catalogReloadToken]);

  // Options are filtered again here so the selector can only ever receive a compatible list.
  const options = useMemo(
    () =>
      filterCatalog(catalog, undefined).map((model) => ({
        value: model.id,
        label: model.name && model.name !== model.id ? `${model.name} (${model.id})` : model.id,
        model,
      })),
    [catalog],
  );

  // Clear a stale selection instead of silently keeping a model the filter no longer returns.
  useEffect(() => {
    if (!modelName) return;
    if (!catalogReady || catalogLoading || catalogError) return;
    if (!options.some((option) => option.value === modelName)) {
      onModelNameChange('');
      notify('error', '当前模型不再兼容，请重新选择模型');
    }
  }, [options, modelName, catalogReady, catalogLoading, catalogError, onModelNameChange, notify]);

  // ---- login lifecycle ----------------------------------------------------------------------
  const connectController = useMemo(
    () =>
      createConnectController({
        startConnect: async () => {
          const res = await startOrcaRouterConnect();
          if (res.code !== 200) throw new Error(res.msg || res.message || '无法开始授权');
          return res.data;
        },
        submitCode: async (sessionId, value) => {
          const res = await submitOrcaRouterCode(sessionId, value);
          if (res.code !== 200) {
            const reason = (res.data as unknown as { reason?: string })?.reason;
            throw new Error(messageForReason(reason) || res.msg || res.message || '授权码换取失败');
          }
          await refreshStatus();
          return { api_key_masked: res.data?.api_key_masked ?? '' };
        },
        cancelConnect: (sessionId, reason) => cancelOrcaRouterConnect(sessionId, reason),
        onUpdate: setConnectState,
      }),
    [refreshStatus],
  );

  const controllerRef = useRef(connectController);
  controllerRef.current = connectController;

  useEffect(() => {
    const onPageHide = () => controllerRef.current.handlePageHide();
    window.addEventListener('pagehide', onPageHide);
    return () => {
      window.removeEventListener('pagehide', onPageHide);
      // A real unmount must release the server-side attempt without writing React state.
      const sessionId = controllerRef.current.getState().sessionId;
      if (sessionId) void cancelOrcaRouterConnect(sessionId, 'unmount');
    };
  }, []);

  const handleSaveApiKey = async () => {
    if (!apiKey.trim()) {
      notify('error', '请粘贴 OrcaRouter API Key');
      return;
    }
    setSavingKey(true);
    try {
      const res = await saveOrcaRouterApiKey(apiKey.trim());
      if (res.code === 200) {
        notify('success', 'OrcaRouter API Key 已保存');
        await refreshStatus();
      } else {
        notify('error', res.msg || res.message || '保存失败');
      }
    } catch {
      notify('error', '保存 OrcaRouter API Key 失败');
    } finally {
      setSavingKey(false);
    }
  };

  const handleClearKey = async () => {
    try {
      await clearOrcaRouterApiKey();
      onApiKeyChange('');
      await refreshStatus();
      notify('success', '已清除 OrcaRouter 凭据');
    } catch {
      notify('error', '清除失败');
    }
  };

  const maskedKey = connectState.maskedKey || status?.api_key_masked || '';

  return (
    <div className="space-y-4" data-testid="orcarouter-fields">
      {/* Two explicit authentication choices */}
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-2">接入方式</label>
        <div
          className="grid grid-cols-2 gap-2"
          data-testid="orcarouter-auth-methods"
          role="radiogroup"
          aria-label="OrcaRouter 接入方式"
        >
          {ORCAROUTER_AUTH_METHODS.map((method) => (
            <button
              key={method.id}
              type="button"
              role="radio"
              aria-checked={authMethod === method.id}
              data-testid={`orcarouter-auth-${method.id}`}
              onClick={() => setAuthMethod(method.id)}
              className={`flex flex-col items-start gap-1 px-3 py-2.5 rounded-[12px] border text-left transition-colors ${
                authMethod === method.id
                  ? 'border-indigo-500 bg-indigo-50'
                  : 'border-slate-200 hover:border-slate-300'
              }`}
            >
              <span className="flex items-center gap-2 text-sm font-medium text-slate-800">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={ORCAROUTER_LOGO_PATH} alt="OrcaRouter" width={18} height={18} />
                {method.label}
              </span>
              <span className="text-xs text-slate-500">{method.description}</span>
            </button>
          ))}
        </div>
      </div>

      {status?.needs_reauth && (
        <div className="flex items-start gap-2 p-3 rounded-[12px] bg-amber-50 text-amber-800 text-xs" data-testid="orcarouter-needs-reauth">
          <AlertCircle className="w-4 h-4 mt-[1px] shrink-0" />
          <span>凭据已失效（密钥被撤销或鉴权失败）。请重新登录或粘贴新的 API Key；系统不会自动刷新。</span>
        </div>
      )}

      {authMethod === 'api_key' ? (
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">OrcaRouter API Key</label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => onApiKeyChange(e.target.value)}
                placeholder="sk-orca-…"
                maxLength={256}
                data-testid="orcarouter-api-key-input"
                className="w-full px-4 py-2.5 pr-10 border border-slate-200 rounded-[12px] text-sm"
              />
              <button
                type="button"
                onClick={onToggleShowApiKey}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                title={showApiKey ? '隐藏' : '显示'}
              >
                {showApiKey ? '隐藏' : '显示'}
              </button>
            </div>
            <button
              type="button"
              onClick={handleSaveApiKey}
              disabled={savingKey}
              data-testid="orcarouter-save-key"
              className="px-4 py-2.5 bg-indigo-600 text-white rounded-[12px] text-sm font-medium disabled:opacity-50 flex items-center gap-2"
            >
              {savingKey ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
              保存密钥
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            在{' '}
            <a
              className="text-indigo-600 inline-flex items-center gap-1"
              href={ORCAROUTER_KEY_DASHBOARD_URL}
              target="_blank"
              rel="noreferrer"
            >
              OrcaRouter 控制台 <ExternalLink className="w-3 h-3" />
            </a>{' '}
            创建密钥后粘贴到这里。密钥保存在服务端，不会回传到浏览器。
          </p>
          {maskedKey && (
            <p className="mt-2 text-xs text-slate-500" data-testid="orcarouter-masked-key">
              已保存密钥：<span className="font-mono">{maskedKey}</span>
              <button type="button" onClick={handleClearKey} className="ml-3 text-red-600">
                清除
              </button>
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-3" data-testid="orcarouter-connect-panel">
          <button
            type="button"
            onClick={() => connectController.start()}
            disabled={connectState.busy}
            data-testid="orcarouter-connect-start"
            className="w-full py-2.5 border border-indigo-500 text-indigo-600 rounded-[12px] text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {connectState.busy ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            连接 OrcaRouter 账号
          </button>

          {connectState.authorizeUrl && (
            <div className="p-3 rounded-[12px] bg-slate-50 text-xs" data-testid="orcarouter-authorize-url">
              <div className="flex items-center justify-between mb-1">
                <span className="text-slate-600">1. 在浏览器中打开授权页面并同意授权</span>
                <span className="flex gap-2">
                  <a
                    className="text-indigo-600 inline-flex items-center gap-1"
                    href={connectState.authorizeUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    打开 <ExternalLink className="w-3 h-3" />
                  </a>
                  <button
                    type="button"
                    className="text-slate-500 inline-flex items-center gap-1"
                    onClick={() => {
                      navigator.clipboard?.writeText(connectState.authorizeUrl || '');
                      notify('success', '授权链接已复制');
                    }}
                  >
                    复制 <Copy className="w-3 h-3" />
                  </button>
                </span>
              </div>
              <div className="break-all font-mono text-[11px] text-slate-500">{connectState.authorizeUrl}</div>
            </div>
          )}

          {connectState.sessionId && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">2. 粘贴授权页面显示的授权码</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="授权码"
                  data-testid="orcarouter-code-input"
                  className="flex-1 px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm"
                />
                <button
                  type="button"
                  onClick={() => connectController.submitCode(code)}
                  disabled={connectState.busy}
                  data-testid="orcarouter-submit-code"
                  className="px-4 py-2.5 bg-indigo-600 text-white rounded-[12px] text-sm font-medium disabled:opacity-50"
                >
                  完成连接
                </button>
                <button
                  type="button"
                  onClick={() => connectController.cancel()}
                  data-testid="orcarouter-cancel"
                  className="px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm"
                >
                  取消
                </button>
              </div>
            </div>
          )}

          {connectState.hint && <p className="text-xs text-slate-500">{connectState.hint}</p>}
          {connectState.error && (
            <p className="text-xs text-red-600" data-testid="orcarouter-connect-error">
              {connectState.error}
            </p>
          )}
          {maskedKey && (
            <p className="text-xs text-slate-500" data-testid="orcarouter-masked-key">
              已连接账号，密钥：<span className="font-mono">{maskedKey}</span>
            </p>
          )}
        </div>
      )}

      {/* Capability-filtered model selector — never free text */}
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-2">
          <span className="text-red-500">*</span> 模型（来自 OrcaRouter 实时目录）
        </label>
        <div className="flex gap-2">
          <Select
            showSearch
            value={modelName || undefined}
            onChange={onModelNameChange}
            placeholder={catalogLoading ? '正在读取模型目录…' : '选择模型'}
            loading={catalogLoading}
            disabled={catalogLoading}
            data-testid="orcarouter-model-select"
            className="flex-1"
            style={{ width: '100%' }}
            optionFilterProp="label"
            options={options.map(({ value, label }) => ({ value, label }))}
            notFoundContent={catalogLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : '无可用模型'}
          />
          <button
            type="button"
            onClick={() => setCatalogReloadToken((token) => token + 1)}
            className="px-3 border border-slate-200 rounded-[12px] text-slate-500"
            title="刷新模型目录"
            data-testid="orcarouter-refresh-catalog"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-500" data-testid="orcarouter-catalog-meta">
          {catalogError
            ? `模型目录读取失败：${catalogError}`
            : `${catalogSource === 'live' ? '实时目录' : '离线备用目录'} · ${options.length} 个可用模型`}
          {catalogDegraded && !catalogError && (
            <span className="ml-2 text-amber-600">（已降级：{catalogReason || '实时目录不可用'}）</span>
          )}
        </p>
      </div>
    </div>
  );
}

function messageForReason(reason?: string): string | null {
  switch (reason) {
    case 'code_rejected':
      return '授权码无效、已过期或已被使用，请重新连接';
    case 'challenge_mismatch':
      return 'PKCE 校验失败，请重新点击“连接 OrcaRouter 账号”';
    case 'rate_limited':
      return '授权请求过于频繁（24 小时内最多 10 次），请稍后再试';
    case 'expired':
      return '授权窗口已关闭，请重新连接';
    case 'network_error':
      return '无法连接 OrcaRouter 授权服务，请检查网络';
    case 'cancelled':
      return '已取消授权';
    default:
      return null;
  }
}
