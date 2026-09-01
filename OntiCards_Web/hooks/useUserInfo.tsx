'use client';

import React, { createContext, useContext, useEffect, useState, useRef } from 'react';
import { getUserInfo } from '@/api/user';

export interface UserInfoType {
  id: string;
  username: string;
  nickname?: string;
  email?: string;
  role?: 'admin' | 'normal';
  status?: 'normal' | 'disabled';
  avatar?: string;
  created_at?: string;
  updated_at?: string;
}

interface UserInfoContextType {
  userInfo: UserInfoType | null;
  loading: boolean;
  error: Error | null;
  // 刷新用户信息（强制从 API 重新获取）
  refreshUserInfo: () => Promise<void>;
}

const UserInfoContext = createContext<UserInfoContextType | null>(null);

// 模块级全局状态，确保跨 Provider 实例共享
let globalUserInfo: UserInfoType | null = null;
let globalLoading = true;
let globalError: Error | null = null;
let hasInitialized = false;

// 从 localStorage 获取缓存的用户信息
const getCachedUserInfo = (): UserInfoType | null => {
  if (typeof window === 'undefined') return null;
  try {
    const cached = window.localStorage.getItem('userInfo');
    if (cached && cached !== 'undefined') {
      return JSON.parse(cached) as UserInfoType;
    }
  } catch {
    // ignore
  }
  return null;
};

// 保存用户信息到 localStorage
const setCachedUserInfo = (userInfo: UserInfoType): void => {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem('userInfo', JSON.stringify(userInfo));
  } catch {
    // ignore
  }
};

// 清除 localStorage 中的用户信息
const clearCachedUserInfo = (): void => {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem('userInfo');
  } catch {
    // ignore
  }
};

// 重置全局状态（退出登录时调用）
export const resetGlobalUserInfo = (): void => {
  globalUserInfo = null;
  globalLoading = true;
  globalError = null;
  hasInitialized = false;
};

// 标记用户信息已初始化（SSO登录后调用，避免重复获取）
export const setUserInfoInitialized = (userInfo: UserInfoType): void => {
  globalUserInfo = userInfo;
  globalLoading = false;
  globalError = null;
  hasInitialized = true;
};

// 检查是否是SSO回调（URL中有access_token参数）
export const isSSOCallback = (): boolean => {
  if (typeof window === 'undefined') return false;
  const params = new URLSearchParams(window.location.search);
  return params.has('access_token');
};

// SSO token 存储完成事件
const SSO_TOKEN_STORED_EVENT = 'sso_token_stored';

// 触发 SSO token 存储完成事件
export const notifySSOTokenStored = (): void => {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(SSO_TOKEN_STORED_EVENT));
};

// 监听 SSO token 存储完成事件
export const onSSOTokenStored = (callback: () => void): (() => void) => {
  if (typeof window === 'undefined') return () => {};
  const handler = () => callback();
  window.addEventListener(SSO_TOKEN_STORED_EVENT, handler);
  return () => window.removeEventListener(SSO_TOKEN_STORED_EVENT, handler);
};

export const UserInfoProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [userInfo, setUserInfo] = useState<UserInfoType | null>(globalUserInfo);
  const [loading, setLoading] = useState(globalLoading);
  const [error, setError] = useState<Error | null>(globalError);

  // 初始化全局状态
  useEffect(() => {
    if (hasInitialized) {
      // 已经初始化过，直接使用全局状态
      setUserInfo(globalUserInfo);
      setLoading(globalLoading);
      setError(globalError);
      return;
    }

    hasInitialized = true;

    const init = async () => {
      // 检查是否是SSO回调场景
      const isSSOCall = isSSOCallback();

      // SSO回调时，等待token存储后再获取用户信息
      if (isSSOCall) {
        // SSO场景：监听token存储完成事件
        await new Promise<void>((resolve) => {
          // 监听 SSO token 存储完成事件
          const unsubscribe = onSSOTokenStored(() => {
            unsubscribe();
            resolve();
          });

          // 同时设置超时保险，最多等待3秒
          setTimeout(() => {
            unsubscribe();
            resolve();
          }, 3000);
        });
      }

      // 优先使用缓存
      const cached = getCachedUserInfo();
      if (cached?.id) {
        globalUserInfo = cached;
        globalLoading = false;
        setUserInfo(cached);
        setLoading(false);
        // 静默刷新（不阻塞），在后台更新
        refreshUserInfoSilent();
        return;
      }

      // 检查是否有token，如果没有token则不调用API
      const token = localStorage.getItem('console_token');
      if (!token) {
        globalLoading = false;
        setLoading(false);
        return;
      }

      // 从 API 获取
      try {
        const res = await getUserInfo() as any;
        if (res?.data) {
          const userData = res.data as UserInfoType;
          globalUserInfo = userData;
          globalError = null;
          setUserInfo(userData);
          setCachedUserInfo(userData);
        }
      } catch (err) {
        console.error('获取用户信息失败:', err);
        globalError = err as Error;
        setError(globalError);
        clearCachedUserInfo();
      } finally {
        globalLoading = false;
        setLoading(false);
      }
    };

    init();
  }, []);

  // 静默刷新（在后台更新用户信息，不显示 loading）
  const refreshUserInfoSilent = async () => {
    try {
      const res = await getUserInfo() as any;
      if (res?.data) {
        const userData = res.data as UserInfoType;
        globalUserInfo = userData;
        setUserInfo(userData);
        setCachedUserInfo(userData);
      }
    } catch {
      // 静默刷新失败时忽略，保持现有数据
    }
  };

  // 强制刷新用户信息
  const refreshUserInfo = async () => {
    setLoading(true);
    globalLoading = true;
    setError(null);
    globalError = null;

    try {
      const res = await getUserInfo() as any;
      if (res?.data) {
        const userData = res.data as UserInfoType;
        globalUserInfo = userData;
        setUserInfo(userData);
        setCachedUserInfo(userData);
      }
    } catch (err) {
      console.error('获取用户信息失败:', err);
      globalError = err as Error;
      setError(globalError);
    } finally {
      globalLoading = false;
      setLoading(false);
    }
  };

  return (
    <UserInfoContext.Provider value={{ userInfo, loading, error, refreshUserInfo }}>
      {children}
    </UserInfoContext.Provider>
  );
};

// 自定义 hook 用于获取用户信息
export const useUserInfo = () => {
  const context = useContext(UserInfoContext);
  // 如果不在 Provider 内部，返回默认值而不是抛出错误
  if (!context) {
    // 尝试从 localStorage 获取缓存的用户信息
    const cachedUser = getCachedUserInfo();
    return {
      userInfo: cachedUser,
      loading: !cachedUser,
      error: null,
      refreshUserInfo: async () => {
        // 如果没有缓存，也不做任何事
      }
    };
  }
  return context;
};
