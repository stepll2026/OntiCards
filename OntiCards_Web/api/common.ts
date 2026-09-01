import { rpaUploadFile } from '@/api/base'
/**
 *
 * 上传附件
 */
export function uploadFile(params: { file: File }): Promise<{ code: number;message: string; data: { file_url: string; upload_file_id: string } }> {
  const { file } = params
  return rpaUploadFile('/file/upload', { file })
}
