'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useSearchParams, usePathname, useParams } from 'next/navigation';
import { useRouter } from 'next-nprogress-bar';
import {
  Settings,
  User,
  Key,
  Brain,
  Database,
  Bell,
  Globe,
  Palette,
  Save,
  Loader2,
  CheckCircle,
  Plus,
  Eye,
  EyeOff,
  Copy,
  Trash2,
  Edit3,
  X,
  FileText,
  AlertCircle,
  Check,
  Plug,
  Search,
  Users,
  Moon,
  Sun,
  Monitor,
  Clock,
  Layout,
  Shield,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { getApiKeysByUserId, createApiKey, updateApiKey, deleteApiKey, ApiKeyItem } from '@/api/apiKey';
import { getModelConfigs, createModelConfig, updateModelConfig, deleteModelConfig, ModelConfigItem, ModelClassType } from '@/api/modelConfig';
import { getChangelog, createChangelog, updateChangelog, deleteChangelog, ChangelogItem } from '@/api/changeLog';
import { getAllUsers, updateUser, deleteUser, createUser, editUser } from '@/api/user';
import { getDataRetention, updateDataRetention, DataRetentionConfig, UpdateDataRetentionParams } from '@/api/systemConfig';
import { useUserInfo, resetGlobalUserInfo } from '@/hooks';
import { notifyChangelogChanged } from '@/hooks/useDataSources';
import { setLoggingOut } from '@/api/base';
import { App, Switch, Form, Input, Select, message } from 'antd';
import ReactMarkdown from '@/components/reactMarkdown/ReactMarkdown';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import utc from 'dayjs/plugin/utc';
import 'dayjs/locale/zh-cn';

dayjs.extend(relativeTime);
dayjs.extend(utc);
dayjs.locale('zh-cn');

const maskKey = (key: string) => {
  if (!key || key.length <= 8) return key || '';
  return key.substring(0, 8) + '••••••••••••' + key.substring(key.length - 4);
};

const formatDate = (dateString: string | null) => {
  if (!dateString) return '从未使用';
  return new Date(dateString).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' });
};

/** 兼容后端多种字段名的邮箱（/users/all 等接口返回，用于展示与表单） */
const pickEmailFromUser = (u: any): string => {
  if (!u || typeof u !== 'object') return '';
  const v =
    u.email ??
    u.Email ??
    u.user_email ??
    u.userEmail ??
    u.mail ??
    u.email_address ??
    (u.profile && (u.profile.email ?? u.profile.user_email));
  return typeof v === 'string' ? String(v).trim() : '';
};

const SettingsPage = ({ lng }: { lng?: string }) => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const { userInfo, loading: userLoading } = useUserInfo();
  // 兼容通过 params.lng 传入和直接使用 useParams 两种方式
  const params = useParams<{ lng?: string }>();
  const resolvedLng = lng ?? params?.lng ?? 'zh-CN';

  const [activeTab, setActiveTab] = useState('account');
  const [currentUserId, setCurrentUserId] = useState<string>('');
  const [currentUserRole, setCurrentUserRole] = useState<string>('normal');
  const [currentUserInfo, setCurrentUserInfo] = useState<any>(null);
  const [userLoaded, setUserLoaded] = useState(false);

  // 从 Context 获取用户信息，设置到组件状态
  useEffect(() => {
    if (userInfo) {
      setCurrentUserId(userInfo.id);
      setCurrentUserRole(userInfo.role || 'normal');
      setCurrentUserInfo(userInfo);
      setUserLoaded(true);
    } else if (!userLoading) {
      // 如果没有加载中且没有用户信息，说明获取失败
      setUserLoaded(true);
    }
  }, [userInfo, userLoading]);

  // 基础 Tab 列表（所有用户可见）
  const baseTabs = [
    { id: 'account', label: '账户', icon: <User className="w-4 h-4" /> },
    { id: 'api-keys', label: 'API密钥', icon: <Key className="w-4 h-4" /> },
    { id: 'data-retention', label: '数据保留', icon: <Clock className="w-4 h-4" /> },
    { id: 'changelog', label: '更新日志', icon: <FileText className="w-4 h-4" /> },
    { id: 'system', label: '系统设置', icon: <Settings className="w-4 h-4" /> }
  ];

  // 完整的 Tab 列表（管理员可见更多功能）
  const fullTabs = [
    { id: 'account', label: '账户', icon: <User className="w-4 h-4" /> },
    { id: 'users', label: '用户管理', icon: <Users className="w-4 h-4" /> },
    { id: 'api-keys', label: 'API密钥', icon: <Key className="w-4 h-4" /> },
    { id: 'model', label: '模型配置', icon: <Brain className="w-4 h-4" /> },
    { id: 'data-retention', label: '数据保留', icon: <Clock className="w-4 h-4" /> },
    { id: 'changelog', label: '更新日志', icon: <FileText className="w-4 h-4" /> },
    { id: 'system', label: '系统设置', icon: <Settings className="w-4 h-4" /> }
  ];

  // 根据用户角色确定显示的 tabs
  const tabs = currentUserRole === 'admin' && userLoaded ? fullTabs : baseTabs;

  // 根据 URL 中的 tab 参数同步当前激活的 Tab（支持旧的 tab=api 兼容）
  useEffect(() => {
    // 等待用户信息加载完成
    if (!userLoaded) return;

    const tabFromUrl = searchParams.get('tab');
    if (!tabFromUrl) return;

    const normalized =
      tabFromUrl === 'api'
        ? 'api-keys'
        : tabFromUrl;

    if (!tabs.some(t => t.id === normalized)) return;

    setActiveTab(normalized);

    // 同步完成后清除 URL 中的 tab 参数（使用 history 避免闪烁）
    if (window.location.search.includes('tab=')) {
      window.history.replaceState({}, '', pathname);
    }
  }, [searchParams, tabs, userLoaded]);

  const handleTabChange = (nextId: string) => {
    setActiveTab(nextId);
    // 不再通过 router 修改 URL，保持纯粹的客户端状态切换
  };

  return (
    <div className="flex flex-col h-full min-h-0" style={{ overflow: 'hidden' }}>
      <div className="flex-shrink-0 pb-0">
        <header className="pb-4">
          <h1 className="text-2xl font-semibold mb-1" style={{ color: 'rgb(var(--theme-text))' }}>设置</h1>
          <p className="text-sm" style={{ color: 'rgb(var(--theme-text-muted))' }}>管理您的账户和系统配置</p>
        </header>

        <div className="border-b" style={{ borderColor: 'rgb(var(--theme-border))' }}>
          <nav className="flex gap-1 overflow-x-auto">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id)}
                className="flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap"
                style={{
                  borderBottomColor: activeTab === tab.id ? 'rgb(var(--theme-primary))' : 'transparent',
                  color: activeTab === tab.id ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-text-muted))',
                }}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, marginTop: 16, overflow: 'hidden' }}>
        {activeTab === 'account' && <AccountTab userInfo={currentUserInfo} userId={currentUserId} lng={resolvedLng} />}
        {activeTab === 'api-keys' && <ApiKeysTab userId={currentUserId} />}
        {activeTab === 'model' && <ModelConfigTab />}
        {activeTab === 'users' && <UsersTab currentUserId={currentUserId} />}
        {activeTab === 'data-retention' && <DataRetentionTab userId={currentUserId} />}
        {activeTab === 'system' && <SystemTab />}
        {activeTab === 'changelog' && <ChangelogTab userRole={currentUserRole} />}
      </div>
    </div>
  );
};

