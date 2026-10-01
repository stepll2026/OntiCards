/**
 * Framework-free OrcaRouter rules shared by the provider UI and its tests.
 *
 * These mirror the backend contract in `core/orcarouter/` exactly, so a model the capability
 * filter excludes can never reach a model selector even if the UI is driven directly.
 * No React / Next / antd imports live here on purpose: the rules must be testable in isolation.
 */

export const ORCAROUTER_PROVIDER_ID = 'orcarouter'
export const ORCAROUTER_MODEL_TYPE = 'orcarouter'
export const ORCAROUTER_AUTH_BASE = 'https://www.orcarouter.ai'
export const ORCAROUTER_API_BASE = 'https://api.orcarouter.ai/v1'
export const ORCAROUTER_KEY_DASHBOARD_URL = 'https://www.orcarouter.ai/console/token'
export const ORCAROUTER_CONNECTED_APPS_URL = 'https://www.orcarouter.ai/console/authorized-apps'
export const ORCAROUTER_LOGO_PATH = '/statics/orcarouter-logo-classic.png'

export type ModelClass = 'base' | 'embedding' | 'rerank'
export type AuthMethodId = 'api_key' | 'pkce'
export type Capability = 'chat' | 'embedding' | 'image' | 'video' | 'rerank'

export const MODEL_CLASS_CAPABILITY: Record<ModelClass, Capability> = {
  base: 'chat',
  embedding: 'embedding',
  rerank: 'rerank',
}

/** Endpoint paths appended to the inference base — identical to the backend `MODEL_CLASS_PATHS`. */
export const MODEL_CLASS_PATHS: Record<ModelClass, string> = {
  base: '/chat/completions',
  embedding: '/embeddings',
  rerank: '/rerank',
}

const TEXT_ENDPOINT_TYPES = ['openai', 'openai-response', 'anthropic', 'gemini']
const NON_TEXT_ENDPOINT_TYPES = ['image-generation', 'openai-video', 'jina-rerank', 'embeddings']

export interface CatalogModel {
  id: string
  name: string
  supported_endpoint_types?: string[]
  input_modalities?: string[]
  reasoning?: boolean
  reasoning_efforts?: string[]
  context_length?: number
}

/** The two authentication choices, presented side by side on the OrcaRouter form. */
export const ORCAROUTER_AUTH_METHODS: { id: AuthMethodId; label: string; description: string }[] = [
  {
    id: 'api_key',
    label: 'OrcaRouter - API',
    description: '使用已有的 sk-orca- 密钥',
  },
  {
    id: 'pkce',
    label: 'OrcaRouter - Auth',
    description: '使用 OrcaRouter 账号授权登录',
  },
]

export function isOrcaRouterModelType(modelType?: string | null): boolean {
  return (modelType || '').trim().toLowerCase() === ORCAROUTER_MODEL_TYPE
}

export function isLoopbackUrl(url: string): boolean {
  try {
    const parsed = new URL(url.includes('://') ? url : `https://${url}`)
    return ['localhost', '127.0.0.1', '::1', '[::1]'].includes(parsed.hostname)
  } catch {
    return false
  }
}

/**
 * Turn a stored `model_config.url` into the URL the request path posts to.
 * Non-OrcaRouter rows keep the historical behaviour: the stored value is used verbatim.
 */
export function resolveModelUrl(modelType: string | null | undefined, modelClass: ModelClass, url: string): string {
  const stored = (url || '').trim()
  if (!isOrcaRouterModelType(modelType)) return stored
  const base = (stored || ORCAROUTER_API_BASE).replace(/\/+$/, '')
  const path = MODEL_CLASS_PATHS[modelClass]
  return base.endsWith(path) ? base : base + path
}

/**
 * Apply the capability rules. `requiredModalities` is fail-closed: a model that does not
 * *explicitly* declare a modality is excluded, never guessed from its name.
 */
export function filterCatalog(
  models: CatalogModel[],
  capability?: Capability | null,
  requiredModalities?: string[] | null,
): CatalogModel[] {
  const required = (requiredModalities || []).map((m) => m.toLowerCase()).filter(Boolean)
  return (models || []).filter((model) => {
    const types = (model.supported_endpoint_types || []).map((t) => t.toLowerCase())
    if (capability && (capability as string) !== 'all') {
      if (capability === 'chat') {
        if (!types.some((t) => TEXT_ENDPOINT_TYPES.includes(t))) return false
        if (types.some((t) => NON_TEXT_ENDPOINT_TYPES.includes(t))) return false
      } else if (capability === 'embedding') {
        if (!types.includes('embeddings')) return false
      } else if (capability === 'image') {
        if (!types.includes('image-generation')) return false
      } else if (capability === 'video') {
        if (!types.includes('openai-video')) return false
      } else if (capability === 'rerank') {
        if (!types.includes('jina-rerank')) return false
      } else {
        return false
      }
    }
    if (required.length) {
      const declared = (model.input_modalities || []).map((m) => m.toLowerCase())
      if (!required.every((m) => declared.includes(m))) return false
    }
    return true
  })
}

/**
 * True when a previously selected model is still compatible with the current requirement.
 * The UI uses this to clear a stale selection instead of silently keeping an invalid value.
 */
export function isModelStillCompatible(
  modelId: string,
  models: CatalogModel[],
  capability?: Capability | null,
  requiredModalities?: string[] | null,
): boolean {
  return filterCatalog(models, capability, requiredModalities).some((m) => m.id === modelId)
}

