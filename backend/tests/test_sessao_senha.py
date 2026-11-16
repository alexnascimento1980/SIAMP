"""Sessão x senha: reset de senha encerra sessões antigas e a senha
mínima é de 10 caracteres."""

from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings
from app.core.security import gerar_hash_senha
from app.models.usuario import Usuario

SENHA = "senha-forte-123"


def _criar_usuario(db_session, email, perfil="OPERADOR"):
    usuario = Usuario(
        nome=f"{perfil.title()} {email}",
        email=email,
        senha_hash=gerar_hash_senha(SENHA),
        perfil=perfil,
        ativo=True,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    return usuario


def _login_token(client, usuario, senha=SENHA):
    client.cookies.clear()
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario.email, "password": senha},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _me_com_bearer(client, token):
    client.cookies.clear()
    return client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})


def test_reset_de_senha_invalida_o_token_antigo_do_usuario(client, db_session):
    admin = _criar_usuario(db_session, "adm@siamp.test", "ADMIN")
    alvo = _criar_usuario(db_session, "alvo@siamp.test")

    token_antigo = _login_token(client, alvo)
    assert _me_com_bearer(client, token_antigo).status_code == 200

    _login_token(client, admin)
    res = client.patch(
        f"/api/v1/usuarios/{alvo.id}/senha", json={"nova_senha": "outra-senha-forte-1"}
    )
    assert res.status_code == 200, res.text

    # O token emitido antes do reset deixou de valer...
    assert _me_com_bearer(client, token_antigo).status_code == 401
    # ...e a senha nova gera um token que funciona.
    token_novo = _login_token(client, alvo, senha="outra-senha-forte-1")
    assert _me_com_bearer(client, token_novo).status_code == 200


def test_admin_que_reseta_a_propria_senha_continua_logado(client, db_session):
    admin = _criar_usuario(db_session, "adm@siamp.test", "ADMIN")
    token_antigo = _login_token(client, admin)

    res = client.patch(
        f"/api/v1/usuarios/{admin.id}/senha",
        json={"nova_senha": "outra-senha-forte-1"},
        headers={"Authorization": f"Bearer {token_antigo}"},
    )
    assert res.status_code == 200, res.text

    # A resposta renova o cookie de sessão: segue autenticado só pelo cookie.
    assert "siamp_token" in res.cookies
    assert client.get("/api/v1/auth/me").status_code == 200
    # O token anterior, porém, não vale mais.
    assert _me_com_bearer(client, token_antigo).status_code == 401


def test_token_legado_sem_claim_de_versao_continua_valido(client, db_session):
    usuario = _criar_usuario(db_session, "legado@siamp.test")
    token = jwt.encode(
        {
            "sub": usuario.email,
            "perfil": usuario.perfil,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    assert _me_com_bearer(client, token).status_code == 200


def test_senha_minima_de_10_caracteres(client, db_session):
    admin = _criar_usuario(db_session, "adm@siamp.test", "ADMIN")
    alvo = _criar_usuario(db_session, "alvo@siamp.test")
    _login_token(client, admin)

    novo = {"nome": "Fulano", "email": "fulano@empresa.com", "perfil": "OPERADOR"}
    assert client.post("/api/v1/usuarios/", json={**novo, "senha": "123456789"}).status_code == 422
    assert client.post("/api/v1/usuarios/", json={**novo, "senha": "1234567890"}).status_code == 201

    url = f"/api/v1/usuarios/{alvo.id}/senha"
    assert client.patch(url, json={"nova_senha": "123456789"}).status_code == 422
    assert client.patch(url, json={"nova_senha": "1234567890"}).status_code == 200
