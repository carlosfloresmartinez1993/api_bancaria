# Imagen única para producción: compila el frontend (React) y lo sirve junto con la API.
# La API queda en /api y la aplicación web en /. Ver render.yaml.

# ---------- 1. Frontend ----------
FROM node:25-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 2. Backend + frontend compilado ----------
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIR=/app/static \
    ARCHIVOS_DIR=/app/archivos

WORKDIR /app
RUN useradd --create-home --uid 1000 app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend /frontend/dist ./static
# Facturas con ALMACENAMIENTO=local. En producción conviene un bucket S3 (ver backend/README.md).
RUN mkdir -p /app/archivos && chown app:app /app/archivos

USER app
EXPOSE 8000
CMD ["sh", "scripts/arranque.sh"]
