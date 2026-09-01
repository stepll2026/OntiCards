"""
 @File: user_datasource_schema.py
 @Description: 绑定用户及其的数据源相关信息（库类型、库名、连接参数、表结构信息）
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-09-19 09:44
"""

from sqlalchemy.dialects.postgresql import UUID, TEXT, VARCHAR
from sqlalchemy import func, text
from extensions.ext_database import db

# 导入加密模块
from core.connect_info_encryptor import decrypt_connect_info


class UserDatasourceSchema(db.Model):
    __tablename__ = 'user_datasource_schemas'

    # 主键
    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text('uuid_generate_v4()'),
        comment='记录ID，主键，自增UUID'
    )

    # 业务字段
    user_id = db.Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment='用户ID（UUID）'
    )
    db_type = db.Column(
        VARCHAR(32),
        nullable=False,
        comment='数据库类型，如 oracle / postgres / mysql 等'
    )
    connect_info = db.Column(
        VARCHAR(4096),  # 扩大长度以容纳加密后的数据
        nullable=False,
        comment='数据库连接信息（加密存储）'
    )
    connect_name = db.Column(
        VARCHAR(2048),
        nullable=False,
        comment='数据源名称'
    )
    database_name = db.Column(
        VARCHAR(256),
        nullable=False,
        comment='数据库名 / schema 名（按你的业务定义）'
    )
    schema_text = db.Column(
        TEXT,
        nullable=False,
        comment='表结构信息（文本，建议存JSON字符串）'
    )
    table_name = db.Column(
        VARCHAR(255),
        nullable=False,
        comment='数据表名'
    )
    db_version = db.Column(
        VARCHAR(255),
        nullable=False,
        comment='数据库版本信息'
    )

    # 审计字段
    created_at = db.Column(
        db.TIMESTAMP(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
        comment='创建时间'
    )
    updated_at = db.Column(
        db.TIMESTAMP(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
        comment='更新时间'
    )

    is_filled = db.Column(
        db.Boolean,
        server_default=text('false'),
        nullable=True,
        comment='字段描述是否经过LLM填充'
    )

    filled_data = db.Column(
        TEXT,
        nullable=True,
        comment='LLM填充结果'
    )

    catalog_type = db.Column(
        VARCHAR(32),
        nullable=True,
        comment='Trino catalog 类型（如 mysql、postgresql），仅 Trino 数据源需要'
    )

    # 新增：视图标识
    is_view = db.Column(
        db.Boolean,
        server_default=text('false'),
        nullable=True,
        comment='是否为视图（true=视图，false=普通表）'
    )

    view_name = db.Column(
        VARCHAR(255),
        nullable=True,
        comment='视图名称（若 is_view=true，则记录视图名）'
    )

    # 数据源 schema 名（PG/MSSQL/Trino/Oracle 用于去重和关联；MySQL 可空/SQLite 可空）
    # 重要：对于 PG/MSSQL/Oracle，同一 (user_id, connect_info) 下不同 schema 应被视为不同数据源工作空间
    # 该字段作为"按 db_type 分支"的关联键。MySQL 的 schema_name 可保持 NULL（旧行为不变）。
    schema_name = db.Column(
        VARCHAR(128),
        nullable=True,
        comment='数据源 schema 名（PG/MSSQL/Trino/Oracle 生效；MySQL/SQLite 可空）'
    )

    # 连接信息哈希：用于快速匹配和去重（因为 AES-GCM 加密每次使用随机 nonce，无法直接匹配）
    connect_info_hash = db.Column(
        VARCHAR(64),
        nullable=True,
        index=True,
        comment='连接信息的稳定哈希值（SHA256），用于匹配和去重'
    )

    # 可选：便捷索引/唯一约束（按需开启）
    __table_args__ = (
        # 用户id+数据库连接信息+schema+表名
        # 注意：PG/MSSQL/Oracle 等多 schema 场景下，必须把 schema_name 加入才能区分同 connect_info 不同 schema 的同名表
        # MySQL/SQLite 等 schema_name=NULL 的数据库，PG 的 NULL 唯一约束默认 NULL != NULL（视为不同），
        # 因此 NULL 与 NULL 视为不同——这与历史行为一致，不会误伤 MySQL/SQLite 的去重
        db.UniqueConstraint('user_id', 'connect_info', 'schema_name', 'table_name',
                            name='uq_userid_connectinfo_schema_tablename'),
        # 通用索引：加速按 user + connect + schema 维度查询
        db.Index('idx_uds_user_conninfo_schema', 'user_id', 'connect_info', 'schema_name'),
    )

    @property
    def connect_info_decrypted(self) -> str:
        """
        获取解密后的连接信息（内部使用，连接数据库时调用）
        自动处理加密/非加密数据
        """
        return decrypt_connect_info(self.connect_info)
