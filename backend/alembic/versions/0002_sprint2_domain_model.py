"""SIAMP Sprint 2 domain model.

Adds products and structured machine stops, plus production-quality fields.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0002_sprint2_domain_model"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name):
    return table_name in inspector.get_table_names()


def _column_exists(inspector, table_name, column_name):
    return any(c["name"] == column_name for c in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _table_exists(inspector, "produtos"):
        op.create_table(
            "produtos",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("codigo", sa.String(length=50), nullable=False),
            sa.Column("descricao", sa.String(length=200), nullable=False),
            sa.Column("ciclo_padrao", sa.Float(), nullable=True),
            sa.Column("cavidades", sa.Integer(), nullable=True),
            sa.Column("peso_gramas", sa.Float(), nullable=True),
            sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("codigo", name="uq_produtos_codigo"),
        )
        op.create_index("ix_produtos_id", "produtos", ["id"])
        op.create_index("ix_produtos_codigo", "produtos", ["codigo"])

    inspector = inspect(bind)

    if not _table_exists(inspector, "usuarios"):
        op.create_table(
            "usuarios",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("nome", sa.String(length=120), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("senha_hash", sa.String(length=255), nullable=False),
            sa.Column("perfil", sa.String(length=30), nullable=False, server_default="OPERADOR"),
            sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("email", name="uq_usuarios_email"),
        )
        op.create_index("ix_usuarios_id", "usuarios", ["id"])
        op.create_index("ix_usuarios_email", "usuarios", ["email"])

    inspector = inspect(bind)

    if not _table_exists(inspector, "paradas"):
        op.create_table(
            "paradas",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("turno_id", sa.Integer(), nullable=False),
            sa.Column("maquina_id", sa.Integer(), nullable=False),
            sa.Column("inicio", sa.Time(), nullable=False),
            sa.Column("fim", sa.Time(), nullable=True),
            sa.Column("duracao_minutos", sa.Float(), nullable=True),
            sa.Column("motivo", sa.String(length=100), nullable=False),
            sa.Column("categoria", sa.String(length=50), nullable=True),
            sa.Column("observacao", sa.Text(), nullable=True),
            sa.Column("usuario_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["turno_id"], ["turnos.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["maquina_id"], ["maquinas.id"]),
            sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        )
        op.create_index("ix_paradas_id", "paradas", ["id"])
        op.create_index("ix_paradas_turno_id", "paradas", ["turno_id"])
        op.create_index("ix_paradas_maquina_id", "paradas", ["maquina_id"])

    inspector = inspect(bind)

    # Campos novos são inicialmente nullable para não quebrar dados existentes.
    if _table_exists(inspector, "registros_horarios"):
        if not _column_exists(inspector, "registros_horarios", "produto_id"):
            op.add_column(
                "registros_horarios",
                sa.Column("produto_id", sa.Integer(), nullable=True),
            )
            op.create_index(
                "ix_registros_horarios_produto_id",
                "registros_horarios",
                ["produto_id"],
            )
            op.create_foreign_key(
                "fk_registros_horarios_produto",
                "registros_horarios",
                "produtos",
                ["produto_id"],
                ["id"],
            )

        for name, column_type in [
            ("pecas_boas", sa.Integer()),
            ("refugo", sa.Integer()),
            ("meta_producao", sa.Integer()),
        ]:
            if not _column_exists(inspector, "registros_horarios", name):
                op.add_column(
                    "registros_horarios",
                    sa.Column(name, column_type, nullable=True),
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "registros_horarios"):
        if _column_exists(inspector, "registros_horarios", "produto_id"):
            try:
                op.drop_constraint(
                    "fk_registros_horarios_produto",
                    "registros_horarios",
                    type_="foreignkey",
                )
            except Exception:
                pass
            try:
                op.drop_index(
                    "ix_registros_horarios_produto_id",
                    table_name="registros_horarios",
                )
            except Exception:
                pass
            op.drop_column("registros_horarios", "produto_id")

        for name in ["pecas_boas", "refugo", "meta_producao"]:
            if _column_exists(inspector, "registros_horarios", name):
                op.drop_column("registros_horarios", name)

    inspector = inspect(bind)

    if _table_exists(inspector, "paradas"):
        op.drop_table("paradas")

    if _table_exists(inspector, "usuarios"):
        op.drop_table("usuarios")

    if _table_exists(inspector, "produtos"):
        op.drop_table("produtos")
