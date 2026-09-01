"""Adiciona marcado_teste ao Turno - marcação reversível para turnos
criados só para teste (ex.: durante implantação do sistema), que
devem ser excluídos do dashboard e dos relatórios agregados sem
perder o registro (diferente de excluir de verdade).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0014_turno_marcado_teste"
down_revision = "0013_usuario_fk_set_null"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _column_exists(inspector, "turnos", "marcado_teste"):
        op.add_column(
            "turnos",
            sa.Column(
                "marcado_teste",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        # server_default só é necessário para preencher as linhas já
        # existentes na migration - remove depois, para não divergir
        # do modelo (que não declara server_default, só default
        # aplicado em Python)
        op.alter_column("turnos", "marcado_teste", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _column_exists(inspector, "turnos", "marcado_teste"):
        op.drop_column("turnos", "marcado_teste")
