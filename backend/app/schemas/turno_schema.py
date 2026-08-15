from datetime import time
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class RegistroHorarioCreate(BaseModel):
    maquina_id: int = Field(..., gt=0)
    hora_referencia: str = Field(..., min_length=5, max_length=5, examples=["05:00"])
    prod_executada: int = Field(default=0, ge=0)
    inicio_parada: Optional[time] = None
    retomada: Optional[time] = None
    motivo_parada: Optional[str] = Field(default=None, max_length=150)

    @field_validator("hora_referencia")
    @classmethod
    def validar_hora_referencia(cls, value: str) -> str:
        try:
            time.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                "hora_referencia deve estar no formato HH:MM."
            ) from exc
        return value

    @field_validator("retomada")
    @classmethod
    def validar_retomada(cls, value: Optional[time], info):
        inicio = info.data.get("inicio_parada")
        if value is not None and inicio is not None and value < inicio:
            raise ValueError("retomada não pode ser anterior ao início da parada.")
        return value


class FechamentoTurnoCreate(BaseModel):
    nome_turno: str = Field(..., min_length=2, max_length=50)
    responsavel_nome: str = Field(..., min_length=2, max_length=120)
    observacoes: Optional[str] = Field(default=None, max_length=2000)
    registros: List[RegistroHorarioCreate] = Field(..., min_length=1)


class ResumoProducaoResponse(BaseModel):
    turno_id: int
    total_produzido: int
    minutos_parada_total: float
    eficiencia_oee: float
    status: str
