"""Cobre o cadastro de um novo usuário e a proteção de conta contra
exclusão/desativação acidental - funcionalidade que existe
justamente por causa de um incidente real (um ADMIN excluiu por
acidente a conta de outro ADMIN, ver commit que introduziu
Usuario.protegido). O valor de testar isso pela interface, não só via
API (já coberto em profundidade em backend/tests/test_usuarios.py), é
confirmar que os botões Desativar/Excluir realmente ficam
desabilitados na tela depois de proteger - a garantia visual que
motivou a funcionalidade em primeiro lugar, não só o bloqueio no
backend.
"""
import time

from playwright.sync_api import expect


def test_criar_usuario_e_proteger_conta(pagina_logada):
    page = pagina_logada
    # E-mail único por execução - tem restrição de unicidade. Domínio
    # ".test" (usado nas credenciais de login, ver conftest.py) é
    # reservado por RFC 2606 e rejeitado pela validação de e-mail do
    # Pydantic no endpoint de criação de usuário (diferente da conta
    # de login, inserida direto no banco pelo bootstrap, sem passar
    # por essa validação) - descoberto rodando este teste de verdade,
    # não hipoteticamente.
    email = f"e2e-{int(time.time())}@siamp-e2e-testes.com"

    page.goto("/usuarios.html")
    page.fill("#novoNome", "Usuário Teste E2E")
    page.fill("#novoEmail", email)
    page.select_option("#novoPerfil", label="Operador")
    page.fill("#novaSenha", "SenhaTesteE2E123")
    page.click("#btnCriar")

    linha = page.locator(f"tr:has-text('{email}')")
    linha.wait_for(state="visible", timeout=5_000)

    # Protege a conta recém-criada - sem diálogo de confirmação ao
    # ADICIONAR proteção (só ao remover, ver frontend/js/usuarios.js,
    # alternarProtecao), então não precisa tratar dialog aqui.
    linha.locator("button[title*='Proteger']").click()

    # A tabela é recarregada de forma assíncrona depois da chamada à
    # API (carregarUsuarios(), disparado só após a resposta de
    # sucesso) - expect() espera automaticamente até a condição ficar
    # verdadeira ou o tempo esgotar, em vez de checar uma vez só
    # (is_disabled() puro checaria antes do recarregamento terminar,
    # dando falso negativo por pura questão de tempo, não de lógica).
    linha = page.locator(f"tr:has-text('{email}')")
    botao_desativar = linha.locator("button", has_text="Desativar")
    # Título do botão Desativar também contém "protegida" quando
    # desabilitado ("Conta protegida - remova a proteção para
    # desativar") - "para excluir" é o trecho que distingue o botão
    # de excluir do de desativar dentro da mesma linha.
    botao_excluir = linha.locator("button[title*='para excluir']")
    expect(botao_desativar).to_be_disabled(timeout=5_000)
    expect(botao_excluir).to_be_disabled(timeout=5_000)
