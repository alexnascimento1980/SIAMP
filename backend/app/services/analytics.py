from sqlalchemy.orm import Session
from app.models.lancamento import Lancamento, TIPO_PARADA_PROGRAMADA, TIPO_PARADA_FALHA, TIPO_PRODUCAO
from app.models.maquina import Maquina
from app.models.produto import Produto
from app.models.registro_turno import RegistroHorario


def calcular_capacidade_esperada_registro(
    reg: RegistroHorario, maq: Maquina, produto: Produto | None
) -> dict:
    """Capacidade teórica esperada de UM registro (hora/máquina), já
    descontando parada programada. Extraída para ser reutilizada tanto no
    agregado de KPIs do turno (_kpis_a_partir_de_registros) quanto no
    detalhamento por linha do relatório em PDF (ver
    turno_service.buscar_registros_para_relatorio), evitando duas
    implementações divergentes da mesma conta."""
    # O ciclo e as cavidades da peça (quando cadastrados) prevalecem
    # sobre os "padrão" da máquina: a mesma injetora pode trocar de
    # molde entre turnos, então usar sempre o ciclo fixo da máquina
    # distorceria a capacidade teórica de peças com ciclo diferente.
    ciclo = maq.ciclo_padrao
    cavidades = maq.cavidades
    if produto is not None:
        if produto.ciclo_padrao:
            ciclo = produto.ciclo_padrao
        if produto.cavidades:
            cavidades = produto.cavidades

    # Ciclo informado manualmente pelo operador (campo editável no
    # apontamento) tem prioridade máxima - usado quando o ciclo
    # cadastrado (peça/máquina) não reflete a regulagem real do molde
    # naquele momento, ou quando nenhum dos dois está cadastrado ainda.
    if reg.ciclo_informado:
        ciclo = reg.ciclo_informado

    # Cálculo de produção nominal esperada (3600s / ciclo * cavidades por hora cheia).
    # Guarda contra ciclo/cavidades ausentes (ex.: máquina e peça sem
    # nenhum dos dois cadastrados) - resulta em capacidade zero em vez
    # de erro.
    capacidade_hora_cheia = int((3600 / ciclo) * cavidades) if ciclo and cavidades else 0

    duracao_parada_min = 0
    if reg.inicio_parada and reg.retomada:
        t_inicio = reg.inicio_parada.hour * 60 + reg.inicio_parada.minute
        t_fim = reg.retomada.hour * 60 + reg.retomada.minute
        duracao_parada_min = max(0, t_fim - t_inicio)

    if duracao_parada_min > 0 and reg.parada_programada:
        # Parada programada (troca de molde, manutenção preventiva,
        # refeição etc.): reduz a capacidade esperada na proporção do
        # tempo parado, para que ela não penalize o OEE. Uma hora
        # inteira de parada programada não conta contra a eficiência.
        fracao_disponivel = max(0.0, (60 - duracao_parada_min) / 60)
        capacidade_ajustada = capacidade_hora_cheia * fracao_disponivel
    else:
        capacidade_ajustada = capacidade_hora_cheia

    return {
        "capacidade_ajustada": capacidade_ajustada,
        "duracao_parada_min": duracao_parada_min,
    }


def _kpis_a_partir_de_registros(
    registros: list[tuple[RegistroHorario, Maquina, Produto | None]],
) -> dict:
    """Lógica pura de cálculo de KPI a partir de uma lista já carregada de
    (registro, máquina, peça). Extraída de calcular_kpis_turno para ser
    reutilizada tanto no cálculo de um único turno quanto no de vários de
    uma vez (ver calcular_kpis_varios_turnos), evitando N+1 queries no
    histórico."""
    total_produzido = 0
    total_esperado = 0.0
    minutos_parados = 0
    minutos_parados_programados = 0
    minutos_parados_nao_programados = 0
    total_pecas_boas = 0
    total_refugo = 0
    houve_apontamento_qualidade = False

    for reg, maq, produto in registros:
        total_produzido += reg.prod_executada

        capacidade = calcular_capacidade_esperada_registro(reg, maq, produto)
        total_esperado += capacidade["capacidade_ajustada"]

        duracao_parada_min = capacidade["duracao_parada_min"]
        minutos_parados += duracao_parada_min
        if duracao_parada_min > 0:
            if reg.parada_programada:
                minutos_parados_programados += duracao_parada_min
            else:
                minutos_parados_nao_programados += duracao_parada_min

        # pecas_boas/refugo são opcionais (retrocompatibilidade com registros
        # antigos, que não apontavam qualidade). Só entram no cálculo do
        # índice de qualidade quando pelo menos um registro do turno os
        # informa.
        if reg.pecas_boas is not None or reg.refugo is not None:
            houve_apontamento_qualidade = True
            total_pecas_boas += reg.pecas_boas or 0
            total_refugo += reg.refugo or 0

    total_esperado = round(total_esperado)

    # Índice de Produção combina Disponibilidade e Performance: quanto do
    # volume teoricamente possível (já descontando paradas programadas) foi
    # de fato produzido.
    indice_producao = (total_produzido / total_esperado) if total_esperado > 0 else 0.0

    # Índice de Qualidade: proporção de peças boas sobre o total inspecionado
    # (boas + refugo). Sem apontamento de qualidade no turno, assume-se 100%
    # para não penalizar turnos que ainda não usam esse campo.
    if houve_apontamento_qualidade and (total_pecas_boas + total_refugo) > 0:
        indice_qualidade = total_pecas_boas / (total_pecas_boas + total_refugo)
    else:
        indice_qualidade = 1.0

    eficiencia_oee = round(indice_producao * indice_qualidade * 100, 2)

    return {
        "total_produzido": total_produzido,
        "total_esperado": total_esperado,
        "minutos_parados": minutos_parados,
        "minutos_parados_programados": minutos_parados_programados,
        "minutos_parados_nao_programados": minutos_parados_nao_programados,
        "total_pecas_boas": total_pecas_boas,
        "total_refugo": total_refugo,
        "indice_producao": round(indice_producao * 100, 2),
        "indice_qualidade": round(indice_qualidade * 100, 2),
        "eficiencia_oee": eficiencia_oee,
        "alerta_ia": "Abaixo da meta esperada" if eficiencia_oee < 75.0 else "Operação normal"
    }


