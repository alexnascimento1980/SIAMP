import smtplib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.mailer import EnvioEmailError, enviar_relatorio_email


def _settings_falsas(**overrides):
    base = dict(
        smtp_user="siamp@empresa.com",
        smtp_pass="senha-app",
        smtp_server="smtp.exemplo.com",
        smtp_port=587,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


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
