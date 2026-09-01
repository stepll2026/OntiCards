'use client';

import { useState, useEffect } from 'react';
import {
  Users,
  Plus,
  Search,
  Edit3,
  Trash2,
  Loader2,
  X,
  Save,
  Shield,
  UserCheck,
  UserX,
} from 'lucide-react';
import { getAllUsers, createUser, updateUser, deleteUser } from '@/api/user';
import { useUserInfo } from '@/hooks';

interface User {
  id: string;
  username: string;
  nickname?: string;
  email?: string;
  role: 'normal' | 'admin';
  status: 'normal' | 'disabled';
  avatar?: string;
  created_at?: string;
}

const UsersPage = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [saving, setSaving] = useState(false);
  const { userInfo } = useUserInfo();
  const currentUserId = userInfo?.id || '';

  const [formData, setFormData] = useState({
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
    } catch (e) {
      console.error('获取用户列表失败', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleSubmit = async () => {
    if (!formData.username.trim()) return;
    setSaving(true);
    try {
      let res;
      if (editingUser) {
        const updateData: any = { id: editingUser.id };
        if (formData.nickname) updateData.nickname = formData.nickname;
        if (formData.status) updateData.status = formData.status;
        if (formData.password) updateData.password = formData.password;
        res = await updateUser(updateData);
      } else {
        res = await createUser(formData);
      }
      if (res.code === 200) {
        fetchUsers();
        setShowCreateModal(false);
        setEditingUser(null);
        resetForm();
      }
    } catch (e) {
      console.error('保存用户失败', e);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (id === currentUserId) {
      alert('不能删除当前登录用户');
      return;
    }
    if (!confirm('确定删除这个用户吗？此操作不可逆。')) return;
    try {
      const res = await deleteUser(id);
      if (res.code === 200) {
        fetchUsers();
      }
    } catch (e) {
      console.error('删除用户失败', e);
    }
  };

  const handleToggleStatus = async (user: User) => {
    if (user.id === currentUserId) {
      alert('不能修改当前登录用户的状态');
      return;
    }
    try {
      const res = await updateUser({ id: user.id, status: user.status === 'normal' ? 'disabled' : 'normal' });
      if (res.code === 200) {
        fetchUsers();
      }
    } catch (e) {
      console.error('修改用户状态失败', e);
    }
  };

  const openEdit = (user: User) => {
    setEditingUser(user);
    setFormData({
      username: user.username,
      password: '',
      nickname: user.nickname || '',
      email: user.email || '',
      role: user.role,
      status: user.status
    });
    setShowCreateModal(true);
  };

  const resetForm = () => {
    setFormData({
      username: '',
      password: '',
      nickname: '',
      email: '',
      role: 'normal',
      status: 'normal'
    });
  };

  const filteredUsers = users.filter(user =>
    user.username?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    user.nickname?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    user.email?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold mb-1 text-slate-900">用户管理</h1>
          <p className="text-sm text-slate-500">管理系统用户和权限</p>
        </div>
        <button
          onClick={() => { setShowCreateModal(true); setEditingUser(null); resetForm(); }}
          className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-5 py-2.5 rounded-[12px] text-sm font-medium hover:from-blue-700 hover:to-indigo-700"
        >
          <Plus className="w-4 h-4" />
          添加用户
        </button>
      </header>

      {/* 搜索 */}
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
        <input
          type="text"
          placeholder="搜索用户名、昵称或邮箱..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-12 pr-4 py-3 bg-white border border-slate-200 rounded-[16px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
        />
      </div>

      {/* 用户列表 */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
        </div>
      ) : filteredUsers.length === 0 ? (
        <div className="bg-white rounded-[20px] border border-slate-200 p-12 text-center">
          <Users className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-slate-900 mb-2">暂无用户</h3>
          <p className="text-sm text-slate-500 mb-6">添加您的第一个用户以开始管理</p>
          <button onClick={() => setShowCreateModal(true)} className="inline-flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-[12px] text-sm font-medium">
            <Plus className="w-4 h-4" />添加用户
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-[20px] border border-slate-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-6 py-4 text-xs font-semibold text-slate-500">用户</th>
                <th className="text-left px-6 py-4 text-xs font-semibold text-slate-500">用户名</th>
                <th className="text-left px-6 py-4 text-xs font-semibold text-slate-500">角色</th>
                <th className="text-left px-6 py-4 text-xs font-semibold text-slate-500">状态</th>
                <th className="text-left px-6 py-4 text-xs font-semibold text-slate-500">创建时间</th>
                <th className="text-right px-6 py-4 text-xs font-semibold text-slate-500">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredUsers.map(user => (
                <tr key={user.id} className="hover:bg-slate-50/50">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center text-indigo-600 font-medium">
                        {user.nickname?.[0] || user.username?.[0]?.toUpperCase() || 'U'}
                      </div>
                      <div>
                        <p className="font-medium text-slate-900">{user.nickname || '-'}</p>
                        <p className="text-xs text-slate-500">{user.email || '-'}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">{user.username}</td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${
                      user.role === 'admin' ? 'bg-purple-50 text-purple-600 border border-purple-200' : 'bg-slate-100 text-slate-600'
                    }`}>
                      {user.role === 'admin' && <Shield className="w-3 h-3" />}
                      {user.role === 'admin' ? '管理员' : '普通用户'}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() => handleToggleStatus(user)}
                      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${
                        user.status === 'normal'
                          ? 'bg-green-50 text-green-600 border border-green-200'
                          : 'bg-red-50 text-red-600 border border-red-200'
                      }`}
                    >
                      {user.status === 'normal' ? <UserCheck className="w-3 h-3" /> : <UserX className="w-3 h-3" />}
                      {user.status === 'normal' ? '正常' : '禁用'}
                    </button>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-500">
                    {user.created_at ? new Date(user.created_at).toLocaleDateString('zh-CN') : '-'}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => openEdit(user)} className="p-2 hover:bg-slate-100 rounded-lg" title="编辑">
                        <Edit3 className="w-4 h-4 text-slate-400" />
                      </button>
                      <button
                        onClick={() => handleDelete(user.id)}
                        className="p-2 hover:bg-red-50 rounded-lg"
                        title="删除"
                        disabled={user.id === currentUserId}
                      >
                        <Trash2 className={`w-4 h-4 ${user.id === currentUserId ? 'text-slate-200' : 'text-slate-400 hover:text-red-500'}`} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 创建/编辑弹窗 */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-[20px] w-full max-w-lg p-6 mx-4">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold">{editingUser ? '编辑用户' : '添加用户'}</h3>
              <button onClick={() => { setShowCreateModal(false); setEditingUser(null); }} className="p-2 hover:bg-slate-100 rounded-lg">
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">用户名 <span className="text-red-500">*</span></label>
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) => setFormData({...formData, username: e.target.value})}
                  disabled={!!editingUser}
                  placeholder="请输入用户名"
                  className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm disabled:bg-slate-50 disabled:text-slate-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  密码 {editingUser && <span className="text-slate-400 text-xs">(留空则不修改)</span>}
                </label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({...formData, password: e.target.value})}
                  placeholder={editingUser ? '留空不修改密码' : '请输入密码'}
                  className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">昵称</label>
                <input
                  type="text"
                  value={formData.nickname}
                  onChange={(e) => setFormData({...formData, nickname: e.target.value})}
                  placeholder="请输入昵称"
                  className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">邮箱</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({...formData, email: e.target.value})}
                  placeholder="请输入邮箱"
                  className="w-full px-4 py-2.5 border border-slate-200 rounded-[12xl] text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">角色</label>
                  <select
                    value={formData.role}
                    onChange={(e) => setFormData({...formData, role: e.target.value as 'normal' | 'admin'})}
                    className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm"
                  >
                    <option value="normal">普通用户</option>
                    <option value="admin">管理员</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">状态</label>
                  <select
                    value={formData.status}
                    onChange={(e) => setFormData({...formData, status: e.target.value as 'normal' | 'disabled'})}
                    className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm"
                  >
                    <option value="normal">正常</option>
                    <option value="disabled">禁用</option>
                  </select>
                </div>
              </div>
              <div className="flex gap-3 pt-4">
                <button
                  onClick={() => { setShowCreateModal(false); setEditingUser(null); }}
                  className="flex-1 py-2.5 border border-slate-200 text-slate-700 rounded-[12px] font-medium hover:bg-slate-50"
                >
                  取消
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={saving || (!editingUser && !formData.username.trim())}
                  className="flex-1 py-2.5 bg-indigo-600 text-white rounded-[12px] font-medium hover:bg-indigo-700 disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  保存
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UsersPage;
