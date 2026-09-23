"""Testes do refugo estimado por peso de descarte - pedido do usuário
(exemplo real: folha de papel "DESCARTES DE PEÇAS MÁQUINA Nº 03" com
peso líquido da peça e peso bruto do lote descartado). Fórmula:

    refugo = (peso_bruto_descarte_kg * 1000) / peso_gramas_peca

peso_bruto_descarte (por lançamento, kg) é novo; peso_gramas (peça,
gramas) é um campo já existente no cadastro, reaproveitado aqui em vez
de criar um segundo campo de peso duplicado na mesma peça."""
from datetime import time

from app.core.security import gerar_hash_senha
from app.models.lancamento import TIPO_PRODUCAO, Lancamento
from app.models.maquina import Maquina
from app.models.produto import Produto
from app.models.usuario import Usuario
from app.services.analytics import calcular_refugo_lancamento


def _login(client, usuario):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 200


def _criar_maquina_e_peca_com_peso(db_session, peso_gramas=92.2):
    maquina = Maquina(numero_maquina="1", descricao="Injetora 1", ativo=True)
    peca = Produto(
        codigo="PL-REFUGO", descricao="Peça com peso cadastrado",
        ciclo_padrao=10.0, cavidades=2, peso_gramas=peso_gramas,
    )
    db_session.add_all([maquina, peca])
    db_session.commit()
    db_session.refresh(maquina)
    db_session.refresh(peca)
    return maquina, peca


def _lancamento_producao(**kwargs):
    padrao = dict(
        tipo=TIPO_PRODUCAO, horario_inicio=time(22, 0), horario_fim=time(4, 0),
        quantidade=1960, peso_bruto_descarte=None,
    )
    padrao.update(kwargs)
    return Lancamento(**padrao)


# --- calcular_refugo_lancamento (unitário, sem banco) -------------------


def test_sem_peso_bruto_descarte_retorna_none():
    peca = Produto(codigo="P1", descricao="Peça", peso_gramas=100.0)
    lanc = _lancamento_producao(peso_bruto_descarte=None)
    assert calcular_refugo_lancamento(lanc, peca) is None


def test_peca_sem_peso_cadastrado_retorna_none():
    peca = Produto(codigo="P1", descricao="Peça", peso_gramas=None)
    lanc = _lancamento_producao(peso_bruto_descarte=1.0)
    assert calcular_refugo_lancamento(lanc, peca) is None


def test_sem_peca_nenhuma_retorna_none():
    lanc = _lancamento_producao(peso_bruto_descarte=1.0)
    assert calcular_refugo_lancamento(lanc, None) is None


def test_calculo_exato_do_exemplo_real():
    # Folha real: CAPOT DV, peso líquido 0,0922 kg = 92,2g por peça,
    # peso bruto do descarte pesado no lançamento: 1,845 kg = 1845g.
    # 1845 / 92.2 = 20.01... -> arredonda para 20.
    peca = Produto(codigo="CAPOT-DV", descricao="Capot DV", peso_gramas=92.2)
    lanc = _lancamento_producao(peso_bruto_descarte=1.845, quantidade=1960)
    assert calcular_refugo_lancamento(lanc, peca) == 20


def test_arredonda_para_o_mais_proximo_nao_trunca():
    # peso_bruto_descarte=10kg=10000g, peça de 2600g cada:
    # 10000 / 2600 = 3.846... - int() (truncamento) daria 3, round()
    # (usado de propósito, ver docstring de calcular_refugo_lancamento)
    # dá 4, mais fiel a uma estimativa física por peso.
    peca = Produto(codigo="P1", descricao="Peça", peso_gramas=2600.0)
    lanc = _lancamento_producao(peso_bruto_descarte=10.0, quantidade=100)
    assert calcular_refugo_lancamento(lanc, peca) == 4


def test_refugo_nao_ultrapassa_a_quantidade_produzida():
    # Peso bruto exagerado (erro de pesagem, ou peso cadastrado
    # desatualizado) não deve gerar refugo maior que o produzido -
    # capado em quantidade, para não dar peças boas negativas.
    peca = Produto(codigo="P1", descricao="Peça", peso_gramas=10.0)
    lanc = _lancamento_producao(peso_bruto_descarte=100.0, quantidade=50)
    assert calcular_refugo_lancamento(lanc, peca) == 50


def test_parada_falha_nunca_calcula_refugo():
    from app.models.lancamento import TIPO_PARADA_FALHA

    peca = Produto(codigo="P1", descricao="Peça", peso_gramas=100.0)
    lanc = _lancamento_producao(tipo=TIPO_PARADA_FALHA, peso_bruto_descarte=1.0, quantidade=None)
    assert calcular_refugo_lancamento(lanc, peca) is None


