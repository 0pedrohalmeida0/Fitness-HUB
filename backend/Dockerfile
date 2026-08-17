# ============================================================
# Fitness Hub — Backend Dockerfile
# Multi-stage build com usuário não-root e gcc removido.
# ============================================================

# ----- Stage 1: build dependencies (com gcc pra compilar bcrypt/passlib) -----
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ----- Stage 2: runtime (sem gcc, usuário não-root) -----
FROM python:3.11-slim

WORKDIR /app

# Cria grupo/usuário não-root
RUN groupadd -r --gid 1001 appgroup \
    && useradd -r --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

# Instala as dependências do wheel pré-compilado (sem precisar de gcc)
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels \
    /wheels/*.whl \
    && rm -rf /wheels

# Copia o código (com ownership do appuser)
COPY --chown=appuser:appgroup . .

# Troca pra usuário não-root
USER appuser

# Expõe a porta
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" \
    || exit 1

# Comando padrão
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
