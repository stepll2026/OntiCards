export type CleanupResponse = {
  code?: number
  msg?: string
  data?: any
  result?: any
}

export function getCleanupError(response: CleanupResponse, httpOk = true): string | null {
  if (!httpOk || response.code !== 200) {
    return response.msg || '操作失败，请检查数据清理状态后重试'
  }
  const details = response.data ?? response.result
  if (details?.weaviate_deleted === false || details?.cleanup_complete === false) {
    return '向量数据清理未完成，请检查服务状态并重试清理'
  }
  return null
}

export async function finishCancelledExtraction(
  cleanup: () => Promise<CleanupResponse>,
  warn: (message: string) => void,
): Promise<CleanupResponse & { code: number; msg: string }> {
  try {
    const response = await cleanup()
    const error = getCleanupError(response)
    if (!error) return { code: 499, msg: '请求已取消', result: null }
    const msg = `请求已取消，但数据清理未完成：${error}`
    warn(msg)
    return { ...response, code: 502, msg }
  } catch {
    const msg = '请求已取消，但无法确认数据清理结果，请检查服务状态并重试清理'
    warn(msg)
    return { code: 502, msg, result: null }
  }
}
