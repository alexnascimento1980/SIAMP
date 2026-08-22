from datetime import date, time

from app.core.security import gerar_hash_senha
from app.models.maquina import Maquina
from app.models.produto import Produto
from app.models.turno import Turno
from app.models.usuario import Usuario


def _login(client, usuario):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 200


def _criar_maquina_e_peca(db_session):
    maquina = Maquina(numero_maquina="1", descricao="Injetora 1", ativo=True)
    peca = Produto(codigo="PL1", descricao="Peça Lançamento", ciclo_padrao=10.0, cavidades=2)
    db_session.add_all([maquina, peca])
    db_session.commit()
    db_session.refresh(maquina)
    db_session.refresh(peca)
    return maquina, peca


def test_fechamento_com_lancamento_de_producao(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)

    payload = {
        "nome_turno": "1º Turno",
        "responsavel_nome": "Líder Teste",
        "lancamentos": [
            {
                "numero_maquina": maquina.numero_maquina,
                "tipo": "PRODUCAO",
                "horario_inicio": "05:00",
                "horario_fim": "07:30",
                "produto_id": peca.id,
                "quantidade": 500,
            }
        ],
    }
    res = client.post("/api/v1/turnos/lancamento", json=payload)
    assert res.status_code == 201, res.text
    dados = res.json()
    # 2h30 = 9000s / ciclo 10s * 2 cavidades = 1800 esperado
    assert dados["kpis"]["total_esperado"] == 1800
    assert dados["kpis"]["total_produzido"] == 500
    assert dados["status_assinatura"] == "ASSINADO_DIGITALMENTE"


def test_horario_fim_antes_do_inicio_e_rejeitado(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)

    payload = {
        "nome_turno": "1º Turno",
        "responsavel_nome": "Líder Teste",
        "lancamentos": [
            {
                "numero_maquina": maquina.numero_maquina,
                "tipo": "PRODUCAO",
                "horario_inicio": "07:00",
                "horario_fim": "05:00",
                "produto_id": peca.id,
                "quantidade": 100,
            }
        ],
    }
    res = client.post("/api/v1/turnos/lancamento", json=payload)
    assert res.status_code == 422


def test_producao_sem_quantidade_e_rejeitado(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)

    payload = {
        "nome_turno": "1º Turno",
        "responsavel_nome": "Líder Teste",
        "lancamentos": [
            {
                "numero_maquina": maquina.numero_maquina,
                "tipo": "PRODUCAO",
                "horario_inicio": "05:00",
                "horario_fim": "06:00",
                "produto_id": peca.id,
            }
        ],
    }
    res = client.post("/api/v1/turnos/lancamento", json=payload)
    assert res.status_code == 422


