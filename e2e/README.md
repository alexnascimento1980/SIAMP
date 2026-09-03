# Testes E2E (ponta a ponta)

Cobrem os fluxos mais usados no dia a dia do sistema através da
interface real, num navegador de verdade (Playwright) - diferente da
suíte em `backend/tests/`, que testa a lógica de negócio isoladamente
via `TestClient`, sem navegador nem frontend envolvido.

Escopo atual:
- **`test_fluxo_critico.py`**: apontar produção de um turno, fechar o
  turno, baixar e confirmar o relatório em PDF.
- **`test_ordens_producao.py`**: cadastro manual de uma Ordem de
  Produção.
- **`test_usuarios.py`**: cadastro de usuário e proteção de conta
  contra exclusão/desativação acidental (confirma que os botões
  destrutivos ficam desabilitados na própria tela, não só bloqueados
  no backend).

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

## Por que login é feito uma única vez por sessão, não por teste

O endpoint de login tem um limite de 5 tentativas por minuto por IP
(rate limit deliberado contra força bruta). Se cada teste fizesse seu
próprio login, rodar a suíte localmente mais de uma ou duas vezes
seguidas em menos de um minuto - bem comum ao depurar algo - esgotaria
esse limite rápido (foi exatamente esse problema, encontrado quando a
suíte ainda tinha só um teste). A fixture `contexto_autenticado`
(`conftest.py`) loga uma única vez por execução inteira da suíte,
reaproveitando o mesmo cookie de sessão em todos os testes - ao
adicionar um novo teste, use a fixture `pagina_logada`, nunca logue
manualmente de novo.

## Por que os dados de seed usados no teste são fixos no código

Os identificadores de máquina/peça usados no teste (`data-numero-
maquina="1"`, "1 - Tube Alimentation 1/2") dependem de dados que já
vêm de `database/seeds.sql` (via `SEED_ON_START=true`). Se algum dia
esses dados de seed mudarem, o teste precisa acompanhar. As
credenciais de login, diferente disso, são configuráveis por variável
de ambiente (ver seção acima) - não fixas no código.
