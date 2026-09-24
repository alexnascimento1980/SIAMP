"""Testes do refugo estimado por peso de descarte - pedido do usuário
(exemplo real: folha de papel "DESCARTES DE PEÇAS MÁQUINA Nº 03" com
peso líquido da peça e peso bruto do lote descartado). Fórmula:

    refugo = peso_bruto_descarte / peso_gramas_peca

Os dois lados em GRAMAS, sem conversão de unidade entre eles - peças
injetadas pequenas podem pesar frações de grama (confirmado pelo
usuário em produção: uma peça real, CAPOT DV, pesa 0,0921g - menos de
1 grama), tornando plausível um lote de poucos gramas mesmo com
dezenas de peças descartadas. peso_gramas (peça) é um campo já
existente no cadastro, reaproveitado aqui em vez de criar um segundo
campo de peso duplicado."""
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


def _criar_maquina_e_peca_com_peso(db_session, peso_gramas=0.0921):
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


def test_calculo_com_peca_real_confirmada_pelo_usuario():
    # CAPOT DV pesa 0,0921g de verdade (confirmado pelo usuário em
    # produção - achado ao tentar cadastrar esse peso e esbarrar na
    # validação antiga, que só aceitava >= 0,1). Lote de 20 peças
    # descartadas pesaria, na prática, 20 x 0.0921 = 1.842g.
    peca = Produto(codigo="CAPOT-DV", descricao="Capot DV", peso_gramas=0.0921)
    lanc = _lancamento_producao(peso_bruto_descarte=1.842, quantidade=1960)
    assert calcular_refugo_lancamento(lanc, peca) == 20


def test_arredonda_para_o_mais_proximo_nao_trunca():
    # 10 / 2.6 = 3.846... - int() (truncamento) daria 3, round()
    # (usado de propósito, ver docstring de calcular_refugo_lancamento)
    # dá 4, mais fiel a uma estimativa física por peso.
    peca = Produto(codigo="P1", descricao="Peça", peso_gramas=2.6)
    lanc = _lancamento_producao(peso_bruto_descarte=10.0, quantidade=100)
    assert calcular_refugo_lancamento(lanc, peca) == 4


def test_refugo_nao_ultrapassa_a_quantidade_produzida():
    # Peso bruto exagerado (erro de pesagem, ou peso cadastrado
    # desatualizado) não deve gerar refugo maior que o produzido -
    # capado em quantidade, para não dar peças boas negativas.
    peca = Produto(codigo="P1", descricao="Peça", peso_gramas=0.01)
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
    maquina, peca = _criar_maquina_e_peca_com_peso(db_session, peso_gramas=0.0921)

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
                    "peso_bruto_descarte": 1.842,
                },
            ],
        },
    )
    assert res.status_code == 201, res.text
    kpis = res.json()["kpis"]
    # 1.842 / 0.0921 = 20 (arredondado)
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
    maquina, peca = _criar_maquina_e_peca_com_peso(db_session, peso_gramas=0.0921)

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
                    "peso_bruto_descarte": 1.842,
                },
            ],
        },
    ).json()["turno_id"]

    detalhe = client.get(f"/api/v1/turnos/{turno_id}").json()
    lanc = detalhe["lancamentos"][0]
    assert lanc["peso_bruto_descarte"] == 1.842
    assert lanc["peso_peca_gramas"] == 0.0921
    assert lanc["refugo_calculado"] == 20


def test_pdf_mostra_a_conta_do_refugo_por_extenso(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca_com_peso(db_session, peso_gramas=0.0921)

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
                    "peso_bruto_descarte": 1.842,
                },
            ],
        },
    ).json()["turno_id"]

    from app.services.lancamento_service import montar_registros_pdf_lancamento

    linhas = montar_registros_pdf_lancamento(db_session, turno_id)
    assert "refugo: 20pçs" in linhas[0]["produto_descricao"]
    assert "1.842g" in linhas[0]["produto_descricao"]
    assert "0.0921g/peça" in linhas[0]["produto_descricao"]


