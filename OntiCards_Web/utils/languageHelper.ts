/**
 * 从 URL 路径中提取语言代码
 * 支持的语言：zh-CN, en, zh-HK
 * @param pathname - URL 路径名
 * @returns 语言代码，如果无法提取则返回默认语言 zh-HK
 */
export function extractLanguageFromPath(pathname: string): string {
  const supportedLocales = ['zh-CN', 'en', 'zh-HK']
  const pathSegments = pathname.split('/').filter(Boolean)

  // 检查第一个路径段是否是支持的语言代码
  if (pathSegments.length > 0 && supportedLocales.includes(pathSegments[0])) {
    return pathSegments[0]
  }

  // 如果无法从路径提取，返回默认语言
  return 'zh-CN'
}

