from datetime import datetime, time

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Parada(Base):
    __tablename__ = "paradas"

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
    inicio: Mapped[time] = mapped_column(nullable=False)
    fim: Mapped[time | None] = mapped_column(nullable=True)
    duracao_minutos: Mapped[float | None] = mapped_column(nullable=True)
    motivo: Mapped[str] = mapped_column(String(100), nullable=False)
    categoria: Mapped[str | None] = mapped_column(String(50), nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    turno = relationship("Turno", back_populates="paradas")
    maquina = relationship("Maquina", back_populates="paradas")
    usuario = relationship("Usuario", back_populates="paradas")
