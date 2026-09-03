from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.parada import Parada
from app.models.usuario import Usuario
from app.schemas.parada_schema import ParadaCreate

router = APIRouter(prefix="/paradas", tags=["Paradas"])


@router.post("/", status_code=status.HTTP_201_CREATED)
def registrar_parada(
    dados: ParadaCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    parada = Parada(
        turno_id=dados.turno_id,
        maquina_id=dados.maquina_id,
        inicio=dados.inicio,
        fim=dados.fim,
        duracao_minutos=dados.duracao_minutos,
        motivo=dados.motivo,
        categoria=dados.categoria,
        observacao=dados.observacao,
        usuario_id=dados.usuario_id or usuario.id,
    )
    db.add(parada)
    db.commit()
    db.refresh(parada)
    return {"id": parada.id, "status": "registrado"}


@router.get("/turno/{turno_id}")
def listar_paradas_do_turno(
    turno_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    paradas = (
        db.query(Parada)
        .filter(Parada.turno_id == turno_id)
        .order_by(Parada.inicio)
        .all()
    )
    if not paradas:
        return []
    return [
        {
            "id": p.id,
            "maquina_id": p.maquina_id,
            "inicio": p.inicio,
            "fim": p.fim,
            "duracao_minutos": p.duracao_minutos,
            "motivo": p.motivo,
            "categoria": p.categoria,
            "observacao": p.observacao,
        }
        for p in paradas
    ]
