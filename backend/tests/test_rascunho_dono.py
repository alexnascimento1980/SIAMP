"""Quem pode continuar editando/fechando um RASCUNHO de turno.

Regra: o próprio autor, SUPERVISOR ou ADMIN. Antes, qualquer usuário
logado (inclusive OPERADOR) podia atualizar ou fechar o rascunho de
outra pessoa só conhecendo o id. Vale para os dois modelos de
apontamento (lançamentos livres e por hora).
"""

from app.core.security import gerar_hash_senha
from app.models.maquina import Maquina
from app.models.produto import Produto
from app.models.turno import Turno
from app.models.usuario import Usuario

SENHA = "senha-forte-123"


def _criar_usuario(db_session, email, perfil, nome=None):
    usuario = Usuario(
        nome=nome or f"{perfil.title()} {email}",
        email=email,
        senha_hash=gerar_hash_senha(SENHA),
        perfil=perfil,
        ativo=True,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    return usuario


def _login(client, usuario):
    # O TestClient guarda um único cookie de sessão: limpa antes para
    # alternar entre usuários dentro do mesmo teste.
    client.cookies.clear()
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario.email, "password": SENHA},
    )
    assert res.status_code == 200, res.text


def _criar_maquina_e_peca(db_session):
    maquina = Maquina(numero_maquina="1", descricao="Injetora 1", ativo=True)
    peca = Produto(codigo="PD1", descricao="Peça Dono", ciclo_padrao=10.0, cavidades=2)
    db_session.add_all([maquina, peca])
    db_session.commit()
    db_session.refresh(maquina)
    db_session.refresh(peca)
    return maquina, peca


def _payload_lancamento(maquina, peca, quantidade=200):
    return {
        "nome_turno": "1º Turno",
        "responsavel_nome": "Líder Teste",
        "lancamentos": [
            {
                "numero_maquina": maquina.numero_maquina,
                "tipo": "PRODUCAO",
                "horario_inicio": "05:00",
                "horario_fim": "06:00",
                "produto_id": peca.id,
                "quantidade": quantidade,
            }
        ],
    }


def _criar_rascunho_lancamento(client):
    res = client.post(
        "/api/v1/turnos/lancamento/rascunho",
        json={"nome_turno": "1º Turno", "responsavel_nome": "Líder Teste", "lancamentos": []},
    )
    assert res.status_code == 201, res.text
    return res.json()["turno_id"]


def test_rascunho_grava_o_autor(client, db_session):
    autor = _criar_usuario(db_session, "autor@siamp.test", "OPERADOR")
    _login(client, autor)
    turno_id = _criar_rascunho_lancamento(client)

    turno = db_session.query(Turno).filter(Turno.id == turno_id).one()
    assert turno.criado_por_id == autor.id


def test_fechamento_direto_grava_o_autor(client, db_session):
    autor = _criar_usuario(db_session, "autor@siamp.test", "OPERADOR")
    maquina, peca = _criar_maquina_e_peca(db_session)
    _login(client, autor)

    res = client.post("/api/v1/turnos/lancamento", json=_payload_lancamento(maquina, peca))
    assert res.status_code == 201, res.text

    turno = db_session.query(Turno).filter(Turno.id == res.json()["turno_id"]).one()
    assert turno.criado_por_id == autor.id


def test_autor_atualiza_e_fecha_o_proprio_rascunho(client, db_session):
    autor = _criar_usuario(db_session, "autor@siamp.test", "OPERADOR")
    maquina, peca = _criar_maquina_e_peca(db_session)
    _login(client, autor)
    turno_id = _criar_rascunho_lancamento(client)

    res = client.patch(
        f"/api/v1/turnos/lancamento/rascunho/{turno_id}",
        json=_payload_lancamento(maquina, peca),
    )
    assert res.status_code == 200, res.text

    res = client.post(
        f"/api/v1/turnos/lancamento/{turno_id}/fechar",
        json=_payload_lancamento(maquina, peca),
    )
    assert res.status_code == 200, res.text


