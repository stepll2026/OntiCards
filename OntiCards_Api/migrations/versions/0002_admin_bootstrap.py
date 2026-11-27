"""Record completion for existing OntiCards deployments."""

from alembic import op
from sqlalchemy import column, table

from core.admin_bootstrap import migrate_bootstrap_state


revision = "0002_admin_bootstrap"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade():
    users = table("users", column("id"), schema="public")
    migrate_bootstrap_state(op.get_bind(), users)


def downgrade():
    # Keep consumed bootstrap state across a downgrade.
    pass
