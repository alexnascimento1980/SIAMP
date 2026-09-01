from datetime import timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.timezone import agora_brasilia
from app.models.lancamento import Lancamento
from app.models.maquina import Maquina
from app.models.registro_turno import RegistroHorario
from app.models.turno import Turno
from app.services.analytics import calcular_kpis_varios_turnos_generico
from app.services.turno_service import STATUS_ASSINADO

# Quantos turnos mais recentes aparecem no gráfico "Produção por
# Turno" (dashboard e PDF de fechamento) - limite para não sobrecarregar
# com um histórico muito longo.
LIMITE_TURNOS_GRAFICO = 10

# Períodos aceitos pelo dashboard e pelo PDF de fechamento de turno -
# "turno" não filtra por data (é tratado à parte, pelos KPIs do
# próprio turno sendo fechado); os demais recortam Turno.data_registro
# a partir de "agora" (fuso de Brasília) para trás.
PERIODOS_VALIDOS = {"diario", "semanal", "mensal", "total"}


def calcular_intervalo_periodo(periodo: str):
    """Retorna (data_inicio, data_fim) para o período pedido, ou
    (None, None) para 'total' (sem filtro - todo o histórico)."""
    agora = agora_brasilia()
    if periodo == "diario":
        inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "semanal":
        inicio = agora - timedelta(days=7)
    elif periodo == "mensal":
        inicio = agora - timedelta(days=30)
    else:
        return None, None
    return inicio, agora


def calcular_metricas_acumuladas(db: Session, periodo: str = "total") -> dict:
    """Métricas acumuladas (total produzido, OEE médio, produção por
    injetora), com filtro de período opcional. Só turnos fechados
    (ASSINADO_DIGITALMENTE) entram - um rascunho em andamento não deve
    inflar/distorcer os agregados até ser efetivamente encerrado.
    Turnos marcados como teste (marcado_teste) também são excluídos -
    ver endpoint PATCH /turnos/marcar-teste. Soma os dois modelos de
    apontamento (HORARIO e LANCAMENTO).
    """
    data_inicio, data_fim = calcular_intervalo_periodo(periodo)

    query_turnos = db.query(Turno).filter(
        Turno.status_assinatura == STATUS_ASSINADO,
        Turno.marcado_teste.is_(False),
    )
    if data_inicio:
        query_turnos = query_turnos.filter(Turno.data_registro >= data_inicio)
    if data_fim:
        query_turnos = query_turnos.filter(Turno.data_registro <= data_fim)
    turnos_do_periodo = query_turnos.all()
    ids_turnos = [t.id for t in turnos_do_periodo]

    total_turnos = len(turnos_do_periodo)

    if not ids_turnos:
        return {
            "periodo": periodo,
            "total_turnos_encerrados": 0,
            "total_pecas_produzidas": 0,
            "oee_medio_estimado": 0.0,
            "producao_por_maquina": [],
        }

    total_pecas_horario = (
        db.query(func.sum(RegistroHorario.prod_executada))
        .filter(RegistroHorario.turno_id.in_(ids_turnos))
        .scalar()
        or 0
    )
    total_pecas_lancamento = (
        db.query(func.sum(Lancamento.quantidade))
        .filter(Lancamento.turno_id.in_(ids_turnos))
        .filter(Lancamento.tipo == "PRODUCAO")
        .scalar()
        or 0
    )
    total_pecas = total_pecas_horario + total_pecas_lancamento

    kpis_por_turno = calcular_kpis_varios_turnos_generico(db, turnos_do_periodo)
    oee_medio_estimado = (
        round(sum(k["eficiencia_oee"] for k in kpis_por_turno.values()) / len(kpis_por_turno), 2)
        if kpis_por_turno
        else 0.0
    )

    # CASE WHEN dentro do SUM (não um filtro na condição do JOIN) é
    # necessário para preservar máquinas sem nenhuma produção no
    # período na lista (LEFT JOIN), zerando só a soma, sem sumir a
    # linha da máquina.
    producao_horario_por_maquina = dict(
        db.query(
            Maquina.numero_maquina,
            func.sum(
                case((RegistroHorario.turno_id.in_(ids_turnos), RegistroHorario.prod_executada), else_=0)
            ),
        )
        .outerjoin(RegistroHorario, Maquina.id == RegistroHorario.maquina_id)
        .group_by(Maquina.numero_maquina)
        .all()
    )
    producao_lancamento_por_maquina = dict(
        db.query(
            Maquina.numero_maquina,
            func.sum(
                case(
                    (
                        Lancamento.turno_id.in_(ids_turnos) & (Lancamento.tipo == "PRODUCAO"),
                        Lancamento.quantidade,
                    ),
                    else_=0,
                )
            ),
        )
        .outerjoin(Lancamento, Maquina.id == Lancamento.maquina_id)
        .group_by(Maquina.numero_maquina)
        .all()
    )
    numeros_maquina = sorted(set(producao_horario_por_maquina) | set(producao_lancamento_por_maquina))
    producao_por_maquina = [
        {
            "numero_maquina": numero,
            "total_produzido": (producao_horario_por_maquina.get(numero) or 0)
            + (producao_lancamento_por_maquina.get(numero) or 0),
        }
        for numero in numeros_maquina
    ]

    return {
        "periodo": periodo,
        "total_turnos_encerrados": total_turnos,
        "total_pecas_produzidas": total_pecas,
        "oee_medio_estimado": oee_medio_estimado,
        "producao_por_maquina": producao_por_maquina,
    }


def montar_producao_por_turno(db: Session) -> dict:
    """Produção e OEE dos turnos mais recentes, em ordem cronológica
    (mais antigo primeiro) - para o gráfico de tendência (dashboard e
    PDF de fechamento de turno). Só turnos fechados
    (ASSINADO_DIGITALMENTE) entram aqui - rascunhos em andamento não
    devem aparecer como se já fossem dado consolidado. Turnos marcados
    como teste também são excluídos. Cobre os dois modelos de
    apontamento (HORARIO e LANCAMENTO)."""
    ultimos_turnos = (
        db.query(Turno)
        .filter(Turno.status_assinatura == STATUS_ASSINADO, Turno.marcado_teste.is_(False))
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
