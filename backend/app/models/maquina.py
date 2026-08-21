from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Maquina(Base):
    __tablename__ = "maquinas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    numero_maquina: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    descricao: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cavidades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ciclo_padrao: Mapped[float | None] = mapped_column(Float, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    registros = relationship("RegistroHorario", back_populates="maquina")
    paradas = relationship("Parada", back_populates="maquina")
