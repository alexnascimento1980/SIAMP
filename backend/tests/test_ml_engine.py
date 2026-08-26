from datetime import time

from app.models.lancamento import Lancamento
from app.models.maquina import Maquina
from app.models.produto import Produto
from app.models.turno import Turno
from app.services.ml_engine import _taxa_falha_historica, prever_risco_parada


def _criar_turno_com_lancamentos(db_session, maquina, lancamentos):
    turno = Turno(
        nome_turno="1º Turno", responsavel_nome="Teste",
        status_assinatura="ASSINADO_DIGITALMENTE", modelo_apontamento="LANCAMENTO",
    )
    db_session.add(turno)
    db_session.flush()
    for tipo, hi, hf, produto_id, quantidade in lancamentos:
        db_session.add(Lancamento(
            turno_id=turno.id, maquina_id=maquina.id, tipo=tipo,
            horario_inicio=hi, horario_fim=hf, produto_id=produto_id, quantidade=quantidade,
        ))
    db_session.commit()
    return turno


def test_taxa_falha_historica_sem_dados_retorna_zero(db_session):
    assert _taxa_falha_historica(db_session, Lancamento.maquina_id, 999) == 0.0


def test_taxa_falha_historica_calcula_proporcao_correta(db_session):
    maquina = Maquina(numero_maquina="1", descricao="Injetora", ativo=True)
    db_session.add(maquina)
    db_session.commit()
    db_session.refresh(maquina)

    # 3 produções + 1 falha = taxa de 1/4 = 25%
    _criar_turno_com_lancamentos(db_session, maquina, [
        ("PRODUCAO", time(5, 0), time(6, 0), None, 100),
        ("PRODUCAO", time(6, 0), time(7, 0), None, 100),
        ("PARADA_FALHA", time(7, 0), time(7, 10), None, None),
        ("PRODUCAO", time(7, 10), time(8, 0), None, 100),
    ])

    taxa = _taxa_falha_historica(db_session, Lancamento.maquina_id, maquina.id)
    assert taxa == 0.25


def test_prever_risco_parada_sem_modelo_usa_heuristica(db_session, monkeypatch):
    # Força o caminho da heurística explicitamente (em vez de depender
    # do modelo treinado não existir no disco - ele agora é parte do
    # projeto, então precisa de um mock para testar esse caminho de
    # forma determinística).
    import app.services.ml_engine as ml_engine
    monkeypatch.setattr(ml_engine, "carregar_modelo", lambda: None)

    maquina = Maquina(numero_maquina="1", descricao="Injetora", ativo=True)
    db_session.add(maquina)
    db_session.commit()
    db_session.refresh(maquina)

    resultado = prever_risco_parada(
        db=db_session, maquina_id=maquina.id, produto_id=None,
        ciclo_efetivo=15.0, ciclo_padrao_peca=15.0, cavidades_efetivas=4,
        duracao_min=60.0, quantidade=1000, turno_num=1, dia_semana=2,
    )
    assert resultado["fonte"] == "heuristica"
    assert "risco_desvio" in resultado
    assert "probabilidade_critica" in resultado
    assert "detalhe" in resultado


def test_prever_risco_parada_com_modelo_treinado_usa_modelo_ml(db_session):
    # Sem mock - usa o modelo treinado de verdade que faz parte do
    # projeto (backend/app/ml_models/modelo_risco_parada.joblib),
    # confirmando que ele carrega e responde no formato esperado.
    maquina = Maquina(numero_maquina="1", descricao="Injetora", ativo=True)
    db_session.add(maquina)
    db_session.commit()
    db_session.refresh(maquina)

    resultado = prever_risco_parada(
        db=db_session, maquina_id=maquina.id, produto_id=None,
        ciclo_efetivo=15.0, ciclo_padrao_peca=15.0, cavidades_efetivas=4,
        duracao_min=60.0, quantidade=1000, turno_num=1, dia_semana=2,
    )
    assert resultado["fonte"] == "modelo_ml"
    assert 0.0 <= resultado["probabilidade_critica"] <= 100.0


def test_prever_risco_parada_maquina_com_muitas_falhas_da_risco_alto(db_session, monkeypatch):
    import app.services.ml_engine as ml_engine
    monkeypatch.setattr(ml_engine, "carregar_modelo", lambda: None)

    maquina_arriscada = Maquina(numero_maquina="1", descricao="Injetora Arriscada", ativo=True)
    maquina_estavel = Maquina(numero_maquina="2", descricao="Injetora Estável", ativo=True)
    db_session.add_all([maquina_arriscada, maquina_estavel])
    db_session.commit()
    db_session.refresh(maquina_arriscada)
    db_session.refresh(maquina_estavel)

    # Máquina arriscada: metade dos lançamentos são falha
    _criar_turno_com_lancamentos(db_session, maquina_arriscada, [
        ("PRODUCAO", time(5, 0), time(6, 0), None, 100),
        ("PARADA_FALHA", time(6, 0), time(6, 20), None, None),
        ("PRODUCAO", time(6, 20), time(7, 0), None, 100),
        ("PARADA_FALHA", time(7, 0), time(7, 20), None, None),
    ])
    # Máquina estável: nunca falhou
    _criar_turno_com_lancamentos(db_session, maquina_estavel, [
        ("PRODUCAO", time(5, 0), time(6, 0), None, 100),
        ("PRODUCAO", time(6, 0), time(7, 0), None, 100),
        ("PRODUCAO", time(7, 0), time(8, 0), None, 100),
    ])

    resultado_arriscada = prever_risco_parada(
        db=db_session, maquina_id=maquina_arriscada.id, produto_id=None,
        ciclo_efetivo=15.0, ciclo_padrao_peca=15.0, cavidades_efetivas=4,
        duracao_min=60.0, quantidade=1000, turno_num=1, dia_semana=2,
    )
    resultado_estavel = prever_risco_parada(
        db=db_session, maquina_id=maquina_estavel.id, produto_id=None,
        ciclo_efetivo=15.0, ciclo_padrao_peca=15.0, cavidades_efetivas=4,
        duracao_min=60.0, quantidade=1000, turno_num=1, dia_semana=2,
    )

    assert resultado_arriscada["probabilidade_critica"] > resultado_estavel["probabilidade_critica"]
    assert resultado_arriscada["detalhe"]["taxa_falha_historica_maquina"] == 50.0
    assert resultado_estavel["detalhe"]["taxa_falha_historica_maquina"] == 0.0


