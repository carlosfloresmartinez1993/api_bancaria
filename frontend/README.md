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

Jerarquía: **Empresa → Cliente (terminal) → Proyecto**, y cada proyecto tiene su % de comisión.

- **Inicio**: entradas netas, comisiones, salidas y saldo; saldo y comisiones por empresa; últimas entradas.
- **Empresas**: solo el nombre es obligatorio; detalle con sus clientes y saldo a una fecha; reasignación (admin).
- **Clientes**: alta, activar/desactivar y detalle con sus **proyectos** (cada uno con historial y cambio de %).
- **Entradas**: captura eligiendo empresa → cliente → proyecto, con método de pago y casilla *Requiere factura*;
  vista previa del % y el neto; corrección y eliminación con motivo (queda en la bitácora).
- **Salidas**: por proyecto, con método de pago; aviso si el saldo del proyecto queda negativo.
- **Reportes**: constructor (elige empresa, marca clientes y proyectos, agrupa por empresa, cliente, proyecto,
  método de pago o detalle) y los demás reportes; todos muestran *Elaborado por* y se descargan en Excel, PDF o CSV.
- **Usuarios** y **Métodos de pago** (admin).
