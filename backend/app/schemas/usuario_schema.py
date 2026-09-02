from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

PERFIS_VALIDOS = ("ADMIN", "SUPERVISOR", "OPERADOR")


class UsuarioCreate(BaseModel):
    nome: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    senha: str = Field(..., min_length=8, max_length=72)
    perfil: str = Field(default="OPERADOR")

    def perfil_normalizado(self) -> str:
        valor = self.perfil.upper().strip()
        return valor if valor in PERFIS_VALIDOS else "OPERADOR"


class UsuarioUpdateStatus(BaseModel):
    ativo: bool


class UsuarioUpdatePerfil(BaseModel):
    perfil: str

    def perfil_normalizado(self) -> str:
        valor = self.perfil.upper().strip()
        if valor not in PERFIS_VALIDOS:
            raise ValueError(f"Perfil inválido. Use um de: {', '.join(PERFIS_VALIDOS)}")
        return valor


class UsuarioResetSenha(BaseModel):
    nova_senha: str = Field(..., min_length=8, max_length=72)


class UsuarioResponse(BaseModel):
    id: int
    nome: str
    email: str
    perfil: str
    ativo: bool
    protegido: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class UsuarioUpdateProtegido(BaseModel):
    protegido: bool