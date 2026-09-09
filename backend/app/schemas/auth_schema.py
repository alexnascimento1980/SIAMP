from pydantic import BaseModel, ConfigDict


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UsuarioLogadoResponse(BaseModel):
    id: int
    nome: str
    email: str
    perfil: str

    model_config = ConfigDict(from_attributes=True)