def calcular_kpis_turno(db: Session, turno_id: int) -> dict:
    registros = db.query(RegistroHorario, Maquina, Produto).\
        join(Maquina, RegistroHorario.maquina_id == Maquina.id).\
        outerjoin(Produto, RegistroHorario.produto_id == Produto.id).\
        filter(RegistroHorario.turno_id == turno_id).all()

    return _kpis_a_partir_de_registros(registros)


def calcular_kpis_varios_turnos(db: Session, turno_ids: list[int]) -> dict[int, dict]:
    """Calcula os KPIs de vários turnos em uma única query (em vez de uma
    query por turno), usado no histórico (GET /turnos/) para evitar N+1.
    Turnos sem nenhum registro entram no resultado com KPIs zerados."""
    kpis_por_turno = {
        turno_id: _kpis_a_partir_de_registros([]) for turno_id in turno_ids
    }

    if not turno_ids:
        return kpis_por_turno

    registros = (
        db.query(RegistroHorario, Maquina, Produto)
        .join(Maquina, RegistroHorario.maquina_id == Maquina.id)
        .outerjoin(Produto, RegistroHorario.produto_id == Produto.id)
        .filter(RegistroHorario.turno_id.in_(turno_ids))
        .all()
    )

    registros_por_turno: dict[int, list] = {turno_id: [] for turno_id in turno_ids}
    for reg, maq, produto in registros:
        registros_por_turno[reg.turno_id].append((reg, maq, produto))

    for turno_id, regs in registros_por_turno.items():
        kpis_por_turno[turno_id] = _kpis_a_partir_de_registros(regs)

    return kpis_por_turno


# ======================================================================
# Modelo novo: lançamentos livres (produção/parada com início-fim
# variável), em paralelo ao modelo por hora acima. Ver
# Turno.modelo_apontamento - turnos antigos continuam usando as
# funções acima; turnos criados com o modelo novo usam estas.
# ======================================================================


def _resolver_ciclo_cavidades(maq: Maquina, produto: Produto | None) -> tuple[float | None, int | None]:
    """Mesma prioridade já usada no modelo por hora: ciclo/cavidades da
    peça (quando cadastrados) prevalecem sobre os padrão da máquina."""
    ciclo = maq.ciclo_padrao
    cavidades = maq.cavidades
    if produto is not None:
        if produto.ciclo_padrao:
            ciclo = produto.ciclo_padrao
        if produto.cavidades:
            cavidades = produto.cavidades
    return ciclo, cavidades


def _duracao_segundos(lanc: Lancamento) -> int:
    """Duração do lançamento em segundos. Quando horario_fim é menor ou
    igual a horario_inicio, interpreta como atravessando a meia-noite
    (ex.: 3º turno, 22:00 até 05:00 do dia seguinte) e soma 24h ao
    horário final - em vez de rejeitar ou dar duração negativa."""
    inicio = lanc.horario_inicio.hour * 3600 + lanc.horario_inicio.minute * 60 + lanc.horario_inicio.second
    fim = lanc.horario_fim.hour * 3600 + lanc.horario_fim.minute * 60 + lanc.horario_fim.second
    if fim <= inicio:
        fim += 24 * 3600
    return fim - inicio


def calcular_capacidade_esperada_lancamento(
    lanc: Lancamento, maq: Maquina, produto: Produto | None
) -> int:
    """Capacidade teórica esperada de UM lançamento de produção, com
    base na duração real do intervalo (não mais numa hora cheia fixa).
    Só se aplica a lançamentos do tipo PRODUCAO - paradas não têm
    'esperado' (o tempo delas simplesmente não conta como capacidade
    disponível, em vez de contar e depois ser proporcionalmente
    descontado como no modelo por hora)."""
    if lanc.tipo != TIPO_PRODUCAO:
        return 0

    ciclo, cavidades = _resolver_ciclo_cavidades(maq, produto)
    if not ciclo or not cavidades:
        return 0

    duracao_s = _duracao_segundos(lanc)
    return int((duracao_s / ciclo) * cavidades)


