from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.timezone import agora_brasilia
from app.models.maquina import Maquina
from app.models.ordem_producao import OrdemProducao
from app.models.produto import Produto
from app.models.registro_turno import RegistroHorario
from app.models.turno import Turno
from app.schemas.ordem_producao_schema import (
    OrdemProducaoComparativo,
    OrdemProducaoCreate,
    OrdemProducaoResponse,
    OrdemProducaoUpdate,
)
from app.services.turno_service import STATUS_ASSINADO


def _resolver_maquina(db: Session, numero_maquina: str | None) -> Maquina | None:
    """Resolve o 'Equipamento' da OP (ex.: "06") para a Maquina já
    cadastrada. Tenta a correspondência exata primeiro; se não achar,
    tenta sem zeros à esquerda (a OP impressa costuma vir com o número
    zero-preenchido - "06" -, enquanto a máquina pode estar cadastrada
    só como "6")."""
    if not numero_maquina or not numero_maquina.strip():
        return None

    numero_maquina = numero_maquina.strip()
    maquina = db.query(Maquina).filter(Maquina.numero_maquina == numero_maquina).first()
    if maquina is not None:
        return maquina

    normalizado = numero_maquina.lstrip("0") or "0"
    if normalizado != numero_maquina:
        maquina = db.query(Maquina).filter(Maquina.numero_maquina == normalizado).first()
        if maquina is not None:
            return maquina

    raise ValueError(
        f"Máquina '{numero_maquina}' não encontrada. Cadastre-a em "
        "Máquinas antes de vincular a uma Ordem de Produção."
    )


def _resolver_produto(db: Session, produto_id: int | None) -> Produto | None:
    """Resolve a peça selecionada (id do catálogo de Peças, GET
    /produtos/). Diferente da máquina, aqui não há normalização - o
    frontend só permite selecionar via dropdown, então o id sempre
    corresponde a um registro real quando enviado."""
    if produto_id is None:
        return None

    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if produto is None:
        raise ValueError(
            f"Peça (id={produto_id}) não encontrada. Cadastre-a em Peças "
            "antes de vincular a uma Ordem de Produção."
        )
    return produto


def montar_response_ordem(ordem: OrdemProducao) -> OrdemProducaoResponse:
    return OrdemProducaoResponse(
        id=ordem.id,
        numero_op=ordem.numero_op,
        data_emissao=ordem.data_emissao,
        tipo_op=ordem.tipo_op,
        setor_produtivo=ordem.setor_produtivo,
        lote=ordem.lote,
        periodo_inicio=ordem.periodo_inicio,
        periodo_fim=ordem.periodo_fim,
        produto_id=ordem.produto_id,
        produto_codigo=ordem.produto_codigo,
        produto_descricao=ordem.produto_descricao,
        quantidade_a_produzir=ordem.quantidade_a_produzir,
        numero_maquina=ordem.maquina.numero_maquina if ordem.maquina else ordem.equipamento_codigo,
        equipamento_descricao=ordem.equipamento_descricao,
        ferramenta_codigo=ordem.ferramenta_codigo,
        ferramenta_descricao=ordem.ferramenta_descricao,
        formula_codigo=ordem.formula_codigo,
        formula_descricao=ordem.formula_descricao,
        embalagem_codigo=ordem.embalagem_codigo,
        embalagem_descricao=ordem.embalagem_descricao,
        qtde_por_embalagem=ordem.qtde_por_embalagem,
        qtde_embalagens_previstas=ordem.qtde_embalagens_previstas,
        cavidades=ordem.cavidades,
        ciclo_segundos=ordem.ciclo_segundos,
        qtde_produzida_por_hora_meta=ordem.qtde_produzida_por_hora_meta,
        peso_liquido_unitario=ordem.peso_liquido_unitario,
        peso_bruto_unitario=ordem.peso_bruto_unitario,
        composicao_mistura=ordem.composicao_mistura,
        observacoes=ordem.observacoes,
        criado_em=ordem.criado_em,
    )


