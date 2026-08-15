from datetime import time

from sqlalchemy import ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RegistroHorario(Base):
    __tablename__ = "registros_horarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    turno_id: Mapped[int] = mapped_column(
        ForeignKey("turnos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    maquina_id: Mapped[int] = mapped_column(
        ForeignKey("maquinas.id"),
        nullable=False,
        index=True,
    )
    produto_id: Mapped[int | None] = mapped_column(
        ForeignKey("produtos.id"),
        nullable=True,
        index=True,
    )
    hora_referencia: Mapped[time] = mapped_column(Time, nullable=False)
    prod_executada: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pecas_boas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    refugo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta_producao: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inicio_parada: Mapped[time | None] = mapped_column(Time, nullable=True)
    retomada: Mapped[time | None] = mapped_column(Time, nullable=True)
    motivo_parada: Mapped[str | None] = mapped_column(String(150), nullable=True)

    turno = relationship("Turno", back_populates="registros")
    maquina = relationship("Maquina", back_populates="registros")
    produto = relationship("Produto", back_populates="registros")
