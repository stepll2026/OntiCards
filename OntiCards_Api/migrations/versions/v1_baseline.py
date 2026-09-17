"""Adopt the existing OntiCards schema, or initialize an empty database."""

from alembic import op
from extensions.schema_validation import API_ROOT, BASELINE_FILE, verify_baseline
from sqlalchemy import inspect

revision = "v1"
down_revision = None
branch_labels = None
depends_on = None
schema_version = "1.0"
checksum_files = (BASELINE_FILE,)


def upgrade():
    connection = op.get_bind()
    tables = set(inspect(connection).get_table_names(schema="public"))
    if not tables.difference({"alembic_version", "schema_migrations"}):
        # The PostgreSQL driver executes the entire script transactionally,
        # including comments, quoted semicolons and multi-line statements.
        sql = (API_ROOT / "init.sql").read_text(encoding="utf-8")
        connection.exec_driver_sql(sql, execution_options={"no_parameters": True})
    verify(connection)


def verify(connection):
    verify_baseline(connection)


def downgrade():
    raise RuntimeError("Automatic schema downgrade is not supported.")
