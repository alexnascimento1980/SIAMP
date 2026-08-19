from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import exigir_perfil
from app.core.database import get_db
from app.models.destinatario_relatorio import DestinatarioRelatorio
from app.models.usuario import Usuario
from app.schemas.destinatario_schema import (
    DestinatarioCreate,
    DestinatarioResponse,
    DestinatarioUpdate,
)

router = APIRouter(prefix="/destinatarios", tags=["Destinatários de Relatório"])


@router.get("/", response_model=list[DestinatarioResponse])
def listar_destinatarios(
    incluir_inativos: bool = False,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_perfil("ADMIN")),
):
    """
    Lista de e-mails que recebem o relatório de fechamento de turno.
    Restrito a ADMIN - é dado sensível (define quem recebe informações
    de produção da empresa).
    """
    query = db.query(DestinatarioRelatorio)
    if not incluir_inativos:
        query = query.filter(DestinatarioRelatorio.ativo.is_(True))
    return query.order_by(DestinatarioRelatorio.email).all()


@router.post("/", response_model=DestinatarioResponse, status_code=status.HTTP_201_CREATED)
def criar_destinatario(
    dados: DestinatarioCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_perfil("ADMIN")),
):
    email_normalizado = dados.email.lower()
    ja_existe = (
        db.query(DestinatarioRelatorio)
        .filter(DestinatarioRelatorio.email == email_normalizado)
        .first()
    )
    if ja_existe:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este e-mail já está cadastrado como destinatário.",
        )

    novo = DestinatarioRelatorio(
        email=email_normalizado,
        nome=dados.nome,
        ativo=dados.ativo,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


@router.patch("/{destinatario_id}", response_model=DestinatarioResponse)
def atualizar_destinatario(
    destinatario_id: int,
    dados: DestinatarioUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_perfil("ADMIN")),
):
    destinatario = (
        db.query(DestinatarioRelatorio)
        .filter(DestinatarioRelatorio.id == destinatario_id)
        .first()
    )
    if destinatario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destinatário não encontrado.",
        )

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(destinatario, campo, valor)

    db.commit()
    db.refresh(destinatario)
    return destinatario


@router.delete("/{destinatario_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_destinatario(
    destinatario_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_perfil("ADMIN")),
):
    destinatario = (
        db.query(DestinatarioRelatorio)
        .filter(DestinatarioRelatorio.id == destinatario_id)
        .first()
    )
    if destinatario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destinatário não encontrado.",
        )

    db.delete(destinatario)
    db.commit()
