"""
@File: schema_context.py
@Description: Schema 上下文提供者 - 互斥获取数据来源，提供完整的 Schema 上下文
@Author: 韩小豪 849631113@qq.com
@Create: 2026-06-02
@Update: 2026-06-11 - 互斥获取逻辑，避免同时传递多个来源的冗余信息

核心设计原则：
1. 互斥获取：一张表只从一个来源获取，不会同时传两个来源
2. 优先级：数据卡片 > UserDatasourceSchema > 实时数据库
3. 自然语言模式：只传目标表信息 + 自然语言给 LLM
"""

import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict


@dataclass
class ColumnInfo:
    """列信息"""
    name: str
    data_type: str
    comment: str = ""
    is_primary: bool = False
    is_foreign: bool = False
    nullable: bool = True
    default_value: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TableSchema:
    """表结构信息"""
    table_name: str
    schema_name: str = ""
    description: str = ""
    columns: List[ColumnInfo] = None
    is_view: bool = False  # 是否为视图

    # 数据卡片扩展信息
    card_abstract: str = ""  # 卡片摘要
    card_topic: str = ""      # 核心主题
    card_entities: List[str] = None  # 核心实体
    card_scenarios: List[str] = None  # 适用场景
    card_tags: List[str] = None  # 标签

    def __post_init__(self):
        if self.columns is None:
            self.columns = []
        if self.card_entities is None:
            self.card_entities = []
        if self.card_scenarios is None:
            self.card_scenarios = []
        if self.card_tags is None:
            self.card_tags = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_llm_context(self) -> str:
        """
        转换为适合 LLM 理解的格式

        包含：
        1. 表的基本信息（表名、描述）
        2. 数据卡片的业务信息（摘要、主题、实体、场景）
        3. 列的详细信息（列名、类型、注释、主键、外键）
        """
        lines = []

        # 表基本信息
        lines.append(f"### 表: {self.table_name}")
        if self.schema_name:
            lines.append(f"- Schema: {self.schema_name}")

        # 表描述
        if self.description:
            lines.append(f"- 表描述: {self.description}")

        # 数据卡片业务信息
        if self.card_abstract or self.card_topic:
            lines.append("")
            lines.append("**业务信息**:")
            if self.card_topic:
                lines.append(f"- 核心主题: {self.card_topic}")
            if self.card_abstract:
                lines.append(f"- 摘要: {self.card_abstract}")
            if self.card_entities:
                lines.append(f"- 核心实体: {', '.join(self.card_entities)}")
            if self.card_scenarios:
                lines.append(f"- 适用场景: {', '.join(self.card_scenarios)}")
            if self.card_tags:
                lines.append(f"- 标签: {', '.join(self.card_tags)}")

        # 列信息
        lines.append("")
        lines.append("**列信息**:")
        lines.append("| 列名 | 类型 | 注释 | 主键 | 外键 |")
        lines.append("|------|------|------|------|------|")
        for col in self.columns:
            pk_mark = "✓" if col.is_primary else ""
            fk_mark = "✓" if col.is_foreign else ""
            comment = col.comment or ""
            lines.append(f"| {col.name} | {col.data_type} | {comment} | {pk_mark} | {fk_mark} |")

        return '\n'.join(lines)

    def matches_keyword(self, keyword: str) -> bool:
        """检查表或列是否匹配关键词"""
        keyword_lower = keyword.lower()
        if keyword_lower in self.table_name.lower():
            return True
        if keyword_lower in self.description.lower():
            return True
        if keyword_lower in self.card_abstract.lower():
            return True
        if keyword_lower in self.card_topic.lower():
            return True
        if any(keyword_lower in tag.lower() for tag in self.card_tags):
            return True
        if any(keyword_lower in entity.lower() for entity in self.card_entities):
            return True
        if any(keyword_lower in scenario.lower() for scenario in self.card_scenarios):
            return True
        for col in self.columns:
            if keyword_lower in col.name.lower():
                return True
            if keyword_lower in (col.comment or '').lower():
                return True
        return False

    def find_column_by_keyword(self, keyword: str) -> Optional[Dict[str, Any]]:
        """根据关键词查找匹配的列，返回列信息字典"""
        keyword_lower = keyword.lower()
        for col in self.columns:
            # 优先匹配注释
            if keyword_lower == (col.comment or '').lower():
                return {'name': col.name, 'data_type': col.data_type, 'comment': col.comment}
        for col in self.columns:
            # 其次模糊匹配注释
            if keyword_lower in (col.comment or '').lower():
                return {'name': col.name, 'data_type': col.data_type, 'comment': col.comment}
        for col in self.columns:
            # 最后模糊匹配列名
            if keyword_lower in col.name.lower():
                return {'name': col.name, 'data_type': col.data_type, 'comment': col.comment}
        return None


