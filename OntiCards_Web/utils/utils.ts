import type { GetProp, UploadFile, UploadProps } from 'antd'
import { message } from 'antd/lib'
type FileType = Parameters<GetProp<UploadProps, 'beforeUpload'>>[0]

/**
 *
 * 格式化显示文件大小
 * @param {number} bytes 需要转换的字节数
 * @param {number} [decimalPoints=2] 保留的小数位数，默认为 2 位
 * @return {*}  {string}
 */
export const formatFileSize = (bytes = 0, decimalPoints = 2): string => {
  bytes = Number(bytes)
  if (bytes === 0) return '0 Bytes'

  const k = 1024
  const dm = decimalPoints < 0 ? 0 : decimalPoints
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']

  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return `${parseFloat((bytes / k ** i).toFixed(dm))} ${sizes[i]}`
}

/**
 *
 *
 * 下载
 *  @param {string} url 下载路径
 *  @param {string} name 下载名称
 */
export const onDownload = ({ url, name }: { url: string; name: string }): void => {
  // const link = document.createElement('a') // a标签下载
  // link.href = url // href属性指定下载链接
  // link.download = name
  // link.click() // click()事件触发下载
  // window.URL.revokeObjectURL(link.href) // 释放内存
  const anchorElement = document.createElement('a')
  anchorElement.href = url
  anchorElement.download = name
  anchorElement.addEventListener('click', (event) => {
    // 检查请求的状态
    event.preventDefault() // 阻止默认的导航行为

    const xhr = new XMLHttpRequest()
    xhr.open('GET', url)
    xhr.responseType = 'blob'
    xhr.setRequestHeader('Authorization', `Bearer ${localStorage.getItem('console_token')}`)
    xhr.onload = function () {
      if (this.status === 404) {
        console.error('文件未找到:', url)
        message.error('文件未找到，请检查链接是否正确')
      } else if (this.status === 200) {
        const link = document.createElement('a') // a标签下载
        link.href = url // href属性指定下载链接
        link.download = name
        link.click() // click()事件触发下载
        window.URL.revokeObjectURL(link.href)
      } else {
        message.error('下载文件时发生网络错误，请检查链接是否正确。')
      }
    }

    xhr.onerror = function () {
      window.open(url)
      // console.error('下载文件时发生网络错误:', url)
      // message.error('下载文件时发生网络错误，请检查链接是否正确。')
    }

    xhr.send()
  })

  // 使用JavaScript触发<a>元素的点击事件
  document.body.appendChild(anchorElement)
  anchorElement.click()
  document.body.removeChild(anchorElement)
}

/**
 *
 * 获取格式是否合法
 * @param {*} file 附件
 * @param {*} extensions 校验格式
 * @return {*}
 */
export function isAttachmentOfType_old(file: UploadFile, extensions: string[]): boolean {
  let fileType = ''
  if (file.type) {
    fileType = file.type.toLowerCase()
  } else if (file.name) {
    const _type = file.name.split('.')
    fileType = _type[1]
  }
  if (fileType) return extensions.some((ext) => fileType.startsWith(ext))
  else return false
}

export function isAttachmentOfType(file: UploadFile, extensions: string[]): boolean {
  let fileType = ''

  if (file.type) {
    fileType = file.type.toLowerCase()
  } else if (file.name) {
    const _type = file.name.split('.').pop()?.toLowerCase()
    fileType = _type ? `.${_type}` : ''
  }

  return fileType && extensions.some((ext) => fileType === ext.toLowerCase() || fileType === `.${ext.toLowerCase()}`)
}

/**
 * 获取base64
 * @param img
 * @param callback
 */
export function getBase64(img: FileType): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.addEventListener('load', () => {
      resolve(reader.result as string)
    })
    reader.readAsDataURL(img)
  })
}

/**
 *
 *  blob转File
 * @param {*} newBlob
 * @param {*} fileName 转换后 file名称
 * @return {*}
 */
export const blobToFile = (newBlob: Blob, fileName = 'newFile.jpg') => {
  const newFile: File = new File([newBlob], fileName, {
    type: newBlob.type ? newBlob.type : 'image/jpg',
    lastModified: new Date().getTime(),
  })
  return newFile
}
