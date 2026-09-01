import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import katex from 'rehype-katex'
import rehypeRaw from 'rehype-raw'
import gfm from 'remark-gfm'
import math from 'remark-math'
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism'
import styles from './ReactMarkdown.module.scss'

interface ReactMarkdownsProps {
  content?: string;
  className?: string;
  fontSize?: string;
}

export default function ReactMarkdowns({ content, className, fontSize }: ReactMarkdownsProps) {
  // 生成标题 id 的辅助函数
  const generateHeadingId = (text: string): string => {
    return text
      .toLowerCase()
      .replace(/[^\u4e00-\u9fa5a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-')
  }

  return content
    ? <ReactMarkdown
      components={{
        code({ node, className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '')
          return match
            ? (
              <SyntaxHighlighter style={tomorrow as { [key: string]: React.CSSProperties } | undefined} language={match[1]} PreTag='div' {...props}>
                {String(children).replace(/\n$/, '')}
              </SyntaxHighlighter>
            )
            : (
              <code className={className} {...props}>
                {children}
              </code>
            )
        },
        h1: ({ node, children, ...props }) => {
          const text = String(children)
          return <h1 id={generateHeadingId(text)} {...props}>{children}</h1>
        },
        h2: ({ node, children, ...props }) => {
          const text = String(children)
          return <h2 id={generateHeadingId(text)} {...props}>{children}</h2>
        },
        h3: ({ node, children, ...props }) => {
          const text = String(children)
          return <h3 id={generateHeadingId(text)} {...props}>{children}</h3>
        },
        h4: ({ node, children, ...props }) => {
          const text = String(children)
          return <h4 id={generateHeadingId(text)} {...props}>{children}</h4>
        },
      }}
      className={`${styles.container} ${className || ''}`}
      remarkPlugins={[gfm, math]}
      rehypePlugins={[rehypeRaw, katex]}
    >
      {String(content)}
    </ReactMarkdown>
    : <></>
}
