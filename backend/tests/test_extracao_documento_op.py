from pathlib import Path

import pytest

from app.services.extracao_documento_op_service import (
    ExtracaoDocumentoError,
    _limpar_decimal,
    _limpar_inteiro,
    _obter_imagem_primeira_pagina,
    _parsear_texto_extraido,
    _remover_ruido_final,
    extrair_dados_ordem_producao,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _texto_ocr_real() -> str:
    """Texto exatamente como o Tesseract leu do PDF real de exemplo
    (backend/tests/fixtures/ordem_producao_maxmanager.pdf) - capturado
    uma vez e congelado aqui, para os testes de parsing rodarem rápido
    e sem depender de ter o tesseract instalado (só os testes que
    exercitam o pipeline completo, mais abaixo, precisam disso)."""
    return (FIXTURES_DIR / "ocr_ordem_producao_maxmanager.txt").read_text()


# --- Parsing de texto (rápido, sem OCR real) -----------------------------


def test_parseia_todos_os_campos_obrigatorios_do_texto_ocr_real():
    dados = _parsear_texto_extraido(_texto_ocr_real(), numero_op_recorte="2817-2026")

    assert dados["numero_op"] == "2817-2026"
    assert dados["produto_codigo"] == "34-7506-00BR"
    assert dados["numero_maquina"] == "06"
    assert dados["quantidade_a_produzir"] == 48000
    assert dados["periodo_inicio"] == "18/08/2026"
    assert dados["periodo_fim"] == "20/08/2026"


def test_parseia_campos_opcionais_do_texto_ocr_real():
    dados = _parsear_texto_extraido(_texto_ocr_real(), numero_op_recorte="2817-2026")

    assert dados["tipo_op"] == "PRODUÇÃO"
    assert dados["equipamento_descricao"] == "INJETORA 06-120T"
    assert dados["cavidades"] == 8
    assert dados["ciclo_segundos"] == 19.0
    assert dados["ferramenta_codigo"] == "7506/1"
    assert dados["formula_codigo"] == "2"
    assert dados["embalagem_codigo"] == "119"
    assert dados["embalagem_descricao"] == "CAIXA M PAPELÃO"
    assert dados["qtde_por_embalagem"] == 8000
    assert dados["qtde_embalagens_previstas"] == 6
    assert dados["qtde_produzida_por_hora_meta"] == 1516
    assert dados["peso_liquido_unitario"] == 0.0015
    assert dados["peso_bruto_unitario"] == 0.0016
    assert "Kanban" in dados["observacoes"]


def test_ruido_de_anotacao_manuscrita_nao_contamina_descricao_da_ferramenta():
    # No documento real, a palavra manuscrita "Exportação" foi escrita
    # por cima da região da Ferramenta/Fórmula, e o OCR emendou
    # fragmentos dela ao fim dessas descrições ("MOLDE CLIP TUBE - 22
    # Ls X O + Q C ç O") - a limpeza de ruído deve cortar isso, sem
    # cortar o "22" legítimo que faz parte da descrição real.
    dados = _parsear_texto_extraido(_texto_ocr_real(), numero_op_recorte="2817-2026")
    assert dados["ferramenta_descricao"] == "MOLDE CLIP TUBE - 22"


def test_numero_op_do_recorte_tem_prioridade_sobre_busca_no_texto_completo():
    # No texto completo (página inteira), o número da OP sai
    # corrompido pelo Tesseract ("281 7-2" ... "026", picotado pelo
    # cabeçalho ao lado) - por isso o recorte dedicado é sempre usado
    # quando disponível, em vez de tentar extrair do texto completo.
    dados = _parsear_texto_extraido(_texto_ocr_real(), numero_op_recorte="2817-2026")
    assert dados["numero_op"] == "2817-2026"
    # confirma a premissa do teste: o texto completo (página inteira)
    # realmente tem o número picotado, não o número correto
    assert "281 7-2" in _texto_ocr_real()
    assert "2817-2026" not in _texto_ocr_real()


def test_sem_recorte_cai_para_busca_no_texto_completo():
    # Sem o recorte (ex.: se um dia a extração por recorte falhar),
    # tenta achar o padrão 'NNNN-NNNN' em qualquer lugar do texto -
    # nesse texto real específico, nenhum trecho bate com esse
    # padrão (o número saiu picotado demais), então cai para None -
    # comportamento correto: melhor não preencher do que preencher
    # errado.
    dados = _parsear_texto_extraido(_texto_ocr_real(), numero_op_recorte=None)
    assert dados["numero_op"] is None


def test_campo_nao_encontrado_no_texto_fica_none_nao_falha():
    dados = _parsear_texto_extraido("texto qualquer sem nenhum campo reconhecível")
    assert dados["numero_op"] is None
    assert dados.get("produto_codigo") is None
    assert dados.get("quantidade_a_produzir") is None


# --- Helpers de conversão -------------------------------------------------


def test_limpar_inteiro_remove_separador_de_milhar():
    assert _limpar_inteiro("48.000") == 48000
    assert _limpar_inteiro("1.516") == 1516
    assert _limpar_inteiro("8000") == 8000  # já sem separador (variação de OCR)
    assert _limpar_inteiro("") is None
    assert _limpar_inteiro(None) is None


def test_limpar_decimal_troca_virgula_por_ponto():
    assert _limpar_decimal("0,0015") == 0.0015
    assert _limpar_decimal("117,0000") == 117.0
    assert _limpar_decimal("") is None
    assert _limpar_decimal("abc") is None


def test_remover_ruido_final_preserva_numero_legitimo_no_fim():
    # "22" é dado real (parte de "MOLDE CLIP TUBE - 22"), "Ls X O + Q
    # C ç O" é ruído de OCR sobre uma anotação manuscrita - só o ruído
    # deve ser cortado.
    resultado = _remover_ruido_final("MOLDE CLIP TUBE - 22 Ls X O + Q C ç O")
    assert resultado == "MOLDE CLIP TUBE - 22"


def test_remover_ruido_final_sem_ruido_mantem_texto_intacto():
    assert _remover_ruido_final("CAIXA M PAPELÃO") == "CAIXA M PAPELÃO"


def test_remover_ruido_final_nao_corta_hifen_e_sigla_curta_legitimos():
    # Bug real encontrado com um segundo documento de teste: a
    # heurística original cortava a partir de QUALQUER par de 2
    # tokens curtos consecutivos, o que incluía casos legítimos como
    # "DV -" (sigla de 2 letras seguida de hífen) - "BASCULE DV - 38"
    # virava só "BASCULE", perdendo dado real. Corrigido para exigir
    # 3+ tokens curtos seguidos (ruído de OCR de verdade tende a vir
    # em sequências bem mais longas que 2).
    assert _remover_ruido_final("BASCULE DV - 38") == "BASCULE DV - 38"


# --- Segundo documento real (camada de texto nativa, não OCR) ------------


def _texto_nativo_real() -> str:
    """Texto extraído diretamente da camada de texto de um segundo
    PDF real de exemplo (não escaneado - gerado digitalmente pelo
    MaxManager) - bem mais limpo que o primeiro (via OCR), usado para
    validar o caminho de extração nativa (_tentar_texto_nativo_pdf)
    e revelar bugs que só aparecem com uma segunda amostra real
    (ex.: rótulos vizinhos vazando na mesma linha em posições
    diferentes das do primeiro documento)."""
    return (FIXTURES_DIR / "texto_nativo_ordem_producao_maxmanager.txt").read_text()


def test_parseia_documento_com_texto_nativo_sem_nenhum_erro():
    # Diferente do primeiro documento (via OCR, com pequenas
    # imperfeições aceitáveis em campos opcionais), o segundo extrai
    # 100% correto em todos os campos - texto nativo não introduz os
    # erros de reconhecimento de caractere que o OCR introduz.
    dados = _parsear_texto_extraido(_texto_nativo_real())

    assert dados["numero_op"] == "3000-2026"
    assert dados["tipo_op"] == "PRODUÇÃO"
    assert dados["setor_produtivo"] == "INJECAO"
    assert dados["lote"] == "20260901/3000"
    assert dados["periodo_inicio"] == "02/09/2026"
    assert dados["periodo_fim"] == "14/09/2026"
    assert dados["produto_codigo"] == "34-5721-00BR"
    assert dados["quantidade_a_produzir"] == 300000
    assert dados["numero_maquina"] == "12"
    assert dados["equipamento_descricao"] == "INJETORA 12-250T"
    assert dados["cavidades"] == 16
    assert dados["ciclo_segundos"] == 25.0
    assert dados["ferramenta_codigo"] == "5721"
    assert dados["ferramenta_descricao"] == "BASCULE DV - 38"
    assert dados["formula_codigo"] == "1"
    assert dados["formula_descricao"] == "POM NATURAL"
    assert dados["embalagem_codigo"] == "146"
    assert dados["qtde_por_embalagem"] == 2700
    assert dados["qtde_embalagens_previstas"] == 111
    assert dados["qtde_produzida_por_hora_meta"] == 2304
    assert dados["peso_liquido_unitario"] == 0.0036
    assert dados["peso_bruto_unitario"] == 0.0044


def test_lote_extraido_do_padrao_numerico_nao_do_rotulo():
    # O rótulo "LOTE" fica colado na linha de "Tipo da OP" (vazamento
    # de coluna vizinha), mas o VALOR do lote fica numa linha própria,
    # separada - a extração busca o padrão do valor
    # (dígitos/dígitos), não o rótulo em si.
    dados = _parsear_texto_extraido(_texto_nativo_real())
    assert dados["lote"] == "20260901/3000"


def test_lote_nao_colide_com_codigo_de_ferramenta():
    # Ferramenta também usa "/" no código (ex.: "7506/1") - o padrão
    # do lote exige grupos de dígitos bem maiores (6-10 e 3-6 dígitos)
    # para não confundir os dois.
    dados = _parsear_texto_extraido(_texto_ocr_real(), numero_op_recorte="2817-2026")
    assert dados["ferramenta_codigo"] == "7506/1"


def test_tipo_op_nao_inclui_rotulo_lote_vizinho():
    # "Tipo da OP: PRODUÇÃO LOTE" no texto nativo - "LOTE" é o
    # cabeçalho da coluna vizinha (direita), que cai na mesma linha
    # na extração de texto por causa do layout em colunas do
    # documento. Não pode contaminar o valor de tipo_op.
    dados = _parsear_texto_extraido(_texto_nativo_real())
    assert dados["tipo_op"] == "PRODUÇÃO"
    assert "LOTE" not in dados["tipo_op"]


def test_equipamento_descricao_nao_inclui_cavidades_vizinho():
    dados = _parsear_texto_extraido(_texto_nativo_real())
    assert dados["equipamento_descricao"] == "INJETORA 12-250T"
    assert "Cavidades" not in dados["equipamento_descricao"]


def test_extracao_completa_do_pdf_real_com_texto_nativo():
    """PDF com camada de texto (diferente do outro teste de pipeline
    completo, que usa um PDF só-imagem) - confirma que
    extrair_dados_ordem_producao detecta e usa o caminho de texto
    nativo corretamente, sem precisar de OCR."""
    conteudo = (FIXTURES_DIR / "ordem_producao_maxmanager_texto.pdf").read_bytes()
    dados = extrair_dados_ordem_producao(conteudo, "ordem_producao_maxmanager_texto.pdf")

    assert dados["numero_op"] == "3000-2026"
    assert dados["produto_codigo"] == "34-5721-00BR"
    assert dados["numero_maquina"] == "12"
    assert dados["quantidade_a_produzir"] == 300000
    assert dados["periodo_inicio"] == "02/09/2026"
    assert dados["periodo_fim"] == "14/09/2026"


def test_tentar_texto_nativo_retorna_none_para_pdf_so_imagem():
    from app.services.extracao_documento_op_service import _tentar_texto_nativo_pdf

    conteudo = (FIXTURES_DIR / "ordem_producao_maxmanager.pdf").read_bytes()
    assert _tentar_texto_nativo_pdf(conteudo) is None


def test_tentar_texto_nativo_retorna_texto_para_pdf_com_camada_de_texto():
    from app.services.extracao_documento_op_service import _tentar_texto_nativo_pdf

    conteudo = (FIXTURES_DIR / "ordem_producao_maxmanager_texto.pdf").read_bytes()
    texto = _tentar_texto_nativo_pdf(conteudo)
    assert texto is not None
    assert "3000-2026" in texto


# --- Formato de arquivo ----------------------------------------------------


def test_extensao_nao_suportada_e_rejeitada():
    with pytest.raises(ExtracaoDocumentoError):
        _obter_imagem_primeira_pagina(b"conteudo qualquer", "documento.docx")


def test_arquivo_sem_extensao_e_rejeitado():
    with pytest.raises(ExtracaoDocumentoError):
        _obter_imagem_primeira_pagina(b"conteudo qualquer", "documento")


def test_pdf_corrompido_da_erro_claro():
    with pytest.raises(ExtracaoDocumentoError):
        _obter_imagem_primeira_pagina(b"isso nao e um pdf de verdade", "documento.pdf")


# --- Pipeline completo (exige tesseract instalado - ver Dockerfile e ------
# --- .github/workflows/tests.yml) ------------------------------------------


def test_extracao_completa_do_pdf_real():
    """Único teste que roda o OCR de verdade, contra o PDF real usado
    para desenhar todo o parser (backend/tests/fixtures/
    ordem_producao_maxmanager.pdf) - garante que o pipeline inteiro
    (PDF -> imagem -> OCR de página inteira + recorte do número da OP
    -> parsing) continua funcionando de ponta a ponta, não só a lógica
    de parsing isolada testada acima com o texto já congelado."""
    conteudo = (FIXTURES_DIR / "ordem_producao_maxmanager.pdf").read_bytes()
    dados = extrair_dados_ordem_producao(conteudo, "ordem_producao_maxmanager.pdf")

    assert dados["numero_op"] == "2817-2026"
    assert dados["produto_codigo"] == "34-7506-00BR"
    assert dados["numero_maquina"] == "06"
    assert dados["quantidade_a_produzir"] == 48000
    assert dados["periodo_inicio"] == "18/08/2026"
    assert dados["periodo_fim"] == "20/08/2026"