class SchemaSource:
    """Schema 数据来源枚举"""
    DATA_CARD = "data_card"        # 数据卡片（最高优先级）
    USER_SCHEMA = "user_schema"    # UserDatasourceSchema
    DATABASE = "database"           # 实时数据库（兜底）


def get_schema_for_target_table(
    datasource_id: str,
    user_id: str,
    table_name: str
) -> tuple:
    """
    互斥获取指定表的 Schema 信息

    获取策略（互斥，不同时传多个来源）：
    1. 优先从 DataCardDataSource（数据卡片）获取
    2. 如果没有，从 UserDatasourceSchema 获取
    3. 如果都没有，返回 None（由调用方决定是否从数据库实时获取）

    Args:
        datasource_id: 数据源 ID
        user_id: 用户 ID
        table_name: 目标表名

    Returns:
        tuple: (TableSchema, SchemaSource) 或 (None, None)
    """
    from models.datasource_infos import DatasourceInfo
    from models.user_datasource_schema import UserDatasourceSchema
    from models.datacards_datasource import DataCardDataSource

    # 获取数据源
    datasource = DatasourceInfo.query.filter_by(id=datasource_id, user_id=user_id).first()
    if not datasource:
        return None, None

    # ============================================
    # 策略1: 优先从数据卡片获取
    # ============================================
    data_card = DataCardDataSource.query.filter_by(
        datasource_id=datasource_id,
        table_name=table_name
    ).first()

    if data_card and data_card.card_data:
        try:
            card_info = json.loads(data_card.card_data)
            table_schema = _build_table_schema_from_card(table_name, card_info)
            return table_schema, SchemaSource.DATA_CARD
        except Exception as e:
            print(f"[WARN] 解析数据卡片 {table_name} 失败: {str(e)}")

    # ============================================
    # 策略2: 从 UserDatasourceSchema 获取
    # ============================================
    # 重要：connect_info 已加密存储（AES-GCM，nonce 随机，密文不可等值比较），
    # 必须用 connect_info_hash（稳定哈希）匹配。
    from core.connect_info_encryptor import get_connect_info_hash

    connect_info_hash = get_connect_info_hash(datasource.connect_info) if datasource.connect_info else ''
    db_schema = None
    if connect_info_hash:
        hash_query = UserDatasourceSchema.query.filter_by(
            user_id=user_id,
            connect_info_hash=connect_info_hash,
            table_name=table_name
        )
        if datasource.schema_name is not None:
            hash_query = hash_query.filter_by(schema_name=datasource.schema_name)
        db_schema = hash_query.first()

    # 回退：hash 未命中或为空时，尝试用解密后的明文 connect_info 做兼容匹配
    if not db_schema and datasource.connect_info:
        from core.connect_info_encryptor import decrypt_connect_info, is_encrypted
        try:
            connect_info_plain = decrypt_connect_info(datasource.connect_info) if is_encrypted(datasource.connect_info) else datasource.connect_info
        except Exception:
            connect_info_plain = datasource.connect_info
        fallback_query = UserDatasourceSchema.query.filter_by(
            user_id=user_id,
            connect_info=connect_info_plain,
            table_name=table_name
        )
        if datasource.schema_name is not None:
            fallback_query = fallback_query.filter_by(schema_name=datasource.schema_name)
        db_schema = fallback_query.first()

    if db_schema and db_schema.schema_text:
        try:
            schema_info = json.loads(db_schema.schema_text)
            table_schema = _build_table_schema_from_db_schema(table_name, schema_info)
            return table_schema, SchemaSource.USER_SCHEMA
        except Exception as e:
            print(f"[WARN] 解析 UserDatasourceSchema {table_name} 失败: {str(e)}")

    # ============================================
    # 策略3: 返回 None，由调用方决定是否从数据库实时获取
    # ============================================
    return None, None


