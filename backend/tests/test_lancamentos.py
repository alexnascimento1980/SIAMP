
from app.core.security import gerar_hash_senha
from app.models.maquina import Maquina
from app.models.produto import Produto
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


def test_horario_fim_igual_ao_inicio_e_rejeitado(client, db_session, usuario_teste):
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
                "horario_fim": "07:00",
                "produto_id": peca.id,
                "quantidade": 100,
            }
        ],
    }
    res = client.post("/api/v1/turnos/lancamento", json=payload)
    assert res.status_code == 422


def test_lancamento_atravessando_meia_noite_e_aceito(client, db_session, usuario_teste):
    # 3º turno: 22:00 até 05:00 do dia seguinte - não deve ser
    # rejeitado, e a duração deve ser calculada como 7h (não negativa).
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)

    payload = {
        "nome_turno": "3º Turno",
        "responsavel_nome": "Líder Teste",
        "lancamentos": [
            {
                "numero_maquina": maquina.numero_maquina,
                "tipo": "PRODUCAO",
                "horario_inicio": "22:00",
                "horario_fim": "05:00",
                "produto_id": peca.id,
                "quantidade": 700,
            }
        ],
    }
    res = client.post("/api/v1/turnos/lancamento", json=payload)
    assert res.status_code == 201, res.text
    # 7h = 25200s / ciclo 10s * 2 cavidades = 5040 esperado
    assert res.json()["kpis"]["total_esperado"] == 5040
    assert res.json()["kpis"]["total_produzido"] == 700


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
    assert res.headers["cache-control"] == "no-store"
    assert res.content[:4] == b"%PDF"


def test_pdf_inclui_observacoes_gerais_do_turno(client, db_session, usuario_teste):
    # Bug real reportado pelo usuário: o campo Observações Gerais era
    # digitado, salvo corretamente no banco, mas nunca aparecia no
    # PDF - o dicionário passado para o gerador de PDF simplesmente
    # não incluía esse campo. Não dá para checar o TEXTO dentro do
    # PDF facilmente (conteúdo comprimido/codificado no formato
    # binário), mas o tamanho do arquivo é um proxy razoável: com a
    # observação incluída, o PDF fica maior do que sem ela.
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)

    payload_base = {
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
    }

    turno_sem_obs_id = client.post(
        "/api/v1/turnos/lancamento", json=payload_base
    ).json()["turno_id"]
    tamanho_sem_obs = len(
        client.get(f"/api/v1/turnos/{turno_sem_obs_id}/relatorio.pdf").content
    )

    payload_com_obs = {
        **payload_base,
        "observacoes": "Troca de molde às 06:30 - parada de 15 minutos não registrada como falha.",
    }
    turno_com_obs_id = client.post(
        "/api/v1/turnos/lancamento", json=payload_com_obs
    ).json()["turno_id"]
    tamanho_com_obs = len(
        client.get(f"/api/v1/turnos/{turno_com_obs_id}/relatorio.pdf").content
    )

    assert tamanho_com_obs > tamanho_sem_obs