def test_outro_operador_nao_atualiza_nem_fecha_rascunho_alheio(client, db_session):
    autor = _criar_usuario(db_session, "autor@siamp.test", "OPERADOR")
    intruso = _criar_usuario(db_session, "intruso@siamp.test", "OPERADOR")
    maquina, peca = _criar_maquina_e_peca(db_session)
    _login(client, autor)
    turno_id = _criar_rascunho_lancamento(client)

    _login(client, intruso)
    res = client.patch(
        f"/api/v1/turnos/lancamento/rascunho/{turno_id}",
        json=_payload_lancamento(maquina, peca),
    )
    assert res.status_code == 403
    res = client.post(
        f"/api/v1/turnos/lancamento/{turno_id}/fechar",
        json=_payload_lancamento(maquina, peca),
    )
    assert res.status_code == 403

    # O rascunho continua intacto e em andamento.
    db_session.expire_all()
    turno = db_session.query(Turno).filter(Turno.id == turno_id).one()
    assert turno.status_assinatura == "EM_ANDAMENTO"
    assert turno.lancamentos == []


def test_supervisor_e_admin_podem_continuar_rascunho_alheio(client, db_session):
    autor = _criar_usuario(db_session, "autor@siamp.test", "OPERADOR")
    supervisor = _criar_usuario(db_session, "sup@siamp.test", "SUPERVISOR")
    admin = _criar_usuario(db_session, "adm@siamp.test", "ADMIN")
    maquina, peca = _criar_maquina_e_peca(db_session)
    _login(client, autor)
    turno_id = _criar_rascunho_lancamento(client)

    for quem in (supervisor, admin):
        _login(client, quem)
        res = client.patch(
            f"/api/v1/turnos/lancamento/rascunho/{turno_id}",
            json=_payload_lancamento(maquina, peca),
        )
        assert res.status_code == 200, (quem.perfil, res.text)

    _login(client, supervisor)
    res = client.post(
        f"/api/v1/turnos/lancamento/{turno_id}/fechar",
        json=_payload_lancamento(maquina, peca),
    )
    assert res.status_code == 200, res.text


def test_rascunho_sem_autor_continua_liberado(client, db_session):
    # Rascunhos criados antes da coluna existir (ou cujo autor foi
    # excluído) ficam com criado_por_id nulo e mantêm o comportamento
    # anterior - senão ninguém poderia concluí-los.
    autor = _criar_usuario(db_session, "autor@siamp.test", "OPERADOR")
    outro = _criar_usuario(db_session, "outro@siamp.test", "OPERADOR")
    maquina, peca = _criar_maquina_e_peca(db_session)
    _login(client, autor)
    turno_id = _criar_rascunho_lancamento(client)

    turno = db_session.query(Turno).filter(Turno.id == turno_id).one()
    turno.criado_por_id = None
    db_session.commit()

    _login(client, outro)
    res = client.patch(
        f"/api/v1/turnos/lancamento/rascunho/{turno_id}",
        json=_payload_lancamento(maquina, peca),
    )
    assert res.status_code == 200, res.text


def test_turno_ja_fechado_continua_respondendo_409_nao_403(client, db_session):
    # A checagem de autoria só vale para rascunho (EM_ANDAMENTO); para
    # turno fechado a resposta continua sendo a de antes.
    autor = _criar_usuario(db_session, "autor@siamp.test", "OPERADOR")
    outro = _criar_usuario(db_session, "outro@siamp.test", "OPERADOR")
    maquina, peca = _criar_maquina_e_peca(db_session)
    _login(client, autor)
    res = client.post("/api/v1/turnos/lancamento", json=_payload_lancamento(maquina, peca))
    turno_id = res.json()["turno_id"]

    _login(client, outro)
    res = client.patch(
        f"/api/v1/turnos/lancamento/rascunho/{turno_id}",
        json=_payload_lancamento(maquina, peca),
    )
    assert res.status_code == 409
