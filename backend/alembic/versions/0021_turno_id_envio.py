"""Adiciona id_envio (UUID, único) ao Turno - identificador do envio de
fechamento, gerado pelo app. Permite reenviar um fechamento (fila
offline do celular, resposta perdida) sem criar turno duplicado. Nulo
nos turnos já existentes; vários NULL são permitidos pelo índice único.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0021_turno_id_envio"
down_revision = "0020_usuario_token_version"
branch_labels = None
depends_on = None

INDICE = "ix_turnos_id_envio"


def _column_exists(inspector, table_name, column_name):
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def _index_exists(inspector, table_name, index_name):
    return index_name in {i["name"] for i in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _column_exists(inspector, "turnos", "id_envio"):
        with op.batch_alter_table("turnos") as batch_op:
            batch_op.add_column(sa.Column("id_envio", sa.String(length=36), nullable=True))

    inspector = inspect(bind)
    if not _index_exists(inspector, "turnos", INDICE):
        with op.batch_alter_table("turnos") as batch_op:
            batch_op.create_index(INDICE, ["id_envio"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _index_exists(inspector, "turnos", INDICE):
        with op.batch_alter_table("turnos") as batch_op:
            batch_op.drop_index(INDICE)

    inspector = inspect(bind)
    if _column_exists(inspector, "turnos", "id_envio"):
        with op.batch_alter_table("turnos") as batch_op:
            batch_op.drop_column("id_envio")
