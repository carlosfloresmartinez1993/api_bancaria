# API Bancaria — control paralelo de entradas y salidas

API REST en **FastAPI + SQLAlchemy 2 + PostgreSQL** que reemplaza el Excel donde se llevan los ingresos de las terminales bancarias de cada empresa y las salidas de dinero, organizados en **Empresa → Cliente (terminal) → Proyecto**; cada proyecto tiene su propio % de comisión. No ejecuta operaciones bancarias: las transferencias reales las hace el equipo contable y aquí solo se registran para saber cuánto debería tener la cuenta de cada empresa.

## Arranque rápido con Docker

```bash
cp .env.example .env          # editar SECRET_KEY (openssl rand -hex 32) y el SMTP
docker compose up -d --build  # aplica las migraciones al arrancar
docker compose exec api python -m app.cli crear-admin --correo admin@empresa.mx --nombre Ana --apellidos "López"
```

La documentación interactiva queda en `http://localhost:8000/docs` (desactivarla en producción con `DOCS_ENABLED=false`).

## Desarrollo local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                       # apuntar DATABASE_URL a tu PostgreSQL
alembic upgrade head
python -m app.cli crear-admin --correo admin@empresa.mx --nombre Ana --apellidos "López"
uvicorn app.main:app --reload
```

### Pruebas

Requieren una base de datos PostgreSQL vacía para pruebas (se borra y recrea en cada corrida):

```bash
createdb banco_test
TEST_DATABASE_URL=postgresql+psycopg://banco:banco@localhost:5432/banco_test pytest
```

Cubren autenticación, aislamiento entre contadores, cálculo de porcentajes por fecha, saldos por empresa/cliente/proyecto, métodos de pago, ediciones con bitácora, constructor de reportes, exportaciones y cierre diario.

## Estructura

```
app/
  core/        configuración, seguridad (JWT, bcrypt), errores, rate limit, zona horaria
  db/          base declarativa (PK UUID) y sesión
  models/      Usuario, Empresa, TerminalBancaria (cliente), Proyecto, HistorialPorcentajeProyecto,
               MetodoPago, Movimiento (entrada), Salida, BitacoraAuditoria
  schemas/     modelos Pydantic de entrada y salida
  services/    reglas de negocio: acceso, porcentajes, saldos, métodos de pago, reportes, exportación, cierre, correo
  api/routes/  endpoints
  jobs/        programador del cierre diario
  cli.py       crear-admin y cierre manual
