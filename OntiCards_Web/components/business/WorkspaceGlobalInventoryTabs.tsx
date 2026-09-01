'use client';

import React, { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import { Tabs, Table, Card, Descriptions, Empty, Spin, Modal, Tag, Tooltip, Progress, Button, Input, message } from 'antd';
import { DatabaseOutlined, TableOutlined, LinkOutlined, InfoCircleOutlined, ApartmentOutlined, DeleteOutlined } from '@ant-design/icons';
import { Search } from 'lucide-react';
import type { ColumnsType } from 'antd/es/table';
import {
  getRelationshipCard,
  deleteRelationshipsByDatasourceId,
  type RelationshipCardItem,
  type GlobalInventory,
  type GraphNode,
  type GraphEdge,
  type RelationshipCard,
} from '@/api/globalInventory';
import type { DataSourceItem } from '@/api/datasource';
import dynamic from 'next/dynamic';

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

    const observer = new MutationObserver(checkDark);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme']
    });

    return () => observer.disconnect();
  }, []);

  return isDark;
};

const RelationshipGraph = dynamic(
  () => import('@/app/[lng]/(newLayout)/global-inventory/RelationshipGraph'),
  { ssr: false, loading: () => <div className="flex items-center justify-center min-h-[400px]"><Spin size="large" tip="加载图谱..." /></div> }
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

// 虚拟列表行高
const RELATIONSHIP_ROW_HEIGHT = 180;
const VISIBLE_ROWS = 3;

// 虚拟列表组件
const VirtualRelationshipList: React.FC<{
  relationships: any[];
  isDark: boolean;
}> = ({ relationships, isDark }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [containerHeight, setContainerHeight] = useState(RELATIONSHIP_ROW_HEIGHT * VISIBLE_ROWS);

  const totalHeight = relationships.length * RELATIONSHIP_ROW_HEIGHT;

  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerHeight(entry.contentRect.height);
      }
    });

    resizeObserver.observe(container);
    return () => resizeObserver.disconnect();
  }, []);

  const startIndex = Math.max(0, Math.floor(scrollTop / RELATIONSHIP_ROW_HEIGHT) - 1);
  const endIndex = Math.min(
    relationships.length,
    Math.ceil((scrollTop + containerHeight) / RELATIONSHIP_ROW_HEIGHT) + 1
  );

  const visibleItems = relationships.slice(startIndex, endIndex);
  const offsetY = startIndex * RELATIONSHIP_ROW_HEIGHT;

  return (
    <div
      ref={containerRef}
      className="overflow-y-auto"
      onScroll={handleScroll}
      style={{ maxHeight: RELATIONSHIP_ROW_HEIGHT * VISIBLE_ROWS }}
    >
      <div style={{ height: totalHeight, position: 'relative' }}>
        <div style={{ transform: `translateY(${offsetY}px)` }}>
          {visibleItems.map((rel, idx) => {
            const actualIndex = startIndex + idx;
            return (
              <div
                key={actualIndex}
                style={{
                  height: RELATIONSHIP_ROW_HEIGHT - 8,
                  marginBottom: 8,
                  border: `1px solid ${rel.is_cross_source ? (isDark ? 'rgba(251, 146, 60, 0.5)' : '#fb923c') : (isDark ? '#334155' : '#e5e7eb')}`,
                  borderRadius: '8px',
                  padding: '12px',
                  background: rel.is_cross_source ? (isDark ? 'rgba(251, 146, 60, 0.1)' : 'rgba(254, 215, 170, 0.3)') : (isDark ? '#1e293b' : '#ffffff'),
                  overflow: 'hidden'
                }}
              >
                <div className="flex items-center justify-between mb-2" style={{ flexWrap: 'wrap', gap: '4px' }}>
                  <div className="flex items-center gap-2">
                    {rel.is_cross_source ? <Tag color="orange">跨源</Tag> : <Tag color="blue">同源</Tag>}
                    <Tag color="green">{rel.related_table}</Tag>
                    {rel.related_datasource_name && <Tag color="cyan" icon={<DatabaseOutlined />}>{rel.related_datasource_name}</Tag>}
                    <Tag color={CARDINALITY_CONFIG[rel.relationship_type]?.color || 'default'}>
                      {CARDINALITY_CONFIG[rel.relationship_type]?.label || rel.relationship_type}
                    </Tag>
                  </div>
                  <Progress percent={Math.round((rel.confidence || 0) * 100)} size="small" style={{ width: 80 }} strokeColor={(rel.confidence || 0) >= 0.85 ? '#52c41a' : (rel.confidence || 0) >= 0.6 ? '#faad14' : '#ff4d4f'} />
                </div>
                {rel.join_fields?.length > 0 && (
                  <div className="mb-2" style={{ overflow: 'hidden' }}>
                    <div className="text-xs mb-1" style={{ color: isDark ? '#94a8b8' : '#6b7280' }}>JOIN 字段：</div>
                    <div className="flex items-center gap-1 text-xs flex-wrap">
                      {rel.join_fields.slice(0, 3).map((field: any, fidx: number) => (
                        <span key={fidx} className="flex items-center gap-1 px-1.5 py-0.5 rounded" style={{ background: isDark ? '#1e293b' : '#f9fafb' }}>
                          <span className="font-mono" style={{ color: isDark ? '#60a5fa' : '#2563eb' }}>{field.local_field}</span>
                          <span style={{ color: isDark ? '#475569' : '#9ca3af' }}>=</span>
                          <span className="font-mono" style={{ color: isDark ? '#4ade80' : '#16a34a' }}>{field.remote_field}</span>
                          <Tag style={{ margin: 0, fontSize: '10px' }}>{RELATIONSHIP_TYPE_CONFIG[field.relationship_type]?.text || field.relationship_type}</Tag>
                        </span>
                      ))}
                      {rel.join_fields.length > 3 && <Tag>+{rel.join_fields.length - 3}</Tag>}
                    </div>
                  </div>
                )}
                {(rel.join_suggestion?.sample_sql || rel.business_relation?.relation_description) && (
                  <div className="text-xs truncate" style={{ color: isDark ? '#64748b' : '#9ca3af' }}>
                    {rel.business_relation?.relation_description || rel.join_suggestion?.join_condition || ''}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

interface WorkspaceGlobalInventoryTabsProps {
  datasourceId: string;
  datasourceName: string;
  /** 可选：完整 id→名称映射（跨源图谱图例），缺省时仅含当前数据源 */
  datasourceNameMap?: Map<string, string>;
  relationshipCards: RelationshipCardItem[];
  tableRelationships: GlobalInventory[];
  graphData: { nodes: GraphNode[]; edges: GraphEdge[] };
  loading: boolean;
  /** 刷新回调，清除数据后调用以刷新全域盘点内容 */
  onRefresh?: () => void;
}

const WorkspaceGlobalInventoryTabs: React.FC<WorkspaceGlobalInventoryTabsProps> = ({
  datasourceId,
  datasourceName,
  datasourceNameMap: datasourceNameMapProp,
  relationshipCards,
  tableRelationships,
  graphData,
  loading,
  onRefresh,
}) => {
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [selectedCardDetail, setSelectedCardDetail] = useState<RelationshipCard | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [cardSearchText, setCardSearchText] = useState('');
  const [relationshipSearchText, setRelationshipSearchText] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [deleteConfirmVisible, setDeleteConfirmVisible] = useState(false);
  const isDark = useDarkMode();

  const datasourceNameMap = useMemo(() => {
    const map = new Map<string, string>();
    if (datasourceNameMapProp) {
      datasourceNameMapProp.forEach((v, k) => map.set(k, v));
    }
    if (datasourceId) {
      map.set(datasourceId, datasourceName || map.get(datasourceId) || datasourceId);
    }
    return map;
  }, [datasourceId, datasourceName, datasourceNameMapProp]);

  // 过滤后的关系卡片数据
  const filteredRelationshipCards = useMemo(() => {
    if (!cardSearchText.trim()) return relationshipCards;
    const search = cardSearchText.toLowerCase();
    return relationshipCards.filter(card =>
      card.table_name?.toLowerCase().includes(search) ||
      card.card?.TableInfo?.table_name?.toLowerCase().includes(search) ||
      card.related_tables_count?.toString().includes(search) ||
      (card.card?.Statistics?.avg_confidence * 100).toFixed(0).includes(search)
    );
  }, [relationshipCards, cardSearchText]);

  // 过滤后的表关系数据
  const filteredTableRelationships = useMemo(() => {
    if (!relationshipSearchText.trim()) return tableRelationships;
    const search = relationshipSearchText.toLowerCase();
    return tableRelationships.filter(rel =>
      rel.table_a?.toLowerCase().includes(search) ||
      rel.table_b?.toLowerCase().includes(search) ||
      rel.table_a_datasource_name?.toLowerCase().includes(search) ||
      rel.table_b_datasource_name?.toLowerCase().includes(search) ||
      rel.relationship_type?.toLowerCase().includes(search) ||
      rel.cardinality?.toLowerCase().includes(search) ||
      (rel.relationship_strength * 100).toFixed(0).includes(search) ||
      (rel.is_cross_source ? '跨源' : '同源').includes(search)
    );
  }, [tableRelationships, relationshipSearchText]);

  const handleViewCardDetail = async (tableName: string) => {
    setSelectedCardDetail(null);
    setDetailModalVisible(true);
    setLoadingDetail(true);
    try {
      const response = await getRelationshipCard(datasourceId, tableName);
      if (response.code === 200 && response.data) {
        setSelectedCardDetail(response.data.card);
      }
    } catch (e) {
      console.error('获取关系卡片详情失败', e);
    } finally {
      setLoadingDetail(false);
    }
  };

  // 清除关系数据
  const handleDeleteRelationships = async () => {
    setDeleteConfirmVisible(false);
    if (!datasourceId) return;

    try {
      setDeleting(true);
      const res = await deleteRelationshipsByDatasourceId(datasourceId);
      if (res.code === 200) {
        message.success('关系数据已清除');
        // 调用刷新回调以重新加载数据
        onRefresh?.();
      } else {
        message.error(res.msg || '清除失败');
      }
    } catch (e) {
      console.error('清除关系数据失败', e);
      message.error('清除失败，请重试');
    } finally {
      setDeleting(false);
    }
  };

  const cardColumns: ColumnsType<RelationshipCardItem> = [
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>表名</span>,
      dataIndex: 'table_name',
      key: 'table_name',
      width: '22%',
      render: (text: string, record) => (
        <div className="flex items-center gap-2">
          <span className="font-medium" style={{ color: isDark ? '#60a5fa' : '#2563eb' }}>{text}</span>
          {record.has_cross_source_relations && <Tag style={{ background: isDark ? 'rgba(251, 191, 36, 0.3)' : '#fef3c7', color: isDark ? '#fbbf24' : '#92400e', borderColor: 'transparent' }}>跨源</Tag>}
        </div>
      ),
    },
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>关联表数</span>,
      dataIndex: 'related_tables_count',
      key: 'related_tables_count',
      width: '12%',
      render: (count: number) => (
        <Tag style={{ background: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', color: isDark ? '#93c5fd' : '#1d4ed8', borderColor: 'transparent' }}>{count} 个关联</Tag>
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
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>更新时间</span>,
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: '20%',
      render: (text: string) => <span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>{text ? new Date(text).toLocaleString() : '-'}</span>,
    },
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>操作</span>,
      key: 'action',
      width: '20%',
      render: (_: any, record) => (
        <Button type="link" icon={<InfoCircleOutlined />} onClick={() => handleViewCardDetail(record.table_name)} style={{ color: isDark ? '#60a5fa' : '#2563eb' }}>
          查看详情
        </Button>
      ),
    },
  ];

  const relationshipColumns: ColumnsType<GlobalInventory> = [
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>关系标识</span>,
      key: 'source_type',
      width: '8%',
      render: (_: any, record) =>
        record.is_cross_source ? (
          <Tag style={{ background: isDark ? 'rgba(251, 191, 36, 0.3)' : '#fef3c7', color: isDark ? '#fbbf24' : '#92400e', borderColor: 'transparent' }}>跨源</Tag>
        ) : (
          <Tag style={{ background: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', color: isDark ? '#93c5fd' : '#1d4ed8', borderColor: 'transparent' }}>同源</Tag>
        ),
    },
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>表A</span>,
      dataIndex: 'table_a',
      key: 'table_a',
      width: '18%',
      render: (text: string, record) => (
        <div>
          <div className="font-medium" style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>{text}</div>
          {record.table_a_datasource_name && (
            <div className="text-xs mt-0.5" style={{ color: isDark ? '#64748b' : '#9ca3af' }}>
              <DatabaseOutlined className="mr-1" />
              {record.table_a_datasource_name}
            </div>
          )}
        </div>
      ),
    },
    { title: '', key: 'arrow', width: '4%', render: (_: any, record) => <LinkOutlined style={{ color: record.is_cross_source ? (isDark ? '#fbbf24' : '#fa8c16') : (isDark ? '#60a5fa' : '#1890ff') }} /> },
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>表B</span>,
      dataIndex: 'table_b',
      key: 'table_b',
      width: '18%',
      render: (text: string, record) => (
        <div>
          <div className="font-medium" style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>{text}</div>
          {record.table_b_datasource_name && (
            <div className="text-xs mt-0.5" style={{ color: isDark ? '#64748b' : '#9ca3af' }}>
              <DatabaseOutlined className="mr-1" />
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
          <Tag style={{ background: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', color: isDark ? '#93c5fd' : '#1d4ed8', borderColor: 'transparent' }}>{config.text}</Tag>
        ) : (
          <Tag style={{ background: isDark ? 'rgba(148, 163, 184, 0.2)' : '#f3f4f6', color: isDark ? '#94a3b8' : '#6b7280', borderColor: 'transparent' }}>{type}</Tag>
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
          <Tag style={{ background: isDark ? 'rgba(139, 92, 246, 0.3)' : '#ede9fe', color: isDark ? '#a5b4fc' : '#7c3aed', borderColor: 'transparent' }}>{config.label}</Tag>
        ) : (
          <Tag style={{ background: isDark ? 'rgba(148, 163, 184, 0.2)' : '#f3f4f6', color: isDark ? '#94a3b8' : '#6b7280', borderColor: 'transparent' }}>{cardinality}</Tag>
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
    {
      title: <span style={{ color: isDark ? '#f1f5f9' : '#1e293b' }}>JOIN条件</span>,
      key: 'join_conditions',
      width: '17%',
      render: (_: any, record) => {
        const conditions = record.join_conditions || [];
        if (conditions.length === 0) return <span style={{ color: isDark ? '#64748b' : '#9ca3af' }}>-</span>;
        const first = conditions[0];
        const hasMore = conditions.length > 1;
        return (
          <Tooltip
            title={
              hasMore ? (
                <div className="space-y-1">
                  {conditions.map((cond: any, idx: number) => (
                    <div key={idx} className="text-xs">
                      {cond.local_field} = {cond.remote_field}
                    </div>
                  ))}
                </div>
              ) : null
            }
          >
            <div className="flex items-center gap-1">
              <span className="font-mono text-xs" style={{ color: isDark ? '#60a5fa' : '#2563eb' }}>{first.local_field}</span>
              <span style={{ color: isDark ? '#475569' : '#d1d5db' }}>=</span>
              <span className="font-mono text-xs" style={{ color: isDark ? '#4ade80' : '#16a34a' }}>{first.remote_field}</span>
              {hasMore && <Tag style={{ background: isDark ? 'rgba(59, 130, 246, 0.3)' : '#dbeafe', color: isDark ? '#93c5fd' : '#1d4ed8', borderColor: 'transparent' }} className="ml-1">+{conditions.length - 1}</Tag>}
            </div>
          </Tooltip>
        );
      },
    },
  ];

  const graphDataValid = graphData?.nodes?.length > 0;
  const avgConf = graphDataValid && graphData.edges?.length
    ? (graphData.edges.reduce((s: number, e: any) => s + (e.strength || 0), 0) / graphData.edges.length) * 100
    : 0;

  return (
    <>
      <Tabs defaultActiveKey="graph" size="large">
        <TabPane tab={<span className="dark:text-slate-300"><ApartmentOutlined /> 关系图谱</span>} key="graph">
          <div className="dark:bg-slate-800 dark:rounded-lg dark:p-4">
            {graphDataValid && (
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-6 text-sm text-gray-500 dark:text-slate-400">
                  <span>表: <span className="font-medium text-blue-600 dark:text-blue-400">{graphData.nodes.length}</span></span>
                  <span>关系: <span className="font-medium text-green-600 dark:text-green-400">{graphData.edges.length}</span></span>
                  <span>平均置信度: <span className="font-medium text-orange-600 dark:text-orange-400">{avgConf.toFixed(0)}%</span></span>
                </div>
                <div>
                  <Button
                    danger
                    type="text"
                    icon={<DeleteOutlined />}
                    size="small"
                    onClick={() => setDeleteConfirmVisible(true)}
                    loading={deleting}
                  >
                    清除关系数据
                  </Button>
                </div>
              </div>
            )}
            <Spin spinning={loading}>
              <RelationshipGraph
                data={graphDataValid ? graphData : null}
                loading={loading}
                datasourceNameMap={datasourceNameMap}
                relationshipCards={relationshipCards}
              />
            </Spin>
          </div>
        </TabPane>
        <TabPane
          tab={<span className="dark:text-slate-300"><TableOutlined /> 关系卡片 {relationshipCards.length > 0 ? `(${relationshipCards.length})` : ''}</span>}
          key="cards"
        >
          <div className="dark:bg-slate-800 dark:rounded-lg dark:p-4">
            <div className="p-4 mb-4" style={{ background: isDark ? 'rgba(59, 130, 246, 0.15)' : '#eff6ff', border: `1px solid ${isDark ? 'rgba(59, 130, 246, 0.4)' : '#bfdbfe'}`, borderRadius: '12px' }}>
              <div className="flex items-center gap-3">
                <InfoCircleOutlined className="text-lg" style={{ color: isDark ? '#60a5fa' : '#3b82f6' }} />
                <h3 className="font-medium m-0" style={{ color: isDark ? '#e2e8f0' : '#1e40af' }}>关系卡片 : 为每张表生成的关系说明书，包含该表与其他表的关联关系、JOIN条件建议和数据融合策略。</h3>
              </div>
            </div>
            {/* 搜索框 */}
            <div className="mb-4 dark-global-search">
              <Input
                placeholder="搜索表名..."
                prefix={<Search className="w-4 h-4" style={{ color: isDark ? '#64748b' : '#9ca3af' }} />}
                value={cardSearchText}
                onChange={(e) => setCardSearchText(e.target.value)}
                allowClear
              />
            </div>
            <Spin spinning={loading}>
              {relationshipCards.length === 0 ? (
                <Empty description="暂无关系卡片数据" className="py-12" />
              ) : filteredRelationshipCards.length === 0 ? (
                <Empty description="未找到匹配的数据" className="py-12" />
              ) : (
                <Table
                  columns={cardColumns}
                  dataSource={filteredRelationshipCards}
                  rowKey="table_name"
                  pagination={{ pageSize: 10, showSizeChanger: true, total: filteredRelationshipCards.length }}
                />
              )}
            </Spin>
          </div>
        </TabPane>
        <TabPane
          tab={<span className="dark:text-slate-300"><LinkOutlined /> 关系列表 {tableRelationships.length > 0 ? `(${tableRelationships.length})` : ''}</span>}
          key="relationships"
        >
          <div className="dark:bg-slate-800 dark:rounded-lg dark:p-4">
            <div className="p-4 mb-4" style={{ background: isDark ? 'rgba(59, 130, 246, 0.15)' : '#eff6ff', border: `1px solid ${isDark ? 'rgba(59, 130, 246, 0.4)' : '#bfdbfe'}`, borderRadius: '12px' }}>
              <div className="flex items-center gap-3">
                <InfoCircleOutlined className="text-lg" style={{ color: isDark ? '#60a5fa' : '#3b82f6' }} />
                <h3 className="font-medium m-0" style={{ color: isDark ? '#e2e8f0' : '#1e40af' }}>表关系列表 : 所有表对之间的关系明细，包括关系类型、基数关系、关系强度和JOIN条件。</h3>
              </div>
            </div>
            {/* 搜索框 */}
            <div className="mb-4 dark-global-search">
              <Input
                placeholder="搜索表名、关系类型..."
                prefix={<Search className="w-4 h-4" style={{ color: isDark ? '#64748b' : '#9ca3af' }} />}
                value={relationshipSearchText}
                onChange={(e) => setRelationshipSearchText(e.target.value)}
                allowClear
              />
            </div>
            <Spin spinning={loading}>
              {tableRelationships.length === 0 ? (
                <Empty description="暂无表关系数据" className="py-12" />
              ) : filteredTableRelationships.length === 0 ? (
                <Empty description="未找到匹配的数据" className="py-12" />
              ) : (
                <Table
                  columns={relationshipColumns}
                  dataSource={filteredTableRelationships}
                  rowKey="id"
                  pagination={{ pageSize: 15, showSizeChanger: true, total: filteredTableRelationships.length }}
                  scroll={{ x: true }}
                />
              )}
            </Spin>
          </div>
        </TabPane>
      </Tabs>

      {/* 关系卡片详情弹窗 - 与 GlobalInventoryResultModal 一致 */}
      <Modal
        title={
          <div className="flex items-center gap-2">
            <TableOutlined className="text-blue-500" />
            <span>关系卡片详情</span>
            {!loadingDetail && selectedCardDetail && (
              <>
                <Tag color="blue">{selectedCardDetail.TableInfo?.table_name}</Tag>
                <Tag color="cyan" icon={<DatabaseOutlined />}>{datasourceName}</Tag>
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
          body: { maxHeight: '75vh', overflowY: 'auto', background: isDark ? '#0f172a' : '#ffffff' },
          content: { background: isDark ? '#1e293b' : '#ffffff' },
          mask: { background: isDark ? 'rgba(0, 0, 0, 0.7)' : 'rgba(0, 0, 0, 0.45)' }
        }}
      >
        {loadingDetail ? (
          <div className="flex flex-col items-center justify-center py-16">
            <Spin size="large" />
            <div className="mt-4 text-gray-500">正在加载关系卡片数据...</div>
          </div>
        ) : selectedCardDetail ? (
          <div className="space-y-6">
            <Card size="small" title="基本信息">
              <Descriptions column={2} size="small">
                <Descriptions.Item label="表名">{selectedCardDetail.TableInfo?.table_name}</Descriptions.Item>
                <Descriptions.Item label="所属数据源">
                  <span className="text-cyan-600"><DatabaseOutlined className="mr-1" />{datasourceName}</span>
                </Descriptions.Item>
                <Descriptions.Item label="字段数">{selectedCardDetail.TableInfo?.fields_count}</Descriptions.Item>
                <Descriptions.Item label="主键">{selectedCardDetail.TableInfo?.primary_key || '-'}</Descriptions.Item>
                <Descriptions.Item label="关联表数">{selectedCardDetail.Statistics?.related_tables_count}</Descriptions.Item>
                <Descriptions.Item label="平均置信度">
                  <span className={(selectedCardDetail.Statistics?.avg_confidence || 0) >= 0.85 ? 'text-green-600' : (selectedCardDetail.Statistics?.avg_confidence || 0) >= 0.6 ? 'text-yellow-600' : 'text-red-600'}>
                    {((selectedCardDetail.Statistics?.avg_confidence || 0) * 100).toFixed(0)}%
                  </span>
                </Descriptions.Item>
              </Descriptions>
            </Card>
            {selectedCardDetail.JoinSummary && (
              <Card size="small" title="关系摘要">
                <p className="text-gray-700 m-0">{selectedCardDetail.JoinSummary}</p>
              </Card>
            )}
            {selectedCardDetail.Relationships && selectedCardDetail.Relationships.length > 0 && (
              <Card size="small" title={`关联关系 (${selectedCardDetail.Relationships.length})`}>
                {selectedCardDetail.Relationships.length > 10 ? (
                  <VirtualRelationshipList relationships={selectedCardDetail.Relationships} isDark={isDark} />
                ) : (
                  <div className="space-y-4">
                    {selectedCardDetail.Relationships.map((rel: any, idx: number) => (
                      <div
                        key={idx}
                        style={{
                          border: `1px solid ${rel.is_cross_source ? (isDark ? 'rgba(251, 146, 60, 0.5)' : '#fb923c') : (isDark ? '#334155' : '#e5e7eb')}`,
                          borderRadius: '8px',
                          padding: '16px',
                          background: rel.is_cross_source ? (isDark ? 'rgba(251, 146, 60, 0.1)' : 'rgba(254, 215, 170, 0.3)') : (isDark ? '#1e293b' : '#ffffff')
                        }}
                      >
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2 flex-wrap">
                            {rel.is_cross_source ? <Tag color="orange">跨源</Tag> : <Tag color="blue">同源</Tag>}
                            <Tag color="green">{rel.related_table}</Tag>
                            {rel.related_datasource_name && <Tag color="cyan" icon={<DatabaseOutlined />}>{rel.related_datasource_name}</Tag>}
                            <Tag color={CARDINALITY_CONFIG[rel.relationship_type]?.color || 'default'}>
                              {CARDINALITY_CONFIG[rel.relationship_type]?.label || rel.relationship_type}
                            </Tag>
                          </div>
                          <Progress percent={Math.round((rel.confidence || 0) * 100)} size="small" style={{ width: 100 }} strokeColor={(rel.confidence || 0) >= 0.85 ? '#52c41a' : (rel.confidence || 0) >= 0.6 ? '#faad14' : '#ff4d4f'} />
                        </div>
                        {rel.join_fields?.length > 0 && (
                          <div className="mb-3">
                            <div className="text-sm mb-1" style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>JOIN 字段：</div>
                            {rel.join_fields.map((field: any, fidx: number) => (
                              <div key={fidx} className="flex items-center gap-2 text-sm p-2 rounded" style={{ background: isDark ? '#1e293b' : '#f9fafb' }}>
                                <span className="font-mono" style={{ color: isDark ? '#60a5fa' : '#2563eb' }}>{field.local_field}</span>
                                <span style={{ color: isDark ? '#475569' : '#9ca3af' }}>=</span>
                                <span className="font-mono" style={{ color: isDark ? '#4ade80' : '#16a34a' }}>{field.remote_field}</span>
                                <Tag>{RELATIONSHIP_TYPE_CONFIG[field.relationship_type]?.text || field.relationship_type}</Tag>
                              </div>
                            ))}
                        </div>
                      )}
                      {rel.join_suggestion && (rel.join_suggestion.join_type || rel.join_suggestion.join_condition || rel.join_suggestion.sample_sql || (rel.join_suggestion.use_cases && rel.join_suggestion.use_cases.length > 0)) && (
                        <div className="bg-blue-50 rounded p-3 mb-3">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-sm text-gray-500">推荐连接：</span>
                            <Tag color="blue">{rel.join_suggestion.join_type || 'INNER JOIN'}</Tag>
                          </div>
                          {rel.join_suggestion.join_condition && (
                            <div className="text-sm font-mono text-gray-700 bg-white p-2 rounded mb-2">{rel.join_suggestion.join_condition}</div>
                          )}
                          {rel.join_suggestion.sample_sql && (
                            <div className="mb-2">
                              <div className="text-sm text-gray-500 mb-1">📝 示例SQL：</div>
                              <pre className="bg-gray-800 rounded p-2 overflow-x-auto text-green-400 text-xs font-mono whitespace-pre-wrap break-all m-0">
                                {rel.join_suggestion.sample_sql}
                              </pre>
                            </div>
                          )}
                          {rel.join_suggestion.use_cases?.length > 0 && (
                            <div className="mt-2">
                              <span className="text-sm text-gray-500">💼 适用场景：</span>
                              <ul className="list-disc list-inside text-sm text-gray-600 mt-1">
                                {rel.join_suggestion.use_cases.map((uc: string, ucIdx: number) => <li key={ucIdx}>{uc}</li>)}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}
                      {rel.business_relation && (rel.business_relation.relation_description || rel.business_relation.from_entity || rel.business_relation.to_entity) && (
                        <div className="bg-indigo-50 rounded p-3 mb-3">
                          <div className="text-sm text-indigo-600 font-medium mb-2">📋 业务关系</div>
                          {rel.business_relation.relation_description && <div className="text-sm text-gray-700 mb-2">{rel.business_relation.relation_description}</div>}
                          <div className="flex items-center gap-4 text-xs">
                            {rel.business_relation.from_entity && rel.business_relation.from_role && (
                              <div className="flex items-center gap-1">
                                <span className="text-gray-500">{rel.business_relation.from_entity}:</span>
                                <Tag color="blue" className="m-0">
                                  {rel.business_relation.from_role === 'master' ? '主表' : rel.business_relation.from_role === 'detail' ? '明细表' : rel.business_relation.from_role === 'fact' ? '事实表' : rel.business_relation.from_role === 'dimension' ? '维度表' : rel.business_relation.from_role}
                                </Tag>
                              </div>
                            )}
                            {rel.business_relation.to_entity && rel.business_relation.to_role && (
                              <div className="flex items-center gap-1">
                                <span className="text-gray-500">{rel.business_relation.to_entity}:</span>
                                <Tag color="green" className="m-0">
                                  {rel.business_relation.to_role === 'master' ? '主表' : rel.business_relation.to_role === 'detail' ? '明细表' : rel.business_relation.to_role === 'fact' ? '事实表' : rel.business_relation.to_role === 'dimension' ? '维度表' : rel.business_relation.to_role}
                                </Tag>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                      {rel.fusion_suggestion && (rel.fusion_suggestion.fusion_strategy || rel.fusion_suggestion.aggregation_hint) && (
                        <div className="bg-green-50 rounded p-3 mb-3">
                          <div className="text-sm text-green-700 font-medium mb-2">🔀 融合建议</div>
                          {rel.fusion_suggestion.fusion_strategy && (
                            <div className="text-sm text-gray-700 mb-1">融合策略：{rel.fusion_suggestion.fusion_strategy}</div>
                          )}
                          {rel.fusion_suggestion.aggregation_hint && (
                            <div className="text-sm text-gray-700">聚合提示：{rel.fusion_suggestion.aggregation_hint}</div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                )}
              </Card>
            )}
            {selectedCardDetail.FusionHints && (selectedCardDetail.FusionHints.as_master?.length > 0 || selectedCardDetail.FusionHints.as_detail?.length > 0 || selectedCardDetail.FusionHints.common_joins?.length > 0) && (
              <Card size="small" title="🔀 数据融合建议">
                <div className="space-y-3">
                  {selectedCardDetail.FusionHints.as_master?.length > 0 && (
                    <div>
                      <div className="text-sm font-medium text-gray-700 mb-1">作为主表时：</div>
                      <ul className="list-disc list-inside text-sm text-gray-600 m-0 pl-0">
                        {selectedCardDetail.FusionHints.as_master.map((hint: string, idx: number) => <li key={idx}>{hint}</li>)}
                      </ul>
                    </div>
                  )}
                  {selectedCardDetail.FusionHints.as_detail?.length > 0 && (
                    <div>
                      <div className="text-sm font-medium text-gray-700 mb-1">作为明细表时：</div>
                      <ul className="list-disc list-inside text-sm text-gray-600 m-0 pl-0">
                        {selectedCardDetail.FusionHints.as_detail.map((hint: string, idx: number) => <li key={idx}>{hint}</li>)}
                      </ul>
                    </div>
                  )}
                  {selectedCardDetail.FusionHints.common_joins?.length > 0 && (
                    <div>
                      <div className="text-sm font-medium text-gray-700 mb-1">常见联表场景：</div>
                      <ul className="list-disc list-inside text-sm text-gray-600 m-0 pl-0">
                        {selectedCardDetail.FusionHints.common_joins.map((hint: string, idx: number) => <li key={idx}>{hint}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              </Card>
            )}
          </div>
        ) : null}
      </Modal>
      {/* 清除关系数据确认弹框 */}
      <Modal
        title="确认清除"
        open={deleteConfirmVisible}
        onCancel={() => setDeleteConfirmVisible(false)}
        onOk={handleDeleteRelationships}
        okText="确认清除"
        cancelText="取消"
        okButtonProps={{ danger: true, loading: deleting }}
        centered
      >
        <p style={{ margin: 0 }}>清除后将删除该数据源的所有关系数据，此操作不可恢复。</p>
      </Modal>
      <style>{`
        .dark .dark-global-search .ant-input {
          color: #f1f5f9 !important;
        }
        .dark .dark-global-search .ant-input::placeholder {
          color: #94a3b8 !important;
        }
        html[data-theme="dark"] .dark-global-search .ant-input {
          color: #f1f5f9 !important;
        }
        html[data-theme="dark"] .dark-global-search .ant-input::placeholder {
          color: #94a3b8 !important;
        }
      `}</style>
    </>
  );
};

export default WorkspaceGlobalInventoryTabs;
