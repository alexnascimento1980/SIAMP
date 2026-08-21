from app.models.usuario import Usuario
from app.core.security import gerar_hash_senha


def _login(client, usuario):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 200


def test_operador_nao_pode_criar_peca(client, usuario_teste):
    _login(client, usuario_teste)
    res = client.post(
        "/api/v1/produtos/",
        json={"codigo": "T1", "descricao": "Teste", "ciclo_padrao": 10.0},
    )
    assert res.status_code == 403


def _criar_admin(db_session, email="admin@siamp.test"):
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


def test_admin_cria_edita_e_desativa_peca(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.post(
        "/api/v1/produtos/",
        json={
            "codigo": "T1",
            "descricao": "Peça de teste",
            "ciclo_padrao": 12.5,
            "cavidades": 2,
        },
    )
    assert res.status_code == 201, res.text
    produto = res.json()
    assert produto["codigo"] == "T1"
    assert produto["ativo"] is True

    # Código duplicado -> 409
    res_dup = client.post(
        "/api/v1/produtos/",
        json={"codigo": "T1", "descricao": "Outra descrição", "ciclo_padrao": 5.0, "cavidades": 1},
    )
    assert res_dup.status_code == 409

    # Edita descrição e ciclo
    res_edit = client.patch(
        f"/api/v1/produtos/{produto['id']}",
        json={"descricao": "Peça de teste (revisada)", "ciclo_padrao": 15.0},
    )
    assert res_edit.status_code == 200
    editado = res_edit.json()
    assert editado["descricao"] == "Peça de teste (revisada)"
    assert editado["ciclo_padrao"] == 15.0
    assert editado["codigo"] == "T1"  # código não muda no update

    # Desativa
    res_desativa = client.patch(
        f"/api/v1/produtos/{produto['id']}", json={"ativo": False}
    )
    assert res_desativa.status_code == 200
    assert res_desativa.json()["ativo"] is False

    # Some da listagem padrão, mas aparece com incluir_inativas=true
    listagem = client.get("/api/v1/produtos/").json()
    assert not any(p["id"] == produto["id"] for p in listagem)

    listagem_completa = client.get("/api/v1/produtos/?incluir_inativas=true").json()
    assert any(p["id"] == produto["id"] for p in listagem_completa)


def test_editar_peca_inexistente_retorna_404(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.patch("/api/v1/produtos/99999", json={"descricao": "Inexistente"})
    assert res.status_code == 404


def test_criar_peca_sem_ciclo_padrao_e_rejeitado(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    res = client.post(
        "/api/v1/produtos/",
        json={"codigo": "SEM-CICLO", "descricao": "Peça sem ciclo", "cavidades": 2},
    )
    assert res.status_code == 422


def test_criar_peca_sem_cavidades_e_rejeitado(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    res = client.post(
        "/api/v1/produtos/",
        json={"codigo": "SEM-CAV", "descricao": "Peça sem cavidades", "ciclo_padrao": 10.0},
    )
    assert res.status_code == 422
