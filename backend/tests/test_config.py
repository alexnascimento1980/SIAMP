from app.core.config import _build_settings


def test_smtp_from_cai_no_smtp_user_quando_nao_definida(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "chave-teste")
    monkeypatch.setenv("SMTP_USER", "usuario@empresa.com")
    monkeypatch.delenv("SMTP_FROM", raising=False)

    settings = _build_settings()

    assert settings.smtp_user == "usuario@empresa.com"
    assert settings.smtp_from == "usuario@empresa.com"


def test_smtp_from_prevalece_quando_definida(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "chave-teste")
    monkeypatch.setenv("SMTP_USER", "b610a9001@smtp-brevo.com")
    monkeypatch.setenv("SMTP_FROM", "siamp@empresa.com")

    settings = _build_settings()

    assert settings.smtp_user == "b610a9001@smtp-brevo.com"
    assert settings.smtp_from == "siamp@empresa.com"


def test_inteiro_do_ambiente_usa_padrao_quando_ausente_ou_invalido(monkeypatch):
    from app.core.database import _inteiro_do_ambiente

    monkeypatch.delenv("DB_POOL_SIZE", raising=False)
    assert _inteiro_do_ambiente("DB_POOL_SIZE", 5) == 5
    monkeypatch.setenv("DB_POOL_SIZE", "abc")
    assert _inteiro_do_ambiente("DB_POOL_SIZE", 5) == 5
    monkeypatch.setenv("DB_POOL_SIZE", "8")
    assert _inteiro_do_ambiente("DB_POOL_SIZE", 5) == 8
    monkeypatch.setenv("DB_POOL_SIZE", "-3")
    assert _inteiro_do_ambiente("DB_POOL_SIZE", 5) == 0
