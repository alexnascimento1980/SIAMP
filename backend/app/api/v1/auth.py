from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import COOKIE_NAME, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import criar_access_token, verificar_senha
from app.models.usuario import Usuario
from app.schemas.auth_schema import TokenResponse, UsuarioLogadoResponse

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Autentica por e-mail (campo `username` do form OAuth2) e senha.

    Define o token também como cookie httpOnly (usado pelo frontend web,
    que não precisa mais manter o JWT em localStorage/JS — reduz o
    impacto de um eventual XSS). O token continua vindo no corpo da
    resposta em JSON para compatibilidade com clientes de API e com o
    Swagger (/docs), que usam `Authorization: Bearer <token>`.

    Limitado a 5 tentativas por minuto por IP, para dificultar ataques
    de força bruta contra senhas.
    """
    usuario = db.query(Usuario).filter(Usuario.email == form_data.username).first()

    if usuario is None or not verificar_senha(form_data.password, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos.",
        )

    if not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário desativado. Contate um administrador.",
        )

    token = criar_access_token(subject=usuario.email, perfil=usuario.perfil)

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.jwt_expires_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        # "lax" é suficiente aqui: o frontend só chama a API via fetch/XHR
        # (nunca via navegação de topo cross-site), e cookies SameSite=Lax
        # não são enviados em requests cross-site desse tipo — o que já
        # mitiga CSRF nos endpoints de escrita sem precisar de um token
        # CSRF separado.
        samesite="lax",
        path="/",
    )

    return TokenResponse(access_token=token)


@router.post("/logout")
def logout(response: Response):
    """Encerra a sessão do navegador removendo o cookie httpOnly."""
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "sucesso", "mensagem": "Sessão encerrada."}


@router.get("/me", response_model=UsuarioLogadoResponse)
def usuario_atual(usuario: Usuario = Depends(get_current_user)):
    return usuario
