'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import { createPortal } from 'react-dom';
import { useRouter } from 'next-nprogress-bar';
import { App } from 'antd';
import {
  X,
  Loader2,
  CheckCircle,
  AlertCircle,
  Sparkles,
  Check,
  ArrowRight,
  Search,
  Table2,
  Eye,
  ListFilter
} from 'lucide-react';
import { testConnection, extractSchema, cancelExtractSchema, listTables, DataSourceConfig, DatabaseType, TableListItem } from '@/api/datasource';
import { useUserInfo } from '@/hooks/useUserInfo';

interface AddDataSourceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

// 数据库类型配置
const databaseTypes = [
  { value: 'mysql', label: 'MySQL', icon: '🐬' },
  { value: 'postgresql', label: 'PostgreSQL', icon: '🐘' },
  { value: 'mssql', label: 'SQL Server', icon: '🏢' },
  { value: 'oracle', label: 'Oracle', icon: '🔶' },
  { value: 'trino', label: 'Trino', icon: '🐰' },
  { value: 'kingbase', label: 'KingBase', icon: '🛡️' },
  { value: 'oceanbase', label: 'OceanBase(MySQL)', icon: '🌊' },
  { value: 'dm', label: 'DMBase(达梦)', icon: '💠' },
  { value: 'sqlite', label: 'SQLite', icon: '📄' }
];

