from pydantic import BaseModel, Field


class MaquinaBase(BaseModel):
    numero_maquina: str = Field(..., min_length=1, max_length=30)
    descricao: str | None = Field(default=None, max_length=150)
    # Opcionais: a fonte de verdade de ciclo/cavidades passou a ser a
    # Peça (ver produto_schema.py), obrigatória lá. Mantidos aqui só
    # como retrocompatibilidade com máquinas já cadastradas e como
    # respaldo para registros sem peça selecionada.
    cavidades: int | None = Field(default=None, gt=0)
    ciclo_padrao: float | None = Field(default=None, gt=0)
    ativo: bool = True


class MaquinaCreate(MaquinaBase):
    pass


class MaquinaUpdate(BaseModel):
    descricao: str | None = Field(default=None, max_length=150)
    cavidades: int | None = Field(default=None, gt=0)
    ciclo_padrao: float | None = Field(default=None, gt=0)
    ativo: bool | None = None


class MaquinaResponse(MaquinaBase):
    id: int

    class Config:
        from_attributes = True