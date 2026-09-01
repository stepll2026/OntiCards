'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next-nprogress-bar';
import { login, getUserInfo } from '@/api/user';
import { setLoggingOut } from '@/api/base';
import { setUserInfoInitialized, notifySSOTokenStored } from '@/hooks/useUserInfo';
import type { UserInfoType } from '@/context/homeContext';
import { Loader2, Eye, EyeOff, AlertCircle, CheckCircle } from 'lucide-react';

// SSO回调处理逻辑
const handleSSOCallback = async (router: ReturnType<typeof useRouter>, lng: string) => {
  const params = new URLSearchParams(window.location.search);
  const accessToken = params.get('access_token');

  if (!accessToken) {
    return false;
  }

  // 将SSO返回的access_token存入localStorage
  localStorage.setItem('console_token', accessToken);
  document.cookie = `console_token=${accessToken}; path=/; max-age=${30 * 24 * 60 * 60}`;

  // 通知其他组件 token 已存储（UserInfoProvider 会收到通知）
  notifySSOTokenStored();

  // 重置登录状态
  setLoggingOut(false);

  // 获取用户信息
  try {
    const userInfoRes = await getUserInfo() as { data: UserInfoType };
    if (userInfoRes?.data) {
      window.localStorage.setItem('userInfo', JSON.stringify(userInfoRes.data));
      // 标记用户信息已初始化，避免重复获取
      setUserInfoInitialized(userInfoRes.data);
    }
  } catch (err) {
    console.error('SSO登录获取用户信息失败:', err);
  }

  // 清除URL中的access_token参数，并跳转到概览页
  const cleanUrl = window.location.pathname + window.location.hash;
  window.history.replaceState(null, '', cleanUrl);
  router.push(`/${lng}/overview`);

  return true;
};

const ERROR_MESSAGE_MAP: Record<string, string> = {
  'Invalid username or password': '用户名或密码错误，请重新输入',
  'User not found': '用户不存在，请检查用户名',
  'Account is disabled': '该账户已被禁用，请联系管理员',
  'Account has been disabled, please contact the administrator': '当前用户已被禁用，请联系管理员',
  'Account is locked': '账户已被锁定，请稍后重试或联系管理员',
  'Password expired': '密码已过期，请联系管理员重置密码',
  'Too many failed attempts': '登录失败次数过多，请稍后再试',
  'Network Error': '网络连接失败，请检查网络后重试',
  'Server Error': '服务器异常，请稍后重试',
  'Unauthorized': '认证失败，请重新登录',
  'request timeout': '请求超时，请检查网络后重试',
};

const getFriendlyErrorMessage = (errorMessage: string): string => {
  if (ERROR_MESSAGE_MAP[errorMessage]) {
    return ERROR_MESSAGE_MAP[errorMessage];
  }

  const lowerErrorMsg = errorMessage.toLowerCase();

  if (lowerErrorMsg.includes('disabled') || lowerErrorMsg.includes('禁用')) {
    return '当前用户已被禁用，请联系管理员';
  }

  if (lowerErrorMsg.includes('locked') || lowerErrorMsg.includes('锁定')) {
    return '账户已被锁定，请稍后重试或联系管理员';
  }

  if (lowerErrorMsg.includes('password') || lowerErrorMsg.includes('username') || lowerErrorMsg.includes('invalid')) {
    return '用户名或密码错误，请重新输入';
  }

  if (lowerErrorMsg.includes('network') || lowerErrorMsg.includes('timeout')) {
    return '网络连接失败，请检查网络后重试';
  }

  if (lowerErrorMsg.includes('server') || lowerErrorMsg.includes('500')) {
    return '服务器异常，请稍后重试';
  }

  return '登录失败，请稍后重试';
};

interface LoginPageProps {
  lng: string;
}

