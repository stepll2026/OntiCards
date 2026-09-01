'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Modal,
  Button,
  Select,
  Card,
  Descriptions,
  Empty,
  message,
  Spin,
  Table,
  Tag,
  Tabs,
  Tooltip,
  Progress,
} from 'antd';
import {
  CheckCircleOutlined,
  DatabaseOutlined,
  ApartmentOutlined,
  TableOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  getRelationshipCards,
  getRelationshipCard,
  getTableRelationships,
  getRelationshipGraph,
  type RelationshipCardItem,
  type GlobalInventory,
  type RelationshipCard,
} from '@/api/globalInventory';
import type { DataSourceItem } from '@/api/datasource';
import dynamic from 'next/dynamic';

const RelationshipGraph = dynamic(
  () => import('@/app/[lng]/(newLayout)/global-inventory/RelationshipGraph'),
  { ssr: false, loading: () => <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}><Spin size="large" tip="加载图谱..." /></div> }
);

const { TabPane } = Tabs;

const RELATIONSHIP_TYPE_CONFIG: Record<string, { color: string; text: string }> = {
  FK: { color: 'success', text: '外键关联' },
  Semantic: { color: 'processing', text: '语义关系' },
  Value: { color: 'default', text: '值域关联' },
  foreign_key: { color: 'success', text: '外键关联' },
  semantic: { color: 'processing', text: '语义关系' },
  same_name: { color: 'default', text: '同名关联' },
  value_overlap: { color: 'default', text: '值域重叠' },
  shared_field: { color: 'default', text: '共享字段' }
};

const CARDINALITY_CONFIG: Record<string, { label: string; color: string }> = {
  many_to_one: { label: 'N:1', color: 'blue' },
  one_to_many: { label: '1:N', color: 'green' },
  one_to_one: { label: '1:1', color: 'purple' },
  many_to_many: { label: 'N:N', color: 'orange' },
};

