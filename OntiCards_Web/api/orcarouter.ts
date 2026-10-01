/**
 * OrcaRouter provider client for the OntiCards console.
 *
 * Two explicit authentication choices are exposed, matching the backend seam:
 *   - `api_key`  — paste an existing `sk-orca-…` key (`OrcaRouter - API`)
 *   - `pkce`     — sign in with an OrcaRouter account (`OrcaRouter - Auth`)
 *
 * The PKCE verifier never reaches the browser: `connectStart` returns only an authorize URL and a
 * session id, and the code the user pastes is exchanged server-side.
 */

import { get, post } from './base'

export const ORCAROUTER_PROVIDER_ID = 'orcarouter'
/** The value stored in `model_config.model_type` that marks an OrcaRouter row. */
export const ORCAROUTER_MODEL_TYPE = 'orcarouter'
export const ORCAROUTER_API_BASE = 'https://api.orcarouter.ai/v1'
export const ORCAROUTER_AUTH_BASE = 'https://www.orcarouter.ai'
export const ORCAROUTER_KEY_DASHBOARD_URL = 'https://www.orcarouter.ai/console/token'
export const ORCAROUTER_LOGO_PATH = '/statics/orcarouter-logo-classic.png'

export type AuthMethodId = 'api_key' | 'pkce'

export interface AuthMethod {
  id: AuthMethodId
  label: string
  available: boolean
}

export interface OrcaRouterStatus {
  provider: string
  auth_base: string
  api_base: string
  configured: boolean
  has_key: boolean
  api_key_masked: string
  credential_source: AuthMethodId | null
  scope: string | null
  generation: number
  needs_reauth: boolean
  auth_methods: AuthMethod[]
  key_dashboard_url: string
  connected_apps_url: string
}

export interface ConnectSession {
  session_id: string
  authorize_url: string
  status: 'pending' | 'completed' | 'failed' | 'cancelled' | 'expired'
  generation: number
  expires_in: number
  error_reason: string | null
  error_message: string | null
}

export interface CatalogModel {
  id: string
  name: string
  supported_endpoint_types?: string[]
  input_modalities?: string[]
  reasoning?: boolean
  reasoning_efforts?: string[]
  context_length?: number
}

export interface CatalogPayload {
  models: CatalogModel[]
  source: 'live' | 'seed'
  degraded: boolean
  reason: string | null
  count: number
  total_before_filter: number
}

export interface ApiResponse<T> {
  code: number
  msg?: string
  message?: string
  data: T
}

const prefix = '/orcarouter'

export const getOrcaRouterStatus = () => get<ApiResponse<OrcaRouterStatus>>(`${prefix}/status`)

export const saveOrcaRouterApiKey = (api_key: string) =>
  post<ApiResponse<{ api_key_masked: string; credential_source: AuthMethodId; generation: number }>>(
    `${prefix}/api-key`,
    { body: { api_key } },
  )

export const clearOrcaRouterApiKey = () => post<ApiResponse<OrcaRouterStatus>>(`${prefix}/api-key/clear`, { body: {} })

export const startOrcaRouterConnect = () => post<ApiResponse<ConnectSession>>(`${prefix}/connect/start`, { body: {} })

export const getOrcaRouterConnect = (sessionId: string) =>
  get<ApiResponse<ConnectSession>>(`${prefix}/connect/${encodeURIComponent(sessionId)}`)

export const submitOrcaRouterCode = (sessionId: string, code: string) =>
  post<ApiResponse<{ connected: boolean; scope: string; credential_source: AuthMethodId; api_key_masked?: string }>>(
    `${prefix}/connect/${encodeURIComponent(sessionId)}/code`,
    { body: { code } },
  )

/**
 * Release a pending authorization. `reason` is recorded server-side; `pagehide` is passed when the
 * page is being frozen so the server does not keep a login open across a back-forward-cache restore.
 */
export const cancelOrcaRouterConnect = (sessionId: string, reason = 'cancelled') =>
  post<ApiResponse<{ cancelled: boolean }>>(`${prefix}/connect/${encodeURIComponent(sessionId)}/cancel`, {
    body: { reason },
  })

export interface CatalogQuery {
  modelClass: 'base' | 'embedding' | 'rerank'
  /** Capability to filter by; defaults to the model class on the server. */
  capability?: string
  /** Non-text input modalities actually being uploaded; models that do not declare them are excluded. */
  modalities?: string[]
}

export const getOrcaRouterModels = ({ modelClass, capability, modalities }: CatalogQuery) => {
  const params: Record<string, string> = { model_class: modelClass }
  if (capability) params.capability = capability
  if (modalities && modalities.length) params.modalities = modalities.join(',')
  return get<ApiResponse<CatalogPayload>>(`${prefix}/models`, { params })
}
