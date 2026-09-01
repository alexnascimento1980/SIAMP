from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import exigir_perfil, get_current_user
from app.core.database import get_db
from app.models.lancamento import Lancamento
from app.models.maquina import Maquina
from app.models.ordem_producao import OrdemProducao
from app.models.produto import Produto
from app.models.registro_turno import RegistroHorario
from app.models.turno import Turno
from app.models.usuario import Usuario
from app.schemas.lancamento_schema import (
    LancamentoDetail,
    TurnoLancamentoCreate,
    TurnoLancamentoRascunho,
)
from app.schemas.turno_schema import (
    FechamentoTurnoCreate,
    RascunhoTurnoCreate,
    RegistroHorarioDetail,
    TurnoDetail,
    TurnoListItem,
    TurnosMarcarTeste,
)
from app.services.analytics import (
    calcular_capacidade_esperada_lancamento,
    calcular_kpis_turno,
    calcular_kpis_varios_turnos_generico,
)
from app.services.lancamento_service import (
    editar_turno_lancamento,
    fechar_turno_lancamento,
    montar_registros_pdf_lancamento,
    salvar_rascunho_lancamento,
)
from app.services.pdf_generator import gerar_relatorio_turno_pdf
from app.services.turno_service import (
    buscar_registros_para_relatorio,
    editar_turno,
    exportar_registros_csv,
    fechar_turno,
    fechar_turno_rascunho,
    montar_nome_arquivo_relatorio,
    reenviar_email_turno,
    salvar_rascunho,
)


router = APIRouter(prefix="/turnos", tags=["Turnos"])


@router.get("/", response_model=list[TurnoListItem])
def listar_turnos(
    limite: int = 50,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """
    Histórico de turnos encerrados, mais recentes primeiro, com os KPIs
    já calculados para exibição direta na tela de histórico.
    """
    turnos = (
        db.query(Turno)
        .order_by(Turno.data_registro.desc())
        .limit(min(limite, 200))
        .all()
    )

    # Uma única query para os KPIs de todos os turnos listados, em vez de
    # uma consulta por turno (evita N+1 em listas grandes de histórico).
    # Cobre os dois modelos de apontamento misturados na mesma lista.
    kpis_por_turno = calcular_kpis_varios_turnos_generico(db, turnos)

    resultado = []
    for turno in turnos:
        kpis = kpis_por_turno[turno.id]
        resultado.append(
            TurnoListItem(
                id=turno.id,
                nome_turno=turno.nome_turno,
                responsavel_nome=turno.responsavel_nome,
                data_registro=turno.data_registro,
                status_assinatura=turno.status_assinatura,
                modelo_apontamento=turno.modelo_apontamento,
                total_produzido=kpis["total_produzido"],
                eficiencia_oee=kpis["eficiencia_oee"],
                indice_qualidade=kpis["indice_qualidade"],
                editado=turno.editado_por_id is not None,
                marcado_teste=turno.marcado_teste,
            )
        )
    return resultado


@router.patch("/marcar-teste")
def marcar_turnos_como_teste(
    dados: TurnosMarcarTeste,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_perfil("ADMIN", "SUPERVISOR")),
):
    """Marca (ou desmarca) em lote uma lista de turnos como 'teste' -
    exclui os turnos marcados do dashboard, dos indicadores acumulados
    e da exportação em CSV, sem apagar o registro. Reversível a
    qualquer momento (basta reenviar com marcado_teste=False). Turnos
    marcados continuam aparecendo normalmente no Histórico, com um
    indicador visual, e o relatório individual de cada um continua
    disponível para download.

    Registrada antes de qualquer rota com padrão /{turno_id} (path
    genérico, sem tipo restrito a dígitos no roteamento do FastAPI/
    Starlette) - se viesse depois, uma chamada para /marcar-teste
    seria capturada por engano pela rota /{turno_id}, tentando
    converter 'marcar-teste' para int e falhando com 422 antes mesmo
    de chegar aqui."""
    turnos = db.query(Turno).filter(Turno.id.in_(dados.turno_ids)).all()
    encontrados = {t.id for t in turnos}
    nao_encontrados = set(dados.turno_ids) - encontrados
    if nao_encontrados:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Turno(s) não encontrado(s): {sorted(nao_encontrados)}",
        )

    for turno in turnos:
        turno.marcado_teste = dados.marcado_teste
    db.commit()
    return {"atualizados": len(turnos), "marcado_teste": dados.marcado_teste}


