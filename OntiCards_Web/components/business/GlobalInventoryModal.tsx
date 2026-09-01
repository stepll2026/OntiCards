'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Modal, Button, Select, Input, Card, Empty, message, Spin, Checkbox, Tag } from 'antd';
import {
  DatabaseOutlined,
  SearchOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons';
import { getUserDataSources } from '@/api/datasource';
import type { DataSourceItem } from '@/api/datasource';
import { discoverRelationships } from '@/api/globalInventory';
import GlobalInventoryResultModal, { type DiscoverResultForModal } from './GlobalInventoryResultModal';

interface GlobalInventoryModalProps {
  visible: boolean;
  onClose: () => void;
  /** 点击返回箭头时调用，若传入则返回“选择盘点类型”弹框，否则关闭弹框 */
  onBack?: () => void;
  defaultDataSourceId: string;
  defaultDataSourceName: string;
  onExecuteSuccess?: (result: any) => void;
}

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
    background: 'linear-gradient(135deg, #a855f7 0%, #ec4899 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0 4px 12px rgba(168, 85, 247, 0.3)'
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
  content: {
    padding: '16px 24px',
    overflow: 'hidden'
  },
  descriptionSection: {
    marginBottom: '12px'
  },
  dataSourceSection: {
    flex: 1,
    minHeight: 0,
    display: 'flex',
    flexDirection: 'column' as const,
    overflow: 'hidden'
  },
  infoBox: {
    background: 'linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%)',
    borderRadius: '12px',
    padding: '16px',
    marginBottom: '20px',
    border: '1px solid #e9d5ff'
  },
  infoContent: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '12px'
  },
  infoText: {
    fontSize: '14px',
    color: '#6b21a8',
    lineHeight: 1.6
  },
  sourceLabel: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '12px',
    fontSize: '14px',
    fontWeight: 500,
    color: '#374151'
  },
  sourceCount: {
    fontSize: '13px',
    color: '#9333ea',
    fontWeight: 500
  },
  sourceCard: {
    padding: '12px 14px',
    borderRadius: '10px',
    border: '2px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    marginBottom: '8px'
  },
  sourceCardSelected: {
    border: '2px solid #a855f7',
    background: 'linear-gradient(135deg, #faf5ff 0%, #fdf4ff 100%)'
  },
  sourceCardNormal: {
    border: '2px solid #e5e7eb',
    background: '#ffffff'
  },
  sourceCardDisabled: {
    border: '2px solid #f3f4f6',
    background: '#f9fafb',
    cursor: 'not-allowed'
  },
  sourceName: {
    fontWeight: 500,
    color: '#1f2937'
  },
  sourceDb: {
    fontSize: '12px',
    color: '#9ca3af'
  },
  configRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '24px',
    paddingTop: '16px',
    borderTop: '1px solid #f0f0f0',
    marginTop: '16px'
  },
  configLabel: {
    fontSize: '13px',
    color: '#6b7280'
  },
  executeButton: {
    display: 'flex',
    justifyContent: 'center',
    padding: '8px 0 4px'
  },
  resultBox: {
    background: 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)',
    borderRadius: '12px',
    padding: '20px',
    marginTop: '16px',
    border: '1px solid #bbf7d0'
  },
  resultTitle: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '16px',
    fontSize: '16px',
    fontWeight: 600,
    color: '#166534'
  },
  resultGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '12px',
    marginBottom: '16px'
  },
  resultStat: {
    textAlign: 'center' as const,
    padding: '16px 12px',
    background: '#ffffff',
    borderRadius: '10px',
    boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
  },
  resultStatValue: {
    fontSize: '24px',
    fontWeight: 700,
    marginBottom: '4px'
  },
  resultStatLabel: {
    fontSize: '12px',
    color: '#6b7280'
  },
  crossSource: {
    paddingTop: '12px',
    borderTop: '1px solid #bbf7d0',
    fontSize: '13px',
    color: '#15803d'
  },
  resultButtonBox: {
    display: 'flex',
    justifyContent: 'center',
    padding: '16px 0'
  }
};

