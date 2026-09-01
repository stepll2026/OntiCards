"""
 @File: 0002_create_datacards_datasource.py
 @Description: Alembic 迁移脚本 - 建表 datacards_datasource
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-09-25 18:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0004_create_datacards_datasource'  # 新版本号
down_revision = '0003_change_unique_constraint'  # 上一个迁移脚本的 revision
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'datacards_datasource',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True, comment="主键ID"),

        # 业务字段
        sa.Column('doc_id', sa.String(length=255), nullable=False, comment="文档ID"),
        sa.Column('w_uuid', sa.String(length=255), nullable=False, unique=True, comment="Weaviate UUID"),
        sa.Column('card_data', sa.Text, nullable=False, comment="卡片数据(JSON字符串)"),

        # 审计字段
        sa.Column('created_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP'),
                  nullable=False, comment="创建时间"),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP'),
                  nullable=False, comment="修改时间（触发器或应用更新）"),

        comment="数据卡片来源数据表"
    )

    # 索引
    op.create_index(
        'ix_datacards_datasource_doc_id',
        'datacards_datasource',
        ['doc_id'],
        unique=False
    )


def downgrade():
    op.drop_index('ix_datacards_datasource_doc_id', table_name='datacards_datasource')
    op.drop_table('datacards_datasource')
