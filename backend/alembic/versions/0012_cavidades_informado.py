"""Adiciona cavidades_informado ao Lancamento - cavidades realmente
utilizadas naquele lançamento, informadas manualmente pelo operador
quando divergem do cadastro (ex.: cavidade temporariamente
desativada). Mesmo padrão já usado para ciclo_informado (migration
0011) - prioridade máxima no cálculo de capacidade esperada.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0012_cavidades_informado"
down_revision = "0011_lancamento_ciclo_informado"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _column_exists(inspector, "lancamentos_turno", "cavidades_informado"):
        op.add_column(
            "lancamentos_turno",
            sa.Column("cavidades_informado", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _column_exists(inspector, "lancamentos_turno", "cavidades_informado"):
        op.drop_column("lancamentos_turno", "cavidades_informado")
