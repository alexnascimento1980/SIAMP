from pydantic import BaseModel, Field


class ProdutoBase(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=50)
    descricao: str = Field(..., min_length=2, max_length=200)
    ciclo_padrao: float | None = Field(default=None, gt=0)
    cavidades: int | None = Field(default=None, gt=0)
    peso_gramas: float | None = Field(default=None, gt=0)
    ativo: bool = True


class ProdutoCreate(ProdutoBase):
    # Obrigatórios apenas para peças novas - a fonte de verdade de
    # ciclo/cavidades passou a ser a Peça, não mais a Máquina (ver
    # maquina_schema.py). Peças já cadastradas sem esses valores
    # continuam existindo normalmente (ProdutoResponse permanece
    # aceitando None, para não quebrar dados antigos).
    ciclo_padrao: float = Field(..., gt=0)
    cavidades: int = Field(..., gt=0)


class ProdutoUpdate(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=50)
    descricao: str | None = Field(default=None, min_length=2, max_length=200)
    ciclo_padrao: float | None = Field(default=None, gt=0)
    cavidades: int | None = Field(default=None, gt=0)
    peso_gramas: float | None = Field(default=None, gt=0)
    ativo: bool | None = None


class ProdutoResponse(ProdutoBase):
    id: int

    class Config:
        from_attributes = True
