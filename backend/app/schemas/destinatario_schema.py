from pydantic import BaseModel, EmailStr, Field


class DestinatarioBase(BaseModel):
    email: EmailStr
    nome: str | None = Field(default=None, max_length=150)
    ativo: bool = True


class DestinatarioCreate(DestinatarioBase):
    pass


class DestinatarioUpdate(BaseModel):
    nome: str | None = Field(default=None, max_length=150)
    ativo: bool | None = None


class DestinatarioResponse(DestinatarioBase):
    id: int

    class Config:
        from_attributes = True
