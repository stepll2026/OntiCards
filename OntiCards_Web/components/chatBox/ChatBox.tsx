'use client'
import { speechRecognition } from '@/api/chat'
import { uploadFile } from '@/api/common'
import { useClientTranslation } from '@/app/i18n/hooks'
import AntSvgIcon from '@/components/antSvgIcon/AntSvgIcon'
import AudioRecorder from '@/components/audioRecorder/AudioRecorder'
import HomeContext from '@/context/homeContext'
import { blobToFile, formatFileSize, isAttachmentOfType } from '@/utils'
import {
  AimOutlined,
  AudioOutlined,
  CloseOutlined,
  FileExcelOutlined,
  FileJpgOutlined,
  FilePdfOutlined,
  FileUnknownOutlined,
  FileWordOutlined,
  GlobalOutlined,
  LoadingOutlined,
  OpenAIOutlined,
  PauseCircleOutlined,
  PlusCircleOutlined,
} from '@ant-design/icons'
import type { GetProp, UploadProps } from 'antd'
import { App, Input, Spin, Tooltip, Upload } from 'antd'
import dayjs from 'dayjs'
import _ from 'lodash'
import { Fragment, forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { useContext } from 'use-context-selector'
import styles from './ChatBox.module.scss'

type SendingDataType = {
  /** 已选择附件、音频 */
  files: FileListTyep[]
  /** 输入的文字 */
  content: string | number
  /** 是否从互联网搜寻资料 */
  isInternet: boolean
  /** 是否从資料庫搜尋資料 */
  isDatabase: boolean
  /** 目标源 */
  mode: string[]
  [key: string]: any
}

type UploadFileDataType = {
  file_url: string
  upload_file_id: string
}

type MenuItmeType = {
  key: string
  label: JSX.Element
}

type FileType = Parameters<GetProp<UploadProps, 'beforeUpload'>>[0]

type FileListTyep = {
  name: string
  type: string
  size: number
  file: FileType | Blob
  id: string
}

type ShowFileLType = {
  [key: string]: string
}

type IconType = {
  [key: string]: React.ComponentType
}

type Props = {
  /** 发送触发 */
  onSending?: ((data: any) => void) | undefined
  /** 发送成功 */
  sendingCallback?: ((id?: string) => void) | undefined
  /** 发送失败 */
  onError?: ((data: string) => void) | undefined
  /** 回复中 */
  isResponse?: boolean
  /** 其他请求参数 */
  params?: { [key: string]: any }
  /** 是否再次对话 */
  dialogueAgain?: boolean
}
// let recognition = null
const ChatBox = (props: Props, ref: any) => {
  const { userInfo, setShowLogin } = useContext(HomeContext)
  const { t } = useClientTranslation()
  const { message, notification, modal } = App.useApp()
  const { dialogueAgain = false } = props
  useImperativeHandle(ref as any, () => ({
    // 父级调用
    onSending,
  }))
  const { TextArea } = Input
  /** 附件ref */
  const filesRef = useRef<HTMLInputElement>(null)
  /** 输入框Ref */
  const textAreaRef = useRef<HTMLTextAreaElement>(null)
  /** 输入框文本值 */
  const [query, setQuery] = useState<string>('')
  /** 前端显示的附件列表 */
  const [fileList, setFileList] = useState<FileListTyep[]>([])
  /** 附件列表 */
  const [fileIds, setFileIds] = useState<string[]>([])
  /** 录音状态 */
  const [recording, setRecording] = useState<boolean>(false)
  /**  发送中loading */
  const [isLoading, setLoading] = useState<boolean>(false)
  /**  上传中loading */
  const [isUploadLoading, setUploadLoading] = useState<boolean>(false)
  /**  是否从网络获取 */
  const [isInternet, setIsInternet] = useState<boolean>(false)
  /**  是否从资料库获取 */
  const [isDatabase, setisDatabase] = useState<boolean>(true)
  /** 已选目标源数组 */
  const [mode, setMode] = useState<string>('GPT')
  /** 目标源选项 */
  const modeItems: MenuItmeType[] = [
    {
      key: 'GPT',
      label: <div className={'cursor-pointer'}>GPT</div>,
    },
    {
      key: 'Baidu',
      label: <div className={'cursor-pointer'}>文心一言</div>,
    },
  ]
  useEffect(() => {
    setisDatabase(true)
    // // 默认获取上一次的设置
    // const _isInternet = sessionStorage.getItem('isInternet')
    // const _isDatabase = sessionStorage.getItem('isDatabase')
    // if (_isInternet)
    //   setIsInternet(!!Number(_isInternet))

    // if (_isDatabase)
    //   setisDatabase(!!Number(_isDatabase))

    // if (!Number(_isDatabase) && !Number(_isInternet))
    //   setIsInternet(false)
  }, [])
  // useEffect(() => {
  //   sessionStorage.setItem('isInternet', String(-(-isInternet)))
  // }, [isInternet])

  useEffect(() => {
    sessionStorage.setItem('isDatabase', String(-(-isDatabase)))
  }, [isDatabase])

  useEffect(() => {
    setFileIds(fileList.map((item) => item.id as string))
  }, [fileList])

  /**
   *
   * 监听键盘
   * @param {React.KeyboardEvent<HTMLTextAreaElement>} event
   */
  const handleKeyPress = (event: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    // 检查是否同时按下了 ctrl 键和 enter 键
    if (event.ctrlKey && event.key === 'Enter') {
      // 阻止默认行为
      event.preventDefault()
      // 获取textArea
      const ref: HTMLTextAreaElement = _.get(textAreaRef, ['current', 'resizableTextArea', 'textArea'])
      if (ref) {
        // 获取光标位置
        const cursor = ref.selectionStart as number
        // 切割光标前后
        const beforeCursor = query.slice(0, cursor)
        const afterCursor = query.slice(cursor)
        // 更新 TextArea 的值，插入换行符
        setQuery(`${beforeCursor}\n${afterCursor}`)
        // 移动光标到下一行的开始位置
        ref.setSelectionRange(cursor + 1, cursor + 1)
      }
    }
  }

  /**
   *
   * 变更目标源
   * @param
   */
  const onChangeMode = ({ key }: { key: string }): void => {
    setMode(key)
  }

  /** 获取附件 */
  function getFiles(file: FileType, id: string): void {
    const _fileList = {
      file,
      name: file.name,
      size: file.size,
      type: getShowType(file.type),
      id,
    }
    setFileList([...fileList, _fileList])
  }

  /**
   *
   * 类型转换显示
   */
  function getShowType(data: string): string {
    const type: ShowFileLType = {
      'application/vnd.ms-excel': 'XLSX',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'XLSX',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.template': 'XLSX',
      'text/csv': 'XLSX',

      'application/msword': 'DOCX',
      'application/vnd.ms-word': 'DOCX',
      'pplication/vnd.ms-word.document.macroEnabled.12': 'DOCX',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.template': 'DOCX',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
      'application/vnd.ms-word.wordprocessingml.template': 'DOCX',
      'application/vnd.ms-word.wordprocessingml.document.macroEnabled': 'DOCX',
      'application/vnd.ms-word.wordprocessingml.template.macroEnabled': 'DOCX',
      'application/vnd.ms-word.document.binary.macroEnabled': 'DOCX',

      'application/epub+zip': 'PDF',
      'application/vnd.ms-xpsdocument': 'PDF',
      'application/oxps': 'PDF',
      'application/vnd.adobe.xdp+xml': 'PDF',
      'application/vnd.adobe.xfdf': 'PDF',
      'application/vnd.adobe.formscentral.pkg': 'PDF',
      'application/pdf': 'PDF',

      'image/jpeg': 'Image',
      'image/png': 'Image',
      'image/gif': 'Image',
      'image/webp': 'Image',
      'image/bmp': 'Image',
      'image/tiff': 'Image',
      'image/svg+xml': 'Image',
      webm: 'MP3',
      'audio/webm;codecs=opus': 'MP3',
    }
    return type[data] ? type[data] : data
  }

  /**
   *
   *  删除已选择附件
   */
  const onDelFile = (index: number) => {
    const _fileList = _.cloneDeep(fileList)
    _fileList.splice(index, 1)
    setFileList(_fileList)
  }

  /**
   *
   * 校验表单
   */
  const validatorFrom = ({ query, fileList }: { query: string; fileList: FileListTyep[] }): boolean => {
    if (!query) {
      message.error(t('chatError', 'chat'))
      return false
    } else if (!fileList.length && !isInternet && !isDatabase && dialogueAgain) {
      message.error(t('chatError2', 'chat'))
      return false
    }
    return true
  }

  /**
   *
   *  点击发送
   */
  function onSending(data = { query, fileList }): void {
    if (!userInfo.id) {
      setShowLogin(true)
      return
    }
    const { query: _query = query, fileList: _fileList = fileList } = data
    if (!validatorFrom({ query: _query, fileList: _fileList })) return

    if (!isLoading && !props.isResponse) {
      setLoading(true)
      const params = !dialogueAgain
        ? {
            net_search: isInternet,
            dataset: isDatabase,
            file_ids: fileIds,
            mode,
            ...data,
            ...props.params,
          }
        : {
            file_ids: fileIds,
            mode,
            ...data,
            ...props.params,
          }
      props.onSending && props.onSending(params)
      setQuery('')
      setFileList([])

      setLoading(false)
      props.sendingCallback && props.sendingCallback()
    }
  }

  /**
   *
   * 获取录音
   */
  const onSetAudios = async (data: { audio: {}; blob: Blob }): Promise<void> => {
    setRecording(false)
    const audiosFile = blobToFile(data.blob, `${dayjs().valueOf()}_audio.wav`)
    setUploadLoading(true)
    uploadFile({ file: audiosFile })
      .then(({ data }) => {
        return speechRecognition({ file_id: data.upload_file_id })
      })
      .then(({ data }) => {
        setQuery(query + data)
      })
      .finally(() => {
        setUploadLoading(false)
      })
  }

  /**
   *
   * 录音组件报错信息
   * @param {string} e
   */
  const audiosError = (e: string): void => {
    setRecording(false)
    message.error(e)
  }

  /**
   *
   * 调用录音
   */
  const onSoundRecording = (): void => {
    if (!userInfo.id) {
      setShowLogin(true)
      return
    }
    if (isLoading || props.isResponse) return
    setRecording(true)
  }

  /**
   *
   * 上传拦截校验
   * @param {FileType} file
   * @return {*}
   */
  const beforeUpload = (file: FileType): Promise<File | Blob> => {
    const supportedTypes: string[] = [
      'text/plain', // TXT
      'text/markdown', // MARKDOWN
      'md', // MARKDOWN
      'application/pdf', // PDF
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', // XLSX
      'application/vnd.ms-excel', // XLS
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // DOCX
      'application/msword', // DOC
      'text/csv', // CSV
      'application/vnd.openxmlformats-officedocument.presentationml.presentation', // PPTX
      'application/vnd.ms-powerpoint', // PPT
    ]
    // 每M等于bytes
    const baseSize = 1048576
    // 最大文件大小
    const maxSize = 15
    // 错误提示
    let errotMessage = ''
    return new Promise((resolve, reject) => {
      const isLegal = isAttachmentOfType(file, supportedTypes)
      if (!isLegal) {
        const errotMessage = t('uploadFormatError', 'common', { type: file.type })
        message.error(errotMessage)
        return reject(new Error(errotMessage))
      } else if (file.size > maxSize * baseSize) {
        errotMessage = t('uploadSizeError', 'common', {
          name: file.name,
          size: String(maxSize || 0),
        })
        message.error(errotMessage)
        return reject(new Error(errotMessage))
      } else {
        return resolve(file)
      }
    })
  }

  /**
   *
   * 上传文件
   */
  function onUpload(data): void {
    // if (!userInfo.id) {
    //   setShowLogin(true)
    //   return
    // }
    // const file = data.file
    // setUploadLoading(true)
    // uploadFile({ file }).then(({ data }: { data: UploadFileDataType }) => {
    //   getFiles(file, data.upload_file_id)
    // }).catch((e) => {
    //   // message.error(e.message || t('requestFailure'))
    // }).finally(() => {
    //   setUploadLoading(false)
    // })
  }

  /**
   *
   * 推理模式节点
   * @returns
   */
  const modeNode = () => {
    const html: JSX.Element[] = []
    modeItems.map((item) => {
      if (mode.includes(item.key)) {
        html.push(
          <div key={item.key} className='flex mr-[10px] '>
            {item.label}
          </div>,
        )
      }
      return undefined
    })
    return mode.length ? html : <span className='cursor-pointer'>请选择推理模式</span>
  }

  /**
   *
   * 已选择附件节点
   */
  const FileListNode = () => {
    const iconType: IconType = {
      PDF: FilePdfOutlined,
      DOCX: FileWordOutlined,
      Image: FileJpgOutlined,
      XLSX: FileExcelOutlined,
      MP3: AudioOutlined,
    }
    return (
      Boolean(fileList.length) && (
        <div
          style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))' }}
          className='w-full min-h-[64px] bg-[#e5e7ed] grid  gap-3 p-3 max-h-[300px] overflow-y-auto'
        >
          {fileList.map((file, index) => {
            const IconComponent = iconType[file.type]
            return (
              <div key={index} className='bg-white rounded-[10px] shadow p-3 flex relative h-15'>
                <div className='text-[26px] flex items-center justify-center mr-3'>
                  {iconType[file.type] ? <IconComponent></IconComponent> : <FileUnknownOutlined />}
                </div>
                <div className='flex-1 flex flex-col truncate leading-5'>
                  <Tooltip title={file.name}>
                    <div className='text-14 truncate'>{file.name}</div>
                  </Tooltip>

                  <div className='text-12 truncate flex'>
                    <Tooltip title={getShowType(file.type)}>
                      <div className='flex-1 truncate'>{getShowType(file.type)}</div>
                    </Tooltip>

                    <Tooltip title={formatFileSize(file.size)}>
                      <div className='truncate'>{formatFileSize(file.size)}</div>
                    </Tooltip>
                  </div>
                </div>

                <div
                  onClick={() => {
                    onDelFile(index)
                  }}
                  className='absolute w-[18px] h-[18px] rounded-[50%] top-[-5px] right-[-7px] bg-[#ff0000] flex items-center justify-center'
                >
                  <div className='text-white text-[12px]'>
                    <CloseOutlined />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )
    )
  }

  return (
    <div className='relative min-h-[160px] w-full rounded-[20px] border-[#eee] border flex flex-col shadow overflow-hidden'>
      {recording && <AudioRecorder onSetAudios={onSetAudios} onSetError={audiosError}></AudioRecorder>}
      {isUploadLoading && (
        <div className='z-999 absolute w-full h-full bg-black/[0.4] flex justify-center items-center'>
          <Spin size='large' />
        </div>
      )}
      <TextArea
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t('chatPlaceholder', 'chat')}
        autoSize={{ minRows: fileList.length ? 2 : 4, maxRows: fileList.length ? 2 : 4 }}
        rows={fileList.length ? 2 : 4}
        className={`${styles.text_area}`}
        onKeyDown={handleKeyPress}
        onPressEnter={(event) => {
          event.preventDefault()
          // 非发送中且非ctrl+ enter
          !isLoading && !event.ctrlKey && onSending()
        }}
        ref={textAreaRef}
      />

      <div className='flex justify-between items-center  px-[20px] min-h-[40px]'>
        <div className='flex flex-1 min-w-0'>
          <Upload
            disabled
            maxCount={5}
            className={'cursor-pointer px-[5px] flex items-center'}
            name='file'
            customRequest={onUpload}
            showUploadList={false}
            beforeUpload={beforeUpload}
          >
            <Tooltip title='支持上传txt，doc，xls，ppt，pdf，markdown格式文件，最多可上传5个，每个大小不超过15MB'>
              <div className='hidden flex items-center'>
                <div className='h-[20px] w-[20px] mr-[5px] text-20 flex items-center '>
                  <PlusCircleOutlined />
                </div>
                <span className='truncate smb:inline-block hidden md:text-14 text-12 items-center'>{t('attachment', 'chat')}</span>
              </div>
            </Tooltip>
          </Upload>

          {!dialogueAgain && (
            <Fragment>
              <Tooltip title={t('internet', 'chat')}>
                <div
                  onClick={() => {
                    // setIsInternet(!isInternet)
                  }}
                  style={{ color: 'rgba(0, 0, 0, 0.25)' }}
                  className={`hidden truncate flex px-[5px] items-center  cursor-not-allowed ${isInternet ? 'text-[#009dff]' : ''}`}
                >
                  <div className='h-[20px] w-[20px] mr-[5px] text-20 flex items-center '>
                    <GlobalOutlined />
                  </div>
                  <span className='truncate smb:inline-block hidden md:text-14 text-12    items-center'>{t('internet', 'chat')}</span>
                </div>
              </Tooltip>
              <Tooltip title={t('database', 'chat')}>
                <div
                  onClick={() => {
                    // setisDatabase(!isDatabase)
                  }}
                  className={`truncate cursor-pointer flex px-[5px] items-center ${isDatabase ? 'text-[#009dff]' : ''}`}
                >
                  <div className='h-[20px] w-[20px] mr-[5px] text-20 flex items-center '>
                    <AimOutlined />
                  </div>
                  <span className='truncate smb:inline-block hidden md:text-14 text-12   items-center'>{t('database', 'chat')}</span>
                </div>
              </Tooltip>

              <div className='flex px-[5px] items-center hidden'>
                <div className='h-[20px] w-[20px] mr-[5px] text-20 flex items-center '>
                  <OpenAIOutlined />
                </div>
                <div className='smb:flex hidden md:text-14 text-12 h-full   items-center'>{modeNode()}</div>
              </div>
            </Fragment>
          )}
        </div>

        <div className='flex '>
          <div
            className='mr-[15px]  text-20 cursor-pointer'
            onClick={() => {
              onSoundRecording()
            }}
          >
            {recording ? (
              <span className='text-[red]'>
                <PauseCircleOutlined className='text-[red]' />
              </span>
            ) : (
              <AudioOutlined />
            )}
          </div>

          <div
            className='mr-[5px]  text-20 cursor-pointer'
            onClick={() => {
              onSending()
            }}
          >
            {isLoading || props.isResponse ? <LoadingOutlined /> : <AntSvgIcon type='sending' />}
          </div>
        </div>
      </div>
      {FileListNode()}
    </div>
  )
}

export default forwardRef<HTMLDivElement, Props>(ChatBox)
