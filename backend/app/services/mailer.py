import base64
import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from app.core.config import settings

logger = logging.getLogger("siamp.mailer")

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


class EnvioEmailError(Exception):
    """Erro ao enviar o e-mail, seja via API HTTP (Brevo) ou SMTP.
    Encapsula a exceção original com uma mensagem mais clara para quem
    for ler o log (ex.: distinguir erro de credenciais de erro de
    rede)."""


def _montar_mensagem(
    destinatarios: list[str],
    assunto: str,
    corpo_html: str,
    pdf_bytes: bytes,
    nome_arquivo: str,
) -> MIMEMultipart:
    mensagem = MIMEMultipart()
    mensagem["From"] = settings.smtp_from
    mensagem["To"] = ", ".join(destinatarios)
    mensagem["Subject"] = assunto

    mensagem.attach(MIMEText(corpo_html, "html"))

    anexo = MIMEApplication(pdf_bytes, _subtype="pdf")
    anexo.add_header(
        "Content-Disposition",
        "attachment",
        filename=nome_arquivo,
    )
    mensagem.attach(anexo)
    return mensagem


def _enviar_via_brevo_api(
    destinatarios: list[str],
    assunto: str,
    corpo_html: str,
    pdf_bytes: bytes,
    nome_arquivo: str,
) -> None:
    """Envia via API HTTP do Brevo (porta 443/HTTPS), em vez de SMTP
    (portas 25/465/587). Necessário porque hospedagens com plano
    gratuito (ex.: Render) bloqueiam tráfego de saída para portas SMTP,
    mas não para HTTPS comum - ver DEPLOY.md."""
    payload = {
        "sender": {"email": settings.smtp_from},
        "to": [{"email": destinatario} for destinatario in destinatarios],
        "subject": assunto,
        "htmlContent": corpo_html,
        "attachment": [
            {
                "content": base64.b64encode(pdf_bytes).decode("ascii"),
                "name": nome_arquivo,
            }
        ],
    }
    headers = {
        "api-key": settings.brevo_api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        resposta = requests.post(BREVO_API_URL, json=payload, headers=headers, timeout=15)
    except requests.RequestException as exc:
        logger.error("Falha de rede ao chamar a API do Brevo: %s", exc)
        raise EnvioEmailError("Falha de rede ao enviar e-mail via Brevo.") from exc

    if resposta.status_code >= 400:
        logger.error(
            "Falha ao enviar e-mail via API do Brevo (HTTP %s): %s",
            resposta.status_code,
            resposta.text,
        )
        raise EnvioEmailError(
            f"Falha ao enviar e-mail via Brevo (HTTP {resposta.status_code})."
        )

    logger.info(
        "E-mail de relatório enviado com sucesso via Brevo para %s.", destinatarios
    )


def _enviar_via_smtp(
    destinatarios: list[str],
    assunto: str,
    corpo_html: str,
    pdf_bytes: bytes,
    nome_arquivo: str,
) -> None:
    """Caminho tradicional via smtplib - funciona bem em desenvolvimento
    local (ex.: Gmail), mas costuma ser bloqueado em hospedagens com
    plano gratuito que restringem portas SMTP de saída (ver
    _enviar_via_brevo_api, o caminho preferido quando BREVO_API_KEY
    está configurada)."""
    mensagem = _montar_mensagem(destinatarios, assunto, corpo_html, pdf_bytes, nome_arquivo)

    try:
        with smtplib.SMTP(settings.smtp_server, settings.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_pass)
            server.send_message(mensagem)
    except smtplib.SMTPAuthenticationError as exc:
        logger.error(
            "Falha de autenticação SMTP (usuário/senha incorretos, ou "
            "senha de app não configurada para %s): %s",
            settings.smtp_user,
            exc,
        )
        raise EnvioEmailError("Falha de autenticação SMTP.") from exc
    except (smtplib.SMTPException, OSError) as exc:
        logger.error(
            "Falha ao enviar e-mail via %s:%s para %s: %s",
            settings.smtp_server,
            settings.smtp_port,
            destinatarios,
            exc,
        )
        raise EnvioEmailError("Falha ao enviar e-mail.") from exc
    else:
        logger.info(
            "E-mail de relatório enviado com sucesso via SMTP para %s.", destinatarios
        )


def enviar_relatorio_email(
    destinatarios: list[str],
    assunto: str,
    corpo_html: str,
    pdf_bytes: bytes,
    nome_arquivo: str = "relatorio_siamp.pdf",
) -> None:
    """Envia o relatório de fechamento de turno por e-mail (chamado em
    background após o fechamento - ver turno_service.fechar_turno).

    Usa a API HTTP do Brevo quando BREVO_API_KEY está configurada
    (necessário em hospedagens que bloqueiam portas SMTP de saída, como
    o plano gratuito do Render); caso contrário, cai para SMTP
    tradicional (bom para desenvolvimento local, ex. Gmail).

    Não faz nada, silenciosamente, se nenhum dos dois estiver
    configurado. Quando configurado mas o envio falhar, a falha é
    registrada no log com detalhes - antes ela desaparecia
    silenciosamente, já que roda em background task e ninguém ficava
    esperando o resultado.
    """
    if not destinatarios:
        logger.warning("Envio de e-mail pulado: nenhum destinatário informado.")
        return

    if settings.brevo_api_key:
        _enviar_via_brevo_api(destinatarios, assunto, corpo_html, pdf_bytes, nome_arquivo)
        return

    if not settings.smtp_user or not settings.smtp_pass:
        logger.info(
            "Envio de e-mail pulado: nem BREVO_API_KEY nem SMTP_USER/"
            "SMTP_PASS configurados."
        )
        return

    _enviar_via_smtp(destinatarios, assunto, corpo_html, pdf_bytes, nome_arquivo)
