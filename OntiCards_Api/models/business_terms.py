"""
 @File: business_terms.py
 @Description: 业务术语表模型
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-05-14
 @Update: 2026-05-14 重构：移除 datasource_id，改用 library_id 关联术语库
"""

import uuid
import json
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import Column, String, Text, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from extensions.ext_database import db
from models.utils import format_datetime

if TYPE_CHECKING:
    pass


class BusinessTerm(db.Model):
    """业务术语表 - 属于某个术语库，用于NL2SQL查询时的术语识别和展开"""
    __tablename__ = "business_terms"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="主键ID"
    )
    library_id = Column(
        UUID(as_uuid=True),
        ForeignKey("business_term_libraries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联术语库ID"
    )
    term_name = Column(
        String(255),
        nullable=False,
        comment="术语名称"
    )
    term_alias = Column(
        Text,
        nullable=True,
        comment="术语别名（JSON数组）"
    )
    term_definition = Column(
        Text,
        nullable=False,
        comment="术语定义（包含计算口径）"
    )
    applicable_conditions = Column(
        Text,
        nullable=True,
        comment="适用条件（选填）"
    )
    remarks = Column(
        Text,
        nullable=True,
        comment="备注（选填）"
    )
    related_datacards = Column(
        Text,
        nullable=True,
        comment="关联的数据卡片/表（JSON数组）"
    )
    related_fields = Column(
        Text,
        nullable=True,
        comment="关联的字段（JSON数组）"
    )
    related_terms = Column(
        Text,
        nullable=True,
        comment="关联的其他术语（JSON数组）"
    )
    status = Column(
        String(20),
        nullable=False,
        default="active",
        index=True,
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

    __table_args__ = (
        UniqueConstraint("library_id", "term_name", name="uq_business_terms_library_term"),
    )

    def get_term_alias_list(self) -> List[str]:
        """获取术语别名列表"""
        if not self.term_alias:
            return []
        try:
            return json.loads(self.term_alias)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_related_datacards_list(self) -> List[dict]:
        """获取关联数据卡片列表"""
        if not self.related_datacards:
            return []
        try:
            return json.loads(self.related_datacards)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_related_fields_list(self) -> List[dict]:
        """获取关联字段列表"""
        if not self.related_fields:
            return []
        try:
            return json.loads(self.related_fields)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_related_terms_list(self) -> List[dict]:
        """获取关联术语列表"""
        if not self.related_terms:
            return []
        try:
            return json.loads(self.related_terms)
        except (json.JSONDecodeError, TypeError):
            return []

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "library_id": str(self.library_id),
            "library_name": self.library.name if self.library else None,
            "term_name": self.term_name,
            "term_alias": self.get_term_alias_list(),
            "term_definition": self.term_definition,
            "applicable_conditions": self.applicable_conditions,
            "remarks": self.remarks,
            "related_datacards": self.get_related_datacards_list(),
            "related_fields": self.get_related_fields_list(),
            "related_terms": self.get_related_terms_list(),
            "status": self.status,
            "created_by": str(self.created_by) if self.created_by else None,
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }

    def to_simple_dict(self) -> dict:
        """简洁版 dict（用于列表展示）"""
        return {
            "id": str(self.id),
            "library_id": str(self.library_id),
            "library_name": self.library.name if self.library else None,
            "term_name": self.term_name,
            "term_alias": self.get_term_alias_list(),
            "term_definition": self.term_definition,
            "status": self.status,
            "created_at": format_datetime(self.created_at),
        }

    def __repr__(self):
        return f"<BusinessTerm term_name={self.term_name} library_id={self.library_id}>"
