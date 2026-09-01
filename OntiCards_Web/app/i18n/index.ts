import type { Resource, i18n } from 'i18next'
import { createInstance } from 'i18next'
import resourcesToBackend from 'i18next-resources-to-backend'
import { initReactI18next } from 'react-i18next/initReactI18next'
import type { ITran } from './type'
import { getOptions } from '@/app/i18n/i18nConfig'

export default async function initTranslations(locale: string, namespaces?: string[], instance?: i18n, resources?: Resource) {
  const i18nInstance = instance || createInstance()

  i18nInstance.use(initReactI18next)
  if (!resources) {
    i18nInstance.use(
      resourcesToBackend((language: string, namespace: string) => {
        return import(`@/public/locales/${language}/${namespace}.json`)
      }),
    )
  }

  await i18nInstance.init(getOptions(locale, namespaces, resources))
  const t: ITran = (key, namespace, occupied) => {
    return (i18nInstance.t as any)(key, { ns: namespace ?? 'common', ...occupied })
  }
  return {
    i18n: i18nInstance,
    resources: i18nInstance.services.resourceStore.data,
    t,
  }
}
