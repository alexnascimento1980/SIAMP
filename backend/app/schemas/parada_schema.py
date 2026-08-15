from datetime import time

from pydantic import BaseModel, Field, model_validator


class ParadaCreate(BaseModel):
    turno_id: int = Field(..., gt=0)
    maquina_id: int = Field(..., gt=0)
    inicio: time
    fim: time | None = None
    duracao_minutos: float | None = Field(default=None, ge=0)
    motivo: str = Field(..., min_length=2, max_length=100)
    categoria: str | None = Field(default=None, max_length=50)
    observacao: str | None = Field(default=None, max_length=1000)
    usuario_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validar_periodo(self):
        if self.fim is not None and self.fim < self.inicio:
            raise ValueError("fim não pode ser anterior ao início da parada.")
        return self
