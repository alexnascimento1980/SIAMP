#!/usr/bin/env sh
set -e

echo "[entrypoint] Aguardando o banco de dados ficar disponível..."
python -c "
import os, sys, time
import psycopg2

url = os.environ['DATABASE_URL'].replace('postgresql+psycopg2', 'postgresql')
for tentativa in range(30):
    try:
        psycopg2.connect(url).close()
        sys.exit(0)
    except Exception as exc:
        print(f'[entrypoint] banco indisponível ({exc}); tentativa {tentativa + 1}/30')
        time.sleep(2)
sys.exit(1)
"

echo "[entrypoint] Aplicando migrations (alembic upgrade head)..."
alembic upgrade head

# Garante a conta admin de bootstrap (protegida contra exclusão/
# desativação) a cada início do container, sem precisar rodar nada
# manualmente no terminal - só ativa se as variáveis estiverem
# definidas, para não mudar o comportamento de quem não usa isso.
if [ -n "${ADMIN_SENHA:-}" ]; then
    echo "[entrypoint] Garantindo conta admin de bootstrap (protegida)..."
    python -m app.scripts.create_admin
fi

if [ "${SEED_ON_START:-false}" = "true" ]; then
    echo "[entrypoint] Carregando dados de seed..."
    python -m app.scripts.seed_db
fi

echo "[entrypoint] Iniciando aplicação..."
exec "$@"