def test_pdf_com_observacoes_contendo_caracteres_especiais_nao_quebra(client, db_session, usuario_teste):
    # As Observações Gerais são texto livre digitado pelo operador -
    # sem escapar antes de inserir no componente de PDF (que
    # interpreta um mini-HTML), um caractere comum como "<" ou "&"
    # quebraria a geração do relatório inteiro, não só essa seção.
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)

    turno_id = client.post(
        "/api/v1/turnos/lancamento",
        json={
            "nome_turno": "1º Turno",
            "responsavel_nome": "Líder Teste",
            "observacoes": "Ciclo < 15s em alguns lotes & queda de energia às 08h.",
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


def test_pdf_inclui_observacoes_apos_fluxo_rascunho_editar_fechar(client, db_session, usuario_teste):
    # Reproduz o fluxo relatado pelo usuário, diferente do
    # fechamento direto testado acima: salva um rascunho SEM
    # observações, reabre e atualiza o rascunho ADICIONANDO
    # observações, e só então fecha via /fechar (não via POST direto
    # em /turnos/lancamento) - caminho de código genuinamente
    # diferente (fechar_turno_lancamento com turno_id existente, não
    # None), que merece teste próprio em vez de assumir que o
    # comportamento é idêntico ao fechamento direto.
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)

    payload_lancamentos = {
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
    }

    turno_id = client.post(
        "/api/v1/turnos/lancamento/rascunho",
        json={"nome_turno": "1º Turno", "responsavel_nome": "Líder Teste", **payload_lancamentos},
    ).json()["turno_id"]

    client.patch(
        f"/api/v1/turnos/lancamento/rascunho/{turno_id}",
        json={
            "nome_turno": "1º Turno",
            "responsavel_nome": "Líder Teste",
            "observacoes": "teste de impressão",
            **payload_lancamentos,
        },
    )

    res_fechar = client.post(
        f"/api/v1/turnos/lancamento/{turno_id}/fechar",
        json={
            "nome_turno": "1º Turno",
            "responsavel_nome": "Líder Teste",
            "observacoes": "teste de impressão",
            **payload_lancamentos,
        },
    )
    assert res_fechar.status_code == 200

    res_sem_obs = client.get(f"/api/v1/turnos/{turno_id}/relatorio.pdf")
    tamanho_com_obs = len(res_sem_obs.content)

    # compara contra um turno equivalente fechado direto, sem
    # observações, como controle
    turno_controle_id = client.post(
        "/api/v1/turnos/lancamento",
        json={"nome_turno": "1º Turno", "responsavel_nome": "Líder Teste", **payload_lancamentos},
    ).json()["turno_id"]
    tamanho_sem_obs = len(
        client.get(f"/api/v1/turnos/{turno_controle_id}/relatorio.pdf").content
    )

    assert tamanho_com_obs > tamanho_sem_obs


def _criar_admin(db_session, email="admin-lanc@siamp.test"):
    admin = Usuario(
        nome="Admin Teste",
        email=email,
        senha_hash=gerar_hash_senha("senha-forte-123"),
        perfil="ADMIN",
        ativo=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def test_corrigir_turno_lancamento_ja_fechado(client, db_session, usuario_teste):
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

    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.patch(
        f"/api/v1/turnos/lancamento/{turno_id}",
        json={
            "nome_turno": "1º Turno",
            "responsavel_nome": "Líder Corrigido",
            "lancamentos": [
                {
                    "numero_maquina": maquina.numero_maquina,
                    "tipo": "PRODUCAO",
                    "horario_inicio": "05:00",
                    "horario_fim": "06:00",
                    "produto_id": peca.id,
                    "quantidade": 150,
                }
            ],
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["kpis"]["total_produzido"] == 150

    detalhe = client.get(f"/api/v1/turnos/{turno_id}").json()
    assert detalhe["responsavel_nome"] == "Líder Corrigido"
    assert detalhe["editado_por_nome"] == "Admin Teste"


def test_corrigir_turno_lancamento_operador_nao_pode(client, db_session, usuario_teste):
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

    res = client.patch(
        f"/api/v1/turnos/lancamento/{turno_id}",
        json={
            "nome_turno": "1º Turno",
            "responsavel_nome": "Tentativa",
            "lancamentos": [
                {
                    "numero_maquina": maquina.numero_maquina,
                    "tipo": "PRODUCAO",
                    "horario_inicio": "05:00",
                    "horario_fim": "06:00",
                    "produto_id": peca.id,
                    "quantidade": 1,
                }
            ],
        },
    )
    assert res.status_code == 403


def test_exportar_csv_inclui_turno_lancamento(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)

    client.post(
        "/api/v1/turnos/lancamento",
        json={
            "nome_turno": "1º Turno",
            "responsavel_nome": "Líder Lançamento",
            "lancamentos": [
                {
                    "numero_maquina": maquina.numero_maquina,
                    "tipo": "PRODUCAO",
                    "horario_inicio": "05:00",
                    "horario_fim": "07:00",
                    "produto_id": peca.id,
                    "quantidade": 300,
                },
                {
                    "numero_maquina": maquina.numero_maquina,
                    "tipo": "PARADA_FALHA",
                    "horario_inicio": "07:00",
                    "horario_fim": "07:15",
                    "motivo": "Sensor travado",
                },
            ],
        },
    )

    res = client.get("/api/v1/turnos/exportar/csv")
    assert res.status_code == 200
    conteudo = res.content.decode("utf-8-sig")
    assert "LANCAMENTO" in conteudo
    assert "PRODUCAO" in conteudo
    assert "PARADA_FALHA" in conteudo
    assert "Sensor travado" in conteudo
    assert "300" in conteudo


def test_dashboard_ve_producao_de_turno_lancamento(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)

    client.post(
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
                    "quantidade": 250,
                }
            ],
        },
    )

    res = client.get("/api/v1/dashboard/metricas-gerais")
    assert res.status_code == 200
    dados = res.json()
    assert dados["kpis"]["total_turnos_encerrados"] == 1
    assert dados["kpis"]["total_pecas_produzidas"] == 250
    assert 250 in dados["grafico_producao"]["valores"]
    assert len(dados["producao_por_turno"]["labels"]) == 1
    assert dados["producao_por_turno"]["produzido"] == [250]


def test_ciclo_informado_no_lancamento_prevalece_sobre_peca(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)
    # Peça tem ciclo_padrao=10.0, cavidades=2 (ver _criar_maquina_e_peca)

    res = client.post(
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
                    "ciclo_informado": 20.0,
                }
            ],
        },
    )
    assert res.status_code == 201, res.text
    # 1h = 3600s / ciclo 20s (informado, não os 10s da peça) * 2 cavidades = 360
    assert res.json()["kpis"]["total_esperado"] == 360


