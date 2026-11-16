"""Cria turnos do modelo antigo (por hora) direto no banco, para testar
a leitura/correção de turnos legados.

As rotas de criação do modelo por hora (POST /turnos/fechamento,
/turnos/rascunho e /turnos/{id}/fechar) foram removidas - o modelo foi
aposentado para escrita -, mas os turnos antigos continuam existindo
em produção e precisam seguir legíveis (Histórico, PDF, CSV, KPIs,
dashboard) e corrigíveis. Este helper reproduz o que o antigo
fechar_turno/salvar_rascunho gravava, sem passar pela API."""

from datetime import time

from app.core.timezone import calcular_data_registro_turno
from app.models.turno import STATUS_ASSINADO, STATUS_EM_ANDAMENTO, Turno
from app.schemas.turno_schema import FechamentoTurnoCreate
from app.services.turno_service import _criar_registros


def criar_turno_horario(
    db,
    payload: dict,
    *,
    em_andamento: bool = False,
    criado_por_id: int | None = None,
) -> Turno:
    dados = FechamentoTurnoCreate(**payload)
    turno = Turno(
        nome_turno=dados.nome_turno,
        responsavel_nome=dados.responsavel_nome,
        regulador_nome=dados.regulador_nome,
        observacoes=dados.observacoes,
        status_assinatura=STATUS_EM_ANDAMENTO if em_andamento else STATUS_ASSINADO,
        modelo_apontamento="HORARIO",
        criado_por_id=criado_por_id,
        data_registro=calcular_data_registro_turno(
            [time.fromisoformat(reg.hora_referencia) for reg in dados.registros]
        ),
    )
    db.add(turno)
    db.flush()
    _criar_registros(db, turno, dados)
    db.commit()
    db.refresh(turno)
    return turno
