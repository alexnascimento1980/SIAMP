from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class OrdemProducaoBase(BaseModel):
    numero_op: str = Field(..., min_length=1, max_length=30)
    data_emissao: date | None = None
    tipo_op: str | None = Field(default=None, max_length=50)
    setor_produtivo: str | None = Field(default=None, max_length=50)
    lote: str | None = Field(default=None, max_length=50)

    periodo_inicio: date
    periodo_fim: date

    produto_codigo: str | None = Field(default=None, max_length=50)
    produto_descricao: str | None = Field(default=None, max_length=200)
    quantidade_a_produzir: int = Field(..., gt=0)

    # Aceita o número do equipamento (ex.: "06") e resolve para
    # maquina_id no backend, igual ao numero_maquina já usado no
    # apontamento - não expõe o id interno para quem preenche o form.
    numero_maquina: str | None = Field(default=None, max_length=30)
    equipamento_descricao: str | None = Field(default=None, max_length=150)

    ferramenta_codigo: str | None = Field(default=None, max_length=50)
    ferramenta_descricao: str | None = Field(default=None, max_length=150)
    formula_codigo: str | None = Field(default=None, max_length=50)
    formula_descricao: str | None = Field(default=None, max_length=150)
    embalagem_codigo: str | None = Field(default=None, max_length=50)
    embalagem_descricao: str | None = Field(default=None, max_length=150)
    qtde_por_embalagem: int | None = Field(default=None, gt=0)
    qtde_embalagens_previstas: int | None = Field(default=None, gt=0)

    cavidades: int | None = Field(default=None, gt=0)
    ciclo_segundos: float | None = Field(default=None, gt=0)
    qtde_produzida_por_hora_meta: int | None = Field(default=None, gt=0)
    peso_liquido_unitario: float | None = Field(default=None, gt=0)
    peso_bruto_unitario: float | None = Field(default=None, gt=0)

    composicao_mistura: str | None = None
    observacoes: str | None = None

    @model_validator(mode="after")
    def _validar_periodo(self):
        if self.periodo_fim < self.periodo_inicio:
            raise ValueError("periodo_fim não pode ser anterior a periodo_inicio.")
        return self


class OrdemProducaoCreate(OrdemProducaoBase):
    pass


class OrdemProducaoUpdate(BaseModel):
    data_emissao: date | None = None
    tipo_op: str | None = Field(default=None, max_length=50)
    setor_produtivo: str | None = Field(default=None, max_length=50)
    lote: str | None = Field(default=None, max_length=50)
    periodo_inicio: date | None = None
    periodo_fim: date | None = None
    produto_codigo: str | None = Field(default=None, max_length=50)
    produto_descricao: str | None = Field(default=None, max_length=200)
    quantidade_a_produzir: int | None = Field(default=None, gt=0)
    numero_maquina: str | None = Field(default=None, max_length=30)
    equipamento_descricao: str | None = Field(default=None, max_length=150)
    ferramenta_codigo: str | None = Field(default=None, max_length=50)
    ferramenta_descricao: str | None = Field(default=None, max_length=150)
    formula_codigo: str | None = Field(default=None, max_length=50)
    formula_descricao: str | None = Field(default=None, max_length=150)
    embalagem_codigo: str | None = Field(default=None, max_length=50)
    embalagem_descricao: str | None = Field(default=None, max_length=150)
    qtde_por_embalagem: int | None = Field(default=None, gt=0)
    qtde_embalagens_previstas: int | None = Field(default=None, gt=0)
    cavidades: int | None = Field(default=None, gt=0)
    ciclo_segundos: float | None = Field(default=None, gt=0)
    qtde_produzida_por_hora_meta: int | None = Field(default=None, gt=0)
    peso_liquido_unitario: float | None = Field(default=None, gt=0)
    peso_bruto_unitario: float | None = Field(default=None, gt=0)
    composicao_mistura: str | None = None
    observacoes: str | None = None


class OrdemProducaoResponse(BaseModel):
    id: int
    numero_op: str
    data_emissao: date | None
    tipo_op: str | None
    setor_produtivo: str | None
    lote: str | None
    periodo_inicio: date
    periodo_fim: date
    produto_codigo: str | None
    produto_descricao: str | None
    quantidade_a_produzir: int
    numero_maquina: str | None
    equipamento_descricao: str | None
    ferramenta_codigo: str | None
    ferramenta_descricao: str | None
    formula_codigo: str | None
    formula_descricao: str | None
    embalagem_codigo: str | None
    embalagem_descricao: str | None
    qtde_por_embalagem: int | None
    qtde_embalagens_previstas: int | None
    cavidades: int | None
    ciclo_segundos: float | None
    qtde_produzida_por_hora_meta: int | None
    peso_liquido_unitario: float | None
    peso_bruto_unitario: float | None
    composicao_mistura: str | None
    observacoes: str | None
    criado_em: datetime

    class Config:
        from_attributes = True


class OrdemProducaoComparativo(BaseModel):
    """Meta planejada x produção real apontada nos turnos, dentro do
    período da OP e (se houver máquina vinculada) filtrada por ela."""

    ordem_id: int
    numero_op: str
    quantidade_meta: int
    quantidade_produzida: int
    percentual_atingido: float
    periodo_inicio: date
    periodo_fim: date
    dentro_do_prazo: bool