def test_prever_risco_parada_ciclo_divergente_aumenta_risco(db_session, monkeypatch):
    import app.services.ml_engine as ml_engine
    monkeypatch.setattr(ml_engine, "carregar_modelo", lambda: None)

    maquina = Maquina(numero_maquina="1", descricao="Injetora", ativo=True)
    db_session.add(maquina)
    db_session.commit()
    db_session.refresh(maquina)

    resultado_normal = prever_risco_parada(
        db=db_session, maquina_id=maquina.id, produto_id=None,
        ciclo_efetivo=15.0, ciclo_padrao_peca=15.0, cavidades_efetivas=4,
        duracao_min=60.0, quantidade=1000, turno_num=1, dia_semana=2,
    )
    # Ciclo real 50% acima do padrão da peça
    resultado_divergente = prever_risco_parada(
        db=db_session, maquina_id=maquina.id, produto_id=None,
        ciclo_efetivo=22.5, ciclo_padrao_peca=15.0, cavidades_efetivas=4,
        duracao_min=60.0, quantidade=1000, turno_num=1, dia_semana=2,
    )

    assert resultado_divergente["detalhe"]["ciclo_divergencia_pct"] == 50.0
    assert resultado_divergente["probabilidade_critica"] > resultado_normal["probabilidade_critica"]


def test_dashboard_insight_sem_lancamentos_de_producao(client, usuario_teste):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario_teste.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 200

    res = client.get("/api/v1/dashboard/metricas-gerais")
    assert res.status_code == 200
    insight = res.json()["insight_ml"]
    assert insight["fonte"] == "sem_dados"
    assert insight["risco_desvio"] is False


def test_dashboard_insight_usa_lancamento_mais_recente(client, db_session, usuario_teste):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario_teste.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 200

    maquina = Maquina(numero_maquina="1", descricao="Injetora", ativo=True)
    peca = Produto(codigo="PC1", descricao="Peça Teste", ciclo_padrao=15.0, cavidades=4)
    db_session.add_all([maquina, peca])
    db_session.commit()
    db_session.refresh(maquina)
    db_session.refresh(peca)

    turno = Turno(
        nome_turno="2º Turno", responsavel_nome="Teste",
        status_assinatura="ASSINADO_DIGITALMENTE", modelo_apontamento="LANCAMENTO",
    )
    db_session.add(turno)
    db_session.flush()
    db_session.add(Lancamento(
        turno_id=turno.id, maquina_id=maquina.id, tipo="PRODUCAO",
        horario_inicio=time(13, 0), horario_fim=time(14, 0),
        produto_id=peca.id, quantidade=500,
    ))
    db_session.commit()

    res = client.get("/api/v1/dashboard/metricas-gerais")
    assert res.status_code == 200
    insight = res.json()["insight_ml"]
    assert insight["fonte"] in ("heuristica", "modelo_ml")
    assert "detalhe" in insight


def test_endpoint_diagnostico_risco_manual(client, db_session, usuario_teste):
    # Endpoint de teste manual (Swagger) do modelo - usado para
    # experimentar hipóteses sem precisar de um lançamento real no
    # banco. Confirma que está de fato registrado e funcional (o
    # arquivo predictions.py existia mas não tinha nenhum teste
    # cobrindo se o router realmente estava incluído na aplicação).
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario_teste.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 200

    maquina = Maquina(numero_maquina="1", descricao="Injetora", ativo=True)
    db_session.add(maquina)
    db_session.commit()
    db_session.refresh(maquina)

    res = client.post(
        "/api/v1/predictions/diagnostico-risco",
        json={
            "maquina_id": maquina.id,
            "produto_id": None,
            "ciclo_efetivo": 18.5,
            "ciclo_padrao_peca": 18.0,
            "cavidades_efetivas": 4,
            "duracao_min": 120.0,
            "quantidade": 350,
            "turno_num": 1,
            "dia_semana": 2,
        },
    )
    assert res.status_code == 200, res.text
    corpo = res.json()
    assert "risco_desvio" in corpo
    assert "probabilidade_critica" in corpo
    assert "detalhe" in corpo


def test_endpoint_diagnostico_risco_exige_autenticacao(client, db_session):
    res = client.post(
        "/api/v1/predictions/diagnostico-risco",
        json={"maquina_id": 1, "duracao_min": 60.0},
    )
    assert res.status_code == 401