# --- Integração via API --------------------------------------------------


def test_fechamento_com_descarte_calcula_qualidade_e_oee(client, db_session):
    admin = Usuario(
        nome="Admin", email="admin-refugo@siamp.test",
        senha_hash=gerar_hash_senha("senha-forte-123"), perfil="ADMIN", ativo=True,
    )
    db_session.add(admin)
    db_session.commit()
    _login(client, admin)
    maquina, peca = _criar_maquina_e_peca_com_peso(db_session, peso_gramas=92.2)

    res = client.post(
        "/api/v1/turnos/lancamento",
        json={
            "nome_turno": "3º Turno (22:00 - 04:00)",
            "responsavel_nome": "Tiago",
            "lancamentos": [
                {
                    "numero_maquina": maquina.numero_maquina,
                    "tipo": "PRODUCAO",
                    "horario_inicio": "22:00",
                    "horario_fim": "04:00",
                    "produto_id": peca.id,
                    "quantidade": 1960,
                    "peso_bruto_descarte": 1.845,
                },
            ],
        },
    )
    assert res.status_code == 201, res.text
    kpis = res.json()["kpis"]
    # (1.845 * 1000) / 92.2 = 20 (arredondado)
    assert kpis["total_refugo"] == 20
    assert kpis["total_pecas_boas"] == 1960 - 20
    assert kpis["indice_qualidade"] == round((1960 - 20) / 1960 * 100, 2)
    # Eficiência (OEE) = índice de produção × índice de qualidade -
    # confirma que o refugo agora participa do OEE, não só do índice
    # de qualidade isolado.
    assert kpis["eficiencia_oee"] < kpis["indice_producao"]


def test_fechamento_sem_nenhum_descarte_mantem_qualidade_em_100(client, db_session, usuario_teste):
    # Regressão: turno sem nenhum lançamento com peso_bruto_descarte
    # continua assumindo 100% de qualidade, mesmo comportamento de
    # antes desta funcionalidade existir.
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca_com_peso(db_session)

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
                    "quantidade": 500,
                },
            ],
        },
    )
    assert res.status_code == 201, res.text
    kpis = res.json()["kpis"]
    assert kpis["indice_qualidade"] == 100.0
    assert kpis["total_refugo"] == 0


def test_detalhe_do_turno_mostra_refugo_calculado(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca_com_peso(db_session, peso_gramas=92.2)

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
                    "quantidade": 1960,
                    "peso_bruto_descarte": 1.845,
                },
            ],
        },
    ).json()["turno_id"]

    detalhe = client.get(f"/api/v1/turnos/{turno_id}").json()
    lanc = detalhe["lancamentos"][0]
    assert lanc["peso_bruto_descarte"] == 1.845
    assert lanc["peso_peca_gramas"] == 92.2
    assert lanc["refugo_calculado"] == 20


def test_pdf_mostra_a_conta_do_refugo_por_extenso(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca_com_peso(db_session, peso_gramas=92.2)

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
                    "quantidade": 1960,
                    "peso_bruto_descarte": 1.845,
                },
            ],
        },
    ).json()["turno_id"]

    from app.services.lancamento_service import montar_registros_pdf_lancamento

    linhas = montar_registros_pdf_lancamento(db_session, turno_id)
    assert "refugo: 20pçs" in linhas[0]["produto_descricao"]
    assert "1.845kg" in linhas[0]["produto_descricao"]
    assert "92.2g/peça" in linhas[0]["produto_descricao"]


def test_dashboard_agrega_indice_de_qualidade_e_refugo_do_periodo(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca_com_peso(db_session, peso_gramas=92.2)

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
                    "quantidade": 1960,
                    "peso_bruto_descarte": 1.845,
                },
            ],
        },
    )

    res = client.get("/api/v1/dashboard/metricas-gerais?periodo=total")
    assert res.status_code == 200
    kpis = res.json()["kpis"]
    assert kpis["total_refugo_periodo"] == 20
    assert kpis["indice_qualidade_medio"] == round((1960 - 20) / 1960 * 100, 2)


def test_dashboard_sem_nenhum_turno_assume_qualidade_100(client, usuario_teste):
    _login(client, usuario_teste)
    res = client.get("/api/v1/dashboard/metricas-gerais?periodo=total")
    assert res.status_code == 200
    kpis = res.json()["kpis"]
    assert kpis["indice_qualidade_medio"] == 100.0
    assert kpis["total_refugo_periodo"] == 0
