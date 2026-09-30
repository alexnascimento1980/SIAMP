from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
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
from app.services.pdf_generator import gerar_relatorio_op_pdf

router = APIRouter(prefix="/ordens-producao", tags=["Ordens de Produção"])

# Limite de tamanho para os dois uploads desta rota (CSV/XML de
# importação em lote, PDF/JPG/PNG de extração automática) - sem isso,
# o conteúdo inteiro é lido para a memória antes de qualquer validação
# (ver _ler_upload_limitado), então um arquivo muito grande (ou vários
# simultâneos) pode esgotar a memória do servidor. 15 MB é generoso
# para qualquer uso legítimo desses dois fluxos (um CSV de milhares de
# linhas, ou a foto de um documento em alta resolução).
_TAMANHO_MAXIMO_UPLOAD = 15 * 1024 * 1024

# Assinatura binária (magic bytes) de cada formato aceito - a extensão
# do nome do arquivo sozinha não garante nada sobre o conteúdo real
# (um arquivo malicioso renomeado para .pdf passaria pela checagem de
# extensão sem problema). Usado só na rota de extração (PDF/imagem);
# CSV/XML não têm uma assinatura binária confiável (são texto puro) -
# nesses casos, o próprio parser (csv nativo / defusedxml) já rejeita
# com segurança um conteúdo que não corresponda ao formato esperado.
_ASSINATURAS_BINARIAS = {
    ".pdf": (b"%PDF",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
}


async def _ler_upload_limitado(arquivo: UploadFile) -> bytes:
    """Lê o conteúdo de um UploadFile em pedaços, rejeitando (413) antes
    de acumular mais de _TAMANHO_MAXIMO_UPLOAD bytes em memória - ler
    tudo de uma vez com .read() só descobre que o arquivo é grande
    demais depois de já ter gastado a memória inteira."""
    pedacos = []
    total = 0
    while True:
        pedaco = await arquivo.read(1024 * 1024)
        if not pedaco:
            break
        total += len(pedaco)
        if total > _TAMANHO_MAXIMO_UPLOAD:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Arquivo maior que o limite permitido "
                f"({_TAMANHO_MAXIMO_UPLOAD // (1024 * 1024)} MB).",
            )
        pedacos.append(pedaco)
    return b"".join(pedacos)


def _conteudo_bate_com_extensao(conteudo: bytes, nome_arquivo: str) -> bool:
    """Confirma que os primeiros bytes do arquivo batem com a
    assinatura binária esperada para a extensão informada - a extensão
    sozinha (checada antes de chamar esta função) não garante nada
    sobre o conteúdo real."""
    extensao = "." + nome_arquivo.rsplit(".", 1)[-1].lower()
    assinaturas = _ASSINATURAS_BINARIAS.get(extensao)
    if not assinaturas:
        return True  # extensão sem assinatura conhecida - não bloqueia aqui
    return any(conteudo.startswith(assinatura) for assinatura in assinaturas)


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


@router.get("/{ordem_id}/relatorio.pdf")
def baixar_relatorio_op(
    ordem_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """PDF de UMA OP (meta x real x refugo) - aberto a qualquer perfil
    autenticado, propositalmente: quem não tem mais acesso à página
    completa de gerenciamento (Supervisor e Operador, ver permissões
    de escrita acima, restritas a ADMIN) ainda precisa conseguir
    acompanhar e baixar o progresso de uma OP."""
    try:
        comparativo = calcular_comparativo(db, ordem_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    pdf_bytes = gerar_relatorio_op_pdf(comparativo.model_dump())
    nome_arquivo = f"relatorio_op_{comparativo.numero_op}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.post("/", response_model=OrdemProducaoResponse, status_code=status.HTTP_201_CREATED)
def criar_ordem(
    dados: OrdemProducaoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_perfil("ADMIN")),
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
    usuario: Usuario = Depends(exigir_perfil("ADMIN")),
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
    usuario: Usuario = Depends(exigir_perfil("ADMIN")),
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
    usuario: Usuario = Depends(exigir_perfil("ADMIN")),
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

    conteudo = await _ler_upload_limitado(arquivo)
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
    usuario: Usuario = Depends(exigir_perfil("ADMIN")),
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

    conteudo = await _ler_upload_limitado(arquivo)
    if not conteudo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo vazio.")

    if not _conteudo_bate_com_extensao(conteudo, arquivo.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O conteúdo do arquivo não corresponde a um PDF/JPG/PNG válido "
            "(a extensão do nome do arquivo não é suficiente - o próprio conteúdo "
            "é verificado).",
        )

    try:
        campos = extrair_dados_ordem_producao(conteudo, arquivo.filename)
    except ExtracaoDocumentoError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
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
