"""Cria o modelo de lançamento livre (produção/parada), em paralelo
ao modelo por hora já existente.

- Turno.modelo_apontamento: HORARIO (padrão, todo turno já existente)
  ou LANCAMENTO (novo). Não há conversão entre os dois - é só um
  discriminador para saber qual tabela de apontamento ler.
- lancamentos_turno: produção ou parada com horário de início/fim
  livre (não mais preso a uma grade fixa de horas).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0010_lancamentos_turno"
down_revision = "0009_regulador_ciclo_contador"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def _table_exists(inspector, table_name):
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _column_exists(inspector, "turnos", "modelo_apontamento"):
        op.add_column(
            "turnos",
            sa.Column(
                "modelo_apontamento",
                sa.String(length=20),
                nullable=False,
                server_default="HORARIO",
            ),
        )

    if not _table_exists(inspector, "lancamentos_turno"):
        op.create_table(
            "lancamentos_turno",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("turno_id", sa.Integer(), sa.ForeignKey("turnos.id"), nullable=False),
            sa.Column("maquina_id", sa.Integer(), sa.ForeignKey("maquinas.id"), nullable=False),
            sa.Column("tipo", sa.String(length=20), nullable=False),
            sa.Column("horario_inicio", sa.Time(), nullable=False),
            sa.Column("horario_fim", sa.Time(), nullable=False),
            sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=True),
            sa.Column(
                "ordem_producao_id",
                sa.Integer(),
                sa.ForeignKey("ordens_producao.id"),
                nullable=True,
            ),
            sa.Column("quantidade", sa.Integer(), nullable=True),
            sa.Column("motivo", sa.String(length=150), nullable=True),
        )
        op.create_index(
            "ix_lancamentos_turno_turno_id", "lancamentos_turno", ["turno_id"]
        )
        op.create_index(
            "ix_lancamentos_turno_maquina_id", "lancamentos_turno", ["maquina_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "lancamentos_turno"):
        op.drop_table("lancamentos_turno")
    if _column_exists(inspector, "turnos", "modelo_apontamento"):
        op.drop_column("turnos", "modelo_apontamento")
