import type { Resource } from 'i18next'

export function getNamespaces() {
  return ['common', 'home', 'chat']
}
const i18nConfig = {
  defaultLocale: 'zh-CN',
  locales: ['zh-CN', 'en', 'zh-HK'],
  getNamespaces,
  cookieName: 'NEXT_LOCALE',
  localeDetector: (request, config) => {
    return 'zh-CN'
  },
}

export function getOptions(locale: string, namespaces?: string[], resources?: Resource) {
  const ns = namespaces !== undefined ? namespaces : getNamespaces()
  return {
    lng: locale,
    resources,
    fallbackLng: i18nConfig.defaultLocale,
    supportedLngs: i18nConfig.locales,
    defaultNS: ns[0],
    fallbackNS: ns[0],
    ns,
    preload: resources ? [] : i18nConfig.locales,
  }
}

export default i18nConfig
