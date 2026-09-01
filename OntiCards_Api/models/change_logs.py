"""
 @File: change_logs.py
 @Description: 版本更新日志模型
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-11-05 10:20
"""

from datetime import datetime, timezone
from extensions.ext_database import db

class Changelog(db.Model):
    __tablename__ = "change_logs"
    id = db.Column(db.BigInteger, primary_key=True)
    version = db.Column(db.String(50), nullable=False, unique=True)
    title = db.Column(db.String(200), nullable=False)
    content_md = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(10), nullable=False, default="hidden")
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
