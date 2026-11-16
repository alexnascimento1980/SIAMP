"""Adiciona rastreabilidade de edição em turnos.

Permite corrigir um turno já fechado (ex.: erro de digitação em produção
ou horário), registrando quem editou e quando.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003_edicao_turno"
down_revision = "0002_sprint2_domain_model"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def _nome_da_fk(inspector, table_name, column_name):
    for fk in inspector.get_foreign_keys(table_name):
        if fk.get("constrained_columns") == [column_name]:
            return fk.get("name")
    return None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _column_exists(inspector, "turnos", "editado_por_id"):
        op.add_column(
            "turnos",
            sa.Column("editado_por_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_turnos_editado_por_id_usuarios",
            "turnos",
            "usuarios",
            ["editado_por_id"],
            ["id"],
        )

    inspector = inspect(bind)
    if not _column_exists(inspector, "turnos", "editado_em"):
        op.add_column(
            "turnos",
            sa.Column("editado_em", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _column_exists(inspector, "turnos", "editado_em"):
        op.drop_column("turnos", "editado_em")

    inspector = inspect(bind)
    if _column_exists(inspector, "turnos", "editado_por_id"):
        # O nome da FK é buscado no banco, não fixado aqui: a migration
        # 0013 recria essa FK (ON DELETE SET NULL) com outro nome
        # ("turnos_editado_por_id_fkey"), e procurar pelo nome original
        # fazia o downgrade falhar em bancos que passaram pela 0013.
        nome_fk = _nome_da_fk(inspector, "turnos", "editado_por_id")
        if nome_fk:
            op.drop_constraint(nome_fk, "turnos", type_="foreignkey")
        op.drop_column("turnos", "editado_por_id")
