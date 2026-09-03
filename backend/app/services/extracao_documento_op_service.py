import io
import re

import pdfplumber
import pytesseract
from PIL import Image


class ExtracaoDocumentoError(Exception):
    """Erro ao processar o arquivo enviado (formato não suportado,
    OCR não conseguiu ler nada aproveitável, etc.)."""


def _tentar_texto_nativo_pdf(conteudo: bytes) -> str | None:
    """Tenta extrair texto diretamente da camada de texto do PDF (não
    imagem) - bem mais confiável que OCR quando disponível, sem
    nenhuma das confusões de caractere que o OCR introduz (visto na
    prática: 'Qtde' virando 'Qrde', ':' virando '.', números inteiros
    picotados etc.). Alguns dos PDFs reais recebidos têm essa camada
    de texto (gerados digitalmente pelo MaxManager); outros são só
    uma digitalização/foto embutida sem texto nenhum - por isso o
    resultado pode ser None, e quem chamou deve então cair para o
    caminho de OCR (ver _obter_imagem_primeira_pagina)."""
    try:
        with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
            if not pdf.pages:
                return None
            texto = pdf.pages[0].extract_text()
    except Exception:
        return None

    # Limite arbitrário, mas generoso - um PDF só-imagem retorna None
    # ou poucas dezenas de caracteres de metadado; um PDF com texto de
    # verdade desse layout tem mais de mil caracteres tipicamente.
    if texto and len(texto.strip()) >= 100:
        return texto
    return None


def _obter_imagem_primeira_pagina(conteudo: bytes, nome_arquivo: str) -> Image.Image:
    """Converte o arquivo enviado (PDF ou imagem) na primeira página
    como uma imagem PIL, pronta para OCR - usado quando o PDF não tem
    camada de texto selecionável (digitalização/foto embutida, caso
    mais comum na prática) ou quando o arquivo já é uma foto (JPG/
    PNG), que nunca tem texto selecionável por definição."""
    extensao = nome_arquivo.rsplit(".", 1)[-1].lower() if "." in nome_arquivo else ""

    if extensao == "pdf":
        from pdf2image import convert_from_bytes

        try:
            paginas = convert_from_bytes(conteudo, dpi=300, first_page=1, last_page=1)
        except Exception as exc:
            raise ExtracaoDocumentoError(
                "Não foi possível abrir o PDF - verifique se o arquivo não está corrompido."
            ) from exc
        if not paginas:
            raise ExtracaoDocumentoError("O PDF não tem nenhuma página.")
        return paginas[0]

    if extensao in ("jpg", "jpeg", "png"):
        try:
            return Image.open(io.BytesIO(conteudo)).convert("RGB")
        except Exception as exc:
            raise ExtracaoDocumentoError(
                "Não foi possível abrir a imagem - verifique se o arquivo não está corrompido."
            ) from exc

    raise ExtracaoDocumentoError(
        "Formato não suportado - envie um PDF, JPG ou PNG."
    )


def _limpar_inteiro(texto: str) -> int | None:
    """Números inteiros no documento usam '.' como separador de
    milhar (padrão brasileiro) - ex.: '48.000', '1.516'. Remove
    qualquer caractere que não seja dígito antes de converter, então
    funciona tanto se o OCR preservou o ponto quanto se não (ex.:
    '8.000' ou '8000' - já observado os dois casos na prática)."""
    if not texto:
        return None
    digitos = re.sub(r"[^\d]", "", texto)
    return int(digitos) if digitos else None


def _limpar_decimal(texto: str) -> float | None:
    """Números decimais no documento usam ',' (padrão brasileiro) -
    ex.: '0,0015'. Troca por '.' antes de converter."""
    if not texto:
        return None
    limpo = texto.strip().replace(".", "").replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return None


