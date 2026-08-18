from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import exigir_perfil, get_current_user
from app.core.database import get_db
from app.models.maquina import Maquina
from app.models.produto import Produto
from app.models.registro_turno import RegistroHorario
from app.models.turno import Turno
from app.models.usuario import Usuario
from app.schemas.turno_schema import (
    FechamentoTurnoCreate,
    RegistroHorarioDetail,
    TurnoDetail,
    TurnoListItem,
)
from app.services.analytics import calcular_kpis_turno, calcular_kpis_varios_turnos
from app.services.pdf_generator import gerar_relatorio_turno_pdf
from app.services.turno_service import buscar_registros_para_relatorio, editar_turno, fechar_turno


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
    kpis_por_turno = calcular_kpis_varios_turnos(db, [t.id for t in turnos])

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
                total_produzido=kpis["total_produzido"],
                eficiencia_oee=kpis["eficiencia_oee"],
                indice_qualidade=kpis["indice_qualidade"],
                editado=turno.editado_por_id is not None,
            )
        )
    return resultado


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


@router.get("/{turno_id}", response_model=TurnoDetail)
def obter_turno(
    turno_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Detalhe completo de um turno, incluindo todos os registros
    horários — usado para pré-carregar a tela de edição."""
    turno = db.query(Turno).filter(Turno.id == turno_id).first()
    if turno is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turno não encontrado.",
        )

    registros = (
        db.query(RegistroHorario, Maquina, Produto)
        .join(Maquina, RegistroHorario.maquina_id == Maquina.id)
        .outerjoin(Produto, RegistroHorario.produto_id == Produto.id)
        .filter(RegistroHorario.turno_id == turno_id)
        .order_by(RegistroHorario.hora_referencia)
        .all()
    )

    return TurnoDetail(
        id=turno.id,
        nome_turno=turno.nome_turno,
        responsavel_nome=turno.responsavel_nome,
        observacoes=turno.observacoes,
        data_registro=turno.data_registro,
        status_assinatura=turno.status_assinatura,
        editado_por_nome=turno.editado_por.nome if turno.editado_por else None,
        editado_em=turno.editado_em,
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
                inicio_parada=reg.inicio_parada,
                retomada=reg.retomada,
                motivo_parada=reg.motivo_parada,
                parada_programada=reg.parada_programada,
            )
            for reg, maq, produto in registros
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

    kpis = calcular_kpis_turno(db, turno_id)
    dados_turno = {
        "nome_turno": turno.nome_turno,
        "responsavel_nome": turno.responsavel_nome,
    }
    registros_pdf = buscar_registros_para_relatorio(db, turno_id)
    pdf_bytes = gerar_relatorio_turno_pdf(dados_turno, kpis, registros_pdf)

    nome_arquivo = f"relatorio_turno_{turno_id}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )