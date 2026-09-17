import { get, post, put, del } from './base'

export type ModelClassType = 'base' | 'embedding' | 'rerank'
export type ModelProtocol = 'auto' | 'openai' | 'dashscope' | 'responses' | 'anthropic' | 'gemini' | 'ollama' | 'cohere' | 'ark' | 'viking' | 'jina' | 'voyage' | 'azure'
export interface ModelApiOptions {
  max_tokens?: number
  access_key_id?: string
  region?: string
  endpoint_id?: string
}
export const MODEL_PROTOCOL_OPTIONS: { value: ModelProtocol; label: string; kinds: ModelClassType[] }[] = [
  { value: 'auto', label: '自动识别（保留已有接口行为）', kinds: ['base', 'embedding', 'rerank'] },
  { value: 'openai', label: 'OpenAI 兼容 / 通用重排', kinds: ['base', 'embedding', 'rerank'] },
  { value: 'dashscope', label: 'DashScope 原生', kinds: ['base', 'embedding', 'rerank'] },
  { value: 'responses', label: 'OpenAI Responses', kinds: ['base'] },
  { value: 'anthropic', label: 'Anthropic Claude', kinds: ['base'] },
  { value: 'gemini', label: 'Google Gemini', kinds: ['base', 'embedding'] },
  { value: 'ollama', label: 'Ollama', kinds: ['base', 'embedding'] },
  { value: 'cohere', label: 'Cohere 原生', kinds: ['base', 'embedding', 'rerank'] },
  { value: 'ark', label: '豆包多模态向量（文本输入）', kinds: ['embedding'] },
  { value: 'viking', label: 'Viking / 豆包重排（AK/SK）', kinds: ['rerank'] },
  { value: 'jina', label: 'Jina', kinds: ['embedding', 'rerank'] },
  { value: 'voyage', label: 'Voyage AI', kinds: ['embedding', 'rerank'] },
  { value: 'azure', label: 'Azure OpenAI', kinds: ['base', 'embedding'] },
]
export interface ModelCatalogItem {
  id: string
  capabilities: (ModelClassType | 'other')[]
  capability_source: 'metadata' | 'name' | 'unknown'
}

export interface ModelConfigItem {
  id: string
  model_name: string
  model_type: string
  model_api_key: string | null
  model_class: ModelClassType
  url: string
  api_protocol?: ModelProtocol
  embedding_dimensions?: number | null
  api_options?: ModelApiOptions | null
  created_at?: string
  updated_at?: string
}

export interface ModelConfigListResponse {
  code: number
  msg?: string
  message?: string
  data: ModelConfigItem[] | ModelConfigItem
}

export interface ModelConfigMutationResponse {
  code: number
  msg?: string
  message?: string
  data?: {
    id: string
  }
}

export interface CreateModelConfigParams {
  model_name: string
  model_type: string
  model_api_key: string
  url: string
  model_class: ModelClassType
  api_protocol?: ModelProtocol
  embedding_dimensions?: number | null
  api_options?: ModelApiOptions | null
}

export interface UpdateModelConfigParams {
  id: string
  model_name?: string
  model_type?: string
  model_api_key?: string
  url?: string
  model_class?: ModelClassType
  api_protocol?: ModelProtocol
  embedding_dimensions?: number | null
  api_options?: ModelApiOptions | null
}

export interface DeleteModelConfigParams {
  id: string
}

export interface ModelCatalogResponse {
  code: number
  msg?: string
  data?: {
    models: ModelCatalogItem[]
    partial: boolean
    message: string
  }
}

export const readAvailableModels = (body: { url: string; model_api_key: string; api_protocol?: ModelProtocol }) => {
  return post<ModelCatalogResponse>('/model_config/models', { body })
}

export interface ModelProbeResult {
  success: boolean
  model_class: ModelClassType
  protocol: ModelProtocol
  latency_ms: number
  dimensions?: number
  ranked_documents?: number
  stream?: boolean
  text_chunks?: number
}

export const testModelConnection = (body: CreateModelConfigParams & { test_stream?: boolean }) => {
  return post<{ code: number; msg?: string; data?: ModelProbeResult }>('/model_config/test', { body })
}

export const getModelConfigs = (params?: { id?: string }) => {
  return get<ModelConfigListResponse>('/model_config', {
    params,
  })
}

export const createModelConfig = (body: CreateModelConfigParams) => {
  return post<ModelConfigMutationResponse>('/model_config', {
    body,
  })
}

export const updateModelConfig = (body: UpdateModelConfigParams) => {
  return put<ModelConfigMutationResponse>('/model_config', {
    body,
  })
}

export const deleteModelConfig = (body: DeleteModelConfigParams) => {
  return del<ModelConfigMutationResponse>('/model_config', {
    body,
  })
}
