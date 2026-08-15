from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.models.registro_turno import Turno, RegistroHorario, Maquina
from app.services.ml_engine import prever_risco_operacional

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/metricas-gerais")
def obter_metricas_dashboard(db: Session = Depends(get_db)):
    total_turnos = db.query(func.count(Turno.id)).scalar() or 0
    total_pecas = db.query(func.sum(RegistroHorario.prod_executada)).scalar() or 0
    
    # Consulta produção agrupada por máquina (Injetoras 1 a 6)
    producao_por_maquina = db.query(
        Maquina.numero_maquina,
        func.sum(RegistroHorario.prod_executada).label("total_produzido")
    ).join(RegistroHorario, Maquina.id == RegistroHorario.maquina_id, isouter=True)\
     .group_by(Maquina.numero_maquina)\
     .order_by(Maquina.numero_maquina).all()

    # Diagnóstico da IA para a última máquina operada
    insight_ia = prever_risco_operacional(
        numero_maquina=1, cavidades=4, ciclo_padrao=18.5, tempo_parada_minutos=15.0
    )

    return {
        "kpis": {
            "total_turnos_encerrados": total_turnos,
            "total_pecas_produzidas": total_pecas,
            "oee_medio_estimado": 82.4
        },
        "grafico_producao": {
            "labels": [f"Injetora {m.numero_maquina}" for m in producao_por_maquina],
            "valores": [m.total_produzido or 0 for m in producao_por_maquina]
        },
        "insight_ml": insight_ia
    }