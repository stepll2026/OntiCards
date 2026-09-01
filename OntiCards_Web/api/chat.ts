import { del, get, post } from '@/api/base'

export function getInformation(conversation_id: string, page: number, limit: number) {
  return get('/pz/conversation/message', { params: { conversation_id, page, limit } })
}

// 获取会话详情 -- 相关问题
export function getConversationDetail(conversation_id: string) {
  return get('/conversation_detail', { params: { conversation_id } })
}


/**
 *
 * 会话删除
 * @export
 * @param {string} id
 * @return {*}
 */
export function deleteConversationHistory(conversation_id: string) {
  return del('/pz/conversation', { body: { conversation_id } })
}

/**
 *
 * 检索图片
 * @export
 * @param {{message_id: string}} params
 */
export function datasetsSearchImage(params: { message_id: string; type: string; page: number }) {
  return get('/datasets_search/image', { params })
}

/**
 *
 * 检索音频
 * @export
 * @param {{message_id: string}} params
 */
export function datasetsSearchAudio(params: { message_id: string }) {
  return get('/datasets_search/audio', { params })
}

/**
 *
 * 语音识别
 * @export
 * @param {{ file_id: string }} params
 * @return {*}
 */
export function speechRecognition(params: { file_id: string }): Promise<{ code: number; message: string; data: string }> {
  return get('/speech_recognition', { params })
}

/**
 *
 * 编辑历史会话标题
 * @export
 * @param {{ id:string; title: string }} body
 * @return {*}
 */
export function editHistoryTitle(body: { id: string; title: string }) {
  const { id, title } = body
  return post('/conversation_detail', { body: { conversation_id: id, title } })
}
