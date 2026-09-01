'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Modal, Button, Select, Card, Empty, message, Spin, Table, Tag, Tabs, Upload, Tooltip, Input } from 'antd';
import {
  DatabaseOutlined,
  SearchOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  ArrowLeftOutlined,
  TableOutlined,
  UploadOutlined,
  ReloadOutlined,
  ExclamationCircleOutlined,
  ApartmentOutlined,
  FileTextOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import type { UploadFile } from 'antd/es/upload/interface';
import {
  getTableList,
  runGlobalInventory,
  confirmFieldRecommendations,
  confirmTableRelationships,
  uploadDictFile,
  type TableListItem,
  type RunJobRequest,
  type GlobalInventoryJobResult,
  type FieldRecommendationConfirmation,
  type TableRelationshipConfirmation,
  type DictUploadResponse,
} from '@/api/targetInventory';

interface TargetInventoryModalProps {
  visible: boolean;
  onClose: () => void;
  /** 点击返回箭头时调用，若传入则返回"选择盘点类型"弹框，否则关闭弹框 */
  onBack?: () => void;
  dataSourceId: string;
  dataSourceName: string;
  onExecuteSuccess?: (result: any) => void;
}

const { TabPane } = Tabs;

// 检测是否为深色模式
const useDarkMode = () => {
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const checkDark = () => {
      // 项目使用 data-theme 属性，不是 dark 类名
      const dark = document.documentElement.getAttribute('data-theme') === 'dark';
      setIsDark(dark);
    };

    checkDark();

    // 监听主题变化
    const observer = new MutationObserver(checkDark);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme']
    });

    return () => observer.disconnect();
  }, []);

  return isDark;
};

// 深色模式颜色
const getColors = (isDark: boolean) => isDark ? {
  text: '#f1f5f9',
  textSecondary: '#94a3b8',
  textMuted: '#64748b',
  border: '#334155',
  headerBg: '#1e293b',
  contentBg: '#0f172a',
  cardBg: '#1e293b',
  tableBg: '#1e293b',
  infoBoxBg: 'rgba(59, 130, 246, 0.1)',
  infoBoxBorder: 'rgba(59, 130, 246, 0.3)',
  infoTextColor: '#60a5fa',
  tableBgAlt: '#334155',
  explainBg: '#1e293b',
  explainBorder: '#334155',
  resultBoxBg: 'rgba(22, 163, 74, 0.1)',
  resultBoxBorder: 'rgba(22, 163, 74, 0.3)',
  resultTitleColor: '#16a34a',
  tagBlue: '#3b82f6',
  tagGreen: '#22c55e',
  tagOrange: '#f97316',
  tagRed: '#ef4444',
  tagPurple: '#a855f7',
  tagCyan: '#06b6d4',
  tagGray: '#6b7280',
} : {
  text: '#1e293b',
  textSecondary: '#64748b',
  textMuted: '#94a3b8',
  border: '#e5e7eb',
  headerBg: '#ffffff',
  contentBg: '#ffffff',
  cardBg: '#ffffff',
  tableBg: '#ffffff',
  infoBoxBg: '#f8fafc',
  infoBoxBorder: '#cbd5e1',
  infoTextColor: '#3b82f6',
  tableBgAlt: '#f8fafc',
  explainBg: '#eff6ff',
  explainBorder: '#bfdbfe',
  resultBoxBg: '#f0fdf4',
  resultBoxBorder: '#bbf7d0',
  resultTitleColor: '#166534',
  tagBlue: '#3b82f6',
  tagGreen: '#22c55e',
  tagOrange: '#f97316',
  tagRed: '#ef4444',
  tagPurple: '#a855f7',
  tagCyan: '#06b6d4',
  tagGray: '#6b7280',
};

const styles = {
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '20px 24px',
    borderBottom: '1px solid #e5e7eb',
    background: '#ffffff'
  },
  headerIcon: {
    width: '44px',
    height: '44px',
    borderRadius: '12px',
    background: 'linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0 4px 12px rgba(59, 130, 246, 0.3)'
  },
  headerText: {
    flex: 1
  },
  headerTitle: {
    fontSize: '18px',
    fontWeight: 600,
    color: '#1e293b',
    margin: 0,
    lineHeight: 1.4
  },
  headerSubtitle: {
    fontSize: '14px',
    color: '#64748b',
    marginTop: '2px'
  },
  closeButton: {
    width: '32px',
    height: '32px',
    borderRadius: '8px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    border: 'none',
    background: 'transparent',
    fontSize: '16px',
    color: '#94a3b8'
  },
  content: (isDark: boolean) => ({
    padding: '0',
    maxHeight: '75vh',
    overflowY: 'auto' as const,
    background: isDark ? '#0f172a' : '#ffffff'
  }),
  tableCard: (isDark: boolean) => ({
    marginBottom: '0',
    background: isDark ? '#1e293b' : '#ffffff',
    borderColor: isDark ? '#334155' : '#e5e7eb'
  }),
  card: (isDark: boolean) => ({
    marginBottom: '16px',
    background: isDark ? '#1e293b' : '#ffffff',
    borderColor: isDark ? '#334155' : '#e5e7eb'
  }),
  executeButton: {
    display: 'flex',
    justifyContent: 'center',
    padding: '4px 0 8px'
  },
  resultBox: (isDark: boolean) => ({
    background: isDark ? 'rgba(22, 163, 74, 0.1)' : 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)',
    borderRadius: '12px',
    padding: '20px',
    margin: '0 24px 24px',
    border: `1px solid ${isDark ? 'rgba(22, 163, 74, 0.3)' : '#bbf7d0'}`
  }),
  resultTitle: (isDark: boolean) => ({
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '16px',
    fontSize: '16px',
    fontWeight: 600,
    color: isDark ? '#4ade80' : '#166534'
  }),
  resultGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: '12px'
  },
  resultStat: (isDark: boolean) => ({
    textAlign: 'center' as const,
    padding: '16px 12px',
    background: isDark ? '#334155' : '#ffffff',
    borderRadius: '10px',
    boxShadow: isDark ? '0 1px 3px rgba(0,0,0,0.3)' : '0 1px 3px rgba(0,0,0,0.05)'
  }),
  resultStatValue: (isDark: boolean) => ({
    fontSize: '24px',
    fontWeight: 700,
    marginBottom: '4px',
    color: isDark ? '#f1f5f9' : '#1e293b'
  }),
  resultStatLabel: (isDark: boolean) => ({
    fontSize: '12px',
    color: isDark ? '#94a3b8' : '#6b7280'
  }),
  resultButtonBox: {
    display: 'flex',
    justifyContent: 'center',
    padding: '16px 0'
  }
};

