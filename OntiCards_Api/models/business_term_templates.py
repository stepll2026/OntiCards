"""
 @File: business_term_templates.py
 @Description: 业务术语模板表模型
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-05-14
"""

import json
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import Column, String, Text
from extensions.ext_database import db
from models.utils import format_datetime

if TYPE_CHECKING:
    pass


class BusinessTermTemplate(db.Model):
    """业务术语模板表 - 预置行业术语模板，只读不修改，用户可导入到业务术语表"""
    __tablename__ = "business_term_templates"

    id = Column(
        String(50),
        primary_key=True,
        comment="模板术语ID（如 tmpl-er-001）"
    )
    category = Column(
        String(100),
        nullable=False,
        index=True,
        comment="行业/场景分类（如 电商零售、ERP生产制造）"
    )
    template_name = Column(
        String(255),
        nullable=False,
        comment="模板名称（如 电商零售-交易类）"
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
    source = Column(
        String(100),
        nullable=False,
        default="system",
        index=True,
        comment="来源：system=系统预置，custom=用户自定义"
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

    def get_term_alias_list(self) -> List[str]:
        """获取术语别名列表"""
        if not self.term_alias:
            return []
        try:
            return json.loads(self.term_alias)
        except (json.JSONDecodeError, TypeError):
            return []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "template_name": self.template_name,
            "term_name": self.term_name,
            "term_alias": self.get_term_alias_list(),
            "term_definition": self.term_definition,
            "applicable_conditions": self.applicable_conditions,
            "remarks": self.remarks,
            "source": self.source,
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }

    def to_simple_dict(self) -> dict:
        """简洁版 dict（用于列表展示）"""
        return {
            "id": self.id,
            "category": self.category,
            "template_name": self.template_name,
            "term_name": self.term_name,
            "term_alias": self.get_term_alias_list(),
            "term_definition": self.term_definition,
        }

    def __repr__(self):
        return f"<BusinessTermTemplate term_name={self.term_name} category={self.category}>"
