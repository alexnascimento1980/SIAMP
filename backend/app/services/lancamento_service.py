from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.timezone import agora_brasilia
from app.models.lancamento import TIPO_PARADA_PROGRAMADA, TIPO_PRODUCAO, Lancamento
from app.models.maquina import Maquina
from app.models.ordem_producao import OrdemProducao
from app.models.produto import Produto
from app.models.turno import Turno
from app.schemas.lancamento_schema import LancamentoCreate, TurnoLancamentoCreate, TurnoLancamentoRascunho
from app.services.analytics import (
    calcular_capacidade_esperada_lancamento,
    calcular_kpis_turno_lancamento,
    resolver_ciclo_cavidades,
)
from app.services.turno_service import STATUS_ASSINADO, STATUS_EM_ANDAMENTO, agendar_email_relatorio

MODELO_LANCAMENTO = "LANCAMENTO"


def _resolver_maquinas(db: Session, lancamentos: list[LancamentoCreate]) -> dict[str, Maquina]:
    numeros = {lanc.numero_maquina for lanc in lancamentos}
    if not numeros:
        return {}
    maquinas = db.query(Maquina).filter(Maquina.numero_maquina.in_(numeros)).all()
    por_numero = {m.numero_maquina: m for m in maquinas}
    faltando = numeros - por_numero.keys()
    if faltando:
        raise ValueError(f"Máquina(s) não encontrada(s): {sorted(faltando)}.")
    return por_numero


def _validar_produtos(db: Session, lancamentos: list[LancamentoCreate]) -> None:
    ids = {lanc.produto_id for lanc in lancamentos if lanc.produto_id is not None}
    if not ids:
        return
    existentes = {pid for (pid,) in db.query(Produto.id).filter(Produto.id.in_(ids)).all()}
    faltando = ids - existentes
    if faltando:
        raise ValueError(f"Peça(s) não encontrada(s): {sorted(faltando)}.")


def _validar_ordens_producao(db: Session, lancamentos: list[LancamentoCreate]) -> None:
    ids = {lanc.ordem_producao_id for lanc in lancamentos if lanc.ordem_producao_id is not None}
    if not ids:
        return
    existentes = {
        oid for (oid,) in db.query(OrdemProducao.id).filter(OrdemProducao.id.in_(ids)).all()
    }
    faltando = ids - existentes
    if faltando:
        raise ValueError(f"Ordem(ns) de Produção não encontrada(s): {sorted(faltando)}.")


def _criar_lancamentos(db: Session, turno: Turno, lancamentos: list[LancamentoCreate]) -> None:
    maquinas_por_numero = _resolver_maquinas(db, lancamentos)
    _validar_produtos(db, lancamentos)
    _validar_ordens_producao(db, lancamentos)

    for lanc in lancamentos:
        maquina = maquinas_por_numero[lanc.numero_maquina]
        db.add(
            Lancamento(
                turno_id=turno.id,
                maquina_id=maquina.id,
                tipo=lanc.tipo,
                horario_inicio=lanc.horario_inicio,
                horario_fim=lanc.horario_fim,
                produto_id=lanc.produto_id,
                ordem_producao_id=lanc.ordem_producao_id,
                quantidade=lanc.quantidade,
                ciclo_informado=lanc.ciclo_informado,
                cavidades_informado=lanc.cavidades_informado,
                motivo=lanc.motivo,
            )
        )


