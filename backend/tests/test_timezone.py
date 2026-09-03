from datetime import UTC, datetime

from app.core.security import gerar_hash_senha
from app.core.timezone import agora_brasilia
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
