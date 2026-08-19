from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.maquina import Maquina
from app.models.ordem_producao import OrdemProducao
from app.models.registro_turno import RegistroHorario
from app.models.turno import Turno
from app.models.usuario import Usuario
from app.services.analytics import calcular_kpis_varios_turnos
from app.services.ml_engine import prever_risco_operacional

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Quantos turnos/OPs mais recentes aparecem nos gráficos do dashboard -
# limite para não sobrecarregar a tela com um histórico muito longo.
LIMITE_TURNOS_GRAFICO = 10
LIMITE_ORDENS_COMPARATIVO = 8


def _montar_producao_por_turno(db: Session) -> dict:
    """Produção e OEE dos turnos mais recentes, em ordem cronológica
    (mais antigo primeiro) - para o gráfico de tendência."""
    ultimos_turnos = (
        db.query(Turno)
        .order_by(Turno.data_registro.desc())
        .limit(LIMITE_TURNOS_GRAFICO)
        .all()
    )
    ultimos_turnos.reverse()

    kpis_por_turno = calcular_kpis_varios_turnos(db, [t.id for t in ultimos_turnos])

    labels = []
    for t in ultimos_turnos:
        prefixo = t.nome_turno.split("(")[0].strip()
        labels.append(f"{prefixo} {t.data_registro.strftime('%d/%m')}")

    return {
        "labels": labels,
        "produzido": [kpis_por_turno[t.id]["total_produzido"] for t in ultimos_turnos],
        "oee": [kpis_por_turno[t.id]["eficiencia_oee"] for t in ultimos_turnos],
    }


def _montar_comparativo_ordens_producao(db: Session) -> list[dict]:
    """Meta x produção real das Ordens de Produção mais recentes (por
    data de início do período programado). Usa uma única query
    agregada para somar a produção de todas de uma vez, em vez de uma
    consulta por OP."""
    ordens = (
        db.query(OrdemProducao)
        .order_by(OrdemProducao.periodo_inicio.desc())
        .limit(LIMITE_ORDENS_COMPARATIVO)
        .all()
    )
    if not ordens:
        return []

    producao_por_ordem = dict(
        db.query(
            RegistroHorario.ordem_producao_id,
            func.coalesce(func.sum(RegistroHorario.prod_executada), 0),
        )
        .filter(RegistroHorario.ordem_producao_id.in_([o.id for o in ordens]))
        .group_by(RegistroHorario.ordem_producao_id)
        .all()
    )

    resultado = []
    for o in ordens:
        produzido = int(producao_por_ordem.get(o.id, 0) or 0)
        percentual = round(produzido / o.quantidade_a_produzir * 100, 1) if o.quantidade_a_produzir else 0.0
        resultado.append({
            "numero_op": o.numero_op,
            "produto_descricao": o.produto_descricao,
            "quantidade_meta": o.quantidade_a_produzir,
            "quantidade_produzida": produzido,
            "percentual_atingido": percentual,
        })
    return resultado


@router.get("/metricas-gerais")
def obter_metricas_dashboard(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    total_turnos = db.query(func.count(Turno.id)).scalar() or 0
    total_pecas = db.query(func.sum(RegistroHorario.prod_executada)).scalar() or 0

    # OEE médio real, calculado a partir dos KPIs de cada turno encerrado
    # (antes era um valor fixo de 82.4%, que não refletia os dados reais).
    ids_turnos = [t.id for t in db.query(Turno.id).all()]
    kpis_por_turno = calcular_kpis_varios_turnos(db, ids_turnos)
    if kpis_por_turno:
        oee_medio_estimado = round(
            sum(k["eficiencia_oee"] for k in kpis_por_turno.values())
            / len(kpis_por_turno),
            2,
        )
    else:
        oee_medio_estimado = 0.0
    
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
            "oee_medio_estimado": oee_medio_estimado
        },
        "grafico_producao": {
            "labels": [f"Injetora {m.numero_maquina}" for m in producao_por_maquina],
            "valores": [m.total_produzido or 0 for m in producao_por_maquina]
        },
        "producao_por_turno": _montar_producao_por_turno(db),
        "comparativo_ordens_producao": _montar_comparativo_ordens_producao(db),
        "insight_ml": insight_ia
    }