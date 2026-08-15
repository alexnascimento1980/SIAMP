from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.registro_turno import RegistroHorario, Turno
from app.schemas.turno_schema import FechamentoTurnoCreate
from app.services.analytics import calcular_kpis_turno
from app.services.mailer import enviar_relatorio_email
from app.services.pdf_generator import gerar_relatorio_turno_pdf


STATUS_ASSINADO = "ASSINADO_DIGITALMENTE"


def fechar_turno(
    db: Session,
    dados: FechamentoTurnoCreate,
    background_tasks: BackgroundTasks,
) -> dict:
    if not dados.registros:
        raise ValueError("O fechamento do turno deve possuir pelo menos um registro.")

    novo_turno = Turno(
        nome_turno=dados.nome_turno,
        responsavel_nome=dados.responsavel_nome,
        observacoes=dados.observacoes,
        status_assinatura=STATUS_ASSINADO,
    )

    db.add(novo_turno)
    db.flush()

    for reg in dados.registros:
        registro_db = RegistroHorario(
            turno_id=novo_turno.id,
            maquina_id=reg.maquina_id,
            hora_referencia=reg.hora_referencia,
            prod_executada=reg.prod_executada,
            inicio_parada=reg.inicio_parada,
            retomada=reg.retomada,
            motivo_parada=reg.motivo_parada,
        )
        db.add(registro_db)

    db.commit()
    db.refresh(novo_turno)

    kpis = calcular_kpis_turno(db, novo_turno.id)

    dados_turno = {
        "nome_turno": novo_turno.nome_turno,
        "responsavel_nome": novo_turno.responsavel_nome,
    }

    pdf_bytes = gerar_relatorio_turno_pdf(dados_turno, kpis)

    if settings.smtp_user and settings.smtp_pass and settings.report_recipients:
        assunto = f"[SIAMP] Fechamento de Turno: {novo_turno.nome_turno}"
        corpo = (
            "<p>Segue em anexo o relatório de produção.</p>"
            f"<p>Eficiência calculada: <b>{kpis['eficiencia_oee']}%</b>.</p>"
        )

        background_tasks.add_task(
            enviar_relatorio_email,
            settings.report_recipients,
            assunto,
            corpo,
            pdf_bytes,
        )

    return {
        "status": "sucesso",
        "mensagem": "Turno encerrado com sucesso.",
        "turno_id": novo_turno.id,
        "status_assinatura": STATUS_ASSINADO,
        "relatorio_email_agendado": bool(
            settings.smtp_user
            and settings.smtp_pass
            and settings.report_recipients
        ),
        "kpis": kpis,
    }
