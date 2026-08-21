from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import exigir_perfil, get_current_user
from app.core.database import get_db
from app.models.produto import Produto
from app.models.usuario import Usuario
from app.schemas.produto_schema import ProdutoCreate, ProdutoResponse, ProdutoUpdate

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


@router.post("/", response_model=ProdutoResponse, status_code=status.HTTP_201_CREATED)
def criar_produto(
    dados: ProdutoCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(exigir_perfil("ADMIN", "SUPERVISOR")),
):
    ja_existe = db.query(Produto).filter(Produto.codigo == dados.codigo).first()
    if ja_existe:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma peça cadastrada com este código.",
        )

    novo_produto = Produto(**dados.model_dump())
    db.add(novo_produto)
    db.commit()
    db.refresh(novo_produto)
    return novo_produto


@router.patch("/{produto_id}", response_model=ProdutoResponse)
def atualizar_produto(
    produto_id: int,
    dados: ProdutoUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(exigir_perfil("ADMIN", "SUPERVISOR")),
):
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if produto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peça não encontrada.",
        )

    dados_dict = dados.model_dump(exclude_unset=True)

    # Código é a chave natural da peça - permite alterar (ex.: corrigir
    # erro de digitação no cadastro original), mas confere que o novo
    # valor não colide com outra peça já existente.
    if "codigo" in dados_dict and dados_dict["codigo"] != produto.codigo:
        colisao = (
            db.query(Produto)
            .filter(Produto.codigo == dados_dict["codigo"], Produto.id != produto_id)
            .first()
        )
        if colisao:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe outra peça cadastrada com este código.",
            )

    for campo, valor in dados_dict.items():
        setattr(produto, campo, valor)

    db.commit()
    db.refresh(produto)
    return produto
