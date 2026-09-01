'use client'
import React, { useState, useEffect, useMemo, useCallback, startTransition } from 'react'
import { Modal, Collapse } from 'antd'
import type { ChangelogItem } from '@/context/homeContext'
import ReactMarkdown from '@/components/reactMarkdown/ReactMarkdown'

interface ChangelogModalProps {
  visible: boolean
  onClose: () => void
  changelogList: ChangelogItem[]
  loading: boolean
  onOpen?: () => void
}

// 单条内容用 memo 避免展开时父组件重渲染导致重复解析
const ChangelogPanelContent = React.memo(({ contentMd }: { contentMd: string }) => (
  <div className="changelog-content px-4 py-3 text-sm text-gray-600 leading-relaxed">
    <ReactMarkdown content={contentMd} />
  </div>
))
ChangelogPanelContent.displayName = 'ChangelogPanelContent'

const ChangelogModal: React.FC<ChangelogModalProps> = ({
  visible,
  onClose,
  changelogList,
  loading,
  onOpen
}) => {
  const [activeKey, setActiveKey] = useState<string | string[]>([])

  const handleChange = useCallback((key: string | string[]) => {
    startTransition(() => setActiveKey(key))
  }, [])

  // 当弹窗打开时，重置为折叠状态并触发已读标记
  useEffect(() => {
    if (visible) {
      setActiveKey([])
      if (onOpen) {
        onOpen()
      }
    }
  }, [visible, onOpen])

  const collapseItems = useMemo(
    () =>
      changelogList.map((item) => ({
        key: item.id,
        label: (
          <div className="flex items-center justify-between pr-4">
            <div className="flex items-center gap-2.5">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-indigo-100 text-indigo-700 border border-indigo-200">
                {item.version}
              </span>
              <h3 className="text-sm font-medium changelog-modal-label">{item.title}</h3>
            </div>
            <span className="text-xs changelog-modal-date">
              {new Date(item.created_at).toLocaleDateString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit'
              }).replace(/\//g, '-')}
            </span>
          </div>
        ),
        children: <ChangelogPanelContent contentMd={item.content_md} />,
        className: 'mb-2.5 changelog-modal-item rounded-lg border border-gray-200 hover:border-indigo-300 hover:shadow-sm transition-all',
        style: { borderRadius: '8px' }
      })),
    [changelogList]
  )

  return (
    <>
      <style jsx global>{`
        .changelog-modal .ant-modal {
          top: 35% !important;
          transform: translateY(-20%) !important;
          padding-bottom: 0 !important;
        }
        
        .changelog-content h1,
        .changelog-content h2,
        .changelog-content h3,
        .changelog-content h4 {
          font-size: 0.9rem !important;
          font-weight: 600 !important;
          margin-top: 0.75rem !important;
          margin-bottom: 0.5rem !important;
          color: #374151 !important;
        }
        
        .changelog-content p {
          font-size: 0.875rem !important;
          line-height: 1.6 !important;
          margin-bottom: 0.5rem !important;
          color: #6b7280 !important;
        }
        
        .changelog-content ul,
        .changelog-content ol {
          font-size: 0.875rem !important;
          margin-top: 0.5rem !important;
          margin-bottom: 0.5rem !important;
          padding-left: 1.5rem !important;
        }
        
        .changelog-content li {
          margin-bottom: 0.25rem !important;
          color: #6b7280 !important;
          line-height: 1.5 !important;
        }
        
        .changelog-content code {
          font-size: 0.8rem !important;
          padding: 0.125rem 0.375rem !important;
          background-color: #f3f4f6 !important;
          border-radius: 0.25rem !important;
          color: #dc2626 !important;
        }
        
        .changelog-content pre {
          font-size: 0.8rem !important;
          padding: 0.75rem !important;
          background-color: #f9fafb !important;
          border-radius: 0.375rem !important;
          margin-top: 0.5rem !important;
          margin-bottom: 0.5rem !important;
          overflow-x: auto !important;
        }
        
        .changelog-content strong {
          font-weight: 600 !important;
          color: #374151 !important;
        }
        
        .changelog-content a {
          color: #4f46e5 !important;
          text-decoration: underline !important;
          font-size: 0.875rem !important;
        }
        
        .changelog-content blockquote {
          border-left: 3px solid #e5e7eb !important;
          padding-left: 0.75rem !important;
          margin: 0.5rem 0 !important;
          color: #6b7280 !important;
          font-style: italic !important;
        }
      `}</style>
    <Modal
      title={
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-indigo-600" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
          <span className="text-base font-medium">版本更新日志</span>
        </div>
      }
      open={visible}
      onCancel={onClose}
      footer={null}
      width={850}
      wrapClassName="changelog-modal"
      styles={{ body: { maxHeight: '65vh', overflowY: 'auto', padding: '20px' } }}
    >
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
          <span className="ml-3 text-gray-600">加载中...</span>
        </div>
      ) : changelogList.length > 0 ? (
        <Collapse
          accordion
          activeKey={activeKey}
          onChange={handleChange}
          className="bg-transparent border-0"
          expandIconPosition="end"
          items={collapseItems}
        />
      ) : (
        <div className="text-center py-12">
          <svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
          <p className="text-gray-500">暂无版本更新日志</p>
        </div>
      )}
    </Modal>
    </>
  )
}

export default ChangelogModal

