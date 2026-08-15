from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.registro_turno import Maquina

router = APIRouter(prefix="/maquinas", tags=["Máquinas"])

@router.get("/")
def listar_maquinas(db: Session = Depends(get_db)):
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