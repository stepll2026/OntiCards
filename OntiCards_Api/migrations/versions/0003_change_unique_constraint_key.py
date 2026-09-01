# -*- coding: utf-8 -*-
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_change_unique_constraint"
down_revision = "0002_add_unique_constraint"
branch_labels = None
depends_on = None

def upgrade():
    # 兼容处理：无论旧约束名是哪一个，都尝试删掉（Postgres 语法 IF EXISTS）
    op.execute("""
    ALTER TABLE user_datasource_schemas
      DROP CONSTRAINT IF EXISTS uq_user_ds_type_and_name;
    """)
    op.execute("""
    ALTER TABLE user_datasource_schemas
      DROP CONSTRAINT IF EXISTS uq_user_dbtype_dbname;
    """)

    # 新唯一约束：同一用户 + 同一连接信息 + 同一表名 只保留一条
    op.create_unique_constraint(
        "uq_userid_connectinfo_tablename",
        "user_datasource_schemas",
        ["user_id", "connect_info", "table_name"],
    )


def downgrade():
    # 回滚：删掉新约束
    op.execute("""
    ALTER TABLE user_datasource_schemas
      DROP CONSTRAINT IF EXISTS uq_userid_connectinfo_tablename;
    """)

    # 恢复旧的唯一约束（与你之前 0002 的一致）
    op.create_unique_constraint(
        "uq_user_ds_type_and_name",
        "user_datasource_schemas",
        ["user_id", "db_type", "database_name"],
    )