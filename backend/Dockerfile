FROM python:3.12-slim

WORKDIR /app

# Instalação de dependências do sistema necessárias para compilação,
# geração de PDFs, e extração de dados de Ordem de Produção a partir
# de PDF/foto escaneados (tesseract-ocr + idioma português; poppler
# converte PDF em imagem para o OCR conseguir ler, já que os PDFs
# reais recebidos são digitalizações sem texto selecionável)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-por \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]