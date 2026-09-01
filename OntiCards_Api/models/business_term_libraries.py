"""
 @File: business_term_libraries.py
 @Description: 业务术语库表模型
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-05-14
"""

import uuid
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import Column, String, Text, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from extensions.ext_database import db
from models.utils import format_datetime

if TYPE_CHECKING:
    pass


class BusinessTermLibrary(db.Model):
    """业务术语库表 - 存储业务术语库，一个库包含多个业务术语"""
    __tablename__ = "business_term_libraries"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="主键ID"
    )
    name = Column(
        String(100),
        nullable=False,
        comment="术语库名称（如 财务术语库、电商零售术语库）"
    )
    description = Column(
        Text,
        nullable=True,
        comment="术语库描述"
    )
    category = Column(
        String(100),
        nullable=True,
        comment="行业分类（如 电商零售、财务管理、CRM客户管理）"
    )
    status = Column(
        String(20),
        nullable=False,
        default="active",
        comment="状态：active=启用，inactive=禁用"
    )
    created_by = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="创建人ID"
    )
    created_at = Column(
        db.TIMESTAMP(timezone=True),
        server_default=db.text("CURRENT_TIMESTAMP"),
        comment="创建时间"
    )
    updated_at = Column(
        db.TIMESTAMP(timezone=True),
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
        comment="更新时间"
    )

    # 关联术语
    terms = relationship(
        "BusinessTerm",
        backref="library",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    # 关联数据源-术语库关联记录（删除术语库时级联删除）
    datasource_links = relationship(
        "DatasourceTermLibrary",
        back_populates="library",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    def get_term_count(self) -> int:
        """获取术语数量"""
        return self.terms.count()

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "status": self.status,
            "term_count": self.get_term_count(),
            "created_by": str(self.created_by) if self.created_by else None,
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }

    def to_simple_dict(self) -> dict:
        """简洁版 dict（用于列表展示）"""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "status": self.status,
            "term_count": self.get_term_count(),
            "created_at": format_datetime(self.created_at),
        }

    def __repr__(self):
        return f"<BusinessTermLibrary name={self.name}>"
