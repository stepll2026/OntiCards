'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  Search,
  Filter,
  CreditCard,
  Grid3X3,
  List,
  X,
  ExternalLink,
  Sparkles,
} from 'lucide-react';
import { getDataCards, DataCardItem } from '@/api/datacard';
import { getUserDataSources } from '@/api/datasource';

const getDbTypeColor = (dbType: string) => {
  const colors: Record<string, string> = {
    mysql: 'bg-blue-100 text-blue-600',
    postgresql: 'bg-emerald-100 text-emerald-600',
    mssql: 'bg-purple-100 text-purple-600',
    oracle: 'bg-red-100 text-red-600',
    sqlite: 'bg-yellow-100 text-yellow-600',
    trino: 'bg-orange-100 text-orange-600',
    kingbase: 'bg-cyan-100 text-cyan-600',
    oceanbase: 'bg-sky-100 text-sky-600',
    dm: 'bg-indigo-100 text-indigo-600',
  };
  return colors[dbType?.toLowerCase()] || 'bg-gray-100 text-gray-600';
};

const formatDate = (dateString: string) => {
  if (!dateString) return '-';
  const date = new Date(dateString);
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

const parseCardData = (cardData: string | any): any => {
  if (typeof cardData === 'string') {
    try {
      return JSON.parse(cardData);
    } catch {
      return null;
    }
  }
  return cardData;
};

const ExplorePage = () => {
  const [cardItems, setCardItems] = useState<DataCardItem[]>([]);
  const [workspaces, setWorkspaces] = useState<
    { id: string; name: string; db_type: string }[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedWorkspace, setSelectedWorkspace] = useState('all');
  const [selectedFillStatus, setSelectedFillStatus] = useState('all');
  const [selectedViewType, setSelectedViewType] = useState('all');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [showFilters, setShowFilters] = useState(false);
  const [totalCards, setTotalCards] = useState(0);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const cardsResponse = await getDataCards({
          parse_json: true,
          page: 1,
          page_size: 50,
        });
        if (cardsResponse.code === 200 && cardsResponse.data) {
          setCardItems(cardsResponse.data.items || []);
          setTotalCards(cardsResponse.data.total_cards || 0);
        }

        const wsResponse = await getUserDataSources({
          page: 1,
          page_size: 50,
        });
        if (wsResponse.code === 200 && wsResponse.data) {
          setWorkspaces(
            wsResponse.data.items?.map((item: any) => ({
              id: item.id,
              name: item.connect_name,
              db_type: item.db_type,
            })) || [],
          );
        }
      } catch (error) {
        console.error('获取数据失败:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const allCards = useMemo(() => {
    return cardItems.flatMap((item) =>
      item.cards.map((card) => ({ ...card, datasource: item.datasource })),
    );
  }, [cardItems]);

  const filteredCards = useMemo(() => {
    let result = allCards;
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter((card) => {
        const cardData = parseCardData(card.card_data);
        return (
          card.table_name?.toLowerCase().includes(query) ||
          cardData?.Abstract?.toLowerCase().includes(query) ||
          card.connect_name?.toLowerCase().includes(query)
        );
      });
    }
    if (selectedWorkspace !== 'all')
      result = result.filter((card) => card.connect_name === selectedWorkspace);
    if (selectedFillStatus === 'filled')
      result = result.filter((card) => card.is_filled === true);
    else if (selectedFillStatus === 'unfilled')
      result = result.filter((card) => !card.is_filled);
    if (selectedViewType === 'table')
      result = result.filter((card) => card.is_view !== true);
    else if (selectedViewType === 'view')
      result = result.filter((card) => card.is_view === true);
    return result;
  }, [
    allCards,
    searchQuery,
    selectedWorkspace,
    selectedFillStatus,
    selectedViewType,
  ]);

  const clearFilters = () => {
    setSearchQuery('');
    setSelectedWorkspace('all');
    setSelectedFillStatus('all');
    setSelectedViewType('all');
  };

  const hasActiveFilters =
    searchQuery ||
    selectedWorkspace !== 'all' ||
    selectedFillStatus !== 'all' ||
    selectedViewType !== 'all';

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold mb-1 text-slate-900">
            探索
          </h1>
          <p className="text-sm text-slate-500">
            浏览并搜索您的数据卡片
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-4 py-2 rounded-[12px] text-sm font-medium transition-colors ${
              showFilters || hasActiveFilters
                ? 'bg-indigo-100 text-indigo-600'
                : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            <Filter className="w-4 h-4" />
            筛选
            {hasActiveFilters && (
              <span className="ml-1 px-1.5 py-0.5 bg-indigo-500 text-white text-xs rounded-full">
                {[
                  searchQuery,
                  selectedWorkspace,
                  selectedFillStatus,
                  selectedViewType,
                ].filter((v) => v && v !== 'all' && v !== '').length}
              </span>
            )}
          </button>
          <div className="flex items-center bg-white rounded-[12px] border border-slate-200 p-1">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-lg transition-colors ${
                viewMode === 'grid'
                  ? 'bg-indigo-100 text-indigo-600'
                  : 'text-slate-400 hover:text-slate-600'
              }`}
            >
              <Grid3X3 className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded-lg transition-colors ${
                viewMode === 'list'
                  ? 'bg-indigo-100 text-indigo-600'
                  : 'text-slate-400 hover:text-slate-600'
              }`}
            >
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
        <input
          type="text"
          placeholder="搜索表名、描述或字段..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-12 pr-4 py-3 bg-white border border-slate-200 rounded-[16px] text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="absolute right-4 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-slate-100 transition-colors"
          >
            <X className="w-4 h-4 text-slate-400" />
          </button>
        )}
      </div>

      {showFilters && (
        <div className="bg-white rounded-[20px] border border-slate-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-slate-900">筛选</h3>
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
              >
                清除全部
              </button>
            )}
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-slate-500 mb-2">
                数据源
              </label>
              <select
                value={selectedWorkspace}
                onChange={(e) => setSelectedWorkspace(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-[10px] text-sm"
              >
                <option value="all">全部数据源</option>
                {workspaces.map((ws) => (
                  <option key={ws.id} value={ws.name}>
                    {ws.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-2">
                字段状态
              </label>
              <select
                value={selectedFillStatus}
                onChange={(e) => setSelectedFillStatus(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-[10px] text-sm"
              >
                <option value="all">全部</option>
                <option value="filled">AI 已填充</option>
                <option value="unfilled">未填充</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-2">类型</label>
              <select
                value={selectedViewType}
                onChange={(e) => setSelectedViewType(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-[10px] text-sm"
              >
                <option value="all">全部</option>
                <option value="table">表</option>
                <option value="view">视图</option>
              </select>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between text-sm">
        <p className="text-slate-500">
          {loading
            ? '加载中...'
            : `已显示 ${filteredCards.length} / ${totalCards} 个数据卡片`}
        </p>
      </div>

      {loading ? (
        <div className={viewMode === 'grid' ? 'grid grid-cols-3 gap-4' : 'space-y-3'}>
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="bg-white p-5 rounded-[20px] border border-slate-200 animate-pulse"
            >
              <div className="h-5 bg-slate-200 rounded w-32 mb-3"></div>
              <div className="h-4 bg-slate-100 rounded w-48 mb-2"></div>
              <div className="h-3 bg-slate-100 rounded w-24"></div>
            </div>
          ))}
        </div>
      ) : filteredCards.length === 0 ? (
        <div className="bg-white rounded-[20px] border border-slate-200 p-12 text-center">
          <CreditCard className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-slate-900 mb-2">
            未找到结果
          </h3>
          <p className="text-sm text-slate-500 mb-6">
            {hasActiveFilters
              ? '请调整筛选条件或搜索关键词'
              : '暂无数据卡片'}
          </p>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-[12px] text-sm font-medium"
            >
              清除筛选
            </button>
          )}
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-3 gap-4">
          {filteredCards.map((card) => {
            const cardData = parseCardData(card.card_data);
            const fieldCount = cardData?.SQLMeta?.columns?.length || 0;
            const displayFields =
              cardData?.SQLMeta?.columns
                ?.slice(0, 3)
                .map((col: any) => col.comment || col.name) || [];
            return (
              <div
                key={card.doc_id}
                className="group bg-white p-5 rounded-[20px] border border-slate-200 hover:shadow-lg hover:border-indigo-200 transition-all cursor-pointer"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-1 rounded-full text-xs font-medium ${getDbTypeColor(card.datasource?.db_type)}`}
                    >
                      {(card.datasource?.db_type || 'DB').toUpperCase()}
                    </span>
                    {card.is_view && (
                      <span className="px-2 py-1 rounded-full text-xs bg-orange-100 text-orange-600">
                        视图
                      </span>
                    )}
                  </div>
                  <ExternalLink className="w-4 h-4 text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <h4 className="font-semibold text-slate-900 mb-1 group-hover:text-indigo-600 transition-colors">
                  {card.table_name}
                </h4>
                <p className="text-xs text-slate-500 mb-3">{card.connect_name}</p>
                <p className="text-xs text-slate-600 mb-4 line-clamp-2">
                  {cardData?.Abstract || '暂无描述'}
                </p>
                <div className="flex flex-wrap gap-1.5 mb-4">
                  {displayFields.slice(0, 3).map((field: string, idx: number) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 bg-slate-100 text-slate-600 text-xs rounded"
                    >
                      {field}
                    </span>
                  ))}
                  {fieldCount > 3 && (
                    <span className="px-2 py-0.5 text-slate-400 text-xs">
                      +{fieldCount - 3} more
                    </span>
                  )}
                </div>
                <div className="flex items-center justify-between pt-3 border-t border-slate-100">
                  <div className="flex items-center gap-2">
                    {card.is_filled && (
                      <span className="flex items-center gap-1 text-xs text-purple-600">
                        <Sparkles className="w-3 h-3" />
                        AI 已填充
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-slate-400">
                    {fieldCount} 个字段
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="bg-white rounded-[20px] border border-slate-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase">
                  表
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase">
                  数据源
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase">
                  类型
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase">
                  状态
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase">
                  字段
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase">
                  更新日期
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredCards.map((card) => {
                const cardData = parseCardData(card.card_data);
                const fieldCount = cardData?.SQLMeta?.columns?.length || 0;
                return (
                  <tr
                    key={card.doc_id}
                    className="hover:bg-slate-50/50 transition-colors cursor-pointer"
                  >
                    <td className="px-4 py-3">
                      <span className="font-medium text-slate-900">
                        {card.table_name}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600">
                      {card.connect_name}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-1 rounded-full text-xs font-medium ${getDbTypeColor(card.datasource?.db_type)}`}
                      >
                        {(card.datasource?.db_type || 'DB').toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {card.is_filled && (
                          <Sparkles className="w-3 h-3 text-purple-600" />
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600">
                      {fieldCount}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-500">
                      {formatDate(card.updated_at)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default ExplorePage;