@router.post("/fechamento", status_code=status.HTTP_201_CREATED)
def criar_fechamento_turno(
    dados: FechamentoTurnoCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """
    Fecha um turno, persiste seus registros, calcula os KPIs e agenda
    o envio do relatório em background.
    """
    try:
        return fechar_turno(
            db=db,
            dados=dados,
            background_tasks=background_tasks,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao processar o fechamento do turno.",
        ) from exc


@router.post("/rascunho", status_code=status.HTTP_201_CREATED)
def criar_rascunho(
    dados: RascunhoTurnoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Cria um novo turno em andamento (rascunho), sem disparar PDF/
    e-mail. Pode ser salvo já no início do turno, com zero registros."""
    resultado = salvar_rascunho(db, dados, turno_id=None)
    return resultado


@router.patch("/rascunho/{turno_id}")
def atualizar_rascunho(
    turno_id: int,
    dados: RascunhoTurnoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Atualiza o progresso de um rascunho já criado. Rejeita se o
    turno já tiver sido fechado (nesse caso, a correção precisa passar
    pela tela de Histórico, restrita a ADMIN/SUPERVISOR)."""
    try:
        return salvar_rascunho(db, dados, turno_id=turno_id)
    except ValueError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "não encontrado" in str(exc)
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/{turno_id}/fechar")
def fechar_rascunho(
    turno_id: int,
    dados: FechamentoTurnoCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Fecha definitivamente um turno que vinha sendo salvo como
    rascunho - só agora o PDF/e-mail são disparados."""
    try:
        return fechar_turno_rascunho(
            db=db, turno_id=turno_id, dados=dados, background_tasks=background_tasks
        )
    except ValueError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "não encontrado" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


# ======================================================================
# Modelo novo: lançamentos livres (produção/parada com início-fim
# variável por peça/OP, não mais grade fixa por hora). Ver
# Turno.modelo_apontamento.
# ======================================================================


@router.post("/lancamento", status_code=status.HTTP_201_CREATED)
def criar_fechamento_lancamento(
    dados: TurnoLancamentoCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Fecha um turno direto (sem passar por rascunho) usando o modelo
    de lançamentos livres."""
    try:
        return fechar_turno_lancamento(db=db, dados=dados, background_tasks=background_tasks)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/lancamento/rascunho", status_code=status.HTTP_201_CREATED)
def criar_rascunho_lancamento(
    dados: TurnoLancamentoRascunho,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Cria um novo turno em andamento (rascunho) no modelo de
    lançamentos livres, sem disparar PDF/e-mail."""
    return salvar_rascunho_lancamento(db, dados, turno_id=None)


@router.patch("/lancamento/rascunho/{turno_id}")
def atualizar_rascunho_lancamento(
    turno_id: int,
    dados: TurnoLancamentoRascunho,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Atualiza o progresso de um rascunho (modelo de lançamentos
    livres) já criado."""
    try:
        return salvar_rascunho_lancamento(db, dados, turno_id=turno_id)
    except ValueError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "não encontrado" in str(exc)
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/lancamento/{turno_id}/fechar")
def fechar_rascunho_lancamento(
    turno_id: int,
    dados: TurnoLancamentoCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Fecha definitivamente um rascunho (modelo de lançamentos
    livres) - só agora o PDF/e-mail são disparados."""
    try:
        return fechar_turno_lancamento(
            db=db, dados=dados, background_tasks=background_tasks, turno_id=turno_id
        )
    except ValueError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "não encontrado" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.patch("/lancamento/{turno_id}")
def corrigir_turno_lancamento(
    turno_id: int,
    dados: TurnoLancamentoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_perfil("ADMIN", "SUPERVISOR")),
):
    """Corrige um turno de lançamentos já encerrado (equivalente a
    PATCH /turnos/{id} do modelo por hora). Restrito a ADMIN/
    SUPERVISOR. Substitui todos os lançamentos do turno pelos
    informados; não reenvia e-mail (evita duplicidade)."""
    try:
        return editar_turno_lancamento(
            db=db, turno_id=turno_id, dados=dados, usuario_id=usuario.id
        )
    except ValueError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "não encontrado" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/{turno_id}", response_model=TurnoDetail)
def obter_turno(
    turno_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Detalhe completo de um turno, incluindo todos os registros
    horários (modelo HORARIO) ou lançamentos (modelo LANCAMENTO) —
    usado para pré-carregar a tela de edição."""
    turno = db.query(Turno).filter(Turno.id == turno_id).first()
    if turno is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turno não encontrado.",
        )

    if turno.modelo_apontamento == "LANCAMENTO":
        linhas = (
            db.query(Lancamento, Maquina, Produto, OrdemProducao)
            .join(Maquina, Lancamento.maquina_id == Maquina.id)
            .outerjoin(Produto, Lancamento.produto_id == Produto.id)
            .outerjoin(OrdemProducao, Lancamento.ordem_producao_id == OrdemProducao.id)
            .filter(Lancamento.turno_id == turno_id)
            .order_by(Lancamento.horario_inicio)
            .all()
        )
        lancamentos_detail = [
            LancamentoDetail(
                id=lanc.id,
                numero_maquina=maq.numero_maquina,
                tipo=lanc.tipo,
                horario_inicio=lanc.horario_inicio.strftime("%H:%M"),
                horario_fim=lanc.horario_fim.strftime("%H:%M"),
                produto_id=produto.id if produto else None,
                produto_codigo=produto.codigo if produto else None,
                produto_descricao=produto.descricao if produto else None,
                ordem_producao_id=ordem.id if ordem else None,
                numero_op=ordem.numero_op if ordem else None,
                quantidade=lanc.quantidade,
                ciclo_informado=lanc.ciclo_informado,
                ciclo_padrao_peca=produto.ciclo_padrao if produto else None,
                cavidades_informado=lanc.cavidades_informado,
                cavidades_padrao_peca=produto.cavidades if produto else None,
                motivo=lanc.motivo,
                producao_esperada=calcular_capacidade_esperada_lancamento(lanc, maq, produto),
            )
            for lanc, maq, produto, ordem in linhas
        ]
        return TurnoDetail(
            id=turno.id,
            nome_turno=turno.nome_turno,
            responsavel_nome=turno.responsavel_nome,
            regulador_nome=turno.regulador_nome,
            observacoes=turno.observacoes,
            data_registro=turno.data_registro,
            status_assinatura=turno.status_assinatura,
            modelo_apontamento=turno.modelo_apontamento,
            editado_por_nome=turno.editado_por.nome if turno.editado_por else None,
            editado_em=turno.editado_em,
            marcado_teste=turno.marcado_teste,
            registros=[],
            lancamentos=lancamentos_detail,
        )

    registros = (
        db.query(RegistroHorario, Maquina, Produto, OrdemProducao)
        .join(Maquina, RegistroHorario.maquina_id == Maquina.id)
        .outerjoin(Produto, RegistroHorario.produto_id == Produto.id)
        .outerjoin(OrdemProducao, RegistroHorario.ordem_producao_id == OrdemProducao.id)
        .filter(RegistroHorario.turno_id == turno_id)
        .order_by(RegistroHorario.hora_referencia)
        .all()
    )

    return TurnoDetail(
        id=turno.id,
        nome_turno=turno.nome_turno,
        responsavel_nome=turno.responsavel_nome,
        regulador_nome=turno.regulador_nome,
        observacoes=turno.observacoes,
        data_registro=turno.data_registro,
        status_assinatura=turno.status_assinatura,
        modelo_apontamento=turno.modelo_apontamento,
        editado_por_nome=turno.editado_por.nome if turno.editado_por else None,
        editado_em=turno.editado_em,
        marcado_teste=turno.marcado_teste,
        registros=[
            RegistroHorarioDetail(
                numero_maquina=maq.numero_maquina,
                hora_referencia=reg.hora_referencia.strftime("%H:%M"),
                prod_executada=reg.prod_executada,
                pecas_boas=reg.pecas_boas,
                refugo=reg.refugo,
                produto_id=produto.id if produto else None,
                produto_codigo=produto.codigo if produto else None,
                produto_descricao=produto.descricao if produto else None,
                ordem_producao_id=ordem.id if ordem else None,
                numero_op=ordem.numero_op if ordem else None,
                ciclo_informado=reg.ciclo_informado,
                inicio_parada=reg.inicio_parada,
                retomada=reg.retomada,
                motivo_parada=reg.motivo_parada,
                parada_programada=reg.parada_programada,
                contador_parada=reg.contador_parada,
                contador_retomada=reg.contador_retomada,
            )
            for reg, maq, produto, ordem in registros
        ],
    )


@router.patch("/{turno_id}")
def corrigir_turno(
    turno_id: int,
    dados: FechamentoTurnoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_perfil("ADMIN", "SUPERVISOR")),
):
    """
    Corrige um turno já encerrado (ex.: erro de digitação em produção ou
    horário). Restrito a ADMIN/SUPERVISOR. Substitui todos os registros
    do turno pelos informados e registra quem editou.
    """
    try:
        return editar_turno(
            db=db,
            turno_id=turno_id,
            dados=dados,
            usuario_id=usuario.id,
        )
    except ValueError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "não encontrado" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao corrigir o turno.",
        ) from exc


@router.post("/{turno_id}/reenviar-email")
def reenviar_email(
    turno_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_perfil("ADMIN", "SUPERVISOR")),
):
    """
    Reenvia o relatório do turno por e-mail, sob demanda (ex.: depois de
    uma correção considerada relevante o suficiente para avisar de
    novo). Diferente de PATCH /turnos/{id} (correção), isto nunca
    acontece automaticamente - é sempre uma ação explícita de
    ADMIN/SUPERVISOR, para não gerar e-mails repetidos a cada ajuste
    pequeno.
    """
    try:
        return reenviar_email_turno(
            db=db,
            turno_id=turno_id,
            background_tasks=background_tasks,
        )
    except ValueError as exc:
        if "não encontrado" in str(exc):
            status_code = status.HTTP_404_NOT_FOUND
        elif "não está configurado" in str(exc):
            status_code = status.HTTP_409_CONFLICT
        else:
            status_code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/{turno_id}/relatorio.pdf")
def baixar_relatorio_turno(
    turno_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """
    Gera (sob demanda) e retorna o PDF de fechamento do turno indicado.
    Os KPIs são recalculados a partir dos registros salvos, então o PDF
    sempre reflete o estado atual do turno (inclusive após correções).
    """
    turno = db.query(Turno).filter(Turno.id == turno_id).first()
    if turno is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turno não encontrado.",
        )

    if turno.modelo_apontamento == "LANCAMENTO":
        from app.services.analytics import calcular_kpis_turno_lancamento
        kpis = calcular_kpis_turno_lancamento(db, turno_id)
        registros_pdf = montar_registros_pdf_lancamento(db, turno_id)
    else:
        kpis = calcular_kpis_turno(db, turno_id)
        registros_pdf = buscar_registros_para_relatorio(db, turno_id)

    dados_turno = {
        "nome_turno": turno.nome_turno,
        "responsavel_nome": turno.responsavel_nome,
    }
    pdf_bytes = gerar_relatorio_turno_pdf(dados_turno, kpis, registros_pdf)

    nome_arquivo = montar_nome_arquivo_relatorio(turno.nome_turno, turno.data_registro)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.get("/exportar/csv")
def exportar_csv(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """
    Exporta os apontamentos horários de turnos fechados em CSV (uma
    linha por hora/máquina), para análise em Excel, Power BI ou
    ferramentas similares. data_inicio/data_fim (formato AAAA-MM-DD)
    são opcionais - sem eles, exporta todo o histórico.
    """
    conteudo = exportar_registros_csv(db, data_inicio=data_inicio, data_fim=data_fim)
    nome_arquivo = "apontamentos_siamp.csv"
    return StreamingResponse(
        iter([conteudo.encode("utf-8")]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )