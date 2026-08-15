import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "notificacoes.siamp@gmail.com")
SMTP_PASS = os.getenv("SMTP_PASS", "")

def enviar_relatorio_email(destinatarios: list[str], assunto: str, corpo_html: str, pdf_bytes: bytes):
    mensagem = MIMEMultipart()
    mensagem["From"] = SMTP_USER
    mensagem["To"] = ", ".join(destinatarios)
    mensagem["Subject"] = assunto

    mensagem.attach(MIMEText(corpo_html, "html"))

    anexo = MIMEApplication(pdf_bytes, _subtype="pdf")
    anexo.add_header("Content-Disposition", "attachment", filename="fechamento_turno_siamp.pdf")
    mensagem.attach(anexo)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        if SMTP_PASS:
            server.login(SMTP_USER, SMTP_PASS)
        server.send_message(mensagem)