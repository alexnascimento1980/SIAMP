"""Aumenta lancamentos_turno.motivo de VARCHAR(150) para
VARCHAR(2000) - o campo passa a ser o único usado para descrever
Parada Programada e Falha na Injetora (motivo do usuário), precisando
comportar bem mais texto do que uma frase curta.
"""

from alembic import op
import sqlalchemy as sa

revision = "0017_lancamento_motivo_2000"
down_revision = "0016_usuario_protegido"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "lancamentos_turno",
        "motivo",
        existing_type=sa.String(150),
        type_=sa.String(2000),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Truncamento defensivo antes de estreitar a coluna de volta -
    # sem isso, qualquer motivo já salvo com mais de 150 caracteres
    # faria o downgrade falhar (Postgres) ou truncar silenciosamente
    # sem aviso (SQLite). substr() é portável entre os dois bancos
    # (LEFT() não existe no SQLite, usado nos testes).
    op.execute(
        "UPDATE lancamentos_turno SET motivo = substr(motivo, 1, 150) "
        "WHERE length(motivo) > 150"
    )
    op.alter_column(
        "lancamentos_turno",
        "motivo",
        existing_type=sa.String(2000),
        type_=sa.String(150),
        existing_nullable=True,
    )
