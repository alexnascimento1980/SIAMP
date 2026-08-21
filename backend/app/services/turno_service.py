from datetime import datetime, time
import re

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.destinatario_relatorio import DestinatarioRelatorio
from app.models.maquina import Maquina
from app.models.ordem_producao import OrdemProducao
from app.models.produto import Produto
from app.models.registro_turno import RegistroHorario
from app.models.turno import Turno
from app.schemas.turno_schema import FechamentoTurnoCreate
from app.services.analytics import calcular_capacidade_esperada_registro, calcular_kpis_turno
from app.services.mailer import enviar_relatorio_email
from app.services.pdf_generator import gerar_relatorio_turno_pdf


STATUS_ASSINADO = "ASSINADO_DIGITALMENTE"


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


def buscar_registros_para_relatorio(db: Session, turno_id: int) -> list[dict]:
    """Registros de um turno formatados para o PDF de fechamento: hora,
    máquina, peça produzida, Ordem de Produção atendida, produção
    esperada e detalhe da parada (se houve)."""
    registros = (
        db.query(RegistroHorario, Maquina, Produto, OrdemProducao)
        .join(Maquina, RegistroHorario.maquina_id == Maquina.id)
        .outerjoin(Produto, RegistroHorario.produto_id == Produto.id)
        .outerjoin(OrdemProducao, RegistroHorario.ordem_producao_id == OrdemProducao.id)
        .filter(RegistroHorario.turno_id == turno_id)
        .order_by(RegistroHorario.hora_referencia, Maquina.numero_maquina)
        .all()
    )
    return [
        {
            "hora_referencia": reg.hora_referencia.strftime("%H:%M"),
            "numero_maquina": maq.numero_maquina,
            "produto_descricao": produto.descricao if produto else None,
            "numero_op": ordem.numero_op if ordem else None,
            "prod_executada": reg.prod_executada,
            "producao_esperada": round(
                calcular_capacidade_esperada_registro(reg, maq, produto)["capacidade_ajustada"]
            ),
            "inicio_parada": reg.inicio_parada.strftime("%H:%M") if reg.inicio_parada else None,
            "retomada": reg.retomada.strftime("%H:%M") if reg.retomada else None,
            "parada_programada": reg.parada_programada,
        }
        for reg, maq, produto, ordem in registros
    ]


def _resolver_maquinas(db: Session, dados: FechamentoTurnoCreate) -> dict:
    """Resolve todos os números de máquina do payload de uma vez, em vez de
    assumir que numero_maquina == id (primary key)."""
    numeros_maquina = {reg.numero_maquina for reg in dados.registros}
    return {
        maq.numero_maquina: maq
        for maq in db.query(Maquina).filter(Maquina.numero_maquina.in_(numeros_maquina)).all()
    }


def _validar_produtos(db: Session, dados: FechamentoTurnoCreate) -> None:
    """Confere que todo produto_id informado existe, para retornar um erro
    400 claro em vez de uma falha de FK crua vinda do banco."""
    ids_informados = {reg.produto_id for reg in dados.registros if reg.produto_id is not None}
    if not ids_informados:
        return

    ids_existentes = {
        produto_id
        for (produto_id,) in db.query(Produto.id).filter(Produto.id.in_(ids_informados)).all()
    }
    ids_invalidos = ids_informados - ids_existentes
    if ids_invalidos:
        raise ValueError(f"Peça(s) não encontrada(s): {sorted(ids_invalidos)}.")


def _validar_ordens_producao(db: Session, dados: FechamentoTurnoCreate) -> None:
    """Confere que toda ordem_producao_id informada existe, para retornar
    um erro 400 claro em vez de uma falha de FK crua vinda do banco."""
    ids_informados = {
        reg.ordem_producao_id for reg in dados.registros if reg.ordem_producao_id is not None
    }
    if not ids_informados:
        return

    ids_existentes = {
        ordem_id
        for (ordem_id,) in db.query(OrdemProducao.id)
        .filter(OrdemProducao.id.in_(ids_informados))
        .all()
    }
    ids_invalidos = ids_informados - ids_existentes
    if ids_invalidos:
        raise ValueError(f"Ordem(ns) de Produção não encontrada(s): {sorted(ids_invalidos)}.")