def _extrair_numero_op_recorte(imagem: Image.Image) -> str | None:
    """O número da OP (canto superior direito, fonte grande) sai mal
    lido no OCR da página inteira - o segmentador de layout do
    Tesseract mistura esse bloco com o texto pequeno do cabeçalho ao
    lado (endereço da empresa), quebrando o número em pedaços
    ilegíveis. Recortar só essa região e reler com --psm 7 (uma
    linha de texto) resolve - testado contra um documento real.
    Coordenadas em fração da largura/altura da página (não em
    pixels), para funcionar em qualquer resolução de digitalização."""
    largura, altura = imagem.size
    recorte = imagem.crop((
        int(largura * 0.71),
        int(altura * 0.014),
        int(largura * 1.0),
        int(altura * 0.055),
    ))
    texto = pytesseract.image_to_string(recorte, lang="por", config="--psm 7")
    match = re.search(r"(\d{3,6}-\d{4})", texto)
    return match.group(1) if match else None


def _remover_ruido_final(texto: str) -> str:
    """Remove ruído de OCR no final de uma descrição - texto
    manuscrito sobreposto na mesma linha de um campo impresso às
    vezes soma tokens curtos e desconexos ao final (ex.: 'MOLDE CLIP
    TUBE - 22 Ls X O + Q C ç O', onde 'Ls X O + Q C ç O' vem de uma
    anotação escrita à mão por cima do documento). Heurística: corta
    a partir da primeira sequência de 3+ tokens consecutivos com 2
    caracteres ou menos (raro em texto real - mesmo um hífen seguido
    de uma sigla curta, tipo 'DV -', não passa de 2 tokens curtos
    seguidos - mas comum em ruído de OCR, que tende a fragmentar
    bastante). Ignora tokens só numéricos como início da sequência,
    para não cortar um número curto legítimo no fim de uma descrição
    real (ex.: '- 22')."""
    tokens = texto.split()
    for i in range(len(tokens) - 2):
        se_curto_e_nao_numerico = (
            len(tokens[i]) <= 2 and not tokens[i].isdigit()
            and len(tokens[i + 1]) <= 2 and not tokens[i + 1].isdigit()
            and len(tokens[i + 2]) <= 2 and not tokens[i + 2].isdigit()
        )
        if se_curto_e_nao_numerico:
            return " ".join(tokens[:i]).strip()
    return texto.strip()


def _proxima_linha_nao_vazia(texto_completo: str, apos_regex: str) -> str | None:
    """Para campos cujo valor fica na LINHA SEGUINTE ao rótulo, não
    na mesma linha (ex.: 'PRODUTO A PRODUZIR' seguido, na linha de
    baixo, do código e descrição da peça)."""
    match = re.search(apos_regex, texto_completo, re.IGNORECASE)
    if not match:
        return None
    resto = texto_completo[match.end():]
    for linha in resto.splitlines():
        linha = linha.strip()
        if linha:
            return linha
    return None


def extrair_dados_ordem_producao(conteudo: bytes, nome_arquivo: str) -> dict:
    """Extrai os campos de uma Ordem de Produção a partir de um PDF
    (com camada de texto real, gerado digitalmente, ou uma
    digitalização/foto embutida sem texto selecionável - os dois
    casos acontecem na prática) ou de uma foto do documento (JPG/PNG)
    - layout fixo do sistema MaxManager. Retorna um dict com os
    mesmos nomes de campo usados na importação CSV/XML (ver
    importacao_ordem_producao_service.py), para reaproveitar a mesma
    lógica de resolução de peça/máquina e conversão de tipos.

    Tenta primeiro ler a camada de texto nativa do PDF (bem mais
    confiável, sem nenhuma das confusões de caractere do OCR) - só
    recorre a OCR (mais lento, com margem de erro real) quando o
    arquivo é uma foto ou quando o PDF não tem texto selecionável
    algum.

    Extração automática nunca é 100% confiável, principalmente pelo
    caminho de OCR - o resultado deve sempre ser revisado por um
    humano antes de confirmar o cadastro, nunca criar a OP direto a
    partir daqui. Campos não encontrados voltam como None, para o
    formulário exibir em branco e pedir preenchimento manual, em vez
    de um valor inventado."""
    extensao = nome_arquivo.rsplit(".", 1)[-1].lower() if "." in nome_arquivo else ""

    if extensao == "pdf":
        texto_nativo = _tentar_texto_nativo_pdf(conteudo)
        if texto_nativo:
            return _parsear_texto_extraido(texto_nativo)

    # PDF sem texto selecionável (digitalização/foto embutida) ou
    # arquivo de imagem (JPG/PNG) - único caminho possível é OCR
    imagem = _obter_imagem_primeira_pagina(conteudo, nome_arquivo)
    texto = pytesseract.image_to_string(imagem, lang="por")

    if len(texto.strip()) < 30:
        raise ExtracaoDocumentoError(
            "Não foi possível ler texto suficiente no documento - "
            "confira se a imagem está nítida e não está de cabeça para baixo."
        )

    # Campo mais crítico (identificador único) - tenta o recorte
    # dedicado primeiro (mais confiável, ver _extrair_numero_op_recorte),
    # cai para uma busca no texto completo só se o recorte não achar
    # nada (ex.: foto com o documento fora da posição esperada).
    numero_op_recorte = _extrair_numero_op_recorte(imagem)

    return _parsear_texto_extraido(texto, numero_op_recorte)


