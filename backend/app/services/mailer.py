import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger("siamp.mailer")


class EnvioEmailError(Exception):
    """Erro ao conectar/autenticar/enviar via SMTP. Encapsula a exceção
    original de smtplib com uma mensagem mais clara para quem for ler o
    log (ex.: distinguir erro de credenciais de erro de rede)."""


def _montar_mensagem(
    destinatarios: list[str], assunto: str, corpo_html: str, pdf_bytes: bytes
) -> MIMEMultipart:
    mensagem = MIMEMultipart()
    mensagem["From"] = settings.smtp_user
    mensagem["To"] = ", ".join(destinatarios)
    mensagem["Subject"] = assunto

    mensagem.attach(MIMEText(corpo_html, "html"))

    anexo = MIMEApplication(pdf_bytes, _subtype="pdf")
    anexo.add_header(
        "Content-Disposition",
        "attachment",
        filename="fechamento_turno_siamp.pdf",
    )
    mensagem.attach(anexo)
    return mensagem


def enviar_relatorio_email(
    destinatarios: list[str],
    assunto: str,
    corpo_html: str,
    pdf_bytes: bytes,
) -> None:
    """Envia o relatório de fechamento de turno por e-mail (chamado em
    background após o fechamento - ver turno_service.fechar_turno).

    Não faz nada, silenciosamente, se SMTP_USER/SMTP_PASS não estiverem
    configurados (ambiente sem e-mail habilitado, ex. desenvolvimento
    local). Quando configurado mas o envio falhar (credenciais erradas,
    SMTP fora do ar etc.), a falha é registrada no log com detalhes -
    antes ela desaparecia silenciosamente, já que roda em background
    task e ninguém ficava esperando o resultado.
    """
    if not settings.smtp_user or not settings.smtp_pass:
        logger.info(
            "Envio de e-mail pulado: SMTP_USER/SMTP_PASS não configurados."
        )
        return

    if not destinatarios:
        logger.warning("Envio de e-mail pulado: nenhum destinatário informado.")
        return

    mensagem = _montar_mensagem(destinatarios, assunto, corpo_html, pdf_bytes)

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
            "E-mail de relatório enviado com sucesso para %s.", destinatarios
        )
