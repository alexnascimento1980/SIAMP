import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings


def enviar_relatorio_email(
    destinatarios: list[str],
    assunto: str,
    corpo_html: str,
    pdf_bytes: bytes,
) -> None:
    if not settings.smtp_user or not settings.smtp_pass:
        return

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

    with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_pass)
        server.send_message(mensagem)
