from datetime import datetime, time

from app.core.security import gerar_hash_senha
from app.models.maquina import Maquina
from app.models.produto import Produto
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


def _seed_produto(db_session, codigo="34-7506-00BR"):
    produto = Produto(codigo=codigo, descricao="CLIP TUBE - BRESIL - UN")
    db_session.add(produto)
    db_session.commit()
    db_session.refresh(produto)
    return produto


def _payload_op_exemplo(produto_id, **overrides):
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
        "produto_id": produto_id,
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


def test_operador_nao_pode_criar_ordem(client, db_session, usuario_teste):
    produto = _seed_produto(db_session)
    _login(client, usuario_teste)
    res = client.post("/api/v1/ordens-producao/", json=_payload_op_exemplo(produto.id))
    assert res.status_code == 403


def test_operador_pode_listar_e_ver_ordem(client, db_session, usuario_teste):
    admin = _criar_admin(db_session)
    _seed_maquina(db_session)
    produto = _seed_produto(db_session)
    _login(client, admin)
    res_criacao = client.post("/api/v1/ordens-producao/", json=_payload_op_exemplo(produto.id))
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
    produto = _seed_produto(db_session)

    _login(client, admin)
    res = client.post("/api/v1/ordens-producao/", json=_payload_op_exemplo(produto.id))
    assert res.status_code == 201, res.text
    assert res.json()["numero_maquina"] == "6"
    assert res.json()["produto_id"] == produto.id


def test_numero_op_duplicado_e_rejeitado(client, db_session):
    admin = _criar_admin(db_session)
    _seed_maquina(db_session)
    produto = _seed_produto(db_session)
    _login(client, admin)
    res1 = client.post("/api/v1/ordens-producao/", json=_payload_op_exemplo(produto.id))
    assert res1.status_code == 201, res1.text
    res = client.post("/api/v1/ordens-producao/", json=_payload_op_exemplo(produto.id))
    assert res.status_code == 409


def test_periodo_fim_antes_do_inicio_e_rejeitado(client, db_session):
    admin = _criar_admin(db_session)
    _seed_maquina(db_session)
    produto = _seed_produto(db_session)
    _login(client, admin)
    payload = _payload_op_exemplo(
        produto.id, periodo_inicio="2026-08-20", periodo_fim="2026-08-18"
    )
    res = client.post("/api/v1/ordens-producao/", json=payload)
    assert res.status_code == 422


def test_produto_inexistente_e_rejeitado(client, db_session):
    admin = _criar_admin(db_session)
    _seed_maquina(db_session)
    _login(client, admin)
    res = client.post("/api/v1/ordens-producao/", json=_payload_op_exemplo(99999))
    assert res.status_code == 400


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
    produto = _seed_produto(db_session)

    _login(client, admin)
    ordem_id = client.post(
        "/api/v1/ordens-producao/", json=_payload_op_exemplo(produto.id)
    ).json()["id"]

    res = client.get(f"/api/v1/ordens-producao/{ordem_id}/comparativo")
    assert res.status_code == 200
    comparativo = res.json()
    assert comparativo["quantidade_meta"] == 48000
    assert comparativo["quantidade_produzida"] == 0
    assert comparativo["percentual_atingido"] == 0.0


