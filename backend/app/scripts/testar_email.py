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
from app.core.timezone import agora_brasilia
import sys

from app.core.config import settings
from app.services.mailer import EnvioEmailError, enviar_relatorio_email
from app.services.pdf_generator import gerar_relatorio_turno_pdf
from app.services.turno_service import montar_nome_arquivo_relatorio


def _gerar_pdf_de_exemplo() -> bytes:
    """PDF de exemplo com o mesmo gerador usado no fechamento real de
    turno, para o e-mail de teste mostrar visualmente como o relatório
    de verdade se parece (em vez de um PDF em branco, que só validaria
    o envio, não o conteúdo)."""
    dados_turno = {
        "nome_turno": "[EXEMPLO] 1º Turno (05:00 - 13:00)",
        "responsavel_nome": "Nome do Responsável",
        "observacoes": "Exemplo de observação geral digitada pelo responsável no fechamento do turno.",
    }
    kpis = {
        "total_produzido": 850,
        "total_esperado": 960,
        "minutos_parados": 20,
        "minutos_parados_programados": 20,
        "minutos_parados_nao_programados": 0,
        "total_pecas_boas": 830,
        "total_refugo": 20,
        "indice_producao": 88.5,
        "indice_qualidade": 97.6,
        "eficiencia_oee": 86.4,
        "alerta_ia": "Operação normal",
    }
    registros = [
        {
            "hora_referencia": "05:00",
            "numero_maquina": "1",
            "produto_descricao": "Peça de exemplo",
            "prod_executada": 320,
            "producao_esperada": 320,
            "inicio_parada": None,
            "retomada": None,
            "parada_programada": False,
        },
        {
            "hora_referencia": "06:00",
            "numero_maquina": "1",
            "produto_descricao": "Peça de exemplo",
            "prod_executada": 530,
            "producao_esperada": 640,
            "inicio_parada": "06:00",
            "retomada": "06:20",
            "parada_programada": True,
        },
    ]
    return gerar_relatorio_turno_pdf(dados_turno, kpis, registros)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--para",
        required=True,
        help="E-mail de destino do teste (ex.: seu-email@empresa.com)",
    )
    args = parser.parse_args()

    if not settings.brevo_api_key and not (settings.smtp_user and settings.smtp_pass):
        print(
            "[testar_email] Nenhum provedor de e-mail configurado no .env - "
            "nada a testar. Defina BREVO_API_KEY (recomendado em hospedagens "
            "que bloqueiam portas SMTP, ex. Render) ou SMTP_USER/SMTP_PASS, e "
            "rode `docker compose up -d backend_api` para recarregar antes "
            "de tentar de novo.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if settings.brevo_api_key:
        print(f"[testar_email] Enviando de {settings.smtp_from} via API do "
              f"Brevo para {args.para}...")
    else:
        print(f"[testar_email] Enviando de {settings.smtp_from} "
              f"(autenticando como {settings.smtp_user} via "
              f"{settings.smtp_server}:{settings.smtp_port}) para {args.para}...")

    try:
        enviar_relatorio_email(
            destinatarios=[args.para],
            assunto="[SIAMP] E-mail de teste",
            corpo_html=(
                "<p>Este é um e-mail de teste do SIAMP, disparado por "
                "<code>python -m app.scripts.testar_email</code>.</p>"
                "<p>Se você recebeu isto, a configuração SMTP está "
                "funcionando corretamente. O PDF em anexo é um "
                "<b>exemplo com dados fictícios</b>, só para mostrar como "
                "o relatório real se parece - o relatório de verdade é "
                "gerado a partir dos dados reais quando um turno é "
                "fechado.</p>"
            ),
            anexos=[(
                _gerar_pdf_de_exemplo(),
                montar_nome_arquivo_relatorio("[EXEMPLO] 1º Turno", agora_brasilia()),
            )],
        )
    except EnvioEmailError as exc:
        print(f"[testar_email] Falha ao enviar: {exc}", file=sys.stderr)
        if settings.brevo_api_key:
            print(
                "[testar_email] Confira BREVO_API_KEY no .env, e se o "
                "remetente (SMTP_FROM) está validado no painel do Brevo "
                "(Settings > Senders, Domains & Dedicated IPs).",
                file=sys.stderr,
            )
        else:
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
