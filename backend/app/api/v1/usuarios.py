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
    UsuarioUpdatePerfil,
    UsuarioUpdateProtegido,
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

    if alvo.protegido and not dados.ativo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"'{alvo.nome}' está marcada como conta protegida - "
                "remova a proteção antes de desativar."
            ),
        )

    alvo.ativo = dados.ativo
    db.commit()
    db.refresh(alvo)
    return alvo


@router.patch("/{usuario_id}/perfil", response_model=UsuarioResponse)
def alterar_perfil_usuario(
    usuario_id: int,
    dados: UsuarioUpdatePerfil,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(exigir_perfil("ADMIN")),
):
    """Muda o perfil de acesso (ADMIN/SUPERVISOR/OPERADOR) de um
    usuário. Restrito a ADMIN. Um ADMIN não pode alterar o próprio
    perfil por aqui - mesma lógica de proteção já usada para
    desativação de conta: evita que uma troca acidental (ex.: rebaixar
    a própria conta para OPERADOR) tire o próprio acesso administrativo
    sem querer."""
    alvo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if alvo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado.",
        )

    try:
        novo_perfil = dados.perfil_normalizado()
    except ValueError as erro:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(erro),
        )

    if alvo.id == usuario_atual.id and novo_perfil != usuario_atual.perfil:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode alterar o próprio perfil de acesso.",
        )

    alvo.perfil = novo_perfil
    db.commit()
    db.refresh(alvo)
    return alvo


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(exigir_perfil("ADMIN")),
):
    """Exclui definitivamente um usuário (não é reversível, diferente
    de desativar). Pensado para contas de teste ou de colaboradores
    desligados. Turnos editados, Ordens de Produção criadas ou paradas
    registradas por esse usuário NÃO são apagados - continuam
    normalmente no histórico, só perdem a referência de quem foi
    (comportamento configurado nas chaves estrangeiras, ON DELETE SET
    NULL - ver migration 0013). Restrito a ADMIN; um ADMIN não pode
    excluir a própria conta."""
    alvo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if alvo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado.",
        )

    if alvo.id == usuario_atual.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode excluir a própria conta.",
        )

    if alvo.protegido:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"'{alvo.nome}' está marcada como conta protegida - "
                "remova a proteção antes de excluir."
            ),
        )

    db.delete(alvo)
    db.commit()


@router.patch("/{usuario_id}/protegido", response_model=UsuarioResponse)
def alterar_protecao_usuario(
    usuario_id: int,
    dados: UsuarioUpdateProtegido,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(exigir_perfil("ADMIN")),
):
    """Marca ou desmarca uma conta como protegida contra exclusão e
    desativação acidental por outro ADMIN. Reversível - marcar uma
    conta como protegida não impede que ela seja excluída/desativada
    de verdade um dia, só exige desproteger antes, deliberadamente,
    em vez de acontecer com um único clique. Sem restrição sobre
    proteger/desproteger a própria conta (diferente de excluir/
    desativar/alterar perfil) - não há risco de perda de acesso
    envolvido nessa ação em si."""
    alvo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if alvo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado.",
        )

    alvo.protegido = dados.protegido
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