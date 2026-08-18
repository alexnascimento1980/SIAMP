from sqlalchemy.orm import Session
from app.models.maquina import Maquina
from app.models.produto import Produto
from app.models.registro_turno import RegistroHorario


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

        # Cálculo de produção nominal esperada (3600s / ciclo * cavidades por hora cheia)
        capacidade_hora = int((3600 / ciclo) * cavidades) if ciclo else 0

        duracao_parada_min = 0
        if reg.inicio_parada and reg.retomada:
            t_inicio = reg.inicio_parada.hour * 60 + reg.inicio_parada.minute
            t_fim = reg.retomada.hour * 60 + reg.retomada.minute
            duracao_parada_min = max(0, t_fim - t_inicio)

        minutos_parados += duracao_parada_min

        if duracao_parada_min > 0 and reg.parada_programada:
            # Parada programada (troca de molde, manutenção preventiva,
            # refeição etc.): reduz a capacidade esperada na proporção do
            # tempo parado, para que ela não penalize o OEE. Uma hora
            # inteira de parada programada não conta contra a eficiência.
            minutos_parados_programados += duracao_parada_min
            fracao_disponivel = max(0.0, (60 - duracao_parada_min) / 60)
            total_esperado += capacidade_hora * fracao_disponivel
        else:
            if duracao_parada_min > 0:
                minutos_parados_nao_programados += duracao_parada_min
            total_esperado += capacidade_hora

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