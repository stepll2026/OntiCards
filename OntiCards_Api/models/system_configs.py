"""
 @File: system_configs.py
 @Description: 系统配置表
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-03-30
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, UniqueConstraint

from extensions.ext_database import db
from models.utils import format_datetime


class SystemConfig(db.Model):
    """系统配置表"""
    __tablename__ = "system_configs"

    # === 主键 ===
    id = Column(
        db.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="主键ID"
    )

    # === 用户ID（可选）===
    # NULL 表示系统级全局配置，非NULL表示用户级别配置
    user_id = Column(
        db.UUID(as_uuid=True),
        nullable=True,
        comment="所属用户ID（NULL=系统级配置）"
    )

    # === 配置键值 ===
    config_key = Column(
        String(128),
        nullable=False,
        comment="配置键"
    )

    config_value = Column(
        Text,
        comment="配置值"
    )

    description = Column(
        String(256),
        comment="配置描述"
    )

    # === 时间戳 ===
    created_at = Column(
        db.TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        comment="记录创建时间"
    )

    updated_at = Column(
        db.TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="记录更新时间"
    )

    # === 唯一约束 ===
    __table_args__ = (
        UniqueConstraint('config_key', 'user_id', name='uq_config_key_user_id'),
    )

    def __repr__(self):
        user_part = f"user={self.user_id}" if self.user_id else "system"
        return f"<SystemConfig key={self.config_key} {user_part}>"

    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "config_key": self.config_key,
            "config_value": self.config_value,
            "description": self.description,
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }


def get_config(key: str, user_id=None, default=None):
    """
    获取系统配置（支持用户级别）

    Args:
        key: 配置键名
        user_id: 用户ID（可选，为None时查询系统级配置）
        default: 默认值（当配置不存在时返回）

    Returns:
        配置值（字符串），如果不存在则返回默认值
    """
    if user_id:
        # 优先查询用户级配置
        config = SystemConfig.query.filter_by(
            config_key=key,
            user_id=user_id
        ).first()
        if config:
            return config.config_value

        # 用户无自定义，回退到系统级默认值
        config = SystemConfig.query.filter_by(
            config_key=key,
            user_id=None
        ).first()
        if config:
            return config.config_value
        return default
    else:
        # 系统级查询
        config = SystemConfig.query.filter_by(
            config_key=key,
            user_id=None
        ).first()
        if config:
            return config.config_value
        return default


def get_config_as_float(key: str, user_id=None, default: float = 0.0) -> float:
    """
    获取系统配置（浮点类型，支持用户级别）

    Args:
        key: 配置键名
        user_id: 用户ID（可选）
        default: 默认值

    Returns:
        配置值（浮点），如果不存在或转换失败则返回默认值
    """
    value = get_config(key, user_id=user_id)
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def get_config_as_int(key: str, user_id=None, default: int = 0) -> int:
    """
    获取系统配置（整数类型，支持用户级别）

    Args:
        key: 配置键名
        user_id: 用户ID（可选）
        default: 默认值

    Returns:
        配置值（整数），如果不存在或转换失败则返回默认值
    """
    value = get_config(key, user_id=user_id)
    if value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def set_config(key: str, value, description: str = None, validate_price: bool = True, user_id=None) -> bool:
    """
    更新或创建系统配置（支持用户级别）

    Args:
        key: 配置键名
        value: 配置值
        description: 配置描述（可选）
        validate_price: 是否校验价格配置（默认True）
        user_id: 用户ID（可选，None表示系统级配置）

    Returns:
        True 成功，False 失败

    Raises:
        ValueError: 当校验失败时抛出
    """
    # 价格配置校验（仅对系统级配置）
    if validate_price and user_id is None:
        price_ranges = {
            'token_price_embedding': (0.00001, 0.1),
            'token_price_rerank': (0.0001, 0.5),
            'token_price_llm_input': (0.0001, 0.5),
            'token_price_llm_output': (0.0001, 1.0),
        }

        if key in price_ranges:
            try:
                float_value = float(value)
                min_val, max_val = price_ranges[key]
                if not (min_val <= float_value <= max_val):
                    raise ValueError(
                        f"价格 {float_value} 不在合理范围内 [{min_val}, {max_val}]，"
                        f"请确认价格单位是否正确（应为元/千token）"
                    )
            except (ValueError, TypeError) as e:
                if "could not convert" in str(e):
                    raise ValueError(f"配置值 '{value}' 不是有效的数字")
                raise

    # 查找或创建配置（按 config_key + user_id 查询）
    config = SystemConfig.query.filter_by(
        config_key=key,
        user_id=user_id
    ).first()

    if config:
        config.config_value = str(value)
        if description:
            config.description = description
    else:
        config = SystemConfig(
            config_key=key,
            config_value=str(value),
            description=description,
            user_id=user_id
        )
        db.session.add(config)

    db.session.commit()
    return True