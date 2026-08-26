from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import exigir_perfil, get_current_user
from app.core.database import get_db
from app.core.security import gerar_hash_senha
from app.models.usuario import Usuario
from app.schemas.usuario_schema import (
    UsuarioCreate,
    UsuarioResetSenha,
    UsuarioResponse,
    UsuarioUpdateStatus,
)

router = APIRouter(prefix="/usuarios", tags=["Usuários"])


@router.get("/", response_model=list[UsuarioResponse])
def listar_usuarios(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_perfil("ADMIN")),
):
    return db.query(Usuario).order_by(Usuario.nome).all()


@router.post("/", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
def criar_usuario(
    dados: UsuarioCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(exigir_perfil("ADMIN")),
):
    ja_existe = db.query(Usuario).filter(Usuario.email == dados.email).first()
    if ja_existe:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um usuário cadastrado com este e-mail.",
        )

    novo_usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=gerar_hash_senha(dados.senha),
        perfil=dados.perfil_normalizado(),
        ativo=True,
    )
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)
    return novo_usuario


@router.patch("/{usuario_id}/status", response_model=UsuarioResponse)
def alterar_status_usuario(
    usuario_id: int,
    dados: UsuarioUpdateStatus,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(exigir_perfil("ADMIN")),
):
    alvo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if alvo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado.",
        )

    if alvo.id == usuario_atual.id and not dados.ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode desativar a própria conta.",
        )

    alvo.ativo = dados.ativo
    db.commit()
    db.refresh(alvo)
    return alvo


@router.patch("/{usuario_id}/senha", response_model=UsuarioResponse)
def resetar_senha_usuario(
    usuario_id: int,
    dados: UsuarioResetSenha,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(exigir_perfil("ADMIN")),
):
    """Define uma nova senha para o usuário, sem exigir a senha atual -
    fluxo de recuperação quando o usuário esqueceu a própria senha e
    não tem outro jeito de entrar. Restrito a ADMIN. Não há como
    'visualizar' a senha atual em nenhuma circunstância: senhas são
    guardadas apenas como hash (bcrypt), uma função de mão única - só
    é possível definir uma nova, nunca recuperar a antiga."""
    alvo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if alvo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado.",
        )

    alvo.senha_hash = gerar_hash_senha(dados.nova_senha)
    db.commit()
    db.refresh(alvo)
    return alvo