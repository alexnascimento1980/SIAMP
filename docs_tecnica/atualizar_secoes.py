from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

CAMINHO = "SIAMP_Documentacao_Tecnica.docx"

doc = Document(CAMINHO)


def encontrar(texto_contido):
    for p in doc.paragraphs:
        if texto_contido in p.text:
            return p
    raise RuntimeError(f"Parágrafo de referência não encontrado: {texto_contido!r}")


def estilo_corpo_de(paragrafo_modelo):
    """Copia o estilo de parágrafo (alignment, espaçamento) de um
    parágrafo de corpo já existente, para os novos ficarem visualmente
    idênticos aos demais - mesmo padrão do inserir_secao.py."""
    def aplicar(p, texto):
        p.alignment = paragrafo_modelo.alignment
        p.paragraph_format.space_after = paragrafo_modelo.paragraph_format.space_after
        p.paragraph_format.line_spacing = paragrafo_modelo.paragraph_format.line_spacing
        r = p.add_run(texto)
        r.font.size = Pt(12)
        return p
    return aplicar


# --- 1. Tabela de tecnologias: python-jose -> PyJWT --------------------
for table in doc.tables:
    for row in table.rows:
        for cell in row.cells:
            if "python-jose" in cell.text:
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.text = r.text.replace("python-jose", "PyJWT")
print("1. Tabela de tecnologias atualizada.")


# --- 2. Seção 5.2: correção da data do 3º turno -------------------------
ref_meia_noite = encontrar("exigir que o operador o divida manualmente em duas partes")
aplicar = estilo_corpo_de(ref_meia_noite)

p1 = ref_meia_noite.insert_paragraph_before()
aplicar(
    p1,
    "Um problema relacionado, mas distinto, surgiu meses depois em uso "
    "real: a data gravada para o turno (usada em filtros por período, "
    "no histórico e nos relatórios) correspondia ao dia em que o "
    "fechamento era realizado, não ao dia em que o turno de fato "
    "começou — no caso do 3º turno, fechar de madrugada (por exemplo, "
    "às 4h) registrava a data do próprio dia do fechamento, quando o "
    "turno havia começado às 22h do dia anterior. A correção calcula a "
    "data do turno a partir do horário de início dos próprios "
    "lançamentos registrados, não do texto do turno selecionado no "
    "formulário — verificação mais robusta, que continua funcionando "
    "mesmo que os horários dos turnos mudem no futuro: se algum "
    "horário registrado for noturno (a partir das 18h) e o momento do "
    "fechamento for de madrugada (antes das 5h), a data recua um dia."
)

p2 = ref_meia_noite.insert_paragraph_before()
aplicar(
    p2,
    "A primeira implementação dessa lógica continha, ela mesma, um "
    "erro sutil, identificado pelos próprios testes automatizados "
    "antes de ser aplicada em produção: comparar os horários "
    "registrados pelo valor mínimo para decidir se algum deles era "
    "noturno falha exatamente no caso mais realista, uma sequência de "
    "lançamentos que atravessa a meia-noite (por exemplo, 22h, 23h e "
    "2h) — o valor mínimo nesse conjunto é 2h, não 22h, porque a "
    "comparação considera apenas a posição no relógio de 24 horas, "
    "sem noção de qual lançamento ocorreu primeiro na sequência real. "
    "A versão corrigida verifica se qualquer um dos horários "
    "registrados é noturno, não apenas o menor deles — episódio que "
    "ilustra como escrever o teste antes de confiar na correção pode "
    "revelar um erro na própria correção, não só no código original."
)
print("2. Seção 5.2 (3º turno) atualizada.")


# --- 3. Seção 5.3: correção da descrição do tratamento de falha ---------
p_errado = encontrar("simplesmente não contribuem para a capacidade teórica esperada")
assert len(p_errado.runs) == 1, "Parágrafo esperado com um único run - formatação pode ter mudado."
p_errado.runs[0].text = (
    "O tratamento das paradas passou por uma correção relevante ao "
    "longo do desenvolvimento. Na primeira versão do modelo de "
    "lançamentos livres, tanto paradas programadas quanto falhas na "
    "injetora simplesmente não contribuíam para a capacidade teórica "
    "esperada, deixando o cálculo de eficiência cego ao tempo perdido "
    "em qualquer um dos dois casos — uma falha de várias horas podia "
    "coexistir com um índice de produção de 100%, desde que o que "
    "fosse produzido no tempo restante batesse com o esperado daquele "
    "intervalo menor. O comportamento divergia do modelo por hora, que "
    "já tratava a distinção corretamente: uma hora com parada não "
    "programada mantinha a capacidade esperada cheia, sem desconto, "
    "enquanto só a parada programada era descontada proporcionalmente "
    "— diferença notada ao comparar deliberadamente os dois modelos "
    "lado a lado. A correção unificou o tratamento, adaptado ao modelo "
    "de duração real: a duração de uma falha na injetora passou a ser "
    "somada à capacidade teórica esperada do turno (usando o ciclo e "
    "as cavidades cadastrados na máquina, já que uma parada não tem "
    "peça vinculada), sem nenhuma produção correspondente a somar no "
    "lado realizado — reduzindo corretamente o índice de produção e o "
    "OEE. A duração de paradas programadas continua não contribuindo "
    "em nenhum dos dois lados do cálculo, por representar tempo de "
    "manutenção ou troca de molde planejado, que não deve penalizar o "
    "turno."
)
print("3. Seção 5.3 (tratamento de falha) corrigida.")


