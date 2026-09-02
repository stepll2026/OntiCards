import { message } from 'antd/lib'

type FetchOptionType = Omit<RequestInit, 'body'> & {
  params?: Record<string, any>
  body?: BodyInit | Record<string, any> | null
}
export type IOnDataMoreInfo = {
  conversationId?: string
  taskId?: string
  messageId: string
  errorMessage?: string
  errorCode?: string
}
export type IOnCompleted = (hasError?: boolean) => void
export type IOnError = (msg: string, code?: string) => void

export type IOnData = (message: string, isFirstMessage: boolean, moreInfo: IOnDataMoreInfo) => void
export type IOtherOptions = {
  bodyStringify?: boolean
  needAllResponseContent?: boolean
  deleteContentType?: boolean
  onData?: IOnData // for stream
  // onThought?: IOnThought
  // onFile?: IOnFile
  // onMessageEnd?: IOnMessageEnd
  // onMessageReplace?: IOnMessageReplace
  onError?: IOnError
  onCompleted?: IOnCompleted // for stream
  getAbortController?: (abortController: AbortController) => void
}
// 全局退出标志，用于标记正在退出登录的状态
let isLoggingOut = false
// token过期跳转标志，防止重复跳转
let isRedirecting = false

// 导出设置退出状态的函数
export const setLoggingOut = (status: boolean) => {
  isLoggingOut = status
}

// 将授权相关错误转换为友好提示
const getFriendlyAuthErrorMessage = (errorMessage: string): string => {
  if (!errorMessage) return errorMessage

  const lowerMsg = errorMessage.toLowerCase()

  // 检测授权token相关错误
  if (
    lowerMsg.includes('missing authorization') ||
    lowerMsg.includes('authorization token') ||
    lowerMsg.includes('token is missing') ||
    lowerMsg.includes('no authorization') ||
    lowerMsg.includes('authorization required')
  ) {
    return '请先登录'
  }

  // 检测token过期相关错误
  if (
    lowerMsg.includes('token expired') ||
    lowerMsg.includes('token invalid') ||
    lowerMsg.includes('invalid token')
  ) {
    return '登录已过期，请重新登录'
  }

  // 检测权限不足相关错误
  if (
    lowerMsg.includes('permission denied') ||
    lowerMsg.includes('access denied') ||
    lowerMsg.includes('insufficient privileges')
  ) {
    return '权限不足，无法访问'
  }

  return errorMessage
}

const TIME_OUT = 28800000 // 8小时超时时间，用于处理大量数据表的数据源添加等耗时操作
const ContentType = {
  json: 'application/json',
  stream: 'text/event-stream',
  form: 'application/x-www-form-urlencoded; charset=UTF-8',
  download: 'application/octet-stream', // for download
  upload: 'multipart/form-data', // for upload
}
const baseOptions = {
  method: 'GET',
  mode: 'cors',
  credentials: 'include', // always send cookies、HTTP Basic authentication.
  headers: new Headers({
    'Content-Type': ContentType.json,
  }),
  redirect: 'follow',
}
// 检查是否是SSO回调（URL中有access_token参数）
const isSSOCallback = (): boolean => {
  if (typeof window === 'undefined') return false
  const params = new URLSearchParams(window.location.search)
  return params.has('access_token')
}

type ResponseError = {
  code: string
  message: string
  status: number
}

// 浏览器始终请求当前站点；Nginx 将此路径转发到 Docker 网络中的 API 服务。
export const urlPrefix = '/console/api'

