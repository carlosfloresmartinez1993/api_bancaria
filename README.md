# Control Bancario

Sistema web para llevar un control paralelo de las entradas y salidas de dinero de varias
empresas, organizadas en **Empresa → Cliente (terminal) → Proyecto**. Cada proyecto tiene su
propio porcentaje de comisión; el sistema calcula el neto con el % vigente del día, lleva el saldo
por proyecto, cliente y empresa, registra el método de pago y si la entrada requiere factura, y
genera reportes a la medida en Excel, PDF y CSV con bitácora de auditoría.

| Carpeta | Contenido |
|---|---|
| [`backend/`](backend/) | API REST con FastAPI, SQLAlchemy 2, Alembic y PostgreSQL |
| [`frontend/`](frontend/) | Interfaz web con React 19, TypeScript, Vite y Tailwind CSS v4 |
| [`docs/`](docs/) | Manual de usuario |

## Requisitos

- Python 3.12 o superior
- Node.js 20 o superior
- PostgreSQL 16

## Puesta en marcha (desarrollo)

**Backend**, desde `backend/`:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows (en Linux/macOS: .venv/bin/python)
cp .env.example .env                                       # y edita DATABASE_URL y SECRET_KEY
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m app.seed                           # opcional: datos de prueba
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

**Frontend**, desde `frontend/`:

```bash
npm install
npm run dev
```

Abre http://localhost:5173. En desarrollo, Vite redirige `/api` al backend en el puerto 8000.

Más detalles en [`backend/README.md`](backend/README.md) y [`frontend/README.md`](frontend/README.md).

## Publicar en Render

El repositorio incluye un [`Dockerfile`](Dockerfile) que compila el frontend y lo sirve junto con la API
(la API en `/api`, la aplicación en `/`), y un Blueprint [`render.yaml`](render.yaml) que crea el servicio
web y la base de datos PostgreSQL.

1. Sube el repositorio a GitHub.
2. En [Render](https://render.com): **New → Blueprint** y elige el repositorio.
3. Render pedirá `ADMIN_CORREO` y `ADMIN_PASSWORD` (mínimo 10 caracteres, con letras y números):
   con ellos se crea el primer administrador al arrancar. La `SECRET_KEY` se genera sola.
4. Al terminar el despliegue, la aplicación queda en `https://control-bancario-XXXX.onrender.com`.

Para una demostración con datos de prueba, cambia `SEED_DEMO` a `true` en el servicio
**antes del primer arranque** (los datos solo se cargan si la base está vacía).

Limitaciones del plan gratuito:

- El servicio se duerme tras unos minutos sin uso; la primera visita tarda en despertarlo.
- La base de datos gratuita tiene vigencia limitada; revisa las condiciones actuales de Render.
- Por lo anterior, el cierre diario automático está desactivado (`SCHEDULER_ENABLED=false`);
  se puede enviar a mano desde **Reportes → Cierre diario**.

## Seguridad

- Nunca subas `backend/.env`: contiene la `SECRET_KEY` y la conexión a la base de datos.
- Los usuarios que crea `app.seed` son **solo para pruebas**; su contraseña está en el código.
  En un entorno real, crea el primer administrador con `python -m app.cli crear-admin`.