# --- 4. Seção 6: achados de segurança e correções -----------------------
ref_seguranca_fim = encontrar("impedindo o envio do cookie de sessão")
# Esse é o último item da lista de bullets - o próximo parágrafo depois
# dele é a heading "7 TESTES AUTOMATIZADOS". Inserimos os novos
# parágrafos narrativos entre os dois.
heading_testes = None
for p in doc.paragraphs:
    if p.text.strip() == "7 TESTES AUTOMATIZADOS" and p.style and p.style.name == "Heading 1":
        heading_testes = p
        break
if heading_testes is None:
    raise RuntimeError("Não encontrou a heading '7 TESTES AUTOMATIZADOS'.")

aplicar_seg = estilo_corpo_de(ref_seguranca_fim)

p_sec1 = heading_testes.insert_paragraph_before()
aplicar_seg(
    p_sec1,
    "Duas avaliações de segurança independentes, conduzidas já com o "
    "sistema em uso, encontraram falhas reais que iam além da lista "
    "acima. A primeira identificou um XSS armazenado (stored "
    "Cross-Site Scripting) em um padrão específico de interpolação: "
    "campos de texto livre digitados pelo usuário (nome do turno, "
    "código de peça, nome de usuário) eram inseridos diretamente "
    "dentro de um atributo de manipulador de evento inline "
    "(onclick=\"...\"), com escape de caracteres HTML aplicado — "
    "suficiente para um atributo comum, mas não para esse caso "
    "específico. O motivo é uma segunda camada de interpretação que só "
    "existe para atributos de evento: o navegador decodifica as "
    "entidades HTML do atributo (por exemplo, aspas escapadas de volta "
    "para aspas literais) antes de tratar o conteúdo decodificado como "
    "código JavaScript, permitindo que uma aspas escapada corretamente "
    "para exibição na página ainda assim escapasse da string de código "
    "onde havia sido interpolada, possibilitando a execução de "
    "JavaScript arbitrário. Como o texto malicioso ficava gravado no "
    "banco de dados (por exemplo, no nome de um turno) e só era "
    "executado quando outro usuário — tipicamente um perfil "
    "administrador, ao abrir a tela correspondente — visualizava a "
    "página, o achado configurava um vetor real de escalonamento de "
    "privilégio entre perfis do sistema. A correção substituiu a "
    "interpolação direta por atributos de dados (data-*), lidos pelo "
    "próprio manipulador de evento em tempo de execução — um atributo "
    "de dado comum não tem a segunda camada de interpretação como "
    "código, então o escape de caracteres HTML já aplicado passa a ser "
    "suficiente. Como reforço adicional, a função de escape usada em "
    "todo o frontend, que já tratava corretamente os caracteres < e > "
    ", passou a tratar aspas simples e duplas também, mesmo nos pontos "
    "em que isso não era estritamente necessário — reduzindo o risco "
    "de um erro equivalente se reintroduzir no futuro por outro "
    "caminho."
)

p_sec2 = heading_testes.insert_paragraph_before()
aplicar_seg(
    p_sec2,
    "A segunda avaliação encontrou uma lacuna na proteção de contas "
    "administrativas contra ação acidental de outro administrador "
    "(mecanismo introduzido após um incidente real, descrito na seção "
    "5.10): a marcação de conta protegida já bloqueava corretamente a "
    "exclusão e a desativação de uma conta, mas duas rotas igualmente "
    "sensíveis — redefinir a senha de outro usuário e alterar o perfil "
    "de acesso — não verificavam essa mesma marcação. Na prática, um "
    "administrador ainda podia redefinir a senha de uma conta "
    "protegida de outro administrador e assumir a sessão dela, ou "
    "rebaixar seu perfil de acesso, exatamente o cenário que a "
    "proteção fora criada para evitar. A correção estendeu a mesma "
    "verificação às duas rotas, com uma exceção deliberada em cada "
    "caso: redefinir a própria senha continua permitido mesmo com a "
    "própria conta protegida, por não reduzir segurança alguma — a "
    "pessoa já está autenticada como ela mesma —, e reenviar o mesmo "
    "perfil de acesso que já está definido também continua permitido, "
    "por não ter efeito prático. Um terceiro achado, de risco mais "
    "baixo, tratou de um campo que identificava o autor de uma "
    "parada registrada aceitando um valor arbitrário enviado pelo "
    "cliente em vez de ser sempre derivado da sessão autenticada — "
    "corrigido para nunca aceitar esse valor de fora, prevenindo a "
    "atribuição de um registro a outro usuário."
)
print("4. Seção 6 (segurança) ampliada.")

doc.save(CAMINHO)
print("\nDocumento salvo com sucesso.")