def test_fechamento_sem_nenhum_lancamento_e_rejeitado(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    res = client.post(
        "/api/v1/turnos/lancamento",
        json={"nome_turno": "1º Turno", "responsavel_nome": "Líder Teste", "lancamentos": []},
    )
    assert res.status_code == 422


def test_parada_programada_nao_conta_no_esperado_mas_falha_e_contabilizada(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)

    payload = {
        "nome_turno": "1º Turno",
        "responsavel_nome": "Líder Teste",
        "lancamentos": [
            {
                "numero_maquina": maquina.numero_maquina,
                "tipo": "PRODUCAO",
                "horario_inicio": "05:00",
                "horario_fim": "06:00",
                "produto_id": peca.id,
                "quantidade": 100,
            },
            {
                "numero_maquina": maquina.numero_maquina,
                "tipo": "PARADA_PROGRAMADA",
                "horario_inicio": "06:00",
                "horario_fim": "06:20",
                "motivo": "Troca de molde",
            },
            {
                "numero_maquina": maquina.numero_maquina,
                "tipo": "PARADA_FALHA",
                "horario_inicio": "06:20",
                "horario_fim": "06:35",
                "motivo": "Sensor travado",
            },
        ],
    }
    res = client.post("/api/v1/turnos/lancamento", json=payload)
    assert res.status_code == 201, res.text
    kpis = res.json()["kpis"]
    assert kpis["minutos_parados_programados"] == 20
    assert kpis["minutos_parados_nao_programados"] == 15
    assert kpis["minutos_parados"] == 35
    # 1h de produção = 3600/10*2 = 720 esperado; paradas não somam ao esperado
    assert kpis["total_esperado"] == 720


def test_rascunho_lancamento_criar_atualizar_fechar(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)

    res = client.post(
        "/api/v1/turnos/lancamento/rascunho",
        json={"nome_turno": "1º Turno", "responsavel_nome": "Líder Teste", "lancamentos": []},
    )
    assert res.status_code == 201, res.text
    turno_id = res.json()["turno_id"]
    assert res.json()["status_assinatura"] == "EM_ANDAMENTO"

    res = client.patch(
        f"/api/v1/turnos/lancamento/rascunho/{turno_id}",
        json={
            "nome_turno": "1º Turno",
            "responsavel_nome": "Líder Teste",
            "lancamentos": [
                {
                    "numero_maquina": maquina.numero_maquina,
                    "tipo": "PRODUCAO",
                    "horario_inicio": "05:00",
                    "horario_fim": "06:00",
                    "produto_id": peca.id,
                    "quantidade": 200,
                }
            ],
        },
    )
    assert res.status_code == 200, res.text

    detalhe = client.get(f"/api/v1/turnos/{turno_id}").json()
    assert detalhe["modelo_apontamento"] == "LANCAMENTO"
    assert len(detalhe["lancamentos"]) == 1
    assert detalhe["registros"] == []

    res = client.post(
        f"/api/v1/turnos/lancamento/{turno_id}/fechar",
        json={
            "nome_turno": "1º Turno (05:00 - 13:00)",
            "responsavel_nome": "Líder Teste",
            "lancamentos": [
                {
                    "numero_maquina": maquina.numero_maquina,
                    "tipo": "PRODUCAO",
                    "horario_inicio": "05:00",
                    "horario_fim": "06:00",
                    "produto_id": peca.id,
                    "quantidade": 200,
                }
            ],
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["status_assinatura"] == "ASSINADO_DIGITALMENTE"


def test_turnos_horario_e_lancamento_juntos_no_historico(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)

    # Turno modelo antigo (por hora)
    client.post(
        "/api/v1/turnos/fechamento",
        json={
            "nome_turno": "1º Turno",
            "responsavel_nome": "Líder Teste",
            "registros": [
                {"numero_maquina": maquina.numero_maquina, "hora_referencia": "05:00", "prod_executada": 50}
            ],
        },
    )
    # Turno modelo novo (lançamento)
    client.post(
        "/api/v1/turnos/lancamento",
        json={
            "nome_turno": "2º Turno",
            "responsavel_nome": "Líder Teste",
            "lancamentos": [
                {
                    "numero_maquina": maquina.numero_maquina,
                    "tipo": "PRODUCAO",
                    "horario_inicio": "13:00",
                    "horario_fim": "14:00",
                    "produto_id": peca.id,
                    "quantidade": 80,
                }
            ],
        },
    )

    res = client.get("/api/v1/turnos/")
    assert res.status_code == 200
    turnos = res.json()
    assert len(turnos) == 2
    modelos = {t["modelo_apontamento"] for t in turnos}
    assert modelos == {"HORARIO", "LANCAMENTO"}
    # Nenhum dos dois deve ter KPIs quebrados/zerados incorretamente.
    for t in turnos:
        assert t["total_produzido"] > 0


def test_pdf_de_turno_lancamento_gera_corretamente(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)

    turno_id = client.post(
        "/api/v1/turnos/lancamento",
        json={
            "nome_turno": "1º Turno",
            "responsavel_nome": "Líder Teste",
            "lancamentos": [
                {
                    "numero_maquina": maquina.numero_maquina,
                    "tipo": "PRODUCAO",
                    "horario_inicio": "05:00",
                    "horario_fim": "06:00",
                    "produto_id": peca.id,
                    "quantidade": 100,
                }
            ],
        },
    ).json()["turno_id"]

    res = client.get(f"/api/v1/turnos/{turno_id}/relatorio.pdf")
    assert res.status_code == 200
    assert res.content[:4] == b"%PDF"
