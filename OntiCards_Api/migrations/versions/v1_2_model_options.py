"""Add optional native model protocol settings."""

from alembic import op
from extensions.schema_validation import API_ROOT, verify_model_columns

revision = "v1_2"
down_revision = "v1_1"
branch_labels = None
depends_on = None
schema_version = "1.2"
SQL_FILE = API_ROOT / "scripts/migrations/20260916_model_native_options.sql"
checksum_files = (SQL_FILE,)


def upgrade():
    op.get_bind().exec_driver_sql(
        SQL_FILE.read_text(encoding="utf-8"), execution_options={"no_parameters": True}
    )


def verify(connection):
    verify_model_columns(connection, native_options=True)


def downgrade():
    raise RuntimeError("Automatic schema downgrade is not supported.")
