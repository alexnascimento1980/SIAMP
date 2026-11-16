"""Adiciona token_version ao Usuario - versão da sessão, conferida a
cada request contra o claim "tv" do JWT. Incrementada no reset de
senha para invalidar os tokens emitidos antes.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0020_usuario_token_version"
down_revision = "0019_turno_criado_por"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _column_exists(inspector, "usuarios", "token_version"):
        op.add_column(
            "usuarios",
            sa.Column(
                "token_version",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _column_exists(inspector, "usuarios", "token_version"):
        op.drop_column("usuarios", "token_version")
