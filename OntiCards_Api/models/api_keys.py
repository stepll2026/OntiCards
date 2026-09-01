"""
 @File: api_keys.py
 @Description: api_key 实体类
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-12-29 13:55
"""

import uuid
from datetime import datetime

from sqlalchemy.dialects.postgresql import UUID

from extensions.ext_database import db


class ApiKey(db.Model):
    __tablename__ = "api_keys"

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="API Key 主键 ID"
    )

    user_id = db.Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属用户 ID，用于数据源和数据空间隔离"
    )

    name = db.Column(
        db.String(64),
        nullable=False,
        comment="API Key 名称/备注，用于区分不同 Key"
    )

    api_key = db.Column(
        db.String(128),
        nullable=False,
        unique=True,
        comment="API Key 明文字符串，用于接口鉴权"
    )

    status = db.Column(
        db.String(16),
        nullable=False,
        default="active",
        comment="API Key 状态：active=可用，disabled=已禁用"
    )

    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
        comment="API Key 过期时间，超过该时间后即视为失效，为空代表永不过期"
    )

    last_used_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
        comment="API Key 最近一次成功调用接口的时间"
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="API Key 创建时间"
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="API Key 更新时间"
    )

    def __repr__(self):
        return f"<ApiKey id={self.id} name={self.name} user_id={self.user_id}>"
