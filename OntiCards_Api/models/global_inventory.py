"""
 @File: global_inventory.py
 @Description: 盘点功能模块所需的模型类（包含定向盘点和全域盘点）
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-01-21 14:32
 @Update: 2026-01-28 新增字段映射、表关系、关系卡片模型
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from extensions.ext_database import db
from models.utils import format_datetime

# 北京时区（东八区）
tz_cst = timezone(timedelta(hours=8))


class TargetInventoryJob(db.Model):
    """定向盘点任务表 - 用户手动选择数据源中的表进行字段注释推荐和表关系确认"""
    __tablename__ = "target_inventory_job"

    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4, comment="任务ID，主键")
    user_id = db.Column(db.Uuid, nullable=False, index=True, comment="用户ID")
    datasource_id = db.Column(db.Uuid, nullable=False, index=True, comment="数据源ID")
    schema_hash = db.Column(db.String(64), nullable=False, comment="Schema哈希值，用于标识数据源结构版本")

    target_tables = db.Column(db.JSON, nullable=False, comment="目标表列表（JSON数组）")
    ref_tables = db.Column(db.JSON, nullable=True, comment="参考表列表（JSON数组）")
    dict_file_id = db.Column(db.String(255), nullable=True, comment="字典文件ID")

    options = db.Column(db.JSON, nullable=True, comment="任务配置选项（JSON对象）")
    status = db.Column(db.String(32), nullable=False, default="queued", comment="任务状态：queued=排队中, processing=处理中, completed=已完成, failed=失败")
    progress = db.Column(db.JSON, nullable=True, comment="任务进度信息（JSON对象）")
    error_msg = db.Column(db.Text, nullable=True, comment="错误信息")

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(tz_cst), comment="创建时间")
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(tz_cst), onupdate=lambda: datetime.now(tz_cst), comment="更新时间")

    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "datasource_id": str(self.datasource_id),
            "schema_hash": self.schema_hash,
            "target_tables": self.target_tables or [],
            "ref_tables": self.ref_tables or [],
            "dict_file_id": self.dict_file_id,
            "options": self.options or {},
            "status": self.status,
            "progress": self.progress or {},
            "error_msg": self.error_msg,
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }

class TargetInventoryJobResult(db.Model):
    """定向盘点任务结果表"""
    __tablename__ = "target_inventory_job_result"

    job_id = db.Column(db.Uuid, db.ForeignKey("target_inventory_job.id", ondelete="CASCADE"), primary_key=True, comment="任务ID，关联 target_inventory_job.id")

    # Phase1-7: 字段映射层结果
    field_profiles_json = db.Column(db.JSON, nullable=True, comment="字段画像结果（JSON对象）")
    candidates_json = db.Column(db.JSON, nullable=True, comment="候选注释结果（JSON对象）")
    llm_json = db.Column(db.JSON, nullable=True, comment="LLM裁决结果（JSON对象）")
    confirm_json = db.Column(db.JSON, nullable=True, comment="用户确认结果（JSON对象）")
    index_meta_json = db.Column(db.JSON, nullable=True, comment="索引元数据（JSON对象）")

    # Phase8-10: 关系发现层结果
    field_mappings_json = db.Column(db.JSON, nullable=True, comment="字段映射结果（JSON对象）")
    table_relationships_json = db.Column(db.JSON, nullable=True, comment="表关系结果（JSON对象）")
    relationship_cards_json = db.Column(db.JSON, nullable=True, comment="关系卡片结果（JSON对象）")

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(tz_cst), comment="创建时间")
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(tz_cst), onupdate=lambda: datetime.now(tz_cst), comment="更新时间")

    def to_dict(self):
        return {
            "job_id": str(self.job_id),
            "field_profiles_json": self.field_profiles_json or {},
            "candidates_json": self.candidates_json or {},
            "llm_json": self.llm_json or {},
            "confirm_json": self.confirm_json or {},
            "index_meta_json": self.index_meta_json or {},
            "field_mappings_json": self.field_mappings_json or {},
            "table_relationships_json": self.table_relationships_json or {},
            "relationship_cards_json": self.relationship_cards_json or {},
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }


class FieldMapping(db.Model):
    """字段映射表，记录字段级别的语义映射关系"""
    __tablename__ = "field_mapping"

    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4, comment="主键ID")
    datasource_id = db.Column(db.Uuid, nullable=False, index=True, comment="数据源ID")
    schema_hash = db.Column(db.String(64), nullable=False, comment="Schema哈希值，用于标识数据源的特定版本")

    # 数据来源标识
    source_job_id = db.Column(db.Uuid, nullable=True, index=True, comment="来源任务ID（定向盘点时记录job_id）")

    source_table = db.Column(db.String(255), nullable=False, comment="源表名")
    source_column = db.Column(db.String(255), nullable=False, comment="源字段名")
    source_type = db.Column(db.String(255), nullable=True, comment="源字段类型")

    target_table = db.Column(db.String(255), nullable=False, comment="目标表名（参考表）")
    target_column = db.Column(db.String(255), nullable=False, comment="目标字段名（参考字段）")
    target_type = db.Column(db.String(255), nullable=True, comment="目标字段类型")

    mapping_type = db.Column(db.String(32), nullable=False, comment="映射类型：exact_match=精确匹配, semantic_match=语义匹配, fuzzy_match=模糊匹配")
    confidence = db.Column(db.Numeric(5, 4), nullable=False, comment="映射置信度，取值范围0~1，值越大表示映射越可靠")
    mapping_basis = db.Column(db.JSON, nullable=True, comment="映射依据（JSON格式），记录name_similarity、value_profile、llm_judgment等评分依据")

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(tz_cst), comment="创建时间")
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(tz_cst), onupdate=lambda: datetime.now(tz_cst), comment="更新时间")

    __table_args__ = (
        db.Index('idx_field_mapping_datasource_schema', 'datasource_id', 'schema_hash'),
        db.Index('idx_field_mapping_source', 'source_table', 'source_column'),
        db.Index('idx_field_mapping_target', 'target_table', 'target_column'),
        db.Index('idx_field_mapping_source_job', 'source_job_id'),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "datasource_id": str(self.datasource_id),
            "schema_hash": self.schema_hash,
            "source_table": self.source_table,
            "source_column": self.source_column,
            "source_type": self.source_type,
            "target_table": self.target_table,
            "target_column": self.target_column,
            "target_type": self.target_type,
            "mapping_type": self.mapping_type,
            "confidence": float(self.confidence) if self.confidence else None,
            "mapping_basis": self.mapping_basis or {},
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }


class TableRelationship(db.Model):
    """表关系表，记录表与表之间的关联关系（关系图谱中的边，支持单源和跨源）

    设计说明：
    - 每条关系记录代表两张表之间的一条边
    - 同源关系：table_a_datasource_id = table_b_datasource_id
    - 跨源关系：table_a_datasource_id ≠ table_b_datasource_id
    - 查询某数据源的所有关系时，使用 OR 条件查询两个 datasource_id 字段
    """
    __tablename__ = "table_relationship"

    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4, comment="主键ID")

    # 表A信息
    table_a = db.Column(db.String(255), nullable=False, comment="关联表A的表名")
    table_a_datasource_id = db.Column(db.Uuid, nullable=False, index=True, comment="表A所属数据源ID")
    table_a_schema_hash = db.Column(db.String(64), nullable=False, comment="表A的Schema哈希值")

    # 表B信息
    table_b = db.Column(db.String(255), nullable=False, comment="关联表B的表名")
    table_b_datasource_id = db.Column(db.Uuid, nullable=False, index=True, comment="表B所属数据源ID")
    table_b_schema_hash = db.Column(db.String(64), nullable=False, comment="表B的Schema哈希值")

    # 跨源标识（冗余字段，方便查询）
    is_cross_source = db.Column(db.Boolean, default=False, nullable=False, comment="是否跨源关系")

    # 数据来源标识
    source_type = db.Column(db.String(32), default='global_inventory', nullable=False, comment="数据来源类型：global_inventory=全域盘点, target_inventory=定向盘点, governance=数据治理")
    source_job_id = db.Column(db.Uuid, nullable=True, index=True, comment="来源任务ID（定向盘点时记录job_id，全域盘点时为NULL）")

    # 治理报告关联字段（仅 source_type=governance 时使用）
    governance_report_id = db.Column(db.Uuid, nullable=True, index=True, comment="关联的治理报告ID（仅 source_type=governance 时有值）")
    governance_job_id = db.Column(db.Uuid, nullable=True, index=True, comment="治理任务ID，用于区分同一报告的多次执行")

    relationship_type = db.Column(db.String(32), nullable=False, comment="关系类型：FK=主外键关联, Semantic=语义关联, Value=值域关联, Composite=复合关联")
    join_conditions = db.Column(db.JSON, nullable=False, comment="JOIN条件（JSON数组），每个元素包含local_field、remote_field、confidence、mapping_type等信息")
    relationship_strength = db.Column(db.Numeric(5, 4), nullable=False, comment="关系强度，取值范围0~1，综合评估关系的可信度")
    cardinality = db.Column(db.String(32), nullable=True, comment="基数/关联方向：one_to_one=一对一, one_to_many=一对多, many_to_many=多对多")

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(tz_cst), comment="创建时间")
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(tz_cst), onupdate=lambda: datetime.now(tz_cst), comment="更新时间")

    __table_args__ = (
        db.Index('idx_table_relationship_table_a_ds', 'table_a_datasource_id'),
        db.Index('idx_table_relationship_table_b_ds', 'table_b_datasource_id'),
        db.Index('idx_table_relationship_table_a', 'table_a'),
        db.Index('idx_table_relationship_table_b', 'table_b'),
        db.Index('idx_table_relationship_is_cross_source', 'is_cross_source'),
        db.Index('idx_table_relationship_source', 'source_type', 'source_job_id'),
        # 唯一约束调整：增加 source_job_id，允许同一表对在不同任务中有不同关系
        db.UniqueConstraint('table_a_datasource_id', 'table_a_schema_hash', 'table_a',
                           'table_b_datasource_id', 'table_b_schema_hash', 'table_b',
                           'source_job_id',
                           name='uq_table_relationship_pair'),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "table_a": self.table_a,
            "table_a_datasource_id": str(self.table_a_datasource_id),
            "table_a_schema_hash": self.table_a_schema_hash,
            "table_b": self.table_b,
            "table_b_datasource_id": str(self.table_b_datasource_id),
            "table_b_schema_hash": self.table_b_schema_hash,
            "is_cross_source": self.is_cross_source,
            "source_type": self.source_type,
            "source_job_id": str(self.source_job_id) if self.source_job_id else None,
            "governance_report_id": str(self.governance_report_id) if self.governance_report_id else None,
            "governance_job_id": str(self.governance_job_id) if self.governance_job_id else None,
            "relationship_type": self.relationship_type,
            "join_conditions": self.join_conditions or [],
            "relationship_strength": float(self.relationship_strength) if self.relationship_strength else None,
            "cardinality": self.cardinality,
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }


class TableRelationshipCard(db.Model):
    """表关系卡片表，存储每张表的关系元数据卡片（支持单源和跨源）

    设计说明：
    - 每张表有自己的关系卡片，记录该表与其他表的所有关系
    - datasource_id 是该表所属的数据源
    - 跨源关系会同时出现在两张表的卡片中（各自数据源下）
    """
    __tablename__ = "table_relationship_card"

    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4, comment="主键ID")
    datasource_id = db.Column(db.Uuid, nullable=False, index=True, comment="该表所属的数据源ID")
    schema_hash = db.Column(db.String(64), nullable=False, comment="Schema哈希值")
    table_name = db.Column(db.String(255), nullable=False, comment="表名")

    # 多源支持字段
    datasource_ids = db.Column(db.JSON, nullable=True, comment="参与的数据源ID列表（多源时使用，JSON数组）")  # 遗留字段，保留兼容
    related_datasource_ids = db.Column(db.JSON, nullable=True, comment="关联的其他数据源ID列表（跨源时使用，JSON数组）")
    has_cross_source_relations = db.Column(db.Boolean, default=False, nullable=False, comment="是否包含跨源关系")

    # 数据来源标识
    source_type = db.Column(db.String(32), default='global_inventory', nullable=False, comment="数据来源类型：global_inventory=全域盘点, target_inventory=定向盘点, governance=数据治理")
    source_job_id = db.Column(db.Uuid, nullable=True, index=True, comment="来源任务ID（定向盘点时记录job_id，全域盘点时为NULL）")

    # 治理报告关联字段（仅 source_type=governance 时使用）
    governance_report_id = db.Column(db.Uuid, nullable=True, index=True, comment="关联的治理报告ID（仅 source_type=governance 时有值）")
    governance_job_id = db.Column(db.Uuid, nullable=True, index=True, comment="治理任务ID，用于区分同一报告的多次执行")

    card_data = db.Column(db.JSON, nullable=False, comment="关系卡片数据（JSON格式），包含该表与其他表的所有关联关系信息")

    w_uuid = db.Column(db.String(255), nullable=True, index=True, comment="Weaviate向量索引UUID，用于向量检索")

    version = db.Column(db.Integer, default=1, comment="卡片版本号，支持版本管理和回滚")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(tz_cst), comment="创建时间")
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(tz_cst), onupdate=lambda: datetime.now(tz_cst), comment="更新时间")

    __table_args__ = (
        db.Index('idx_table_relationship_card_datasource', 'datasource_id'),
        db.Index('idx_table_relationship_card_w_uuid', 'w_uuid'),
        db.Index('idx_table_relationship_card_has_cross_source', 'has_cross_source_relations'),
        db.Index('idx_table_relationship_card_source', 'source_type', 'source_job_id'),
        # 唯一约束调整：增加 source_job_id，允许同一表在不同任务中有不同卡片
        db.UniqueConstraint('datasource_id', 'schema_hash', 'table_name', 'source_job_id', name='uq_table_relationship_card_datasource_table'),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "datasource_id": str(self.datasource_id),
            "schema_hash": self.schema_hash,
            "table_name": self.table_name,
            "datasource_ids": self.datasource_ids,
            "related_datasource_ids": self.related_datasource_ids,
            "has_cross_source_relations": self.has_cross_source_relations,
            "source_type": self.source_type,
            "source_job_id": str(self.source_job_id) if self.source_job_id else None,
            "governance_report_id": str(self.governance_report_id) if self.governance_report_id else None,
            "governance_job_id": str(self.governance_job_id) if self.governance_job_id else None,
            "card_data": self.card_data or {},
            "w_uuid": self.w_uuid,
            "version": self.version,
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }
