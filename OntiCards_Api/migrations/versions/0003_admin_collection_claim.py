"""Persist independent ownership evidence for new administrator collections."""

from alembic import op
from sqlalchemy import column, table

from core.admin_bootstrap import migrate_bootstrap_state


revision = "0003_admin_collection_claim"
down_revision = "0002_admin_bootstrap"
branch_labels = None
depends_on = None


def upgrade():
    migrate_bootstrap_state(op.get_bind(), table("users", column("id"), schema="public"))


def downgrade():
    # Keep the claim alongside the consumed bootstrap marker.
    pass