def montar_registros_pdf_lancamento(db: Session, turno_id: int) -> list[dict]:
    """Converte os lançamentos de um turno para o mesmo formato de linha
    já usado pelo relatório em PDF do modelo por hora (ver
    turno_service.buscar_registros_para_relatorio) - reaproveita o
    gerador de PDF sem nenhuma mudança nele."""
    linhas = (
        db.query(Lancamento, Maquina, Produto, OrdemProducao)
        .join(Maquina, Lancamento.maquina_id == Maquina.id)
        .outerjoin(Produto, Lancamento.produto_id == Produto.id)
        .outerjoin(OrdemProducao, Lancamento.ordem_producao_id == OrdemProducao.id)
        .filter(Lancamento.turno_id == turno_id)
        .order_by(Lancamento.horario_inicio, Maquina.numero_maquina)
        .all()
    )

    resultado = []
    for lanc, maq, produto, ordem in linhas:
        inicio_str = lanc.horario_inicio.strftime("%H:%M")
        fim_str = lanc.horario_fim.strftime("%H:%M")
        if lanc.tipo == TIPO_PRODUCAO:
            esperado = calcular_capacidade_esperada_lancamento(lanc, maq, produto)
            # Produção real aconteceu, mas não foi possível calcular uma
            # capacidade esperada (peça/máquina sem ciclo ou cavidades
            # cadastrados) - mostrar "0" nesse caso é enganoso, parece uma
            # meta cumprida com folga quando na verdade não há meta
            # nenhuma para comparar. "N/D" deixa isso explícito e aponta
            # direto para o cadastro incompleto.
            esperado_exibicao = "N/D" if esperado == 0 and (lanc.quantidade or 0) > 0 else esperado

            # Mostra qual ciclo e quais cavidades entraram de fato na
            # conta (e de onde vieram) - sem isso, não dá pra saber, só
            # olhando o relatório, se um "Esperado" divergente da
            # produção real vem de um valor informado impreciso ou do
            # cadastro da peça desatualizado.
            ciclo_padrao, cavidades_padrao = resolver_ciclo_cavidades(maq, produto)
            if lanc.ciclo_informado:
                ciclo_texto = f"ciclo informado: {lanc.ciclo_informado}s"
            elif ciclo_padrao:
                ciclo_texto = f"ciclo cadastrado: {ciclo_padrao}s"
            else:
                ciclo_texto = "sem ciclo cadastrado"
            if lanc.cavidades_informado:
                cavidades_texto = f"cavidades informadas: {lanc.cavidades_informado}"
            elif cavidades_padrao:
                cavidades_texto = f"cavidades cadastradas: {cavidades_padrao}"
            else:
                cavidades_texto = "sem cavidades cadastradas"
            descricao_com_ciclo = (
                f"{produto.descricao} ({ciclo_texto}; {cavidades_texto})"
                if produto else f"({ciclo_texto}; {cavidades_texto})"
            )

            resultado.append({
                "hora_referencia": f"{inicio_str}-{fim_str}",
                "numero_maquina": maq.numero_maquina,
                "produto_descricao": descricao_com_ciclo,
                "numero_op": ordem.numero_op if ordem else None,
                "prod_executada": lanc.quantidade or 0,
                "producao_esperada": esperado_exibicao,
                "inicio_parada": None,
                "retomada": None,
                "parada_programada": False,
            })
        else:
            resultado.append({
                "hora_referencia": f"{inicio_str}-{fim_str}",
                "numero_maquina": maq.numero_maquina,
                "produto_descricao": lanc.motivo or (
                    "Parada programada" if lanc.tipo == TIPO_PARADA_PROGRAMADA else "Falha na injetora"
                ),
                "numero_op": None,
                "prod_executada": 0,
                "producao_esperada": 0,
                "inicio_parada": inicio_str,
                "retomada": fim_str,
                "parada_programada": lanc.tipo == TIPO_PARADA_PROGRAMADA,
            })
    return resultado


def salvar_rascunho_lancamento(
    db: Session,
    dados: TurnoLancamentoRascunho,
    turno_id: int | None,
) -> dict:
    if turno_id is None:
        turno = Turno(
            nome_turno=dados.nome_turno,
            responsavel_nome=dados.responsavel_nome,
            regulador_nome=dados.regulador_nome,
            observacoes=dados.observacoes,
            status_assinatura=STATUS_EM_ANDAMENTO,
            modelo_apontamento=MODELO_LANCAMENTO,
        )
        db.add(turno)
        db.flush()
    else:
        turno = db.query(Turno).filter(Turno.id == turno_id).first()
        if turno is None:
            raise ValueError("Turno não encontrado.")
        if turno.modelo_apontamento != MODELO_LANCAMENTO:
            raise ValueError("Este turno não usa o modelo de lançamentos livres.")
        if turno.status_assinatura != STATUS_EM_ANDAMENTO:
            raise ValueError(
                "Este turno já foi fechado - use a tela de Histórico para "
                "corrigi-lo, em vez de salvar como rascunho."
            )
        turno.nome_turno = dados.nome_turno
        turno.responsavel_nome = dados.responsavel_nome
        turno.regulador_nome = dados.regulador_nome
        turno.observacoes = dados.observacoes
        db.query(Lancamento).filter(Lancamento.turno_id == turno_id).delete()
        db.flush()

    if dados.lancamentos:
        _criar_lancamentos(db, turno, dados.lancamentos)

    db.commit()
    db.refresh(turno)

    return {
        "status": "sucesso",
        "mensagem": "Rascunho salvo.",
        "turno_id": turno.id,
        "status_assinatura": STATUS_EM_ANDAMENTO,
    }


