import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError

from app.api.routes import auth, empresas, metodos_pago, movimientos, proyectos, reportes, salidas, terminales, usuarios
from app.core.config import settings
from app.core.errors import ErrorDominio
from app.core.rate_limit import limiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler = None
    if settings.SCHEDULER_ENABLED:
        from app.jobs.scheduler import iniciar_scheduler

        scheduler = iniciar_scheduler()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


docs = settings.DOCS_ENABLED
app = FastAPI(
    title=settings.APP_NAME,
    description="Control paralelo de entradas y salidas por empresa, cliente (terminal) y proyecto.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if docs else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=False,  # se usa token Bearer, no cookies
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    respuesta = await call_next(request)
    respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
    respuesta.headers.setdefault("X-Frame-Options", "DENY")
    respuesta.headers.setdefault("Referrer-Policy", "no-referrer")
    if not request.url.path.startswith(("/docs", "/openapi.json")):
        respuesta.headers.setdefault("Cache-Control", "no-store")
    if settings.ENVIRONMENT == "production":
        respuesta.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return respuesta


@app.exception_handler(ErrorDominio)
async def manejar_error_dominio(_: Request, exc: ErrorDominio):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detalle})


@app.exception_handler(IntegrityError)
async def manejar_integridad(_: Request, exc: IntegrityError):
    # Respaldo ante carreras (p. ej. dos altas simultáneas con el mismo correo).
    logger.warning("Violación de integridad: %s", exc.orig)
    return JSONResponse(status_code=409, content={"detail": "La operación entra en conflicto con datos existentes"})


@app.exception_handler(Exception)
async def manejar_error_inesperado(_: Request, exc: Exception):
    logger.exception("Error no controlado", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


for modulo in (auth, usuarios, empresas, terminales, proyectos, metodos_pago, movimientos, salidas, reportes):
    app.include_router(modulo.router)


@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok"}
