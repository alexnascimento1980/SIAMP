"""Vincula a Ordem de Produção a uma peça já cadastrada (produto_id).

O cadastro de OP passa a exigir a seleção de uma peça do catálogo já
existente (evita erro de digitação), em vez de aceitar código e
descrição como texto livre.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0008_ordem_producao_produto_id"
down_revision = "0007_registro_ordem_producao"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _column_exists(inspector, "ordens_producao", "produto_id"):
        op.add_column(
            "ordens_producao",
            sa.Column(
                "produto_id",
                sa.Integer(),
                sa.ForeignKey("produtos.id"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _column_exists(inspector, "ordens_producao", "produto_id"):
        op.drop_column("ordens_producao", "produto_id")
