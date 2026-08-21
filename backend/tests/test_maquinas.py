from datetime import time

from app.core.security import gerar_hash_senha
from app.models.maquina import Maquina
from app.models.registro_turno import RegistroHorario
from app.models.turno import Turno
from app.models.usuario import Usuario


def _login(client, usuario):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 200


def _criar_admin(db_session, email="admin-maq@siamp.test"):
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


def test_criar_maquina_sem_cavidades_e_ciclo(client, db_session):
    # Cavidades/ciclo padrão deixaram de ser obrigatórios na Máquina -
    # a fonte de verdade passou a ser a Peça.
    admin = _criar_admin(db_session)
    _login(client, admin)
    res = client.post(
        "/api/v1/maquinas/",
        json={"numero_maquina": "9", "descricao": "Injetora sem ciclo cadastrado"},
    )
    assert res.status_code == 201, res.text
    assert res.json()["cavidades"] is None
    assert res.json()["ciclo_padrao"] is None


def test_excluir_maquina_sem_registros(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    maquina_id = client.post(
        "/api/v1/maquinas/", json={"numero_maquina": "10", "descricao": "Descartável"}
    ).json()["id"]

    res = client.delete(f"/api/v1/maquinas/{maquina_id}")
    assert res.status_code == 204

    listagem = client.get("/api/v1/maquinas/?incluir_inativas=true").json()
    assert not any(m["id"] == maquina_id for m in listagem)


def test_excluir_maquina_com_registros_e_bloqueado(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    maquina = Maquina(numero_maquina="11", descricao="Em uso", ativo=True)
    db_session.add(maquina)
    db_session.commit()
    db_session.refresh(maquina)

    turno = Turno(
        nome_turno="1º Turno",
        responsavel_nome="Teste",
        status_assinatura="ASSINADO_DIGITALMENTE",
    )
    db_session.add(turno)
    db_session.flush()
    db_session.add(
        RegistroHorario(
            turno_id=turno.id,
            maquina_id=maquina.id,
            hora_referencia=time(8, 0),
            prod_executada=100,
        )
    )
    db_session.commit()

    res = client.delete(f"/api/v1/maquinas/{maquina.id}")
    assert res.status_code == 409
    assert "istórico" in res.json()["detail"] or "produção" in res.json()["detail"]


def test_excluir_maquina_inexistente_retorna_404(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    res = client.delete("/api/v1/maquinas/99999")
    assert res.status_code == 404