const baseFetch = <T>(
  url: string,
  fetchOptions: FetchOptionType,
  {
    bodyStringify = true,
    needAllResponseContent,
    deleteContentType,
    getAbortController,
  }: IOtherOptions,
): Promise<T> => {
  const options: typeof baseOptions & FetchOptionType = Object.assign({}, baseOptions, fetchOptions)

  // 确保 headers 是 Headers 对象
  if (!(options.headers instanceof Headers)) {
    const headersObj = options.headers || {}
    options.headers = new Headers(baseOptions.headers)
    // 将传入的 headers 添加到 Headers 对象中
    Object.entries(headersObj).forEach(([key, value]) => {
      if (typeof value === 'string') {
        options.headers.set(key, value)
      }
    })
  }

  if (getAbortController) {
    const abortController = new AbortController()
    getAbortController(abortController)
    options.signal = abortController.signal
  }

  const accessToken = localStorage.getItem('console_token') || ''
  // 只有当 token 存在时才设置 Authorization header
  if (accessToken) {
    options.headers.set('Authorization', `${accessToken}`)
  }

  if (deleteContentType) {
    options.headers.delete('Content-Type')
  }
  else {
    const contentType = options.headers.get('Content-Type')
    if (!contentType)
      options.headers.set('Content-Type', ContentType.json)
  }

  let urlWithPrefix = `${urlPrefix}${url.startsWith('/') ? url : `/${url}`}`

  const { method, params, body } = options
  // handle query
  if (method === 'GET' && params) {
    const paramsArray: string[] = []
    Object.keys(params).forEach(key => {
      const value = params[key]
      // 过滤掉 undefined 和 null 值，避免它们被拼接到 URL 中
      if (value !== undefined && value !== null) {
        paramsArray.push(`${key}=${encodeURIComponent(value)}`)
      }
    })
    if (urlWithPrefix.search(/\?/) === -1)
      urlWithPrefix += `?${paramsArray.join('&')}`

    else
      urlWithPrefix += `&${paramsArray.join('&')}`

    delete options.params
  }

  if (body && bodyStringify)
    options.body = JSON.stringify(body)

  // Handle timeout
  return Promise.race([
    new Promise((resolve, reject) => {
      setTimeout(() => {
        reject(new Error('request timeout'))
      }, TIME_OUT)
    }),
    new Promise((resolve, reject) => {
      let res: Response | null = null
      globalThis.fetch(urlWithPrefix, options as RequestInit)
        .then((response) => {
          res = response
          const resClone = res.clone()

          const bodyJson = resClone.json()

          bodyJson.then((data: any) => {
            if (data.code === 'unauthorized' || data.code === 403 || data.code === 401) {
              // 如果正在退出登录，不处理token过期逻辑（避免重复跳转）
              if (isLoggingOut) {
                return
              }

              // SSO回调场景下，如果是首次获取用户信息失败（token刚存储），不触发跳转
              // 让页面组件的SSO回调处理逻辑来处理
              if (isSSOCallback()) {
                // SSO场景下不自动跳转，等待页面组件处理
                return
              }

              // 防止重复跳转
              if (isRedirecting) {
                return
              }
              isRedirecting = true

              // token 无效或过期，清除本地存储并跳转到登录页面
              localStorage.removeItem('console_token')
              localStorage.removeItem('userInfo')
              document.cookie = 'console_token=; path=/; max-age=0'

              // 显示提示信息
              message.warning('登录已过期，请重新登录')

              // 提取语言代码并跳转到登录页
              // 动态导入以避免服务端执行问题
              import('@/utils/languageHelper').then(({ extractLanguageFromPath }) => {
                const lng = extractLanguageFromPath(window.location.pathname)
                // 如果不在登录页面，则跳转到登录页面（使用绝对路径）
                if (!window.location.pathname.includes('/login')) {
                  // 使用 setTimeout 确保提示信息能够显示
                  setTimeout(() => {
                    window.location.href = `/${lng}/login`
                  }, 100)
                } else {
                  // 如果已经在登录页，重置跳转标志
                  isRedirecting = false
                }
              })
            }
            else if (data.code !== 200 && data.message) {
              // 如果正在退出登录，不显示任何错误提示
              if (isLoggingOut) {
                return
              }

              // 如果是退出接口的错误，且已经在登录页或即将跳转，则不显示错误
              const isLogoutRequest = url.includes('/logout')
              const hasNoToken = !localStorage.getItem('console_token')

              // 如果是退出请求且 token 已被清除，说明退出流程正在进行中，忽略错误提示
              if (isLogoutRequest && hasNoToken) {
                return
              }

              // 检测 "User not found." 错误，需要跳转到登录页
              const errorMessage = data.message || ''
              const isUserNotFoundError = errorMessage.toLowerCase().includes('user not found')

              // 如果是 "User not found." 错误，且不在登录页，则跳转到登录页
              if (isUserNotFoundError && !window.location.pathname.includes('/login')) {
                // 防止重复跳转
                if (isRedirecting) {
                  return
                }
                isRedirecting = true

                // 清除本地存储
                localStorage.removeItem('console_token')
                localStorage.removeItem('userInfo')
                document.cookie = 'console_token=; path=/; max-age=0'

                // 显示提示信息
                message.warning('用户信息获取失败，请重新登录')

                // 提取语言代码并跳转到登录页
                import('@/utils/languageHelper').then(({ extractLanguageFromPath }) => {
                  const lng = extractLanguageFromPath(window.location.pathname)
                  setTimeout(() => {
                    window.location.href = `/${lng}/login`
                  }, 100)
                })
                return
              }

              // 如果是登录页面，不显示全局错误提示（由登录页面自己处理）
              const isLoginPage = window.location.pathname.includes('/login')
              const isLoginRequest = url.includes('/login')

              if (!isLoginPage || !isLoginRequest) {
                // 将授权相关错误转换为友好提示
                const friendlyMessage = getFriendlyAuthErrorMessage(data.message)
                friendlyMessage && message.error(friendlyMessage)
              }
            }
          })

          // handle delete api. Delete api not return content.
          if (res.status === 204) {
            resolve({ result: 'success' })
            return
          }

          // return data
          const data: Promise<T> = options.headers.get('Content-type') === ContentType.download ? res.blob() : res.json()

          resolve(needAllResponseContent ? resClone : data)
        })
        .catch((err) => {
          // 如果正在退出登录，不显示任何错误提示
          if (isLoggingOut) {
            reject(err)
            return
          }

          // 如果是 AbortError，直接 reject，不显示错误消息
          if (err.name === 'AbortError') {
            reject(err)
            return
          }

          // JSON 解析错误（后端返回 HTML 等非 JSON 内容）
          if (err instanceof SyntaxError || err?.message?.includes('Unexpected token')) {
            // 获取 HTTP 状态码
            const status = res?.status || 'unknown'
            const statusText = res?.statusText || ''
            let friendlyMessage = ''

            // 根据状态码提供友好提示
            if (status === 502 || status === 504 || status === 'unknown') {
              friendlyMessage = '后端服务暂时不可用，请稍后重试'
            } else if (status === 500) {
              friendlyMessage = '服务器内部错误，请稍后重试'
            } else if (status === 503) {
              friendlyMessage = '服务暂时过载，请稍后重试'
            } else if (status === 504) {
              friendlyMessage = '请求超时，请稍后重试'
            } else if (status === 404) {
              friendlyMessage = '请求的资源不存在'
            } else {
              friendlyMessage = `请求失败 (${status} ${statusText})`
            }

            message.error(friendlyMessage)
            reject(new Error(friendlyMessage))
            return
          }

          // 将错误信息转换为友好提示
          const errorMessage = err?.message || err?.toString() || err
          const friendlyMessage = getFriendlyAuthErrorMessage(errorMessage)
          friendlyMessage && message.error(friendlyMessage)
          reject(err)
        })
    }),
  ]) as Promise<T>
}

