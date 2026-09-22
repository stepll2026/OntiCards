'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, Button, Collapse, Descriptions, Drawer, Empty, Input, Select, Space, Spin, Switch, Table, Tabs, Tag, Timeline, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useUserInfo } from '@/hooks'
import { getQueryHistoryDetail, getQueryHistoryList } from '@/api/queryHistory'
import type { QueryExecutionAttempt, QueryHistoryDetailData, QueryHistoryItem } from '@/api/queryHistory'
import { getSystemLogs } from '@/api/logCenter'
import type { SystemLogItem, SystemLogLevel } from '@/api/logCenter'

type ApiResponse<T> = { code: number; data: T; msg?: string; message?: string }
type QueryStatus = 'all' | 'success' | 'error' | 'timeout'
type Filters = { keyword: string; startDate: string; endDate: string; page: number; pageSize: number }
const initialFilters: Filters = { keyword: '', startDate: '', endDate: '', page: 1, pageSize: 20 }

// A request can finish after the user changes filters/tabs or closes a drawer.
// Keep its result scoped to its original key and ignore superseded responses.
function useLogRequest<T>(enabled: boolean, key: string, request: () => Promise<ApiResponse<T>>, refresh: number, autoRefresh = false) {
  const [result, setResult] = useState<{ key: string; data: T } | null>(null)
  const [error, setError] = useState<{ key: string; text: string } | null>(null)
  const [loading, setLoading] = useState(false)
  const sequence = useRef(0)

  useEffect(() => {
    let cancelled = false
    let inFlight = false
    const generation = ++sequence.current
    if (!enabled) {
      setLoading(false)
      return
    }
    setResult(null)
    setError(null)
    const load = async () => {
      if (inFlight) return
      inFlight = true
      setLoading(true)
      setError(null)
      try {
        const response = await request()
        if (cancelled || generation !== sequence.current) return
        if (response.code !== 200 || !response.data) {
          setResult(null)
          setError({ key, text: response.msg || response.message || '读取日志失败，请重试' })
          return
        }
        setResult({ key, data: response.data })
      } catch {
        if (!cancelled && generation === sequence.current) {
          setResult(null)
          setError({ key, text: '读取日志失败，请检查网络或访问权限后重试' })
        }
      } finally {
        inFlight = false
        if (!cancelled && generation === sequence.current) setLoading(false)
      }
    }
    void load()
    const timer = autoRefresh ? window.setInterval(() => { void load() }, 10000) : undefined
    return () => {
      cancelled = true
      if (timer !== undefined) window.clearInterval(timer)
    }
  }, [enabled, key, request, refresh, autoRefresh])

  return {
    data: enabled && result?.key === key ? result.data : null,
    error: enabled && error?.key === key ? error.text : null,
    loading,
  }
}

function statusTag(status?: string) {
  const labels: Record<string, { color: string; text: string }> = {
    success: { color: 'success', text: '成功' },
    error: { color: 'error', text: '失败' },
    failed: { color: 'error', text: '失败' },
    timeout: { color: 'warning', text: '超时' },
    retry: { color: 'processing', text: '纠错中' },
    INFO: { color: 'processing', text: '信息' },
    WARNING: { color: 'warning', text: '警告' },
    ERROR: { color: 'error', text: '错误' },
  }
  const item = labels[status || '']
  return <Tag color={item?.color}>{item?.text || status || '未记录'}</Tag>
}

function formatTime(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

function duration(value?: number | null) {
  return typeof value === 'number' ? `${value.toLocaleString()} ms` : '—'
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    message.success('已复制')
  } catch {
    message.error('复制失败，请手动选择文本复制')
  }
}

function SqlBlock({ sql }: { sql?: string | null }) {
  if (!sql) return <span style={{ color: 'rgb(var(--theme-text-muted))' }}>未记录 SQL</span>
  return <div className="space-y-2">
    <Button size="small" onClick={() => { void copyText(sql) }}>复制 SQL</Button>
    <pre className="overflow-auto rounded-lg p-3 text-xs whitespace-pre-wrap break-words" style={{ maxHeight: 360, background: 'rgb(var(--theme-bg-tertiary))', color: 'rgb(var(--theme-text))' }}>{sql}</pre>
  </div>
}

const stageLabels: Record<string, string> = {
  generation: '生成 SQL', generate: '生成 SQL', validation: '校验 SQL', validate: '校验 SQL',
  execution: '执行 SQL', execute: '执行 SQL', retry: '模型纠错', correction: '模型纠错',
  model: '模型调用', result: '执行结果',
}

