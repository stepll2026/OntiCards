"""
 @File: 0001_create_user_datasource_schemas.py
 @Description: Alembic 的首次迁移脚本 - 建表 UserDatasourceSchema
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-09-22 09:51
"""

"""create user_datasource_schemas

Revision ID: 0001_create_user_datasource_schemas
Revises: 
Create Date: 2025-09-22 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql

# revision identifiers, used by Alembic.
revision = '0001_create_user_ds_schemas'  # 版本号信息，注意不要过长
down_revision = None   # 需要回退的迁移前版本，此时为 None，代表这个文件所迁移的版本为链头结点（第一个版本）
branch_labels = None
depends_on = None


def upgrade():
    # 1) PostgreSQL 扩展：uuid-ossp（提供 uuid_generate_v4()）
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

    # 2) 建表
    op.create_table(
        'user_datasource_schemas',
        sa.Column('id', psql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('uuid_generate_v4()'),
                  comment='记录ID，主键，自增UUID'),
        sa.Column('user_id', psql.UUID(as_uuid=True), nullable=False,
                  comment='用户ID（UUID）'),
        sa.Column('db_type', sa.VARCHAR(length=32), nullable=False,
                  comment='数据库类型，如 oracle / postgres / mysql 等'),
        sa.Column('connect_info', sa.VARCHAR(length=2048), nullable=False,
                  comment='数据库连接信息（建议脱敏或加密后保存）'),
        sa.Column('database_name', sa.VARCHAR(length=256), nullable=False,
                  comment='数据库名 / schema 名'),
        sa.Column('schema_text', sa.TEXT(), nullable=False,
                  comment='表结构信息（文本，建议存JSON字符串）'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP'),
                  nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP'),
                  nullable=False, comment='更新时间（可在应用层按需更新）'),
        # 也可加表注释
        comment='用户数据源的库结构快照'
    )

    # 3) 索引（常用查询字段）
    op.create_index(
        'ix_user_datasource_schemas_user_id',
        'user_datasource_schemas',
        ['user_id'],
        unique=False
    )

    # # （可选）唯一约束：同一用户 + 类型 + 数据库名 仅一条
    # op.create_unique_constraint(
    #     'uq_user_ds_type_and_name',
    #     'user_datasource_schemas',
    #     ['user_id', 'db_type', 'database_name']
    # )

    # （可选进阶）如果希望 updated_at 在 DB 侧自动更新，可创建触发器：
    # op.execute("""
    # CREATE OR REPLACE FUNCTION set_updated_at()
    # RETURNS TRIGGER AS $$
    # BEGIN
    #   NEW.updated_at = CURRENT_TIMESTAMP;
    #   RETURN NEW;
    # END;
    # $$ LANGUAGE plpgsql;
    # """)
    # op.execute("""
    # CREATE TRIGGER trg_user_ds_schemas_updated_at
    # BEFORE UPDATE ON user_datasource_schemas
    # FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
    # """)


def downgrade():
    # （如创建了触发器，先删）
    # op.execute("DROP TRIGGER IF EXISTS trg_user_ds_schemas_updated_at ON user_datasource_schemas;")
    # op.execute("DROP FUNCTION IF EXISTS set_updated_at;")

    op.drop_index('ix_user_datasource_schemas_user_id', table_name='user_datasource_schemas')
    # op.drop_constraint('uq_user_ds_type_and_name', 'user_datasource_schemas', type_='unique')
    op.drop_table('user_datasource_schemas')
    # 注意：不 drop 扩展，避免影响其它对象
