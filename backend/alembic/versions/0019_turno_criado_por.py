"""Adiciona criado_por_id ao Turno - autor do turno/rascunho, usado
para restringir quem pode continuar editando ou fechando um rascunho
(o próprio autor, SUPERVISOR ou ADMIN). Nulo nos turnos já existentes:
rascunhos antigos continuam liberados para qualquer usuário logado.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0019_turno_criado_por"
down_revision = "0018_peso_descarte"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _column_exists(inspector, "turnos", "criado_por_id"):
        # batch_alter_table: SQLite (usado nos testes) não suporta
        # ADD CONSTRAINT direto; no Postgres vira ALTER TABLE normal.
        with op.batch_alter_table("turnos") as batch_op:
            batch_op.add_column(sa.Column("criado_por_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_turnos_criado_por_id_usuarios",
                "usuarios",
                ["criado_por_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _column_exists(inspector, "turnos", "criado_por_id"):
        with op.batch_alter_table("turnos") as batch_op:
            batch_op.drop_constraint("fk_turnos_criado_por_id_usuarios", type_="foreignkey")
            batch_op.drop_column("criado_por_id")
