from datetime import datetime, time

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.maquina import Maquina
from app.models.registro_turno import RegistroHorario
from app.models.turno import Turno
from app.schemas.turno_schema import FechamentoTurnoCreate
from app.services.analytics import calcular_kpis_turno
from app.services.mailer import enviar_relatorio_email
from app.services.pdf_generator import gerar_relatorio_turno_pdf


STATUS_ASSINADO = "ASSINADO_DIGITALMENTE"


def _resolver_maquinas(db: Session, dados: FechamentoTurnoCreate) -> dict:
    """Resolve todos os números de máquina do payload de uma vez, em vez de
    assumir que numero_maquina == id (primary key)."""
    numeros_maquina = {reg.numero_maquina for reg in dados.registros}
    return {
        maq.numero_maquina: maq
        for maq in db.query(Maquina).filter(Maquina.numero_maquina.in_(numeros_maquina)).all()
    }


def _criar_registros(db: Session, turno: Turno, dados: FechamentoTurnoCreate) -> None:
    maquinas_por_numero = _resolver_maquinas(db, dados)

    for reg in dados.registros:
        maquina = maquinas_por_numero.get(reg.numero_maquina)
        if maquina is None:
            raise ValueError(f"Máquina '{reg.numero_maquina}' não encontrada.")

        registro_db = RegistroHorario(
            turno_id=turno.id,
            maquina_id=maquina.id,
            hora_referencia=time.fromisoformat(reg.hora_referencia),
            prod_executada=reg.prod_executada,
            pecas_boas=reg.pecas_boas,
            refugo=reg.refugo,
            meta_producao=reg.meta_producao,
            inicio_parada=reg.inicio_parada,
            retomada=reg.retomada,
            motivo_parada=reg.motivo_parada,
        )
        db.add(registro_db)


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

    _criar_registros(db, novo_turno, dados)

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


def editar_turno(
    db: Session,
    turno_id: int,
    dados: FechamentoTurnoCreate,
    usuario_id: int,
) -> dict:
    """
    Corrige um turno já encerrado: substitui integralmente seus registros
    pelos informados e recalcula os KPIs. Não reenvia e-mail (evita
    duplicidade) — o PDF sob demanda (GET /turnos/{id}/relatorio.pdf) já
    reflete os dados corrigidos automaticamente, pois é gerado na hora.
    """
    if not dados.registros:
        raise ValueError("O turno deve possuir pelo menos um registro.")

    turno = db.query(Turno).filter(Turno.id == turno_id).first()
    if turno is None:
        raise ValueError("Turno não encontrado.")

    turno.nome_turno = dados.nome_turno
    turno.responsavel_nome = dados.responsavel_nome
    turno.observacoes = dados.observacoes
    turno.editado_por_id = usuario_id
    turno.editado_em = datetime.utcnow()

    # Substitui todos os registros (mais simples e seguro do que tentar
    # casar registro a registro por hora/máquina).
    db.query(RegistroHorario).filter(RegistroHorario.turno_id == turno_id).delete()
    db.flush()

    _criar_registros(db, turno, dados)

    db.commit()
    db.refresh(turno)

    kpis = calcular_kpis_turno(db, turno.id)

    return {
        "status": "sucesso",
        "mensagem": "Turno corrigido com sucesso.",
        "turno_id": turno.id,
        "kpis": kpis,
    }