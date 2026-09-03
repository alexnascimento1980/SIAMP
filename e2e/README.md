# Testes E2E (ponta a ponta)

Cobrem o caminho mais usado no dia a dia do sistema (login → apontar
produção → fechar turno → gerar PDF) através da interface real, num
navegador de verdade (Playwright) - diferente da suíte em
`backend/tests/`, que testa a lógica de negócio isoladamente via
`TestClient`, sem navegador nem frontend envolvido.

As duas suítes têm propósitos diferentes e **não se substituem**: a
do backend é rápida (minutos) e cobre muito mais casos/variações; esta
aqui é mais lenta, cobre menos casos, mas garante que frontend e
backend realmente conversam certo através da interface, do jeito que
uma pessoa usaria.

## Rodando localmente

Precisa da stack completa de pé (não do `TestClient`, da aplicação
rodando de verdade):

```bash
# na raiz do projeto
cp .env.example .env
# edita o .env e preenche ADMIN_EMAIL=admin-e2e@siamp.test e
# ADMIN_SENHA=SenhaE2E-Testes-123 (precisam bater com conftest.py)
docker compose up --build -d

# espera responder em http://localhost:8090, depois:
cd e2e
pip install -r requirements.txt
playwright install --with-deps chromium
pytest -v
```

## Rodando com `--headed` (ver o navegador de verdade, útil para depurar)

```bash
pytest -v --headed --slowmo 300
```

## Por que só um teste, com um único login

O endpoint de login tem um limite de 5 tentativas por minuto por IP
(rate limit deliberado contra força bruta). Rodar a suíte localmente
várias vezes seguidas em menos de um minuto - bem comum ao depurar
algo - esgota esse limite rápido se cada teste fizer seu próprio
login. Por isso a suíte tem um único teste cobrindo o fluxo inteiro,
com um único login, em vez de vários testes pequenos.

## Por que as credenciais e dados de seed são fixos no código

`EMAIL_ADMIN_E2E`/`SENHA_ADMIN_E2E` (em `conftest.py`) e os
identificadores de máquina/peça usados no teste (`data-numero-
maquina="1"`, "1 - Tube Alimentation 1/2") dependem de dados que já
vêm de `database/seeds.sql` (via `SEED_ON_START=true`) e do bootstrap
automático de conta admin (`ADMIN_EMAIL`/`ADMIN_SENHA` no `.env`, ver
`backend/app/scripts/create_admin.py`). Se algum desses três
mudar - o seed, o bootstrap, ou o teste -, os outros dois precisam
acompanhar.
