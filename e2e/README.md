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
rodando de verdade). **Não edite nem sobrescreva o `.env` da raiz do
projeto** - ele já tem suas configurações reais (senha do banco,
`JWT_SECRET_KEY`, credenciais de e-mail, sua conta admin protegida).
Suba a stack normalmente, do jeito que você já faz:

```bash
# na raiz do projeto, com o .env que você já tem configurado
docker compose up --build -d
```

Os testes fazem login usando as credenciais das variáveis de ambiente
`E2E_ADMIN_EMAIL`/`E2E_ADMIN_SENHA` - defina-as apontando pra uma
conta ADMIN que já existe no seu banco (ex.: a sua conta admin
protegida), sem precisar criar uma conta nova só pra isso:

```powershell
# PowerShell - troque pelos valores da sua conta admin real
$env:E2E_ADMIN_EMAIL = "seu-email-admin@empresa.com"
$env:E2E_ADMIN_SENHA = "sua-senha-real"

cd e2e
pip install -r requirements.txt
playwright install --with-deps chromium
pytest -v
```

```bash
# bash/Linux/macOS - equivalente
export E2E_ADMIN_EMAIL="seu-email-admin@empresa.com"
export E2E_ADMIN_SENHA="sua-senha-real"
```

Se essas duas variáveis não forem definidas, os testes usam um valor
padrão (`admin-e2e@siamp.test`) que só existe na stack isolada do CI
- rodar localmente sem defini-las vai falhar no login, não porque o
teste esteja quebrado, só porque essa conta não existe no seu banco.

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

## Por que os dados de seed usados no teste são fixos no código

Os identificadores de máquina/peça usados no teste (`data-numero-
maquina="1"`, "1 - Tube Alimentation 1/2") dependem de dados que já
vêm de `database/seeds.sql` (via `SEED_ON_START=true`). Se algum dia
esses dados de seed mudarem, o teste precisa acompanhar. As
credenciais de login, diferente disso, são configuráveis por variável
de ambiente (ver seção acima) - não fixas no código.