// 用户管理Tab（仅管理员可见）
const UsersTab = ({ currentUserId }: { currentUserId: string }) => {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingUser, setEditingUser] = useState<any>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [saving, setSaving] = useState(false);
  // 分页状态
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const { message: messageApi } = App.useApp();

  const [formData, setFormData] = useState({
    nickname: '',
    email: '',
    role: 'normal' as 'normal' | 'admin',
    status: 'normal' as 'normal' | 'disabled',
    /** 留空则不修改密码 */
    password: ''
  });

  const [addFormData, setAddFormData] = useState({
    username: '',
    password: '',
    nickname: '',
    email: '',
    role: 'normal' as 'normal' | 'admin',
    status: 'normal' as 'normal' | 'disabled'
  });

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await getAllUsers() as any;
      if (res.code === 200 && Array.isArray(res.data)) {
        setUsers(res.data);
      }
    } catch (e) { console.error('获取用户列表失败', e); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchUsers(); }, []);

  const [deleteTarget, setDeleteTarget] = useState<{ id: string; username: string } | null>(null);
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);
  const [tipMessage, setTipMessage] = useState<string | null>(null);

  const formatLastLogin = (dateStr: string | null | undefined) => {
    if (dateStr === null || dateStr === undefined || dateStr === '') return '未登录过系统';
    try {
      const date = new Date(dateStr);
      if (Number.isNaN(date.getTime())) return '未登录过系统';
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return '未登录过系统';
    }
  };

  const openDeleteConfirm = (user: any) => {
    if (user.id === currentUserId) {
      messageApi.warning('不能删除当前登录用户');
      return;
    }
    setDeleteTarget({ id: user.id, username: user.username || '' });
  };

  const executeDelete = async () => {
    if (!deleteTarget) return;
    const idToRemove = deleteTarget.id;
    setDeleteSubmitting(true);
    try {
      const res: any = await deleteUser(idToRemove);
      if (res.code === 200) {
        setUsers((prev) => prev.filter((u) => u.id !== idToRemove));
        setDeleteTarget(null);
        messageApi.success('用户删除成功');
      } else {
        messageApi.error(res.message || '删除用户失败');
      }
    } catch (e) {
      console.error('删除用户失败', e);
      messageApi.error('删除用户失败，请稍后重试');
    } finally {
      setDeleteSubmitting(false);
    }
  };

  const openEdit = (user: any) => {
    setEditingUser(user);
    setFormData({
      nickname: user.nickname || '',
      email: pickEmailFromUser(user),
      role: user.role,
      status: user.status,
      password: ''
    });
    setShowEditModal(true);
  };

  const handleSubmit = async () => {
    if (!editingUser) return;
    setSaving(true);
    try {
      const params: {
        id: string;
        nickname?: string;
        password?: string;
        role?: 'normal' | 'admin';
        status?: 'normal' | 'disabled';
        email?: string;
      } = { id: editingUser.id };

      if (formData.nickname !== (editingUser.nickname ?? '')) {
        params.nickname = formData.nickname;
      }
      const pwd = formData.password.trim();
      if (pwd) {
        if (pwd.length < 6) {
          setTipMessage('新密码至少6个字符');
          setSaving(false);
          return;
        }
        params.password = pwd;
      }
      if (formData.role !== editingUser.role) {
        params.role = formData.role;
      }
      if (formData.status !== editingUser.status) {
        params.status = formData.status;
      }
      const prevEmail = pickEmailFromUser(editingUser);
      const nextEmail = (formData.email ?? '').trim();
      if (nextEmail !== prevEmail) {
        params.email = nextEmail;
      }

      const changedKeys = Object.keys(params).filter((k) => k !== 'id');
      if (changedKeys.length === 0) {
        setShowEditModal(false);
        setEditingUser(null);
        setSaving(false);
        return;
      }

      const res: any = await updateUser(params);
      if (res.code === 200) {
        fetchUsers();
        setShowEditModal(false);
        setEditingUser(null);
        messageApi.success('用户更新成功');
      } else {
        setTipMessage(res.message || '更新用户失败');
      }
    } catch (e) { console.error('更新用户失败', e); setTipMessage('更新用户失败，请稍后重试'); }
    finally { setSaving(false); }
  };

  const handleAddUser = async () => {
    if (!addFormData.username.trim() || !addFormData.password.trim() || !addFormData.nickname.trim()) {
      messageApi.error('请填写必填项');
      return;
    }
    if (addFormData.password.length < 6) {
      messageApi.error('密码至少6个字符');
      return;
    }
    setSaving(true);
    try {
      const res: any = await createUser({
        username: addFormData.username.trim(),
        password: addFormData.password,
        nickname: addFormData.nickname.trim(),
        email: addFormData.email.trim() || undefined,
        role: addFormData.role,
        status: addFormData.status
      });
      if (res.code === 200) {
        fetchUsers();
        setShowAddModal(false);
        setAddFormData({
          username: '',
          password: '',
          nickname: '',
          email: '',
          role: 'normal',
          status: 'normal'
        });
        messageApi.success('用户创建成功');
      } else {
        messageApi.error(res.message || '创建用户失败');
      }
    } catch (e) { console.error('创建用户失败', e); messageApi.error('创建用户失败'); }
    finally { setSaving(false); }
  };

  const openAddModal = () => {
    setAddFormData({
      username: '',
      password: '',
      nickname: '',
      email: '',
      role: 'normal',
      status: 'normal'
    });
    setShowAddModal(true);
  };

  const filteredUsers = users.filter(user =>
    user.username?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    user.nickname?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    pickEmailFromUser(user).toLowerCase().includes(searchQuery.toLowerCase())
  );

  // 搜索时重置到第一页
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

  // 分页后的用户数据
  const totalUsers = filteredUsers.length;
  const totalPages = Math.max(1, Math.ceil(totalUsers / pageSize));
  const paginatedUsers = filteredUsers.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

  // 切换页码时滚动到表格顶部
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    // 滚动到表格区域
    const tableContainer = document.querySelector('.users-table-container');
    if (tableContainer) {
      tableContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  // 重新加载数据时重置页码
  useEffect(() => {
    setCurrentPage(1);
  }, []);

  return (
    <div className="flex flex-col min-h-0 flex-1">
      {/* 固定部分：标题 + 搜索框 */}
      <div className="space-y-4 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>用户管理</h3>
            <p className="text-sm" style={{ color: 'rgb(var(--theme-text-muted))' }}>管理系统用户和权限</p>
          </div>
          <button
            onClick={openAddModal}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-[12px] text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            添加用户
          </button>
        </div>

        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
          <input
            type="text"
            placeholder="搜索用户名、昵称或邮箱..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-12 pr-4 py-3 bg-white border border-slate-200 rounded-[16px] text-sm"
          />
        </div>
      </div>

      {/* 可滚动部分：用户表格（仅此区域滚动） */}
      <div className="flex-1 min-h-0 mt-4 flex flex-col">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
          </div>
        ) : (
          <div className="flex-1 min-h-0 bg-white rounded-[20px] border border-slate-200 overflow-hidden flex flex-col">
            <div className="flex-1 min-h-0 overflow-y-auto users-table-container">
              <table className="w-full">
                <thead className="bg-slate-50 border-b border-slate-200 sticky top-0">
                <tr>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-slate-500">用户名</th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-slate-500">昵称</th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-slate-500">角色</th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-slate-500">状态</th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-slate-500">最后登录</th>
                  <th className="text-right px-6 py-4 text-xs font-semibold text-slate-500">操作</th>
                </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                {paginatedUsers.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                      {searchQuery ? '未找到匹配的用户' : '暂无用户数据'}
                    </td>
                  </tr>
                ) : (
                  paginatedUsers.map(user => {
                    const rowEmail = pickEmailFromUser(user);
                    return (
                      <tr key={user.id} className="hover:bg-slate-50/50">
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div
                              style={{
                                width: 40,
                                height: 40,
                                borderRadius: 12,
                                overflow: 'hidden',
                                flexShrink: 0,
                                background: 'linear-gradient(135deg, #e0e7ff 0%, #ede9fe 100%)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                color: '#4f46e5',
                                fontWeight: 600,
                                fontSize: 14,
                              }}
                            >
                              {user.avatar ? (
                                <img
                                  src={user.avatar}
                                  alt=""
                                  style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 12 }}
                                />
                              ) : (
                                (user.nickname?.[0] || user.username?.[0]?.toUpperCase() || 'U')
                              )}
                            </div>
                            <div className="min-w-0">
                              <p className="font-medium text-slate-900 truncate">{user.username}</p>
                              {rowEmail ? (
                                <p className="text-xs text-slate-500 truncate">{rowEmail}</p>
                              ) : null}
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-sm text-slate-700">{user.nickname || '—'}</td>
                        <td className="px-6 py-4">
                          <span
                            style={
                              user.role === 'admin'
                                ? {
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  padding: '4px 10px',
                                  fontSize: 12,
                                  fontWeight: 600,
                                  borderRadius: 9999,
                                  backgroundColor: '#f3e8ff',
                                  color: '#7c3aed',
                                  border: '1px solid #ddd6fe',
                                }
                                : {
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  padding: '4px 10px',
                                  fontSize: 12,
                                  fontWeight: 600,
                                  borderRadius: 9999,
                                  backgroundColor: '#eff6ff',
                                  color: '#2563eb',
                                  border: '1px solid #bfdbfe',
                                }
                            }
                          >
                            {user.role === 'admin' ? '管理员' : '普通用户'}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <span
                            style={
                              user.status === 'normal'
                                ? {
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  padding: '4px 10px',
                                  fontSize: 12,
                                  fontWeight: 600,
                                  borderRadius: 9999,
                                  backgroundColor: '#ecfdf5',
                                  color: '#059669',
                                  border: '1px solid #a7f3d0',
                                }
                                : {
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  padding: '4px 10px',
                                  fontSize: 12,
                                  fontWeight: 600,
                                  borderRadius: 9999,
                                  backgroundColor: '#fef2f2',
                                  color: '#dc2626',
                                  border: '1px solid #fecaca',
                                }
                            }
                          >
                            {user.status === 'normal' ? '正常' : '禁用'}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-slate-500 whitespace-nowrap">
                          {formatLastLogin(user.login_at)}
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              type="button"
                              onClick={() => openEdit(user)}
                              className="transition-opacity p-1"
                              style={{ background: 'none', border: 'none', cursor: 'pointer' }}
                              title="编辑"
                            >
                              <Edit3 className="h-[18px] w-[18px] text-slate-400 hover:text-indigo-600" />
                            </button>
                            <button
                              type="button"
                              onClick={() => openDeleteConfirm(user)}
                              className="transition-opacity"
                              style={{ background: 'none', border: 'none', cursor: user.id === currentUserId ? 'not-allowed' : 'pointer' }}
                              title="删除"
                              disabled={user.id === currentUserId}
                            >
                              <Trash2
                                className={`h-[18px] w-[18px] ${user.id === currentUserId ? 'text-slate-200' : 'text-slate-400 hover:text-red-500'}`}
                              />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
                </tbody>
              </table>
            </div>
            {/* 分页控件 */}
            {totalUsers > pageSize && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '16px 24px',
                borderTop: '1px solid #e2e8f0',
                backgroundColor: 'white',
                flexShrink: 0
              }}>
                <div style={{ fontSize: 14, color: '#64748b' }}>
                  共 <span style={{ fontWeight: 600, color: '#334155' }}>{totalUsers}</span> 条记录，
                  第 <span style={{ fontWeight: 600, color: '#334155' }}>{currentPage}</span> / {totalPages} 页
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <button
                    onClick={() => handlePageChange(1)}
                    disabled={currentPage === 1}
                    style={{
                      padding: '6px 12px',
                      fontSize: 14,
                      borderRadius: 12,
                      transition: 'all 0.2s',
                      border: 'none',
                      cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
                      backgroundColor: currentPage === 1 ? '#f1f5f9' : '#f1f5f9',
                      color: currentPage === 1 ? '#94a3b8' : '#475569',
                    }}
                  >
                    首页
                  </button>
                  <button
                    onClick={() => handlePageChange(currentPage - 1)}
                    disabled={currentPage === 1}
                    style={{
                      padding: '6px 12px',
                      fontSize: 14,
                      borderRadius: 12,
                      transition: 'all 0.2s',
                      border: 'none',
                      cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
                      backgroundColor: currentPage === 1 ? '#f1f5f9' : '#f1f5f9',
                      color: currentPage === 1 ? '#94a3b8' : '#475569',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    <ChevronLeft style={{ width: 16, height: 16 }} />
                    上一页
                  </button>
                  {/* 页码按钮 */}
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    let pageNum: number;
                    if (totalPages <= 5) {
                      pageNum = i + 1;
                    } else if (currentPage <= 3) {
                      pageNum = i + 1;
                    } else if (currentPage >= totalPages - 2) {
                      pageNum = totalPages - 4 + i;
                    } else {
                      pageNum = currentPage - 2 + i;
                    }
                    return (
                      <button
                        key={pageNum}
                        onClick={() => handlePageChange(pageNum)}
                        style={{
                          padding: '6px 12px',
                          fontSize: 14,
                          borderRadius: 12,
                          transition: 'all 0.2s',
                          border: 'none',
                          cursor: 'pointer',
                          backgroundColor: currentPage === pageNum ? '#4f46e5' : '#f1f5f9',
                          color: currentPage === pageNum ? 'white' : '#475569',
                        }}
                      >
                        {pageNum}
                      </button>
                    );
                  })}
                  <button
                    onClick={() => handlePageChange(currentPage + 1)}
                    disabled={currentPage === totalPages}
                    style={{
                      padding: '6px 12px',
                      fontSize: 14,
                      borderRadius: 12,
                      transition: 'all 0.2s',
                      border: 'none',
                      cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
                      backgroundColor: currentPage === totalPages ? '#f1f5f9' : '#f1f5f9',
                      color: currentPage === totalPages ? '#94a3b8' : '#475569',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    下一页
                    <ChevronRight style={{ width: 16, height: 16 }} />
                  </button>
                  <button
                    onClick={() => handlePageChange(totalPages)}
                    disabled={currentPage === totalPages}
                    style={{
                      padding: '6px 12px',
                      fontSize: 14,
                      borderRadius: 12,
                      transition: 'all 0.2s',
                      border: 'none',
                      cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
                      backgroundColor: currentPage === totalPages ? '#f1f5f9' : '#f1f5f9',
                      color: currentPage === totalPages ? '#94a3b8' : '#475569',
                    }}
                  >
                    末页
                  </button>
                </div>
              </div>
            )}
            {/* 每页显示条数选择 */}
            {totalUsers > 5 && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                gap: 8,
                padding: '12px 24px',
                borderTop: '1px solid #f1f5f9',
                backgroundColor: '#f8fafc',
                flexShrink: 0
              }}>
                <span style={{ fontSize: 14, color: '#64748b' }}>每页显示</span>
                <select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setCurrentPage(1);
                  }}
                  style={{
                    padding: '4px 8px',
                    fontSize: 14,
                    borderRadius: 12,
                    border: '1px solid #e2e8f0',
                    backgroundColor: 'white',
                    color: '#334155',
                    cursor: 'pointer',
                    outline: 'none',
                  }}
                >
                  <option value={5}>5 条</option>
                  <option value={10}>10 条</option>
                  <option value={20}>20 条</option>
                  <option value={50}>50 条</option>
                </select>
              </div>
            )}
          </div>
        )}
      </div>

      {showEditModal && editingUser && typeof document !== 'undefined' && createPortal(
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0 }}>
          <div className="bg-white rounded-[20px] w-full max-w-md p-6 mx-4">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>编辑用户</h3>
              <button onClick={() => setShowEditModal(false)} className="transition-opacity">
                <X className="w-5 h-5 text-slate-400 hover:text-slate-600" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">用户名</label>
                <input type="text" value={editingUser.username} disabled className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm bg-slate-50" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">昵称</label>
                <input type="text" value={formData.nickname} onChange={(e) => setFormData({...formData, nickname: e.target.value})} className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">邮箱</label>
                <input type="email" value={formData.email} onChange={(e) => setFormData({...formData, email: e.target.value})} className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm" placeholder="请输入邮箱" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">新密码（留空则不修改）</label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  placeholder="留空则不修改密码"
                  className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm"
                  autoComplete="new-password"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">角色</label>
                  <select value={formData.role} onChange={(e) => setFormData({...formData, role: e.target.value as 'normal' | 'admin'})} className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm">
                    <option value="normal">普通用户</option>
                    <option value="admin">管理员</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">状态</label>
                  <select value={formData.status} onChange={(e) => setFormData({...formData, status: e.target.value as 'normal' | 'disabled'})} className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm">
                    <option value="normal">正常</option>
                    <option value="disabled">禁用</option>
                  </select>
                </div>
              </div>
              <div className="flex gap-3 pt-4">
                <button onClick={() => setShowEditModal(false)} className="flex-1 py-2.5 border border-slate-200 text-slate-700 rounded-[12px] font-medium">取消</button>
                <button onClick={handleSubmit} disabled={saving} className="flex-1 py-2.5 bg-indigo-600 text-white rounded-[12px] font-medium disabled:opacity-50 flex items-center justify-center gap-2">
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  保存
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}

      {showAddModal && typeof document !== 'undefined' && createPortal(
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0 }}>
          <div className="bg-white rounded-[20px] w-full max-w-md p-6 mx-4">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>添加用户</h3>
              <button onClick={() => setShowAddModal(false)} className="transition-opacity">
                <X className="w-5 h-5 text-slate-400 hover:text-slate-600" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  用户名 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={addFormData.username}
                  onChange={(e) => setAddFormData({...addFormData, username: e.target.value})}
                  placeholder="请输入用户名"
                  className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  昵称 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={addFormData.nickname}
                  onChange={(e) => setAddFormData({...addFormData, nickname: e.target.value})}
                  placeholder="请输入昵称"
                  className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  密码 <span className="text-red-500">*</span>
                </label>
                <input
                  type="password"
                  value={addFormData.password}
                  onChange={(e) => setAddFormData({...addFormData, password: e.target.value})}
                  placeholder="请输入密码（至少6位）"
                  className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">邮箱</label>
                <input
                  type="email"
                  value={addFormData.email}
                  onChange={(e) => setAddFormData({...addFormData, email: e.target.value})}
                  placeholder="请输入邮箱（可选）"
                  className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">角色</label>
                  <select
                    value={addFormData.role}
                    onChange={(e) => setAddFormData({...addFormData, role: e.target.value as 'normal' | 'admin'})}
                    className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm"
                  >
                    <option value="normal">普通用户</option>
                    <option value="admin">管理员</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">状态</label>
                  <select
                    value={addFormData.status}
                    onChange={(e) => setAddFormData({...addFormData, status: e.target.value as 'normal' | 'disabled'})}
                    className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm"
                  >
                    <option value="normal">正常</option>
                    <option value="disabled">禁用</option>
                  </select>
                </div>
              </div>
              <div className="flex gap-3 pt-4">
                <button onClick={() => setShowAddModal(false)} className="flex-1 py-2.5 border border-slate-200 text-slate-700 rounded-[12px] font-medium">取消</button>
                <button
                  onClick={handleAddUser}
                  disabled={saving || !addFormData.username.trim() || !addFormData.password.trim() || !addFormData.nickname.trim()}
                  className="flex-1 py-2.5 bg-indigo-600 text-white rounded-[12px] font-medium disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  添加
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}

      {deleteTarget && typeof document !== 'undefined' && createPortal(
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4"
          style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(15, 23, 42, 0.45)' }}
          role="presentation"
          onClick={() => !deleteSubmitting && setDeleteTarget(null)}
        >
          <div
            className="w-full max-w-md rounded-[20px] p-6 shadow-xl"
            style={{ backgroundColor: 'rgb(var(--theme-bg))', border: '1px solid rgb(var(--theme-border))' }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-user-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start gap-4">
              <AlertCircle className="h-8 w-8 shrink-0" style={{ color: '#dc2626' }} aria-hidden />
              <div className="min-w-0 flex-1">
                <h3 id="delete-user-title" className="text-lg font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>
                  确认删除用户
                </h3>
                <p className="mt-2 text-sm leading-relaxed" style={{ color: 'rgb(var(--theme-text-muted))' }}>
                  确定要删除用户
                  <span className="mx-1 font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>
                    「{deleteTarget.username}」
                  </span>
                  吗？操作不可逆。
                </p>
              </div>
            </div>
            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <button
                type="button"
                disabled={deleteSubmitting}
                onClick={() => !deleteSubmitting && setDeleteTarget(null)}
                className="w-full rounded-[12px] border px-4 py-2.5 text-sm font-medium sm:w-auto"
                style={{
                  borderColor: 'rgb(var(--theme-border))',
                  color: 'rgb(var(--theme-text-secondary))',
                  backgroundColor: 'rgb(var(--theme-bg-secondary))',
                }}
              >
                取消
              </button>
              <button
                type="button"
                disabled={deleteSubmitting}
                onClick={executeDelete}
                className="flex w-full items-center justify-center gap-2 rounded-[12px] px-4 py-2.5 text-sm font-medium text-white sm:w-auto disabled:opacity-60"
                style={{ backgroundColor: '#dc2626' }}
              >
                {deleteSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                确认删除
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {tipMessage && typeof document !== 'undefined' && createPortal(
        (
          <div
            className="fixed inset-0 z-[60] flex items-center justify-center p-4"
            style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(15, 23, 42, 0.45)' }}
            onClick={() => setTipMessage(null)}
            role="presentation"
          >
            <div
              className="w-full max-w-sm rounded-[20px] p-6 shadow-xl"
              style={{ backgroundColor: 'rgb(var(--theme-bg))', border: '1px solid rgb(var(--theme-border))' }}
              onClick={(e) => e.stopPropagation()}
              role="alertdialog"
              aria-modal="true"
              aria-labelledby="user-tip-title"
            >
              <div className="flex items-center gap-3">
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
                  style={{ backgroundColor: 'rgba(99, 102, 241, 0.12)' }}
                >
                  <AlertCircle className="h-5 w-5" style={{ color: 'rgb(var(--theme-primary))' }} />
                </div>
                <h3 id="user-tip-title" className="text-base font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>
                  提示
                </h3>
              </div>
              <p className="mt-4 text-sm leading-relaxed" style={{ color: 'rgb(var(--theme-text-muted))' }}>
                {tipMessage}
              </p>
              <div className="mt-6 flex justify-end">
                <button
                  type="button"
                  onClick={() => setTipMessage(null)}
                  className="rounded-[12px] px-5 py-2.5 text-sm font-medium text-white"
                  style={{ backgroundColor: 'rgb(var(--theme-primary))' }}
                >
                  知道了
                </button>
              </div>
            </div>
          </div>
        ),
        document.body
      )}
    </div>
  );
};

// 账户设置
const AccountTab = ({ userInfo, userId, lng }: { userInfo: any; userId: string; lng?: string }) => {
  const { message: messageApi } = App.useApp();
  const { refreshUserInfo } = useUserInfo();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [formData, setFormData] = useState({
    nickname: '',
    email: '',
    newPassword: '',
    confirmPassword: ''
  });

  useEffect(() => {
    if (userInfo) {
      setFormData(prev => ({
        ...prev,
        nickname: userInfo.nickname || '',
        email: pickEmailFromUser(userInfo)
      }));
    }
    setLoading(false);
  }, [userInfo]);

  const handleSave = async () => {
    if (formData.newPassword && formData.newPassword !== formData.confirmPassword) {
      messageApi.error('两次密码输入不一致');
      return;
    }
    setSaving(true);
    try {
      const newPwd = formData.newPassword?.trim();
      const params: { nickname: string; email?: string; password?: string } = {
        nickname: formData.nickname
      };
      const emailVal = formData.email.trim();
      if (emailVal) params.email = emailVal;
      if (newPwd) {
        if (newPwd.length < 6) {
          messageApi.error('新密码至少6个字符');
          setSaving(false);
          return;
        }
        params.password = newPwd;
      }

      await editUser(params);

      // 成功后清空密码字段
      setFormData(prev => ({ ...prev, newPassword: '', confirmPassword: '' }));
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);

      // 如果修改了密码，强制重新登录
      if (newPwd) {
        setLoggingOut(true);
        localStorage.removeItem('userInfo');
        localStorage.removeItem('console_token');
        document.cookie = 'console_token=; path=/; max-age=0';
        resetGlobalUserInfo();
        messageApi.success('密码已修改，请重新登录');
        setTimeout(() => {
          const resolvedLng = lng ?? 'zh-CN';
          window.location.href = `/${resolvedLng}/login`;
        }, 800);
        return;
      }

      messageApi.success('保存成功');
      await refreshUserInfo();
    } catch (e) {
      console.error('更新用户信息失败', e);
      messageApi.error('保存失败，请稍后重试');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
      </div>
    );
  }

  // 生成随机渐变色头像
  const getAvatarGradient = () => {
    const gradients = [
      'from-indigo-500 via-purple-500 to-pink-500',
      'from-blue-500 via-cyan-500 to-teal-500',
      'from-orange-500 via-red-500 to-pink-500',
      'from-green-500 via-emerald-500 to-cyan-500',
      'from-violet-500 via-fuchsia-500 to-rose-500',
      'from-amber-500 via-orange-500 to-red-500',
    ];
    const index = userInfo?.nickname?.charCodeAt(0) % gradients.length || 0;
    return gradients[index];
  };

  return (
    <div className="space-y-6">
      {/* 个人信息卡片 - 紧凑版 */}
      <div className="rounded-[16px] border p-4" style={{
        background: 'linear-gradient(to bottom right, rgb(var(--theme-bg-secondary)), rgb(var(--theme-bg)))',
        borderColor: 'rgb(var(--theme-border))'
      }}>
        <div className="flex items-center gap-4">
          {/* 头像 - 使用内联样式确保圆角 */}
          <div
            style={{ borderRadius: '50%' }}
            className={`w-14 h-14 bg-gradient-to-br ${getAvatarGradient()} flex items-center justify-center text-white text-xl font-bold shadow-md flex-shrink-0`}
          >
            {userInfo?.nickname?.[0] || userInfo?.username?.[0]?.toUpperCase() || 'U'}
          </div>

          {/* 用户信息 */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-lg font-semibold truncate" style={{ color: 'rgb(var(--theme-text))' }}>{userInfo?.nickname || userInfo?.username}</h3>
              {/* 角色标签 - 使用内联样式确保圆角 */}
              <span
                style={{ borderRadius: '12px' }}
                className={`px-2 py-0.5 text-xs font-medium flex-shrink-0 ${
                  userInfo?.role === 'admin'
                    ? 'bg-purple-100 text-purple-600 border border-purple-200'
                    : ''
                }`}
                {...(userInfo?.role !== 'admin' ? { style: { borderRadius: '12px', backgroundColor: 'rgb(var(--theme-bg-tertiary))', color: 'rgb(var(--theme-text-secondary))', border: '1px solid rgb(var(--theme-border))' } } : {})}
              >
                {userInfo?.role === 'admin' ? '管理员' : '普通用户'}
              </span>
            </div>
            <p className="text-sm truncate" style={{ color: 'rgb(var(--theme-text-muted))' }}>{pickEmailFromUser(userInfo) || '未设置邮箱'}</p>
          </div>
        </div>
      </div>

      {/* 基本信息编辑 */}
      <div className="rounded-[20px] border p-6 space-y-6" style={{
        backgroundColor: 'rgb(var(--theme-bg))',
        borderColor: 'rgb(var(--theme-border))'
      }}>
        <div className="flex items-center gap-2 pb-4 border-b border-slate-200 dark:border-slate-600/60">
          <User className="w-5 h-5" style={{ color: 'rgb(var(--theme-primary))' }} />
          <h4 className="font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>基本信息</h4>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: 'rgb(var(--theme-text-secondary))' }}>昵称</label>
            <input
              type="text"
              value={formData.nickname}
              onChange={(e) => setFormData({...formData, nickname: e.target.value})}
              className="w-full px-4 py-2.5 border rounded-[12px] text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors outline-none"
              placeholder="请输入昵称"
              style={{
                outline: 'none',
                backgroundColor: 'rgb(var(--theme-bg-secondary))',
                borderColor: 'rgb(var(--theme-border))',
                color: 'rgb(var(--theme-text))'
              }}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: 'rgb(var(--theme-text-secondary))' }}>邮箱</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({...formData, email: e.target.value})}
              className="w-full px-4 py-2.5 border rounded-[12px] text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors outline-none"
              placeholder="请输入邮箱"
              style={{
                outline: 'none',
                backgroundColor: 'rgb(var(--theme-bg-secondary))',
                borderColor: 'rgb(var(--theme-border))',
                color: 'rgb(var(--theme-text))'
              }}
            />
          </div>
        </div>
      </div>

      {/* 修改密码 */}
      <div className="rounded-[20px] border p-6 space-y-6" style={{
        backgroundColor: 'rgb(var(--theme-bg))',
        borderColor: 'rgb(var(--theme-border))'
      }}>
        <div className="flex items-center gap-2 pb-4 border-b border-slate-200 dark:border-slate-600/60">
          <Key className="w-5 h-5" style={{ color: 'rgb(var(--theme-primary))' }} />
          <h4 className="font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>修改密码</h4>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: 'rgb(var(--theme-text-secondary))' }}>新密码</label>
            <input
              type="password"
              value={formData.newPassword}
              onChange={(e) => setFormData({...formData, newPassword: e.target.value})}
              className="w-full px-4 py-2.5 border rounded-[12px] text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors outline-none"
              placeholder="请输入新密码"
              style={{
                outline: 'none',
                backgroundColor: 'rgb(var(--theme-bg-secondary))',
                borderColor: 'rgb(var(--theme-border))',
                color: 'rgb(var(--theme-text))'
              }}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: 'rgb(var(--theme-text-secondary))' }}>确认新密码</label>
            <input
              type="password"
              value={formData.confirmPassword}
              onChange={(e) => setFormData({...formData, confirmPassword: e.target.value})}
              className="w-full px-4 py-2.5 border rounded-[12px] text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors outline-none"
              placeholder="请再次输入新密码"
              style={{
                outline: 'none',
                backgroundColor: 'rgb(var(--theme-bg-secondary))',
                borderColor: 'rgb(var(--theme-border))',
                color: 'rgb(var(--theme-text))'
              }}
            />
          </div>
        </div>
      </div>

      <div className="flex items-center justify-end gap-3 pt-2">
        {saved && (
          <span className="flex items-center gap-2 text-green-600 text-sm">
            <CheckCircle className="w-4 h-4" />
            保存成功
          </span>
        )}
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-[12px] font-medium hover:from-indigo-700 hover:to-purple-700 disabled:opacity-50 transition-all shadow-md hover:shadow-lg"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          保存修改
        </button>
      </div>
    </div>
  );
};

