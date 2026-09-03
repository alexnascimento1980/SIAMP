import csv
import io
from datetime import date, datetime

from defusedxml import ElementTree as SafeET
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.maquina import Maquina
from app.models.ordem_producao import OrdemProducao
from app.models.produto import Produto
from app.schemas.ordem_producao_schema import OrdemProducaoCreate

# Colunas esperadas no arquivo (CSV: cabeçalho da primeira linha; XML:
# nome da tag dentro de cada elemento) - mesmos nomes dos campos do
# formulário manual de Ordem de Produção, para manter consistência.
# Só as cinco primeiras são obrigatórias; o resto é opcional -
# numero_maquina inclusive, já que uma OP pode ser atendida por mais
# de uma injetora ao longo do período (comparativo de meta x produção
# soma por ordem_producao_id, independente da máquina).
COLUNAS_OBRIGATORIAS = {
    "numero_op", "produto_codigo",
    "quantidade_a_produzir", "periodo_inicio", "periodo_fim",
}
COLUNAS_OPCIONAIS = {
    "numero_maquina",
    "data_emissao", "tipo_op", "setor_produtivo", "lote",
    "equipamento_descricao", "ferramenta_codigo", "ferramenta_descricao",
    "formula_codigo", "formula_descricao", "embalagem_codigo",
    "embalagem_descricao", "qtde_por_embalagem", "qtde_embalagens_previstas",
    "cavidades", "ciclo_segundos", "qtde_produzida_por_hora_meta",
    "peso_liquido_unitario", "peso_bruto_unitario", "composicao_mistura",
    "observacoes",
}
COLUNAS_INTEIRAS = {
    "quantidade_a_produzir", "qtde_por_embalagem", "qtde_embalagens_previstas",
    "cavidades", "qtde_produzida_por_hora_meta",
}
COLUNAS_FLOAT = {"ciclo_segundos", "peso_liquido_unitario", "peso_bruto_unitario"}
COLUNAS_DATA = {"data_emissao", "periodo_inicio", "periodo_fim"}


class LinhaInvalidaError(Exception):
    """Erro específico de UMA linha do arquivo - não interrompe o
    processamento das demais, só faz essa linha ser reportada como
    rejeitada."""


def _obter(linha: dict, chave: str) -> str:
    """Leitura segura de um campo da linha - trata tanto coluna ausente
    (chave nem existe no dict) quanto valor vazio/None (linha do CSV
    mais curta que o cabeçalho, ou tag XML sem texto)."""
    valor = linha.get(chave)
    return (valor or "").strip()


def _parse_data(valor: str) -> date:
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(valor, formato).date()
        except ValueError:
            continue
    raise LinhaInvalidaError(
        f"Data inválida: '{valor}' (use AAAA-MM-DD ou DD/MM/AAAA)."
    )


def _converter_linha(linha: dict) -> dict:
    """Converte os valores textuais brutos (de CSV/XML, sempre string)
    para os tipos esperados pelo schema - datas, inteiros e floats.
    Ignora colunas vazias ou desconhecidas."""
    convertido = {}
    for chave in COLUNAS_OBRIGATORIAS | COLUNAS_OPCIONAIS:
        valor = _obter(linha, chave)
        if not valor:
            continue
        if chave in COLUNAS_DATA:
            convertido[chave] = _parse_data(valor)
        elif chave in COLUNAS_INTEIRAS:
            try:
                convertido[chave] = int(float(valor.replace(",", ".")))
            except ValueError as erro:
                raise LinhaInvalidaError(
                    f"Valor inválido em '{chave}': '{valor}' (esperado número inteiro)."
                ) from erro
        elif chave in COLUNAS_FLOAT:
            try:
                convertido[chave] = float(valor.replace(",", "."))
            except ValueError as erro:
                raise LinhaInvalidaError(
                    f"Valor inválido em '{chave}': '{valor}' (esperado número)."
                ) from erro
        else:
            convertido[chave] = valor
    return convertido


def _ler_csv(conteudo: bytes) -> list[dict]:
    texto = conteudo.decode("utf-8-sig")  # aceita BOM (Excel/Windows)
    linhas_texto = texto.splitlines()
    primeira_linha = linhas_texto[0] if linhas_texto else ""
    # ERPs/Excel em configuração pt-BR costumam exportar CSV com ';'
    # como separador (vírgula é usada como decimal) - detecta qual dos
    # dois aparece mais na primeira linha.
    delimitador = ";" if primeira_linha.count(";") > primeira_linha.count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto), delimiter=delimitador)
    return [dict(linha) for linha in leitor]


def _ler_xml(conteudo: bytes) -> list[dict]:
    """Espera uma tag raiz contendo elementos repetidos (qualquer nome
    de tag), cada um com subelementos nomeados igual às colunas do
    CSV. Ex.:
    <ordens_producao>
      <ordem>
        <numero_op>OP-123</numero_op>
        <produto_codigo>34-7506-00BR</produto_codigo>
        ...
      </ordem>
    </ordens_producao>

    Usa defusedxml (não xml.etree.ElementTree puro) - parsing de XML
    de arquivos enviados por usuários é um vetor de ataque conhecido
    (XXE, bilhão de risadas); defusedxml bloqueia isso por padrão.
    """
    raiz = SafeET.fromstring(conteudo)
    linhas = []
    for elemento in raiz:
        linha = {filho.tag: (filho.text or "") for filho in elemento}
        if linha:
            linhas.append(linha)
    return linhas


