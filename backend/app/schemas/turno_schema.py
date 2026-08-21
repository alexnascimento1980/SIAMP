from datetime import time
from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class RegistroHorarioCreate(BaseModel):
    # Identifica a máquina pelo número de injetora exibido na interface
    # (ex.: "1" a "6"), não pelo id interno (primary key) da tabela
    # `maquinas`. A resolução para o id real é feita no service, via
    # busca por Maquina.numero_maquina, para não depender da ordem de
    # inserção do seed.
    numero_maquina: str = Field(..., min_length=1, max_length=30)
    hora_referencia: str = Field(..., min_length=5, max_length=5, examples=["05:00"])
    prod_executada: int = Field(default=0, ge=0)
    # Peça produzida nessa hora/máquina (opcional, para retrocompatibilidade
    # com registros antigos). Identifica pelo id do catálogo de produtos
    # (GET /produtos/), não pelo código, já que o frontend já carrega a
    # lista com os ids reais para popular o seletor.
    produto_id: Optional[int] = Field(default=None, gt=0)
    # Ordem de Produção atendida nessa hora/máquina (opcional). Permite
    # somar a produção real por OP mesmo quando ela é feita em mais de
    # uma injetora ao mesmo tempo, e mostrar qual OP foi atendida no
    # relatório de turno.
    ordem_producao_id: Optional[int] = Field(default=None, gt=0)
    # Apontamento de qualidade (opcional). Quando informados, entram no
    # cálculo do Índice de Qualidade do OEE (ver app/services/analytics.py).
    pecas_boas: Optional[int] = Field(default=None, ge=0)
    refugo: Optional[int] = Field(default=None, ge=0)
    meta_producao: Optional[int] = Field(default=None, ge=0)
    # Ciclo (segundos) informado manualmente pelo operador para esta
    # hora/máquina - prevalece sobre o ciclo da peça/máquina no cálculo
    # de capacidade esperada. Útil quando o ciclo padrão não reflete a
    # regulagem real do molde, ou quando ainda não há ciclo cadastrado.
    ciclo_informado: Optional[float] = Field(default=None, gt=0)
    inicio_parada: Optional[time] = None
    retomada: Optional[time] = None
    motivo_parada: Optional[str] = Field(default=None, max_length=150)
    # Leitura do contador de peças da máquina no início/retomada da
    # parada, para conferência - não entra no cálculo de OEE.
    contador_parada: Optional[int] = Field(default=None, ge=0)
    contador_retomada: Optional[int] = Field(default=None, ge=0)
    # Parada programada (troca de molde, manutenção preventiva, refeição
    # etc.): o tempo parado não entra na capacidade esperada do cálculo
    # de OEE (ver app/services/analytics.py). Só faz sentido quando
    # inicio_parada/retomada estão preenchidos.
    parada_programada: bool = False

    @field_validator("hora_referencia")
    @classmethod
    def validar_hora_referencia(cls, value: str) -> str:
        try:
            time.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                "hora_referencia deve estar no formato HH:MM."
            ) from exc
        return value

    @field_validator("retomada")
    @classmethod
    def validar_retomada(cls, value: Optional[time], info):
        inicio = info.data.get("inicio_parada")
        if value is not None and inicio is not None and value < inicio:
            raise ValueError("retomada não pode ser anterior ao início da parada.")
        return value

    @field_validator("refugo")
    @classmethod
    def validar_soma_qualidade(cls, value: Optional[int], info):
        pecas_boas = info.data.get("pecas_boas")
        prod_executada = info.data.get("prod_executada")
        if value is not None and pecas_boas is not None and prod_executada is not None:
            if (value + pecas_boas) > prod_executada:
                raise ValueError(
                    "A soma de peças boas e refugo não pode ser maior que a "
                    "produção executada informada."
                )
        return value

    @field_validator("parada_programada")
    @classmethod
    def validar_parada_programada(cls, value: bool, info):
        if value and info.data.get("inicio_parada") is None:
            raise ValueError(
                "Marque o início da parada antes de sinalizá-la como programada."
            )
        return value


class FechamentoTurnoCreate(BaseModel):
    nome_turno: str = Field(..., min_length=2, max_length=50)
    responsavel_nome: str = Field(..., min_length=2, max_length=120)
    regulador_nome: Optional[str] = Field(default=None, max_length=120)
    observacoes: Optional[str] = Field(default=None, max_length=2000)
    registros: List[RegistroHorarioCreate] = Field(..., min_length=1)


class ResumoProducaoResponse(BaseModel):
    turno_id: int
    total_produzido: int
    minutos_parada_total: float
    eficiencia_oee: float
    status: str


class TurnoListItem(BaseModel):
    id: int
    nome_turno: str
    responsavel_nome: str
    data_registro: datetime
    status_assinatura: str
    total_produzido: int
    eficiencia_oee: float
    indice_qualidade: float
    editado: bool = False


class RegistroHorarioDetail(BaseModel):
    numero_maquina: str
    hora_referencia: str
    prod_executada: int
    pecas_boas: Optional[int] = None
    refugo: Optional[int] = None
    produto_id: Optional[int] = None
    produto_codigo: Optional[str] = None
    produto_descricao: Optional[str] = None
    ordem_producao_id: Optional[int] = None
    numero_op: Optional[str] = None
    ciclo_informado: Optional[float] = None
    inicio_parada: Optional[time] = None
    retomada: Optional[time] = None
    motivo_parada: Optional[str] = None
    parada_programada: bool = False
    contador_parada: Optional[int] = None
    contador_retomada: Optional[int] = None


class TurnoDetail(BaseModel):
    id: int
    nome_turno: str
    responsavel_nome: str
    regulador_nome: Optional[str] = None
    observacoes: Optional[str] = None
    data_registro: datetime
    status_assinatura: str
    editado_por_nome: Optional[str] = None
    editado_em: Optional[datetime] = None
    registros: List[RegistroHorarioDetail]