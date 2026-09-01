'use client';

import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  X,
  BarChart3,
  Bot,
  Code,
  Sparkles,
  FileDown,
  Bell,
  Gauge,
  Share2,
  LayoutDashboard,
  Zap,
  BookOpen,
  Copy,
  Check,
  ExternalLink,
  ArrowRight,
  Database,
  Table,
  Users,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Settings,
  Play,
  Terminal,
  FileJson,
  BarChart,
  PieChart,
  LineChart,
  MessageSquare,
  Send,
  RefreshCw,
  Download,
  Eye,
  Filter,
  Layers,
  Book,
  Calendar,
  Mail,
  Webhook,
  DatabaseZap,
  Activity,
  Target,
  ClipboardList,
  GitBranch,
  Network,
  Cpu,
  Brain,
  LineChart as LineChartIcon,
  Circle
} from 'lucide-react';

// 检测是否为深色模式
const useDarkMode = () => {
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const checkDark = () => {
      const dark = document.documentElement.getAttribute('data-theme') === 'dark';
      setIsDark(dark);
    };

    checkDark();

    const observer = new MutationObserver(checkDark);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme']
    });

    return () => observer.disconnect();
  }, []);

  return isDark;
};

const toneMap: Record<string, { bg: string; border: string; text: string; bar: string }> = {
  rose: { bg: 'rgba(244, 63, 94, 0.1)', border: 'rgba(244, 63, 94, 0.25)', text: '#fb7185', bar: '#f43f5e' },
  blue: { bg: 'rgba(59, 130, 246, 0.1)', border: 'rgba(59, 130, 246, 0.25)', text: '#60a5fa', bar: '#3b82f6' },
  emerald: { bg: 'rgba(16, 185, 129, 0.1)', border: 'rgba(16, 185, 129, 0.25)', text: '#34d399', bar: '#10b981' },
  violet: { bg: 'rgba(139, 92, 246, 0.1)', border: 'rgba(139, 92, 246, 0.25)', text: '#a78bfa', bar: '#8b5cf6' },
  amber: { bg: 'rgba(245, 158, 11, 0.1)', border: 'rgba(245, 158, 11, 0.25)', text: '#fbbf24', bar: '#f59e0b' },
};

// 场景类型
export type ScenarioType =
  | 'bi'
  | 'ai-agent'
  | 'api'
  | 'prediction'
  | 'export'
  | 'subscription'
  | 'quality'
  | 'sharing'
  | 'report'
  | 'metrics'
  | 'docs'
  | 'quality-report'
  | 'quality-fix';

interface DataConsumeScenariosModalProps {
  isOpen: boolean;
  onClose: () => void;
  scenarioType: ScenarioType | null;
}

// 弹框内浅色点缀色（标题区图标、勾选图标等）
const scenarioAccentHex: Record<ScenarioType, string> = {
  bi: '#2563eb',
  'ai-agent': '#7c3aed',
  api: '#059669',
  prediction: '#d97706',
  export: '#0891b2',
  subscription: '#e11d48',
  quality: '#7c3aed',
  sharing: '#0d9488',
  report: '#4f46e5',
  metrics: '#ca8a04',
  docs: '#475569',
  'quality-report': '#dc2626',
  'quality-fix': '#0891b2',
};

// 场景配置
const scenarioConfig: Record<ScenarioType, {
  title: string;
  icon: React.ReactNode;
  theme: {
    accent: string;
    bgLight: string;
  };
}> = {
  bi: {
    title: 'BI 系统对接',
    icon: <BarChart3 className="w-5 h-5" />,
    theme: { accent: 'text-blue-600', bgLight: 'bg-blue-50' }
  },
  'ai-agent': {
    title: 'AI 智能体集成',
    icon: <Bot className="w-5 h-5" />,
    theme: { accent: 'text-purple-600', bgLight: 'bg-purple-50' }
  },
  api: {
    title: 'API 取数',
    icon: <Code className="w-5 h-5" />,
    theme: { accent: 'text-emerald-600', bgLight: 'bg-emerald-50' }
  },
  prediction: {
    title: '数据预测分析',
    icon: <Sparkles className="w-5 h-5" />,
    theme: { accent: 'text-amber-600', bgLight: 'bg-amber-50' }
  },
  export: {
    title: '数据导出',
    icon: <FileDown className="w-5 h-5" />,
    theme: { accent: 'text-cyan-600', bgLight: 'bg-cyan-50' }
  },
  subscription: {
    title: '数据订阅推送',
    icon: <Bell className="w-5 h-5" />,
    theme: { accent: 'text-rose-600', bgLight: 'bg-rose-50' }
  },
  quality: {
    title: '数据质量监控',
    icon: <Gauge className="w-5 h-5" />,
    theme: { accent: 'text-violet-600', bgLight: 'bg-violet-50' }
  },
  sharing: {
    title: '数据市场共享',
    icon: <Share2 className="w-5 h-5" />,
    theme: { accent: 'text-teal-600', bgLight: 'bg-teal-50' }
  },
  report: {
    title: '自动化报表',
    icon: <LayoutDashboard className="w-5 h-5" />,
    theme: { accent: 'text-indigo-600', bgLight: 'bg-indigo-50' }
  },
  metrics: {
    title: '指标中心',
    icon: <Zap className="w-5 h-5" />,
    theme: { accent: 'text-yellow-600', bgLight: 'bg-yellow-50' }
  },
  docs: {
    title: '数据文档中心',
    icon: <BookOpen className="w-5 h-5" />,
    theme: { accent: 'text-slate-600', bgLight: 'bg-slate-50' }
  },
  'quality-report': {
    title: '数据质检报告',
    icon: <ClipboardList className="w-5 h-5" />,
    theme: { accent: 'text-red-600', bgLight: 'bg-red-50' }
  },
  'quality-fix': {
    title: '数据修复建议',
    icon: <Settings className="w-5 h-5" />,
    theme: { accent: 'text-cyan-600', bgLight: 'bg-cyan-50' }
  }
};

