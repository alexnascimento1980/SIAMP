from datetime import date, time

from app.core.security import gerar_hash_senha
from app.models.maquina import Maquina
from app.models.ordem_producao import OrdemProducao
from app.models.produto import Produto
from app.models.registro_turno import RegistroHorario
from app.models.turno import Turno
from app.models.usuario import Usuario


def _login(client, usuario):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 200


def test_dashboard_sem_dados_nao_quebra(client, usuario_teste):
    _login(client, usuario_teste)
    res = client.get("/api/v1/dashboard/metricas-gerais")
    assert res.status_code == 200
    dados = res.json()
    assert dados["producao_por_turno"] == {"labels": [], "produzido": [], "oee": []}
    assert dados["comparativo_ordens_producao"] == []


def test_dashboard_producao_por_turno_reflete_turnos_reais(client, db_session, usuario_teste):
    maquina = Maquina(numero_maquina="1", descricao="Injetora", cavidades=2, ciclo_padrao=10.0)
    db_session.add(maquina)
    db_session.commit()
    db_session.refresh(maquina)

    _login(client, usuario_teste)
    client.post(
        "/api/v1/turnos/fechamento",
        json={
            "nome_turno": "1º Turno (05:00 - 13:00)",
            "responsavel_nome": "Teste",
            "registros": [
                {"numero_maquina": "1", "hora_referencia": "05:00", "prod_executada": 300},
            ],
        },
    )

    res = client.get("/api/v1/dashboard/metricas-gerais")
    assert res.status_code == 200
    grafico = res.json()["producao_por_turno"]
    assert len(grafico["labels"]) == 1
    assert grafico["produzido"] == [300]
    assert "1º Turno" in grafico["labels"][0]


def test_dashboard_comparativo_ordens_producao_soma_multiplas_maquinas(client, db_session, usuario_teste):
    maquina_a = Maquina(numero_maquina="1", descricao="Injetora A", cavidades=2, ciclo_padrao=10.0)
    maquina_b = Maquina(numero_maquina="2", descricao="Injetora B", cavidades=4, ciclo_padrao=8.0)
    produto = Produto(codigo="P1", descricao="Peça Teste")
    db_session.add_all([maquina_a, maquina_b, produto])
    db_session.commit()
    db_session.refresh(maquina_a)
    db_session.refresh(maquina_b)
    db_session.refresh(produto)

    ordem = OrdemProducao(
        numero_op="OP-DASH-1",
        periodo_inicio=date(2026, 8, 18),
        periodo_fim=date(2026, 8, 20),
        produto_id=produto.id,
        produto_descricao=produto.descricao,
        quantidade_a_produzir=1000,
    )
    db_session.add(ordem)
    db_session.commit()
    db_session.refresh(ordem)

    turno = Turno(
        nome_turno="1º Turno",
        responsavel_nome="Teste",
        status_assinatura="ASSINADO_DIGITALMENTE",
    )
    db_session.add(turno)
    db_session.flush()
    db_session.add(
        RegistroHorario(
            turno_id=turno.id,
            maquina_id=maquina_a.id,
            hora_referencia=time(8, 0),
            prod_executada=300,
            ordem_producao_id=ordem.id,
        )
    )
    db_session.add(
        RegistroHorario(
            turno_id=turno.id,
            maquina_id=maquina_b.id,
            hora_referencia=time(8, 0),
            prod_executada=200,
            ordem_producao_id=ordem.id,
        )
    )
    db_session.commit()

    _login(client, usuario_teste)
    res = client.get("/api/v1/dashboard/metricas-gerais")
    assert res.status_code == 200
    comparativo = res.json()["comparativo_ordens_producao"]
    assert len(comparativo) == 1
    assert comparativo[0]["numero_op"] == "OP-DASH-1"
    assert comparativo[0]["quantidade_produzida"] == 500
    assert comparativo[0]["percentual_atingido"] == 50.0


def test_dashboard_limita_a_8_ordens_de_producao(client, db_session, usuario_teste):
    produto = Produto(codigo="P1", descricao="Peça Teste")
    db_session.add(produto)
    db_session.commit()
    db_session.refresh(produto)

    for i in range(10):
        db_session.add(
            OrdemProducao(
                numero_op=f"OP-LIMITE-{i}",
                periodo_inicio=date(2026, 8, 1),
                periodo_fim=date(2026, 8, 2),
                produto_id=produto.id,
                quantidade_a_produzir=100,
            )
        )
    db_session.commit()

    _login(client, usuario_teste)
    res = client.get("/api/v1/dashboard/metricas-gerais")
    assert res.status_code == 200
    assert len(res.json()["comparativo_ordens_producao"]) == 8
