"""
Envia um e-mail de teste usando a configuração SMTP atual (variáveis de
ambiente SMTP_SERVER/SMTP_PORT/SMTP_USER/SMTP_PASS), para validar as
credenciais sem precisar fechar um turno de verdade.

Uso:
    docker compose exec backend_api python -m app.scripts.testar_email --para seu-email@empresa.com

Se SMTP_USER/SMTP_PASS não estiverem configurados no .env, o script
avisa e não tenta enviar nada (mesmo comportamento do envio real).
"""
import argparse
import sys

from app.core.config import settings
from app.services.mailer import EnvioEmailError, enviar_relatorio_email


PDF_MINIMO = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--para",
        required=True,
        help="E-mail de destino do teste (ex.: seu-email@empresa.com)",
    )
    args = parser.parse_args()

    if not settings.smtp_user or not settings.smtp_pass:
        print(
            "[testar_email] SMTP_USER/SMTP_PASS não configurados no .env - "
            "nada a testar. Defina-os e rode `docker compose up -d "
            "backend_api` para recarregar antes de tentar de novo.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(f"[testar_email] Enviando de {settings.smtp_user} "
          f"(via {settings.smtp_server}:{settings.smtp_port}) para {args.para}...")

    try:
        enviar_relatorio_email(
            destinatarios=[args.para],
            assunto="[SIAMP] E-mail de teste",
            corpo_html=(
                "<p>Este é um e-mail de teste do SIAMP, disparado por "
                "<code>python -m app.scripts.testar_email</code>.</p>"
                "<p>Se você recebeu isto, a configuração SMTP está "
                "funcionando corretamente.</p>"
            ),
            pdf_bytes=PDF_MINIMO,
        )
    except EnvioEmailError as exc:
        print(f"[testar_email] Falha ao enviar: {exc}", file=sys.stderr)
        print(
            "[testar_email] Confira SMTP_SERVER/SMTP_PORT/SMTP_USER/"
            "SMTP_PASS no .env. Para Gmail, lembre que é necessário usar "
            "uma 'senha de app' (App Password), não a senha normal da "
            "conta - veja https://myaccount.google.com/apppasswords",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    print("[testar_email] Enviado com sucesso! Confira a caixa de entrada de", args.para)


if __name__ == "__main__":
    main()
