# SIAMP - Sistema de Otimização de Produção e Passagem de Turno

Plataforma desenvolvida para digitalização e automação do processo de fechamento de turno no setor de Injeção Plástica, eliminando registros em papel e integrando dados operacionais a dashboards analíticos.

## 🚀 Funcionalidades Principais

- **Registro Operacional Ágil:** Interface para tablets com seleção de injetoras, apontamento de horas, ciclo, cavidades e paradas.
- **Assinatura Digital de Turno:** Validação e rastreabilidade na troca de equipes.
- **Processamento & Inteligência:** Consolidação dos dados de produção e métricas de desempenho.
- **Relatórios Automáticos:** Geração e disparo diário de relatórios PDF consolidados por e-mail para a liderança.

## 🛠️ Tecnologias

- **Backend:** Python 3.11 + FastAPI, SQLAlchemy, Alembic
- **Frontend:** HTML5/CSS3/JavaScript + Bootstrap (páginas estáticas, servidas via Nginx)
- **Banco de Dados:** PostgreSQL
- **Relatórios:** ReportLab (PDF)
- **Autenticação:** JWT (login por e-mail/senha em `/api/v1/auth/login`)

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
docker-compose up --build
```

Ao subir, o backend aplica automaticamente as migrations do Alembic e,
se `SEED_ON_START=true` (padrão no `.env.example`), carrega os dados
de exemplo em `database/seeds.sql`.

- API: http://localhost:8000 (docs interativos em `/docs`)
- Frontend: http://localhost:8080

### Criando o primeiro usuário

Não há endpoint público de cadastro (por design — o registro de
turno é uma operação sensível). Crie o primeiro usuário direto no
banco, por exemplo:

```bash
docker compose exec backend_api python -c "
from app.core.database import SessionLocal
from app.core.security import gerar_hash_senha
from app.models.usuario import Usuario

db = SessionLocal()
db.add(Usuario(nome='Admin', email='admin@empresa.com',
                senha_hash=gerar_hash_senha('troque-esta-senha'),
                perfil='ADMIN'))
db.commit()
"
```

### Rodando os testes

```bash
cd backend
pip install -r requirements.txt pytest
pytest -v
```