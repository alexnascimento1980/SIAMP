"""Montagem e agendamento do e-mail de fechamento de turno (PDF do
relatório + PDF do dashboard) - extraído de turno_service.py, onde
vivia ao lado da lógica específica do modelo HORARIO mesmo sendo
totalmente genérico em relação a qual modelo de apontamento produziu
os dados.

agendar_email_relatorio() não sabe nada sobre HORARIO nem LANCAMENTO -
recebe kpis/registros_pdf já prontos, no formato que
gerar_relatorio_turno_pdf() espera, e cabe a quem chama (turno_service.
fechar_turno/fechar_turno_rascunho para HORARIO,
lancamento_service.fechar_turno_lancamento para LANCAMENTO) montar
esses dois argumentos a partir do próprio modelo antes de chamar.
Antes, registros_pdf tinha um valor padrão que buscava os dados do
modelo HORARIO internamente quando não informado - o que forçava este
módulo a depender de turno_service.py, sendo justamente a causa da
dependência circular que essa extração resolve (turno_service.py e
lancamento_service.py já precisavam um do outro por outros motivos;
adicionar mais um duplicava o problema)."""
import re
from datetime import datetime

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.destinatario_relatorio import DestinatarioRelatorio
from app.models.turno import Turno
from app.services.dashboard_service import calcular_metricas_acumuladas, montar_producao_por_turno
from app.services.mailer import enviar_relatorio_email
from app.services.pdf_generator import gerar_relatorio_dashboard_pdf, gerar_relatorio_turno_pdf


def montar_nome_arquivo_relatorio(nome_turno: str, data_registro: datetime) -> str:
    """Nome de arquivo amigável para o PDF do relatório - inclui o turno
    e a data, em vez de só 'relatorio_turno_<id>.pdf' (o id sozinho não
    diz nada para quem recebe o arquivo por e-mail ou baixa vários de
    uma vez). Usado tanto no download manual (GET /turnos/{id}/
    relatorio.pdf) quanto no anexo do e-mail.

    Ex.: "1º Turno (05:00 - 13:00)" + 19/08/2026 -> "relatorio_1-turno_19-08-2026.pdf"
    """
    # Corta na primeira parte antes de "(" - o range de horário já fica
    # implícito pela data e pelo nome do turno, sem precisar repetir os
    # dois-pontos (que não são válidos em nome de arquivo no Windows).
    prefixo = nome_turno.split("(")[0].strip()
    slug = re.sub(r"[^a-z0-9]+", "-", prefixo.lower()).strip("-") or "turno"
    data_formatada = data_registro.strftime("%d-%m-%Y")
    return f"relatorio_{slug}_{data_formatada}.pdf"


def _resolver_destinatarios(db: Session) -> list[str]:
    """Lista de e-mails que recebem o relatório de fechamento de turno.
    Prioriza os cadastrados na tela Destinatários (banco de dados); se
    nenhum estiver ativo lá, cai para REPORT_RECIPIENTS do .env
    (retrocompatibilidade, para ambientes que ainda não migraram para
    a tela)."""
    emails_db = [
        email
        for (email,) in db.query(DestinatarioRelatorio.email)
        .filter(DestinatarioRelatorio.ativo.is_(True))
        .all()
    ]
    return emails_db if emails_db else settings.report_recipients


def agendar_email_relatorio(
    db: Session,
    turno: Turno,
    kpis: dict,
    background_tasks: BackgroundTasks,
    registros_pdf: list[dict],
) -> bool:
    """Monta os PDFs (relatório de fechamento + dashboard do turno) e
    agenda o envio do e-mail em background. Retorna True se o envio
    foi agendado (algum provedor de e-mail configurado e há pelo menos
    um destinatário), False se foi pulado.

    registros_pdf é sempre exigido explicitamente (nunca montado
    internamente) - cabe a quem chama buscar os dados no formato certo
    para o modelo de apontamento do turno em questão (ver
    turno_service.buscar_registros_para_relatorio para HORARIO,
    lancamento_service.montar_registros_pdf_lancamento para
    LANCAMENTO)."""
    destinatarios = _resolver_destinatarios(db)
    # Verifica os dois provedores possíveis (Brevo OU SMTP) - checar só
    # smtp_user/smtp_pass aqui faria o envio parar silenciosamente se
    # só o Brevo estivesse configurado (caso de produção no Render).
    provedor_configurado = bool(settings.brevo_api_key) or bool(
        settings.smtp_user and settings.smtp_pass
    )
    if not (provedor_configurado and destinatarios):
        return False

    dados_turno = {
        "nome_turno": turno.nome_turno,
        "responsavel_nome": turno.responsavel_nome,
        "observacoes": turno.observacoes,
    }
    pdf_turno = gerar_relatorio_turno_pdf(dados_turno, kpis, registros_pdf)

    metricas_por_periodo = {
        periodo: calcular_metricas_acumuladas(db, periodo=periodo)
        for periodo in ("diario", "semanal", "mensal")
    }
    producao_por_turno = montar_producao_por_turno(db)
    pdf_dashboard = gerar_relatorio_dashboard_pdf(
        dados_turno, kpis, metricas_por_periodo, producao_por_turno
    )

    assunto = (
        f"[SIAMP] Fechamento de Turno: {turno.nome_turno} - "
        f"{turno.data_registro.strftime('%d/%m/%y')}"
    )
    corpo = (
        "<p>Segue em anexo o relatório de produção e o dashboard do "
        "turno (desempenho comparado ao acumulado diário/semanal/"
        "mensal).</p>"
        f"<p>Eficiência calculada: <b>{kpis['eficiencia_oee']}%</b>.</p>"
    )

    nome_base = montar_nome_arquivo_relatorio(turno.nome_turno, turno.data_registro)
    nome_dashboard = nome_base.replace(".pdf", "_dashboard.pdf")

    background_tasks.add_task(
        enviar_relatorio_email,
        destinatarios,
        assunto,
        corpo,
        [(pdf_turno, nome_base), (pdf_dashboard, nome_dashboard)],
    )
    return True