alembic/       migraciones
tests/
```

## Reglas de negocio implementadas

- **Jerarquía**: Empresa → Cliente (terminal, en la API `/terminales`) → Proyecto. Solo el nombre de la empresa es obligatorio. Entradas y salidas siempre pertenecen a un proyecto.
- **Acceso**: cada empresa guarda en `usuario_id` quién la registró. Un contador solo ve y opera sus empresas y, por extensión, sus clientes, proyectos, entradas y salidas. Un recurso ajeno responde **404** para no revelar que existe. El admin ve todo y puede reasignar empresas.
- **Porcentaje**: se aplica el vigente en la **fecha del movimiento** (no el de la captura), tomado del historial del **proyecto** (`HistorialPorcentajeProyecto`), y se guarda en `porcentaje_aplicado`. Un cambio de % con fecha pasada recalcula los movimientos desde esa fecha. No se pueden reescribir periodos anteriores al vigente.
- **Neto**: `monto_neto` es una columna generada por PostgreSQL; la API nunca lo escribe.
- **Saldo**: no se almacena. `saldo = Σ netos − Σ salidas`, calculado al consultar por proyecto, cliente o empresa (`/proyectos|terminales|empresas/{id}/saldo`).
- **Salidas**: no se bloquean aunque el saldo del proyecto quede negativo; la respuesta incluye una advertencia.
- **Métodos de pago**: catálogo (Transferencia, Depósito, Efectivo) que el admin puede ampliar o desactivar; entradas y salidas indican el suyo.
- **Factura**: cada entrada lleva `requiere_factura` (por ahora solo se registra y se filtra).
- **Correcciones**: el dueño de la empresa o un admin pueden editar o eliminar movimientos y salidas sin límite de tiempo. Cada cambio guarda en la bitácora el antes, el después y un motivo opcional.
- **Clientes y proyectos inactivos**: no aceptan capturas nuevas; lo ya capturado se conserva y se puede corregir.
- **Reportes**: todos indican al final *Elaborado por* (nombre y apellidos de quien los genera).

## Seguridad

- Contraseñas con **bcrypt** (12 rondas); mínimo 10 caracteres con letras y números.
- **JWT** firmados (HS256) con expiración configurable. En cada petición se verifica que el usuario siga activo, así que desactivarlo corta su acceso de inmediato.
- Login con **límite de intentos por IP** (`LOGIN_RATE_LIMIT`, 5/minuto por defecto) y tiempo de respuesta uniforme para no revelar qué correos existen.
- **Bitácora inmutable**: un trigger de PostgreSQL rechaza UPDATE y DELETE sobre `bitacora_auditoria`.
- Cabeceras `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Cache-Control: no-store` y HSTS en producción.
- CORS restringido a los orígenes de `CORS_ORIGINS`. Errores internos sin detalles técnicos hacia el cliente.
- En producción: servir detrás de HTTPS, `DOCS_ENABLED=false`, `ENVIRONMENT=production` y una `SECRET_KEY` aleatoria propia.

## Cierre diario

Calcula con una consulta los movimientos del día agrupados por contador, lo envía por correo a los admins activos (con PDF adjunto) y registra `CIERRE_ENVIADO` o `CIERRE_ERROR` en la bitácora, con los totales enviados.

- Automático con `SCHEDULER_ENABLED=true` en **un solo proceso**, a la hora `CIERRE_HORA:CIERRE_MINUTO` de `TIMEZONE`.
- Alternativa con cron: `python -m app.cli cierre`.
- Manual por API: `POST /reportes/cierre-diario/enviar?fecha=AAAA-MM-DD&forzar=true`.
- Un candado de PostgreSQL impide envíos duplicados si dos procesos lo intentan a la vez, y no se reenvía un día ya enviado salvo con `forzar`.

## Endpoints

| Grupo | Rutas |
|---|---|
| Autenticación | `POST /auth/login`, `GET /auth/me`, `POST /auth/cambiar-password` |
| Usuarios (admin) | `GET/POST /usuarios`, `GET/PATCH /usuarios/{id}`, `POST /usuarios/{id}/activar`, `/desactivar`, `/restablecer-password` |
| Empresas | `GET/POST /empresas`, `GET/PATCH /empresas/{id}`, `GET /empresas/{id}/saldo`, `POST /empresas/{id}/reasignar` (admin) |
| Clientes (terminales) | `GET/POST /terminales`, `GET/PATCH /terminales/{id}`, `POST /terminales/{id}/activar`, `/desactivar`, `GET /terminales/{id}/saldo` |
| Proyectos | `GET/POST /proyectos`, `GET/PATCH /proyectos/{id}`, `POST /proyectos/{id}/activar`, `/desactivar`, `GET/POST /proyectos/{id}/porcentajes`, `GET /proyectos/{id}/porcentaje-vigente`, `GET /proyectos/{id}/saldo` |
| Métodos de pago | `GET /metodos-pago`, `POST /metodos-pago` y `PATCH /metodos-pago/{id}` (admin) |
| Entradas | `GET/POST /movimientos`, `GET/PATCH/DELETE /movimientos/{id}` |
| Salidas | `GET/POST /salidas`, `GET/PATCH/DELETE /salidas/{id}` |
| Reportes | `/reportes/constructor` (empresa, `terminal_id`/`proyecto_id`/`metodo_pago_id` repetibles, `contenido`, `agrupar`, `requiere_factura`, `texto`), `saldos`, `estado-cuenta`, `conciliacion-diaria`, `resumen-mensual`, `auditoria-captura`, `bitacora`, `cierre-diario` |

Todos los reportes aceptan `?formato=json|csv|xlsx|pdf`.

## Diferencias respecto al documento de diseño

- Las vigencias del historial de porcentajes y la fecha de las salidas son de tipo `date`, porque la regla de negocio es por día. Las salidas guardan además `fecha_registro` (timestamp).
- Se agregó eliminar movimientos y salidas (para capturas duplicadas), con registro completo en la bitácora.
- El catálogo de acciones de la bitácora es cerrado (enum) e incluye `EDITAR_USUARIO`, `CAMBIO_PASSWORD`, `ELIMINAR_MOVIMIENTO` y `ELIMINAR_SALIDA`.
- Las llaves primarias son UUID v4, generadas por la aplicación y, como respaldo, por PostgreSQL (`gen_random_uuid()`).
