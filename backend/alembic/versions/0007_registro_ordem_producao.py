"""Vincula o apontamento horário à Ordem de Produção atendida.

Permite comparar meta x produção real por peça/OP em vez de por
máquina+período, já que a mesma OP pode ser produzida em mais de uma
injetora simultaneamente - somar por máquina+data seria só uma
aproximação. Também deixa o número da OP disponível no relatório de
turno (qual OP foi atendida em cada hora/máquina).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0007_registro_ordem_producao"
down_revision = "0006_ordens_producao"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _column_exists(inspector, "registros_horarios", "ordem_producao_id"):
        op.add_column(
            "registros_horarios",
            sa.Column(
                "ordem_producao_id",
                sa.Integer(),
                sa.ForeignKey("ordens_producao.id"),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_registros_horarios_ordem_producao_id",
            "registros_horarios",
            ["ordem_producao_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _column_exists(inspector, "registros_horarios", "ordem_producao_id"):
        op.drop_column("registros_horarios", "ordem_producao_id")
