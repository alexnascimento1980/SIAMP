from datetime import date, datetime, time

from app.core.security import gerar_hash_senha
from app.models.maquina import Maquina
from app.models.registro_turno import RegistroHorario
from app.models.turno import Turno
from app.models.usuario import Usuario


def _login(client, usuario):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": usuario.email, "password": "senha-forte-123"},
    )
    assert res.status_code == 200


def _criar_admin(db_session, email="admin-op@siamp.test"):
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


def _payload_op_exemplo(**overrides):
    # Dados baseados na Ordem de Produção 2817-2026 (exemplo real
    # fornecido: CLIP TUBE - BRESIL, Injetora 06-120T).
    payload = {
        "numero_op": "2817-2026",
        "data_emissao": "2026-08-17",
        "tipo_op": "PRODUÇÃO",
        "setor_produtivo": "INJEÇÃO",
        "lote": "20260817/2817",
        "periodo_inicio": "2026-08-18",
        "periodo_fim": "2026-08-20",
        "produto_codigo": "34-7506-00BR",
        "produto_descricao": "CLIP TUBE - BRESIL - UN",
        "quantidade_a_produzir": 48000,
        "numero_maquina": "06",
        "equipamento_descricao": "INJETORA 06-120T",
        "ferramenta_codigo": "7506/1",
        "ferramenta_descricao": "MOLDE CLIP TUBE - 22",
        "formula_codigo": "2",
        "formula_descricao": "POM CINZA",
        "embalagem_codigo": "119",
        "embalagem_descricao": "CAIXA M PAPELAO",
        "qtde_por_embalagem": 8000,
        "qtde_embalagens_previstas": 6,
        "cavidades": 8,
        "ciclo_segundos": 19,
        "qtde_produzida_por_hora_meta": 1516,
        "peso_liquido_unitario": 0.0015,
        "peso_bruto_unitario": 0.0016,
        "observacoes": "Ordem de Produção Aberta pelo Kanban de Nível de Estoque",
    }
    payload.update(overrides)
    return payload


def _seed_maquina(db_session, numero="6"):
    maquina = Maquina(
        numero_maquina=numero, descricao="Injetora de teste", cavidades=8, ciclo_padrao=19.0
    )
    db_session.add(maquina)
    db_session.commit()
    db_session.refresh(maquina)
    return maquina


def test_operador_nao_pode_criar_ordem(client, usuario_teste):
    _login(client, usuario_teste)
    res = client.post("/api/v1/ordens-producao/", json=_payload_op_exemplo())
    assert res.status_code == 403


def test_operador_pode_listar_e_ver_ordem(client, db_session, usuario_teste):
    admin = _criar_admin(db_session)
    _seed_maquina(db_session)
    _login(client, admin)
    res_criacao = client.post("/api/v1/ordens-producao/", json=_payload_op_exemplo())
    assert res_criacao.status_code == 201, res_criacao.text

    _login(client, usuario_teste)
    res = client.get("/api/v1/ordens-producao/")
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_criar_ordem_resolve_maquina_com_zero_a_esquerda(client, db_session):
    # A OP impressa mostra "06", mas a máquina cadastrada é "6" - o
    # sistema precisa resolver essa normalização automaticamente.
    admin = _criar_admin(db_session)
    db_session.add(
        Maquina(numero_maquina="6", descricao="Injetora 06-120T", cavidades=8, ciclo_padrao=19.0)
    )
    db_session.commit()

    _login(client, admin)
    res = client.post("/api/v1/ordens-producao/", json=_payload_op_exemplo())
    assert res.status_code == 201, res.text
    assert res.json()["numero_maquina"] == "6"


def test_numero_op_duplicado_e_rejeitado(client, db_session):
    admin = _criar_admin(db_session)
    _seed_maquina(db_session)
    _login(client, admin)
    res1 = client.post("/api/v1/ordens-producao/", json=_payload_op_exemplo())
    assert res1.status_code == 201, res1.text
    res = client.post("/api/v1/ordens-producao/", json=_payload_op_exemplo())
    assert res.status_code == 409


def test_periodo_fim_antes_do_inicio_e_rejeitado(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    payload = _payload_op_exemplo(periodo_inicio="2026-08-20", periodo_fim="2026-08-18")
    res = client.post("/api/v1/ordens-producao/", json=payload)
    assert res.status_code == 422


def test_editar_ordem_inexistente_retorna_404(client, db_session):
    admin = _criar_admin(db_session)
    _login(client, admin)
    res = client.patch("/api/v1/ordens-producao/99999", json={"lote": "X"})
    assert res.status_code == 404


def test_comparativo_sem_producao_real(client, db_session):
    admin = _criar_admin(db_session)
    db_session.add(
        Maquina(numero_maquina="6", descricao="Injetora", cavidades=8, ciclo_padrao=19.0)
    )
    db_session.commit()

    _login(client, admin)
    ordem_id = client.post(
        "/api/v1/ordens-producao/", json=_payload_op_exemplo()
    ).json()["id"]

    res = client.get(f"/api/v1/ordens-producao/{ordem_id}/comparativo")
    assert res.status_code == 200
    comparativo = res.json()
    assert comparativo["quantidade_meta"] == 48000
    assert comparativo["quantidade_produzida"] == 0
    assert comparativo["percentual_atingido"] == 0.0


def test_comparativo_soma_producao_real_dentro_do_periodo(client, db_session):
    admin = _criar_admin(db_session)
    maquina = Maquina(numero_maquina="6", descricao="Injetora", cavidades=8, ciclo_padrao=19.0)
    db_session.add(maquina)
    db_session.commit()
    db_session.refresh(maquina)

    _login(client, admin)
    ordem_id = client.post(
        "/api/v1/ordens-producao/", json=_payload_op_exemplo()
    ).json()["id"]

    # Turno dentro do período (18 a 20/08/2026) - deve contar.
    turno_dentro = Turno(
        nome_turno="1º Turno",
        responsavel_nome="Teste",
        status_assinatura="ASSINADO_DIGITALMENTE",
        data_registro=datetime(2026, 8, 19, 8, 0, 0),
    )
    db_session.add(turno_dentro)
    db_session.flush()
    db_session.add(
        RegistroHorario(
            turno_id=turno_dentro.id,
            maquina_id=maquina.id,
            hora_referencia=time(8, 0),
            prod_executada=10000,
        )
    )

    # Turno fora do período - não deve contar.
    turno_fora = Turno(
        nome_turno="1º Turno",
        responsavel_nome="Teste",
        status_assinatura="ASSINADO_DIGITALMENTE",
        data_registro=datetime(2026, 8, 25, 8, 0, 0),
    )
    db_session.add(turno_fora)
    db_session.flush()
    db_session.add(
        RegistroHorario(
            turno_id=turno_fora.id,
            maquina_id=maquina.id,
            hora_referencia=time(8, 0),
            prod_executada=99999,
        )
    )
    db_session.commit()

    res = client.get(f"/api/v1/ordens-producao/{ordem_id}/comparativo")
    assert res.status_code == 200
    comparativo = res.json()
    assert comparativo["quantidade_produzida"] == 10000
    assert comparativo["percentual_atingido"] == round(10000 / 48000 * 100, 1)