def _parsear_texto_extraido(texto: str, numero_op_recorte: str | None = None) -> dict:
    """Toda a lógica de reconhecimento de padrão (regex) que
    transforma o texto já extraído (por OCR ou de outra forma) nos
    campos da Ordem de Produção - separada de extrair_dados_ordem_
    producao() de propósito, para poder testar essa lógica com um
    texto fixo, sem depender de rodar OCR de verdade (lento, e exige
    o tesseract instalado no ambiente que roda os testes)."""
    dados: dict = {}

    dados["numero_op"] = numero_op_recorte
    if not dados["numero_op"]:
        match = re.search(r"N[ºo°]?\s*[:.]?\s*(\d{3,6}-\d{4})", texto)
        dados["numero_op"] = match.group(1) if match else None

    tipo_op_match = re.search(r"[Tt]ipo\s+da\s+OP[:.\s]+(\S+)", texto)
    dados["tipo_op"] = tipo_op_match.group(1) if tipo_op_match else None

    setor_match = re.search(r"[Ss]etor\s+[Pp]rodut[ivíoO]+\.?[:.\s]+(\S+)", texto)
    dados["setor_produtivo"] = setor_match.group(1) if setor_match else None

    # O valor do lote (ex.: "20260901/3000") fica sozinho numa linha
    # própria, separado do rótulo "LOTE" - o rótulo em si aparece
    # colado na linha de 'Tipo da OP' (vazamento de coluna vizinha,
    # mesmo padrão de layout visto em outros campos), então busca o
    # PADRÃO do valor (dígitos/dígitos) em vez do rótulo.
    lote_match = re.search(r"\b(\d{6,10}/\d{3,6})\b", texto)
    dados["lote"] = lote_match.group(1) if lote_match else None

    periodo = re.search(
        r"Principal[:.\s]+(\d{2}/\d{2}/\d{4})\s*at[eé]\s*(\d{2}/\d{2}/\d{4})", texto
    )
    if periodo:
        dados["periodo_inicio"] = periodo.group(1)
        dados["periodo_fim"] = periodo.group(2)

    produto_linha = _proxima_linha_nao_vazia(texto, r"PRODUTO\s+A\s+PRODUZIR")
    if produto_linha:
        # "34-7506-00BR - CLIP TUBE - BRESIL - UN" -> código é tudo
        # antes do primeiro " - "
        dados["produto_codigo"] = produto_linha.split(" - ")[0].strip()

    quantidade_linha = _proxima_linha_nao_vazia(texto, r"QUANTIDADE\s+A\s+PRODUZIR")
    dados["quantidade_a_produzir"] = _limpar_inteiro(quantidade_linha) if quantidade_linha else None

    equipamento = re.search(
        r"Equipamento[:.\s]+(\S+)\s*-\s*(.+?)(?:\s*Cavidades|\n|$)", texto
    )
    if equipamento:
        dados["numero_maquina"] = equipamento.group(1).strip()
        dados["equipamento_descricao"] = equipamento.group(2).strip()

    cavidades = re.search(r"Cavidades[:.\s]+(\d+)", texto)
    if cavidades:
        dados["cavidades"] = int(cavidades.group(1))

    ciclo = re.search(r"Ciclo\s*\(segundos\)[:.\s]+([\d,\.]+)", texto)
    if ciclo:
        dados["ciclo_segundos"] = _limpar_decimal(ciclo.group(1))

    ferramenta = re.search(
        r"Ferramenta[:.\s]+(\S+)\s*-\s*(.+?)(?:\s*Ciclo\s*\(segundos\)|\n|$)", texto
    )
    if ferramenta:
        dados["ferramenta_codigo"] = ferramenta.group(1).strip()
        dados["ferramenta_descricao"] = _remover_ruido_final(ferramenta.group(2))

    formula = re.search(
        r"F[óo]rmula[:.\s]+(\d+)\s*-\s*(.+?)(?:\s*Q[tr]de\s+Produzida|\n|$)", texto
    )
    if formula:
        dados["formula_codigo"] = formula.group(1).strip()
        dados["formula_descricao"] = _remover_ruido_final(formula.group(2))

    embalagem = re.search(
        r"Embalagem[:.\s]+(\d+)\s*-\s*(.+?)(?:\s*Peso\s+l[íi]quido|\n|$)", texto
    )
    if embalagem:
        dados["embalagem_codigo"] = embalagem.group(1).strip()
        dados["embalagem_descricao"] = _remover_ruido_final(embalagem.group(2))

    qtde_embalagem = re.search(r"Q[tr]de\s+por\s+embalagem[:.\s]+([\d\.]+)", texto)
    if qtde_embalagem:
        dados["qtde_por_embalagem"] = _limpar_inteiro(qtde_embalagem.group(1))

    qtde_embalagens_prev = re.search(r"Q[tr]de\s+de\s+Embalagens\s+Previstas[:.\s]+(\d+)", texto)
    if qtde_embalagens_prev:
        dados["qtde_embalagens_previstas"] = int(qtde_embalagens_prev.group(1))

    qtde_hora = re.search(r"Q[tr]de\s+Produzida\s+por\s+Hora[:.\s]+([\d\.]+)", texto)
    if qtde_hora:
        dados["qtde_produzida_por_hora_meta"] = _limpar_inteiro(qtde_hora.group(1))

    peso_liq = re.search(r"Peso\s+l[íi]quido\s+unit[áa]rio[:.\s]+([\d,\.]+)", texto)
    if peso_liq:
        dados["peso_liquido_unitario"] = _limpar_decimal(peso_liq.group(1))

    peso_bru = re.search(r"Peso\s+bruto\s+unit[áa]rio[:.\s]+([\d,\.]+)", texto)
    if peso_bru:
        dados["peso_bruto_unitario"] = _limpar_decimal(peso_bru.group(1))

    observacoes = re.search(r"Observa[çc][õo]es[:.\s]+(.+)", texto)
    if observacoes:
        dados["observacoes"] = observacoes.group(1).strip()

    # Composição da mistura: bloco de texto entre os dois cabeçalhos -
    # guardado como texto livre (mesmo formato do campo no schema),
    # não estruturado, já que a tabela pode ter qualquer nº de linhas
    composicao = re.search(
        r"COMPOSI[ÇC][ÃA]O\s+DA\s+MISTURA\s*\n(.+?)(?:Observa[çc][õo]es|\Z)",
        texto, re.IGNORECASE | re.DOTALL,
    )
    if composicao:
        linhas_composicao = [linha.strip() for linha in composicao.group(1).splitlines() if linha.strip()]
        if linhas_composicao:
            dados["composicao_mistura"] = "\n".join(linhas_composicao)

    return dados
