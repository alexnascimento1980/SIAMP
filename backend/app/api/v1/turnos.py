from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.turno_schema import FechamentoTurnoCreate
from app.services.turno_service import fechar_turno


router = APIRouter(prefix="/turnos", tags=["Turnos"])


@router.post("/fechamento", status_code=status.HTTP_201_CREATED)
def criar_fechamento_turno(
    dados: FechamentoTurnoCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Fecha um turno, persiste seus registros, calcula os KPIs e agenda
    o envio do relatório em background.
    """
    try:
        return fechar_turno(
            db=db,
            dados=dados,
            background_tasks=background_tasks,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao processar o fechamento do turno.",
        ) from exc
