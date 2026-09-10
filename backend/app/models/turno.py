from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.timezone import agora_brasilia

# Valores possíveis de Turno.status_assinatura. Ficam aqui (perto do
# campo que descrevem), não em turno_service.py como antes - várias
# partes do projeto que não têm nada a ver com o modelo HORARIO
# especificamente (dashboard_service.py, ordem_producao_service.py,
# lancamento_service.py) precisavam desses valores e importavam de
# turno_service.py só por isso, criando uma dependência desnecessária
# (inclusive contribuindo para um ciclo de import real entre
# turno_service.py e lancamento_service.py - ver histórico de commits
# sobre a extração dos validadores compartilhados em
# apontamento_validacoes.py, parte da mesma limpeza).
STATUS_ASSINADO = "ASSINADO_DIGITALMENTE"
# Turno salvo como rascunho, ainda sendo preenchido - permite salvar o
# progresso ao longo do turno sem disparar PDF/e-mail a cada gravação;
# só a transição para STATUS_ASSINADO dispara o envio.
STATUS_EM_ANDAMENTO = "EM_ANDAMENTO"


class Turno(Base):
    __tablename__ = "turnos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nome_turno: Mapped[str] = mapped_column(String(50), nullable=False)
    data_registro: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=agora_brasilia,
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
    # HORARIO = grade fixa por hora (modelo original). LANCAMENTO =
    # lançamentos livres por peça/parada, com início/fim variável
    # (modelo novo). Turnos já existentes ficam para sempre em
    # HORARIO - não há conversão automática entre os dois modelos.
    # A leitura (KPIs, PDF, CSV) verifica este campo para saber qual
    # tabela de apontamento usar (RegistroHorario ou Lancamento).
    modelo_apontamento: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="HORARIO",
    )
    # Trilha de auditoria de correções: um turno já fechado pode ser
    # editado por SUPERVISOR/ADMIN (ex.: corrigir erro de digitação),
    # e aqui fica registrado quem foi e quando.
    editado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    editado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Marca reversível para turnos criados só para teste (ex.: durante
    # a implantação do sistema, treinamento de operadores). Continua
    # aparecendo no Histórico, mas é excluído do dashboard, dos
    # indicadores acumulados e da exportação em CSV - não interfere
    # nos números de produção real. Diferente de excluir de verdade
    # (não implementado para Turno, ao contrário de Usuario/Produto):
    # a marcação é reversível a qualquer momento, sem perder o
    # registro.
    marcado_teste: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )

    registros = relationship(
        "RegistroHorario",
        back_populates="turno",
        cascade="all, delete-orphan",
    )
    lancamentos = relationship(
        "Lancamento",
        back_populates="turno",
        cascade="all, delete-orphan",
    )
    paradas = relationship(
        "Parada",
        back_populates="turno",
        cascade="all, delete-orphan",
    )
    editado_por = relationship("Usuario", foreign_keys=[editado_por_id])