function AttemptContent({ attempt }: { attempt: QueryExecutionAttempt }) {
  return <div className="space-y-2 pb-2">
    <Space wrap>
      <strong>{attempt.attempt === 0 ? '首次尝试' : `第 ${attempt.attempt} 次纠错`}</strong>
      <span>{stageLabels[attempt.stage] || attempt.stage || '未记录阶段'}</span>
      {statusTag(attempt.status)}
      <span className="text-xs" style={{ color: 'rgb(var(--theme-text-muted))' }}>{formatTime(attempt.created_at)} · {duration(attempt.duration_ms)}</span>
    </Space>
    {attempt.error_code && <div><Tag>{attempt.error_code}</Tag></div>}
    {attempt.message && <p className="whitespace-pre-wrap break-words text-sm">{attempt.message}</p>}
    {attempt.sql && <Collapse size="small" items={[{ key: 'sql', label: '本次 SQL', children: <SqlBlock sql={attempt.sql} /> }]} />}
  </div>
}

function QueryDetail({ detail }: { detail: QueryHistoryDetailData }) {
  const logs = detail.execution_logs || []
  const sqls = detail.cluster_sqls || []
  return <div className="space-y-6">
    {detail.error_message && <Alert type="error" showIcon message="查询失败原因" description={<span className="whitespace-pre-wrap break-words">{detail.error_message}</span>} />}
    <Descriptions bordered size="small" column={1} items={[
      { key: 'question', label: '问题', children: <span className="whitespace-pre-wrap break-words">{detail.question}</span> },
      { key: 'id', label: '查询 ID', children: detail.id },
      { key: 'status', label: '状态', children: statusTag(detail.status) },
      { key: 'created', label: '时间', children: formatTime(detail.created_at) },
      { key: 'sources', label: '数据源', children: (detail.source_datasource_names?.length ? detail.source_datasource_names : detail.datasource_names)?.join('、') || '—' },
      { key: 'tables', label: '数据表', children: detail.table_names?.join('、') || '—' },
      { key: 'results', label: '结果行数', children: detail.result?.result_count ?? '—' },
    ]} />
    <section>
      <h3 className="font-semibold mb-3">SQL</h3>
      {sqls.length ? <Collapse items={sqls.map((cluster, index) => ({
        key: `${index}`, label: cluster.datasource_names?.join('、') || `数据源 ${index + 1}`,
        children: <SqlBlock sql={cluster.sql} />,
      }))} /> : <SqlBlock sql={detail.sql} />}
    </section>
    <section>
      <h3 className="font-semibold mb-3">耗时与用量</h3>
      <Descriptions bordered size="small" column={{ xs: 1, sm: 2 }} items={[
        { key: 'total', label: '总耗时', children: duration(detail.performance?.total_duration_ms) },
        { key: 'vector', label: '向量检索', children: duration(detail.performance?.vector_search_ms) },
        { key: 'rerank', label: '重排序', children: duration(detail.performance?.rerank_ms) },
        { key: 'generate', label: '生成 SQL', children: duration(detail.performance?.llm_gen_sql_ms) },
        { key: 'execution', label: '执行 SQL', children: duration(detail.performance?.sql_execution_ms) },
        { key: 'fusion', label: '结果融合', children: duration(detail.performance?.fusion_ms) },
        { key: 'input', label: '输入 Token', children: detail.tokens?.llm_prompt_tokens?.toLocaleString() ?? '—' },
        { key: 'output', label: '输出 Token', children: detail.tokens?.llm_completion_tokens?.toLocaleString() ?? '—' },
        { key: 'tokens', label: '总 Token', children: detail.tokens?.total_tokens?.toLocaleString() ?? '—' },
      ]} />
    </section>
    <section>
      <h3 className="font-semibold mb-3">逐次纠错记录</h3>
      {logs.length ? <Collapse defaultActiveKey={['0']} items={logs.map((cluster, index) => ({
        key: `${index}`,
        label: <Space wrap><span>查询簇 {index + 1} · {cluster.db_type || '未知类型'}</span><Tag>纠错 {cluster.retry_count ?? 0} 次</Tag></Space>,
        children: <div className="space-y-4">
          <p className="text-sm break-words">数据表：{cluster.table_names?.join('、') || '—'}</p>
          {cluster.attempts?.length ? <Timeline items={cluster.attempts.map((attempt, attemptIndex) => ({
            key: `${attemptIndex}`,
            color: ['error', 'failed', 'timeout'].includes(attempt.status) ? 'red' : attempt.status === 'success' ? 'green' : 'blue',
            children: <AttemptContent attempt={attempt} />,
          }))} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="未记录纠错详情" />}
        </div>,
      }))} /> : <Alert type="info" showIcon message="未记录纠错详情" description="这条历史记录没有保存逐次执行信息，仍可查看已有 SQL 和错误原因。" />}
    </section>
  </div>
}

