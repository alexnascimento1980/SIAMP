"""Altera as chaves estrangeiras que apontam para usuarios.id
(turnos.editado_por_id, ordens_producao.criado_por_id,
paradas.usuario_id) para ON DELETE SET NULL. Sem isso, o Postgres
bloqueia por padrão (RESTRICT) a exclusão de qualquer usuário que já
tenha editado um turno, criado uma Ordem de Produção ou registrado
uma parada - exatamente os usuários mais prováveis de precisar
excluir de verdade (colaboradores desligados, que geralmente têm
histórico). Com SET NULL, o turno/OP continua existindo
normalmente, só perde a referência de quem foi.
"""

from alembic import op
from sqlalchemy import inspect

revision = "0013_usuario_fk_set_null"
down_revision = "0012_cavidades_informado"
branch_labels = None
depends_on = None

# (tabela, coluna) de cada FK que precisa ser alterada
_FKS_PARA_AJUSTAR = [
    ("turnos", "editado_por_id"),
    ("ordens_producao", "criado_por_id"),
    ("paradas", "usuario_id"),
]


def _fk_ja_e_set_null(inspector, tabela, coluna) -> bool:
    for fk in inspector.get_foreign_keys(tabela):
        if fk.get("constrained_columns") == [coluna]:
            return fk.get("options", {}).get("ondelete") == "SET NULL"
    return False


def _nome_da_fk(inspector, tabela, coluna) -> str | None:
    for fk in inspector.get_foreign_keys(tabela):
        if fk.get("constrained_columns") == [coluna]:
            return fk.get("name")
    return None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    for tabela, coluna in _FKS_PARA_AJUSTAR:
        if _fk_ja_e_set_null(inspector, tabela, coluna):
            continue

        nome_atual = _nome_da_fk(inspector, tabela, coluna)
        if nome_atual:
            op.drop_constraint(nome_atual, tabela, type_="foreignkey")

        op.create_foreign_key(
            f"{tabela}_{coluna}_fkey",
            tabela,
            "usuarios",
            [coluna],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    for tabela, coluna in _FKS_PARA_AJUSTAR:
        nome_atual = _nome_da_fk(inspector, tabela, coluna)
        if nome_atual:
            op.drop_constraint(nome_atual, tabela, type_="foreignkey")
        op.create_foreign_key(
            f"{tabela}_{coluna}_fkey", tabela, "usuarios", [coluna], ["id"]
        )