def test_dashboard_agrega_indice_de_qualidade_e_refugo_do_periodo(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca_com_peso(db_session, peso_gramas=0.0921)

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
                    "peso_bruto_descarte": 1.842,
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


def test_pecas_boas_conta_o_turno_inteiro_nao_so_a_injetora_com_descarte(client, db_session, usuario_teste):
    # Bug real relatado pelo usuário: com várias injetoras produzindo
    # no mesmo turno e só UMA delas com descarte pesado, "Peças Boas"
    # no relatório mostrava só a produção daquela injetora específica
    # (produção - refugo), como se as outras não tivessem produzido
    # nada - a correção soma o refugo de qualquer lançamento que tenha
    # essa informação, mas "Peças Boas" sempre reflete o turno inteiro
    # (total_produzido - total_refugo), nunca só uma fração dele.
    _login(client, usuario_teste)
    maquina1, peca_com_descarte = _criar_maquina_e_peca_com_peso(db_session, peso_gramas=0.0921)
    maquina2 = Maquina(numero_maquina="2", descricao="Injetora 2", ativo=True)
    peca_sem_descarte = Produto(
        codigo="PL-SEM-DESCARTE", descricao="Peça sem descarte pesado nesse turno",
        ciclo_padrao=20.0, cavidades=4,
    )
    db_session.add_all([maquina2, peca_sem_descarte])
    db_session.commit()
    db_session.refresh(maquina2)
    db_session.refresh(peca_sem_descarte)

    res = client.post(
        "/api/v1/turnos/lancamento",
        json={
            "nome_turno": "1º Turno",
            "responsavel_nome": "Rafael",
            "lancamentos": [
                {
                    "numero_maquina": maquina1.numero_maquina,
                    "tipo": "PRODUCAO",
                    "horario_inicio": "05:00",
                    "horario_fim": "13:00",
                    "produto_id": peca_com_descarte.id,
                    "quantidade": 2476,
                    "peso_bruto_descarte": 10.53,  # -> 114 peças de refugo
                },
                {
                    "numero_maquina": maquina2.numero_maquina,
                    "tipo": "PRODUCAO",
                    "horario_inicio": "05:00",
                    "horario_fim": "13:00",
                    "produto_id": peca_sem_descarte.id,
                    "quantidade": 23944,  # sem nenhum descarte informado nessa linha
                },
            ],
        },
    )
    assert res.status_code == 201, res.text
    kpis = res.json()["kpis"]
    # 10.53 / 0.0921 = 114.3 -> arredonda para 114
    assert kpis["total_refugo"] == 114
    # Peças boas do TURNO INTEIRO: 2476 + 23944 - 114 = 26306 (não
    # 2476 - 114 = 2362, que seria só a injetora com descarte)
    assert kpis["total_pecas_boas"] == 26306
    assert kpis["total_produzido"] == 26420
    assert kpis["total_pecas_boas"] + kpis["total_refugo"] == kpis["total_produzido"]


# --- Coluna de Refugo no PDF de fechamento de turno, e relatório de OP ---


def test_pdf_de_turno_mostra_coluna_de_refugo(client, db_session, usuario_teste):
    # Pedido do usuário: uma coluna dedicada de "Refugo" na tabela de
    # detalhe do relatório, não só embutido no texto da peça.
    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca_com_peso(db_session, peso_gramas=0.0921)

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
                    "quantidade": 1960,
                    "peso_bruto_descarte": 1.842,
                },
            ],
        },
    )
    turno_id = res.json()["turno_id"]

    pdf_bytes = client.get(f"/api/v1/turnos/{turno_id}/relatorio.pdf").content
    import io as io_module

    import pdfplumber

    with pdfplumber.open(io_module.BytesIO(pdf_bytes)) as pdf:
        texto = pdf.pages[0].extract_text()
    assert "Refugo" in texto  # cabeçalho da coluna nova
    assert "20" in texto  # valor da linha (1.842 / 0.0921 = 20)


def test_relatorio_op_pdf_mostra_meta_real_refugo(client, db_session, usuario_teste):
    from datetime import date

    from app.models.ordem_producao import OrdemProducao

    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca_com_peso(db_session, peso_gramas=0.0921)

    op = OrdemProducao(
        numero_op="OP-REFUGO-1", produto_id=peca.id, produto_codigo=peca.codigo,
        produto_descricao=peca.descricao, quantidade_a_produzir=5000,
        periodo_inicio=date(2026, 1, 1), periodo_fim=date(2026, 12, 31),
        maquina_id=maquina.id,
    )
    db_session.add(op)
    db_session.commit()
    db_session.refresh(op)

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
                    "ordem_producao_id": op.id,
                    "quantidade": 1960,
                    "peso_bruto_descarte": 1.842,
                },
            ],
        },
    )

    res = client.get(f"/api/v1/ordens-producao/{op.id}/relatorio.pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"

    import io as io_module

    import pdfplumber

    with pdfplumber.open(io_module.BytesIO(res.content)) as pdf:
        texto = pdf.pages[0].extract_text()
    assert "OP-REFUGO-1" in texto
    assert "5.000" in texto  # meta
    assert "1.960" in texto  # produzido
    assert "20" in texto  # refugo


def test_relatorio_op_pdf_acessivel_a_supervisor_e_operador(client, db_session, usuario_teste):
    from datetime import date

    from app.models.ordem_producao import OrdemProducao

    peca = _criar_maquina_e_peca_com_peso(db_session)[1]
    op = OrdemProducao(
        numero_op="OP-ACESSO-1", produto_id=peca.id, produto_codigo=peca.codigo,
        produto_descricao=peca.descricao, quantidade_a_produzir=100,
        periodo_inicio=date(2026, 1, 1), periodo_fim=date(2026, 12, 31),
    )
    db_session.add(op)
    db_session.commit()
    db_session.refresh(op)

    _login(client, usuario_teste)  # OPERADOR
    assert client.get(f"/api/v1/ordens-producao/{op.id}/relatorio.pdf").status_code == 200


def test_dashboard_comparativo_op_inclui_refugo(client, db_session, usuario_teste):
    from datetime import date

    from app.models.ordem_producao import OrdemProducao

    _login(client, usuario_teste)
    maquina, peca = _criar_maquina_e_peca_com_peso(db_session, peso_gramas=0.0921)

    op = OrdemProducao(
        numero_op="OP-DASH-1", produto_id=peca.id, produto_codigo=peca.codigo,
        produto_descricao=peca.descricao, quantidade_a_produzir=5000,
        periodo_inicio=date(2026, 1, 1), periodo_fim=date(2026, 12, 31),
    )
    db_session.add(op)
    db_session.commit()
    db_session.refresh(op)

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
                    "ordem_producao_id": op.id,
                    "quantidade": 1960,
                    "peso_bruto_descarte": 1.842,
                },
            ],
        },
    )

    res = client.get("/api/v1/dashboard/metricas-gerais?periodo=total")
    assert res.status_code == 200
    comparativo = next(
        c for c in res.json()["comparativo_ordens_producao"] if c["numero_op"] == "OP-DASH-1"
    )
    assert comparativo["quantidade_refugo"] == 20
    assert comparativo["id"] == op.id
