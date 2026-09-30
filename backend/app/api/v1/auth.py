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

# Hash bcrypt fixo, pré-computado, não ligado a nenhum usuário real -
# usado só como alvo de comparação em /login quando o e-mail informado
# não existe, para gastar aproximadamente o mesmo tempo de CPU que uma
# tentativa com e-mail válido e senha errada (ver comentário em
# login() - mitiga enumeração de e-mail por tempo de resposta).
_HASH_FALSO_PARA_TIMING = "$2b$12$oMj.DNOAk/Z7exFXwA1o1eLdEICHgMdft.2R4eUjBK/RS/cwBE5sy"


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

    # Sempre roda a verificação de senha, mesmo quando o e-mail não
    # existe - com curto-circuito (usuario is None or not verificar_senha(...))
    # a chamada ao bcrypt (deliberadamente lenta) só acontecia quando o
    # e-mail existia, tornando a resposta mensuravelmente mais rápida
    # para e-mails inexistentes; isso permite enumerar quais e-mails
    # têm conta só pelo tempo de resposta, mesmo com a mensagem de erro
    # sendo idêntica nos dois casos. Usa um hash bcrypt fixo (não
    # ligado a usuário nenhum) como alvo da verificação quando o
    # usuário não existe, para gastar aproximadamente o mesmo tempo de
    # CPU nos dois caminhos.
    hash_para_comparar = usuario.senha_hash if usuario else _HASH_FALSO_PARA_TIMING
    senha_valida = verificar_senha(form_data.password, hash_para_comparar)

    if usuario is None or not senha_valida:
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
