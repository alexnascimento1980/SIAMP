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
