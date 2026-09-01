'use client'

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useRouter } from 'next-nprogress-bar'
import {
  ArrowLeft,
  ArrowRight,
  Shield,
  Plus,
  RefreshCw,
  BookOpen,
  Loader2,
  Upload,
  ToggleLeft,
  ToggleRight,
  Trash2,
  Edit3,
  Library,
  ChevronDown,
  ChevronUp,
  Database,
  GitBranch,
  Sparkles,
  Copy,
  Check,
  Code2,
  MessageSquare,
} from 'lucide-react'
import { message, Modal, Input, Select, Tooltip } from 'antd'
import {
  getGovernanceLibraries,
  createGovernanceRule,
  getGovernanceRules,
  updateGovernanceRule,
  deleteGovernanceRule,
  deleteGovernanceLibrary,
  toggleGovernanceRule,
  getRuleTemplates,
  getRuleTemplatesGrouped,
  getTemplateDetail,
  importRulesFromTemplate,
  parseGovernanceRule,
  previewGovernanceRule,
  suggestGovernanceRules,
  getDatasourceTables,
  getDatasourceTableColumns,
  GovernanceRule,
  GovernanceRuleTemplate,
  GovernanceLibrary,
  GovernanceRuleCondition,
  GovernanceRuleParsePrimaryResult,
  GovernanceRuleParseCandidateItem,
  GovernanceRuleParseCandidates,
  GovernanceRuleParseResponseData,
  GovernanceRuleSuggestionItemV2,
  GovernanceRulePreviewPayload,
  GovernanceDatasourceTable,
  GovernanceDatasourceColumn,
  RuleCreateSource,
  RuleType,
  SeverityLevel,
  severityColors,
  getRuleDisplayName,
  getSeverityDisplayName,
  ParseStage,
  GovernanceRuleParseMultiConfig,
  GovernanceTemplateGroup,
  GovernanceTemplatesGroupedResponse,
} from '@/api/governance'
import { CreateLibraryModal } from '../CreateLibraryModal'

// 加载动画样式
const spinKeyframes = `
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
`

const getUrlParam = (key: string): string | null => {
  if (typeof window === 'undefined') return null
  const params = new URLSearchParams(window.location.search)
  return params.get(key)
}

const ruleTypeOptions = [
  { value: 'null_check', label: '空值检测' },
  { value: 'unique', label: '唯一性检测' },
  { value: 'format', label: '格式检测' },
  { value: 'threshold', label: '阈值检测' },
  { value: 'enum', label: '枚举检测' },
  { value: 'custom_sql', label: '自定义SQL' },
  { value: 'length_check', label: '长度检测' },
  { value: 'range_check', label: '范围检测' },
  { value: 'date_check', label: '日期检测' },
  { value: 'consistency_check', label: '一致性检测' },
  { value: 'freshness_check', label: '新鲜度检测' },
  { value: 'value_distribution', label: '值分布检测' },
  { value: 'composite', label: '复合规则' },
  { value: 'table_stats', label: '表级统计' },
  { value: 'multi_column_compare', label: '多列比对' },
]

const severityOptions = [
  { value: 'critical', label: '严重' },
  { value: 'warning', label: '警告' },
  { value: 'info', label: '信息' },
]

const EmptyStateCard = ({
  icon,
  title,
  description,
  buttonText,
  onButtonClick,
}: {
  icon: React.ReactNode
  title: string
  description: string
  buttonText?: string
  onButtonClick?: () => void
}) => (
  <div style={{ textAlign: 'center', padding: 32, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: 200 }}>
    <div style={{ color: 'rgb(var(--theme-text-muted))', opacity: 0.4 }}>
      {React.cloneElement(icon as React.ReactElement, { style: { width: 48, height: 48 } })}
    </div>
    <p style={{ fontWeight: 500, marginTop: 12, fontSize: 15, color: 'rgb(var(--theme-text))' }}>{title}</p>
    <p style={{ fontSize: 13, marginTop: 4, color: 'rgb(var(--theme-text-secondary))' }}>{description}</p>
    {buttonText && onButtonClick && (
      <button
        onClick={onButtonClick}
        style={{ marginTop: 16, display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8, fontSize: 14, fontWeight: 500, color: 'white', backgroundColor: 'rgb(var(--theme-primary))', border: 'none', cursor: 'pointer' }}
      >
        <Plus style={{ width: 14, height: 14 }} />
        {buttonText}
      </button>
    )}
  </div>
)