def test_ciclo_informado_aparece_no_detalhe_do_turno_com_ciclo_padrao_da_peca(client, db_session, usuario_teste):
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
                    "ciclo_informado": 15.5,
                }
            ],
        },
    ).json()["turno_id"]

    detalhe = client.get(f"/api/v1/turnos/{turno_id}").json()
    lanc = detalhe["lancamentos"][0]
    assert lanc["ciclo_informado"] == 15.5
    assert lanc["ciclo_padrao_peca"] == peca.ciclo_padrao


def test_exportar_csv_inclui_ciclo_informado_do_lancamento(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)

    client.post(
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
                    "ciclo_informado": 12.3,
                }
            ],
        },
    )

    res = client.get("/api/v1/turnos/exportar/csv")
    conteudo = res.content.decode("utf-8-sig")
    assert "12.3" in conteudo


def test_indice_producao_e_limitado_a_100_por_cento(client, db_session, usuario_teste):
    # Regressão: ciclo real mais rápido que o ciclo padrão cadastrado
    # fazia o índice de produção (e o OEE) passar de 100%, o que não
    # tem sentido na convenção usual de OEE - acima de 100% indica
    # ciclo padrão desatualizado, não desempenho sobre-humano.
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)
    # peca: ciclo_padrao=10.0, cavidades=2 -> 1h = 3600/10*2 = 720 esperado

    res = client.post(
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
                    "quantidade": 900,  # bem acima do esperado (720)
                }
            ],
        },
    )
    assert res.status_code == 201, res.text
    kpis = res.json()["kpis"]
    assert kpis["total_produzido"] == 900
    assert kpis["total_esperado"] == 720
    assert kpis["indice_producao"] == 100.0
    assert kpis["eficiencia_oee"] == 100.0