export const request = <T>(url: string, options = {}, otherOptions?: IOtherOptions) => {
  return baseFetch<T>(url, options, otherOptions || {})
}

export const get = <T>(url: string, options = {}, otherOptions?: IOtherOptions) => {
  return request<T>(url, Object.assign({}, options, { method: 'GET' }), otherOptions)
}
export const post = <T>(url: string, options = {}, otherOptions?: IOtherOptions) => {
  return request<T>(url, Object.assign({}, options, { method: 'POST' }), otherOptions)
}
export const del = <T>(url: string, options = {}, otherOptions?: IOtherOptions) => {
  return request<T>(url, Object.assign({}, options, { method: 'DELETE' }), otherOptions)
}
export const put = <T>(url: string, options = {}, otherOptions?: IOtherOptions) => {
  return request<T>(url, Object.assign({}, options, { method: 'PUT' }), otherOptions)
}

const handleStream = (response: any, onData: IOnData, onCompleted?: IOnCompleted) => {
  if (!response.ok)
    throw new Error('Network response was not ok')

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let bufferObj: any
  let isFirstMessage = true

  function read() {
    let hasError = false
    reader.read().then((result: any) => {
      if (result.done) {
        onCompleted && onCompleted()
        return
      }
      buffer += decoder.decode(result.value, { stream: true })
      const lines = buffer.split('\n')
      try {
        lines.forEach((message) => {
          if (message.startsWith('data: ')) { // check if it starts with data:
            // console.log(message)
            try {
              bufferObj = JSON.parse(message.substring(6)) // remove data: and parse as json
            }
            catch (e) {
              // mute handle message cut off
              // onData('', isFirstMessage, {
              //   conversationId: bufferObj?.conversation_id,
              //   messageId: bufferObj?.id,
              // })
              return
            }
            // 不在200-300之间的都是错误
            if (false && bufferObj.code && (bufferObj.code < 200 || bufferObj.code >= 300)) {
              console.log(bufferObj)
              onData('', false, {
                conversationId: undefined,
                messageId: '',
                errorMessage: bufferObj.message || bufferObj.msg,
              })
              hasError = true
              onCompleted && onCompleted(true)
              return
            }
            // can not use format here. Because message is splited.
            onData((bufferObj), isFirstMessage, {
              conversationId: undefined,
              taskId: undefined,
              messageId: '',
            })
            isFirstMessage = false
          }
        })
        buffer = lines[lines.length - 1]
      }
      catch (e) {
        onData('', false, {
          conversationId: undefined,
          messageId: '',
          errorMessage: `${e}`,
        })
        hasError = true
        onCompleted && onCompleted(true)
        return
      }
      if (!hasError)
        read()
    })
  }

  read()
}