def fechar_turno_lancamento(
    db: Session,
    dados: TurnoLancamentoCreate,
    background_tasks: BackgroundTasks,
    turno_id: int | None = None,
) -> dict:
    """Fecha um turno usando o modelo de lançamentos livres - cria um
    novo (turno_id=None) ou finaliza um rascunho já existente."""
    if not dados.lancamentos:
        raise ValueError("O fechamento do turno deve possuir pelo menos um lançamento.")

    if turno_id is None:
        turno = Turno(
            nome_turno=dados.nome_turno,
            responsavel_nome=dados.responsavel_nome,
            regulador_nome=dados.regulador_nome,
            observacoes=dados.observacoes,
            status_assinatura=STATUS_ASSINADO,
            modelo_apontamento=MODELO_LANCAMENTO,
        )
        db.add(turno)
        db.flush()
    else:
        turno = db.query(Turno).filter(Turno.id == turno_id).first()
        if turno is None:
            raise ValueError("Turno não encontrado.")
        if turno.modelo_apontamento != MODELO_LANCAMENTO:
            raise ValueError("Este turno não usa o modelo de lançamentos livres.")
        if turno.status_assinatura == STATUS_ASSINADO:
            raise ValueError("Este turno já está fechado.")
        turno.nome_turno = dados.nome_turno
        turno.responsavel_nome = dados.responsavel_nome
        turno.regulador_nome = dados.regulador_nome
        turno.observacoes = dados.observacoes
        turno.status_assinatura = STATUS_ASSINADO
        db.query(Lancamento).filter(Lancamento.turno_id == turno_id).delete()
        db.flush()

    _criar_lancamentos(db, turno, dados.lancamentos)

    db.commit()
    db.refresh(turno)

    kpis = calcular_kpis_turno_lancamento(db, turno.id)
    registros_pdf = montar_registros_pdf_lancamento(db, turno.id)
    email_agendado = agendar_email_relatorio(db, turno, kpis, background_tasks, registros_pdf)

    return {
        "status": "sucesso",
        "mensagem": "Turno encerrado com sucesso.",
        "turno_id": turno.id,
        "status_assinatura": STATUS_ASSINADO,
        "relatorio_email_agendado": email_agendado,
        "kpis": kpis,
    }


def editar_turno_lancamento(
    db: Session,
    turno_id: int,
    dados: TurnoLancamentoCreate,
    usuario_id: int,
) -> dict:
    """Corrige um turno de lançamentos já encerrado (ASSINADO_DIGITALMENTE):
    substitui integralmente seus lançamentos e recalcula os KPIs. Não
    reenvia e-mail (evita duplicidade) - mesmo comportamento de
    turno_service.editar_turno (modelo por hora), espelhado aqui para
    o modelo de lançamentos livres. Restrito a ADMIN/SUPERVISOR (ver
    endpoint)."""
    if not dados.lancamentos:
        raise ValueError("O turno deve possuir pelo menos um lançamento.")

    turno = db.query(Turno).filter(Turno.id == turno_id).first()
    if turno is None:
        raise ValueError("Turno não encontrado.")
    if turno.modelo_apontamento != MODELO_LANCAMENTO:
        raise ValueError("Este turno não usa o modelo de lançamentos livres.")

    turno.nome_turno = dados.nome_turno
    turno.responsavel_nome = dados.responsavel_nome
    turno.regulador_nome = dados.regulador_nome
    turno.observacoes = dados.observacoes
    turno.editado_por_id = usuario_id
    turno.editado_em = agora_brasilia()

    db.query(Lancamento).filter(Lancamento.turno_id == turno_id).delete()
    db.flush()

    _criar_lancamentos(db, turno, dados.lancamentos)

    db.commit()
    db.refresh(turno)

    kpis = calcular_kpis_turno_lancamento(db, turno.id)

    return {
        "status": "sucesso",
        "mensagem": "Turno corrigido com sucesso.",
        "turno_id": turno.id,
        "kpis": kpis,
    }
