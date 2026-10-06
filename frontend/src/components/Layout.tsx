import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import { useAuth } from "../auth/AuthContext";
import { cn } from "../lib/cn";
import { Icono, type NombreIcono } from "./Icono";

interface Enlace {
  a: string;
  texto: string;
  icono: NombreIcono;
  soloAdmin?: boolean;
}

const ENLACES: Enlace[] = [
  { a: "/", texto: "Inicio", icono: "inicio" },
  { a: "/empresas", texto: "Empresas", icono: "empresas" },
  { a: "/clientes", texto: "Clientes", icono: "terminales" },
  { a: "/movimientos", texto: "Entradas", icono: "movimientos" },
  { a: "/salidas", texto: "Salidas", icono: "salidas" },
  { a: "/reportes", texto: "Reportes", icono: "reportes" },
  { a: "/usuarios", texto: "Usuarios", icono: "usuarios", soloAdmin: true },
  { a: "/metodos-pago", texto: "Métodos de pago", icono: "pago", soloAdmin: true },
];

function Navegacion({ onNavegar }: { onNavegar?: () => void }) {
  const { usuario, esAdmin, salir } = useAuth();
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 shrink-0 items-center gap-2.5 px-5">
        <img src="/favicon.svg" alt="" className="size-8" />
        <div className="leading-tight">
          <p className="text-sm font-semibold text-white">Integra</p>
          <p className="text-xs text-teal-200/80">Control de Clientes</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {ENLACES.filter((e) => !e.soloAdmin || esAdmin).map((e) => (
          <NavLink
            key={e.a}
            to={e.a}
            end={e.a === "/"}
            onClick={onNavegar}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive ? "bg-teal-800 text-white" : "text-teal-100/80 hover:bg-teal-800/60 hover:text-white",
              )
            }
          >
            <Icono nombre={e.icono} />
            {e.texto}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-teal-800 p-3">
        <div className="px-3 pb-3">
          <p className="truncate text-sm font-medium text-white">
            {usuario?.nombre} {usuario?.apellidos}
          </p>
          <p className="truncate text-xs text-teal-200/80">
            {usuario?.correo} · {esAdmin ? "Administrador" : "Contador"}
          </p>
        </div>
        <NavLink
          to="/perfil"
          onClick={onNavegar}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium",
              isActive ? "bg-teal-800 text-white" : "text-teal-100/80 hover:bg-teal-800/60 hover:text-white",
            )
          }
        >
          <Icono nombre="llave" />
          Cambiar contraseña
        </NavLink>
        <button
          type="button"
          onClick={salir}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-teal-100/80 hover:bg-teal-800/60 hover:text-white"
        >
          <Icono nombre="salir" />
          Cerrar sesión
        </button>
      </div>
    </div>
  );
}

export function Layout() {
  const [menuAbierto, setMenuAbierto] = useState(false);
  const { pathname } = useLocation();
  const actual = ENLACES.find((e) => (e.a === "/" ? pathname === "/" : pathname.startsWith(e.a)));

  return (
    <div className="min-h-dvh bg-slate-50">
      {/* Menú lateral fijo en escritorio */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 bg-teal-900 lg:block">
        <Navegacion />
      </aside>

      {/* Menú deslizable en móvil */}
      {menuAbierto && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setMenuAbierto(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 bg-teal-900 shadow-xl">
            <Navegacion onNavegar={() => setMenuAbierto(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur lg:hidden">
          <button
            type="button"
            onClick={() => setMenuAbierto(true)}
            className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100"
            aria-label="Abrir menú"
          >
            <Icono nombre="menu" />
          </button>
          <span className="text-sm font-semibold text-slate-900">{actual?.texto ?? "Control de Clientes"}</span>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