const TargetInventoryModal: React.FC<TargetInventoryModalProps> = ({
  visible,
  onClose,
  onBack,
  dataSourceId,
  dataSourceName,
  onExecuteSuccess
}) => {
  const [executing, setExecuting] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [tableList, setTableList] = useState<TableListItem[]>([]);
  const [loadingTables, setLoadingTables] = useState(false);
  const [targetTables, setTargetTables] = useState<string[]>([]);
  const [refTables, setRefTables] = useState<string[]>([]);
  const [dictFileId, setDictFileId] = useState<string>('');
  const [dictFileList, setDictFileList] = useState<UploadFile[]>([]);
  const [uploadingDict, setUploadingDict] = useState(false);
  const [executeResult, setExecuteResult] = useState<any>(null);
  const [activeTab, setActiveTab] = useState('config');
  const [showTargetDetail, setShowTargetDetail] = useState(false);
  const isDark = useDarkMode();
  // 分页状态 - 目标表和参考表
  const [targetTablePageSize, setTargetTablePageSize] = useState(8);
  const [refTablePageSize, setRefTablePageSize] = useState(8);
  // 搜索状态 - 目标表和参考表
  const [targetTableSearch, setTargetTableSearch] = useState('');
  const [refTableSearch, setRefTableSearch] = useState('');
  // 盘点结果详情：字段推荐与表关系
  const jobResult = executeResult?.result as GlobalInventoryJobResult | undefined;
  const [fieldRecommendations, setFieldRecommendations] = useState<Record<string, Record<string, any>>>({});
  const [tableRelationships, setTableRelationships] = useState<any[]>([]);
  const [fieldConfirmations, setFieldConfirmations] = useState<Record<string, Record<string, FieldRecommendationConfirmation>>>({});
  const [relationConfirmations, setRelationConfirmations] = useState<Record<string, TableRelationshipConfirmation>>({});
  const [resultActiveTab, setResultActiveTab] = useState('field');
  const [loadingRecommendations, setLoadingRecommendations] = useState(false);
  const [submittingField, setSubmittingField] = useState(false);
  const [submittingRelation, setSubmittingRelation] = useState(false);

  useEffect(() => {
    if (visible) {
      setModalVisible(true);
      setTargetTables([]);
      setRefTables([]);
      setDictFileId('');
      setDictFileList([]);
      setExecuteResult(null);
      setActiveTab('config');
      setShowTargetDetail(false);
      setFieldRecommendations({});
      setTableRelationships([]);
      setFieldConfirmations({});
      setRelationConfirmations({});
      setResultActiveTab('field');
      fetchTableList();
    } else {
      setModalVisible(false);
    }
  }, [visible, dataSourceId]);

  const fetchTableList = async () => {
    if (!dataSourceId) return;

    setLoadingTables(true);
    try {
      const response = await getTableList(dataSourceId);
      if (response.code === 200 && response.data) {
        setTableList(response.data || []);
      } else {
        message.error(response.msg || '获取表列表失败');
      }
    } catch (error) {
      console.error('获取表列表失败:', error);
      message.error('获取表列表失败');
    } finally {
      setLoadingTables(false);
    }
  };

  const handleUploadDict = async (file: File) => {
    setUploadingDict(true);
    try {
      const response: DictUploadResponse = await uploadDictFile(file);

      if (response.code === 200 && response.data) {
        setDictFileId(response.data.dict_file_id);
        message.success(`字典文件上传成功，包含 ${response.data.entry_count} 条记录`);
        return true;
      } else {
        message.error(response.message || '上传失败');
        return false;
      }
    } catch (error: any) {
      console.error('上传字典文件失败:', error);
      message.error(error?.message || '上传失败');
      return false;
    } finally {
      setUploadingDict(false);
    }
  };

  const handleExecute = async () => {
    if (targetTables.length === 0) {
      message.warning('请选择至少一个目标表');
      return;
    }
    if (refTables.length === 0) {
      message.warning('请选择至少一个参考表');
      return;
    }

    const hideLoading = message.loading('正在执行定向盘点，可能需要1-5分钟，请耐心等待...', 0);

    try {
      setExecuting(true);

      const params: RunJobRequest = {
        datasource_id: dataSourceId,
        target_tables: targetTables,
        ref_tables: refTables,
        dict_file_id: dictFileId || undefined
      };

      const response = await runGlobalInventory(params);

      if (response.code === 200 && response.data) {
        setExecuteResult(response.data);
        setActiveTab('result');
        message.success('盘点完成！');
        onExecuteSuccess?.(response.data);
      } else {
        message.error(response.msg || '盘点执行失败');
      }
    } catch (error: any) {
      console.error('盘点执行失败:', error);
      message.error(error?.message || '盘点执行失败');
    } finally {
      hideLoading();
      setExecuting(false);
    }
  };

  const handleCancel = () => {
    if (executing) {
      message.warning('盘点执行中，请稍候...');
      return;
    }
    onClose();
  };

  const handleBack = () => {
    if (executing) {
      message.warning('盘点执行中，请稍候...');
      return;
    }
    if (onBack) {
      onBack();
    } else {
      onClose();
    }
  };

  // 从 jobResult 解析字段推荐与表关系，并初始化确认状态
  const parseRecommendationData = (result: GlobalInventoryJobResult) => {
    setLoadingRecommendations(true);
    try {
      if (result.llm_json) {
        setFieldRecommendations(result.llm_json);
        const initialConfirmations: Record<string, Record<string, FieldRecommendationConfirmation>> = {};
        Object.entries(result.llm_json).forEach(([tableName, columns]: [string, any]) => {
          initialConfirmations[tableName] = {};
          Object.entries(columns).forEach(([columnName, data]: [string, any]) => {
            if (data.candidates && data.candidates.length > 0) {
              initialConfirmations[tableName][columnName] = {
                action: 'accept',
                selected_candidate: data.candidates[0]
              };
            }
          });
        });
        setFieldConfirmations(initialConfirmations);
      }
      const resultAny = result as any;
      if (resultAny.table_relationships_json) {
        const relationships = resultAny.table_relationships_json.relationships || [];
        setTableRelationships(relationships);
        const initialRelationConfirmations: Record<string, TableRelationshipConfirmation> = {};
        relationships.forEach((rel: any, idx: number) => {
          const key = `${rel.from_table}.${rel.from_column}-${rel.to_table}.${rel.to_column}-${idx}`;
          initialRelationConfirmations[key] = {
            from_table: rel.from_table,
            from_column: rel.from_column,
            to_table: rel.to_table,
            to_column: rel.to_column,
            relationship_type: rel.relationship_type || 'semantic',
            confidence: rel.confidence || 0,
            action: 'accept'
          };
        });
        setRelationConfirmations(initialRelationConfirmations);
      }
    } catch (error) {
      console.error('解析推荐数据失败:', error);
      message.error('解析推荐数据失败');
    } finally {
      setLoadingRecommendations(false);
    }
  };

  useEffect(() => {
    if (jobResult) {
      parseRecommendationData(jobResult);
    }
  }, [executeResult?.result]);

  const handleFieldConfirmationChange = (tableName: string, columnName: string, confirmation: FieldRecommendationConfirmation) => {
    setFieldConfirmations(prev => ({
      ...prev,
      [tableName]: {
        ...prev[tableName],
        [columnName]: confirmation
      }
    }));
  };

  const handleSubmitFieldConfirmations = async () => {
    const jobId = jobResult?.job_id || executeResult?.job?.id;
    if (!jobId) {
      message.warning('没有可确认的任务');
      return;
    }
    setSubmittingField(true);
    try {
      const response = await confirmFieldRecommendations({
        job_id: jobId,
        confirmations: fieldConfirmations
      });
      if (response.code === 200) {
        const data = response.data as any;
        message.success(`字段注释确认成功，已更新 ${data?.updated_fields ?? data?.confirmed_count ?? 0} 个字段，创建 ${data?.created_mappings ?? 0} 个映射`);
        onExecuteSuccess?.(executeResult);
      } else {
        message.error(response.msg || '确认失败');
      }
    } catch (error: any) {
      console.error('字段确认失败:', error);
      message.error(error?.message || '字段确认失败');
    } finally {
      setSubmittingField(false);
    }
  };

  const handleSubmitRelationConfirmations = async () => {
    const jobId = jobResult?.job_id || executeResult?.job?.id;
    if (!jobId) {
      message.warning('没有可确认的任务');
      return;
    }
    const selectedConfirmations = Object.values(relationConfirmations).filter(r => r.action === 'accept');
    if (selectedConfirmations.length === 0) {
      message.warning('请至少选择一个表关系');
      return;
    }
    setSubmittingRelation(true);
    try {
      const response = await confirmTableRelationships({
        job_id: jobId,
        confirmations: selectedConfirmations
      });
      if (response.code === 200) {
        message.success(`表关系确认成功，已创建 ${response.data?.created_relationships ?? 0} 个关系，${response.data?.created_cards ?? 0} 张卡片`);
        onExecuteSuccess?.(executeResult);
        // 发送刷新事件，通知 TargetInventory 组件刷新历史任务列表
        window.dispatchEvent(new CustomEvent('refresh-target-inventory-history'));
        // 关闭弹框
        onClose();
      } else {
        message.error(response.msg || '确认失败');
      }
    } catch (error: any) {
      console.error('表关系确认失败:', error);
      message.error(error?.message || '表关系确认失败');
    } finally {
      setSubmittingRelation(false);
    }
  };

  // 目标表列定义 - 显示AI填充字段数、缺失注释字段数、质量等级
  const targetTableColumns = [
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>表名</span>,
      dataIndex: 'table_name',
      key: 'table_name',
      width: '45%',
      render: (text: string) => <span style={{ fontWeight: 500, color: isDark ? '#60a5fa' : '#2563eb' }}>{text}</span>
    },
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>AI填充字段数</span>,
      dataIndex: 'auto_filled_count',
      key: 'auto_filled_count',
      width: 100,
      align: 'center' as const,
      render: (count: number) => (
        <Tag style={{ background: isDark ? 'rgba(251, 191, 36, 0.3)' : '#fef3c7', color: isDark ? '#fbbf24' : '#92400e', borderColor: 'transparent' }}>{count || 0}</Tag>
      )
    },
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>缺失注释</span>,
      dataIndex: 'missing_comment_fields',
      key: 'missing_comment_fields',
      width: 80,
      align: 'center' as const,
      render: (count: number) => (
        <Tag style={{ background: count > 0 ? (isDark ? 'rgba(239, 68, 68, 0.3)' : '#fee2e2') : (isDark ? 'rgba(34, 197, 94, 0.2)' : '#dcfce7'), color: count > 0 ? (isDark ? '#f87171' : '#dc2626') : (isDark ? '#4ade80' : '#16a34a'), borderColor: 'transparent' }}>{count}</Tag>
      )
    },
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>质量等级</span>,
      dataIndex: 'quality_level',
      key: 'quality_level',
      width: 80,
      align: 'center' as const,
      render: (level: string) => {
        const colorMap: Record<string, { bg: string; text: string }> = {
          'high': { bg: isDark ? 'rgba(34, 197, 94, 0.2)' : '#dcfce7', text: isDark ? '#4ade80' : '#16a34a' },
          'medium': { bg: isDark ? 'rgba(251, 191, 36, 0.3)' : '#fef3c7', text: isDark ? '#fbbf24' : '#ca8a04' },
          'low': { bg: isDark ? 'rgba(239, 68, 68, 0.2)' : '#fee2e2', text: isDark ? '#f87171' : '#dc2626' }
        };
        const textMap: Record<string, string> = {
          'high': '高',
          'medium': '中',
          'low': '低'
        };
        const style = level ? colorMap[level] || { bg: isDark ? 'rgba(148, 163, 184, 0.2)' : '#f3f4f6', text: isDark ? '#94a3b8' : '#6b7280' } : { bg: isDark ? 'rgba(148, 163, 184, 0.2)' : '#f3f4f6', text: isDark ? '#94a3b8' : '#6b7280' };
        return level ? <Tag style={{ background: style.bg, color: style.text, borderColor: 'transparent' }}>{textMap[level] || level}</Tag> : <Tag style={{ background: style.bg, color: style.text, borderColor: 'transparent' }}>-</Tag>;
      }
    }
  ];

  // 参考表列定义 - 显示缺失注释字段数、质量等级
  const refTableColumns = [
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>表名</span>,
      dataIndex: 'table_name',
      key: 'table_name',
      width: '40%',
      render: (text: string) => <span style={{ fontWeight: 500, color: isDark ? '#60a5fa' : '#2563eb' }}>{text}</span>
    },
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>缺失注释</span>,
      dataIndex: 'missing_comment_fields',
      key: 'missing_comment_fields',
      width: 80,
      align: 'center' as const,
      render: (count: number) => (
        <Tag style={{ background: count > 0 ? (isDark ? 'rgba(239, 68, 68, 0.3)' : '#fee2e2') : (isDark ? 'rgba(34, 197, 94, 0.2)' : '#dcfce7'), color: count > 0 ? (isDark ? '#f87171' : '#dc2626') : (isDark ? '#4ade80' : '#16a34a'), borderColor: 'transparent' }}>{count}</Tag>
      )
    },
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>质量等级</span>,
      dataIndex: 'quality_level',
      key: 'quality_level',
      width: 80,
      align: 'center' as const,
      render: (level: string) => {
        const colorMap: Record<string, { bg: string; text: string }> = {
          'high': { bg: isDark ? 'rgba(34, 197, 94, 0.2)' : '#dcfce7', text: isDark ? '#4ade80' : '#16a34a' },
          'medium': { bg: isDark ? 'rgba(251, 191, 36, 0.3)' : '#fef3c7', text: isDark ? '#fbbf24' : '#ca8a04' },
          'low': { bg: isDark ? 'rgba(239, 68, 68, 0.2)' : '#fee2e2', text: isDark ? '#f87171' : '#dc2626' }
        };
        const textMap: Record<string, string> = {
          'high': '高',
          'medium': '中',
          'low': '低'
        };
        const style = level ? colorMap[level] || { bg: isDark ? 'rgba(148, 163, 184, 0.2)' : '#f3f4f6', text: isDark ? '#94a3b8' : '#6b7280' } : { bg: isDark ? 'rgba(148, 163, 184, 0.2)' : '#f3f4f6', text: isDark ? '#94a3b8' : '#6b7280' };
        return level ? <Tag style={{ background: style.bg, color: style.text, borderColor: 'transparent' }}>{textMap[level] || level}</Tag> : <Tag style={{ background: style.bg, color: style.text, borderColor: 'transparent' }}>-</Tag>;
      }
    }
  ];

  const autoFilledTables = tableList.filter(t => t.is_auto_filled === true);
  const manualTables = tableList.filter(t => !t.is_auto_filled);

  // 过滤后的目标表数据（包含AI填充和手动填充的表）
  const filteredTargetTables = useMemo(() => {
    const combined = [...autoFilledTables, ...manualTables];
    if (!targetTableSearch.trim()) return combined;
    const search = targetTableSearch.toLowerCase();
    return combined.filter(t => t.table_name.toLowerCase().includes(search));
  }, [autoFilledTables, manualTables, targetTableSearch]);

  // 过滤后的参考表数据
  const filteredRefTables = useMemo(() => {
    if (!refTableSearch.trim()) return tableList;
    const search = refTableSearch.toLowerCase();
    return tableList.filter(t => t.table_name.toLowerCase().includes(search));
  }, [tableList, refTableSearch]);

  return (
    <Modal
      open={modalVisible}
      onCancel={handleCancel}
      footer={null}
      width={1280}
      centered
      closable={false}
      styles={{
        body: { padding: '0', background: isDark ? '#1e293b' : '#ffffff' },
        content: { borderRadius: '16px', overflow: 'hidden', background: isDark ? '#1e293b' : '#ffffff' },
        header: { display: 'none' },
        mask: { background: isDark ? 'rgba(0, 0, 0, 0.7)' : 'rgba(0, 0, 0, 0.45)' }
      }}
      maskClosable={!executing}
    >
      {/* Header */}
      <div style={{
        ...styles.header,
        background: 'transparent',
        borderBottom: `1px solid ${isDark ? '#334155' : '#e5e7eb'}`
      }}>
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={handleBack}
          disabled={executing}
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            color: isDark ? '#f1f5f9' : '#64748b'
          }}
        />
        <div style={styles.headerIcon}>
          <TableOutlined style={{ fontSize: '20px', color: '#fff' }} />
        </div>
        <div style={styles.headerText}>
          <h2 style={{ ...styles.headerTitle, color: isDark ? '#f1f5f9' : '#1e293b' }}>定向盘点配置</h2>
          <p style={{ ...styles.headerSubtitle, color: isDark ? '#94a3b8' : '#64748b' }}>针对特定表进行精细化的字段注释推荐和关系发现</p>
        </div>
        <button
          style={{ ...styles.closeButton, color: isDark ? '#64748b' : '#94a3b8' }}
          onClick={handleCancel}
          disabled={executing}
        >
          ✕
        </button>
      </div>

      {/* 数据源：并入标题区下方一行 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '8px 24px 12px',
        borderBottom: `1px solid ${isDark ? '#334155' : '#e5e7eb'}`,
        background: isDark ? '#1e293b' : '#fff'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: isDark ? '#94a3b8' : '#64748b' }}>
          <DatabaseOutlined style={{ color: '#3b82f6' }} />
          <span>数据源：</span>
          <span style={{ color: isDark ? '#60a5fa' : '#1e40af', fontWeight: 500 }}>{dataSourceName}</span>
        </div>
        <Button type="link" size="small" icon={<ReloadOutlined />} onClick={fetchTableList} loading={loadingTables} style={{ padding: 0, height: 'auto', fontSize: '13px' }}>
          刷新表列表
        </Button>
      </div>

      <div style={styles.content(isDark)}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ padding: '0 24px' }}
        >
          <TabPane
            tab={
              <span>
                <SearchOutlined />
                配置盘点
              </span>
            }
            key="config"
          >
            <Spin spinning={loadingTables}>
              {/* 说明与选表建议：合并为一块，点击展开 */}
              <div
                style={{
                  background: isDark ? 'rgba(59, 130, 246, 0.1)' : '#f8fafc',
                  border: `1px dashed ${isDark ? 'rgba(59, 130, 246, 0.5)' : '#cbd5e1'}`,
                  borderRadius: '10px',
                  padding: '12px 16px',
                  margin: '12px 0 16px',
                  cursor: 'pointer'
                }}
                onClick={() => setShowTargetDetail(!showTargetDetail)}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <InfoCircleOutlined style={{ color: isDark ? '#60a5fa' : '#3b82f6', fontSize: '15px' }} />
                    <span style={{ color: isDark ? '#94a3b8' : '#475569', fontSize: '13px' }}>什么是定向盘点？选表有什么建议？</span>
                  </div>
                  <span style={{ color: isDark ? '#60a5fa' : '#3b82f6', fontSize: '12px', transform: showTargetDetail ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>▼</span>
                </div>
              </div>

              {showTargetDetail && (
                <div style={{
                  background: isDark ? 'rgba(59, 130, 246, 0.1)' : '#eff6ff',
                  border: `1px solid ${isDark ? 'rgba(59, 130, 246, 0.3)' : '#bfdbfe'}`,
                  borderRadius: '12px',
                  padding: '16px',
                  marginBottom: '16px'
                }}>
                  <style>{`@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }`}</style>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                    <InfoCircleOutlined style={{ color: isDark ? '#60a5fa' : '#3b82f6', fontSize: '18px', marginTop: '2px' }} />
                    <div style={{ flex: 1 }}>
                      <p style={{ margin: '0 0 10px 0', fontWeight: 500, color: isDark ? '#60a5fa' : '#1e40af', fontSize: '14px' }}>定向盘点说明</p>
                      <ul style={{ margin: 0, paddingLeft: 0, listStyle: 'none', lineHeight: 1.8 }}>
                        {[
                          {
                            dot: '#f97316',
                            title: '适用场景',
                            desc: '当你需要对特定的表进行精细化处理，比如补充缺失的字段注释、建立表之间的关联关系时使用'
                          },
                          {
                            dot: '#22c55e',
                            title: '操作流程',
                            desc: '先选择一个或多个"参考表"（字段注释完整、准确的表），再选择需要补充注释的"目标表"，系统会自动分析并推荐合适的注释'
                          },
                          {
                            dot: '#3b82f6',
                            title: '产出结果',
                            desc: '（1）为目标表的每个字段智能推荐更准确的注释；（2）发现并生成可复用的关系卡片，记录表与表之间的关联'
                          },
                          {
                            dot: '#8b5cf6',
                            title: '使用价值',
                            desc: '有了完整和高质量的字段注释，向AI描述查询需求时能得到更准确的SQL；关系卡片能让AI快速知道哪些表可以 Join、在什么条件下 Join'
                          }
                        ].map((item, idx) => (
                          <li key={idx} style={{ marginBottom: idx < 3 ? '8px' : 0 }}>
                            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                              <span style={{ width: 6, height: 6, borderRadius: '50%', background: item.dot, marginTop: 7, flexShrink: 0 }} />
                              <span style={{ color: isDark ? '#94a3b8' : '#1e3a8a', fontSize: '13px' }}><strong style={{ color: item.dot }}>{item.title}：</strong>{item.desc}</span>
                            </div>
                          </li>
                        ))}
                      </ul>
                      <div style={{ marginTop: '12px', padding: '10px 12px', background: isDark ? 'rgba(251, 191, 36, 0.1)' : '#fffbeb', border: `1px solid ${isDark ? 'rgba(251, 191, 36, 0.3)' : '#fed7aa'}`, borderRadius: '8px' }}>
                        <div style={{ fontSize: '13px', color: isDark ? '#fbbf24' : '#92400e' }}>
                          <strong>选表建议：</strong>优先选择字段注释<strong>完整且准确</strong>的表作为参考表；注释<strong>缺失较多</strong>或质量等级<strong>中低</strong>的表建议作为目标表
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '55% 45%', gap: '16px', marginBottom: '8px' }}>
                {/* 目标表 */}
                <Card
                  title={
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>
                        <ExclamationCircleOutlined style={{ color: '#f97316', marginRight: '8px' }} />
                        目标表（需要推荐注释）
                        <Tooltip title="目标表是指字段注释由AI自动填充的表，这些表的注释需要人工确认和校验。系统将为这些表的字段推荐更准确的注释。">
                          <InfoCircleOutlined style={{ marginLeft: '8px', color: isDark ? '#64748b' : '#9ca3af' }} />
                        </Tooltip>
                      </span>
                      <span style={{ fontSize: '13px', color: isDark ? '#94a3b8' : '#6b7280', fontWeight: 'normal' }}>
                        已选 {targetTables.length} 个
                      </span>
                    </div>
                  }
                  size="small"
                  style={styles.tableCard(isDark)}
                  headStyle={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb' }}
                  bodyStyle={{ background: isDark ? '#1e293b' : '#ffffff', paddingBottom: '8px' }}
                >
                  <style>{`
                    .target-table-pagination .ant-pagination {
                      margin-bottom: 0 !important;
                      padding-bottom: 0 !important;
                    }
                    .target-table-pagination .ant-table-wrapper {
                      padding-bottom: 0 !important;
                    }
                  `}</style>
                  {tableList.length === 0 ? (
                    <Empty description="暂无表数据" />
                  ) : (
                    <div className="target-table-pagination">
                      {/* 目标表搜索框 */}
                      <div style={{ marginBottom: 12 }}>
                        <Input
                          placeholder="搜索目标表..."
                          prefix={<SearchOutlined style={{ color: isDark ? '#64748b' : '#9ca3af' }} />}
                          suffix={
                            targetTableSearch && (
                              <CloseCircleOutlined
                                style={{ color: isDark ? '#64748b' : '#9ca3af', cursor: 'pointer' }}
                                onClick={() => setTargetTableSearch('')}
                              />
                            )
                          }
                          value={targetTableSearch}
                          onChange={(e) => setTargetTableSearch(e.target.value)}
                          allowClear={false}
                          style={{
                            background: isDark ? '#0f172a' : '#f9fafb',
                            borderColor: isDark ? '#334155' : '#e5e7eb',
                          }}
                        />
                        {targetTableSearch && (
                          <div style={{ marginTop: 6, fontSize: 12, color: isDark ? '#94a3b8' : '#6b7280' }}>
                            找到 {filteredTargetTables.length} 个匹配的表
                          </div>
                        )}
                      </div>
                      <Table
                        columns={targetTableColumns}
                        dataSource={filteredTargetTables}
                        rowKey="table_name"
                        size="small"
                        pagination={{
                          pageSize: targetTablePageSize,
                          showSizeChanger: true,
                          pageSizeOptions: ['8', '10', '20', '50'],
                          hideOnSinglePage: true,
                          onShowSizeChange: (_current, size) => setTargetTablePageSize(size),
                          showTotal: (total: number) => `${total} 条/页`,
                          size: 'small'
                        }}
                        rowSelection={{
                          selectedRowKeys: targetTables,
                          onChange: (keys) => setTargetTables(keys as string[])
                        }}
                        scroll={{ y: 220 }}
                        locale={{
                          emptyText: targetTableSearch
                            ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={`未找到包含"${targetTableSearch}"的表`} />
                            : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无表数据" />
                        }}
                      />
                    </div>
                  )}
                </Card>

                {/* 参考表 */}
                <Card
                  title={
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>
                        <CheckCircleOutlined style={{ color: '#22c55e', marginRight: '8px' }} />
                        参考表（提供参考注释）
                        <Tooltip title="参考表是指字段注释完整且经过人工增强的表，无需AI填充。系统将参考这些表的字段注释来为目标表推荐合适的注释。">
                          <InfoCircleOutlined style={{ marginLeft: '8px', color: isDark ? '#64748b' : '#9ca3af' }} />
                        </Tooltip>
                      </span>
                      <span style={{ fontSize: '13px', color: isDark ? '#94a3b8' : '#6b7280', fontWeight: 'normal' }}>
                        已选 {refTables.length} 个
                      </span>
                    </div>
                  }
                  size="small"
                  style={styles.tableCard(isDark)}
                  headStyle={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb' }}
                  bodyStyle={{ background: isDark ? '#1e293b' : '#ffffff', paddingBottom: '8px' }}
                >
                  <style>{`
                    .ref-table-pagination .ant-pagination {
                      margin-bottom: 0 !important;
                      padding-bottom: 0 !important;
                    }
                    .ref-table-pagination .ant-table-wrapper {
                      padding-bottom: 0 !important;
                    }
                  `}</style>
                  {tableList.length === 0 ? (
                    <Empty description="暂无表数据" />
                  ) : (
                    <div className="ref-table-pagination">
                      {/* 参考表搜索框 */}
                      <div style={{ marginBottom: 12 }}>
                        <Input
                          placeholder="搜索参考表..."
                          prefix={<SearchOutlined style={{ color: isDark ? '#64748b' : '#9ca3af' }} />}
                          suffix={
                            refTableSearch && (
                              <CloseCircleOutlined
                                style={{ color: isDark ? '#64748b' : '#9ca3af', cursor: 'pointer' }}
                                onClick={() => setRefTableSearch('')}
                              />
                            )
                          }
                          value={refTableSearch}
                          onChange={(e) => setRefTableSearch(e.target.value)}
                          allowClear={false}
                          style={{
                            background: isDark ? '#0f172a' : '#f9fafb',
                            borderColor: isDark ? '#334155' : '#e5e7eb',
                          }}
                        />
                        {refTableSearch && (
                          <div style={{ marginTop: 6, fontSize: 12, color: isDark ? '#94a3b8' : '#6b7280' }}>
                            找到 {filteredRefTables.length} 个匹配的表
                          </div>
                        )}
                      </div>
                      <Table
                        columns={refTableColumns}
                        dataSource={filteredRefTables}
                        rowKey="table_name"
                        size="small"
                        pagination={{
                          pageSize: refTablePageSize,
                          showSizeChanger: true,
                          pageSizeOptions: ['8', '10', '20', '50'],
                          hideOnSinglePage: true,
                          onShowSizeChange: (_current, size) => setRefTablePageSize(size),
                          showTotal: (total: number) => `${total} 条/页`,
                          size: 'small'
                        }}
                        rowSelection={{
                          selectedRowKeys: refTables,
                          onChange: (keys) => setRefTables(keys as string[]),
                          getCheckboxProps: (record: any) => ({
                            disabled: targetTables.includes(record.table_name),
                            title: targetTables.includes(record.table_name) ? '无法对自身进行盘点与关系发现' : undefined
                          })
                        }}
                        onRow={(record) => ({
                          onMouseEnter: () => {},
                          title: targetTables.includes(record.table_name) ? '无法对自身进行盘点与关系发现' : undefined
                        })}
                        scroll={{ y: 220 }}
                        locale={{
                          emptyText: refTableSearch
                            ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={`未找到包含"${refTableSearch}"的表`} />
                            : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无表数据" />
                        }}
                      />
                    </div>
                  )}
                </Card>
              </div>

                {/* 字典文件上传 */}
                <Card
                  size="small"
                  style={{ ...styles.card(isDark), marginTop: '0' }}
                headStyle={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb' }}
                bodyStyle={{ background: isDark ? '#1e293b' : '#ffffff', padding: '14px 16px' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
                  {/* 左侧：标题和说明 */}
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                      <UploadOutlined style={{ color: '#a855f7', fontSize: '14px' }} />
                      <span style={{ color: isDark ? '#f1f5f9' : '#1e293b', fontSize: '14px', fontWeight: 500 }}>
                        字典文件（可选）
                      </span>
                      <Tooltip title="提供额外的字段注释参考，帮助提升大模型的推断准确性">
                        <InfoCircleOutlined style={{ color: isDark ? '#64748b' : '#9ca3af', fontSize: '14px', cursor: 'pointer' }} />
                      </Tooltip>
                    </div>
                    <div style={{ color: isDark ? '#94a3b8' : '#64748b', fontSize: '12px', lineHeight: 1.5 }}>
                      支持 CSV、Excel 格式，需包含「column_name」和「column_comment」列
                      {dictFileId && (
                        <span style={{ marginLeft: '12px', color: '#22c55e' }}>
                          · 已上传
                        </span>
                      )}
                    </div>
                  </div>

                  {/* 右侧：上传按钮 */}
                  <Upload
                    accept=".csv,.xlsx,.xls"
                    maxCount={1}
                    fileList={dictFileList}
                    beforeUpload={async (file) => {
                      const success = await handleUploadDict(file);
                      if (success) {
                        setDictFileList([{
                          uid: '-1',
                          name: file.name,
                          status: 'done'
                        }]);
                      }
                      return false;
                    }}
                    onRemove={() => {
                      setDictFileList([]);
                      setDictFileId('');
                    }}
                  >
                    <Button icon={<UploadOutlined />} loading={uploadingDict}>
                      {dictFileId ? '重新上传' : '上传字典文件'}
                    </Button>
                  </Upload>
                </div>
              </Card>

              {/* 执行按钮 */}
              <div style={styles.executeButton}>
                <Button
                  type="primary"
                  size="large"
                  icon={<SearchOutlined />}
                  loading={executing}
                  disabled={targetTables.length === 0 || refTables.length === 0}
                  onClick={handleExecute}
                  style={{
                    height: '44px',
                    paddingLeft: '28px',
                    paddingRight: '28px',
                    borderRadius: '8px',
                    background: 'linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)',
                    border: 'none',
                    fontWeight: 500,
                    fontSize: '15px',
                    boxShadow: '0 4px 12px rgba(59, 130, 246, 0.4)'
                  }}
                >
                  {executing ? '盘点中...' : '执行定向盘点'}
                </Button>
              </div>
            </Spin>
          </TabPane>

          <TabPane
            tab={
              <span>
                <ApartmentOutlined />
                盘点结果
                {executeResult && (
                  <Tag color="blue" style={{ marginLeft: '8px' }}>
                    已完成
                  </Tag>
                )}
              </span>
            }
            key="result"
            disabled={!executeResult}
          >
            {executeResult ? (
              <div style={{ padding: '0 24px 24px' }}>
                {/* 结果统计 - 与 /target-inventory 页一致：浅绿底、绿边框、盘点完成 + 字段推荐数/表关系数/任务状态 */}
                <div style={{
                  background: isDark ? 'rgba(22, 163, 74, 0.1)' : '#f0fdf4',
                  border: `1px solid ${isDark ? 'rgba(22, 163, 74, 0.3)' : '#bbf7d0'}`,
                  borderRadius: '8px',
                  padding: '16px',
                  marginBottom: '16px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                    <CheckCircleOutlined style={{ color: isDark ? '#4ade80' : '#16a34a', fontSize: '18px' }} />
                    <span style={{ fontWeight: 500, color: isDark ? '#4ade80' : '#166534' }}>盘点完成</span>
                  </div>
                  <div style={{ display: 'flex', gap: '24px', fontSize: '14px' }}>
                    <div>
                      <span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>字段推荐数：</span>
                      <span style={{ fontWeight: 500, color: isDark ? '#60a5fa' : '#2563eb' }}>
                        {executeResult.result?.field_recommendations_count ?? (jobResult?.llm_json ? Object.values(jobResult.llm_json).reduce((sum, cols) => sum + Object.keys(cols).length, 0) : 0)}
                      </span>
                    </div>
                    <div>
                      <span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>表关系数：</span>
                      <span style={{ fontWeight: 500, color: isDark ? '#c084fc' : '#9333ea' }}>{tableRelationships.length}</span>
                    </div>
                    <div>
                      <span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>任务状态：</span>
                      <Tag color="success">{executeResult?.job?.status || 'completed'}</Tag>
                    </div>
                  </div>
                </div>

                {/* 字段推荐确认 & 表关系确认 */}
                <Spin spinning={loadingRecommendations}>
                  <Tabs activeKey={resultActiveTab} onChange={setResultActiveTab} type="card" style={{ marginTop: 0 }}>
                    <TabPane tab={<span style={{ color: isDark ? '#f1f5f9' : undefined }}><FileTextOutlined /> 字段注释确认</span>} key="field">
                      <div style={{ maxHeight: 420, overflowY: 'auto' }}>
                        {fieldRecommendations && Object.keys(fieldRecommendations).length > 0 ? (
                          <>
                            {Object.entries(fieldRecommendations).map(([tableName, columns]: [string, any]) => {
                              const tableData = Object.entries(columns).map(([colName, data]: [string, any]) => ({
                                key: `${tableName}.${colName}`,
                                table_name: tableName,
                                column_name: colName,
                                original_comment: data.original_comment || '',
                                llm_comment: data.llm_comment || '',
                                candidates: data.candidates || []
                              }));
                              return (
                                <Card
                                  key={tableName}
                                  title={<span style={{ color: isDark ? '#60a5fa' : '#2563eb' }}><TableOutlined style={{ marginRight: 8 }} />{tableName}<span style={{ fontSize: 14, fontWeight: 400, color: isDark ? '#94a3b8' : '#6b7280', marginLeft: 12 }}>共 {tableData.length} 个字段</span></span>}
                                  size="small"
                                  style={{ marginBottom: 16, boxShadow: isDark ? '0 1px 3px rgba(0,0,0,0.3)' : '0 1px 3px rgba(0,0,0,0.05)', background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb' }}
                                  headStyle={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb' }}
                                  bodyStyle={{ background: isDark ? '#1e293b' : '#ffffff' }}
                                >
                                  <Table
                                    dataSource={tableData}
                                    columns={[
                                      { title: '字段名', dataIndex: 'column_name', key: 'column_name', width: 150, render: (t: string) => <span style={{ fontFamily: 'monospace', fontSize: 14, color: isDark ? '#e2e8f0' : '#1f2937', fontWeight: 500 }}>{t}</span> },
                                      { title: '原始注释', dataIndex: 'original_comment', key: 'original_comment', width: 200, render: (t: string) => <div style={{ padding: '4px 0' }}><span style={{ color: isDark ? '#94a3b8' : (t ? '#4b5563' : '#9ca3af'), fontStyle: t ? 'normal' : 'italic', fontSize: 13 }}>{t || '暂无注释'}</span></div> },
                                      {
                                        title: '选择推荐注释',
                                        key: 'recommended',
                                        width: 280,
                                        render: (_: any, record: any) => {
                                          const currentSelection = fieldConfirmations[tableName]?.[record.column_name]?.selected_candidate;
                                          const selectedComment = currentSelection?.column_comment || '';
                                          if (record.candidates.length === 0) return <span style={{ color: isDark ? '#64748b' : '#9ca3af', fontStyle: 'italic', fontSize: 13 }}>无推荐</span>;
                                          return (
                                            <Select
                                              size="middle"
                                              style={{ width: '100%' }}
                                              value={selectedComment}
                                              onChange={(value) => {
                                                const selected = record.candidates.find((c: any) => c.column_comment === value);
                                                if (selected) handleFieldConfirmationChange(tableName, record.column_name, { action: 'accept', selected_candidate: selected });
                                              }}
                                              placeholder="选择推荐注释"
                                              dropdownStyle={{ minWidth: 400 }}
                                              optionLabelProp="label"
                                            >
                                              {record.candidates.map((candidate: any, idx: number) => {
                                                const sourceMap: Record<string, { color: string; text: string }> = { reference_table: { color: 'blue', text: '参考表' }, llm: { color: 'purple', text: 'LLM' }, dictionary: { color: 'green', text: '字典' } };
                                                const sc = sourceMap[candidate.source] || { color: 'default', text: candidate.source || '-' };
                                                return (
                                                  <Select.Option key={idx} value={candidate.column_comment} label={candidate.column_comment}>
                                                    <div style={{ padding: '4px 0' }}><div style={{ fontWeight: 500, color: isDark ? '#f1f5f9' : '#1f2937' }}>{candidate.column_comment}</div><div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4, fontSize: 12, color: isDark ? '#94a3b8' : '#6b7280' }}><span>来源: <Tag color={sc.color}>{sc.text}</Tag></span><span>置信度: <Tag color={candidate.confidence >= 0.8 ? 'green' : candidate.confidence >= 0.5 ? 'orange' : 'red'}>{(candidate.confidence * 100).toFixed(0)}%</Tag></span></div></div>
                                                  </Select.Option>
                                                );
                                              })}
                                            </Select>
                                          );
                                        }
                                      },
                                      { title: '来源', key: 'source', width: 100, align: 'center' as const, render: (_: any, record: any) => { const s = fieldConfirmations[tableName]?.[record.column_name]?.selected_candidate?.source || ''; const colorMap: Record<string, string> = { reference_table: 'blue', llm: 'purple', dictionary: 'green' }; const textMap: Record<string, string> = { reference_table: '参考表', llm: 'LLM', dictionary: '字典' }; return s ? <Tag color={colorMap[s] || 'default'}>{textMap[s] || s}</Tag> : <span style={{ color: isDark ? '#64748b' : '#9ca3af' }}>-</span>; } },
                                      { title: '置信度', key: 'confidence', width: 90, align: 'center' as const, render: (_: any, record: any) => { const c = fieldConfirmations[tableName]?.[record.column_name]?.selected_candidate?.confidence; if (c == null) return <span style={{ color: isDark ? '#64748b' : '#9ca3af' }}>-</span>; return <Tag color={c >= 0.8 ? 'green' : c >= 0.5 ? 'orange' : 'red'}>{(c * 100).toFixed(0)}%</Tag>; } },
                                      { title: '推荐原因', key: 'reasoning', width: 180, render: (_: any, record: any) => { const reasoning = fieldConfirmations[tableName]?.[record.column_name]?.selected_candidate?.reasoning || ''; return reasoning ? <Tooltip title={reasoning} placement="topLeft"><div style={{ fontSize: 12, color: isDark ? '#94a3b8' : '#6b7280', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as any, overflow: 'hidden' }}>{reasoning}</div></Tooltip> : <span style={{ color: isDark ? '#64748b' : '#9ca3af' }}>-</span>; } }
                                    ]}
                                    pagination={false}
                                    size="middle"
                                    scroll={{ x: true }}
                                  />
                                </Card>
                              );
                            })}
                            <div style={{ display: 'flex', justifyContent: 'center', gap: 16, padding: '8px 0 16px' }}>
                              <Button type="primary" size="large" icon={<CheckCircleOutlined />} loading={submittingField} onClick={handleSubmitFieldConfirmations}>确认字段注释</Button>
                            </div>
                          </>
                        ) : (
                          <Empty description="暂无字段推荐数据" />
                        )}
                      </div>
                    </TabPane>
                    <TabPane tab={<span style={{ color: isDark ? '#f1f5f9' : undefined }}><ApartmentOutlined /> 表关系确认</span>} key="relation">
                      <div style={{ maxHeight: 420, overflowY: 'auto' }}>
                        {tableRelationships.length > 0 ? (
                          <>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: isDark ? '#1e293b' : '#f9fafb', borderRadius: '8px', padding: '8px 16px', marginBottom: 12 }}>
                              <span style={{ color: isDark ? '#94a3b8' : '#4b5563' }}>已选择 <span style={{ color: isDark ? '#60a5fa' : '#2563eb', fontWeight: 500 }}>{Object.values(relationConfirmations).filter(r => r.action === 'accept').length}</span> / {tableRelationships.length} 个关系</span>
                              <div style={{ display: 'flex', gap: 8 }}>
                                <Button size="small" onClick={() => { const next: Record<string, TableRelationshipConfirmation> = {}; tableRelationships.forEach((rel: any, idx: number) => { const key = `${rel.from_table}.${rel.from_column}-${rel.to_table}.${rel.to_column}-${idx}`; next[key] = { from_table: rel.from_table, from_column: rel.from_column, to_table: rel.to_table, to_column: rel.to_column, relationship_type: rel.relationship_type || 'semantic', confidence: rel.confidence || 0, action: 'accept' }; }); setRelationConfirmations(next); }}>全选</Button>
                                <Button size="small" onClick={() => { const next: Record<string, TableRelationshipConfirmation> = {}; tableRelationships.forEach((rel: any, idx: number) => { const key = `${rel.from_table}.${rel.from_column}-${rel.to_table}.${rel.to_column}-${idx}`; next[key] = { from_table: rel.from_table, from_column: rel.from_column, to_table: rel.to_table, to_column: rel.to_column, relationship_type: rel.relationship_type || 'semantic', confidence: rel.confidence || 0, action: 'reject' }; }); setRelationConfirmations(next); }}>取消全选</Button>
                              </div>
                            </div>
                            <Card size="small" style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
                              <Table
                                dataSource={tableRelationships.map((rel: any, idx: number) => ({ key: `${rel.from_table}.${rel.from_column}-${rel.to_table}.${rel.to_column}-${idx}`, ...rel }))}
                                rowSelection={{
                                  selectedRowKeys: Object.entries(relationConfirmations).filter(([, v]) => v.action === 'accept').map(([k]) => k),
                                  onChange: (selectedKeys) => {
                                    const next: Record<string, TableRelationshipConfirmation> = {};
                                    tableRelationships.forEach((rel: any, idx: number) => {
                                      const key = `${rel.from_table}.${rel.from_column}-${rel.to_table}.${rel.to_column}-${idx}`;
                                      next[key] = { from_table: rel.from_table, from_column: rel.from_column, to_table: rel.to_table, to_column: rel.to_column, relationship_type: rel.relationship_type || 'semantic', confidence: rel.confidence || 0, action: selectedKeys.includes(key) ? 'accept' : 'reject' };
                                    });
                                    setRelationConfirmations(next);
                                  }
                                }}
                                columns={[
                                  { title: '源表', key: 'from_table', width: 140, render: (_: any, r: any) => <span style={{ color: isDark ? '#60a5fa' : '#2563eb', fontWeight: 500 }}>{r.from_table}</span> },
                                  { title: '源字段', key: 'from_column', width: 130, render: (_: any, r: any) => <span style={{ fontFamily: 'monospace', fontSize: 14, background: isDark ? '#334155' : '#f3f4f6', padding: '2px 8px', borderRadius: 4 }}>{r.from_column}</span> },
                                  { title: '', key: 'arrow', width: 60, align: 'center' as const, render: () => <span style={{ color: isDark ? '#38bdf8' : '#60a5fa', fontSize: 20, fontWeight: 700 }}>→</span> },
                                  { title: '目标表', key: 'to_table', width: 140, render: (_: any, r: any) => <span style={{ color: isDark ? '#4ade80' : '#16a34a', fontWeight: 500 }}>{r.to_table}</span> },
                                  { title: '目标字段', key: 'to_column', width: 130, render: (_: any, r: any) => <span style={{ fontFamily: 'monospace', fontSize: 14, background: isDark ? '#334155' : '#f3f4f6', padding: '2px 8px', borderRadius: 4 }}>{r.to_column}</span> },
                                  { title: '关系类型', dataIndex: 'relationship_type', key: 'relationship_type', width: 100, align: 'center' as const, render: (t: string) => { const colorM: Record<string, string> = { foreign_key: 'blue', semantic: 'purple', name_based: 'cyan', synonym: 'orange', value_overlap: 'default', shared_field: 'orange' }; const textM: Record<string, string> = { foreign_key: '外键', semantic: '语义', name_based: '命名', synonym: '同义', value_overlap: '值域重叠', shared_field: '字段共享' }; return <Tag color={colorM[t] || 'default'}>{textM[t] || t || '未知'}</Tag>; } },
                                  { title: '基数', dataIndex: 'cardinality', key: 'cardinality', width: 90, align: 'center' as const, render: (text: string) => text ? <Tag color="geekblue">{text}</Tag> : <span style={{ color: isDark ? '#64748b' : '#9ca3af' }}>-</span> },
                                  { title: '置信度', dataIndex: 'confidence', key: 'confidence', width: 90, align: 'center' as const, render: (c: number) => <Tag color={(c || 0) >= 0.8 ? 'green' : (c || 0) >= 0.5 ? 'orange' : 'red'}>{((c || 0) * 100).toFixed(0)}%</Tag> },
                                  { title: '推荐原因', dataIndex: 'reasoning', key: 'reasoning', width: 180, render: (text: string) => <Tooltip title={text || '-'} placement="topLeft"><div style={{ fontSize: 12, color: isDark ? '#94a3b8' : '#6b7280', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as any, overflow: 'hidden' }}>{text || '-'}</div></Tooltip> }
                                ]}
                                pagination={{ pageSize: 10, hideOnSinglePage: true, showTotal: (total: number) => `共 ${total} 条关系` }}
                                size="middle"
                                scroll={{ x: true }}
                              />
                            </Card>
                            <div style={{ display: 'flex', justifyContent: 'center', padding: '8px 0 16px' }}>
                              <Button type="primary" size="large" icon={<CheckCircleOutlined />} loading={submittingRelation} onClick={handleSubmitRelationConfirmations}>确认表关系</Button>
                            </div>
                          </>
                        ) : (
                          <div style={{ minHeight: 420 }} className="flex items-center justify-center"><Empty description="暂无表关系数据" style={{ color: isDark ? '#94a3b8' : '#6b7280' }} /></div>
                        )}
                      </div>
                    </TabPane>
                  </Tabs>
                </Spin>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '48px', color: '#9ca3af' }}>
                <Empty description="暂无盘点结果，请先执行盘点任务" />
              </div>
            )}
          </TabPane>
        </Tabs>
      </div>
    </Modal>
  );
};

export default TargetInventoryModal;
