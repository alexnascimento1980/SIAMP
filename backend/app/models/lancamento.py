from datetime import time

from sqlalchemy import Float, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Tipos de lançamento. PRODUCAO usa produto_id/ordem_producao_id/
# quantidade; os dois tipos de parada usam apenas o intervalo de tempo
# (e opcionalmente 'motivo' como detalhe livre). PARADA_PROGRAMADA não
# penaliza o cálculo de OEE (mesma lógica do campo parada_programada
# do modelo antigo); PARADA_FALHA penaliza (equivalente à parada não
# programada de hoje).
TIPO_PRODUCAO = "PRODUCAO"
TIPO_PARADA_PROGRAMADA = "PARADA_PROGRAMADA"
TIPO_PARADA_FALHA = "PARADA_FALHA"
TIPOS_VALIDOS = {TIPO_PRODUCAO, TIPO_PARADA_PROGRAMADA, TIPO_PARADA_FALHA}


class Lancamento(Base):
    """Lançamento livre de produção ou parada, com início/fim variável
    dentro do turno - modelo novo de apontamento (ver
    Turno.modelo_apontamento), usado só por turnos criados a partir da
    introdução deste recurso. Turnos antigos continuam usando
    RegistroHorario (grade fixa por hora)."""

    __tablename__ = "lancamentos_turno"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    turno_id: Mapped[int] = mapped_column(ForeignKey("turnos.id"), nullable=False, index=True)
    maquina_id: Mapped[int] = mapped_column(ForeignKey("maquinas.id"), nullable=False, index=True)

    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    horario_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    horario_fim: Mapped[time] = mapped_column(Time, nullable=False)

    # Só para tipo=PRODUCAO
    produto_id: Mapped[int | None] = mapped_column(ForeignKey("produtos.id"), nullable=True)
    ordem_producao_id: Mapped[int | None] = mapped_column(
        ForeignKey("ordens_producao.id"), nullable=True
    )
    quantidade: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Ciclo (segundos) informado manualmente pelo operador para este
    # lançamento - tem prioridade sobre o ciclo da peça/máquina no
    # cálculo de capacidade esperada (ver
    # app/services/analytics.py:calcular_capacidade_esperada_lancamento).
    # Útil para o líder de turno comparar o ciclo real observado na
    # injetora com o ciclo médio padrão cadastrado na peça, e para
    # casos em que o ciclo real difere do cadastrado (molde regulado
    # diferente naquele momento).
    ciclo_informado: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Detalhe livre - motivo da falha (tipo=PARADA_FALHA) ou
    # observação da parada programada (tipo=PARADA_PROGRAMADA).
    motivo: Mapped[str | None] = mapped_column(String(150), nullable=True)

    turno = relationship("Turno", back_populates="lancamentos")
    maquina = relationship("Maquina")
    produto = relationship("Produto")
    ordem_producao = relationship("OrdemProducao")