const AddDataSourceModal: React.FC<AddDataSourceModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const { message } = App.useApp();
  const router = useRouter();
  const { userInfo } = useUserInfo();
  const isAdmin = userInfo?.role === 'admin';
  const [step, setStep] = useState<'form' | 'testing' | 'saving' | 'success'>('form');
  const [selectedDbType, setSelectedDbType] = useState<DatabaseType>('mysql');
  const [connectionMode, setConnectionMode] = useState<string>('host');
  const [showPassword, setShowPassword] = useState(false);

  const [formData, setFormData] = useState<DataSourceConfig>({
    connect_name: '',
    dbType: 'mysql'
  });

  // 连接测试结果
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
    details?: any;
  } | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  // 抽取模式相关状态
  const [extractMode, setExtractMode] = useState<'full' | 'select'>('full');
  const [tableList, setTableList] = useState<TableListItem[]>([]);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const [isLoadingTables, setIsLoadingTables] = useState(false);
  const [showTableSelector, setShowTableSelector] = useState(false);
  const [tableSearchKeyword, setTableSearchKeyword] = useState('');
  const [tableTypeFilter, setTableTypeFilter] = useState<'all' | 'TABLE' | 'VIEW'>('all');

  // 保存进度 - 任务列表形式（含实时进度）
  const [savingSteps, setSavingSteps] = useState<{ id: string; name: string; description: string; status: 'pending' | 'processing' | 'completed'; progress: number }[]>([]);

  // 是否显示保存动画（用于快速判断是否需要显示动画）
  const [showAnimation, setShowAnimation] = useState(false);

  // 验证错误
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  // 路由参数中的语言代码，默认 zh-CN
  const params = useParams<{ lng?: string }>();
  const lng = params?.lng ?? 'zh-CN';

  // 取消功能相关状态
  const abortControllerRef = useRef<AbortController | null>(null);
  const savingCancelledRef = useRef(false);
  // 用于“取消后再次保存”时正确检测当前这次 extract 是否已返回（Promise 无 .status，用 ref 标记）
  const extractSchemaErrorRef = useRef<string | null>(null);
  // 用于"取消后再次保存"时正确检测当前这次 extract 是否已返回（Promise 无 .status，用 ref 标记）
  const extractResolvedRef = useRef(false);
  // 用于通知动画 API 已成功返回，动画可以继续执行到完成
  const apiSuccessRef = useRef(false);

  // 内容区域滚动 ref
  const contentRef = useRef<HTMLDivElement>(null);

  // 测试连接结果变化时，自动滚动到底部
  useEffect(() => {
    if (testResult && contentRef.current) {
      // 使用 requestAnimationFrame 确保在 DOM 更新后执行
      requestAnimationFrame(() => {
        if (contentRef.current) {
          contentRef.current.scrollTo({
            top: contentRef.current.scrollHeight,
            behavior: 'smooth'
          });
        }
      });
    }
  }, [testResult]);

  useEffect(() => {
    if (!isOpen) {
      // 如果正在保存数据源，取消正在进行的请求
      if (abortControllerRef.current) {
        console.log('模态框关闭，取消正在进行的数据源添加请求');
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }

      savingCancelledRef.current = true;
      extractResolvedRef.current = false;

      // 重置状态
      setStep('form');
      setSelectedDbType('mysql');
      setConnectionMode('host');
      setFormData({ connect_name: '', dbType: 'mysql' });
      setTestResult(null);
      setSavingSteps([]);
      setValidationErrors({});
      // 重置抽取模式相关状态
      setExtractMode('full');
      setTableList([]);
      setSelectedTables([]);
      setIsLoadingTables(false);
      setShowTableSelector(false);
      setTableSearchKeyword('');
      setTableTypeFilter('all');
    }
  }, [isOpen]);

  // 过滤后的表列表
  const filteredTables = tableList.filter(table => {
    const matchSearch = tableSearchKeyword === '' ||
      table.name.toLowerCase().includes(tableSearchKeyword.toLowerCase());
    const matchType = tableTypeFilter === 'all' || table.type === tableTypeFilter;
    return matchSearch && matchType;
  });

  // 已选中的表数量统计
  const selectedTableCount = selectedTables.length;
  const totalTableCount = filteredTables.length;
  const allSelected = totalTableCount > 0 && selectedTables.length === tableList.length;

  const handleDbTypeChange = (type: DatabaseType) => {
    setSelectedDbType(type);
    setFormData(prev => ({ ...prev, dbType: type }));
    setTestResult(null);
    // 重置连接方式
    if (type === 'oracle') {
      setConnectionMode('service_name');
    } else if (type === 'sqlite') {
      setConnectionMode('file');
    } else if (type === 'mssql') {
      setConnectionMode('host');
    }
  };

  const handleConnectionModeChange = (mode: string) => {
    setConnectionMode(mode);
    setTestResult(null);
  };

  const handleFormChange = (field: string, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setTestResult(null);
  };

  const validateForm = () => {
    const errors: Record<string, string> = {};

    if (!formData.connect_name?.trim()) {
      errors.connect_name = '请输入数据源名称';
    }

    // SQLite 文件模式
    if (selectedDbType === 'sqlite' && connectionMode === 'file') {
      if (!formData.sqlite_path?.trim()) {
        errors.sqlite_path = '请输入SQLite文件路径';
      }
    }
    // SQLite 内存模式 - 不需要额外字段
    else if (selectedDbType === 'sqlite' && connectionMode === 'memory') {
      // 无需验证
    }
    // SQL Server DSN 模式
    else if (selectedDbType === 'mssql' && connectionMode === 'dsn') {
      if (!formData.dsn?.trim()) {
        errors.dsn = '请输入DSN名称';
      }
    }
    // 其他数据库（主机模式）
    else {
      // 用户名和密码
      if (!formData.username?.trim()) {
        errors.username = '请输入用户名';
      }
      // Trino 密码可选
      if (selectedDbType !== 'trino' && !formData.password?.trim()) {
        errors.password = '请输入密码';
      }
      // 主机和端口
      if (!formData.host?.trim()) {
        errors.host = '请输入主机地址';
      }
      if (!formData.port) {
        errors.port = '请输入端口号';
      }
      // 数据库名称（Oracle、DM和Trino不需要）
      if (selectedDbType !== 'oracle' && selectedDbType !== 'dm' && selectedDbType !== 'trino' && !formData.database?.trim()) {
        errors.database = '请输入数据库名称';
      }
      // Trino 特有字段
      if (selectedDbType === 'trino') {
        if (!formData.catalog?.trim()) {
          errors.catalog = '请输入Catalog';
        }
        if (!formData.schema?.trim()) {
          errors.schema = '请输入Schema';
        }
      }
      // Oracle 特有字段
      if (selectedDbType === 'oracle') {
        if (connectionMode === 'service_name' && !formData.service_name?.trim()) {
          errors.service_name = '请输入Service Name';
        } else if (connectionMode === 'sid' && !formData.sid?.trim()) {
          errors.sid = '请输入SID';
        }
      }
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleTestConnection = async () => {
    if (!validateForm()) return;

    setIsTesting(true);
    setTestResult(null);
    // 每次点击测试连接时，重置抽取模式为全量抽取
    setExtractMode('full');
    setSelectedTables([]);

    try {
      const res = await testConnection(formData);
      if (res.code === 200) {
        setTestResult({
          success: true,
          message: res.msg || '连接成功！',
          details: res.result
        });
      } else {
        setTestResult({
          success: false,
          message: res.msg || '连接失败，请检查网络或配置'
        });
      }
    } catch (error: any) {
      setTestResult({
        success: false,
        message: error.message || '连接失败，请检查网络或配置'
      });
    } finally {
      setIsTesting(false);
    }
  };

  // 显示错误提示（使用 antd message.error）
  const showErrorTip = (errorMessage: string) => {
    message.error({
      content: errorMessage,
      duration: 3,
    });
  };

  // 获取表列表
  const handleFetchTableList = async () => {
    setIsLoadingTables(true);
    setShowTableSelector(true);

    try {
      const res = await listTables(formData);
      if (res.code === 200 && res.result) {
        setTableList(res.result.tables || []);
      } else {
        message.error(res.msg || '获取表列表失败');
        setShowTableSelector(false);
      }
    } catch (error: any) {
      message.error(error?.message || '获取表列表失败');
      setShowTableSelector(false);
    } finally {
      setIsLoadingTables(false);
    }
  };

  // 处理抽取模式切换
  const handleExtractModeChange = (mode: 'full' | 'select') => {
    setExtractMode(mode);
    if (mode === 'select') {
      // 切换到选择模式时，获取表列表
      handleFetchTableList();
    } else {
      // 切换到全量模式时，清空选择
      setSelectedTables([]);
    }
  };

  // 切换单个表的选中状态
  const handleToggleTable = (tableName: string) => {
    setSelectedTables(prev =>
      prev.includes(tableName)
        ? prev.filter(t => t !== tableName)
        : [...prev, tableName]
    );
  };

  // 全选/取消全选
  const handleSelectAll = (selectAll: boolean) => {
    if (selectAll) {
      setSelectedTables(filteredTables.map(t => t.name));
    } else {
      setSelectedTables([]);
    }
  };

  // 确认选择表
  const handleConfirmTables = () => {
    if (selectedTables.length === 0) {
      message.warning('请至少选择一个表');
      return;
    }
    setShowTableSelector(false);
  };

  const handleSubmit = async () => {
    if (!testResult?.success) {
      alert('请先测试连接成功后再保存');
      return;
    }

    // 清理之前的 AbortController（如果存在）
    if (abortControllerRef.current) {
      abortControllerRef.current = null;
    }

    extractSchemaErrorRef.current = null;
    extractResolvedRef.current = false;
    // 重置取消状态
    savingCancelledRef.current = false;
    apiSuccessRef.current = false;

    // 生成请求ID
    const requestId = `extract_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // 构建提交参数
    const submitData: DataSourceConfig = {
      ...formData,
      ...(extractMode === 'select' && selectedTables.length > 0
        ? { table_names: selectedTables }
        : {})
    };

    const steps = [
      { id: 'connect', name: '连接数据源', description: '正在建立数据库连接...', duration: 1500 },
      { id: 'extract', name: '提取表结构', description: '正在分析并提取数据库表结构...', duration: 8000 },
      { id: 'ai', name: 'AI字段增强', description: '基于大模型进行字段描述填充和增强...', duration: 9000 },
      { id: 'cards', name: '生成数据卡片', description: '正在生成数据卡片...', target: 70, duration: 13000 }
    ];

    // 先设置 savingSteps，再切换 step，确保 UI 不会出现空窗口
    setSavingSteps(steps.map(s => ({ ...s, status: 'pending' as const, progress: 0 })));
    setShowAnimation(true);
    setStep('saving');

    // 用于存储 API 返回结果
    let apiResult: any = null;

    // 模拟进度动画
    const runProgressAnimation = async () => {
      // 前3步：按间隔模拟完成
      for (let i = 0; i < steps.length - 1; i++) {
        // 检查是否已取消或 API 返回错误/成功（成功时前3步应该已完成）
        if (savingCancelledRef.current || (apiResult && apiResult.code !== 200)) {
          setSavingSteps([]); // 立即清空状态
          return; // 退出动画
        }

        setSavingSteps(prev => prev.map((s, idx) =>
          idx === i ? { ...s, status: 'processing', progress: 0 } : s
        ));

        const startTime = Date.now();
        const duration = steps[i].duration;
        const updateInterval = 50;

        while (Date.now() - startTime < duration) {
          // 检查是否已取消或 API 返回错误/成功
          if (savingCancelledRef.current || (apiResult && apiResult.code !== 200)) {
            setSavingSteps([]); // 立即清空状态
            return; // 退出动画
          }
          const elapsed = Date.now() - startTime;
          const progress = Math.min((elapsed / duration) * 100, 99);
          setSavingSteps(prev => prev.map((s, idx) =>
            idx === i ? { ...s, progress } : s
          ));
          await new Promise(resolve => setTimeout(resolve, updateInterval));
        }

        // 检查是否已取消或 API 返回错误/成功
        if (savingCancelledRef.current || (apiResult && apiResult.code !== 200)) {
          setSavingSteps([]); // 立即清空状态
          return; // 退出动画
        }

        setSavingSteps(prev => prev.map((s, idx) =>
          idx === i ? { ...s, status: 'completed', progress: 100 } : s
        ));
      }

      // 第4步：设为进行中，进度到70%后等待接口，API返回后继续到100%
      const lastIndex = steps.length - 1;
      setSavingSteps(prev => prev.map((s, idx) =>
        idx === lastIndex ? { ...s, status: 'processing', progress: 0 } : s
      ));

      const startTime = Date.now();
      const targetTime = steps[lastIndex].duration || 8000;
      const updateInterval = 50;

      while (true) {
        // 检查是否已取消或 API 返回错误（API成功时继续执行到完成）
        if (savingCancelledRef.current || (apiResult && apiResult.code !== 200)) {
          setSavingSteps([]); // 立即清空状态
          return; // 退出动画
        }

        const elapsed = Date.now() - startTime;
        // 如果 API 已成功返回，目标为 100%；否则为 70%
        const targetProgress = apiSuccessRef.current ? 100 : 70;
        const progress = Math.min((elapsed / targetTime) * targetProgress, targetProgress);
        setSavingSteps(prev => prev.map((s, idx) =>
          idx === lastIndex ? { ...s, progress } : s
        ));

        // 如果已完成目标进度且 API 已成功返回，退出循环
        if (apiSuccessRef.current && progress >= 99) {
          // 最后一步设为完成
          setSavingSteps(prev => prev.map((s, idx) =>
            idx === lastIndex ? { ...s, status: 'completed', progress: 100 } : s
          ));
          return; // 退出动画
        }

        await new Promise(resolve => setTimeout(resolve, updateInterval));
      }
    };

    // 快速完成所有进度条动画
    const completeAllSteps = async () => {
      // 将所有 pending 步骤设为 completed，进度为 100%
      setSavingSteps(prev => prev.map((s) => ({
        ...s,
        status: s.status === 'pending' ? 'completed' : s.status,
        progress: 100
      })));
      await new Promise(resolve => setTimeout(resolve, 300));
    };

    // 快速中断动画（仅关闭动画容器）
    const abortAnimation = () => {
      setShowAnimation(false);
    };

    try {
      // 记录开始时间
      const startTime = Date.now();
      console.log('开始保存流程');

      // 先调用 API，设置 AbortController
      const extractPromise = extractSchema(submitData, (abortController) => {
        abortControllerRef.current = abortController;
      }).then(res => {
        apiResult = res;
        // 如果 API 成功，通知动画继续执行到完成
        if (res.code === 200) {
          apiSuccessRef.current = true;
        }
        console.log(`API 返回，耗时: ${Date.now() - startTime}ms, code: ${res.code}`);
        return res;
      }).catch(err => {
        apiResult = { code: 500, msg: err?.message || '请求失败' };
        console.log(`API 错误，耗时: ${Date.now() - startTime}ms, error: ${err?.message}`);
        return apiResult;
      });
      extractPromise.finally(() => {
        extractResolvedRef.current = true;
      });

      // 等待 API 返回或超时（300ms），用于判断是否需要显示动画
      const QUICK_RESPONSE_THRESHOLD = 300;
      const timeoutPromise = new Promise<null>((resolve) => {
        setTimeout(() => {
          console.log(`等待 ${QUICK_RESPONSE_THRESHOLD}ms 后超时`);
          resolve(null);
        }, QUICK_RESPONSE_THRESHOLD);
      });

      const result = await Promise.race([extractPromise, timeoutPromise]);
      console.log(`Promise.race 完成，result:`, result, '耗时:', Date.now() - startTime, 'ms');

      // 如果 result 为 null，说明超时了，需要显示动画
      // 如果 result 有值，说明 API 已经返回
      if (result === null) {
        // API 超时未返回，动画已经通过 savingSteps 初始化显示，现在继续更新进度
        console.log('API 超时，开始显示动画');

        await Promise.all([
          extractPromise,
          runProgressAnimation()
        ]);

        // API返回后，处理结果
        abortControllerRef.current = null;

        if (apiResult?.code === 200) {
          // API 返回成功，动画已经完成，现在关闭并调用成功回调
          setShowAnimation(false);
          setSavingSteps([]);
          onSuccess?.();
          onClose();
        } else if (apiResult?.code === 499) {
          // 操作已取消
          console.log('操作已取消');
          abortAnimation();
          setStep('form');
        } else {
          // API 返回错误，立即关闭动画并显示错误
          console.log('API 返回错误:', apiResult?.msg);
          abortAnimation();
          showErrorTip(apiResult?.msg || '保存失败');
          setStep('form');
        }
      } else {
        // API 在 300ms 内返回
        console.log('API 快速返回，code:', apiResult?.code);
        abortControllerRef.current = null;

        if (apiResult?.code === 200) {
          // 成功：先显示完成动画
          setSavingSteps(steps.map(s => ({ ...s, status: 'completed' as const, progress: 100 })));
          setShowAnimation(true);
          await new Promise(resolve => setTimeout(resolve, 300));
          setShowAnimation(false);
          setSavingSteps([]);
          onSuccess?.();
          onClose();
        } else if (apiResult?.code === 499) {
          // 取消操作：不显示动画
          console.log('操作已取消');
          setStep('form');
        } else {
          // API 返回错误：不显示动画
          console.log('API 返回错误:', apiResult?.msg);
          showErrorTip(apiResult?.msg || '保存失败');
          setStep('form');
        }
      }
    } catch (error: any) {
      abortControllerRef.current = null;
      setShowAnimation(false);
      setSavingSteps([]);

      if (error?.name === 'AbortError') {
        console.log('请求已被取消');
        setStep('form');
        return;
      }
      if (error?.message === 'SavingCancelled') {
        console.log('保存已取消');
        setStep('form');
        return;
      }
      // 其他错误，显示自定义错误提示（显示在弹框内）
      console.log('Catch 块捕获错误:', error);
      showErrorTip(error?.message || '保存失败');
      setStep('form');
    }
  };

  // 取消保存操作
  const handleCancelSaving = () => {
    savingCancelledRef.current = true;
    extractResolvedRef.current = false;
    extractSchemaErrorRef.current = null;

    // 如果正在进行请求，取消正在进行的请求
    if (abortControllerRef.current) {
      console.log('取消正在进行的数据源添加请求');
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    // 重置状态
    setStep('form');
    setSavingSteps([]);
  };

  if (!isOpen) return null;

  const modalContent = (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center p-4"
      style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9999 }}
    >
      <div
        className={`bg-white rounded-[20px] w-full max-h-[90vh] overflow-hidden flex flex-col ${
          step === 'saving' || step === 'testing' ? 'max-w-md' : 'max-w-2xl'
        }`}
      >
        {/* 头部 */}
        <div
          className={`flex items-center justify-between border-b border-slate-100 ${
            step === 'saving' || step === 'testing' ? 'px-5 py-3' : 'px-6 py-4'
          }`}
        >
          <h2
            className={`font-semibold text-slate-900 ${
              step === 'saving' || step === 'testing' ? 'text-base' : 'text-lg'
            }`}
          >
            {step === 'success' ? '添加成功' : '添加数据源'}
          </h2>
          <button
            onClick={() => {
              if (step === 'saving') {
                handleCancelSaving();
              }
              onClose();
            }}
            className="p-2 hover:bg-slate-100 rounded-[10px] transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        {/* 内容区 */}
        <div
          ref={contentRef}
          className={`flex-1 overflow-y-auto ${
            step === 'saving' || step === 'testing' ? 'p-5' : 'p-6'
          }`}
        >
          {step === 'form' && (
            <div className="space-y-5">
              {/* LLM配置提示（仅管理员可见，更紧凑） */}
              {isAdmin && (
                <div className="bg-blue-50/80 border border-blue-100 px-3 py-2 rounded-[10px]">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <Sparkles className="w-4 h-4 text-blue-600 flex-shrink-0" />
                      <p className="text-[12px] leading-relaxed text-slate-700 truncate">
                        <span className="font-semibold text-blue-700">温馨提示：</span>
                        数据卡片的生成需依赖LLM，请先在设置中完成模型配置。
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => router.push(`/${lng}/settings?tab=model`)}
                      className="flex-shrink-0 text-blue-600 hover:text-blue-700 transition-colors"
                      title="前往模型配置"
                    >
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )}

              {/* 数据源名称 */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  数据源名称 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={formData.connect_name}
                  onChange={(e) => handleFormChange('connect_name', e.target.value)}
                  placeholder="请输入数据源名称"
                  className={`w-full px-4 py-2.5 border rounded-[12px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                    validationErrors.connect_name ? 'border-red-500' : 'border-slate-200'
                  }`}
                />
                {validationErrors.connect_name && (
                  <p className="mt-1 text-sm text-red-500">{validationErrors.connect_name}</p>
                )}
              </div>

              {/* 数据库类型选择 */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  数据库类型 <span className="text-red-500">*</span>
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {databaseTypes.map((dbType) => (
                    <button
                      key={dbType.value}
                      onClick={() => handleDbTypeChange(dbType.value as DatabaseType)}
                      className={`px-3 py-2.5 rounded-[12px] border transition-all flex items-center justify-center gap-2 ${
                        selectedDbType === dbType.value
                          ? 'border-indigo-500 bg-indigo-50 text-indigo-700 shadow-sm'
                          : 'border-slate-200 hover:border-indigo-300 hover:bg-slate-50 text-slate-700'
                      }`}
                    >
                      <span className="text-base">{dbType.icon}</span>
                      <span className="text-xs font-medium">{dbType.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* OceanBase 模式提示 */}
              {selectedDbType === 'oceanbase' && (
                <div className="bg-amber-50 border border-amber-200 rounded-[12px] p-3">
                  <div className="flex items-start gap-2">
                    <span className="text-amber-500 text-sm mt-0.5">💡</span>
                    <div className="text-xs text-amber-700 leading-relaxed">
                      <span className="font-medium">说明：</span>系统现阶段仅支持 OceanBase 的 <span className="font-medium text-amber-800">MySQL 租户模式</span>，Oracle 模式将在后续适配。
                    </div>
                  </div>
                </div>
              )}

              {/* 连接方式选择 (SQL Server, Oracle, SQLite) */}
              {(selectedDbType === 'mssql' || selectedDbType === 'oracle' || selectedDbType === 'sqlite') && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    连接方式 <span className="text-red-500">*</span>
                  </label>
                  <div className="flex gap-4">
                    {selectedDbType === 'mssql' && (
                      <>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="radio"
                            name="connectionMode"
                            value="host"
                            checked={connectionMode === 'host'}
                            onChange={(e) => handleConnectionModeChange(e.target.value)}
                            className="text-indigo-600"
                          />
                          <span className="text-sm text-slate-700">主机连接</span>
                        </label>
                      </>
                    )}
                    {selectedDbType === 'oracle' && (
                      <>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="radio"
                            name="connectionMode"
                            value="service_name"
                            checked={connectionMode === 'service_name'}
                            onChange={(e) => handleConnectionModeChange(e.target.value)}
                            className="text-indigo-600"
                          />
                          <span className="text-sm text-slate-700">Service Name</span>
                        </label>
                      </>
                    )}
                    {selectedDbType === 'sqlite' && (
                      <>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="radio"
                            name="connectionMode"
                            value="file"
                            checked={connectionMode === 'file'}
                            onChange={(e) => handleConnectionModeChange(e.target.value)}
                            className="text-indigo-600"
                          />
                          <span className="text-sm text-slate-700">文件路径</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="radio"
                            name="connectionMode"
                            value="memory"
                            checked={connectionMode === 'memory'}
                            onChange={(e) => handleConnectionModeChange(e.target.value)}
                            className="text-indigo-600"
                          />
                          <span className="text-sm text-slate-700">内存模式</span>
                        </label>
                      </>
                    )}
                  </div>
                </div>
              )}

              {/* 动态表单字段 */}
              <div className="space-y-4">
                {/* SQLite 特有字段 */}
                {selectedDbType === 'sqlite' && (
                  <>
                    {connectionMode === 'file' ? (
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">
                          文件路径 <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="text"
                          value={formData.sqlite_path || ''}
                          onChange={(e) => handleFormChange('sqlite_path', e.target.value)}
                          placeholder="/path/to/database.db"
                          className={`w-full px-4 py-2.5 border rounded-[12px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                            validationErrors.sqlite_path ? 'border-red-500' : 'border-slate-200'
                          }`}
                        />
                        {validationErrors.sqlite_path && (
                          <p className="mt-1 text-sm text-red-500">{validationErrors.sqlite_path}</p>
                        )}
                      </div>
                    ) : (
                      <div className="p-4 bg-blue-50 rounded-[12px]">
                        <p className="text-sm text-blue-700">
                          内存模式将创建临时数据库，重启后数据将丢失。
                        </p>
                      </div>
                    )}
                  </>
                )}

                {/* SQL Server DSN 模式 */}
                {selectedDbType === 'mssql' && connectionMode === 'dsn' && (
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      DSN名称 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.dsn || ''}
                      onChange={(e) => handleFormChange('dsn', e.target.value)}
                      placeholder="请输入DSN名称"
                      className={`w-full px-4 py-2.5 border rounded-[12px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                        validationErrors.dsn ? 'border-red-500' : 'border-slate-200'
                      }`}
                    />
                    {validationErrors.dsn && (
                      <p className="mt-1 text-sm text-red-500">{validationErrors.dsn}</p>
                    )}
                  </div>
                )}

                {/* MySQL, PostgreSQL, SQL Server(host), Oracle, Trino, KingBase 的通用字段 */}
                {selectedDbType !== 'sqlite' && !(selectedDbType === 'mssql' && connectionMode === 'dsn') && (
                  <>
                    {/* 用户名和密码 */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">
                          用户名 <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="text"
                          value={formData.username || ''}
                          onChange={(e) => handleFormChange('username', e.target.value)}
                          placeholder="请输入用户名"
                          className={`w-full px-4 py-2.5 border rounded-[12px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                            validationErrors.username ? 'border-red-500' : 'border-slate-200'
                          }`}
                        />
                        {validationErrors.username && (
                          <p className="mt-1 text-sm text-red-500">{validationErrors.username}</p>
                        )}
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">
                          密码 {selectedDbType === 'trino' && <span className="text-xs text-slate-500 font-normal ml-1">(可选)</span>}
                          {selectedDbType !== 'trino' && <span className="text-red-500">*</span>}
                        </label>
                        <div className="relative">
                          <input
                            type={showPassword ? 'text' : 'password'}
                            value={formData.password || ''}
                            onChange={(e) => handleFormChange('password', e.target.value)}
                            placeholder="请输入密码"
                            className={`w-full px-4 py-2.5 pr-10 border rounded-[12px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                              validationErrors.password ? 'border-red-500' : 'border-slate-200'
                            }`}
                          />
                          <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                          >
                            {showPassword ? (
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                              </svg>
                            ) : (
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                              </svg>
                            )}
                          </button>
                        </div>
                        {validationErrors.password && (
                          <p className="mt-1 text-sm text-red-500">{validationErrors.password}</p>
                        )}
                      </div>
                    </div>

                    {/* 主机和端口 */}
                    <div className="grid grid-cols-3 gap-4">
                      <div className="col-span-2">
                        <label className="block text-sm font-medium text-slate-700 mb-2">
                          主机地址 <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="text"
                          value={formData.host || ''}
                          onChange={(e) => handleFormChange('host', e.target.value)}
                          placeholder="localhost"
                          className={`w-full px-4 py-2.5 border rounded-[12px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                            validationErrors.host ? 'border-red-500' : 'border-slate-200'
                          }`}
                        />
                        {validationErrors.host && (
                          <p className="mt-1 text-sm text-red-500">{validationErrors.host}</p>
                        )}
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">
                          端口 <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="number"
                          value={formData.port || ''}
                          onChange={(e) => handleFormChange('port', parseInt(e.target.value) || undefined)}
                          placeholder={getDefaultPort(selectedDbType).toString()}
                          className={`w-full px-4 py-2.5 border rounded-[12px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                            validationErrors.port ? 'border-red-500' : 'border-slate-200'
                          }`}
                        />
                        {validationErrors.port && (
                          <p className="mt-1 text-sm text-red-500">{validationErrors.port}</p>
                        )}
                      </div>
                    </div>

                    {/* 数据库名称 - Oracle、DM和Trino不需要 */}
                    {selectedDbType !== 'oracle' && selectedDbType !== 'dm' && selectedDbType !== 'trino' && (
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">
                          数据库名称 <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="text"
                          value={formData.database || ''}
                          onChange={(e) => handleFormChange('database', e.target.value)}
                          placeholder="请输入数据库名称"
                          className={`w-full px-4 py-2.5 border rounded-[12px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                            validationErrors.database ? 'border-red-500' : 'border-slate-200'
                          }`}
                        />
                        {validationErrors.database && (
                          <p className="mt-1 text-sm text-red-500">{validationErrors.database}</p>
                        )}
                      </div>
                    )}

                    {/* Trino 特有字段 */}
                    {selectedDbType === 'trino' && (
                      <>
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-2">
                            Catalog <span className="text-red-500">*</span>
                          </label>
                          <input
                            type="text"
                            value={formData.catalog || ''}
                            onChange={(e) => handleFormChange('catalog', e.target.value)}
                            placeholder="请输入Catalog名称"
                            className={`w-full px-4 py-2.5 border rounded-[12px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                              validationErrors.catalog ? 'border-red-500' : 'border-slate-200'
                            }`}
                          />
                          {validationErrors.catalog && (
                            <p className="mt-1 text-sm text-red-500">{validationErrors.catalog}</p>
                          )}
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-2">
                            Schema <span className="text-red-500">*</span>
                          </label>
                          <input
                            type="text"
                            value={formData.schema || ''}
                            onChange={(e) => handleFormChange('schema', e.target.value)}
                            placeholder="请输入Schema名称"
                            className={`w-full px-4 py-2.5 border rounded-[12px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                              validationErrors.schema ? 'border-red-500' : 'border-slate-200'
                            }`}
                          />
                          {validationErrors.schema && (
                            <p className="mt-1 text-sm text-red-500">{validationErrors.schema}</p>
                          )}
                        </div>
                      </>
                    )}

                    {/* Oracle 特有字段 */}
                    {selectedDbType === 'oracle' && (
                      <>
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-2">
                            {connectionMode === 'service_name' ? 'Service Name' : 'SID'} <span className="text-red-500">*</span>
                          </label>
                          <input
                            type="text"
                            value={connectionMode === 'service_name' ? (formData.service_name || '') : (formData.sid || '')}
                            onChange={(e) => handleFormChange(
                              connectionMode === 'service_name' ? 'service_name' : 'sid',
                              e.target.value
                            )}
                            placeholder={connectionMode === 'service_name' ? '例如：ORCL' : '例如：ORCL'}
                            className={`w-full px-4 py-2.5 border rounded-[12px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                              (connectionMode === 'service_name' ? validationErrors.service_name : validationErrors.sid) ? 'border-red-500' : 'border-slate-200'
                            }`}
                          />
                          {(connectionMode === 'service_name' ? validationErrors.service_name : validationErrors.sid) && (
                            <p className="mt-1 text-sm text-red-500">
                              {connectionMode === 'service_name' ? validationErrors.service_name : validationErrors.sid}
                            </p>
                          )}
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-2">
                            Schema <span className="text-xs text-slate-500 font-normal ml-1">(可选)</span>
                          </label>
                          <input
                            type="text"
                            value={formData.target_schema || ''}
                            onChange={(e) => handleFormChange('target_schema', e.target.value)}
                            placeholder="默认使用用户名作为Schema"
                            className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                        </div>
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            id="oracle_sysdba"
                            checked={formData.oracle_mode_sysdba || false}
                            onChange={(e) => handleFormChange('oracle_mode_sysdba', e.target.checked)}
                            className="w-4 h-4 text-indigo-600 rounded"
                          />
                          <label htmlFor="oracle_sysdba" className="text-sm text-slate-700">
                            以SYSDBA模式连接
                          </label>
                        </div>
                      </>
                    )}

                    {/* DM(达梦) 特有字段 */}
                    {selectedDbType === 'dm' && (
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">
                          Schema <span className="text-xs text-slate-500 font-normal ml-1">(可选)</span>
                        </label>
                        <input
                          type="text"
                          value={formData.target_schema || ''}
                          onChange={(e) => handleFormChange('target_schema', e.target.value)}
                          placeholder="默认使用用户名大写作为Schema"
                          className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>
                    )}

                    {/* PostgreSQL, SQL Server 和 KingBase 的 Schema (可选) */}
                    {(selectedDbType === 'postgresql' || selectedDbType === 'mssql' || selectedDbType === 'kingbase') && (
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">
                          Schema (可选)
                        </label>
                        <input
                          type="text"
                          value={formData.schema || ''}
                          onChange={(e) => handleFormChange('schema', e.target.value)}
                          placeholder={selectedDbType === 'postgresql' || selectedDbType === 'kingbase' ? '默认public' : '默认dbo'}
                          className="w-full px-4 py-2.5 border border-slate-200 rounded-[12px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* 数据异常值检测开关 - 暂时屏蔽，功能将移至其他模块 */}
              {/* 数据异常值检测开关 - 暂时屏蔽，功能将移至其他模块
              <div
                className={`group relative flex items-center justify-between py-3 px-4 rounded-[12px] border transition-all duration-200 cursor-pointer hover:shadow-sm ${
                  formData.is_audit
                    ? 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-200 hover:border-green-300'
                    : 'bg-white border-slate-300 hover:border-slate-400 hover:bg-slate-50 shadow-sm'
                }`}
                onClick={() => handleFormChange('is_audit', !formData.is_audit)}
              >
                <div className="flex items-center gap-3">
                  <ShieldCheck className={`w-5 h-5 transition-colors duration-200 ${formData.is_audit ? 'text-green-600' : 'text-slate-500'}`} />
                  <div>
                    <span className={`text-sm font-medium transition-colors duration-200 ${
                      formData.is_audit ? 'text-green-700' : 'text-slate-700 group-hover:text-slate-900'
                    }`}>
                      数据异常值检测
                    </span>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {formData.is_audit ? '已开启 - 将对数据进行异常值检测' : '关闭 - 不进行异常值检测'}
                    </p>
                  </div>
                </div>
                <div className={`p-2 rounded-lg transition-all duration-300 ${
                  formData.is_audit
                    ? 'text-green-500'
                    : 'text-slate-400'
                }`}>
                  {formData.is_audit ? (
                    <ToggleRight className="w-8 h-8" />
                  ) : (
                    <ToggleLeft className="w-8 h-8" />
                  )}
                </div>
              </div>
              */}

              {/* 测试连接结果 */}
              {testResult && (
                <div className={`p-4 rounded-[12px] border ${
                  testResult.success
                    ? 'bg-green-50 border-green-200'
                    : 'bg-red-50 border-red-200'
                }`}>
                  <div className="flex items-center gap-2">
                    {testResult.success ? (
                      <CheckCircle className="w-5 h-5 text-green-600" />
                    ) : (
                      <AlertCircle className="w-5 h-5 text-red-600" />
                    )}
                    <span className={testResult.success ? 'text-green-700' : 'text-red-700'}>
                      {testResult.message}
                    </span>
                  </div>
                  {/* 连接成功时显示数据库类型和版本 */}
                  {testResult.success && testResult.details && (
                    <div className="mt-2 pt-2 border-t border-green-200 space-y-0.5">
                      {testResult.details.database_type && (
                        <p className="text-xs text-green-600">
                          数据库类型：{testResult.details.database_type?.toUpperCase() || testResult.details.database_type}
                        </p>
                      )}
                      {testResult.details.database_version && (
                        <p className="text-xs text-green-600">
                          版本信息：{testResult.details.database_version}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* 抽取模式选择 - 仅在测试连接成功后显示 */}
              {testResult?.success && (
                <div className="border border-slate-200 rounded-[12px] p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <ListFilter className="w-4 h-4 text-indigo-600" />
                    <span className="text-sm font-medium text-slate-700">抽取模式</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => handleExtractModeChange('full')}
                      className={`p-3 rounded-[10px] border-2 transition-all text-left ${
                        extractMode === 'full'
                          ? 'border-indigo-500 bg-indigo-50'
                          : 'border-slate-200 hover:border-indigo-300 bg-white'
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <Table2 className={`w-4 h-4 ${extractMode === 'full' ? 'text-indigo-600' : 'text-slate-400'}`} />
                        <span className={`text-sm font-medium ${extractMode === 'full' ? 'text-indigo-700' : 'text-slate-700'}`}>
                          全量抽取
                        </span>
                      </div>
                      <p className={`text-xs ${extractMode === 'full' ? 'text-indigo-600' : 'text-slate-500'}`}>
                        抽取数据源中所有表
                      </p>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleExtractModeChange('select')}
                      className={`p-3 rounded-[10px] border-2 transition-all text-left ${
                        extractMode === 'select'
                          ? 'border-indigo-500 bg-indigo-50'
                          : 'border-slate-200 hover:border-indigo-300 bg-white'
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <ListFilter className={`w-4 h-4 ${extractMode === 'select' ? 'text-indigo-600' : 'text-slate-400'}`} />
                        <span className={`text-sm font-medium ${extractMode === 'select' ? 'text-indigo-700' : 'text-slate-700'}`}>
                          选择特定表
                        </span>
                      </div>
                      <p className={`text-xs ${extractMode === 'select' ? 'text-indigo-600' : 'text-slate-500'}`}>
                        {selectedTables.length > 0 ? `已选择 ${selectedTables.length} 个表` : '选择要抽取的表'}
                      </p>
                    </button>
                  </div>
                  {/* 选择特定表时显示已选表预览 */}
                  {extractMode === 'select' && selectedTables.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-200">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-slate-500">已选择的表：</span>
                        <button
                          type="button"
                          onClick={() => handleFetchTableList()}
                          className="text-xs text-indigo-600 hover:text-indigo-700"
                        >
                          修改选择
                        </button>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {selectedTables.slice(0, 5).map(table => (
                          <span
                            key={table}
                            className="inline-flex items-center px-2 py-0.5 rounded-md bg-indigo-100 text-indigo-700 text-xs"
                            style={{ borderRadius: '6px' }}
                          >
                            {table}
                          </span>
                        ))}
                        {selectedTables.length > 5 && (
                          <span
                            className="inline-flex items-center px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 text-xs"
                            style={{ borderRadius: '6px' }}
                          >
                            +{selectedTables.length - 5} 更多
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* 测试中 / 保存中 - 弹框缩小、内容字号加大以平衡 */}
          {(step === 'testing' || step === 'saving') && (
            <div className="py-2">
              {step === 'testing' && (
                <div className="flex items-center justify-center gap-3 mb-6">
                  <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
                  <span className="text-base text-slate-600">测试连接中...</span>
                </div>
              )}

              {/* 保存中：to-do 列表 + 实时进度条，字号与弹框匹配 */}
              {step === 'saving' && showAnimation && savingSteps.length > 0 && (
                <div className="w-full space-y-4">
                  {/* 顶部标题和状态 */}
                  <div className="flex items-center justify-center gap-3">
                    <div className="relative">
                      <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 4px 14px rgba(99, 102, 241, 0.35)' }}>
                        <Sparkles style={{ width: '18px', height: '18px', color: 'white' }} />
                      </div>
                      <div style={{ position: 'absolute', bottom: '-2px', right: '-2px', width: '12px', height: '12px', borderRadius: '50%', background: '#34d399', border: '2px solid white', animation: 'pulse 2s ease-in-out infinite' }} />
                    </div>
                    <div className="text-center">
                      <p style={{ fontSize: '15px', fontWeight: 600, color: '#334155' }}>正在处理数据源</p>
                      <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>请稍候，可能需要几分钟时间...</p>
                    </div>
                  </div>

                  {/* 进度步骤列表 */}
                  <ul className="space-y-3">
                    {savingSteps.map((item, index) => (
                      <li key={item.id} className="relative">
                        {/* 连接线（除了最后一个） */}
                        {index < savingSteps.length - 1 && (
                          <div style={{ position: 'absolute', left: '15px', top: '32px', width: '2px', height: '20px', background: item.status === 'completed' ? '#34d399' : '#e2e8f0' }} />
                        )}

                        <div className="flex items-start gap-4">
                          {/* 状态图标 */}
                          <div style={{
                            width: '32px',
                            height: '32px',
                            borderRadius: '50%',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                            transition: 'all 0.3s ease',
                            background: item.status === 'completed'
                              ? 'linear-gradient(135deg, #34d399 0%, #10b981 100%)'
                              : item.status === 'processing'
                                ? 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)'
                                : '#f1f5f9',
                            boxShadow: item.status !== 'pending' ? '0 4px 12px rgba(0, 0, 0, 0.15)' : 'none'
                          }}>
                            {item.status === 'completed' ? (
                              <Check style={{ width: '16px', height: '16px', color: 'white' }} strokeWidth={3} />
                            ) : item.status === 'processing' ? (
                              <Loader2 style={{ width: '16px', height: '16px', color: 'white', animation: 'spin 1s linear infinite' }} />
                            ) : (
                              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#94a3b8' }} />
                            )}
                          </div>

                          {/* 文字内容 */}
                          <div style={{ flex: 1, minWidth: 0, paddingTop: '4px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <p style={{
                                fontSize: '14px',
                                fontWeight: 500,
                                color: item.status === 'completed' ? '#059669' : '#334155',
                                transition: 'color 0.3s ease'
                              }}>
                                {item.name}
                              </p>
                              {item.status === 'completed' && (
                                <span style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '9999px', background: '#d1fae5', color: '#059669', fontWeight: 500 }}>
                                  完成
                                </span>
                              )}
                              {item.status === 'processing' && (
                                <span style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '9999px', background: '#e0e7ff', color: '#4f46e5', fontWeight: 500, animation: 'pulse 2s ease-in-out infinite' }}>
                                  进行中
                                </span>
                              )}
                            </div>
                            {item.status === 'processing' && (
                              <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>{item.description}</p>
                            )}
                            {item.status === 'processing' && (
                              <div style={{ marginTop: '8px' }}>
                                <div style={{ height: '6px', background: '#f1f5f9', borderRadius: '9999px', overflow: 'hidden' }}>
                                  <div
                                    style={{
                                      height: '100%',
                                      width: `${item.progress}%`,
                                      borderRadius: '9999px',
                                      background: 'linear-gradient(90deg, #6366f1 0%, #8b5cf6 50%, #ec4899 100%)',
                                      transition: 'width 0.2s ease-out',
                                      position: 'relative',
                                      overflow: 'hidden'
                                    }}
                                  >
                                    <div style={{
                                      position: 'absolute',
                                      right: 0,
                                      top: 0,
                                      bottom: 0,
                                      width: '30px',
                                      background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.5), transparent)',
                                      animation: 'shimmer 1.5s ease-in-out infinite'
                                    }} />
                                  </div>
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '6px' }}>
                                  <span style={{ fontSize: '10px', color: '#cbd5e1' }}>进度</span>
                                  <span style={{ fontSize: '12px', fontWeight: 600, color: '#6366f1', fontVariantNumeric: 'tabular-nums' }}>
                                    {Math.round(item.progress)}%
                                  </span>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>

                  {/* 底部装饰 */}
                  <div style={{ height: '32px', marginTop: '12px', borderTop: '1px solid #f1f5f9', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '6px' }}>
                    <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#818cf8', animation: 'bounce 1.4s ease-in-out infinite', animationDelay: '0ms' }} />
                    <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#a78bfa', animation: 'bounce 1.4s ease-in-out infinite', animationDelay: '0.2s' }} />
                    <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#c4b5fd', animation: 'bounce 1.4s ease-in-out infinite', animationDelay: '0.4s' }} />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 成功：弹框内简洁提示后自动关闭 */}
          {step === 'success' && (
            <div className="flex flex-col items-center justify-center py-10">
              <span className="flex items-center justify-center w-12 h-12 rounded-full border-2 border-indigo-500 bg-indigo-50 mb-4">
                <Check className="w-6 h-6 text-indigo-600" strokeWidth={2.5} />
              </span>
              <p className="text-lg font-semibold text-slate-900">添加成功</p>
              <p className="text-sm text-slate-500 mt-1">数据源已成功添加</p>
            </div>
          )}
        </div>

        {/* 底部按钮 */}
        {step === 'form' && (
          <div className="px-6 py-4 border-t border-slate-100 flex justify-between gap-3">
            <button
              onClick={onClose}
              className="px-6 py-2.5 border border-slate-200 text-slate-700 rounded-[12px] font-medium hover:bg-slate-50 transition-colors"
            >
              取消
            </button>
            <div className="flex gap-2">
              <button
                onClick={handleTestConnection}
                disabled={isTesting}
                className="px-6 py-2.5 border border-indigo-200 text-indigo-600 rounded-[12px] font-medium hover:bg-indigo-50 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {isTesting ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                测试连接
              </button>
              <button
                onClick={handleSubmit}
                disabled={!testResult?.success || (extractMode === 'select' && selectedTables.length === 0)}
                className="px-6 py-2.5 bg-indigo-600 text-white rounded-[12px] font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                title={extractMode === 'select' && selectedTables.length === 0 ? '请先选择要抽取的表' : ''}
              >
                {testResult?.success ? (
                  <>
                    <CheckCircle className="w-4 h-4" />
                    保存
                  </>
                ) : (
                  '请先测试连接'
                )}
              </button>
            </div>
          </div>
        )}

        {step === 'success' && (
          <div className="px-6 py-4 border-t border-slate-100">
            <button
              onClick={onClose}
              className="w-full px-6 py-2.5 bg-indigo-600 text-white rounded-[12px] font-medium hover:bg-indigo-700 transition-colors"
            >
              完成
            </button>
          </div>
        )}

        {/* 保存中 - 取消按钮（只在显示动画时显示） */}
        {step === 'saving' && showAnimation && (
          <div className="px-6 py-4 border-t border-slate-100 flex justify-center">
            <button
              onClick={handleCancelSaving}
              className="px-6 py-2.5 border border-slate-200 text-slate-700 rounded-[12px] font-medium hover:bg-slate-50 transition-colors"
            >
              取消
            </button>
          </div>
        )}
      </div>

      {/* 表选择弹窗 */}
      {showTableSelector && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center p-4"
          style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 10000 }}
        >
          <div className="bg-white rounded-[20px] w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
            {/* 头部 */}
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-slate-900">选择要抽取的表</h3>
                <p className="text-xs text-slate-500 mt-0.5">勾选您需要抽取的表，全量抽取所有表可直接关闭</p>
              </div>
              <button
                onClick={() => setShowTableSelector(false)}
                className="p-2 hover:bg-slate-100 rounded-[10px] transition-colors"
              >
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>

            {/* 搜索和筛选 */}
            <div className="px-6 py-3 border-b border-slate-100 flex items-center gap-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  value={tableSearchKeyword}
                  onChange={(e) => setTableSearchKeyword(e.target.value)}
                  placeholder="搜索表名..."
                  className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-[10px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div className="flex items-center gap-1 bg-slate-100 rounded-[10px] p-1">
                <button
                  onClick={() => setTableTypeFilter('all')}
                  className={`px-3 py-1.5 rounded-[8px] text-xs font-medium transition-colors ${
                    tableTypeFilter === 'all' ? 'bg-white text-slate-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  全部
                </button>
                <button
                  onClick={() => setTableTypeFilter('TABLE')}
                  className={`px-3 py-1.5 rounded-[8px] text-xs font-medium transition-colors flex items-center gap-1 ${
                    tableTypeFilter === 'TABLE' ? 'bg-white text-slate-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <Table2 className="w-3 h-3" />
                  表
                </button>
                <button
                  onClick={() => setTableTypeFilter('VIEW')}
                  className={`px-3 py-1.5 rounded-[8px] text-xs font-medium transition-colors flex items-center gap-1 ${
                    tableTypeFilter === 'VIEW' ? 'bg-white text-slate-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <Eye className="w-3 h-3" />
                  视图
                </button>
              </div>
            </div>

            {/* 表列表 */}
            <div className="flex-1 overflow-y-auto p-4">
              {isLoadingTables ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 animate-spin text-indigo-600 mr-3" />
                  <span className="text-slate-600">正在获取表列表...</span>
                </div>
              ) : filteredTables.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-slate-500">
                  <Table2 className="w-12 h-12 mb-3 text-slate-300" />
                  <p>暂无表数据</p>
                </div>
              ) : (
                <div className="space-y-1">
                  {/* 全选行 */}
                  <div className="flex items-center gap-3 px-3 py-2 bg-slate-50 rounded-[10px] mb-2">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={(e) => handleSelectAll(e.target.checked)}
                      className="w-4 h-4 text-indigo-600 rounded"
                    />
                    <span className="text-sm font-medium text-slate-700">全选</span>
                    <span className="text-xs text-slate-500 ml-auto">
                      已选 {selectedTables.length}/{tableList.length} 项
                    </span>
                  </div>
                  {/* 表列表 */}
                  <div className="max-h-[300px] overflow-y-auto space-y-1">
                    {filteredTables.map((table) => (
                      <div
                        key={table.name}
                        className={`flex items-center gap-3 px-3 py-2.5 rounded-[10px] cursor-pointer transition-colors ${
                          selectedTables.includes(table.name)
                            ? 'bg-indigo-50 border border-indigo-200'
                            : 'hover:bg-slate-50 border border-transparent'
                        }`}
                        onClick={() => handleToggleTable(table.name)}
                      >
                        <input
                          type="checkbox"
                          checked={selectedTables.includes(table.name)}
                          onChange={() => handleToggleTable(table.name)}
                          className="w-4 h-4 text-indigo-600 rounded"
                        />
                        <span className="text-sm text-slate-700 flex-1">{table.name}</span>
                        <span
                          className={`px-2 py-0.5 text-xs font-medium ${
                            table.type === 'TABLE'
                              ? 'bg-blue-100 text-blue-700'
                              : 'bg-purple-100 text-purple-700'
                          }`}
                          style={{ borderRadius: '6px' }}
                        >
                          {table.type === 'TABLE' ? '表' : '视图'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* 底部按钮 */}
            <div className="px-6 py-4 border-t border-slate-100 flex justify-between items-center">
              <div className="text-sm text-slate-500">
                已选择 <span className="font-medium text-indigo-600">{selectedTables.length}</span> 个表
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => setShowTableSelector(false)}
                  className="px-5 py-2 border border-slate-200 text-slate-700 rounded-[10px] font-medium hover:bg-slate-50 transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={handleConfirmTables}
                  disabled={selectedTables.length === 0}
                  className="px-5 py-2 bg-indigo-600 text-white rounded-[10px] font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  确认选择 ({selectedTables.length})
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  return typeof document !== 'undefined'
    ? createPortal(modalContent, document.body)
    : null;
};

// 获取默认端口
function getDefaultPort(dbType: DatabaseType): number {
  const ports: Record<DatabaseType, number> = {
    mysql: 3306,
    postgresql: 5432,
    mssql: 1433,
    oracle: 1521,
    trino: 8080,
    sqlite: 0,
    kingbase: 54321,
    oceanbase: 2881,
    dm: 5236
  };
  return ports[dbType] || 3306;
}

export default AddDataSourceModal;
