import { get, post, put, del } from '@/api/base';
/**
 *
 * 获取用户信息
 * @export
 */
export function getUserInfo() {
  return get('/user')
}

/**
 *
 * 退出
 * @export
 */
export function logout() {
  return get('/logout')
}

/**
 *
 * 修改用户信息（当前用户）
 * @export
 */
export function editUser(params: {
  nickname?: string
  avatar?: string
  email?: string
  password?: string
}) {
  const { nickname = '', avatar = '', email, password } = params
  const body: Record<string, string> = { nickname, avatar }
  if (email !== undefined) body.email = email
  if (password !== undefined) body.password = password
  return put('/user', { body })
}

/**
 *
 * 修改用户密码
 * @param {type} params
 */
export function personalPasswordReset(params: { old_password: string; new_password: string; id: string }) {
  const { old_password, new_password, id } = params
  return post('/change_password', { body: { old_password, new_password, id } })
}

/**
 *
 * 登录
 * @export
 * @param {{ username: string; password:string }} body
 * @return {*}
 */
export function login(body: { username: string; password: string }): Promise<{ data: { token: string }; code: number; message: string }> {
  const { username, password } = body
  return post('/login', { body: { username, password } })
}

/**
 *
 * 获取所有用户
 * @export
 */
export function getAllUsers() {
  return get('/users/all')
}

/**
 *
 * 新增用户
 * @export
 * @param {object} params - 用户信息参数
 */
export function createUser(params: {
  username: string
  password: string
  nickname?: string
  email?: string
  role?: 'normal' | 'admin'
  status?: 'normal' | 'disabled'
  user_group_id?: string
  avatar?: string
}) {
  return post('/users/manage', { body: params })
}

/**
 *
 * 修改用户信息
 * @export
 * @param {object} params - 用户信息参数
 */
export function updateUser(params: {
  id: string
  nickname?: string
  password?: string
  status?: 'normal' | 'disabled'
  role?: 'normal' | 'admin'
  email?: string
}): Promise<{ code: number; data?: any; msg?: string }> {
  return put('/users/manage', { body: params })
}

/**
 *
 * 删除用户
 * @export
 * @param {string} id - 用户ID
 */
export function deleteUser(id: string): Promise<{ code: number; data?: any; msg?: string }> {
  return del('/users/manage', { body: { id } })
}