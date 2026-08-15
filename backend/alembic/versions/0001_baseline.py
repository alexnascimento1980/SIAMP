"""SIAMP database baseline.

This revision intentionally does not create tables. It marks the existing
schema as the Alembic baseline. For a database already created by the previous
SIAMP version, use `alembic stamp 0001_baseline`.
"""

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
