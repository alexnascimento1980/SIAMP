
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name):
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _table_exists(inspector, "maquinas"):
        op.create_table(
            "maquinas",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("numero_maquina", sa.String(length=30), nullable=False),
            sa.Column("descricao", sa.String(length=150), nullable=True),
            sa.Column("cavidades", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("ciclo_padrao", sa.Float(), nullable=False, server_default="0"),
            sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.UniqueConstraint("numero_maquina", name="uq_maquinas_numero_maquina"),
        )
        op.create_index("ix_maquinas_id", "maquinas", ["id"])
        op.create_index("ix_maquinas_numero_maquina", "maquinas", ["numero_maquina"])

    inspector = inspect(bind)

    if not _table_exists(inspector, "turnos"):
        op.create_table(
            "turnos",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("nome_turno", sa.String(length=50), nullable=False),
            sa.Column("data_registro", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("responsavel_nome", sa.String(length=120), nullable=False),
            sa.Column("observacoes", sa.Text(), nullable=True),
            sa.Column("status_assinatura", sa.String(length=30), nullable=False, server_default="PENDENTE"),
        )
        op.create_index("ix_turnos_id", "turnos", ["id"])
        op.create_index("ix_turnos_data_registro", "turnos", ["data_registro"])
        op.create_index("ix_turnos_status_assinatura", "turnos", ["status_assinatura"])

    inspector = inspect(bind)

    if not _table_exists(inspector, "registros_horarios"):
        op.create_table(
            "registros_horarios",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("turno_id", sa.Integer(), nullable=False),
            sa.Column("maquina_id", sa.Integer(), nullable=False),
            sa.Column("hora_referencia", sa.Time(), nullable=False),
            sa.Column("prod_executada", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("inicio_parada", sa.Time(), nullable=True),
            sa.Column("retomada", sa.Time(), nullable=True),
            sa.Column("motivo_parada", sa.String(length=150), nullable=True),
            sa.ForeignKeyConstraint(["turno_id"], ["turnos.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["maquina_id"], ["maquinas.id"]),
        )
        op.create_index("ix_registros_horarios_id", "registros_horarios", ["id"])
        op.create_index("ix_registros_horarios_turno_id", "registros_horarios", ["turno_id"])
        op.create_index("ix_registros_horarios_maquina_id", "registros_horarios", ["maquina_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "registros_horarios"):
        op.drop_table("registros_horarios")

    inspector = inspect(bind)
    if _table_exists(inspector, "turnos"):
        op.drop_table("turnos")

    inspector = inspect(bind)
    if _table_exists(inspector, "maquinas"):
        op.drop_table("maquinas")