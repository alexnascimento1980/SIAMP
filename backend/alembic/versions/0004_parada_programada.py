"""Adiciona parada programada aos registros horários.

Paradas marcadas como programadas (troca de molde, manutenção
preventiva, refeição etc.) não devem penalizar o cálculo do OEE - ver
app/services/analytics.py.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0004_parada_programada"
down_revision = "0003_edicao_turno"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _column_exists(inspector, "registros_horarios", "parada_programada"):
        op.add_column(
            "registros_horarios",
            sa.Column(
                "parada_programada",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _column_exists(inspector, "registros_horarios", "parada_programada"):
        op.drop_column("registros_horarios", "parada_programada")