def test_dentro_do_prazo_usa_horario_de_brasilia_nao_utc(client, db_session, monkeypatch):
    # Bug real encontrado por um linter (ruff, regra DTZ011): a
    # comparação usava date.today() (UTC no servidor) em vez de
    # agora_brasilia().date() - mesma classe de bug já corrigida antes
    # em outros pontos do sistema. Sem a correção, um servidor em UTC
    # poderia considerar uma OP "fora do prazo" até 3h antes da hora
    # real da virada do dia em Brasília (ou o oposto, dependendo do
    # horário). Mocka agora_brasilia() para os dois lados do prazo,
    # já que o bug só se manifesta perto da meia-noite - não dá pra
    # depender do horário real de quando o teste roda.
    import app.services.ordem_producao_service as modulo

    admin = _criar_admin(db_session)
    db_session.add(
        Maquina(numero_maquina="6", descricao="Injetora", cavidades=8, ciclo_padrao=19.0)
    )
    db_session.commit()
    produto = _seed_produto(db_session)

    _login(client, admin)
    ordem_id = client.post(
        "/api/v1/ordens-producao/", json=_payload_op_exemplo(produto.id)
    ).json()["id"]

    # periodo_fim = 2026-08-20 - ainda dentro do prazo
    monkeypatch.setattr(modulo, "agora_brasilia", lambda: datetime(2026, 8, 20, 10, 0))
    res = client.get(f"/api/v1/ordens-producao/{ordem_id}/comparativo")
    assert res.json()["dentro_do_prazo"] is True

    # um dia depois do prazo - fora do prazo
    monkeypatch.setattr(modulo, "agora_brasilia", lambda: datetime(2026, 8, 21, 10, 0))
    res = client.get(f"/api/v1/ordens-producao/{ordem_id}/comparativo")
    assert res.json()["dentro_do_prazo"] is False


def test_comparativo_soma_producao_de_multiplas_maquinas(client, db_session):
    # Cenário real: a mesma OP é produzida em duas injetoras ao mesmo
    # tempo - o comparativo deve somar as duas, e ignorar produção de
    # outras OPs feita na mesma máquina.
    admin = _criar_admin(db_session)
    maquina_a = Maquina(numero_maquina="6", descricao="Injetora A", cavidades=8, ciclo_padrao=19.0)
    maquina_b = Maquina(numero_maquina="7", descricao="Injetora B", cavidades=4, ciclo_padrao=15.0)
    db_session.add_all([maquina_a, maquina_b])
    db_session.commit()
    db_session.refresh(maquina_a)
    db_session.refresh(maquina_b)
    produto = _seed_produto(db_session)
    outro_produto = _seed_produto(db_session, codigo="OUTRO-COD")

    _login(client, admin)
    ordem_id = client.post(
        "/api/v1/ordens-producao/", json=_payload_op_exemplo(produto.id)
    ).json()["id"]

    # Outra OP, para confirmar que não entra na soma.
    outra_ordem_id = client.post(
        "/api/v1/ordens-producao/",
        json=_payload_op_exemplo(outro_produto.id, numero_op="9999-2026", numero_maquina="6"),
    ).json()["id"]

    turno = Turno(
        nome_turno="1º Turno",
        responsavel_nome="Teste",
        status_assinatura="ASSINADO_DIGITALMENTE",
    )
    db_session.add(turno)
    db_session.flush()

    # Máquina A, apontado para a OP em teste.
    db_session.add(
        RegistroHorario(
            turno_id=turno.id,
            maquina_id=maquina_a.id,
            hora_referencia=time(8, 0),
            prod_executada=10000,
            ordem_producao_id=ordem_id,
        )
    )
    # Máquina B, mesma OP - produção simultânea em duas injetoras.
    db_session.add(
        RegistroHorario(
            turno_id=turno.id,
            maquina_id=maquina_b.id,
            hora_referencia=time(8, 0),
            prod_executada=5000,
            ordem_producao_id=ordem_id,
        )
    )
    # Máquina A de novo, mas para a OUTRA ordem - não deve contar.
    db_session.add(
        RegistroHorario(
            turno_id=turno.id,
            maquina_id=maquina_a.id,
            hora_referencia=time(9, 0),
            prod_executada=99999,
            ordem_producao_id=outra_ordem_id,
        )
    )
    # Registro sem nenhuma OP vinculada - também não deve contar.
    db_session.add(
        RegistroHorario(
            turno_id=turno.id,
            maquina_id=maquina_a.id,
            hora_referencia=time(10, 0),
            prod_executada=77777,
        )
    )
    db_session.commit()

    res = client.get(f"/api/v1/ordens-producao/{ordem_id}/comparativo")
    assert res.status_code == 200
    comparativo = res.json()
    assert comparativo["quantidade_produzida"] == 15000
    assert comparativo["percentual_atingido"] == round(15000 / 48000 * 100, 1)
