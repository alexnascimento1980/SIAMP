from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.timezone import agora_brasilia


class Produto(Base):
    __tablename__ = "produtos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    codigo: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    descricao: Mapped[str] = mapped_column(String(200), nullable=False)
    ciclo_padrao: Mapped[float | None] = mapped_column(Float, nullable=True)
    cavidades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Peso de UMA peça, em GRAMAS - campo pré-existente, já usado no
    # cadastro ("Peso (g)"). Reaproveitado como o "peso líquido da
    # peça" da fórmula de refugo (peso_bruto_descarte, em kg, dividido
    # por este campo convertido para kg - ver analytics.
    # calcular_refugo_lancamento), em vez de criar um segundo campo de
    # peso duplicado na mesma peça.
    peso_gramas: Mapped[float | None] = mapped_column(Float, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=agora_brasilia,
    )

    registros = relationship("RegistroHorario", back_populates="produto")
