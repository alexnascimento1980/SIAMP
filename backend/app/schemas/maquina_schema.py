from pydantic import BaseModel, Field


class MaquinaBase(BaseModel):
    numero_maquina: str = Field(..., min_length=1, max_length=30)
    descricao: str | None = Field(default=None, max_length=150)
    cavidades: int = Field(..., gt=0)
    ciclo_padrao: float = Field(..., gt=0)
    ativo: bool = True


class MaquinaCreate(MaquinaBase):
    pass


class MaquinaResponse(MaquinaBase):
    id: int

    class Config:
        from_attributes = True
