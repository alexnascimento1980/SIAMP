from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Turno(Base):
    __tablename__ = "turnos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nome_turno: Mapped[str] = mapped_column(String(50), nullable=False)
    data_registro: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    responsavel_nome: Mapped[str] = mapped_column(String(120), nullable=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_assinatura: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PENDENTE",
        index=True,
    )

    registros = relationship(
        "RegistroHorario",
        back_populates="turno",
        cascade="all, delete-orphan",
    )
    paradas = relationship(
        "Parada",
        back_populates="turno",
        cascade="all, delete-orphan",
    )
