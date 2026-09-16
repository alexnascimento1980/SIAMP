from docx import Document

CAMINHO = "SIAMP_Documentacao_Tecnica.docx"
doc = Document(CAMINHO)

# (prefixo do título no sumário, página antiga, página nova) - só as
# entradas que de fato mudaram, medidas linha a linha no PDF renderizado
# (nunca estimadas - ver docs_tecnica/README.md).
ATUALIZACOES = [
    ("5.3 Cálculo do Indicador OEE", "16", "17"),
    ("5.4 Salvamento de Rascunho do Turno", "18", "20"),
    ("5.5 Gestão de Máquinas e Peças", "19", "20"),
    ("5.6 Ordens de Produção e Importação em Lote", "20", "21"),
    ("5.7 Dashboard Analítico e Machine Learning", "21", "22"),
    ("5.8 Histórico, Relatórios em PDF e Exportação para Análise", "24", "25"),
    ("5.9 Envio Automático de Relatórios por E-mail", "25", "26"),
    ("5.10 Gestão de Usuários e Destinatários", "27", "28"),
    ("5.11 Extração de Dados de Ordem de Produção via PDF ou Foto", "29", "30"),
    ("6 SEGURANÇA DA APLICAÇÃO", "32", "33"),
    ("7 TESTES AUTOMATIZADOS", "33", "35"),
    ("8 IMPLANTAÇÃO EM PRODUÇÃO (DEPLOY)", "35", "37"),
    ("9 CONSIDERAÇÕES FINAIS", "35", "38"),
    ("REFERÊNCIAS", "36", "38"),
]

# Título do sumário e heading real no corpo do texto têm o MESMO texto -
# a diferença é a linha do sumário conter "\t<página>" no final (ver
# docs_tecnica/README.md). Filtramos por "\t" para nunca pegar o
# heading do corpo por engano.
paragrafos_sumario = [p for p in doc.paragraphs if "\t" in p.text]

nao_encontrados = []
for prefixo, pagina_antiga, pagina_nova in ATUALIZACOES:
    encontrado = False
    for p in paragrafos_sumario:
        texto_titulo, _, pagina_atual = p.text.rpartition("\t")
        if texto_titulo.strip() == prefixo and pagina_atual.strip() == pagina_antiga:
            # A página nem sempre vive isolada no último run - às vezes
            # o run final é vazio (artefato de formatação), e o texto
            # "título\tpágina" inteiro vive num run anterior. Busca
            # qualquer run cujo texto termine com "\t<página_antiga>" e
            # substitui só esse sufixo, preservando o resto do run
            # intacto.
            alvo = "\t" + pagina_antiga
            for r in p.runs:
                if r.text.endswith(alvo):
                    r.text = r.text[: -len(alvo)] + "\t" + pagina_nova
                    encontrado = True
                    break
            break
    if not encontrado:
        nao_encontrados.append((prefixo, pagina_antiga, pagina_nova))
    else:
        print(f"OK: {prefixo!r} {pagina_antiga} -> {pagina_nova}")

if nao_encontrados:
    print("\nNÃO ENCONTRADOS (revisar manualmente):")
    for item in nao_encontrados:
        print(" ", item)
else:
    doc.save(CAMINHO)
    print("\nSumário atualizado e salvo com sucesso.")