def get_schema_for_target_table_with_fallback(
    datasource_id: str,
    user_id: str,
    table_name: str,
    connect_info: str = None
) -> tuple:
    """
    获取指定表的 Schema 信息（含实时数据库回退）

    策略（互斥）：
    1. 优先从 DataCardDataSource 获取
    2. 如果没有，从 UserDatasourceSchema 获取
    3. 如果都没有，从数据库实时获取

    Args:
        datasource_id: 数据源 ID
        user_id: 用户 ID
        table_name: 目标表名
        connect_info: 数据库连接信息（用于实时获取）

    Returns:
        tuple: (TableSchema, SchemaSource)
    """
    # 先尝试互斥获取
    schema, source = get_schema_for_target_table(datasource_id, user_id, table_name)
    if schema:
        return schema, source

    # 兜底：从数据库实时获取
    if connect_info:
        try:
            from controllers.datasource.database_schema_extractor import get_db_engine
            from core.connect_info_encryptor import decrypt_connect_info
            from sqlalchemy import inspect

            # 注意：connect_info 参数可能是加密值，需要先解密
            connect_info_decrypted = decrypt_connect_info(connect_info)
            engine = get_db_engine(connect_info_decrypted)
            inspector = inspect(engine)

            # 获取表的列信息
            columns_info = inspector.get_columns(table_name)

            columns = []
            for col in columns_info:
                columns.append(ColumnInfo(
                    name=col['name'],
                    data_type=str(col['type']),
                    comment=col.get('comment', ''),
                    is_primary=col.get('primary_key', False),
                    is_foreign=bool(col.get('foreign_keys')),
                    nullable=col.get('nullable', True),
                    default_value=str(col.get('default')) if col.get('default') else None
                ))

            table_schema = TableSchema(
                table_name=table_name,
                columns=columns
            )
            return table_schema, SchemaSource.DATABASE
        except Exception as e:
            print(f"[WARN] 实时获取表 {table_name} 失败: {str(e)}")

    return None, None


def _build_table_schema_from_card(table_name: str, card_info: dict, is_view: bool = False) -> TableSchema:
    """从数据卡片构建 TableSchema"""
    card_sql_meta = card_info.get('SQLMeta', {})
    card_columns = card_sql_meta.get('columns', [])

    columns = []
    for c in card_columns:
        col_name = c.get('name', '')
        if col_name:
            columns.append(ColumnInfo(
                name=col_name,
                data_type=c.get('type', ''),
                comment=c.get('comment', ''),  # 数据卡片的注释经过增强
                is_primary=c.get('is_primary', False),
                is_foreign=c.get('is_foreign', False),
                nullable=c.get('nullable', True),
                default_value=c.get('default')
            ))

    # 构建表信息
    key_concepts = card_info.get('KeyConcepts', {})
    table_schema = TableSchema(
        table_name=table_name,
        description=card_info.get('Abstract', ''),
        columns=columns,
        is_view=is_view,
        card_abstract=card_info.get('Abstract', ''),
        card_topic=key_concepts.get('canonical_topic', ''),
        card_entities=key_concepts.get('key_entities', []),
        card_scenarios=key_concepts.get('applicable_scenarios', []),
        card_tags=card_info.get('Tags', [])
    )
    return table_schema