// 各场景案例内容
const scenarioContents: Record<ScenarioType, {
  description: string;
  useCases: Array<{ title: string; desc: string; icon: React.ReactNode }>;
  demoContent: React.ReactNode;
  codeExample?: { title: string; code: string; language: string };
  keyBenefits: string[];
}> = {
  bi: {
    description: '通过标准接口将数据卡片接入 BI 系统，实现企业级数据可视化与分析',
    useCases: [
      { title: '销售大屏', desc: '实时展示销售数据、业绩排名', icon: <TrendingUp className="w-4 h-4" /> },
      { title: '经营看板', desc: '多维度数据汇总与趋势分析', icon: <BarChart className="w-4 h-4" /> },
      { title: '财务报告', desc: '自动生成财务报表与对比分析', icon: <PieChart className="w-4 h-4" /> }
    ],
    demoContent: (
      <div
        className="bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white font-mono text-xs overflow-hidden"
        style={{ borderRadius: 16, overflow: 'hidden' }}
      >
        <div className="flex items-center gap-2 mb-4">
          <div className="w-3 h-3 rounded-full bg-red-500"></div>
          <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
          <div className="w-3 h-3 rounded-full bg-green-500"></div>
          <span className="ml-2 text-slate-400 text-[10px]">BI Dashboard - Sales Overview</span>
        </div>
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="bg-white/10 p-3" style={{ borderRadius: 12 }}>
            <div className="text-slate-400 text-[10px] mb-1">总收入</div>
            <div className="text-xl font-bold text-emerald-400">¥2,847,320</div>
            <div className="text-[10px] text-emerald-400 flex items-center gap-1 mt-1">
              <TrendingUp className="w-3 h-3" /> +12.5%
            </div>
          </div>
          <div className="bg-white/10 p-3" style={{ borderRadius: 12 }}>
            <div className="text-slate-400 text-[10px] mb-1">订单数</div>
            <div className="text-xl font-bold text-blue-400">1,284</div>
            <div className="text-[10px] text-blue-400 flex items-center gap-1 mt-1">
              <TrendingUp className="w-3 h-3" /> +8.2%
            </div>
          </div>
          <div className="bg-white/10 p-3" style={{ borderRadius: 12 }}>
            <div className="text-slate-400 text-[10px] mb-1">客户数</div>
            <div className="text-xl font-bold text-purple-400">856</div>
            <div className="text-[10px] text-purple-400 flex items-center gap-1 mt-1">
              <TrendingUp className="w-3 h-3" /> +5.1%
            </div>
          </div>
        </div>
        <div className="bg-white/5 p-3" style={{ borderRadius: 12 }}>
          <div className="text-[10px] text-slate-400 mb-2">月度销售趋势</div>
          <div className="flex items-end gap-1 h-16">
            {[40, 55, 45, 70, 60, 85, 75, 90, 80, 95, 88, 100].map((h, i) => (
              <div key={i} className="flex-1 bg-gradient-to-t from-blue-500 to-indigo-500 rounded-t" style={{ height: `${h}%` }}></div>
            ))}
          </div>
          <div className="flex justify-between mt-1 text-[9px] text-slate-500">
            <span>1月</span><span>6月</span><span>12月</span>
          </div>
        </div>
      </div>
    ),
    codeExample: {
      title: '获取数据卡片',
      language: 'javascript',
      code: `// 通过 API 获取数据卡片
const response = await fetch('/api/cards/sales_summary', {
  headers: {
    'Authorization': 'Bearer your_token',
    'Content-Type': 'application/json'
  }
});

const card = await response.json();
// card.data: [{ label: "总收入", value: 2847320 }]`
    },
    keyBenefits: ['标准JDBC/ODBC协议', '支持主流BI工具', '实时数据同步', '权限精细控制']
  },
  'ai-agent': {
    description: '将数据资产无缝接入 AI 智能体，实现自然语言驱动的数据分析与决策',
    useCases: [
      { title: '智能问数', desc: '用自然语言查询数据库', icon: <MessageSquare className="w-4 h-4" /> },
      { title: '数据解读', desc: 'AI 自动分析数据异常', icon: <Brain className="w-4 h-4" /> },
      { title: '报告生成', desc: '一键生成分析报告', icon: <FileDown className="w-4 h-4" /> }
    ],
    demoContent: (
      <div
        className="bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white font-mono text-xs overflow-hidden"
        style={{ borderRadius: 16, overflow: 'hidden' }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Bot className="w-4 h-4 text-purple-400" />
          <span className="text-slate-300">AI 智能体对话</span>
        </div>
        <div className="space-y-3">
          <div className="flex gap-2">
            <div
              className="w-6 h-6 bg-indigo-500 flex items-center justify-center text-[10px] flex-shrink-0"
              style={{ borderRadius: 9999, overflow: 'hidden' }}
            >
              U
            </div>
            <div
              className="bg-white/10 p-2.5 flex-1"
              style={{ borderRadius: '0 12px 12px 12px' }}
            >
              最近一个月各地区的销售额排名？
            </div>
          </div>
          <div className="flex gap-2">
            <div
              className="w-6 h-6 bg-purple-500 flex items-center justify-center text-[10px] flex-shrink-0"
              style={{ borderRadius: 9999, overflow: 'hidden' }}
            >
              <Bot className="w-3 h-3" />
            </div>
            <div
              className="bg-purple-500/20 p-2.5 flex-1"
              style={{ borderRadius: '0 12px 12px 12px' }}
            >
              <div className="text-purple-300 text-[10px] mb-2">根据数据分析，近一个月各地区销售额排名如下：</div>
              <div className="space-y-1">
                {[
                  { region: '华东地区', sales: '¥892,450', trend: '+15.2%' },
                  { region: '华南地区', sales: '¥756,320', trend: '+8.7%' },
                  { region: '华北地区', sales: '¥623,180', trend: '+5.3%' },
                  { region: '西南地区', sales: '¥412,560', trend: '+12.1%' }
                ].map((r, i) => (
                  <div key={i} className="flex justify-between items-center text-[10px]">
                    <span className="text-slate-300">{i + 1}. {r.region}</span>
                    <span className="text-emerald-400">{r.sales}</span>
                    <span className="text-emerald-400/70">{r.trend}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    ),
    codeExample: {
      title: 'Agent SDK 集成',
      language: 'python',
      code: `from onticards import Agent

agent = Agent(api_key="your_key")
result = agent.analyze(
    query="分析Q3季度销售数据趋势",
    data_sources=["sales_db", "orders_db"]
)
print(result.insights)  # AI 分析结论`
    },
    keyBenefits: ['自然语言查询', '多数据源融合', '智能推理分析', '上下文记忆']
  },
  api: {
    description: '通过 RESTful API 获取结构化数据，支持二次开发和系统集成',
    useCases: [
      { title: '系统集成', desc: 'ERP、CRM 数据对接', icon: <Network className="w-4 h-4" /> },
      { title: '数据中台', desc: '构建企业数据中枢', icon: <DatabaseZap className="w-4 h-4" /> },
      { title: '移动应用', desc: 'APP 数据展示', icon: <Cpu className="w-4 h-4" /> }
    ],
    demoContent: (
      <div
        className="bg-gradient-to-br from-slate-900 to-slate-800 overflow-hidden"
        style={{ borderRadius: 16, overflow: 'hidden' }}
      >
        <div className="bg-slate-800/50 px-4 py-2 flex items-center justify-between border-b border-slate-700">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-emerald-400" />
            <span className="text-slate-300 text-xs font-mono">API Request</span>
          </div>
          <span
            className="text-emerald-400 text-[10px] font-mono px-2 py-0.5 bg-emerald-500/20"
            style={{ borderRadius: 8 }}
          >
            200 OK
          </span>
        </div>
        <div className="p-4 font-mono text-[11px] text-slate-300 overflow-hidden">
          <div className="text-slate-500 mb-2">// GET /api/v1/cards/revenue_summary</div>
          <div className="bg-white/5 p-3 overflow-x-auto" style={{ borderRadius: 12 }}>
            <pre className="text-emerald-400">{`{
  "code": 200,
  "data": {
    "total_revenue": 2847320,
    "currency": "CNY",
    "period": "2024-Q3",
    "breakdown": [
      { "region": "华东", "amount": 892450 },
      { "region": "华南", "amount": 756320 }
    ]
  },
  "timestamp": "2024-09-15T10:30:00Z"
}`}</pre>
          </div>
        </div>
      </div>
    ),
    codeExample: {
      title: 'cURL 示例',
      language: 'bash',
      code: `# 获取数据卡片
curl -X GET "https://api.onticards.com/v1/cards/sales" \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Content-Type: application/json"

# 返回 JSON 数据，可直接用于您的系统`
    },
    keyBenefits: ['完整 REST API', 'SDK 多语言支持', '高并发低延迟', 'Webhook 回调']
  },
  prediction: {
    description: '基于历史数据与 AI 算法，提供销售预测、趋势分析等智能洞察',
    useCases: [
      { title: '销售预测', desc: '预测未来销量与趋势', icon: <TrendingUp className="w-4 h-4" /> },
      { title: '异常检测', desc: '自动发现数据异常', icon: <AlertTriangle className="w-4 h-4" /> },
      { title: '归因分析', desc: '分析影响业绩的关键因素', icon: <Target className="w-4 h-4" /> }
    ],
    demoContent: (
      <div
        className="bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white font-mono text-xs overflow-hidden"
        style={{ borderRadius: 16, overflow: 'hidden' }}
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-slate-400 text-[10px]">销售预测分析</div>
            <div className="text-white text-sm font-semibold">Q4 季度预测模型</div>
          </div>
          <div
            className="flex items-center gap-1 text-amber-400 text-[10px] bg-amber-500/20 px-2 py-1"
            style={{ borderRadius: 9999 }}
          >
            <Sparkles className="w-3 h-3" /> AI 驱动
          </div>
        </div>
        <div className="relative h-32 mb-4">
          <svg className="w-full h-full" viewBox="0 0 300 100" preserveAspectRatio="none">
            {/* 历史数据 */}
            <path d="M0,80 L30,70 L60,75 L90,60 L120,65 L150,50 L180,55" fill="none" stroke="#3B82F6" strokeWidth="2" />
            {/* 预测数据 */}
            <path d="M180,55 L210,40 L240,35 L270,25 L300,20" fill="none" stroke="#F59E0B" strokeWidth="2" strokeDasharray="4" />
            {/* 置信区间 */}
            <path d="M180,55 L210,30 L240,25 L270,15 L300,10 L300,30 L270,35 L240,45 L210,50 L180,65 Z" fill="#F59E0B" fillOpacity="0.1" />
          </svg>
          <div className="absolute bottom-0 left-0 text-[9px] text-slate-500">历史</div>
          <div className="absolute bottom-0 right-0 text-[9px] text-amber-400">预测</div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-white/5 p-2" style={{ borderRadius: 12 }}>
            <div className="text-slate-400 text-[9px]">预测销量</div>
            <div className="text-amber-400 font-bold">+23.5%</div>
          </div>
          <div className="bg-white/5 p-2" style={{ borderRadius: 12 }}>
            <div className="text-slate-400 text-[9px]">置信度</div>
            <div className="text-emerald-400 font-bold">92.8%</div>
          </div>
        </div>
      </div>
    ),
    codeExample: {
      title: '预测接口调用',
      language: 'python',
      code: `# 调用预测分析 API
result = onticards.predict(
    metric="sales",
    period="Q4",
    model="arima_plus",
    confidence_level=0.95
)

# result.forecast: 预测值
# result.confidence_interval: 置信区间
# result.factors: 影响因素`
    },
    keyBenefits: ['多种预测模型', '可解释性 AI', '置信区间', '因素归因']
  },
  export: {
    description: '支持多种格式的数据导出，满足不同场景的离线分析需求',
    useCases: [
      { title: 'Excel 报表', desc: '日常数据分析', icon: <FileDown className="w-4 h-4" /> },
      { title: 'JSON 导出', desc: 'API 格式对接', icon: <FileJson className="w-4 h-4" /> },
      { title: 'CSV 批量', desc: '数据迁移同步', icon: <Download className="w-4 h-4" /> }
    ],
    demoContent: (
      <div
        className="bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white overflow-hidden"
        style={{ borderRadius: 16, overflow: 'hidden' }}
      >
        <div className="text-xs mb-4">
          <span className="text-slate-400">导出任务</span>
          <span className="text-white ml-2">销售数据 2024-Q3</span>
        </div>
        <div className="space-y-3 mb-4">
          {[
            { name: 'sales_summary.xlsx', size: '2.4 MB', progress: 100, status: '完成', icon: <FileDown className="w-4 h-4 text-emerald-400" /> },
            { name: 'customer_data.csv', size: '856 KB', progress: 100, status: '完成', icon: <FileDown className="w-4 h-4 text-emerald-400" /> },
            { name: 'inventory.json', size: '124 KB', progress: 67, status: '进行中', icon: <RefreshCw className="w-4 h-4 text-cyan-400 animate-spin" /> }
          ].map((file, i) => (
            <div key={i} className="bg-white/5 p-3" style={{ borderRadius: 12 }}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {file.icon}
                  <span className="text-xs text-slate-300">{file.name}</span>
                </div>
                <span className="text-[10px] text-slate-500">{file.size}</span>
              </div>
              <div
                className="h-1.5 bg-slate-700 overflow-hidden"
                style={{ borderRadius: 9999, overflow: 'hidden' }}
              >
                <div
                  className={`h-full transition-all ${file.status === '进行中' ? 'bg-cyan-500' : 'bg-emerald-500'}`}
                  style={{ width: `${file.progress}%`, borderRadius: 9999 }}
                ></div>
              </div>
            </div>
          ))}
        </div>
        <div className="text-[10px] text-slate-500">支持格式：Excel、CSV、JSON、Parquet、SQL</div>
      </div>
    ),
    codeExample: {
      title: 'API 导出示例',
      language: 'javascript',
      code: `// 导出数据卡片
const exportJob = await fetch('/api/export', {
  method: 'POST',
  body: JSON.stringify({
    card_id: 'sales_summary',
    format: 'xlsx',
    date_range: '2024-Q3'
  })
});

// 获取下载链接
const { download_url } = await exportJob.json();
window.open(download_url);`
    },
    keyBenefits: ['多格式支持', '大文件分片', '定时导出', '批量导出']
  },
  subscription: {
    description: '设置数据订阅规则，当数据达到指定条件时自动推送通知',
    useCases: [
      { title: '异常告警', desc: '数据异常实时通知', icon: <AlertTriangle className="w-4 h-4" /> },
      { title: '定时报表', desc: '每日/周数据推送', icon: <Calendar className="w-4 h-4" /> },
      { title: '阈值提醒', desc: 'KPI 达标提醒', icon: <Bell className="w-4 h-4" /> }
    ],
    demoContent: (
      <div
        className="bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white overflow-hidden"
        style={{ borderRadius: 16, overflow: 'hidden' }}
      >
        <div className="flex items-center gap-2 mb-4">
          <Bell className="w-4 h-4 text-rose-400" />
          <span className="text-white text-sm">订阅通知</span>
        </div>
        <div className="space-y-3">
          {[
            { type: 'alert', title: '销售异常告警', desc: '华东区销量下降超过 20%', time: '刚刚', color: 'rose' },
            { type: 'report', title: '日报已生成', desc: '2024-09-15 销售日报', time: '5分钟前', color: 'blue' },
            { type: 'milestone', title: 'KPI 已达标', desc: 'Q3季度目标完成 105%', time: '1小时前', color: 'emerald' }
          ].map((item, i) => (
            <div
              key={i}
              className="p-3"
              style={{
                borderRadius: 12,
                backgroundColor: toneMap[item.color]?.bg || 'rgba(148, 163, 184, 0.1)',
                border: `1px solid ${toneMap[item.color]?.border || 'rgba(148, 163, 184, 0.25)'}`,
              }}
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    {item.type === 'alert' && <AlertTriangle className="w-3.5 h-3.5" style={{ color: toneMap[item.color]?.text }} />}
                    {item.type === 'report' && <FileDown className="w-3.5 h-3.5" style={{ color: toneMap[item.color]?.text }} />}
                    {item.type === 'milestone' && <CheckCircle2 className="w-3.5 h-3.5" style={{ color: toneMap[item.color]?.text }} />}
                    <span className="text-xs text-white font-medium">{item.title}</span>
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1 ml-5">{item.desc}</p>
                </div>
                <span className="text-[9px] text-slate-500">{item.time}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    ),
    codeExample: {
      title: '创建订阅规则',
      language: 'json',
      code: `// 创建数据订阅
POST /api/subscriptions
{
  "name": "销售异常监控",
  "card_id": "daily_sales",
  "condition": {
    "field": "revenue",
    "operator": "<",
    "threshold": 100000
  },
  "notify": {
    "channels": ["email", "webhook"],
    "recipients": ["manager@company.com"]
  }
}`
    },
    keyBenefits: ['多渠道推送', '条件触发', '定时/实时', '已读回执']
  },
  quality: {
    description: '实时监控数据质量，及时发现数据问题并告警',
    useCases: [
      { title: '完整性检查', desc: '空值、缺失检测', icon: <CheckCircle2 className="w-4 h-4" /> },
      { title: '一致性验证', desc: '跨表数据校验', icon: <GitBranch className="w-4 h-4" /> },
      { title: '及时性监控', desc: '数据更新延迟告警', icon: <Clock className="w-4 h-4" /> }
    ],
    demoContent: (
      <div
        className="bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white overflow-hidden"
        style={{ borderRadius: 16, overflow: 'hidden' }}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Gauge className="w-4 h-4 text-violet-400" />
            <span className="text-white text-sm">数据质量评分</span>
          </div>
          <span className="text-emerald-400 font-bold">98.5%</span>
        </div>
        <div className="space-y-3">
          {[
            { name: '完整性', score: 99.2, color: 'emerald' },
            { name: '准确性', score: 97.8, color: 'blue' },
            { name: '一致性', score: 98.5, color: 'violet' },
            { name: '及时性', score: 96.3, color: 'amber' }
          ].map((item, i) => (
            <div key={i}>
              <div className="flex justify-between text-[10px] mb-1">
                <span className="text-slate-400">{item.name}</span>
                <span style={{ color: toneMap[item.color]?.text || '#94a3b8' }}>{item.score}%</span>
              </div>
              <div
                className="h-2 bg-slate-700 overflow-hidden"
                style={{ borderRadius: 9999, overflow: 'hidden' }}
              >
                <div
                  className="h-full"
                  style={{ width: `${item.score}%`, backgroundColor: toneMap[item.color]?.bar || '#64748b', borderRadius: 9999 }}
                ></div>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 pt-3 border-t border-slate-700">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-amber-400 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" /> 2 项需关注
            </span>
            <span className="text-[10px] text-slate-500">最近检测: 5分钟前</span>
          </div>
        </div>
      </div>
    ),
    codeExample: {
      title: '质量检测报告',
      language: 'json',
      code: `// 数据质量检测结果
{
  "table": "orders",
  "total_rows": 125847,
  "issues": [
    {
      "type": "null_count",
      "column": "customer_id",
      "count": 23,
      "severity": "warning"
    },
    {
      "type": "duplication",
      "column": "order_id",
      "count": 5,
      "severity": "error"
    }
  ],
  "score": 98.5
}`
    },
    keyBenefits: ['多维质检', '自动告警', '根因分析', '趋势追踪']
  },
  sharing: {
    description: '构建企业内部数据市场，实现数据资产的安全共享与价值变现',
    useCases: [
      { title: '内部共享', desc: '部门间数据协作', icon: <Share2 className="w-4 h-4" /> },
      { title: 'API 市场', desc: '数据服务化', icon: <Webhook className="w-4 h-4" /> },
      { title: '权限管理', desc: '细粒度访问控制', icon: <Settings className="w-4 h-4" /> }
    ],
    demoContent: (
      <div
        className="bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white overflow-hidden"
        style={{ borderRadius: 16, overflow: 'hidden' }}
      >
        <div className="text-xs mb-4">
          <span className="text-teal-400">数据市场</span>
          <span className="text-slate-400 ml-2">| 已发布的数据服务</span>
        </div>
        <div className="space-y-2">
          {[
            { name: '客户画像数据', owner: '市场部', usage: 156, rating: 4.8, type: 'API' },
            { name: '销售汇总数据', owner: '销售部', usage: 89, rating: 4.6, type: '数据集' },
            { name: '产品目录API', owner: '产品部', usage: 234, rating: 4.9, type: 'API' }
          ].map((item, i) => (
            <div key={i} className="bg-white/5 p-3 flex items-center justify-between" style={{ borderRadius: 12 }}>
              <div className="flex items-center gap-3">
                <div
                  className="w-8 h-8 bg-teal-500/20 flex items-center justify-center"
                  style={{ borderRadius: 10 }}
                >
                  <Database className="w-4 h-4 text-teal-400" />
                </div>
                <div>
                  <div className="text-xs text-white">{item.name}</div>
                  <div className="text-[9px] text-slate-500">{item.owner} · {item.type}</div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-[10px] text-slate-400">{item.usage} 次调用</div>
                <div className="text-[10px] text-amber-400">★ {item.rating}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    ),
    codeExample: {
      title: '数据市场 API',
      language: 'javascript',
      code: `// 发现并申请数据
const datasets = await onticards.marketplace.list({
  category: 'sales',
  filters: { public: true }
});

// 申请数据访问权限
await onticards.marketplace.requestAccess({
  dataset_id: 'customer_profile',
  purpose: 'CRM系统对接'
});`
    },
    keyBenefits: ['一键发布', '权限审批', '使用计量', '价值评估']
  },
  report: {
    description: '自动化生成各类报表，减少人工统计工作量，提高工作效率',
    useCases: [
      { title: '日报周报', desc: '自动汇总数据', icon: <Calendar className="w-4 h-4" /> },
      { title: '经营分析', desc: '多维度数据对比', icon: <BarChart className="w-4 h-4" /> },
      { title: '数据简报', desc: '一键生成摘要', icon: <FileDown className="w-4 h-4" /> }
    ],
    demoContent: (
      <div
        className="bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white overflow-hidden"
        style={{ borderRadius: 16, overflow: 'hidden' }}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <LayoutDashboard className="w-4 h-4 text-indigo-400" />
            <span className="text-white text-sm">自动化报表</span>
          </div>
          <span
            className="text-[10px] px-2 py-0.5 bg-indigo-500/20 text-indigo-300"
            style={{ borderRadius: 8 }}
          >
            已生成
          </span>
        </div>
        <div className="bg-white/5 p-4 mb-4" style={{ borderRadius: 12 }}>
          <div className="text-xs text-indigo-300 mb-2">销售日报 · 2024-09-15</div>
          <div className="space-y-2 text-[10px]">
            <div className="flex justify-between">
              <span className="text-slate-400">今日销售额</span>
              <span className="text-white font-medium">¥89,234</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">订单数量</span>
              <span className="text-white font-medium">1,234 单</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">客单价</span>
              <span className="text-white font-medium">¥72.3</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">环比昨日</span>
              <span className="text-emerald-400">↑ 5.2%</span>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="flex-1 bg-indigo-500/20 text-indigo-300 py-2 text-[10px] flex items-center justify-center gap-1"
            style={{ borderRadius: 10 }}
          >
            <Eye className="w-3 h-3" /> 查看详情
          </button>
          <button
            type="button"
            className="flex-1 bg-white/10 text-slate-300 py-2 text-[10px] flex items-center justify-center gap-1"
            style={{ borderRadius: 10 }}
          >
            <Download className="w-3 h-3" /> 下载
          </button>
        </div>
      </div>
    ),
    codeExample: {
      title: '报表生成 API',
      language: 'javascript',
      code: `// 创建自动化报表任务
const report = await onticards.reports.create({
  template: 'sales_daily',
  schedule: '0 9 * * *', // 每天9点
  recipients: ['manager@company.com'],
  format: 'pdf',
  channels: ['email', 'slack']
});

// 手动触发一次
await report.runNow();`
    },
    keyBenefits: ['多种模板', '定时调度', '多渠道发送', '历史归档']
  },
  metrics: {
    description: '统一管理企业指标体系，确保数据口径一致，避免数据指标歧义',
    useCases: [
      { title: '指标定义', desc: '统一口径管理', icon: <Target className="w-4 h-4" /> },
      { title: '指标血缘', desc: '追踪数据来源', icon: <GitBranch className="w-4 h-4" /> },
      { title: '指标监控', desc: '指标异常告警', icon: <Activity className="w-4 h-4" /> }
    ],
    demoContent: (
      <div
        className="bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white overflow-hidden"
        style={{ borderRadius: 16, overflow: 'hidden' }}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-yellow-400" />
            <span className="text-white text-sm">核心指标</span>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 mb-4">
          {[
            { name: 'DAU', value: '12.5K', trend: '+3.2%', color: 'emerald' },
            { name: 'MAU', value: '89.2K', trend: '+5.1%', color: 'blue' },
            { name: 'ARPU', value: '¥45.8', trend: '-1.2%', color: 'amber' },
            { name: '留存率', value: '68.5%', trend: '+2.3%', color: 'violet' }
          ].map((m, i) => (
            <div key={i} className="bg-white/5 p-2.5" style={{ borderRadius: 12 }}>
              <div className="text-[9px] text-slate-400 mb-1">{m.name}</div>
              <div className="text-sm font-bold text-white">{m.value}</div>
              <div className={`text-[9px] ${m.trend.startsWith('+') ? 'text-emerald-400' : 'text-rose-400'}`}>
                {m.trend}
              </div>
            </div>
          ))}
        </div>
        <div className="bg-white/5 p-3" style={{ borderRadius: 12 }}>
          <div className="text-[10px] text-slate-400 mb-2">指标血缘</div>
          <div className="flex items-center justify-between text-[9px]">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-slate-600"></div>
              <span className="text-slate-400">原始表</span>
            </div>
            <ArrowRight className="w-3 h-3 text-slate-500" />
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-yellow-500"></div>
              <span className="text-slate-400">ETL</span>
            </div>
            <ArrowRight className="w-3 h-3 text-slate-500" />
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
              <span className="text-slate-400">指标</span>
            </div>
          </div>
        </div>
      </div>
    ),
    codeExample: {
      title: '指标定义',
      language: 'yaml',
      code: `# 指标定义示例
metrics:
  - name: daily_revenue
    expression: |
      SUM(orders.amount)
    dimensions:
      - region
      - product_category
    filters:
      - status = 'completed'
    description: 日销售额
    owner: finance_team
    data_quality_expectation: > 10000`
    },
    keyBenefits: ['口径统一', '血缘追溯', '版本管理', '质量监控']
  },
  docs: {
    description: '自动生成数据字典和文档，让数据资产可发现、可理解',
    useCases: [
      { title: '数据字典', desc: '表字段说明', icon: <Book className="w-4 h-4" /> },
      { title: '业务标签', desc: '业务含义标注', icon: <Layers className="w-4 h-4" /> },
      { title: '使用指南', desc: '数据使用说明', icon: <ClipboardList className="w-4 h-4" /> }
    ],
    demoContent: (
      <div
        className="bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white overflow-hidden"
        style={{ borderRadius: 16, overflow: 'hidden' }}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-slate-300" />
            <span className="text-white text-sm">数据文档</span>
          </div>
        </div>
        <div className="bg-white/5 overflow-hidden" style={{ borderRadius: 12 }}>
          <div className="px-3 py-2 border-b border-slate-700">
            <div className="text-xs text-white font-medium">orders (订单表)</div>
            <div className="text-[9px] text-slate-500">记录所有用户订单信息</div>
          </div>
          <div className="divide-y divide-slate-700/50">
            {[
              { field: 'order_id', type: 'VARCHAR(32)', desc: '订单唯一标识', biz: '主键' },
              { field: 'user_id', type: 'VARCHAR(32)', desc: '用户ID', biz: '关联用户表' },
              { field: 'amount', type: 'DECIMAL(10,2)', desc: '订单金额', biz: '单位：元' },
              { field: 'status', type: 'TINYINT', desc: '订单状态', biz: '1-待支付 2-已支付' }
            ].map((col, i) => (
              <div key={i} className="px-3 py-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-cyan-400">{col.field}</span>
                  <span className="text-[9px] text-slate-500">{col.type}</span>
                </div>
                <div className="text-[9px] text-slate-400 mt-0.5">{col.desc}</div>
                <div className="text-[9px] text-amber-400/70 mt-0.5">📌 {col.biz}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    ),
    codeExample: {
      title: '获取数据文档',
      language: 'javascript',
      code: `// 获取表文档
const docs = await onticards.docs.getTable('orders');

// 返回完整的数据字典
{
  table: "orders",
  description: "订单主表",
  business_owner: "交易团队",
  columns: [
    {
      name: "order_id",
      type: "VARCHAR",
      description: "订单唯一ID",
      tags: ["PII"],
      sample: "ORD202409150001"
    }
  ],
  relationships: [...],
  usage_notes: "..."
}`
    },
    keyBenefits: ['自动生成', '业务标注', '版本同步', '搜索发现']
  },
  'quality-report': {
    description: '查看数据质量检测报告，了解数据健康状况，及时发现并处理潜在数据问题',
    useCases: [
      { title: '质量总览', desc: '整体数据健康评分', icon: <Activity className="w-4 h-4" /> },
      { title: '问题明细', desc: '各类质量问题列表', icon: <AlertTriangle className="w-4 h-4" /> },
      { title: '趋势分析', desc: '质量变化趋势追踪', icon: <LineChartIcon className="w-4 h-4" /> }
    ],
    demoContent: (
      <div
        className="bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white overflow-hidden"
        style={{ borderRadius: 16, overflow: 'hidden' }}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <ClipboardList className="w-4 h-4 text-red-400" />
            <span className="text-white text-sm">数据质检报告</span>
          </div>
          <span className="text-[10px] px-2 py-0.5 bg-amber-500/20 text-amber-300" style={{ borderRadius: 8 }}>
            检测时间: 2024-09-15 14:30
          </span>
        </div>
        <div className="grid grid-cols-3 gap-2 mb-4">
          {[
            { name: '整体评分', value: '96.5', color: 'emerald', status: '优秀' },
            { name: '问题数', value: '12', color: 'amber', status: '待处理' },
            { name: '检测表数', value: '156', color: 'blue', status: '已扫描' }
          ].map((item, i) => (
            <div key={i} className="bg-white/5 p-3" style={{ borderRadius: 12 }}>
              <div className="text-[9px] text-slate-400 mb-1">{item.name}</div>
              <div className="text-lg font-bold" style={{ color: toneMap[item.color]?.text || '#94a3b8' }}>{item.value}</div>
              <div className="text-[9px] text-slate-500">{item.status}</div>
            </div>
          ))}
        </div>
        <div className="space-y-2">
          <div className="text-[10px] text-slate-400 mb-2">典型问题分布</div>
          {[
            { type: '空值检测', count: 5, severity: 'warning', color: 'amber' },
            { type: '格式异常', count: 3, severity: 'error', color: 'rose' },
            { type: '重复记录', count: 2, severity: 'warning', color: 'amber' },
            { type: '数据漂移', count: 2, severity: 'info', color: 'blue' }
          ].map((item, i) => (
            <div key={i} className="flex items-center justify-between bg-white/5 p-2" style={{ borderRadius: 10 }}>
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-3.5 h-3.5" style={{ color: toneMap[item.color]?.text }} />
                <span className="text-[10px] text-slate-300">{item.type}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-slate-500">{item.count} 项</span>
                <span
                  className="text-[9px] px-1.5 py-0.5"
                  style={{
                    borderRadius: 6,
                    backgroundColor: toneMap[item.color]?.bg,
                    color: toneMap[item.color]?.text
                  }}
                >
                  {item.severity === 'error' ? '严重' : item.severity === 'warning' ? '警告' : '提示'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    ),
    codeExample: {
      title: '获取质检报告',
      language: 'json',
      code: `// 获取数据质量报告
GET /api/v1/quality/report

Response:
{
  "report_id": "QR20240915001",
  "generated_at": "2024-09-15T14:30:00Z",
  "overall_score": 96.5,
  "summary": {
    "total_tables": 156,
    "checked_tables": 156,
    "issues_found": 12,
    "critical": 2,
    "warnings": 8,
    "info": 2
  },
  "top_issues": [
    {
      "type": "null_count",
      "severity": "warning",
      "affected_columns": 5
    }
  ]
}`
    },
    keyBenefits: ['全面检测', '问题分级', '趋势追踪', '一键导出']
  },
  'quality-fix': {
    description: '基于质检报告生成修复建议，指导数据团队快速定位并解决数据质量问题',
    useCases: [
      { title: 'SQL 修复', desc: '自动生成修复脚本', icon: <Code className="w-4 h-4" /> },
      { title: '根因分析', desc: '问题溯源定位', icon: <Target className="w-4 h-4" /> },
      { title: '修复跟踪', desc: '问题处理进度', icon: <CheckCircle2 className="w-4 h-4" /> }
    ],
    demoContent: (
      <div
        className="bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white overflow-hidden"
        style={{ borderRadius: 16, overflow: 'hidden' }}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Settings className="w-4 h-4 text-cyan-400" />
            <span className="text-white text-sm">数据修复建议</span>
          </div>
          <span className="text-[10px] px-2 py-0.5 bg-cyan-500/20 text-cyan-300" style={{ borderRadius: 8 }}>
            AI 智能分析
          </span>
        </div>
        <div className="space-y-3">
          {[
            {
              issue: 'orders.amount 字段存在 23 条空值',
              severity: 'warning',
              color: 'amber',
              status: '待处理',
              suggestions: [
                '检查 ETL 流程是否正常',
                '评估是否需要设置默认值'
              ]
            },
            {
              issue: 'customer.email 格式不一致',
              severity: 'error',
              color: 'rose',
              status: '进行中',
              suggestions: [
                '统一邮箱格式校验规则',
                '清理历史脏数据'
              ]
            }
          ].map((item, i) => (
            <div key={i} className="bg-white/5 p-3" style={{ borderRadius: 12 }}>
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-3.5 h-3.5" style={{ color: toneMap[item.color]?.text }} />
                  <span className="text-[10px] text-slate-300">{item.issue}</span>
                </div>
                <span
                  className="text-[9px] px-1.5 py-0.5"
                  style={{
                    borderRadius: 6,
                    backgroundColor: item.status === '进行中' ? 'rgba(59, 130, 246, 0.2)' : 'rgba(148, 163, 184, 0.2)',
                    color: item.status === '进行中' ? '#60a5fa' : '#94a3b8'
                  }}
                >
                  {item.status}
                </span>
              </div>
              <div className="pl-5 space-y-1.5">
                <div className="text-[9px] text-slate-500">修复建议：</div>
                {item.suggestions.map((s, j) => (
                  <div key={j} className="flex items-start gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 mt-1.5 flex-shrink-0"></div>
                    <span className="text-[10px] text-slate-400">{s}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 pt-3 border-t border-slate-700">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-slate-500">修复进度: 8/12 问题已处理</span>
            <div className="flex gap-1">
              <button
                className="px-2 py-1 bg-cyan-500/20 text-cyan-300 text-[9px]"
                style={{ borderRadius: 6 }}
              >
                生成修复脚本
              </button>
            </div>
          </div>
        </div>
      </div>
    ),
    codeExample: {
      title: '获取修复建议',
      language: 'json',
      code: `// 获取修复建议
POST /api/v1/quality/fix-suggestions

{
  "issue_ids": ["NULL_001", "FORMAT_002"]
}

Response:
{
  "suggestions": [
    {
      "issue_id": "NULL_001",
      "table": "orders",
      "column": "amount",
      "severity": "warning",
      "suggestions": [
        {
          "type": "sql_script",
          "priority": 1,
          "description": "替换空值为默认值",
          "sql": "UPDATE orders SET amount = 0 WHERE amount IS NULL"
        },
        {
          "type": "root_cause",
          "priority": 2,
          "description": "检查上游 ETL 数据源"
        }
      ]
    }
  ]
}`
    },
    keyBenefits: ['智能分析', 'SQL 修复', '根因定位', '进度追踪']
  }
};

// 每个消费案例对应的系统功能点，突出 OntiCards 价值
const scenarioSystemFeatures: Record<ScenarioType, Array<{ title: string; desc: string }>> = {
  bi: [
    { title: '业务化数据目录', desc: '数据卡片是表级业务说明（非预聚合指标）；BI 可据此理解语义并通过 API 取数建模。' },
    { title: '工作空间统一管理', desc: '在同一工作空间维护数据口径，确保多报表数据口径一致，避免数据歧义。' },
    { title: '多数据源接入', desc: '快速连接 MySQL/PostgreSQL/Oracle 等异构数据源，一次接入多处复用。' },
  ],
  'ai-agent': [
    { title: '智能问数', desc: '自然语言转 SQL 与结果解释，缩短业务问数链路，让智能体具备数据查询能力。' },
    { title: 'API Key 认证', desc: '提供独立的 API Key 认证方式，支持智能体平台无缝接入，无需额外登录流程。' },
    { title: '向量索引能力', desc: '利用向量检索增强语义理解与召回准确率，提升问答准确率。' },
  ],
  api: [
    { title: 'API Keys 管理', desc: '在系统内统一签发与轮转 Key，保障接口访问安全。' },
    { title: '标准化查询 API', desc: '统一返回结构与字段说明，便于 CRM、ERP、APP 等系统按需取数与二次开发。' },
    { title: '工作空间隔离', desc: '不同业务线按空间隔离接口权限与数据范围。' },
  ],
  prediction: [
    { title: '数据准备能力', desc: '提供清洗后的结构化数据，为第三方预测模型提供高质量数据输入。' },
    { title: '趋势查询支持', desc: '支持自然语言提问趋势类问题，如「近三个月销量走势」「环比增长率」等。' },
    { title: '第三方指标闭环', desc: '通过标准化 API 将查询结果对接到指标平台或 BI，形成预测与监控闭环。' },
  ],
  export: [
    { title: '口径一致导出', desc: '同一问数或同一数据卡片口径可导出为 Excel/CSV/JSON 等，减少重复取数与口径漂移。' },
    { title: '盘点与作业协同', desc: '盘点、问数等作业产生的数据可配合导出流程，便于线下分析与留痕追溯。' },
    { title: '权限边界控制', desc: '结合用户数据源权限与角色，限制可导出数据范围，降低敏感数据外泄风险。' },
  ],
  subscription: [
    { title: '指标阈值告警', desc: '系统提供稳定取数能力，可配合定时脚本或第三方监控在指标越界时触发告警。' },
    { title: '自动化报表联动', desc: '通过 API 定时拉取数据，结合邮件、企业微信、Webhook 等渠道实现报表自动分发。' },
    { title: '最近动态可追踪', desc: '关键操作与查询行为可在概览「最近动态」留痕，便于回溯与协同。' },
  ],
  quality: [
    { title: '数据源与表级巡检', desc: '对接入库表执行质量检测，支持异常值等问题的发现与报告输出。' },
    { title: '问数结果可解释', desc: '每次查询附带数据来源与条件说明，便于核对完整性与一致性，提升消费可信度。' },
    { title: '异常闭环（可扩展）', desc: '质量报告可对接邮件、IM、工单等第三方通道，缩短问题发现到处理的时间。' },
  ],
  sharing: [
    { title: '数据服务化发布', desc: '将数据卡片与 API 作为可复用资产对外提供，供其他团队或系统订阅调用。' },
    { title: '权限与隔离', desc: '通过工作空间与用户数据源权限控制共享边界，降低越权访问风险。' },
    { title: '文档与卡片同源', desc: '数据卡片自带表/字段业务说明，降低跨团队沟通与交接成本。' },
  ],
  report: [
    { title: '定时取数编排', desc: '通过 API 与定时任务（脚本、调度平台）按日/周/月拉取数据，自动生成固定报表。' },
    { title: '口径与模板解耦', desc: '报表模板引用同一问数口径或数据卡片说明，口径调整时减少多处改模成本。' },
    { title: '运营闭环（可扩展）', desc: '报表结果可继续推送至订阅、指标看板或第三方系统，形成分析与运营闭环。' },
  ],
  metrics: [
    { title: '统一口径底座', desc: '在工作空间与数据卡片层沉淀业务语义与表关系，为第三方指标平台提供一致口径依据。' },
    { title: '跨库指标计算', desc: '基于已接入多数据源与自然语言问数，完成跨库汇总、对比类指标取数。' },
    { title: '多入口消费', desc: '同一指标逻辑可通过问数、API、导出等方式被 BI、智能体等多场景复用。' },
  ],
  docs: [
    { title: '自动数据字典', desc: '随数据源扫描与卡片生成，自动维护表/字段及业务含义说明。' },
    { title: '探索与检索', desc: '通过探索页按数据源、状态等筛选浏览卡片，提升资产可发现性。' },
    { title: '协作口径一致', desc: '团队共用同一套卡片与问数入口，减少「同名不同义」与口头传递偏差。' },
  ],
  'quality-report': [
    { title: '多维度质检', desc: '支持空值、格式、重复、数据漂移等多维度数据质量检测，全面评估数据健康状况。' },
    { title: '可视化报告', desc: '生成直观的质检报告，包括评分、问题分布、趋势分析等，便于管理层了解数据质量。' },
    { title: '定时检测任务', desc: '可配置定时质检任务，持续监控数据质量变化，及时发现新出现的问题。' },
  ],
  'quality-fix': [
    { title: '智能修复建议', desc: '基于质检结果自动生成修复建议和 SQL 脚本，指导数据团队快速解决问题。' },
    { title: '根因分析能力', desc: '帮助定位数据问题的根本原因，从源头杜绝同类问题重复发生。' },
    { title: '修复进度追踪', desc: '记录问题处理状态，确保每个发现的问题都能得到妥善解决和闭环。' },
  ],
};

const DataConsumeScenariosModal: React.FC<DataConsumeScenariosModalProps> = ({
  isOpen,
  onClose,
  scenarioType
}) => {
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const isDark = useDarkMode();

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!isOpen) {
      setCopiedCode(null);
    }
  }, [isOpen]);

  if (!isOpen || !scenarioType || !mounted) return null;

  const config = scenarioConfig[scenarioType];
  const content = scenarioContents[scenarioType];
  const featureList = scenarioSystemFeatures[scenarioType];
  const accentHex = scenarioAccentHex[scenarioType];

  const handleCopy = async (code: string, id: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedCode(id);
      setTimeout(() => setCopiedCode(null), 2000);
    } catch (err) {
      console.error('复制失败', err);
    }
  };

  // 深色模式样式
  const styles = {
    modal: {
      background: isDark ? '#1e293b' : '#ffffff',
      border: isDark ? '1px solid rgba(71, 85, 105, 0.6)' : '1px solid rgba(226, 232, 240, 0.8)',
    },
    header: {
      background: isDark ? '#0f172a' : '#f8fafc',
      borderBottom: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid rgba(226, 232, 240, 0.9)',
    },
    headerIcon: {
      background: isDark ? '#1e293b' : '#ffffff',
      border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
    },
    closeButton: isDark ? {
      background: '#1e293b',
      border: '1px solid rgba(71, 85, 105, 0.5)',
      color: '#94a3b8',
    } : {
      background: '#ffffff',
      border: '1px solid #e2e8f0',
      color: '#64748b',
    },
    title: {
      color: isDark ? '#f1f5f9' : '#1e293b',
    },
    subtitle: {
      color: isDark ? '#94a3b8' : '#64748b',
    },
    demoContainer: {
      border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
    },
    featureSection: {
      background: isDark ? '#0f172a' : '#fafafa',
      border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
    },
    featureItem: {
      background: isDark ? '#1e293b' : '#ffffff',
      border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
    },
    featureTitle: {
      color: isDark ? '#e2e8f0' : '#334155',
    },
    featureDesc: {
      color: isDark ? '#94a3b8' : '#64748b',
    },
    sectionTitle: {
      color: isDark ? '#f1f5f9' : '#1e293b',
    },
    useCaseItem: {
      background: isDark ? '#0f172a' : '#f8fafc',
      border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
    },
    useCaseIcon: {
      background: isDark ? '#1e293b' : '#ffffff',
      border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
    },
    useCaseTitle: {
      color: isDark ? '#e2e8f0' : '#334155',
    },
    useCaseDesc: {
      color: isDark ? '#94a3b8' : '#64748b',
    },
    codeContainer: {
      border: isDark ? '1px solid rgba(51, 65, 85, 0.8)' : '1px solid #1e293b',
    },
    codeHeader: {
      background: isDark ? '#0f172a' : '#1e293b',
    },
    benefitItem: {
      background: isDark ? 'rgba(30, 41, 59, 0.8)' : '#f1f5f9',
      border: isDark ? '1px solid rgba(71, 85, 105, 0.5)' : '1px solid #e2e8f0',
      color: isDark ? '#cbd5e1' : '#475569',
    },
  };

  const modalContent = (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div
        className="relative w-full max-w-3xl max-h-[88vh] overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-200"
        style={{
          borderRadius: 24,
          boxShadow: isDark ? '0 20px 70px rgba(0, 0, 0, 0.5)' : '0 20px 70px rgba(15, 23, 42, 0.35)',
          ...styles.modal,
        }}
      >
        {/* Header */}
        <div
          className="flex-shrink-0 p-5"
          style={{
            borderTopLeftRadius: 24,
            borderTopRightRadius: 24,
            ...styles.header,
          }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className="flex items-center justify-center shrink-0"
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 12,
                  ...styles.headerIcon,
                  color: accentHex,
                }}
              >
                {config.icon}
              </div>
              <div>
                <h2 className="text-lg font-semibold" style={styles.title}>{config.title}</h2>
                <p className="text-xs mt-0.5 leading-relaxed" style={styles.subtitle}>{content.description}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="flex items-center justify-center transition-colors hover:opacity-80"
              style={{
                width: 32,
                height: 32,
                borderRadius: 10,
                ...styles.closeButton,
              }}
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Demo Display */}
          <div
            className="overflow-hidden shadow-sm"
            style={{ borderRadius: 16, ...styles.demoContainer }}
          >
            {content.demoContent}
          </div>

          {/* OntiCards 功能点价值映射 */}
          <div
            style={{
              borderRadius: 16,
              padding: 14,
              ...styles.featureSection,
            }}
          >
            <h3 className="text-sm font-semibold mb-3" style={styles.sectionTitle}>本案例体现的系统功能点</h3>
            <div className="space-y-2.5">
              {featureList.map((feature, i) => (
                <div
                  key={i}
                  style={{
                    borderRadius: 12,
                    padding: '10px 12px',
                    ...styles.featureItem,
                  }}
                >
                  <div className="text-xs font-semibold mb-1" style={styles.featureTitle}>{feature.title}</div>
                  <div className="text-[11px] leading-5" style={styles.featureDesc}>{feature.desc}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Use Cases */}
          <div>
            <h3 className="text-sm font-semibold mb-3" style={styles.sectionTitle}>适用场景</h3>
            <div className="grid grid-cols-3 gap-2">
              {content.useCases.map((useCase, i) => (
                <div
                  key={i}
                  className="text-center"
                  style={{
                    borderRadius: 14,
                    padding: 12,
                    ...styles.useCaseItem,
                  }}
                >
                  <div
                    className="mx-auto mb-2 flex items-center justify-center"
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 10,
                      ...styles.useCaseIcon,
                      color: accentHex,
                    }}
                  >
                    {useCase.icon}
                  </div>
                  <div className="text-xs font-medium" style={styles.useCaseTitle}>{useCase.title}</div>
                  <div className="text-[10px] mt-0.5" style={styles.useCaseDesc}>{useCase.desc}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Code Example */}
          {content.codeExample && (
            <div>
              <h3 className="text-sm font-semibold mb-3" style={styles.sectionTitle}>代码示例</h3>
              <div className="bg-slate-900 overflow-hidden" style={{ borderRadius: 16, ...styles.codeContainer }}>
                <div
                  className="flex items-center justify-between px-4 py-2"
                  style={{
                    borderTopLeftRadius: 16,
                    borderTopRightRadius: 16,
                    background: isDark ? '#0f172a' : '#1e293b',
                  }}
                >
                  <span className="text-xs text-slate-400">{content.codeExample.title}</span>
                  <button
                    type="button"
                    onClick={() => handleCopy(content.codeExample!.code, scenarioType)}
                    className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-white transition-colors"
                    style={{ borderRadius: 10, padding: '6px 10px', background: 'rgba(255,255,255,0.06)' }}
                  >
                    {copiedCode === scenarioType ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-400" />
                        <span className="text-emerald-400">已复制</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        <span>复制</span>
                      </>
                    )}
                  </button>
                </div>
                <pre className="p-4 text-[11px] text-slate-300 font-mono overflow-x-auto">
                  <code>{content.codeExample.code}</code>
                </pre>
              </div>
            </div>
          )}

          {/* Key Benefits */}
          <div>
            <h3 className="text-sm font-semibold mb-3" style={styles.sectionTitle}>核心优势</h3>
            <div className="flex flex-wrap gap-2">
              {content.keyBenefits.map((benefit, i) => (
                <div
                  key={i}
                  className="inline-flex items-center gap-1.5 flex-shrink-0 whitespace-nowrap text-xs"
                  style={{
                    borderRadius: 9999,
                    padding: '6px 12px',
                    ...styles.benefitItem,
                  }}
                >
                  <CheckCircle2 className="w-3.5 h-3.5 shrink-0" style={{ color: accentHex }} />
                  {benefit}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  if (typeof window === 'undefined') return null;
  return createPortal(modalContent, document.body);
};

export default DataConsumeScenariosModal;

// 导出类型供外部使用
export type { DataConsumeScenariosModalProps };
