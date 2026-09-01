from pathlib import Path

from app.core.security import gerar_hash_senha
from app.models.maquina import Maquina
from app.models.produto import Produto
from app.models.usuario import Usuario

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _login(client, usuario):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 200


def _criar_admin(db_session, email="admin-extracao@siamp.test"):
    admin = Usuario(
        nome="Admin Teste", email=email,
        senha_hash=gerar_hash_senha("senha-forte-123"), perfil="ADMIN", ativo=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def _pdf_real():
    return (FIXTURES_DIR / "ordem_producao_maxmanager.pdf").read_bytes()


def test_extrair_documento_reconhece_peca_e_maquina_ja_cadastradas(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    # Cadastra exatamente a peça e a máquina que aparecem no PDF real
    maquina = Maquina(numero_maquina="06", descricao="Injetora 06", ativo=True)
    peca = Produto(codigo="34-7506-00BR", descricao="CLIP TUBE - BRESIL", ciclo_padrao=19.0, cavidades=8)
    db_session.add_all([maquina, peca])
    db_session.commit()
    db_session.refresh(peca)

    res = client.post(
        "/api/v1/ordens-producao/extrair-documento",
        files={"arquivo": ("ordem.pdf", _pdf_real(), "application/pdf")},
    )
    assert res.status_code == 200, res.text
    corpo = res.json()

    assert corpo["campos"]["numero_op"] == "2817-2026"
    assert corpo["campos"]["quantidade_a_produzir"] == 48000
    assert corpo["produto_id"] == peca.id
    assert corpo["produto_nao_encontrado"] is None
    assert corpo["numero_maquina_nao_encontrada"] is None


def test_extrair_documento_avisa_peca_e_maquina_nao_cadastradas(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    # Não cadastra nada - peça/máquina do PDF não existem no catálogo

    res = client.post(
        "/api/v1/ordens-producao/extrair-documento",
        files={"arquivo": ("ordem.pdf", _pdf_real(), "application/pdf")},
    )
    assert res.status_code == 200, res.text
    corpo = res.json()

    assert corpo["produto_id"] is None
    assert corpo["produto_nao_encontrado"] == "34-7506-00BR"
    assert corpo["numero_maquina_nao_encontrada"] == "06"


def test_extrair_documento_extensao_nao_suportada_e_rejeitada(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.post(
        "/api/v1/ordens-producao/extrair-documento",
        files={"arquivo": ("ordem.docx", b"conteudo qualquer", "application/octet-stream")},
    )
    assert res.status_code == 400


def test_extrair_documento_arquivo_vazio_e_rejeitado(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.post(
        "/api/v1/ordens-producao/extrair-documento",
        files={"arquivo": ("ordem.pdf", b"", "application/pdf")},
    )
    assert res.status_code == 400


def test_extrair_documento_pdf_corrompido_retorna_erro_claro(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.post(
        "/api/v1/ordens-producao/extrair-documento",
        files={"arquivo": ("ordem.pdf", b"isso nao e um pdf de verdade", "application/pdf")},
    )
    assert res.status_code == 422


def test_extrair_documento_operador_nao_pode(client, db_session, usuario_teste):
    _login(client, usuario_teste)

    res = client.post(
        "/api/v1/ordens-producao/extrair-documento",
        files={"arquivo": ("ordem.pdf", _pdf_real(), "application/pdf")},
    )
    assert res.status_code == 403


def test_extrair_documento_nao_cria_ordem_de_producao_nenhuma(client, db_session):
    # A extração é só uma sugestão para revisão - nunca deve criar a
    # OP sozinha, mesmo quando peça e máquina batem perfeitamente.
    from app.models.ordem_producao import OrdemProducao

    admin = _criar_admin(db_session)
    _login(client, admin)
    maquina = Maquina(numero_maquina="06", descricao="Injetora 06", ativo=True)
    peca = Produto(codigo="34-7506-00BR", descricao="CLIP TUBE", ciclo_padrao=19.0, cavidades=8)
    db_session.add_all([maquina, peca])
    db_session.commit()

    client.post(
        "/api/v1/ordens-producao/extrair-documento",
        files={"arquivo": ("ordem.pdf", _pdf_real(), "application/pdf")},
    )

    assert db_session.query(OrdemProducao).count() == 0
