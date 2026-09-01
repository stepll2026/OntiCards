
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func, text
from extensions.ext_database import db

class Model_configuration(db.Model):
    __tablename__ = 'model_config'  # 对应表名
    __table_args__ = (
        db.PrimaryKeyConstraint('id', name='model_configuration_pkey'),
    )
    id = db.Column(UUID, server_default=db.text('uuid_generate_v4()'), nullable=False, comment='模型id')
    model_name = db.Column(db.String, nullable=False, comment='模型名称')
    model_type = db.Column(db.String, nullable=False, comment='模型类型（豆包、千问、DS）')
    model_api_key = db.Column(db.String, nullable=True, comment='模型apikey')
    created_at = db.Column(db.TIMESTAMP(timezone=True), server_default=func.current_timestamp(), comment='創建時間')
    updated_at = db.Column(db.TIMESTAMP(timezone=True), server_default=func.current_timestamp(),
                           onupdate=func.current_timestamp(), comment='更新時間')
    model_class = db.Column(db.String(255), nullable=False, comment='模型作用类别（大语言、重排序、向量化嵌入）')
    url = db.Column(db.String(255), nullable=False, comment='模型接口url')

    # 这里是为了方便理解，类的属性不必要再写重复的注释。
