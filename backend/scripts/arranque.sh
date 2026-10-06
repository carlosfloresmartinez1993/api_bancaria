#!/bin/sh
# Arranque en producción (Dockerfile de la raíz / Render).
set -e

# 1. Migraciones pendientes
alembic upgrade head

# 2. Datos de demostración (solo si SEED_DEMO=true y la base está vacía)
if [ "$SEED_DEMO" = "true" ]; then
  python -m app.seed || echo "seed: omitido (la base ya tiene datos)"
fi

# 3. Primer administrador desde ADMIN_CORREO / ADMIN_PASSWORD (solo si no hay usuarios),
#    o restablecer su contraseña con ADMIN_RESTABLECER=true. Un error aquí no impide arrancar.
python -m app.cli inicializar || echo "inicializar: falló; revisa ADMIN_CORREO / ADMIN_PASSWORD"

# 4. API en /api y frontend en /
exec uvicorn app.servidor:servidor --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