// API密钥
const ApiKeysTab = ({ userId }: { userId: string }) => {
  const [apiKeys, setApiKeys] = useState<ApiKeyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showKey, setShowKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newApiKeyExpiresAt, setNewApiKeyExpiresAt] = useState<string>('');
  const [newApiKey, setNewApiKey] = useState<{ id: string; api_key: string } | null>(null);
  const { message: messageApi } = App.useApp();

  const fetchApiKeys = async (showLoading = true) => {
    if (!userId) return;
    if (showLoading) setLoading(true);
    else setRefreshing(true);
    try {
      const res = await getApiKeysByUserId(userId);
      if (res.code === 200 && Array.isArray(res.data)) {
        setApiKeys(res.data);
      }
    } catch (e) {
      console.error('获取API密钥失败', e);
      messageApi.error('获取 API Key 列表失败');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { fetchApiKeys(); }, [userId]);

  const handleCreate = async () => {
    if (!newKeyName.trim() || !userId) {
      messageApi.error('请输入 API Key 名称');
      return;
    }
    setCreating(true);
    try {
      const payload: any = {
        user_id: userId,
        name: newKeyName.trim(),
      };
      if (newApiKeyExpiresAt) {
        payload.expires_at = dayjs(newApiKeyExpiresAt).endOf('day').utcOffset(8).format();
      }
      const res = await createApiKey(payload);
      if (res.code === 200 && res.data) {
        messageApi.success('API Key 创建成功');
        setNewApiKey(res.data);
        fetchApiKeys();
      } else {
        messageApi.error(res.msg || res.message || 'API Key 创建失败');
      }
    } catch (e) {
      console.error('创建API密钥失败', e);
      messageApi.error('创建失败，请稍后重试');
    } finally {
      setCreating(false);
    }
  };

  const setQuickExpiry = (days: number | null) => {
    if (days === null) {
      setNewApiKeyExpiresAt('');
    } else {
      setNewApiKeyExpiresAt(dayjs().add(days, 'day').format('YYYY-MM-DD'));
    }
  };

  const closeCreateModal = () => {
    setShowCreateModal(false);
    setNewApiKey(null);
    setNewKeyName('');
    setNewApiKeyExpiresAt('');
  };

  const { modal } = App.useApp();

  const handleDelete = (id: string) => {
    modal.confirm({
      title: '确认删除',
      content: '确定要删除这个API密钥吗？',
      okText: '确定',
      cancelText: '取消',
      okButtonProps: { danger: true },
      centered: true,
      onOk: async () => {
        try {
          const res = await deleteApiKey({ id });
          if (res.code === 200) fetchApiKeys();
        } catch (e) { console.error('删除API密钥失败', e); }
      }
    });
  };

  const handleToggleStatus = async (key: ApiKeyItem) => {
    try {
      const res = await updateApiKey({
        id: key.id,
        status: key.status === 'active' ? 'disabled' : 'active'
      });
      if (res.code === 200) {
        fetchApiKeys();
        messageApi.success(key.status === 'active' ? '已禁用 API Key' : '已启用 API Key');
      }
    } catch (e) { console.error('更新状态失败', e); }
  };

  const copyToClipboard = (key: string, name: string) => {
    navigator.clipboard.writeText(key);
    setCopiedKey(key);
    messageApi.success(`API Key 已复制到剪贴板`);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>API 密钥</h3>
          <p className="text-sm" style={{ color: 'rgb(var(--theme-text-muted))' }}>管理用于外部集成的API密钥</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => fetchApiKeys(false)}
            disabled={refreshing}
            className="flex items-center gap-2 px-3 py-2 border border-slate-200 text-slate-600 rounded-[10px] text-sm font-medium hover:bg-slate-50 transition-colors disabled:opacity-50"
            title="刷新列表"
          >
            <Loader2 className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            刷新
          </button>
          <button
            onClick={() => { setShowCreateModal(true); setNewKeyName(''); setNewApiKey(null); setNewApiKeyExpiresAt(''); }}
            className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-4 py-2 rounded-[12px] text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            创建密钥
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-12 gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
          <span className="text-sm text-slate-500">正在加载 API Key 列表...</span>
        </div>
      ) : apiKeys.length === 0 ? (
        <div className="bg-white rounded-[20px] border border-slate-200 p-12 text-center">
          <Key className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <h4 className="text-lg font-semibold text-slate-900 mb-2">暂无API密钥</h4>
          <p className="text-sm text-slate-500 mb-6">创建您的第一个API密钥以开始集成</p>
        </div>
      ) : (
        <div className="space-y-3">
          {apiKeys.map(key => (
            <div key={key.id} className="bg-white rounded-[16px] border border-slate-200 p-5 hover:border-slate-300 transition-colors">
              {/* 顶部：名称和操作 */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <h4 className="font-semibold text-slate-900">{key.name}</h4>
                  {key.status === 'active' ? (
                    <span style={{ padding: '2px 8px', borderRadius: '9999px', backgroundColor: '#f0fdf4', color: '#16a34a', fontSize: '12px', fontWeight: 500 }}>启用中</span>
                  ) : (
                    <span style={{ padding: '2px 8px', borderRadius: '9999px', backgroundColor: '#f1f5f9', color: '#64748b', fontSize: '12px', fontWeight: 500 }}>已禁用</span>
                  )}
                  {key.expires_at && dayjs(key.expires_at).isBefore(dayjs()) && (
                    <span style={{ padding: '2px 8px', borderRadius: '9999px', backgroundColor: '#fef2f2', color: '#dc2626', fontSize: '12px', fontWeight: 500 }}>已过期</span>
                  )}
                </div>
                <div className="flex items-center gap-4">
                  <Switch
                    checked={key.status === 'active'}
                    onChange={() => handleToggleStatus(key)}
                    size="small"
                  />
                  <button
                    onClick={() => handleDelete(key.id)}
                    className="transition-opacity"
                    title="删除"
                  >
                    <Trash2 className="w-[18px] h-[18px] text-slate-400 hover:text-red-500" />
                  </button>
                </div>
              </div>

              {/* API Key 显示 */}
              <div className="bg-slate-50 rounded-[10px] px-4 py-2.5 mb-4 flex items-center justify-between">
                <code className="text-sm font-mono text-slate-600">
                  {key.api_key.length > 8
                    ? `${key.api_key.slice(0, 4)}${'*'.repeat(key.api_key.length - 8)}${key.api_key.slice(-4)}`
                    : '*'.repeat(key.api_key.length)}
                </code>
                <button
                  onClick={() => copyToClipboard(key.api_key, key.name)}
                  className="transition-opacity"
                  title="复制"
                >
                  {copiedKey === key.id
                    ? <Check className="w-[18px] h-[18px] text-green-500" />
                    : <Copy className="w-[18px] h-[18px] text-slate-400 hover:text-indigo-600" />
                  }
                </button>
              </div>

              {/* 底部信息 */}
              <div className="flex items-center gap-4 text-xs text-slate-500">
                <div className="flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v3.586L7.707 9.293a1 1 0 00-1.414 1.414l3 3a1 1 0 001.414 0l3-3a1 1 0 00-1.414-1.414L11 10.586V7z" clipRule="evenodd" />
                  </svg>
                  <span>最近使用:</span>
                  <span className="font-medium text-slate-700">{key.last_used_at ? dayjs(key.last_used_at).fromNow() : '从未'}</span>
                </div>
                <span className="text-slate-300">|</span>
                <div className="flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z" clipRule="evenodd" />
                  </svg>
                  <span>创建:</span>
                  <span className="font-medium text-slate-700">{key.created_at ? dayjs(key.created_at).format('YYYY-MM-DD') : '--'}</span>
                </div>
                <span className="text-slate-300">|</span>
                <div className="flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5 text-indigo-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                  </svg>
                  <span>过期:</span>
                  <span className="font-medium text-slate-700">{key.expires_at ? dayjs(key.expires_at).format('YYYY-MM-DD') : '永不'}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreateModal && createPortal(
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999]" style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0 }}>
          <div className="bg-white rounded-[20px] w-full max-w-xl p-6 mx-4">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>创建API密钥</h3>
              <button onClick={closeCreateModal} className="transition-opacity">
                <X className="w-5 h-5 text-slate-400 hover:text-slate-600" />
              </button>
            </div>

            {newApiKey ? (
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <div style={{ width: 40, height: 40, borderRadius: '50%', backgroundColor: '#22c55e', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <CheckCircle className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <p className="text-base font-medium text-green-700">API Key 创建成功！</p>
                    <p className="text-xs text-slate-500 mt-0.5">请妥善保存以下密钥，关闭后将无法再次查看完整内容</p>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">您的 API Key</label>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 bg-slate-50 px-4 py-3 border border-slate-200 rounded-[10px] break-all">
                      <code className="text-sm font-mono text-slate-700">{newApiKey.api_key}</code>
                    </div>
                    <button
                      onClick={() => copyToClipboard(newApiKey.api_key, 'API Key')}
                      className="transition-opacity flex-shrink-0"
                      title="复制"
                    >
                      <Copy className="w-4 h-4 text-slate-400 hover:text-indigo-600" />
                    </button>
                  </div>
                </div>
                <button onClick={closeCreateModal} className="w-full py-2.5 bg-indigo-600 text-white rounded-[12px] font-medium hover:bg-indigo-700 transition-colors">
                  我已保存，关闭
                </button>
              </div>
            ) : (
              <div className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    密钥名称 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    placeholder="例如：生产环境密钥"
                    maxLength={128}
                    className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    过期时间 <span className="text-xs text-slate-400 font-normal">(需大于今天，不填则默认永不过期)</span>
                  </label>
                  <input
                    type="date"
                    value={newApiKeyExpiresAt}
                    onChange={(e) => setNewApiKeyExpiresAt(e.target.value)}
                    min={dayjs().format('YYYY-MM-DD')}
                    className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />

                  {/* 快捷选择 */}
                  <div className="flex flex-wrap gap-2 mt-3">
                    <span className="text-xs text-slate-500 self-center">快捷选择：</span>
                    {[
                      { label: '3天', days: 3 },
                      { label: '7天', days: 7 },
                      { label: '30天', days: 30 },
                      { label: '90天', days: 90 },
                      { label: '1年', days: 365 },
                    ].map((item) => (
                      <button
                        key={item.label}
                        type="button"
                        onClick={() => setQuickExpiry(item.days)}
                        className="px-3 py-1 text-xs font-medium bg-gradient-to-r from-blue-50 to-indigo-50 text-indigo-600 border border-indigo-200 hover:shadow-sm hover:from-blue-100 hover:to-indigo-100 transition-all rounded-[6px]"
                      >
                        {item.label}
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={() => setQuickExpiry(null)}
                      className="px-3 py-1 text-xs font-medium bg-gradient-to-r from-purple-50 to-pink-50 text-purple-600 border border-purple-200 hover:shadow-sm hover:from-purple-100 hover:to-pink-100 transition-all rounded-[6px]"
                    >
                      永不过期
                    </button>
                  </div>
                </div>

                <div className="bg-amber-50 border border-amber-200 rounded-[12px] p-4 flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-amber-800">安全提醒</p>
                    <p className="text-xs text-amber-700 mt-1">密钥创建后只能查看一次，请妥善保存</p>
                  </div>
                </div>

                <div className="flex gap-3 pt-2">
                  <button onClick={closeCreateModal} className="flex-1 py-2.5 border border-slate-200 text-slate-700 rounded-[12px] font-medium hover:bg-slate-50 transition-colors">
                    取消
                  </button>
                  <button
                    onClick={handleCreate}
                    disabled={!newKeyName.trim() || creating}
                    className="flex-1 py-2.5 bg-indigo-600 text-white rounded-[12px] font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 hover:bg-indigo-700 transition-colors"
                  >
                    {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    创建
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};

// 模型配置（仅管理员可见）
const MODEL_CLASS_META: { key: ModelClassType; label: string; description: string }[] = [
  { key: 'base', label: '基础对话模型', description: '负责自然语言对话、问答或智能助理等通用文本生成能力。' },
  { key: 'embedding', label: '向量化嵌入模型', description: '用于文本向量化、语义检索及知识库问答等场景。' },
  { key: 'rerank', label: '重排序模型', description: '对召回结果进行语义打分与排序，提升检索精度。' },
];

const ModelConfigTab = () => {
  const [models, setModels] = useState<ModelConfigItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingModel, setEditingModel] = useState<ModelConfigItem | null>(null);
  const [addingModelClass, setAddingModelClass] = useState<ModelClassType | null>(null);
  const [saving, setSaving] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const { modal, message: messageApi } = App.useApp();

  const [formData, setFormData] = useState({
    model_type: '',
    model_name: '',
    model_api_key: '',
    url: '',
    model_class: 'base' as ModelClassType
  });

  const fetchModels = async () => {
    setLoading(true);
    try {
      const res = await getModelConfigs();
      if (res.code === 200 && Array.isArray(res.data)) {
        setModels(res.data);
      } else {
        messageApi.error(res?.msg || res?.message || '获取模型配置失败');
      }
    } catch (e) {
      console.error('获取模型配置失败', e);
      messageApi.error('获取模型配置失败，请稍后重试');
    } finally {
      setLoading(false);
    }
    return true;
  };

  useEffect(() => { fetchModels(); }, []);

  const groupedByClass = useMemo(() => {
    const map: Record<ModelClassType, ModelConfigItem[]> = { base: [], embedding: [], rerank: [] };
    models.forEach(m => {
      if (map[m.model_class]) map[m.model_class].push(m);
    });
    return map;
  }, [models]);

  const hasAllThree = useMemo(() => {
    return MODEL_CLASS_META.every(meta => (groupedByClass[meta.key]?.length ?? 0) > 0);
  }, [groupedByClass]);

  const openAddModal = (modelClass: ModelClassType) => {
    setAddingModelClass(modelClass);
    setEditingModel(null);
    setFormData({
      model_type: '',
      model_name: '',
      model_api_key: '',
      url: '',
      model_class: modelClass
    });
    setShowApiKey(false);
    setShowCreateModal(true);
  };

  const openEdit = (model: ModelConfigItem) => {
    // 从最新 models 列表中查找，避免使用闭包捕获的旧数据
    const latest = models.find(m => m.id === model.id);
    const target = latest || model;
    setEditingModel(target);
    setAddingModelClass(null);
    setFormData({
      model_type: target.model_type,
      model_name: target.model_name,
      model_api_key: target.model_api_key,
      url: target.url,
      model_class: target.model_class
    });
    setShowApiKey(false);
    setShowCreateModal(true);
  };

  const closeModal = () => {
    setShowCreateModal(false);
    setEditingModel(null);
    setAddingModelClass(null);
    setFormData({ model_type: '', model_name: '', model_api_key: '', url: '', model_class: 'base' });
  };

  const getModalTitle = () => {
    if (editingModel) return '编辑模型';
    const meta = MODEL_CLASS_META.find(m => m.key === formData.model_class);
    return meta ? `新增${meta.label}` : '添加模型';
  };

  const validateUrl = (url: string) => {
    if (!url.trim()) return false;
    try {
      new URL(url.trim());
      return true;
    } catch { return false; }
  };

  const handleSubmit = async () => {
    if (!formData.model_name.trim()) {
      messageApi.error('请输入模型名称');
      return;
    }
    if (!formData.url.trim()) {
      messageApi.error('请输入接口地址 URL');
      return;
    }
    if (!validateUrl(formData.url)) {
      messageApi.error('请输入合法的 URL 地址');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        model_name: formData.model_name.trim(),
        model_type: formData.model_type.trim() || 'gpt-4',
        model_api_key: formData.model_api_key.trim(),
        url: formData.url.trim(),
        model_class: formData.model_class
      };
      if (editingModel) {
        const res = await updateModelConfig({ id: editingModel.id, ...payload });
        if (res.code === 200) {
          messageApi.success('模型配置更新成功');
          await fetchModels();
          closeModal();
        } else {
          messageApi.error(res.msg || res.message || '更新失败');
        }
      } else {
        const res = await createModelConfig(payload);
        if (res.code === 200) {
          messageApi.success('模型配置创建成功');
          await fetchModels();
          closeModal();
        } else {
          messageApi.error(res.msg || res.message || '创建失败');
        }
      }
    } catch (e) {
      console.error('保存模型配置失败', e);
      messageApi.error('保存失败，请稍后重试');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = (id: string) => {
    modal.confirm({
      title: '确认删除',
      content: '确定要删除这个模型配置吗？',
      okText: '确定',
      cancelText: '取消',
      okButtonProps: { danger: true },
      centered: true,
      onOk: async () => {
        try {
          const res = await deleteModelConfig({ id });
          if (res.code === 200) {
            messageApi.success('删除成功');
            fetchModels();
          } else {
            messageApi.error(res.msg || res.message || '删除失败');
          }
        } catch (e) { console.error('删除失败', e); }
      }
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>模型配置</h3>
          <p className="text-sm" style={{ color: 'rgb(var(--theme-text-muted))' }}>配置基础对话、向量化嵌入与重排序模型，需三种类型各一个</p>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-12 gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
          <span className="text-sm text-slate-500">正在加载模型配置...</span>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {MODEL_CLASS_META.map(meta => {
              const list = groupedByClass[meta.key] || [];
              const hasConfig = list.length > 0;
              const canAdd = !hasConfig;
              return (
                <div
                  key={meta.key}
                  className="rounded-[16px] border p-5 transition-shadow"
                  style={{
                    borderColor: hasConfig ? 'rgb(var(--theme-border))' : 'rgba(148, 163, 184, 0.4)',
                    backgroundColor: 'rgb(var(--theme-bg))'
                  }}
                >
                  <div className="flex items-start justify-between mb-3">
                    <h4 className="font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>{meta.label}</h4>
                    {hasConfig ? (
                      <span style={{ padding: '2px 8px', borderRadius: '9999px', fontSize: '12px', fontWeight: 500, backgroundColor: '#dcfce7', color: '#16a34a' }}>已配置</span>
                    ) : (
                      <span style={{ padding: '2px 8px', borderRadius: '9999px', fontSize: '12px', fontWeight: 500, backgroundColor: '#fef2f2', color: '#dc2626' }}>未配置</span>
                    )}
                  </div>
                  <p className="text-xs mb-4" style={{ color: 'rgb(var(--theme-text-muted))' }}>{meta.description}</p>
                  {hasConfig ? (
                    <div className="space-y-3">
                      {list.map(model => (
                        <div key={model.id} className="rounded-[12px] border p-4" style={{ borderColor: 'rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg-secondary))' }}>
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p className="font-medium truncate" style={{ color: 'rgb(var(--theme-text))' }}>{model.model_name}</p>
                              <p className="text-xs mt-1" style={{ color: 'rgb(var(--theme-text-secondary))' }}>{model.model_type || '—'}</p>
                              <div className="flex items-center gap-2 mt-2 text-xs" style={{ color: 'rgb(var(--theme-text-muted))' }}>
                                <Plug className="w-3.5 h-3.5 flex-shrink-0" />
                                <span className="truncate">{model.url || '—'}</span>
                              </div>
                            </div>
                            <div className="flex items-center gap-1 flex-shrink-0">
                              <button onClick={() => openEdit(model)} className="transition-opacity p-1" title="编辑"><Edit3 className="w-[18px] h-[18px]" style={{ color: 'rgb(var(--theme-text-muted))' }} /></button>
                              <button onClick={() => handleDelete(model.id)} className="transition-opacity p-1" title="删除"><Trash2 className="w-[18px] h-[18px]" style={{ color: 'rgb(var(--theme-text-muted))' }} /></button>
                            </div>
                          </div>
                          {model.updated_at && (
                            <div className="flex items-center gap-1.5 mt-2 pt-2 text-xs border-t" style={{ borderColor: 'rgb(var(--theme-border))', color: 'rgb(var(--theme-text-muted))' }}>
                              <Clock className="w-3 h-3" />
                              <span>最近更新：{new Date(model.updated_at).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <button
                      onClick={() => openAddModal(meta.key)}
                      className="w-full flex items-center justify-center gap-2 py-3 border border-dashed rounded-[12px] text-sm font-medium transition-colors"
                      style={{ borderColor: 'rgb(var(--theme-border))', color: 'rgb(var(--theme-text-muted))' }}
                    >
                      <Plus className="w-4 h-4" />
                      添加配置
                    </button>
                  )}
                </div>
              );
            })}
          </div>

          {!hasAllThree && (
            <p className="text-sm" style={{ color: 'rgb(var(--theme-text-muted))' }}>
              当前缺少：{MODEL_CLASS_META.filter(m => (groupedByClass[m.key]?.length ?? 0) === 0).map(m => m.label).join('、')}，请为对应类型添加至少一个配置。
            </p>
          )}
        </>
      )}

      {showCreateModal && createPortal(
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999]" style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0 }}>
          <div className="bg-white rounded-[20px] w-full max-w-lg p-6 mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>{getModalTitle()}</h3>
              <button onClick={closeModal} className="transition-opacity"><X className="w-5 h-5 text-slate-400 hover:text-slate-600" /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">模型类别（便于识别，如 DeepSeek、通义千问、豆包）</label>
                <input
                  type="text"
                  value={formData.model_type}
                  onChange={(e) => setFormData({ ...formData, model_type: e.target.value })}
                  placeholder="例如：豆包、千问、GPT-4o"
                  maxLength={64}
                  className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2"><span className="text-red-500">*</span> 模型名称（唯一标识）</label>
                <input
                  type="text"
                  value={formData.model_name}
                  onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
                  placeholder="例如：qwen3.7-max"
                  maxLength={128}
                  className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">API Key</label>
                <div className="relative">
                  <input
                    type={showApiKey ? 'text' : 'password'}
                    value={formData.model_api_key}
                    onChange={(e) => setFormData({ ...formData, model_api_key: e.target.value })}
                    placeholder="请粘贴完整的 API Key"
                    maxLength={256}
                    className="w-full px-4 py-2.5 pr-10 border border-slate-200 rounded-[12px] text-sm"
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    title={showApiKey ? '隐藏' : '显示'}
                  >
                    {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2"><span className="text-red-500">*</span> 接口地址 URL</label>
                <input
                  type="text"
                  value={formData.url}
                  onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                  placeholder="例如：https://api.example.com/v1/chat/completions"
                  className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm"
                />
              </div>
              <div className="flex gap-3 pt-4">
                <button onClick={closeModal} className="flex-1 py-2.5 border border-slate-200 text-slate-700 rounded-[12px] font-medium">取消</button>
                <button
                  onClick={handleSubmit}
                  disabled={saving || !formData.model_name.trim() || !formData.url.trim()}
                  className="flex-1 py-2.5 bg-indigo-600 text-white rounded-[12px] font-medium disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  保存配置
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};

// 系统设置
const SystemTab = () => {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // 主题状态
  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('light');
  const [pageSize, setPageSize] = useState('20');
  const [language, setLanguage] = useState('zh-CN');

  // 应用主题
  const applyTheme = (newTheme: 'light' | 'dark' | 'system') => {
    const root = document.documentElement;

    if (newTheme === 'system') {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      root.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
    } else {
      root.setAttribute('data-theme', newTheme);
    }
  };

  // 切换主题
  const handleThemeChange = (newTheme: 'light' | 'dark' | 'system') => {
    setTheme(newTheme);
    localStorage.setItem('onticards-theme', newTheme);
    applyTheme(newTheme);
  };

  // 加载保存的设置
  useEffect(() => {
    const savedTheme = localStorage.getItem('onticards-theme') as 'light' | 'dark' | 'system' | null;
    const savedPageSize = localStorage.getItem('onticards-pagesize');
    const savedLanguage = localStorage.getItem('onticards-language');

    // 应用保存的主题
    if (savedTheme) {
      setTheme(savedTheme);
      applyTheme(savedTheme);
    }

    if (savedPageSize) setPageSize(savedPageSize);
    if (savedLanguage) setLanguage(savedLanguage);
  }, []);

  const handleSave = async () => {
    // 保存到 localStorage
    localStorage.setItem('onticards-pagesize', pageSize);
    localStorage.setItem('onticards-language', language);

    setSaving(true);
    setTimeout(() => {
      setSaving(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }, 500);
  };

  const themeOptions = [
    { value: 'light', label: '浅色', icon: <Sun className="w-4 h-4" /> },
    { value: 'dark', label: '深色', icon: <Moon className="w-4 h-4" /> },
    { value: 'system', label: '跟随系统', icon: <Monitor className="w-4 h-4" /> },
  ];

  return (
    <div className="space-y-6">
      <div className="rounded-[20px] border p-6 space-y-6" style={{
        backgroundColor: 'rgb(var(--theme-bg))',
        borderColor: 'rgb(var(--theme-border))'
      }}>
        {/* 语言与外观 - 紧凑版 */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Palette className="w-5 h-5" style={{ color: 'rgb(var(--theme-primary))' }} />
            <h3 className="text-lg font-semibold" style={{ color: 'rgb(var(--theme-text))' }}>语言与外观</h3>
          </div>

          {/* 主题选择 - 紧凑横向排列 */}
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2" style={{ color: 'rgb(var(--theme-text-secondary))' }}>主题模式</label>
            <div className="flex gap-2">
              {themeOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => handleThemeChange(option.value as 'light' | 'dark' | 'system')}
                  style={{ borderRadius: '8px' }}
                  className={`flex items-center gap-2 px-4 py-2 border-2 transition-all ${
                    theme === option.value
                      ? ''
                      : ''
                  }`}
                  {...(theme === option.value
                      ? { style: { borderRadius: '8px', borderColor: 'rgb(var(--theme-primary))', backgroundColor: 'rgba(var(--theme-primary), 0.1)', color: 'rgb(var(--theme-primary))' } }
                      : { style: { borderRadius: '8px', borderColor: 'rgb(var(--theme-border))', color: 'rgb(var(--theme-text-secondary))' } }
                  )}
                >
                  {option.icon}
                  <span className="text-sm font-medium">{option.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* 界面语言 */}
          {/* <div className="flex items-center gap-4">
            <div className="flex-1 max-w-xs">
              <label className="block text-sm font-medium mb-2" style={{ color: 'rgb(var(--theme-text-secondary))' }}>界面语言</label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full px-4 py-2.5 border rounded-[12px] text-sm"
                style={{
                  backgroundColor: 'rgb(var(--theme-bg-secondary))',
                  borderColor: 'rgb(var(--theme-border))',
                  color: 'rgb(var(--theme-text))'
                }}
              >
                <option value="zh-CN">简体中文</option>
                <option value="zh-HK">繁體中文</option>
                <option value="en">English</option>
              </select>
            </div>
            <div className="flex-1 max-w-xs">
              <label className="block text-sm font-medium mb-2" style={{ color: 'rgb(var(--theme-text-secondary))' }}>每页显示</label>
              <select
                value={pageSize}
                onChange={(e) => setPageSize(e.target.value)}
                className="w-full px-4 py-2.5 border rounded-[12px] text-sm"
                style={{
                  backgroundColor: 'rgb(var(--theme-bg-secondary))',
                  borderColor: 'rgb(var(--theme-border))',
                  color: 'rgb(var(--theme-text))'
                }}
              >
                <option value="10">10 条</option>
                <option value="20">20 条</option>
                <option value="50">50 条</option>
                <option value="100">100 条</option>
              </select>
            </div>
          </div> */}
        </div>

        <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-200 dark:border-slate-600/60">
          {saved && (
            <span className="flex items-center gap-2 text-green-600 text-sm">
              <CheckCircle className="w-4 h-4" />
              保存成功
            </span>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 text-white rounded-[12px] font-medium hover:bg-indigo-700 disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            保存设置
          </button>
        </div>
      </div>
    </div>
  );
};

// 更新日志
const { TextArea } = Input;

const ChangelogTab = ({ userRole }: { userRole: string }) => {
  const isAdmin = userRole === 'admin';
  const { modal, message: messageApi } = App.useApp();
  const [logs, setLogs] = useState<ChangelogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLog, setSelectedLog] = useState<ChangelogItem | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');
  const [editingLog, setEditingLog] = useState<ChangelogItem | null>(null);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [previewContent, setPreviewContent] = useState('');
  const watchContentMd = Form.useWatch('content_md', form);
  useEffect(() => {
    if (modalOpen && watchContentMd !== undefined) setPreviewContent(watchContentMd);
  }, [modalOpen, watchContentMd]);

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const res = await getChangelog();
      if (res.code === 200 && Array.isArray(res.data)) {
        setLogs(res.data);
        if (res.data.length > 0 && !selectedLog) setSelectedLog(res.data[0]);
      }
    } catch (e) { console.error('获取更新日志失败', e); }
    finally { setLoading(false); }
  };

  const filteredLogs = logs.filter(log =>
    log.version?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    log.title?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' });
  };

  const formatVersion = (version: string) => {
    if (!version) return '';
    return /^v/i.test(version.trim()) ? version.trim() : `v${version.trim()}`;
  };

  const getDefaultTemplate = () => {
    const today = new Date();
    const dateStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    return `## 🆕 v1.x.x 版本更新日志（${dateStr}）

### ✨ 新功能
- 
---
### ⚙️ 功能优化 / 调整
- 
---
### 🐛 问题修复
- 
---
### 🧩 兼容性与依赖
- 
---
### 📘 注意事项
- 
`;
  };

  const handleOpenCreate = () => {
    setModalMode('create');
    setEditingLog(null);
    setPreviewContent(getDefaultTemplate());
    form.resetFields();
    setTimeout(() => {
      form.setFieldsValue({ content_md: getDefaultTemplate(), status: 'public' });
    }, 0);
    setModalOpen(true);
  };

  const handleOpenEdit = (log: ChangelogItem) => {
    setModalMode('edit');
    setEditingLog(log);
    setPreviewContent(log.content_md);
    form.resetFields();
    setTimeout(() => {
      form.setFieldsValue({
        version: log.version,
        title: log.title,
        content_md: log.content_md,
        status: log.status,
      });
    }, 0);
    setModalOpen(true);
  };

  const handleDeleteChangelog = (id: number) => {
    modal.confirm({
      title: '确认删除',
      content: '确定要删除这条版本日志吗？',
      okText: '确定',
      cancelText: '取消',
      okButtonProps: { danger: true },
      centered: true,
      onOk: async () => {
        try {
          const res = await deleteChangelog(id);
          if (res.code === 200) {
            messageApi.success('删除成功');
            if (selectedLog?.id === id) setSelectedLog(null);
            await fetchLogs();
            notifyChangelogChanged();
          } else {
            messageApi.error(res.msg || '删除失败');
          }
        } catch (e) { console.error('删除版本日志失败', e); }
      }
    });
  };


  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      if (modalMode === 'create') {
        const res = await createChangelog({ version: values.version, title: values.title, content_md: values.content_md, status: values.status || 'hidden' });
        if (res.code === 200) {
          messageApi.success('创建成功');
          setModalOpen(false);
          await fetchLogs();
          notifyChangelogChanged();
        } else {
          messageApi.error(res.msg || '创建失败');
        }
      } else if (editingLog) {
        const res = await updateChangelog(editingLog.id, { version: values.version, title: values.title, content_md: values.content_md, status: values.status });
        if (res.code === 200) {
          messageApi.success('更新成功');
          setModalOpen(false);
          await fetchLogs();
          notifyChangelogChanged();
          if (selectedLog?.id === editingLog.id) {
            const updated = logs.find(l => l.id === editingLog.id);
            if (updated) setSelectedLog({ ...updated, ...values });
          }
        } else {
          messageApi.error(res.msg || '更新失败');
        }
      }
    } catch (e: any) {
      if (!e.errorFields) {
        console.error('保存失败', e);
        messageApi.error('保存失败，请稍后重试');
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div id="changelog-tab-container" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflow: 'hidden' }}>
      {/* 工具栏：搜索 + 新增按钮（仅管理员可见） */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0, marginBottom: 16 }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 pointer-events-none" />
          <input
            type="text"
            placeholder="搜索版本号或标题..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-12 pr-4 py-2.5 bg-white border border-slate-200 rounded-[12px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-300 transition-all"
          />
        </div>
        {isAdmin && (
          <button
            onClick={handleOpenCreate}
            className="flex items-center gap-2 px-4 py-2.5 text-white text-sm font-medium rounded-[12px] flex-shrink-0 transition-all hover:opacity-90 active:scale-95"
            style={{ background: 'linear-gradient(to right, #6366f1, #a855f7)' }}
          >
            <Plus className="w-4 h-4" />
            新增日志
          </button>
        )}
      </div>

      {/* 主体：左右分栏，固定高度，各自内部滚动 */}
      <div style={{ display: 'flex', flexDirection: 'row', gap: 20, height: 'calc(100vh - 280px)', minHeight: 0 }}>
        {/* 左侧版本列表 */}
        <div style={{ display: 'flex', flexDirection: 'column', width: '33.333333%', height: '100%' }}>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              flex: 1,
              minHeight: 0,
              overflow: 'hidden',
              backgroundColor: 'rgb(var(--theme-bg))',
              borderRadius: 16,
              border: '1px solid rgb(var(--theme-border))',
            }}
          >
            <div style={{ padding: '16px 16px 12px', borderBottom: '1px solid rgb(var(--theme-border))', flexShrink: 0 }}>
              <p className="text-xs font-medium uppercase tracking-wider" style={{ color: 'rgb(var(--theme-text-muted))' }}>版本列表</p>
              <p className="text-xs mt-0.5" style={{ color: 'rgb(var(--theme-text-muted))' }}>{filteredLogs.length} 条记录</p>
            </div>
            <div className="version-list-scroll" style={{ flex: 1, overflowY: 'auto', padding: '12px 12px 24px', minHeight: 0 }}>
              {loading ? (
                <div className="flex items-center justify-center py-10">
                  <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
                </div>
              ) : filteredLogs.length === 0 ? (
                <div className="text-center py-10">
                  <FileText className="w-10 h-10 mx-auto mb-2" style={{ color: 'rgb(var(--theme-text-muted))' }} />
                  <p className="text-sm" style={{ color: 'rgb(var(--theme-text-muted))' }}>暂无更新日志</p>
                </div>
              ) : filteredLogs.map(log => (
                <button
                  key={log.id}
                  onClick={() => setSelectedLog(log)}
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    padding: 14,
                    marginBottom: 8,
                    borderRadius: 12,
                    border: '1px solid',
                    transition: 'all 0.2s',
                    backgroundColor: selectedLog?.id === log.id ? 'rgba(var(--theme-primary), 0.12)' : 'rgb(var(--theme-bg-secondary))',
                    borderColor: selectedLog?.id === log.id ? 'rgba(var(--theme-primary), 0.5)' : 'rgb(var(--theme-border))',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span
                      style={{
                        borderRadius: 9999,
                        background: 'linear-gradient(to right, #6366f1, #a855f7)',
                        color: 'white',
                        fontSize: 12,
                        fontWeight: 500,
                        padding: '2px 8px',
                      }}
                    >
                      {formatVersion(log.version)}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      {log.status === 'public' && (
                        <span style={{ borderRadius: 6, padding: '2px 8px', fontSize: 11, fontWeight: 500, backgroundColor: '#dcfce7', color: '#15803d', border: '1px solid #86efac' }}>
                          公开
                        </span>
                      )}
                      {log.status === 'hidden' && (
                        <span style={{ borderRadius: 6, padding: '2px 8px', fontSize: 11, fontWeight: 500, backgroundColor: '#fef3c7', color: '#b45309', border: '1px solid #fcd34d' }}>
                          隐藏
                        </span>
                      )}
                    </span>
                  </div>
                  <h4 style={{ fontWeight: 500, fontSize: 14, marginBottom: 4, color: 'rgb(var(--theme-text))', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', lineHeight: 1.4 }}>{log.title}</h4>
                  <p style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))' }}>{formatDate(log.created_at)}</p>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 右侧详情 */}
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, height: '100%' }}>
          {selectedLog ? (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                flex: 1,
                minHeight: 0,
                overflow: 'hidden',
                padding: 24,
                backgroundColor: 'rgb(var(--theme-bg))',
                borderRadius: 20,
                border: '1px solid rgb(var(--theme-border))',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexShrink: 0 }}>
                <span
                  style={{
                    borderRadius: 9999,
                    background: 'linear-gradient(to right, #6366f1, #a855f7)',
                    color: 'white',
                    fontSize: 14,
                    fontWeight: 500,
                    padding: '6px 12px',
                  }}
                >
                  {formatVersion(selectedLog.version)}
                </span>
                <span style={{ fontSize: 14, color: 'rgb(var(--theme-text-muted))' }}>{formatDate(selectedLog.created_at)}</span>
                {isAdmin && (
                  <>
                    <button
                      onClick={() => handleOpenEdit(selectedLog)}
                      style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', fontSize: 12, fontWeight: 500, background: 'transparent', color: 'rgb(var(--theme-text-secondary))', borderRadius: 8, cursor: 'pointer' }}
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                      编辑
                    </button>
                    <button
                      onClick={() => handleDeleteChangelog(selectedLog.id)}
                      style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', fontSize: 12, fontWeight: 500, background: 'transparent', color: 'rgb(var(--theme-text-muted))', borderRadius: 8, cursor: 'pointer' }}
                      title="删除"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </>
                )}
              </div>
              <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 16, flexShrink: 0, color: 'rgb(var(--theme-text))' }}>{selectedLog.title}</h2>
              <div className="version-detail-scroll" style={{ flex: 1, minHeight: 0, overflowY: 'auto', paddingRight: 8, color: 'rgb(var(--theme-text-secondary))' }}>
                <ReactMarkdown content={selectedLog.content_md} />
              </div>
            </div>
          ) : (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                flex: 1,
                minHeight: 0,
                overflow: 'hidden',
                padding: 48,
                backgroundColor: 'rgb(var(--theme-bg))',
                borderRadius: 20,
                border: '1px solid rgb(var(--theme-border))',
              }}
            >
              <FileText className="w-16 h-16 mb-4 flex-shrink-0" style={{ color: 'rgb(var(--theme-text-muted))' }} />
              <p style={{ fontSize: 14, color: 'rgb(var(--theme-text-muted))' }}>选择左侧版本查看详情</p>
            </div>
          )}
        </div>
      </div>

      {/* 新增/编辑版本日志弹框 - 不透明白底 + 加宽，与背景明显分离 */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-5"
          style={{
            backgroundColor: 'rgba(15,23,42,0.5)',
            backdropFilter: 'blur(8px)',
          }}
        >
          <div
            className="w-full flex flex-col overflow-hidden"
            style={{
              maxWidth: 1200,
              maxHeight: '92vh',
              backgroundColor: 'rgb(var(--theme-bg))',
              border: '1px solid rgb(var(--theme-border))',
              borderRadius: 20,
              boxShadow: '0 0 0 1px rgba(0,0,0,0.03), 0 2px 4px rgba(0,0,0,0.05), 0 12px 24px rgba(0,0,0,0.1), 0 24px 48px rgba(0,0,0,0.12)',
            }}
          >
            {/* 头部 */}
            <div
              className="flex-shrink-0 px-6 py-5 flex items-center justify-between"
              style={{
                borderBottom: '1px solid rgb(var(--theme-border))',
                background: 'linear-gradient(180deg, rgba(99,102,241,0.06) 0%, transparent 100%)',
              }}
            >
              <div className="flex items-center gap-4">
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 14,
                    background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <FileText className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h3 style={{ fontSize: 18, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>
                    {modalMode === 'create' ? '新增版本日志' : '编辑版本日志'}
                  </h3>
                  <p style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))', marginTop: 4 }}>
                    {modalMode === 'create' ? '填写版本号、标题与 Markdown，右侧实时预览' : '修改后保存即可'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 12,
                  border: 'none',
                  background: 'rgb(var(--theme-bg-tertiary))',
                  color: 'rgb(var(--theme-text-muted))',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <Form form={form} layout="vertical" className="flex-1 flex flex-col min-h-0 overflow-hidden">
              <div className="flex-1 overflow-y-auto px-6 py-4" style={{ minHeight: 0 }}>
                {/* 版本号、状态、标题三列一行 */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 160px 1fr', gap: 16, marginBottom: 16 }}>
                  <Form.Item
                    label={<span style={{ fontSize: 13, fontWeight: 500, color: '#475569', marginBottom: 4, display: 'block' }}>版本号</span>}
                    name="version"
                    rules={[{ required: true, message: '请输入版本号' }]}
                  >
                    <Input
                      placeholder="例如 v1.4.0"
                      style={{ height: 38, borderRadius: 10, border: '1px solid #e2e8f0', fontSize: 13 }}
                    />
                  </Form.Item>
                  <Form.Item
                    label={<span style={{ fontSize: 13, fontWeight: 500, color: '#475569', marginBottom: 4, display: 'block' }}>状态</span>}
                    name="status"
                    initialValue="public"
                    rules={[{ required: true, message: '请选择状态' }]}
                  >
                    <Select
                      style={{ height: 38, borderRadius: 10, fontSize: 13 }}
                      options={[
                        { value: 'public', label: '公开' },
                        { value: 'hidden', label: '隐藏' },
                      ]}
                    />
                  </Form.Item>
                  <Form.Item
                    label={<span style={{ fontSize: 13, fontWeight: 500, color: '#475569', marginBottom: 4, display: 'block' }}>标题</span>}
                    name="title"
                    rules={[{ required: true, message: '请输入标题' }]}
                  >
                    <Input
                      placeholder="例如 新增数据源管理功能"
                      style={{ height: 38, borderRadius: 10, border: '1px solid #e2e8f0', fontSize: 13 }}
                    />
                  </Form.Item>
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: '#475569', marginBottom: 8 }}>更新内容（Markdown，新增时已填充预设）</div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                    <div>
                      <span style={{ fontSize: 12, fontWeight: 500, color: '#64748b', marginBottom: 8, display: 'block' }}>编辑</span>
                      <Form.Item name="content_md" rules={[{ required: true, message: '请输入更新内容' }]} noStyle>
                        <TextArea
                          placeholder="支持 Markdown..."
                          className="font-mono text-sm"
                          style={{ height: 480, resize: 'none', borderRadius: 12, border: '1px solid #e2e8f0', fontSize: 13 }}
                        />
                      </Form.Item>
                    </div>
                    <div>
                      <span style={{ fontSize: 12, fontWeight: 500, color: '#64748b', marginBottom: 8, display: 'block' }}>预览</span>
                      <div
                        style={{
                          height: 480,
                          overflowY: 'auto',
                          borderRadius: 12,
                          border: '1px solid rgb(var(--theme-border))',
                          backgroundColor: 'rgb(var(--theme-bg-secondary))',
                          padding: '12px 16px',
                        }}
                      >
                        {previewContent ? (
                          <div
                            className="changelog-prose"
                            style={{
                              color: 'rgb(var(--theme-text-secondary))',
                              fontSize: 12,
                              lineHeight: 1.7,
                            }}
                          >
                            <ReactMarkdown
                              content={previewContent}
                              className="!text-[12px]"
                            />
                          </div>
                        ) : (
                          <p style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))', textAlign: 'center', paddingTop: 48 }}>左侧输入后实时预览</p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div
                className="flex-shrink-0 px-6 py-4 flex justify-end gap-3"
                style={{
                  borderTop: '1px solid rgb(var(--theme-border))',
                  backgroundColor: 'rgb(var(--theme-bg-secondary))',
                }}
              >
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  style={{
                    padding: '10px 20px',
                    borderRadius: 12,
                    fontSize: 14,
                    fontWeight: 500,
                    border: '1px solid rgb(var(--theme-border))',
                    background: 'rgb(var(--theme-bg))',
                    color: 'rgb(var(--theme-text-muted))',
                    cursor: 'pointer',
                  }}
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  style={{
                    padding: '10px 24px',
                    borderRadius: 12,
                    fontSize: 14,
                    fontWeight: 500,
                    border: 'none',
                    background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                    color: '#fff',
                    cursor: saving ? 'not-allowed' : 'pointer',
                    opacity: saving ? 0.7 : 1,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  保存
                </button>
              </div>
            </Form>
          </div>
        </div>
      )}
    </div>
  );
};

// 数据保留Tab
const DataRetentionTab = ({ userId }: { userId: string }) => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dataRetention, setDataRetention] = useState<DataRetentionConfig | null>(null);
  const [retentionForm, setRetentionForm] = useState<UpdateDataRetentionParams>({});
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const { message: messageApi } = App.useApp();

  const fetchDataRetention = async () => {
    setLoading(true);
    try {
      const res = await getDataRetention(userId);
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
  };

  useEffect(() => {
    fetchDataRetention();
  }, [userId]);

  const handleSaveDataRetention = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const res = await updateDataRetention({ ...retentionForm, user_id: userId });
      if (res.code === 200) {
        setMessage({ type: 'success', text: res.data.message || '数据保留配置更新成功' });
        fetchDataRetention();
        messageApi.success(res.data.message || '数据保留配置更新成功');
      } else {
        setMessage({ type: 'error', text: res.message || '更新失败' });
        messageApi.error(res.message || '更新失败');
      }
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.message || '更新失败' });
      messageApi.error(e?.message || '更新失败');
    } finally {
      setSaving(false);
    }
  };

  const retentionItems = dataRetention ? [
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
  ] : [];

  const handleChange = (key: keyof UpdateDataRetentionParams, value: string) => {
    const parsed = parseInt(value);
    setRetentionForm({ ...retentionForm, [key]: isNaN(parsed) ? undefined : parsed });
  };

  const hasChanges = dataRetention && retentionItems.some(item => {
    const formValue = retentionForm[item.key];
    const currentValue = parseInt(dataRetention[item.key].value);
    return formValue !== currentValue;
  });

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300 }}>
        <Loader2 className="w-6 h-6 animate-spin" style={{ color: 'rgb(var(--theme-primary))' }} />
      </div>
    );
  }

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: '0 4px' }}>
      <div style={{
        background: 'rgb(var(--theme-card-bg))',
        borderRadius: 20,
        border: '1px solid rgb(var(--theme-border))',
        padding: 24,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
          <div>
            <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 4, color: 'rgb(var(--theme-text))' }}>数据保留策略</h3>
            <p style={{ fontSize: 14, color: 'rgb(var(--theme-text-muted))' }}>
              配置历史数据的保留天数，超期数据将自动清理
            </p>
            {dataRetention?.scope && (
              <p style={{ fontSize: 12, color: 'rgb(var(--theme-primary))', marginTop: 8 }}>
                当前配置层级：{dataRetention.scope === 'system' ? '系统级' : '用户自定义'}
              </p>
            )}
          </div>
          <button
            onClick={handleSaveDataRetention}
            disabled={saving || !hasChanges}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '10px 20px',
              borderRadius: 12,
              fontSize: 14,
              fontWeight: 500,
              border: 'none',
              background: saving || !hasChanges ? 'rgb(var(--theme-border))' : 'rgb(var(--theme-primary))',
              color: saving || !hasChanges ? 'rgb(var(--theme-text-muted))' : '#fff',
              cursor: saving || !hasChanges ? 'not-allowed' : 'pointer',
              opacity: saving ? 0.7 : 1,
            }}
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            保存配置
          </button>
        </div>

        <div style={{
          background: 'rgba(245, 158, 11, 0.1)',
          border: '1px solid rgba(245, 158, 11, 0.3)',
          borderRadius: 12,
          padding: 16,
          display: 'flex',
          alignItems: 'flex-start',
          gap: 12,
          marginBottom: 24,
        }}>
          <AlertCircle className="w-5 h-5 flex-shrink-0" style={{ color: 'rgb(245, 158, 11)', marginTop: 2 }} />
          <div>
            <p style={{ fontSize: 14, fontWeight: 500, color: 'rgb(217, 119, 6)' }}>重要提示</p>
            <p style={{ fontSize: 12, color: 'rgb(217, 119, 6)', marginTop: 4, opacity: 0.8 }}>
              减少保留天数可能导致历史数据丢失，请谨慎操作。建议保留至少90天以支持趋势分析。
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {retentionItems.map(item => (
            <div key={item.key} style={{
              background: 'rgb(var(--theme-bg-secondary))',
              borderRadius: 16,
              padding: 24,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div>
                  <h4 style={{ fontSize: 14, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>{item.label}</h4>
                  <p style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))', marginTop: 4 }}>{item.description}</p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))' }}>
                    当前: {item.current}{item.unit}
                  </span>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <input
                  type="range"
                  min={item.min}
                  max={item.max}
                  value={retentionForm[item.key] || parseInt(item.current)}
                  onChange={(e) => handleChange(item.key, e.target.value)}
                  style={{
                    flex: 1,
                    height: 8,
                    background: 'rgb(var(--theme-border))',
                    borderRadius: 4,
                    cursor: 'pointer',
                    accentColor: 'rgb(var(--theme-primary))',
                  }}
                />
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: 128 }}>
                  <input
                    type="number"
                    min={item.min}
                    max={item.max}
                    value={retentionForm[item.key] || parseInt(item.current)}
                    onChange={(e) => handleChange(item.key, e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: 10,
                      fontSize: 14,
                      textAlign: 'center',
                      border: '1px solid rgb(var(--theme-border))',
                      background: 'rgb(var(--theme-bg))',
                      color: 'rgb(var(--theme-text))',
                      outline: 'none',
                    }}
                  />
                  <span style={{ fontSize: 14, color: 'rgb(var(--theme-text-muted))' }}>{item.unit}</span>
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 12, color: 'rgb(var(--theme-text-muted))' }}>
                <span>{item.min}天</span>
                <span>{item.max}天</span>
              </div>
              {/* 快捷选项 */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 16 }}>
                <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))' }}>快捷设置:</span>
                {[30, 90, 180, 365, 730].map(days => (
                  <button
                    key={days}
                    onClick={() => handleChange(item.key, String(days))}
                    style={{
                      padding: '4px 8px',
                      borderRadius: 6,
                      fontSize: 12,
                      border: (retentionForm[item.key] || parseInt(item.current)) === days
                        ? 'none'
                        : '1px solid rgb(var(--theme-border))',
                      background: (retentionForm[item.key] || parseInt(item.current)) === days
                        ? 'rgba(99, 102, 241, 0.1)'
                        : 'transparent',
                      color: (retentionForm[item.key] || parseInt(item.current)) === days
                        ? 'rgb(var(--theme-primary))'
                        : 'rgb(var(--theme-text-muted))',
                      cursor: 'pointer',
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
};

export default SettingsPage;
