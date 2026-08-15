import numpy as np
import pandas as pd
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

    for reg, maq in registros:
        total_produzido += reg.prod_executada
        
        # Cálculo de produção nominal esperada (3600s / ciclo * cavidades por hora cheia)
        capacidade_hora = int((3600 / maq.ciclo_padrao) * maq.cavidades)
        total_esperado += capacidade_hora
        
        if reg.inicio_parada and reg.retomada:
            t_inicio = reg.inicio_parada.hour * 60 + reg.inicio_parada.minute
            t_fim = reg.retomada.hour * 60 + reg.retomada.minute
            minutos_parados += max(0, t_fim - t_inicio)

    eficiencia = round((total_produzido / total_esperado * 100), 2) if total_esperado > 0 else 0.0

    return {
        "total_produzido": total_produzido,
        "total_esperado": total_esperado,
        "minutos_parados": minutos_parados,
        "eficiencia_oee": eficiencia,
        "alerta_ia": "Abaixo da meta esperada" if eficiencia < 75.0 else "Operação normal"
    }