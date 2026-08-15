from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import time, datetime

class RegistroHorarioCreate(BaseModel):
    maquina_id: int
    hora_referencia: str = Field(..., example="05:00")
    prod_executada: int = Field(default=0, ge=0)
    inicio_parada: Optional[time] = None
    retomada: Optional[time] = None
    motivo_parada: Optional[str] = None

class FechamentoTurnoCreate(BaseModel):
    nome_turno: str = Field(..., example="1º Turno (05:00 - 13:00)")
    responsavel_nome: str = Field(..., example="Líder Operacional")
    observacoes: Optional[str] = None
    registros: List[RegistroHorarioCreate]

class ResumoProducaoResponse(BaseModel):
    turno_id: int
    total_produzido: int
    minutos_parada_total: float
    eficiencia_oee: float
    status: str