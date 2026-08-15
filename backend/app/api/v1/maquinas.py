from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.maquina import Maquina
from app.models.usuario import Usuario

router = APIRouter(prefix="/maquinas", tags=["Máquinas"])

@router.get("/")
def listar_maquinas(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    maquinas = db.query(Maquina).order_by(Maquina.numero_maquina).all()
    return [
        {
            "id": m.id,
            "numero_maquina": m.numero_maquina,
            "descricao": m.descricao,
            "cavidades": m.cavidades,
            "ciclo_padrao": m.ciclo_padrao
        }
        for m in maquinas
    ]