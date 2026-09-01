import { createContext } from 'use-context-selector'
import type React from 'react'

export type UserInfoType = {
  id: string
  /** 用户名 */
  username: string
  /** 全名 */
  nickname: string
  /** 用户头像 */
  avatar: string
  /** 所属用户组 */
  user_group_name: string
  /** 手机号 */
  tel: string
  /** 角色 */
  role: 'normal' | 'admin'
  /** 默认语言 */
  default_lang?: string
}

export type ChangelogItem = {
  id: number
  version: string
  title: string
  content_md: string
  status: 'public' | 'hidden'
  created_at: string
  updated_at: string
}

type IHomeConfiguration = {
  userInfo?: UserInfoType
  setUserInfo?: (userInfo: any | React.SetStateAction<any>) => void
  isMobile?: boolean
  setIsMobile?: (isMobile: boolean | React.SetStateAction<boolean>) => void
  scrollRef: HTMLDivElement | null
  firstSendingData?: any
  setFirstSendingData?: (firstSendingData: any) => void
  showLogin?: boolean
  setShowLogin: (showLogin: boolean | React.SetStateAction<boolean>) => void
  changelogList?: ChangelogItem[]
  setChangelogList?: (changelogList: ChangelogItem[] | React.SetStateAction<ChangelogItem[]>) => void
  changelogLoading?: boolean
  setChangelogLoading?: (loading: boolean | React.SetStateAction<boolean>) => void
  hasUnreadChangelog?: boolean
  setHasUnreadChangelog?: (hasUnread: boolean | React.SetStateAction<boolean>) => void
  markChangelogAsRead?: () => void
}

const HomeContext = createContext<IHomeConfiguration>({
  userInfo: {} as UserInfoType,
  setUserInfo: () => {},
  isMobile: false,
  setIsMobile: () => {},
  scrollRef: null,
  firstSendingData: null,
  setFirstSendingData: () => {},
  showLogin: false,
  setShowLogin: () => {},
  changelogList: [],
  setChangelogList: () => {},
  changelogLoading: false,
  setChangelogLoading: () => {},
  hasUnreadChangelog: false,
  setHasUnreadChangelog: () => {},
  markChangelogAsRead: () => {},
})

export default HomeContext
