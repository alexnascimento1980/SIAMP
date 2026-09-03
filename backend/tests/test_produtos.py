from app.core.security import gerar_hash_senha
from app.models.usuario import Usuario


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


def test_editar_codigo_da_peca_com_sucesso(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    produto = client.post(
        "/api/v1/produtos/",
        json={"codigo": "COD-ANTIGO", "descricao": "Peça", "ciclo_padrao": 10.0, "cavidades": 2},
    ).json()

    res = client.patch(
        f"/api/v1/produtos/{produto['id']}", json={"codigo": "COD-NOVO"}
    )
    assert res.status_code == 200, res.text
    assert res.json()["codigo"] == "COD-NOVO"


def test_editar_codigo_para_um_ja_existente_e_rejeitado(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    client.post(
        "/api/v1/produtos/",
        json={"codigo": "COD-A", "descricao": "Peça A", "ciclo_padrao": 10.0, "cavidades": 2},
    )
    produto_b = client.post(
        "/api/v1/produtos/",
        json={"codigo": "COD-B", "descricao": "Peça B", "ciclo_padrao": 8.0, "cavidades": 4},
    ).json()

    res = client.patch(f"/api/v1/produtos/{produto_b['id']}", json={"codigo": "COD-A"})
    assert res.status_code == 409


# --- Excluir peça ---------------------------------------------------


def test_admin_exclui_peca_sem_historico(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    produto_id = client.post(
        "/api/v1/produtos/",
        json={"codigo": "SEM-USO", "descricao": "Peça sem uso", "ciclo_padrao": 10.0, "cavidades": 2},
    ).json()["id"]

    res = client.delete(f"/api/v1/produtos/{produto_id}")
    assert res.status_code == 204

    # confirma que sumiu de verdade, não só desativou
    res_listagem = client.get("/api/v1/produtos/")
    assert not any(p["id"] == produto_id for p in res_listagem.json())


def test_excluir_peca_com_lancamento_e_bloqueado(client, db_session):
    from app.models.maquina import Maquina

    admin = _criar_admin(db_session)
    _login(client, admin)
    produto_id = client.post(
        "/api/v1/produtos/",
        json={"codigo": "COM-USO", "descricao": "Peça com uso", "ciclo_padrao": 10.0, "cavidades": 2},
    ).json()["id"]

    maquina = Maquina(numero_maquina="1", descricao="Injetora 1", ativo=True)
    db_session.add(maquina)
    db_session.commit()
    db_session.refresh(maquina)

    client.post(
        "/api/v1/turnos/lancamento",
        json={
            "nome_turno": "1º Turno",
            "responsavel_nome": "Líder Teste",
            "lancamentos": [
                {
                    "numero_maquina": maquina.numero_maquina,
                    "tipo": "PRODUCAO",
                    "horario_inicio": "05:00",
                    "horario_fim": "06:00",
                    "produto_id": produto_id,
                    "quantidade": 100,
                }
            ],
        },
    )

    res = client.delete(f"/api/v1/produtos/{produto_id}")
    assert res.status_code == 409
    assert "Desativar" in res.json()["detail"]

    # a peça continua existindo, só não foi excluída
    res_listagem = client.get("/api/v1/produtos/")
    assert any(p["id"] == produto_id for p in res_listagem.json())


def test_excluir_peca_com_registro_horario_e_bloqueado(client, db_session):
    from datetime import time

    from app.models.maquina import Maquina
    from app.models.registro_turno import RegistroHorario
    from app.models.turno import Turno

    admin = _criar_admin(db_session)
    _login(client, admin)
    produto_id = client.post(
        "/api/v1/produtos/",
        json={"codigo": "MODELO-ANTIGO", "descricao": "Peça modelo antigo", "ciclo_padrao": 10.0, "cavidades": 2},
    ).json()["id"]

    maquina = Maquina(numero_maquina="1", descricao="Injetora 1", ativo=True)
    turno = Turno(
        nome_turno="1º Turno", responsavel_nome="Líder Teste",
        status_assinatura="ASSINADO_DIGITALMENTE", modelo_apontamento="HORARIO",
    )
    db_session.add_all([maquina, turno])
    db_session.commit()
    db_session.refresh(maquina)
    db_session.refresh(turno)
    db_session.add(RegistroHorario(
        turno_id=turno.id, maquina_id=maquina.id, produto_id=produto_id,
        hora_referencia=time(5, 0), prod_executada=100,
    ))
    db_session.commit()

    res = client.delete(f"/api/v1/produtos/{produto_id}")
    assert res.status_code == 409


def test_excluir_peca_inexistente_retorna_404(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.delete("/api/v1/produtos/99999")
    assert res.status_code == 404


def test_operador_nao_pode_excluir_peca(client, db_session, usuario_teste):
    admin = _criar_admin(db_session)
    _login(client, admin)
    produto_id = client.post(
        "/api/v1/produtos/",
        json={"codigo": "PROTEGIDA", "descricao": "Peça protegida", "ciclo_padrao": 10.0, "cavidades": 2},
    ).json()["id"]

    client.get("/api/v1/auth/logout")
    _login(client, usuario_teste)

    res = client.delete(f"/api/v1/produtos/{produto_id}")
    assert res.status_code == 403
