from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decodificar_access_token
from app.models.usuario import Usuario

# Nome do cookie httpOnly de sessão, definido em /auth/login (ver
# app/api/v1/auth.py) e usado pelo frontend web.
COOKIE_NAME = "siamp_token"

# auto_error=False: a ausência do header Authorization não deve derrubar a
# request aqui, pois o token também pode chegar via cookie httpOnly (fluxo
# do frontend). Continua funcionando normalmente com Bearer token puro
# para clientes de API e para testar pelo Swagger (/docs).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    request: Request,
    token_header: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou expiradas.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = token_header or request.cookies.get(COOKIE_NAME)
    if token is None:
        raise credenciais_invalidas

    payload = decodificar_access_token(token)
    if payload is None:
        raise credenciais_invalidas

    email = payload.get("sub")
    if email is None:
        raise credenciais_invalidas

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario is None or not usuario.ativo:
        raise credenciais_invalidas

    return usuario


def exigir_perfil(*perfis_permitidos: str):
    """Dependência de autorização: restringe uma rota a certos perfis
    (ex.: exigir_perfil("SUPERVISOR", "ADMIN"))."""

    def verificador(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.perfil not in perfis_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário sem permissão para esta operação.",
            )
        return usuario

    return verificador
