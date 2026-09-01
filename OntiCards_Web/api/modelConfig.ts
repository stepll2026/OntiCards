import { get, post, put, del } from './base'

export type ModelClassType = 'base' | 'embedding' | 'rerank'

export interface ModelConfigItem {
  id: string
  model_name: string
  model_type: string
  model_api_key: string
  model_class: ModelClassType
  url: string
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
}

export interface UpdateModelConfigParams {
  id: string
  model_name?: string
  model_type?: string
  model_api_key?: string
  url?: string
  model_class?: ModelClassType
}

export interface DeleteModelConfigParams {
  id: string
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
