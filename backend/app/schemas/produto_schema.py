from pydantic import BaseModel, Field


class ProdutoBase(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=50)
    descricao: str = Field(..., min_length=2, max_length=200)
    ciclo_padrao: float | None = Field(default=None, gt=0)
    cavidades: int | None = Field(default=None, gt=0)
    peso_gramas: float | None = Field(default=None, gt=0)
    ativo: bool = True


class ProdutoCreate(ProdutoBase):
    pass


class ProdutoResponse(ProdutoBase):
    id: int

    class Config:
        from_attributes = True
