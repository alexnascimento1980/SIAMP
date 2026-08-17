from sqlalchemy.orm import Session
from app.models.maquina import Maquina
from app.models.registro_turno import RegistroHorario


def calcular_kpis_turno(db: Session, turno_id: int) -> dict:
    registros = db.query(RegistroHorario, Maquina).\
        join(Maquina, RegistroHorario.maquina_id == Maquina.id).\
        filter(RegistroHorario.turno_id == turno_id).all()

    total_produzido = 0
    total_esperado = 0
    minutos_parados = 0
    total_pecas_boas = 0
    total_refugo = 0
    houve_apontamento_qualidade = False

    for reg, maq in registros:
        total_produzido += reg.prod_executada

        # Cálculo de produção nominal esperada (3600s / ciclo * cavidades por hora cheia)
        capacidade_hora = int((3600 / maq.ciclo_padrao) * maq.cavidades)
        total_esperado += capacidade_hora

        if reg.inicio_parada and reg.retomada:
            t_inicio = reg.inicio_parada.hour * 60 + reg.inicio_parada.minute
            t_fim = reg.retomada.hour * 60 + reg.retomada.minute
            minutos_parados += max(0, t_fim - t_inicio)

        # pecas_boas/refugo são opcionais (retrocompatibilidade com registros
        # antigos, que não apontavam qualidade). Só entram no cálculo do
        # índice de qualidade quando pelo menos um registro do turno os
        # informa.
        if reg.pecas_boas is not None or reg.refugo is not None:
            houve_apontamento_qualidade = True
            total_pecas_boas += reg.pecas_boas or 0
            total_refugo += reg.refugo or 0

    # Índice de Produção combina Disponibilidade e Performance: quanto do
    # volume teoricamente possível (sem paradas) foi de fato produzido.
    indice_producao = (total_produzido / total_esperado) if total_esperado > 0 else 0.0

    # Índice de Qualidade: proporção de peças boas sobre o total inspecionado
    # (boas + refugo). Sem apontamento de qualidade no turno, assume-se 100%
    # para não penalizar turnos que ainda não usam esse campo.
    if houve_apontamento_qualidade and (total_pecas_boas + total_refugo) > 0:
        indice_qualidade = total_pecas_boas / (total_pecas_boas + total_refugo)
    else:
        indice_qualidade = 1.0

    eficiencia_oee = round(indice_producao * indice_qualidade * 100, 2)

    return {
        "total_produzido": total_produzido,
        "total_esperado": total_esperado,
        "minutos_parados": minutos_parados,
        "total_pecas_boas": total_pecas_boas,
        "total_refugo": total_refugo,
        "indice_producao": round(indice_producao * 100, 2),
        "indice_qualidade": round(indice_qualidade * 100, 2),
        "eficiencia_oee": eficiencia_oee,
        "alerta_ia": "Abaixo da meta esperada" if eficiencia_oee < 75.0 else "Operação normal"
    }