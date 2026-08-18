from datetime import time

from app.models.maquina import Maquina
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