def criar_ordem_producao(
    db: Session, dados: OrdemProducaoCreate, usuario_id: int
) -> OrdemProducaoResponse:
    ja_existe = (
        db.query(OrdemProducao).filter(OrdemProducao.numero_op == dados.numero_op).first()
    )
    if ja_existe:
        raise ValueError("Já existe uma Ordem de Produção cadastrada com este número.")

    maquina = _resolver_maquina(db, dados.numero_maquina)
    produto = _resolver_produto(db, dados.produto_id)

    payload = dados.model_dump(exclude={"numero_maquina", "produto_id"})
    nova = OrdemProducao(
        **payload,
        maquina_id=maquina.id if maquina else None,
        equipamento_codigo=dados.numero_maquina,
        produto_id=produto.id if produto else None,
        produto_codigo=produto.codigo if produto else None,
        produto_descricao=produto.descricao if produto else None,
        criado_por_id=usuario_id,
    )
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return montar_response_ordem(nova)


def atualizar_ordem_producao(
    db: Session, ordem_id: int, dados: OrdemProducaoUpdate
) -> OrdemProducaoResponse:
    ordem = db.query(OrdemProducao).filter(OrdemProducao.id == ordem_id).first()
    if ordem is None:
        raise ValueError("Ordem de Produção não encontrada.")

    dados_dict = dados.model_dump(exclude_unset=True)
    if "numero_maquina" in dados_dict:
        numero_maquina = dados_dict.pop("numero_maquina")
        maquina = _resolver_maquina(db, numero_maquina)
        ordem.maquina_id = maquina.id if maquina else None
        ordem.equipamento_codigo = numero_maquina

    if "produto_id" in dados_dict:
        produto_id = dados_dict.pop("produto_id")
        produto = _resolver_produto(db, produto_id)
        ordem.produto_id = produto.id if produto else None
        ordem.produto_codigo = produto.codigo if produto else None
        ordem.produto_descricao = produto.descricao if produto else None

    for campo, valor in dados_dict.items():
        setattr(ordem, campo, valor)

    if ordem.periodo_fim < ordem.periodo_inicio:
        raise ValueError("periodo_fim não pode ser anterior a periodo_inicio.")

    db.commit()
    db.refresh(ordem)
    return montar_response_ordem(ordem)


def calcular_comparativo(db: Session, ordem_id: int) -> OrdemProducaoComparativo:
    """Compara a meta da OP com a produção real apontada nos turnos.

    Soma RegistroHorario.prod_executada de todos os registros marcados
    explicitamente com esta ordem_producao_id, em qualquer máquina -
    diferente de somar por máquina+período, isto funciona corretamente
    mesmo quando a mesma OP é produzida em mais de uma injetora ao
    mesmo tempo.
    """
    ordem = db.query(OrdemProducao).filter(OrdemProducao.id == ordem_id).first()
    if ordem is None:
        raise ValueError("Ordem de Produção não encontrada.")

    total = (
        db.query(func.coalesce(func.sum(RegistroHorario.prod_executada), 0))
        .join(Turno, RegistroHorario.turno_id == Turno.id)
        .filter(RegistroHorario.ordem_producao_id == ordem.id)
        .filter(Turno.status_assinatura == STATUS_ASSINADO)
        .scalar()
    )
    quantidade_produzida = int(total or 0)

    percentual = (
        round((quantidade_produzida / ordem.quantidade_a_produzir) * 100, 1)
        if ordem.quantidade_a_produzir
        else 0.0
    )

    return OrdemProducaoComparativo(
        ordem_id=ordem.id,
        numero_op=ordem.numero_op,
        quantidade_meta=ordem.quantidade_a_produzir,
        quantidade_produzida=quantidade_produzida,
        percentual_atingido=percentual,
        periodo_inicio=ordem.periodo_inicio,
        periodo_fim=ordem.periodo_fim,
        # date.today() usaria UTC no servidor (produção roda em UTC),
        # divergindo da data real em Brasília por até 3h perto da
        # meia-noite - mesma classe de bug já corrigida antes em
        # outros pontos do sistema (ver core/timezone.py).
        dentro_do_prazo=agora_brasilia().date() <= ordem.periodo_fim,
    )
