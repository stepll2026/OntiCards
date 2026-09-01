"""
@File: relationship_discovery.py
@Description: 关系发现集成服务 - 整合全域/定向盘点结果
@Author: 韩小豪 849631113@qq.com
@Create: 2026-06-01

整合方式：内部 API 调用，不修改原有模块代码
"""

from typing import List, Dict, Any, Optional
from datetime import datetime


class RelationshipDiscovery:
    """关系发现集成服务"""

    def __init__(self, datasource_id: str, user_id: str):
        """初始化

        Args:
            datasource_id: 数据源ID
            user_id: 用户ID
        """
        self.datasource_id = datasource_id
        self.user_id = user_id

    def discover_global(self,
                       schema_name: str = None,
                       confidence_threshold: float = 0.5,
                       tables: List[str] = None) -> Dict[str, Any]:
        """调用全域盘点进行关系发现

        Args:
            schema_name: Schema 名称
            confidence_threshold: 置信度阈值
            tables: 指定表列表（可选，不填则全部）

        Returns:
            关系发现结果
        """
        from controllers.global_inventory.global_inventory_service import run_global_inventory

        try:
            result = run_global_inventory(
                datasource_id=self.datasource_id,
                user_id=self.user_id,
                schema_name=schema_name,
                confidence_threshold=confidence_threshold,
                max_workers=10,
                enable_profiling=True
            )

            if not result.get('success'):
                return {
                    'success': False,
                    'error': result.get('errors', '全域盘点执行失败')
                }

            # 过滤指定表的关系
            relationships = result.get('relationships', [])
            if tables:
                relationships = self._filter_relationships_by_tables(relationships, tables)

            return {
                'success': True,
                'relationships': relationships,
                'cards': result.get('cards', []),
                'statistics': result.get('statistics', {}),
                'tables_count': result.get('tables_count', 0),
                'relationships_count': len(relationships),
                'is_multi_source': result.get('is_multi_source', False),
                'cross_source_count': result.get('cross_source_count', 0)
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'全域盘点调用失败: {str(e)}'
            }

    def discover_target(self, tables: List[str]) -> Dict[str, Any]:
        """调用定向盘点进行关系确认

        Args:
            tables: 指定表列表

        Returns:
            定向盘点结果
        """
        from controllers.target_inventory.target_inventory_tool import TablesAPI, RunAPI
        from flask import request

        try:
            # 使用定向盘点的 API
            tables_api = TablesAPI()
            run_api = RunAPI()

            # 获取表列表（通过定向盘点）
            tables_result = tables_api.get()

            if not tables_result or tables_result[0].get('code') != 200:
                return {
                    'success': False,
                    'error': '获取表列表失败'
                }

            # 过滤指定表
            all_tables = tables_result[0].get('data', {}).get('tables', [])
            filtered_tables = [t for t in all_tables if t.get('table_name') in tables]

            return {
                'success': True,
                'tables': filtered_tables,
                'count': len(filtered_tables)
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'定向盘点调用失败: {str(e)}'
            }

    def _filter_relationships_by_tables(self,
                                        relationships: List[dict],
                                        tables: List[str]) -> List[dict]:
        """过滤只涉及指定表的关系

        Args:
            relationships: 关系列表
            tables: 目标表列表

        Returns:
            过滤后的关系列表
        """
        if not tables:
            return relationships

        filtered = []
        for rel in relationships:
            source_table = rel.get('source_table') or rel.get('table_a')
            target_table = rel.get('target_table') or rel.get('table_b')

            if source_table in tables or target_table in tables:
                filtered.append(rel)

        return filtered

    def build_relationship_summary(self,
                                  global_result: Dict[str, Any] = None,
                                  target_result: Dict[str, Any] = None) -> Dict[str, Any]:
        """构建关系汇总

        Args:
            global_result: 全域盘点结果
            target_result: 定向盘点结果

        Returns:
            关系汇总
        """
        summary = {
            'total_relationships': 0,
            'total_tables': 0,
            'cross_source_relationships': 0,
            'high_confidence_relationships': 0,
            'tables_with_relationships': set(),
            'relationship_types': {}
        }

        if global_result and global_result.get('success'):
            relationships = global_result.get('relationships', [])

            summary['total_relationships'] = len(relationships)
            summary['total_tables'] = global_result.get('tables_count', 0)
            summary['cross_source_relationships'] = global_result.get('cross_source_count', 0)

            for rel in relationships:
                # 统计高置信度关系
                confidence = rel.get('confidence', 0)
                if confidence >= 0.8:
                    summary['high_confidence_relationships'] += 1

                # 统计涉及表
                source = rel.get('source_table') or rel.get('table_a')
                target = rel.get('target_table') or rel.get('table_b')
                if source:
                    summary['tables_with_relationships'].add(source)
                if target:
                    summary['tables_with_relationships'].add(target)

                # 统计关系类型
                rel_type = rel.get('relationship_type') or rel.get('relation_type', 'unknown')
                summary['relationship_types'][rel_type] = summary['relationship_types'].get(rel_type, 0) + 1

        if target_result and target_result.get('success'):
            tables = target_result.get('tables', [])
            summary['total_tables'] = max(summary['total_tables'], len(tables))

        # 转换 set 为 list
        summary['tables_with_relationships'] = list(summary['tables_with_relationships'])
        summary['relationship_coverage'] = round(
            len(summary['tables_with_relationships']) / max(summary['total_tables'], 1) * 100,
            2
        )

        return summary


def get_relationship_for_report(datasource_id: str,
                                 user_id: str,
                                 include_relationship: bool = True,
                                 schema_name: str = None,
                                 tables: List[str] = None) -> Dict[str, Any]:
    """获取关系发现结果（便捷函数）

    Args:
        datasource_id: 数据源ID
        user_id: 用户ID
        include_relationship: 是否包含关系发现
        schema_name: Schema 名称
        tables: 指定表列表

    Returns:
        关系发现结果
    """
    if not include_relationship:
        return {'success': True, 'relationships': [], 'summary': {}}

    discoverer = RelationshipDiscovery(datasource_id, user_id)

    # 调用全域盘点
    global_result = discoverer.discover_global(
        schema_name=schema_name,
        confidence_threshold=0.5,
        tables=tables
    )

    # 构建汇总
    summary = discoverer.build_relationship_summary(global_result=global_result)

    return {
        'success': global_result.get('success', False),
        'relationships': global_result.get('relationships', []),
        'cards': global_result.get('cards', []),
        'summary': summary,
        'tables_count': global_result.get('tables_count', 0),
        'relationships_count': global_result.get('relationships_count', 0)
    }
