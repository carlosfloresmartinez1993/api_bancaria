FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN useradd --create-home --uid 1000 app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER app
EXPOSE 8000

# Aplica migraciones pendientes y arranca la API.
# --proxy-headers: usar la IP real del cliente cuando hay un proxy (nginx) delante;
# definir FORWARDED_ALLOW_IPS con la IP del proxy.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
