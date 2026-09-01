"""add unique constraint to user_datasource_schemas

Revision ID: 0002_add_unique_constraint
Revises: 0001_create_user_ds_schemas
Create Date: 2025-09-22 14:30
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_add_unique_constraint" # 新的版本链节点
down_revision = "0001_create_user_ds_schemas"  # 要回退的迁移前版本，注意要和上一个节点的版本号revision
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_user_ds_type_and_name",
        "user_datasource_schemas",   # 指定了要修改的表名
        ["user_id", "db_type", "database_name"],
    )


def downgrade():
    op.drop_constraint(
        "uq_user_ds_type_and_name",
        "user_datasource_schemas",
        type_="unique",
    )
