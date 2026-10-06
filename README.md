# Control Bancario

Sistema web para llevar un control paralelo de los ingresos por terminal punto de venta (TPV)
y las salidas de dinero de varias empresas. Calcula automáticamente la comisión del banco según
el porcentaje vigente de cada terminal y mantiene el saldo de cada empresa, con bitácora de
auditoría y reportes en Excel, PDF y CSV.

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

## Seguridad

- Nunca subas `backend/.env`: contiene la `SECRET_KEY` y la conexión a la base de datos.
- Los usuarios que crea `app.seed` son **solo para pruebas**; su contraseña está en el código.
  En un entorno real, crea el primer administrador con `python -m app.cli crear-admin`.
