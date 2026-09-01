"""
 @File: datasource_term_library.py
 @Description: 数据源-术语库关联表模型
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-05-14

 说明：此表用于建立数据源与术语库的多对多关联关系
       - 一个数据源可以添加多个术语库
       - 一个术语库可以被多个数据源引用
       - 每个关联关系独立控制启用/禁用状态
"""

import uuid
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Column, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from extensions.ext_database import db
from models.utils import format_datetime

if TYPE_CHECKING:
    pass


class DatasourceTermLibrary(db.Model):
    """数据源-术语库关联表 - 建立数据源与术语库的多对多关系"""
    __tablename__ = "datasource_term_library"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="主键ID"
    )
    datasource_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="数据源ID"
    )
    library_id = Column(
        UUID(as_uuid=True),
        ForeignKey("business_term_libraries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="术语库ID"
    )
    is_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用：true=启用，false=禁用"
    )
    added_by = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="添加人ID"
    )
    added_at = Column(
        db.TIMESTAMP(timezone=True),
        server_default=db.text("CURRENT_TIMESTAMP"),
        comment="添加时间"
    )
    updated_at = Column(
        db.TIMESTAMP(timezone=True),
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
        comment="更新时间"
    )

    # 关联术语库
    library = relationship(
        "BusinessTermLibrary",
        foreign_keys=[library_id],
        back_populates="datasource_links",
        lazy="joined"
    )

    __table_args__ = (
        # 同一数据源不能重复添加同一术语库
        UniqueConstraint("datasource_id", "library_id", name="uq_datasource_library"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "datasource_id": str(self.datasource_id),
            "library_id": str(self.library_id),
            "library_name": self.library.name if self.library else None,
            "library_category": self.library.category if self.library else None,
            "library_description": self.library.description if self.library else None,
            "library_status": self.library.status if self.library else None,
            "library_term_count": self.library.get_term_count() if self.library else 0,
            "is_enabled": self.is_enabled,
            "added_by": str(self.added_by) if self.added_by else None,
            "added_at": format_datetime(self.added_at),
            "updated_at": format_datetime(self.updated_at),
        }

    def to_simple_dict(self) -> dict:
        """简洁版 dict（用于列表展示）"""
        return {
            "id": str(self.id),
            "datasource_id": str(self.datasource_id),
            "library_id": str(self.library_id),
            "library_name": self.library.name if self.library else None,
            "library_category": self.library.category if self.library else None,
            "library_term_count": self.library.get_term_count() if self.library else 0,
            "is_enabled": self.is_enabled,
            "added_at": format_datetime(self.added_at),
        }

    def __repr__(self):
        return f"<DatasourceTermLibrary datasource={self.datasource_id} library={self.library_id} enabled={self.is_enabled}>"
