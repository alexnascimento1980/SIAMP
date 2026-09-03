"""Cobre o cadastro manual de uma Ordem de Produção pela interface -
não cobre a extração via PDF/foto (OCR), que já tem cobertura própria
e mais detalhada na suíte do backend (backend/tests/
test_extracao_documento_op*.py), incluindo testes de integração
contra documentos reais. Repetir isso aqui, através do navegador,
adicionaria tempo de execução sem cobrir nada que a suíte do backend
já não cubra - o valor de um teste E2E está em confirmar que
frontend e backend conversam certo pela interface, não em duplicar
cobertura de lógica já testada em profundidade em outro lugar.
"""
import time


def test_criar_ordem_de_producao_manual(pagina_logada):
    page = pagina_logada
    # Número único por execução - numero_op tem restrição de
    # unicidade, então rodar a suíte mais de uma vez contra o mesmo
    # banco (comum ao depurar localmente) não pode reusar o mesmo
    # número.
    numero_op = f"E2E-{int(time.time())}"

    page.goto("/ordens_producao.html")
    page.click("#btnToggleForm")
    page.wait_for_selector("#numeroOp", state="visible", timeout=5_000)

    page.fill("#numeroOp", numero_op)
    page.fill("#periodoInicio", "2026-09-01")
    page.fill("#periodoFim", "2026-09-10")
    # Peça e máquina cadastradas em database/seeds.sql - rótulo exato
    # montado em frontend/js/ordens_producao.js (carregarCatalogos).
    page.select_option("#produtoId", label="1 - Tube Alimentation 1/2")
    page.select_option("#numeroMaquina", label="1 - Injetora 01 - Peça A")
    page.fill("#quantidadeAProduzir", "1000")

    page.click("#btnSalvarOp")

    # A OP recém-criada deve aparecer na lista, identificável pelo
    # número único gerado acima.
    page.wait_for_selector(f"#listaOps :text('{numero_op}')", timeout=5_000)
