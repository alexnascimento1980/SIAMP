"""Fixtures compartilhadas entre os testes E2E.

Credenciais e dados de seed usados aqui (EMAIL_ADMIN_E2E, máquina "1",
peça "1") precisam bater com o que a stack de CI efetivamente
provisiona - ver .github/workflows/e2e.yml (variáveis ADMIN_EMAIL/
ADMIN_SENHA do bootstrap automático, ver backend/app/scripts/
create_admin.py) e database/seeds.sql (que já cadastra a Injetora 01
e a peça de código "1" usadas aqui). Só credenciais de CI/teste local
- nunca usar essas mesmas credenciais numa instância real.
"""
import pytest

EMAIL_ADMIN_E2E = "admin-e2e@siamp.test"
SENHA_ADMIN_E2E = "SenhaE2E-Testes-123"


@pytest.fixture
def pagina_logada(page):
    """Página já autenticada, pronta em home.html - reutilize esta
    fixture ao adicionar novos testes (em vez de repetir o login
    manualmente), mas tenha em mente que cada teste que a usa consome
    uma tentativa do limite de 5 logins/minuto por IP (ver docstring
    de test_fluxo_critico.py) - ao ampliar a suíte, prefira poucos
    testes que cobrem vários passos do fluxo a muitos testes pequenos
    que logam de novo a cada um."""
    page.goto("/login.html")
    page.fill("#email", EMAIL_ADMIN_E2E)
    page.fill("#senha", SENHA_ADMIN_E2E)
    page.click("#btnEntrar")
    page.wait_for_url("**/home.html", timeout=10_000)
    return page
