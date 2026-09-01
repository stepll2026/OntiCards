import type chat from '@/public/locales/zh-CN/chat.json'
import type common from '@/public/locales/zh-CN/common.json'
import type home from '@/public/locales/zh-CN/home.json'

type resource = {
  common: typeof common
  home: typeof home
  chat: typeof chat
}
// 定义一个辅助类型，用于获取 resource 中特定键的类型
type ResourceKeyType<T extends keyof resource> = keyof resource[T]

/**
 * 定义函数类型
 * key 为国际化中翻译的key值，该值集合由namespace确定
 * namespace 命名空间，即国际化json文件的名字
 * occupied 是占位值的替换
 *  如：有一个字段写为"after_time_redirect_to": "{{time}}秒后，即将跳转至"
 *  occupied 写作{time: '3'}即可在翻译时进行替换
 */
export type ITran = <T extends keyof resource = 'common'>(key: ResourceKeyType<T>, namespace?: T, occupied?: Record<string, string>) => string
