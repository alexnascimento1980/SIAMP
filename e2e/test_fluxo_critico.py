"""Cobre o caminho mais usado no dia a dia do sistema: um operador
loga, aponta a produção de um turno, fecha o turno, e confere que o
relatório em PDF é gerado corretamente. Roda contra a stack real
(docker compose), não contra um TestClient - complementa (não
substitui) a suíte de unidade/integração do backend, que já cobre a
lógica de negócio isoladamente com muito mais profundidade e
velocidade. O valor aqui é garantir que frontend e backend continuam
conversando direito através da interface real, do jeito que uma
pessoa realmente usa o sistema.

Um único teste, de propósito - não um teste avulso de "login funciona"
mais um teste separado do fluxo completo. O endpoint de login tem um
limite de 5 tentativas por minuto por IP (rate limit deliberado contra
força bruta - ver backend/app/core/rate_limit.py), e cada teste que
loga consome uma tentativa: com dois testes fazendo login cada um,
rodar a suíte localmente mais de duas vezes seguidas em menos de um
minuto (cenário bem comum ao depurar algo) já esgotava o limite,
fazendo os testes seguintes falharem por timeout - não por causa de
bug nenhum, só por já ter usado as tentativas disponíveis. Login já é
exercitado aqui como primeiro passo do fluxo, cobertura suficiente sem
precisar de um teste dedicado só para ele.
"""
from conftest import EMAIL_ADMIN_E2E, SENHA_ADMIN_E2E


def test_fechar_turno_e_baixar_pdf_do_historico(page):
    page.goto("/login.html")
    page.fill("#email", EMAIL_ADMIN_E2E)
    page.fill("#senha", SENHA_ADMIN_E2E)
    page.click("#btnEntrar")
    page.wait_for_url("**/home.html", timeout=10_000)

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