def _build_table_schema_from_db_schema(table_name: str, schema_info: dict) -> TableSchema:
    """从 UserDatasourceSchema 构建 TableSchema"""
    columns = []
    for col in schema_info.get('columns', []):
        col_name = col.get('name', '')
        if col_name:
            columns.append(ColumnInfo(
                name=col_name,
                data_type=col.get('type', ''),
                comment=col.get('comment', ''),
                is_primary=col.get('is_primary', False),
                is_foreign=col.get('is_foreign', False),
                nullable=col.get('nullable', True),
                default_value=col.get('default')
            ))

    table_schema = TableSchema(
        table_name=table_name,
        schema_name=schema_info.get('schema', ''),
        description=schema_info.get('description', ''),
        columns=columns
    )
    return table_schema


def get_schema_from_datasource(datasource_id: str, user_id: str) -> List[TableSchema]:
    """
    从数据源获取完整 Schema 信息

    策略（互斥）：
    - 优先从 DataCardDataSource 获取
    - 数据卡片没有的表，从 UserDatasourceSchema 获取
    - 如果都没有，不返回该表

    Args:
        datasource_id: 数据源 ID
        user_id: 用户 ID

    Returns:
        TableSchema 列表（每个表只来自一个来源）
    """
    from models.datasource_infos import DatasourceInfo
    from models.user_datasource_schema import UserDatasourceSchema
    from models.datacards_datasource import DataCardDataSource

    # 获取数据源
    datasource = DatasourceInfo.query.filter_by(id=datasource_id, user_id=user_id).first()
    if not datasource:
        return []

    schemas = []

    # ============================================
    # 步骤0: 预先收集所有表的 is_view 信息
    # ============================================
    # 重要：connect_info 已加密存储，必须用 connect_info_hash 匹配。
    from core.connect_info_encryptor import get_connect_info_hash

    connect_info_hash = get_connect_info_hash(datasource.connect_info) if datasource.connect_info else ''
    db_schemas = []
    if connect_info_hash:
        hash_query = UserDatasourceSchema.query.filter_by(
            user_id=user_id,
            connect_info_hash=connect_info_hash
        )
        if datasource.schema_name is not None:
            hash_query = hash_query.filter_by(schema_name=datasource.schema_name)
        db_schemas = hash_query.all()

    # 回退：hash 未命中或为空时，尝试明文匹配
    if not db_schemas and datasource.connect_info:
        from core.connect_info_encryptor import decrypt_connect_info, is_encrypted
        try:
            connect_info_plain = decrypt_connect_info(datasource.connect_info) if is_encrypted(datasource.connect_info) else datasource.connect_info
        except Exception:
            connect_info_plain = datasource.connect_info
        fallback_query = UserDatasourceSchema.query.filter_by(
            user_id=user_id,
            connect_info=connect_info_plain
        )
        if datasource.schema_name is not None:
            fallback_query = fallback_query.filter_by(schema_name=datasource.schema_name)
        db_schemas = fallback_query.all()

    # 构建表名 -> is_view 的映射
    table_is_view_map = {}
    for s in db_schemas:
        table_is_view_map[s.table_name.lower()] = bool(s.is_view)

    # ============================================
    # 步骤1: 从数据卡片获取表信息
    # ============================================
    data_cards = DataCardDataSource.query.filter_by(
        datasource_id=datasource_id
    ).all()

    card_tables = set()
    for card in data_cards:
        if card.card_data:
            try:
                card_data = json.loads(card.card_data)
                # 获取 is_view 信息（从 UserDatasourceSchema 中查找）
                is_view = table_is_view_map.get(card.table_name.lower(), False)
                table_schema = _build_table_schema_from_card(card.table_name, card_data, is_view=is_view)
                schemas.append(table_schema)
                card_tables.add(card.table_name.lower())
            except Exception as e:
                print(f"[WARN] 解析数据卡片 {card.table_name} 失败: {str(e)}")

    # ============================================
    # 步骤2: 从 UserDatasourceSchema 获取数据卡片没有的表
    # ============================================
    for s in db_schemas:
        if s.table_name.lower() in card_tables:
            continue  # 跳过已从数据卡片获取的表

        if s.schema_text:
            try:
                schema_data = json.loads(s.schema_text)
                table_schema = _build_table_schema_from_db_schema(s.table_name, schema_data)
                table_schema.is_view = bool(s.is_view)  # 设置 is_view
                schemas.append(table_schema)
            except Exception as e:
                print(f"[WARN] 解析 UserDatasourceSchema {s.table_name} 失败: {str(e)}")

    return schemas


