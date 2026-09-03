from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import exigir_perfil, get_current_user
from app.core.database import get_db
from app.models.ordem_producao import OrdemProducao
from app.models.usuario import Usuario
from app.schemas.ordem_producao_schema import (
    OrdemProducaoComparativo,
    OrdemProducaoCreate,
    OrdemProducaoResponse,
    OrdemProducaoUpdate,
)
from app.services.extracao_documento_op_service import (
    ExtracaoDocumentoError,
    extrair_dados_ordem_producao,
)
from app.services.importacao_ordem_producao_service import (
    _resolver_maquina_por_numero,
    _resolver_produto_por_codigo,
    importar_ordens_producao,
)
from app.services.ordem_producao_service import (
    atualizar_ordem_producao,
    calcular_comparativo,
    criar_ordem_producao,
    montar_response_ordem,
)

router = APIRouter(prefix="/ordens-producao", tags=["Ordens de Produção"])


@router.get("/", response_model=list[OrdemProducaoResponse])
def listar_ordens_producao(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Lista as Ordens de Produção cadastradas, mais recentes primeiro.
    Leitura liberada para qualquer usuário logado (base para os
    dashboards de acompanhamento)."""
    ordens = (
        db.query(OrdemProducao)
        .order_by(OrdemProducao.periodo_inicio.desc())
        .all()
    )
    return [montar_response_ordem(o) for o in ordens]


@router.get("/{ordem_id}", response_model=OrdemProducaoResponse)
def obter_ordem_producao(
    ordem_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    ordem = db.query(OrdemProducao).filter(OrdemProducao.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ordem de Produção não encontrada.",
        )
    return montar_response_ordem(ordem)


@router.get("/{ordem_id}/comparativo", response_model=OrdemProducaoComparativo)
def obter_comparativo(
    ordem_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Meta planejada x produção real apontada nos turnos, no período
    da OP. Só calcula produção real quando a OP tem máquina vinculada."""
    try:
        return calcular_comparativo(db, ordem_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.post("/", response_model=OrdemProducaoResponse, status_code=status.HTTP_201_CREATED)
def criar_ordem(
    dados: OrdemProducaoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_perfil("ADMIN", "SUPERVISOR")),
):
    try:
        return criar_ordem_producao(db, dados, usuario.id)
    except ValueError as exc:
        status_code = (
            status.HTTP_409_CONFLICT
            if "já existe" in str(exc).lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.patch("/{ordem_id}", response_model=OrdemProducaoResponse)
def editar_ordem(
    ordem_id: int,
    dados: OrdemProducaoUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_perfil("ADMIN", "SUPERVISOR")),
):
    try:
        return atualizar_ordem_producao(db, ordem_id, dados)
    except ValueError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "não encontrada" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.delete("/{ordem_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_ordem(
    ordem_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_perfil("ADMIN", "SUPERVISOR")),
):
    ordem = db.query(OrdemProducao).filter(OrdemProducao.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ordem de Produção não encontrada.",
        )
    db.delete(ordem)
    db.commit()


@router.post("/importar")
async def importar_ordens_producao_endpoint(
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_perfil("ADMIN", "SUPERVISOR")),
):
    """
    Importa Ordens de Produção em lote, de um arquivo .csv ou .xml.

    Colunas obrigatórias: numero_op, produto_codigo, numero_maquina,
    quantidade_a_produzir, periodo_inicio, periodo_fim. Peça
    (produto_codigo) e máquina (numero_maquina) precisam já estar
    cadastradas - linhas cujo código não bate com nenhuma peça/máquina
    existente são rejeitadas e reportadas, sem travar a importação das
    demais linhas válidas do mesmo arquivo.
    """
    if not arquivo.filename or not arquivo.filename.lower().endswith((".csv", ".xml")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Envie um arquivo .csv ou .xml.",
        )

    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo vazio.",
        )

    try:
        return importar_ordens_producao(
            db=db,
            conteudo=conteudo,
            nome_arquivo=arquivo.filename,
            usuario_id=usuario.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não foi possível ler o arquivo: {exc}",
        ) from exc


@router.post("/extrair-documento")
async def extrair_documento_op_endpoint(
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_perfil("ADMIN", "SUPERVISOR")),
):
    """Extrai os dados de uma Ordem de Produção a partir de um PDF ou
    foto do documento (mesmo layout da importação em lote - sistema
    MaxManager), via OCR, para pré-preencher o formulário manual de
    cadastro. NUNCA cria a OP diretamente - extração automática de
    documento (ainda mais escaneado/fotografado) nunca é 100%
    confiável, então o resultado sempre precisa ser revisado e
    confirmado manualmente antes de salvar. Campos não reconhecidos
    voltam como null, para o formulário pedir preenchimento manual em
    vez de mostrar um valor inventado."""
    if not arquivo.filename or not arquivo.filename.lower().endswith((".pdf", ".jpg", ".jpeg", ".png")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Envie um arquivo .pdf, .jpg ou .png.",
        )

    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo vazio.")

    try:
        campos = extrair_dados_ordem_producao(conteudo, arquivo.filename)
    except ExtracaoDocumentoError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não foi possível processar o documento: {exc}",
        ) from exc

    # Confere se a peça/máquina extraídas já estão cadastradas, mesma
    # lógica já usada na importação em lote - avisa o formulário sem
    # bloquear nada (a peça/máquina podem ser trocadas manualmente na
    # revisão antes de salvar).
    produto_id = None
    produto_codigo = campos.get("produto_codigo")
    if produto_codigo:
        produto = _resolver_produto_por_codigo(db, produto_codigo)
        if produto is not None:
            produto_id = produto.id

    numero_maquina_encontrada = None
    numero_maquina = campos.get("numero_maquina")
    if numero_maquina:
        maquina = _resolver_maquina_por_numero(db, numero_maquina)
        if maquina is not None:
            numero_maquina_encontrada = maquina.numero_maquina

    return {
        "campos": campos,
        "produto_id": produto_id,
        "produto_nao_encontrado": produto_codigo if produto_id is None and produto_codigo else None,
        "numero_maquina_nao_encontrada": (
            numero_maquina if numero_maquina_encontrada is None and numero_maquina else None
        ),
    }
