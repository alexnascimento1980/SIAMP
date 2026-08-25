from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.lancamento import Lancamento
from app.models.maquina import Maquina
from app.models.ordem_producao import OrdemProducao
from app.models.registro_turno import RegistroHorario
from app.models.turno import Turno
from app.models.usuario import Usuario
from app.services.analytics import calcular_kpis_varios_turnos_generico
from app.services.dashboard_service import PERIODOS_VALIDOS, calcular_metricas_acumuladas
from app.services.ml_engine import prever_risco_operacional
from app.services.turno_service import STATUS_ASSINADO

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Quantos turnos/OPs mais recentes aparecem nos gráficos do dashboard -
# limite para não sobrecarregar a tela com um histórico muito longo.
LIMITE_TURNOS_GRAFICO = 10
LIMITE_ORDENS_COMPARATIVO = 8


def _montar_producao_por_turno(db: Session) -> dict:
    """Produção e OEE dos turnos mais recentes, em ordem cronológica
    (mais antigo primeiro) - para o gráfico de tendência. Só turnos
    fechados (ASSINADO_DIGITALMENTE) entram aqui - rascunhos em
    andamento não devem aparecer como se já fossem dado consolidado.
    Cobre os dois modelos de apontamento (HORARIO e LANCAMENTO)."""
    ultimos_turnos = (
        db.query(Turno)
        .filter(Turno.status_assinatura == STATUS_ASSINADO)
        .order_by(Turno.data_registro.desc())
        .limit(LIMITE_TURNOS_GRAFICO)
        .all()
    )
    ultimos_turnos.reverse()

    kpis_por_turno = calcular_kpis_varios_turnos_generico(db, ultimos_turnos)

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
    agregada por modelo de apontamento para somar a produção de todas
    de uma vez, em vez de uma consulta por OP. Soma os dois modelos
    (HORARIO e LANCAMENTO) - uma OP pode ser atendida por turnos dos
    dois tipos ao longo do tempo."""
    ordens = (
        db.query(OrdemProducao)
        .order_by(OrdemProducao.periodo_inicio.desc())
        .limit(LIMITE_ORDENS_COMPARATIVO)
        .all()
    )
    if not ordens:
        return []

    ids_ordens = [o.id for o in ordens]
    producao_por_ordem: dict[int, int] = {}

    for oid, total in (
        db.query(
            RegistroHorario.ordem_producao_id,
            func.coalesce(func.sum(RegistroHorario.prod_executada), 0),
        )
        .join(Turno, RegistroHorario.turno_id == Turno.id)
        .filter(RegistroHorario.ordem_producao_id.in_(ids_ordens))
        .filter(Turno.status_assinatura == STATUS_ASSINADO)
        .group_by(RegistroHorario.ordem_producao_id)
        .all()
    ):
        producao_por_ordem[oid] = producao_por_ordem.get(oid, 0) + int(total or 0)

    for oid, total in (
        db.query(
            Lancamento.ordem_producao_id,
            func.coalesce(func.sum(Lancamento.quantidade), 0),
        )
        .join(Turno, Lancamento.turno_id == Turno.id)
        .filter(Lancamento.ordem_producao_id.in_(ids_ordens))
        .filter(Lancamento.tipo == "PRODUCAO")
        .filter(Turno.status_assinatura == STATUS_ASSINADO)
        .group_by(Lancamento.ordem_producao_id)
        .all()
    ):
        producao_por_ordem[oid] = producao_por_ordem.get(oid, 0) + int(total or 0)

    resultado = []
    for o in ordens:
        produzido = producao_por_ordem.get(o.id, 0)
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
    periodo: str = "total",
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """
    periodo: 'diario' (hoje), 'semanal' (últimos 7 dias), 'mensal'
    (últimos 30 dias) ou 'total' (todo o histórico, padrão) - filtra
    os KPIs acumulados e a produção por injetora. O gráfico de
    'Produção por Turno' (últimos 10 turnos) e o comparativo de
    Ordens de Produção continuam sempre mostrando os mais recentes,
    independente do período escolhido - são naturalmente "por turno",
    não acumulados por data.
    """
    if periodo not in PERIODOS_VALIDOS:
        periodo = "total"

    metricas = calcular_metricas_acumuladas(db, periodo=periodo)

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
        "periodo": periodo,
        "kpis": {
            "total_turnos_encerrados": metricas["total_turnos_encerrados"],
            "total_pecas_produzidas": metricas["total_pecas_produzidas"],
            "oee_medio_estimado": metricas["oee_medio_estimado"],
        },
        "grafico_producao": {
            "labels": [f"Injetora {m['numero_maquina']}" for m in metricas["producao_por_maquina"]],
            "valores": [m["total_produzido"] for m in metricas["producao_por_maquina"]],
        },
        "producao_por_turno": _montar_producao_por_turno(db),
        "comparativo_ordens_producao": _montar_comparativo_ordens_producao(db),
        "insight_ml": insight_ia,
    }