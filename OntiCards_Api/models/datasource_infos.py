"""
 @File: datasource_infos.py
 @Description: 数据源信息表模型
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-10-22 11:59
"""

from sqlalchemy.dialects.postgresql import UUID, VARCHAR, INTEGER
from sqlalchemy import func, text
from extensions.ext_database import db
from models.utils import format_datetime

# 导入加密模块
from core.connect_info_encryptor import encrypt_connect_info, decrypt_connect_info, is_encrypted
from sqlalchemy.orm import declared_attr


class DatasourceInfo(db.Model):
    """
    用于记录每个用户下的数据源摘要信息（一个连接一条）
    对应表结构：
      - table_num: 记录该数据源包含的表数量
      - status: 数据源连接状态（connected / disconnected / unstable）
      - created_at / updated_at: 审计字段
    """
    __tablename__ = "datasource_infos"

    # 主键（建议增加）
    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
        comment="主键ID"
    )

    # 业务字段
    user_id = db.Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="用户ID"
    )

    connect_info = db.Column(
        VARCHAR(2048),  # 扩大长度以容纳加密后的数据
        nullable=False,
        comment="数据源连接信息（加密存储）"
    )

    connect_name = db.Column(
        VARCHAR(255),
        nullable=False,
        comment="数据源名称"
    )

    table_num = db.Column(
        INTEGER,
        nullable=False,
        default=0,
        comment="数据表数量"
    )

    status = db.Column(
        VARCHAR(255),
        nullable=False,
        server_default=text("'available'"),
        comment="数据源状态，如 available、unavailable"
    )

    db_type = db.Column(
        VARCHAR(255),
        nullable=False,
        comment="数据库类型，如 MySQL / PostgreSQL / SQL Server / Oracle"
    )

    database_name = db.Column(
        VARCHAR(255),
        nullable=True,
        comment="数据库名称"
    )

    schema_name = db.Column(
        VARCHAR(128),
        nullable=True,
        comment="数据源默认 schema（PostgreSQL/MSSQL/Trino/Oracle 生效；MySQL可为空或等同database_name）"
    )

    created_at = db.Column(
        db.TIMESTAMP(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
        comment="创建时间"
    )

    updated_at = db.Column(
        db.TIMESTAMP(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
        comment="更新时间"
    )

    catalog_type = db.Column(
        VARCHAR(32),
        nullable=True,
        comment='Trino catalog 类型（如 mysql、postgresql），仅 Trino 数据源需要'
    )

    # 连接信息哈希：用于与 user_datasource_schemas 表关联匹配
    connect_info_hash = db.Column(
        VARCHAR(64),
        nullable=True,
        index=True,
        comment='连接信息的稳定哈希值（SHA256），用于与表结构数据关联匹配'
    )

    # 唯一约束：同一用户下数据源名称（connect_name）唯一
    # 注：原约束 (user_id, connect_info) 已被移除，原因是 PG/MSSQL/Oracle 等允许同一 connect_info 不同 schema 共存
    # 新约束不直接用 (user_id, connect_info) —— connect_info 在 schema_name 不同时可重复
    # 这部分去重在应用层（ExtractSchemaAPI 入口校验 + upsert 兜底）按 db_type 分支判断
    __table_args__ = (
        db.UniqueConstraint("user_id", "connect_name", name="uq_user_connect_name"),
    )

    @property
    def connect_info_decrypted(self) -> str:
        """
        获取解密后的连接信息（内部使用，连接数据库时调用）
        自动处理加密/非加密数据
        """
        return decrypt_connect_info(self.connect_info)

    @property
    def connect_info_safe(self) -> str:
        """
        获取脱敏后的连接信息（返回给前端时调用）
        将密码部分替换为 ******（6个星号）
        """
        from sqlalchemy import make_url
        raw = decrypt_connect_info(self.connect_info)
        try:
            # 先用 SQLAlchemy 渲染，然后用 6 个 * 替换默认的 3 个 *
            rendered = make_url(raw).render_as_string(hide_password=True)
            return rendered.replace("***", "******", 1)
        except Exception:
            # 如果解析失败，至少隐藏部分字符
            if len(raw) > 10:
                return raw[:len(raw)//2] + "******" + raw[-5:]
            return "******"

    def to_dict(self):
        """便捷转换：序列化给前端（使用脱敏后的连接信息）"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "connect_name": self.connect_name,
            "db_type": self.db_type,
            "database_name": self.database_name,
            "schema_name": self.schema_name,
            "connect_info": self.connect_info_safe,  # 返回脱敏后的连接信息
            "table_num": self.table_num,
            "status": self.status,
            "catalog_type": self.catalog_type,
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }
