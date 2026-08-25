from datetime import time
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

TIPOS_LANCAMENTO = {"PRODUCAO", "PARADA_PROGRAMADA", "PARADA_FALHA"}


class LancamentoCreate(BaseModel):
    numero_maquina: str = Field(..., min_length=1, max_length=30)
    tipo: str = Field(..., description="PRODUCAO, PARADA_PROGRAMADA ou PARADA_FALHA")
    horario_inicio: time
    horario_fim: time

    produto_id: Optional[int] = Field(default=None, gt=0)
    ordem_producao_id: Optional[int] = Field(default=None, gt=0)
    quantidade: Optional[int] = Field(default=None, ge=0)
    ciclo_informado: Optional[float] = Field(default=None, gt=0)
    motivo: Optional[str] = Field(default=None, max_length=150)

    @model_validator(mode="after")
    def _validar(self):
        if self.tipo not in TIPOS_LANCAMENTO:
            raise ValueError(
                f"tipo deve ser um de: {', '.join(sorted(TIPOS_LANCAMENTO))}."
            )
        if self.horario_fim == self.horario_inicio:
            raise ValueError("horario_fim não pode ser igual a horario_inicio.")
        # horario_fim <= horario_inicio é interpretado como o lançamento
        # atravessando a meia-noite (ex.: 3º turno, 22:00 até 05:00 do
        # dia seguinte) - não é rejeitado, o cálculo de duração (ver
        # app/services/analytics.py) soma 24h ao horário final nesse
        # caso. Isso evita ter que quebrar todo lançamento do 3º turno
        # em duas partes manualmente.
        if self.tipo == "PRODUCAO" and self.quantidade is None:
            raise ValueError("quantidade é obrigatória para lançamento de produção.")
        return self


class LancamentoDetail(BaseModel):
    id: int
    numero_maquina: str
    tipo: str
    horario_inicio: str
    horario_fim: str
    produto_id: Optional[int] = None
    produto_codigo: Optional[str] = None
    produto_descricao: Optional[str] = None
    ordem_producao_id: Optional[int] = None
    numero_op: Optional[str] = None
    quantidade: Optional[int] = None
    ciclo_informado: Optional[float] = None
    ciclo_padrao_peca: Optional[float] = None
    motivo: Optional[str] = None
    producao_esperada: Optional[int] = None


class TurnoLancamentoCreate(BaseModel):
    nome_turno: str = Field(..., min_length=2, max_length=50)
    responsavel_nome: str = Field(..., min_length=2, max_length=120)
    regulador_nome: Optional[str] = Field(default=None, max_length=120)
    observacoes: Optional[str] = Field(default=None, max_length=2000)
    lancamentos: List[LancamentoCreate] = Field(..., min_length=1)


class TurnoLancamentoRascunho(BaseModel):
    """Mesma forma do fechamento, mas sem exigir pelo menos um
    lançamento - um rascunho pode ser salvo assim que o turno é
    aberto, antes de qualquer lançamento."""

    nome_turno: str = Field(..., min_length=2, max_length=50)
    responsavel_nome: str = Field(..., min_length=2, max_length=120)
    regulador_nome: Optional[str] = Field(default=None, max_length=120)
    observacoes: Optional[str] = Field(default=None, max_length=2000)
    lancamentos: List[LancamentoCreate] = Field(default_factory=list)
