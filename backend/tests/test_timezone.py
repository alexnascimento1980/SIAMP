from datetime import UTC, datetime, time

from app.core.security import gerar_hash_senha
from app.core.timezone import agora_brasilia, calcular_data_registro_turno
from app.models.maquina import Maquina
from app.models.produto import Produto
from app.models.turno import Turno
from app.models.usuario import Usuario


def test_agora_brasilia_tem_offset_de_3_horas_do_utc():
    utc_agora = datetime.now(UTC).replace(tzinfo=None)
    brasilia_agora = agora_brasilia()

    diferenca_horas = (utc_agora - brasilia_agora).total_seconds() / 3600
    # Pequena tolerância pelo tempo de execução entre as duas chamadas.
    assert 2.99 <= diferenca_horas <= 3.01


def test_agora_brasilia_retorna_datetime_naive():
    # Sem tzinfo, para bater com a coluna DateTime (sem timezone) já
    # usada no banco - evita erro de comparação/serialização por
    # misturar naive e aware.
    assert agora_brasilia().tzinfo is None


def test_turno_data_registro_usa_horario_de_brasilia(db_session):
    antes = agora_brasilia()
    turno = Turno(
        nome_turno="1º Turno",
        responsavel_nome="Teste",
        status_assinatura="ASSINADO_DIGITALMENTE",
    )
    db_session.add(turno)
    db_session.commit()
    db_session.refresh(turno)
    depois = agora_brasilia()

    # data_registro deve estar entre "antes" e "depois" (ambos já no
    # fuso de Brasília) - se ainda estivesse usando func.now()/UTC,
    # ficaria ~3h à frente e essa comparação falharia.
    assert antes <= turno.data_registro <= depois


def test_usuario_created_at_usa_horario_de_brasilia(db_session):
    antes = agora_brasilia()
    usuario = Usuario(
        nome="Teste",
        email="fuso@teste.com",
        senha_hash=gerar_hash_senha("senha123"),
        perfil="OPERADOR",
        ativo=True,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    depois = agora_brasilia()

    assert antes <= usuario.created_at <= depois


def test_produto_created_at_usa_horario_de_brasilia(db_session):
    antes = agora_brasilia()
    produto = Produto(codigo="FUSO-1", descricao="Peça Teste Fuso")
    db_session.add(produto)
    db_session.commit()
    db_session.refresh(produto)
    depois = agora_brasilia()

    assert antes <= produto.created_at <= depois


def test_maquina_nao_tem_coluna_de_timestamp_afetada(db_session):
    # Máquina não tem coluna de timestamp - só confirma que o cadastro
    # continua funcionando normalmente após as mudanças nos outros
    # modelos (nenhum import quebrado em cadeia).
    maquina = Maquina(numero_maquina="99", descricao="Teste Fuso", ativo=True)
    db_session.add(maquina)
    db_session.commit()
    db_session.refresh(maquina)
    assert maquina.id is not None


# --- calcular_data_registro_turno -----------------------------------
# Achado real relatado pelo usuário: fechar/salvar o 3º Turno
# (22:00-04:00) de madrugada gravava a data do dia do fechamento, não
# a do dia em que o turno realmente começou (ex.: fechado às 04h de
# 15/09, deveria ser 14/09 - dia em que o turno começou às 22h).


def _fixar_agora(monkeypatch, valor: datetime):
    import app.core.timezone as timezone_mod

    monkeypatch.setattr(timezone_mod, "agora_brasilia", lambda: valor)


def test_fechamento_de_madrugada_do_3o_turno_recua_para_o_dia_anterior(monkeypatch):
    _fixar_agora(monkeypatch, datetime(2026, 9, 15, 4, 0))

    resultado = calcular_data_registro_turno([time(22, 0), time(23, 0), time(2, 0)])

    assert resultado == datetime(2026, 9, 14, 4, 0)


def test_lista_vazia_retorna_agora_sem_ajuste(monkeypatch):
    agora_fixo = datetime(2026, 9, 15, 4, 0)
    _fixar_agora(monkeypatch, agora_fixo)

    assert calcular_data_registro_turno([]) == agora_fixo


def test_1o_turno_normal_nao_sofre_ajuste(monkeypatch):
    # 1º Turno (05:00-13:00) fechado dentro do próprio dia - nenhum
    # ajuste deve acontecer.
    agora_fixo = datetime(2026, 9, 15, 13, 5)
    _fixar_agora(monkeypatch, agora_fixo)

    resultado = calcular_data_registro_turno([time(5, 0), time(8, 0)])

    assert resultado == agora_fixo


def test_2o_turno_normal_nao_sofre_ajuste(monkeypatch):
    # 2º Turno (14:00-21:00) não atravessa meia-noite - mesmo com
    # horário de início à tarde, fechar ainda à noite não deve recuar.
    agora_fixo = datetime(2026, 9, 15, 21, 5)
    _fixar_agora(monkeypatch, agora_fixo)

    resultado = calcular_data_registro_turno([time(14, 0), time(18, 0)])

    assert resultado == agora_fixo


def test_3o_turno_salvo_ainda_antes_da_meia_noite_nao_sofre_ajuste(monkeypatch):
    # Rascunho salvo às 23h do próprio dia do início do turno - a data
    # já está correta nesse momento (ainda não passou da meia-noite),
    # não deve recuar.
    agora_fixo = datetime(2026, 9, 14, 23, 0)
    _fixar_agora(monkeypatch, agora_fixo)

    resultado = calcular_data_registro_turno([time(22, 0), time(23, 0)])

    assert resultado == agora_fixo


def test_fechamento_atrasado_do_3o_turno_ainda_recua(monkeypatch):
    # Fechamento esquecido e feito só de manhãzinha, mas ainda antes
    # do 1º Turno do dia seguinte começar (04:50) - continua sendo
    # tratado como madrugada do turno anterior.
    _fixar_agora(monkeypatch, datetime(2026, 9, 15, 4, 50))

    resultado = calcular_data_registro_turno([time(22, 0)])

    assert resultado == datetime(2026, 9, 14, 4, 50)


def test_apos_o_limite_da_madrugada_nao_recua_mais(monkeypatch):
    # Passado o horário em que o 1º Turno do dia já começou (05:00),
    # não é mais razoável presumir que ainda é madrugada do turno
    # anterior - evita recuar por engano um novo apontamento genuíno
    # criado logo pela manhã.
    _fixar_agora(monkeypatch, datetime(2026, 9, 15, 5, 0))

    resultado = calcular_data_registro_turno([time(22, 0)])

    assert resultado == datetime(2026, 9, 15, 5, 0)
