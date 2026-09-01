'use client';

import { useState, useEffect } from 'react';
import {
  FileText,
  Search,
  Loader2,
  Calendar,
  Eye,
  EyeOff,
} from 'lucide-react';
import { getChangelog, ChangelogItem } from '@/api/changeLog';
import ReactMarkdown from '@/components/reactMarkdown/ReactMarkdown';

const ChangelogPage = () => {
  const [logs, setLogs] = useState<ChangelogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLog, setSelectedLog] = useState<ChangelogItem | null>(null);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const res = await getChangelog();
      if (res.code === 200 && Array.isArray(res.data)) {
        setLogs(res.data);
      }
    } catch (e) {
      console.error('获取更新日志失败', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const filteredLogs = logs.filter((log) =>
    log.version?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    log.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    log.content_md?.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold mb-1 text-slate-900">
            更新日志
          </h1>
          <p className="text-sm text-slate-500">
            查看系统版本更新和功能介绍
          </p>
        </div>
      </header>

      {/* 搜索 */}
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
        <input
          type="text"
          placeholder="搜索版本号或内容..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-12 pr-4 py-3 bg-white border border-slate-200 rounded-[16px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
        />
      </div>

      {/* 内容区域 */}
      <div className="grid grid-cols-3 gap-6">
        {/* 左侧列表 */}
        <div className="col-span-1 space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
            </div>
          ) : filteredLogs.length === 0 ? (
            <div className="bg-white rounded-[20px] border border-slate-200 p-8 text-center">
              <FileText className="w-12 h-12 text-slate-300 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-slate-900 mb-2">
                暂无更新日志
              </h3>
            </div>
          ) : (
            filteredLogs.map((log) => (
              <button
                key={log.id}
                onClick={() => setSelectedLog(log)}
                className={`w-full text-left p-4 rounded-[16px] border transition-all ${
                  selectedLog?.id === log.id
                    ? 'bg-indigo-50 border-indigo-200 shadow-sm'
                    : 'bg-white border-slate-200 hover:border-indigo-200 hover:shadow-sm'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="px-2.5 py-1 bg-gradient-to-r from-indigo-500 to-purple-500 text-white text-xs font-medium rounded-full">
                    v{log.version}
                  </span>
                  {log.status === 'hidden' ? (
                    <EyeOff className="w-4 h-4 text-slate-400" />
                  ) : (
                    <Eye className="w-4 h-4 text-slate-400" />
                  )}
                </div>
                <h4 className="font-medium text-slate-900 mb-1 line-clamp-2">
                  {log.title}
                </h4>
                <div className="flex items-center gap-1 text-xs text-slate-400">
                  <Calendar className="w-3 h-3" />
                  {formatDate(log.created_at)}
                </div>
              </button>
            ))
          )}
        </div>

        {/* 右侧详情 */}
        <div className="col-span-2">
          {selectedLog ? (
            <div className="bg-white rounded-[20px] border border-slate-200 p-6">
              <div className="flex items-center gap-3 mb-4">
                <span className="px-3 py-1.5 bg-gradient-to-r from-indigo-500 to-purple-500 text-white text-sm font-medium rounded-full">
                  v{selectedLog.version}
                </span>
                <span className="text-sm text-slate-500">
                  {formatDate(selectedLog.created_at)}
                </span>
              </div>

              <h2 className="text-xl font-semibold text-slate-900 mb-6">
                {selectedLog.title}
              </h2>

              <div className="prose prose-sm max-w-none text-slate-600">
                <ReactMarkdown content={selectedLog.content_md} />
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-[20px] border border-slate-200 p-12 text-center h-full flex flex-col items-center justify-center">
              <FileText className="w-16 h-16 text-slate-200 mb-4" />
              <h3 className="text-lg font-medium text-slate-400 mb-2">
                选择查看更新日志
              </h3>
              <p className="text-sm text-slate-300">
                点击左侧列表查看版本详情
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChangelogPage;

