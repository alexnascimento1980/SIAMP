from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.usuario import Usuario
from app.services.ml_engine import prever_risco_parada

router = APIRouter(prefix="/predictions", tags=["Inteligência Artificial"])


class InferenciaRequest(BaseModel):
    maquina_id: int = Field(..., example=1)
    produto_id: int | None = Field(default=None, example=1)
    ciclo_efetivo: float | None = Field(
        default=None, example=18.5, description="Ciclo real informado, ou padrão da peça/máquina"
    )
    ciclo_padrao_peca: float | None = Field(default=None, example=18.0)
    cavidades_efetivas: int | None = Field(default=None, example=4)
    duracao_min: float = Field(..., example=120.0)
    quantidade: int | None = Field(default=None, example=350)
    turno_num: int = Field(default=1, example=1)
    dia_semana: int = Field(default=0, example=2, description="0=segunda ... 6=domingo")


@router.post("/diagnostico-risco")
def diagnosticar_risco(
    dados: InferenciaRequest,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Endpoint de teste manual do modelo de risco de parada - útil
    para experimentar hipóteses via Swagger sem precisar de um
    lançamento real no banco. O dashboard usa a mesma função de
    predição, mas alimentada automaticamente pelo lançamento de
    produção mais recente (ver app/api/v1/dashboard.py)."""
    return prever_risco_parada(
        db=db,
        maquina_id=dados.maquina_id,
        produto_id=dados.produto_id,
        ciclo_efetivo=dados.ciclo_efetivo,
        ciclo_padrao_peca=dados.ciclo_padrao_peca,
        cavidades_efetivas=dados.cavidades_efetivas,
        duracao_min=dados.duracao_min,
        quantidade=dados.quantidade,
        turno_num=dados.turno_num,
        dia_semana=dados.dia_semana,
    )