#!/usr/bin/env sh
set -e

# Sobe o backend em background, escutando só em 127.0.0.1 (nunca exposto
# diretamente - só o nginx é público). Reaproveita o entrypoint.sh do
# backend, que já espera o banco ficar disponível e roda
# "alembic upgrade head" antes de iniciar o uvicorn.
(
    cd /app/backend
    ./entrypoint.sh uvicorn app.main:app --host 127.0.0.1 --port 8000
) &

# Processa o template do nginx com a porta que o Render injeta (padrão
# 10000 se não vier definida, ex.: rodando localmente para testar esta
# imagem). O filtro restringe a substituição só a $PORT, para não
# corromper as variáveis do próprio nginx no arquivo (ex.: $host, $uri).
export PORT="${PORT:-10000}"
envsubst '${PORT}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

echo "[start] nginx escutando na porta ${PORT}, repassando /api/ para o backend em 127.0.0.1:8000"

# nginx em primeiro plano - é o processo principal do container. Um
# 502 breve em /api/ nos primeiros segundos é esperado: o backend
# ainda está rodando migrations/subindo o uvicorn em paralelo.
exec nginx -g "daemon off;"