def _resolver_produto_por_codigo(db: Session, codigo: str) -> Produto | None:
    return (
        db.query(Produto)
        .filter(func.lower(Produto.codigo) == codigo.lower())
        .first()
    )


def _resolver_maquina_por_numero(db: Session, numero: str) -> Maquina | None:
    maquina = db.query(Maquina).filter(Maquina.numero_maquina == numero).first()
    if maquina is not None:
        return maquina
    normalizado = numero.lstrip("0") or "0"
    if normalizado != numero:
        return db.query(Maquina).filter(Maquina.numero_maquina == normalizado).first()
    return None


def importar_ordens_producao(
    db: Session, conteudo: bytes, nome_arquivo: str, usuario_id: int
) -> dict:
    """Importa Ordens de Produção em lote, de um arquivo CSV ou XML.

    Processa cada linha de forma independente: uma linha com erro
    (peça não cadastrada, data inválida, número de OP duplicado etc.)
    é rejeitada e reportada, sem impedir que as demais linhas válidas
    sejam importadas. Peças e máquinas não encontradas no cadastro são
    listadas à parte, para facilitar cadastrá-las antes de tentar de
    novo.
    """
    extensao = nome_arquivo.rsplit(".", 1)[-1].lower() if "." in nome_arquivo else ""
    if extensao == "csv":
        linhas_brutas = _ler_csv(conteudo)
    elif extensao == "xml":
        linhas_brutas = _ler_xml(conteudo)
    else:
        raise ValueError("Formato não suportado - envie um arquivo .csv ou .xml.")

    if not linhas_brutas:
        raise ValueError("O arquivo não contém nenhuma linha de dados.")

    erros = []
    pecas_faltando = set()
    maquinas_faltando = set()
    numeros_op_no_arquivo = set()
    novas_ordens = []

    numeros_op_existentes = {
        numero for (numero,) in db.query(OrdemProducao.numero_op).all()
    }

    # Começa em 2: linha 1 é o cabeçalho no CSV (aproximação razoável
    # também para XML, onde não há de fato uma "linha 1" literal, mas
    # mantém a numeração consistente entre os dois formatos).
    for indice, linha_bruta in enumerate(linhas_brutas, start=2):
        numero_op = _obter(linha_bruta, "numero_op")
        try:
            faltando = {c for c in COLUNAS_OBRIGATORIAS if not _obter(linha_bruta, c)}
            if faltando:
                raise LinhaInvalidaError(
                    f"Campo(s) obrigatório(s) ausente(s): {', '.join(sorted(faltando))}."
                )

            if numero_op in numeros_op_existentes:
                raise LinhaInvalidaError(
                    f"Já existe uma OP cadastrada com o número '{numero_op}'."
                )
            if numero_op in numeros_op_no_arquivo:
                raise LinhaInvalidaError(
                    f"Número de OP '{numero_op}' repetido dentro do próprio arquivo."
                )

            produto_codigo = _obter(linha_bruta, "produto_codigo")
            produto = _resolver_produto_por_codigo(db, produto_codigo)
            if produto is None:
                pecas_faltando.add(produto_codigo)
                raise LinhaInvalidaError(
                    f"Peça com código '{produto_codigo}' não está cadastrada no catálogo."
                )

            numero_maquina = _obter(linha_bruta, "numero_maquina")
            maquina = None
            if numero_maquina:
                maquina = _resolver_maquina_por_numero(db, numero_maquina)
                if maquina is None:
                    maquinas_faltando.add(numero_maquina)
                    raise LinhaInvalidaError(f"Máquina '{numero_maquina}' não está cadastrada.")

            dados_convertidos = _converter_linha(linha_bruta)
            dados_convertidos["produto_id"] = produto.id
            dados_validados = OrdemProducaoCreate(**dados_convertidos)

            nova = OrdemProducao(
                **dados_validados.model_dump(exclude={"numero_maquina", "produto_id"}),
                maquina_id=maquina.id if maquina else None,
                equipamento_codigo=dados_validados.numero_maquina,
                produto_id=produto.id,
                produto_codigo=produto.codigo,
                produto_descricao=produto.descricao,
                criado_por_id=usuario_id,
            )
            novas_ordens.append(nova)
            numeros_op_no_arquivo.add(numero_op)

        except LinhaInvalidaError as exc:
            erros.append({"linha": indice, "numero_op": numero_op or None, "motivo": str(exc)})
        except Exception as exc:
            # Erros de validação do Pydantic (ex.: periodo_fim antes de
            # periodo_inicio) caem aqui - mesma mensagem clara, mesma
            # forma de reportar.
            erros.append({"linha": indice, "numero_op": numero_op or None, "motivo": str(exc)})

    for ordem in novas_ordens:
        db.add(ordem)
    db.commit()

    return {
        "total_linhas": len(linhas_brutas),
        "criadas": len(novas_ordens),
        "numeros_op_criados": [o.numero_op for o in novas_ordens],
        "erros": erros,
        "pecas_faltando": sorted(pecas_faltando),
        "maquinas_faltando": sorted(maquinas_faltando),
    }
