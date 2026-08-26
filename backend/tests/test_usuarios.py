from app.core.security import gerar_hash_senha, verificar_senha
from app.models.usuario import Usuario


def _login(client, usuario, senha="senha-forte-123"):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario.email, "password": senha},
    )
    assert res.status_code == 200


def _criar_admin(db_session, email="admin-usuarios@siamp.test"):
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


def _criar_operador(db_session, email="operador-usuarios@siamp.test"):
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


def test_admin_lista_usuarios(client, db_session):
    admin = _criar_admin(db_session)
    _criar_operador(db_session)
    _login(client, admin)

    res = client.get("/api/v1/usuarios/")
    assert res.status_code == 200
    nomes = [u["nome"] for u in res.json()]
    assert "Admin Teste" in nomes
    assert "Operador Teste" in nomes


def test_operador_nao_pode_listar_usuarios(client, db_session):
    op = _criar_operador(db_session)
    _login(client, op)

    res = client.get("/api/v1/usuarios/")
    assert res.status_code == 403


def test_admin_cria_usuario(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.post(
        "/api/v1/usuarios/",
        json={
            "nome": "Novo Usuário",
            "email": "novo@empresa.com",
            "senha": "senha12345",
            "perfil": "SUPERVISOR",
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["perfil"] == "SUPERVISOR"


def test_criar_usuario_com_email_duplicado_e_rejeitado(client, db_session):
    admin = _criar_admin(db_session)
    _criar_operador(db_session, email="duplicado@empresa.com")
    _login(client, admin)

    res = client.post(
        "/api/v1/usuarios/",
        json={
            "nome": "Outro",
            "email": "duplicado@empresa.com",
            "senha": "senha12345",
        },
    )
    assert res.status_code == 409


def test_admin_desativa_e_reativa_usuario(client, db_session):
    admin = _criar_admin(db_session)
    op = _criar_operador(db_session)
    _login(client, admin)

    res = client.patch(f"/api/v1/usuarios/{op.id}/status", json={"ativo": False})
    assert res.status_code == 200
    assert res.json()["ativo"] is False

    res = client.patch(f"/api/v1/usuarios/{op.id}/status", json={"ativo": True})
    assert res.status_code == 200
    assert res.json()["ativo"] is True


def test_admin_nao_pode_desativar_a_propria_conta(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.patch(f"/api/v1/usuarios/{admin.id}/status", json={"ativo": False})
    assert res.status_code == 400


# --- Reset de senha ----------------------------------------------------


def test_admin_reseta_senha_de_outro_usuario(client, db_session):
    admin = _criar_admin(db_session)
    op = _criar_operador(db_session)
    _login(client, admin)

    res = client.patch(
        f"/api/v1/usuarios/{op.id}/senha", json={"nova_senha": "senha-nova-123"}
    )
    assert res.status_code == 200, res.text

    db_session.refresh(op)
    assert verificar_senha("senha-nova-123", op.senha_hash)
    assert not verificar_senha("senha-forte-123", op.senha_hash)


def test_login_funciona_com_a_senha_nova_apos_reset(client, db_session):
    admin = _criar_admin(db_session)
    op = _criar_operador(db_session)
    _login(client, admin)

    client.patch(f"/api/v1/usuarios/{op.id}/senha", json={"nova_senha": "senha-nova-123"})

    res = client.post(
        "/api/v1/auth/login",
        data={"username": op.email, "password": "senha-nova-123"},
    )
    assert res.status_code == 200

    res = client.post(
        "/api/v1/auth/login",
        data={"username": op.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 401


def test_resposta_do_reset_nao_expoe_hash_nem_senha(client, db_session):
    admin = _criar_admin(db_session)
    op = _criar_operador(db_session)
    _login(client, admin)

    res = client.patch(
        f"/api/v1/usuarios/{op.id}/senha", json={"nova_senha": "senha-nova-123"}
    )
    corpo = res.json()
    assert "senha_hash" not in corpo
    assert "senha" not in corpo
    assert "nova_senha" not in corpo


def test_operador_nao_pode_resetar_senha_de_ninguem(client, db_session):
    op1 = _criar_operador(db_session, email="op1@siamp.test")
    op2 = _criar_operador(db_session, email="op2@siamp.test")
    _login(client, op1)

    res = client.patch(
        f"/api/v1/usuarios/{op2.id}/senha", json={"nova_senha": "senha-nova-123"}
    )
    assert res.status_code == 403


def test_resetar_senha_de_usuario_inexistente_retorna_404(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.patch("/api/v1/usuarios/99999/senha", json={"nova_senha": "senha-nova-123"})
    assert res.status_code == 404


def test_resetar_senha_curta_e_rejeitada(client, db_session):
    admin = _criar_admin(db_session)
    op = _criar_operador(db_session)
    _login(client, admin)

    res = client.patch(f"/api/v1/usuarios/{op.id}/senha", json={"nova_senha": "curta"})
    assert res.status_code == 422


def test_admin_pode_resetar_a_propria_senha(client, db_session):
    # Diferente da desativação de conta, resetar a própria senha não
    # tem risco de "travar o próprio acesso" (o admin já está
    # autenticado ao fazer isso) - não há motivo para bloquear.
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.patch(
        f"/api/v1/usuarios/{admin.id}/senha", json={"nova_senha": "senha-nova-admin"}
    )
    assert res.status_code == 200
