from datetime import date

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


# --- Alterar perfil -----------------------------------------------------


def test_admin_altera_perfil_de_operador_para_supervisor(client, db_session):
    admin = _criar_admin(db_session)
    op = _criar_operador(db_session)
    _login(client, admin)

    res = client.patch(f"/api/v1/usuarios/{op.id}/perfil", json={"perfil": "SUPERVISOR"})
    assert res.status_code == 200, res.text
    assert res.json()["perfil"] == "SUPERVISOR"

    db_session.refresh(op)
    assert op.perfil == "SUPERVISOR"


def test_admin_altera_perfil_de_supervisor_para_operador(client, db_session):
    admin = _criar_admin(db_session)
    sup = Usuario(
        nome="Supervisor Teste", email="sup@siamp.test",
        senha_hash=gerar_hash_senha("senha-forte-123"), perfil="SUPERVISOR", ativo=True,
    )
    db_session.add(sup)
    db_session.commit()
    db_session.refresh(sup)
    _login(client, admin)

    res = client.patch(f"/api/v1/usuarios/{sup.id}/perfil", json={"perfil": "OPERADOR"})
    assert res.status_code == 200
    assert res.json()["perfil"] == "OPERADOR"


def test_perfil_invalido_e_rejeitado(client, db_session):
    admin = _criar_admin(db_session)
    op = _criar_operador(db_session)
    _login(client, admin)

    res = client.patch(f"/api/v1/usuarios/{op.id}/perfil", json={"perfil": "GERENTE"})
    assert res.status_code == 422


def test_admin_nao_pode_alterar_o_proprio_perfil(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.patch(f"/api/v1/usuarios/{admin.id}/perfil", json={"perfil": "OPERADOR"})
    assert res.status_code == 400


def test_admin_pode_reenviar_o_mesmo_perfil_da_propria_conta(client, db_session):
    # Reenviar o MESMO perfil que já tem não é uma troca de verdade -
    # não há razão para bloquear (evita um alerta confuso de "não pode
    # alterar" quando na prática nada mudaria).
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.patch(f"/api/v1/usuarios/{admin.id}/perfil", json={"perfil": "ADMIN"})
    assert res.status_code == 200


def test_operador_nao_pode_alterar_perfil_de_ninguem(client, db_session):
    op1 = _criar_operador(db_session, email="op1@siamp.test")
    op2 = _criar_operador(db_session, email="op2@siamp.test")
    _login(client, op1)

    res = client.patch(f"/api/v1/usuarios/{op2.id}/perfil", json={"perfil": "SUPERVISOR"})
    assert res.status_code == 403


# --- Excluir definitivamente ---------------------------------------------


def test_admin_exclui_usuario_de_teste_sem_historico(client, db_session):
    admin = _criar_admin(db_session)
    op = _criar_operador(db_session)
    _login(client, admin)

    res = client.delete(f"/api/v1/usuarios/{op.id}")
    assert res.status_code == 204

    assert db_session.query(Usuario).filter(Usuario.id == op.id).first() is None


def test_admin_nao_pode_excluir_a_propria_conta(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.delete(f"/api/v1/usuarios/{admin.id}")
    assert res.status_code == 400


def test_excluir_usuario_inexistente_retorna_404(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.delete("/api/v1/usuarios/99999")
    assert res.status_code == 404


def test_operador_nao_pode_excluir_ninguem(client, db_session):
    op1 = _criar_operador(db_session, email="op1@siamp.test")
    op2 = _criar_operador(db_session, email="op2@siamp.test")
    _login(client, op1)

    res = client.delete(f"/api/v1/usuarios/{op2.id}")
    assert res.status_code == 403


def test_excluir_usuario_com_turno_editado_nao_quebra_e_desvincula(client, db_session):
    # O caso real que motivou a migration 0013: um colaborador
    # desligado quase sempre tem histórico de turnos editados. Sem
    # ON DELETE SET NULL nas FKs, isso bloquearia a exclusão
    # (RESTRICT, padrão do Postgres).
    from app.models.turno import Turno

    admin = _criar_admin(db_session)
    colaborador_desligado = _criar_operador(db_session, email="desligado@siamp.test")

    turno = Turno(
        nome_turno="1º Turno", responsavel_nome="Alguém",
        status_assinatura="ASSINADO_DIGITALMENTE", modelo_apontamento="LANCAMENTO",
        editado_por_id=colaborador_desligado.id,
    )
    db_session.add(turno)
    db_session.commit()
    db_session.refresh(turno)

    _login(client, admin)
    res = client.delete(f"/api/v1/usuarios/{colaborador_desligado.id}")
    assert res.status_code == 204, res.text

    db_session.refresh(turno)
    assert turno.editado_por_id is None
    # O turno em si continua existindo normalmente, intacto
    assert db_session.query(Turno).filter(Turno.id == turno.id).first() is not None


def test_excluir_usuario_com_ordem_producao_criada_desvincula(client, db_session):
    from app.models.ordem_producao import OrdemProducao
    from app.models.produto import Produto

    admin = _criar_admin(db_session)
    colaborador_desligado = _criar_operador(db_session, email="desligado2@siamp.test")

    peca = Produto(codigo="OP-TESTE", descricao="Peça Teste", ciclo_padrao=10.0, cavidades=2)
    db_session.add(peca)
    db_session.commit()
    db_session.refresh(peca)

    ordem = OrdemProducao(
        numero_op="OP-2026-0001", produto_id=peca.id,
        periodo_inicio=date(2026, 9, 1), periodo_fim=date(2026, 9, 30),
        quantidade_a_produzir=1000, criado_por_id=colaborador_desligado.id,
    )
    db_session.add(ordem)
    db_session.commit()
    db_session.refresh(ordem)

    _login(client, admin)
    res = client.delete(f"/api/v1/usuarios/{colaborador_desligado.id}")
    assert res.status_code == 204, res.text

    db_session.refresh(ordem)
    assert ordem.criado_por_id is None
    assert db_session.query(OrdemProducao).filter(OrdemProducao.id == ordem.id).first() is not None
