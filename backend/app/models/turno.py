from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
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
    # Regulador do turno (papel de quem regula/ajusta o molde nas
    # injetoras), além do líder. Opcional para não quebrar turnos
    # antigos, que não tinham esse campo.
    regulador_nome: Mapped[str | None] = mapped_column(String(120), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_assinatura: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PENDENTE",
        index=True,
    )
    # Trilha de auditoria de correções: um turno já fechado pode ser
    # editado por SUPERVISOR/ADMIN (ex.: corrigir erro de digitação),
    # e aqui fica registrado quem foi e quando.
    editado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=True,
    )
    editado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

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
    editado_por = relationship("Usuario", foreign_keys=[editado_por_id])