import i18nConfig from '@/app/i18n/i18nConfig'
import initTranslations from '@/app/i18n/index'
import NprogressProvider from '@/components/nprogressProvider/NprogressProvider'
import TranslationsProvider from '@/components/translationsProvider/TranslationsProvider'
import ThemeProvider from '@/components/themeProvider/ThemeProvider'
import '@/styles/animate.min.css'
import '@/styles/animation.css'
import '@/styles/globals.css'
import { AntdRegistry } from '@ant-design/nextjs-registry'
import { App, ConfigProvider, Skeleton } from 'antd'
import enUS from 'antd/lib/locale/en_US'
import zhCN from 'antd/lib/locale/zh_CN'
import zhHK from 'antd/lib/locale/zh_HK'
import dayjs from 'dayjs'
import 'dayjs/locale/en'
import 'dayjs/locale/zh-cn'
import 'dayjs/locale/zh-hk'
import { dir } from 'i18next'
import type { Metadata, Viewport } from 'next'
import { Suspense } from 'react'
export const metadata: Metadata = {
  // title: '星島頭條AICG及媒體資訊管理平台',
  // description: '星島頭條AICG及媒體資訊管理平台',
  title: 'OntiCards',
  description: 'OntiCards',
  icons: '/statics/new_logo_final_web_title.jpg',
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  minimumScale: 1,
  userScalable: false,
  viewportFit: 'cover',
}
export async function generateStaticParams() {
  return i18nConfig.locales.map(lng => ({ lng }))
}
const LocaleLayout = async ({
                              children,
                              params: { lng },
                            }: {
  children: React.ReactNode
  params: {
    lng: string
  }
}) => {
  const antdLocale = {
    'en': enUS,
    'zh-CN': zhCN,
    'zh-HK': zhHK,
  }[lng]
  const dayjsLocaleMap: Record<string, string> = {
    'en': 'en',
    'zh-CN': 'zh-cn',
    'zh-HK': 'zh-hk',
  }
  dayjs.locale(dayjsLocaleMap[lng] || 'zh-cn')
  const ns = i18nConfig.getNamespaces()
  const { resources } = await initTranslations(lng, ns)
  return (
    <html lang={lng} dir={dir(lng)} suppressHydrationWarning>
    <head>
      {/* 首屏前同步设置 data-theme，避免深色模式闪烁或样式未生效 */}
      <script
        dangerouslySetInnerHTML={{
          __html: `(function(){try{var t=localStorage.getItem('onticards-theme');if(t==='dark'){document.documentElement.setAttribute('data-theme','dark');}else if(t==='light'){document.documentElement.setAttribute('data-theme','light');}else if(t==='system'){document.documentElement.setAttribute('data-theme',window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');}}catch(e){}})();`,
        }}
      />
      <meta name='theme-color' content='#FFFFFF' />
      <meta name='mobile-web-app-capable' content='yes' />
      <meta name='apple-mobile-web-app-capable' content='yes' />
      <meta name='apple-mobile-web-app-status-bar-style' content='default' />
      <link rel="icon" href="/statics/new_logo_final.png" sizes="any" />
    </head>
    <body
      id='root'
      className='h-full select-auto'
      data-api-prefix={process.env.NEXT_PUBLIC_API_PREFIX}
      data-file-prefix={process.env.NEXT_PUBLIC_FILE_PREFIX}
      data-pubic-api-prefix={process.env.NEXT_PUBLIC_PUBLIC_API_PREFIX}
      data-public-edition={process.env.NEXT_PUBLIC_EDITION}
      data-public-sentry-dsn={process.env.NEXT_PUBLIC_SENTRY_DSN}
      data-public-maintenance-notice={process.env.NEXT_PUBLIC_MAINTENANCE_NOTICE}
      data-public-site-about={process.env.NEXT_PUBLIC_SITE_ABOUT}
    >
    <ThemeProvider>
      <AntdRegistry>
        <NprogressProvider>
          <ConfigProvider
            locale={antdLocale || zhHK}
            theme={{
              components: {
                Switch: {},
                Button: {},
              },
              token: {},
            }}
          >
            <App>
              <Suspense
                fallback={
                  <div className='w-full'>
                    <div className='mb-[20px]'>
                      <Skeleton active />
                    </div>

                    <div className='mb-[20px]'>
                      <Skeleton active />
                    </div>
                    <div className='mb-[20px]'>
                      <Skeleton active />
                    </div>
                    <div className='mb-[20px]'>
                      <Skeleton active />
                    </div>
                    <div className='mb-[20px]'>
                      <Skeleton active />
                    </div>
                  </div>
                }
              >
                <TranslationsProvider namespaces={ns} locale={lng} resources={resources}>
                  {children}
                </TranslationsProvider>
              </Suspense>
            </App>
          </ConfigProvider>
        </NprogressProvider>
      </AntdRegistry>
    </ThemeProvider>
    {/* */}
    </body>
    </html>
  )
}

export default LocaleLayout
