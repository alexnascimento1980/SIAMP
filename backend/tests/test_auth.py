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


def test_login_define_cookie_httponly(client, usuario_teste):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario_teste.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 200
    assert "siamp_token" in res.cookies

    cookie_header = res.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie_header
    assert "samesite=lax" in cookie_header.lower()


def test_rota_protegida_funciona_somente_com_cookie(client, usuario_teste):
    # Login via TestClient já grava o cookie no client (cookie jar).
    login = client.post(
        "/api/v1/auth/login",
        data={"username": usuario_teste.email, "password": "senha-forte-123"},
    )
    assert login.status_code == 200

    # Sem header Authorization: deve autenticar só pelo cookie.
    res = client.get("/api/v1/maquinas/")
    assert res.status_code == 200


def test_logout_remove_cookie_e_bloqueia_acesso(client, usuario_teste):
    client.post(
        "/api/v1/auth/login",
        data={"username": usuario_teste.email, "password": "senha-forte-123"},
    )
    assert client.get("/api/v1/maquinas/").status_code == 200

    res_logout = client.post("/api/v1/auth/logout")
    assert res_logout.status_code == 200

    res = client.get("/api/v1/maquinas/")
    assert res.status_code == 401


def test_login_bloqueia_apos_5_tentativas_por_minuto(client, usuario_teste):
    for _ in range(5):
        res = client.post(
            "/api/v1/auth/login",
            data={"username": usuario_teste.email, "password": "senha-errada"},
        )
        assert res.status_code == 401

    # 6ª tentativa no mesmo minuto/IP deve ser bloqueada pelo rate limit.
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario_teste.email, "password": "senha-errada"},
    )
    assert res.status_code == 429
