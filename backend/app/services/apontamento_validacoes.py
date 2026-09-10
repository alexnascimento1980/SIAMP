"""Validadores compartilhados entre os dois modelos de apontamento
(HORARIO e LANCAMENTO) - extraídos de turno_service.py e
lancamento_service.py, onde existiam como funções praticamente
idênticas com o mesmo nome (_resolver_maquinas, _validar_produtos,
_validar_ordens_producao), cada arquivo com sua própria cópia.

Recebem os IDs/números já extraídos como um conjunto simples (não o
objeto FechamentoTurnoCreate/lista de LancamentoCreate inteiro) -
cada modelo de apontamento extrai o conjunto relevante da sua própria
estrutura de dados antes de chamar, então o validador em si não
precisa conhecer o formato de nenhum dos dois payloads.
"""
from sqlalchemy.orm import Session

from app.models.maquina import Maquina
from app.models.ordem_producao import OrdemProducao
from app.models.produto import Produto


def resolver_maquinas(db: Session, numeros_maquina: set[str]) -> dict[str, Maquina]:
    """Resolve todos os números de máquina de uma vez, em vez de
    assumir que numero_maquina == id (primary key). Levanta ValueError
    se algum número informado não corresponder a uma máquina
    cadastrada - validação antecipada em lote (unificando os dois
    comportamentos que existiam antes: o modelo LANCAMENTO já validava
    assim; o HORARIO só descobria a máquina faltando mais tarde, ao
    montar cada registro individualmente - mesmo resultado final
    (ValueError, gerando um 400), só que descoberto num ponto
    diferente da cadeia de chamada)."""
    if not numeros_maquina:
        return {}
    maquinas = db.query(Maquina).filter(Maquina.numero_maquina.in_(numeros_maquina)).all()
    por_numero = {m.numero_maquina: m for m in maquinas}
    faltando = numeros_maquina - por_numero.keys()
    if faltando:
        raise ValueError(f"Máquina(s) não encontrada(s): {sorted(faltando)}.")
    return por_numero


def validar_produtos_existem(db: Session, produto_ids: set[int]) -> None:
    """Confere que todo produto_id informado existe, para retornar um
    erro 400 claro em vez de uma falha de FK crua vinda do banco."""
    if not produto_ids:
        return
    existentes = {pid for (pid,) in db.query(Produto.id).filter(Produto.id.in_(produto_ids)).all()}
    faltando = produto_ids - existentes
    if faltando:
        raise ValueError(f"Peça(s) não encontrada(s): {sorted(faltando)}.")


def validar_ordens_producao_existem(db: Session, ordem_ids: set[int]) -> None:
    """Confere que toda ordem_producao_id informada existe, para
    retornar um erro 400 claro em vez de uma falha de FK crua vinda do
    banco."""
    if not ordem_ids:
        return
    existentes = {
        oid for (oid,) in db.query(OrdemProducao.id).filter(OrdemProducao.id.in_(ordem_ids)).all()
    }
    faltando = ordem_ids - existentes
    if faltando:
        raise ValueError(f"Ordem(ns) de Produção não encontrada(s): {sorted(faltando)}.")
