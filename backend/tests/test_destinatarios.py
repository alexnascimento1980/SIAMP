from app.core.security import gerar_hash_senha
from app.models.usuario import Usuario


def _login(client, usuario):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 200


def _criar_admin(db_session, email="admin-dest@siamp.test"):
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


def test_operador_nao_pode_listar_destinatarios(client, usuario_teste):
    _login(client, usuario_teste)
    res = client.get("/api/v1/destinatarios/")
    assert res.status_code == 403


def test_admin_cria_lista_edita_e_remove_destinatario(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.post(
        "/api/v1/destinatarios/",
        json={"email": "Gerente@Empresa.com", "nome": "Gerente de Produção"},
    )
    assert res.status_code == 201, res.text
    destinatario = res.json()
    # E-mail é normalizado para minúsculas.
    assert destinatario["email"] == "gerente@empresa.com"

    # Duplicado (mesmo com case diferente) -> 409
    res_dup = client.post(
        "/api/v1/destinatarios/", json={"email": "gerente@empresa.com"}
    )
    assert res_dup.status_code == 409

    listagem = client.get("/api/v1/destinatarios/").json()
    assert any(d["id"] == destinatario["id"] for d in listagem)

    # Desativa
    res_edit = client.patch(
        f"/api/v1/destinatarios/{destinatario['id']}", json={"ativo": False}
    )
    assert res_edit.status_code == 200
    assert res_edit.json()["ativo"] is False

    listagem_ativos = client.get("/api/v1/destinatarios/").json()
    assert not any(d["id"] == destinatario["id"] for d in listagem_ativos)

    listagem_todos = client.get("/api/v1/destinatarios/?incluir_inativos=true").json()
    assert any(d["id"] == destinatario["id"] for d in listagem_todos)

    # Remove de vez
    res_del = client.delete(f"/api/v1/destinatarios/{destinatario['id']}")
    assert res_del.status_code == 204

    listagem_final = client.get("/api/v1/destinatarios/?incluir_inativos=true").json()
    assert not any(d["id"] == destinatario["id"] for d in listagem_final)


def test_email_invalido_e_rejeitado(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    res = client.post("/api/v1/destinatarios/", json={"email": "nao-e-um-email"})
    assert res.status_code == 422


def test_editar_destinatario_inexistente_retorna_404(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    res = client.patch("/api/v1/destinatarios/99999", json={"ativo": False})
    assert res.status_code == 404