function DateFilters({ filters, onChange }: { filters: Filters; onChange: (patch: Partial<Filters>) => void }) {
  return <>
    <label className="flex items-center gap-2 text-sm"><span className="whitespace-nowrap">开始日期</span><Input aria-label="开始日期" type="date" value={filters.startDate} onChange={event => onChange({ startDate: event.target.value, page: 1 })} /></label>
    <label className="flex items-center gap-2 text-sm"><span className="whitespace-nowrap">结束日期</span><Input aria-label="结束日期" type="date" value={filters.endDate} onChange={event => onChange({ endDate: event.target.value, page: 1 })} /></label>
  </>
}

// Copy only the documented, server-sanitized fields, never an arbitrary API object.
function systemLogView(item: SystemLogItem) {
  return {
    id: item.id, created_at: item.created_at, level: item.level, event: item.event,
    message: item.message, request_id: item.request_id, method: item.method, path: item.path,
    status_code: item.status_code, duration_ms: item.duration_ms,
  }
}

export default function LogCenterPage() {
  const { userInfo, loading: userLoading } = useUserInfo()
  const userId = userInfo?.id || ''
  const isAdmin = userInfo?.role === 'admin'
  const [tab, setTab] = useState('query')
  const [queryFilters, setQueryFilters] = useState<Filters>(initialFilters)
  const [queryStatus, setQueryStatus] = useState<QueryStatus>('all')
  const [queryKeyword, setQueryKeyword] = useState('')
  const [systemFilters, setSystemFilters] = useState<Filters>(initialFilters)
  const [level, setLevel] = useState<SystemLogLevel>('all')
  const [systemKeyword, setSystemKeyword] = useState('')
  const [queryRefresh, setQueryRefresh] = useState(0)
  const [systemRefresh, setSystemRefresh] = useState(0)
  const [detailRefresh, setDetailRefresh] = useState(0)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [queryId, setQueryId] = useState<string | null>(null)
  const [selectedSystem, setSelectedSystem] = useState<SystemLogItem | null>(null)

  useEffect(() => {
    setQueryId(null)
    setSelectedSystem(null)
    setAutoRefresh(false)
  }, [userId, isAdmin])

  const invalidQueryDates = Boolean(queryFilters.startDate && queryFilters.endDate && queryFilters.startDate > queryFilters.endDate)
  const invalidSystemDates = Boolean(systemFilters.startDate && systemFilters.endDate && systemFilters.startDate > systemFilters.endDate)
  const queryKey = JSON.stringify([userId, queryFilters, queryStatus])
  const systemKey = JSON.stringify([userId, isAdmin, systemFilters, level])
  const detailKey = `${userId}:${queryId || ''}`
  const requestQueries = useCallback(() => getQueryHistoryList({
    user_id: userId, page: queryFilters.page, page_size: queryFilters.pageSize,
    keyword: queryFilters.keyword || undefined, status: queryStatus,
    start_date: queryFilters.startDate || undefined, end_date: queryFilters.endDate || undefined,
  }), [userId, queryFilters, queryStatus])
  const requestSystem = useCallback(() => getSystemLogs({
    page: systemFilters.page, page_size: systemFilters.pageSize, level,
    keyword: systemFilters.keyword || undefined,
    start_date: systemFilters.startDate || undefined, end_date: systemFilters.endDate || undefined,
  }), [systemFilters, level])
  const requestDetail = useCallback(() => getQueryHistoryDetail(queryId || '', userId), [queryId, userId])
  const queries = useLogRequest(Boolean(userId) && tab === 'query' && !invalidQueryDates, queryKey, requestQueries, queryRefresh)
  const system = useLogRequest(Boolean(userId) && isAdmin && tab === 'system' && !invalidSystemDates, systemKey, requestSystem, systemRefresh, autoRefresh)
  const detail = useLogRequest(Boolean(userId && queryId), detailKey, requestDetail, detailRefresh)

  const queryColumns: ColumnsType<QueryHistoryItem> = [
    { title: '时间', dataIndex: 'created_at', width: 180, render: formatTime },
    { title: '问题', dataIndex: 'question', width: 280, ellipsis: true },
    { title: '数据源', width: 180, ellipsis: true, render: (_, item) => (item.source_datasource_names?.length ? item.source_datasource_names : item.datasource_names)?.join('、') || '—' },
    { title: '状态', dataIndex: 'status', width: 90, render: statusTag },
    { title: '耗时', dataIndex: 'total_duration_ms', width: 120, render: duration },
    { title: '纠错次数', dataIndex: 'retry_count', width: 90, render: value => value ?? '未记录' },
    { title: '结果行数', dataIndex: 'result_count', width: 90 },
    { title: '错误原因', dataIndex: 'error_message', width: 220, ellipsis: true, render: value => value || '—' },
    { title: '操作', key: 'action', width: 80, fixed: 'right', render: (_, item) => <Button type="link" size="small" onClick={() => setQueryId(item.id)}>详情</Button> },
  ]
  const systemColumns: ColumnsType<SystemLogItem> = [
    { title: '时间', dataIndex: 'created_at', width: 180, render: formatTime },
    { title: '级别', dataIndex: 'level', width: 90, render: statusTag },
    { title: '事件', dataIndex: 'event', width: 150, ellipsis: true },
    { title: '消息', dataIndex: 'message', width: 280, ellipsis: true },
    { title: '请求', width: 210, ellipsis: true, render: (_, item) => [item.method, item.path].filter(Boolean).join(' ') || '—' },
    { title: '状态码', dataIndex: 'status_code', width: 90, render: value => value ?? '—' },
    { title: '耗时', dataIndex: 'duration_ms', width: 120, render: duration },
    { title: '操作', key: 'action', width: 80, fixed: 'right', render: (_, item) => <Button type="link" size="small" onClick={() => setSelectedSystem(systemLogView(item))}>详情</Button> },
  ]
  const patchQuery = (patch: Partial<Filters>) => setQueryFilters(previous => ({ ...previous, ...patch }))
  const patchSystem = (patch: Partial<Filters>) => setSystemFilters(previous => ({ ...previous, ...patch }))
  const resetQuery = () => { setQueryFilters(initialFilters); setQueryKeyword(''); setQueryStatus('all') }
  const resetSystem = () => { setSystemFilters(initialFilters); setSystemKeyword(''); setLevel('all') }

  if (userLoading && !userId) return <div className="py-16 text-center"><Spin tip="正在读取账户信息" /></div>
  if (!userId) return <Alert type="warning" showIcon message="请先登录后查看日志" />

  return <div className="space-y-5" style={{ color: 'rgb(var(--theme-text))' }}>
    <header>
      <h1 className="text-2xl font-semibold mb-2">日志中心</h1>
      <p className="text-sm" style={{ color: 'rgb(var(--theme-text-muted))' }}>查询日志仅展示当前账户的记录；系统日志仅管理员可见。</p>
    </header>
    <Tabs activeKey={tab} onChange={value => { setTab(value); setQueryId(null); setSelectedSystem(null) }} items={[
      { key: 'query', label: '查询日志', children: <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <Input.Search aria-label="搜索查询日志" placeholder="搜索问题、SQL 或错误信息" allowClear value={queryKeyword} onChange={event => setQueryKeyword(event.target.value)} onSearch={value => patchQuery({ keyword: value.trim(), page: 1 })} style={{ width: 280 }} />
          <Select aria-label="查询状态" value={queryStatus} onChange={value => { setQueryStatus(value); patchQuery({ page: 1 }) }} style={{ width: 130 }} options={[
            { value: 'all', label: '全部状态' }, { value: 'success', label: '成功' }, { value: 'error', label: '失败' }, { value: 'timeout', label: '超时' },
          ]} />
          <DateFilters filters={queryFilters} onChange={patchQuery} />
          <Button onClick={resetQuery}>重置</Button>
          <Button loading={queries.loading} onClick={() => setQueryRefresh(value => value + 1)}>刷新</Button>
        </div>
        {invalidQueryDates && <Alert type="warning" showIcon message="开始日期不能晚于结束日期" />}
        {queries.error && <Alert type="error" showIcon message={queries.error} action={<Button size="small" onClick={() => setQueryRefresh(value => value + 1)}>重试</Button>} />}
        <Table<QueryHistoryItem> rowKey="id" columns={queryColumns} dataSource={queries.data?.items || []} loading={queries.loading} scroll={{ x: 1330 }} size="middle"
          locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={queries.error ? '日志读取失败' : '暂无符合条件的查询日志'} /> }}
          pagination={{ current: queryFilters.page, pageSize: queryFilters.pageSize, total: queries.data?.total || 0, showSizeChanger: true, pageSizeOptions: [20, 50, 100], showTotal: total => `共 ${total} 条`, onChange: (page, pageSize) => patchQuery({ page: pageSize !== queryFilters.pageSize ? 1 : page, pageSize }) }} />
      </div> },
      { key: 'system', label: '系统日志', children: !isAdmin ? <Alert type="info" showIcon message="系统日志仅管理员可见" description="你可以在“查询日志”中查看当前账户的查询与纠错记录。" /> : <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <Input.Search aria-label="搜索系统日志" placeholder="搜索事件、消息或请求 ID" allowClear value={systemKeyword} onChange={event => setSystemKeyword(event.target.value)} onSearch={value => patchSystem({ keyword: value.trim(), page: 1 })} style={{ width: 280 }} />
          <Select aria-label="日志级别" value={level} onChange={value => { setLevel(value); patchSystem({ page: 1 }) }} style={{ width: 130 }} options={[
            { value: 'all', label: '全部级别' }, { value: 'INFO', label: '信息' }, { value: 'WARNING', label: '警告' }, { value: 'ERROR', label: '错误' },
          ]} />
          <DateFilters filters={systemFilters} onChange={patchSystem} />
          <Button onClick={resetSystem}>重置</Button>
          <Button loading={system.loading} onClick={() => setSystemRefresh(value => value + 1)}>刷新</Button>
          <label className="flex items-center gap-2 text-sm"><Switch aria-label="每十秒自动刷新" checked={autoRefresh} onChange={setAutoRefresh} />每 10 秒刷新</label>
        </div>
        <p className="text-xs" style={{ color: 'rgb(var(--theme-text-muted))' }}>仅展示服务端提供的脱敏日志，可在详情中复制单条记录。</p>
        {invalidSystemDates && <Alert type="warning" showIcon message="开始日期不能晚于结束日期" />}
        {system.data?.truncated && <Alert type="warning" showIcon message="仅显示保留范围内的日志" description="当前日志读取范围受限，可缩小日期或关键词范围定位记录。" />}
        {system.error && <Alert type="error" showIcon message={system.error} action={<Button size="small" onClick={() => setSystemRefresh(value => value + 1)}>重试</Button>} />}
        <Table<SystemLogItem> rowKey="id" columns={systemColumns} dataSource={system.data?.items || []} loading={system.loading} scroll={{ x: 1200 }} size="middle"
          locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={system.error ? '日志读取失败' : '暂无符合条件的系统日志'} /> }}
          pagination={{ current: systemFilters.page, pageSize: systemFilters.pageSize, total: system.data?.total || 0, showSizeChanger: true, pageSizeOptions: [20, 50, 100], showTotal: total => `共 ${total} 条`, onChange: (page, pageSize) => patchSystem({ page: pageSize !== systemFilters.pageSize ? 1 : page, pageSize }) }} />
      </div> },
    ]} />
    <Drawer title="查询日志详情" open={Boolean(queryId)} onClose={() => setQueryId(null)} width="min(900px, 100vw)" destroyOnClose>
      {detail.loading ? <div className="py-12 text-center"><Spin /></div> : detail.error ? <Alert type="error" showIcon message={detail.error} action={<Button size="small" onClick={() => setDetailRefresh(value => value + 1)}>重试</Button>} /> : detail.data ? <QueryDetail detail={detail.data} /> : <Empty description="暂无详情" />}
    </Drawer>
    <Drawer title="系统日志详情" open={Boolean(isAdmin && selectedSystem)} onClose={() => setSelectedSystem(null)} width="min(760px, 100vw)" destroyOnClose>
      {isAdmin && selectedSystem && <div className="space-y-4">
        <Descriptions bordered size="small" column={1} items={[
          { key: 'time', label: '时间', children: formatTime(selectedSystem.created_at) },
          { key: 'level', label: '级别', children: statusTag(selectedSystem.level) },
          { key: 'event', label: '事件', children: selectedSystem.event || '—' },
          { key: 'request', label: '请求 ID', children: selectedSystem.request_id || '—' },
          { key: 'path', label: '请求', children: [selectedSystem.method, selectedSystem.path].filter(Boolean).join(' ') || '—' },
          { key: 'status', label: '状态码', children: selectedSystem.status_code ?? '—' },
          { key: 'duration', label: '耗时', children: duration(selectedSystem.duration_ms) },
          { key: 'message', label: '消息', children: <span className="whitespace-pre-wrap break-words">{selectedSystem.message || '—'}</span> },
        ]} />
        <Button onClick={() => { void copyText(JSON.stringify(systemLogView(selectedSystem), null, 2)) }}>复制脱敏 JSON</Button>
        <pre className="overflow-auto rounded-lg p-3 text-xs whitespace-pre-wrap break-words" style={{ background: 'rgb(var(--theme-bg-tertiary))' }}>{JSON.stringify(systemLogView(selectedSystem), null, 2)}</pre>
      </div>}
    </Drawer>
  </div>
}
