from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.timezone import agora_brasilia


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    perfil: Mapped[str] = mapped_column(String(30), nullable=False, default="OPERADOR")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Marca uma conta como protegida contra exclusão e desativação
    # acidental por outro ADMIN - a auto-proteção existente (um ADMIN
    # não pode excluir/desativar a PRÓPRIA conta) não cobre o caso de
    # um ADMIN excluir a conta de OUTRO ADMIN por engano, que foi
    # exatamente o incidente que motivou este campo. Reversível (um
    # ADMIN pode desproteger deliberadamente antes de excluir de
    # verdade, se um dia for realmente necessário) - a proteção não
    # impede a ação em si, só exige uma etapa deliberada extra antes,
    # convertendo um clique acidental numa ação de duas etapas.
    protegido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=agora_brasilia,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=agora_brasilia,
        onupdate=agora_brasilia,
    )

    paradas = relationship("Parada", back_populates="usuario")
