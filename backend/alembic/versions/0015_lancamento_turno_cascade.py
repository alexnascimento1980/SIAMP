"""Altera lancamentos_turno.turno_id para ON DELETE CASCADE - sem
isso, excluir um turno do modelo de lançamento livre (o modelo
atual) falharia com violação de chave estrangeira (RESTRICT, padrão
do Postgres), já que cada lançamento aponta para o turno ao qual
pertence. registros_horarios.turno_id e paradas.turno_id já tinham
CASCADE desde a criação; esta era a única tabela de "filhos de
turno" sem esse comportamento - inconsistência não notada até a
exclusão definitiva de turno ser implementada.
"""

from alembic import op
from sqlalchemy import inspect

revision = "0015_lancamento_turno_cascade"
down_revision = "0014_turno_marcado_teste"
branch_labels = None
depends_on = None

_TABELA = "lancamentos_turno"
_COLUNA = "turno_id"


def _fk_ja_e_cascade(inspector) -> bool:
    for fk in inspector.get_foreign_keys(_TABELA):
        if fk.get("constrained_columns") == [_COLUNA]:
            return fk.get("options", {}).get("ondelete") == "CASCADE"
    return False


def _nome_da_fk(inspector) -> str | None:
    for fk in inspector.get_foreign_keys(_TABELA):
        if fk.get("constrained_columns") == [_COLUNA]:
            return fk.get("name")
    return None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _fk_ja_e_cascade(inspector):
        return

    nome_atual = _nome_da_fk(inspector)
    if nome_atual:
        op.drop_constraint(nome_atual, _TABELA, type_="foreignkey")

    op.create_foreign_key(
        f"{_TABELA}_{_COLUNA}_fkey",
        _TABELA,
        "turnos",
        [_COLUNA],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    nome_atual = _nome_da_fk(inspector)
    if nome_atual:
        op.drop_constraint(nome_atual, _TABELA, type_="foreignkey")
    op.create_foreign_key(f"{_TABELA}_{_COLUNA}_fkey", _TABELA, "turnos", [_COLUNA], ["id"])
