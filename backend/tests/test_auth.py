def test_login_com_credenciais_validas(client, usuario_teste):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario_teste.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_com_senha_invalida(client, usuario_teste):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario_teste.email, "password": "senha-errada"},
    )
    assert res.status_code == 401


def test_rota_protegida_sem_token(client):
    res = client.get("/api/v1/maquinas/")
    assert res.status_code == 401


def test_rota_protegida_com_token(client, usuario_teste):
    login = client.post(
        "/api/v1/auth/login",
        data={"username": usuario_teste.email, "password": "senha-forte-123"},
    )
    token = login.json()["access_token"]

    res = client.get(
        "/api/v1/maquinas/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
