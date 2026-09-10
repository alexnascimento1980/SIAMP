
from app.core.security import gerar_hash_senha
from app.models.maquina import Maquina
from app.models.turno import Turno
from app.models.usuario import Usuario


def _login(client, usuario):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 200


def _criar_usuario(db_session, email="operador-paradas@siamp.test", perfil="OPERADOR"):
    usuario = Usuario(
        nome="Usuário Teste",
        email=email,
        senha_hash=gerar_hash_senha("senha-forte-123"),
        perfil=perfil,
        ativo=True,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    return usuario


def _criar_turno_e_maquina(db_session):
    turno = Turno(nome_turno="1º Turno", responsavel_nome="Teste", status_assinatura="EM_ANDAMENTO")
    maquina = Maquina(numero_maquina="1", descricao="Injetora Teste", ativo=True)
    db_session.add_all([turno, maquina])
    db_session.commit()
    db_session.refresh(turno)
    db_session.refresh(maquina)
    return turno, maquina


def test_registrar_parada_com_sucesso(client, db_session):
    usuario = _criar_usuario(db_session)
    turno, maquina = _criar_turno_e_maquina(db_session)
    _login(client, usuario)

    res = client.post(
        "/api/v1/paradas/",
        json={
            "turno_id": turno.id,
            "maquina_id": maquina.id,
            "inicio": "08:00",
            "fim": "08:30",
            "motivo": "Troca de molde",
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "registrado"


def test_usuario_id_do_payload_e_ignorado_usa_sempre_o_autenticado(client, db_session):
    # Correção de segurança: usuario_id não é mais aceito no payload -
    # antes existia como campo opcional, e o endpoint usava
    # "dados.usuario_id or usuario.id" (confiando cegamente no valor
    # do cliente quando enviado) - qualquer usuário autenticado podia
    # atribuir uma parada a outra pessoa, corrompendo a trilha de
    # auditoria. Confirma que o campo nem é mais aceito pelo schema
    # (extra='ignore' é o padrão do Pydantic - o campo desconhecido é
    # silenciosamente descartado, não gera erro de validação) e que o
    # registro salvo sempre usa o usuário de verdade.
    outro_usuario = _criar_usuario(db_session, email="outro@siamp.test")
    usuario = _criar_usuario(db_session, email="autenticado@siamp.test")
    turno, maquina = _criar_turno_e_maquina(db_session)
    _login(client, usuario)

    res = client.post(
        "/api/v1/paradas/",
        json={
            "turno_id": turno.id,
            "maquina_id": maquina.id,
            "inicio": "08:00",
            "motivo": "Sensor travado",
            "usuario_id": outro_usuario.id,
        },
    )
    assert res.status_code == 201, res.text

    from app.models.parada import Parada

    parada = db_session.query(Parada).filter(Parada.id == res.json()["id"]).first()
    assert parada.usuario_id == usuario.id
    assert parada.usuario_id != outro_usuario.id


def test_listar_paradas_do_turno(client, db_session):
    usuario = _criar_usuario(db_session)
    turno, maquina = _criar_turno_e_maquina(db_session)
    _login(client, usuario)

    client.post(
        "/api/v1/paradas/",
        json={
            "turno_id": turno.id,
            "maquina_id": maquina.id,
            "inicio": "08:00",
            "motivo": "Troca de molde",
        },
    )

    res = client.get(f"/api/v1/paradas/turno/{turno.id}")
    assert res.status_code == 200
    assert len(res.json()) == 1