def _kpis_a_partir_de_lancamentos(
    lancamentos: list[tuple[Lancamento, Maquina, Produto | None]],
) -> dict:
    """Mesmo formato de saída de _kpis_a_partir_de_registros, calculado
    a partir de lançamentos livres em vez de registros por hora."""
    total_produzido = 0
    total_esperado = 0

    minutos_parados_programados = 0
    minutos_parados_nao_programados = 0

    for lanc, maq, produto in lancamentos:
        if lanc.tipo == TIPO_PRODUCAO:
            total_produzido += lanc.quantidade or 0
            total_esperado += calcular_capacidade_esperada_lancamento(lanc, maq, produto)
        else:
            duracao_min = round(_duracao_segundos(lanc) / 60)
            if lanc.tipo == TIPO_PARADA_PROGRAMADA:
                minutos_parados_programados += duracao_min
            elif lanc.tipo == TIPO_PARADA_FALHA:
                minutos_parados_nao_programados += duracao_min

    minutos_parados = minutos_parados_programados + minutos_parados_nao_programados
    indice_producao = (total_produzido / total_esperado) if total_esperado > 0 else 0.0
    # O modelo de lançamento não tem apontamento de peças boas/refugo -
    # qualidade sempre 100% (mesmo fallback do modelo por hora quando
    # não há apontamento de qualidade).
    indice_qualidade = 1.0
    eficiencia_oee = round(indice_producao * indice_qualidade * 100, 2)

    return {
        "total_produzido": total_produzido,
        "total_esperado": total_esperado,
        "minutos_parados": minutos_parados,
        "minutos_parados_programados": minutos_parados_programados,
        "minutos_parados_nao_programados": minutos_parados_nao_programados,
        "total_pecas_boas": 0,
        "total_refugo": 0,
        "indice_producao": round(indice_producao * 100, 2),
        "indice_qualidade": round(indice_qualidade * 100, 2),
        "eficiencia_oee": eficiencia_oee,
        "alerta_ia": "Abaixo da meta esperada" if eficiencia_oee < 75.0 else "Operação normal",
    }


def calcular_kpis_turno_lancamento(db: Session, turno_id: int) -> dict:
    lancamentos = (
        db.query(Lancamento, Maquina, Produto)
        .join(Maquina, Lancamento.maquina_id == Maquina.id)
        .outerjoin(Produto, Lancamento.produto_id == Produto.id)
        .filter(Lancamento.turno_id == turno_id)
        .all()
    )
    return _kpis_a_partir_de_lancamentos(lancamentos)


def calcular_kpis_turno_qualquer_modelo(db: Session, turno) -> dict:
    """Despacha para o cálculo certo conforme Turno.modelo_apontamento -
    'turno' já precisa estar carregado (evita uma query extra só para
    ler o campo)."""
    if turno.modelo_apontamento == "LANCAMENTO":
        return calcular_kpis_turno_lancamento(db, turno.id)
    return calcular_kpis_turno(db, turno.id)


def calcular_kpis_varios_turnos_generico(db: Session, turnos: list) -> dict[int, dict]:
    """Mesma ideia de calcular_kpis_varios_turnos (uma query em lote, não
    uma por turno), mas cobrindo os dois modelos de apontamento
    misturados na mesma lista - usado no histórico (GET /turnos/), que
    lista turnos antigos e novos juntos."""
    ids_horario = [t.id for t in turnos if t.modelo_apontamento != "LANCAMENTO"]
    ids_lancamento = [t.id for t in turnos if t.modelo_apontamento == "LANCAMENTO"]

    resultado = calcular_kpis_varios_turnos(db, ids_horario)

    kpis_lancamento = {
        turno_id: _kpis_a_partir_de_lancamentos([]) for turno_id in ids_lancamento
    }
    if ids_lancamento:
        lancamentos = (
            db.query(Lancamento, Maquina, Produto)
            .join(Maquina, Lancamento.maquina_id == Maquina.id)
            .outerjoin(Produto, Lancamento.produto_id == Produto.id)
            .filter(Lancamento.turno_id.in_(ids_lancamento))
            .all()
        )
        lancamentos_por_turno: dict[int, list] = {turno_id: [] for turno_id in ids_lancamento}
        for lanc, maq, produto in lancamentos:
            lancamentos_por_turno[lanc.turno_id].append((lanc, maq, produto))
        for turno_id, lancs in lancamentos_por_turno.items():
            kpis_lancamento[turno_id] = _kpis_a_partir_de_lancamentos(lancs)

    resultado.update(kpis_lancamento)
    return resultado