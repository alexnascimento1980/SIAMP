from datetime import time

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Time
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
    # Ordem de Produção atendida por este apontamento (opcional). Permite
    # somar a produção real de uma OP mesmo quando ela é feita em mais de
    # uma injetora ao mesmo tempo - ver
    # app/services/ordem_producao_service.py.
    ordem_producao_id: Mapped[int | None] = mapped_column(
        ForeignKey("ordens_producao.id"),
        nullable=True,
        index=True,
    )
    hora_referencia: Mapped[time] = mapped_column(Time, nullable=False)
    prod_executada: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pecas_boas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    refugo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta_producao: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Ciclo (segundos) informado manualmente pelo operador para esta
    # hora/máquina - tem prioridade sobre o ciclo da peça/máquina no
    # cálculo de capacidade esperada (ver
    # app/services/analytics.py:calcular_capacidade_esperada_registro).
    # Útil quando o ciclo padrão cadastrado não reflete a regulagem
    # real do molde naquele momento, ou quando não há peça/ciclo
    # cadastrado ainda.
    ciclo_informado: Mapped[float | None] = mapped_column(Float, nullable=True)
    inicio_parada: Mapped[time | None] = mapped_column(Time, nullable=True)
    retomada: Mapped[time | None] = mapped_column(Time, nullable=True)
    motivo_parada: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # Leitura do contador de peças da máquina no início e na retomada
    # da parada, só para conferência/auditoria - não entra no cálculo
    # de OEE.
    contador_parada: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contador_retomada: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Parada programada (troca de molde, manutenção preventiva, refeição
    # etc.): o tempo parado não deve contar contra a capacidade esperada
    # no cálculo do OEE (ver app/services/analytics.py). Paradas não
    # marcadas aqui são tratadas como não programadas (penalizam o OEE).
    parada_programada: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    turno = relationship("Turno", back_populates="registros")
    maquina = relationship("Maquina", back_populates="registros")
    produto = relationship("Produto", back_populates="registros")
    ordem_producao = relationship("OrdemProducao")
