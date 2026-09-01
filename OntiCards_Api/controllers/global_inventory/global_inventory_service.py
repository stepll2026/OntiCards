"""
 @File: global_inventory_service.py
 @Description: 全域盘点服务 - 对数据源中的所有表进行关系盘点和发现（支持单源和多源）
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-02-06

 功能说明：
 1. 自动发现数据源中所有表之间的关系（支持单数据源和多数据源）
 2. 生成以表为中心的关系卡片（每张表一张关系卡片）
 3. 关系卡片入库（数据库+向量库），用于NL2SQL时的联表查询和结果融合
 4. 多数据源场景下，自动标记跨源关系，用于多源异构融合
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import uuid

# 北京时区（东八区）
tz_cst = timezone(timedelta(hours=8))

from extensions.ext_database import db
from models.global_inventory import TableRelationship, TableRelationshipCard
from models.datasource_infos import DatasourceInfo
from models.datacards_datasource import DataCardDataSource

from controllers.target_inventory.table_relationship_inference import (
    infer_table_relationships,
    group_relationships_by_table_pair
)
from controllers.datasource.datasource_tool import calculate_schema_hash_from_datasource


class GlobalInventoryService:
    """
    全域盘点服务

    主要功能：
    1. 对数据源中的所有表进行关系盘点（支持单源和多源）
    2. 生成以表为中心的关系卡片
    3. 将关系卡片入库（数据库+向量库）
    4. 多源场景下标记跨源关系
    """

    def __init__(
        self,
        datasource_id: Union[str, List[str]],
        user_id: str,
        schema_name: str = None,
        enable_profiling: bool = True
    ):
        """
        初始化服务

        Args:
            datasource_id: 数据源ID，可以是单个ID字符串或多个ID的列表
            user_id: 用户ID
            schema_name: Schema名称（可选，默认从数据源配置中获取）
            enable_profiling: 是否启用字段画像（默认True，提升准确性）
        """
        # 统一处理为列表
        if isinstance(datasource_id, str):
            self.datasource_ids = [datasource_id]
        else:
            self.datasource_ids = datasource_id

        self.is_multi_source = len(self.datasource_ids) > 1
        self.primary_datasource_id = self.datasource_ids[0]  # 主数据源ID（用于存储）

        self.user_id = user_id
        self.schema_name = schema_name
        self.enable_profiling = enable_profiling

        # 获取所有数据源信息
        self.datasources = {}  # {datasource_id: DatasourceInfo}
        self.datasource_names = {}  # {datasource_id: name}
        for ds_id in self.datasource_ids:
            ds = self._get_datasource(ds_id)
            if ds:
                self.datasources[ds_id] = ds
                self.datasource_names[ds_id] = ds.connect_name or ds_id
            else:
                raise ValueError(f"数据源不存在: {ds_id}")

        # 如果没有指定schema_name，从主数据源中获取
        if not self.schema_name:
            primary_ds = self.datasources.get(self.primary_datasource_id)
            self.schema_name = getattr(primary_ds, 'schema_name', None) or 'public'

        # 计算schema_hash（改进版：基于真实表结构）
        from controllers.datasource.datasource_tool import calculate_schema_hash_from_datasource

        if self.is_multi_source:
            # 多数据源：使用主数据源的hash（或者可以考虑组合多个hash）
            # 这里简化处理，使用主数据源的hash
            self.schema_hash = calculate_schema_hash_from_datasource(
                datasource_id=self.primary_datasource_id,
                schema_name=self.schema_name
            )
            print(f"[全域盘点] 多数据源模式，使用主数据源的schema_hash")
        else:
            # 单数据源：直接计算
            self.schema_hash = calculate_schema_hash_from_datasource(
                datasource_id=self.primary_datasource_id,
                schema_name=self.schema_name
            )

        # 获取用户的向量库类名
        from models.users import User
        user = db.session.query(User).filter(User.id == user_id).first()
        self.weaviate_class_name = user.weaviate_class_name if user else None

        # 字段画像缓存
        self.field_profiles = {}

    def _get_datasource(self, datasource_id: str) -> Optional[DatasourceInfo]:
        """获取数据源信息"""
        from uuid import UUID as PyUUID
        try:
            ds_uuid = PyUUID(str(datasource_id))
            return db.session.query(DatasourceInfo).filter(
                DatasourceInfo.id == ds_uuid
            ).first()
        except ValueError:
            return None

    def discover_all_relationships(
        self,
        confidence_threshold: float = 0.5,
        max_workers: int = 12,  # 外层并行度（原10）
        progress_callback: callable = None
    ) -> Dict[str, Any]:
        """
        发现数据源中所有表之间的关系（支持单源和多源）

        Args:
            confidence_threshold: 置信度阈值
            max_workers: 最大并行工作线程数
            progress_callback: 进度回调函数 callback(current, total, message)

        Returns:
            {
                "success": True,
                "tables_count": 10,
                "relationships_count": 25,
                "cards_count": 10,
                "relationships": [...],
                "cards": [...],
                "statistics": {...},
                "is_multi_source": False,
                "cross_source_count": 0
            }
        """
        result = {
            "success": False,
            "tables_count": 0,
            "relationships_count": 0,
            "cards_count": 0,
            "relationships": [],
            "cards": [],
            "statistics": {},
            "errors": [],
            "is_multi_source": self.is_multi_source,
            "datasource_ids": self.datasource_ids,
            "cross_source_count": 0
        }

        try:
            # Step 1: 获取所有表的结构信息 + 字段画像
            if progress_callback:
                progress_callback(0, 100, "正在获取表结构信息...")

            tables_info, table_datasource_map = self._get_all_tables_info()
            if not tables_info:
                result["errors"].append("无法获取表结构信息，请确保已对数据源进行盘点生成数据卡片")
                return result
    
            # 保存到实例变量，供后续方法使用
            self.table_datasource_map = table_datasource_map
    
            # 构建 datasource_schema_map（数据源ID -> schema_hash 的映射）
            self.datasource_schema_map = {}
            for ds_id in self.datasource_ids:
                ds = self.datasources.get(ds_id)
                if ds:
                    ds_schema_name = getattr(ds, 'schema_name', None) or 'public'
                    # 使用改进的schema_hash计算方法
                    ds_schema_hash = calculate_schema_hash_from_datasource(
                        datasource_id=ds_id,
                        schema_name=ds_schema_name
                    )
                    self.datasource_schema_map[str(ds_id)] = ds_schema_hash
    
            result["tables_count"] = len(tables_info)
            print(f"[全域盘点] 获取到 {len(tables_info)} 张表的结构信息")
    
            # Step 1.5: 生成字段画像（如果启用）
            if self.enable_profiling:
                if progress_callback:
                    progress_callback(5, 100, "正在生成字段画像...")
    
                print(f"[全域盘点] 🔍 开始生成字段画像 (并发数: 4)...")
    
            try:
                self._generate_field_profiles(tables_info, progress_callback)
                print(f"[全域盘点] ✓ 字段画像生成完成: {len(self.field_profiles)} 个字段")
            except Exception as e:
                print(f"[全域盘点] 字段画像生成失败（将使用基础模式）: {e}")
                # 画像生成失败不影响主流程，继续执行
                self.field_profiles = {}
    
            if len(tables_info) < 2:
                result["success"] = True
                result["errors"].append("表数量少于2张，无法进行关系发现")
                return result
    
            # Step 2: 推断所有表之间的关系
            if progress_callback:
                progress_callback(20, 100, "正在分析表关系...")
    
            # ✅ 阈值生效位置：这里打印实际生效的阈值，便于调试和确认
            # 根据阈值档位判断对 LLM 的影响程度
            from controllers.target_inventory.table_relationship_inference import _threshold_to_tier
            threshold_tier = _threshold_to_tier(confidence_threshold)
            tier_desc_map = {
                "very_high": "很高（≥0.85）：LLM 仅输出强外键证据",
                "high": "高（≥0.7）：LLM 至少 2 项证据才输出",
                "medium": "中（0.5）：LLM 至少 1 项证据输出",
                "low": "低（<0.5）：LLM 鼓励发现更多潜在关联"
            }
            tier_desc = tier_desc_map.get(threshold_tier, "默认")
            print(f"[全域盘点] 配置: 置信度阈值={confidence_threshold}, 档位={threshold_tier} ({tier_desc}), 最大并行数={max_workers}")
    
            relationships = self._infer_all_relationships(
                tables_info,
                confidence_threshold,
                max_workers,
                progress_callback
            )
    
            # 标记数据源信息（单源和多源都需要）
            relationships = self._mark_cross_source_relationships(relationships, table_datasource_map)
            if self.is_multi_source:
                cross_source_count = sum(1 for r in relationships if r.get("is_cross_source", False))
                result["cross_source_count"] = cross_source_count
                print(f"[全域盘点] 其中跨源关系: {cross_source_count} 个")
    
            result["relationships"] = relationships
            result["relationships_count"] = len(relationships)
            print(f"[全域盘点] 发现 {len(relationships)} 个表关系")
    
            # Step 3: 生成以表为中心的关系卡片
            if progress_callback:
                progress_callback(75, 100, "正在生成关系卡片...")
    
            cards = self._generate_table_centric_cards(relationships, tables_info)
            result["cards"] = cards
            result["cards_count"] = len(cards)
            print(f"[全域盘点] 生成 {len(cards)} 张关系卡片")
    
            # Step 4: 持久化（数据库+向量库）
            if progress_callback:
                progress_callback(90, 100, "正在保存关系卡片...")
    
            # 先删除该数据源的旧数据，确保每次盘点都是全新的开始
            self._cleanup_old_data()
            print(f"[全域盘点] 已清理该数据源的旧关系数据")
    
            persist_result = self._persist_results(relationships, cards)
            result["persist_result"] = persist_result
    
            # Step 5: 生成统计信息
            result["statistics"] = self._generate_statistics(relationships, cards)
    
            result["success"] = True
    
            # 打印完成汇总
            print(f"[全域盘点] ═══════════════════════════════════════════════════════")
            print(f"[全域盘点] ✅ 全域盘点完成!")
            print(f"[全域盘点]    • 发现关系: {len(relationships)} 个")
            print(f"[全域盘点]    • 生成卡片: {len(cards)} 张")
            if self.is_multi_source and result.get("cross_source_count"):
                print(f"[全域盘点]    • 跨源关系: {result['cross_source_count']} 个")
            print(f"[全域盘点] ═══════════════════════════════════════════════════════")
    
            if progress_callback:
                progress_callback(100, 100, "关系发现完成")

        except Exception as e:
            import traceback
            traceback.print_exc()
            result["errors"].append(str(e))

        return result

    def _mark_cross_source_relationships(
        self,
        relationships: List[Dict[str, Any]],
        table_datasource_map: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        标记跨源关系

        Args:
            relationships: 关系列表
            table_datasource_map: 表所属数据源映射

        Returns:
            标记后的关系列表
        """
        for rel in relationships:
            from_table = rel.get("from_table", "")
            to_table = rel.get("to_table", "")

            from_ds_id = table_datasource_map.get(from_table, self.primary_datasource_id)
            to_ds_id = table_datasource_map.get(to_table, self.primary_datasource_id)

            # 标记是否跨源
            is_cross_source = from_ds_id != to_ds_id
            rel["is_cross_source"] = is_cross_source
            rel["from_datasource_id"] = from_ds_id
            rel["to_datasource_id"] = to_ds_id
            rel["from_datasource_name"] = self.datasource_names.get(from_ds_id, "")
            rel["to_datasource_name"] = self.datasource_names.get(to_ds_id, "")
            # 添加 schema_hash 信息
            rel["from_schema_hash"] = self.datasource_schema_map.get(str(from_ds_id), self.schema_hash)
            rel["to_schema_hash"] = self.datasource_schema_map.get(str(to_ds_id), self.schema_hash)

        return relationships

    def _get_all_tables_info(self) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, str]]:
        """
        获取所有数据源中所有表的结构信息

        Returns:
            (tables_info, table_datasource_map)
            - tables_info: {table_name: [field_info, ...], ...}
            - table_datasource_map: {table_name: datasource_id, ...} 表所属数据源映射
        """
        from uuid import UUID as PyUUID  # 添加 UUID 导入
        tables_info = {}
        table_datasource_map = {}  # 记录每张表属于哪个数据源

        # 从所有数据源的数据卡片中获取表结构信息
        for ds_id in self.datasource_ids:
            # 确保 ds_id 是有效的 UUID
            try:
                ds_uuid = PyUUID(str(ds_id))
            except ValueError:
                print(f"[全域盘点] ⚠️ 无效的数据源ID: {ds_id}，跳过")
                continue

            datacards = db.session.query(DataCardDataSource).filter(
                DataCardDataSource.datasource_id == ds_uuid
            ).all()

            ds_name = self.datasource_names.get(ds_id, ds_id)
            print(f"[全域盘点] 从数据源 {ds_name} 获取表信息...")

            for card in datacards:
                try:
                    card_data = card.card_data
                    if isinstance(card_data, str):
                        card_data = json.loads(card_data)

                    # 获取表名
                    table_name = card.table_name
                    if not table_name:
                        sql_meta = card_data.get("SQLMeta", {})
                        table_name = sql_meta.get("table", "")

                    if not table_name:
                        continue

                    # 多源场景下，如果表名重复，添加数据源前缀区分
                    original_table_name = table_name
                    if self.is_multi_source and table_name in tables_info:
                        # 检查是否来自不同数据源
                        existing_ds_id = table_datasource_map.get(table_name)
                        if existing_ds_id and existing_ds_id != ds_id:
                            # 表名冲突，使用数据源名称作为前缀
                            table_name = f"{ds_name}.{table_name}"
                            print(f"[全域盘点]   表名冲突，重命名为: {table_name}")

                    # 获取字段信息
                    sql_meta = card_data.get("SQLMeta", {})
                    columns = sql_meta.get("columns", [])

                    if columns:
                        # 转换为标准格式
                        fields = []
                        for col in columns:
                            field_info = {
                                "column_name": col.get("name", ""),
                                "column_type": col.get("type", ""),
                                "column_comment": col.get("comment", "") or "",
                                "datasource_id": ds_id,  # 添加数据源ID
                                "datasource_name": ds_name,  # 添加数据源名称
                                "original_table_name": original_table_name  # 原始表名
                            }
                            fields.append(field_info)
                        tables_info[table_name] = fields
                        table_datasource_map[table_name] = str(ds_id)  # 确保存储为字符串
                        # 同时存储 UUID 形式的映射（用于数据库查询）
                        if not hasattr(self, '_datasource_uuid_map'):
                            self._datasource_uuid_map = {}
                        try:
                            from uuid import UUID
                            self._datasource_uuid_map[table_name] = UUID(str(ds_id))
                        except ValueError:
                            pass

                except Exception as e:
                    print(f"[全域盘点] 解析表 {card.table_name} 失败: {e}")
                    continue

            print(f"[全域盘点]   获取到 {len([t for t, d in table_datasource_map.items() if d == ds_id])} 张表")

        print(f"[全域盘点] 共获取 {len(tables_info)} 张表（来自 {len(self.datasource_ids)} 个数据源）")
        return tables_info, table_datasource_map

    def _generate_field_profiles(
        self,
        tables_info: Dict[str, List[Dict[str, Any]]],
        progress_callback: callable = None,
        sample_size: int = 100,
        max_workers: int = 4  # 并行工作线程数
    ):
        """
        为所有表的字段生成画像信息（并行版本）

        Args:
            tables_info: 表信息字典
            progress_callback: 进度回调
            sample_size: 采样大小
            max_workers: 并行工作线程数（默认4）
        """
        from controllers.target_inventory.value_profiling import profile_columns
        from sqlalchemy import create_engine
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        try:
            # 获取数据库连接信息
            primary_ds = self.datasources.get(self.primary_datasource_id)
            if not primary_ds:
                raise ValueError(f"主数据源 {self.primary_datasource_id} 不存在")

            connect_info = primary_ds.connect_info

            total_tables = len(tables_info)
            completed = 0
            counter_lock = threading.Lock()  # 线程安全计数器

            def process_single_table(table_name: str, fields: List[Dict]) -> Dict[str, Any]:
                """处理单张表的画像生成（在线程中执行）"""
                # 每个线程创建独立的 engine，避免连接池冲突
                thread_engine = create_engine(
                    connect_info,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    pool_size=2,  # 限制连接池大小
                    max_overflow=2
                )
                try:
                    # 获取所有字段名
                    column_names = [f.get("column_name") for f in fields if f.get("column_name")]
                    if not column_names:
                        return {}

                    # 构建完整表名（带schema）
                    if self.schema_name and self.schema_name != 'public':
                        table_full_name = f'"{self.schema_name}"."{table_name}"'
                    else:
                        table_full_name = f'"{table_name}"'

                    # 调用画像生成函数
                    profiles = profile_columns(
                        thread_engine,
                        table_full_name,
                        column_names,
                        sample_size=sample_size
                    )

                    # 转换为 {profile_key: profile} 格式
                    result = {}
                    for col_name, profile in profiles.items():
                        profile_key = f"{table_name}.{col_name}"
                        result[profile_key] = profile

                    return result
                finally:
                    thread_engine.dispose()

            # 使用线程池并行处理
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_table = {
                    executor.submit(process_single_table, table_name, fields): table_name
                    for table_name, fields in tables_info.items()
                }

                # 收集结果
                for future in as_completed(future_to_table):
                    table_name = future_to_table[future]
                    try:
                        table_profiles = future.result()
                        # 合并到总画像（线程安全）
                        with counter_lock:
                            self.field_profiles.update(table_profiles)
                            completed += 1

                            # 更新进度
                            if progress_callback:
                                progress = 10 + int(10 * completed / total_tables)
                                progress_callback(progress, 100, f"正在生成字段画像 ({completed}/{total_tables})...")

                    except Exception as e:
                        print(f"[全域盘点] 生成表 {table_name} 的字段画像失败: {e}")

        except Exception as e:
            print(f"[全域盘点] 字段画像生成过程出错: {e}")
            raise

    def _infer_all_relationships(
        self,
        tables_info: Dict[str, List[Dict[str, Any]]],
        confidence_threshold: float,
        max_workers: int,
        progress_callback: callable = None
    ) -> List[Dict[str, Any]]:
        """
        推断所有表之间的关系

        采用所有表两两配对的方式进行关系推断
        """
        from flask import current_app

        all_relationships = []
        table_names = list(tables_info.keys())

        # 生成所有需要分析的表对
        table_pairs = []
        for i in range(len(table_names)):
            for j in range(i + 1, len(table_names)):
                table_pairs.append((table_names[i], table_names[j]))

        total_pairs = len(table_pairs)
        print(f"[全域盘点] ═══════════════════════════════════════════════════════")
        print(f"[全域盘点] 📊 全域盘点开始执行")
        print(f"[全域盘点]    • 数据源: {self.datasource_names.get(self.primary_datasource_id, self.primary_datasource_id)}")
        print(f"[全域盘点]    • 表数量: {len(table_names)} 张")
        print(f"[全域盘点]    • 表对数量: {total_pairs} 对")
        print(f"[全域盘点]    • 并发线程数: {max_workers}")
        print(f"[全域盘点] ═══════════════════════════════════════════════════════")

        if total_pairs == 0:
            return []

        # 获取当前 Flask app，用于在线程中创建应用上下文
        app = current_app._get_current_object()

        # 使用线程池并行分析
        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for table_a, table_b in table_pairs:
                future = executor.submit(
                    self._analyze_table_pair_with_context,
                    app,  # 传入 app 对象
                    table_a, tables_info[table_a],
                    table_b, tables_info[table_b],
                    confidence_threshold
                )
                futures[future] = (table_a, table_b)

            for future in as_completed(futures):
                table_a, table_b = futures[future]
                completed += 1

                # 计算进度百分比
                progress_percent = int(100 * completed / total_pairs)
                bar_len = 20
                filled = int(bar_len * completed / total_pairs)
                bar = "█" * filled + "░" * (bar_len - filled)

                try:
                    relationships = future.result()
                    rel_count = len(relationships) if relationships else 0
                    if relationships:
                        all_relationships.extend(relationships)
                    # 简洁的进度日志（每完成10对或最后一对时打印）
                    if completed % max(1, total_pairs // 10) == 0 or completed == total_pairs:
                        print(f"[全域盘点] [{bar}] {progress_percent:3d}% ({completed:3d}/{total_pairs}) | {table_a} <-> {table_b} ({rel_count}个关系)")
                except Exception as e:
                    print(f"[全域盘点] [{bar}] {progress_percent:3d}% ({completed:3d}/{total_pairs}) | {table_a} <-> {table_b} ❌ {e}")

                # 更新进度
                if progress_callback:
                    # 字段画像占 10%，表关系分析占 20-75%，共55%
                    progress = 20 + int(55 * completed / total_pairs)
                    progress_callback(progress, 100, f"正在分析表关系 ({completed}/{total_pairs})...")

        return all_relationships

    def _analyze_table_pair_with_context(
        self,
        app,
        table_a: str, fields_a: List[Dict[str, Any]],
        table_b: str, fields_b: List[Dict[str, Any]],
        confidence_threshold: float
    ) -> List[Dict[str, Any]]:
        """
        在 Flask 应用上下文中分析两张表之间的关系
        """
        with app.app_context():
            return self._analyze_table_pair(
                table_a, fields_a,
                table_b, fields_b,
                confidence_threshold
            )

    def _analyze_table_pair(
        self,
        table_a: str, fields_a: List[Dict[str, Any]],
        table_b: str, fields_b: List[Dict[str, Any]],
        confidence_threshold: float
    ) -> List[Dict[str, Any]]:
        """
        分析两张表之间的关系（增强版：支持字段画像）

        采用混合策略：
        1. 规则匹配（快速、确定性高）
        2. 字段画像验证（客观数据支持）
        3. LLM 语义分析（深度理解）

        注意：双向分析是必要的，因为：
        - A->B 检查 A 的字段是否能关联到 B
        - B->A 检查 B 的字段是否能关联到 A
        这两种关系可能不同（例如：user.org_id -> org.id 与 org.admin_id -> user.id）
        """
        # 使用增强版表关系推断（传递字段画像和所有优化参数）
        relationships = infer_table_relationships(
            target_tables_info={table_a: fields_a},
            ref_tables_info={table_b: fields_b},
            confidence_threshold=confidence_threshold,
            field_profiles=self.field_profiles,  # ✅ 传递字段画像
            schema_hash=self.schema_hash,        # ✅ 传递schema哈希（启用缓存）
            use_prefilter=False,                 # ❌ 单表对分析不需要预筛选
            similarity_threshold=0.1,
            max_pairs=100,
            use_cache=True,                      # ✅ 启用缓存（避免重复LLM调用）
            parallel=True,                        # ✅ 启用并行
            max_workers=4                        # ✅ 内部分析线程数
        )

        # 反向分析（B -> A）
        # 由于外层已有缓存，这里大概率会命中，跳过大部分重复的LLM调用
        reverse_relationships = infer_table_relationships(
            target_tables_info={table_b: fields_b},
            ref_tables_info={table_a: fields_a},
            confidence_threshold=confidence_threshold,
            field_profiles=self.field_profiles,
            schema_hash=self.schema_hash,
            use_prefilter=False,
            similarity_threshold=0.1,
            max_pairs=100,
            use_cache=True,                      # ✅ 启用缓存
            parallel=True,
            max_workers=4
        )

        # 合并并去重（同时过滤低于阈值的关系）
        all_rels = relationships + reverse_relationships
        return self._deduplicate_relationships(all_rels, confidence_threshold)

    def _deduplicate_relationships(
        self,
        relationships: List[Dict[str, Any]],
        confidence_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        去重并过滤：同一对字段只保留置信度最高的关系，并过滤低于阈值的关系
        """
        seen = {}

        for rel in relationships:
            # 过滤：低于阈值的关系直接跳过
            if rel.get("confidence", 0) < confidence_threshold:
                continue

            # 创建双向键（确保 A-B 和 B-A 被视为同一关系）
            key = tuple(sorted([
                (rel["from_table"], rel["from_column"]),
                (rel["to_table"], rel["to_column"])
            ]))

            if key not in seen or rel["confidence"] > seen[key]["confidence"]:
                seen[key] = rel

        return list(seen.values())

    def _generate_table_centric_cards(
        self,
        relationships: List[Dict[str, Any]],
        tables_info: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        生成以表为中心的关系卡片

        每张表生成一张关系卡片，包含该表与其他表的所有关系
        """
        # 按表分组关系
        table_relationships = {}
        for rel in relationships:
            from_table = rel["from_table"]
            to_table = rel["to_table"]

            # 为 from_table 添加关系
            if from_table not in table_relationships:
                table_relationships[from_table] = []
            table_relationships[from_table].append(rel)

            # 为 to_table 添加反向关系
            if to_table not in table_relationships:
                table_relationships[to_table] = []
            # 创建反向关系视图
            reverse_rel = self._create_reverse_relationship(rel)
            table_relationships[to_table].append(reverse_rel)

        # 为每张表生成关系卡片
        cards = []
        for table_name in tables_info.keys():
            rels = table_relationships.get(table_name, [])
            card = self._create_table_centric_card(
                table_name,
                tables_info.get(table_name, []),
                rels
            )
            cards.append(card)

        return cards

    def _create_reverse_relationship(self, rel: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建反向关系视图
        """
        reverse = rel.copy()
        reverse["from_table"] = rel["to_table"]
        reverse["from_column"] = rel["to_column"]
        reverse["to_table"] = rel["from_table"]
        reverse["to_column"] = rel["from_column"]

        # 反转基数关系
        cardinality = rel.get("cardinality", "many_to_many")
        reverse_cardinality_map = {
            "one_to_one": "one_to_one",
            "one_to_many": "many_to_one",
            "many_to_one": "one_to_many",
            "many_to_many": "many_to_many"
        }
        reverse["cardinality"] = reverse_cardinality_map.get(cardinality, "many_to_many")

        # 反转业务关系
        business_rel = rel.get("business_relation", {})
        if business_rel:
            reverse["business_relation"] = {
                "from_entity": business_rel.get("to_entity", ""),
                "to_entity": business_rel.get("from_entity", ""),
                "relation_description": business_rel.get("relation_description", ""),
                "from_role": business_rel.get("to_role", ""),
                "to_role": business_rel.get("from_role", "")
            }

        # 反转跨源关系的数据源ID
        if rel.get("is_cross_source"):
            reverse["from_datasource_id"] = rel.get("to_datasource_id")
            reverse["to_datasource_id"] = rel.get("from_datasource_id")
            reverse["from_datasource_name"] = rel.get("to_datasource_name", "")
            reverse["to_datasource_name"] = rel.get("from_datasource_name", "")

        return reverse

    def _create_table_centric_card(
        self,
        table_name: str,
        fields: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        创建以表为中心的关系卡片

        卡片结构设计用于支持：
        1. NL2SQL联表查询时的JOIN条件推荐
        2. 结果融合时的关系信息提供
        """
        # 按关联表分组关系
        related_tables = {}
        for rel in relationships:
            related_table = rel["to_table"]
            if related_table not in related_tables:
                related_tables[related_table] = {
                    "table_name": related_table,
                    "relationships": [],
                    "avg_confidence": 0,
                    "cardinality": None
                }
            related_tables[related_table]["relationships"].append(rel)

        # 计算每个关联表的聚合信息
        relationship_list = []
        for related_table, info in related_tables.items():
            rels = info["relationships"]

            # 计算平均置信度
            avg_confidence = sum(r["confidence"] for r in rels) / len(rels)

            # 获取主要基数关系
            cardinalities = [r.get("cardinality", "many_to_many") for r in rels]
            main_cardinality = max(set(cardinalities), key=cardinalities.count)

            # 获取业务关系信息（取置信度最高的）
            best_rel = max(rels, key=lambda r: r.get("confidence", 0))
            business_relation = best_rel.get("business_relation", {})
            join_suggestion = best_rel.get("join_suggestion", {})
            fusion_suggestion = best_rel.get("fusion_suggestion", {})

            # 获取跨源关系信息（从最佳关系中获取）
            is_cross_source = best_rel.get("is_cross_source", False)
            related_datasource_id = best_rel.get("to_datasource_id")
            related_datasource_name = best_rel.get("to_datasource_name", "")

            # 构建JOIN字段列表
            join_fields = []
            for rel in rels:
                join_fields.append({
                    "local_field": rel["from_column"],
                    "remote_field": rel["to_column"],
                    "confidence": rel["confidence"],
                    "relationship_type": rel.get("relationship_type", "semantic")
                })

            relationship_list.append({
                "related_table": related_table,
                "relationship_type": main_cardinality,
                "confidence": round(avg_confidence, 4),
                "join_fields": join_fields,
                "join_suggestion": join_suggestion,
                "business_relation": business_relation,
                "fusion_suggestion": fusion_suggestion,
                "is_cross_source": is_cross_source,
                "related_datasource_id": str(related_datasource_id) if related_datasource_id else None,
                "related_datasource_name": related_datasource_name
            })

        # 按置信度排序
        relationship_list.sort(key=lambda x: x["confidence"], reverse=True)

        # 生成摘要
        join_summary = self._generate_join_summary(table_name, relationship_list)

        # 生成融合建议
        fusion_hints = self._generate_fusion_hints(table_name, relationship_list)

        # 获取该表所属的数据源ID
        table_datasource_id = self.table_datasource_map.get(table_name, self.primary_datasource_id)

        # 构建卡片
        doc_id = f"rel_card_{table_datasource_id}_{table_name}"

        card = {
            "DocInfo": {
                "doc_id": doc_id,
                "title": f"关系卡片: {table_name}",
                "source_type": "relationship",
                "datasource_id": str(table_datasource_id),
                "schema_name": self.schema_name,
                "table_name": table_name,
                "created_at": datetime.now(tz_cst).isoformat()
            },
            "TableInfo": {
                "table_name": table_name,
                "fields_count": len(fields),
                "primary_key": self._get_primary_key(fields)
            },
            "Relationships": relationship_list,
            "FusionHints": fusion_hints,
            "JoinSummary": join_summary,
            "Statistics": {
                "related_tables_count": len(relationship_list),
                "total_join_fields": sum(len(r["join_fields"]) for r in relationship_list),
                "avg_confidence": round(
                    sum(r["confidence"] for r in relationship_list) / len(relationship_list), 4
                ) if relationship_list else 0
            }
        }

        return card

    def _get_primary_key(self, fields: List[Dict[str, Any]]) -> str:
        """
        推断主键字段
        """
        for field in fields:
            name = field.get("column_name", "").lower()
            if name == "id":
                return field.get("column_name", "id")

        # 如果没有id字段，查找xxx_id模式
        for field in fields:
            name = field.get("column_name", "").lower()
            if name.endswith("_id") and not name.startswith(("fk_", "ref_")):
                return field.get("column_name", "")

        return "id"

    def _generate_join_summary(
        self,
        table_name: str,
        relationships: List[Dict[str, Any]]
    ) -> str:
        """
        生成JOIN摘要
        """
        if not relationships:
            return f"表 {table_name} 暂未发现与其他表的关联关系"

        related_tables = [r["related_table"] for r in relationships[:3]]
        more_count = len(relationships) - 3

        summary = f"表 {table_name} 与 {len(relationships)} 张表存在关联关系"

        if related_tables:
            summary += f"，主要关联: {', '.join(related_tables)}"
            if more_count > 0:
                summary += f" 等"

        return summary

    def _generate_fusion_hints(
        self,
        table_name: str,
        relationships: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """
        生成数据融合建议
        """
        hints = {
            "as_master": [],
            "as_detail": [],
            "common_joins": []
        }

        for rel in relationships:
            cardinality = rel.get("relationship_type", "many_to_many")
            related_table = rel["related_table"]
            fusion = rel.get("fusion_suggestion", {})

            if cardinality == "one_to_many":
                hints["as_master"].append(
                    f"{table_name} 作为主表，可关联 {related_table} 获取明细数据"
                )
            elif cardinality == "many_to_one":
                hints["as_detail"].append(
                    f"{table_name} 作为明细表，可关联 {related_table} 获取主表信息"
                )

            # 添加通用JOIN建议
            join_suggestion = rel.get("join_suggestion", {})
            if join_suggestion.get("use_cases"):
                hints["common_joins"].extend(join_suggestion["use_cases"][:2])

        # 限制数量
        hints["as_master"] = hints["as_master"][:3]
        hints["as_detail"] = hints["as_detail"][:3]
        hints["common_joins"] = hints["common_joins"][:5]

        return hints

    def _persist_results(
        self,
        relationships: List[Dict[str, Any]],
        cards: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        持久化结果到数据库

        注意：关系卡片不入向量库，而是在NL2SQL召回数据卡片后，
        根据召回的表名从数据库中查询对应的关系卡片，一并提供给LLM
        """
        result = {
            "relationships_saved": 0,
            "cards_saved": 0,
            "errors": []
        }

        try:
            # 1. 保存表关系到 table_relationship 表
            saved_rels = self._save_relationships_to_db(relationships)
            result["relationships_saved"] = saved_rels

            # 2. 保存关系卡片到 table_relationship_card 表
            saved_cards = self._save_cards_to_db(cards)
            result["cards_saved"] = saved_cards

        except Exception as e:
            import traceback
            traceback.print_exc()
            result["errors"].append(str(e))

        return result

    def _cleanup_old_data(self):
        """
        清理该数据源的旧关系数据

        在每次全域盘点开始前调用，确保数据是全新分析的结果
        而不是与旧数据混合
        """
        from models.global_inventory import TableRelationship, TableRelationshipCard

        deleted_rels = 0
        deleted_cards = 0

        try:
            # 只删除 source_type='global_inventory' 的记录
            # governance 来源的记录由治理报告管理，不被全域盘点清理掉
            rel_query = db.session.query(TableRelationship).filter(
                db.or_(
                    TableRelationship.table_a_datasource_id == self.primary_datasource_id,
                    TableRelationship.table_b_datasource_id == self.primary_datasource_id
                ),
                TableRelationship.source_type == 'global_inventory'
            )
            deleted_rels = rel_query.delete(synchronize_session=False)

            # 只删除 source_type='global_inventory' 的卡片
            card_query = db.session.query(TableRelationshipCard).filter(
                TableRelationshipCard.datasource_id == self.primary_datasource_id,
                TableRelationshipCard.source_type == 'global_inventory'
            )
            deleted_cards = card_query.delete(synchronize_session=False)

            db.session.commit()
            print(f"[全域盘点] 清理完成: 删除 {deleted_rels} 条关系记录, {deleted_cards} 张关系卡片")

        except Exception as e:
            db.session.rollback()
            print(f"[全域盘点] 清理旧数据失败: {e}")
            raise

    def _save_relationships_to_db(self, relationships: List[Dict[str, Any]]) -> int:
        """
        保存表关系到数据库（支持跨源关系）
        每条关系存储在 table_a 所属的数据源下
        """
        saved = 0

        # 按表对分组
        grouped = group_relationships_by_table_pair(relationships)

        for (table_a, table_b), rels in grouped.items():
            try:
                # 获取跨源信息（从第一个关系中获取）
                first_rel = rels[0]
                is_cross_source = first_rel.get("is_cross_source", False)
                table_a_datasource_id = first_rel.get("from_datasource_id") or self.table_datasource_map.get(table_a, self.primary_datasource_id)
                table_b_datasource_id = first_rel.get("to_datasource_id") or self.table_datasource_map.get(table_b, self.primary_datasource_id)

                # 获取各表的 schema_hash
                table_a_schema_hash = first_rel.get("from_schema_hash") or self.datasource_schema_map.get(str(table_a_datasource_id), self.schema_hash)
                table_b_schema_hash = first_rel.get("to_schema_hash") or self.datasource_schema_map.get(str(table_b_datasource_id), self.schema_hash)

                # 检查是否已存在（使用新的唯一约束字段）
                existing = db.session.query(TableRelationship).filter(
                    TableRelationship.table_a_datasource_id == table_a_datasource_id,
                    TableRelationship.table_a_schema_hash == table_a_schema_hash,
                    TableRelationship.table_a == table_a,
                    TableRelationship.table_b_datasource_id == table_b_datasource_id,
                    TableRelationship.table_b_schema_hash == table_b_schema_hash,
                    TableRelationship.table_b == table_b
                ).first()

                # 计算聚合信息
                avg_strength = sum(r["confidence"] for r in rels) / len(rels)
                cardinalities = [r.get("cardinality", "many_to_many") for r in rels]
                main_cardinality = max(set(cardinalities), key=cardinalities.count)

                # 构建JOIN条件
                join_conditions = []
                for rel in rels:
                    join_conditions.append({
                        "local_field": rel["from_column"],
                        "remote_field": rel["to_column"],
                        "confidence": rel["confidence"],
                        "mapping_type": rel.get("relationship_type", "semantic")
                    })

                # 判断关系类型
                rel_types = [r.get("relationship_type", "semantic") for r in rels]
                if "foreign_key" in rel_types:
                    relationship_type = "FK"
                elif "semantic" in rel_types:
                    relationship_type = "Semantic"
                else:
                    relationship_type = "Value"

                if existing:
                    # 更新
                    existing.relationship_type = relationship_type
                    existing.join_conditions = join_conditions
                    existing.relationship_strength = avg_strength
                    existing.cardinality = main_cardinality
                    existing.is_cross_source = is_cross_source
                    existing.updated_at = datetime.now(tz_cst)
                else:
                    # 新增
                    new_rel = TableRelationship(
                        table_a=table_a,
                        table_a_datasource_id=table_a_datasource_id,
                        table_a_schema_hash=table_a_schema_hash,
                        table_b=table_b,
                        table_b_datasource_id=table_b_datasource_id,
                        table_b_schema_hash=table_b_schema_hash,
                        is_cross_source=is_cross_source,
                        source_type='global_inventory',  # ✅ 新增：标识来源
                        source_job_id=None,              # ✅ 新增：全域盘点无任务ID
                        relationship_type=relationship_type,
                        join_conditions=join_conditions,
                        relationship_strength=avg_strength,
                        cardinality=main_cardinality
                    )
                    db.session.add(new_rel)

                saved += 1

            except Exception as e:
                print(f"[全域盘点] 保存关系 {table_a} <-> {table_b} 失败: {e}")
                continue

        db.session.commit()
        return saved

    def _save_cards_to_db(self, cards: List[Dict[str, Any]]) -> int:
        """
        保存关系卡片到数据库（支持跨源关系）
        每张表的关系卡片存储在其所属的数据源下
        """
        saved = 0

        for card in cards:
            try:
                table_name = card["DocInfo"]["table_name"]

                # 获取该表所属的数据源ID（每张表存储在自己的数据源下）
                table_datasource_id = self.table_datasource_map.get(table_name, self.primary_datasource_id)

                # 获取该表的 schema_hash
                table_schema_hash = self.datasource_schema_map.get(str(table_datasource_id), self.schema_hash)

                # 检查卡片中是否包含跨源关系，并收集关联的数据源ID
                has_cross_source = False
                related_datasource_ids = set()
                relationships = card.get("Relationships", [])
                for rel in relationships:
                    if rel.get("is_cross_source", False):
                        has_cross_source = True
                        # 收集关联的其他数据源ID
                        related_ds = rel.get("related_datasource_id")
                        if related_ds and related_ds != str(table_datasource_id):
                            related_datasource_ids.add(related_ds)

                # 检查是否已存在（使用新的唯一约束字段）
                existing = db.session.query(TableRelationshipCard).filter(
                    TableRelationshipCard.datasource_id == table_datasource_id,
                    TableRelationshipCard.schema_hash == table_schema_hash,
                    TableRelationshipCard.table_name == table_name
                ).first()

                if existing:
                    # 更新
                    existing.card_data = card
                    existing.version = (existing.version or 0) + 1
                    existing.related_datasource_ids = list(related_datasource_ids) if related_datasource_ids else None
                    existing.has_cross_source_relations = has_cross_source
                    existing.updated_at = datetime.now(tz_cst)
                else:
                    # 新增（存储在该表所属的数据源下）
                    new_card = TableRelationshipCard(
                        datasource_id=table_datasource_id,
                        schema_hash=table_schema_hash,
                        table_name=table_name,
                        source_type='global_inventory',  # ✅ 新增：标识来源
                        source_job_id=None,              # ✅ 新增：全域盘点无任务ID
                        card_data=card,
                        version=1,
                        related_datasource_ids=list(related_datasource_ids) if related_datasource_ids else None,
                        has_cross_source_relations=has_cross_source
                    )
                    db.session.add(new_card)

                saved += 1

            except Exception as e:
                print(f"[全域盘点] 保存卡片 {card.get('DocInfo', {}).get('table_name', 'unknown')} 失败: {e}")
                continue

        db.session.commit()
        return saved

    def _generate_statistics(
        self,
        relationships: List[Dict[str, Any]],
        cards: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        生成统计信息
        """
        # 计算表对级别的统计
        grouped = group_relationships_by_table_pair(relationships)
        table_pair_count = len(grouped)
        cross_source_table_pair_count = 0
        for (table_a, table_b), rels in grouped.items():
            # 只要有一个字段关系是跨源的，这个表对就算跨源
            if any(r.get("is_cross_source", False) for r in rels):
                cross_source_table_pair_count += 1

        stats = {
            "total_tables": len(cards),
            "total_relationships": len(relationships),  # 字段级关系数
            "total_table_pairs": table_pair_count,  # 表对级关系数
            "cross_source_table_pairs": cross_source_table_pair_count,  # 跨源表对数
            "tables_with_relationships": 0,
            "tables_without_relationships": 0,
            "relationship_types": {},
            "cardinality_distribution": {},
            "avg_confidence": 0,
            "high_confidence_count": 0,
            "low_confidence_count": 0
        }

        # 统计关系类型分布
        for rel in relationships:
            rel_type = rel.get("relationship_type", "semantic")
            stats["relationship_types"][rel_type] = stats["relationship_types"].get(rel_type, 0) + 1

            cardinality = rel.get("cardinality", "many_to_many")
            stats["cardinality_distribution"][cardinality] = stats["cardinality_distribution"].get(cardinality, 0) + 1

            confidence = rel.get("confidence", 0)
            if confidence >= 0.8:
                stats["high_confidence_count"] += 1
            elif confidence < 0.6:
                stats["low_confidence_count"] += 1

        # 计算平均置信度
        if relationships:
            stats["avg_confidence"] = round(
                sum(r.get("confidence", 0) for r in relationships) / len(relationships), 4
            )

        # 统计有/无关系的表
        for card in cards:
            rels = card.get("Relationships", [])
            if rels:
                stats["tables_with_relationships"] += 1
            else:
                stats["tables_without_relationships"] += 1

        return stats


def run_global_inventory(
    datasource_id: str,
    user_id: str,
    schema_name: str = None,
    confidence_threshold: float = 0.5,
    max_workers: int = 10,
    enable_profiling: bool = True
) -> Dict[str, Any]:
    """
    执行全域盘点（便捷函数）

    Args:
        datasource_id: 数据源ID
        user_id: 用户ID
        schema_name: Schema名称（可选）
        confidence_threshold: 置信度阈值
        max_workers: 最大并行线程数（默认10）
        enable_profiling: 是否启用字段画像（默认True，提升准确性和稳定性）

    Returns:
        发现结果
    """
    service = GlobalInventoryService(
        datasource_id=datasource_id,
        user_id=user_id,
        schema_name=schema_name,
        enable_profiling=enable_profiling
    )

    return service.discover_all_relationships(
        confidence_threshold=confidence_threshold,
        max_workers=max_workers
    )
