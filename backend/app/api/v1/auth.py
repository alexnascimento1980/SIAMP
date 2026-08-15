from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import criar_access_token, verificar_senha
from app.models.usuario import Usuario
from app.schemas.auth_schema import TokenResponse, UsuarioLogadoResponse

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Autentica por e-mail (campo `username` do form OAuth2) e senha,
    retornando um JWT a ser enviado como `Authorization: Bearer <token>`
    nas demais rotas da API.
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
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UsuarioLogadoResponse)
def usuario_atual(usuario: Usuario = Depends(get_current_user)):
    return usuario
