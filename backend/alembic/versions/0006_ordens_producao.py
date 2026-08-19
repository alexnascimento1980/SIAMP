"""Cria a tabela de ordens de produção.

Guarda os dados da Ordem de Produção emitida pelo ERP (cadastrada
manualmente a partir do documento impresso), para comparar a meta
planejada com a produção real apontada nos turnos.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0006_ordens_producao"
down_revision = "0005_destinatarios_relatorio"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name):
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _table_exists(inspector, "ordens_producao"):
        op.create_table(
            "ordens_producao",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("numero_op", sa.String(length=30), nullable=False),
            sa.Column("data_emissao", sa.Date(), nullable=True),
            sa.Column("tipo_op", sa.String(length=50), nullable=True),
            sa.Column("setor_produtivo", sa.String(length=50), nullable=True),
            sa.Column("lote", sa.String(length=50), nullable=True),
            sa.Column("periodo_inicio", sa.Date(), nullable=False),
            sa.Column("periodo_fim", sa.Date(), nullable=False),
            sa.Column("produto_codigo", sa.String(length=50), nullable=True),
            sa.Column("produto_descricao", sa.String(length=200), nullable=True),
            sa.Column("quantidade_a_produzir", sa.Integer(), nullable=False),
            sa.Column("maquina_id", sa.Integer(), sa.ForeignKey("maquinas.id"), nullable=True),
            sa.Column("equipamento_codigo", sa.String(length=30), nullable=True),
            sa.Column("equipamento_descricao", sa.String(length=150), nullable=True),
            sa.Column("ferramenta_codigo", sa.String(length=50), nullable=True),
            sa.Column("ferramenta_descricao", sa.String(length=150), nullable=True),
            sa.Column("formula_codigo", sa.String(length=50), nullable=True),
            sa.Column("formula_descricao", sa.String(length=150), nullable=True),
            sa.Column("embalagem_codigo", sa.String(length=50), nullable=True),
            sa.Column("embalagem_descricao", sa.String(length=150), nullable=True),
            sa.Column("qtde_por_embalagem", sa.Integer(), nullable=True),
            sa.Column("qtde_embalagens_previstas", sa.Integer(), nullable=True),
            sa.Column("cavidades", sa.Integer(), nullable=True),
            sa.Column("ciclo_segundos", sa.Float(), nullable=True),
            sa.Column("qtde_produzida_por_hora_meta", sa.Integer(), nullable=True),
            sa.Column("peso_liquido_unitario", sa.Float(), nullable=True),
            sa.Column("peso_bruto_unitario", sa.Float(), nullable=True),
            sa.Column("composicao_mistura", sa.Text(), nullable=True),
            sa.Column("observacoes", sa.Text(), nullable=True),
            sa.Column("criado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
            sa.Column(
                "criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()
            ),
            sa.UniqueConstraint("numero_op", name="uq_ordens_producao_numero_op"),
        )
        op.create_index(
            "ix_ordens_producao_numero_op", "ordens_producao", ["numero_op"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "ordens_producao"):
        op.drop_table("ordens_producao")
