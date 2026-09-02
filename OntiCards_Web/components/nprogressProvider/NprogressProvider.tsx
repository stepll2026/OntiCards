'use client'

import { AppProgressBar as ProgressBar } from 'next-nprogress-bar'
import type { ReactNode } from 'react'

/**
 * NprogressProvider
 *
 * 修复说明：
 * 原来的进度条实现存在以下问题：
 * - 在中间件触发 URL 重定向的语言切换场景下，浏览器当前地址（location.href）
 *   与 <Link> 解析出来的目标 URL 在客户端 routing 过程中可能存在短暂不一致；
 *   同时，由于目标 URL 实际与当前 URL"看起来"相同（都被中间件归一化为同一地址），
 *   Next.js 客户端不会重新触发 pathname 变化，因此组件内监听 [pathname, searchParams]
 *   的 useEffect 不会再次执行 NProgress.done()，导致进度条卡住不消失。
 *
 * 解决方案：
 * - 在侧边栏菜单的当前激活项 <Link> 上添加 data-prevent-nprogress="true"，
 *   让 next-nprogress-bar 在 click 阶段直接 return，从源头阻止进度条启动；
 * - 同时启用 disableSameURL，保证即使是其他位置意外触发的同 URL 跳转也不会起条；
 * - 保留 <a> 默认监听行为，未激活菜单跳转仍正常显示进度条。
 */
const NprogressProvider = ({ children }: { children: ReactNode }) => {
  return (
    <>
      {children}
      <ProgressBar
        height="4px"
        color="#6366f1"
        options={{
          showSpinner: false,
          easing: 'ease-in-out',
          speed: 300,
          minimum: 0.1,
        }}
        disableSameURL={true}
        stopDelay={300}
      />
    </>
  )
}

export default NprogressProvider
