from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.lancamento import Lancamento
from app.models.maquina import Maquina
from app.models.ordem_producao import OrdemProducao
from app.models.produto import Produto
from app.models.registro_turno import RegistroHorario
from app.models.turno import Turno
from app.models.usuario import Usuario
from app.services.dashboard_service import (
    PERIODOS_VALIDOS,
    calcular_metricas_acumuladas,
    montar_producao_por_turno,
)
from app.services.ml_engine import prever_risco_parada
from app.services.turno_service import STATUS_ASSINADO

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Quantas Ordens de Produção mais recentes aparecem no comparativo do
# dashboard - limite para não sobrecarregar a tela com um histórico
# muito longo.
LIMITE_ORDENS_COMPARATIVO = 8


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
        .filter(Turno.marcado_teste.is_(False))
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
        .filter(Turno.marcado_teste.is_(False))
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


def _montar_diagnostico_ia(db: Session) -> dict:
    """Risco de a próxima produção de uma injetora ser seguida por uma
    parada não programada, calculado a partir do lançamento de
    produção mais recente registrado no sistema (modelo de
    lançamentos livres - o modelo por hora, descontinuado, não tem os
    dados de ciclo real necessários para esta previsão)."""
    ultimo = (
        db.query(Lancamento, Turno, Maquina, Produto)
        .join(Turno, Turno.id == Lancamento.turno_id)
        .join(Maquina, Maquina.id == Lancamento.maquina_id)
        .outerjoin(Produto, Produto.id == Lancamento.produto_id)
        .filter(Lancamento.tipo == "PRODUCAO")
        .order_by(Lancamento.id.desc())
        .first()
    )

    if not ultimo:
        return {
            "risco_desvio": False,
            "probabilidade_critica": 0.0,
            "mensagem": "Sem lançamentos de produção suficientes para diagnóstico.",
            "fonte": "sem_dados",
            "detalhe": {},
        }

    lanc, turno, maq, produto = ultimo

    ciclo_efetivo = lanc.ciclo_informado or (produto.ciclo_padrao if produto else None) or maq.ciclo_padrao
    cavidades_efetivas = (produto.cavidades if produto else None) or maq.cavidades

    inicio_seg = (
        lanc.horario_inicio.hour * 3600 + lanc.horario_inicio.minute * 60 + lanc.horario_inicio.second
    )
    fim_seg = lanc.horario_fim.hour * 3600 + lanc.horario_fim.minute * 60 + lanc.horario_fim.second
    if fim_seg <= inicio_seg:
        fim_seg += 24 * 3600
    duracao_min = (fim_seg - inicio_seg) / 60

    primeiro_char = turno.nome_turno[0] if turno.nome_turno else "1"
    turno_num = int(primeiro_char) if primeiro_char.isdigit() else 1
    dia_semana = turno.data_registro.weekday()

    return prever_risco_parada(
        db=db,
        maquina_id=maq.id,
        produto_id=produto.id if produto else None,
        ciclo_efetivo=ciclo_efetivo,
        ciclo_padrao_peca=produto.ciclo_padrao if produto else None,
        cavidades_efetivas=cavidades_efetivas,
        duracao_min=duracao_min,
        quantidade=lanc.quantidade,
        turno_num=turno_num,
        dia_semana=dia_semana,
    )


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
    insight_ia = _montar_diagnostico_ia(db)

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
        "producao_por_turno": montar_producao_por_turno(db),
        "comparativo_ordens_producao": _montar_comparativo_ordens_producao(db),
        "insight_ml": insight_ia,
    }