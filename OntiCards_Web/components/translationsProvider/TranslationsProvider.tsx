'use client'

import type { Resource } from 'i18next'
import { createInstance } from 'i18next'
import type { PropsWithChildren } from 'react'
import { I18nextProvider } from 'react-i18next'
import { tranInstanceManager } from '@/app/i18n/hooks'
import initTranslations from '@/app/i18n'

export default function TranslationsProvider({
  children,
  locale,
  namespaces,
  resources,
}: PropsWithChildren<{
  locale: string
  namespaces: string[]
  resources: Resource
}>) {
  const i18n = createInstance()
  tranInstanceManager.instance = i18n
  initTranslations(locale, namespaces, i18n, resources)

  return <I18nextProvider i18n={i18n}>{children}</I18nextProvider>
}
