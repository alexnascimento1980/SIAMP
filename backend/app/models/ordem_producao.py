from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.timezone import agora_brasilia


class OrdemProducao(Base):
    """Ordem de Produção (OP) emitida pelo sistema de ERP da empresa
    (ex.: MaxManager), cadastrada manualmente no SIAMP a partir do
    documento impresso. Serve de base para comparar a meta planejada
    com a produção real apontada nos turnos (ver
    app/services/ordem_producao_service.py)."""

    __tablename__ = "ordens_producao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Cabeçalho do documento
    numero_op: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    data_emissao: Mapped[date | None] = mapped_column(Date, nullable=True)
    tipo_op: Mapped[str | None] = mapped_column(String(50), nullable=True)
    setor_produtivo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lote: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Período programado da produção - usado para comparar com o real
    # apontado nos turnos cujo data_registro cai nesse intervalo.
    periodo_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    periodo_fim: Mapped[date] = mapped_column(Date, nullable=False)

    # Produto a produzir. Antes ficava como texto livre porque o código
    # de produto do ERP (ex. "34-7506-00BR") usa um padrão diferente do
    # catálogo de peças/ciclo já cadastrado - mas o cadastro de OP agora
    # exige selecionar uma peça já cadastrada (evita erro de digitação),
    # então vinculamos por FK e guardamos código/descrição como um
    # retrato (snapshot) no momento do cadastro, preservando o histórico
    # mesmo que a peça seja editada ou desativada depois.
    produto_id: Mapped[int | None] = mapped_column(ForeignKey("produtos.id"), nullable=True)
    produto_codigo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    produto_descricao: Mapped[str | None] = mapped_column(String(200), nullable=True)
    quantidade_a_produzir: Mapped[int] = mapped_column(Integer, nullable=False)

    # Máquina: aqui SIM vinculamos por FK, já que o número do
    # "Equipamento" da OP corresponde ao numero_maquina já cadastrado.
    maquina_id: Mapped[int | None] = mapped_column(ForeignKey("maquinas.id"), nullable=True)
    equipamento_codigo: Mapped[str | None] = mapped_column(String(30), nullable=True)
    equipamento_descricao: Mapped[str | None] = mapped_column(String(150), nullable=True)

    ferramenta_codigo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ferramenta_descricao: Mapped[str | None] = mapped_column(String(150), nullable=True)
    formula_codigo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    formula_descricao: Mapped[str | None] = mapped_column(String(150), nullable=True)
    embalagem_codigo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    embalagem_descricao: Mapped[str | None] = mapped_column(String(150), nullable=True)
    qtde_por_embalagem: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qtde_embalagens_previstas: Mapped[int | None] = mapped_column(Integer, nullable=True)

    cavidades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ciclo_segundos: Mapped[float | None] = mapped_column(Float, nullable=True)
    qtde_produzida_por_hora_meta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    peso_liquido_unitario: Mapped[float | None] = mapped_column(Float, nullable=True)
    peso_bruto_unitario: Mapped[float | None] = mapped_column(Float, nullable=True)

    composicao_mistura: Mapped[str | None] = mapped_column(Text, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=agora_brasilia
    )

    maquina = relationship("Maquina")
    produto = relationship("Produto")
    criado_por = relationship("Usuario", foreign_keys=[criado_por_id])