export default function LoginPage({ lng }: LoginPageProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [isSSOLoading, setIsSSOLoading] = useState(false);
  const router = useRouter();

  // SSO回调处理：检查URL中是否有access_token
  useEffect(() => {
    const handleSSOLoading = async () => {
      const params = new URLSearchParams(window.location.search);
      const hasAccessToken = params.has('access_token');

      // 只有在 URL 中有 access_token 时才显示 SSO 加载状态
      if (hasAccessToken) {
        setIsSSOLoading(true);
        const isSSOCallback = await handleSSOCallback(router, lng);
        setIsSSOLoading(false);
        if (isSSOCallback) {
          return;
        }
      }
    };
    handleSSOLoading();
  }, [router, lng]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!username || !password) {
      setError('请输入用户名和密码');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const loginRes = await login({ username, password });

      if (loginRes.code === 200 && loginRes.data.token) {
        setLoggingOut(false);

        localStorage.setItem('console_token', loginRes.data.token);
        document.cookie = `console_token=${loginRes.data.token}; path=/; max-age=${30 * 24 * 60 * 60}`;

        const userInfoRes = await getUserInfo() as { data: UserInfoType };
        if (userInfoRes?.data) {
          window.localStorage.setItem('userInfo', JSON.stringify(userInfoRes.data));
        }

        setSuccess(true);
        setLoading(false);

        setTimeout(() => {
          router.push(`/${lng}/overview`);
        }, 1000);
      } else {
        const friendlyMessage = getFriendlyErrorMessage(loginRes.message || 'Unknown error');
        setError(friendlyMessage);
        setLoading(false);
      }
    } catch (err: any) {
      console.error('登录失败:', err);
      const errorMessage = err?.message || err?.toString() || 'Unknown error';
      const friendlyMessage = getFriendlyErrorMessage(errorMessage);
      setError(friendlyMessage);
      setLoading(false);
    }
  };

  return (
    <div className="login-page min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background decorations */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/4 -left-32 w-96 h-96 bg-blue-200/30 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 -right-32 w-96 h-96 bg-indigo-200/30 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-to-r from-blue-100/40 to-purple-100/40 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* SSO加载状态 */}
        {isSSOLoading ? (
          <div className="bg-white shadow-xl border border-slate-100 overflow-hidden flex items-center justify-center p-12" style={{ borderRadius: '24px' }}>
            <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
            <span className="ml-3 text-slate-600">SSO登录中...</span>
          </div>
        ) : (
          <>
            {/* Logo & Title */}
            <div className="text-center mb-4">
              <div className="inline-flex items-center justify-center mb-1">
                <img src="/statics/new_logo_final.png" alt="OntiCards" className="h-20 w-auto object-contain" style={{ mixBlendMode: 'multiply' }} />
              </div>
              <h1 className="text-2xl font-semibold text-slate-900">欢迎使用</h1>
              <p className="text-sm text-slate-500 mt-1">OntiCards - AI数据中枢</p>
            </div>

            {/* Login Card */}
            <div className="bg-white shadow-xl border border-slate-100 overflow-hidden" style={{ borderRadius: '24px' }}>
          <form onSubmit={handleSubmit} className="p-8 space-y-6">
            {/* Error Message */}
            {error && (
              <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 text-sm text-red-600" style={{ borderRadius: '16px' }}>
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                {error}
              </div>
            )}

            {/* Success Message */}
            {success && (
              <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 text-sm text-green-600" style={{ borderRadius: '16px' }}>
                <CheckCircle className="w-5 h-5 flex-shrink-0" />
                登录成功！正在跳转...
              </div>
            )}

            {/* Username */}
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-slate-700 mb-2">
                用户名
              </label>
              <div className="relative">
                <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                </div>
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={loading}
                  placeholder="请输入用户名"
                  className="w-full pl-12 pr-4 py-3.5 bg-slate-50 border border-slate-200 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent focus:bg-white disabled:opacity-50 transition-all"
                  style={{ borderRadius: '16px' }}
                  autoComplete="username"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-2">
                密码
              </label>
              <div className="relative">
                <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={loading}
                  placeholder="请输入密码"
                  className="w-full pl-12 pr-14 py-3.5 bg-slate-50 border border-slate-200 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent focus:bg-white disabled:opacity-50 transition-all"
                  style={{ borderRadius: '16px' }}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading || success}
              className="w-full py-3.5 px-6 bg-indigo-600 text-white font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-2"
              style={{ borderRadius: '16px' }}
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  登录中...
                </>
              ) : (
                '登录'
              )}
            </button>
          </form>

          {/* Footer */}
          <div className="px-8 py-5 bg-slate-50 border-t border-slate-100" style={{ borderBottomLeftRadius: '24px', borderBottomRightRadius: '24px' }}>
            <p className="text-center text-xs text-slate-400">
              © 2025 OntiCards. 保留所有权利。
            </p>
          </div>
        </div>
          </>
        )}
      </div>
    </div>
  );
}
