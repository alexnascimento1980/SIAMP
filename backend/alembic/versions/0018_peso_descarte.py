"""Adiciona lancamentos_turno.peso_bruto_descarte (peso do lote de
peças descartadas pesado naquele lançamento específico, em GRAMAS) -
junto do campo peso_gramas já existente em Produto (peso de UMA peça,
também em gramas - já usado no cadastro, reaproveitado aqui em vez de
criar um segundo campo de peso duplicado), permite calcular a
quantidade de refugo sem depender de contagem manual peça por peça:

    refugo = peso_bruto_descarte / peso_gramas

Os dois lados em gramas, sem conversão de unidade entre eles - peças
injetadas pequenas podem pesar frações de grama (confirmado pelo
usuário em produção), tornando plausível um lote de poucos gramas
mesmo com dezenas de peças descartadas.

Opcional - o descarte só é registrado "quando existir" (pedido do
usuário), sem quebrar lançamentos que nunca tiveram descarte algum.
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_peso_descarte"
down_revision = "0017_lancamento_motivo_2000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lancamentos_turno",
        sa.Column("peso_bruto_descarte", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lancamentos_turno", "peso_bruto_descarte")
