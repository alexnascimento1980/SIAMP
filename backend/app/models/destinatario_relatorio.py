from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DestinatarioRelatorio(Base):
    """E-mail que recebe o relatório de fechamento de turno (e reenvios
    sob demanda). Cadastrável pela tela Destinatários (ADMIN), em vez
    de fixo na variável de ambiente REPORT_RECIPIENTS - ver
    app/services/turno_service.py para como a lista final é montada."""

    __tablename__ = "destinatarios_relatorio"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    nome: Mapped[str | None] = mapped_column(String(150), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
