from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.produto import Produto
from app.models.usuario import Usuario
from app.schemas.produto_schema import ProdutoResponse

router = APIRouter(prefix="/produtos", tags=["Produtos"])


@router.get("/", response_model=list[ProdutoResponse])
def listar_produtos(
    incluir_inativas: bool = False,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """
    Catálogo de peças que podem ser produzidas nas injetoras (ciclo médio
    em segundos, cavidades quando difere da máquina). Usado para
    preencher o seletor de "peça produzida" no apontamento horário.
    """
    query = db.query(Produto)
    if not incluir_inativas:
        query = query.filter(Produto.ativo.is_(True))
    return query.order_by(Produto.codigo).all()