const LibraryCard = ({
  library,
  isSelected,
  onClick,
  onDelete,
}: {
  library: GovernanceLibrary
  isSelected: boolean
  onClick: () => void
  onDelete: () => void
}) => (
  <div
    onClick={onClick}
    style={{
      padding: 14,
      borderRadius: 12,
      border: `2px solid ${isSelected ? 'rgb(var(--theme-primary))' : 'rgb(var(--theme-border))'}`,
      backgroundColor: isSelected ? 'rgba(var(--theme-primary), 0.05)' : 'rgb(var(--theme-bg))',
      cursor: 'pointer',
      transition: 'all 0.2s ease',
    }}
  >
    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <h3 style={{ fontWeight: 600, fontSize: 14, color: 'rgb(var(--theme-text))', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{library.name}</h3>
        {(library.connect_name || library.database_name || library.datasource_db_type || library.datasource?.connect_name || library.datasource?.database_name || library.datasource?.db_type) && (
          <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {(library.connect_name || library.datasource?.connect_name) && <span style={{ display: 'inline-flex', alignItems: 'center', padding: '2px 8px', borderRadius: 9999, fontSize: 11, fontWeight: 500, backgroundColor: 'rgba(24, 144, 255, 0.12)', color: '#1677ff' }}>数据源 · {library.connect_name || library.datasource?.connect_name}</span>}
            {(library.database_name || library.datasource?.database_name) && <span style={{ display: 'inline-flex', alignItems: 'center', padding: '2px 8px', borderRadius: 9999, fontSize: 11, fontWeight: 500, backgroundColor: 'rgba(82, 196, 26, 0.12)', color: '#389e0d' }}>数据库 · {library.database_name || library.datasource?.database_name}</span>}
            {(library.datasource_db_type || library.datasource?.db_type) && <span style={{ display: 'inline-flex', alignItems: 'center', padding: '2px 8px', borderRadius: 9999, fontSize: 11, fontWeight: 500, backgroundColor: 'rgba(250, 173, 20, 0.14)', color: '#d48806', textTransform: 'uppercase' }}>类型 · {library.datasource_db_type || library.datasource?.db_type}</span>}
          </div>
        )}
      </div>
      <button onClick={(e) => { e.stopPropagation(); onDelete() }} style={{ padding: 4, borderRadius: 6, backgroundColor: 'transparent', border: 'none', cursor: 'pointer', color: 'rgb(var(--theme-text-muted))', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Trash2 style={{ width: 14, height: 14 }} />
      </button>
    </div>
    <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', padding: '2px 8px', borderRadius: 6, fontSize: 12, backgroundColor: 'rgb(var(--theme-bg-secondary))', color: 'rgb(var(--theme-text-secondary))' }}>
        <Library style={{ width: 10, height: 10, marginRight: 3 }} />
        {library.rule_count || 0} 规则
      </span>
      <span style={{ display: 'inline-flex', alignItems: 'center', padding: '2px 8px', borderRadius: 9999, fontSize: 12, backgroundColor: library.status === 'active' ? 'rgba(82, 196, 26, 0.1)' : 'rgba(var(--theme-bg-tertiary), 0.5)', color: library.status === 'active' ? '#52c41a' : 'rgb(var(--theme-text-muted))' }}>
        {library.status === 'active' ? '● 运行中' : '○ 已停用'}
      </span>
    </div>
  </div>
)

const getCreateSourceDisplayName = (source?: RuleCreateSource) => {
  if (source === 'ai') return 'AI智能解析'
  if (source === 'template') return '模板导入'
  return '手动配置'
}

const ruleTypeAccentColors: Record<string, { background: string; color: string }> = {
  composite: { background: 'rgba(114, 46, 209, 0.12)', color: '#722ed1' },
  custom_sql: { background: 'rgba(24, 144, 255, 0.12)', color: '#1677ff' },
  null_check: { background: 'rgba(250, 173, 20, 0.14)', color: '#d48806' },
  unique: { background: 'rgba(82, 196, 26, 0.12)', color: '#389e0d' },
}

const getRuleTypeAccent = (ruleType?: string) => ruleTypeAccentColors[ruleType || ''] || { background: 'rgb(var(--theme-bg-secondary))', color: 'rgb(var(--theme-text-secondary))' }

const parseRuleConditions = (rule: GovernanceRule): GovernanceRuleCondition[] => {
  const rawConfig = rule.conditions_config
  if (!rawConfig) return []

  let parsedConfig: any = rawConfig
  if (typeof rawConfig === 'string') {
    try {
      parsedConfig = JSON.parse(rawConfig)
    } catch {
      return []
    }
  }

  if (Array.isArray(parsedConfig)) return parsedConfig as GovernanceRuleCondition[]
  if (Array.isArray(parsedConfig?.conditions)) return parsedConfig.conditions as GovernanceRuleCondition[]
  return []
}

const getRuleConditionMode = (rule: GovernanceRule): 'AND' | 'OR' | undefined => {
  const rawConfig = rule.conditions_config
  if (!rawConfig) return undefined

  let parsedConfig: any = rawConfig
  if (typeof rawConfig === 'string') {
    try {
      parsedConfig = JSON.parse(rawConfig)
    } catch {
      return undefined
    }
  }

  const mode = parsedConfig?.condition_mode
  return mode === 'AND' || mode === 'OR' ? mode : undefined
}

const getRuleScopeText = (rule: GovernanceRule) => {
  if (rule.target_table && rule.target_column) return `作用范围：${rule.target_table} 表 → ${rule.target_column} 列`
  if (rule.target_table) return `作用范围：${rule.target_table} 表`
  if (rule.scope_description) return `作用范围：${rule.scope_description}`
  return '作用范围：未设置'
}

const RuleCard = ({ rule, onEdit, onDelete, onToggle }: { rule: GovernanceRule; onEdit: () => void; onDelete: () => void; onToggle: () => void }) => {
  const [sqlExpanded, setSqlExpanded] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleCopySql = async () => {
    if (!rule.sql_text) return
    try {
      await navigator.clipboard.writeText(rule.sql_text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      message.error('复制失败')
    }
  }

  const ruleTypeAccent = getRuleTypeAccent(rule.rule_type)
  const compositeConditions = rule.rule_type === 'composite' ? parseRuleConditions(rule) : []
  const conditionMode = rule.rule_type === 'composite' ? getRuleConditionMode(rule) : undefined
  const sourceText = rule.create_source_name || getCreateSourceDisplayName(rule.create_source)
  const severityText = getSeverityDisplayName(rule)
  const compositeConditionItems = compositeConditions.map((condition) => ({
    column: condition.column || '未命名列',
    condition: condition.condition || '未设置条件表达式',
  }))
  const singleConditionSummary = rule.condition_expr || '未设置条件表达式'
  // 复合规则：显示所有列
  const isCompositeWithColumns = rule.rule_type === 'composite' && compositeConditionItems.length > 0
  const columnsText = isCompositeWithColumns
    ? compositeConditionItems.map(item => item.column).filter(Boolean).join('、')
    : rule.target_column
  const scopeNode = rule.target_table && columnsText
    ? <span>作用范围：<span style={{ color: '#1677ff', fontWeight: 600 }}>{rule.target_table}</span><span> 表 → </span><span style={{ color: '#722ed1', fontWeight: 600 }}>{columnsText}</span><span> 列</span></span>
    : rule.target_table
      ? <span>作用范围：<span style={{ color: '#1677ff', fontWeight: 600 }}>{rule.target_table}</span><span> 表</span></span>
      : rule.scope_description
        ? <span>作用范围：<span style={{ color: 'rgb(var(--theme-text))', fontWeight: 500 }}>{rule.scope_description}</span></span>
        : '作用范围：未设置'

  return (
    <div style={{ padding: '12px 14px', borderRadius: 14, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))', boxShadow: '0 4px 14px rgba(15,23,42,0.035)' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flexWrap: 'wrap' }}>
            <h4 style={{ fontWeight: 600, fontSize: 14, lineHeight: 1.4, color: 'rgb(var(--theme-text))', margin: 0, minWidth: 0, maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{rule.rule_name}</h4>
            <span style={{ display: 'inline-flex', alignItems: 'center', padding: '2px 8px', borderRadius: 9999, fontSize: 12, fontWeight: 500, backgroundColor: ruleTypeAccent.background, color: ruleTypeAccent.color, flexShrink: 0 }}>{getRuleDisplayName(rule)}</span>
            <span style={{ width: 8, height: 8, borderRadius: 9999, backgroundColor: rule.enabled ? '#52c41a' : 'rgb(var(--theme-text-muted))', flexShrink: 0 }} />
          </div>
          <div style={{ marginTop: 7, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <span>程度</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', padding: '2px 8px', borderRadius: 9999, fontSize: 12, fontWeight: 500, backgroundColor: severityColors[rule.severity] ? `${severityColors[rule.severity]}15` : 'rgb(var(--theme-bg-secondary))', color: severityColors[rule.severity] || 'rgb(var(--theme-text-secondary))' }}>{severityText}</span>
            </span>
            <span style={{ color: 'rgb(var(--theme-border))' }}>•</span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <span>配置方式</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', padding: '2px 8px', borderRadius: 9999, fontSize: 12, fontWeight: 500, backgroundColor: 'rgba(82, 196, 26, 0.1)', color: '#389e0d' }}>{sourceText}</span>
            </span>
          </div>
          {rule.description && <p style={{ fontSize: 12, margin: '8px 0 0', color: 'rgb(var(--theme-text-secondary))', lineHeight: 1.45, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>描述：{rule.description}</p>}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 2, flexShrink: 0, marginTop: -2 }}>
          <button onClick={onToggle} title={rule.enabled ? '禁用规则' : '启用规则'} style={{ padding: 4, borderRadius: 8, backgroundColor: 'transparent', border: 'none', cursor: 'pointer', color: rule.enabled ? '#52c41a' : 'rgb(var(--theme-text-muted))', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {rule.enabled ? <ToggleRight style={{ width: 18, height: 18 }} /> : <ToggleLeft style={{ width: 18, height: 18 }} />}
          </button>
          <button onClick={onEdit} title="编辑规则" style={{ padding: 4, borderRadius: 8, backgroundColor: 'transparent', border: 'none', cursor: 'pointer', color: 'rgb(var(--theme-text-muted))', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Edit3 style={{ width: 14, height: 14 }} />
          </button>
          <button onClick={onDelete} title="删除规则" style={{ padding: 4, borderRadius: 8, backgroundColor: 'transparent', border: 'none', cursor: 'pointer', color: 'rgb(var(--theme-text-muted))', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Trash2 style={{ width: 14, height: 14 }} />
          </button>
        </div>
      </div>

      <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, minWidth: 0 }}>
          <Database style={{ width: 13, height: 13, flexShrink: 0 }} />
          <span style={{ color: 'rgb(var(--theme-text))' }}>{scopeNode}</span>
        </span>
      </div>

      <div style={{ marginTop: 10, display: 'flex', alignItems: 'flex-start', gap: 8, padding: '9px 10px', borderRadius: 10, backgroundColor: rule.rule_type === 'composite' ? 'rgba(114,46,209,0.055)' : 'rgb(var(--theme-bg-secondary))', border: rule.rule_type === 'composite' ? '1px solid rgba(114,46,209,0.08)' : '1px solid transparent' }}>
        {rule.rule_type === 'composite' ? <GitBranch style={{ width: 13, height: 13, color: '#722ed1', marginTop: 2, flexShrink: 0 }} /> : <Sparkles style={{ width: 13, height: 13, color: 'rgb(var(--theme-text-secondary))', marginTop: 2, flexShrink: 0 }} />}
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: rule.rule_type === 'composite' ? 8 : 0 }}>
            <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>{rule.rule_type === 'composite' ? '复合条件' : '条件表达式'}</span>
            {rule.rule_type === 'composite' && conditionMode && <span style={{ fontSize: 11, padding: '1px 6px', borderRadius: 9999, backgroundColor: 'rgba(114,46,209,0.12)', color: '#722ed1' }}>{conditionMode}</span>}
            {rule.rule_type !== 'composite' && <span style={{ fontSize: 12.5, color: 'rgb(var(--theme-text))', lineHeight: 1.5, wordBreak: 'break-word' }}>{singleConditionSummary}</span>}
          </div>
          {rule.rule_type === 'composite' ? (
            <div style={{ display: 'grid', gap: 8 }}>
              {compositeConditionItems.map((item, index) => (
                <div key={`${item.column}-${index}`} style={{ display: 'grid', gridTemplateColumns: 'minmax(180px, 240px) minmax(320px, 1fr)', columnGap: 28, alignItems: 'start', fontSize: 12.5, color: 'rgb(var(--theme-text))', lineHeight: 1.5 }}>
                  <div style={{ display: 'flex', alignItems: 'center', minWidth: 0 }}>
                    <span style={{ width: 28, flexShrink: 0, fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>列：</span>
                    <span style={{ color: '#722ed1', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.column}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', minWidth: 0 }}>
                    <span style={{ width: 78, flexShrink: 0, fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>条件表达式：</span>
                    <span style={{ minWidth: 0, wordBreak: 'break-word' }}>{item.condition}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      {rule.sql_text && (
        <div style={{ marginTop: 10 }}>
          <button
            onClick={() => setSqlExpanded(!sqlExpanded)}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 0',
              backgroundColor: 'transparent',
              border: 'none',
              cursor: 'pointer',
              textAlign: 'left',
            }}
          >
            <Code2 style={{ width: 13, height: 13, color: '#1677ff', flexShrink: 0 }} />
            <span style={{ fontSize: 12, fontWeight: 500, color: '#1677ff' }}>SQL 预览</span>
            {sqlExpanded ? (
              <ChevronUp style={{ width: 13, height: 13, color: 'rgb(var(--theme-text-muted))' }} />
            ) : (
              <ChevronDown style={{ width: 13, height: 13, color: 'rgb(var(--theme-text-muted))' }} />
            )}
          </button>

          {sqlExpanded && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
              <pre style={{
                flex: 1,
                margin: 0,
                padding: '10px 12px',
                borderRadius: 6,
                fontSize: 12,
                lineHeight: 1.5,
                color: 'rgb(var(--theme-text-secondary))',
                overflow: 'auto',
                fontFamily: "'Fira Code', 'Cascadia Code', 'Consolas', monospace",
                wordBreak: 'break-all',
                maxHeight: Math.min(Math.max((rule.sql_text?.split('\n').length || 1) * 24, 100), 400),
              }}>
                <code>{rule.sql_text}</code>
              </pre>
              <Tooltip title={copied ? '已复制' : '复制 SQL'}>
                <button
                  onClick={handleCopySql}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: 6,
                    borderRadius: 4,
                    border: 'none',
                    backgroundColor: 'transparent',
                    cursor: 'pointer',
                    color: copied ? '#52c41a' : 'rgb(var(--theme-text-muted))',
                    transition: 'all 0.2s ease',
                    flexShrink: 0,
                  }}
                >
                  {copied ? <Check style={{ width: 14, height: 14 }} /> : <Copy style={{ width: 14, height: 14 }} />}
                </button>
              </Tooltip>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function LibrariesPageContent({ lng }: { lng: string }) {
  const router = useRouter()

  const [libraries, setLibraries] = useState<GovernanceLibrary[]>([])
  const [selectedLibrary, setSelectedLibrary] = useState<GovernanceLibrary | null>(null)
  const [rules, setRules] = useState<GovernanceRule[]>([])
  const [allRules, setAllRules] = useState<GovernanceRule[]>([])
  const [ruleSourceFilter, setRuleSourceFilter] = useState<'all' | RuleCreateSource>('all')
  const [severityFilter, setSeverityFilter] = useState<'all' | SeverityLevel>('all')
  const [loading, setLoading] = useState(true)
  // 规则视图状态：'idle'未选择, 'loading'加载中, 'loaded'已加载, 'empty'无数据
  const [rulesViewStatus, setRulesViewStatus] = useState<'idle' | 'loading' | 'loaded' | 'empty'>('idle')
  const [libraryIdFromUrl, setLibraryIdFromUrl] = useState<string | null>(null)
  const isLibraryViewMode = !!libraryIdFromUrl

  useEffect(() => {
    const updateUrlParam = () => setLibraryIdFromUrl(getUrlParam('id'))
    updateUrlParam()
    window.addEventListener('popstate', updateUrlParam)
    return () => window.removeEventListener('popstate', updateUrlParam)
  }, [])

  const [libraryModalVisible, setLibraryModalVisible] = useState(false)
  const [ruleModalVisible, setRuleModalVisible] = useState(false)
  const [importModalVisible, setImportModalVisible] = useState(false)
  const [editingRule, setEditingRule] = useState<GovernanceRule | null>(null)
  const [editingLibrary, setEditingLibrary] = useState<GovernanceLibrary | null>(null)
  const [originalEditingRule, setOriginalEditingRule] = useState<GovernanceRule | null>(null)

  const emptyRuleForm = {
    rule_name: '',
    description: '',
    rule_type: 'null_check' as RuleType,
    severity: 'warning' as SeverityLevel,
    target_table: '',
    target_column: '',
    condition_expr: '',
    sql_text: '',
  }

  const [ruleForm, setRuleForm] = useState<{ rule_name: string; description: string; rule_type: RuleType; severity: SeverityLevel; target_table: string; target_column: string; condition_expr: string; sql_text: string }>(emptyRuleForm)
  const [templates, setTemplates] = useState<GovernanceRuleTemplate[]>([])
  const [selectedTemplateIds, setSelectedTemplateIds] = useState<string[]>([])
  const [ruleCreationMode, setRuleCreationMode] = useState<'manual' | 'ai' | 'template'>('manual')
  const [naturalLanguageInput, setNaturalLanguageInput] = useState('')
  const [parseLoading, setParseLoading] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [rulePreviewSql, setRulePreviewSql] = useState('')
  const [previewScope, setPreviewScope] = useState<'column' | 'table' | 'global' | ''>('')
  const [previewConfirmed, setPreviewConfirmed] = useState(false)
  const [showSqlPreview, setShowSqlPreview] = useState(false)
  const [parsedPrimaryResult, setParsedPrimaryResult] = useState<GovernanceRuleParsePrimaryResult | null>(null)
  const [parsedAlternatives, setParsedAlternatives] = useState<GovernanceRuleParsePrimaryResult[]>([])
  const [parsedConfidence, setParsedConfidence] = useState<number | null>(null)
  // 二阶段交互状态
  const [parseCandidates, setParseCandidates] = useState<GovernanceRuleParseCandidates | null>(null)
  const [parseNeedsConfirmation, setParseNeedsConfirmation] = useState(false)
  const [parseStage, setParseStage] = useState<ParseStage | ''>('')
  const [parseReasoning, setParseReasoning] = useState<string>('')
  // AI模式：追踪用户是否编辑了条件表达式或复合条件（编辑后必须重新预览）
  const [aiConditionEdited, setAiConditionEdited] = useState(false)
  // 多列候选模式下已选中的列
  const [selectedMultiColumns, setSelectedMultiColumns] = useState<string[]>([])
  // multi_preview 模式下的多规则配置
  const [multiRuleConfigs, setMultiRuleConfigs] = useState<GovernanceRuleParseMultiConfig[]>([])
  // multi_preview 模式下用户勾选的规则索引
  const [selectedRuleIndices, setSelectedRuleIndices] = useState<number[]>([])
  // 保存原始输入用于二次调用
  const [originalParseInput, setOriginalParseInput] = useState<{
    user_input: string;
    target_table: string;
    target_column: string;
    selected_table?: string
    target_columns?: string  // 新增：多列参数
  } | null>(null)
  // 新版规则建议数据 (LLM 模式)
  const [smartSuggestions, setSmartSuggestions] = useState<GovernanceRuleSuggestionItemV2[]>([])
  const [suggestionsSource, setSuggestionsSource] = useState<string>('')
  const [suggestionsCollapsed, setSuggestionsCollapsed] = useState(false)
  const [suggestionsLoading, setSuggestionsLoading] = useState(false)
  const [templateRuleId, setTemplateRuleId] = useState('')
  const [templateGroups, setTemplateGroups] = useState<GovernanceTemplateGroup[]>([])
  const [templatesLoading, setTemplatesLoading] = useState(false)
  const [selectedTemplateDetail, setSelectedTemplateDetail] = useState<GovernanceRuleTemplate | null>(null)
  const [compositeConditions, setCompositeConditions] = useState<GovernanceRuleCondition[]>([])
  const [availableTables, setAvailableTables] = useState<GovernanceDatasourceTable[]>([])
  const [tableOptionsLoading, setTableOptionsLoading] = useState(false)
  const [tableOptionsLoadedFor, setTableOptionsLoadedFor] = useState<string>('')
  const [availableColumnsMap, setAvailableColumnsMap] = useState<Record<string, GovernanceDatasourceColumn[]>>({})
  const [columnOptionsLoading, setColumnOptionsLoading] = useState(false)
  const [columnOptionsTable, setColumnOptionsTable] = useState<string>('')
  const defaultCompositeCondition: GovernanceRuleCondition = { column: '', condition: '', description: '' }
  const [conditionMode, setConditionMode] = useState<'AND' | 'OR'>('AND')
  const [importTargetTable, setImportTargetTable] = useState('')
  const [importTargetColumn, setImportTargetColumn] = useState('')
  const [importOverrideName, setImportOverrideName] = useState(true)
  const [importingTemplates, setImportingTemplates] = useState(false)
  const sqlTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const ruleModalScrollRef = useRef<HTMLDivElement | null>(null)

  const adjustSqlTextareaHeight = () => {
    const el = sqlTextareaRef.current
    if (!el) return
    try {
      el.style.height = 'auto'
      el.style.height = `${el.scrollHeight}px`
    } catch (e) {
      // Ignore errors
    }
  }

  const adjustSqlTextareaHeightLater = () => {
    setTimeout(() => adjustSqlTextareaHeight(), 50)
  }

  const getImportPreviewName = (template: GovernanceRuleTemplate) => {
    const baseName = template.template_name || template.name || template.id
    if (!importOverrideName) return baseName
    if (importTargetTable && importTargetColumn) return `${baseName}(${importTargetTable}.${importTargetColumn})`
    if (importTargetTable) return `${baseName}(${importTargetTable})`
    return baseName
  }

  const buildImportScopeHint = () => {
    if (!importTargetTable && !importTargetColumn) return '当前将导入通用规则'
    if (importTargetTable && !importTargetColumn) return `当前将导入到表 ${importTargetTable}`
    if (importTargetTable && importTargetColumn) return `当前将导入到列 ${importTargetTable}.${importTargetColumn}`
    return '当前作用域配置无效，请补充表名'
  }

  const getCurrentDatasourceId = () => selectedLibrary?.datasource_id || selectedLibrary?.datasource?.id || ''

  const normalizeTableName = (table?: GovernanceDatasourceTable | null) => table?.name || table?.table_name || ''

  const normalizeColumnName = (column?: GovernanceDatasourceColumn | null) => column?.name || column?.column_name || ''

  const normalizeColumnType = (column?: GovernanceDatasourceColumn | null) => column?.type || column?.data_type || ''

  const normalizeColumnNullable = (column?: GovernanceDatasourceColumn | null) => {
    if (typeof column?.nullable === 'boolean') return column.nullable
    if (typeof column?.is_nullable === 'boolean') return column.is_nullable
    return undefined
  }

  const normalizeColumnDefault = (column?: GovernanceDatasourceColumn | null) => column?.default ?? column?.default_value ?? null

  const normalizeColumnComment = (column?: GovernanceDatasourceColumn | null) => column?.comment || column?.description || ''

  const normalizeColumnPrimary = (column?: GovernanceDatasourceColumn | null) => Boolean(column?.is_primary || column?.is_primary_key)

  const getColumnOptionsForTable = (tableName: string) => availableColumnsMap[tableName] || []

  const getTableSelectOptions = () => availableTables.map((table) => {
    const tableName = normalizeTableName(table)
    const tableDescription = table.description || ''
    const tableType = table.type || ''
    const columnCount = typeof table.column_count === 'number' ? table.column_count : undefined

    const typeLabel = tableType === 'VIEW' ? '视图' : tableType === 'TABLE' ? '表' : tableType
    const typeColor = tableType === 'VIEW' ? '#7c3aed' : '#1677ff'
    const typeBg = tableType === 'VIEW' ? 'rgba(124,58,237,0.1)' : 'rgba(22,119,255,0.08)'

    return {
      value: tableName,
      label: (
        <div style={{ display: 'grid', gap: 6, padding: '4px 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 600, color: 'rgb(var(--theme-text))', lineHeight: 1.4 }}>{tableName}</span>
            {tableType && (
              <span style={{ fontSize: 12, color: typeColor, backgroundColor: typeBg, borderRadius: 9999, padding: '1px 8px', lineHeight: '18px' }}>
                {typeLabel}
              </span>
            )}
            {typeof columnCount === 'number' && (
              <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', backgroundColor: 'rgb(var(--theme-bg-secondary))', borderRadius: 9999, padding: '1px 8px', lineHeight: '18px' }}>
                {columnCount} 列
              </span>
            )}
          </div>
          {tableDescription && (
            <Tooltip title={tableDescription} placement="right" mouseEnterDelay={0.3}>
              <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', lineHeight: 1.5, overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', paddingLeft: 2 }}>
                {tableDescription}
              </div>
            </Tooltip>
          )}
        </div>
      ),
      title: tableName,
    }
  }).filter((item) => item.value)

  const getColumnSelectOptions = (tableName: string) => getColumnOptionsForTable(tableName).map((column) => {
    const columnName = normalizeColumnName(column)
    const columnType = normalizeColumnType(column)
    const columnNullable = normalizeColumnNullable(column)
    const columnDefault = normalizeColumnDefault(column)
    const columnComment = normalizeColumnComment(column)
    const isPrimary = normalizeColumnPrimary(column)

    return {
      value: columnName,
      label: (
        <div style={{ display: 'grid', gap: 6, padding: '4px 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 600, color: 'rgb(var(--theme-text))', lineHeight: 1.4 }}>{columnName}</span>
            {columnType && <span style={{ fontSize: 12, color: '#1677ff', backgroundColor: 'rgba(22,119,255,0.08)', borderRadius: 9999, padding: '1px 8px', lineHeight: '18px' }}>{columnType}</span>}
            {isPrimary && <span style={{ fontSize: 12, color: '#d48806', backgroundColor: 'rgba(250,173,20,0.12)', borderRadius: 9999, padding: '1px 8px', lineHeight: '18px' }}>主键</span>}
            {typeof columnNullable === 'boolean' && (
              <span style={{ fontSize: 12, color: columnNullable ? '#389e0d' : '#cf1322', backgroundColor: columnNullable ? 'rgba(82,196,26,0.1)' : 'rgba(255,85,68,0.1)', borderRadius: 9999, padding: '1px 8px', lineHeight: '18px' }}>{columnNullable ? '可为空' : '非空'}</span>
            )}
          </div>
          {columnComment && (
            <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', lineHeight: 1.5, wordBreak: 'break-word', paddingLeft: 2 }}>
              注释：{columnComment}
            </div>
          )}
          {columnDefault !== undefined && columnDefault !== null && (
            <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', lineHeight: 1.5, wordBreak: 'break-word', paddingLeft: 2 }}>
              默认值：{String(columnDefault)}
            </div>
          )}
        </div>
      ),
      title: columnName,
    }
  }).filter((item) => item.value)

  const ensureDatasourceTablesLoaded = async (force = false) => {
    const datasourceId = getCurrentDatasourceId()
    if (!datasourceId) return [] as GovernanceDatasourceTable[]
    if (!force && tableOptionsLoadedFor === datasourceId && availableTables.length > 0) return availableTables

    setTableOptionsLoading(true)
    try {
      const res = await getDatasourceTables(datasourceId)
      if (res.code === 200) {
        const tables = res.data.tables || []
        setAvailableTables(tables)
        setTableOptionsLoadedFor(datasourceId)
        return tables
      }
      message.error(res.msg || '获取数据表列表失败')
      return []
    } catch (error) {
      message.error('获取数据表列表失败')
      return []
    } finally {
      setTableOptionsLoading(false)
    }
  }

  const ensureTableColumnsLoaded = async (tableName: string, force = false) => {
    const datasourceId = getCurrentDatasourceId()
    const normalizedTableName = tableName.trim()
    if (!datasourceId || !normalizedTableName) return [] as GovernanceDatasourceColumn[]
    if (!force && availableColumnsMap[normalizedTableName]?.length) return availableColumnsMap[normalizedTableName]

    setColumnOptionsLoading(true)
    setColumnOptionsTable(normalizedTableName)
    try {
      const res = await getDatasourceTableColumns(datasourceId, normalizedTableName)
      if (res.code === 200) {
        const columns = res.data.columns || []
        setAvailableColumnsMap((prev) => ({ ...prev, [normalizedTableName]: columns }))
        return columns
      }
      message.error(res.msg || '获取字段列表失败')
      return []
    } catch (error) {
      message.error('获取字段列表失败')
      return []
    } finally {
      setColumnOptionsLoading(false)
      setColumnOptionsTable('')
    }
  }

  const resetRuleBuilderState = () => {
    setRuleForm(emptyRuleForm)
    setCompositeConditions([])
    setConditionMode('AND')
    setRulePreviewSql('')
    setPreviewScope('')
    setPreviewConfirmed(false)
    setShowSqlPreview(false)
    setNaturalLanguageInput('')
    setTemplateRuleId('')
    setSelectedTemplateDetail(null)
    setParsedPrimaryResult(null)
    setParsedAlternatives([])
    setParsedConfidence(null)
    setSmartSuggestions([])
    setSuggestionsCollapsed(false)
    // 清理二阶段交互状态
    setParseCandidates(null)
    setParseNeedsConfirmation(false)
    setParseStage('')
    setParseReasoning('')
    setOriginalParseInput(null)
    setOriginalEditingRule(null)
    setMultiRuleConfigs([])
    setSelectedRuleIndices([])
    setSelectedMultiColumns([])
  }

  const clearRulePreviewState = () => {
    setRulePreviewSql('')
    setPreviewScope('')
    setPreviewConfirmed(false)
    setShowSqlPreview(false)
    setMultiRuleConfigs([])
    setSelectedRuleIndices([])
    setSelectedMultiColumns([])
    setParseStage('')
    // 注意：不要在这里清空 selectedTemplateDetail，否则模板模式的步骤 2/3 会瞬间消失。
    // 模板选择状态应在 handleSwitchRuleMode/applyTemplateRule/resetRuleBuilderState 等显式入口里重置。
  }

  const applyParsedResultToForm = (parsed?: GovernanceRuleParsePrimaryResult | null) => {
    if (!parsed) return
    clearRulePreviewState()
    setRuleForm((prev) => ({
      ...prev,
      rule_type: parsed.rule_type as RuleType,
      target_table: parsed.target_table || '',
      target_column: parsed.target_column || '',
      condition_expr: parsed.condition_expr || '',
      severity: (parsed.severity as SeverityLevel) || prev.severity,
      description: prev.description,
    }))

    if (parsed.rule_type === 'composite' && parsed.conditions?.length) {
      setCompositeConditions(parsed.conditions)
      setConditionMode(parsed.condition_mode || 'AND')
      ensureCompositeConditionExists()
    } else {
      setCompositeConditions([])
      setConditionMode('AND')
    }
  }

  const buildSingleRulePreviewPayload = (): GovernanceRulePreviewPayload => {
    const normalizedConditions = compositeConditions.map((item) => ({ column: item.column.trim(), condition: item.condition.trim() })).filter((item) => item.column && item.condition)
    const isManualCompositeRule = ruleCreationMode === 'manual' && ruleForm.rule_type === 'composite'
    const isAiCompositeRule = ruleCreationMode === 'ai' && ruleForm.rule_type === 'composite'
    const createSource = getCurrentCreateSource()
    return {
      library_id: selectedLibrary?.id,
      rule_type: ruleForm.rule_type,
      target_table: ruleForm.target_table || undefined,
      target_column: isManualCompositeRule ? undefined : ruleForm.target_column || undefined,
      condition_expr: (isManualCompositeRule || isAiCompositeRule) ? undefined : ruleForm.condition_expr || undefined,
      conditions: (isManualCompositeRule || isAiCompositeRule) && normalizedConditions.length > 0 ? normalizedConditions : undefined,
      condition_mode: (isManualCompositeRule || isAiCompositeRule) && normalizedConditions.length > 0 ? conditionMode : undefined,
      db_type: selectedLibrary?.datasource_db_type || selectedLibrary?.datasource?.db_type,
      // Template mode specific
      template_id: createSource === 'template' ? templateRuleId : undefined,
    }
  }

  const getCurrentCreateSource = (): RuleCreateSource => {
    if (editingRule?.create_source) return editingRule.create_source
    return ruleCreationMode === 'ai' ? 'ai' : ruleCreationMode === 'template' ? 'template' : 'manual'
  }

  const buildCreatePayload = () => {
    const normalizedConditions = compositeConditions.map((item) => ({ ...item, column: item.column.trim(), condition: item.condition.trim(), description: item.description?.trim() || undefined })).filter((item) => item.column && item.condition)
    const createSource = getCurrentCreateSource()
    const isCompositeRule = createSource === 'manual' && ruleForm.rule_type === 'composite'
    const basePayload = {
      ...ruleForm,
      library_id: selectedLibrary?.id,
      target_table: ruleForm.target_table || null,
      condition_expr: ruleForm.condition_expr || undefined,
      conditions_config: undefined,
      conditions: isCompositeRule ? normalizedConditions : undefined,
      condition_mode: isCompositeRule && normalizedConditions.length > 1 ? conditionMode : undefined,
      create_source: createSource,
      sql_text: ruleForm.sql_text || undefined,
      // Template mode specific
      template_id: createSource === 'template' ? templateRuleId : undefined,
    }

    return {
      normalizedConditions,
      isCompositeRule,
      payload: isCompositeRule
        ? {
            ...basePayload,
            target_column: undefined,
          }
        : {
            ...basePayload,
            target_column: ruleForm.target_column || null,
          },
    }
  }

  const validateRuleForParse = () => {
    if (!selectedLibrary) {
      message.warning('请先选择一个规则库')
      return false
    }
    if (!ruleForm.rule_name.trim()) {
      message.warning('请输入规则名称')
      return false
    }
    if (!naturalLanguageInput.trim()) {
      message.warning('请输入自然语言规则描述')
      return false
    }
    // 目标表和目标列现在是可选的，不强制验证
    return true
  }

  const validateRuleForPreview = () => {
    if (!selectedLibrary) {
      message.warning('请先选择一个规则库')
      return false
    }
    const currentCreateSource = getCurrentCreateSource()

    if (currentCreateSource === 'template') {
      if (!templateRuleId) {
        message.warning('请先选择一个规则模板')
        return false
      }
      if (!ruleForm.target_table.trim()) {
        message.warning('请先选择目标表')
        return false
      }
      return true
    }

    const isManualCompositeRule = currentCreateSource === 'manual' && ruleForm.rule_type === 'composite'
    const isAiCompositeRule = currentCreateSource === 'ai' && editingRule && ruleForm.rule_type === 'composite'
    const existingRule = editingRule || null
    const targetTable = ruleForm.target_table.trim() || existingRule?.target_table?.trim() || ''
    const targetColumn = ruleForm.target_column.trim() || existingRule?.target_column?.trim() || ''
    if (!targetTable) {
      message.warning(currentCreateSource === 'manual' ? '手动专家模式下请先填写目标表名' : '请先填写目标表名')
      return false
    }
    if (currentCreateSource === 'manual' && !isManualCompositeRule && !targetColumn) {
      message.warning('手动专家模式下请先填写目标列名')
      return false
    }
    if (isManualCompositeRule || isAiCompositeRule) {
      const hasValidConditions = compositeConditions.some((item) => item.column.trim() && item.condition.trim())
      if (!hasValidConditions) {
        message.warning('复合规则预览请至少配置一条有效条件')
        return false
      }
      return true
    }
    const conditionExpr = ruleForm.condition_expr.trim() || existingRule?.condition_expr?.trim() || ''
    if (!conditionExpr) {
      message.warning(currentCreateSource === 'manual' ? '手动专家模式下请先填写条件表达式' : '请先填写条件表达式')
      return false
    }
    return true
  }

  const validateRuleForCreate = () => {
    if (!selectedLibrary) {
      message.warning('请先选择一个规则库')
      return false
    }
    const currentCreateSource = getCurrentCreateSource()

    // 自然语言模式验证
    if (currentCreateSource === 'ai') {
      if (!ruleForm.rule_name.trim()) {
        message.warning('请输入规则名称')
        return false
      }
      if (!parsedPrimaryResult) {
        message.warning('请先完成AI解析')
        return false
      }
      if (parseNeedsConfirmation) {
        message.warning('请先从候选列表中选择目标')
        return false
      }
      return true
    }

    // 手动模式和模板模式验证
    if (!ruleForm.rule_name.trim()) {
      message.warning('请输入规则名称')
      return false
    }

    // Template mode specific validation
    if (currentCreateSource === 'template') {
      if (!templateRuleId) {
        message.warning('请先选择一个规则模板')
        return false
      }
      if (!ruleForm.target_table.trim()) {
        message.warning('请先选择目标表')
        return false
      }
      // Template mode doesn't require target_column, but if target_column is provided, it replaces 'column' placeholder
      return true
    }

    // Manual mode validation
    const isManualCompositeRule = currentCreateSource === 'manual' && ruleForm.rule_type === 'composite'
    if (!ruleForm.target_table.trim()) {
      message.warning('手动专家模式下请先填写目标表名')
      return false
    }
    if (currentCreateSource === 'manual' && !isManualCompositeRule && !ruleForm.target_column.trim()) {
      message.warning('手动专家模式下请先填写目标列名')
      return false
    }
    const hasConditionExpr = !!ruleForm.condition_expr.trim()
    const hasConditions = compositeConditions.some((item) => item.column.trim() && item.condition.trim())
    if (currentCreateSource === 'manual' && !hasConditionExpr && !hasConditions) {
      message.warning('手动专家模式下请至少填写条件表达式或配置一条有效条件')
      return false
    }
    if (isManualCompositeRule && !hasConditions) {
      message.warning('复合规则至少需要配置一条有效条件')
      return false
    }
    return true
  }

  useEffect(() => {
    fetchLibraries()
  }, [])

  useEffect(() => {
    const handlePopState = () => window.location.reload()
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  const fetchLibraries = async () => {
    setLoading(true)
    try {
      const res = await getGovernanceLibraries({ page_size: 100 })
      if (res.code === 200) setLibraries(res.data.items)
    } catch (error) {
      message.error('获取规则库失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!libraryIdFromUrl) return
    const matchedLibrary = libraries.find((item) => item.id === libraryIdFromUrl)
    if (!matchedLibrary) return
    
    setSelectedLibrary(matchedLibrary)
    setRuleSourceFilter('all')
    setSeverityFilter('all')
    setAllRules([])
    setRules([])
    setRulesViewStatus('loading')
    
    // 延迟调用 API，确保状态更新先触发渲染
    setTimeout(() => {
      fetchRules(matchedLibrary.id)
    }, 0)
  }, [libraryIdFromUrl, libraries])

  useEffect(() => {
    if (!ruleModalVisible) return
    if (ruleCreationMode === 'manual' || (editingRule && ruleForm.sql_text)) {
      adjustSqlTextareaHeightLater()
    }
  }, [ruleModalVisible, ruleCreationMode, ruleForm.sql_text, editingRule])

  const fetchRules = async (libraryId: string) => {
    try {
      const res = await getGovernanceRules({ library_id: libraryId, page_size: 100 })
      if (res.code === 200) {
        const items = res.data.items
        setAllRules(items)
        setRules(items)
        // 根据数据量设置状态
        setRulesViewStatus(items.length === 0 ? 'empty' : 'loaded')
      } else {
        setAllRules([])
        setRules([])
        setRulesViewStatus('empty')
        message.error(res.msg || '获取规则失败')
      }
    } catch (error) {
      setAllRules([])
      setRules([])
      setRulesViewStatus('empty')
      message.error('获取规则失败')
    }
  }

  // 前端筛选规则
  const applyFilters = useCallback(() => {
    let filtered = [...allRules]

    // 按来源筛选
    if (ruleSourceFilter !== 'all') {
      filtered = filtered.filter(rule => rule.create_source === ruleSourceFilter)
    }

    // 按严重程度筛选
    if (severityFilter !== 'all') {
      filtered = filtered.filter(rule => rule.severity === severityFilter)
    }

    setRules(filtered)
    
    // 根据筛选结果更新状态（只有在数据已加载后才更新）
    if (rulesViewStatus === 'loaded') {
      setRulesViewStatus(filtered.length === 0 ? 'empty' : 'loaded')
    }
  }, [allRules, ruleSourceFilter, severityFilter, rulesViewStatus])

  useEffect(() => {
    // 只有在非加载状态下才执行筛选
    if (rulesViewStatus === 'loading') return
    applyFilters()
  }, [allRules, ruleSourceFilter, severityFilter, applyFilters, rulesViewStatus])

  const handleSelectLibrary = (library: GovernanceLibrary) => {
    setSelectedLibrary(library)
    setRuleSourceFilter('all')
    setSeverityFilter('all')
    // 清空当前数据
    setAllRules([])
    setRules([])
    // 设置加载状态
    setRulesViewStatus('loading')
    // 延迟调用 API，确保状态更新先触发渲染
    setTimeout(() => {
      fetchRules(library.id)
    }, 0)
  }

  const handleDeleteLibrary = async (library: GovernanceLibrary) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定删除规则库 "${library.name}" 吗？该操作不可逆。`,
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      centered: true,
      onOk: async () => {
        try {
          const res = await deleteGovernanceLibrary(library.id)
          if (res.code === 200) {
            message.success('删除成功')
            if (selectedLibrary?.id === library.id) setSelectedLibrary(null)
            fetchLibraries()
          } else {
            message.error(res.msg || '删除失败')
          }
        } catch (error) {
          message.error('删除失败')
        }
      },
    })
  }

  const handleCreateRule = async () => {
    const currentCreateSource = getCurrentCreateSource()

    // 编辑模式下检查是否可以直接保存
    if (editingRule && originalEditingRule) {
      const nameChanged = ruleForm.rule_name !== originalEditingRule.rule_name
      const severityChanged = ruleForm.severity !== originalEditingRule.severity
      const sqlChanged = ruleForm.sql_text !== (originalEditingRule.sql_text || '')
      const descChanged = ruleForm.description !== (originalEditingRule.description || '')
      const ruleTypeChanged = ruleForm.rule_type !== originalEditingRule.rule_type
      const targetTableChanged = (ruleForm.target_table || '') !== (originalEditingRule?.target_table || '')
      const targetColumnChanged = (ruleForm.target_column || '') !== (originalEditingRule?.target_column || '')
      const conditionExprChanged = (ruleForm.condition_expr || '') !== (originalEditingRule?.condition_expr || '')

      // 检查复合规则条件是否变化
      const getOriginalCompositeConditions = () => {
        if (!originalEditingRule || originalEditingRule.rule_type !== 'composite') return []
        return parseRuleConditions(originalEditingRule)
      }
      const getOriginalConditionMode = (): 'AND' | 'OR' | undefined => {
        if (!originalEditingRule || originalEditingRule.rule_type !== 'composite') return undefined
        return getRuleConditionMode(originalEditingRule)
      }
      const compositeConditionsChanged = ruleForm.rule_type === 'composite'
        ? JSON.stringify(compositeConditions) !== JSON.stringify(getOriginalCompositeConditions())
        : false
      // 检查复合规则的条件模式（AND/OR）是否变化
      const conditionModeChanged = ruleForm.rule_type === 'composite'
        ? conditionMode !== getOriginalConditionMode()
        : false

      // AI解析模式：可以快速保存 name、severity、ruleType、sql
      // 注意：如果规则描述（自然语言）改变了，或目标表/目标列改变了，必须先点击 AI 解析，不能直接保存
      // 注意：如果复合规则条件或条件模式改变了，必须先进行SQL预览
      // 注意：parsedPrimaryResult 存在时表示已经完成了AI解析并确认，可以直接保存
      const nlChanged = editingRule ? naturalLanguageInput !== (originalEditingRule?.description || '') : false
      // AI模式下，目标表或目标列变化也需要重新解析，但已有 parsedPrimaryResult 时说明已确认过解析结果，可以保存
      const aiNeedsParse = (nlChanged || targetTableChanged || targetColumnChanged) && !parsedPrimaryResult
      // AI模式下，复合规则的条件或条件模式变化需要预览SQL，不能快速保存
      const aiCompositeNeedsPreview = ruleForm.rule_type === 'composite' && (compositeConditionsChanged || conditionModeChanged)
      // AI模式下，条件表达式变化需要重新预览SQL，不能快速保存
      const aiQuickSave = currentCreateSource === 'ai' && ruleForm.rule_type !== 'composite' && (nameChanged || severityChanged || ruleTypeChanged || sqlChanged) && !aiNeedsParse && !conditionExprChanged && !aiCompositeNeedsPreview

      // 手动配置模式：可以快速保存 name、severity、description、sql_text
      // 注意：目标表、目标列、条件表达式、复合规则条件变化或条件模式（AND/OR）变化时，必须进行SQL预览
      const needsPreview = targetTableChanged || targetColumnChanged || conditionExprChanged || compositeConditionsChanged || conditionModeChanged
      const editableFieldsChanged = nameChanged || severityChanged || ruleTypeChanged || sqlChanged || descChanged
      const manualQuickSave = currentCreateSource === 'manual' && editableFieldsChanged && !needsPreview

      // 模板模式：可以快速保存 name、severity、sql_text、description
      // 注意：目标表、目标列、条件表达式变化或条件模式（AND/OR）变化时，必须进行SQL预览
      const templateEditableFieldsChanged = nameChanged || severityChanged || sqlChanged || descChanged
      const templateNeedsPreview = targetTableChanged || targetColumnChanged || conditionExprChanged || compositeConditionsChanged || conditionModeChanged
      const templateQuickSave = currentCreateSource === 'template' && templateEditableFieldsChanged && !templateNeedsPreview

      if (aiQuickSave || manualQuickSave || templateQuickSave) {
        // AI模式下，description 实际存储在 naturalLanguageInput 中
        const descToSave = currentCreateSource === 'ai' ? naturalLanguageInput : ruleForm.description
        try {
          // 手动配置的复合规则需要包含完整的 conditions 和 condition_mode
          const normalizedConditions = compositeConditions.map((item) => ({ ...item, column: item.column.trim(), condition: item.condition.trim(), description: item.description?.trim() || undefined })).filter((item) => item.column && item.condition)
          const manualCompositePayload = currentCreateSource === 'manual' && ruleForm.rule_type === 'composite' ? {
            target_table: ruleForm.target_table || null,
            conditions: normalizedConditions,
            condition_mode: normalizedConditions.length > 1 ? conditionMode : undefined,
          } : {}

          // AI模式下需要传入 target_table 和 target_column（可能被 AI 解析更新过）
          const res = await updateGovernanceRule(editingRule.id, {
            rule_name: ruleForm.rule_name,
            description: descToSave,
            severity: currentCreateSource === 'ai' && parsedPrimaryResult ? (parsedPrimaryResult.severity as SeverityLevel || ruleForm.severity) : ruleForm.severity,
            rule_type: currentCreateSource === 'ai' && parsedPrimaryResult ? (parsedPrimaryResult.rule_type as RuleType || ruleForm.rule_type) : ruleForm.rule_type,
            sql_text: ruleForm.sql_text,
            condition_expr: currentCreateSource === 'ai' && parsedPrimaryResult ? (parsedPrimaryResult.condition_expr || ruleForm.condition_expr) : ruleForm.condition_expr,
            target_table: currentCreateSource === 'ai' ? ((parsedPrimaryResult?.target_table || ruleForm.target_table) || undefined) : (ruleForm.target_table || undefined),
            target_column: currentCreateSource === 'ai' ? ((parsedPrimaryResult?.target_column || ruleForm.target_column) || undefined) : (ruleForm.target_column || undefined),
            ...manualCompositePayload,
          })
          if (res.code === 200) {
            message.success('更新成功')
            setRuleModalVisible(false)
            resetRuleBuilderState()
            setEditingRule(null)
            setOriginalEditingRule(null)
            fetchRules(selectedLibrary!.id)
          } else {
            message.error(res.msg || '更新失败')
          }
        } catch (error) {
          message.error('更新失败')
        }
        return
      }

      // AI模式下规则描述或目标表/目标列改变了，但没有解析结果，不允许直接保存
      if (currentCreateSource === 'ai' && aiNeedsParse) {
        message.warning('规则描述或目标表/目标列已修改，请先点击 AI 解析生成新的校验 SQL')
        return
      }

      // AI模式编辑时：复合规则条件或条件模式（AND/OR）变化了，必须先完成SQL预览，否则禁止保存
      if (currentCreateSource === 'ai' && editingRule && aiCompositeNeedsPreview && !previewConfirmed) {
        message.warning('复合规则条件或连接方式已修改，请先点击"SQL预览"生成新的校验 SQL')
        return
      }

      // AI模式编辑时：用户编辑了条件表达式（复合条件或单条件），必须先完成SQL预览，否则禁止保存
      if (currentCreateSource === 'ai' && editingRule && aiConditionEdited && !previewConfirmed) {
        message.warning('条件表达式已修改，请先点击"SQL预览"生成新的校验 SQL')
        return
      }

      // AI模式下编辑时，已完成解析（parsedPrimaryResult 存在）且用户未编辑条件表达式，使用解析结果更新
      if (currentCreateSource === 'ai' && editingRule && parsedPrimaryResult && !aiConditionEdited) {
        const ruleConfig = {
          rule_type: parsedPrimaryResult.rule_type,
          target_table: parsedPrimaryResult.target_table || ruleForm.target_table || undefined,
          target_column: parsedPrimaryResult.target_column || ruleForm.target_column || undefined,
          condition_expr: parsedPrimaryResult.condition_expr || undefined,
          severity: (parsedPrimaryResult.severity as SeverityLevel) || ruleForm.severity,
          conditions: parsedPrimaryResult.conditions || undefined,
          condition_mode: parsedPrimaryResult.condition_mode || undefined,
        }
        // AI模式编辑复合规则时，需要包含完整的 conditions 和 condition_mode
        const normalizedConditions = ruleConfig.rule_type === 'composite' && ruleConfig.conditions?.length
          ? ruleConfig.conditions.map((item: any) => ({ ...item, column: item.column.trim(), condition: item.condition.trim(), description: item.description?.trim() || undefined })).filter((item: any) => item.column && item.condition)
          : []
        const compositePayload = ruleConfig.rule_type === 'composite' && normalizedConditions.length > 0 ? {
          conditions: normalizedConditions,
          condition_mode: normalizedConditions.length > 1 ? ruleConfig.condition_mode : undefined,
        } : {}
        try {
          const res = await updateGovernanceRule(editingRule.id, {
            rule_name: ruleForm.rule_name,
            description: naturalLanguageInput || editingRule.description || 'AI智能解析生成',
            severity: ruleConfig.severity,
            rule_type: ruleConfig.rule_type as RuleType,
            sql_text: ruleForm.sql_text || rulePreviewSql,
            target_table: ruleConfig.target_table,
            target_column: ruleConfig.target_column,
            condition_expr: ruleConfig.condition_expr,
            ...compositePayload,
          })
          if (res.code === 200) {
            message.success('更新成功')
            setRuleModalVisible(false)
            resetRuleBuilderState()
            setEditingRule(null)
            setOriginalEditingRule(null)
            fetchRules(selectedLibrary!.id)
          } else {
            message.error(res.msg || '更新失败')
          }
        } catch (error) {
          message.error('更新失败')
        }
        return
      }

      // 模板模式下目标表、目标列、条件表达式改变了，或复合规则条件/条件模式改变了，且尚未进行预览，必须先进行SQL预览
      if (currentCreateSource === 'template' && templateNeedsPreview && !previewConfirmed) {
        message.warning('目标表、目标列、条件表达式或复合规则已修改，请先点击 SQL 预览')
        return
      }

      // AI模式编辑时：已完成SQL预览，有实际变更（字段修改 或 条件表达式修改后已预览），使用 ruleForm 数据直接更新
      if (currentCreateSource === 'ai' && editingRule && ((nameChanged || severityChanged || ruleTypeChanged || sqlChanged || descChanged) || conditionExprChanged || aiCompositeNeedsPreview)) {
        try {
          // AI模式编辑复合规则时，需要包含完整的 conditions 和 condition_mode
          const normalizedConditions = ruleForm.rule_type === 'composite'
            ? compositeConditions.map((item) => ({ ...item, column: item.column.trim(), condition: item.condition.trim(), description: item.description?.trim() || undefined })).filter((item) => item.column && item.condition)
            : []
          const aiCompositePayload = ruleForm.rule_type === 'composite' && normalizedConditions.length > 0 ? {
            conditions: normalizedConditions,
            condition_mode: normalizedConditions.length > 1 ? conditionMode : undefined,
          } : {}
          const res = await updateGovernanceRule(editingRule.id, {
            rule_name: ruleForm.rule_name,
            description: ruleForm.description || naturalLanguageInput || editingRule.description || 'AI智能解析生成',
            severity: ruleForm.severity,
            rule_type: ruleForm.rule_type as RuleType,
            sql_text: ruleForm.sql_text,
            target_table: ruleForm.target_table || undefined,
            target_column: ruleForm.target_column || undefined,
            condition_expr: ruleForm.condition_expr || undefined,
            ...aiCompositePayload,
          })
          if (res.code === 200) {
            message.success('更新成功')
            setRuleModalVisible(false)
            resetRuleBuilderState()
            setEditingRule(null)
            setOriginalEditingRule(null)
            fetchRules(selectedLibrary!.id)
          } else {
            message.error(res.msg || '更新失败')
          }
        } catch (error) {
          message.error('更新失败')
        }
        return
      }

      // AI模式下没有任何修改，关闭弹窗（编辑模式下未触发快速保存，也没有其他变更）
      if (currentCreateSource === 'ai' && !aiNeedsParse && !(nameChanged || severityChanged || ruleTypeChanged || sqlChanged)) {
        setRuleModalVisible(false)
        setEditingRule(null)
        setOriginalEditingRule(null)
        return
      }

      // 手动模式下没有任何修改，关闭弹窗
      if (currentCreateSource === 'manual' && !editableFieldsChanged && !needsPreview) {
        setRuleModalVisible(false)
        setEditingRule(null)
        setOriginalEditingRule(null)
        return
      }

      // 模板模式下没有任何修改，关闭弹窗
      if (currentCreateSource === 'template' && !templateEditableFieldsChanged && !templateNeedsPreview) {
        setRuleModalVisible(false)
        setEditingRule(null)
        setOriginalEditingRule(null)
        return
      }
    }

    if (!validateRuleForCreate()) return

    // 自然语言模式创建：优先使用用户在解析成功区域编辑后的 ruleForm 数据
    if (currentCreateSource === 'ai' && parsedPrimaryResult) {
      // 必须先点击"确认解析结果"（previewConfirmed = true）才能保存
      if (!previewConfirmed) {
        message.warning('请先点击 "确认解析结果" 按钮后再保存')
        return
      }
      const normalizedConditions = ruleForm.rule_type === 'composite'
        ? compositeConditions.map((item) => ({ ...item, column: item.column.trim(), condition: item.condition.trim(), description: item.description?.trim() || undefined })).filter((item) => item.column && item.condition)
        : []
      const ruleConfig = {
        rule_type: ruleForm.rule_type || parsedPrimaryResult.rule_type,
        target_table: ruleForm.target_table || parsedPrimaryResult.target_table || undefined,
        target_column: ruleForm.target_column || parsedPrimaryResult.target_column || undefined,
        condition_expr: ruleForm.rule_type !== 'composite' ? (ruleForm.condition_expr || parsedPrimaryResult.condition_expr || undefined) : undefined,
        severity: (ruleForm.severity || parsedPrimaryResult.severity) as SeverityLevel,
        conditions: ruleForm.rule_type === 'composite' && normalizedConditions.length > 0 ? normalizedConditions : (parsedPrimaryResult.conditions || undefined),
        condition_mode: ruleForm.rule_type === 'composite' && normalizedConditions.length > 0 ? (normalizedConditions.length > 1 ? conditionMode : undefined) : (parsedPrimaryResult.condition_mode || undefined),
      }

      try {
        const res = await createGovernanceRule({
          rule_name: ruleForm.rule_name,
          library_id: selectedLibrary!.id,
          create_source: 'ai',
          rule_config: ruleConfig,
          description: naturalLanguageInput || ruleForm.description || 'AI智能解析生成',
          sql_preview: rulePreviewSql || undefined,
        })
        if (res.code === 200) {
          message.success('创建成功')
          setRuleModalVisible(false)
          resetRuleBuilderState()
          setEditingRule(null)
          setOriginalEditingRule(null)
          fetchRules(selectedLibrary!.id)
        } else {
          message.error(res.msg || '创建失败')
        }
      } catch (error) {
        message.error('创建失败')
      }
      return
    }

    // 手动模式和模板模式创建
    const { normalizedConditions, isCompositeRule, payload } = buildCreatePayload()
    if (isCompositeRule && normalizedConditions.length === 0) {
      message.warning('复合规则至少需要配置一条有效条件')
      return
    }
    // 手动模式和模板模式编辑都需要预览确认
    // 模板模式创建也需要预览（用户在创建时可能会修改条件）
    if (!previewConfirmed) {
      message.warning('请先完成 SQL 预览并确认后再保存')
      return
    }
    try {
      const res = editingRule ? await updateGovernanceRule(editingRule.id, payload) : await createGovernanceRule(payload)
      if (res.code === 200) {
        message.success(editingRule ? '更新成功' : '创建成功')
        setRuleModalVisible(false)
        resetRuleBuilderState()
        setEditingRule(null)
        setOriginalEditingRule(null)
        fetchRules(selectedLibrary!.id)
      } else {
        message.error(res.msg || '操作失败')
      }
    } catch (error) {
      message.error('操作失败')
    }
  }

  const handleDeleteRule = async (rule: GovernanceRule) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除规则 "${rule.rule_name}" 吗？`,
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      centered: true,
      onOk: async () => {
        try {
          const res = await deleteGovernanceRule(rule.id)
          if (res.code === 200) {
            message.success('删除成功')
            fetchRules(selectedLibrary!.id)
          } else {
            message.error(res.msg || '删除失败')
          }
        } catch (error) {
          message.error('删除失败')
        }
      },
    })
  }

  const handleToggleRule = async (rule: GovernanceRule) => {
    try {
      const res = await toggleGovernanceRule(rule.id)
      if (res.code === 200) {
        message.success(rule.enabled ? '规则已禁用' : '规则已启用')
        fetchRules(selectedLibrary!.id)
      } else {
        message.error(res.msg || '操作失败')
      }
    } catch (error) {
      message.error('操作失败')
    }
  }

  const handleImportTemplate = async () => {
    if (!selectedLibrary) {
      message.warning('请先选择一个规则库')
      return
    }
    if (selectedTemplateIds.length === 0) {
      message.warning('请至少选择一个模板')
      return
    }
    if (importTargetColumn && !importTargetTable) {
      message.warning('填写列名时请先填写表名')
      return
    }
    setImportingTemplates(true)
    try {
      const res = await importRulesFromTemplate({ library_id: selectedLibrary.id, template_ids: selectedTemplateIds, target_table: importTargetTable.trim() || undefined, target_column: importTargetColumn.trim() || undefined, override_name: importOverrideName })
      if (res.code === 200) {
        message.success(`成功导入 ${res.data.imported_count} 条规则`)
        setImportModalVisible(false)
        setSelectedTemplateIds([])
        setImportTargetTable('')
        setImportTargetColumn('')
        setImportOverrideName(true)
        fetchRules(selectedLibrary.id)
        fetchLibraries()
      } else {
        message.error(res.msg || '导入失败')
      }
    } catch (error) {
      message.error('导入失败')
    } finally {
      setImportingTemplates(false)
    }
  }

  const openLibraryModal = (library?: GovernanceLibrary) => {
    setEditingLibrary(library || null)
    setLibraryModalVisible(true)
  }

  // Helper function to find matching template for a rule
  const findMatchingTemplate = (rule: GovernanceRule, templates: GovernanceRuleTemplate[]): GovernanceRuleTemplate | null => {
    // Try to find a template where rule_type matches and condition_expr matches default_condition
    const sameTypeTemplates = templates.filter(t => t.rule_type === rule.rule_type)

    // 1. 先尝试精确匹配：rule_type 相同 且 condition 相同（normalize 后比较）
    for (const template of sameTypeTemplates) {
      if (rule.condition_expr && template.default_condition) {
        const normalizedRuleCondition = rule.condition_expr.trim().replace(/\s+/g, ' ').toLowerCase()
        const normalizedTemplateCondition = template.default_condition.trim().replace(/\s+/g, ' ').toLowerCase()
        if (normalizedRuleCondition === normalizedTemplateCondition) {
          return template
        }
      }
    }

    // 2. 再尝试占位符匹配：去掉列名后相同
    for (const template of sameTypeTemplates) {
      if (rule.condition_expr && template.default_condition) {
        const normalizedRuleCondition = rule.condition_expr.trim().replace(/\s+/g, ' ').toLowerCase()
        const normalizedTemplateCondition = template.default_condition.trim().replace(/\s+/g, ' ').toLowerCase()
        const rulePattern = normalizedRuleCondition.replace(/\b\w+\b/g, 'COL')
        const templatePattern = normalizedTemplateCondition.replace(/\b\w+\b/g, 'COL')
        if (rulePattern === templatePattern) {
          return template
        }
      }
    }

    // 3. 兜底：同类型的第一个模板（避免显示"无法匹配"）
    if (sameTypeTemplates.length > 0) {
      return sameTypeTemplates[0]
    }

    return null
  }

  const openRuleModal = async (rule?: GovernanceRule) => {
    resetRuleBuilderState()
    void ensureDatasourceTablesLoaded()
    if (rule) {
      setEditingRule(rule)
      setOriginalEditingRule(rule)
      const mode = rule.create_source === 'ai' ? 'ai' : rule.create_source === 'template' ? 'template' : 'manual'
      setRuleCreationMode(mode)
      setRuleForm({
        rule_name: rule.rule_name,
        description: rule.description || '',
        rule_type: rule.rule_type,
        severity: rule.severity,
        target_table: rule.target_table || '',
        target_column: rule.target_column || '',
        condition_expr: rule.condition_expr || '',
        sql_text: rule.sql_text || '',
      })
      if (rule.sql_text) {
        setRulePreviewSql(rule.sql_text)
      }
      setShowSqlPreview(false)
      setPreviewConfirmed(false)
      // AI创建的规则，把描述填充到自然语言输入框
      if (mode === 'ai' && rule.description) {
        setNaturalLanguageInput(rule.description)
      }
      // 模板导入的规则，尝试匹配对应的模板
      if (mode === 'template') {
        if (templateGroups.length === 0) {
          await loadTemplateGroups()
        }
        const allTemplates = templateGroups.flatMap(g => g.templates)
        let matchedTemplate: GovernanceRuleTemplate | null = null
        if (rule.template_id) {
          matchedTemplate = allTemplates.find(t => t.id === rule.template_id) || null
        }
        if (!matchedTemplate) {
          matchedTemplate = findMatchingTemplate(rule, allTemplates)
        }
        if (matchedTemplate) {
          setTemplateRuleId(matchedTemplate.id)
          setSelectedTemplateDetail(matchedTemplate)
        }
        setPreviewConfirmed(false)
      }
      if (rule.target_table) void ensureTableColumnsLoaded(rule.target_table)
      if (rule.rule_type === 'composite') {
        const parsedConditions = parseRuleConditions(rule)
        setCompositeConditions(parsedConditions.length > 0 ? parsedConditions : [{ ...defaultCompositeCondition }])
        setConditionMode(getRuleConditionMode(rule) || 'AND')
      } else {
        setCompositeConditions([])
      }
    } else {
      setEditingRule(null)
      setOriginalEditingRule(null)
      setRuleCreationMode('manual')
    }
    setRuleModalVisible(true)
  }

  const openImportModal = async () => {
    if (!selectedLibrary) {
      message.warning('请先选择一个规则库')
      return
    }
    const templateList = await loadRuleTemplates()
    if (templateList.length > 0) setImportModalVisible(true)
  }

  const loadRuleTemplates = async (ruleType?: RuleType | string) => {
    try {
      const res = await getRuleTemplates(ruleType ? { rule_type: ruleType } : undefined)
      if (res.code === 200) {
        setTemplates(res.data)
        return res.data
      }
      message.error(res.msg || '获取模板失败')
      return []
    } catch (error) {
      message.error('获取模板失败')
      return []
    }
  }

  // Load templates grouped by rule type (for template mode)
  const loadTemplateGroups = async () => {
    setTemplatesLoading(true)
    try {
      const res = await getRuleTemplatesGrouped()
      console.log('Template groups API response:', res)
      if (res.code === 200) {
        const groups = res.data?.groups || []
        console.log('Setting template groups:', groups)
        setTemplateGroups(groups)
        // Also flatten templates for backward compatibility
        const allTemplates = groups.flatMap((g: any) => g.templates || [])
        setTemplates(allTemplates)
        return groups
      }
      message.error(res.msg || '获取模板分组失败')
      return []
    } catch (error) {
      console.error('Load template groups error:', error)
      message.error('获取模板分组失败')
      return []
    } finally {
      setTemplatesLoading(false)
    }
  }

  // Note: applyTemplateRule and getFilteredColumnOptions are defined later in the file

  const handleParseRule = async () => {
    if (!validateRuleForParse()) return
    setParseLoading(true)
    const loadingKey = 'parseRuleLoading'
    message.loading({ content: '正在解析规则，请稍候...', key: loadingKey, duration: 0 })
    clearRulePreviewState()
    setParseCandidates(null)
    setParseNeedsConfirmation(false)
    setMultiRuleConfigs([])
    setSelectedRuleIndices([])
    try {
      const res = await parseGovernanceRule({
        user_input: naturalLanguageInput.trim(),
        datasource_id: selectedLibrary!.datasource_id!,
        target_table: ruleForm.target_table.trim() || undefined,
        target_column: ruleForm.target_column.trim() || undefined,
        mode: ruleForm.rule_type ? 'auto' : undefined,
      })
      if (res.code === 200 && res.data.success) {
        // 保存原始输入用于后续调用
        setOriginalParseInput({
          user_input: naturalLanguageInput.trim(),
          target_table: ruleForm.target_table.trim(),
          target_column: ruleForm.target_column.trim(),
        })

        const stage = res.data.stage || res.data.scope_type
        setParseStage(stage as ParseStage || '')

        // 处理各阶段响应
        if (stage === 'rule_preview') {
          // 直接生成规则配置，无需确认
          handleRulePreviewResult(res.data)
        } else if (stage === 'multi_preview') {
          // 多条规则预览
          handleMultiPreviewResult(res.data)
        } else if (res.data.needs_confirmation && res.data.candidates) {
          // 需要确认：展示候选列表（table_selection / column_selection / multi_column_selection）
          setParseCandidates(res.data.candidates)
          setParseNeedsConfirmation(true)
          setParseReasoning(res.data.reasoning || '')
          setRulePreviewSql(res.data.sql_preview || '')

          // multi_column_selection 阶段：初始化选中状态
          if (stage === 'multi_column_selection') {
            setSelectedMultiColumns([])
          }

          message.info(res.data.reasoning || '请从候选列表中选择目标')
        } else {
          // 兜底：解析成功但无候选
          handleRulePreviewResult(res.data)
        }
      } else {
        setParsedPrimaryResult(null)
        setParsedAlternatives([])
        clearRulePreviewState()
        setParseCandidates(null)
        setMultiRuleConfigs([])
        setParsedConfidence(null)
        message.warning(res.msg || '未能解析规则，请尝试手动填写')
      }
    } catch (error) {
      message.error('规则解析失败')
    } finally {
      setParseLoading(false)
      message.destroy('parseRuleLoading')
    }
  }

  // 处理 rule_preview 阶段结果
  const handleRulePreviewResult = (data: GovernanceRuleParseResponseData) => {
    setParseCandidates(null)
    setParseNeedsConfirmation(false)
    setSelectedRuleIndices([])
    setAiConditionEdited(false) // 重置：用户尚未编辑条件表达式

    if (data.rule_config) {
      const ruleConfig = data.rule_config
      setParsedPrimaryResult(ruleConfig)
      setParsedConfidence(typeof data.confidence === 'number' ? data.confidence : null)
      // 解析成功后，将结果同步到 ruleForm 和 compositeConditions，让用户可以直接编辑
      setRuleForm((prev) => ({
        ...prev,
        rule_type: (ruleConfig.rule_type as RuleType) || prev.rule_type,
        target_table: data.target_table || ruleConfig.target_table || '',
        target_column: data.target_column || ruleConfig.target_column || '',
        condition_expr: ruleConfig.condition_expr || prev.condition_expr,
        severity: (ruleConfig.severity as SeverityLevel) || prev.severity,
      }))
      if (ruleConfig.rule_type === 'composite' && ruleConfig.conditions?.length) {
        setCompositeConditions(ruleConfig.conditions)
        setConditionMode(ruleConfig.condition_mode || 'AND')
      } else {
        setCompositeConditions([])
        setConditionMode('AND')
      }
      // 同步 SQL 预览
      setRulePreviewSql(data.sql_preview || '')
      setShowSqlPreview(!!data.sql_preview)
      setPreviewScope(data.stage === 'column_selection' || data.stage === 'rule_preview' ? 'column' : '')
      setParseStage('rule_preview')
      setParseReasoning(ruleConfig.reasoning || data.reasoning || '')

      // 如果有 rule_configs（composite 规则），保存用于展示参考
      if (data.rule_configs && data.rule_configs.length > 0) {
        setMultiRuleConfigs(data.rule_configs)
      } else {
        setMultiRuleConfigs([])
      }

      // AI编辑模式：解析成功后同步 originalEditingRule.condition_expr，让 conditionExprChanged 重置
      if (editingRule) {
        setOriginalEditingRule((prev) => prev ? { ...prev, condition_expr: ruleConfig.condition_expr || prev.condition_expr } : prev)
      }

      message.success('规则解析成功，请确认解析结果后再创建')
    } else {
      message.warning('未能解析出有效的规则配置，请尝试手动填写')
    }
  }

  // 处理 multi_preview 阶段结果
  const handleMultiPreviewResult = (data: GovernanceRuleParseResponseData) => {
    setParseCandidates(null)
    setParseNeedsConfirmation(true)
    setParseStage('multi_preview')
    setParseReasoning(data.reasoning || '已为多个字段生成规则预览，请确认要创建哪些规则')

    if (data.rule_configs && data.rule_configs.length > 0) {
      setMultiRuleConfigs(data.rule_configs)
      // 默认全选
      setSelectedRuleIndices(data.rule_configs.map((_, idx) => idx))
      setParsedConfidence(typeof data.confidence === 'number' ? data.confidence : null)
    }
  }

  // 处理确认多列后生成规则预览
  const handleConfirmMultiColumns = async () => {
    if (selectedMultiColumns.length === 0 || !originalParseInput) {
      message.warning('请至少选择一个列')
      return
    }

    setParseLoading(true)
    try {
      // 单列：使用 selected_column
      if (selectedMultiColumns.length === 1) {
        const res = await parseGovernanceRule({
          user_input: originalParseInput.user_input,
          datasource_id: selectedLibrary!.datasource_id!,
          target_table: originalParseInput.selected_table || originalParseInput.target_table,
          selected_column: selectedMultiColumns[0],
        })
        if (res.code === 200 && res.data.success) {
          handleRulePreviewResult(res.data)
        } else {
          message.warning(res.msg || '解析失败')
        }
      } else {
        // 多列：使用 target_columns，后端返回 composite 聚合规则（rule_preview）
        const res = await parseGovernanceRule({
          user_input: originalParseInput.user_input,
          datasource_id: selectedLibrary!.datasource_id!,
          target_table: originalParseInput.selected_table || originalParseInput.target_table,
          target_columns: selectedMultiColumns.join(','),
        })
        if (res.code === 200 && res.data.success) {
          // 后端返回 rule_preview（composite 规则），直接进入规则预览
          handleRulePreviewResult(res.data)
        } else {
          message.warning(res.msg || '解析失败')
        }
      }
    } catch (error) {
      message.error('解析失败')
    } finally {
      setParseLoading(false)
    }
  }

  // 处理用户从候选列表中选择（表或单列）
  const handleSelectCandidate = async (candidate: GovernanceRuleParseCandidateItem) => {
    if (!originalParseInput) return
    setParseLoading(true)

    try {
      // 根据候选类型构建请求参数
      if (parseCandidates?.type === 'table') {
        // 表候选：选择表后进入下一阶段
        // 注意：此时用 target_table 传入已选中的表名
        // inferred_columns 传候选列数组（带 reason），完整保留一阶段返回的列信息
        const inferredColumns: Array<{ column: string; reason?: string }> | undefined = (() => {
          if (candidate.inferred_columns?.length) {
            // 可能是对象数组 { column, reason } 或字符串数组
            if (typeof candidate.inferred_columns[0] === 'object') {
              return candidate.inferred_columns.map(col => ({
                column: (col as { column?: string }).column || '',
                reason: (col as { reason?: string }).reason,
              }))
            }
            return candidate.inferred_columns.map(col => ({ column: String(col) }))
          }
          if (candidate.inferred_column_names) {
            return candidate.inferred_column_names.split(',').map(col => ({ column: col.trim() }))
          }
          return undefined
        })()

        const res = await parseGovernanceRule({
          user_input: originalParseInput.user_input,
          datasource_id: selectedLibrary!.datasource_id!,
          target_table: candidate.name,  // 用 target_table 而非 selected_table
          inferred_columns: inferredColumns,
        })

        if (res.code === 200 && res.data.success) {
          handleParseResponse(res.data, candidate.name)
        } else {
          message.warning(res.msg || '选择后解析失败')
        }
      } else if (parseCandidates?.type === 'column') {
        // 单列候选：直接生成规则
        const res = await parseGovernanceRule({
          user_input: originalParseInput.user_input,
          datasource_id: selectedLibrary!.datasource_id!,
          target_table: ruleForm.target_table,
          selected_column: candidate.name,
        })

        if (res.code === 200 && res.data.success) {
          handleParseResponse(res.data)
        } else {
          message.warning(res.msg || '选择后解析失败')
        }
      }
    } catch (error) {
      message.error('解析失败')
    } finally {
      setParseLoading(false)
    }
  }

  // 统一处理解析响应
  const handleParseResponse = (data: GovernanceRuleParseResponseData, selectedTable?: string) => {
    const stage = data.stage || data.scope_type
    setParseStage(stage as ParseStage || '')

    if (stage === 'rule_preview') {
      handleRulePreviewResult(data)
    } else if (stage === 'multi_preview') {
      handleMultiPreviewResult(data)
    } else if (data.needs_confirmation && data.candidates) {
      // 仍需确认（table_selection / column_selection / multi_column_selection）
      setParseCandidates(data.candidates)
      setParseNeedsConfirmation(true)
      setParseReasoning(data.reasoning || '')
      setRulePreviewSql(data.sql_preview || '')

      // 回填表单，并把已确认的表名同步回 originalParseInput，避免后续请求丢失
      if (selectedTable) {
        setRuleForm((prev) => ({ ...prev, target_table: selectedTable }))
        setOriginalParseInput((prev) => (prev ? { ...prev, target_table: selectedTable, selected_table: selectedTable } : prev))
      }

      // multi_column_selection 阶段：初始化选中状态
      if (stage === 'multi_column_selection') {
        setSelectedMultiColumns([])
        setMultiRuleConfigs([])
        setParsedPrimaryResult(null)  // 重要：multi_column_selection 时 rule_config 为 null
      }

      message.info(data.reasoning || '请继续从候选列表中选择')
    } else {
      handleRulePreviewResult(data)
    }
  }

  const handleAcceptParsedAlternative = (parsed: GovernanceRuleParsePrimaryResult) => {
    setParsedPrimaryResult(parsed)
    applyParsedResultToForm(parsed)
    setPreviewScope(parsed.target_column ? 'column' : parsed.target_table ? 'table' : '')
  }

  const handlePreviewRule = async () => {
    if (!validateRuleForPreview()) return
    setPreviewLoading(true)
    // 捕获当前编辑的条件表达式值（避免闭包陷阱）
    const currentConditionExpr = ruleForm.condition_expr
    try {
      const res = await previewGovernanceRule(buildSingleRulePreviewPayload())
      if (res.code === 200 && res.data.success) {
        setRulePreviewSql(res.data.sql)
        // 同步更新 ruleForm.sql_text，确保保存时使用预览后的 SQL
        setRuleForm((prev) => ({ ...prev, sql_text: res.data.sql }))
        setPreviewScope((res.data as { scope?: 'column' | 'table' }).scope || (ruleForm.target_column ? 'column' : 'table'))
        setPreviewConfirmed(true)
        setShowSqlPreview(true)
        setAiConditionEdited(false) // 预览成功后重置编辑标记
        // AI编辑模式：预览成功后同步 originalEditingRule 的 condition_expr（使用用户编辑后的值）
        if (editingRule) {
          setOriginalEditingRule((prev) => prev ? { ...prev, condition_expr: currentConditionExpr || prev.condition_expr } : prev)
          // 清除 parsedPrimaryResult，避免保存时走旧路径（用旧 condition_expr）而忽略用户刚预览生成的新条件表达式
          setParsedPrimaryResult(null)
        }
        requestAnimationFrame(() => {
          ruleModalScrollRef.current?.scrollTo({ top: ruleModalScrollRef.current.scrollHeight, behavior: 'smooth' })
        })
      } else {
        message.error(res.msg || '预览失败')
      }
    } catch (error) {
      message.error('预览失败')
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleSuggestRules = async () => {
    if (!selectedLibrary?.datasource_id) {
      message.warning('当前规则库未绑定数据源')
      return
    }
    setSuggestionsLoading(true)
    try {
      const res = await suggestGovernanceRules({ datasource_id: selectedLibrary.datasource_id })
      if (res.code === 200 && res.data.success) {
        setSmartSuggestions(res.data.suggestions || [])
        setSuggestionsSource(res.data.source || 'llm')
        setSuggestionsCollapsed(false)
      } else {
        message.error(res.msg || '规则建议获取失败')
        setSmartSuggestions([])
      }
    } catch (error) {
      message.error('规则建议获取失败')
      setSmartSuggestions([])
    } finally {
      setSuggestionsLoading(false)
    }
  }

  // Apply selected template to form
  const applyTemplateRule = async (templateId: string) => {
    setTemplateRuleId(templateId)
    clearRulePreviewState()

    if (!templateId) {
      setSelectedTemplateDetail(null)
      setRuleForm(prev => ({
        ...prev,
        rule_name: '',
        description: '',
        rule_type: 'null_check',
        severity: 'warning',
        condition_expr: '',
      }))
      return
    }

    // 先从已加载的模板组中查找模板
    const allTemplates = templateGroups.flatMap(g => g.templates)
    const template = allTemplates.find(t => t.id === templateId)

    if (template) {
      // 直接使用缓存的模板信息
      setSelectedTemplateDetail(template)

      // 编辑模式下：如果当前已有目标列，且模板条件中有 column 占位符，则用真实列名替换
      const currentTargetColumn = ruleForm.target_column
      let conditionExpr = template.default_condition || ''
      if (editingRule && currentTargetColumn && /\bcolumn\b/i.test(conditionExpr)) {
        conditionExpr = conditionExpr.replace(/\bcolumn\b/gi, currentTargetColumn)
      }

      // Auto-fill form based on template (仅在添加模式时回填规则名称，编辑模式保持原名称)
      setRuleForm(prev => ({
        ...prev,
        rule_name: editingRule ? prev.rule_name : (template.template_name || template.name || ''),
        description: template.description || '',
        rule_type: (template.rule_type as RuleType) || 'null_check',
        severity: (template.default_severity as SeverityLevel) || 'warning',
        condition_expr: conditionExpr,
      }))
    } else {
      // 如果缓存中没有（理论上不应该发生），尝试调用API获取详情
      setSelectedTemplateDetail(null)
      try {
        const res = await getTemplateDetail(templateId)
        if (res.code === 200) {
          const templateDetail = res.data
          setSelectedTemplateDetail(templateDetail)

          // 编辑模式下：如果当前已有目标列，且模板条件中有 column 占位符，则用真实列名替换
          const currentTargetColumn = ruleForm.target_column
          let conditionExpr = templateDetail.default_condition || ''
          if (editingRule && currentTargetColumn && /\bcolumn\b/i.test(conditionExpr)) {
            conditionExpr = conditionExpr.replace(/\bcolumn\b/gi, currentTargetColumn)
          }

          setRuleForm(prev => ({
            ...prev,
            rule_name: editingRule ? prev.rule_name : (templateDetail.template_name || templateDetail.name || ''),
            description: templateDetail.description || '',
            rule_type: (templateDetail.rule_type as RuleType) || 'null_check',
            severity: (templateDetail.default_severity as SeverityLevel) || 'warning',
            condition_expr: conditionExpr,
          }))
        } else {
          message.error(res.msg || '获取模板详情失败')
        }
      } catch (error) {
        message.error('获取模板详情失败')
      }
    }

    // Load tables if not already loaded
    const dsId = getCurrentDatasourceId()
    if (dsId && !availableTables.length) {
      await ensureDatasourceTablesLoaded()
    }
  }

  // Get filtered columns based on template's applicable_columns_list
  const getFilteredColumnOptions = (tableName: string) => {
    const columns = availableColumnsMap[tableName] || []
    if (!selectedTemplateDetail?.applicable_columns_list?.length) {
      return columns
    }
    const applicableTypes = selectedTemplateDetail.applicable_columns_list.map(t => t.toLowerCase())
    return columns.filter(col => {
      const colType = (col.type || col.data_type || '').toLowerCase()
      return applicableTypes.some(t => colType.includes(t))
    })
  }

  const handleSwitchRuleMode = async (mode: 'manual' | 'ai' | 'template') => {
    setRuleCreationMode(mode)
    clearRulePreviewState()
    setSmartSuggestions([])
    setSuggestionsCollapsed(false)
    if (mode === 'manual' && ruleForm.rule_type === 'composite') ensureCompositeConditionExists()
    if (mode === 'template') {
      await loadTemplateGroups()
      // Reset template selection state
      setTemplateRuleId('')
      setSelectedTemplateDetail(null)
    }
  }

  const addCompositeCondition = () => {
    clearRulePreviewState()
    setCompositeConditions((prev) => [...prev, { ...defaultCompositeCondition }])
  }

  const ensureCompositeConditionExists = () => {
    setCompositeConditions((prev) => (prev.length > 0 ? prev : [{ ...defaultCompositeCondition }]))
  }

  const updateCompositeCondition = (index: number, field: keyof GovernanceRuleCondition, value: string) => {
    clearRulePreviewState()
    setCompositeConditions((prev) => prev.map((item, idx) => (idx === index ? { ...item, [field]: value } : item)))
  }

  const removeCompositeCondition = (index: number) => {
    clearRulePreviewState()
    setCompositeConditions((prev) => prev.filter((_, idx) => idx !== index))
  }

  const getCompositePreview = () => {
    if (compositeConditions.length === 0) return ''
    return compositeConditions.filter((item) => item.column || item.condition).map((item) => `${item.column || 'column'} ${item.condition || '[condition]'}`).join(` ${conditionMode} `)
  }

  return (
    <div className="space-y-3" style={{ marginTop: -8 }}>
      <style>{spinKeyframes}</style>
      <button onClick={() => router.push(`/${lng}/governance`)} style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '6px 10px', borderRadius: 6, fontSize: 13, color: 'rgb(var(--theme-text-secondary))', backgroundColor: 'transparent', border: 'none', cursor: 'pointer' }}>
        <ArrowLeft style={{ width: 16, height: 16 }} />
        返回
      </button>

      <div style={{ display: 'grid', gridTemplateColumns: isLibraryViewMode ? '1fr' : '40% 60%', gap: 16, height: 'calc(100vh - 140px)', minHeight: 500 }}>
        {!isLibraryViewMode && (
          <div style={{ borderRadius: 16, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))', overflow: 'hidden', display: 'flex', flexDirection: 'column', flex: 1 }}>
            <div style={{ padding: '16px 16px 14px', borderBottom: '1px solid rgb(var(--theme-border))', flexShrink: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <h3 style={{ fontSize: 15, fontWeight: 600, color: 'rgb(var(--theme-text))', margin: 0 }}>规则库</h3>
                  <p style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))', marginTop: 4 }}>创建和管理数据质检规则库</p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={fetchLibraries} title="刷新规则库列表" style={{ padding: 6, borderRadius: 6, backgroundColor: 'transparent', border: 'none', cursor: 'pointer', color: 'rgb(var(--theme-text-secondary))', display: 'flex', alignItems: 'center' }}><RefreshCw style={{ width: 14, height: 14 }} /></button>
                  <button onClick={() => openLibraryModal()} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 8, fontSize: 13, fontWeight: 500, color: 'white', backgroundColor: 'rgb(var(--theme-primary))', border: 'none', cursor: 'pointer' }}><Plus style={{ width: 14, height: 14 }} />新建</button>
                </div>
              </div>
            </div>
            <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
              {loading ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}><Loader2 style={{ width: 36, height: 36, color: 'rgb(var(--theme-primary))', animation: 'spin 1s linear infinite' }} /></div>
              ) : libraries.length === 0 ? (
                <EmptyStateCard icon={<Library />} title="暂无规则库" description="创建规则库来管理规则" buttonText="创建规则库" onButtonClick={() => openLibraryModal()} />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {libraries.map((lib) => <LibraryCard key={lib.id} library={lib} isSelected={selectedLibrary?.id === lib.id} onClick={() => handleSelectLibrary(lib)} onDelete={() => handleDeleteLibrary(lib)} />)}
                </div>
              )}
            </div>
          </div>
        )}

        <div style={{ borderRadius: 16, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))', overflow: 'hidden', display: 'flex', flexDirection: 'column', flex: 1 }}>
          {selectedLibrary || (isLibraryViewMode && loading) ? (
            <>
              <div style={{ padding: '16px 16px 14px', borderBottom: '1px solid rgb(var(--theme-border))', flexShrink: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <h3 style={{ fontSize: 15, fontWeight: 600, color: 'rgb(var(--theme-text))', margin: 0 }}>{selectedLibrary?.name || '规则库'}</h3>
                    {selectedLibrary?.description && <p style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))', marginTop: 2 }}>{selectedLibrary.description}</p>}
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <button onClick={() => {
                      if (!selectedLibrary) return
                      setRulesViewStatus('loading')
                      fetchRules(selectedLibrary.id)
                    }} title="刷新规则列表" style={{ padding: 6, borderRadius: 6, backgroundColor: 'transparent', border: 'none', cursor: 'pointer', color: 'rgb(var(--theme-text-secondary))', display: 'flex', alignItems: 'center' }}><RefreshCw style={{ width: 14, height: 14 }} /></button>
                    <Select value={ruleSourceFilter} onChange={(value) => setRuleSourceFilter(value as 'all' | RuleCreateSource)} options={[{ value: 'all', label: '全部来源' }, { value: 'manual', label: '手动配置' }, { value: 'ai', label: 'AI智能解析' }, { value: 'template', label: '模板导入' }]} style={{ width: 160 }} />
                    <Select value={severityFilter} onChange={(value) => setSeverityFilter(value as 'all' | SeverityLevel)} options={[{ value: 'all', label: '全部程度' }, { value: 'critical', label: '严重' }, { value: 'warning', label: '警告' }, { value: 'info', label: '信息' }]} style={{ width: 140 }} />
                    {/* <button onClick={openImportModal} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 12px', borderRadius: 8, fontSize: 13, fontWeight: 500, color: 'rgb(var(--theme-text))', backgroundColor: 'transparent', border: '1px solid rgb(var(--theme-border))', cursor: 'pointer' }}><Upload style={{ width: 14, height: 14 }} />批量导入模板</button> */}
                    <button onClick={() => openRuleModal()} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 12px', borderRadius: 8, fontSize: 13, fontWeight: 500, color: 'white', backgroundColor: 'rgb(var(--theme-primary))', border: 'none', cursor: 'pointer' }}><Plus style={{ width: 14, height: 14 }} />新建规则</button>
                  </div>
                </div>
              </div>

              <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
                {rulesViewStatus === 'loading' ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}><Loader2 style={{ width: 36, height: 36, color: 'rgb(var(--theme-primary))', animation: 'spin 1s linear infinite' }} /></div>
                ) : rulesViewStatus === 'empty' ? (
                  <EmptyStateCard icon={<Shield />} title="暂无规则" description="添加规则来执行数据质量检测" buttonText="新建规则" onButtonClick={() => openRuleModal()} />
                ) : rulesViewStatus === 'loaded' ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>{rules.map((rule) => <RuleCard key={rule.id} rule={rule} onEdit={() => openRuleModal(rule)} onDelete={() => handleDeleteRule(rule)} onToggle={() => handleToggleRule(rule)} />)}</div>
                ) : null}
              </div>
            </>
          ) : (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><EmptyStateCard icon={<BookOpen />} title="选择规则库" description="从左侧列表选择一个规则库来管理规则" /></div>
          )}
        </div>
      </div>

      <CreateLibraryModal visible={libraryModalVisible} editingLibrary={editingLibrary} onClose={() => { setLibraryModalVisible(false); setEditingLibrary(null) }} onSuccess={fetchLibraries} />

      <Modal
        title={<span style={{ fontWeight: 600, fontSize: 16 }}>{editingRule ? '编辑规则' : '创建规则'}</span>}
        open={ruleModalVisible}
        onCancel={() => { setRuleModalVisible(false); setEditingRule(null) }}
        footer={null}
        width={760}
        centered
        className="rule-modal-dark"
        styles={{ body: { padding: '8px 6px 6px 8px' }, header: { borderBottom: 'none', padding: '12px 6px 6px', marginBottom: 0 } }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', maxHeight: '75vh', minHeight: 'min(560px, 75vh)', overflow: 'hidden' }}>
          <div ref={ruleModalScrollRef} style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto', paddingRight: 6, marginRight: 2, scrollbarWidth: 'thin', scrollbarColor: 'rgba(15,23,42,0.14) transparent', flex: 1, minHeight: 0 }}>
            <div style={{ padding: 12, borderRadius: 12, backgroundColor: 'rgb(var(--theme-bg-secondary))', color: 'rgb(var(--theme-text-secondary))', fontSize: 13, display: 'grid', gap: 4 }}>
              <div>当前创建来源：<span style={{ color: 'rgb(var(--theme-text))', fontWeight: 500 }}>{editingRule?.create_source_name || getCreateSourceDisplayName(getCurrentCreateSource())}</span></div>
            </div>

            {!editingRule ? (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button onClick={() => handleSwitchRuleMode('manual')} style={{ padding: '6px 12px', borderRadius: 9999, border: '1px solid rgb(var(--theme-border))', backgroundColor: ruleCreationMode === 'manual' ? 'rgba(24,144,255,0.12)' : 'transparent', color: ruleCreationMode === 'manual' ? '#1677ff' : 'rgb(var(--theme-text-secondary))', cursor: 'pointer' }}>手动专家模式</button>
                <button onClick={() => handleSwitchRuleMode('ai')} style={{ padding: '6px 12px', borderRadius: 9999, border: '1px solid rgb(var(--theme-border))', backgroundColor: ruleCreationMode === 'ai' ? 'rgba(24,144,255,0.12)' : 'transparent', color: ruleCreationMode === 'ai' ? '#1677ff' : 'rgb(var(--theme-text-secondary))', cursor: 'pointer' }}>自然语言模式</button>
                <button onClick={() => handleSwitchRuleMode('template')} style={{ padding: '6px 12px', borderRadius: 9999, border: '1px solid rgb(var(--theme-border))', backgroundColor: ruleCreationMode === 'template' ? 'rgba(24,144,255,0.12)' : 'transparent', color: ruleCreationMode === 'template' ? '#1677ff' : 'rgb(var(--theme-text-secondary))', cursor: 'pointer' }}>单条模板建规则</button>
              </div>
            ) : (
              <div style={{ padding: 10, borderRadius: 10, border: '1px dashed rgb(var(--theme-border))', fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>编辑态下不允许切换创建来源模式；如需变更来源，请重新创建一条规则。</div>
            )}

            {!editingRule && (
              <div style={{ padding: 12, borderRadius: 12, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg-secondary))', fontSize: 13, color: 'rgb(var(--theme-text-secondary))' }}>
                {ruleCreationMode === 'manual' && '专家模式适合对目标表、目标列和检测条件进行精细化配置。'}
                {ruleCreationMode === 'ai' && '通过自然语言描述质检需求，系统自动识别并生成规则配置与 SQL。'}
                {ruleCreationMode === 'template' && '选择模板后会自动回填规则信息，再选择目标表和列即可创建规则。'}
              </div>
            )}

            {ruleCreationMode === 'ai' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: 12, borderRadius: 12, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg-secondary))' }}>
                <div style={{ fontWeight: 500, color: 'rgb(var(--theme-text))' }}>信息</div>
                {/* 规则名称、规则类型、严重程度 */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>规则名称 *</label>
                    <Input
                      value={ruleForm.rule_name}
                      onChange={(e) => setRuleForm({ ...ruleForm, rule_name: e.target.value })}
                      placeholder="例如：订单金额不能为负"
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>规则类型</label>
                    <Select
                      value={ruleForm.rule_type || undefined}
                      onChange={(value) => {
                        clearRulePreviewState()
                        setRuleForm({ ...ruleForm, rule_type: value as RuleType || 'null_check' })
                      }}
                      options={ruleTypeOptions}
                      showSearch
                      allowClear
                      placeholder="自动推断"
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>严重程度</label>
                    <Select
                      value={ruleForm.severity}
                      onChange={(value) => setRuleForm({ ...ruleForm, severity: value })}
                      options={severityOptions}
                      style={{ width: '100%' }}
                    />
                  </div>
                </div>
                {/* 目标表、目标列 */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>目标表</label>
                    <Select
                      value={ruleForm.target_table || undefined}
                      onDropdownVisibleChange={(open) => { if (open) void ensureDatasourceTablesLoaded() }}
                      onChange={(value) => {
                        clearRulePreviewState()
                        setRuleForm({ ...ruleForm, target_table: value || '', target_column: '' })
                        if (value) void ensureTableColumnsLoaded(value, true)
                      }}
                      options={getTableSelectOptions()}
                      optionLabelProp="title"
                      loading={tableOptionsLoading}
                      showSearch
                      allowClear
                      placeholder="可选"
                      optionFilterProp="label"
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>目标列</label>
                    <Select
                      value={ruleForm.target_column || undefined}
                      onDropdownVisibleChange={(open) => { if (open && ruleForm.target_table) void ensureTableColumnsLoaded(ruleForm.target_table) }}
                      onChange={(value) => {
                        clearRulePreviewState()
                        setRuleForm({ ...ruleForm, target_column: value || '' })
                      }}
                      options={getColumnSelectOptions(ruleForm.target_table)}
                      optionLabelProp="title"
                      loading={columnOptionsLoading && columnOptionsTable === ruleForm.target_table}
                      showSearch
                      allowClear
                      disabled={!ruleForm.target_table}
                      placeholder={ruleForm.target_table ? '可选' : '先选表'}
                      optionFilterProp="label"
                      style={{ width: '100%' }}
                    />
                  </div>
                </div>
                <div>
                  <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>规则描述 *（用于生成校验SQL的自然语言）</label>
                  <Input.TextArea
                    value={naturalLanguageInput}
                    onChange={(e) => setNaturalLanguageInput(e.target.value)}
                    rows={3}
                    placeholder="例如：检查订单金额字段必须大于0，如果为负则记录一条违规"
                  />
                </div>

                {/* 条件表达式编辑（AI模式编辑态下可编辑） */}
                {editingRule && (
                  <>
                    {/* 单条件编辑 */}
                    {ruleForm.rule_type !== 'composite' && (
                      <div>
                        <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>条件表达式</label>
                        <Input.TextArea
                          value={ruleForm.condition_expr}
                          onChange={(e) => {
                            setRuleForm({ ...ruleForm, condition_expr: e.target.value })
                            setAiConditionEdited(true)
                          }}
                          onBlur={() => {
                            // AI模式：条件表达式变化后，若已有解析结果，清除预览SQL让用户重新预览
                            if (ruleCreationMode === 'ai' && parsedPrimaryResult && ruleForm.condition_expr !== parsedPrimaryResult.condition_expr) {
                              clearRulePreviewState()
                            }
                          }}
                          placeholder="请输入条件表达式，例如 column IS NULL OR column = ''"
                          rows={2}
                        />
                      </div>
                    )}
                    {/* 复合条件编辑（复用手动模式组件） */}
                    {ruleForm.rule_type === 'composite' && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: 14, borderRadius: 14, border: '1px solid rgba(24,144,255,0.18)', background: 'linear-gradient(180deg, rgba(var(--theme-bg-secondary), 0.8) 0%, rgba(var(--theme-bg-tertiary), 0.6) 100%)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                          <div>
                            <div style={{ fontWeight: 600, color: 'rgb(var(--theme-text))' }}>复合规则配置</div>
                            <div style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))', marginTop: 4 }}>复合规则只要求目标表，具体列条件请在下方逐条配置。</div>
                          </div>
                          <button onClick={addCompositeCondition} style={{ padding: '6px 12px', borderRadius: 9999, border: '1px solid rgba(24,144,255,0.24)', backgroundColor: 'rgb(var(--theme-bg))', color: '#1677ff', cursor: 'pointer', boxShadow: '0 1px 2px rgba(0,0,0,0.04)' }}>添加条件</button>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                          <div style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))' }}>连接方式</div>
                          <button onClick={() => { const originalSql = originalEditingRule?.sql_text; clearRulePreviewState(); if (originalSql !== undefined) setRuleForm(prev => ({ ...prev, sql_text: originalSql || '' })); const newMode = 'AND'; setConditionMode(newMode); setAiConditionEdited(originalEditingRule ? newMode !== (getRuleConditionMode(originalEditingRule) || 'AND') : true) }} style={{ padding: '6px 12px', borderRadius: 9999, border: '1px solid rgb(var(--theme-border))', backgroundColor: conditionMode === 'AND' ? 'rgba(24,144,255,0.12)' : 'rgb(var(--theme-bg))', color: conditionMode === 'AND' ? '#1677ff' : 'rgb(var(--theme-text-secondary))', cursor: 'pointer' }}>AND</button>
                          <button onClick={() => { const originalSql = originalEditingRule?.sql_text; clearRulePreviewState(); if (originalSql !== undefined) setRuleForm(prev => ({ ...prev, sql_text: originalSql || '' })); const newMode = 'OR'; setConditionMode(newMode); setAiConditionEdited(originalEditingRule ? newMode !== (getRuleConditionMode(originalEditingRule) || 'AND') : true) }} style={{ padding: '6px 12px', borderRadius: 9999, border: '1px solid rgb(var(--theme-border))', backgroundColor: conditionMode === 'OR' ? 'rgba(24,144,255,0.12)' : 'rgb(var(--theme-bg))', color: conditionMode === 'OR' ? '#1677ff' : 'rgb(var(--theme-text-secondary))', cursor: 'pointer' }}>OR</button>
                        </div>
                        {compositeConditions.length === 0 ? (
                          <div style={{ padding: 12, borderRadius: 10, backgroundColor: 'rgb(var(--theme-bg-secondary))', fontSize: 13, color: 'rgb(var(--theme-text-secondary))', border: '1px dashed rgb(var(--theme-border))' }}>当前暂无条件，点击右上角"添加条件"开始配置。</div>
                        ) : (
                          <div style={{ display: 'grid', gap: 8 }}>
                            {compositeConditions.map((condition, index) => (
                              <div key={index} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 8, padding: 10, borderRadius: 10, backgroundColor: 'rgb(var(--theme-bg-secondary))', border: '1px solid rgb(var(--theme-border))' }}>
                                <Select
                                  value={condition.column || undefined}
                                  onDropdownVisibleChange={(open) => { if (open && ruleForm.target_table) void ensureTableColumnsLoaded(ruleForm.target_table) }}
                                  onChange={(value) => updateCompositeCondition(index, 'column', value || '')}
                                  options={getColumnSelectOptions(ruleForm.target_table)}
                                  optionLabelProp="title"
                                  loading={columnOptionsLoading && columnOptionsTable === ruleForm.target_table}
                                  showSearch
                                  allowClear
                                  disabled={!ruleForm.target_table}
                                  placeholder={ruleForm.target_table ? (index === 0 ? '默认第一条条件的列名' : '请选择追加条件的列名') : '请先选择目标表'}
                                  optionFilterProp="label"
                                />
                                <Input value={condition.condition} onChange={(e) => { const updated = [...compositeConditions]; updated[index] = { ...updated[index], condition: e.target.value }; setCompositeConditions(updated); setAiConditionEdited(true) }} placeholder={index === 0 ? '默认第一条条件表达式，例如 column >= 0' : '追加条件表达式'} />
                                <button onClick={() => removeCompositeCondition(index)} disabled={compositeConditions.length === 1} style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid rgba(239,68,68,0.4)', backgroundColor: 'rgba(239,68,68,0.1)', color: '#f87171', cursor: compositeConditions.length === 1 ? 'not-allowed' : 'pointer', opacity: compositeConditions.length === 1 ? 0.5 : 1 }}>删除</button>
                              </div>
                            ))}
                            <div style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))' }}>条件预览：{getCompositePreview() || '暂无'}</div>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                  <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>目标表、目标列、规则类型均为可选参数，AI会自动推断，指定可提高解析准确度。</div>
                  {(() => {
                    // 只有当规则描述（自然语言）或目标表/目标列改变了才显示清空和AI解析按钮
                    const nlChanged = editingRule ? naturalLanguageInput !== (originalEditingRule?.description || '') : naturalLanguageInput.trim() !== ''
                    const targetTableChanged = editingRule ? (ruleForm.target_table || '') !== (originalEditingRule?.target_table || '') : false
                    const targetColumnChanged = editingRule ? (ruleForm.target_column || '') !== (originalEditingRule?.target_column || '') : false
                    const needsReParse = nlChanged || targetTableChanged || targetColumnChanged
                    if (!needsReParse) {
                      return <div style={{ fontSize: 12, color: parsedPrimaryResult ? '#389e0d' : 'rgb(var(--theme-text-muted))' }}>{parsedPrimaryResult ? '已解析成功，请确认信息无误后创建规则' : '请输入规则描述并进行AI解析'}</div>
                    }
                    return (
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button onClick={() => { clearRulePreviewState(); setParseCandidates(null); setParseNeedsConfirmation(false); setParsedPrimaryResult(null); setNaturalLanguageInput(''); setParsedConfidence(null) }} disabled={!naturalLanguageInput.trim() && !parsedPrimaryResult} style={{ padding: '4px 10px', borderRadius: 6, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'transparent', cursor: (naturalLanguageInput.trim() || parsedPrimaryResult) ? 'pointer' : 'not-allowed', color: (naturalLanguageInput.trim() || parsedPrimaryResult) ? 'rgb(var(--theme-text))' : 'rgb(var(--theme-text-muted))', fontSize: 12 }}>清空</button>
                        <button onClick={handleParseRule} disabled={parseLoading || !naturalLanguageInput.trim() || !ruleForm.rule_name.trim()} style={{ padding: '6px 12px', borderRadius: 6, border: 'none', color: 'white', backgroundColor: parseLoading || !naturalLanguageInput.trim() || !ruleForm.rule_name.trim() ? 'rgba(24,144,255,0.6)' : 'rgb(var(--theme-primary))', cursor: parseLoading || !naturalLanguageInput.trim() || !ruleForm.rule_name.trim() ? 'not-allowed' : 'pointer', fontSize: 14, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          {parseLoading && <Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} />}
                          {parseLoading ? '解析中...' : 'AI解析'}
                        </button>
                      </div>
                    )
                  })()}
                </div>

                {/* 候选列表展示区域（基于 stage 的多阶段交互） */}
                {parseNeedsConfirmation && parseCandidates && (
                  <div style={{ display: 'grid', gap: 12, padding: 16, borderRadius: 12, backgroundColor: 'rgb(var(--theme-bg))', border: '1px solid rgba(24,144,255,0.3)' }}>

                    {/* 表候选阶段：顶部预览信息 */}
                    {parseCandidates.type === 'table' && parsedPrimaryResult && (
                      <div style={{ display: 'grid', gap: 8, padding: 12, borderRadius: 8, backgroundColor: 'rgba(24,144,255,0.05)', border: '1px solid rgba(24,144,255,0.15)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                          <span style={{ fontSize: 13, fontWeight: 600, color: '#1677ff' }}>规则预览</span>
                          <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>
                            规则类型：<span style={{ color: '#1677ff', fontWeight: 500 }}>{getRuleDisplayName({ rule_type: parsedPrimaryResult.rule_type } as GovernanceRule) || parsedPrimaryResult.rule_type}</span>
                          </span>
                          {parsedConfidence !== null && (
                            <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>
                              置信度：<span style={{ fontWeight: 500 }}>{Math.round(parsedConfidence * 100)}%</span>
                            </span>
                          )}
                        </div>
                    {showSqlPreview && (
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 500, color: '#1677ff', marginBottom: 4 }}>SQL预览：</div>
                        <pre style={{ margin: 0, padding: '8px 10px', borderRadius: 6, backgroundColor: 'rgba(15,23,42,0.04)', fontSize: 10, color: 'rgb(var(--theme-text-secondary))', overflow: 'auto', maxHeight: 80 }}>{rulePreviewSql}</pre>
                      </div>
                    )}
                      </div>
                    )}

                    {/* 多列候选阶段：顶部不显示预览（rule_config 为 null） */}
                    {/* 阶段标题 */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 15, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>
                          {parseCandidates.type === 'table' ? '请选择目标表' : parseCandidates.type === 'multi_column' ? '请勾选目标列' : '请选择目标列'}
                        </span>
                        <span style={{ fontSize: 12, color: '#1677ff', backgroundColor: 'rgba(22,119,255,0.1)', borderRadius: 9999, padding: '2px 10px' }}>
                          {parseCandidates.items.length} 个候选
                        </span>
                      </div>
                      <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>{parseReasoning}</span>
                    </div>

                    {/* 多列候选：已选中列展示 */}
                    {parseCandidates.type === 'multi_column' && selectedMultiColumns.length > 0 && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 8, backgroundColor: 'rgba(82,196,26,0.08)', border: '1px solid rgba(82,196,26,0.2)' }}>
                        <span style={{ fontSize: 12, color: '#389e0d', fontWeight: 500 }}>已选择：</span>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          {selectedMultiColumns.map((col) => (
                            <span key={col} style={{ fontSize: 12, color: '#389e0d', backgroundColor: 'rgba(82,196,26,0.15)', padding: '2px 8px', borderRadius: 4 }}>
                              {col}
                            </span>
                          ))}
                        </div>
                        <button
                          onClick={() => setSelectedMultiColumns([])}
                          style={{ marginLeft: 'auto', padding: '2px 8px', fontSize: 11, border: 'none', backgroundColor: 'transparent', color: 'rgb(var(--theme-text-muted))', cursor: 'pointer' }}
                        >
                          清除
                        </button>
                      </div>
                    )}

                    {/* 候选卡片列表 */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      {parseCandidates.items.map((candidate, index) => (
                        <CandidateCard
                          key={`${candidate.name}-${index}`}
                          candidate={candidate}
                          type={parseCandidates.type}
                          isLoading={parseLoading}
                          selectedColumns={selectedMultiColumns}
                          onToggleColumn={(colName) => {
                            const pureColName = colName.split('（')[0]
                            setSelectedMultiColumns((prev) =>
                              prev.includes(pureColName)
                                ? prev.filter((c) => c !== pureColName)
                                : [...prev, pureColName]
                            )
                          }}
                          onSelect={() => !parseLoading && handleSelectCandidate(candidate)}
                        />
                      ))}
                    </div>

                    {/* 多列候选：确认按钮 */}
                    {parseCandidates.type === 'multi_column' && selectedMultiColumns.length > 0 && (
                      <div style={{ display: 'flex', justifyContent: 'center', padding: '8px 0' }}>
                        <button
                          onClick={handleConfirmMultiColumns}
                          disabled={parseLoading}
                          style={{ padding: '10px 28px', borderRadius: 8, border: 'none', backgroundColor: '#389e0d', color: 'white', fontSize: 14, fontWeight: 500, cursor: parseLoading ? 'not-allowed' : 'pointer', display: 'inline-flex', alignItems: 'center', gap: 8 }}
                        >
                          {parseLoading && <Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} />}
                          {parseLoading ? '正在解析选中项...' : `确认并生成 ${selectedMultiColumns.length} 条规则`}
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* 多条规则预览（multi_preview 阶段） */}
                {parseStage === 'multi_preview' && multiRuleConfigs.length > 0 && (
                  <div style={{ display: 'grid', gap: 12, padding: 16, borderRadius: 12, backgroundColor: 'rgb(var(--theme-bg))', border: '1px solid rgba(250,173,20,0.3)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 15, fontWeight: 600, color: '#fa8c16' }}>多条规则预览</span>
                      <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>{parseReasoning}</span>
                    </div>

                    {/* 全选/取消全选 */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px', borderRadius: 8, backgroundColor: 'rgb(var(--theme-bg-secondary))' }}>
                      <div
                        onClick={() => {
                          if (selectedRuleIndices.length === multiRuleConfigs.length) {
                            setSelectedRuleIndices([])
                          } else {
                            setSelectedRuleIndices(multiRuleConfigs.map((_, idx) => idx))
                          }
                        }}
                        style={{
                          width: 20,
                          height: 20,
                          borderRadius: 4,
                          border: `2px solid ${selectedRuleIndices.length === multiRuleConfigs.length ? '#389e0d' : 'rgb(var(--theme-border))'}`,
                          backgroundColor: selectedRuleIndices.length === multiRuleConfigs.length ? '#389e0d' : 'transparent',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          cursor: 'pointer',
                        }}
                      >
                        {selectedRuleIndices.length === multiRuleConfigs.length && (
                          <Check size={14} style={{ color: 'white' }} />
                        )}
                      </div>
                      <span style={{ fontSize: 13, color: 'rgb(var(--theme-text))' }}>
                        全选 ({selectedRuleIndices.length}/{multiRuleConfigs.length})
                      </span>
                    </div>

                    {/* 规则卡片列表 */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      {multiRuleConfigs.map((config, index) => {
                        const isSelected = selectedRuleIndices.includes(index)
                        return (
                          <div
                            key={index}
                            style={{
                              display: 'flex',
                              flexDirection: 'column',
                              gap: 10,
                              padding: 14,
                              borderRadius: 10,
                              backgroundColor: isSelected ? 'rgba(82,196,26,0.05)' : 'rgb(var(--theme-bg-secondary))',
                              border: `1px solid ${isSelected ? 'rgba(82,196,26,0.4)' : 'rgb(var(--theme-border))'}`,
                              transition: 'all 0.2s ease',
                            }}
                            onClick={() => {
                              setSelectedRuleIndices((prev) =>
                                prev.includes(index)
                                  ? prev.filter((i) => i !== index)
                                  : [...prev, index]
                              )
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                <div
                                  style={{
                                    width: 20,
                                    height: 20,
                                    borderRadius: 4,
                                    border: `2px solid ${isSelected ? '#389e0d' : 'rgb(var(--theme-border))'}`,
                                    backgroundColor: isSelected ? '#389e0d' : 'transparent',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    cursor: 'pointer',
                                  }}
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    setSelectedRuleIndices((prev) =>
                                      prev.includes(index)
                                        ? prev.filter((i) => i !== index)
                                        : [...prev, index]
                                    )
                                  }}
                                >
                                  {isSelected && <Check size={14} style={{ color: 'white' }} />}
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                  <span style={{ fontSize: 14, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>
                                    {config.target_column}
                                  </span>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <span style={{ fontSize: 11, color: '#fa8c16', backgroundColor: 'rgba(250,173,20,0.1)', padding: '1px 6px', borderRadius: 4 }}>
                                      {getRuleDisplayName({ rule_type: config.rule_type } as GovernanceRule) || config.rule_type}
                                    </span>
                                    <span style={{ fontSize: 11, color: severityColors[config.severity] || 'rgb(var(--theme-text-muted))' }}>
                                      {getSeverityDisplayName({ severity: config.severity as SeverityLevel } as GovernanceRule)}
                                    </span>
                                  </div>
                                </div>
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <span style={{ fontSize: 12, color: '#389e0d', backgroundColor: 'rgba(82,196,26,0.1)', padding: '2px 8px', borderRadius: 4 }}>
                                  {Math.round(config.confidence * 100)}% 置信度
                                </span>
                              </div>
                            </div>

                            {/* SQL预览 */}
                            {config.sql_preview && (
                              <div style={{ padding: '8px 10px', borderRadius: 6, backgroundColor: 'rgba(15,23,42,0.04)' }}>
                                <div style={{ fontSize: 11, fontWeight: 500, color: 'rgb(var(--theme-text-secondary))', marginBottom: 4 }}>SQL预览</div>
                                <pre style={{ margin: 0, fontSize: 10, color: 'rgb(var(--theme-text-secondary))', overflow: 'auto', maxHeight: 60 }}>{config.sql_preview}</pre>
                              </div>
                            )}

                            {/* 解析说明 */}
                            {config.reasoning && (
                              <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>
                                {config.reasoning}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>

                    {/* 批量创建按钮 */}
                    {selectedRuleIndices.length > 0 && (
                      <div style={{ display: 'flex', justifyContent: 'center', padding: '8px 0' }}>
                        <button
                          onClick={async () => {
                            // 遍历选中的规则，逐条创建
                            for (const idx of selectedRuleIndices) {
                              const config = multiRuleConfigs[idx]
                              // 这里调用创建规则接口
                              // 需要根据实际接口调整
                              try {
                                await createGovernanceRule({
                                  library_id: selectedLibrary!.id,
                                  datasource_id: selectedLibrary!.datasource_id!,
                                  user_input: originalParseInput?.user_input,
                                  rule_config: {
                                    rule_type: config.rule_type,
                                    target_table: ruleForm.target_table,
                                    target_column: config.target_column,
                                    condition_expr: config.condition_expr,
                                    severity: config.severity as SeverityLevel,
                                  }
                                } as any)
                              } catch (error) {
                                console.error('创建规则失败', error)
                              }
                            }
                            message.success(`已成功创建 ${selectedRuleIndices.length} 条规则`)
                            // 重置状态
                            setMultiRuleConfigs([])
                            setSelectedRuleIndices([])
                            setParseStage('')
                            setParseCandidates(null)
                            setParseNeedsConfirmation(false)
                          }}
                          style={{ padding: '10px 28px', borderRadius: 8, border: 'none', backgroundColor: '#389e0d', color: 'white', fontSize: 14, fontWeight: 500, cursor: 'pointer' }}
                        >
                          确认创建 {selectedRuleIndices.length} 条规则
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* 解析成功结果展示（rule_preview 阶段） */}
                {parsedPrimaryResult && !parseNeedsConfirmation && parseStage === 'rule_preview' && (
                  <div style={{ display: 'grid', gap: 10, padding: 12, borderRadius: 10, backgroundColor: 'rgb(var(--theme-bg))', border: '1px solid rgba(82,196,26,0.3)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 14, fontWeight: 600, color: '#389e0d' }}>解析成功</span>
                      {parseStage && (
                        <span style={{ fontSize: 12, color: '#1677ff', backgroundColor: 'rgba(22,119,255,0.1)', borderRadius: 9999, padding: '2px 10px' }}>
                          {parseStage === 'rule_preview' ? '规则预览' : parseStage === 'multi_preview' ? '多规则预览' : parseStage}
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, fontSize: 12 }}>
                      <div style={{ padding: '8px 10px', borderRadius: 6, backgroundColor: 'rgb(var(--theme-bg-secondary))' }}>
                        <div style={{ color: 'rgb(var(--theme-text-secondary))', marginBottom: 4 }}>规则类型</div>
                        <div style={{ color: 'rgb(var(--theme-text))', fontWeight: 500 }}>{getRuleDisplayName({ rule_type: parsedPrimaryResult.rule_type } as GovernanceRule) || parsedPrimaryResult.rule_type}</div>
                      </div>
                      <div style={{ padding: '8px 10px', borderRadius: 6, backgroundColor: 'rgb(var(--theme-bg-secondary))' }}>
                        <div style={{ color: 'rgb(var(--theme-text-secondary))', marginBottom: 4 }}>置信度</div>
                        <div style={{ color: 'rgb(var(--theme-text))', fontWeight: 500 }}>
                          {parsedConfidence !== null ? `${Math.round(parsedConfidence * 100)}%` : '未返回'}
                        </div>
                      </div>
                      <div style={{ padding: '8px 10px', borderRadius: 6, backgroundColor: 'rgb(var(--theme-bg-secondary))' }}>
                        <div style={{ color: 'rgb(var(--theme-text-secondary))', marginBottom: 4 }}>严重程度</div>
                        <div style={{ color: severityColors[parsedPrimaryResult.severity || 'warning'], fontWeight: 500 }}>
                          {getSeverityDisplayName({ severity: (parsedPrimaryResult.severity as SeverityLevel) || 'warning' } as GovernanceRule)}
                        </div>
                      </div>
                    </div>
                    {parsedPrimaryResult.target_table && (
                      <div style={{ fontSize: 13, color: 'rgb(var(--theme-text))', padding: '8px 10px', borderRadius: 6, backgroundColor: 'rgb(var(--theme-bg-secondary))' }}>
                        <span style={{ color: 'rgb(var(--theme-text-secondary))' }}>目标定位：</span>
                        <span style={{ fontWeight: 600, color: '#1677ff' }}>{parsedPrimaryResult.target_table}</span>
                        {parsedPrimaryResult.target_column && (
                          <>
                            <span style={{ color: 'rgb(var(--theme-text-secondary))' }}> → </span>
                            <span style={{ fontWeight: 600, color: '#722ed1' }}>{parsedPrimaryResult.target_column}</span>
                          </>
                        )}
                      </div>
                    )}
                    {parsedPrimaryResult.condition_expr && ruleForm.rule_type !== 'composite' && (
                      <div style={{ fontSize: 13, color: 'rgb(var(--theme-text))', padding: '8px 10px', borderRadius: 6, backgroundColor: 'rgb(var(--theme-bg-secondary))' }}>
                        <span style={{ color: 'rgb(var(--theme-text-secondary))' }}>条件表达式（可编辑）：</span>
                        <Input.TextArea value={ruleForm.condition_expr} onChange={(e) => { setRuleForm({ ...ruleForm, condition_expr: e.target.value }); setParsedPrimaryResult((prev) => prev ? { ...prev, condition_expr: e.target.value } : prev); setAiConditionEdited(true) }} placeholder="请输入条件表达式" rows={1} style={{ marginTop: 4, fontSize: 12 }} />
                        {aiConditionEdited && <div style={{ fontSize: 11, color: '#d48806', marginTop: 4 }}>条件已修改，请点击下方「SQL 预览」按钮重新生成校验 SQL</div>}
                      </div>
                    )}
                    {parsedPrimaryResult.reasoning && (
                      <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', padding: '6px 0' }}>
                        <span style={{ fontWeight: 500 }}>解析说明：</span>{parsedPrimaryResult.reasoning}
                      </div>
                    )}
                    {/* 复合条件（从 parsedPrimaryResult 同步到 compositeConditions，可编辑） */}
                    {ruleForm.rule_type === 'composite' && compositeConditions.length > 0 && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 10, borderRadius: 8, backgroundColor: 'rgb(var(--theme-bg-secondary))', border: '1px solid rgba(24,144,255,0.18)', overflow: 'hidden' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, minWidth: 0 }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: 'rgb(var(--theme-text))', flexShrink: 0 }}>复合条件（可编辑）</div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
                              <span style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))' }}>连接方式：</span>
                              <button onClick={() => { const originalMode = parsedPrimaryResult?.condition_mode || (originalEditingRule ? getRuleConditionMode(originalEditingRule) || 'AND' : 'AND'); const newMode = 'AND'; setConditionMode(newMode); setAiConditionEdited((prev) => prev || newMode !== originalMode || newMode !== conditionMode) }} style={{ padding: '2px 8px', borderRadius: 4, border: '1px solid', borderColor: conditionMode === 'AND' ? '#1677ff' : 'rgb(var(--theme-border))', backgroundColor: conditionMode === 'AND' ? 'rgba(24,144,255,0.12)' : 'white', color: conditionMode === 'AND' ? '#1677ff' : 'rgb(var(--theme-text-secondary))', cursor: 'pointer', fontSize: 11 }}>AND</button>
                              <button onClick={() => { const originalMode = parsedPrimaryResult?.condition_mode || (originalEditingRule ? getRuleConditionMode(originalEditingRule) || 'AND' : 'AND'); const newMode = 'OR'; setConditionMode(newMode); setAiConditionEdited((prev) => prev || newMode !== originalMode || newMode !== conditionMode) }} style={{ padding: '2px 8px', borderRadius: 4, border: '1px solid', borderColor: conditionMode === 'OR' ? '#1677ff' : 'rgb(var(--theme-border))', backgroundColor: conditionMode === 'OR' ? 'rgba(24,144,255,0.12)' : 'white', color: conditionMode === 'OR' ? '#1677ff' : 'rgb(var(--theme-text-secondary))', cursor: 'pointer', fontSize: 11 }}>OR</button>
                            </div>
                        </div>
                        <div style={{ display: 'grid', gap: 6, minWidth: 0 }}>
                          {compositeConditions.map((cond, idx) => (
                            <div key={idx} style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 6, alignItems: 'center', minWidth: 0 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '0 8px', height: 32, borderRadius: 6, backgroundColor: 'rgba(0,0,0,0.04)', color: 'rgb(var(--theme-text-secondary))', fontSize: 12, border: '1px solid rgb(var(--theme-border))', minWidth: 80, maxWidth: 120 }}>{cond.column}</div>
                              <Input value={cond.condition} onChange={(e) => { const updated = [...compositeConditions]; updated[idx] = { ...updated[idx], condition: e.target.value }; setCompositeConditions(updated); setAiConditionEdited(true) }} placeholder={`条件表达式 ${idx + 1}`} style={{ fontSize: 12 }} />
                            </div>
                          ))}
                        </div>
                        {aiConditionEdited && <div style={{ fontSize: 11, color: '#d48806', marginTop: 4 }}>复合条件已修改，请点击下方「SQL 预览」按钮重新生成校验 SQL</div>}
                      </div>
                    )}
                    {showSqlPreview && (
                      <div style={{ marginTop: 4 }}>
                        <div style={{ fontSize: 12, fontWeight: 500, color: 'rgb(var(--theme-text-secondary))', marginBottom: 6 }}>SQL预览：</div>
                        <pre style={{ margin: 0, padding: '10px 12px', borderRadius: 6, backgroundColor: 'rgba(15,23,42,0.04)', fontSize: 11, color: 'rgb(var(--theme-text-secondary))', overflow: 'auto', maxHeight: 100, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{rulePreviewSql}</pre>
                      </div>
                    )}
                  </div>
                )}

              {/* SQL预览区域（非自然语言模式） */}
              {showSqlPreview && rulePreviewSql && !parsedPrimaryResult && !parseNeedsConfirmation && (
                <div style={{ padding: 12, borderRadius: 12, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))' }}>
                  <div style={{ fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8 }}>SQL 预览{previewScope ? `（${previewScope === 'column' ? '列级' : previewScope === 'table' ? '表级' : '全局'}）` : ''}</div>
                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>{rulePreviewSql}</pre>
                </div>
              )}
              </div>
            )}

            {ruleCreationMode === 'template' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: 12, borderRadius: 12, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg-secondary))' }}>
                {!editingRule && (
                  <div style={{ fontWeight: 500, color: 'rgb(var(--theme-text))' }}>单条模板建规则</div>
                )}

                {/* Template Selection - show in both create and edit mode */}
                <div>
                  <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>
                    {editingRule ? '规则模板' : '步骤1：选择规则模板'} {!editingRule && <span style={{ color: '#f5222d' }}>*</span>}
                    {editingRule && <span style={{ color: 'rgb(var(--theme-text-muted))', fontWeight: 400, fontSize: 12, marginLeft: 8 }}>（可选择更换其他模板）</span>}
                  </label>
                  <Select
                    value={editingRule ? undefined : (templateRuleId || undefined)}
                    onDropdownVisibleChange={async (open) => {
                      if (open) {
                        if (templateGroups.length === 0) {
                          await loadTemplateGroups()
                        }
                      }
                    }}
                    onChange={(value) => {
                      clearRulePreviewState()
                      applyTemplateRule(value)
                    }}
                    placeholder={editingRule ? '请选择要更换的模板' : '请选择一个规则模板'}
                    showSearch
                    filterOption={(input, option) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())}
                    style={{ width: '100%' }}
                    options={[
                      ...templateGroups.flatMap(group =>
                        group.templates.map(t => ({
                          value: t.id,
                          label: `[${group.rule_type_name}] ${t.template_name || t.name || t.id}`,
                          title: `${t.template_name || t.name || t.id}\n${t.description || ''}\n适用列类型: ${t.applicable_columns || 'all'}`,
                        }))
                      )
                    ]}
                    notFoundContent={templatesLoading ? (
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
                        <Loader2 style={{ width: 20, height: 20, color: 'rgb(var(--theme-primary))', animation: 'spin 1s linear infinite' }} />
                        <span style={{ marginLeft: 8, color: 'rgb(var(--theme-text-secondary))' }}>加载模板中...</span>
                      </div>
                    ) : templateGroups.length === 0 ? '暂无可用模板' : null}
                  />
                </div>

                {/* Template Info Card (when template is selected) */}
                {selectedTemplateDetail && (
                  <div style={{ padding: 12, borderRadius: 10, backgroundColor: 'rgb(var(--theme-bg))', border: '1px solid rgba(24,144,255,0.3)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                      <span style={{ fontSize: 12, padding: '2px 8px', borderRadius: 4, backgroundColor: 'rgba(24,144,255,0.12)', color: '#1677ff' }}>
                        {selectedTemplateDetail.rule_type_name || selectedTemplateDetail.rule_type}
                      </span>
                      <span style={{ fontSize: 12, padding: '2px 8px', borderRadius: 4, backgroundColor: `rgba(${selectedTemplateDetail.default_severity === 'critical' ? '245,34,45' : selectedTemplateDetail.default_severity === 'info' ? '24,144,255' : '250,173,20'}, 0.12)`, color: selectedTemplateDetail.default_severity === 'critical' ? '#f5222d' : selectedTemplateDetail.default_severity === 'info' ? '#1890ff' : '#faad14' }}>
                        {selectedTemplateDetail.severity_name || selectedTemplateDetail.default_severity}
                      </span>
                    </div>
                    {selectedTemplateDetail.description && (
                      <div style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))', marginBottom: 8 }}>
                        {selectedTemplateDetail.description}
                      </div>
                    )}
                    {selectedTemplateDetail.applicable_columns && (
                      <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))' }}>
                        <span style={{ fontWeight: 500 }}>适用列类型：</span>
                        {selectedTemplateDetail.applicable_columns}
                      </div>
                    )}
                    {selectedTemplateDetail.has_placeholder && selectedTemplateDetail.condition_placeholder_hint && (
                      <div style={{ fontSize: 12, color: '#d48806', marginTop: 6, padding: '4px 8px', backgroundColor: 'rgba(250,173,20,0.1)', borderRadius: 4 }}>
                        {selectedTemplateDetail.condition_placeholder_hint}
                      </div>
                    )}
                  </div>
                )}

                {/* Common form fields: show when template selected OR in template mode editing */}
                {(selectedTemplateDetail || editingRule) && (
                  <>
                    {!editingRule && (
                      <div style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginTop: 4 }}>步骤2：选择目标表和目标列</div>
                    )}

                    {/* Target Table */}
                    <div>
                      <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>
                        目标表 <span style={{ color: '#f5222d' }}>*</span>
                      </label>
                      <Select
                        value={ruleForm.target_table || undefined}
                        onDropdownVisibleChange={(open) => { if (open) void ensureDatasourceTablesLoaded() }}
                        onChange={(value) => {
                          clearRulePreviewState()
                          const newTable = value || ''
                          setRuleForm({ ...ruleForm, target_table: newTable, target_column: '' })
                          if (value) void ensureTableColumnsLoaded(value, true)
                        }}
                        options={getTableSelectOptions()}
                        optionLabelProp="title"
                        loading={tableOptionsLoading}
                        showSearch
                        allowClear
                        placeholder="请选择目标表"
                        optionFilterProp="label"
                        style={{ width: '100%' }}
                      />
                    </div>

                    {/* Target Column */}
                    <div>
                      <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>
                        目标列 {selectedTemplateDetail?.applicable_columns_list?.length ? '(已过滤)' : ''} <span style={{ color: '#f5222d' }}>*</span>
                      </label>
                      <Select
                        value={ruleForm.target_column || undefined}
                        onDropdownVisibleChange={(open) => { if (open && ruleForm.target_table) void ensureTableColumnsLoaded(ruleForm.target_table) }}
                        onChange={(value) => {
                          clearRulePreviewState()
                          const newColumn = value || ''
                          let nextCondition = ruleForm.condition_expr
                          if (newColumn) {
                            if (selectedTemplateDetail?.has_placeholder) {
                              // 优先使用原始模板条件表达式进行替换
                              const baseCondition = selectedTemplateDetail.default_condition || ruleForm.condition_expr
                              nextCondition = baseCondition.replace(/\bcolumn\b/g, newColumn)
                            } else if (/\bcolumn\b/.test(nextCondition)) {
                              // 如果不是模板规则但条件表达式中有 column 占位符，也进行替换
                              nextCondition = nextCondition.replace(/\bcolumn\b/g, newColumn)
                            }
                          }
                          setRuleForm({ ...ruleForm, target_column: newColumn, condition_expr: nextCondition })
                        }}
                        options={(selectedTemplateDetail ? getFilteredColumnOptions(ruleForm.target_table) : getColumnSelectOptions(ruleForm.target_table)).map(col => ({
                          value: normalizeColumnName(col),
                          label: `${normalizeColumnName(col)}${col.data_type || col.type ? ` (${col.data_type || col.type})` : ''}${col.comment ? ` - ${col.comment}` : ''}`,
                          title: `${normalizeColumnName(col)}${col.comment ? `\n${col.comment}` : ''}\n类型: ${col.data_type || col.type}`,
                        }))}
                        optionLabelProp="title"
                        loading={columnOptionsLoading && columnOptionsTable === ruleForm.target_table}
                        showSearch
                        allowClear
                        disabled={!ruleForm.target_table}
                        placeholder={ruleForm.target_table ? '请选择目标列' : '请先选择目标表'}
                        optionFilterProp="label"
                        style={{ width: '100%' }}
                        notFoundContent={
                          !ruleForm.target_table ? null
                            : columnOptionsLoading && columnOptionsTable === ruleForm.target_table ? (
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
                                <Loader2 style={{ width: 18, height: 18, color: 'rgb(var(--theme-primary))', animation: 'spin 1s linear infinite' }} />
                                <span style={{ marginLeft: 8, color: 'rgb(var(--theme-text-secondary))' }}>加载字段中...</span>
                              </div>
                            )
                            : (selectedTemplateDetail ? getFilteredColumnOptions(ruleForm.target_table) : getColumnSelectOptions(ruleForm.target_table)).length === 0 ? (
                              <div style={{ padding: 12, textAlign: 'center', color: 'rgb(var(--theme-text-muted))' }}>
                                没有找到符合条件的列
                              </div>
                            )
                            : null
                        }
                      />
                      {selectedTemplateDetail?.applicable_columns_list?.length > 0 && ruleForm.target_table && (
                        <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-muted))', marginTop: 4 }}>
                          已按模板要求过滤列类型，当前表符合条件的列：{getFilteredColumnOptions(ruleForm.target_table).map(c => normalizeColumnName(c)).join(', ') || '无'}
                        </div>
                      )}
                    </div>

                    {!editingRule && (
                      <div style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginTop: 4 }}>步骤3：确认规则信息</div>
                    )}

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                      <div>
                        <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>规则名称</label>
                        <Input value={ruleForm.rule_name} onChange={(e) => { clearRulePreviewState(); setRuleForm({ ...ruleForm, rule_name: e.target.value }) }} placeholder="请输入规则名称" />
                      </div>
                      <div>
                        <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>严重程度</label>
                        <Select value={ruleForm.severity} onChange={(value) => { clearRulePreviewState(); setRuleForm({ ...ruleForm, severity: value }) }} options={severityOptions} style={{ width: '100%' }} />
                      </div>
                    </div>

                    <div>
                      <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>规则描述</label>
                      <Input.TextArea
                        value={ruleForm.description}
                        onChange={(e) => { clearRulePreviewState(); setRuleForm({ ...ruleForm, description: e.target.value }) }}
                        placeholder="请输入规则描述（可选）"
                        rows={2}
                      />
                    </div>

                    <div>
                      <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>条件表达式</label>
                      <Input.TextArea
                        value={ruleForm.condition_expr}
                        onChange={(e) => { clearRulePreviewState(); setRuleForm({ ...ruleForm, condition_expr: e.target.value }) }}
                        placeholder="请输入条件表达式，例如 column IS NULL"
                        rows={2}
                      />
                    </div>
                  </>
                )}
              </div>
            )}

            {ruleCreationMode === 'manual' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>规则名称 *</label>
                    <Input value={ruleForm.rule_name} onChange={(e) => { clearRulePreviewState(); setRuleForm({ ...ruleForm, rule_name: e.target.value }) }} placeholder="请输入规则名称" />
                  </div>
                  <div>
                    <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>严重程度</label>
                    <Select value={ruleForm.severity} onChange={(value) => { clearRulePreviewState(); setRuleForm({ ...ruleForm, severity: value }) }} options={severityOptions} style={{ width: '100%' }} />
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>规则类型</label>
                    <Select value={ruleForm.rule_type} onChange={(value) => { clearRulePreviewState(); setRuleForm({ ...ruleForm, rule_type: value, target_column: value === 'composite' ? '' : ruleForm.target_column, condition_expr: value === 'composite' ? '' : ruleForm.condition_expr }); if (value === 'composite') ensureCompositeConditionExists() }} options={ruleTypeOptions} style={{ width: '100%' }} />
                  </div>
                  <div>
                    <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>描述</label>
                    <Input value={ruleForm.description} onChange={(e) => { clearRulePreviewState(); setRuleForm({ ...ruleForm, description: e.target.value }) }} placeholder="请输入规则描述（可选）" />
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: ruleForm.rule_type === 'composite' ? '1fr' : '1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>目标表 *</label>
                    <Select
                      value={ruleForm.target_table || undefined}
                      onDropdownVisibleChange={(open) => { if (open) void ensureDatasourceTablesLoaded() }}
                      onChange={(value) => {
                        clearRulePreviewState()
                        const newTable = value || ''
                        const shouldClearColumn = newTable !== originalEditingRule?.target_table
                        setRuleForm({ ...ruleForm, target_table: newTable, target_column: shouldClearColumn ? '' : ruleForm.target_column })
                        if (value) void ensureTableColumnsLoaded(value, true)
                      }}
                      options={getTableSelectOptions()}
                      optionLabelProp="title"
                      loading={tableOptionsLoading}
                      showSearch
                      allowClear
                      placeholder="手动专家模式必填，请选择或搜索目标表"
                      optionFilterProp="label"
                      style={{ width: '100%' }}
                    />
                  </div>
                  {ruleForm.rule_type !== 'composite' && (
                    <div>
                      <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>目标列 *</label>
                      <Select
                        value={ruleForm.target_column || undefined}
                        onDropdownVisibleChange={(open) => { if (open && ruleForm.target_table) void ensureTableColumnsLoaded(ruleForm.target_table) }}
                        onChange={(value) => {
                          clearRulePreviewState()
                          setRuleForm({ ...ruleForm, target_column: value || '' })
                        }}
                        options={getColumnSelectOptions(ruleForm.target_table)}
                        optionLabelProp="title"
                        loading={columnOptionsLoading && columnOptionsTable === ruleForm.target_table}
                        showSearch
                        allowClear
                        disabled={!ruleForm.target_table}
                        placeholder={ruleForm.target_table ? '手动专家模式必填，请选择或搜索目标列' : '请先选择目标表'}
                        optionFilterProp="label"
                        style={{ width: '100%' }}
                      />
                    </div>
                  )}
                </div>
                {ruleForm.rule_type !== 'composite' && (
                  <div>
                    <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>条件表达式 *</label>
                    <Input.TextArea value={ruleForm.condition_expr} onChange={(e) => { clearRulePreviewState(); setRuleForm({ ...ruleForm, condition_expr: e.target.value }) }} placeholder="请输入条件表达式，例如 column IS NULL OR column = ''" rows={2} />
                  </div>
                )}
              </div>
            )}

            {ruleCreationMode === 'manual' && ruleForm.rule_type === 'composite' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: 14, borderRadius: 14, border: '1px solid rgba(24,144,255,0.18)', background: 'linear-gradient(180deg, rgba(24,144,255,0.06) 0%, rgba(24,144,255,0.02) 100%)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                  <div>
                    <div style={{ fontWeight: 600, color: 'rgb(var(--theme-text))' }}>复合规则配置</div>
                    <div style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))', marginTop: 4 }}>复合规则只要求目标表，具体列条件请在下方逐条配置，系统会默认生成第一条条件。</div>
                  </div>
                  <button onClick={addCompositeCondition} style={{ padding: '6px 12px', borderRadius: 9999, border: '1px solid rgba(24,144,255,0.24)', backgroundColor: 'white', color: '#1677ff', cursor: 'pointer', boxShadow: '0 1px 2px rgba(0,0,0,0.04)' }}>添加条件</button>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <div style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))' }}>连接方式</div>
                  <button onClick={() => { const originalSql = originalEditingRule?.sql_text; clearRulePreviewState(); if (originalSql !== undefined) setRuleForm(prev => ({ ...prev, sql_text: originalSql || '' })); setConditionMode('AND') }} style={{ padding: '6px 12px', borderRadius: 9999, border: '1px solid rgb(var(--theme-border))', backgroundColor: conditionMode === 'AND' ? 'rgba(24,144,255,0.12)' : 'white', color: conditionMode === 'AND' ? '#1677ff' : 'rgb(var(--theme-text-secondary))', cursor: 'pointer' }}>AND</button>
                  <button onClick={() => { const originalSql = originalEditingRule?.sql_text; clearRulePreviewState(); if (originalSql !== undefined) setRuleForm(prev => ({ ...prev, sql_text: originalSql || '' })); setConditionMode('OR') }} style={{ padding: '6px 12px', borderRadius: 9999, border: '1px solid rgb(var(--theme-border))', backgroundColor: conditionMode === 'OR' ? 'rgba(24,144,255,0.12)' : 'white', color: conditionMode === 'OR' ? '#1677ff' : 'rgb(var(--theme-text-secondary))', cursor: 'pointer' }}>OR</button>
                </div>
                {compositeConditions.length === 0 ? (
                  <div style={{ padding: 12, borderRadius: 10, backgroundColor: 'rgba(255,255,255,0.72)', fontSize: 13, color: 'rgb(var(--theme-text-secondary))', border: '1px dashed rgb(var(--theme-border))' }}>当前暂无条件，点击右上角“添加条件”开始配置。</div>
                ) : (
                  <div style={{ display: 'grid', gap: 8 }}>
                    {compositeConditions.map((condition, index) => (
                      <div key={index} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 8, padding: 10, borderRadius: 10, backgroundColor: 'rgba(255,255,255,0.82)', border: '1px solid rgba(24,144,255,0.12)' }}>
                        <Select
                          value={condition.column || undefined}
                          onDropdownVisibleChange={(open) => { if (open && ruleForm.target_table) void ensureTableColumnsLoaded(ruleForm.target_table) }}
                          onChange={(value) => updateCompositeCondition(index, 'column', value || '')}
                          options={getColumnSelectOptions(ruleForm.target_table)}
                          optionLabelProp="title"
                          loading={columnOptionsLoading && columnOptionsTable === ruleForm.target_table}
                          showSearch
                          allowClear
                          disabled={!ruleForm.target_table}
                          placeholder={ruleForm.target_table ? (index === 0 ? '默认第一条条件的列名' : '请选择追加条件的列名') : '请先选择目标表'}
                          optionFilterProp="label"
                        />
                        <Input value={condition.condition} onChange={(e) => updateCompositeCondition(index, 'condition', e.target.value)} placeholder={index === 0 ? '默认第一条条件表达式，例如 column >= 0' : '追加条件表达式'} />
                        <button onClick={() => removeCompositeCondition(index)} disabled={compositeConditions.length === 1} style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'transparent', cursor: compositeConditions.length === 1 ? 'not-allowed' : 'pointer', opacity: compositeConditions.length === 1 ? 0.5 : 1 }}>删除</button>
                      </div>
                    ))}
                    <div style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))' }}>条件预览：{getCompositePreview() || '暂无'}</div>
                  </div>
                )}
              </div>
            )}

            {editingRule && (
              <div>
                <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>SQL 语句</label>
                <Input.TextArea
                  ref={sqlTextareaRef}
                  value={ruleForm.sql_text}
                  onChange={(e) => { setRuleForm({ ...ruleForm, sql_text: e.target.value }); setTimeout(() => adjustSqlTextareaHeight(), 0) }}
                  placeholder="规则对应的检测 SQL 语句，可用于预览和执行"
                  style={{ fontFamily: "'Fira Code', 'Cascadia Code', 'Consolas', monospace", fontSize: 12 }}
                  autoSize={{ minRows: 2, maxRows: 30 }}
                />
              </div>
            )}

            {!editingRule && (
              <div style={{ padding: 12, borderRadius: 14, border: '1px solid rgb(var(--theme-border))', background: 'linear-gradient(180deg, rgb(var(--theme-bg-secondary)) 0%, rgba(24,144,255,0.03) 100%)', boxShadow: '0 4px 14px rgba(15,23,42,0.04)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                  <div style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))' }}>
                    <span style={{ fontWeight: 600, color: 'rgb(var(--theme-text))' }}>AI 智能规则建议</span>
                    <span style={{ marginLeft: 8 }}>基于数据源结构智能推荐质量检测规则</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    {smartSuggestions.length > 0 && (
                      <button
                        onClick={() => setSuggestionsCollapsed((prev) => !prev)}
                        title={suggestionsCollapsed ? '展开建议' : '收起建议'}
                        aria-label={suggestionsCollapsed ? '展开建议' : '收起建议'}
                        style={{ padding: 6, width: 32, height: 32, borderRadius: 9999, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'transparent', cursor: 'pointer', color: 'rgb(var(--theme-text-secondary))', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}
                      >
                        {suggestionsCollapsed ? <ChevronDown style={{ width: 16, height: 16 }} /> : <ChevronUp style={{ width: 16, height: 16 }} />}
                      </button>
                    )}
                    <button onClick={handleSuggestRules} disabled={suggestionsLoading} style={{ padding: '6px 12px', borderRadius: 9999, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))', cursor: suggestionsLoading ? 'not-allowed' : 'pointer', color: 'rgb(var(--theme-text))', opacity: suggestionsLoading ? 0.6 : 1 }}>
                      获取建议
                    </button>
                  </div>
                </div>
                {suggestionsCollapsed ? (
                  <div style={{ padding: 10, borderRadius: 10, border: '1px dashed rgb(var(--theme-border))', fontSize: 13, color: 'rgb(var(--theme-text-secondary))', backgroundColor: 'rgb(var(--theme-bg-secondary))', marginTop: 12 }}>已收起规则建议</div>
                ) : suggestionsLoading ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '32px 16px', marginTop: 12, borderRadius: 12, backgroundColor: 'rgb(var(--theme-bg-secondary))', border: '1px solid rgba(24,144,255,0.12)' }}>
                    <Loader2 style={{ width: 28, height: 28, color: '#1890ff', animation: 'spin 1s linear infinite', marginBottom: 12 }} />
                    <div style={{ fontSize: 14, color: 'rgb(var(--theme-text-secondary))', fontWeight: 500 }}>正在分析数据源结构...</div>
                    <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', marginTop: 4, opacity: 0.8 }}>AI 正在根据表结构、列注释和数据类型生成推荐规则</div>
                  </div>
                ) : smartSuggestions.length > 0 ? (
                  <div style={{ marginTop: 12 }}>
                    {suggestionsSource && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10, fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>
                        <Sparkles style={{ width: 14, height: 14, color: '#722ed1' }} />
                        <span>由 AI (LLM) 智能分析生成 · 共 {smartSuggestions.length} 条建议</span>
                      </div>
                    )}
                    <div style={{ display: 'grid', gap: 10 }}>
                      {smartSuggestions.map((suggestion, index) => {
                        const confidencePercent = Math.round((suggestion.confidence || 0) * 100)
                        const confidenceColor = confidencePercent >= 90 ? '#52c41a' : confidencePercent >= 70 ? '#1890ff' : '#faad14'
                        return (
                          <div key={`${suggestion.table}-${suggestion.column}-${index}`} style={{ padding: 14, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.88)', border: '1px solid rgb(var(--theme-border))', boxShadow: '0 2px 8px rgba(15,23,42,0.04)' }}>
                            {/* 卡片头部：表和列信息 */}
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 10 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                  <Database style={{ width: 14, height: 14, color: '#1890ff' }} />
                                  <span style={{ fontWeight: 600, fontSize: 13, color: 'rgb(var(--theme-text))' }}>{suggestion.table}</span>
                                </div>
                                <span style={{ color: 'rgb(var(--theme-border))', fontSize: 12 }}>·</span>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                  <Code2 style={{ width: 14, height: 14, color: '#722ed1' }} />
                                  <span style={{ fontWeight: 500, fontSize: 13, color: 'rgb(var(--theme-text))' }}>{suggestion.column}</span>
                                  {suggestion.column_comment && (
                                    <span style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', backgroundColor: 'rgba(114,46,209,0.08)', padding: '2px 8px', borderRadius: 9999 }}>{suggestion.column_comment}</span>
                                  )}
                                  <span style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', backgroundColor: 'rgba(0,0,0,0.04)', padding: '2px 8px', borderRadius: 4, fontFamily: "'Fira Code', monospace" }}>{suggestion.data_type}</span>
                                </div>
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                                <span style={{ color: 'rgb(var(--theme-text-secondary))' }}>置信度</span>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                  <div style={{ width: 60, height: 6, borderRadius: 3, backgroundColor: 'rgba(0,0,0,0.06)', overflow: 'hidden' }}>
                                    <div style={{ width: `${confidencePercent}%`, height: '100%', backgroundColor: confidenceColor, borderRadius: 3, transition: 'width 0.3s ease' }} />
                                  </div>
                                  <span style={{ fontWeight: 600, color: confidenceColor, minWidth: 36 }}>{confidencePercent}%</span>
                                </div>
                              </div>
                            </div>
                            {/* 规则建议信息 */}
                            <div style={{ padding: 10, borderRadius: 8, backgroundColor: 'linear-gradient(135deg, rgba(24,144,255,0.06) 0%, rgba(114,46,209,0.04) 100%)', border: '1px solid rgba(24,144,255,0.12)' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                                <Shield style={{ width: 14, height: 14, color: '#1890ff' }} />
                                <span style={{ fontWeight: 600, fontSize: 13, color: 'rgb(var(--theme-text))' }}>{suggestion.rule_name}</span>
                              </div>
                              {suggestion.rule_description && (
                                <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', marginBottom: suggestion.reasoning ? 8 : 0, lineHeight: 1.5 }}>{suggestion.rule_description}</div>
                              )}
                              {suggestion.reasoning && (
                                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6, padding: 8, borderRadius: 6, backgroundColor: 'rgba(255,255,255,0.6)', marginTop: suggestion.rule_description ? 0 : 0 }}>
                                  <MessageSquare style={{ width: 12, height: 12, color: 'rgb(var(--theme-text-secondary))', marginTop: 3, flexShrink: 0 }} />
                                  <span style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', lineHeight: 1.5, fontStyle: 'italic' }}>{suggestion.reasoning}</span>
                                </div>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                ) : (
                  <div style={{ padding: 24, marginTop: 12, borderRadius: 12, border: '1px dashed rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg-secondary))', textAlign: 'center' }}>
                    <Sparkles style={{ width: 24, height: 24, color: 'rgb(var(--theme-text-muted))', margin: '0 auto 8px', opacity: 0.7 }} />
                    <div style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))' }}>点击「获取建议」按钮，AI 将分析当前数据源并推荐质量检测规则</div>
                  </div>
                )}
              </div>
            )}

            {/* SQL 预览区域（手动模式和模板模式创建/编辑时均显示） */}
            {showSqlPreview && rulePreviewSql && (ruleCreationMode === 'manual' || ruleCreationMode === 'template') && (
              <div style={{ padding: 12, borderRadius: 12, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg-secondary))' }}>
                <div style={{ fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8 }}>SQL 预览{previewScope ? `（${previewScope === 'column' ? '列级' : previewScope === 'table' ? '表级' : '全局'}）` : ''}</div>
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12, color: 'rgb(var(--theme-text-secondary))' }}>{rulePreviewSql}</pre>
              </div>
            )}
          </div>

          <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid rgb(var(--theme-border))', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap', flexShrink: 0 }}>
            {(!editingRule || ruleCreationMode === 'template') && (
              <div style={{ fontSize: 12, color: previewConfirmed ? '#389e0d' : parseNeedsConfirmation ? '#d48806' : 'rgb(var(--theme-text-secondary))', flex: 1, minWidth: 220 }}>
                {ruleCreationMode === 'ai' ? (
                  parseNeedsConfirmation ? '请从候选列表中选择目标以继续' : parsedPrimaryResult ? '已解析成功，请确认信息无误后创建规则' : '请输入规则描述并进行AI解析'
                ) : previewConfirmed ? (editingRule ? '已完成预览，可直接保存' : '已完成预览确认，可直接创建规则') : '请先完成 SQL 预览并确认，再保存规则'}
              </div>
            )}
              {/* AI模式编辑时：条件表达式已变化但尚未解析，提示用户进行AI解析 */}
              {ruleCreationMode === 'ai' && editingRule && (ruleForm.condition_expr || '') !== (originalEditingRule?.condition_expr || '') && !parsedPrimaryResult && (
                <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', flex: 1, minWidth: 220 }}>
                  条件表达式已修改，请点击"AI解析"重新生成校验规则
                </div>
              )}
              {/* AI模式编辑时：复合规则条件或连接方式已变化，提示用户进行SQL预览 */}
              {ruleCreationMode === 'ai' && editingRule && ruleForm.rule_type === 'composite' && (
                (() => {
                  const originalConditions = originalEditingRule ? parseRuleConditions(originalEditingRule) : []
                  const originalMode = originalEditingRule ? getRuleConditionMode(originalEditingRule) : undefined
                  const compositeChanged = JSON.stringify(compositeConditions) !== JSON.stringify(originalConditions)
                  const modeChanged = conditionMode !== originalMode
                  if (compositeChanged || modeChanged) {
                    return (
                      <div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', flex: 1, minWidth: 220 }}>
                        复合规则条件{compositeChanged ? '已修改' : ''}{compositeChanged && modeChanged ? '，' : ''}{modeChanged ? '连接方式已切换' : ''}，请先点击"SQL预览"确认后再保存
                      </div>
                    )
                  }
                  return null
                })()
              )}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6, flexWrap: 'wrap', marginLeft: 'auto', paddingTop: 2 }}>
                {(ruleCreationMode === 'manual' || ruleCreationMode === 'template') && (
                  <button onClick={handlePreviewRule} disabled={previewLoading} style={{ padding: '7px 14px', borderRadius: 8, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'transparent', cursor: previewLoading ? 'not-allowed' : 'pointer' }}>{previewLoading ? '预览中...' : 'SQL预览'}</button>
                )}
                {/* AI模式新建时：用户编辑了条件表达式，显示SQL预览按钮 */}
                {ruleCreationMode === 'ai' && !editingRule && parsedPrimaryResult && aiConditionEdited && (
                  <button onClick={handlePreviewRule} disabled={previewLoading} style={{ padding: '7px 14px', borderRadius: 8, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'transparent', cursor: previewLoading ? 'not-allowed' : 'pointer' }}>{previewLoading ? '预览中...' : 'SQL预览'}</button>
                )}
                {/* AI模式编辑时：用户编辑了条件表达式，显示SQL预览按钮（无论是否已完成AI解析） */}
                {ruleCreationMode === 'ai' && editingRule && (
                  (() => {
                    // 已完成AI解析：用户编辑了条件表达式（aiConditionEdited）
                    if (parsedPrimaryResult && aiConditionEdited) {
                      return (
                        <button onClick={handlePreviewRule} disabled={previewLoading} style={{ padding: '7px 14px', borderRadius: 8, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'transparent', cursor: previewLoading ? 'not-allowed' : 'pointer' }}>{previewLoading ? '预览中...' : 'SQL预览'}</button>
                      )
                    }
                    // 尚未完成AI解析：用户直接编辑了condition_expr
                    if (!parsedPrimaryResult && (ruleForm.condition_expr || '') !== (originalEditingRule?.condition_expr || '')) {
                      return (
                        <button onClick={handlePreviewRule} disabled={previewLoading} style={{ padding: '7px 14px', borderRadius: 8, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'transparent', cursor: previewLoading ? 'not-allowed' : 'pointer' }}>{previewLoading ? '预览中...' : 'SQL预览'}</button>
                      )
                    }
                    return null
                  })()
                )}
                {/* AI模式编辑时：复合规则条件或连接方式已变化，显示SQL预览按钮 */}
                {ruleCreationMode === 'ai' && editingRule && ruleForm.rule_type === 'composite' && aiConditionEdited && (
                  <button onClick={handlePreviewRule} disabled={previewLoading} style={{ padding: '7px 14px', borderRadius: 8, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'transparent', cursor: previewLoading ? 'not-allowed' : 'pointer' }}>{previewLoading ? '预览中...' : 'SQL预览'}</button>
                )}
                {/* AI模式：解析成功后（parsedPrimaryResult 存在）且尚未确认，显示"确认解析结果"按钮，新建和编辑模式均适用 */}
                {ruleCreationMode === 'ai' && !parseNeedsConfirmation && parsedPrimaryResult && !previewConfirmed && (
                  <button onClick={() => {
                    // 如果用户编辑了条件表达式或复合条件，必须先点击 SQL 预览
                    if (aiConditionEdited) {
                      message.warning('条件表达式已修改，请先点击 "SQL 预览" 生成新的校验 SQL')
                      return
                    }
                    setPreviewConfirmed(true)
                    setAiConditionEdited(false) // 确认后重置
                    // 将 SQL 预览同步到 ruleForm.sql_text，方便用户继续编辑
                    if (rulePreviewSql) {
                      setRuleForm((prev) => ({ ...prev, sql_text: rulePreviewSql }))
                    }
                    // 编辑模式下：同步 originalEditingRule，重置 conditionExprChanged
                    if (editingRule) {
                      setOriginalEditingRule((prev) => prev ? { ...prev, condition_expr: parsedPrimaryResult?.condition_expr || prev.condition_expr, description: naturalLanguageInput || prev.description } : prev)
                    }
                    message.success('已确认解析结果，可以直接保存')
                  }} style={{ padding: '7px 14px', borderRadius: 8, border: 'none', color: 'white', backgroundColor: '#389e0d', cursor: 'pointer' }}>确认解析结果</button>
                )}
              </div>
              <button onClick={handleCreateRule} style={{ padding: '7px 16px', borderRadius: 8, fontSize: 14, fontWeight: 500, color: 'white', backgroundColor: 'rgb(var(--theme-primary))', border: 'none', cursor: 'pointer' }}>{editingRule ? '保存' : '创建'}</button>
        </div>
        </div>
      </Modal>

      <Modal title={<span style={{ fontWeight: 600, fontSize: 16 }}>从模板导入规则</span>} open={importModalVisible} onCancel={() => { setImportModalVisible(false); setSelectedTemplateIds([]); setImportTargetTable(''); setImportTargetColumn(''); setImportOverrideName(true) }} footer={null} width={620} centered styles={{ body: { padding: '16px 20px 20px' }, header: { borderBottom: 'none', padding: '16px 20px 0', marginBottom: 0 } }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ padding: 12, borderRadius: 12, backgroundColor: 'rgb(var(--theme-bg-secondary))', color: 'rgb(var(--theme-text-secondary))', fontSize: 13 }}>{selectedLibrary ? `当前规则库：${selectedLibrary.name}。这里是批量导入流程，后端会自动把导入规则标记为 template 来源。` : '请选择规则库后再批量导入模板'}</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>目标表名</label>
              <Input value={importTargetTable} onChange={(e) => setImportTargetTable(e.target.value)} placeholder="可选：如 customer_info" />
            </div>
            <div>
              <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>目标列名</label>
              <Input value={importTargetColumn} onChange={(e) => setImportTargetColumn(e.target.value)} placeholder="可选：如 mobile" />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: 12, borderRadius: 12, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))' }}>
            <div>
              <div style={{ fontWeight: 500, color: 'rgb(var(--theme-text))' }}>导入时自动重命名</div>
              <div style={{ fontSize: 13, color: 'rgb(var(--theme-text-secondary))', marginTop: 2 }}>开启后会把表/列信息合并到规则名称里，便于区分作用域</div>
            </div>
            <button onClick={() => setImportOverrideName((prev) => !prev)} style={{ padding: '6px 12px', borderRadius: 9999, border: '1px solid rgb(var(--theme-border))', backgroundColor: importOverrideName ? 'rgba(24,144,255,0.12)' : 'transparent', color: importOverrideName ? '#1677ff' : 'rgb(var(--theme-text-secondary))', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6 }}>{importOverrideName ? '已开启' : '已关闭'}</button>
          </div>
          <div style={{ padding: 12, borderRadius: 12, backgroundColor: 'rgb(var(--theme-bg-secondary))', fontSize: 13, color: 'rgb(var(--theme-text-secondary))' }}>{buildImportScopeHint()}</div>
          <div>
            <label style={{ fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', marginBottom: 8, display: 'block' }}>选择模板（可多选）</label>
            <Select mode="multiple" value={selectedTemplateIds} onChange={setSelectedTemplateIds} placeholder="请选择要导入的模板" options={templates.map((t) => ({ value: t.id, label: t.template_name || t.name || t.id }))} style={{ width: '100%' }} showSearch filterOption={(input, option) => (option?.label as string)?.toLowerCase().includes(input.toLowerCase())} />
          </div>
          {selectedTemplateIds.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ padding: 12, borderRadius: 8, backgroundColor: 'rgb(var(--theme-bg-secondary))', fontSize: 14, color: 'rgb(var(--theme-text-secondary))' }}>已选择 {selectedTemplateIds.length} 个模板</div>
              <div style={{ display: 'grid', gap: 8, maxHeight: 160, overflow: 'auto' }}>
                {selectedTemplateIds.map((id) => {
                  const template = templates.find((item) => item.id === id)
                  if (!template) return null
                  return <div key={id} style={{ padding: 10, borderRadius: 10, border: '1px solid rgb(var(--theme-border))', backgroundColor: 'rgb(var(--theme-bg))' }}><div style={{ fontWeight: 500, color: 'rgb(var(--theme-text))' }}>{template.template_name || template.name || template.id}</div><div style={{ fontSize: 12, color: 'rgb(var(--theme-text-secondary))', marginTop: 2 }}>导入后名称预览：{getImportPreviewName(template)}</div></div>
                })}
              </div>
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
            <button onClick={() => { setImportModalVisible(false); setSelectedTemplateIds([]); setImportTargetTable(''); setImportTargetColumn(''); setImportOverrideName(true) }} style={{ padding: '8px 16px', borderRadius: 8, fontSize: 14, fontWeight: 500, color: 'rgb(var(--theme-text))', backgroundColor: 'transparent', border: '1px solid rgb(var(--theme-border))', cursor: 'pointer' }}>取消</button>
            <button onClick={handleImportTemplate} disabled={importingTemplates} style={{ padding: '8px 16px', borderRadius: 8, fontSize: 14, fontWeight: 500, color: 'white', backgroundColor: importingTemplates ? 'rgba(24,144,255,0.6)' : 'rgb(var(--theme-primary))', border: 'none', cursor: importingTemplates ? 'not-allowed' : 'pointer' }}>{importingTemplates ? '导入中...' : `导入 (${selectedTemplateIds.length})`}</button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

// 候选表/列卡片组件
interface CandidateCardProps {
  candidate: GovernanceRuleParseCandidateItem
  type: 'table' | 'column' | 'multi_column'
  isLoading: boolean
  selectedColumns?: string[]
  onToggleColumn?: (colName: string) => void
  onSelect: () => void
}

function CandidateCard({ candidate, type, isLoading, selectedColumns = [], onToggleColumn, onSelect }: CandidateCardProps) {
  const [descExpanded, setDescExpanded] = useState(false)
  const scorePercent = Math.round((candidate.score || 0) * 100)
  const pureColName = candidate.name.split('（')[0]
  const isSelected = selectedColumns.includes(pureColName)

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return { bg: 'rgba(82,196,26,0.1)', color: '#389e0d', border: 'rgba(82,196,26,0.3)' }
    if (score >= 0.6) return { bg: 'rgba(24,144,255,0.1)', color: '#1677ff', border: 'rgba(24,144,255,0.3)' }
    return { bg: 'rgba(250,173,20,0.1)', color: '#d48806', border: 'rgba(250,173,20,0.3)' }
  }

  const scoreStyle = getScoreColor(candidate.score || 0)

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        padding: 14,
        borderRadius: 10,
        backgroundColor: isSelected ? 'rgba(82,196,26,0.05)' : 'rgb(var(--theme-bg-secondary))',
        border: `1px solid ${isSelected ? 'rgba(82,196,26,0.4)' : 'rgb(var(--theme-border))'}`,
        transition: 'all 0.2s ease',
      }}
      onMouseEnter={(e) => {
        if (!isSelected) {
          e.currentTarget.style.borderColor = 'rgba(24,144,255,0.4)'
          e.currentTarget.style.boxShadow = '0 2px 8px rgba(24,144,255,0.1)'
        }
      }}
      onMouseLeave={(e) => {
        if (!isSelected) {
          e.currentTarget.style.borderColor = 'rgb(var(--theme-border))'
          e.currentTarget.style.boxShadow = 'none'
        }
      }}
    >
      {/* 头部：表名/列名 + 匹配度 + 选择按钮 */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* 多列候选场景：添加复选框 */}
          {type === 'multi_column' && (
            <div
              onClick={() => onToggleColumn?.(candidate.name)}
              style={{
                width: 20,
                height: 20,
                borderRadius: 4,
                border: `2px solid ${isSelected ? '#389e0d' : 'rgb(var(--theme-border))'}`,
                backgroundColor: isSelected ? '#389e0d' : 'transparent',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {isSelected && (
                <Check size={14} style={{ color: 'white' }} />
              )}
            </div>
          )}
          <div style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            backgroundColor: type === 'table' ? 'rgba(24,144,255,0.1)' : type === 'multi_column' ? 'rgba(250,173,20,0.1)' : 'rgba(114,46,209,0.1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            {type === 'table' ? (
              <Database size={16} style={{ color: '#1677ff' }} />
            ) : type === 'multi_column' ? (
              <GitBranch size={16} style={{ color: '#fa8c16' }} />
            ) : (
              <GitBranch size={16} style={{ color: '#722ed1' }} />
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {/* 多列候选场景：解析列名显示 */}
            {(() => {
              const displayName = type === 'multi_column'
                ? candidate.name.split('（')[0]  // 提取纯列名（如 "warehouse"）
                : candidate.name
              const extraInfo = type === 'multi_column' && candidate.name.includes('（')
                ? candidate.name.substring(candidate.name.indexOf('（'))  // 提取括号内的说明（如 "（仓库名称不为空）"）
                : null
              return (
                <>
                  <span style={{ fontSize: 14, fontWeight: 600, color: 'rgb(var(--theme-text))' }}>
                    {displayName}
                  </span>
                  {extraInfo && (
                    <span style={{ fontSize: 11, color: '#fa8c16' }}>
                      {extraInfo}
                    </span>
                  )}
                </>
              )
            })()}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              {type === 'table' && (
                <span style={{ fontSize: 11, color: 'rgb(var(--theme-text-muted))' }}>
                  {candidate.is_view ? '数据视图' : '数据表'}
                </span>
              )}
              {type === 'multi_column' && candidate.rule_type && (
                <span style={{ fontSize: 11, color: '#fa8c16', backgroundColor: 'rgba(250,173,20,0.1)', padding: '1px 6px', borderRadius: 4 }}>
                  {getRuleDisplayName({ rule_type: candidate.rule_type } as GovernanceRule) || candidate.rule_type}
                </span>
              )}
              {type === 'multi_column' && (candidate.data_type || candidate.comment) && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginLeft: 'auto' }}>
                  {candidate.data_type && (
                    <span style={{ fontSize: 10, color: 'rgb(var(--theme-text-muted))', backgroundColor: 'rgb(var(--theme-bg))', padding: '1px 6px', borderRadius: 4, border: '1px solid rgba(15,23,42,0.08)' }}>
                      {candidate.data_type}
                    </span>
                  )}
                  {candidate.comment && (
                    <span style={{ fontSize: 10, color: 'rgb(var(--theme-text-secondary))', fontStyle: 'italic' }}>
                      {candidate.comment}
                    </span>
                  )}
                </div>
              )}
              {candidate.from_card && (
                <span style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 3,
                  padding: '1px 6px',
                  borderRadius: 9999,
                  backgroundColor: 'rgba(82,196,26,0.08)',
                  border: '1px solid rgba(82,196,26,0.2)',
                  fontSize: 9,
                  color: '#389e0d',
                }}>
                  <BookOpen size={10} />
                  来自数据卡片
                </span>
              )}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            padding: '4px 10px',
            borderRadius: 9999,
            backgroundColor: scoreStyle.bg,
            border: `1px solid ${scoreStyle.border}`,
          }}>
            <div style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: scoreStyle.color,
            }} />
            <span style={{ fontSize: 12, fontWeight: 500, color: scoreStyle.color }}>
              {scorePercent}% 匹配
            </span>
          </div>
          {/* 多列候选场景：显示选中状态，否则显示选择按钮 */}
          {type === 'multi_column' ? (
            isSelected ? (
              <span style={{ padding: '6px 14px', borderRadius: 8, backgroundColor: 'rgba(82,196,26,0.15)', color: '#389e0d', fontSize: 13, fontWeight: 500 }}>
                已选择
              </span>
            ) : (
              <span style={{ padding: '6px 14px', borderRadius: 8, border: '1px solid rgba(82,196,26,0.3)', color: '#389e0d', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}
                onClick={() => onToggleColumn?.(candidate.name)}>
                选择
              </span>
            )
          ) : (
            <button
              onClick={(e) => { e.stopPropagation(); onSelect() }}
              disabled={isLoading}
              style={{
                padding: '6px 14px',
                borderRadius: 8,
                border: 'none',
                backgroundColor: 'rgb(var(--theme-primary))',
                color: 'white',
                fontSize: 13,
                fontWeight: 500,
                cursor: isLoading ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s',
              }}
              onMouseEnter={(e) => {
                if (!isLoading) e.currentTarget.style.opacity = '0.9'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.opacity = '1'
              }}
            >
              选择
            </button>
          )}
        </div>
      </div>

      {/* 匹配原因 */}
      <div style={{ padding: '8px 10px', borderRadius: 6, backgroundColor: 'rgb(var(--theme-bg))', border: '1px solid rgba(24,144,255,0.08)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
          <Sparkles size={12} style={{ color: '#1677ff' }} />
          <span style={{ fontSize: 11, fontWeight: 500, color: 'rgb(var(--theme-text-secondary))' }}>匹配原因</span>
        </div>
        <div style={{ fontSize: 12, color: 'rgb(var(--theme-text))', lineHeight: 1.6, paddingLeft: 4, textIndent: '1em' }}>
          {candidate.reason}
        </div>
      </div>

      {/* 表候选场景：显示推断的列信息（支持新版详细格式） */}
      {type === 'table' && (
        (candidate.inferred_columns_detail && candidate.inferred_columns_detail.length > 0) ||
        (candidate.inferred_columns && candidate.inferred_columns.length > 0) ||
        candidate.inferred_column ||
        candidate.inferred_column_names
      ) && (
        <div style={{ padding: '8px 10px', borderRadius: 6, backgroundColor: 'rgba(114,46,209,0.05)', border: '1px solid rgba(114,46,209,0.15)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <GitBranch size={12} style={{ color: '#722ed1' }} />
            <span style={{ fontSize: 11, fontWeight: 500, color: '#722ed1' }}>推断的目标列</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {/* 新版详细格式：inferred_columns_detail */}
            {candidate.inferred_columns_detail?.map((colInfo, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#722ed1', padding: '2px 10px', borderRadius: 4, backgroundColor: 'rgba(114,46,209,0.1)' }}>
                  {colInfo.column}
                </span>
                {colInfo.data_type && (
                  <span style={{ fontSize: 10, color: 'rgb(var(--theme-text-muted))' }}>({colInfo.data_type})</span>
                )}
                {colInfo.comment && (
                  <span style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))' }}>{colInfo.comment}</span>
                )}
                {colInfo.reason && (
                  <span style={{ fontSize: 10, color: 'rgb(var(--theme-text-muted))', fontStyle: 'italic' }}>{colInfo.reason}</span>
                )}
              </div>
            ))}

            {/* 旧版字符串数组格式：inferred_columns */}
            {!candidate.inferred_columns_detail && !candidate.inferred_column && !candidate.inferred_column_names && candidate.inferred_columns?.length && typeof candidate.inferred_columns[0] === 'string' && (
              candidate.inferred_columns.map((col, idx) => (
                <span key={idx} style={{ fontSize: 13, fontWeight: 600, color: '#722ed1', padding: '2px 10px', borderRadius: 4, backgroundColor: 'rgba(114,46,209,0.1)' }}>
                  {col}
                </span>
              ))
            )}

            {/* 新版对象数组格式：inferred_columns（含 column/data_type/comment/reason） */}
            {!candidate.inferred_columns_detail && !candidate.inferred_column && !candidate.inferred_column_names && candidate.inferred_columns?.length && typeof candidate.inferred_columns[0] === 'object' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {(candidate.inferred_columns as Array<{ column?: string; data_type?: string; comment?: string; reason?: string }>).map((colInfo, idx) => (
                  <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    {colInfo.column && (
                      <span style={{ fontSize: 13, fontWeight: 600, color: '#722ed1', padding: '2px 10px', borderRadius: 4, backgroundColor: 'rgba(114,46,209,0.1)' }}>
                        {colInfo.column}
                      </span>
                    )}
                    {colInfo.data_type && (
                      <span style={{ fontSize: 10, color: 'rgb(var(--theme-text-muted))' }}>({colInfo.data_type})</span>
                    )}
                    {colInfo.comment && (
                      <span style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))' }}>{colInfo.comment}</span>
                    )}
                    {colInfo.reason && (
                      <span style={{ fontSize: 10, color: 'rgb(var(--theme-text-muted))', fontStyle: 'italic' }}>{colInfo.reason}</span>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* 旧版字符串格式：inferred_column */}
            {!candidate.inferred_columns_detail && !candidate.inferred_columns && candidate.inferred_column && (
              <span style={{ fontSize: 13, fontWeight: 600, color: '#722ed1', padding: '2px 10px', borderRadius: 4, backgroundColor: 'rgba(114,46,209,0.1)' }}>
                {candidate.inferred_column}
              </span>
            )}

            {/* 新版逗号分隔格式：inferred_column_names */}
            {!candidate.inferred_columns_detail && !candidate.inferred_columns && !candidate.inferred_column && candidate.inferred_column_names && (
              candidate.inferred_column_names.split(',').map((col, idx) => (
                <span key={idx} style={{ fontSize: 13, fontWeight: 600, color: '#722ed1', padding: '2px 10px', borderRadius: 4, backgroundColor: 'rgba(114,46,209,0.1)' }}>
                  {col.trim()}
                </span>
              ))
            )}

            {candidate.column_reasoning && (
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6, marginTop: 4 }}>
                <ArrowRight size={12} style={{ color: 'rgb(var(--theme-text-muted))', marginTop: 2, flexShrink: 0 }} />
                <span style={{ fontSize: 11, color: 'rgb(var(--theme-text-secondary))', lineHeight: 1.5 }}>
                  {candidate.column_reasoning}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 多列候选场景：显示规则类型和条件提示 */}
      {type === 'multi_column' && (
        <>
          {candidate.condition_hint && (
            <div style={{ padding: '8px 10px', borderRadius: 6, backgroundColor: 'rgba(250,173,20,0.05)', border: '1px solid rgba(250,173,20,0.2)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <MessageSquare size={12} style={{ color: '#fa8c16' }} />
                <span style={{ fontSize: 11, fontWeight: 500, color: '#fa8c16' }}>规则条件</span>
              </div>
              <div style={{ fontSize: 12, color: 'rgb(var(--theme-text))', lineHeight: 1.6 }}>
                {candidate.condition_hint}
              </div>
            </div>
          )}
        </>
      )}

      {/* 表描述（仅表候选有，列候选和多列候选不显示） */}
      {type === 'table' && candidate.description && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <button
            onClick={(e) => { e.stopPropagation(); setDescExpanded(!descExpanded) }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: 0,
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'rgb(var(--theme-text-secondary))',
              fontSize: 11,
            }}
          >
            {descExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            <span>{descExpanded ? '收起' : '查看'}表描述</span>
          </button>
          {descExpanded && (
            <div style={{
              padding: '10px 14px 10px 18px',
              borderRadius: 6,
              backgroundColor: 'rgb(var(--theme-bg))',
              fontSize: 11,
              color: 'rgb(var(--theme-text-secondary))',
              lineHeight: 1.6,
              textIndent: '1em',
              maxHeight: 120,
              overflow: 'auto',
            }}>
              {candidate.description}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function LibrariesPage({ params }: { params: { lng: string } }) {
  return <LibrariesPageContent lng={params.lng} />
}
