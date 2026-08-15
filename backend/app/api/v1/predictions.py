from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.services.ml_engine import prever_risco_operacional

router = APIRouter(prefix="/predictions", tags=["Inteligência Artificial"])

class InferenciaRequest(BaseModel):
    numero_maquina: int = Field(..., example=1)
    cavidades: int = Field(..., example=4)
    ciclo_padrao: float = Field(..., example=18.5)
    tempo_parada_minutos: float = Field(..., example=25.0)

@router.post("/diagnostico-risco")
def diagnosticar_risco(dados: InferenciaRequest):
    resultado = prever_risco_operacional(
        numero_maquina=dados.numero_maquina,
        cavidades=dados.cavidades,
        ciclo_padrao=dados.ciclo_padrao,
        tempo_parada_minutos=dados.tempo_parada_minutos
    )
    return resultado