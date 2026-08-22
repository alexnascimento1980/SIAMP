from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import case, func
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.lancamento import Lancamento
from app.models.maquina import Maquina
from app.models.ordem_producao import OrdemProducao
from app.models.registro_turno import RegistroHorario
from app.models.turno import Turno
from app.models.usuario import Usuario
from app.services.analytics import calcular_kpis_varios_turnos_generico
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
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    # Só turnos fechados contam nas métricas gerais - um rascunho em
    # andamento não deve inflar/distorcer os agregados até ser
    # efetivamente encerrado. Soma os dois modelos de apontamento.
    total_turnos = (
        db.query(func.count(Turno.id))
        .filter(Turno.status_assinatura == STATUS_ASSINADO)
        .scalar()
        or 0
    )
    total_pecas_horario = (
        db.query(func.sum(RegistroHorario.prod_executada))
        .join(Turno, RegistroHorario.turno_id == Turno.id)
        .filter(Turno.status_assinatura == STATUS_ASSINADO)
        .scalar()
        or 0
    )
    total_pecas_lancamento = (
        db.query(func.sum(Lancamento.quantidade))
        .join(Turno, Lancamento.turno_id == Turno.id)
        .filter(Lancamento.tipo == "PRODUCAO")
        .filter(Turno.status_assinatura == STATUS_ASSINADO)
        .scalar()
        or 0
    )
    total_pecas = total_pecas_horario + total_pecas_lancamento

    # OEE médio real, calculado a partir dos KPIs de cada turno encerrado
    # (antes era um valor fixo de 82.4%, que não refletia os dados reais).
    # Cobre os dois modelos de apontamento.
    turnos_fechados = (
        db.query(Turno).filter(Turno.status_assinatura == STATUS_ASSINADO).all()
    )
    kpis_por_turno = calcular_kpis_varios_turnos_generico(db, turnos_fechados)
    if kpis_por_turno:
        oee_medio_estimado = round(
            sum(k["eficiencia_oee"] for k in kpis_por_turno.values())
            / len(kpis_por_turno),
            2,
        )
    else:
        oee_medio_estimado = 0.0
    
    # Consulta produção agrupada por máquina (Injetoras 1 a 6) - só de
    # turnos fechados, somando os dois modelos de apontamento. CASE
    # WHEN dentro do SUM (não um filtro na condição do JOIN) é
    # necessário para preservar máquinas sem nenhuma produção fechada
    # ainda na lista (LEFT JOIN), zerando só a soma, sem sumir a linha
    # da máquina.
    producao_horario_por_maquina = dict(
        db.query(
            Maquina.numero_maquina,
            func.sum(
                case(
                    (Turno.status_assinatura == STATUS_ASSINADO, RegistroHorario.prod_executada),
                    else_=0,
                )
            ),
        ).outerjoin(
            RegistroHorario, Maquina.id == RegistroHorario.maquina_id
        ).outerjoin(
            Turno, RegistroHorario.turno_id == Turno.id
        ).group_by(Maquina.numero_maquina).all()
    )
    producao_lancamento_por_maquina = dict(
        db.query(
            Maquina.numero_maquina,
            func.sum(
                case(
                    (
                        (Turno.status_assinatura == STATUS_ASSINADO) & (Lancamento.tipo == "PRODUCAO"),
                        Lancamento.quantidade,
                    ),
                    else_=0,
                )
            ),
        ).outerjoin(
            Lancamento, Maquina.id == Lancamento.maquina_id
        ).outerjoin(
            Turno, Lancamento.turno_id == Turno.id
        ).group_by(Maquina.numero_maquina).all()
    )
    numeros_maquina = sorted(
        set(producao_horario_por_maquina) | set(producao_lancamento_por_maquina)
    )
    producao_por_maquina = [
        (
            numero,
            (producao_horario_por_maquina.get(numero) or 0)
            + (producao_lancamento_por_maquina.get(numero) or 0),
        )
        for numero in numeros_maquina
    ]

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
            "labels": [f"Injetora {numero}" for numero, _ in producao_por_maquina],
            "valores": [total or 0 for _, total in producao_por_maquina]
        },
        "producao_por_turno": _montar_producao_por_turno(db),
        "comparativo_ordens_producao": _montar_comparativo_ordens_producao(db),
        "insight_ml": insight_ia
    }