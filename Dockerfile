# ===== Stage 1: Build =====
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependências de build (libpq-dev é necessário para psycopg)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt


# ===== Stage 2: Runtime =====
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar libpq (runtime necessário para psycopg)
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copiar dependências do builder
COPY --from=builder /install /usr/local

# Copiar código da aplicação
COPY main.py .
COPY src/ ./src/
COPY res/ ./res/
COPY static/ ./static/
COPY db/ ./db/

# Expor a porta que o Fly.io usará
ENV PORT=8000
EXPOSE 8000

# Comando padrão do Fly.io
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
