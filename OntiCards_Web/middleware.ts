import acceptLanguage from 'accept-language'
import { i18nRouter } from 'next-i18n-router'
import type { NextRequest } from 'next/server'
import { NextResponse } from 'next/server'
import i18nConfig from './app/i18n/i18nConfig'

acceptLanguage.languages(i18nConfig.locales)

const isApiRoute = (pathname: string) => {
  const apiRouteRegex = /^\/api\//
  return apiRouteRegex.test(pathname)
}

export function middleware(request: NextRequest) {
  // 排除 API 路由
  if (isApiRoute(request.nextUrl.pathname))
    return NextResponse.next()

  // 排除静态资源
  if (!/^(?!.*(?:statics|_next)).*$/.test(request.nextUrl.pathname))
    return NextResponse.next()

  // 根路径的登录态分流
  if (request.nextUrl.pathname === '/') {
    const token = request.cookies.get('console_token')?.value
    const target = token ? '/overview' : '/login'
    return NextResponse.redirect(new URL(target, request.url))
  }

  // 其他路由交给 i18nRouter：
  // - 默认语言 zh-CN 不带前缀（/login、/overview 等地址栏显示干净）
  // - 非默认语言（en、zh-HK）会带前缀
  // - 内部 rewrite 到 app/[lng]/... 下对应页面，浏览器 URL 不变
  return i18nRouter(request, i18nConfig)
}

// applies this middleware only to files in the app directory
export const config = {
  matcher: '/((?!api|static|.*\\..*|_next).*)',
}
