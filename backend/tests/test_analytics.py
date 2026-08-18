from datetime import time

from app.models.maquina import Maquina
from app.models.produto import Produto
from app.models.registro_turno import RegistroHorario
from app.models.turno import Turno
from app.services.analytics import calcular_kpis_turno, calcular_kpis_varios_turnos


def _criar_turno_com_registro(db_session, *, nome: str, prod_executada: int) -> Turno:
    maquina = Maquina(
        numero_maquina=f"maq-{nome}",
        descricao="Máquina de teste",
        cavidades=2,
        ciclo_padrao=10.0,
        ativo=True,
    )
    db_session.add(maquina)
    db_session.flush()

    turno = Turno(
        nome_turno=nome,
        responsavel_nome="Responsável Teste",
        status_assinatura="ASSINADO_DIGITALMENTE",
    )
    db_session.add(turno)
    db_session.flush()

    registro = RegistroHorario(
        turno_id=turno.id,
        maquina_id=maquina.id,
        hora_referencia=time(8, 0),
        prod_executada=prod_executada,
        pecas_boas=prod_executada,
        refugo=0,
    )
    db_session.add(registro)
    db_session.commit()
    return turno


def test_calcular_kpis_varios_turnos_bate_com_calculo_individual(db_session):
    turno_a = _criar_turno_com_registro(db_session, nome="A", prod_executada=500)
    turno_b = _criar_turno_com_registro(db_session, nome="B", prod_executada=300)

    individual_a = calcular_kpis_turno(db_session, turno_a.id)
    individual_b = calcular_kpis_turno(db_session, turno_b.id)

    em_lote = calcular_kpis_varios_turnos(db_session, [turno_a.id, turno_b.id])

    assert em_lote[turno_a.id] == individual_a
    assert em_lote[turno_b.id] == individual_b


def test_calcular_kpis_varios_turnos_lista_vazia(db_session):
    assert calcular_kpis_varios_turnos(db_session, []) == {}


def test_calcular_kpis_varios_turnos_turno_sem_registros(db_session):
    turno = Turno(
        nome_turno="Sem registros",
        responsavel_nome="Responsável Teste",
        status_assinatura="ASSINADO_DIGITALMENTE",
    )
    db_session.add(turno)
    db_session.commit()

    resultado = calcular_kpis_varios_turnos(db_session, [turno.id])
    assert resultado[turno.id]["total_produzido"] == 0
    assert resultado[turno.id]["eficiencia_oee"] == 0.0


def _criar_maquina(db_session, *, nome: str, ciclo_padrao=10.0, cavidades=2) -> Maquina:
    maquina = Maquina(
        numero_maquina=f"maq-{nome}",
        descricao="Máquina de teste",
        cavidades=cavidades,
        ciclo_padrao=ciclo_padrao,
        ativo=True,
    )
    db_session.add(maquina)
    db_session.flush()
    return maquina


def _criar_turno_vazio(db_session, *, nome: str) -> Turno:
    turno = Turno(
        nome_turno=nome,
        responsavel_nome="Responsável Teste",
        status_assinatura="ASSINADO_DIGITALMENTE",
    )
    db_session.add(turno)
    db_session.flush()
    return turno


def test_parada_programada_nao_penaliza_oee(db_session):
    # Máquina: ciclo 10s, 2 cavidades -> capacidade cheia = 720 pçs/hora.
    maquina = _criar_maquina(db_session, nome="prog")
    turno = _criar_turno_vazio(db_session, nome="Parada programada")

    # 30 min de parada programada -> só 50% da hora disponível ->
    # capacidade esperada ajustada = 360. Produzindo exatamente 360,
    # o índice de produção deve ser 100% (a parada não penaliza).
    registro = RegistroHorario(
        turno_id=turno.id,
        maquina_id=maquina.id,
        hora_referencia=time(8, 0),
        prod_executada=360,
        inicio_parada=time(8, 0),
        retomada=time(8, 30),
        parada_programada=True,
    )
    db_session.add(registro)
    db_session.commit()

    kpis = calcular_kpis_turno(db_session, turno.id)
    assert kpis["total_esperado"] == 360
    assert kpis["indice_producao"] == 100.0
    assert kpis["minutos_parados_programados"] == 30
    assert kpis["minutos_parados_nao_programados"] == 0


def test_parada_nao_programada_penaliza_oee(db_session):
    # Mesmo cenário do teste acima, mas SEM marcar como programada: a
    # capacidade esperada continua cheia (720), então produzir só 360
    # deve reduzir o índice de produção pela metade.
    maquina = _criar_maquina(db_session, nome="naoprog")
    turno = _criar_turno_vazio(db_session, nome="Parada não programada")

    registro = RegistroHorario(
        turno_id=turno.id,
        maquina_id=maquina.id,
        hora_referencia=time(8, 0),
        prod_executada=360,
        inicio_parada=time(8, 0),
        retomada=time(8, 30),
        parada_programada=False,
    )
    db_session.add(registro)
    db_session.commit()

    kpis = calcular_kpis_turno(db_session, turno.id)
    assert kpis["total_esperado"] == 720
    assert kpis["indice_producao"] == 50.0
    assert kpis["minutos_parados_programados"] == 0
    assert kpis["minutos_parados_nao_programados"] == 30


def test_ciclo_da_peca_prevalece_sobre_ciclo_da_maquina(db_session):
    # Máquina com ciclo 10s (capacidade base 720/h), mas a peça
    # selecionada tem ciclo próprio de 5s -> capacidade esperada deve
    # usar o ciclo da peça (1440/h), não o da máquina.
    maquina = _criar_maquina(db_session, nome="peca")
    peca = Produto(codigo="PX", descricao="Peça de teste", ciclo_padrao=5.0)
    db_session.add(peca)
    db_session.flush()

    turno = _criar_turno_vazio(db_session, nome="Com peça")
    registro = RegistroHorario(
        turno_id=turno.id,
        maquina_id=maquina.id,
        produto_id=peca.id,
        hora_referencia=time(8, 0),
        prod_executada=1440,
    )
    db_session.add(registro)
    db_session.commit()

    kpis = calcular_kpis_turno(db_session, turno.id)
    assert kpis["total_esperado"] == 1440
    assert kpis["indice_producao"] == 100.0
