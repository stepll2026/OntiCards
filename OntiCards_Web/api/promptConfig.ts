import { get, post, del, put } from './base';

export interface PromptConfig {
  id: string;
  file_name: string;
  prompt?: string;
  description?: string;
  category?: string;
  db_type?: string;
  prompt_length?: number;
}

export interface PromptListItem {
  id: string;
  file_name: string;
  description?: string;
  category?: string;
  db_type?: string;
  prompt_length?: number;
  created_at?: string;
  updated_at?: string;
}

export interface PaginationInfo {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface PromptListResponse {
  code: number;
  msg: string;
  data: {
    items: PromptListItem[];
    pagination: PaginationInfo;
  };
}

export interface PromptDetailResponse {
  code: number;
  msg: string;
  data: PromptConfig;
}

export interface CreatePromptParams {
  file_name: string;
  prompt: string;
  description?: string;
}

export interface UpdatePromptParams {
  prompt?: string;
  description?: string;
}

export interface SyncPromptParams {
  file_name?: string;
  file_path?: string;
}

export interface CategoryInfo {
  name: string;
  count: number;
  db_types: string[];
}

export interface CategoriesResponse {
  code: number;
  msg: string;
  data: {
    categories: CategoryInfo[];
    db_types: string[];
  };
}

export interface ApiResponse<T = any> {
  code: number;
  msg: string;
  data?: T;
}

export const getPromptList = (params?: {
  page?: number;
  page_size?: number;
  search?: string;
  category?: string;
  db_type?: string;
  include_prompt?: boolean;
}) => {
  return get<PromptListResponse>('/prompt_config/list', { params });
};

export const getPromptDetail = (id: string) => {
  return get<PromptDetailResponse>(`/prompt_config/${id}`);
};

export const createPrompt = (data: CreatePromptParams) => {
  return post<ApiResponse<{ id: string; file_name: string; description?: string; message: string }>>('/prompt_config/list', { body: data });
};

export const updatePrompt = (id: string, data: UpdatePromptParams) => {
  return put<ApiResponse<{ id: string; file_name: string; updated_fields: string[]; message: string }>>(`/prompt_config/${id}`, { body: data });
};

export const deletePrompt = (id: string) => {
  return del<ApiResponse<{ file_name: string; message: string }>>(`/prompt_config/${id}`);
};

export const getPromptByFileName = (fileName: string, params?: { use_cache?: boolean }) => {
  return get<PromptDetailResponse>(`/prompt_config/file/${encodeURIComponent(fileName)}`, { params });
};

export const syncPrompt = (data: SyncPromptParams = {}) => {
  return post<ApiResponse<any>>('/prompt_config/sync', { body: data });
};

export const getCategories = () => {
  return get<CategoriesResponse>('/prompt_config/categories');
};
