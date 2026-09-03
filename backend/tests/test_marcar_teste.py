from datetime import time

from app.core.security import gerar_hash_senha
from app.models.lancamento import Lancamento
from app.models.maquina import Maquina
from app.models.produto import Produto
from app.models.turno import Turno
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


# --- Exclusão definitiva de turno (DELETE /turnos/{id}) ------------------


def test_admin_exclui_turno_definitivamente(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    turno = _criar_turno_fechado_com_producao(db_session)

    res = client.delete(f"/api/v1/turnos/{turno.id}")
    assert res.status_code == 204

    assert db_session.query(Turno).filter(Turno.id == turno.id).first() is None


def test_excluir_turno_apaga_lancamentos_em_cascata(client, db_session):
    from app.models.lancamento import Lancamento

    admin = _criar_admin(db_session)
    _login(client, admin)
    turno = _criar_turno_fechado_com_producao(db_session)
    lancamento_id = db_session.query(Lancamento).filter(Lancamento.turno_id == turno.id).first().id

    res = client.delete(f"/api/v1/turnos/{turno.id}")
    assert res.status_code == 204, res.text

    # o lançamento não pode continuar órfão - foi apagado junto
    assert db_session.query(Lancamento).filter(Lancamento.id == lancamento_id).first() is None


def test_excluir_turno_modelo_por_hora_apaga_registros_em_cascata(client, db_session):
    from datetime import time

    from app.models.registro_turno import RegistroHorario

    admin = _criar_admin(db_session)
    _login(client, admin)

    maquina = Maquina(numero_maquina="9", descricao="Injetora Teste 2", ativo=True)
    db_session.add(maquina)
    db_session.commit()
    db_session.refresh(maquina)

    turno = Turno(
        nome_turno="1º Turno", responsavel_nome="Líder Teste",
        status_assinatura="ASSINADO_DIGITALMENTE", modelo_apontamento="HORARIO",
    )
    db_session.add(turno)
    db_session.flush()
    db_session.add(RegistroHorario(
        turno_id=turno.id, maquina_id=maquina.id,
        hora_referencia=time(5, 0), prod_executada=50,
    ))
    db_session.commit()
    db_session.refresh(turno)
    registro_id = db_session.query(RegistroHorario).filter(RegistroHorario.turno_id == turno.id).first().id

    res = client.delete(f"/api/v1/turnos/{turno.id}")
    assert res.status_code == 204, res.text
    assert db_session.query(RegistroHorario).filter(RegistroHorario.id == registro_id).first() is None


def test_excluir_turno_nao_apaga_ordem_de_producao_referenciada(client, db_session):
    from datetime import date, time

    from app.models.lancamento import Lancamento
    from app.models.ordem_producao import OrdemProducao

    admin = _criar_admin(db_session)
    _login(client, admin)

    maquina = Maquina(numero_maquina="9", descricao="Injetora Teste 3", ativo=True)
    peca = Produto(codigo="PC-OP", descricao="Peça com OP", ciclo_padrao=10.0, cavidades=2)
    db_session.add_all([maquina, peca])
    db_session.commit()
    db_session.refresh(maquina)
    db_session.refresh(peca)

    op = OrdemProducao(
        numero_op="OP-TESTE-EXCLUIR", produto_id=peca.id,
        periodo_inicio=date(2026, 9, 1), periodo_fim=date(2026, 9, 30),
        quantidade_a_produzir=1000,
    )
    db_session.add(op)
    db_session.commit()
    db_session.refresh(op)

    turno = Turno(
        nome_turno="1º Turno", responsavel_nome="Líder Teste",
        status_assinatura="ASSINADO_DIGITALMENTE", modelo_apontamento="LANCAMENTO",
    )
    db_session.add(turno)
    db_session.flush()
    db_session.add(Lancamento(
        turno_id=turno.id, maquina_id=maquina.id, tipo="PRODUCAO",
        horario_inicio=time(5, 0), horario_fim=time(6, 0),
        produto_id=peca.id, quantidade=100, ordem_producao_id=op.id,
    ))
    db_session.commit()
    db_session.refresh(turno)

    res = client.delete(f"/api/v1/turnos/{turno.id}")
    assert res.status_code == 204, res.text

    # a OP continua existindo normalmente, independente do turno
    assert db_session.query(OrdemProducao).filter(OrdemProducao.id == op.id).first() is not None


def test_excluir_turno_inexistente_retorna_404(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)

    res = client.delete("/api/v1/turnos/99999")
    assert res.status_code == 404


def test_operador_nao_pode_excluir_turno(client, db_session, usuario_teste):
    turno = _criar_turno_fechado_com_producao(db_session)
    _login(client, usuario_teste)

    res = client.delete(f"/api/v1/turnos/{turno.id}")
    assert res.status_code == 403


def test_supervisor_nao_pode_excluir_turno_definitivamente(client, db_session):
    # Diferente de marcar como teste (ADMIN/SUPERVISOR), excluir de
    # vez é restrito só a ADMIN - mesma política já usada para
    # excluir usuário e peça.
    supervisor = Usuario(
        nome="Supervisor Teste", email="supervisor-exclui@siamp.test",
        senha_hash=gerar_hash_senha("senha-forte-123"), perfil="SUPERVISOR", ativo=True,
    )
    db_session.add(supervisor)
    db_session.commit()
    db_session.refresh(supervisor)
    turno = _criar_turno_fechado_com_producao(db_session)
    _login(client, supervisor)

    res = client.delete(f"/api/v1/turnos/{turno.id}")
    assert res.status_code == 403
