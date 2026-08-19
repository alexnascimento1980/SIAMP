"""Cria a tabela de destinatários do relatório de e-mail.

Antes, a lista de e-mails que recebem o relatório de fechamento de
turno era fixa na variável de ambiente REPORT_RECIPIENTS. Agora pode
ser cadastrada pela tela Destinatários (ADMIN), sem precisar editar o
.env e reiniciar o container.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0005_destinatarios_relatorio"
down_revision = "0004_parada_programada"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name):
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _table_exists(inspector, "destinatarios_relatorio"):
        op.create_table(
            "destinatarios_relatorio",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("nome", sa.String(length=150), nullable=True),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.UniqueConstraint("email", name="uq_destinatarios_relatorio_email"),
        )
        op.create_index(
            "ix_destinatarios_relatorio_email",
            "destinatarios_relatorio",
            ["email"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "destinatarios_relatorio"):
        op.drop_table("destinatarios_relatorio")
