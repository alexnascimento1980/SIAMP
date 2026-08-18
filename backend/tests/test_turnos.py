from app.models.maquina import Maquina
from app.models.produto import Produto


def _login(client, usuario_teste):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario_teste.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 200


def _criar_maquina_e_peca(db_session):
    maquina = Maquina(
        numero_maquina="1",
        descricao="Injetora de teste",
        cavidades=2,
        ciclo_padrao=10.0,
        ativo=True,
    )
    peca = Produto(codigo="PX", descricao="Peça de teste", ciclo_padrao=5.0)
    db_session.add_all([maquina, peca])
    db_session.commit()
    db_session.refresh(maquina)
    db_session.refresh(peca)
    return maquina, peca


def test_fechamento_com_peca_e_parada_programada(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)

    payload = {
        "nome_turno": "1º Turno (05:00 - 13:00)",
        "responsavel_nome": "Líder Teste",
        "registros": [
            {
                "numero_maquina": maquina.numero_maquina,
                "hora_referencia": "05:00",
                "prod_executada": 1440,
                "produto_id": peca.id,
            },
            {
                "numero_maquina": maquina.numero_maquina,
                "hora_referencia": "06:00",
                "prod_executada": 720,
                "produto_id": peca.id,
                "inicio_parada": "06:00:00",
                "retomada": "06:30:00",
                "parada_programada": True,
                "motivo_parada": "Troca de molde",
            },
        ],
    }

    res = client.post("/api/v1/turnos/fechamento", json=payload)
    assert res.status_code == 201, res.text
    corpo = res.json()
    turno_id = corpo["turno_id"]

    # 05:00 -> capacidade cheia da peça (ciclo 5s, 2 cavidades) = 1440.
    # 06:00 -> 30 min de parada programada -> capacidade ajustada = 720.
    # total_esperado = 1440 + 720 = 2160; produzido = 1440 + 720 = 2160.
    assert corpo["kpis"]["total_esperado"] == 2160
    assert corpo["kpis"]["eficiencia_oee"] == 100.0
    assert corpo["kpis"]["minutos_parados_programados"] == 30
    assert corpo["kpis"]["minutos_parados_nao_programados"] == 0

    detalhe = client.get(f"/api/v1/turnos/{turno_id}").json()
    reg_com_parada = next(
        r for r in detalhe["registros"] if r["hora_referencia"] == "06:00"
    )
    assert reg_com_parada["produto_codigo"] == "PX"
    assert reg_com_parada["produto_descricao"] == "Peça de teste"
    assert reg_com_parada["parada_programada"] is True

    pdf_res = client.get(f"/api/v1/turnos/{turno_id}/relatorio.pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content[:4] == b"%PDF"


def test_parada_programada_sem_inicio_e_rejeitada(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, _peca = _criar_maquina_e_peca(db_session)

    payload = {
        "nome_turno": "1º Turno (05:00 - 13:00)",
        "responsavel_nome": "Líder Teste",
        "registros": [
            {
                "numero_maquina": maquina.numero_maquina,
                "hora_referencia": "05:00",
                "prod_executada": 100,
                "parada_programada": True,
            },
        ],
    }

    res = client.post("/api/v1/turnos/fechamento", json=payload)
    assert res.status_code == 422


def test_fechamento_com_produto_id_inexistente_e_rejeitado(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, _peca = _criar_maquina_e_peca(db_session)

    payload = {
        "nome_turno": "1º Turno (05:00 - 13:00)",
        "responsavel_nome": "Líder Teste",
        "registros": [
            {
                "numero_maquina": maquina.numero_maquina,
                "hora_referencia": "05:00",
                "prod_executada": 100,
                "produto_id": 99999,
            },
        ],
    }

    res = client.post("/api/v1/turnos/fechamento", json=payload)
    assert res.status_code == 400
    assert "não encontrada" in res.json()["detail"].lower()


def test_producao_esperada_por_linha_no_relatorio(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)

    payload = {
        "nome_turno": "1º Turno (05:00 - 13:00)",
        "responsavel_nome": "Líder Teste",
        "registros": [
            {
                "numero_maquina": maquina.numero_maquina,
                "hora_referencia": "05:00",
                "prod_executada": 1000,
                "produto_id": peca.id,
            },
            {
                "numero_maquina": maquina.numero_maquina,
                "hora_referencia": "06:00",
                "prod_executada": 200,
                "produto_id": peca.id,
                "inicio_parada": "06:00:00",
                "retomada": "06:30:00",
                "parada_programada": True,
            },
        ],
    }

    res = client.post("/api/v1/turnos/fechamento", json=payload)
    assert res.status_code == 201, res.text
    turno_id = res.json()["turno_id"]

    from app.services.turno_service import buscar_registros_para_relatorio

    registros = buscar_registros_para_relatorio(db_session, turno_id)
    por_hora = {r["hora_referencia"]: r for r in registros}

    # Peça com ciclo 5s / 2 cavidades -> capacidade cheia = 1440/h.
    assert por_hora["05:00"]["producao_esperada"] == 1440
    # 30 min de parada programada -> metade da capacidade = 720.
    assert por_hora["06:00"]["producao_esperada"] == 720
