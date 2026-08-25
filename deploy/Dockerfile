# Imagem única combinando backend (FastAPI/uvicorn) e frontend (nginx),
# usada SÓ para o deploy no Render (free tier). O desenvolvimento local
# continua usando docker-compose.yml, com backend e frontend como
# containers separados - mais prático para iterar. Ver DEPLOY.md.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev nginx gettext-base \
    && rm -rf /var/lib/apt/lists/*

# --- Backend ---------------------------------------------------------
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
RUN chmod +x entrypoint.sh

# --- Frontend (servido pelo nginx do sistema) -------------------------
COPY frontend/*.html /usr/share/nginx/html/
COPY frontend/css/ /usr/share/nginx/html/css/
COPY frontend/js/ /usr/share/nginx/html/js/
COPY frontend/img/ /usr/share/nginx/html/img/
COPY frontend/favicon-16.png frontend/favicon-32.png frontend/apple-touch-icon.png /usr/share/nginx/html/

COPY deploy/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY deploy/start.sh /start.sh
RUN chmod +x /start.sh

# Render injeta a porta pública real via $PORT em tempo de execução
# (padrão 10000) - este EXPOSE é só documentação, não trava a porta.
EXPOSE 10000

WORKDIR /app
CMD ["/start.sh"]
