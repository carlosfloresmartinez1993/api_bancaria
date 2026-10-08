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

## Dependencias

Las versiones están **fijadas** para que cada instalación (tu PC, las pruebas de GitHub y Render) use
exactamente las mismas librerías:

| Archivo | Para qué |
|---|---|
| `requirements.in` | Dependencias directas con rangos aceptados. **Es el que se edita.** |
| `requirements.txt` | Generado: versiones exactas de todo (incluye dependencias indirectas). Lo usan Docker y Render. |
| `requirements-dev.in` / `requirements-dev.txt` | Lo mismo, más las herramientas de pruebas. |

Para agregar o actualizar una librería, edita el `.in` y regenera los `.txt` con [uv](https://docs.astral.sh/uv/):

```bash
uv pip compile requirements.in --universal --python-version 3.13 -o requirements.txt
uv pip compile requirements-dev.in --universal --python-version 3.13 -o requirements-dev.txt
uv pip install -r requirements-dev.txt --python .venv/Scripts/python.exe   # Linux/macOS: .venv/bin/python
pytest
```

Para subir todas a la última versión permitida, agrega `--upgrade` a los dos `uv pip compile`. Dependabot
(ver el README principal) propone estas actualizaciones automáticamente cada semana.

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

- **Jerarquía**: Empresa (opcional) → Cliente (terminal, en la API `/terminales`) → Proyecto. Solo el nombre de la empresa es obligatorio. Entradas y salidas siempre pertenecen a un proyecto.
- **Clientes sin empresa**: un cliente puede no tener empresa. Cada cliente tiene un responsable (`usuario_id`): el de su empresa (una llave compuesta lo garantiza y lo actualiza en cascada al reasignar la empresa) o, sin empresa, el contador que lo registró. En reportes e inicio aparecen como «Sin empresa». Un cliente se puede asociar a una empresa o quitársela (`POST /terminales/{id}/empresa`), con historial (`GET /terminales/{id}/historial-empresa`) y reversión del último cambio (`POST /terminales/{id}/revertir-movimiento`); todo queda en la bitácora (`MOVER_CLIENTE`).
- **Acceso**: un contador ve sus empresas y los clientes de los que es responsable (con o sin empresa) y, por extensión, sus proyectos, entradas y salidas. Un recurso ajeno responde **404** para no revelar que existe. El admin ve todo y puede reasignar empresas.
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

## Facturas (PDF) de las entradas

Cada entrada puede tener **una** factura en PDF (máximo `MAX_DOCUMENTO_MB`, 5 MB por defecto). Subir otra la reemplaza.
La BD guarda solo la **clave** del archivo (`entradas/<id de la entrada>/<aleatorio>.pdf`), su nombre, tamaño y fecha;
el archivo vive en el almacenamiento que elija `ALMACENAMIENTO`:

| `ALMACENAMIENTO` | Dónde | Uso |
|---|---|---|
| `local` (por defecto) | carpeta `ARCHIVOS_DIR` (`./archivos`; en Docker `/app/archivos`) | desarrollo. En Render gratuito se borra en cada despliegue. |
| `s3` | bucket compatible con S3: **Railway Buckets**, Supabase Storage, Cloudflare R2 o AWS S3 | producción |

Variables para `s3`: `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_ENDPOINT_URL` (vacío = AWS),
`S3_REGION` (por defecto `auto`) y, opcional, `S3_PREFIJO` (carpeta dentro del bucket). Si falta alguna obligatoria,
la aplicación no arranca y dice cuál. En Railway: crea un *Bucket* en el proyecto y, en las variables del
servicio, asigna a cada `S3_*` el valor correspondiente que muestra el bucket (nombre, endpoint, región y llaves),
de preferencia como referencia a la variable del bucket para que se actualice sola.

- El bucket debe ser **privado**: el PDF se entrega por `GET /movimientos/{id}/documento` solo a quien puede ver la entrada.
- Se valida que el contenido sea PDF (no basta la extensión) y el nombre se limpia (sin rutas del equipo del usuario).
- Subir, reemplazar y quitar quedan en la bitácora (`SUBIR_DOCUMENTO`, `ELIMINAR_DOCUMENTO`). Al eliminar la entrada
  se borra su archivo.
- Para cambiar de proveedor, copia el contenido del bucket (o de la carpeta) al nuevo con las mismas claves; la BD no cambia.

## Endpoints

| Grupo | Rutas |
|---|---|
| Autenticación | `POST /auth/login`, `GET /auth/me`, `POST /auth/cambiar-password` |
| Usuarios (admin) | `GET/POST /usuarios`, `GET/PATCH /usuarios/{id}`, `POST /usuarios/{id}/activar`, `/desactivar`, `/restablecer-password` |
| Empresas | `GET/POST /empresas`, `GET/PATCH /empresas/{id}`, `GET /empresas/{id}/saldo`, `POST /empresas/{id}/reasignar` (admin) |
| Clientes (terminales) | `GET/POST /terminales`, `GET/PATCH /terminales/{id}`, `POST /terminales/{id}/activar`, `/desactivar`, `GET /terminales/{id}/saldo` |
| Proyectos | `GET/POST /proyectos`, `GET/PATCH /proyectos/{id}`, `POST /proyectos/{id}/activar`, `/desactivar`, `GET/POST /proyectos/{id}/porcentajes`, `GET /proyectos/{id}/porcentaje-vigente`, `GET /proyectos/{id}/saldo` |
| Métodos de pago | `GET /metodos-pago`, `POST /metodos-pago` y `PATCH /metodos-pago/{id}` (admin) |
| Entradas | `GET/POST /movimientos`, `GET/PATCH/DELETE /movimientos/{id}`, `PUT/GET/DELETE /movimientos/{id}/documento` (factura PDF) |
| Salidas | `GET/POST /salidas`, `GET/PATCH/DELETE /salidas/{id}` |
| Reportes | `/reportes/constructor` (empresa, `terminal_id`/`proyecto_id`/`metodo_pago_id` repetibles, `contenido`, `agrupar`, `requiere_factura`, `texto`), `saldos`, `estado-cuenta`, `conciliacion-diaria`, `resumen-mensual`, `auditoria-captura`, `bitacora`, `cierre-diario` |

Todos los reportes aceptan `?formato=json|csv|xlsx|pdf`.

## Diferencias respecto al documento de diseño

- Las vigencias del historial de porcentajes y la fecha de las salidas son de tipo `date`, porque la regla de negocio es por día. Las salidas guardan además `fecha_registro` (timestamp).
- Se agregó eliminar movimientos y salidas (para capturas duplicadas), con registro completo en la bitácora.
- El catálogo de acciones de la bitácora es cerrado (enum) e incluye `EDITAR_USUARIO`, `CAMBIO_PASSWORD`, `ELIMINAR_MOVIMIENTO` y `ELIMINAR_SALIDA`.
- Las llaves primarias son UUID v4, generadas por la aplicación y, como respaldo, por PostgreSQL (`gen_random_uuid()`).