def test_pdf_mostra_nd_quando_producao_sem_ciclo_cadastrado(client, db_session, usuario_teste):
    # Regressão: produção real numa peça sem ciclo/cavidades cadastrados
    # mostrava "Esperado: 0" no PDF, que parece uma meta cumprida com
    # folga em vez de "não há como calcular uma meta aqui".
    _login(client, usuario_teste)
    maquina = Maquina(numero_maquina="9", descricao="Injetora sem cadastro completo", ativo=True)
    peca_incompleta = Produto(codigo="SEM-CICLO", descricao="Peça Sem Ciclo", ciclo_padrao=None, cavidades=None)
    db_session.add_all([maquina, peca_incompleta])
    db_session.commit()
    db_session.refresh(maquina)
    db_session.refresh(peca_incompleta)

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
                    "produto_id": peca_incompleta.id,
                    "quantidade": 500,
                }
            ],
        },
    ).json()["turno_id"]

    from app.services.lancamento_service import montar_registros_pdf_lancamento

    linhas = montar_registros_pdf_lancamento(db_session, turno_id)
    assert len(linhas) == 1
    assert linhas[0]["prod_executada"] == 500
    assert linhas[0]["producao_esperada"] == "N/D"


def test_pdf_mostra_origem_do_ciclo_usado_no_calculo(client, db_session, usuario_teste):
    # Sem essa informação no relatório, não dá pra saber se um "Esperado"
    # divergente da produção real vem do ciclo informado pelo operador ou
    # do cadastro da peça - motivou dúvida real reportada pelo usuário.
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)  # ciclo_padrao=10.0, cavidades=2

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
                    "quantidade": 500,
                    "ciclo_informado": 8.0,
                },
            ],
        },
    ).json()["turno_id"]

    from app.services.lancamento_service import montar_registros_pdf_lancamento

    linhas = montar_registros_pdf_lancamento(db_session, turno_id)
    assert "ciclo informado: 8.0s" in linhas[0]["produto_descricao"]
    assert "ciclo cadastrado" not in linhas[0]["produto_descricao"]


def test_cavidades_informadas_no_lancamento_prevalece_sobre_peca(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)
    # Peça tem ciclo_padrao=10.0, cavidades=2 (ver _criar_maquina_e_peca)

    res = client.post(
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
                    "cavidades_informado": 1,  # metade das cavidades cadastradas (molde com 1 tamponada)
                }
            ],
        },
    )
    assert res.status_code == 201, res.text
    # 1h = 3600s / ciclo 10s (da peça) * 1 cavidade (informada, não as 2 da peça) = 360
    assert res.json()["kpis"]["total_esperado"] == 360


def test_ciclo_e_cavidades_informados_juntos(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca(db_session)

    res = client.post(
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
                    "ciclo_informado": 20.0,
                    "cavidades_informado": 4,
                }
            ],
        },
    )
    assert res.status_code == 201, res.text
    # 1h = 3600s / ciclo 20s (informado) * 4 cavidades (informadas) = 720
    assert res.json()["kpis"]["total_esperado"] == 720


def test_cavidades_informadas_aparece_no_detalhe_do_turno(client, db_session, usuario_teste):
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
                    "cavidades_informado": 1,
                }
            ],
        },
    ).json()["turno_id"]

    detalhe = client.get(f"/api/v1/turnos/{turno_id}").json()
    lanc = detalhe["lancamentos"][0]
    assert lanc["cavidades_informado"] == 1
    assert lanc["cavidades_padrao_peca"] == peca.cavidades


def test_pdf_mostra_cavidades_informadas_e_cadastradas(client, db_session, usuario_teste):
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
                    "cavidades_informado": 1,
                },
                {
                    "numero_maquina": maquina.numero_maquina,
                    "tipo": "PRODUCAO",
                    "horario_inicio": "06:00",
                    "horario_fim": "07:00",
                    "produto_id": peca.id,
                    "quantidade": 200,
                },
            ],
        },
    ).json()["turno_id"]

    from app.services.lancamento_service import montar_registros_pdf_lancamento

    linhas = montar_registros_pdf_lancamento(db_session, turno_id)
    assert "cavidades informadas: 1" in linhas[0]["produto_descricao"]
    assert "cavidades cadastradas: 2" in linhas[1]["produto_descricao"]
