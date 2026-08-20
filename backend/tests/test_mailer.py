import smtplib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.services.mailer import EnvioEmailError, enviar_relatorio_email


def _settings_falsas(**overrides):
    base = dict(
        smtp_user="siamp@empresa.com",
        smtp_pass="senha-app",
        smtp_from="siamp@empresa.com",
        smtp_server="smtp.exemplo.com",
        smtp_port=587,
        brevo_api_key="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# --- Caminho SMTP (fallback, sem BREVO_API_KEY) -----------------------


def test_pula_envio_sem_credenciais():
    with patch("app.services.mailer.settings", _settings_falsas(smtp_user="", smtp_pass="")):
        with patch("smtplib.SMTP") as mock_smtp:
            enviar_relatorio_email(["dest@empresa.com"], "Assunto", "<p>corpo</p>", b"%PDF-1.4")
            mock_smtp.assert_not_called()


def test_pula_envio_sem_destinatarios():
    with patch("app.services.mailer.settings", _settings_falsas()):
        with patch("smtplib.SMTP") as mock_smtp:
            enviar_relatorio_email([], "Assunto", "<p>corpo</p>", b"%PDF-1.4")
            mock_smtp.assert_not_called()


def test_envio_bem_sucedido_chama_login_e_send_message():
    with patch("app.services.mailer.settings", _settings_falsas()):
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__.return_value = mock_smtp.return_value

            enviar_relatorio_email(
                ["dest1@empresa.com", "dest2@empresa.com"],
                "Fechamento de turno",
                "<p>corpo</p>",
                b"%PDF-1.4 conteudo falso",
            )

            mock_smtp.assert_called_once_with("smtp.exemplo.com", 587, timeout=15)
            mock_smtp.return_value.starttls.assert_called_once()
            mock_smtp.return_value.login.assert_called_once_with(
                "siamp@empresa.com", "senha-app"
            )
            assert mock_smtp.return_value.send_message.call_count == 1
            mensagem_enviada = mock_smtp.return_value.send_message.call_args[0][0]
            assert mensagem_enviada["To"] == "dest1@empresa.com, dest2@empresa.com"
            assert mensagem_enviada["Subject"] == "Fechamento de turno"


def test_from_usa_smtp_from_quando_diferente_do_smtp_user():
    fake_settings = _settings_falsas(
        smtp_user="b610a9001@smtp-brevo.com", smtp_from="siamp@empresa.com"
    )
    with patch("app.services.mailer.settings", fake_settings):
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__.return_value = mock_smtp.return_value

            enviar_relatorio_email(
                ["dest@empresa.com"], "Assunto", "<p>corpo</p>", b"%PDF-1.4"
            )

            mensagem_enviada = mock_smtp.return_value.send_message.call_args[0][0]
            assert mensagem_enviada["From"] == "siamp@empresa.com"
            mock_smtp.return_value.login.assert_called_once_with(
                "b610a9001@smtp-brevo.com", "senha-app"
            )


def test_falha_autenticacao_levanta_envio_email_error():
    with patch("app.services.mailer.settings", _settings_falsas()):
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__.return_value = mock_smtp.return_value
            mock_smtp.return_value.login.side_effect = smtplib.SMTPAuthenticationError(
                535, b"credenciais invalidas"
            )

            with pytest.raises(EnvioEmailError):
                enviar_relatorio_email(
                    ["dest@empresa.com"], "Assunto", "<p>corpo</p>", b"%PDF-1.4"
                )


def test_falha_de_rede_levanta_envio_email_error():
    with patch("app.services.mailer.settings", _settings_falsas()):
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = OSError("Connection refused")

            with pytest.raises(EnvioEmailError):
                enviar_relatorio_email(
                    ["dest@empresa.com"], "Assunto", "<p>corpo</p>", b"%PDF-1.4"
                )


# --- Caminho API HTTP do Brevo (preferido quando BREVO_API_KEY existe) -


def test_usa_brevo_quando_api_key_configurada_ignora_smtp():
    fake_settings = _settings_falsas(brevo_api_key="chave-brevo-falsa")
    with patch("app.services.mailer.settings", fake_settings):
        with patch("smtplib.SMTP") as mock_smtp:
            with patch("requests.post") as mock_post:
                mock_post.return_value = MagicMock(status_code=201, text="")

                enviar_relatorio_email(
                    ["dest@empresa.com"], "Assunto", "<p>corpo</p>", b"%PDF-1.4"
                )

                mock_smtp.assert_not_called()
                mock_post.assert_called_once()


def test_brevo_monta_payload_correto_com_anexo_em_base64():
    fake_settings = _settings_falsas(brevo_api_key="chave-brevo-falsa")
    with patch("app.services.mailer.settings", fake_settings):
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=201, text="")

            enviar_relatorio_email(
                ["dest1@empresa.com", "dest2@empresa.com"],
                "Fechamento de turno",
                "<p>corpo</p>",
                b"conteudo-do-pdf",
                "relatorio.pdf",
            )

            kwargs = mock_post.call_args[1]
            assert mock_post.call_args[0][0] == "https://api.brevo.com/v3/smtp/email"
            assert kwargs["headers"]["api-key"] == "chave-brevo-falsa"

            payload = kwargs["json"]
            assert payload["sender"] == {"email": "siamp@empresa.com"}
            assert payload["to"] == [
                {"email": "dest1@empresa.com"},
                {"email": "dest2@empresa.com"},
            ]
            assert payload["subject"] == "Fechamento de turno"
            assert payload["attachment"][0]["name"] == "relatorio.pdf"

            import base64

            assert base64.b64decode(payload["attachment"][0]["content"]) == b"conteudo-do-pdf"


def test_brevo_erro_http_levanta_envio_email_error():
    fake_settings = _settings_falsas(brevo_api_key="chave-brevo-falsa")
    with patch("app.services.mailer.settings", fake_settings):
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=401, text='{"message":"Key not found"}'
            )

            with pytest.raises(EnvioEmailError):
                enviar_relatorio_email(
                    ["dest@empresa.com"], "Assunto", "<p>corpo</p>", b"%PDF-1.4"
                )


def test_brevo_falha_de_rede_levanta_envio_email_error():
    fake_settings = _settings_falsas(brevo_api_key="chave-brevo-falsa")
    with patch("app.services.mailer.settings", fake_settings):
        with patch("requests.post") as mock_post:
            mock_post.side_effect = requests.ConnectionError("timeout")

            with pytest.raises(EnvioEmailError):
                enviar_relatorio_email(
                    ["dest@empresa.com"], "Assunto", "<p>corpo</p>", b"%PDF-1.4"
                )
