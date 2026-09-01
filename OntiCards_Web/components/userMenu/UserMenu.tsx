'use client'
import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next-nprogress-bar'
import { usePathname } from 'next/navigation'
import { logout } from '@/api/user'
import { setLoggingOut } from '@/api/base'
import { resetGlobalUserInfo } from '@/hooks'
import { extractLanguageFromPath } from '@/utils/languageHelper'
import { message } from 'antd'
import styles from './UserMenu.module.scss'

interface UserMenuProps {
  userInfo: {
    username?: string
    nickname?: string
    tel?: string
    avatar?: string
  }
}

export default function UserMenu({ userInfo }: UserMenuProps) {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const router = useRouter()
  const pathname = usePathname()

  // 点击外部关闭下拉菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false)
      }
    }

    if (isDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isDropdownOpen])

  // 获取用户名首字母
  const getUserNameIcon = (name: string): string => {
    const firstChar = name.charAt(0)
    return firstChar.toUpperCase()
  }

  // 处理退出
  const handleLogout = async () => {
    try {
      // 立即设置退出标志，防止后续请求显示错误
      setLoggingOut(true)
      
      // 关闭确认弹窗
      setShowLogoutConfirm(false)
      
      // 提取语言代码
      const lng = extractLanguageFromPath(pathname)
      
      // 尝试调用退出接口（最好有，但即使失败也继续）
      try {
        await logout()
      } catch (error) {
        console.log('退出接口调用失败，继续执行本地清除:', error)
      }
      
      // 显示退出成功提示
      message.success('退出成功')
      
      // 清除本地存储和 cookie
      window.localStorage.removeItem('userInfo')
      window.localStorage.removeItem('console_token')
      document.cookie = 'console_token=; path=/; max-age=0'

      // 重置全局用户信息状态
      resetGlobalUserInfo()
      
      // 使用 window.location.href 直接跳转，避免 router.push 过程中的新页面请求
      // 延迟一小段时间确保提示信息显示
      setTimeout(() => {
        window.location.href = `/${lng}/login`
      }, 300)
      
    } catch (error) {
      console.error('退出流程错误:', error)
      // 重置退出标志
      setLoggingOut(false)
      message.error('退出失败，请重试')
    }
  }

  return (
    <>
      {/* 用户头像和下拉菜单 */}
      <div className={styles.userMenuContainer} ref={dropdownRef}>
        <button
          className={styles.userButton}
          onClick={() => setIsDropdownOpen(!isDropdownOpen)}
        >
          {userInfo.avatar ? (
            <img src={userInfo.avatar} alt="User Avatar" className={styles.avatar} />
          ) : (
            <div className={styles.avatarPlaceholder}>
              {getUserNameIcon(userInfo.username || 'U')}
            </div>
          )}
          <svg
            className={`${styles.dropdownIcon} ${isDropdownOpen ? styles.rotated : ''}`}
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
              clipRule="evenodd"
            />
          </svg>
        </button>

        {/* 下拉菜单 */}
        {isDropdownOpen && (
          <div className={styles.dropdownMenu}>
            {/* 用户信息 */}
            <div className={styles.userInfo}>
              <div className={styles.userInfoAvatar}>
                {userInfo.avatar ? (
                  <img src={userInfo.avatar} alt="User Avatar" />
                ) : (
                  getUserNameIcon(userInfo.username || 'U')
                )}
              </div>
              <div className={styles.userInfoText}>
                <div className={styles.username}>{userInfo.username}</div>
                <div className={styles.userDetails}>
                  {userInfo.nickname && <span>{userInfo.nickname}</span>}
                  {userInfo.tel && <span>{userInfo.tel}</span>}
                </div>
              </div>
            </div>

            <div className={styles.divider}></div>

            {/* 菜单项 */}
            <button
              className={styles.menuItem}
              onClick={() => {
                setIsDropdownOpen(false)
                setShowLogoutConfirm(true)
              }}
            >
              <svg className={styles.menuIcon} fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M3 3a1 1 0 00-1 1v12a1 1 0 102 0V4a1 1 0 00-1-1zm10.293 9.293a1 1 0 001.414 1.414l3-3a1 1 0 000-1.414l-3-3a1 1 0 10-1.414 1.414L14.586 9H7a1 1 0 100 2h7.586l-1.293 1.293z"
                  clipRule="evenodd"
                />
              </svg>
              <span>退出登录</span>
            </button>
          </div>
        )}
      </div>

      {/* 退出确认模态框 */}
      {showLogoutConfirm && (
        <div className={styles.modalOverlay} onClick={() => setShowLogoutConfirm(false)}>
          <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <svg className={styles.warningIcon} fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
              <h3>确认退出</h3>
            </div>
            <p className={styles.modalText}>您确定要退出登录吗？</p>
            <div className={styles.modalActions}>
              <button
                className={styles.cancelButton}
                onClick={() => setShowLogoutConfirm(false)}
              >
                取消
              </button>
              <button
                className={styles.confirmButton}
                onClick={handleLogout}
              >
                确认退出
              </button>
            </div>
          </div>
        </div>
      )}

    </>
  )
}

