from datetime import time

from app.core.security import gerar_hash_senha
from app.models.maquina import Maquina
from app.models.produto import Produto
from app.models.turno import Turno
from app.models.lancamento import Lancamento
from app.models.usuario import Usuario


def _login(client, usuario, senha="senha-forte-123"):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario.email, "password": senha},
    )
    assert res.status_code == 200


def _criar_admin(db_session, email="admin-teste@siamp.test"):
    admin = Usuario(
        nome="Admin Teste", email=email,
        senha_hash=gerar_hash_senha("senha-forte-123"), perfil="ADMIN", ativo=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def _criar_turno_fechado_com_producao(db_session, quantidade=100, numero_maquina="1"):
    """Cria um turno já fechado (ASSINADO_DIGITALMENTE), com um
    lançamento de produção, pronto para ser contado no dashboard."""
    maquina = Maquina(numero_maquina=numero_maquina, descricao="Injetora Teste", ativo=True)
    peca = Produto(codigo=f"PC-TESTE-{numero_maquina}", descricao="Peça Teste", ciclo_padrao=10.0, cavidades=2)
    db_session.add_all([maquina, peca])
    db_session.commit()
    db_session.refresh(maquina)
    db_session.refresh(peca)

    turno = Turno(
        nome_turno="1º Turno", responsavel_nome="Líder Teste",
        status_assinatura="ASSINADO_DIGITALMENTE", modelo_apontamento="LANCAMENTO",
    )
    db_session.add(turno)
    db_session.flush()
    db_session.add(Lancamento(
        turno_id=turno.id, maquina_id=maquina.id, tipo="PRODUCAO",
        horario_inicio=time(5, 0), horario_fim=time(6, 0),
        produto_id=peca.id, quantidade=quantidade,
    ))
    db_session.commit()
    db_session.refresh(turno)
    return turno


# --- Endpoint PATCH /turnos/marcar-teste ---------------------------------


def test_admin_marca_turnos_como_teste_em_lote(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    turno1 = _criar_turno_fechado_com_producao(db_session, numero_maquina="1")
    turno2 = _criar_turno_fechado_com_producao(db_session, numero_maquina="2")

    res = client.patch(
        "/api/v1/turnos/marcar-teste",
        json={"turno_ids": [turno1.id, turno2.id], "marcado_teste": True},
    )
    assert res.status_code == 200, res.text
    assert res.json() == {"atualizados": 2, "marcado_teste": True}

    db_session.refresh(turno1)
    db_session.refresh(turno2)
    assert turno1.marcado_teste is True
    assert turno2.marcado_teste is True


def test_admin_desmarca_turno_de_teste(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    turno = _criar_turno_fechado_com_producao(db_session)
    turno.marcado_teste = True
    db_session.commit()

    res = client.patch(
        "/api/v1/turnos/marcar-teste",
        json={"turno_ids": [turno.id], "marcado_teste": False},
    )
    assert res.status_code == 200

    db_session.refresh(turno)
    assert turno.marcado_teste is False


def test_marcar_teste_com_turno_inexistente_retorna_404(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    turno = _criar_turno_fechado_com_producao(db_session)

    res = client.patch(
        "/api/v1/turnos/marcar-teste",
        json={"turno_ids": [turno.id, 99999], "marcado_teste": True},
    )
    assert res.status_code == 404

    # nenhum turno foi alterado - a operação é tudo ou nada
    db_session.refresh(turno)
    assert turno.marcado_teste is False


def test_operador_nao_pode_marcar_turno_como_teste(client, db_session, usuario_teste):
    turno = _criar_turno_fechado_com_producao(db_session)
    _login(client, usuario_teste)

    res = client.patch(
        "/api/v1/turnos/marcar-teste",
        json={"turno_ids": [turno.id], "marcado_teste": True},
    )
    assert res.status_code == 403


def test_marcar_teste_lista_vazia_e_rejeitada(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.patch(
        "/api/v1/turnos/marcar-teste",
        json={"turno_ids": [], "marcado_teste": True},
    )
    assert res.status_code == 422


# --- Exclusão do dashboard --------------------------------------------


def test_turno_marcado_teste_some_do_dashboard(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    turno = _criar_turno_fechado_com_producao(db_session, quantidade=500)

    res_antes = client.get("/api/v1/dashboard/metricas-gerais")
    assert res_antes.json()["kpis"]["total_pecas_produzidas"] == 500

    client.patch(
        "/api/v1/turnos/marcar-teste",
        json={"turno_ids": [turno.id], "marcado_teste": True},
    )

    res_depois = client.get("/api/v1/dashboard/metricas-gerais")
    assert res_depois.json()["kpis"]["total_pecas_produzidas"] == 0


def test_turno_desmarcado_volta_a_aparecer_no_dashboard(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    turno = _criar_turno_fechado_com_producao(db_session, quantidade=300)
    turno.marcado_teste = True
    db_session.commit()

    res_marcado = client.get("/api/v1/dashboard/metricas-gerais")
    assert res_marcado.json()["kpis"]["total_pecas_produzidas"] == 0

    client.patch(
        "/api/v1/turnos/marcar-teste",
        json={"turno_ids": [turno.id], "marcado_teste": False},
    )

    res_desmarcado = client.get("/api/v1/dashboard/metricas-gerais")
    assert res_desmarcado.json()["kpis"]["total_pecas_produzidas"] == 300


def test_turno_marcado_teste_continua_no_historico(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    turno = _criar_turno_fechado_com_producao(db_session)
    turno.marcado_teste = True
    db_session.commit()

    res = client.get("/api/v1/turnos/")
    assert res.status_code == 200
    turnos_listados = res.json()
    encontrado = next((t for t in turnos_listados if t["id"] == turno.id), None)
    assert encontrado is not None, "turno marcado como teste sumiu do Histórico"
    assert encontrado["marcado_teste"] is True


# --- Exclusão da exportação CSV -----------------------------------------


def test_turno_marcado_teste_nao_aparece_no_csv(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    turno = _criar_turno_fechado_com_producao(db_session, quantidade=777)
    turno.marcado_teste = True
    db_session.commit()

    res = client.get("/api/v1/turnos/exportar/csv")
    conteudo = res.content.decode("utf-8-sig")
    assert "777" not in conteudo
