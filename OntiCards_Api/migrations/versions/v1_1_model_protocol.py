"""Add model protocol and optional embedding dimensions."""

from alembic import op
from extensions.schema_validation import API_ROOT, verify_model_columns

revision = "v1_1"
down_revision = "v1"
branch_labels = None
depends_on = None
schema_version = "1.1"
SQL_FILE = API_ROOT / "scripts/migrations/20260916_model_protocol.sql"
checksum_files = (SQL_FILE,)


def upgrade():
    op.get_bind().exec_driver_sql(
        SQL_FILE.read_text(encoding="utf-8"), execution_options={"no_parameters": True}
    )


def verify(connection):
    verify_model_columns(connection)


def downgrade():
    raise RuntimeError("Automatic schema downgrade is not supported.")
