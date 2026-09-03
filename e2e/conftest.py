"""Fixtures compartilhadas entre os testes E2E.

As credenciais de login (E2E_ADMIN_EMAIL/E2E_ADMIN_SENHA) são lidas de
variáveis de ambiente, com um valor padrão que bate com o que o CI
provisiona automaticamente (ver .github/workflows/e2e.yml e
backend/app/scripts/create_admin.py) - o valor padrão não serve pra
rodar localmente contra o SEU banco de dados de verdade, a menos que
você tenha uma conta com esse e-mail/senha específicos cadastrada.
Pra testar localmente usando a conta admin que você já tem (sem
precisar editar o .env nem reiniciar a stack), defina as duas
variáveis antes de rodar o pytest - ver e2e/README.md.

Máquina "1" e peça "1" usadas no teste vêm de database/seeds.sql
(cadastradas via SEED_ON_START=true) - se algum dia esses dados de
seed mudarem, o teste precisa acompanhar.
"""
import os

import pytest

EMAIL_ADMIN_E2E = os.getenv("E2E_ADMIN_EMAIL", "admin-e2e@siamp.test")
SENHA_ADMIN_E2E = os.getenv("E2E_ADMIN_SENHA", "SenhaE2E-Testes-123")


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
