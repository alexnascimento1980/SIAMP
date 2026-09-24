"""Pedido do usuário (reunião com PCP/coordenação de produção):
Operador e Supervisor perdem acesso de ESCRITA a Ordens de Produção e
Peças - passa a ser exclusivo de ADMIN. A LEITURA (listar) continua
aberta a todo mundo de propósito: o dropdown de seleção no apontamento
de produção depende dela, e o Dashboard mostra o comparativo de OPs a
qualquer perfil (confirmado com o usuário antes de implementar)."""
from app.core.security import gerar_hash_senha
from app.models.produto import Produto
from app.models.usuario import Usuario


def _login(client, usuario):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 200


def _criar_usuario(db_session, perfil, email):
    usuario = Usuario(
        nome=f"Teste {perfil}", email=email,
        senha_hash=gerar_hash_senha("senha-forte-123"), perfil=perfil, ativo=True,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    return usuario


def _criar_peca(db_session, codigo="PECA-TESTE-OP"):
    peca = Produto(codigo=codigo, descricao="Peça de teste", ciclo_padrao=10.0, cavidades=2)
    db_session.add(peca)
    db_session.commit()
    db_session.refresh(peca)
    return peca


# --- Ordens de Produção ---------------------------------------------------


def test_supervisor_nao_pode_criar_op(client, db_session):
    supervisor = _criar_usuario(db_session, "SUPERVISOR", "sup-op@siamp.test")
    peca = _criar_peca(db_session)
    _login(client, supervisor)
    res = client.post(
        "/api/v1/ordens-producao/",
        json={
            "numero_op": "OP-TESTE-1",
            "produto_id": peca.id,
            "quantidade_a_produzir": 100,
            "periodo_inicio": "2026-01-01",
            "periodo_fim": "2026-01-31",
        },
    )
    assert res.status_code == 403


def test_operador_nao_pode_criar_op(client, db_session, usuario_teste):
    peca = _criar_peca(db_session, codigo="PECA-TESTE-OP-2")
    _login(client, usuario_teste)
    res = client.post(
        "/api/v1/ordens-producao/",
        json={
            "numero_op": "OP-TESTE-2",
            "produto_id": peca.id,
            "quantidade_a_produzir": 100,
            "periodo_inicio": "2026-01-01",
            "periodo_fim": "2026-01-31",
        },
    )
    assert res.status_code == 403


def test_supervisor_e_operador_ainda_conseguem_listar_ops(client, db_session, usuario_teste):
    # Leitura continua aberta - o dropdown de OP no apontamento
    # depende disso para todo mundo, não só ADMIN.
    supervisor = _criar_usuario(db_session, "SUPERVISOR", "sup-op-listar@siamp.test")

    _login(client, supervisor)
    assert client.get("/api/v1/ordens-producao/").status_code == 200

    _login(client, usuario_teste)
    assert client.get("/api/v1/ordens-producao/").status_code == 200


# --- Peças ------------------------------------------------------------------


def test_supervisor_nao_pode_criar_peca(client, db_session):
    supervisor = _criar_usuario(db_session, "SUPERVISOR", "sup-peca@siamp.test")
    _login(client, supervisor)
    res = client.post(
        "/api/v1/produtos/",
        json={"codigo": "SUP-TESTE", "descricao": "Teste", "ciclo_padrao": 10.0, "cavidades": 2},
    )
    assert res.status_code == 403


def test_supervisor_e_operador_ainda_conseguem_listar_pecas(client, db_session, usuario_teste):
    supervisor = _criar_usuario(db_session, "SUPERVISOR", "sup-peca-listar@siamp.test")

    _login(client, supervisor)
    assert client.get("/api/v1/produtos/").status_code == 200

    _login(client, usuario_teste)
    assert client.get("/api/v1/produtos/").status_code == 200
