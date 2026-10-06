# Control Bancario — Frontend

Interfaz web de la API bancaria (carpeta `../backend`). Hecha con **React 19 + TypeScript + Vite + Tailwind CSS v4**,
**React Router** para la navegación y **TanStack Query** para las peticiones y la caché.

## Requisitos

- Node.js 20 o superior
- El backend corriendo en `http://localhost:8000`

## Arranque en desarrollo

```bash
npm install
npm run dev
```

Abre http://localhost:5173. En desarrollo, Vite redirige `/api/*` al backend (ver `vite.config.ts`),
así que no hace falta configurar CORS. Si el backend está en otra dirección, copia `.env.example` a `.env`
y cambia `BACKEND_URL`.

## Build de producción

```bash
npm run build      # revisa tipos y genera dist/
npm run preview    # sirve dist/ localmente
```

En producción, sirve `dist/` con el mismo servidor que hace de proxy a la API bajo `/api`
(p. ej. nginx), o define `VITE_API_URL` con la URL completa de la API y agrega el dominio del
frontend a `CORS_ORIGINS` en el backend. Como es una SPA, todas las rutas deben responder con `index.html`.

## Estructura

```
src/
├── main.tsx              → proveedores (Query, Router, Toast, Auth)
├── App.tsx               → rutas y protección por sesión/rol
├── auth/AuthContext.tsx  → login, token JWT, usuario actual, cierre por 401
├── lib/
│   ├── api.ts            → cliente fetch: token, errores de FastAPI, descargas
│   ├── types.ts          → tipos de los esquemas del backend
│   ├── queries.ts        → catálogos (empresas, terminales, usuarios)
│   ├── filtros.ts        → filtros guardados en la URL
│   └── format.ts         → moneda MXN, fechas, porcentajes
├── components/
│   ├── ui.tsx            → botones, campos, tablas, modal, avisos, paginación
│   ├── Layout.tsx        → menú lateral (responsive)
│   ├── Selectores.tsx    → selects de empresa / terminal / usuario
│   └── formularios/      → movimiento, salida, terminal, empresa, eliminación con motivo
└── pages/                → Inicio, Empresas, EmpresaDetalle, Terminales, Movimientos,
                            Salidas, Reportes, Usuarios (admin), Perfil, Login
```

## Funcionalidad

- **Inicio**: saldo total, saldo por empresa (aviso de saldos negativos) y últimos movimientos.
- **Empresas**: alta/edición, detalle con saldo a una fecha, terminales, PDFs y logo; reasignación (admin).
- **Terminales**: alta con % inicial, activar/desactivar, historial y cambio de porcentaje
  (avisa cuántos movimientos se recalcularon).
- **Movimientos**: captura con vista previa del % vigente y el neto, "guardar y capturar otro",
  corrección y eliminación con motivo (queda en la bitácora).
- **Salidas**: registro con aviso si el saldo queda negativo, corrección y eliminación con motivo.
- **Reportes**: los 12 reportes del backend con sus filtros, vista en tabla y descarga en Excel, PDF o CSV;
  envío del cierre diario por correo (admin).
- **Usuarios** (admin): alta, edición, activar/desactivar, restablecer contraseña.
- Un contador solo ve sus empresas; las opciones de admin se ocultan según el rol.
