"""Testes diretos dos validadores compartilhados entre HORARIO e
LANCAMENTO (extraídos de turno_service.py/lancamento_service.py, onde
existiam como cópias praticamente idênticas do mesmo nome em cada
arquivo - ver commit que fez essa extração)."""
from datetime import date

import pytest

from app.models.maquina import Maquina
from app.models.ordem_producao import OrdemProducao
from app.models.produto import Produto
from app.services.apontamento_validacoes import (
    resolver_maquinas,
    validar_ordens_producao_existem,
    validar_produtos_existem,
)


def test_resolver_maquinas_conjunto_vazio_retorna_dict_vazio(db_session):
    assert resolver_maquinas(db_session, set()) == {}


def test_resolver_maquinas_resolve_todas_de_uma_vez(db_session):
    m1 = Maquina(numero_maquina="1", descricao="Injetora 1", ativo=True)
    m2 = Maquina(numero_maquina="2", descricao="Injetora 2", ativo=True)
    db_session.add_all([m1, m2])
    db_session.commit()
    db_session.refresh(m1)
    db_session.refresh(m2)

    resultado = resolver_maquinas(db_session, {"1", "2"})
    assert resultado == {"1": m1, "2": m2}


def test_resolver_maquinas_faltando_uma_levanta_value_error(db_session):
    m1 = Maquina(numero_maquina="1", descricao="Injetora 1", ativo=True)
    db_session.add(m1)
    db_session.commit()

    with pytest.raises(ValueError, match="não encontrada"):
        resolver_maquinas(db_session, {"1", "99"})


def test_validar_produtos_existem_conjunto_vazio_nao_faz_nada(db_session):
    validar_produtos_existem(db_session, set())  # não deve levantar


def test_validar_produtos_existem_com_id_faltando_levanta_value_error(db_session):
    peca = Produto(codigo="PC-A", descricao="Peça A", ciclo_padrao=10.0, cavidades=2)
    db_session.add(peca)
    db_session.commit()
    db_session.refresh(peca)

    with pytest.raises(ValueError, match="Peça"):
        validar_produtos_existem(db_session, {peca.id, 99999})


def test_validar_ordens_producao_existem_com_id_faltando_levanta_value_error(db_session):
    with pytest.raises(ValueError, match="Ordem"):
        validar_ordens_producao_existem(db_session, {99999})


def test_validar_ordens_producao_existem_todas_presentes_nao_levanta(db_session):
    produto = Produto(codigo="PC-B", descricao="Peça B", ciclo_padrao=10.0, cavidades=2)
    db_session.add(produto)
    db_session.commit()
    db_session.refresh(produto)

    ordem = OrdemProducao(
        numero_op="OP-1", produto_id=produto.id, produto_codigo=produto.codigo,
        produto_descricao=produto.descricao, quantidade_a_produzir=1000,
        periodo_inicio=date(2026, 9, 1), periodo_fim=date(2026, 9, 10),
    )
    db_session.add(ordem)
    db_session.commit()
    db_session.refresh(ordem)

    validar_ordens_producao_existem(db_session, {ordem.id})  # não deve levantar
