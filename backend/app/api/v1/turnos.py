from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.turno import Turno
from app.models.usuario import Usuario
from app.schemas.turno_schema import FechamentoTurnoCreate, TurnoListItem
from app.services.analytics import calcular_kpis_turno
from app.services.pdf_generator import gerar_relatorio_turno_pdf
from app.services.turno_service import fechar_turno


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

    resultado = []
    for turno in turnos:
        kpis = calcular_kpis_turno(db, turno.id)
        resultado.append(
            TurnoListItem(
                id=turno.id,
                nome_turno=turno.nome_turno,
                responsavel_nome=turno.responsavel_nome,
                data_registro=turno.data_registro,
                status_assinatura=turno.status_assinatura,
                total_produzido=kpis["total_produzido"],
                eficiencia_oee=kpis["eficiencia_oee"],
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


@router.get("/{turno_id}/relatorio.pdf")
def baixar_relatorio_turno(
    turno_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """
    Gera (sob demanda) e retorna o PDF de fechamento do turno indicado.
    Os KPIs são recalculados a partir dos registros salvos, então o PDF
    sempre reflete o estado atual do turno.
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
    pdf_bytes = gerar_relatorio_turno_pdf(dados_turno, kpis)

    nome_arquivo = f"relatorio_turno_{turno_id}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )