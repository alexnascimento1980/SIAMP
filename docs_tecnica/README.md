# Scripts de edição da documentação técnica (Word)

O arquivo `SIAMP_Documentacao_Tecnica.docx` (entregue ao usuário, não
versionado aqui por ser binário/grande) é editado incrementalmente
com `python-docx`, não gerado do zero a cada sessão.

Cada script nesta pasta documenta UMA rodada de edição - histórico de
como o documento chegou ao estado atual. Ao adicionar uma seção nova,
copie o padrão de `inserir_secao.py`:

1. Localize o parágrafo de referência (heading) antes do qual inserir.
2. Repita as funções auxiliares (`corpo`, `heading2`, `imagem`, `legenda`)
   copiando o estilo/formatação de um parágrafo já existente do mesmo
   tipo (`p.style`, `paragraph_format`) - nunca formate do zero.
3. Ao inserir uma linha nova no **sumário**, copie o `pPr` (XML) de uma
   linha de sumário já existente para a nova, não só o `.style` - o
   tab stop com dot leader é uma configuração direta de parágrafo, não
   herdada do estilo. Cuidado ao buscar o parágrafo de referência: título
   de seção no sumário e o heading real no corpo do texto têm o MESMO
   texto (a diferença é a linha do sumário conter `\t<página>` no final)
   - sempre filtre por `"\t" in p.text` para não pegar o heading errado.
4. Depois de editar, sempre renderize e MEÇA as páginas reais
   (`soffice.py --convert-to pdf` + `pdftotext -layout` procurando os
   títulos de seção), nunca estime - a paginação real muda de formas
   não óbvias.

Motivo de existir esta pasta: numa sessão anterior, o pipeline original
(gerava o .docx do zero via `docx` npm) foi perdido num reset de
sandbox, por nunca ter sido versionado no Git - só o arquivo `.docx`
final sobreviveu (estava em `/mnt/user-data/outputs`). Recuperado
editando esse arquivo final diretamente. Versionar os scripts de edição
evita repetir essa perda.
