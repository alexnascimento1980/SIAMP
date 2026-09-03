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

Máquina "1" e peça "1" usadas nos testes vêm de database/seeds.sql
(cadastradas via SEED_ON_START=true) - se algum dia esses dados de
seed mudarem, os testes precisam acompanhar.
"""
import os

import pytest

EMAIL_ADMIN_E2E = os.getenv("E2E_ADMIN_EMAIL", "admin-e2e@siamp.test")
SENHA_ADMIN_E2E = os.getenv("E2E_ADMIN_SENHA", "SenhaE2E-Testes-123")


@pytest.fixture(scope="session")
def contexto_autenticado(browser, base_url):
    """Faz login uma única vez por SESSÃO INTEIRA de testes (não por
    teste individual, nem por arquivo) - o endpoint de login tem um
    limite de 5 tentativas por minuto por IP (rate limit deliberado
    contra força bruta, ver backend/app/core/rate_limit.py); com a
    suíte crescendo para cobrir mais fluxos, repetir login a cada
    teste esgotaria esse limite rápido (foi exatamente esse problema,
    encontrado e corrigido quando a suíte ainda tinha só um teste).

    O contexto do navegador retornado aqui já carrega o cookie de
    sessão autenticado - reaproveitado por todos os testes da
    execução via a fixture `pagina_logada` abaixo, que só abre uma
    página nova dentro dele, sem logar de novo."""
    context = browser.new_context(base_url=base_url)
    page = context.new_page()
    page.goto("/login.html")
    page.fill("#email", EMAIL_ADMIN_E2E)
    page.fill("#senha", SENHA_ADMIN_E2E)
    page.click("#btnEntrar")
    page.wait_for_url("**/home.html", timeout=10_000)
    page.close()
    yield context
    context.close()


@pytest.fixture
def pagina_logada(contexto_autenticado):
    """Página nova dentro do contexto já autenticado (uma aba/página
    própria por teste, para não vazar estado de UI entre testes -
    ex.: um formulário meio preenchido de um teste anterior), mas sem
    precisar logar de novo - reaproveita o cookie de sessão já
    presente no contexto compartilhado."""
    page = contexto_autenticado.new_page()
    yield page
    page.close()