export function maskKey(key?: string | null): string {
  if (!key) return ''
  if (key.length <= 8) return '*'.repeat(key.length)
  return `${key.slice(0, 7)}…${'*'.repeat(4)}`
}

/** Map an auth-method id onto the label shown anywhere both choices can appear. */
export function authMethodLabel(id: AuthMethodId | null | undefined): string {
  const method = ORCAROUTER_AUTH_METHODS.find((m) => m.id === id)
  return method ? method.label : ''
}

// ---------------------------------------------------------------------------------------------
// Login lifecycle
// ---------------------------------------------------------------------------------------------

export type ConnectPhase = 'idle' | 'starting' | 'awaiting_code' | 'exchanging' | 'connected' | 'error'

export interface ConnectViewState {
  phase: ConnectPhase
  busy: boolean
  hint: string | null
  error: string | null
  sessionId: string | null
  authorizeUrl: string | null
  generation: number
  maskedKey: string | null
}

export interface ConnectSessionLike {
  session_id: string
  authorize_url: string
  status: string
}

export interface ConnectControllerDeps {
  startConnect: () => Promise<ConnectSessionLike>
  submitCode: (sessionId: string, code: string) => Promise<{ api_key_masked?: string }>
  cancelConnect: (sessionId: string, reason: string) => void | Promise<unknown>
  /** Called whenever the view state changes; the React layer re-renders from this. */
  onUpdate: (state: ConnectViewState) => void
}

export interface ConnectController {
  getState: () => ConnectViewState
  /** Begin a login. A second call supersedes the first even if the first is still in flight. */
  start: () => Promise<void>
  submitCode: (code: string) => Promise<void>
  cancel: (reason?: string) => void
  /**
   * Release everything when the page is hidden or frozen.
   *
   * The browser may put a mounted page into the back-forward cache instead of unmounting it, so
   * this must synchronously clear busy/hint state itself — it cannot rely on a guarded `finally`
   * block, which will correctly refuse to mutate state and leave the restored page stuck busy.
   */
  handlePageHide: () => void
}

/**
 * Generation-guarded login controller.
 *
 * Every async response checks that it still belongs to the current generation before it is allowed
 * to change credentials or UI state, so a late URL or success from one attempt can never appear
 * under a newer one.
 */
export function createConnectController(deps: ConnectControllerDeps): ConnectController {
  let generation = 0
  let state: ConnectViewState = {
    phase: 'idle',
    busy: false,
    hint: null,
    error: null,
    sessionId: null,
    authorizeUrl: null,
    generation: 0,
    maskedKey: null,
  }

  const emit = (next: Partial<ConnectViewState>) => {
    state = { ...state, ...next, generation }
    deps.onUpdate(state)
  }

  const isCurrent = (token: number) => token === generation

  return {
    getState: () => state,

    async start() {
      const token = ++generation
      emit({
        phase: 'starting',
        busy: true,
        hint: '正在创建 OrcaRouter 授权链接…',
        error: null,
        sessionId: null,
        authorizeUrl: null,
      })
      try {
        const session = await deps.startConnect()
        if (!isCurrent(token)) return // superseded while in flight
        emit({
          phase: 'awaiting_code',
          busy: false,
          sessionId: session.session_id,
          authorizeUrl: session.authorize_url,
          hint: '已在浏览器打开授权页面；完成授权后把显示的授权码粘贴到下方。',
        })
      } catch (error) {
        if (!isCurrent(token)) return
        emit({
          phase: 'error',
          busy: false,
          hint: null,
          error: error instanceof Error ? error.message : '无法开始 OrcaRouter 授权',
        })
      }
    },

    async submitCode(code: string) {
      const token = generation
      const sessionId = state.sessionId
      if (!sessionId) {
        emit({ phase: 'error', error: '请先点击“连接 OrcaRouter”开始授权' })
        return
      }
      if (!code.trim()) {
        emit({ phase: 'error', error: '请粘贴授权码' })
        return
      }
      emit({ phase: 'exchanging', busy: true, error: null, hint: '正在换取 OrcaRouter 密钥…' })
      try {
        const result = await deps.submitCode(sessionId, code.trim())
        if (!isCurrent(token)) return
        emit({
          phase: 'connected',
          busy: false,
          hint: '已连接 OrcaRouter 账号',
          error: null,
          maskedKey: result?.api_key_masked ?? null,
        })
      } catch (error) {
        if (!isCurrent(token)) return
        emit({
          phase: 'error',
          busy: false,
          hint: null,
          error: error instanceof Error ? error.message : '授权码换取失败',
        })
      }
    },

    cancel(reason = 'cancelled') {
      const sessionId = state.sessionId
      generation += 1
      emit({ phase: 'idle', busy: false, hint: null, error: null, sessionId: null, authorizeUrl: null })
      if (sessionId) {
        try {
          void deps.cancelConnect(sessionId, reason)
        } catch {
          /* cancellation is best-effort */
        }
      }
    },

    handlePageHide() {
      const sessionId = state.sessionId
      // Invalidate first so any in-flight response is discarded.
      generation += 1
      // Clear the UI synchronously: a bfcache restore must not come back busy.
      state = {
        ...state,
        phase: 'idle',
        busy: false,
        hint: null,
        error: null,
        sessionId: null,
        authorizeUrl: null,
        generation,
      }
      deps.onUpdate(state)
      if (sessionId) {
        // Tell the server to release the attempt; the page may already be frozen.
        try {
          void deps.cancelConnect(sessionId, 'pagehide')
        } catch {
          /* best-effort */
        }
      }
    },
  }
}

