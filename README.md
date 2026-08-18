# SIAMP - Sistema de Otimização de Produção e Passagem de Turno

Plataforma desenvolvida para digitalização e automação do processo de fechamento de turno no setor de Injeção Plástica, eliminando registros em papel e integrando dados operacionais a dashboards analíticos.

## 🚀 Funcionalidades Principais

- **Autenticação por usuário:** login com e-mail/senha (JWT), sem cadastro público — contas são criadas por um administrador.
- **Controle de acesso por perfil:** `ADMIN`, `SUPERVISOR` e `OPERADOR`, com permissões diferentes em cada tela.
- **Registro Operacional Ágil:** apontamento por injetora (hora a hora), produção executada, paradas e retomadas, por turno (1º, 2º ou 3º).
- **Injetoras configuráveis:** o número de máquinas não é fixo no código — administradores e supervisores cadastram, editam e ativam/desativam injetoras pela própria interface, e as abas de apontamento são geradas automaticamente a partir desse cadastro.
- **Gestão de usuários:** administradores cadastram novos usuários (operador, supervisor ou admin) e podem ativar/desativar contas.
- **Assinatura Digital de Turno:** fechamento de turno vinculado ao usuário autenticado, com cálculo automático de KPIs (produção total, minutos parados, eficiência OEE).
- **Histórico de Turnos:** listagem dos turnos encerrados com produção total, eficiência e status, com download do relatório em PDF direto pela tela.
- **Relatórios em PDF sob demanda:** gerados a partir dos dados reais do turno a qualquer momento (não dependem de e-mail configurado).
- **Dashboard Analítico:** KPIs gerais, gráfico de produção por injetora e um diagnóstico de risco operacional baseado em um modelo de Machine Learning (scikit-learn).
- **Registro de Paradas:** paradas avulsas por máquina/turno, com motivo e categoria.

## 🛠️ Tecnologias

- **Backend:** Python 3.12 + FastAPI, SQLAlchemy, Alembic
- **Frontend:** HTML5/CSS3/JavaScript + Bootstrap (páginas estáticas, servidas via Nginx)
- **Banco de Dados:** PostgreSQL
- **Relatórios:** ReportLab (PDF)
- **Autenticação:** JWT (`python-jose` + `passlib`/`bcrypt`), login em `/api/v1/auth/login`
- **IA / Analytics:** scikit-learn (diagnóstico de risco operacional no dashboard)

## 🏁 Como Executar o Projeto

```bash
# 1. Clone o repositório
git clone https://github.com/alexnascimento1980/siamp.git
cd siamp

# 2. Configurar variáveis de ambiente
cp .env.example .env
# Edite o .env e defina POSTGRES_PASSWORD e JWT_SECRET_KEY
# (gere uma chave forte com: python -c "import secrets; print(secrets.token_urlsafe(64))")

# 3. Execução via Docker Compose (Recomendado)
docker compose up --build
```

Ao subir, o backend aplica automaticamente as migrations do Alembic e,
se `SEED_ON_START=true` (padrão no `.env.example`), carrega os dados
de exemplo em `database/seeds.sql`.

- API: http://localhost:8000 (docs interativos em `/docs`)
- Frontend: http://localhost:8090

> **Porta ocupada?** Se `8090` já estiver em uso na sua máquina, altere
> o mapeamento em `docker-compose.yml` (serviço `frontend`, chave
> `ports`) para outra porta livre, e atualize `CORS_ORIGINS` no `.env`
> para incluir a nova origem (ex. `http://localhost:8091`).

### Criando o primeiro usuário (administrador)

Não há endpoint público de cadastro (por design — criar contas é uma
operação sensível). Crie o primeiro usuário (admin) com o script
idempotente `create_admin` (pode rodar mais de uma vez sem risco —
se o e-mail já existir, ele só avisa e não faz nada):

```bash
docker compose exec backend_api python -m app.scripts.create_admin \
    --nome "Admin" \
    --email admin@empresa.com \
    --senha "troque-esta-senha"
```

A partir daí, faça login em `http://localhost:8090/login.html` e use a
tela **Usuários** (visível só para ADMIN) para cadastrar os demais
usuários da equipe — não é mais necessário repetir o comando acima.

> **Perdeu o usuário depois de reiniciar o projeto?** Os dados do
> Postgres ficam num volume Docker (`pgdata`) que sobrevive a
> `docker compose down` / `docker compose up` normalmente. Só
> `docker compose down -v` remove esse volume (e junto, todo o banco,
> inclusive os usuários) — use `-v` apenas quando quiser mesmo resetar
> o ambiente do zero.

### Envio de relatório por e-mail (opcional)

Ao fechar um turno, o SIAMP tenta enviar o PDF do relatório por e-mail
em background (não bloqueia o fechamento do turno em si). Isso só
acontece se `SMTP_USER`, `SMTP_PASS` e `REPORT_RECIPIENTS` estiverem
configurados no `.env` — sem eles, o envio é simplesmente pulado (não
é erro).

```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu-email@empresa.com
SMTP_PASS=sua-senha-de-app
REPORT_RECIPIENTS=gerente.producao@empresa.com,supervisao@empresa.com
```

> **Usando Gmail?** É necessário gerar uma ["senha de
> app"](https://myaccount.google.com/apppasswords) — a senha normal da
> conta Google não funciona para SMTP via terceiros, mesmo com a senha
> certa (o Gmail bloqueia por segurança).

Depois de configurar, valide sem precisar fechar um turno de verdade:

```bash
docker compose exec backend_api python -m app.scripts.testar_email --para seu-email@empresa.com
```

Se der erro, o script já indica a causa mais provável (credenciais
erradas, servidor/porta incorretos etc.) — os mesmos detalhes também
ficam registrados no log do container (`docker compose logs backend_api`)
sempre que um envio de relatório real falhar.

### Perfis de usuário

| Perfil       | Apontamento / Histórico / Dashboard | Gestão de Máquinas | Gestão de Usuários |
| ------------ | ----------------------------------- | ------------------ | ------------------ |
| `OPERADOR`   | ✅                                  | ❌                 | ❌                 |
| `SUPERVISOR` | ✅                                  | ✅                 | ❌                 |
| `ADMIN`      | ✅                                  | ✅                 | ✅                 |

O frontend esconde os links conforme o perfil, mas a permissão de
verdade é sempre revalidada pelo backend em cada endpoint.

### Cadastrando injetoras

O número de injetoras não é fixo: administradores e supervisores
cadastram novas máquinas na tela **Máquinas** (número, descrição,
cavidades e ciclo padrão). Elas aparecem automaticamente como abas na
tela de apontamento assim que cadastradas.

### Rodando os testes

```bash
cd backend
pip install -r requirements-dev.txt
pytest -v
```

#teste
