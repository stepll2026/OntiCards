'use client';

import { useState, useEffect, useRef } from 'react';
import {
  Send,
  Sparkles,
  Bot,
  User,
  Code,
  Copy,
  Check,
  Loader2,
  Clock,
  ThumbsUp,
  ThumbsDown,
  RefreshCw,
  Table,
  X,
  ChevronDown,
  ChevronUp,
  BookOpen,
} from 'lucide-react';
import { queryByDatacards, type TermRewrite, type TermMatchedItem } from '@/api/query';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sql?: string;
  results?: any[];
  loading?: boolean;
  error?: string;
  term_rewrite?: TermRewrite;
}

const suggestedQuestions = [
  '查询销售额最高的产品',
  '统计本月新增用户数',
  '列出所有订单状态',
  '查询库存低于100的商品',
  '查看销售趋势',
];

const AskPage = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    const loadingMessage: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      loading: true,
    };
    setMessages((prev) => [...prev, loadingMessage]);

    try {
      const response = await queryByDatacards({ query: input });

      if (response.code === 200 && response.results) {
        const result = response.results[0];
        const aiResponse: Message = {
          id: (Date.now() + 2).toString(),
          role: 'assistant',
          content: result?.note || '查询完成',
          timestamp: new Date(),
          sql: result?.target_sql,
          results: result?.sql_result,
        };
        setMessages((prev) =>
          prev.map((msg) => (msg.id === loadingMessage.id ? aiResponse : msg)),
        );
      } else {
        const errorResponse: Message = {
          id: (Date.now() + 2).toString(),
          role: 'assistant',
          content: '查询失败: ' + (response.msg || '未知错误'),
          timestamp: new Date(),
          error: response.msg,
        };
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === loadingMessage.id ? errorResponse : msg,
          ),
        );
      }
    } catch (error: any) {
      const errorResponse: Message = {
        id: (Date.now() + 2).toString(),
        role: 'assistant',
        content: '请求失败: ' + (error.message || '网络错误'),
        timestamp: new Date(),
        error: error.message,
      };
      setMessages((prev) =>
        prev.map((msg) => (msg.id === loadingMessage.id ? errorResponse : msg)),
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleSuggestedQuestion = (question: string) => {
    setInput(question);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="h-[calc(100vh-180px)] flex flex-col">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold mb-1 text-slate-900">
          智能问数
        </h1>
        <p className="text-sm text-slate-500">使用自然语言查询您的数据库</p>
      </header>

      <div className="flex-1 bg-white rounded-[20px] border border-slate-200 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-full bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center mb-4">
                <Bot className="w-8 h-8 text-indigo-600" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900 mb-2">
                向数据提问
              </h3>
              <p className="text-sm text-slate-500 mb-6 max-w-md">
                我可以帮您查询数据库、探索表结构，并从数据中获得洞察
              </p>
              <div className="grid grid-cols-2 gap-3 max-w-2xl">
                {suggestedQuestions.map((question, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSuggestedQuestion(question)}
                    className="text-left px-4 py-3 bg-slate-50 hover:bg-indigo-50 hover:border-indigo-200 border border-slate-200 rounded-[12px] text-sm text-slate-600 hover:text-indigo-600 transition-all"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex gap-4 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}
                >
                  <div
                    className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                      message.role === 'user'
                        ? 'bg-indigo-600'
                        : 'bg-gradient-to-br from-indigo-100 to-purple-100'
                    }`}
                  >
                    {message.role === 'user' ? (
                      <User className="w-4 h-4 text-white" />
                    ) : (
                      <Bot className="w-4 h-4 text-indigo-600" />
                    )}
                  </div>

                  <div
                    className={`flex-1 max-w-[80%] ${message.role === 'user' ? 'text-right' : ''}`}
                  >
                    {message.loading ? (
                      <div className="flex items-center gap-2 text-slate-500">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span className="text-sm">思考中...</span>
                      </div>
                    ) : (
                      <>
                        <div
                          className={`prose prose-sm max-w-none ${
                            message.role === 'user'
                              ? 'bg-indigo-600 text-white'
                              : message.error
                                ? 'bg-red-50 text-red-800'
                                : 'bg-slate-50 text-slate-800'
                          } rounded-[16px] px-4 py-3 ${message.role === 'user' ? 'rounded-tr-sm' : 'rounded-tl-sm'}`}
                        >
                          <p className="whitespace-pre-wrap">{message.content}</p>
                        </div>

                        {/* 术语展开信息展示 */}
                        {message.role === 'assistant' && message.term_rewrite?.enabled && message.term_rewrite.matched_count > 0 && (
                          <div style={{ border: '1px solid #e0e7ff', borderRadius: '12px', overflow: 'hidden', backgroundColor: '#fafafa' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', backgroundColor: '#f5f3ff', borderBottom: '1px solid #e0e7ff' }}>
                              <Sparkles className="w-4 h-4 text-indigo-600" />
                              <span className="text-sm font-medium text-indigo-700">
                                术语展开
                              </span>
                              <span className="text-xs text-indigo-500">
                                匹配到 {message.term_rewrite.matched_count} 个术语
                              </span>
                            </div>
                            {message.term_rewrite.rewritten_question && (
                              <div style={{ padding: '8px 12px', borderBottom: '1px solid #f3f4f6' }}>
                                <div className="text-xs text-slate-500 mb-1">展开后的问题</div>
                                <div className="text-sm text-slate-700">
                                  {message.term_rewrite.rewritten_question}
                                </div>
                              </div>
                            )}
                            {message.term_rewrite.matched_terms && message.term_rewrite.matched_terms.length > 0 && (
                              <div style={{ padding: '8px 12px', maxHeight: '192px', overflowY: 'auto' }}>
                                <div style={{ display: 'grid', gap: '8px' }}>
                                  {message.term_rewrite.matched_terms.map((term: TermMatchedItem, index: number) => (
                                    <div
                                      key={index}
                                      style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', padding: '8px', backgroundColor: '#ffffff', borderWidth: '1px', borderStyle: 'solid', borderColor: '#e5e7eb', borderRadius: '8px', boxSizing: 'border-box' }}
                                    >
                                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginTop: '2px', flexShrink: 0, backgroundColor: 'transparent' }}>
                                        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
                                        <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
                                      </svg>
                                      <div style={{ flex: 1, minWidth: 0 }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                          <span className="text-sm font-medium text-indigo-700">
                                            {term.term_name}
                                          </span>
                                          <span className="text-xs text-slate-400">
                                            ({term.matched_name})
                                          </span>
                                          <span style={{ padding: '2px 6px', backgroundColor: '#f3f4f6', borderRadius: '4px', fontSize: '12px', color: '#6b7280' }}>
                                            {term.library_name}
                                          </span>
                                        </div>
                                        <div className="text-xs text-slate-500 mt-1">
                                          {term.term_definition}
                                        </div>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        )}

                        {/* 术语展开未匹配时的友好提示 */}
                        {message.role === 'assistant' && message.term_rewrite?.enabled && message.term_rewrite.matched_count === 0 && (
                          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', marginTop: '8px', padding: '6px 12px', backgroundColor: '#fef3c7', border: '1px solid #fcd34d', borderRadius: '8px' }}>
                            <Sparkles className="w-4 h-4 text-amber-500" />
                            <span className="text-xs text-amber-700">
                              暂未匹配到相关术语，或术语库功能未启用
                            </span>
                          </div>
                        )}

                        {message.sql && (
                          <div className="mt-3">
                            <div className="flex items-center justify-between px-3 py-2 bg-slate-900 rounded-[10px] text-xs">
                              <div className="flex items-center gap-2 text-slate-400">
                                <Code className="w-3 h-3" />
                                <span className="font-mono">{message.sql}</span>
                              </div>
                              <button
                                onClick={() =>
                                  copyToClipboard(message.sql || '', message.id)
                                }
                                className="p-1.5 hover:bg-slate-800 rounded transition-colors"
                                title="复制SQL"
                              >
                                {copiedId === message.id ? (
                                  <Check className="w-3 h-3 text-green-400" />
                                ) : (
                                  <Copy className="w-3 h-3 text-slate-400" />
                                )}
                              </button>
                            </div>
                          </div>
                        )}

                        {message.results && message.results.length > 0 && (
                          <div className="mt-3 overflow-x-auto">
                            <table className="w-full text-xs border border-slate-200 rounded-[10px] overflow-hidden">
                              <thead className="bg-slate-50">
                                <tr>
                                  {Object.keys(message.results[0] || {}).map(
                                    (key) => (
                                      <th
                                        key={key}
                                        className="px-3 py-2 text-left font-medium text-slate-600 border-b"
                                      >
                                        {key}
                                      </th>
                                    ),
                                  )}
                                </tr>
                              </thead>
                              <tbody>
                                {message.results.slice(0, 5).map((row, idx) => (
                                  <tr
                                    key={idx}
                                    className="border-b last:border-0"
                                  >
                                    {Object.values(row).map((val: any, i) => (
                                      <td
                                        key={i}
                                        className="px-3 py-2 text-slate-600"
                                      >
                                        {String(val ?? '-')}
                                      </td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                            {message.results.length > 5 && (
                              <p className="text-xs text-slate-400 mt-2">
                                显示前5条，共{message.results.length}条结果
                              </p>
                            )}
                          </div>
                        )}

                        {message.role === 'assistant' &&
                          !message.loading &&
                          !message.error && (
                            <div className="flex items-center gap-2 mt-3">
                              <button
                                className="p-1.5 hover:bg-slate-100 rounded-lg"
                                title="好评"
                              >
                                <ThumbsUp className="w-4 h-4 text-slate-400 hover:text-green-500" />
                              </button>
                              <button
                                className="p-1.5 hover:bg-slate-100 rounded-lg"
                                title="差评"
                              >
                                <ThumbsDown className="w-4 h-4 text-slate-400 hover:text-red-500" />
                              </button>
                              <button
                                className="p-1.5 hover:bg-slate-100 rounded-lg"
                                title="重新生成"
                              >
                                <RefreshCw className="w-4 h-4 text-slate-400 hover:text-indigo-500" />
                              </button>
                            </div>
                          )}

                        <p className="text-xs text-slate-400 mt-2">
                          <Clock className="w-3 h-3 inline mr-1" />
                          {message.timestamp.toLocaleTimeString()}
                        </p>
                      </>
                    )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        <div className="border-t border-slate-200 p-4">
          <div className="relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="输入您的问题..."
              className="w-full px-4 py-3 pr-12 bg-slate-50 border border-slate-200 rounded-[16px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all resize-none"
              rows={1}
              style={{ minHeight: '48px', maxHeight: '120px' }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className={`absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-[12px] transition-all ${
                input.trim() && !isLoading
                  ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                  : 'bg-slate-200 text-slate-400 cursor-not-allowed'
              }`}
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
          <p className="text-xs text-slate-400 mt-2 text-center">
            <Sparkles className="w-3 h-3 inline mr-1" />
            由AI驱动。结果基于您的数据库架构生成。
          </p>
        </div>
      </div>
    </div>
  );
};

export default AskPage;

