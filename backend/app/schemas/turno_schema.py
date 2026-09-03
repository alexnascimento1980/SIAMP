from datetime import datetime, time

from pydantic import BaseModel, Field, field_validator

from app.schemas.lancamento_schema import LancamentoDetail


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
    produto_id: int | None = Field(default=None, gt=0)
    # Ordem de Produção atendida nessa hora/máquina (opcional). Permite
    # somar a produção real por OP mesmo quando ela é feita em mais de
    # uma injetora ao mesmo tempo, e mostrar qual OP foi atendida no
    # relatório de turno.
    ordem_producao_id: int | None = Field(default=None, gt=0)
    # Apontamento de qualidade (opcional). Quando informados, entram no
    # cálculo do Índice de Qualidade do OEE (ver app/services/analytics.py).
    pecas_boas: int | None = Field(default=None, ge=0)
    refugo: int | None = Field(default=None, ge=0)
    meta_producao: int | None = Field(default=None, ge=0)
    # Ciclo (segundos) informado manualmente pelo operador para esta
    # hora/máquina - prevalece sobre o ciclo da peça/máquina no cálculo
    # de capacidade esperada. Útil quando o ciclo padrão não reflete a
    # regulagem real do molde, ou quando ainda não há ciclo cadastrado.
    ciclo_informado: float | None = Field(default=None, gt=0)
    inicio_parada: time | None = None
    retomada: time | None = None
    motivo_parada: str | None = Field(default=None, max_length=150)
    # Leitura do contador de peças da máquina no início/retomada da
    # parada, para conferência - não entra no cálculo de OEE.
    contador_parada: int | None = Field(default=None, ge=0)
    contador_retomada: int | None = Field(default=None, ge=0)
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
    def validar_retomada(cls, value: time | None, info):
        inicio = info.data.get("inicio_parada")
        if value is not None and inicio is not None and value < inicio:
            raise ValueError("retomada não pode ser anterior ao início da parada.")
        return value

    @field_validator("refugo")
    @classmethod
    def validar_soma_qualidade(cls, value: int | None, info):
        pecas_boas = info.data.get("pecas_boas")
        prod_executada = info.data.get("prod_executada")
        if (
            value is not None
            and pecas_boas is not None
            and prod_executada is not None
            and (value + pecas_boas) > prod_executada
        ):
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
    regulador_nome: str | None = Field(default=None, max_length=120)
    observacoes: str | None = Field(default=None, max_length=2000)
    registros: list[RegistroHorarioCreate] = Field(..., min_length=1)


class RascunhoTurnoCreate(BaseModel):
    """Mesma forma do fechamento, mas sem exigir pelo menos um
    registro - um rascunho pode ser salvo assim que o turno é aberto,
    antes de qualquer apontamento."""

    nome_turno: str = Field(..., min_length=2, max_length=50)
    responsavel_nome: str = Field(..., min_length=2, max_length=120)
    regulador_nome: str | None = Field(default=None, max_length=120)
    observacoes: str | None = Field(default=None, max_length=2000)
    registros: list[RegistroHorarioCreate] = Field(default_factory=list)


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
    modelo_apontamento: str = "HORARIO"
    total_produzido: int
    eficiencia_oee: float
    indice_qualidade: float
    editado: bool = False
    marcado_teste: bool = False


class RegistroHorarioDetail(BaseModel):
    numero_maquina: str
    hora_referencia: str
    prod_executada: int
    pecas_boas: int | None = None
    refugo: int | None = None
    produto_id: int | None = None
    produto_codigo: str | None = None
    produto_descricao: str | None = None
    ordem_producao_id: int | None = None
    numero_op: str | None = None
    ciclo_informado: float | None = None
    inicio_parada: time | None = None
    retomada: time | None = None
    motivo_parada: str | None = None
    parada_programada: bool = False
    contador_parada: int | None = None
    contador_retomada: int | None = None


class TurnoDetail(BaseModel):
    id: int
    nome_turno: str
    responsavel_nome: str
    regulador_nome: str | None = None
    observacoes: str | None = None
    data_registro: datetime
    status_assinatura: str
    modelo_apontamento: str = "HORARIO"
    editado_por_nome: str | None = None
    editado_em: datetime | None = None
    marcado_teste: bool = False
    registros: list[RegistroHorarioDetail] = []
    lancamentos: list[LancamentoDetail] = []


class TurnosMarcarTeste(BaseModel):
    turno_ids: list[int] = Field(..., min_length=1)
    marcado_teste: bool