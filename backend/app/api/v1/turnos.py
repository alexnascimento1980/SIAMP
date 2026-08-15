from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.registro_turno import Turno, RegistroHorario

router = APIRouter(prefix="/turnos", tags=["Turnos"])

@router.post("/fechamento", status_code=status.HTTP_201_CREATED)
def criar_fechamento_turno(dados: dict, db: Session = Depends(get_db)):
    try:
        novo_turno = Turno(
            nome_turno=dados["nome_turno"],
            responsavel_nome=dados["responsavel_nome"],
            observacoes=dados.get("observacoes"),
            status_assinatura="ASSINADO"
        )
        db.add(novo_turno)
        db.commit()
        db.refresh(novo_turno)
        return {"status": "sucesso", "turno_id": novo_turno.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))