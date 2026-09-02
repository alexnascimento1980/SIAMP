import sys

import pytest

from app.core.security import gerar_hash_senha, verificar_senha
from app.models.usuario import Usuario


@pytest.fixture()
def _redirecionar_sessao_do_script(monkeypatch, db_session):
    """O script usa app.core.database.SessionLocal diretamente (não a
    fixture `client`/`db_session` via dependency override do FastAPI),
    já que roda fora de uma requisição HTTP. Redireciona SessionLocal()
    para devolver a MESMA sessão de teste já aberta (não uma nova
    instância de sessionmaker) - importar conftest diretamente para
    reaproveitar o TestingSessionLocal de lá criaria um módulo Python
    separado, com seu próprio engine/tabelas, desconectado do que o
    pytest de fato usa internamente."""
    import app.scripts.create_admin as create_admin_module

    monkeypatch.setattr(create_admin_module, "SessionLocal", lambda: db_session)
    return create_admin_module


def _rodar_script(modulo, monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["create_admin"] + argv)
    modulo.main()


def test_cria_conta_admin_ja_protegida_quando_nao_existe(
    db_session, _redirecionar_sessao_do_script, monkeypatch
):
    modulo = _redirecionar_sessao_do_script
    _rodar_script(
        modulo, monkeypatch,
        ["--nome", "Conta Mestre", "--email", "mestre@siamp.com", "--senha", "senhaForte123"],
    )

    usuario = db_session.query(Usuario).filter(Usuario.email == "mestre@siamp.com").first()
    assert usuario is not None
    assert usuario.perfil == "ADMIN"
    assert usuario.ativo is True
    assert usuario.protegido is True
    assert verificar_senha("senhaForte123", usuario.senha_hash)


def test_restaura_conta_sabotada_sem_tocar_na_senha(
    db_session, _redirecionar_sessao_do_script, monkeypatch
):
    # Reproduz o incidente que motivou esta funcionalidade: a conta
    # existe mas foi desativada, rebaixada de perfil, e desprotegida -
    # o script deve restaurar os três, sem sobrescrever uma senha
    # trocada deliberadamente depois pela tela de Usuários.
    modulo = _redirecionar_sessao_do_script
    senha_trocada_pelo_usuario = gerar_hash_senha("senha-trocada-manualmente")
    usuario = Usuario(
        nome="Conta Mestre", email="mestre@siamp.com",
        senha_hash=senha_trocada_pelo_usuario,
        perfil="OPERADOR", ativo=False, protegido=False,
    )
    db_session.add(usuario)
    db_session.commit()

    _rodar_script(
        modulo, monkeypatch,
        ["--nome", "Conta Mestre", "--email", "mestre@siamp.com", "--senha", "senha-do-env-antiga"],
    )

    usuario = db_session.query(Usuario).filter(Usuario.email == "mestre@siamp.com").first()
    assert usuario.ativo is True
    assert usuario.perfil == "ADMIN"
    assert usuario.protegido is True
    # a senha trocada continua intacta - a do .env NÃO deveria funcionar
    assert usuario.senha_hash == senha_trocada_pelo_usuario
    assert verificar_senha("senha-trocada-manualmente", usuario.senha_hash)
    assert not verificar_senha("senha-do-env-antiga", usuario.senha_hash)


def test_recria_conta_excluida_totalmente(
    db_session, _redirecionar_sessao_do_script, monkeypatch
):
    # Cenário mais crítico: a conta foi excluída de vez (não só
    # desativada) - o próximo restart do container deve recriá-la do
    # zero, já protegida.
    modulo = _redirecionar_sessao_do_script
    assert db_session.query(Usuario).filter(Usuario.email == "mestre@siamp.com").first() is None

    _rodar_script(
        modulo, monkeypatch,
        ["--nome", "Conta Mestre", "--email", "mestre@siamp.com", "--senha", "senhaForte123"],
    )

    usuario = db_session.query(Usuario).filter(Usuario.email == "mestre@siamp.com").first()
    assert usuario is not None
    assert usuario.ativo is True
    assert usuario.perfil == "ADMIN"
    assert usuario.protegido is True


def test_conta_ja_correta_nao_altera_nada(
    db_session, _redirecionar_sessao_do_script, monkeypatch
):
    modulo = _redirecionar_sessao_do_script
    senha_hash_original = gerar_hash_senha("senha-ja-correta")
    usuario = Usuario(
        nome="Conta Mestre", email="mestre@siamp.com",
        senha_hash=senha_hash_original,
        perfil="ADMIN", ativo=True, protegido=True,
    )
    db_session.add(usuario)
    db_session.commit()
    atualizado_em_antes = usuario.updated_at

    _rodar_script(
        modulo, monkeypatch,
        ["--nome", "Conta Mestre", "--email", "mestre@siamp.com", "--senha", "outra-senha-qualquer"],
    )

    usuario = db_session.query(Usuario).filter(Usuario.email == "mestre@siamp.com").first()
    assert usuario.senha_hash == senha_hash_original
    assert usuario.updated_at == atualizado_em_antes


def test_sem_senha_encerra_com_erro_claro(_redirecionar_sessao_do_script, monkeypatch, capsys):
    modulo = _redirecionar_sessao_do_script
    monkeypatch.delenv("ADMIN_SENHA", raising=False)

    with pytest.raises(SystemExit):
        _rodar_script(modulo, monkeypatch, ["--email", "mestre@siamp.com"])

    saida = capsys.readouterr()
    assert "senha" in saida.err.lower()
