import io

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


def _criar_admin(db_session, email="admin-import@siamp.test"):
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


def _criar_operador(db_session, email="operador-import@siamp.test"):
    op = Usuario(
        nome="Operador Teste",
        email=email,
        senha_hash=gerar_hash_senha("senha-forte-123"),
        perfil="OPERADOR",
        ativo=True,
    )
    db_session.add(op)
    db_session.commit()
    db_session.refresh(op)
    return op


def _criar_maquina_e_peca(db_session):
    maquina = Maquina(numero_maquina="1", descricao="Injetora 1", ativo=True)
    peca = Produto(codigo="PC-100", descricao="Peça Importação", ciclo_padrao=10.0, cavidades=2)
    db_session.add_all([maquina, peca])
    db_session.commit()
    db_session.refresh(maquina)
    db_session.refresh(peca)
    return maquina, peca


def _upload(client, conteudo: bytes, nome_arquivo: str, content_type="text/csv"):
    return client.post(
        "/api/v1/ordens-producao/importar",
        files={"arquivo": (nome_arquivo, io.BytesIO(conteudo), content_type)},
    )


def test_importar_csv_com_linha_valida(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    maquina, peca = _criar_maquina_e_peca(db_session)

    csv_conteudo = (
        "numero_op,produto_codigo,numero_maquina,quantidade_a_produzir,periodo_inicio,periodo_fim\n"
        f"OP-IMP-1,{peca.codigo},{maquina.numero_maquina},1000,2026-09-01,2026-09-05\n"
    ).encode()

    res = _upload(client, csv_conteudo, "ordens.csv")
    assert res.status_code == 200, res.text
    dados = res.json()
    assert dados["criadas"] == 1
    assert dados["numeros_op_criados"] == ["OP-IMP-1"]
    assert dados["erros"] == []

    listagem = client.get("/api/v1/ordens-producao/").json()
    assert any(o["numero_op"] == "OP-IMP-1" for o in listagem)


def test_importar_csv_sem_numero_maquina_e_aceito(client, db_session):
    # Pedido do usuário: máquina não deve ser obrigatória, já que uma
    # OP pode ser atendida por mais de uma injetora - vale tanto pro
    # cadastro manual quanto pra importação em lote.
    admin = _criar_admin(db_session)
    _login(client, admin)
    _, peca = _criar_maquina_e_peca(db_session)

    csv_conteudo = (
        "numero_op,produto_codigo,quantidade_a_produzir,periodo_inicio,periodo_fim\n"
        f"OP-SEM-MAQ,{peca.codigo},1000,2026-09-01,2026-09-05\n"
    ).encode()

    res = _upload(client, csv_conteudo, "ordens.csv")
    assert res.status_code == 200, res.text
    dados = res.json()
    assert dados["criadas"] == 1
    assert dados["erros"] == []


def test_importar_csv_peca_nao_cadastrada_e_rejeitada_e_listada(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    maquina, _peca = _criar_maquina_e_peca(db_session)

    csv_conteudo = (
        "numero_op,produto_codigo,numero_maquina,quantidade_a_produzir,periodo_inicio,periodo_fim\n"
        f"OP-IMP-2,CODIGO-INEXISTENTE,{maquina.numero_maquina},500,2026-09-01,2026-09-05\n"
    ).encode()

    res = _upload(client, csv_conteudo, "ordens.csv")
    assert res.status_code == 200, res.text
    dados = res.json()
    assert dados["criadas"] == 0
    assert len(dados["erros"]) == 1
    assert "CODIGO-INEXISTENTE" in dados["erros"][0]["motivo"]
    assert dados["pecas_faltando"] == ["CODIGO-INEXISTENTE"]


def test_importar_csv_maquina_nao_cadastrada_e_rejeitada_e_listada(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    _maquina, peca = _criar_maquina_e_peca(db_session)

    csv_conteudo = (
        "numero_op,produto_codigo,numero_maquina,quantidade_a_produzir,periodo_inicio,periodo_fim\n"
        f"OP-IMP-3,{peca.codigo},99,500,2026-09-01,2026-09-05\n"
    ).encode()

    res = _upload(client, csv_conteudo, "ordens.csv")
    assert res.status_code == 200
    dados = res.json()
    assert dados["criadas"] == 0
    assert dados["maquinas_faltando"] == ["99"]


def test_importar_csv_numero_op_ja_existente_e_rejeitado(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    maquina, peca = _criar_maquina_e_peca(db_session)

    client.post(
        "/api/v1/ordens-producao/",
        json={
            "numero_op": "OP-DUP",
            "produto_id": peca.id,
            "quantidade_a_produzir": 100,
            "numero_maquina": maquina.numero_maquina,
            "periodo_inicio": "2026-09-01",
            "periodo_fim": "2026-09-05",
        },
    )

    csv_conteudo = (
        "numero_op,produto_codigo,numero_maquina,quantidade_a_produzir,periodo_inicio,periodo_fim\n"
        f"OP-DUP,{peca.codigo},{maquina.numero_maquina},200,2026-09-01,2026-09-05\n"
    ).encode()

    res = _upload(client, csv_conteudo, "ordens.csv")
    dados = res.json()
    assert dados["criadas"] == 0
    assert "já existe" in dados["erros"][0]["motivo"].lower()


def test_importar_csv_numero_op_duplicado_dentro_do_arquivo(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    maquina, peca = _criar_maquina_e_peca(db_session)

    csv_conteudo = (
        "numero_op,produto_codigo,numero_maquina,quantidade_a_produzir,periodo_inicio,periodo_fim\n"
        f"OP-REPETIDA,{peca.codigo},{maquina.numero_maquina},100,2026-09-01,2026-09-05\n"
        f"OP-REPETIDA,{peca.codigo},{maquina.numero_maquina},200,2026-09-06,2026-09-10\n"
    ).encode()

    res = _upload(client, csv_conteudo, "ordens.csv")
    dados = res.json()
    assert dados["criadas"] == 1
    assert len(dados["erros"]) == 1
    assert "repetido" in dados["erros"][0]["motivo"].lower()


def test_importar_csv_data_invalida_e_rejeitada(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    maquina, peca = _criar_maquina_e_peca(db_session)

    csv_conteudo = (
        "numero_op,produto_codigo,numero_maquina,quantidade_a_produzir,periodo_inicio,periodo_fim\n"
        f"OP-DATA-RUIM,{peca.codigo},{maquina.numero_maquina},100,31-31-2026,2026-09-05\n"
    ).encode()

    res = _upload(client, csv_conteudo, "ordens.csv")
    dados = res.json()
    assert dados["criadas"] == 0
    assert "data inválida" in dados["erros"][0]["motivo"].lower()


def test_importar_csv_com_separador_ponto_e_virgula(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    maquina, peca = _criar_maquina_e_peca(db_session)

    csv_conteudo = (
        "numero_op;produto_codigo;numero_maquina;quantidade_a_produzir;periodo_inicio;periodo_fim\n"
        f"OP-PTV;{peca.codigo};{maquina.numero_maquina};300;01/09/2026;05/09/2026\n"
    ).encode()

    res = _upload(client, csv_conteudo, "ordens.csv")
    dados = res.json()
    assert dados["criadas"] == 1, dados


def test_importar_xml_com_linha_valida(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    maquina, peca = _criar_maquina_e_peca(db_session)

    xml_conteudo = f"""<?xml version="1.0" encoding="UTF-8"?>
    <ordens_producao>
      <ordem>
        <numero_op>OP-XML-1</numero_op>
        <produto_codigo>{peca.codigo}</produto_codigo>
        <numero_maquina>{maquina.numero_maquina}</numero_maquina>
        <quantidade_a_produzir>750</quantidade_a_produzir>
        <periodo_inicio>2026-09-01</periodo_inicio>
        <periodo_fim>2026-09-05</periodo_fim>
      </ordem>
    </ordens_producao>""".encode()

    res = _upload(client, xml_conteudo, "ordens.xml", content_type="application/xml")
    assert res.status_code == 200, res.text
    dados = res.json()
    assert dados["criadas"] == 1
    assert dados["numeros_op_criados"] == ["OP-XML-1"]


def test_importar_xml_malicioso_xxe_nao_quebra_o_servidor(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    xml_malicioso = b"""<?xml version="1.0"?>
    <!DOCTYPE ordens_producao [
      <!ENTITY xxe SYSTEM "file:///etc/passwd">
    ]>
    <ordens_producao>
      <ordem>
        <numero_op>&xxe;</numero_op>
      </ordem>
    </ordens_producao>"""

    res = _upload(client, xml_malicioso, "malicioso.xml", content_type="application/xml")
    # defusedxml deve bloquear o DOCTYPE/entidade externa antes de
    # sequer tentar resolvê-la - a resposta deve ser um erro tratado
    # (400). A mensagem de erro pode ecoar a URI que a entidade
    # maliciosa tentou acessar (isso é só o texto que o próprio
    # atacante escreveu no XML, inofensivo) - o que importa é que
    # nenhum CONTEÚDO real de arquivo foi lido e vazado (ex.: a
    # primeira linha clássica de /etc/passwd, "root:").
    assert res.status_code == 400
    assert "root:" not in res.text


def test_importar_arquivo_com_extensao_invalida_e_rejeitado(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = _upload(client, b"conteudo qualquer", "ordens.txt", content_type="text/plain")
    assert res.status_code == 400


def test_importar_arquivo_vazio_e_rejeitado(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = _upload(client, b"", "ordens.csv")
    assert res.status_code == 400


def test_operador_nao_pode_importar(client, db_session):
    operador = _criar_operador(db_session)
    _login(client, operador)

    csv_conteudo = b"numero_op,produto_codigo,numero_maquina,quantidade_a_produzir,periodo_inicio,periodo_fim\n"
    res = _upload(client, csv_conteudo, "ordens.csv")
    assert res.status_code == 403


def test_importar_csv_linha_valida_e_linha_com_erro_juntas(client, db_session):
    # Uma linha ruim não deve travar a importação das linhas boas do
    # mesmo arquivo.
    admin = _criar_admin(db_session)
    _login(client, admin)
    maquina, peca = _criar_maquina_e_peca(db_session)

    csv_conteudo = (
        "numero_op,produto_codigo,numero_maquina,quantidade_a_produzir,periodo_inicio,periodo_fim\n"
        f"OP-BOA,{peca.codigo},{maquina.numero_maquina},100,2026-09-01,2026-09-05\n"
        f"OP-RUIM,CODIGO-FALSO,{maquina.numero_maquina},100,2026-09-01,2026-09-05\n"
    ).encode()

    res = _upload(client, csv_conteudo, "ordens.csv")
    dados = res.json()
    assert dados["criadas"] == 1
    assert dados["numeros_op_criados"] == ["OP-BOA"]
    assert len(dados["erros"]) == 1
    assert dados["erros"][0]["numero_op"] == "OP-RUIM"
