from datetime import date, datetime, time, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.timezone import agora_brasilia
from app.models.lancamento import Lancamento
from app.models.maquina import Maquina
from app.models.ordem_producao import OrdemProducao
from app.models.produto import Produto
from app.models.registro_turno import RegistroHorario
from app.models.turno import Turno
from app.services.analytics import calcular_kpis_varios_turnos_generico
from app.services.ml_engine import prever_risco_parada
from app.services.turno_service import STATUS_ASSINADO

# Quantas Ordens de Produção mais recentes aparecem no comparativo do
# dashboard - limite para não sobrecarregar a tela com um histórico
# muito longo.
LIMITE_ORDENS_COMPARATIVO = 8

# Quantos turnos mais recentes aparecem no gráfico "Produção por
# Turno" (dashboard e PDF de fechamento) - limite para não sobrecarregar
# com um histórico muito longo.
LIMITE_TURNOS_GRAFICO = 10

# Períodos aceitos pelo dashboard e pelo PDF de fechamento de turno -
# "turno" não filtra por data (é tratado à parte, pelos KPIs do
# próprio turno sendo fechado); os demais recortam Turno.data_registro
# a partir de "agora" (fuso de Brasília) para trás.
PERIODOS_VALIDOS = {"diario", "semanal", "mensal", "total", "personalizado"}


def calcular_intervalo_periodo(
    periodo: str,
    data_inicio_custom: date | None = None,
    data_fim_custom: date | None = None,
):
    """Retorna (data_inicio, data_fim) para o período pedido, ou
    (None, None) para 'total' (sem filtro - todo o histórico).

    'personalizado' usa as datas informadas por quem chama (tela de
    Dashboard - filtro de intervalo específico), em vez de calcular a
    partir de "agora" como os demais períodos - data_fim_custom é
    tratado como o FIM daquele dia (23:59:59), não o instante exato
    informado, para incluir turnos fechados em qualquer horário
    daquele último dia (mesmo padrão intuitivo de "até tal data,
    incluindo ela inteira")."""
    agora = agora_brasilia()
    if periodo == "diario":
        inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "semanal":
        inicio = agora - timedelta(days=7)
    elif periodo == "mensal":
        inicio = agora - timedelta(days=30)
    elif periodo == "personalizado":
        if data_inicio_custom is None or data_fim_custom is None:
            return None, None
        inicio = datetime.combine(data_inicio_custom, time.min)
        fim = datetime.combine(data_fim_custom, time.max)
        return inicio, fim
    else:
        return None, None
    return inicio, agora


def calcular_metricas_acumuladas(
    db: Session,
    periodo: str = "total",
    data_inicio_custom: date | None = None,
    data_fim_custom: date | None = None,
) -> dict:
    """Métricas acumuladas (total produzido, OEE médio, produção por
    injetora), com filtro de período opcional. Só turnos fechados
    (ASSINADO_DIGITALMENTE) entram - um rascunho em andamento não deve
    inflar/distorcer os agregados até ser efetivamente encerrado.
    Turnos marcados como teste (marcado_teste) também são excluídos -
    ver endpoint PATCH /turnos/marcar-teste. Soma os dois modelos de
    apontamento (HORARIO e LANCAMENTO).
    """
    data_inicio, data_fim = calcular_intervalo_periodo(periodo, data_inicio_custom, data_fim_custom)

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


def montar_comparativo_ordens_producao(db: Session) -> list[dict]:
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


def montar_diagnostico_ia(db: Session) -> dict:
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
