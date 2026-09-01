import i18nConfig from '@/app/i18n/i18nConfig'
import type { ITran } from '@/app/i18n/type'
import type { i18n } from 'i18next'
import { useRouter } from 'next-nprogress-bar'
import { usePathname, useSearchParams } from 'next/navigation'
import { useTranslation } from 'react-i18next'

/**
 *
 * 切换语言回调函数
 */
let changeLanguageCallback = () => {}
/**
 *
 * 其实客户端可以直接调用useTranslation()获取t，但没有类型提示，所以我们封装了一层
 * @export
 * @return {*}
 */
export function useClientTranslation(): {
  t: ITran
  i18n: i18n
} {
  const { t: tt, i18n } = useTranslation()
  const t: ITran = (key, namespace, occupied) => {
    return (tt as any)(key, { ns: namespace ?? 'common', ...occupied })
  }
  return { t, i18n } as { t: ITran; i18n: i18n }
}

/**
 *
 * 设置切换语言回调函数
 * @export
 * @param {*} [callback=() => {}] 回调函数
 */
export function setChangeLanguageCallback(callback = () => {}): void {
  changeLanguageCallback = callback
}

/**
 *
 * 改变语言的hook
 * @export
 * @return {*}
 */
export function useChangeLanguage(): {
  currentLocale: string
  handleChange: (newLocale: string) => void
} {
  const { i18n } = useTranslation()
  const currentLocale = i18n.language
  const router = useRouter()
  const currentPathname = usePathname()
  const searchParams = useSearchParams()

  const handleChange = (newLocale: string) => {
    // set cookie for next-i18n-router
    if(currentLocale === newLocale)
      return
    const days = 30
    const date = new Date()
    date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000)
    const expires = `; expires=${date.toUTCString()}`
    document.cookie = `${i18nConfig.cookieName}=${newLocale}${expires};path=/`
    let query = ''
    searchParams.forEach((value: any, key: any) => {
      query = `${query ? `${query}&` : ''}${key}=${value}`
    })
    let url = ''
    if (currentLocale === i18nConfig.defaultLocale)
      url = `/${newLocale}${currentPathname}${query ? `?${query}` : ''}`

    else
      url = `${currentPathname.replace(`${currentLocale}/`, `${newLocale}/`)}${query ? `?${query}` : ''}`

    // router.push(url);
    // router.refresh();
    router.replace(url)
    changeLanguageCallback()
  }
  return { currentLocale, handleChange }
}

/**
 *
 * 在非组件中引用
 * @class TranInstanceManager
 */
class TranInstanceManager {
  private i18nInstance!: i18n
  get instance() {
    return this.i18nInstance
  }

  set instance(value: i18n) {
    this.i18nInstance = value
  }
}
export const tranInstanceManager = new TranInstanceManager()

export function getTranslationWithoutReact() {
  const i18n = tranInstanceManager.instance
  return i18n.t as unknown as ITran
}