// 深色模式颜色
const getColors = (isDark: boolean) => isDark ? {
  text: '#f1f5f9',
  textSecondary: '#94a3b8',
  textMuted: '#64748b',
  border: '#334155',
  cardBg: '#1e293b',
  cardHoverBg: '#334155',
  infoBg: 'rgba(168, 85, 247, 0.1)',
  infoBorder: 'rgba(168, 85, 247, 0.3)',
  headerBg: '#1e293b',
  contentBg: '#0f172a',
} : {
  text: '#1e293b',
  textSecondary: '#64748b',
  textMuted: '#94a3b8',
  border: '#e2e8f0',
  cardBg: '#ffffff',
  cardHoverBg: '#ffffff',
  infoBg: 'linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%)',
  infoBorder: '#e9d5ff',
  headerBg: '#ffffff',
  contentBg: '#ffffff',
};

const GlobalInventoryModal: React.FC<GlobalInventoryModalProps> = ({
  visible,
  onClose,
  onBack,
  defaultDataSourceId,
  defaultDataSourceName,
  onExecuteSuccess
}) => {
  const [loading, setLoading] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [dataSources, setDataSources] = useState<DataSourceItem[]>([]);
  const [selectedDataSources, setSelectedDataSources] = useState<string[]>([defaultDataSourceId]);
  const [schemaName, setSchemaName] = useState<string>('');
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.5);
  const [modalVisible, setModalVisible] = useState(false);
  const [showGlobalDetail, setShowGlobalDetail] = useState(false);
  const [resultModalVisible, setResultModalVisible] = useState(false);
  const [discoverResult, setDiscoverResult] = useState<DiscoverResultForModal | null>(null);
  const isDark = useDarkMode();

  useEffect(() => {
    if (visible) {
      setModalVisible(true);
      setSelectedDataSources([defaultDataSourceId]);
      fetchDataSources();
      setDiscoverResult(null);
      setResultModalVisible(false);
      setSchemaName('');
      setConfidenceThreshold(0.5);
      setShowGlobalDetail(false);
    } else {
      setModalVisible(false);
      setResultModalVisible(false);
    }
  }, [visible, defaultDataSourceId]);

  const fetchDataSources = async () => {
    try {
      setLoading(true);
      const response = await getUserDataSources({ page: 1, page_size: 100 });
      if (response.code === 200 && response.data) {
        setDataSources(response.data.items || []);
      } else {
        message.error('获取数据源列表失败');
      }
    } catch (error) {
      console.error('获取数据源列表失败:', error);
      message.error('获取数据源列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectDataSource = (dsId: string) => {
    setSelectedDataSources(prev => {
      if (prev.includes(dsId)) {
        if (dsId === defaultDataSourceId) {
          message.warning('当前数据源为必选');
          return prev;
        }
        return prev.filter(id => id !== dsId);
      } else {
        return [...prev, dsId];
      }
    });
  };

  const handleDiscoverRelationships = async () => {
    if (selectedDataSources.length === 0) {
      message.warning('请先选择要发现关系的数据源');
      return;
    }

    const isMultiSource = selectedDataSources.length > 1;
    const hideLoading = message.loading(
      isMultiSource
        ? `正在分析 ${selectedDataSources.length} 个数据源的表关系，可能需要较长时间，请耐心等待...`
        : '正在分析表间关系，可能需要较长时间，请稍后...',
      0
    );

    try {
      setDiscovering(true);
      const response = await discoverRelationships({
        datasource_ids: selectedDataSources,
        schema_name: schemaName || undefined,
        confidence_threshold: confidenceThreshold
      });

      if (response.code === 200 && response.data?.success) {
        const stats = (response.data as any).statistics;
        const tablePairs = stats?.total_table_pairs ?? response.data.relationships_count;
        const crossSourcePairs = stats?.cross_source_table_pairs ?? 0;
        const intraSourceCount = stats?.intra_source_count ?? Math.max(0, tablePairs - crossSourcePairs);

        setDiscoverResult({
          tables_count: response.data.tables_count,
          relationships_count: stats?.total_relationships ?? response.data.relationships_count,
          total_table_pairs: tablePairs,
          cards_count: response.data.cards_count,
          cross_source_table_pairs: crossSourcePairs,
          intra_source_count: intraSourceCount,
          datasource_ids: response.data.datasource_ids || selectedDataSources,
          statistics: stats ? { avg_confidence: stats.avg_confidence } : undefined,
        });

        setResultModalVisible(true);
        const crossSourceInfo = crossSourcePairs > 0 ? `，其中跨源关系 ${crossSourcePairs} 个` : '';
        message.success(`关系发现完成！发现 ${tablePairs} 个表关系${crossSourceInfo}`);
        onExecuteSuccess?.(response.data);
      } else {
        message.error(response.msg || '关系发现失败');
      }
    } catch (error: any) {
      console.error('关系发现失败:', error);
      message.error(error?.message || '关系发现失败，请稍后重试');
    } finally {
      hideLoading();
      setDiscovering(false);
    }
  };

  const handleCancel = () => {
    if (discovering) {
      message.warning('关系发现执行中，请稍候...');
      return;
    }
    onClose();
  };

  const handleBack = () => {
    if (discovering) {
      message.warning('关系发现执行中，请稍候...');
      return;
    }
    if (onBack) {
      onBack();
    } else {
      onClose();
    }
  };

  const availableDataSources = useMemo(() => {
    const filtered = dataSources.filter(ds => ds.status === 'available');
    if (!defaultDataSourceId) return filtered;

    // 将当前数据源排在第一位
    const defaultDs = filtered.find(ds => ds.id === defaultDataSourceId);
    if (!defaultDs) return filtered;

    const others = filtered.filter(ds => ds.id !== defaultDataSourceId);
    return [defaultDs, ...others];
  }, [dataSources, defaultDataSourceId]);

  const getSourceCardStyle = (dsId: string, isSelected: boolean, isDefault: boolean) => {
    if (isDefault) {
      return {
        ...styles.sourceCard,
        border: `2px solid ${isDark ? '#475569' : '#f3f4f6'}`,
        background: isDark ? '#1e293b' : '#f9fafb',
        cursor: 'not-allowed'
      };
    }
    return {
      ...styles.sourceCard,
      border: `2px solid ${isSelected ? '#a855f7' : (isDark ? '#475569' : '#e5e7eb')}`,
      background: isSelected
        ? (isDark ? 'rgba(168, 85, 247, 0.15)' : 'linear-gradient(135deg, #faf5ff 0%, #fdf4ff 100%)')
        : (isDark ? '#1e293b' : '#ffffff'),
    };
  };

  return (
    <Modal
      open={modalVisible}
      onCancel={handleCancel}
      footer={null}
      width={1000}
      centered
      closable={false}
      styles={{
        body: { padding: '0', background: isDark ? '#1e293b' : '#ffffff', overflow: 'hidden', display: 'flex', flexDirection: 'column' as const },
        content: { borderRadius: '16px', overflow: 'hidden', background: isDark ? '#1e293b' : '#ffffff', display: 'flex', flexDirection: 'column' as const, maxHeight: 'calc(100vh - 80px)' },
        header: { display: 'none' },
        mask: { background: isDark ? 'rgba(0, 0, 0, 0.7)' : 'rgba(0, 0, 0, 0.45)' }
      }}
      maskClosable={!discovering}
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
          disabled={discovering}
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            color: isDark ? '#f1f5f9' : '#64748b'
          }}
        />
        <div style={styles.headerIcon}>
          <SearchOutlined style={{ fontSize: '20px', color: '#fff' }} />
        </div>
        <div style={styles.headerText}>
          <h2 style={{ ...styles.headerTitle, color: isDark ? '#f1f5f9' : '#1e293b' }}>全域盘点配置</h2>
          <p style={{ ...styles.headerSubtitle, color: isDark ? '#94a3b8' : '#64748b' }}>自动发现表之间的关联关系</p>
        </div>
        <button
          style={{ ...styles.closeButton, color: isDark ? '#64748b' : '#94a3b8' }}
          onClick={handleCancel}
          disabled={discovering}
        >
          ✕
        </button>
      </div>

      <div style={{
        ...styles.content,
        background: isDark ? '#0f172a' : '#ffffff',
        display: 'flex',
        flexDirection: 'column' as const,
        height: '100%',
        maxHeight: 'calc(100vh - 120px)',
        overflow: 'hidden'
      }}>
        {/* 说明区域 */}
        <div style={styles.descriptionSection}>
          {/* 说明入口：单行紧凑 */}
          <div
            style={{
              background: isDark ? 'rgba(168, 85, 247, 0.1)' : '#f8fafc',
              border: `1px dashed ${isDark ? 'rgba(168, 85, 247, 0.5)' : '#cbd5e1'}`,
              borderRadius: '10px',
              padding: '12px 16px',
              cursor: 'pointer',
              marginBottom: showGlobalDetail ? '0' : '12px'
            }}
            onClick={() => setShowGlobalDetail(!showGlobalDetail)}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <InfoCircleOutlined style={{ color: isDark ? '#c084fc' : '#9333ea', fontSize: '15px' }} />
                <span style={{ color: isDark ? '#94a3b8' : '#475569', fontSize: '13px' }}>什么是全域盘点？有什么作用？</span>
              </div>
              <span style={{ color: isDark ? '#c084fc' : '#9333ea', fontSize: '12px', transform: showGlobalDetail ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>▼</span>
            </div>
          </div>

          {/* 详细说明 - 折叠显示 */}
          {showGlobalDetail && (
            <div style={{
              background: isDark ? 'rgba(168, 85, 247, 0.1)' : 'linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%)',
              border: `1px solid ${isDark ? 'rgba(168, 85, 247, 0.3)' : '#e9d5ff'}`,
              borderRadius: '12px',
              padding: '16px',
              marginTop: '12px'
            }}>
              <div style={styles.infoContent}>
                <InfoCircleOutlined style={{ fontSize: '18px', color: isDark ? '#c084fc' : '#9333ea', marginTop: '2px' }} />
                <div style={{ ...styles.infoText, paddingLeft: 0, flex: 1 }}>
                  <p style={{ margin: '0 0 10px 0', fontWeight: 500, fontSize: '14px', color: isDark ? '#c084fc' : '#6b21a8' }}>全域盘点说明</p>
                  <ul style={{ margin: 0, paddingLeft: 0, listStyle: 'none', lineHeight: 1.8 }}>
                    {[
                      {
                        dot: '#9333ea',
                        title: '适用场景',
                        desc: '当你需要对整个数据环境进行全面普查，想了解所有表之间的关联关系、发现潜在的数据价值时使用'
                      },
                      {
                        dot: '#ea580c',
                        title: '操作流程',
                        desc: '选择需要盘点的一个或多个数据源，设置好置信度阈值（决定发现关系的严格程度），点击开始即可全自动扫描'
                      },
                      {
                        dot: '#16a34a',
                        title: '产出结果',
                        desc: '生成完整的表关系图谱，清晰展示哪些表有关联、在什么字段上关联、关联的置信度有多高；同时生成可直接使用的关系卡片'
                      },
                      {
                        dot: '#2563eb',
                        title: '使用价值',
                        desc: '适合做复杂报表或多表关联查询时使用，快速找到表间的JOIN路径；支持跨不同类型数据库和数据源发现关联，增强异构数据融合'
                      }
                    ].map((item, idx) => (
                      <li key={idx} style={{ marginBottom: idx < 3 ? '8px' : 0 }}>
                        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                          <span style={{ width: 6, height: 6, borderRadius: '50%', background: item.dot, marginTop: 7, flexShrink: 0 }} />
                          <span style={{ color: isDark ? '#94a3b8' : '#4c1d95', fontSize: '13px' }}><strong style={{ color: item.dot }}>{item.title}：</strong>{item.desc}</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                  <div style={{ marginTop: '12px', padding: '10px 12px', background: isDark ? 'rgba(59, 130, 246, 0.1)' : '#f0f9ff', border: `1px solid ${isDark ? 'rgba(59, 130, 246, 0.3)' : '#bae6fd'}`, borderRadius: '8px' }}>
                    <div style={{ fontSize: '13px', color: isDark ? '#60a5fa' : '#0369a1' }}>
                      <strong>产出价值：</strong>全域关系图谱可以显著提升<strong>跨表JOIN查询</strong>的准确性，适合复杂业务报表问数、数据分析及<strong>多数据源异构融合</strong>场景
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 数据源选择 - 可滚动 */}
          <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' as const, maxHeight: '450px' }}>
          <div style={{
            ...styles.sourceLabel,
            color: isDark ? '#f1f5f9' : '#374151',
            flexShrink: 0
          }}>
            <span>选择数据源 <span style={{ color: '#ef4444' }}>*</span></span>
            <span style={{ ...styles.sourceCount, color: isDark ? '#c084fc' : '#9333ea' }}>已选 {selectedDataSources.length} 个</span>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', marginTop: '8px', minHeight: '80px' }}>
            <Spin spinning={loading}>
              {availableDataSources.map(ds => {
                const isSelected = selectedDataSources.includes(ds.id);
                const isDefault = ds.id === defaultDataSourceId;
                return (
                  <div
                    key={ds.id}
                    onClick={() => !isDefault && handleSelectDataSource(ds.id)}
                    style={getSourceCardStyle(ds.id, isSelected, isDefault)}
                  >
                    <Checkbox
                      checked={isSelected}
                      disabled={isDefault}
                    />
                    <DatabaseOutlined style={{
                      fontSize: '18px',
                      color: isSelected ? (isDark ? '#c084fc' : '#a855f7') : (isDark ? '#64748b' : '#9ca3af')
                    }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ ...styles.sourceName, color: isDark ? '#f1f5f9' : '#1f2937' }}>{ds.connect_name}</div>
                      <div style={{ ...styles.sourceDb, color: isDark ? '#64748b' : '#9ca3af' }}>({ds.database_name})</div>
                    </div>
                    {isDefault && (
                      <Tag style={{ margin: 0, background: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', color: isDark ? '#93c5fd' : '#1d4ed8', borderColor: isDark ? 'rgba(59, 130, 246, 0.5)' : '#93c5fd' }}>当前</Tag>
                    )}
                  </div>
                );
              })}
              {availableDataSources.length === 0 && !loading && (
                <div style={{ textAlign: 'center', padding: '24px', color: isDark ? '#64748b' : '#9ca3af' }}>
                  暂无可用数据源
                </div>
              )}
            </Spin>
          </div>
        </div>

        {/* 底部固定区域 */}
        <div style={{
          flexShrink: 0,
          borderTop: `1px solid ${isDark ? '#334155' : '#f0f0f0'}`,
          paddingTop: '12px',
          marginTop: '12px'
        }}>
          {/* 高级配置 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '24px', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ ...styles.configLabel, color: isDark ? '#94a3b8' : '#6b7280' }}>置信度阈值:</span>
              <Select
                value={confidenceThreshold}
                onChange={setConfidenceThreshold}
                size="small"
                style={{ width: 160 }}
                options={[
                  { value: 0.3, label: '低 (0.3) - 更多关系' },
                  { value: 0.5, label: '中 (0.5) - 推荐' },
                  { value: 0.7, label: '高 (0.7) - 精确关系' },
                  { value: 0.85, label: '很高 (0.85) - 最精确' }
                ]}
              />
            </div>
          </div>

          {/* 执行按钮 */}
          <div style={styles.executeButton}>
            <Button
              type="primary"
              size="large"
              icon={<SearchOutlined />}
              loading={discovering}
              disabled={selectedDataSources.length === 0}
              onClick={handleDiscoverRelationships}
              style={{
                height: '44px',
                paddingLeft: '28px',
                paddingRight: '28px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, #a855f7 0%, #ec4899 100%)',
                border: 'none',
                fontWeight: 500,
                fontSize: '15px',
                boxShadow: '0 4px 12px rgba(168, 85, 247, 0.4)'
              }}
            >
              {discovering ? '发现中...' : `发现表关系${selectedDataSources.length > 1 ? ` (${selectedDataSources.length}个)` : ''}`}
            </Button>
          </div>
        </div>
      </div>

      <GlobalInventoryResultModal
        visible={resultModalVisible}
        onClose={() => setResultModalVisible(false)}
        discoverResult={discoverResult}
        dataSources={dataSources}
        selectedDatasourceIds={selectedDataSources}
      />
    </Modal>
  );
};

export default GlobalInventoryModal;
