from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.usuario import Usuario
from app.services.dashboard_service import (
    PERIODOS_VALIDOS,
    calcular_metricas_acumuladas,
    montar_comparativo_ordens_producao,
    montar_diagnostico_ia,
    montar_producao_por_turno,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/metricas-gerais")
def obter_metricas_dashboard(
    periodo: str = "total",
    data_inicio: date | None = None,
    data_fim: date | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """
    periodo: 'diario' (hoje), 'semanal' (últimos 7 dias), 'mensal'
    (últimos 30 dias), 'total' (todo o histórico, padrão) ou
    'personalizado' (intervalo específico, exige data_inicio e
    data_fim) - filtra os KPIs acumulados e a produção por injetora.
    O gráfico de 'Produção por Turno' (últimos 10 turnos) e o
    comparativo de Ordens de Produção continuam sempre mostrando os
    mais recentes, independente do período escolhido - são
    naturalmente "por turno", não acumulados por data.
    """
    if periodo not in PERIODOS_VALIDOS:
        periodo = "total"

    if periodo == "personalizado":
        if data_inicio is None or data_fim is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Período personalizado exige data_inicio e data_fim.",
            )
        if data_fim < data_inicio:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A data final não pode ser anterior à data inicial.",
            )

    metricas = calcular_metricas_acumuladas(
        db, periodo=periodo, data_inicio_custom=data_inicio, data_fim_custom=data_fim
    )
    insight_ia = montar_diagnostico_ia(db)

    return {
        "periodo": periodo,
        "data_inicio": data_inicio.isoformat() if data_inicio else None,
        "data_fim": data_fim.isoformat() if data_fim else None,
        "kpis": {
            "total_turnos_encerrados": metricas["total_turnos_encerrados"],
            "total_pecas_produzidas": metricas["total_pecas_produzidas"],
            "oee_medio_estimado": metricas["oee_medio_estimado"],
        },
        "grafico_producao": {
            "labels": [f"Injetora {m['numero_maquina']}" for m in metricas["producao_por_maquina"]],
            "valores": [m["total_produzido"] for m in metricas["producao_por_maquina"]],
        },
        "producao_por_turno": montar_producao_por_turno(db),
        "comparativo_ordens_producao": montar_comparativo_ordens_producao(db),
        "insight_ml": insight_ia,
    }
