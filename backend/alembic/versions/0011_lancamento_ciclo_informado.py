"""Adiciona ciclo_informado ao Lancamento - ciclo real informado
manualmente pelo operador, para comparar com o ciclo médio padrão
cadastrado na peça. Prioridade máxima no cálculo de capacidade
esperada, mesma lógica já usada no modelo por hora (RegistroHorario.
ciclo_informado).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0011_lancamento_ciclo_informado"
down_revision = "0010_lancamentos_turno"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _column_exists(inspector, "lancamentos_turno", "ciclo_informado"):
        op.add_column(
            "lancamentos_turno",
            sa.Column("ciclo_informado", sa.Float(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _column_exists(inspector, "lancamentos_turno", "ciclo_informado"):
        op.drop_column("lancamentos_turno", "ciclo_informado")
