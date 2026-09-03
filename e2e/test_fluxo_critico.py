"""Cobre o caminho mais usado no dia a dia do sistema: apontar a
produção de um turno, fechar o turno, e confere que o relatório em
PDF é gerado corretamente. Roda contra a stack real (docker compose),
não contra um TestClient - complementa (não substitui) a suíte de
unidade/integração do backend, que já cobre a lógica de negócio
isoladamente com muito mais profundidade e velocidade. O valor aqui é
garantir que frontend e backend continuam conversando direito através
da interface real, do jeito que uma pessoa realmente usa o sistema.

Login não é feito aqui diretamente - reaproveita a fixture
`pagina_logada` (login único por sessão inteira de testes, ver
conftest.py) para não esgotar o limite de tentativas por minuto do
endpoint de login conforme a suíte cresce para cobrir mais fluxos.
"""


def test_fechar_turno_e_baixar_pdf_do_historico(pagina_logada):
    page = pagina_logada
    dialogs = []
    page.on("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.accept()))

    page.goto("/apontamento.html")
    # Injetora e peça cadastradas em database/seeds.sql - ver docstring
    # de conftest.py sobre manter isso sincronizado.
    page.wait_for_selector('[data-numero-maquina="1"]', timeout=10_000)
    page.click('[data-numero-maquina="1"]')

    page.fill("#nomeLider", "Líder Teste E2E")
    # A busca de peça resolve por correspondência exata de texto
    # ("código - descrição") para o campo oculto #lancPeca - ver
    # frontend/js/apontamento.js, listener de "input" em
    # #lancPecaBusca.
    page.fill("#lancPecaBusca", "1 - Tube Alimentation 1/2")
    page.fill("#lancQuantidade", "500")
    page.fill("#lancInicio", "05:00")
    page.fill("#lancFim", "06:00")
    page.click("#btnAdicionarLancamento")

    # Confirma que o lançamento realmente entrou na lista antes de
    # tentar fechar o turno - evita um falso positivo caso o clique
    # anterior não tenha sido processado a tempo.
    page.wait_for_selector("#corpoListaLancamentos tr", timeout=5_000)

    page.click('button:has-text("Assinar e Finalizar Turno")')
    page.wait_for_url("**/historico.html", timeout=10_000)
    assert any("sucesso" in msg.lower() for msg in dialogs), (
        f"Esperava um alerta de sucesso ao fechar o turno, recebido: {dialogs}"
    )

    # O turno recém-fechado deve aparecer no topo da lista - baixa o
    # relatório e confirma que é mesmo um PDF válido, não uma página
    # de erro disfarçada de download.
    with page.expect_download() as download_info:
        page.locator('button:has-text("PDF")').first.click()
    download = download_info.value

    caminho = download.path()
    with open(caminho, "rb") as arquivo:
        conteudo = arquivo.read()
    assert conteudo[:4] == b"%PDF", "Arquivo baixado não começa com a assinatura de um PDF válido"
    assert len(conteudo) > 1000, "PDF baixado parece vazio ou incompleto demais para ser real"
