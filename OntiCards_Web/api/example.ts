// 获取登录信息
import { get, put } from '@/api/base'

export const getUserInfo = () => {
  return get('/user')
}

// 退出登录
export const logout = () => {
  return get('/logout')
}

// 修改用户信息
export const updateUserInfo = (params: any) => {
  return put('/user', { body: params })
}
