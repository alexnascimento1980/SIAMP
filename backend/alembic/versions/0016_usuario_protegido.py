"""Adiciona protegido ao Usuario - marca uma conta como protegida
contra exclusão e desativação acidental por outro ADMIN (a
auto-proteção existente só cobre a própria conta de quem está
logado, não a de outro administrador).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0016_usuario_protegido"
down_revision = "0015_lancamento_turno_cascade"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _column_exists(inspector, "usuarios", "protegido"):
        op.add_column(
            "usuarios",
            sa.Column(
                "protegido",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.alter_column("usuarios", "protegido", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _column_exists(inspector, "usuarios", "protegido"):
        op.drop_column("usuarios", "protegido")
