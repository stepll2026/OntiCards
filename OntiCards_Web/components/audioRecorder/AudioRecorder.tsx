'use client'
import { AudioOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import _ from 'lodash'
import { useEffect, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'
import RecordPlugin from 'wavesurfer.js/dist/plugins/record'
import { useClientTranslation } from '@/app/i18n/hooks'

type Props = {
  /** 触发录音 */
  onSetAudios?: (data: { audio: {}; blob: Blob }) => void
  onSetError?: (e: string) => void
}
let stream: MediaStream | null = null

const AudioRecorder = (props: Props) => {
  const { t } = useClientTranslation()
  const micRef = useRef(null)
  const [record, setRecord] = useState<any>(null)
  const [init, setInit] = useState(false)
  useEffect(() => {
    // 组件销毁时停止录音
    return () => {
      if (record) {
        // console.log(record);
        record.stopMic()
        record.destroy()
      }
    }
  }, [record])

  /**
   *
   *  初始化Wavesurfer-防抖
   */
  const initWavesurfer = _.debounce(
    () => {
      if (!micRef.current)
        return

      const _wavesurfer = WaveSurfer.create({
        container: micRef.current,
        waveColor: 'rgb(200, 0, 200)',
        progressColor: 'rgb(100, 0, 100)',
      })

      const _record = _wavesurfer.registerPlugin(RecordPlugin.create() as any)

      // 监听录音停止
      _record.on('record-end', async (blob: Blob) => {
        const arrayBuffer = await blob.arrayBuffer()
        const audioBuffer = await new AudioContext().decodeAudioData(arrayBuffer)
        const wavBuffer = encodeWAV(audioBuffer)
        const wavBlob = new Blob([wavBuffer], { type: 'audio/wav' })
        const recordedUrl = URL.createObjectURL(blob)
        const duration = await _record.getDuration(blob)
        const audio = {
          url: recordedUrl,
          type: blob.type.split(';')[0].split('/')[1] || 'webm',
          createdAt: dayjs().format(),
          duration,
        }
        // 回调父级页面获取音频
        props.onSetAudios && props.onSetAudios({ audio, blob: wavBlob })
      })
      // console.log(record);
      setRecord(_record)
      setInit(true)
    },
    500,
    {},
  )

  useEffect(() => {
    if (!micRef.current)
      return

    if (init)
      return

    initWavesurfer()
  }, [init, initWavesurfer, micRef])
  /**
   *
   * 初始化录音
   */
  const initRecord = async () => {
    try {
      const devices = await RecordPlugin.getAvailableAudioDevices()
      if (!devices.length) {
        props.onSetError && props.onSetError(t('audioError', 'chat'))
      }
      else {
        // 原生方法打开麦克风，未知原因用插件打开无法关闭
        stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        // 打开麦克风权限
        // record.startMic();
        // 开始录音
        record.startRecording()
      }
    }
    catch (error) {
      console.log(error)
      props.onSetError && props.onSetError(String(error))
    }
  }

  /**
   *
   * 监听录音实例是否创建成功
   */
  useEffect(() => {
    if (record)
      initRecord()

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [record])

  /**
   *
   * 停止录音
   */
  function onClose() {
    if (stream)
      stream.getTracks().forEach(track => track.stop())

    if (record.isRecording()) {
      record.stopRecording()
      record.stopMic()
    }
  }

  function encodeWAV(audioBuffer) {
    const numOfChan = audioBuffer.numberOfChannels
    const length = audioBuffer.length * numOfChan * 2 + 44
    const buffer = new ArrayBuffer(length)
    const view = new DataView(buffer)
    const channels = []
    const sampleRate = audioBuffer.sampleRate
    const sampleBits = 16

    let offset = 0

    // write WAVE header
    writeString(view, offset, 'RIFF'); offset += 4
    view.setUint32(offset, 36 + audioBuffer.length * numOfChan * 2, true); offset += 4
    writeString(view, offset, 'WAVE'); offset += 4
    writeString(view, offset, 'fmt '); offset += 4
    view.setUint32(offset, 16, true); offset += 4
    view.setUint16(offset, 1, true); offset += 2
    view.setUint16(offset, numOfChan, true); offset += 2
    view.setUint32(offset, sampleRate, true); offset += 4
    view.setUint32(offset, sampleRate * numOfChan * 2, true); offset += 4
    view.setUint16(offset, numOfChan * 2, true); offset += 2
    view.setUint16(offset, sampleBits, true); offset += 2
    writeString(view, offset, 'data'); offset += 4
    view.setUint32(offset, audioBuffer.length * numOfChan * 2, true); offset += 4

    // write interleaved data
    for (let i = 0; i < audioBuffer.numberOfChannels; i++)
      channels.push(audioBuffer.getChannelData(i))

    let sample
    for (let i = 0; i < audioBuffer.length; i++) {
      for (let channel = 0; channel < numOfChan; channel++) {
        sample = Math.max(-1, Math.min(1, channels[channel][i]))
        sample = (sample < 0 ? sample * 0x8000 : sample * 0x7FFF) | 0
        view.setInt16(offset, sample, true)
        offset += 2
      }
    }

    return buffer
  }

  function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++)
      view.setUint8(offset + i, string.charCodeAt(i))
  }

  return (
    <div className='flex justify-center items-center fixed w-screen h-screen top-0 left-0 z-[1000] bg-opacity-50 bg-[#000]'>
      <div className=' w-full h-[400px] flex flex-col justify-center items-center '>
        <div id='waveform' ref={micRef} className='mb-[20px] w-full'></div>
        <div className='relative w-[60px] h-[60px] flex justify-center items-center  mt-[20px] '>
          <div className='w-[50%] h-[50%]  pointer-events-none rounded-round animate-ping  shadow-red-3xl'></div>
          <div
            className='absolute w-full h-full top-0 left-0 flex items-center justify-center rounded-round bg-[#fff]  cursor-pointer shadow-red-xl'
            onClick={onClose}
          >
            <div className=' text-red-500 text-[30px]'>
              <AudioOutlined />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AudioRecorder
