from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.maquina import Maquina
from app.models.registro_turno import RegistroHorario
from app.models.turno import Turno
from app.models.usuario import Usuario
from app.services.ml_engine import prever_risco_operacional

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/metricas-gerais")
def obter_metricas_dashboard(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    total_turnos = db.query(func.count(Turno.id)).scalar() or 0
    total_pecas = db.query(func.sum(RegistroHorario.prod_executada)).scalar() or 0
    
    # Consulta produção agrupada por máquina (Injetoras 1 a 6)
    producao_por_maquina = db.query(
        Maquina.numero_maquina,
        func.sum(RegistroHorario.prod_executada).label("total_produzido")
    ).join(RegistroHorario, Maquina.id == RegistroHorario.maquina_id, isouter=True)\
     .group_by(Maquina.numero_maquina)\
     .order_by(Maquina.numero_maquina).all()

    # Diagnóstico da IA baseado no registro mais recente com parada,
    # em vez de valores fixos que ignoravam os dados reais do turno.
    ultimo_registro = (
        db.query(RegistroHorario, Maquina)
        .join(Maquina, Maquina.id == RegistroHorario.maquina_id)
        .filter(RegistroHorario.inicio_parada.isnot(None))
        .order_by(RegistroHorario.id.desc())
        .first()
    )

    if ultimo_registro:
        reg, maq = ultimo_registro
        tempo_parada = 0.0
        if reg.inicio_parada and reg.retomada:
            inicio_min = reg.inicio_parada.hour * 60 + reg.inicio_parada.minute
            fim_min = reg.retomada.hour * 60 + reg.retomada.minute
            tempo_parada = max(0, fim_min - inicio_min)

        insight_ia = prever_risco_operacional(
            numero_maquina=int(maq.numero_maquina) if str(maq.numero_maquina).isdigit() else 0,
            cavidades=maq.cavidades,
            ciclo_padrao=maq.ciclo_padrao,
            tempo_parada_minutos=tempo_parada,
        )
    else:
        insight_ia = {
            "risco_desvio": False,
            "probabilidade_critica": 0.0,
            "mensagem": "Sem registros de parada suficientes para diagnóstico.",
        }

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