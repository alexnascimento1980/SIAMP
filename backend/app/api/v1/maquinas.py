from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import exigir_perfil, get_current_user
from app.core.database import get_db
from app.models.maquina import Maquina
from app.models.usuario import Usuario
from app.schemas.maquina_schema import MaquinaCreate, MaquinaResponse, MaquinaUpdate

router = APIRouter(prefix="/maquinas", tags=["Máquinas"])


@router.get("/", response_model=list[MaquinaResponse])
def listar_maquinas(
    incluir_inativas: bool = False,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    query = db.query(Maquina)
    if not incluir_inativas:
        query = query.filter(Maquina.ativo.is_(True))
    return query.order_by(Maquina.numero_maquina).all()


@router.post("/", response_model=MaquinaResponse, status_code=status.HTTP_201_CREATED)
def criar_maquina(
    dados: MaquinaCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(exigir_perfil("ADMIN", "SUPERVISOR")),
):
    ja_existe = db.query(Maquina).filter(Maquina.numero_maquina == dados.numero_maquina).first()
    if ja_existe:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma máquina cadastrada com este número.",
        )

    nova_maquina = Maquina(**dados.model_dump())
    db.add(nova_maquina)
    db.commit()
    db.refresh(nova_maquina)
    return nova_maquina


@router.patch("/{maquina_id}", response_model=MaquinaResponse)
def atualizar_maquina(
    maquina_id: int,
    dados: MaquinaUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(exigir_perfil("ADMIN", "SUPERVISOR")),
):
    maquina = db.query(Maquina).filter(Maquina.id == maquina_id).first()
    if maquina is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Máquina não encontrada.",
        )

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(maquina, campo, valor)

    db.commit()
    db.refresh(maquina)
    return maquina


@router.delete("/{maquina_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_maquina(
    maquina_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(exigir_perfil("ADMIN", "SUPERVISOR")),
):
    maquina = db.query(Maquina).filter(Maquina.id == maquina_id).first()
    if maquina is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Máquina não encontrada.",
        )

    db.delete(maquina)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Não é possível excluir: esta máquina já tem registros de "
                "produção ou Ordens de Produção vinculados. Desative-a em "
                "vez de excluir, para preservar o histórico."
            ),
        )