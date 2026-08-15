# SIAMP - Sistema de Otimização de Produção e Passagem de Turno

Plataforma desenvolvida para digitalização e automação do processo de fechamento de turno no setor de Injeção Plástica, eliminando registros em papel e integrando dados operacionais a dashboards analíticos.

## 🚀 Funcionalidades Principais

- **Registro Operacional Ágil:** Interface para tablets com seleção de injetoras, apontamento de horas, ciclo, cavidades e paradas.
- **Assinatura Digital de Turno:** Validação e rastreabilidade na troca de equipes.
- **Processamento & Inteligência:** Consolidação dos dados de produção e métricas de desempenho.
- **Relatórios Automáticos:** Geração e disparo diário de relatórios PDF consolidados por e-mail para a liderança.

## 🛠️ Tecnologias

- **Backend:** Python (FastAPI / Flask)
- **Frontend:** HTML5/CSS3/JavaScript (Bootstrap / React / Vue)
- **Banco de Dados:** MySQL / PostgreSQL
- **Relatórios:** WeasyPrint / ReportLab (Python)

## 🏁 Como Executar o Projeto

```bash
# 1. Clone o repositório
git clone [https://github.com/alexnascimento1980/siamp.git](https://github.com/alexnascimento1980/siamp.git)
cd siamp

# 2. Configurar variáveis de ambiente
cp .env.example .env

# 3. Execução via Docker Compose (Recomendado)
docker-compose up --build
```
