import acceptLanguage from 'accept-language'
import { i18nRouter } from 'next-i18n-router'
import type { NextRequest } from 'next/server'
import { NextResponse } from 'next/server'
import i18nConfig from '@/app/i18n/i18nConfig'
acceptLanguage.languages(i18nConfig.locales)
const isApiRoute = (pathname: string) => {
  const apiRouteRegex = /^\/api\//
  return apiRouteRegex.test(pathname)
}
export function middleware(request: NextRequest) {
  const cookieName = i18nConfig.cookieName
  // 排除 API 路由重定向
  if (isApiRoute(request.nextUrl.pathname))
    return NextResponse.next()

  // 排除静态资源重定向
  if (!/^(?!.*(?:statics|_next)).*$/.test(request.nextUrl.pathname))
    return NextResponse.next()

  // // 排除静态资源重定向
  // if (request.nextUrl.pathname.startsWith('/_next'))
  //   return NextResponse.next()

  let lng: string | undefined | null
  if (request.cookies && request.cookies.has(cookieName))
    lng = request.cookies.get(cookieName)?.value || ''

  if (!lng)
    lng = acceptLanguage.get(request.headers.get('Accept-Language'))
  
  // 如果没有语言代码，使用默认语言
  if (!lng) {
    lng = 'zh-CN'
  }
  
  // 检查用户是否已登录（检查 token）
  const token = request.cookies.get('console_token')?.value
  
  // 拦截根路径（/ 或 /语言代码）
  if (request.nextUrl.pathname === '/' || request.nextUrl.pathname === `/${lng}`) {
    // 如果未登录，跳转到登录页
    if (!token) {
      return NextResponse.redirect(new URL(`/${lng}/login`, request.url))
    }
    // 如果已登录，跳转到概览页面
    return NextResponse.redirect(new URL(`/${lng}/overview`, request.url))
  }

  // 多语言重定向
  return i18nRouter(request, i18nConfig)
}

// applies this middleware only to files in the app directory
export const config = {
  matcher: '/((?!api|static|.*\\..*|_next).*)',
}
