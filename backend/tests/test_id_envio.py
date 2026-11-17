"""Fechamento idempotente por id_envio (base da fila offline do app)."""

import uuid

from app.models.maquina import Maquina
from app.models.produto import Produto
from app.models.turno import Turno
from app.services import lancamento_service


def _login(client, usuario):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 200


def _payload(db_session, id_envio=None):
    maquina = db_session.query(Maquina).filter(Maquina.numero_maquina == "1").first()
    peca = db_session.query(Produto).filter(Produto.codigo == "PL1").first()
    if maquina is None:
        maquina = Maquina(numero_maquina="1", descricao="Injetora 1", ativo=True)
        peca = Produto(codigo="PL1", descricao="Peça", ciclo_padrao=10.0, cavidades=2)
        db_session.add_all([maquina, peca])
        db_session.commit()
        db_session.refresh(maquina)
        db_session.refresh(peca)
    corpo = {
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
    if id_envio is not None:
        corpo["id_envio"] = id_envio
    return corpo


def _contar_turnos(db_session):
    db_session.expire_all()
    return db_session.query(Turno).count()


def test_reenvio_do_mesmo_fechamento_nao_duplica_o_turno(client, db_session, usuario_teste, monkeypatch):
    chamadas = []
    monkeypatch.setattr(lancamento_service, "agendar_email_relatorio", lambda *a, **k: chamadas.append(1) or True)
    _login(client, usuario_teste)
    corpo = _payload(db_session, str(uuid.uuid4()))

    primeiro = client.post("/api/v1/turnos/lancamento", json=corpo)
    segundo = client.post("/api/v1/turnos/lancamento", json=corpo)

    assert primeiro.status_code == 201, primeiro.text
    assert segundo.status_code == 201, segundo.text
    assert segundo.json()["turno_id"] == primeiro.json()["turno_id"]
    assert segundo.json()["reenvio"] is True
    assert "reenvio" not in primeiro.json()
    assert segundo.json()["kpis"]["total_produzido"] == 100
    assert _contar_turnos(db_session) == 1
    assert len(chamadas) == 1  # e-mail/PDF só no primeiro envio


def test_envios_com_ids_diferentes_geram_turnos_diferentes(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    a = client.post("/api/v1/turnos/lancamento", json=_payload(db_session, str(uuid.uuid4())))
    b = client.post("/api/v1/turnos/lancamento", json=_payload(db_session, str(uuid.uuid4())))
    assert a.json()["turno_id"] != b.json()["turno_id"]
    assert _contar_turnos(db_session) == 2


def test_sem_id_envio_continua_funcionando_como_antes(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    corpo = _payload(db_session)
    a = client.post("/api/v1/turnos/lancamento", json=corpo)
    b = client.post("/api/v1/turnos/lancamento", json=corpo)
    assert a.status_code == b.status_code == 201
    assert a.json()["turno_id"] != b.json()["turno_id"]
    assert "reenvio" not in b.json()


def test_id_envio_invalido_e_rejeitado(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    res = client.post("/api/v1/turnos/lancamento", json=_payload(db_session, "isso-nao-e-um-uuid"))
    assert res.status_code == 422


def test_id_envio_e_normalizado_para_minusculas(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    id_envio = str(uuid.uuid4())
    a = client.post("/api/v1/turnos/lancamento", json=_payload(db_session, id_envio.upper()))
    b = client.post("/api/v1/turnos/lancamento", json=_payload(db_session, id_envio.lower()))
    assert b.json()["turno_id"] == a.json()["turno_id"]
    assert _contar_turnos(db_session) == 1


def test_reenvio_do_fechamento_de_rascunho_e_idempotente(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    rascunho = client.post(
        "/api/v1/turnos/lancamento/rascunho",
        json={"nome_turno": "1º Turno", "responsavel_nome": "Líder Teste", "lancamentos": []},
    )
    turno_id = rascunho.json()["turno_id"]
    corpo = _payload(db_session, str(uuid.uuid4()))

    primeiro = client.post(f"/api/v1/turnos/lancamento/{turno_id}/fechar", json=corpo)
    segundo = client.post(f"/api/v1/turnos/lancamento/{turno_id}/fechar", json=corpo)

    assert primeiro.status_code == 200, primeiro.text
    assert segundo.status_code == 200, segundo.text
    assert segundo.json()["turno_id"] == turno_id
    assert segundo.json()["reenvio"] is True
    assert _contar_turnos(db_session) == 1


def test_fechar_rascunho_ja_fechado_sem_id_envio_continua_dando_erro(client, db_session, usuario_teste):
    _login(client, usuario_teste)
    turno_id = client.post(
        "/api/v1/turnos/lancamento/rascunho",
        json={"nome_turno": "1º Turno", "responsavel_nome": "Líder Teste", "lancamentos": []},
    ).json()["turno_id"]
    corpo = _payload(db_session)
    assert client.post(f"/api/v1/turnos/lancamento/{turno_id}/fechar", json=corpo).status_code == 200
    assert client.post(f"/api/v1/turnos/lancamento/{turno_id}/fechar", json=corpo).status_code == 400


def test_corrida_de_dois_envios_iguais_devolve_o_turno_vencedor(client, db_session, usuario_teste, monkeypatch):
    """Simula o segundo envio passando pela checagem inicial antes de o
    primeiro commitar: o índice único barra e o serviço devolve o turno
    já gravado, em vez de 500."""
    _login(client, usuario_teste)
    corpo = _payload(db_session, str(uuid.uuid4()))
    primeiro = client.post("/api/v1/turnos/lancamento", json=corpo)

    original = lancamento_service._turno_ja_registrado
    chamadas = {"n": 0}

    def _cega_na_primeira(db, id_envio):
        chamadas["n"] += 1
        return None if chamadas["n"] == 1 else original(db, id_envio)

    monkeypatch.setattr(lancamento_service, "_turno_ja_registrado", _cega_na_primeira)
    segundo = client.post("/api/v1/turnos/lancamento", json=corpo)

    assert segundo.status_code == 201, segundo.text
    assert segundo.json()["turno_id"] == primeiro.json()["turno_id"]
    assert segundo.json()["reenvio"] is True
    assert _contar_turnos(db_session) == 1


# --- data do turno quando o envio atrasa (fila offline) -----------------


def _data_do_turno(client, turno_id):
    return client.get(f"/api/v1/turnos/{turno_id}").json()["data_registro"][:16]


def _congelar_agora(monkeypatch, momento):
    from app.core import timezone as timezone_mod

    monkeypatch.setattr(timezone_mod, "agora_brasilia", lambda: momento)


def test_fechado_em_do_cliente_define_a_data_quando_o_envio_atrasa(client, db_session, usuario_teste, monkeypatch):
    from datetime import datetime

    _congelar_agora(monkeypatch, datetime(2026, 9, 16, 9, 0))  # servidor recebe às 09h de 16/09
    _login(client, usuario_teste)
    corpo = _payload(db_session, str(uuid.uuid4()))
    corpo["fechado_em"] = "2026-09-15T20:30:00Z"  # operador tocou às 17h30 (Brasília) de 15/09

    res = client.post("/api/v1/turnos/lancamento", json=corpo)

    assert res.status_code == 201, res.text
    assert _data_do_turno(client, res.json()["turno_id"]) == "2026-09-15T17:30"


def test_fechado_em_no_futuro_e_ignorado(client, db_session, usuario_teste, monkeypatch):
    from datetime import datetime

    _congelar_agora(monkeypatch, datetime(2026, 9, 16, 9, 0))
    _login(client, usuario_teste)
    corpo = _payload(db_session, str(uuid.uuid4()))
    corpo["fechado_em"] = "2026-09-20T12:00:00Z"  # relógio do celular adiantado

    res = client.post("/api/v1/turnos/lancamento", json=corpo)

    assert res.status_code == 201, res.text
    assert _data_do_turno(client, res.json()["turno_id"]) == "2026-09-16T09:00"


def test_fechado_em_muito_antigo_e_ignorado(client, db_session, usuario_teste, monkeypatch):
    from datetime import datetime

    _congelar_agora(monkeypatch, datetime(2026, 9, 16, 9, 0))
    _login(client, usuario_teste)
    corpo = _payload(db_session, str(uuid.uuid4()))
    corpo["fechado_em"] = "2026-08-01T12:00:00Z"

    res = client.post("/api/v1/turnos/lancamento", json=corpo)

    assert res.status_code == 201, res.text
    assert _data_do_turno(client, res.json()["turno_id"]) == "2026-09-16T09:00"


def test_3o_turno_enviado_depois_usa_o_horario_do_toque_para_o_ajuste_de_madrugada(
    client, db_session, usuario_teste, monkeypatch
):
    from datetime import datetime

    _congelar_agora(monkeypatch, datetime(2026, 9, 15, 14, 0))  # chega à tarde
    _login(client, usuario_teste)
    corpo = _payload(db_session, str(uuid.uuid4()))
    corpo["lancamentos"][0]["horario_inicio"] = "22:00"
    corpo["lancamentos"][0]["horario_fim"] = "23:30"
    corpo["fechado_em"] = "2026-09-15T07:00:00Z"  # tocou às 04h de 15/09 (Brasília), turno começou em 14/09

    res = client.post("/api/v1/turnos/lancamento", json=corpo)

    assert res.status_code == 201, res.text
    assert _data_do_turno(client, res.json()["turno_id"]) == "2026-09-14T04:00"