export const sseAgent = (url: string, fetchOptions: any, {
  onData,
  onCompleted,
  onError,
  getAbortController,
}: IOtherOptions) => {
  const abortController = new AbortController()

  const options = Object.assign({}, baseOptions, {
    method: 'POST',
    signal: abortController.signal,
  }, fetchOptions)

  // 确保 headers 是 Headers 对象
  if (!(options.headers instanceof Headers)) {
    const headersObj = options.headers || {}
    options.headers = new Headers(baseOptions.headers)
    // 将传入的 headers 添加到 Headers 对象中
    Object.entries(headersObj).forEach(([key, value]) => {
      if (typeof value === 'string') {
        options.headers.set(key, value)
      }
    })
  }

  const accessToken = localStorage.getItem('console_token') || ''
  // 只有当 token 存在时才设置 Authorization header
  if (accessToken) {
    options.headers.set('Authorization', `${accessToken}`)
  }
  const contentType = options.headers.get('Content-Type')
  if (!contentType)
    options.headers.set('Content-Type', ContentType.json)

  getAbortController?.(abortController)

  const urlWithPrefix = `${urlPrefix}${url.startsWith('/') ? url : `/${url}`}`

  const { body } = options
  if (body)
    options.body = JSON.stringify(body)

  globalThis.fetch(urlWithPrefix, options)
    .then((res: any) => {
      // debugger
      if (!/^(2|3)\d{2}$/.test(res.status)) {
        // eslint-disable-next-line no-new
        new Promise(() => {
          res.json().then((data: any) => {
            // Toast.notify({ type: 'error', message: data.message || 'Server Error' })
          })
        })
        onError?.('Server Error')
        return
      }
      return handleStream(res, (str: string, isFirstMessage: boolean, moreInfo: IOnDataMoreInfo) => {
        if (moreInfo.errorMessage) {
          onError?.(moreInfo.errorMessage)
          if (moreInfo.errorMessage !== 'AbortError: The user aborted a request.')
          // Toast.notify({ type: 'error', message: moreInfo.errorMessage })
            return
        }
        onData?.(str, isFirstMessage, moreInfo)
      }, onCompleted)
    }).catch((e) => {
      if (e.toString() !== 'AbortError: The user aborted a request.')
      // Toast.notify({ type: 'error', message: e })

        onError?.(e)
    })
}

export const sendCompletionMessage = async (url: string, body: Record<string, any>, {
  onData,
  onCompleted,
  onError,
  getAbortController,
}: {
  onData: IOnData
  onCompleted: IOnCompleted
  onError: IOnError
  getAbortController?: (abortController: AbortController) => void
}) => {
  return sseAgent(url, {
    body: {
      ...body,
      response_mode: 'streaming',
    },
  }, { onData, onCompleted, onError, getAbortController })
}

export type UploadFileOptions = {
  file: File // 要上传的文件
  should_compress?: boolean // 是否压缩
}

export const rpaUploadFile = async (url: string, options: UploadFileOptions): Promise<any> => {
  const formData = new FormData()
  formData.append('file', options.file)
  formData.append('should_compress', options.should_compress ? 'true' : 'false')

  const accessToken = localStorage.getItem('console_token') || ''
  const headers: Record<string, string> = {}
  // 只有当 token 存在时才设置 Authorization header
  if (accessToken) {
    headers.Authorization = `${accessToken}`
  }

  const response = await fetch(`${urlPrefix}${url}`, {
    method: 'POST',
    body: formData,
    headers,
  })

  // if (!response.ok)
  //   throw new Error('Network response was not ok')

  // 解析响应数据
  const responseData = await response.json()

  return responseData // 返回整理后的响应数据
}