def _criar_registros(db: Session, turno: Turno, dados: FechamentoTurnoCreate) -> None:
    maquinas_por_numero = _resolver_maquinas(db, dados)
    _validar_produtos(db, dados)
    _validar_ordens_producao(db, dados)

    for reg in dados.registros:
        maquina = maquinas_por_numero.get(reg.numero_maquina)
        if maquina is None:
            raise ValueError(f"Máquina '{reg.numero_maquina}' não encontrada.")

        registro_db = RegistroHorario(
            turno_id=turno.id,
            maquina_id=maquina.id,
            produto_id=reg.produto_id,
            ordem_producao_id=reg.ordem_producao_id,
            hora_referencia=time.fromisoformat(reg.hora_referencia),
            prod_executada=reg.prod_executada,
            pecas_boas=reg.pecas_boas,
            refugo=reg.refugo,
            meta_producao=reg.meta_producao,
            ciclo_informado=reg.ciclo_informado,
            inicio_parada=reg.inicio_parada,
            retomada=reg.retomada,
            motivo_parada=reg.motivo_parada,
            parada_programada=reg.parada_programada,
            contador_parada=reg.contador_parada,
            contador_retomada=reg.contador_retomada,
        )
        db.add(registro_db)


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


def _agendar_email_relatorio(
    db: Session,
    turno: Turno,
    kpis: dict,
    background_tasks: BackgroundTasks,
) -> bool:
    """Monta o PDF e agenda o envio do relatório em background. Retorna
    True se o envio foi agendado (SMTP configurado e há pelo menos um
    destinatário), False se foi pulado."""
    destinatarios = _resolver_destinatarios(db)
    if not (settings.smtp_user and settings.smtp_pass and destinatarios):
        return False

    dados_turno = {
        "nome_turno": turno.nome_turno,
        "responsavel_nome": turno.responsavel_nome,
    }
    registros_pdf = buscar_registros_para_relatorio(db, turno.id)
    pdf_bytes = gerar_relatorio_turno_pdf(dados_turno, kpis, registros_pdf)

    assunto = (
        f"[SIAMP] Fechamento de Turno: {turno.nome_turno} - "
        f"{turno.data_registro.strftime('%d/%m/%y')}"
    )
    corpo = (
        "<p>Segue em anexo o relatório de produção.</p>"
        f"<p>Eficiência calculada: <b>{kpis['eficiencia_oee']}%</b>.</p>"
    )

    background_tasks.add_task(
        enviar_relatorio_email,
        destinatarios,
        assunto,
        corpo,
        pdf_bytes,
        montar_nome_arquivo_relatorio(turno.nome_turno, turno.data_registro),
    )
    return True


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
        regulador_nome=dados.regulador_nome,
        observacoes=dados.observacoes,
        status_assinatura=STATUS_ASSINADO,
    )

    db.add(novo_turno)
    db.flush()

    _criar_registros(db, novo_turno, dados)

    db.commit()
    db.refresh(novo_turno)

    kpis = calcular_kpis_turno(db, novo_turno.id)
    email_agendado = _agendar_email_relatorio(db, novo_turno, kpis, background_tasks)

    return {
        "status": "sucesso",
        "mensagem": "Turno encerrado com sucesso.",
        "turno_id": novo_turno.id,
        "status_assinatura": STATUS_ASSINADO,
        "relatorio_email_agendado": email_agendado,
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
    turno.regulador_nome = dados.regulador_nome
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


def reenviar_email_turno(
    db: Session,
    turno_id: int,
    background_tasks: BackgroundTasks,
) -> dict:
    """Reenvia o relatório de um turno já encerrado por e-mail, sob
    demanda (ex.: depois de uma correção que a pessoa considera
    relevante o suficiente para avisar de novo). Diferente do
    fechamento e da edição, isto é sempre uma ação explícita da pessoa
    - o sistema nunca reenvia sozinho a cada correção, para não gerar
    e-mails repetidos por ajustes pequenos."""
    turno = db.query(Turno).filter(Turno.id == turno_id).first()
    if turno is None:
        raise ValueError("Turno não encontrado.")

    kpis = calcular_kpis_turno(db, turno.id)
    email_agendado = _agendar_email_relatorio(db, turno, kpis, background_tasks)

    if not email_agendado:
        raise ValueError(
            "Envio de e-mail não está configurado: confira se SMTP_USER/"
            "SMTP_PASS estão definidos no .env e se há pelo menos um "
            "destinatário ativo cadastrado (tela Destinatários) ou em "
            "REPORT_RECIPIENTS."
        )

    return {
        "status": "sucesso",
        "mensagem": "Relatório reenviado por e-mail.",
        "turno_id": turno.id,
    }