export interface DiscoverResultForModal {
  tables_count: number;
  relationships_count: number;
  total_table_pairs: number;
  cards_count: number;
  cross_source_table_pairs?: number;
  intra_source_count?: number;
  datasource_ids?: string[];
  statistics?: {
    avg_confidence?: number;
  };
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

// ... existing interface definitions ...

interface GlobalInventoryResultModalProps {
  visible: boolean;
  onClose: () => void;
  discoverResult: DiscoverResultForModal | null;
  dataSources: DataSourceItem[];
  selectedDatasourceIds: string[];
}

// ... rest of the component definition with isDark hook ...

const GlobalInventoryResultModal: React.FC<GlobalInventoryResultModalProps> = ({
  visible,
  onClose,
  discoverResult,
  dataSources,
  selectedDatasourceIds,
}) => {
  const [viewingDataSourceId, setViewingDataSourceId] = useState<string>('');
  const [relationshipCards, setRelationshipCards] = useState<RelationshipCardItem[]>([]);
  const [tableRelationships, setTableRelationships] = useState<GlobalInventory[]>([]);
  const [graphData, setGraphData] = useState<{ nodes: any[]; edges: any[] } | null>(null);
  const [loadingData, setLoadingData] = useState(false);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [selectedCardDetail, setSelectedCardDetail] = useState<RelationshipCard | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  // 用于强制重置关系图谱组件
  const [graphKey, setGraphKey] = useState(0);
  // 当前激活的 Tab
  const [activeTab, setActiveTab] = useState('graph');

  // 添加深色模式 hook 调用
  const isDark = useDarkMode();

  const datasourceNameMap = useMemo(() => {
    const map = new Map<string, string>();
    dataSources.forEach((ds) => map.set(ds.id, ds.connect_name));
    return map;
  }, [dataSources]);

  const loadRelationshipData = useCallback(async (datasourceId: string) => {
    try {
      setLoadingData(true);
      const [cardsRes, relationshipsRes, graphRes] = await Promise.all([
        getRelationshipCards(datasourceId),
        getTableRelationships(datasourceId),
        getRelationshipGraph(datasourceId),
      ]);
      if (cardsRes.code === 200 && cardsRes.data) {
        setRelationshipCards(cardsRes.data.cards || []);
      } else {
        setRelationshipCards([]);
      }
      if (relationshipsRes.code === 200 && relationshipsRes.data) {
        setTableRelationships(relationshipsRes.data.relationships || []);
      } else {
        setTableRelationships([]);
      }
      if (graphRes.code === 200 && graphRes.data) {
        setGraphData(graphRes.data);
      } else {
        setGraphData(null);
      }
    } catch (e) {
      console.error('加载关系数据失败', e);
      setRelationshipCards([]);
      setTableRelationships([]);
      setGraphData(null);
    } finally {
      setLoadingData(false);
    }
  }, []);

  useEffect(() => {
    if (visible && discoverResult && selectedDatasourceIds.length > 0) {
      setViewingDataSourceId(selectedDatasourceIds[0]);
    }
  }, [visible]);

  useEffect(() => {
    if (visible && viewingDataSourceId) {
      loadRelationshipData(viewingDataSourceId);
    }
  }, [visible, viewingDataSourceId, loadRelationshipData]);

  // 初始加载时重置图谱尺寸
  useEffect(() => {
    if (graphData && visible) {
      setGraphKey(prev => prev + 1);
    }
  }, [graphData]);

  const handleViewCardDetail = async (tableName: string) => {
    if (!viewingDataSourceId) return;
    setSelectedCardDetail(null);
    setDetailModalVisible(true);
    setLoadingDetail(true);
    try {
      const response = await getRelationshipCard(viewingDataSourceId, tableName);
      if (response.code === 200 && response.data) {
        setSelectedCardDetail(response.data.card);
      } else {
        message.error(response.msg || '获取详情失败');
      }
    } catch (e) {
      console.error('获取关系卡片详情失败', e);
      message.error('获取详情失败');
    } finally {
      setLoadingDetail(false);
    }
  };

  const viewingDataSource = useMemo(
    () => dataSources.find((d) => d.id === viewingDataSourceId),
    [dataSources, viewingDataSourceId]
  );

  if (!discoverResult) return null;

  const dsCount = discoverResult.datasource_ids?.length || selectedDatasourceIds.length;
  const avgConf = discoverResult.statistics?.avg_confidence ?? 0;
  const totalPairs = discoverResult.total_table_pairs || 0;
  const crossSource = discoverResult.cross_source_table_pairs ?? 0;
  const intraSource = discoverResult.intra_source_count ?? totalPairs - crossSource;
  const crossPct = totalPairs > 0 ? ((crossSource / totalPairs) * 100).toFixed(0) : '0';
  const intraPct = totalPairs > 0 ? ((intraSource / totalPairs) * 100).toFixed(0) : '0';

  return (
    <>
      <Modal
        open={visible}
        onCancel={onClose}
        footer={null}
        width={1200}
        centered
        closable={true}
        title={null}
        styles={{
          body: { padding: 0, maxHeight: '85vh', overflowY: 'auto', background: isDark ? '#0f172a' : '#ffffff' },
          content: { borderRadius: 16, overflow: 'hidden', background: isDark ? '#1e293b' : '#ffffff' },
        }}
      >
        <div style={{ padding: '20px 24px', background: isDark ? '#0f172a' : '#ffffff' }}>
          {/* 结果摘要 - 紧凑列表 */}
          <div style={{
            background: isDark ? 'rgba(22, 163, 74, 0.1)' : '#f0fdf4',
            border: `1px solid ${isDark ? 'rgba(22, 163, 74, 0.3)' : '#bbf7d0'}`,
            borderRadius: 8,
            padding: '14px 18px',
            marginBottom: 16
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <CheckCircleOutlined style={{ color: isDark ? '#4ade80' : '#16a34a', fontSize: 18 }} />
              <span style={{ fontWeight: 600, color: isDark ? '#4ade80' : '#166534' }}>关系发现完成</span>
              {dsCount > 1 && (
                <Tag color="blue" style={{ marginLeft: 8 }}>{dsCount} 个数据源</Tag>
              )}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px 24px', fontSize: 13, color: isDark ? '#94a3b8' : '#374151' }}>
              <div>平均置信度: <strong style={{ color: isDark ? '#fb923c' : '#ea580c' }}>{Math.round(avgConf * 100)}%</strong></div>
              <div>分析表数（参与表关系发现的总数）: <strong style={{ color: isDark ? '#60a5fa' : '#2563eb' }}>{discoverResult.tables_count}</strong></div>
              <div>表对关系数（合并后的表间关系）: <strong style={{ color: isDark ? '#c084fc' : '#9333ea' }}>{discoverResult.total_table_pairs}</strong></div>
              <div>字段映射数（原始的字段关系映射）: <strong style={{ color: isDark ? '#fb923c' : '#ea580c' }}>{discoverResult.relationships_count}</strong></div>
              <div>生成卡片数（表关系说明书）: <strong style={{ color: isDark ? '#4ade80' : '#16a34a' }}>{discoverResult.cards_count}</strong></div>
              <div>跨源表对关系（不同数据源间）: <strong>{crossSource}</strong> ({crossPct}%)</div>
              <div>源内表对关系（同一数据源内）: <strong>{intraSource}</strong> ({intraPct}%)</div>
            </div>
          </div>

          {/* 数据源选择（多数据源时） */}
          {selectedDatasourceIds.length > 1 && (
            <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 13, color: isDark ? '#94a3b8' : '#6b7280' }}>查看数据源：</span>
              <Select
                value={viewingDataSourceId}
                onChange={setViewingDataSourceId}
                style={{ width: 280 }}
                options={selectedDatasourceIds.map((id) => ({
                  value: id,
                  label: dataSources.find((d) => d.id === id)?.connect_name || id,
                }))}
              />
            </div>
          )}

          {/* Tabs: 关系图谱 / 关系卡片 / 关系列表 */}
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            size="large"
            destroyInactiveTabPane={false}
            style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}
          >
            <TabPane
              tab={<span className={isDark ? 'text-slate-100 [&>*]:!text-slate-100' : ''} style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}><ApartmentOutlined /> 关系图谱</span>}
              key="graph"
            >
              {graphData && graphData.nodes?.length > 0 && (
                <div style={{ marginBottom: 8, fontSize: 13, color: isDark ? '#94a3b8' : '#6b7280' }}>
                  表: <strong style={{ color: isDark ? '#60a5fa' : '#2563eb' }}>{graphData.nodes.length}</strong>
                  {' '}关系: <strong style={{ color: isDark ? '#4ade80' : '#16a34a' }}>{graphData.edges?.length || 0}</strong>
                  {' '}平均置信度: <strong style={{ color: isDark ? '#fb923c' : '#ea580c' }}>
                    {graphData.edges?.length
                      ? Math.round(
                          (graphData.edges.reduce((s: number, e: any) => s + (e.strength || 0), 0) / graphData.edges.length) * 100
                        )
                      : 0}%
                  </strong>
                </div>
              )}
              <Spin spinning={loadingData}>
                <div style={{ height: 520, minHeight: 400 }}>
                  <RelationshipGraph
                    key={`graph-${graphKey}`}
                    data={graphData}
                    loading={loadingData}
                    datasourceNameMap={datasourceNameMap}
                    relationshipCards={relationshipCards}
                  />
                </div>
              </Spin>
            </TabPane>
            <TabPane
              tab={<span className={isDark ? 'text-slate-100 [&>*]:!text-slate-100' : ''} style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}><TableOutlined /> 关系卡片 {relationshipCards.length > 0 ? `(${relationshipCards.length})` : ''}</span>}
              key="cards"
            >
              <div style={{ background: isDark ? 'rgba(59, 130, 246, 0.15)' : '#eff6ff', border: `1px solid ${isDark ? 'rgba(59, 130, 246, 0.4)' : '#bfdbfe'}`, borderRadius: 8, padding: 12, marginBottom: 16 }}>
                <div style={{ fontSize: 13, color: isDark ? '#e2e8f0' : '#1e40af' }}>
                  <strong style={{ color: isDark ? '#93c5fd' : '#1e40af' }}>关系卡片</strong>：为每张表生成的关系说明书，包含该表与其他表的关联关系、JOIN 条件建议和数据融合策略。
                </div>
              </div>
              <Spin spinning={loadingData}>
                {relationshipCards.length === 0 ? (
                  <Empty description="暂无关系卡片数据" style={{ padding: 48, color: isDark ? '#94a3b8' : '#6b7280' }} />
                ) : (
                  <Table
                    dataSource={relationshipCards}
                    rowKey="table_name"
                    pagination={{ pageSize: 10, showSizeChanger: true }}
                    size="small"
                    style={{ background: isDark ? '#1e293b' : '#ffffff', borderRadius: 8 }}
                    className={isDark ? 'dark-table' : ''}
                    columns={[
                      {
                        title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>表名</span>,
                        dataIndex: 'table_name',
                        key: 'table_name',
                        width: '22%',
                        render: (text: string, record) => (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontWeight: 500, color: isDark ? '#60a5fa' : '#2563eb' }}>{text}</span>
                            {record.has_cross_source_relations && (
                              <Tag style={{ background: isDark ? 'rgba(251, 191, 36, 0.3)' : '#fef3c7', color: isDark ? '#fbbf24' : '#92400e', borderColor: 'transparent' }}>跨源</Tag>
                            )}
                          </div>
                        ),
                      },
                      {
                        title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>关联表数</span>,
                        dataIndex: 'related_tables_count',
                        key: 'related_tables_count',
                        width: '12%',
                        render: (count: number) => (
                          <Tag style={{ background: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', color: isDark ? '#60a5fa' : '#1e40af', borderColor: 'transparent' }}>
                            {count} 个关联
                          </Tag>
                        ),
                      },
                      {
                        title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>平均置信度</span>,
                        key: 'avg_confidence',
                        width: '20%',
                        render: (_: any, record) => {
                          const avgConf = record.card?.Statistics?.avg_confidence || 0;
                          return (
                            <Progress
                              percent={Math.round(avgConf * 100)}
                              size="small"
                              strokeColor={avgConf >= 0.85 ? '#52c41a' : avgConf >= 0.6 ? '#faad14' : '#ff4d4f'}
                              style={{ width: 120 }}
                            />
                          );
                        },
                      },
                      {
                        title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>操作</span>,
                        key: 'action',
                        width: '18%',
                        render: (_: any, record) => (
                          <Button type="link" size="small" onClick={() => handleViewCardDetail(record.table_name)} style={{ color: isDark ? '#60a5fa' : '#2563eb' }}>
                            查看详情
                          </Button>
                        ),
                      },
                    ]}
                  />
                )}
              </Spin>
            </TabPane>
            <TabPane
              tab={<span className={isDark ? 'text-slate-100 [&>*]:!text-slate-100' : ''} style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}><LinkOutlined /> 关系列表 {tableRelationships.length > 0 ? `(${tableRelationships.length})` : ''}</span>}
              key="relationships"
            >
              <div style={{ background: isDark ? 'rgba(59, 130, 246, 0.15)' : '#eff6ff', border: `1px solid ${isDark ? 'rgba(59, 130, 246, 0.4)' : '#bfdbfe'}`, borderRadius: 8, padding: 12, marginBottom: 16 }}>
                <div style={{ fontSize: 13, color: isDark ? '#e2e8f0' : '#1e40af' }}>
                  <strong style={{ color: isDark ? '#93c5fd' : '#1e40af' }}>表关系列表</strong>：所有表对之间的关系明细，包括关系类型、基数、强度等。
                </div>
              </div>
              <Spin spinning={loadingData}>
                {tableRelationships.length === 0 ? (
                  <Empty description="暂无表关系数据" style={{ padding: 48, color: isDark ? '#94a3b8' : '#6b7280' }} />
                ) : (
                  <Table
                    dataSource={tableRelationships}
                    rowKey="id"
                    pagination={{ pageSize: 15, showSizeChanger: true }}
                    size="small"
                    scroll={{ x: true }}
                    style={{ background: isDark ? '#1e293b' : '#ffffff', borderRadius: 8 }}
                    className={isDark ? 'dark-table' : ''}
                    columns={[
                      {
                        title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>关系类型</span>,
                        key: 'source_type',
                        width: '10%',
                        render: (_: any, record) =>
                          record.is_cross_source ? (
                            <Tag style={{ background: isDark ? 'rgba(251, 191, 36, 0.3)' : '#fef3c7', color: isDark ? '#fbbf24' : '#92400e', borderColor: 'transparent' }}>跨源</Tag>
                          ) : (
                            <Tag style={{ background: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', color: isDark ? '#60a5fa' : '#1e40af', borderColor: 'transparent' }}>同源</Tag>
                          ),
                      },
                      {
                        title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>表A</span>,
                        dataIndex: 'table_a',
                        key: 'table_a',
                        width: '18%',
                        render: (text: string, record) => (
                          <div>
                            <div style={{ fontWeight: 500, color: isDark ? '#f1f5f9' : '#1f2937' }}>{text}</div>
                            {record.table_a_datasource_name && (
                              <div style={{ fontSize: 12, color: isDark ? '#64748b' : '#9ca3af', marginTop: 2 }}>
                                <DatabaseOutlined style={{ marginRight: 4 }} />
                                {record.table_a_datasource_name}
                              </div>
                            )}
                          </div>
                        ),
                      },
                      { title: '', key: 'arrow', width: '4%', render: () => <LinkOutlined style={{ color: isDark ? '#60a5fa' : '#1890ff' }} /> },
                      {
                        title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>表B</span>,
                        dataIndex: 'table_b',
                        key: 'table_b',
                        width: '18%',
                        render: (text: string, record) => (
                          <div>
                            <div style={{ fontWeight: 500, color: isDark ? '#f1f5f9' : '#1f2937' }}>{text}</div>
                            {record.table_b_datasource_name && (
                              <div style={{ fontSize: 12, color: isDark ? '#64748b' : '#9ca3af', marginTop: 2 }}>
                                <DatabaseOutlined style={{ marginRight: 4 }} />
                                {record.table_b_datasource_name}
                              </div>
                            )}
                          </div>
                        ),
                      },
                      {
                        title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>关系类型</span>,
                        dataIndex: 'relationship_type',
                        key: 'relationship_type',
                        width: '10%',
                        render: (type: string) => {
                          const config = RELATIONSHIP_TYPE_CONFIG[type];
                          return config ? (
                            <Tag style={{ background: isDark ? 'rgba(99, 102, 241, 0.2)' : '#ede9fe', color: isDark ? '#a5b4fc' : '#7c3aed', borderColor: 'transparent' }}>{config.text}</Tag>
                          ) : (
                            <Tag>{type}</Tag>
                          );
                        },
                      },
                      {
                        title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>基数</span>,
                        dataIndex: 'cardinality',
                        key: 'cardinality',
                        width: '8%',
                        render: (cardinality: string) => {
                          const config = CARDINALITY_CONFIG[cardinality];
                          return config ? (
                            <Tag style={{ background: isDark ? 'rgba(139, 92, 246, 0.2)' : '#ede9fe', color: isDark ? '#c084fc' : '#7c3aed', borderColor: 'transparent' }}>{config.label}</Tag>
                          ) : (
                            <Tag>{cardinality}</Tag>
                          );
                        },
                      },
                      {
                        title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>强度</span>,
                        dataIndex: 'relationship_strength',
                        key: 'relationship_strength',
                        width: '12%',
                        render: (strength: number) => (
                          <Progress
                            percent={Math.round((strength || 0) * 100)}
                            size="small"
                            strokeColor={(strength || 0) >= 0.85 ? '#52c41a' : (strength || 0) >= 0.6 ? '#faad14' : '#ff4d4f'}
                            style={{ width: 80 }}
                          />
                        ),
                      },
                    ]}
                  />
                )}
              </Spin>
            </TabPane>
          </Tabs>
        </div>
      </Modal>

      {/* 关系卡片详情弹窗 */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <TableOutlined style={{ color: isDark ? '#60a5fa' : '#2563eb' }} />
            <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>关系卡片详情</span>
            {!loadingDetail && selectedCardDetail && (
              <>
                <Tag style={{ background: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', color: isDark ? '#93c5fd' : '#1d4ed8', borderColor: 'transparent' }}>{selectedCardDetail.TableInfo?.table_name}</Tag>
                {viewingDataSource && (
                  <Tag style={{ background: isDark ? 'rgba(6, 182, 212, 0.2)' : '#cffafe', color: isDark ? '#67e8f9' : '#0891b2', borderColor: 'transparent' }} icon={<DatabaseOutlined />}>{viewingDataSource.connect_name}</Tag>
                )}
              </>
            )}
          </div>
        }
        open={detailModalVisible}
        onCancel={() => { setDetailModalVisible(false); setSelectedCardDetail(null); }}
        footer={null}
        width={1100}
        centered
        styles={{
          body: { maxHeight: '83vh', overflowY: 'auto', background: isDark ? '#0f172a' : '#ffffff', color: isDark ? '#f1f5f9' : '#1e293b' },
          content: { background: isDark ? '#1e293b' : '#ffffff' },
          header: { background: isDark ? '#1e293b' : '#ffffff', borderBottom: isDark ? '1px solid #334155' : '#e5e7eb' }
        }}
      >
        {loadingDetail ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 48 }}>
            <Spin size="large" />
            <div style={{ marginTop: 16, color: isDark ? '#94a3b8' : '#6b7280' }}>正在加载关系卡片数据...</div>
          </div>
        ) : selectedCardDetail ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <Card
              size="small"
              title={<span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>基本信息</span>}
              style={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb' }}
              headStyle={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb', color: isDark ? '#f1f5f9' : '#1e293b' }}
              bodyStyle={{ background: isDark ? '#1e293b' : '#ffffff' }}
            >
              <Descriptions column={2} size="small">
                <Descriptions.Item label={<span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>表名</span>}><span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>{selectedCardDetail.TableInfo?.table_name}</span></Descriptions.Item>
                <Descriptions.Item label={<span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>所属数据源</span>}>
                  <span style={{ color: isDark ? '#67e8f9' : '#0891b2' }}>
                    <DatabaseOutlined style={{ marginRight: 4 }} />
                    {viewingDataSource?.connect_name || '-'}
                  </span>
                </Descriptions.Item>
                <Descriptions.Item label={<span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>字段数</span>}><span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>{selectedCardDetail.TableInfo?.fields_count}</span></Descriptions.Item>
                <Descriptions.Item label={<span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>主键</span>}><span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>{selectedCardDetail.TableInfo?.primary_key || '-'}</span></Descriptions.Item>
                <Descriptions.Item label={<span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>关联表数</span>}><span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>{selectedCardDetail.Statistics?.related_tables_count}</span></Descriptions.Item>
                <Descriptions.Item label={<span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>平均置信度</span>}>
                  <span style={{
                    color: (selectedCardDetail.Statistics?.avg_confidence || 0) >= 0.85 ? (isDark ? '#4ade80' : '#16a34a') : (selectedCardDetail.Statistics?.avg_confidence || 0) >= 0.6 ? (isDark ? '#fbbf24' : '#ca8a04') : (isDark ? '#f87171' : '#dc2626'),
                  }}>
                    {((selectedCardDetail.Statistics?.avg_confidence || 0) * 100).toFixed(0)}%
                  </span>
                </Descriptions.Item>
              </Descriptions>
            </Card>
            {selectedCardDetail.JoinSummary && (
              <Card
                size="small"
                title={<span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>关系摘要</span>}
                style={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb' }}
                headStyle={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb', color: isDark ? '#f1f5f9' : '#1e293b' }}
                bodyStyle={{ background: isDark ? '#1e293b' : '#ffffff' }}
              >
                <p style={{ color: isDark ? '#94a3b8' : '#374151', margin: 0 }}>{selectedCardDetail.JoinSummary}</p>
              </Card>
            )}
            {selectedCardDetail.Relationships && selectedCardDetail.Relationships.length > 0 && (
              <Card
                size="small"
                title={<span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>关联关系 ({selectedCardDetail.Relationships.length})</span>}
                style={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb' }}
                headStyle={{ background: isDark ? '#1e293b' : '#ffffff', borderColor: isDark ? '#334155' : '#e5e7eb', color: isDark ? '#f1f5f9' : '#1e293b' }}
                bodyStyle={{ background: isDark ? '#1e293b' : '#ffffff' }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {selectedCardDetail.Relationships.map((rel: any, idx: number) => (
                    <div key={idx} style={{ border: rel.is_cross_source ? (isDark ? '1px solid rgba(251, 191, 36, 0.5)' : '1px solid #fed7aa') : (isDark ? '1px solid #334155' : '1px solid #e5e7eb'), borderRadius: 8, padding: 12, background: rel.is_cross_source ? (isDark ? 'rgba(251, 191, 36, 0.1)' : '#fff7ed') : (isDark ? '#0f172a' : 'transparent') }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                          {rel.is_cross_source ? <Tag style={{ background: isDark ? 'rgba(251, 191, 36, 0.3)' : '#fef3c7', color: isDark ? '#fbbf24' : '#92400e', borderColor: 'transparent' }}>跨源</Tag> : <Tag style={{ background: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', color: isDark ? '#60a5fa' : '#1e40af', borderColor: 'transparent' }}>同源</Tag>}
                          <Tag style={{ background: isDark ? 'rgba(34, 197, 94, 0.2)' : '#dcfce7', color: isDark ? '#4ade80' : '#16a34a', borderColor: 'transparent' }}>{rel.related_table}</Tag>
                          {rel.related_datasource_name && (
                            <Tag style={{ background: isDark ? 'rgba(6, 182, 212, 0.2)' : '#cffafe', color: isDark ? '#67e8f9' : '#0891b2', borderColor: 'transparent' }} icon={<DatabaseOutlined />}>{rel.related_datasource_name}</Tag>
                          )}
                          <Tag style={{ background: isDark ? 'rgba(99, 102, 241, 0.2)' : '#ede9fe', color: isDark ? '#a5b4fc' : '#7c3aed', borderColor: 'transparent' }}>
                            {CARDINALITY_CONFIG[rel.relationship_type]?.label || rel.relationship_type}
                          </Tag>
                        </div>
                        <Progress
                          percent={Math.round((rel.confidence || 0) * 100)}
                          size="small"
                          style={{ width: 100 }}
                          strokeColor={(rel.confidence || 0) >= 0.85 ? '#52c41a' : (rel.confidence || 0) >= 0.6 ? '#faad14' : '#ff4d4f'}
                        />
                      </div>
                      {rel.join_fields?.length > 0 && (
                        <div style={{ marginBottom: 8 }}>
                          <div style={{ fontSize: 12, color: isDark ? '#64748b' : '#6b7280', marginBottom: 4 }}>JOIN 字段：</div>
                          {rel.join_fields.map((field: any, fidx: number) => (
                            <div key={fidx} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, background: isDark ? '#0f172a' : '#f9fafb', padding: '6px 8px', borderRadius: 4, marginBottom: 4 }}>
                              <span style={{ fontFamily: 'monospace', color: isDark ? '#60a5fa' : '#2563eb' }}>{field.local_field}</span>
                              <span style={{ color: isDark ? '#475569' : '#9ca3af' }}>=</span>
                              <span style={{ fontFamily: 'monospace', color: isDark ? '#4ade80' : '#16a34a' }}>{field.remote_field}</span>
                              <Tag style={{ background: isDark ? 'rgba(148, 163, 184, 0.2)' : '#f3f4f6', color: isDark ? '#94a3b8' : '#6b7280', borderColor: 'transparent' }}>{RELATIONSHIP_TYPE_CONFIG[field.relationship_type]?.text || field.relationship_type}</Tag>
                            </div>
                          ))}
                        </div>
                      )}
                      {rel.join_suggestion && (rel.join_suggestion.join_type || rel.join_suggestion.join_condition || rel.join_suggestion.sample_sql || (rel.join_suggestion.use_cases && rel.join_suggestion.use_cases.length > 0)) && (
                        <div style={{ background: isDark ? 'rgba(59, 130, 246, 0.1)' : '#eff6ff', border: isDark ? '1px solid rgba(59, 130, 246, 0.3)' : '1px solid #bfdbfe', borderRadius: 6, padding: 10, marginBottom: 8 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                            <span style={{ fontSize: 12, color: isDark ? '#64748b' : '#6b7280' }}>推荐连接：</span>
                            <Tag style={{ background: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', color: isDark ? '#60a5fa' : '#1e40af', borderColor: 'transparent' }}>{rel.join_suggestion.join_type || 'INNER JOIN'}</Tag>
                          </div>
                          {rel.join_suggestion.join_condition && (
                            <div style={{ fontFamily: 'monospace', fontSize: 12, color: isDark ? '#e2e8f0' : '#374151', background: isDark ? '#0f172a' : '#fff', padding: '6px 8px', borderRadius: 4, marginBottom: 6 }}>
                              {rel.join_suggestion.join_condition}
                            </div>
                          )}
                          {rel.join_suggestion.sample_sql && (
                            <div style={{ marginBottom: 6 }}>
                              <div style={{ fontSize: 12, color: isDark ? '#64748b' : '#6b7280', marginBottom: 4 }}>📝 示例SQL：</div>
                              <pre style={{ background: isDark ? '#1e293b' : '#1f2937', color: '#4ade80', padding: 8, borderRadius: 4, overflow: 'auto', margin: 0, fontSize: 11, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                                {rel.join_suggestion.sample_sql}
                              </pre>
                            </div>
                          )}
                          {rel.join_suggestion.use_cases && rel.join_suggestion.use_cases.length > 0 && (
                            <div style={{ marginTop: 6 }}>
                              <span style={{ fontSize: 12, color: isDark ? '#64748b' : '#6b7280' }}>💼 适用场景：</span>
                              <ul style={{ margin: '4px 0 0 16px', padding: 0, fontSize: 12, color: isDark ? '#94a3b8' : '#6b7280' }}>
                                {rel.join_suggestion.use_cases.map((uc: string, ucIdx: number) => (
                                  <li key={ucIdx}>{uc}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}
                      {rel.business_relation && (rel.business_relation.relation_description || rel.business_relation.from_entity || rel.business_relation.to_entity) && (
                        <div style={{ background: isDark ? 'rgba(99, 102, 241, 0.1)' : '#eef2ff', border: isDark ? '1px solid rgba(99, 102, 241, 0.3)' : '1px solid #c7d2fe', borderRadius: 6, padding: 10 }}>
                          <div style={{ fontSize: 12, color: isDark ? '#a5b4fc' : '#4f46e5', fontWeight: 500, marginBottom: 6 }}>📋 业务关系</div>
                          {rel.business_relation.relation_description && (
                            <div style={{ fontSize: 13, color: isDark ? '#94a3b8' : '#374151', marginBottom: 8 }}>{rel.business_relation.relation_description}</div>
                          )}
                          <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 12 }}>
                            {rel.business_relation.from_entity && rel.business_relation.from_role && (
                              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                <span style={{ color: isDark ? '#64748b' : '#6b7280' }}>{rel.business_relation.from_entity}:</span>
                                <Tag style={{ background: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', color: isDark ? '#60a5fa' : '#1e40af', borderColor: 'transparent', margin: 0 }}>
                                  {rel.business_relation.from_role === 'master' ? '主表' : rel.business_relation.from_role === 'detail' ? '明细表' : rel.business_relation.from_role === 'fact' ? '事实表' : rel.business_relation.from_role === 'dimension' ? '维度表' : rel.business_relation.from_role}
                                </Tag>
                              </div>
                            )}
                            {rel.business_relation.to_entity && rel.business_relation.to_role && (
                              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                <span style={{ color: isDark ? '#64748b' : '#6b7280' }}>{rel.business_relation.to_entity}:</span>
                                <Tag style={{ background: isDark ? 'rgba(34, 197, 94, 0.2)' : '#dcfce7', color: isDark ? '#4ade80' : '#16a34a', borderColor: 'transparent', margin: 0 }}>
                                  {rel.business_relation.to_role === 'master' ? '主表' : rel.business_relation.to_role === 'detail' ? '明细表' : rel.business_relation.to_role === 'fact' ? '事实表' : rel.business_relation.to_role === 'dimension' ? '维度表' : rel.business_relation.to_role}
                                </Tag>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                      {rel.fusion_suggestion && (rel.fusion_suggestion.fusion_strategy || rel.fusion_suggestion.aggregation_hint) && (
                        <div style={{ background: isDark ? 'rgba(34, 197, 94, 0.1)' : '#f0fdf4', border: isDark ? '1px solid rgba(34, 197, 94, 0.3)' : '1px solid #bbf7d0', borderRadius: 6, padding: 10 }}>
                          <div style={{ fontSize: 12, color: isDark ? '#4ade80' : '#15803d', fontWeight: 500, marginBottom: 6 }}>🔀 融合建议</div>
                          {rel.fusion_suggestion.fusion_strategy && (
                            <div style={{ fontSize: 12, color: isDark ? '#94a3b8' : '#374151', marginBottom: rel.fusion_suggestion.aggregation_hint ? 6 : 0 }}>
                              融合策略：{rel.fusion_suggestion.fusion_strategy}
                            </div>
                          )}
                          {rel.fusion_suggestion.aggregation_hint && (
                            <div style={{ fontSize: 12, color: isDark ? '#94a3b8' : '#374151' }}>
                              聚合提示：{rel.fusion_suggestion.aggregation_hint}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* 数据融合建议 */}
            {selectedCardDetail.FusionHints && (selectedCardDetail.FusionHints.as_master?.length > 0 || selectedCardDetail.FusionHints.as_detail?.length > 0 || selectedCardDetail.FusionHints.common_joins?.length > 0) && (
              <Card size="small" title="🔀 数据融合建议">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {selectedCardDetail.FusionHints.as_master?.length > 0 && (
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 6 }}>作为主表时：</div>
                      <ul style={{ margin: 0, paddingLeft: 20, fontSize: 12, color: '#6b7280' }}>
                        {selectedCardDetail.FusionHints.as_master.map((hint: string, idx: number) => (
                          <li key={idx}>{hint}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {selectedCardDetail.FusionHints.as_detail?.length > 0 && (
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 6 }}>作为明细表时：</div>
                      <ul style={{ margin: 0, paddingLeft: 20, fontSize: 12, color: '#6b7280' }}>
                        {selectedCardDetail.FusionHints.as_detail.map((hint: string, idx: number) => (
                          <li key={idx}>{hint}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {selectedCardDetail.FusionHints.common_joins?.length > 0 && (
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 6 }}>常见联表场景：</div>
                      <ul style={{ margin: 0, paddingLeft: 20, fontSize: 12, color: '#6b7280' }}>
                        {selectedCardDetail.FusionHints.common_joins.map((hint: string, idx: number) => (
                          <li key={idx}>{hint}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </Card>
            )}
          </div>
        ) : null}
      </Modal>
    </>
  );
};

export default GlobalInventoryResultModal;
