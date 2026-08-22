from datetime import date, datetime, time
import csv
import io
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
from app.schemas.turno_schema import FechamentoTurnoCreate, RascunhoTurnoCreate
from app.services.analytics import calcular_capacidade_esperada_registro, calcular_kpis_turno
from app.services.mailer import enviar_relatorio_email
from app.services.pdf_generator import gerar_relatorio_turno_pdf


STATUS_ASSINADO = "ASSINADO_DIGITALMENTE"
# Turno salvo como rascunho, ainda sendo preenchido - permite salvar o
# progresso ao longo do turno sem disparar PDF/e-mail a cada gravação;
# só a transição para STATUS_ASSINADO (fechar_turno_rascunho) dispara
# o envio.
STATUS_EM_ANDAMENTO = "EM_ANDAMENTO"


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


def exportar_registros_csv(
    db: Session,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> str:
    """Exporta os apontamentos horários de turnos fechados, num período
    opcional, em CSV (uma linha por hora/máquina apontada) - para
    análise em Excel, Power BI ou ferramentas similares. Usa ';' como
    separador (não ','), padrão esperado pelo Excel em configuração
    regional Brasil ao abrir o arquivo direto com duplo clique.

    Só turnos fechados (ASSINADO_DIGITALMENTE) entram - um rascunho
    ainda em andamento pode mudar completamente até o fechamento, não
    faz sentido exportar como se fosse dado definitivo.
    """
    query = (
        db.query(RegistroHorario, Turno, Maquina, Produto, OrdemProducao)
        .join(Turno, RegistroHorario.turno_id == Turno.id)
        .join(Maquina, RegistroHorario.maquina_id == Maquina.id)
        .outerjoin(Produto, RegistroHorario.produto_id == Produto.id)
        .outerjoin(OrdemProducao, RegistroHorario.ordem_producao_id == OrdemProducao.id)
        .filter(Turno.status_assinatura == STATUS_ASSINADO)
    )
    if data_inicio:
        query = query.filter(Turno.data_registro >= datetime.combine(data_inicio, time.min))
    if data_fim:
        query = query.filter(Turno.data_registro <= datetime.combine(data_fim, time.max))

    registros = query.order_by(Turno.data_registro, RegistroHorario.hora_referencia).all()

    saida = io.StringIO()
    saida.write("\ufeff")  # BOM - Excel reconhece UTF-8 com acentuação corretamente
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow([
        "data_turno", "nome_turno", "lider", "regulador", "numero_maquina",
        "hora_referencia", "produto_codigo", "produto_descricao", "numero_op",
        "prod_executada", "producao_esperada", "ciclo_informado",
        "inicio_parada", "retomada", "parada_programada", "contador_parada",
        "contador_retomada", "motivo_parada",
    ])

    for reg, turno, maq, produto, ordem in registros:
        capacidade = calcular_capacidade_esperada_registro(reg, maq, produto)
        escritor.writerow([
            turno.data_registro.strftime("%d/%m/%Y"),
            turno.nome_turno,
            turno.responsavel_nome,
            turno.regulador_nome or "",
            maq.numero_maquina,
            reg.hora_referencia.strftime("%H:%M"),
            produto.codigo if produto else "",
            produto.descricao if produto else "",
            ordem.numero_op if ordem else "",
            reg.prod_executada,
            round(capacidade["capacidade_ajustada"]),
            reg.ciclo_informado or "",
            reg.inicio_parada.strftime("%H:%M") if reg.inicio_parada else "",
            reg.retomada.strftime("%H:%M") if reg.retomada else "",
            "Sim" if reg.parada_programada else "Não",
            reg.contador_parada if reg.contador_parada is not None else "",
            reg.contador_retomada if reg.contador_retomada is not None else "",
            reg.motivo_parada or "",
        ])

    return saida.getvalue()


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


def agendar_email_relatorio(
    db: Session,
    turno: Turno,
    kpis: dict,
    background_tasks: BackgroundTasks,
    registros_pdf: list[dict] | None = None,
) -> bool:
    """Monta o PDF e agenda o envio do relatório em background. Retorna
    True se o envio foi agendado (SMTP configurado e há pelo menos um
    destinatário), False se foi pulado.

    registros_pdf: se não informado, monta a partir de
    buscar_registros_para_relatorio (modelo por hora). Passar
    explicitamente permite reaproveitar esta função para o modelo de
    lançamentos livres (ver lancamento_service.py), que monta os
    registros num formato equivalente."""
    destinatarios = _resolver_destinatarios(db)
    if not (settings.smtp_user and settings.smtp_pass and destinatarios):
        return False

    dados_turno = {
        "nome_turno": turno.nome_turno,
        "responsavel_nome": turno.responsavel_nome,
    }
    if registros_pdf is None:
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
    email_agendado = agendar_email_relatorio(db, novo_turno, kpis, background_tasks)

    return {
        "status": "sucesso",
        "mensagem": "Turno encerrado com sucesso.",
        "turno_id": novo_turno.id,
        "status_assinatura": STATUS_ASSINADO,
        "relatorio_email_agendado": email_agendado,
        "kpis": kpis,
    }


def salvar_rascunho(
    db: Session,
    dados: RascunhoTurnoCreate,
    turno_id: int | None,
) -> dict:
    """Salva (cria ou atualiza) o progresso de um turno ainda em
    andamento, sem disparar PDF/e-mail - permite ao operador ir
    gravando o apontamento ao longo do turno, não só no fechamento.
    Liberado para qualquer usuário logado (é o trabalho da própria
    pessoa, diferente de corrigir um turno já fechado, que exige
    ADMIN/SUPERVISOR - ver editar_turno)."""
    if turno_id is None:
        turno = Turno(
            nome_turno=dados.nome_turno,
            responsavel_nome=dados.responsavel_nome,
            regulador_nome=dados.regulador_nome,
            observacoes=dados.observacoes,
            status_assinatura=STATUS_EM_ANDAMENTO,
        )
        db.add(turno)
        db.flush()
    else:
        turno = db.query(Turno).filter(Turno.id == turno_id).first()
        if turno is None:
            raise ValueError("Turno não encontrado.")
        if turno.status_assinatura != STATUS_EM_ANDAMENTO:
            raise ValueError(
                "Este turno já foi fechado - use a tela de Histórico para "
                "corrigi-lo, em vez de salvar como rascunho."
            )
        turno.nome_turno = dados.nome_turno
        turno.responsavel_nome = dados.responsavel_nome
        turno.regulador_nome = dados.regulador_nome
        turno.observacoes = dados.observacoes
        db.query(RegistroHorario).filter(RegistroHorario.turno_id == turno_id).delete()
        db.flush()

    if dados.registros:
        _criar_registros(db, turno, dados)

    db.commit()
    db.refresh(turno)

    return {
        "status": "sucesso",
        "mensagem": "Rascunho salvo.",
        "turno_id": turno.id,
        "status_assinatura": STATUS_EM_ANDAMENTO,
    }


def fechar_turno_rascunho(
    db: Session,
    turno_id: int,
    dados: FechamentoTurnoCreate,
    background_tasks: BackgroundTasks,
) -> dict:
    """Fecha definitivamente um turno que vinha sendo salvo como
    rascunho: grava os registros finais, muda o status para
    ASSINADO_DIGITALMENTE e - só agora - agenda o PDF/e-mail. Depois
    dessa chamada, o turno passa a seguir as mesmas regras de um turno
    fechado direto (correção só via ADMIN/SUPERVISOR)."""
    if not dados.registros:
        raise ValueError("O fechamento do turno deve possuir pelo menos um registro.")

    turno = db.query(Turno).filter(Turno.id == turno_id).first()
    if turno is None:
        raise ValueError("Turno não encontrado.")
    if turno.status_assinatura == STATUS_ASSINADO:
        raise ValueError("Este turno já está fechado.")

    turno.nome_turno = dados.nome_turno
    turno.responsavel_nome = dados.responsavel_nome
    turno.regulador_nome = dados.regulador_nome
    turno.observacoes = dados.observacoes
    turno.status_assinatura = STATUS_ASSINADO

    db.query(RegistroHorario).filter(RegistroHorario.turno_id == turno_id).delete()
    db.flush()

    _criar_registros(db, turno, dados)

    db.commit()
    db.refresh(turno)

    kpis = calcular_kpis_turno(db, turno.id)
    email_agendado = agendar_email_relatorio(db, turno, kpis, background_tasks)

    return {
        "status": "sucesso",
        "mensagem": "Turno encerrado com sucesso.",
        "turno_id": turno.id,
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

    if turno.modelo_apontamento == "LANCAMENTO":
        from app.services.analytics import calcular_kpis_turno_lancamento
        from app.services.lancamento_service import montar_registros_pdf_lancamento

        kpis = calcular_kpis_turno_lancamento(db, turno.id)
        registros_pdf = montar_registros_pdf_lancamento(db, turno.id)
    else:
        kpis = calcular_kpis_turno(db, turno.id)
        registros_pdf = None  # agendar_email_relatorio monta via buscar_registros_para_relatorio

    email_agendado = agendar_email_relatorio(db, turno, kpis, background_tasks, registros_pdf)

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