def get_schema_from_connection(connect_info: Dict[str, Any]) -> List[TableSchema]:
    """
    从数据库连接获取 Schema 信息

    Args:
        connect_info: 数据库连接信息

    Returns:
        TableSchema 列表
    """
    from controllers.datasource.database_schema_extractor import get_database_info

    try:
        # 获取数据库信息
        db_info = get_database_info(connect_info)
        schemas = []

        for table_info in db_info.get('tables', []):
            columns = []
            for col in table_info.get('columns', []):
                columns.append(ColumnInfo(
                    name=col.get('name', ''),
                    data_type=col.get('type', ''),
                    comment=col.get('comment', ''),
                    is_primary=col.get('is_primary', False),
                    is_foreign=col.get('is_foreign', False),
                    nullable=col.get('nullable', True),
                    default_value=col.get('default')
                ))

            schemas.append(TableSchema(
                table_name=table_info.get('table_name', ''),
                schema_name=table_info.get('schema', ''),
                description=table_info.get('description', ''),
                columns=columns
            ))

        return schemas

    except Exception as e:
        print(f"[ERROR] 获取 Schema 失败: {str(e)}")
        return []


def build_schema_context_for_llm(schemas: List[TableSchema], max_tables: int = 20) -> str:
    """
    构建适合 LLM 的 Schema 上下文

    Args:
        schemas: TableSchema 列表
        max_tables: 最大表数量（避免上下文过长）

    Returns:
        格式化的上下文字符串
    """
    if not schemas:
        return "（无可用数据库结构信息）"

    # 如果表太多，按名称排序并截取
    schemas = sorted(schemas, key=lambda x: x.table_name)
    if len(schemas) > max_tables:
        schemas = schemas[:max_tables]

    lines = ["## 数据库 Schema 信息\n"]
    lines.append(f"共 {len(schemas)} 张表:\n")

    for schema in schemas:
        lines.append(schema.to_llm_context())
        lines.append("")  # 空行分隔

    return '\n'.join(lines)


def extract_column_keywords() -> Dict[str, List[str]]:
    """
    获取列名关键词映射（用于快速匹配）

    Returns:
        关键词到列名模式的映射
    """
    return {
        '手机': ['phone', 'mobile', 'tel', 'telephone', '手机号', '手机'],
        '电话': ['phone', 'mobile', 'tel', 'telephone', '手机', '电话'],
        '邮箱': ['email', 'mail', 'email_address', '邮箱'],
        '金额': ['amount', 'money', 'price', 'total', 'balance', '金额', '总价', '总额'],
        '价格': ['price', 'cost', 'amount', '单价', '价格'],
        '数量': ['quantity', 'qty', 'count', 'num', 'number', '数量', '数目'],
        '日期': ['date', 'day', 'time', 'created_at', 'updated_at', '日期', '时间'],
        '时间': ['time', 'timestamp', 'datetime', 'created_at', 'updated_at', '时间'],
        '状态': ['status', 'state', 'flag', '状态'],
        '名称': ['name', 'title', 'username', '名称', '姓名'],
        '地址': ['address', 'addr', 'location', '地址'],
        '年龄': ['age', 'birthday', 'birth_date', '年龄', '生日'],
        '性别': ['gender', 'sex', '性别'],
        'ID': ['id', '_id', 'uuid', '编码', '编号'],
        '用户': ['user', 'customer', 'member', '用户', '客户'],
        '订单': ['order', '订单', '交易'],
        '商品': ['product', 'item', 'goods', '商品', '产品'],
        '库存': ['stock', 'inventory', '库存', '仓储'],
    }
