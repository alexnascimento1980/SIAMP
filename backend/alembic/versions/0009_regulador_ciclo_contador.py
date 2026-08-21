"""Adiciona regulador do turno e campos de ciclo/contador na parada.

- Turno.regulador_nome: segundo responsável do turno (além do líder),
  papel comum em injeção plástica (regulador de máquina/molde).
- RegistroHorario.ciclo_informado: ciclo real informado pelo operador
  para aquela hora/máquina, tem prioridade sobre o ciclo da peça/
  máquina no cálculo de capacidade esperada - usado quando o ciclo
  padrão não reflete a realidade daquele momento (molde regulado
  diferente, ciclo não cadastrado etc.).
- RegistroHorario.contador_parada / contador_retomada: leitura do
  contador de peças da máquina no início e na retomada da parada,
  para conferência - não entra no cálculo de OEE.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0009_regulador_ciclo_contador"
down_revision = "0008_ordem_producao_produto_id"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _column_exists(inspector, "turnos", "regulador_nome"):
        op.add_column(
            "turnos",
            sa.Column("regulador_nome", sa.String(length=120), nullable=True),
        )

    if not _column_exists(inspector, "registros_horarios", "ciclo_informado"):
        op.add_column(
            "registros_horarios",
            sa.Column("ciclo_informado", sa.Float(), nullable=True),
        )

    if not _column_exists(inspector, "registros_horarios", "contador_parada"):
        op.add_column(
            "registros_horarios",
            sa.Column("contador_parada", sa.Integer(), nullable=True),
        )

    if not _column_exists(inspector, "registros_horarios", "contador_retomada"):
        op.add_column(
            "registros_horarios",
            sa.Column("contador_retomada", sa.Integer(), nullable=True),
        )

    # Cavidades/ciclo_padrao da Máquina deixam de ser obrigatórios: a
    # fonte de verdade passa a ser a Peça (agora obrigatória lá). Os
    # valores já cadastrados são preservados, só a restrição NOT NULL é
    # removida.
    op.alter_column("maquinas", "cavidades", existing_type=sa.Integer(), nullable=True)
    op.alter_column("maquinas", "ciclo_padrao", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _column_exists(inspector, "turnos", "regulador_nome"):
        op.drop_column("turnos", "regulador_nome")
    if _column_exists(inspector, "registros_horarios", "ciclo_informado"):
        op.drop_column("registros_horarios", "ciclo_informado")
    if _column_exists(inspector, "registros_horarios", "contador_parada"):
        op.drop_column("registros_horarios", "contador_parada")
    if _column_exists(inspector, "registros_horarios", "contador_retomada"):
        op.drop_column("registros_horarios", "contador_retomada")
