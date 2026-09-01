'use client'
import { Modal, Tabs } from 'antd'
import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from '@/components/reactMarkdown/ReactMarkdown'

interface HelpModalProps {
  visible: boolean
  onClose: () => void
}

interface TocItem {
  id: string
  text: string
  level: number
}

const HelpModal: React.FC<HelpModalProps> = ({ visible, onClose }) => {
  const [quickStartContent, setQuickStartContent] = useState<string>('')
  const [productDocContent, setProductDocContent] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [quickStartToc, setQuickStartToc] = useState<TocItem[]>([])
  const [productDocToc, setProductDocToc] = useState<TocItem[]>([])
  const [activeSection, setActiveSection] = useState<string>('')
  const [currentTab, setCurrentTab] = useState<string>('quickstart')
  const quickStartContentRef = useRef<HTMLDivElement>(null)
  const productDocContentRef = useRef<HTMLDivElement>(null)
  const quickStartTocListRef = useRef<HTMLDivElement>(null)
  const productDocTocListRef = useRef<HTMLDivElement>(null)
  const intersectionObserverRef = useRef<IntersectionObserver | null>(null)
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const hasFetchedRef = useRef(false)

  useEffect(() => {
    if (visible && !hasFetchedRef.current) {
      hasFetchedRef.current = true
      fetchDocuments()
    }
    if (!visible) {
      hasFetchedRef.current = false
    }
    return () => {
      if (intersectionObserverRef.current) {
        intersectionObserverRef.current.disconnect()
      }
    }
  }, [visible])

  // 提取目录
  const extractToc = (content: string): TocItem[] => {
    const toc: TocItem[] = []
    // 移除可能的 BOM
    const cleanContent = content.replace(/^\uFEFF/, '')
    const lines = cleanContent.split('\n')
    
    lines.forEach((line) => {
      // 清理行首尾的空白字符和特殊字符
      const cleanLine = line.trim()
      const match = cleanLine.match(/^(#{1,4})\s+(.+)$/)
      if (match) {
        const level = match[1].length
        const text = match[2].trim()
        const id = text
          .toLowerCase()
          .replace(/[^\u4e00-\u9fa5a-z0-9\s-]/g, '')
          .replace(/\s+/g, '-')
        
        toc.push({ id, text, level })
      }
    })
    
    return toc
  }

  const fetchDocuments = async () => {
    setLoading(true)
    try {
      // 通过API读取文档内容
      const quickStartRes = await fetch('/api/help-docs?doc=quickstart')
      const quickStartData = await quickStartRes.json()
      const qsContent = quickStartData.content || ''
      setQuickStartContent(qsContent)
      const qsToc = extractToc(qsContent)
      setQuickStartToc(qsToc)

      const productDocRes = await fetch('/api/help-docs?doc=product')
      const productDocData = await productDocRes.json()
      const pdContent = productDocData.content || ''
      setProductDocContent(pdContent)
      const pdToc = extractToc(pdContent)
      setProductDocToc(pdToc)

      // 文档加载完成后设置滚动监听
      setTimeout(() => {
        setupIntersectionObserver(currentTab)
      }, 200)
    } catch (error) {
      console.error('加载文档失败:', error)
    } finally {
      setLoading(false)
    }
  }

  // 处理目录点击
  const handleTocClick = (id: string) => {
    const element = document.getElementById(id)
    const contentRef = currentTab === 'quickstart' ? quickStartContentRef : productDocContentRef
    
    if (element && contentRef.current) {
      const container = contentRef.current
      const elementTop = element.offsetTop
      const containerTop = container.offsetTop
      
      container.scrollTo({
        top: elementTop - containerTop - 20,
        behavior: 'smooth'
      })
      setActiveSection(id)
    }
  }

  // 处理标签页切换
  const handleTabChange = (key: string) => {
    setCurrentTab(key)
    setActiveSection('')
    setTimeout(() => {
      setupIntersectionObserver(key)
    }, 100)
  }

  // 设置 Intersection Observer 来监听标题元素
  const setupIntersectionObserver = (tab: string) => {
    if (intersectionObserverRef.current) {
      intersectionObserverRef.current.disconnect()
    }

    const contentRef = tab === 'quickstart' ? quickStartContentRef : productDocContentRef
    const tocListRef = tab === 'quickstart' ? quickStartTocListRef : productDocTocListRef

    if (!contentRef.current) return

    const headingElements = contentRef.current.querySelectorAll('h1, h2, h3, h4')

    if (headingElements.length === 0) return

    // 使用 Intersection Observer 检测哪些标题在视口中
    const observer = new IntersectionObserver(
      (entries) => {
        // 找到第一个进入视口的标题
        const visibleEntries = entries.filter(entry => entry.isIntersecting)

        if (visibleEntries.length > 0) {
          // 按 top 值排序，找到最上面的
          visibleEntries.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
          const topEntry = visibleEntries[0]
          const id = topEntry.target.id

          if (id && id !== activeSection) {
            setActiveSection(id)

            // 自动滚动目录列表到对应位置
            if (tocListRef.current) {
              const tocList = tocListRef.current
              const activeElement = tocList.querySelector(`[data-id="${id}"]`)
              if (activeElement) {
                const containerTop = tocList.scrollTop
                const containerHeight = tocList.clientHeight
                const elementTop = (activeElement as HTMLElement).offsetTop
                const elementHeight = (activeElement as HTMLElement).offsetHeight

                // 如果元素不在可视区域内，则滚动
                if (elementTop < containerTop || elementTop + elementHeight > containerTop + containerHeight) {
                  tocList.scrollTo({
                    top: elementTop - containerHeight / 3,
                    behavior: 'smooth'
                  })
                }
              }
            }
          }
        }
      },
      {
        root: contentRef.current,
        rootMargin: '-10% 0px -80% 0px',
        threshold: 0
      }
    )

    headingElements.forEach(element => {
      if (element.id) {
        observer.observe(element)
      }
    })

    intersectionObserverRef.current = observer
  }

  // 内容区域滚动时检测当前章节 (使用 scrollTop 计算，更稳定)
  const handleContentScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const container = e.currentTarget
    if (!container) return

    // 延迟执行，避免频繁触发
    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current)
    }

    scrollTimeoutRef.current = setTimeout(() => {
      const headings = container.querySelectorAll('h1, h2, h3, h4')
      const containerScrollTop = container.scrollTop

      let currentHeading: Element | null = null

      headings.forEach((heading) => {
        const offsetTop = (heading as HTMLElement).offsetTop
        if (offsetTop <= containerScrollTop + 150) {
          currentHeading = heading
        }
      })

      // 如果没找到，使用第一个可见的标题
      if (!currentHeading && headings.length > 0) {
        currentHeading = headings[0]
      }

      if (currentHeading && currentHeading.id) {
        setActiveSection(currentHeading.id)

        // 自动滚动目录到对应位置
        const tocListRef = currentTab === 'quickstart' ? quickStartTocListRef : productDocTocListRef
        if (tocListRef.current) {
          const tocList = tocListRef.current
          const activeElement = tocList.querySelector(`[data-id="${currentHeading!.id}"]`)
          if (activeElement) {
            const containerTop = tocList.scrollTop
            const containerHeight = tocList.clientHeight
            const elementTop = (activeElement as HTMLElement).offsetTop
            const elementHeight = (activeElement as HTMLElement).offsetHeight

            // 如果元素不在可视区域内，则滚动
            if (elementTop < containerTop || elementTop + elementHeight > containerTop + containerHeight) {
              tocList.scrollTo({
                top: elementTop - containerHeight / 3,
                behavior: 'smooth'
              })
            }
          }
        }
      }
    }, 50)
  }

  // 渲染目录
  const renderToc = (toc: TocItem[], tab: string) => {
    if (toc.length === 0) return null

    const tocListRef = tab === 'quickstart' ? quickStartTocListRef : productDocTocListRef

    return (
      <div className="toc-sidebar">
        <div className="toc-title">目录</div>
        <div className="toc-list" ref={tocListRef}>
          {toc.map((item) => (
            <div
              key={item.id}
              data-id={item.id}
              className={`toc-item toc-level-${item.level} ${activeSection === item.id ? 'active' : ''}`}
              onClick={() => handleTocClick(item.id)}
              style={{ paddingLeft: `${(item.level - 1) * 12}px` }}
            >
              {item.text}
            </div>
          ))}
        </div>
      </div>
    )
  }

  // 为markdown内容添加id (已移至 ReactMarkdown 组件)

  // 加载状态组件
  const LoadingSpinner = () => (
    <div className="loading-container">
      <div className="spinner"></div>
      <p className="loading-text">正在加载文档...</p>
    </div>
  )

  const items = [
    {
      key: 'quickstart',
      label: (
        <span className="flex items-center gap-2">
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
          </svg>
          快速开始
        </span>
      ),
      children: loading ? (
        <LoadingSpinner />
      ) : (
        <div className="doc-layout">
          {quickStartToc.length > 0 && renderToc(quickStartToc, 'quickstart')}
          <div
            className={`help-content ${quickStartToc.length > 0 ? 'with-toc' : ''}`}
            ref={quickStartContentRef}
            onScroll={handleContentScroll}
          >
            <ReactMarkdown content={quickStartContent} />
          </div>
        </div>
      ),
    },
    {
      key: 'productdoc',
      label: (
        <span className="flex items-center gap-2">
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z" clipRule="evenodd" />
          </svg>
          说明文档
        </span>
      ),
      children: loading ? (
        <LoadingSpinner />
      ) : (
        <div className="doc-layout">
          {productDocToc.length > 0 && renderToc(productDocToc, 'productdoc')}
          <div
            className={`help-content ${productDocToc.length > 0 ? 'with-toc' : ''}`}
            ref={productDocContentRef}
            onScroll={handleContentScroll}
          >
            <ReactMarkdown content={productDocContent} />
          </div>
        </div>
      ),
    },
  ]

  return (
    <>
      <style jsx global>{`
        .help-modal .ant-modal {
          top: 20px !important;
          max-width: 95vw !important;
        }
        
        .help-modal .ant-modal-body {
          padding: 0 !important;
        }

        .help-modal .ant-tabs {
          height: 100%;
        }

        .help-modal .ant-tabs-nav {
          padding: 0 24px;
          margin-bottom: 0;
          background: #fafafa;
          border-bottom: 1px solid #e5e7eb;
        }

        .help-modal .ant-tabs-tab {
          padding: 12px 16px;
          font-weight: 500;
        }

        .help-modal .ant-tabs-content-holder {
          padding: 0 !important;
          overflow: hidden !important;
          max-height: calc(95vh - 120px);
        }

        /* 文档布局 */
        .doc-layout {
          display: flex;
          height: calc(95vh - 120px);
          overflow: hidden;
        }

        /* 目录侧边栏 */
        .toc-sidebar {
          width: 280px;
          flex-shrink: 0;
          border-right: 1px solid #e5e7eb;
          background: #fafafa;
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }

        .toc-title {
          font-size: 0.875rem;
          font-weight: 600;
          color: #6b7280;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          padding: 20px 20px 12px;
          border-bottom: 2px solid #e5e7eb;
          margin-bottom: 0;
          flex-shrink: 0;
          background: #fafafa;
        }

        .toc-list {
          padding: 12px 12px;
          overflow-y: auto;
          flex: 1;
        }

        .toc-item {
          font-size: 0.875rem;
          color: #4b5563;
          padding: 8px 12px;
          margin: 2px 0;
          cursor: pointer;
          border-radius: 6px;
          transition: all 0.2s;
          line-height: 1.4;
        }

        .toc-item:hover {
          background: #e0e7ff;
          color: #4f46e5;
        }

        .toc-item.active {
          background: #4f46e5;
          color: white;
          font-weight: 500;
        }

        .toc-level-1 {
          font-weight: 600;
        }

        .toc-level-2 {
          font-size: 0.8125rem;
        }

        .toc-level-3 {
          font-size: 0.8125rem;
          color: #6b7280;
        }

        .toc-level-4 {
          font-size: 0.75rem;
          color: #9ca3af;
        }

        /* 内容区域 */
        .help-content {
          flex: 1;
          overflow-y: auto;
          padding: 24px 32px;
        }

        .help-content.with-toc {
          padding: 24px 40px;
        }
        
        .help-content h1 {
          font-size: 1.875rem !important;
          font-weight: 700 !important;
          margin-top: 1.5rem !important;
          margin-bottom: 1rem !important;
          color: #111827 !important;
          border-bottom: 2px solid #e5e7eb !important;
          padding-bottom: 0.5rem !important;
        }
        
        .help-content h2 {
          font-size: 1.5rem !important;
          font-weight: 600 !important;
          margin-top: 2rem !important;
          margin-bottom: 0.75rem !important;
          color: #1f2937 !important;
          border-bottom: 1px solid #e5e7eb !important;
          padding-bottom: 0.375rem !important;
        }
        
        .help-content h3 {
          font-size: 1.25rem !important;
          font-weight: 600 !important;
          margin-top: 1.5rem !important;
          margin-bottom: 0.625rem !important;
          color: #374151 !important;
        }
        
        .help-content h4 {
          font-size: 1.125rem !important;
          font-weight: 600 !important;
          margin-top: 1.25rem !important;
          margin-bottom: 0.5rem !important;
          color: #4b5563 !important;
        }
        
        .help-content p {
          font-size: 0.9375rem !important;
          line-height: 1.75 !important;
          margin-bottom: 1rem !important;
          color: #4b5563 !important;
        }
        
        .help-content ul,
        .help-content ol {
          font-size: 0.9375rem !important;
          margin-top: 0.75rem !important;
          margin-bottom: 1rem !important;
          padding-left: 2rem !important;
        }
        
        .help-content li {
          margin-bottom: 0.5rem !important;
          color: #4b5563 !important;
          line-height: 1.625 !important;
        }

        .help-content li > ul,
        .help-content li > ol {
          margin-top: 0.5rem !important;
          margin-bottom: 0.5rem !important;
        }
        
        .help-content code {
          font-size: 0.875rem !important;
          padding: 0.125rem 0.375rem !important;
          background-color: #f3f4f6 !important;
          border: 1px solid #e5e7eb !important;
          border-radius: 0.25rem !important;
          color: #dc2626 !important;
          font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace !important;
        }
        
        .help-content pre {
          font-size: 0.875rem !important;
          padding: 1rem !important;
          background-color: #1f2937 !important;
          border-radius: 0.5rem !important;
          margin-top: 0.75rem !important;
          margin-bottom: 1rem !important;
          overflow-x: auto !important;
          border: 1px solid #374151 !important;
        }

        .help-content pre code {
          background: none !important;
          border: none !important;
          padding: 0 !important;
          color: #e5e7eb !important;
        }
        
        .help-content strong {
          font-weight: 600 !important;
          color: #111827 !important;
        }
        
        .help-content a {
          color: #4f46e5 !important;
          text-decoration: none !important;
          border-bottom: 1px solid #c7d2fe !important;
          transition: all 0.2s !important;
        }

        .help-content a:hover {
          color: #4338ca !important;
          border-bottom-color: #4f46e5 !important;
        }
        
        .help-content blockquote {
          border-left: 4px solid #6366f1 !important;
          padding-left: 1rem !important;
          padding-top: 0.25rem !important;
          padding-bottom: 0.25rem !important;
          margin: 1rem 0 !important;
          background-color: #f9fafb !important;
          color: #4b5563 !important;
        }

        .help-content table {
          width: 100% !important;
          border-collapse: collapse !important;
          margin: 1rem 0 !important;
          font-size: 0.875rem !important;
        }

        .help-content table th {
          background-color: #f9fafb !important;
          border: 1px solid #e5e7eb !important;
          padding: 0.625rem !important;
          text-align: left !important;
          font-weight: 600 !important;
          color: #374151 !important;
        }

        .help-content table td {
          border: 1px solid #e5e7eb !important;
          padding: 0.625rem !important;
          color: #4b5563 !important;
        }

        .help-content table tr:nth-child(even) {
          background-color: #fafafa !important;
        }

        .help-content hr {
          margin: 2rem 0 !important;
          border: none !important;
          border-top: 2px solid #e5e7eb !important;
        }

        .help-content img {
          max-width: 100% !important;
          height: auto !important;
          border-radius: 0.5rem !important;
          margin: 1rem 0 !important;
        }

        /* 加载动画样式 */
        .loading-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: calc(95vh - 120px);
          background: #fafafa;
        }

        .spinner {
          width: 48px;
          height: 48px;
          border: 4px solid #e5e7eb;
          border-top-color: #4f46e5;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }

        .loading-text {
          margin-top: 16px;
          font-size: 0.9375rem;
          color: #6b7280;
          font-weight: 500;
        }
      `}</style>
      <Modal
        title={
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-indigo-600" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
            </svg>
            <span className="text-base font-medium">帮助文档</span>
          </div>
        }
        open={visible}
        onCancel={onClose}
        footer={null}
        width={1400}
        wrapClassName="help-modal"
        styles={{ body: { maxHeight: '95vh', overflowY: 'hidden' } }}
      >
        <Tabs 
          defaultActiveKey="quickstart" 
          items={items}
          onChange={handleTabChange}
        />
      </Modal>
    </>
  )
}

export default HelpModal

